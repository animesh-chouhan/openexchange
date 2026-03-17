import time
import heapq
import itertools
from datetime import datetime
from collections import defaultdict, deque
from functools import total_ordering


@total_ordering
class Order:
    _ids = itertools.count(1)

    def __init__(self, side, price, quantity):
        self.id = next(self._ids)
        self.timestamp = time.time()
        self.side = side  # "buy" or "sell"
        self.price = price
        self.quantity = quantity
        self.remaining = quantity
        self.cancelled = False

    def __repr__(self):
        return f"ORDER#{self.id} {datetime.fromtimestamp(self.timestamp)} {self.side.upper()}: {self.quantity} @ {self.price}"

    def __eq__(self, other):
        if not self.side == other.side:
            return NotImplemented
        return (self.price, self.timestamp) == (other.price, other.timestamp)

    def __lt__(self, other):
        if not self.side == other.side:
            return NotImplemented

        if self.side == "buy":
            return (self.price, self.timestamp) > (other.price, other.timestamp)
        elif self.side == "sell":
            return (self.price, self.timestamp) < (other.price, other.timestamp)

    def status(self):
        if self.remaining == self.quantity:
            return "open"
        elif self.remaining == 0:
            if self.cancelled:
                return "cancelled"
            else:
                return "filled"
        else:
            return "partial"


class Node:
    def __init__(self, side, price):
        self.side = side
        self.price = price
        self.orders = deque()

    def __eq__(self, other):
        if not self.side == other.side:
            return NotImplemented
        return self.price == other.price

    def __lt__(self, other):
        if not self.side == other.side:
            return NotImplemented

        if self.side == "buy":
            return self.price > other.price
        elif self.side == "sell":
            return self.price < other.price


class Trade:
    _ids = itertools.count(1)

    def __init__(self, price, volume, buy_id, sell_id):
        self.id = next(self._ids)
        self.timestamp = time.time()
        self.price = price
        self.volume = volume
        self.buy_id = buy_id
        self.sell_id = sell_id

    def __repr__(self):
        return f"TRADE#{self.id} {datetime.fromtimestamp(self.timestamp)}: {self.volume} @ {self.price}"


class OrderBook:
    def __init__(self):
        self.orders = dict()
        self.trades = dict()
        self.buys = []  # Max-heap for buy orders
        self.sells = []  # Min-heap for sell orders
        self.buy_nodes = dict()
        self.sell_nodes = dict()

    def place_order(self, order):
        if order.side == "buy":
            self.match_buy(order)
        elif order.side == "sell":
            self.match_sell(order)

    def clean_heap_top(self, heap):
        while heap:
            top_node = heap[0]
            while top_node.orders and (
                top_node.orders[0].remaining == 0 or top_node.orders[0].cancelled
            ):
                top_node.orders.popleft()
            if len(top_node.orders) == 0:
                heapq.heappop(heap)
                if top_node.side == "buy":
                    del self.buy_nodes[top_node.price]
                else:
                    del self.sell_nodes[top_node.price]

            else:
                break

    def match_buy(self, buy_order):
        self.orders[buy_order.id] = buy_order
        self.clean_heap_top(self.sells)

        while self.sells and buy_order.remaining > 0:
            best_sell_node = self.sells[0]

            # Clean up any canceled or filled orders
            while best_sell_node.orders and (
                best_sell_node.orders[0].remaining == 0
                or best_sell_node.orders[0].cancelled
            ):
                best_sell_node.orders.popleft()

            if not best_sell_node.orders:
                heapq.heappop(self.sells)
                del self.sell_nodes[best_sell_node.price]
                continue

            best_sell = best_sell_node.orders[0]
            if best_sell.price <= buy_order.price:
                trade_price = best_sell.price
                trade_quantity = min(best_sell.remaining, buy_order.remaining)
                # Execute trade
                trade = Trade(
                    trade_price,
                    trade_quantity,
                    buy_order.id,
                    best_sell.id,
                )
                best_sell.remaining -= trade_quantity
                buy_order.remaining -= trade_quantity

                if best_sell.remaining == 0:
                    best_sell_node.orders.popleft()  # Remove fully filled sell order

                self.trades[trade.id] = trade
                # print(trade)
            else:
                break
        if buy_order.remaining > 0:
            if buy_order.price in self.buy_nodes:
                self.buy_nodes[buy_order.price].orders.append(buy_order)
            else:
                node = Node(buy_order.side, buy_order.price)
                node.orders.append(buy_order)
                heapq.heappush(self.buys, node)
                self.buy_nodes[buy_order.price] = node

    def match_sell(self, sell_order):
        self.orders[sell_order.id] = sell_order
        self.clean_heap_top(self.buys)

        while self.buys and sell_order.remaining > 0:
            best_buy_node = self.buys[0]

            # Clean up any canceled or filled orders
            while best_buy_node.orders and (
                best_buy_node.orders[0].remaining == 0
                or best_buy_node.orders[0].cancelled
            ):
                best_buy_node.orders.popleft()

            if not best_buy_node.orders:
                heapq.heappop(self.buys)
                del self.buy_nodes[best_buy_node.price]
                continue

            best_buy = best_buy_node.orders[0]

            if best_buy.price >= sell_order.price:
                trade_price = best_buy.price
                trade_quantity = min(best_buy.remaining, sell_order.remaining)

                # Execute trade
                trade = Trade(
                    trade_price,
                    trade_quantity,
                    best_buy.id,
                    sell_order.id,
                )
                best_buy.remaining -= trade_quantity
                sell_order.remaining -= trade_quantity

                if best_buy.remaining == 0:
                    best_buy_node.orders.popleft()  # Remove fully filled buy order

                self.trades[trade.id] = trade
                # print(trade)
            else:
                break

        if sell_order.remaining > 0:
            if sell_order.price in self.sell_nodes:
                self.sell_nodes[sell_order.price].orders.append(sell_order)
            else:
                node = Node(sell_order.side, sell_order.price)
                node.orders.append(sell_order)
                heapq.heappush(self.sells, node)
                self.sell_nodes[sell_order.price] = node

    def get_order_book_depth(self):
        buy_levels = defaultdict(int)
        sell_levels = defaultdict(int)

        for price, node in self.buy_nodes.items():
            buy_levels[price] = sum(order.remaining for order in node.orders)

        for price, node in self.sell_nodes.items():
            sell_levels[price] = sum(order.remaining for order in node.orders)

        return {
            "buy": buy_levels,  # High to low
            "sell": sell_levels,  # Low to high
        }

    @property
    def last_trading_price(self):
        if self.trades:
            # dict preserves order of insertion
            return list(self.trades.values())[-1].price
        else:
            return None

    def get_order_by_id(self, order_id):
        return self.orders[order_id]

    def cancel_order(self, order_id):
        order = self.get_order_by_id(order_id)
        order.remaining = 0
        order.cancelled = True

    def update_order(self, order_id, side, price, quantity):
        self.cancel_order(order_id)
        new_order = Order(side, price, quantity)
        self.place_order(new_order)
