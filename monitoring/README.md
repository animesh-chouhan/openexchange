# Monitoring

## Prometheus + Grafana (Docker)

Full time-series storage, per-endpoint breakdowns, p95/p99 latency, and historical data across restarts.

**Prerequisites:** Docker and Docker Compose installed.

### Start

```bash
cd monitoring
docker compose up -d
```

| Service    | URL                   | Credentials   |
| ---------- | --------------------- | ------------- |
| Grafana    | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | —             |

The OpenExchange dashboard loads automatically in Grafana (provisioned on startup).

### Stop

```bash
cd monitoring
docker compose down
```

### Requirements

The app must be running and reachable on **port 8000** on the host. Prometheus scrapes
`http://host.docker.internal:8000/metrics` every 5 seconds.

If you're on Linux and `host.docker.internal` doesn't resolve, add this to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: openexchange
    static_configs:
      - targets: ["172.17.0.1:8000"] # Docker bridge gateway
```

### Dashboard panels

| Panel            | What it shows                        |
| ---------------- | ------------------------------------ |
| Request Rate     | req/s by endpoint                    |
| Response Latency | p50 / p95 / p99 across all endpoints |
| Active Users     | current registered players           |
| Round Status     | Running / Stopped                    |
| Orders / sec     | buy vs sell rate                     |
| OHLC Rebuild     | pandas rebuild duration (p95)        |
| CPU %            | Python process CPU usage             |
| Memory RSS       | Python process resident memory       |

---

## Metrics reference

The app exposes Prometheus metrics at `GET /metrics`.

| Metric                                          | Type      | Description                                           |
| ----------------------------------------------- | --------- | ----------------------------------------------------- |
| `openexchange_active_users`                     | Gauge     | Players registered in the current round               |
| `openexchange_round_running`                    | Gauge     | 1 while round is running, 0 otherwise                 |
| `openexchange_orders_total{side}`               | Counter   | Orders placed, labelled `buy` or `sell`               |
| `openexchange_ohlc_rebuild_seconds`             | Histogram | Time spent on pandas OHLC rebuild (cache misses only) |
| `http_requests_total{handler,method,status}`    | Counter   | Per-endpoint HTTP request count                       |
| `http_request_duration_seconds{handler,method}` | Histogram | Per-endpoint response time                            |
| `process_cpu_seconds_total`                     | Counter   | Python process CPU time                               |
| `process_resident_memory_bytes`                 | Gauge     | Python process RSS memory                             |
