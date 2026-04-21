# Embedding Gateway Design

## Purpose

`layer-gateway-embed-v1` is a standalone gateway for embedding traffic only. It exposes `POST /v1/embeddings`, validates required request context headers, routes requests to the best backend, and adds reliability/observability controls at request level.

## Request Flow

1. Client sends `POST /v1/embeddings` with:
   - `X-Request-Id`
   - `X-Trace-Id`
   - `X-Session-Id`
2. Gateway validates headers and parses payload.
3. Routing selector scores available backends and picks the lowest score.
4. Gateway forwards the request to the selected backend.
5. Gateway returns backend response transparently.
6. On timeout/retryable failure, gateway retries on alternate backend when possible.

## Routing Model

Backends are scored using:

`score = inflight * W1 + latency * W2 + error_rate * W3`

Where:
- `inflight`: current active requests
- `latency`: rolling latency signal
- `error_rate`: rolling failure signal

Lower score is preferred.

To avoid starvation while preserving latency preference, routing also uses two hybrid controls:
- `ROUTING_EXPLORATION_RATE`: small probability to choose a random healthy backend for fresh samples.
- `ROUTING_MAX_IDLE_MS`: if a healthy backend has not been selected recently, it is preferred to rebalance traffic.

## Reliability Controls

- Retry on timeout and retryable statuses (`502`, `503`, `504`)
- Configurable retry attempts (`RETRY_MAX_ATTEMPTS`)
- Per-backend circuit breaker:
  - Opens after repeated failures
  - Excludes backend from routing during cool-down
  - Allows recovery after reset timeout

## Observability

- Structured JSON logging with gateway event schema
- Key events: startup, request finished, retry, request failed
- Prometheus metrics:
  - request totals
  - request latency
  - backend selection
  - inflight requests
  - failures
  - retries
- Operational endpoints:
  - `GET /health`
  - `GET /metrics`

## Configuration Surface

Runtime behavior is environment-driven through:
- server host/port
- timeout values
- retry policy
- circuit breaker thresholds
- routing weights
- routing exploration and idle rebalance knobs
- backend list
- logging options

See `README.md` and `.env.example` for concrete runtime values.

## Future Enhancements

- Admission queue / rate limiting to protect backends during burst traffic
- Dynamic backend discovery
- Adaptive routing weights based on live traffic shape
