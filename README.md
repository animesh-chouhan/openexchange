# OpenExchange

OpenExchange is an educational order-matching engine and real-time trading game. It includes multiple matching-engine implementations, a FastAPI web app, a browser UI, deployment scripts, and benchmarking helpers.

## Quick Start

Install [uv](https://docs.astral.sh/uv/) if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then:

```bash
uv sync
./run.sh
```

The app starts on:

```text
http://127.0.0.1:8000
```

You can also run the app directly:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Project Layout

```text
openexchange/
├── app/                    # FastAPI app, templates, static UI assets
├── engine/                 # Matching engines and trading simulation
├── visualization/          # Local matplotlib/mplfinance chart helpers
├── deploy/                 # systemd, nginx, status, and server config files
├── scripts/                # Real setup/update/run scripts
├── tests/                  # Engine test suite
├── benchmarks/             # k6 and Locust load tests
├── docs/                   # Architecture notes, plan, presentation material
├── media/                  # Images/videos used by docs and presentations
├── notebooks/              # Engine explanation notebooks
├── run.sh                  # Compatibility wrapper for scripts/run.sh
├── setup.sh                # Compatibility wrapper for scripts/setup.sh
└── update.sh               # Compatibility wrapper for scripts/update.sh
```

## Main Components

- `app/main.py` — FastAPI app entrypoint and HTTP routes.
- `app/templates/` — HTML pages for index, login, user, and admin views.
- `app/static/` — browser JavaScript and CSS.
- `engine/fifo.py` — FIFO/price-time priority matching engine used by the game.
- `engine/simulation.py` — trader, market maker, and simulation loop.
- `deploy/openexchange.service` — production systemd unit.
- `deploy/nginx.conf` — nginx reverse proxy config.
- `tests/test_engine.py` — shared tests for the engine implementations.

The root `server.py` is intentionally kept as a compatibility shim for older deployments that still run `server:app`.

## Common Commands

Run locally:

```bash
./run.sh
```

Run tests:

```bash
uv run pytest
```

The test suite covers:

- matching-engine behavior across the heap, naive, and FIFO engines
- FIFO-only price-time priority guarantees
- trading simulation state changes
- app-level game/login/order helper logic
- shell script syntax for deploy/run scripts

Run the simulation visualizer:

```bash
uv run python -m engine.simulation
```

Run the performance script:

```bash
uv run python perf_test.py
```

Deploy/update on the server:

```bash
./update.sh
```

Install or refresh nginx/systemd setup:

```bash
./setup.sh
```

## Deployment Notes

The production service should run:

```text
/opt/openexchange/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`deploy/openexchange.service` contains that systemd unit. `deploy/nginx.conf` proxies public HTTP traffic to the local Uvicorn process.

For service checks and recovery commands, see:

```text
deploy/STATUS.md
```

## Architecture Note

The current app keeps trading state in memory. That means one Uvicorn process is the safest default for correctness. Running multiple workers can duplicate the order book and leaderboard per process unless state is moved to Redis, a database, or a separate engine service.

See `docs/architecture.md` for scaling options.

## License

See `LICENSE`.
