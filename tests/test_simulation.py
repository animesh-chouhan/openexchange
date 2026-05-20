import itertools
import time
import unittest
from decimal import Decimal

from engine.fifo import Order, Trade
from engine.simulation import TradingSimulation


class TradingSimulationTest(unittest.TestCase):
    def setUp(self):
        Order._ids = itertools.count(1)
        Trade._ids = itertools.count(1)
        self.sim = TradingSimulation(num_traders=0)

    def tearDown(self):
        self.sim.stop_simulation()

    def test_register_trader_returns_existing_duplicate(self):
        first, created_first = self.sim.register_trader("Alice")
        second, created_second = self.sim.register_trader("Alice")

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertIs(first, second)
        self.assertEqual(len(self.sim.traders), 1)

    def test_market_buy_updates_cash_holdings_and_order_state(self):
        trader, _ = self.sim.register_trader("Buyer", initial_cash=1000)
        self.sim.book.place_order(Order("sell", 100, 5))

        trader.place_market_order("buy", 3, self.sim.book)

        self.assertEqual(trader.holdings, 3)
        self.assertEqual(trader.cash, Decimal("700.00"))
        self.assertEqual(self.sim.book.last_trading_price, Decimal("100.00"))
        self.assertEqual(len(trader.orders), 1)

    def test_market_sell_updates_cash_and_short_holdings(self):
        trader, _ = self.sim.register_trader("Seller", initial_cash=1000)
        self.sim.book.place_order(Order("buy", 100, 5))

        trader.place_market_order("sell", 2, self.sim.book)

        self.assertEqual(trader.holdings, -2)
        self.assertEqual(trader.cash, Decimal("1200.00"))
        self.assertEqual(self.sim.book.last_trading_price, Decimal("100.00"))

    def test_reset_traders_restores_portfolios_and_orders(self):
        trader, _ = self.sim.register_trader("Alice")
        trader.cash = 123
        trader.holdings = -4
        trader.portfolio_value = 42
        trader.orders = {1: object()}

        self.sim.reset_traders(initial_cash=5000)

        self.assertEqual(trader.cash, 5000)
        self.assertEqual(trader.holdings, 0)
        self.assertEqual(trader.portfolio_value, 5000)
        self.assertEqual(trader.orders, {})

    def test_clear_traders_removes_registered_players(self):
        self.sim.register_trader("Alice")
        self.sim.register_trader("Bob")

        self.sim.clear_traders()

        self.assertEqual(self.sim.traders, [])

    def test_leaderboard_sorts_by_portfolio_value_descending(self):
        alice, _ = self.sim.register_trader("Alice")
        bob, _ = self.sim.register_trader("Bob")
        alice.portfolio_value = 100
        bob.portfolio_value = 200

        self.assertEqual(
            [trader.name for trader in self.sim.get_leaderboard()], ["Bob", "Alice"]
        )

    def test_leaderboard_is_cached_between_calls(self):
        alice, _ = self.sim.register_trader("Alice")
        alice.portfolio_value = 100

        first = self.sim.get_leaderboard()
        second = self.sim.get_leaderboard()

        self.assertIs(first, second)

    def test_leaderboard_cache_invalidated_after_register(self):
        alice, _ = self.sim.register_trader("Alice")
        alice.portfolio_value = 100
        first = self.sim.get_leaderboard()

        bob, _ = self.sim.register_trader("Bob")
        bob.portfolio_value = 200

        second = self.sim.get_leaderboard()
        self.assertIsNot(first, second)
        self.assertEqual([t.name for t in second], ["Bob", "Alice"])

    def test_leaderboard_cache_invalidated_after_reset(self):
        alice, _ = self.sim.register_trader("Alice")
        alice.portfolio_value = 500
        _ = self.sim.get_leaderboard()

        self.sim.reset_traders(initial_cash=100000)

        leaderboard = self.sim.get_leaderboard()
        self.assertEqual(leaderboard[0].portfolio_value, 100000)

    def test_leaderboard_cache_invalidated_after_clear(self):
        self.sim.register_trader("Alice")
        _ = self.sim.get_leaderboard()

        self.sim.clear_traders()

        self.assertEqual(self.sim.get_leaderboard(), [])

    def test_random_order_burst_refuses_second_concurrent_run(self):
        self.sim.register_trader("Alice", initial_cash=1_000_000)
        self.sim.book.place_order(Order("buy", 100, 500))
        self.sim.book.place_order(Order("sell", 100, 500))

        first_started = self.sim.trigger_random_orders(num_orders=50, delay=0.01)
        second_started = self.sim.trigger_random_orders(num_orders=50, delay=0.01)

        self.assertTrue(first_started)
        self.assertFalse(second_started)

        self.sim.random_order_thread.join(timeout=2)
        self.assertFalse(self.sim.random_order_thread.is_alive())

    def test_start_simulation_can_be_stopped(self):
        self.sim.start_simulation()
        self.assertTrue(self.sim.running)
        self.assertTrue(self.sim.book.bids)
        self.assertTrue(self.sim.book.asks)

        self.sim.stop_simulation()
        time.sleep(0.01)

        self.assertFalse(self.sim.running)


if __name__ == "__main__":
    unittest.main()
