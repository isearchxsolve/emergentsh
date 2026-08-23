# EmergentSH — Emergent.sh clone (NVIDIA NIM inference)

Production-oriented clone of [emergent.sh](https://emergent.sh): describe an app in plain English; a multi-agent team plans, codes, tests, and produces a full-stack project. **NVIDIA NIM is the primary OpenAI-compatible inference path.** An explicitly enabled OmniRoute secondary path can fail over through measured NVIDIA model routes when NIM has a transport/upstream failure.

## Quick smoke (no Docker, no API key)

```bash
pip install -r backend/requirements.txt aiosqlite
PYTHONPATH=src:backend:. python scripts/smoke_build.py --prompt "Build a todo SaaS with auth"
# optional live preview of generated index:
PYTHONPATH=src:backend:. python scripts/smoke_build.py --serve --port 3001
```

## API server (local)

```bash
pip install -r backend/requirements.txt aiosqlite python-jose passlib bcrypt
PYTHONPATH=src:backend:. uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
# health:  curl localhost:8000/health
# build:   curl -X POST localhost:8000/api/pipeline/run-sync -H 'Content-Type: application/json' \
#            -d '{"prompt":"Build a hello SaaS","use_mock":true}'
# preview: open http://localhost:8000/preview/<job_id>/
```

## Docker smoke

```bash
export NIM_API_KEY=nvapi-...   # optional; without it, mock NIM is used
docker compose -f docker-compose.smoke.yml up --build
```

## Scaled inference through OmniRoute

Production should set `INFERENCE_PROVIDER=omniroute`,
`INFERENCE_STRICT_MODE=true`, and `OMNIROUTE_API_KEY`. OmniRoute owns the
underlying NVIDIA key rotation; individual NVIDIA keys are not configured in
EmergentSH. Direct `INFERENCE_PROVIDER=nim` remains available for development.

## OmniRoute route health

After setting the gateway credential, verify an actual completion with:

```bash
python scripts/probe_omniroute.py
```

The default ordered routes are measured NVIDIA routes through OmniRoute:
`nvidia/nvidia/nemotron-3-super-120b-a12b`,
`nvidia/nvidia/nemotron-3-nano-30b-a3b`, and
`nvidia/meta/llama-3.1-8b-instruct`. Override their order with the comma
separated `OMNIROUTE_FALLBACK_MODELS` variable. The fallback circuit opens for
30 seconds after all routes fail, so a saturated gateway cannot extend every
NIM failure.

## Layout

- `backend/` — FastAPI, agent pipeline, NIM clients
- `src/` — multi-agent system, PySide6 desktop shell, preview manager
- `frontend/` — Next.js workspace UI
- `scripts/smoke_build.py` — end-to-end prompt → artifacts → preview index
- `tests/` — agents, NIM, integration, self-debug, code generation

## Tests

```bash
pip install pytest pytest-asyncio
PYTHONPATH=src:backend:. pytest tests/ -q --ignore=tests/test_ui.py
```
