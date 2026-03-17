import itertools
from datetime import datetime
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_EVEN


class Order:
    """Represents a single order in the order book."""

    _ids = itertools.count(1)

    def __init__(self, side, price, quantity):
        self.id = next(self._ids)
        self.timestamp = datetime.now()
        self.side = side  # "buy" or "sell"
        self.price = Decimal(price).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        self.quantity = quantity
        self.remaining = quantity
        self.cancelled = False

    def __repr__(self):
        return f"ORDER#{self.id} [{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {self.side.upper()}: {self.quantity} @ {self.price}"

    @property
    def is_filled(self):
        return self.remaining == 0 or self.cancelled


class Trade:
    """Represents a trade that has been executed."""

    _ids = itertools.count(1)

    def __init__(self, price, volume, buy_order_id, sell_order_id):
        self.id = next(self._ids)
        self.timestamp = datetime.now()
        self.price = Decimal(price).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        self.volume = volume
        self.buy_order_id = buy_order_id
        self.sell_order_id = sell_order_id

    def __repr__(self):
        return f"TRADE#{self.id} [{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {self.volume} @ {self.price}"


class OrderBook:
    """A naive order book that uses simple lists and sorting for matching."""

    def __init__(self):
        self.buys = []
        self.sells = []
        self.trades = []
        # A dictionary to access any order by its ID, for status checks.
        self.orders = {}

    def place_order(self, order: Order):
        """Places an order and triggers the matching process."""
        self.orders[order.id] = order

        if order.side == "buy":
            self.buys.append(order)
        else:  # 'sell'
            self.sells.append(order)

        print(f"Placed {order}")
        self._match_orders()

    def _match_orders(self):
        """
        A naive matching algorithm that sorts orders and matches them.
        This is inefficient because it re-sorts the lists on every match attempt.
        """
        # Filter out any orders that are already filled or cancelled.
        self.buys = [o for o in self.buys if not o.is_filled]
        self.sells = [o for o in self.sells if not o.is_filled]

        # Sort buy orders from highest to lowest price (best for matching).
        self.buys.sort(key=lambda o: (-o.price, o.timestamp))
        # Sort sell orders from lowest to highest price (best for matching).
        self.sells.sort(key=lambda o: (o.price, o.timestamp))

        # Loop as long as there's a potential match.
        while self.buys and self.sells and self.buys[0].price >= self.sells[0].price:
            best_buy = self.buys[0]
            best_sell = self.sells[0]

            # Determine trade quantity and price
            trade_quantity = min(best_buy.remaining, best_sell.remaining)
            # The trade price is typically the price of the order that was on the book first (the sell order in this case).
            trade_price = best_sell.price

            # Create and record the trade
            trade = Trade(trade_price, trade_quantity, best_buy.id, best_sell.id)
            self.trades.append(trade)
            print(f"Executed {trade}")

            # Update the remaining quantities of the orders
            best_buy.remaining -= trade_quantity
            best_sell.remaining -= trade_quantity

            # Remove filled orders from the books
            if best_buy.is_filled:
                self.buys.pop(0)

            if best_sell.is_filled:
                self.sells.pop(0)

    def get_order_by_id(self, order_id):
        return self.orders.get(order_id)

    def cancel_order(self, order_id):
        order = self.get_order_by_id(order_id)
        if order and not order.is_filled:
            order.cancelled = True
            if order.side == "buy":
                self.buys = [o for o in self.buys if o.id != order_id]
            else:  # 'sell'
                self.sells = [o for o in self.sells if o.id != order_id]

    def update_order(self, order_id, side, price, quantity):
        self.cancel_order(order_id)
        new_order = Order(side, price, quantity)
        self.place_order(new_order)

    def get_order_book_depth(self):
        buy_levels = defaultdict(int)
        sell_levels = defaultdict(int)

        for order in self.buys:
            if not order.is_filled:
                buy_levels[order.price] += order.remaining

        for order in self.sells:
            if not order.is_filled:
                sell_levels[order.price] += order.remaining
        
        # Filter out zero-quantity levels before returning
        buy_levels = {p: q for p, q in buy_levels.items() if q > 0}
        sell_levels = {p: q for p, q in sell_levels.items() if q > 0}

        return {
            "buy": dict(sorted(buy_levels.items(), reverse=True)),
            "sell": dict(sorted(sell_levels.items())),
        }

    @property
    def last_trading_price(self):
        if self.trades:
            return self.trades[-1].price
        else:
            return None


if __name__ == "__main__":
    # A simple demonstration of the naive engine
    book = OrderBook()

    # Add some orders
    book.place_order(Order(side="buy", price=100, quantity=10))
    print(book.get_order_book_depth())

    book.place_order(Order(side="sell", price=102, quantity=5))
    print(book.get_order_book_depth())

    book.place_order(Order(side="buy", price=101, quantity=8))
    print(book.get_order_book_depth())

    # This order should trigger a trade
    print("### Placing an order that should trigger a trade ###")
    book.place_order(Order(side="sell", price=101, quantity=12))
    print(book.get_order_book_depth())

    print("### Final Trades ###")
    for t in book.trades:
        print(t)

    print(f"\nLast trading price: {book.last_trading_price}")

    # Cancel an order
    # First, let's place an order to be cancelled
    book.place_order(Order(side="buy", price=99, quantity=5))
    print(book.get_order_book_depth())
    order_to_cancel_id = list(book.orders.keys())[-1]
    print(f"\nCancelling ORDER#{order_to_cancel_id}...")
    book.cancel_order(order_to_cancel_id)
    print(book.get_order_book_depth())
