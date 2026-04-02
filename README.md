# layer-gateway-embed-v1

HTTP gateway in front of vLLM embedding servers (failover / round-robin).

## run local

#### venv
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```
#### run
```bash
python -m app.main
# or after pip install -e '.[dev]': router-embed
```

## Docker
```bash
# Verify: docker --version && docker compose version
# Option A: docker compose (auto-restart on Docker/PC restart)
sudo docker compose down
sudo docker compose up -d
# Verify .env
sudo docker compose exec router env | egrep 'INTERNAL_API_KEY|EMBEDDING_BACKENDS|ROUTER_|GRAFANA_'
```

## Push to Docker Hub

**GitHub Actions** (`.github/workflows/docker-push.yml`): on push to `main`, builds and pushes to Docker Hub. Add repo secrets: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`.

**Manual:**
```bash
docker login
docker tag layer-gateway-embed-v1 taixingbi/layer-gateway-embed-v1:latest
docker push taixingbi/layer-gateway-embed-v1:latest
```

**Pull and run:**
```bash
ssh tb@192.168.86.179
sudo docker pull taixingbi/layer-gateway-embed-v1:latest
sudo docker rm -f gateway-embed
sudo docker run -d --restart unless-stopped \
  --name gateway-embed \
  -p 8011:8011 \
  --env-file .env \
  taixingbi/layer-gateway-embed-v1:latest
```

## API

```bash
# Health
curl http://localhost:8011/health
curl http://192.168.86.179:8011/health

# Models
curl -H "X-Internal-Key: 1234" http://localhost:8011/v1/models
curl -H "X-Internal-Key: 1234" http://192.168.86.179:8011/v1/models

# Embeddings (non-empty X-Request-Id and X-Session-Id required)
curl -X POST http://localhost:8011/v1/embeddings \
  -H "X-Internal-Key: 1234" \
  -H "X-Request-Id: request_id_1" \
  -H "X-Session-Id: session_id_1" \
  -H "Content-Type: application/json" \
  -d '{"model": "BAAI/bge-m3", "input": "hello world"}'

curl -X POST http://192.168.86.179:8011/v1/embeddings \
  -H "X-Internal-Key: 1234" \
  -H "X-Request-Id: request_id_1" \
  -H "X-Session-Id: session_id_1" \
  -H "Content-Type: application/json" \
  -d '{"model": "BAAI/bge-m3", "input": "hello world"}'
```

**Correlation:** **`GET /health`** and **`GET /v1/models`** do not require correlation headers. For **`POST /v1/embeddings`**, both **`X-Request-Id`** and **`X-Session-Id`** must be present and non-empty (after trim); otherwise the gateway returns **400** with `missing` listing which headers were absent. For other routes, if **`X-Request-Id`** is omitted, the gateway generates one; **`X-Session-Id`** is optional. Responses echo **`X-Request-Id`**; **`X-Session-Id`** is echoed when sent. For `/v1/*` proxy routes, these headers are forwarded to the vLLM backend. Logs include **`request_id=`** / **`session_id=`** (stderr / optional Loki). Logs outside any HTTP request (startup, Loki init) use **`request_id=startup`** and **`session_id=n/a`**.

Prefer **headers only** for correlation; do **not** duplicate ids in the JSON body unless you need them there (e.g. clients that cannot set headers, or downstream consumers that only read the body). If you add them to JSON, use clear names like **`request_id`** and **`session_id`**, and confirm your vLLM / OpenAI compatibility layer accepts unknown fields.

**Config:** `INTERNAL_API_KEY` (required at startup), `EMBEDDING_BACKENDS` (at least one backend required), `ROUTER_STRATEGY` (failover|round_robin), `ROUTER_PORT` (8011), `ROUTER_RETRY_ATTEMPTS` (>0, default 1)
