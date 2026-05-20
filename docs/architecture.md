# Architecture — OpenExchange (detailed)

This document describes the current implementation, runtime behavior, data model, concurrency, and practical deployment recommendations for the OpenExchange repository.

## 1. Purpose

Capture the code structure and runtime architecture so it's easy to plan scaling, testing, and production deployments.

## 2. High-level components

- `app/main.py` — FastAPI HTTP server. Exposes UI routes and REST endpoints used by the web UI and programmatic clients.
- `engine/simulation.py` — `TradingSimulation`, `Trader`, `MarketMaker`. Owns the `OrderBook`, manages simulation threads and producer logic for orders.
- `engine/fifo.py` — Matching engine implementation (`OrderBook`, `Order`, `Trade`). Core matching logic lives here.
- `app/templates/`, `app/static/`, `visualization/charts.py` — Frontend assets and local visualization helpers.
- `binance.py`, `tests/`, `perf_test.py` — example connectors, tests, and performance scripts.

## 3. Data model (key types)

- Order: id, timestamp, side, price, quantity, remaining, cancelled.
- Trade: id, timestamp, price, volume, buy_id, sell_id.
- Trader: name, cash, holdings, portfolio_value, orders.
- OrderBook: sorted price maps (`bids`, `asks`), orders index, trades list.

## 4. Runtime / process model

- Single-process authoritative mode (current default): `app/main.py` creates a `TradingSimulation` instance named `sim` and calls `sim.start_simulation()` at startup.
- Background threads inside the same process:
  - Simulation thread: market maker loop that places liquidity and updates trader portfolios (runs every second).
  - Random order thread(s): spawned by `sim.trigger_random_orders` for load testing.
  - Cache thread: background thread that precomputes leaderboard, orderbook depth, and OHLC for faster reads.
- FastAPI/ASGI: requests are handled by Uvicorn/Gunicorn workers. In-process state (`sim`, cache) is local to each worker process.

## 5. API surface (selected endpoints)

- GET `/` — index page
- GET `/login` — login page / register user
- GET `/game` — game snapshot, leaderboard, profile
- POST `/orders` — place a market order (synchronous call into `sim`)
- POST `/orders/random` — start a burst of random orders (starts a background thread)
- GET `/orderbook` — order book depth (served from background cache)
- GET `/ohlc` — OHLC timeseries (served from background cache)

## 6. Concurrency and consistency

- Concurrency model relies on Python threads inside a process and in-memory data structures. `TradingSimulation` uses a `trader_lock` for trader list operations; `GameRound` uses a lock for round lifecycle.
- `OrderBook` operations are not protected by a global lock — they mutate internal structures directly. In the single-process deployment this is acceptable; in multi-threaded access scenarios there is potential for race conditions.
- When multiple processes (workers) are used, each maintains independent state. This creates eventual divergence between workers' leaderboards and orderbooks unless state is externalized.

## 7. Performance hotspots (observed / likely)

- Per-request leaderboard sorting and pandas OHLC computation — mitigated by the background cache.
- `OrderBook.place_order` matching logic — CPU-bound and sensitive to Python GIL; expensive bursts will consume CPU.
- Use of `pandas` for OHLC is convenient but relatively heavy; consider incremental aggregation to avoid full-data resampling on each change.

## 8. Deployment and scaling options (practical)

- **Option A — Simple multi-process (quick):** run Gunicorn with multiple `uvicorn.workers.UvicornWorker` workers. Pros: easy to run and uses multiple cores. Cons: state is duplicated per worker.
  - Example: `gunicorn -k uvicorn.workers.UvicornWorker -w 4 app.main:app -b 0.0.0.0:8000`
- **Option B — Single authoritative engine + stateless API frontends (recommended for correctness):**
  - One engine process owns `TradingSimulation` and `OrderBook`.
  - API frontends are stateless and forward order requests to the engine (HTTP/gRPC/Redis stream). Reads can be served from a shared cache or from the engine.
  - Pros: single source of truth, scalable frontends. Cons: engine is a single point to scale vertically or sharded by instrument.
- **Option C — Redis-backed queue + shared cache (recommended for scale and reliability):**
  - API workers push orders into a Redis list/stream and/or publish events. Engine consumers pop/consume and apply to the authoritative `OrderBook` and publish state updates back to Redis.
  - Use Redis keys for leaderboard/orderbook snapshots and Pub/Sub for notifications. This enables many API workers and one or more engine consumers.
- **Option D — Message broker (Kafka) for extremely high throughput and replayability.**

## 9. Pragmatic migration steps

1. Add an order ingestion queue in the API layer (e.g., Redis `LPUSH`/`XADD`) and a small consumer process that reads orders and applies them to `sim.book`.
2. Move the background cache into the engine process and have API workers read precomputed snapshots from Redis.
3. Replace pandas aggregation with incremental aggregators to compute OHLC on the fly and flush per-second buckets to Redis.
4. Add metrics (Prometheus) and health endpoints; run with multiple workers behind a load-balancer.

## 10. Observability and testing

- Add Prometheus metrics for request latency, orders/sec, trades/sec, and cache age.
- Use k6/Locust/wrk for stress tests; run load generator from a separate VM to avoid client bottlenecks.

## 11. Durability and recovery

- Persist trades and order snapshots to durable storage (Postgres, S3 snapshots) if you need auditability or recovery.

## 12. Security and operations

- Protect admin endpoints with strong auth and remove default admin password.
- Use TLS at the load-balancer level in production and secure session keys.

## 13. File map (where to change)

- `app/main.py` — API glue, sessions, and route handlers.
- `engine/simulation.py` — simulation loop, trader logic, entrypoint for engine behavior.
- `engine/fifo.py` — matching logic; consider replacing with a C-extension or Rust service for higher throughput.

## 14. Next recommended task (minimal):

- Implement a Redis-backed order queue and move shared state to Redis so multiple API workers can be used without diverging state.

---

If you'd like, I will now scaffold a minimal Redis-backed producer/consumer example in the repo and update `requirements.txt` and `run` instructions.
