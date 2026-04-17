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
- `CB_FAILURE_THRESHOLD`
- `CB_RESET_TIMEOUT_SEC`
- `ROUTING_INFLIGHT_WEIGHT`
- `ROUTING_LATENCY_WEIGHT`
- `ROUTING_ERROR_WEIGHT`

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
