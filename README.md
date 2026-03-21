# router-embed

HTTP proxy router for vLLM embedding API. Routes `/v1/embeddings` and `/v1/models` requests to multiple vLLM backends with configurable round-robin or failover strategies.

## Setup

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Run

```bash
cp .env.example .env   # edit EMBEDDING_BACKENDS for your vLLM servers
source venv/bin/activate
python -m router_embed.main
```

Or `router-embed` (after activating venv). If `router-embed` isn't found, use `./venv/bin/python -m router_embed.main` with no activation.

Configure clients (ingest/retrieve layers): set `EMBEDDING_URL=http://<router-host>:8011` instead of pointing directly at a vLLM server.

## Deploy (simple)

```bash
# From the project directory
source venv/bin/activate
cp .env.example .env   # edit EMBEDDING_BACKENDS
nohup python -m router_embed.main &
```

Or run in foreground (logs to terminal):
```bash
source venv/bin/activate && python -m router_embed.main
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_BACKENDS` | `192.168.86.173:8001,192.168.86.176:8001` | Comma-separated backend URLs |
| `ROUTER_STRATEGY` | `failover` | `failover` or `round_robin` |
| `ROUTER_PORT` | `8011` | Port for the router (do not use 8001) |
| `ROUTER_MAX_CONCURRENT` | `20` | Max concurrent requests; excess wait in queue |

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/embeddings` | POST | Forward to backend (OpenAI-compatible) |
| `/v1/models` | GET | Forward to backend |
| `/health` | GET | Health check |

Examples:
```bash
# Embeddings
curl -X POST http://localhost:8011/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "BAAI/bge-m3", "input": "hello world"}'

# Models
curl http://localhost:8011/v1/models

# Health
curl http://localhost:8011/health
```

## Troubleshooting

**"address already in use" (port 8011)** — Another process is using the port. Stop it: `lsof -ti:8011 | xargs kill` (macOS/Linux). Or set `ROUTER_PORT=8012` in `.env` to use a different port.

**"All backends unavailable: All connection attempts failed"** — The router could not reach any vLLM backend. Ensure:
1. vLLM is running on your backend hosts (default: 192.168.86.173:8001, 192.168.86.176:8001)
2. Your machine can reach those IPs (same network, no firewall blocking)
3. Or set `EMBEDDING_BACKENDS` in `.env` to your vLLM URLs, e.g. `localhost:8001` if vLLM runs on the same machine

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
# or: make test
```

## Publish to PyPI

One-shot via GitHub Actions (see [pypi-hello-world](https://github.com/taixingbi/pypi-hello-world)):

1. Add `PYPI_API_TOKEN` as a repo secret (Settings → Secrets → Actions). Get token at [pypi.org/manage/account/token/](https://pypi.org/manage/account/token/).
2. Push to `main` or run **Actions → Publish to PyPI → Run workflow** manually.
3. The workflow builds and uploads to PyPI.
