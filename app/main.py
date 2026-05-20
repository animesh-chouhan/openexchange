import re
import secrets
import threading
import time
import os
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from engine.simulation import TradingSimulation

APP_DIR = Path(__file__).resolve().parent

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

_ohlc_cache: list = []
_ohlc_cache_ts: float = 0.0
_ohlc_lock = threading.Lock()

import logging

# Configure logging format and level for the whole app
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=secrets.token_hex(32))
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")
# Disable Jinja template caching to avoid template-cache key hashing issues
try:
    templates.env.cache_size = 0
except Exception:
    pass

# --- Prometheus metrics ---
active_users_gauge = Gauge("openexchange_active_users", "Active players in current round")
round_running_gauge = Gauge("openexchange_round_running", "1 if round is running, 0 otherwise")
orders_counter = Counter("openexchange_orders", "Total orders placed", ["side"])
ohlc_rebuild_histogram = Histogram(
    "openexchange_ohlc_rebuild_seconds",
    "Duration of OHLC pandas rebuild (cache misses only)",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)
Instrumentator(excluded_handlers=["/metrics"]).instrument(app).expose(app)


def normalize_username(username: str) -> str:
    return username.strip()


def username_exists(username: str) -> bool:
    return sim.get_trader(normalize_username(username)) is not None


def validate_username(username: str) -> str | None:
    normalized = normalize_username(username)
    if not USERNAME_PATTERN.match(normalized):
        return None
    if normalized.lower().startswith(BOT_PREFIX):
        return None
    return normalized


_round_timer: threading.Timer | None = None

# Round expiry is timer-driven: no per-request sync. _expire_round fires once at
# ends_at; reset functions cancel it so a stale timer can't flip a new round.

def _expire_round():
    with game_round.lock:
        if game_round.status == "running":
            game_round.status = "finished"
    round_running_gauge.set(0)


def _schedule_round_expiry(delay: float):
    global _round_timer
    if _round_timer is not None:
        _round_timer.cancel()
    _round_timer = threading.Timer(delay, _expire_round)
    _round_timer.daemon = True
    _round_timer.start()


def reset_round_state():
    global _round_timer
    if _round_timer is not None:
        _round_timer.cancel()
        _round_timer = None
    with game_round.lock:
        game_round.status = "waiting"
        game_round.started_at = None
        game_round.ends_at = None
        game_round.round_id += 1
    sim.reset_traders()
    round_running_gauge.set(0)


def reset_all_state():
    global _round_timer
    if _round_timer is not None:
        _round_timer.cancel()
        _round_timer = None
    with game_round.lock:
        game_round.status = "waiting"
        game_round.started_at = None
        game_round.ends_at = None
        game_round.active_players = set()
        game_round.round_id += 1
    sim.clear_traders()
    active_users_gauge.set(0)
    round_running_gauge.set(0)


def add_player_to_waiting_round(username: str):
    with game_round.lock:
        if game_round.status == "finished":
            return False, "Round has finished. Wait for the admin to start the next game."
        if game_round.status == "running" and username not in game_round.active_players:
            return False, "A round is already running. Wait for the next 2-minute game."

        game_round.active_players.add(username)
        count = len(game_round.active_players)
    active_users_gauge.set(count)
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
    _schedule_round_expiry(GAME_DURATION_SECONDS)
    round_running_gauge.set(1)


def start_round():
    with game_round.lock:
        if game_round.status != "waiting":
            return False, "Round is not in waiting state"
        if not game_round.active_players:
            return False, "No registered players to start the round"

        game_round.status = "running"
        game_round.started_at = time.time()
        game_round.ends_at = game_round.started_at + GAME_DURATION_SECONDS
    _schedule_round_expiry(GAME_DURATION_SECONDS)
    round_running_gauge.set(1)
    return True, None


def get_logged_in_user(request: Request) -> str | None:
    return request.session.get("username")


def is_admin_authenticated(request: Request) -> bool:
    return bool(request.session.get("is_admin"))


def require_logged_in_user(request: Request) -> str | None:
    return get_logged_in_user(request)


def get_active_leaderboard_entries(limit: int | None = 10):
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


def get_active_leaderboard_and_profile(username: str | None, limit: int = 14):
    """Single pass over the active leaderboard: returns (leaderboard, profile)."""
    snapshot = game_round.snapshot()
    active_names = set(snapshot["active_players"])

    ranked = (
        [t for t in sim.get_leaderboard() if t.name in active_names]
        if active_names
        else []
    )
    total_players = len(ranked)

    leaderboard_out = []
    profile = None

    for index, trader in enumerate(ranked, start=1):
        if index <= limit:
            leaderboard_out.append(
                {
                    "name": trader.name,
                    "cash": trader.cash,
                    "holdings": trader.holdings,
                    "portfolio_value": trader.portfolio_value,
                }
            )
        if username and trader.name == username:
            profile = {
                "name": trader.name,
                "cash": trader.cash,
                "holdings": trader.holdings,
                "portfolio_value": trader.portfolio_value,
                "rank": index,
                "total_players": total_players,
            }
        if index >= limit and (profile is not None or not username):
            break

    if username and profile is None:
        profile = {
            "name": username,
            "cash": None,
            "holdings": None,
            "portfolio_value": None,
            "rank": None,
            "total_players": total_players,
        }

    return leaderboard_out, profile


def get_active_player_profile(username: str | None):
    _, profile = get_active_leaderboard_and_profile(username)
    return profile


def get_active_player_names():
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
    game_snapshot = game_round.snapshot()
    # JSON-safe snapshot for templates/inline JS (avoid unhashable/complex objects)
    game_json = {
        "status": game_snapshot.get("status"),
        "round_id": game_snapshot.get("round_id"),
        "started_at": game_snapshot.get("started_at"),
        "ends_at": game_snapshot.get("ends_at"),
        "seconds_remaining": int(game_snapshot.get("seconds_remaining", 0)),
        "duration_seconds": int(game_snapshot.get("duration_seconds", 0)),
        "active_players": list(game_snapshot.get("active_players", [])),
    }

    return {
        "request": request,
        "page_name": page_name,
        "current_user": get_logged_in_user(request),
        "game": game_snapshot,
        "game_json": game_json,
    }


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    if get_logged_in_user(request):
        return RedirectResponse(url="/user", status_code=302)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=get_template_context(request, "index"),
    )


@app.get("/login")
async def login(request: Request, username: str | None = None):
    if username is None:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context=get_template_context(request, "login"),
        )
    normalized = validate_username(username)
    if not normalized:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
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
                request=request,
                name="login.html",
                context={
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
            request=request,
            name="login.html",
            context={
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
            request=request,
            name="admin_login.html",
            context=get_template_context(request, "admin_login"),
        )
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context=get_template_context(request, "admin"),
    )


@app.post("/admin/login")
async def admin_login(request: Request, payload: AdminPasswordRequest):
    if payload.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password")
    request.session["is_admin"] = True
    return {"message": "Admin authenticated"}


@app.post("/admin/logout")
async def admin_logout(request: Request):
    request.session.pop("is_admin", None)
    return {"message": "Admin logged out"}


@app.post("/admin/round/reset")
def admin_reset_round(request: Request):
    if not is_admin_authenticated(request):
        raise HTTPException(status_code=403, detail="Admin access required")

    reset_round_state()
    return {"message": "Round reset", "game": game_round.snapshot()}


@app.post("/admin/reset-all")
def admin_reset_all(request: Request):
    if not is_admin_authenticated(request):
        raise HTTPException(status_code=403, detail="Admin access required")

    reset_all_state()
    return {
        "message": "All players and round state cleared",
        "game": game_round.snapshot(),
    }


@app.post("/admin/round/start")
def admin_start_round(request: Request):
    if not is_admin_authenticated(request):
        raise HTTPException(status_code=403, detail="Admin access required")

    started, error = start_round()
    if not started:
        return {"error": error}

    return {"message": "Round started", "game": game_round.snapshot()}


@app.post("/admin/players/seed")
def admin_seed_players(request: Request, payload: SeedPlayersRequest):
    if not is_admin_authenticated(request):
        raise HTTPException(status_code=403, detail="Admin access required")
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
        request=request,
        name="user.html",
        context=get_template_context(request, "user"),
    )


@app.get("/game")
def get_game_state(request: Request):
    username = get_logged_in_user(request)
    leaderboard, profile = get_active_leaderboard_and_profile(username)
    snapshot = game_round.snapshot()
    snapshot["current_user"] = username
    snapshot["leaderboard"] = leaderboard
    snapshot["current_user_profile"] = profile
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
    orders_counter.labels(side=order.side).inc()
    return {"message": "Order placed successfully", "game": game_round.snapshot()}


@app.post("/orders/random")
def trigger_random_orders(http_request: Request, request: RandomOrderRequest):
    if not is_admin_authenticated(http_request):
        raise HTTPException(status_code=403, detail="Admin access required")
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


def _build_orderbook():
    depth = sim.book.get_order_book_depth()
    return {
        "bids": [
            {"price": str(price), "quantity": quantity}
            for price, quantity in reversed(depth["buy"].items())
        ],
        "asks": [
            {"price": str(price), "quantity": quantity}
            for price, quantity in depth["sell"].items()
        ],
        "last_trading_price": sim.book.last_trading_price,
        "best_bid": sim.book.best_bid,
        "best_ask": sim.book.best_ask,
    }


def _build_ohlc():
    global _ohlc_cache, _ohlc_cache_ts
    now = time.time()
    if now - _ohlc_cache_ts < 1.0:
        return _ohlc_cache
    with _ohlc_lock:
        if now - _ohlc_cache_ts < 1.0:  # another thread rebuilt while we waited
            return _ohlc_cache

        trades = (
            list(sim.book.trades.values())
            if isinstance(sim.book.trades, dict)
            else sim.book.trades
        )
        if not trades:
            _ohlc_cache, _ohlc_cache_ts = [], now
            return _ohlc_cache

        df = pd.DataFrame(
            [
                {"time": t.timestamp, "price": float(t.price), "volume": t.volume}
                for t in trades
            ]
        )
        if df.empty:
            _ohlc_cache, _ohlc_cache_ts = [], now
            return _ohlc_cache

        with ohlc_rebuild_histogram.time():
            df["time"] = pd.to_datetime(df["time"], unit="s")
            df.set_index("time", inplace=True)
            ohlc = df["price"].resample("1s").ohlc()
            ohlc["volume"] = df["volume"].resample("1s").sum()
            ohlc = ohlc.dropna().reset_index()
            ohlc["time"] = ohlc["time"].apply(lambda v: int(v.timestamp()))
            _ohlc_cache = ohlc.to_dict(orient="records")

        _ohlc_cache_ts = now
    return _ohlc_cache


def get_full_state(username: str | None):
    leaderboard, profile = get_active_leaderboard_and_profile(username)
    snapshot = game_round.snapshot()
    snapshot["current_user"] = username
    snapshot["leaderboard"] = leaderboard
    snapshot["current_user_profile"] = profile
    return {
        "game": snapshot,
        "orderbook": _build_orderbook(),
        "leaderboard": leaderboard,
        "ohlc": _build_ohlc(),
    }


@app.get("/state")
def get_state(request: Request):
    username = get_logged_in_user(request)
    return get_full_state(username)


@app.get("/leaderboard")
def get_leaderboard():
    return get_active_leaderboard()


@app.get("/orderbook")
def get_order_book():
    return _build_orderbook()


@app.get("/ohlc")
def get_ohlc_data():
    return _build_ohlc()


@app.get("/metrics/json")
def metrics_json():
    from prometheus_client import REGISTRY
    result = {
        "active_users": 0, "round_running": 0,
        "orders": {"buy": 0, "sell": 0},
        "http_requests_total": 0,
        "http_duration_sum": 0.0, "http_duration_count": 0.0,
        "cpu_seconds": 0.0, "memory_bytes": 0.0,
        "ohlc_rebuild_sum": 0.0, "ohlc_rebuild_count": 0.0,
    }
    for metric in REGISTRY.collect():
        for s in metric.samples:
            n = s.name
            if n == "openexchange_active_users":
                result["active_users"] = s.value
            elif n == "openexchange_round_running":
                result["round_running"] = s.value
            elif n == "openexchange_orders_total":
                result["orders"][s.labels.get("side", "unknown")] = s.value
            elif n == "http_requests_total":
                result["http_requests_total"] += s.value
            elif n == "http_request_duration_seconds_sum":
                result["http_duration_sum"] += s.value
            elif n == "http_request_duration_seconds_count":
                result["http_duration_count"] += s.value
            elif n == "process_cpu_seconds_total":
                result["cpu_seconds"] = s.value
            elif n == "process_resident_memory_bytes":
                result["memory_bytes"] = s.value
            elif n == "openexchange_ohlc_rebuild_seconds_sum":
                result["ohlc_rebuild_sum"] = s.value
            elif n == "openexchange_ohlc_rebuild_seconds_count":
                result["ohlc_rebuild_count"] = s.value
    return result


@app.get("/dashboard", response_class=HTMLResponse)
async def metrics_dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="metrics_dashboard.html",
        context={},
    )


@app.on_event("shutdown")
def shutdown_event():
    sim.stop_simulation()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
