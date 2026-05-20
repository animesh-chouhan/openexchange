# ADR 001 — Timer-Driven Round Expiry

**Status:** Accepted  
**Date:** 2026-05-20

## Context

`GameRound` transitions from `"running"` to `"finished"` when `time.time() >= ends_at`. The original implementation handled this with a `sync_game_round()` function that performed this check on every incoming request. It was called defensively in six places: `require_logged_in_user`, `get_active_leaderboard_entries`, `get_active_leaderboard_and_profile`, `get_active_player_names`, `get_template_context`, and directly inside the `/orders` handler.

This meant:
- The same time comparison ran dozens of times per second under load.
- When one helper called another, the check fired multiple times per request with no benefit.
- The correct call site was unclear — every function that read game state felt obligated to sync first.

## Decision

Replace the per-request check with a single `threading.Timer` scheduled at round start. When `start_round()` or `start_round_if_needed()` sets `ends_at`, it immediately schedules `_expire_round` to fire after `GAME_DURATION_SECONDS`. `_expire_round` acquires the lock and flips `status` to `"finished"` exactly once.

`reset_round_state()` and `reset_all_state()` cancel the timer before resetting state, so a late-firing timer cannot flip a freshly reset round.

`sync_game_round()` and all six call sites were deleted.

## Consequences

**Good:**
- The transition happens at the right time on a background thread — no polling.
- Helpers that read game state no longer need to trigger side effects.
- Removes ambiguity about where the sync responsibility lives.

**Accepted risk:**
- If the process restarts mid-round, the timer is lost. On restart, `ends_at` is in the past and the round stays `"running"` until an admin resets it. This is the same behavior as before (the per-request check would have caught it on the next request), except now there is no per-request fallback. Acceptable given the project has no persistence and a restart already wipes all state.
- `threading.Timer` fires on a background thread; the lock in `_expire_round` prevents races with concurrent request handlers.
