import re
import secrets
import threading
import time
import os

import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from trading_sim import TradingSimulation

GAME_DURATION_SECONDS = 120
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{2,20}$")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ignite123")
BOT_PREFIX = "noobot"


class OrderRequest(BaseModel):
    side: str
    quantity: int


class RandomOrderRequest(BaseModel):
    num_orders: int = 5000
    delay: float = 0.02
    prefix: str | None = None


class AdminPasswordRequest(BaseModel):
    password: str


class SeedPlayersRequest(BaseModel):
    count: int = 100
    prefix: str = BOT_PREFIX


class GameRound:
    def __init__(self):
        self.lock = threading.Lock()
        self.status = "waiting"
        self.started_at = None
        self.ends_at = None
        self.active_players = set()
        self.round_id = 1

    def snapshot(self):
        now = time.time()
        seconds_remaining = 0
        if self.status == "running" and self.ends_at is not None:
            seconds_remaining = max(0, int(self.ends_at - now))

        return {
            "status": self.status,
            "round_id": self.round_id,
            "started_at": self.started_at,
            "ends_at": self.ends_at,
            "seconds_remaining": seconds_remaining,
            "duration_seconds": GAME_DURATION_SECONDS,
            "active_players": sorted(self.active_players),
        }


sim = TradingSimulation(num_traders=0)
sim.start_simulation()
game_round = GameRound()

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=secrets.token_hex(32))
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def normalize_username(username: str) -> str:
    return username.strip()


def username_exists(username: str) -> bool:
    normalized = normalize_username(username).lower()
    return any(trader.name.lower() == normalized for trader in sim.traders)


def validate_username(username: str) -> str | None:
    normalized = normalize_username(username)
    if not USERNAME_PATTERN.match(normalized):
        return None
    if normalized.lower().startswith(BOT_PREFIX):
        return None
    return normalized


def sync_game_round():
    with game_round.lock:
        if game_round.status == "running" and game_round.ends_at is not None:
            if time.time() >= game_round.ends_at:
                game_round.status = "finished"


def reset_round_state():
    with game_round.lock:
        game_round.status = "waiting"
        game_round.started_at = None
        game_round.ends_at = None
        game_round.round_id += 1
    sim.reset_traders()


def reset_all_state():
    with game_round.lock:
        game_round.status = "waiting"
        game_round.started_at = None
        game_round.ends_at = None
        game_round.active_players = set()
        game_round.round_id += 1
    sim.clear_traders()


def add_player_to_waiting_round(username: str):
    with game_round.lock:
        if game_round.status == "finished":
            game_round.status = "waiting"
            game_round.started_at = None
            game_round.ends_at = None
            game_round.active_players = set()
            game_round.round_id += 1
            sim.reset_traders()

        if game_round.status == "running" and username not in game_round.active_players:
            return False, "A round is already running. Wait for the next 2-minute game."

        game_round.active_players.add(username)
        return True, None


def start_round_if_needed():
    with game_round.lock:
        if game_round.status != "waiting":
            return
        if not game_round.active_players:
            return

        game_round.status = "running"
        game_round.started_at = time.time()
        game_round.ends_at = game_round.started_at + GAME_DURATION_SECONDS


def start_round():
    with game_round.lock:
        if game_round.status != "waiting":
            return False, "Round is not in waiting state"
        if not game_round.active_players:
            return False, "No registered players to start the round"

        game_round.status = "running"
        game_round.started_at = time.time()
        game_round.ends_at = game_round.started_at + GAME_DURATION_SECONDS
        return True, None


def get_logged_in_user(request: Request) -> str | None:
    return request.session.get("username")


def is_admin_authenticated(request: Request) -> bool:
    return bool(request.session.get("is_admin"))


def require_logged_in_user(request: Request) -> str | None:
    sync_game_round()
    return get_logged_in_user(request)


def get_active_leaderboard_entries(limit: int | None = 10):
    sync_game_round()
    snapshot = game_round.snapshot()
    active_names = set(snapshot["active_players"])
    leaderboard = sim.get_leaderboard()
    if active_names:
        leaderboard = [trader for trader in leaderboard if trader.name in active_names]
    else:
        leaderboard = []

    if limit is not None:
        leaderboard = leaderboard[:limit]

    return [
        {
            "name": trader.name,
            "cash": trader.cash,
            "holdings": trader.holdings,
            "portfolio_value": trader.portfolio_value,
        }
        for trader in leaderboard
    ]


def get_active_leaderboard():
    return get_active_leaderboard_entries(limit=14)


def get_active_player_profile(username: str | None):
    if not username:
        return None

    sync_game_round()
    snapshot = game_round.snapshot()
    active_names = set(snapshot["active_players"])
    leaderboard = sim.get_leaderboard()
    if active_names:
        leaderboard = [trader for trader in leaderboard if trader.name in active_names]
    else:
        leaderboard = []

    total_players = len(leaderboard)
    for index, trader in enumerate(leaderboard, start=1):
        if trader.name == username:
            return {
                "name": trader.name,
                "cash": trader.cash,
                "holdings": trader.holdings,
                "portfolio_value": trader.portfolio_value,
                "rank": index,
                "total_players": total_players,
            }

    return {
        "name": username,
        "cash": None,
        "holdings": None,
        "portfolio_value": None,
        "rank": None,
        "total_players": total_players,
    }


def get_active_player_names():
    sync_game_round()
    return list(game_round.snapshot()["active_players"])


def seed_bot_players(count: int, prefix: str):
    added_names = []
    if count <= 0:
        return added_names

    existing_names = {trader.name for trader in sim.traders}
    next_index = 1

    while len(added_names) < count:
        candidate = f"{prefix}{next_index:03d}"
        next_index += 1
        if candidate in existing_names or username_exists(candidate):
            continue

        sim.register_trader(candidate)
        success, _ = add_player_to_waiting_round(candidate)
        if success:
            added_names.append(candidate)
            existing_names.add(candidate)

    return added_names


def get_template_context(request: Request, page_name: str):
    sync_game_round()
    return {
        "request": request,
        "page_name": page_name,
        "current_user": get_logged_in_user(request),
        "game": game_round.snapshot(),
    }


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    if get_logged_in_user(request):
        return RedirectResponse(url="/user", status_code=302)
    return templates.TemplateResponse(
        "index.html", get_template_context(request, "index")
    )


@app.get("/login")
async def login(request: Request, username: str | None = None):
    if username is None:
        return templates.TemplateResponse(
            "login.html", get_template_context(request, "login")
        )
    normalized = validate_username(username)
    if not normalized:
        return templates.TemplateResponse(
            "login.html",
            {
                **get_template_context(request, "login"),
                "error": f"Use 2-20 letters, numbers, underscores, or hyphens. Names starting with '{BOT_PREFIX}' are reserved for bots.",
                "entered_username": username,
            },
            status_code=400,
        )

    if username_exists(normalized):
        existing_trader = sim.get_trader(normalized)
        if existing_trader is None or existing_trader.name != normalized:
            return templates.TemplateResponse(
                "login.html",
                {
                    **get_template_context(request, "login"),
                    "error": "That name is already taken.",
                    "entered_username": username,
                },
                status_code=409,
            )

    trader, _ = sim.register_trader(normalized)
    success, error = add_player_to_waiting_round(trader.name)
    if not success:
        return templates.TemplateResponse(
            "login.html",
            {
                **get_template_context(request, "login"),
                "error": error,
                "entered_username": username,
            },
            status_code=409,
        )

    request.session["username"] = trader.name
    return RedirectResponse(url="/user", status_code=302)


@app.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)


@app.get("/admin", response_class=HTMLResponse)
async def read_admin(request: Request):
    if not is_admin_authenticated(request):
        return templates.TemplateResponse(
            "admin_login.html", get_template_context(request, "admin_login")
        )
    return templates.TemplateResponse(
        "admin.html", get_template_context(request, "admin")
    )


@app.post("/admin/login")
async def admin_login(request: Request, payload: AdminPasswordRequest):
    if payload.password != ADMIN_PASSWORD:
        return {"error": "Invalid admin password"}
    request.session["is_admin"] = True
    return {"message": "Admin authenticated"}


@app.post("/admin/logout")
async def admin_logout(request: Request):
    request.session.pop("is_admin", None)
    return {"message": "Admin logged out"}


@app.post("/admin/round/reset")
def admin_reset_round(request: Request):
    if not is_admin_authenticated(request):
        return {"error": "Admin access required"}

    reset_round_state()
    return {"message": "Round reset", "game": game_round.snapshot()}


@app.post("/admin/reset-all")
def admin_reset_all(request: Request):
    if not is_admin_authenticated(request):
        return {"error": "Admin access required"}

    reset_all_state()
    return {
        "message": "All players and round state cleared",
        "game": game_round.snapshot(),
    }


@app.post("/admin/round/start")
def admin_start_round(request: Request):
    if not is_admin_authenticated(request):
        return {"error": "Admin access required"}

    started, error = start_round()
    if not started:
        return {"error": error}

    return {"message": "Round started", "game": game_round.snapshot()}


@app.post("/admin/players/seed")
def admin_seed_players(request: Request, payload: SeedPlayersRequest):
    if not is_admin_authenticated(request):
        return {"error": "Admin access required"}
    if payload.count <= 0:
        return {"error": "count must be greater than zero"}
    if payload.count > 500:
        return {"error": "count must be 500 or less"}
    if not re.match(r"^[A-Za-z0-9_-]{1,12}$", payload.prefix):
        return {
            "error": "prefix must be 1-12 letters, numbers, underscores, or hyphens"
        }
    if payload.prefix.lower() != BOT_PREFIX:
        return {"error": f"prefix must be '{BOT_PREFIX}'"}

    added_names = seed_bot_players(payload.count, payload.prefix)
    return {
        "message": f"Added {len(added_names)} bot players",
        "players_added": len(added_names),
        "game": game_round.snapshot(),
    }


@app.get("/user", response_class=HTMLResponse)
async def read_user(request: Request):
    username = require_logged_in_user(request)
    if not username:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        "user.html", get_template_context(request, "user")
    )


@app.get("/game")
def get_game_state(request: Request):
    username = get_logged_in_user(request)
    sync_game_round()
    snapshot = game_round.snapshot()
    snapshot["current_user"] = username
    snapshot["leaderboard"] = get_active_leaderboard()
    snapshot["current_user_profile"] = get_active_player_profile(username)
    return snapshot


@app.post("/orders")
def place_order(order: OrderRequest, request: Request):
    username = require_logged_in_user(request)
    if not username:
        return {"error": "Login required"}
    if order.side not in {"buy", "sell"}:
        return {"error": "side must be buy or sell"}
    if order.quantity <= 0:
        return {"error": "quantity must be greater than zero"}

    sync_game_round()
    snapshot = game_round.snapshot()
    if username not in snapshot["active_players"]:
        return {"error": "You are not registered in the current round"}
    if snapshot["status"] == "waiting":
        return {"error": "Waiting for admin to start the round"}
    if snapshot["status"] == "finished":
        return {"error": "This round has finished. Wait for the next game."}
    trader = sim.get_trader(username)
    if trader is None:
        return {"error": "Trader not found"}

    trader.place_market_order(order.side, order.quantity, sim.book)
    return {"message": "Order placed successfully", "game": game_round.snapshot()}


@app.post("/orders/random")
def trigger_random_orders(request: RandomOrderRequest):
    if request.num_orders <= 0:
        return {"error": "num_orders must be greater than zero"}
    if request.delay < 0:
        return {"error": "delay must be non-negative"}
    if request.prefix is not None and not re.match(
        r"^[A-Za-z0-9_-]{1,12}$", request.prefix
    ):
        return {
            "error": "prefix must be 1-12 letters, numbers, underscores, or hyphens"
        }
    if request.prefix is not None and request.prefix.lower() != BOT_PREFIX:
        return {"error": f"prefix must be '{BOT_PREFIX}'"}

    active_players = get_active_player_names()
    if request.prefix:
        active_players = [
            player_name
            for player_name in active_players
            if player_name.startswith(request.prefix)
        ]
    if not active_players:
        return {"error": "No active players available for random orders"}

    started = sim.trigger_random_orders(
        num_orders=request.num_orders,
        delay=request.delay,
        trader_names=active_players,
    )
    if not started:
        return {"error": "Random order burst already running"}

    return {
        "message": "Random order burst started",
        "num_orders": request.num_orders,
        "delay": request.delay,
        "prefix": request.prefix,
    }


@app.get("/leaderboard")
def get_leaderboard():
    return get_active_leaderboard()


@app.get("/orderbook")
def get_order_book():
    return {
        "bids": [
            {"price": str(price), "quantity": quantity}
            for price, quantity in reversed(
                sim.book.get_order_book_depth()["buy"].items()
            )
        ],
        "asks": [
            {"price": str(price), "quantity": quantity}
            for price, quantity in sim.book.get_order_book_depth()["sell"].items()
        ],
        "last_trading_price": sim.book.last_trading_price,
        "best_bid": sim.book.best_bid,
        "best_ask": sim.book.best_ask,
    }


@app.get("/ohlc")
def get_ohlc_data():
    if not sim.book.trades:
        return []

    trades = (
        list(sim.book.trades.values())
        if isinstance(sim.book.trades, dict)
        else sim.book.trades
    )

    df = pd.DataFrame(
        [
            {
                "time": trade.timestamp,
                "price": float(trade.price),
                "volume": trade.volume,
            }
            for trade in trades
        ]
    )

    if df.empty:
        return []

    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)

    ohlc = df["price"].resample("1s").ohlc()
    volume = df["volume"].resample("1s").sum()
    ohlc["volume"] = volume
    ohlc = ohlc.dropna()

    ohlc = ohlc.reset_index()
    ohlc["time"] = ohlc["time"].apply(lambda value: int(value.timestamp()))

    return ohlc.to_dict(orient="records")


@app.on_event("shutdown")
def shutdown_event():
    sim.stop_simulation()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
