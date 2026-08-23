# Plan: Clone of Emergent.sh using NVIDIA NIM as Inference Engine

Emergent.sh is the world's first truly agentic "vibe coding" platform: a user describes an app in plain English and a coordinated team of specialized AI agents (Architect, Designer, Developer, Integration, Product Manager) plans, codes, tests, debugs, and deploys a production-ready full-stack application (React/Next.js frontend, FastAPI backend, MongoDB/Postgres database, built-in auth) with live preview, GitHub sync, version rollback, and credit-based usage. This project delivers a 100% working clone of that experience with **NVIDIA NIM as the exclusive inference engine** for every agent call.

## Requirements

### Functional
- **R1 — Landing & Onboarding:** Polished modern SaaS landing page ("Describe your idea → Build websites & apps with AI") with sign-in / start-project flow. Dark/light developer-grade aesthetic matching emergent.sh quality. No lorem ipsum, no "coming soon".
- **R2 — Conversational Workspace:** Chat interface where the user talks to the agent team. Messages stream in real time; agent activity (planning → coding → testing → deploying) is visualized as a progress feed. User can iterate ("add dark mode", "fix the login bug", "add a payments page").
- **R3 — Live Preview Pane:** A live, runnable preview of the generated app that updates as the agents build. Must render a real running app, not a static screenshot.
- **R4 — Project Dashboard:** History of projects, deployed URLs, GitHub sync status, credit balance/usage, model/agent selector.
- **R5 — Multi-Agent Code Generation (NIM-exclusive):** A coordinated agent team powered **only** by NVIDIA NIM:
  - Orchestrator/Manager Agent — task breakdown, architecture blueprint, coordination.
  - Frontend Agent — React/Next.js components, layouts, styling.
  - Backend Agent — FastAPI/Node API, auth, business logic.
  - Database Agent — schema, migrations, queries.
  - Tester/Debugger Agent — runs tests, detects failures, self-heals.
  - Deployer Agent — produces runnable preview + deployable artifact.
  - Agents must produce **real, executable code** — not placeholders or TODO stubs.
- **R6 — Prompt → Working App Loop:** Given a prompt like "Build a SaaS task manager with user auth, Stripe billing, and a dashboard", the system iteratively produces a working full-stack app that can be previewed and exported.
- **R7 — Iteration & Error Recovery:** Continue the conversation to refine; agents self-detect errors, root-cause, and apply fixes without user intervention.
- **R8 — Export & GitHub Sync:** Export/download code; GitHub repo sync with meaningful commit history.
- **R9 — Auth & Persistence:** User authentication for the clone itself; persistent projects, conversations, generated artifacts, deployment status.
- **R10 — Credit System:** Credit consumption tracking per build/agent action.
- **R11 — Integrations Settings:** UI for GitHub, auth providers, Stripe-like payments, database configuration.

### Non-Functional
- **N1 — NIM Exclusivity:** NVIDIA NIM is the **only** inference engine for all generative/reasoning calls. No OpenAI, Anthropic, Gemini, Groq, OpenRouter. Document exact NIM models + endpoints used.
- **N2 — Streaming:** Real-time progress via SSE or WebSocket so the user sees agents working live.
- **N3 — Job Queue:** Real task queue for long-running multi-agent builds (not blocking HTTP).
- **N4 — Security:** Secure handling of NIM API keys/endpoints; user auth; no secrets in client.
- **N5 — Runnable Deliverable:** docker-compose (or equivalent) so a user can start the platform, describe an app, and receive a previewable result.
- **N6 — Quality:** Tests for critical paths; clear docs for configuring NIM credentials.
- **N7 — Stack:** React/Next frontend, FastAPI backend, Postgres/SQLite persistence, NIM inference layer isolated from platform logic.

## Risks

- **K1 — NIM Availability/Rate Limits:** NIM endpoints may rate-limit or be unavailable; long multi-agent builds can stall. *Mitigation:* retry/backoff, configurable timeout, queue with status surfacing, allow resuming.
- **K2 — Code Generation Quality:** LLM-generated code may be non-functional or contain subtle bugs. *Mitigation:* Tester/Debugger agent loop with real test execution; iterative self-healing; sandboxed execution.
- **K3 — Live Preview Sandboxing:** Running generated apps safely in-browser/server is hard. *Mitigation:* isolated container/iframe per project; resource limits; ephemeral preview servers.
- **K4 — Context Window Limits:** Large builds exceed token limits. *Mitigation:* per-agent scoped context, summarization, "fork" mechanism (fresh context, preserved code).
- **K5 — Scope Creep vs. emergent.sh Parity:** Full parity is enormous. *Mitigation:* prioritize the core prompt→plan→code→test→preview loop first; layer iteration, credits, GitHub after core works.
- **K6 — Secret Leakage:** NIM keys must never reach the browser. *Mitigation:* server-only env vars; proxy all NIM calls through backend.
- **K7 — Non-Determinism:** Same prompt → different builds. *Mitigation:* seed/version prompts; persist agent transcripts for reproducibility.
- **K8 — Windows Dev Environment:** Tooling (docker, node, python) on Windows host. *Mitigation:* cross-platform scripts; document Windows-specific setup.

## Acceptance Criteria

A non-technical user can:
1. **Open** the cloned platform (via docker-compose up) and see a polished landing/onboarding page.
2. **Sign in / start** a new project.
3. **Type** a natural-language description of an application (e.g. "Build a SaaS task manager with user auth, Stripe billing, and a dashboard").
4. **Watch** a multi-agent team — powered **exclusively by NVIDIA NIM** — plan, code, test, and produce a working full-stack app, with streaming progress visible in the UI.
5. **See a live preview** of that app rendering and functioning.
6. **Iterate via chat** ("add dark mode", "fix the login bug") and watch the preview update.
7. **Export the code** or obtain a deployable artifact (download / GitHub sync).
8. **Verify** the entire inference path uses only NVIDIA NIM (no other provider calls in logs/code).
9. **Persistence:** projects, conversations, and artifacts survive restarts; credits are tracked.
10. **Verification report:** a recorded flow / screenshots of a real non-trivial app built from a single prompt using only NIM.

### Gate Definition (Planning Phase)
- PLAN.md contains real Requirements, Risks, and Acceptance Criteria sections (this document).
- ≥5 todos created for downstream phases.
- NIM connectivity + working client confirmed (already green: `pytest tests/test_nim_client.py -v`).
