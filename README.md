# openexchange

OpenExchange is a small, educational order-matching engine and trading simulator.

Quick start
- Install dependencies: `pip install -r requirements.txt`
- Run the web server: `./run.sh` or `python3 server.py`
- Run a simulation: `python3 trading_sim.py` or `python3 perf_test.py`

Key components
- `engine_naive.py` — simple, readable matching engine implementation
- `engine_fifo.py` — FIFO matching engine
- `engine_heap.py` / `engine_heapnodes.py` — heap-based engines (optimized)
- `server.py` — Flask server exposing a simple UI/API
- `visualization.py`, `static/`, `templates/` — UI and visualization assets
- `binance.py` — example connector
- `test.py`, `perf_test.py` — test and performance scripts

Notes
- This repo is intended for experimentation and teaching — expect informal code.
- See `LICENSE` for licensing details.

Contributing
- Open issues or pull requests with clear descriptions and minimal tests/examples.
