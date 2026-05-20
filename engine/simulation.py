import time
import random
import threading
from collections import defaultdict
from decimal import Decimal
import logging

from engine.fifo import OrderBook, Order

# module logger
logger = logging.getLogger(__name__)


class Trader:
    def __init__(self, name, initial_cash=100000):
        self.name = name
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.holdings = 0  # Number of shares
        self.portfolio_value = initial_cash
        self.orders = {}  # order_id -> order

    def place_market_order(self, side, quantity, book):
        # Market order: set price to best available for immediate match
        if side == "buy":
            price = book.best_ask if book.best_ask is not None else 100
        else:
            price = book.best_bid if book.best_bid is not None else 100
        order = Order(side, price, quantity)
        book.place_order(order)
        self.orders[order.id] = order

        # Update holdings and cash based on filled quantity
        filled = quantity - order.remaining
        ltp = book.last_trading_price or 100
        if ltp == float("inf") or ltp == float("-inf"):
            raise ValueError(
                f"Invalid LTP: {ltp}. Check for missing trades or price errors."
            )
        if side == "buy":
            if self.cash >= filled * ltp:  # Check sufficient cash
                self.holdings += filled
                self.cash -= filled * ltp
            else:
                logger.debug("%s: Insufficient cash for buy", self.name)
        else:  # Allow unlimited short sells
            self.holdings -= filled
            self.cash += filled * ltp

        logger.debug(
            "%-7s: %-4s order %3d shares, filled %3d at ₹%6.2f",
            self.name,
            side.upper(),
            quantity,
            filled,
            float(ltp),
        )

    def cancel_order(self, order_id, book):
        if order_id in self.orders:
            book.cancel_order(order_id)
            del self.orders[order_id]
            logger.debug("%-10s cancelled order %s", self.name, order_id)

    def update_portfolio(self, current_price):
        if current_price and not (
            current_price == float("inf") or current_price == float("-inf")
        ):
            self.portfolio_value = self.cash + self.holdings * current_price
        else:
            self.portfolio_value = self.cash  # Fallback if price is invalid


class MarketMaker:
    def __init__(self, book, spread=1.5, inventory_limit=100):
        self.book = book
        self.spread = Decimal(str(spread))
        self.inventory = 0
        self.inventory_limit = inventory_limit
        self.active_orders = []

    def maintain_liquidity(self, ltp):
        # Cancel old orders
        for oid in self.active_orders:
            self.book.cancel_order(oid)
        self.active_orders = []

        # Place new limit orders
        buy_price = ltp - self.spread
        sell_price = ltp + self.spread
        buy_qty = random.randint(10, 60)
        sell_qty = random.randint(10, 60)

        buy_order = Order("buy", buy_price, buy_qty)
        sell_order = Order("sell", sell_price, sell_qty)

        self.book.place_order(buy_order)
        self.book.place_order(sell_order)

        self.active_orders = [buy_order.id, sell_order.id]

    def manipulate_market(self, direction, intensity=0.5):
        # Add bias: more buys for rally, more sells for pull down
        ltp = self.book.last_trading_price or 100
        if direction == "rally":
            # Add more buy orders
            for _ in range(int(intensity * 10)):
                price = ltp + Decimal(str(random.uniform(0, 5)))
                qty = random.randint(20, 100)
                order = Order("buy", price, qty)
                self.book.place_order(order)
                self.active_orders.append(order.id)
        elif direction == "pull":
            # Add more sell orders
            for _ in range(int(intensity * 10)):
                price = ltp - Decimal(str(random.uniform(0, 5)))
                qty = random.randint(20, 100)
                order = Order("sell", price, qty)
                self.book.place_order(order)
                self.active_orders.append(order.id)


class TradingSimulation:
    def __init__(self, num_traders=2):
        self.book = OrderBook()
        # self.traders = [Trader(f"Trader{i+1}") for i in range(num_traders)]
        names = [
            "Animesh",
            "Modi",
            "Bapu",
            "Trump",
            "Kim",
            "Putin",
            "Zuck",
            "Elon",
            "Altman",
            "Warren",
        ]
        self.traders = [Trader(names[i]) for i in range(num_traders)]
        self.market_maker = MarketMaker(self.book)
        self.running = False
        self.random_order_thread = None
        self.trader_lock = threading.Lock()
        self._leaderboard_cache = []
        self._leaderboard_dirty = True

    def start_simulation(self):
        # Place initial liquidity
        initial_price = 100
        for _ in range(10):  # 10 buy and 10 sell orders
            buy_order = Order(
                "buy", initial_price - random.uniform(0.5, 2), random.randint(10, 100)
            )
            sell_order = Order(
                "sell", initial_price + random.uniform(0.5, 2), random.randint(10, 100)
            )
            self.book.place_order(buy_order)
            self.book.place_order(sell_order)
        self.running = True
        threading.Thread(target=self._run_loop, daemon=True).start()

    def stop_simulation(self):
        self.running = False

    def _run_loop(self):
        while self.running:
            ltp = self.book.last_trading_price or 100
            if ltp == float("inf") or ltp == float("-inf"):
                ltp = 100  # Fallback
            self.market_maker.maintain_liquidity(ltp)

            # Random manipulation
            if random.random() < 0.2:  # 20% chance
                direction = random.choice(["rally", "pull"])
                self.market_maker.manipulate_market(direction)

            # Update portfolios
            for trader in self.traders:
                trader.update_portfolio(ltp)
            self._leaderboard_dirty = True

            time.sleep(1)  # Update every second

    def settle_shorts(self, final_price):
        """Force settlement of short positions at final price."""
        for trader in self.traders:
            if trader.holdings < 0:
                # Buy back shorts
                qty_to_cover = -trader.holdings
                cost = qty_to_cover * final_price
                trader.cash -= cost  # Deduct cost (may go negative)
                trader.holdings = 0
                if trader.cash >= 0:
                    logger.info(
                        "%-8s settled shorts: bought back %3d at ₹%6.2f",
                        trader.name,
                        qty_to_cover,
                        float(final_price),
                    )
                else:
                    logger.warning(
                        "%-8s forced settlement: cash now ₹%6.2f (negative)",
                        trader.name,
                        float(trader.cash),
                    )
            trader.update_portfolio(final_price)

    def get_leaderboard(self):
        if self._leaderboard_dirty:
            self._leaderboard_cache = sorted(
                self.traders, key=lambda t: t.portfolio_value, reverse=True
            )
            self._leaderboard_dirty = False
        return self._leaderboard_cache

    def get_trader(self, name):
        with self.trader_lock:
            return next(
                (trader for trader in self.traders if trader.name == name), None
            )

    def register_trader(self, name, initial_cash=100000):
        with self.trader_lock:
            trader = next(
                (existing for existing in self.traders if existing.name == name), None
            )
            if trader is not None:
                return trader, False

            trader = Trader(name, initial_cash=initial_cash)
            self.traders.append(trader)
        self._leaderboard_dirty = True
        return trader, True

    def reset_traders(self, initial_cash=100000):
        with self.trader_lock:
            for trader in self.traders:
                trader.cash = initial_cash
                trader.holdings = 0
                trader.portfolio_value = initial_cash
                trader.orders = {}
        self._leaderboard_dirty = True

    def clear_traders(self):
        with self.trader_lock:
            self.traders = []
        self._leaderboard_dirty = True

    def trigger_random_orders(self, num_orders=5000, delay=0.1, trader_names=None):
        if self.random_order_thread and self.random_order_thread.is_alive():
            return False

        def place_orders():
            if trader_names:
                eligible_traders = [
                    trader
                    for trader in self.traders
                    if trader.name in set(trader_names)
                ]
            else:
                eligible_traders = list(self.traders)

            if not eligible_traders:
                return

            for _ in range(num_orders):
                trader = random.choice(eligible_traders)
                side = random.choice(["buy", "sell"])
                qty = random.randint(5, 40)
                trader.place_market_order(side, qty, self.book)
                time.sleep(delay)

        self.random_order_thread = threading.Thread(target=place_orders, daemon=True)
        self.random_order_thread.start()
        return True


# Example usage
if __name__ == "__main__":
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    sim = TradingSimulation(num_traders=10)
    sim.start_simulation()

    from visualization.charts import Visualization

    vis = Visualization(sim.book)

    ani = FuncAnimation(vis.fig, vis.update, interval=200)

    sim.trigger_random_orders()

    plt.show()
