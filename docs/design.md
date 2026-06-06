# Embedding Gateway Design

## Purpose

`layer-gateway-embed-v1` is a standalone gateway for embedding traffic only. It exposes `POST /v1/embeddings`, resolves optional correlation headers (missing or blank values get UUIDs), routes requests to the best backend, and adds reliability/observability controls at request level.

## Request Flow

1. Client sends `POST /v1/embeddings` (optionally with `X-Request-Id`, `X-Trace-Id`, `X-Session-Id`; missing or empty values are filled with UUIDs).
2. Gateway resolves correlation ids and parses payload.
3. Routing selector scores available backends and picks the lowest score.
4. Gateway forwards the request to the selected backend.
5. Gateway returns backend response transparently.
6. On timeout/retryable failure, gateway retries on alternate backend when possible.

## Routing Model

Backends are scored using (same model as inference gateway):

`score = inflight * W1 + latency * W2 + error_rate * W3 + hot_penalty + overload_penalty`

Where:
- `inflight`: current active requests
- `latency`: rolling latency signal
- `error_rate`: rolling failure signal
- `hot_penalty`: penalizes backends taking too large a share of recent dispatches (anti hotspot)
- `overload_penalty`: soft penalty when inflight exceeds per-backend `soft_limit`

Lower score is preferred. Backends at or above `hard_limit` inflight are excluded from selection.

Tie-break among equal scores uses random choice to avoid first-backend bias.

Optional legacy controls (disabled in production config):
- `ROUTING_EXPLORATION_RATE`: random healthy backend for fresh samples
- `ROUTING_MAX_IDLE_MS`: prefer longest-idle backend to rebalance traffic

## Reliability Controls

- Retry on timeout and retryable statuses (`502`, `503`, `504`)
- Configurable retry attempts (`RETRY_MAX_ATTEMPTS`)
- Per-backend circuit breaker:
  - Opens after repeated failures
  - Uses half-open probes after cool-down before full re-enable
  - Limits concurrent half-open probes (`CB_HALF_OPEN_MAX_PROBES`)
  - Closes circuit after enough probe successes (`CB_HALF_OPEN_SUCCESS_THRESHOLD`)
  - Excludes backend from routing during cool-down
  - Allows recovery after reset timeout

## Observability

- Structured JSON logging with gateway event schema
- Key events: startup, request finished, retry, request failed
- `routing_pick` includes:
  - `decision_reason` (`score`, `exploration`, `idle_rebalance`, `none`)
  - per-backend circuit fields (`circuit_open`, `circuit_half_open`, `half_open_inflight`, `half_open_successes`)
- Prometheus metrics:
  - request totals
  - request latency
  - backend selection
  - inflight requests
  - failures
  - retries
  - admission queue wait and rejected counts
- Operational endpoints:
  - `GET /health`
  - `GET /metrics`

## Configuration Surface

Runtime behavior is loaded from:
- **`GATEWAY_CONFIG`** YAML file (production / k8s; mirrors inference gateway ConfigMap pattern)
- **Environment variables** when `GATEWAY_CONFIG` is unset (local dev)

Key settings:
- server host/port
- timeout values
- retry policy
- circuit breaker thresholds
- per-backend `soft_limit` / `hard_limit`
- routing weights and hot-spot / overload penalties
- admission semaphore limits
- backend list
- logging options

See `README.md` and `.env.example` for concrete runtime values.

## Future Enhancements

- Admission queue / rate limiting to protect backends during burst traffic
- Dynamic backend discovery
- Adaptive routing weights based on live traffic shape
