# ADR 002 — O(1) Trader Lookup via Name Index

**Status:** Accepted  
**Date:** 2026-05-20

## Context

`TradingSimulation` stored traders in a plain list (`self.traders`). Three call sites performed linear scans of that list:

1. `username_exists()` in `app/main.py` — iterated `sim.traders` without holding `trader_lock`, a latent data race and O(n) scan.
2. `register_trader()` — scanned the list under `trader_lock` to check for duplicates before inserting.
3. `get_trader()` — scanned the list under `trader_lock` to find a trader by name.

With 500 bot traders seeded, each login request triggered at least two full O(n) scans. Under concurrent load these scans serialized through `trader_lock`, producing extreme tail latency on `GET /login`: p95 = 36 s, p99 = 37 s, max = 69 s, despite a healthy 210 ms median. The `/state` endpoint (49 ms median, 358 RPS) confirmed the rest of the stack was fine; the bottleneck was isolated to login.

## Decision

Add `_trader_index: dict[str, Trader]` to `TradingSimulation`, keyed by `name.lower()`. All methods that structurally mutate `self.traders` keep the dict in sync under `trader_lock`:

- `register_trader()` — check and insert via `_trader_index`, O(1).
- `get_trader()` — return `_trader_index.get(name.lower())`, O(1).
- `clear_traders()` — reset both `self.traders` and `_trader_index`.

`username_exists()` in `app/main.py` now delegates to `sim.get_trader()`, eliminating the unguarded access to `sim.traders` and the duplicate case-folding logic.

`self.traders` (the list) is kept for the leaderboard sort and the portfolio update loop; only lookup is moved to the dict.

## Consequences

**Good:**
- Login path goes from O(n) under lock to O(1) — eliminates the p95 spike.
- `username_exists` no longer accesses `sim.traders` without a lock.
- Case-insensitive uniqueness is enforced in one place (`_trader_index` key is always lowercased).

**Accepted trade-off:**
- Two structures must stay in sync. Every mutation of `self.traders` must also update `_trader_index` under the same lock. This is contained to `register_trader`, `clear_traders`, and `__init__` — all narrow, well-tested paths. `reset_traders` does not need changes because it mutates trader attributes in-place without adding or removing entries.
