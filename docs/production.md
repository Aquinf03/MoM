# Production deployment

This is the real path: OpenAI-compatible / Anthropic adapters, env config, HTTP
service, Docker, CI. Stubs under `src/models/stub_*` are **test fixtures only** —
set `MOM_INCLUDE_STUBS=0` (default) in production.

## Architecture

```
Client → mom.server (/v1/run, /v1/chat, /health, /ready)
              ↓
         GraphRegistry (speculate_chat, …)
              ↓
         ModelDirectory (prod.router, prod.chat.fast, prod.chat.strong, …)
              ↓
         httpx → Ollama/vLLM/OpenAI/Anthropic
```

## Configure

```bash
cp .env.example .env
# Local (recommended for colocated latency):
#   MOM_PREFER_LOCAL=1
#   ollama serve && ollama pull llama3.2
# Cloud:
#   MOM_PREFER_LOCAL=0
#   OPENAI_API_KEY=...
#   ANTHROPIC_API_KEY=...   # optional strong path
```

## Run the API

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt   # includes starlette/uvicorn
cd python && maturin develop && cd ..

python -m mom.server
# → http://0.0.0.0:8080
```

```bash
curl -s localhost:8080/health | jq
curl -s localhost:8080/ready | jq
curl -s localhost:8080/v1/run -H 'content-type: application/json' \
  -d '{"input":"hello","graph":"speculate_chat"}' | jq
```

## Docker Compose (Mom + Ollama)

```bash
docker compose up --build
# pull a model inside the ollama container once:
docker compose exec ollama ollama pull llama3.2
```

## Library use (no HTTP)

```python
from mom.config import Settings
from mom.runtime import build_directory, build_registry, concurrency_limits
from mom import Session

settings = Settings.from_env()
directory = build_directory(settings)
registry = build_registry(directory)
spec = registry.pick(directory, "speculate_chat")
session = Session(directory, spec.graph, limits=concurrency_limits(settings))
print(session.say("hello").output)
```

## Production ids

| Id | Role |
| --- | --- |
| `prod.router` | Route to fast vs strong (heuristic + optional model) |
| `prod.chat.fast` | OpenAI-compatible chat (local or cloud) |
| `prod.chat.strong` | Anthropic if keyed, else stronger system prompt on same endpoint |
| `prod.embed` | OpenAI-compatible embeddings |

## Ops checklist

- [ ] Secrets only via env / secret manager — never commit `.env`
- [ ] `MOM_MAX_RUNS` / `MOM_MAX_MODEL_WORKERS` sized to GPU/CPU
- [ ] `/ready` behind the load balancer; `/health` for liveness
- [ ] JSON logs: `MOM_LOG_JSON=1`
- [ ] CI green on every PR (`.github/workflows/ci.yml`)
- [ ] Live smoke against your real endpoint before promoting a build

## What is still explicitly out of scope

- Publishing to PyPI (install from this repo)
- Multi-host shared `StateStore` (v1 remains colocated)
- Guaranteeing latency-hide on serial / reconcile graphs
