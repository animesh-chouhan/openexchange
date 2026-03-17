import unittest
import sys
import importlib
import itertools
from io import StringIO
from decimal import Decimal

# A list of engine modules to be tested
ENGINES_TO_TEST = [
    'engine',
    'engine_naive',
    'engine_fifo',
]

class EngineTestMixin:
    """
    A mixin class containing generic tests that can be run against any engine.
    The `setUp` method of the actual test class is responsible for setting:
    - self.book (an instance of the OrderBook)
    - self.Order (the Order class)
    """

    def _get_trades(self):
        """Helper to get trades, as storage differs between engines."""
        if isinstance(self.book.trades, dict):
            return list(self.book.trades.values())
        return self.book.trades

    def test_simple_trade(self):
        """Tests a full trade between one buy and one sell order."""
        self.book.place_order(self.Order(side="buy", price=100, quantity=10))
        self.book.place_order(self.Order(side="sell", price=100, quantity=10))
        
        trades = self._get_trades()
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].price, Decimal('100'))
        self.assertEqual(trades[0].volume, 10)
        
        depth = self.book.get_order_book_depth()
        self.assertEqual(len(depth['buy']), 0)
        self.assertEqual(len(depth['sell']), 0)

    def test_partial_fill(self):
        """Tests when a smaller order partially fills a larger one."""
        buy_order = self.Order(side="buy", price=100, quantity=10)
        self.book.place_order(buy_order)
        sell_order = self.Order(side="sell", price=100, quantity=5)
        self.book.place_order(sell_order)

        trades = self._get_trades()
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].volume, 5)

        self.assertEqual(buy_order.remaining, 5)
        self.assertTrue(sell_order.is_filled or sell_order.remaining == 0)

        depth = self.book.get_order_book_depth()
        self.assertEqual(len(depth['buy']), 1)
        self.assertEqual(depth['buy'][Decimal('100')], 5)
        self.assertEqual(len(depth['sell']), 0)

    def test_no_trade_on_price_mismatch(self):
        """Tests that no trade occurs if prices don't cross."""
        self.book.place_order(self.Order(side="buy", price=99, quantity=10))
        self.book.place_order(self.Order(side="sell", price=100, quantity=10))
        
        self.assertEqual(len(self._get_trades()), 0)
        depth = self.book.get_order_book_depth()
        self.assertEqual(len(depth['buy']), 1)
        self.assertEqual(len(depth['sell']), 1)

    def test_last_trading_price(self):
        """Tests the last_trading_price property."""
        self.assertIsNone(self.book.last_trading_price)
        self.book.place_order(self.Order(side="buy", price=101, quantity=10))
        self.book.place_order(self.Order(side="sell", price=101, quantity=5))
        self.assertEqual(self.book.last_trading_price, Decimal('101'))
        self.book.place_order(self.Order(side="buy", price=102, quantity=5))
        self.book.place_order(self.Order(side="sell", price=102, quantity=5))
        self.assertEqual(self.book.last_trading_price, Decimal('102'))

    def test_cancel_order(self):
        """Tests cancelling an open order."""
        order_to_cancel = self.Order("buy", 100, 10)
        self.book.place_order(order_to_cancel)
        
        depth_before = self.book.get_order_book_depth()
        self.assertEqual(depth_before['buy'][Decimal('100')], 10)

        self.book.cancel_order(order_to_cancel.id)
        self.assertTrue(order_to_cancel.cancelled)
        
        # Placing a new order should not match with the cancelled one
        self.book.place_order(self.Order("sell", 100, 10))
        
        depth_after = self.book.get_order_book_depth()
        self.assertNotIn(Decimal('100'), depth_after['buy']) # The buy order should be gone
        self.assertEqual(len(self._get_trades()), 0) # No new trade should have happened

    def test_update_order(self):
        """Tests updating an order."""
        order_to_update = self.Order("buy", 100, 10)
        self.book.place_order(order_to_update)
        
        self.book.update_order(order_to_update.id, "buy", 101, 15)
        
        depth = self.book.get_order_book_depth()
        self.assertNotIn(Decimal('100'), depth['buy'])
        self.assertIn(Decimal('101'), depth['buy'])
        self.assertEqual(depth['buy'][Decimal('101')], 15)

        # Check that the old order is cancelled
        self.assertTrue(order_to_update.cancelled)


def create_test_class(engine_name):
    """A factory function to create a TestCase class for a given engine."""
    
    # Dynamically import the engine module
    try:
        engine_module = importlib.import_module(engine_name)
    except ImportError:
        return None

    Order = engine_module.Order
    OrderBook = engine_module.OrderBook

    class TestEngine(unittest.TestCase, EngineTestMixin):
        
        def setUp(self):
            # Reset class-level counters for predictable IDs
            Order._ids = itertools.count(1)
            # Some engines might not have a book-level ID counter
            if hasattr(OrderBook, '_ids'):
                OrderBook._ids = itertools.count(1)
            
            self.book = OrderBook()
            self.Order = Order

            # Suppress print statements from the naive engine during tests
            if engine_name == 'engine_naive':
                self.held_stdout = sys.stdout
                sys.stdout = StringIO()

        def tearDown(self):
            if engine_name == 'engine_naive':
                sys.stdout = self.held_stdout
    
    # Set a dynamic name for the class for clear test reporting
    TestEngine.__name__ = f'Test{engine_name.replace("_", " ").title().replace(" ", "")}'
    return TestEngine

# Create a global scope variable for each test class
for engine_name in ENGINES_TO_TEST:
    test_class = create_test_class(engine_name)
    if test_class:
        globals()[test_class.__name__] = test_class

if __name__ == '__main__':
    unittest.main()
