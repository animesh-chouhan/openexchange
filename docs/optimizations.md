# Optimization History — OpenExchange

A living record of identified bottlenecks, known issues, and improvement opportunities across every layer of the stack. Each entry describes the problem, the impact, and a concrete fix path. Status markers: **[ ]** identified · **[~]** in progress · **[x]** done.

---

## 1. Engine Layer — `engine/fifo.py`, `engine/heap.py`, `engine/naive.py`

### 1.1 No lock on `OrderBook` mutations
**Status:** [ ]  
**File:** [engine/fifo.py](../engine/fifo.py)

`_match_buy` and `_match_sell` mutate `bids`, `asks`, and `trades` directly. The MarketMaker background thread (`_run_loop`) calls `book.place_order` concurrently with HTTP handlers doing the same. CPython's GIL prevents torn reads of reference-counted objects, but compound operations like `peekitem → pop → setdefault` are not atomic — a context switch mid-match can corrupt book state under load.

**Fix:** Wrap `place_order` and `cancel_order` with a single `threading.Lock` on the `OrderBook`. Because the matching loop exits quickly, contention is low.

---

### 1.2 `Order._ids` / `Trade._ids` are class-level counters shared globally
**Status:** [ ]  
**Files:** [engine/fifo.py:10](../engine/fifo.py#L10), [engine/heap.py:14](../engine/heap.py#L14), [engine/naive.py:14](../engine/naive.py#L14)

`_ids = itertools.count(1)` is a class attribute. All `OrderBook` instances in the same process share one counter. The test suite resets them manually in `setUp`. Across game rounds, IDs increment unboundedly and never reset. On server restart they reset to 1, so IDs repeat across sessions.

**Fix (short term):** Move the counter onto the `OrderBook` instance and pass it to `Order.__init__`. Each book owns its own sequence. **Fix (long term):** Use UUIDs or a monotonic wall-clock-derived ID if durability matters.

---

### 1.3 `heap.py` `get_order_book_depth()` scans the full heap on every call
**Status:** [ ]  
**File:** [engine/heap.py:145-161](../engine/heap.py#L145)

The method builds `temp_buys` / `temp_sells` by iterating the entire heap — O(n) per call — then aggregates by price level. Called on every `/orderbook` request (currently once per second via polling).

**Fix:** Maintain a `defaultdict(int)` of `{price: remaining_qty}` updated incrementally inside `match_buy` / `match_sell`. Depth reads become O(1) copies. Same optimization applies to `fifo.py` if `get_order_book_depth` proves slow under many price levels.

---

### 1.4 `Trade` storage is inconsistent between engines
**Status:** [ ]  
**Files:** [engine/fifo.py:65](../engine/fifo.py#L65), [engine/heap.py:73](../engine/heap.py#L73)

`fifo.py` stores trades in a `list`; `heap.py` stores them in a `dict`. The app works around this with a branch in `/ohlc` ([app/main.py:583-587](../app/main.py#L583)). The test suite uses a `_get_trades()` helper to paper over the difference.

**Fix:** Standardize on `list` in both engines (ordering by insertion is already the desired semantics). Remove the branch in `main.py`.

---

### 1.5 `naive.py` re-sorts both lists on every `place_order`
**Status:** [ ] (by design — educational)  
**File:** [engine/naive.py:72-84](../engine/naive.py#L72)

`_match_orders` sorts `buys` and `sells` on every invocation. O(n log n) per order. This is intentional as a teaching baseline, but noting it here so it is never accidentally used under load.

**Fix:** Use `engine.fifo` for any production path. Leave `naive` as-is with a clear module docstring.

---

## 2. Simulation Layer — `engine/simulation.py`

### 2.1 Market order fill price uses LTP after the match, not actual fill price
**Status:** [ ]  
**File:** [engine/simulation.py:34-47](../engine/simulation.py#L34)

After calling `book.place_order(order)`, `Trader.place_market_order` computes accounting using `book.last_trading_price` — the price of the most recent trade. On a multi-level fill (order sweeps several price levels), all filled shares are accounted at a single price (the last fill price), not the actual weighted average. This causes small portfolio value errors and can lead to cash going negative unexpectedly.

**Fix:** Change `Order` to accumulate a `fill_cost` field during matching, or have `place_order` return a list of executions. Account cash/holdings using the actual per-fill quantities and prices.

---

### 2.2 `get_leaderboard()` sorts all traders on every call
**Status:** [x]  
**File:** [engine/simulation.py:204](../engine/simulation.py#L204)

`sorted(self.traders, ...)` is O(n log n) and called on every `/leaderboard` and `/game` request. With 500 bot traders this is 500 comparisons per request, once per second.

**Fix:** Cache the sorted leaderboard in a class variable; invalidate it only when `update_portfolio` runs (once per second in `_run_loop`). A `threading.Event` or a generation counter makes invalidation cheap.

---

### 2.3 `get_active_player_profile()` iterates the leaderboard a second time
**Status:** [x]  
**File:** [app/main.py:223-255](../app/main.py#L223)

The `/game` endpoint calls `get_active_leaderboard()` (sort + filter) and then `get_active_player_profile()` (sort + filter + linear scan for username). That is two full sorts per request.

**Fix:** Compute both in a single pass — sort once, record rank during iteration, slice for leaderboard, and record the requesting user's rank simultaneously.

---

### 2.4 `trigger_random_orders` has no rate limiting or back-pressure
**Status:** [ ]  
**File:** [engine/simulation.py:237-263](../engine/simulation.py#L237)

A single admin click can spawn 1 500+ orders at `delay=0.1s` across 500 bot traders. There is no check on how many pending orders are already in the book or how far price has drifted. Under heavy load the MarketMaker may not keep up, spreading the book and causing every order to partially fill.

**Fix (short term):** Reduce default `num_orders` and `delay`. **Fix (long term):** Add a `max_pending_orders` check and pause the burst when the book spread exceeds a threshold.

---

### 2.5 MarketMaker `manipulate_market` appends to `active_orders` without bound
**Status:** [ ]  
**File:** [engine/simulation.py:101-119](../engine/simulation.py#L101)

`active_orders.append(order.id)` is called inside `manipulate_market` but `active_orders` is only cleared at the start of `maintain_liquidity`. If `manipulate_market` fires many times between `maintain_liquidity` calls (e.g., during a burst), the list grows indefinitely and the cancel loop in `maintain_liquidity` loops over thousands of stale IDs.

**Fix:** Clear `active_orders` after the cancel loop regardless of whether new orders are placed, and cap the list length.

---

## 3. App Layer — `app/main.py`

### 3.1 `/ohlc` runs full pandas `resample` on every request
**Status:** [x]  
**File:** [app/main.py:578-614](../app/main.py#L578)

Constructs a DataFrame from every trade in `book.trades`, resamples to 1-second OHLC, and serializes the full result — O(trades) per call, called once per second by every connected client.

**Fix:** Maintain a rolling OHLC aggregator in `TradingSimulation`. On each new trade, update the current 1-second bucket. Expose a `get_ohlc_snapshot()` method that returns the pre-built list. The `/ohlc` handler becomes a trivial copy of that list.

---

### 3.2 Four parallel polling requests per second per client
**Status:** [x]  
**File:** [app/static/script.js:417-437](../app/static/script.js#L417)

`fetchDashboardData` issues four concurrent fetches (`/ohlc`, `/orderbook`, `/leaderboard`, `/game`) every second. With N connected clients that is 4N requests/sec hitting the server synchronously.

**Fix (short term):** Merge into a single `/state` endpoint that returns all four payloads in one JSON response.  
**Fix (long term):** Replace polling with a WebSocket or Server-Sent Events stream. Server pushes a state delta when the book changes; clients stay idle otherwise.

---

### 3.3 Chart replaces all candle data on every refresh
**Status:** [ ]  
**File:** [app/static/script.js:400-414](../app/static/script.js#L400)

`candlestickSeries.setData(formattedCandles)` replaces the full dataset every second. `lightweight-charts` provides `update(bar)` for appending/updating the latest candle without re-rendering history.

**Fix:** Track the last known candle timestamp in `state`. On each refresh, call `setData` only on the first render; use `update()` for incremental additions.

---

### 3.4 `renderLeaderboard` and `renderBookRows` do full `innerHTML` replacement every second
**Status:** [ ]  
**File:** [app/static/script.js:264-289](../app/static/script.js#L264), [app/static/script.js:239-262](../app/static/script.js#L239)

Every second, these functions blow away and rebuild all DOM rows unconditionally. This causes layout reflows, flickers on slower devices, and loses any DOM state (hover, focus).

**Fix:** Diff the incoming data against the previous render. Only update `textContent` on cells that changed, or key rows by trader name and reuse existing elements.

---

### 3.5 `sync_game_round()` called on every request instead of being timer-driven
**Status:** [x]  
**File:** [app/main.py:114-118](../app/main.py#L114)

`sync_game_round` checks `time.time() >= game_round.ends_at` and transitions state to `"finished"`. It is called at the start of `require_logged_in_user`, `get_active_leaderboard_entries`, `get_active_player_profile`, and `get_active_player_names`. Under load this is called many times per second for the same state.

**Fix:** Schedule the transition in a single `threading.Timer` when the round starts. Set it to fire at `ends_at`. Remove the per-request check.

---

### 3.6 `add_player_to_waiting_round` silently resets the round as a side effect
**Status:** [x]  
**File:** [app/main.py:140-154](../app/main.py#L140)

When a new player joined after a finished round, this function was resetting `status`, clearing `active_players`, and incrementing `round_id` — effectively starting a new lobby without admin control.

**Fix:** Removed the reset side effect entirely. `add_player_to_waiting_round` now rejects logins when the round is `"finished"` with a clear message ("Round has finished. Wait for the admin to start the next game."). Only the admin can reset via `/admin/round/reset` or `/admin/reset-all`.

---

## 4. Security

### 4.1 `ADMIN_PASSWORD` defaults to `"ignite123"`
**Status:** [ ]  
**File:** [app/main.py:21](../app/main.py#L21)

If `ADMIN_PASSWORD` is not set in the environment, the default is public knowledge from the source code. Any visitor can take admin control, reset rounds, and seed bots.

**Fix:** Remove the default. Raise a startup error if `ADMIN_PASSWORD` is unset or is the literal default string. Document the env var in `deploy/config.sh`.

---

### 4.2 `/orders/random` has no admin authentication
**Status:** [x]  
**File:** [app/main.py:513-551](../app/main.py#L513)

Any unauthenticated user who knows the API can `POST /orders/random` and start a burst of random orders using bot players — no session or admin check is required.

**Fix:** Add an `is_admin_authenticated(request)` check at the top of `trigger_random_orders`, or move the endpoint under `/admin/`.

---

### 4.3 Admin endpoints return `{"error": ...}` with HTTP 200
**Status:** [x]  
**Files:** [app/main.py:409-438](../app/main.py#L409)

`admin_reset_round`, `admin_reset_all`, `admin_start_round` return `{"error": "Admin access required"}` as a 200 response when not authenticated. Clients and monitoring tools expecting non-2xx for errors will miss these.

**Fix:** Return `Response(status_code=403)` or raise `HTTPException(status_code=403, ...)` for unauthorized access.

---

### 4.4 No rate limiting on `/orders`
**Status:** [ ]  
**File:** [app/main.py:487-510](../app/main.py#L487)

A single authenticated user can hammer `POST /orders` in a tight loop, generating arbitrarily many book mutations per second and crowding out other players.

**Fix:** Apply a per-user rate limit (e.g., slowapi middleware or a simple token bucket keyed on `username` in session). A limit of 10–20 orders/second per user is enough for gameplay while blocking abuse.

---

## 5. Architecture / Scalability

### 5.1 All state is in-process — no horizontal scaling
**Status:** [ ]  
**Ref:** [docs/architecture.md](architecture.md)

Running more than one Uvicorn worker gives each worker its own `TradingSimulation` instance with a divergent order book and leaderboard. The README already calls this out.

**Fix path (incremental):**
1. Move order ingestion to a Redis stream (`XADD`). An engine consumer pops orders and applies them to the authoritative book.
2. Push leaderboard/orderbook snapshots to Redis keys after each engine tick. API workers serve reads from Redis.
3. This decouples read scaling (many API workers) from write correctness (one engine consumer).

---

### 5.2 No persistence — full state lost on restart
**Status:** [ ]

All trades, player balances, and the order book exist only in memory. A process restart during a live round wipes everything.

**Fix:** At round end (or periodically), flush `(trader.name, cash, holdings, portfolio_value)` and all executed trades to a SQLite or Postgres table. On startup, reload the last committed state.

---

### 5.3 No health or readiness endpoint
**Status:** [ ]

No `/healthz` or `/ready` endpoint exists for nginx upstreams, systemd watchdog, or load-balancer health checks to consume.

**Fix:** Add `GET /healthz` returning `{"status": "ok"}` with a 200. Optionally include `{"book_trades": N, "traders": N}` for deeper liveness signals.

---

### 5.4 No metrics
**Status:** [x]

Prometheus metrics are now exposed at `/metrics` via `prometheus-fastapi-instrumentator`. Custom gauges and counters cover active users, round status, orders placed (by side), and OHLC rebuild duration. A lightweight built-in dashboard is available at `/dashboard` (no external dependencies).

**Remaining:** Native (no-Docker) Prometheus + Grafana setup. Both ship as standalone binaries — download, point Prometheus at `monitoring/prometheus.yml`, and Grafana at `monitoring/grafana/provisioning/`. Write `monitoring/setup.sh` / `start.sh` / `stop.sh` scripts to automate this.

---

## 6. Completed Optimizations

| Date | Change | Notes |
|------|--------|-------|
| 2026-03 | Reorganized app layout | Templates, static files, and engine moved into `app/` and `engine/` packages |
| 2026-03 | FIFO engine replaces naive in production | `sortedcontainers.SortedDict` gives O(log n) matching vs O(n log n) naive |
| 2026-03 | Jinja template caching disabled | Prevented cache key hashing errors on restart |
| 2026-03 | Compatibility shims added | `server.py`, `run.sh`, `setup.sh` wrappers kept for older deployments |
| 2026-03 | Benchmark suite added | k6 and Locust scripts in `benchmarks/` for load profiling |
