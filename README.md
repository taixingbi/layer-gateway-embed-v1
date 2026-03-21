# router-embed

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
kill -9 $(lsof -t -i:8011) 
```

## Docker
```bash
# Verify: docker --version && docker compose version
# Option A: docker compose (auto-restart on Docker/PC restart)
docker compose down
docker compose up -d
# Edit EMBEDDING_BACKENDS in docker-compose.yml

# Option B: docker run
docker build -t router-embed .
docker run -d --restart unless-stopped -p 8011:8011 \
  -e EMBEDDING_BACKENDS=192.168.86.173:8001,192.168.86.176:8001 \
  router-embed
```

## Push to Docker Hub

**GitHub Actions** (`.github/workflows/docker-push.yml`): on push to `main`, builds and pushes to Docker Hub. Add repo secrets: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`.

**Manual:**
```bash
docker login
docker tag layer-router-embed-v1 taixingbi/layer-router-embed-v1:latest
docker push taixingbi/layer-router-embed-v1:latest
```

**Pull and run:**
```bash
docker pull taixingbi/layer-router-embed-v1:latest
docker run -d --restart unless-stopped -p 8011:8011 \
  -e EMBEDDING_BACKENDS=192.168.86.173:8001,192.168.86.176:8001 \
  taixingbi/layer-router-embed-v1:latest
```

## API

```bash
# Health
curl http://localhost:8011/health

# Models
curl http://localhost:8011/v1/models

# Embeddings
curl -X POST http://localhost:8011/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "BAAI/bge-m3", "input": "hello world"}'
```

**Config:** `EMBEDDING_BACKENDS`, `ROUTER_STRATEGY` (failover|round_robin), `ROUTER_PORT` (8011)
