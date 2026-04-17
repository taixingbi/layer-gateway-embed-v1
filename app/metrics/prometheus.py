from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

REQUESTS = Counter(
    "gateway_embed_requests_total",
    "Total embedding requests",
    ["backend", "status", "request_class"],
)
LATENCY = Histogram(
    "gateway_embed_request_latency_ms",
    "Embedding request latency in ms",
    ["backend"],
    buckets=(5, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000),
)
BACKEND_SELECTED = Counter(
    "gateway_embed_backend_selected_total",
    "Backend selected for request",
    ["backend"],
)
INFLIGHT = Gauge(
    "gateway_embed_inflight",
    "Current inflight embedding requests",
    ["backend"],
)
FAILURES = Counter(
    "gateway_embed_failures_total",
    "Failed requests",
    ["backend", "reason"],
)
RETRIES = Counter(
    "gateway_embed_retries_total",
    "Total retries",
    ["backend"],
)
ADMISSION_WAIT = Histogram(
    "gateway_embed_admission_wait_ms",
    "Queue wait before request is admitted",
    buckets=(0.1, 1, 5, 10, 25, 50, 100, 250, 500, 1000),
)
ADMISSION_REJECTED = Counter(
    "gateway_embed_admission_rejected_total",
    "Requests rejected by admission queue timeout",
)
ADMISSION_INQUEUE = Gauge(
    "gateway_embed_admission_inqueue",
    "Current requests waiting for admission",
)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
