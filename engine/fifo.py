import time
import itertools
from collections import deque
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN
from sortedcontainers import SortedDict


class Order:
    _ids = itertools.count(1)

    __slots__ = (
        "id",
        "timestamp",
        "side",
        "price",
        "quantity",
        "remaining",
        "cancelled",
    )

    def __init__(self, side, price, quantity):
        self.id = next(Order._ids)
        self.timestamp = time.time()
        self.side = side
        self.price = Decimal(price).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        self.quantity = quantity
        self.remaining = quantity
        self.cancelled = False

    def __repr__(self):
        return f"ORDER#{self.id:<4} {self.side.upper():<4} {self.quantity:>3}@{self.price:>7.2f}"

    @property
    def is_filled(self):
        return self.remaining == 0 or self.cancelled


class Trade:
    _ids = itertools.count(1)

    __slots__ = ("id", "timestamp", "price", "volume", "buy_id", "sell_id")

    def __init__(self, price, volume, buy_id, sell_id):
        self.id = next(Trade._ids)
        self.timestamp = time.time()
        self.price = Decimal(price).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        self.volume = volume
        self.buy_id = buy_id
        self.sell_id = sell_id

    def __repr__(self):
        return f"TRADE#{self.id:>4} {self.volume:>3}@{self.price:>7.2f}"


class OrderBook:

    def __init__(self):

        # price -> FIFO queue
        self.bids = SortedDict()  # highest price last
        self.asks = SortedDict()  # lowest price first

        self.orders = {}
        self.trades = []

    def place_order(self, order):

        self.orders[order.id] = order

        if order.side == "buy":
            self._match_buy(order)
        else:
            self._match_sell(order)

    def _match_buy(self, buy):

        while buy.remaining > 0 and self.asks:

            best_price, queue = self.asks.peekitem(0)

            if best_price > buy.price:
                break

            sell = queue[0]

            # Clean up filled/cancelled orders from the front of the queue
            if sell.remaining == 0 or sell.cancelled:
                queue.popleft()
                if not queue:
                    del self.asks[best_price]
                continue

            trade_qty = min(buy.remaining, sell.remaining)

            trade = Trade(best_price, trade_qty, buy.id, sell.id)
            self.trades.append(trade)

            buy.remaining -= trade_qty
            sell.remaining -= trade_qty

            if sell.remaining == 0:
                queue.popleft()

            if not queue:
                del self.asks[best_price]

        if buy.remaining > 0:
            self.bids.setdefault(buy.price, deque()).append(buy)

    def _match_sell(self, sell):

        while sell.remaining > 0 and self.bids:

            best_price, queue = self.bids.peekitem(-1)

            if best_price < sell.price:
                break

            buy = queue[0]

            # Clean up filled/cancelled orders from the front of the queue
            if buy.remaining == 0 or buy.cancelled:
                queue.popleft()
                if not queue:
                    del self.bids[best_price]
                continue

            trade_qty = min(sell.remaining, buy.remaining)

            trade = Trade(best_price, trade_qty, buy.id, sell.id)
            self.trades.append(trade)

            sell.remaining -= trade_qty
            buy.remaining -= trade_qty

            if buy.remaining == 0:
                queue.popleft()

            if not queue:
                del self.bids[best_price]

        if sell.remaining > 0:
            self.asks.setdefault(sell.price, deque()).append(sell)

    def cancel_order(self, order_id):

        order = self.orders.get(order_id)

        if not order:
            return

        order.remaining = 0
        order.cancelled = True

    def get_order_book_depth(self):

        bids_raw = {
            price: sum(o.remaining for o in q if not o.cancelled)
            for price, q in reversed(self.bids.items())
        }

        asks_raw = {
            price: sum(o.remaining for o in q if not o.cancelled)
            for price, q in self.asks.items()
        }
        return {
            "buy": {p: q for p, q in bids_raw.items() if q > 0},
            "sell": {p: q for p, q in asks_raw.items() if q > 0},
        }

    @property
    def last_trading_price(self):

        if not self.trades:
            return None

        return self.trades[-1].price

    @property
    def best_bid(self):
        if self.bids:
            return self.bids.peekitem(-1)[0]  # Highest bid
        return None

    @property
    def best_ask(self):
        if self.asks:
            return self.asks.peekitem(0)[0]  # Lowest ask
        return None

    def get_order_by_id(self, order_id):
        return self.orders[order_id]

    def update_order(self, order_id, side, price, quantity):
        self.cancel_order(order_id)
        new_order = Order(side, price, quantity)
        self.place_order(new_order)
