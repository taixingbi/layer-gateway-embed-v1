# router-embed

## run local
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
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
