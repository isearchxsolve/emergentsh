# EmergentSH — Emergent.sh clone (NVIDIA NIM inference)

Production-oriented clone of [emergent.sh](https://emergent.sh): describe an app in plain English; a multi-agent team plans, codes, tests, and produces a full-stack project. **All generative inference is routed through NVIDIA NIM** (OpenAI-compatible).

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

## Live NIM

Set `NIM_API_KEY` or `NVIDIA_API_KEY` (from https://build.nvidia.com). Omit `use_mock` / use `--live` on the smoke script.

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
