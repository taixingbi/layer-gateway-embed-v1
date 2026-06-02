# Docker Guide

This guide covers:
- Running the gateway locally with Docker
- Publishing the image to GHCR

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- A `.env` file in repo root (you can start from `.env.example`)
- Reachable embedding backends configured in `EMBED_BACKENDS`

## 1) Local Docker Deploy (single container)

Build image from project root:

```bash
docker build -t layer-gateway-embed-v1:local .
```

Run container:

```bash
docker run --rm \
  --name layer-gateway-embed-v1 \
  --env-file .env \
  -p 30181:30181 \
  layer-gateway-embed-v1:local
```

Verify:

```bash
curl http://localhost:30181/health
curl -sS http://localhost:30181/ready | jq .
```

Expected response:

```json
{"status":"ok"}
```

## 2) Local Docker Deploy (compose)

Use compose from project root:

```bash
docker compose up --build
```

Run in background:

```bash
docker compose up -d --build
```

Stop:

```bash
docker compose down
```

## 3) Test the Embeddings Endpoint

```bash
curl -X POST http://localhost:30181/v1/embeddings \
  -H "X-Request-Id: request_id_1" \
  -H "X-Trace-Id: trace_id_1" \
  -H "X-Session-Id: session_id_1" \
  -H "Content-Type: application/json" \
  -d '{"model":"BAAI/bge-m3","input":"hello world"}'
```

## 4) Publish to GHCR

Set your GHCR namespace and target tag:

```bash
export IMAGE=ghcr.io/taixingbi/layer-gateway-embed-v1
export IMAGE_TAG=v1.0.0
```

Build and tag:

```bash
docker build -t ${IMAGE}:${IMAGE_TAG} .
docker tag ${IMAGE}:${IMAGE_TAG} ${IMAGE}:latest
```

Login and push:

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u USERNAME --password-stdin
docker push ${IMAGE}:${IMAGE_TAG}
docker push ${IMAGE}:latest
```

## 5) Pull and Run from GHCR

```bash
docker pull ${IMAGE}:latest
docker run --rm \
  --name layer-gateway-embed-v1 \
  --env-file .env \
  -p 30181:30181 \
  ${IMAGE}:latest
```

## Troubleshooting

- `503 No healthy backend available`: verify `EMBED_BACKENDS` and backend health.
- `429 Gateway busy`: increase `ADMISSION_MAX_CONCURRENT` or `ADMISSION_WAIT_TIMEOUT_MS`.
