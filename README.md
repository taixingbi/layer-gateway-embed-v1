# layer-gateway-embed-v1

Request-level routing gateway for `/v1/embeddings` across multiple vLLM backends.

## Endpoints

- `POST /v1/embeddings`
- `GET /health`
- `GET /metrics`

## Required Headers

- `X-Request-Id`
- `X-Trace-Id`
- `X-Session-Id`

## Configuration

Set values via environment variables (see `.env.example`):

- `EMBED_BACKENDS` (`name=url,name=url`)
- `TIMEOUT_CONNECT_MS`
- `TIMEOUT_READ_MS`
- `RETRY_MAX_ATTEMPTS`
- `ADMISSION_MAX_CONCURRENT`
- `ADMISSION_WAIT_TIMEOUT_MS`
- `CB_FAILURE_THRESHOLD`
- `CB_RESET_TIMEOUT_SEC`
- `CB_HALF_OPEN_MAX_PROBES`
- `CB_HALF_OPEN_SUCCESS_THRESHOLD`
- `ROUTING_INFLIGHT_WEIGHT`
- `ROUTING_LATENCY_WEIGHT`
- `ROUTING_ERROR_WEIGHT`
- `ROUTING_EXPLORATION_RATE`
- `ROUTING_MAX_IDLE_MS`

## Routing and Reliability

- Routing score: `inflight * W1 + latency * W2 + error_rate * W3`
- Hybrid routing controls:
  - exploration sampling (`ROUTING_EXPLORATION_RATE`)
  - idle rebalance (`ROUTING_MAX_IDLE_MS`)
- Circuit breaker:
  - open after consecutive failures
  - half-open probe recovery (`CB_HALF_OPEN_MAX_PROBES`, `CB_HALF_OPEN_SUCCESS_THRESHOLD`)

## Related Docs

- `docs/design.md`
- `docs/status-codes.md`
- `docs/run-locally.md`
- `docs/docker.md`

## Run

```bash
pip install .
python -m app.main
```

## Example

```bash
curl http://localhost:30181/health

curl -X POST http://localhost:30181/v1/embeddings \
  -H "X-Request-Id: request_id_1" \
  -H "X-Trace-Id: trace_id_1" \
  -H "X-Session-Id: session_id_1" \
  -H "Content-Type: application/json" \
  -d '{"model":"BAAI/bge-m3","input":"hello world"}'
```
