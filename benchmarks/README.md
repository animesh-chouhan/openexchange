# Benchmarks — Quick start

This folder contains example k6 and Locust scripts to benchmark read- and write-heavy workloads against the OpenExchange server.

Prerequisites

- k6 — fast HTTP load testing tool (https://k6.io/)
- locust — for session/cookie-based user-flow testing (`pip install locust`)
- wrk (optional) — lightweight HTTP benchmarking tool

Examples

k6 (read-heavy)

```bash
k6 run benchmarks/k6_read.js
```

k6 (write-heavy)

```bash
k6 run benchmarks/k6_write.js
```

Locust (user-flow test)

```bash
pip install locust
locust -f benchmarks/locustfile.py
# then open http://localhost:8089 and start the test from the UI
```

wrk example (if installed)

```bash
wrk -t4 -c200 -d30s http://127.0.0.1:8000/orderbook
```

Notes and recommendations

- Run the server in a production-like mode before benchmarking. Example (Gunicorn + Uvicorn workers):

```bash
pip install -r requirements.txt
# example: 4 workers
gunicorn -k uvicorn.workers.UvicornWorker -w 4 app.main:app -b 0.0.0.0:8000
```

- For write-heavy scenarios, either run the built-in engine in single-process mode or scaffold the Redis producer/consumer before scaling to many API workers.
- Run load generators from a separate machine or VM to avoid client-side bottlenecks (CPU, network).
- Warm up the server (short low-rate ramp) before collecting steady-state measurements.

What to measure

- Response times: p50 / p95 / p99
- Error rate and HTTP statuses
- Throughput (requests/sec)
- Server CPU and memory during the test

Next steps

- I can scaffold a Redis-backed producer/consumer and add benchmark scenarios to compare the current in-process flow vs Redis-backed flow. Want me to do that next?
