import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
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
        if main._round_timer is not None:
            main._round_timer.cancel()
            main._round_timer = None

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

    def test_add_player_rejected_when_round_finished(self):
        self.round.status = "finished"
        self.round.active_players = {"Alice"}
        self.round.round_id = 3

        success, error = main.add_player_to_waiting_round("Bob")

        self.assertFalse(success)
        self.assertIn("finished", error.lower())
        self.assertNotIn("Bob", self.round.active_players)
        self.assertEqual(self.round.status, "finished")
        self.assertEqual(self.round.round_id, 3)

    def test_login_rejected_when_round_finished(self):
        self.round.status = "finished"
        request = self.request()

        response = asyncio.run(main.login(request, username="Bob"))

        self.assertNotIn("username", request.session)

    def test_single_pass_leaderboard_and_profile_top_ranked(self):
        alice, _ = self.sim.register_trader("Alice")
        bob, _ = self.sim.register_trader("Bob")
        alice.portfolio_value = 200
        bob.portfolio_value = 100
        self.round.active_players = {"Alice", "Bob"}
        self.sim._leaderboard_dirty = True

        leaderboard, profile = main.get_active_leaderboard_and_profile("Bob")

        self.assertEqual([t["name"] for t in leaderboard], ["Alice", "Bob"])
        self.assertEqual(profile["name"], "Bob")
        self.assertEqual(profile["rank"], 2)
        self.assertEqual(profile["total_players"], 2)

    def test_single_pass_profile_beyond_leaderboard_limit(self):
        # 16 traders ranked 1–16; current user is ranked 16 (below limit=14)
        for i in range(1, 17):
            t, _ = self.sim.register_trader(f"P{i:02d}")
            t.portfolio_value = 1000 - i  # P01 highest, P16 lowest
        self.round.active_players = {f"P{i:02d}" for i in range(1, 17)}
        self.sim._leaderboard_dirty = True

        leaderboard, profile = main.get_active_leaderboard_and_profile("P16")

        self.assertEqual(len(leaderboard), 14)
        self.assertEqual(profile["rank"], 16)
        self.assertEqual(profile["total_players"], 16)

    def test_single_pass_profile_none_for_unknown_user(self):
        self.sim.register_trader("Alice")
        self.round.active_players = {"Alice"}
        self.sim._leaderboard_dirty = True

        leaderboard, profile = main.get_active_leaderboard_and_profile("Ghost")

        self.assertEqual(len(leaderboard), 1)
        self.assertIsNone(profile["rank"])
        self.assertEqual(profile["name"], "Ghost")
        self.assertEqual(profile["total_players"], 1)

    def test_single_pass_no_username_returns_none_profile(self):
        self.sim.register_trader("Alice")
        self.round.active_players = {"Alice"}
        self.sim._leaderboard_dirty = True

        leaderboard, profile = main.get_active_leaderboard_and_profile(None)

        self.assertEqual(len(leaderboard), 1)
        self.assertIsNone(profile)

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

    # --- timer-driven round expiry ---

    def test_expire_round_transitions_running_to_finished(self):
        self.round.status = "running"
        main._expire_round()
        self.assertEqual(self.round.status, "finished")

    def test_expire_round_is_noop_when_not_running(self):
        self.round.status = "waiting"
        main._expire_round()
        self.assertEqual(self.round.status, "waiting")

    def test_start_round_schedules_expiry_timer(self):
        self.round.active_players.add("Alice")
        main.start_round()
        self.assertIsNotNone(main._round_timer)
        self.assertTrue(main._round_timer.is_alive())

    def test_reset_round_cancels_pending_timer(self):
        mock_timer = MagicMock()
        main._round_timer = mock_timer
        main.reset_round_state()
        mock_timer.cancel.assert_called_once()
        self.assertIsNone(main._round_timer)

    def test_reset_all_cancels_pending_timer(self):
        mock_timer = MagicMock()
        main._round_timer = mock_timer
        main.reset_all_state()
        mock_timer.cancel.assert_called_once()
        self.assertIsNone(main._round_timer)

    def test_timer_fires_and_expires_round(self):
        self.round.active_players.add("Alice")
        with patch.object(main, "GAME_DURATION_SECONDS", 0.05):
            main.start_round()
        main._round_timer.join(timeout=1)
        self.assertEqual(self.round.status, "finished")

    # --- /state endpoint ---

    def test_get_state_returns_all_four_keys(self):
        self.sim.register_trader("Alice")
        self.round.active_players.add("Alice")

        state = main.get_state(self.request({"username": "Alice"}))

        for key in ("game", "orderbook", "leaderboard", "ohlc"):
            self.assertIn(key, state)

    def test_get_state_game_contains_current_user_and_leaderboard(self):
        self.sim.register_trader("Alice")
        self.round.active_players.add("Alice")

        state = main.get_state(self.request({"username": "Alice"}))

        self.assertEqual(state["game"]["current_user"], "Alice")
        self.assertIsNotNone(state["game"]["current_user_profile"])
        self.assertEqual(state["leaderboard"], state["game"]["leaderboard"])

    # --- /orders/random auth ---

    def test_random_orders_requires_admin(self):
        with self.assertRaises(HTTPException) as ctx:
            main.trigger_random_orders(
                self.request(),
                main.RandomOrderRequest(num_orders=10, delay=0.1),
            )
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
