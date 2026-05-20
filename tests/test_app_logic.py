import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.responses import RedirectResponse

import app.main as main
from engine.simulation import TradingSimulation


class AppLogicTest(unittest.TestCase):
    def setUp(self):
        self.sim = TradingSimulation(num_traders=0)
        self.round = main.GameRound()
        self.sim_patch = patch.object(main, "sim", self.sim)
        self.round_patch = patch.object(main, "game_round", self.round)
        self.sim_patch.start()
        self.round_patch.start()

    def tearDown(self):
        self.sim.stop_simulation()
        self.sim_patch.stop()
        self.round_patch.stop()

    @staticmethod
    def request(session=None):
        return SimpleNamespace(session=session or {})

    def test_username_validation(self):
        self.assertEqual(main.validate_username(" Alice_1 "), "Alice_1")
        self.assertIsNone(main.validate_username("a"))
        self.assertIsNone(main.validate_username("bad name"))
        self.assertIsNone(main.validate_username("noobot001"))

    def test_add_player_to_waiting_round_registers_active_player(self):
        success, error = main.add_player_to_waiting_round("Alice")

        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertIn("Alice", self.round.snapshot()["active_players"])

    def test_running_round_rejects_new_player(self):
        self.round.active_players.add("Alice")
        self.round.status = "running"

        success, error = main.add_player_to_waiting_round("Bob")

        self.assertFalse(success)
        self.assertIn("already running", error)

    def test_start_round_requires_waiting_players(self):
        started, error = main.start_round()
        self.assertFalse(started)
        self.assertEqual(error, "No registered players to start the round")

        self.round.active_players.add("Alice")
        started, error = main.start_round()

        self.assertTrue(started)
        self.assertIsNone(error)
        self.assertEqual(self.round.status, "running")
        self.assertIsNotNone(self.round.ends_at)

    def test_login_registers_user_and_sets_session(self):
        request = self.request()

        response = asyncio.run(main.login(request, username="Alice"))

        self.assertIsInstance(response, RedirectResponse)
        self.assertEqual(response.headers["location"], "/user")
        self.assertEqual(request.session["username"], "Alice")
        self.assertIsNotNone(self.sim.get_trader("Alice"))
        self.assertIn("Alice", self.round.snapshot()["active_players"])

    def test_game_state_includes_current_user_and_leaderboard(self):
        self.sim.register_trader("Alice")
        self.round.active_players.add("Alice")
        request = self.request({"username": "Alice"})

        state = main.get_game_state(request)

        self.assertEqual(state["current_user"], "Alice")
        self.assertEqual(state["leaderboard"][0]["name"], "Alice")
        self.assertEqual(state["current_user_profile"]["name"], "Alice")

    def test_unauthenticated_order_is_rejected(self):
        response = main.place_order(main.OrderRequest(side="buy", quantity=1), self.request())

        self.assertEqual(response, {"error": "Login required"})

    def test_order_requires_running_round(self):
        self.sim.register_trader("Alice")
        self.round.active_players.add("Alice")
        request = self.request({"username": "Alice"})

        response = main.place_order(main.OrderRequest(side="buy", quantity=1), request)

        self.assertEqual(response, {"error": "Waiting for admin to start the round"})


if __name__ == "__main__":
    unittest.main()
