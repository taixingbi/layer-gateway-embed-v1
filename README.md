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
docker compose down
docker compose up -d
# Edit EMBEDDING_BACKENDS in docker-compose.yml

# Option B: docker run
docker build -t layer-gateway-embed-v1 .
docker run -d --restart unless-stopped -p 8011:8011 \
  -e EMBEDDING_BACKENDS=192.168.86.173:8001,192.168.86.176:8001 \
  layer-gateway-embed-v1
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
docker pull taixingbi/layer-gateway-embed-v1:latest
docker run -d --restart unless-stopped \
  --name gateway-embed \
  -p 8011:8011 \
  -e EMBEDDING_BACKENDS=192.168.86.173:8001,192.168.86.176:8001 \
  -e INTERNAL_API_KEY=1234 \
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

# Embeddings
curl -X POST http://localhost:8011/v1/embeddings \
  -H "X-Internal-Key: 1234" \
  -H "Content-Type: application/json" \
  -d '{"model": "BAAI/bge-m3", "input": "hello world"}'

curl -X POST http://192.168.86.179:8011/v1/embeddings \
  -H "X-Internal-Key: 1234" \
  -H "Content-Type: application/json" \
  -d '{"model": "BAAI/bge-m3", "input": "hello world"}'
```

**Config:** `INTERNAL_API_KEY` (required for `/v1/*`; missing server config → 500, wrong key → 401), `EMBEDDING_BACKENDS`, `ROUTER_STRATEGY` (failover|round_robin), `ROUTER_PORT` (8011)
