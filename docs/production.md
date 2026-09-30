# Production deployment

Primary path: **in-process models** from Hugging Face Hub ids or filesystem
paths, shared `StateStore`, graph/speculate. Stubs under `src/models/stub_*`
are **test fixtures only** — `MOM_INCLUDE_STUBS=0` (default).

Optional: `MOM_BACKEND=http` for external OpenAI-compatible / Anthropic APIs.

## Architecture

```
Client → mom.server (/v1/run, /v1/chat, /health, /ready)
              ↓
         GraphRegistry (speculate_chat, …)
              ↓
         ModelDirectory (prod.router, prod.chat.fast, prod.chat.strong, …)
              ↓
         Local engines (transformers) ← HF Hub or ./weights/<path>
```

## Configure

```bash
cp .env.example .env
pip install -r requirements-local.txt   # torch + transformers + huggingface_hub

# Hub ids (downloaded into MOM_WEIGHTS_DIR/hub/…)
#   MOM_CHAT_FAST=HuggingFaceTB/SmolLM2-135M-Instruct
#   MOM_CHAT_STRONG=HuggingFaceTB/SmolLM2-360M-Instruct
#   MOM_EMBED=sentence-transformers/all-MiniLM-L6-v2

# Or local paths you already own:
#   MOM_CHAT_FAST=./weights/my-slm
#   MOM_CHAT_STRONG=/data/models/my-llm
```

Gated Hub repos: set `HF_TOKEN`.

## Run the API

```bash
source .venv/bin/activate
maturin develop
python -m mom.server
# → http://0.0.0.0:8080
```

```bash
curl -s localhost:8080/health | jq
curl -s localhost:8080/ready | jq
curl -s localhost:8080/v1/run -H 'content-type: application/json' \
  -d '{"input":"hello","graph":"speculate_chat"}' | jq
```

## Library use

```python
from mom import MoM

app = MoM()  # MOM_BACKEND=local → HF / path adapters
print(app.chat("hello").text)
```

## Production ids

| Id | Role |
| --- | --- |
| `prod.router` | Heuristic (optional local LM via `MOM_ROUTER`) |
| `prod.chat.fast` | Local causal LM (`MOM_CHAT_FAST` Hub id or path) |
| `prod.chat.strong` | Local causal LM (`MOM_CHAT_STRONG`) |
| `prod.embed` | Local embedder (`MOM_EMBED`) |

## Ops checklist

- [ ] Secrets only via env (`HF_TOKEN`, …) — never commit `.env`
- [ ] `MOM_WEIGHTS_DIR` on fast local disk; models cached under `hub/`
- [ ] `MOM_DEVICE` / `MOM_DTYPE` match GPU/MPS/CPU
- [ ] `MOM_MAX_RUNS` / `MOM_MAX_MODEL_WORKERS` sized to VRAM
- [ ] `/ready` behind the load balancer; `/health` for liveness
- [ ] JSON logs: `MOM_LOG_JSON=1`

## What is still explicitly out of scope

- Publishing to PyPI (install from this repo)
- Multi-host shared `StateStore` (v1 remains colocated)
- Guaranteeing latency-hide on serial / reconcile graphs
