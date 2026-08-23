# REMEDIATION_WORKLOG — emergentsh (C:\god_ai\emergentsh)

Executing `D:\omniroute-monetizer\MASTER_REMEDIATION_PROMPT.md` gaps EM-1..EM-6.
Baseline before remediation: **8 failed, 68 passed, 1 skipped** (all 8 failures
pre-existing; root causes catalogued in entry #1).

---

### [2026-08-22] #1 — BASELINE RECON + ROOT-CAUSE CATALOGUE OF THE 8 PRE-EXISTING FAILURES

**[VERIFY]** Ran `python -m pytest tests/ -q` before touching anything:
`8 failed, 68 passed, 1 skipped in 5.35s`. Investigated each failure:

1. `tests/baseline/test_suite.py::TestL1VisionAndNIMExclusivity::test_no_mock_fallback_in_pipeline_router`
   — ROOT_DIR bug: `ROOT_DIR = Path(__file__).resolve().parents[1]` resolves to
   `emergentsh/tests/`, so it looks for `tests/backend/app/api/pipeline.py`.
   Needs `parents[2]`.
2. `test_next_config_has_standalone_output` — same ROOT_DIR bug (file exists
   and DOES contain `output: 'standalone'`; test just looks in wrong dir).
3. `test_workspace_component_hydration_safety` — same ROOT_DIR bug.
4. `test_frontend_dockerfile_multistage_structure` — same ROOT_DIR bug
   (frontend/Dockerfile exists, is multi-stage, copies .next/standalone).
5. `test_docker_compose_config_validity` — same ROOT_DIR bug (docker-compose.yml
   exists and references NIM_API_KEY/NVIDIA_API_KEY at lines 49-50).
6-8. `tests/test_integration.py::TestFullPipeline` (3 tests) — REAL pipeline
   bug, maps to gap EM-3: `AgentPipeline.run()` has a 3-retry self-heal loop
   for ValueError, but `stream_run()` has NO retry loop. The mock NIM client's
   designer branch yields a Markdown heading ("# Design Specification...")
   instead of JSON, DesignerAgent raises ValueError, stream_run fails the
   pipeline after 2 of 7 agents (`assert 2 == 7`). Also the mock fixture has
   no "qa"/"devops" branches, so even with retry parity the fixture needs
   those branches to complete all 7 agents.

Also discovered during recon:
- `backend/app/api/pipeline.py` routes `/run /stream /status /jobs /export
  /credits` are ALL unauthenticated; `USER_CREDITS = 10` is a process-global.
- `backend/app/core/auth.py:14` — `SECRET_KEY = os.getenv("SECRET_KEY",
  "your-secret-key-change-in-production")` — forgeable default, no boot check.
- Ambient shell carries stale `DATABASE_URL=postgres://postgres:***@localhost:5432/crypto_db`
  (legacy from another project; SQLAlchemy rejects the `postgres://` scheme).
  No existing test imports `backend.app.main`, which is why this never
  surfaced. New tests pin `DATABASE_URL=sqlite+aiosqlite` before import.
  (Secrets redacted per T11 — the password in that URL is a local dev default
  and is not logged here.)

---

### [2026-08-22] #2 — GAP-EM-1 FIXED: SECRET_KEY fail-closed boot + pipeline route auth + bcrypt/passlib runtime break

**[VERIFY]** Confirmed by reading `backend/app/core/auth.py` (hardcoded
forgeable default, no validation anywhere) and `backend/app/api/pipeline.py`
(six routes with zero auth dependencies, global credit counter).

**[FIX]** Three changes:

1. **Fail-closed boot** (`backend/app/core/auth.py` + `backend/app/main.py`):
   - Added `INSECURE_SECRET_KEYS` frozenset (empty string, the shipped
     default, and other common defaults), `MIN_SECRET_KEY_LENGTH = 32`.
   - Added `validate_secret_key(secret=None)` raising `RuntimeError` on
     missing / known-insecure / too-short keys.
   - `main.py` lifespan now calls `validate_secret_key()` BEFORE `init_db()`:
     a served app refuses to boot on a forgeable signing key. Module import
     stays side-effect-free so unit tests can still import.
2. **Route auth + job ownership** (`backend/app/api/pipeline.py`):
   - All six routes now take `current_user: User = Depends(get_current_active_user)`.
   - `/run` records `user_id` on the job; `_job_owner()` enforces ownership
     on `/status`, `/stream`, `/export` (returns 404, not 403, to avoid job
     existence leaks); `/jobs` is scoped to the owner (superuser sees all).
3. **Latent runtime break found while testing (fixed as part of EM-1):**
   `passlib 1.7.4` is incompatible with the installed `bcrypt 5.0.0` —
   `get_password_hash()` raised `ValueError: password cannot be longer than
   72 bytes` for ANY password, so `/api/auth/register` was broken at runtime
   (no test exercised it because the only TestAuth class lives inside a mock
   string literal in test_integration.py). Replaced the passlib CryptContext
   with direct `bcrypt.hashpw/checkpw` calls and explicit 72-byte truncation
   (bcrypt's algorithm cap, which passlib used to apply silently).

**[TEST]** New `tests/test_em1_auth_fail_closed.py` — **22/22 PASS**:
- `TestPasswordHashing` (3): hash/verify round trip, >72-byte password
  truncated not crashed, garbage hash returns False.
- `TestValidateSecretKey` (6): missing/known-default/short refused, strong
  accepted, every entry of INSECURE_SECRET_KEYS refused, shipped module
  default refused.
- `TestBootFailClosed` (3): lifespan raises on insecure default, raises on
  short key, boots cleanly on strong key.
- `TestPipelineRouteAuth` (10): 401 matrix across all six routes for
  anonymous callers; valid-token /run accepted and records owner; cross-user
  isolation (user B gets 404 on user A's status/export, A's jobs absent from
  B's list); /credits with token; token FORGED with the old insecure default
  key is rejected 401.

Test-infra notes (honest): pytest-asyncio 0.23.5 async fixtures crash with
`'FixtureDef' object has no attribute 'unittest'` on this pytest version, so
the client is a sync `client_factory` fixture returning an async context
manager. The get_db override must commit per-request (mirroring the real
get_db) or register→login can't see the new user.

**[VERIFY-REGRESSION]** Full suite after fix: **90 passed, 8 failed, 1 skipped**
— exactly the same 8 pre-existing failures as baseline (68+22=90), zero new
failures. The 8 are tracked for EM-3/EM-4 and the ROOT_DIR bug.

**[COMMIT]** next.

---

### [2026-08-22] #3 — GAP-EM-2 FIXED: per-user persisted credit ledger replaces process-global USER_CREDITS

**[VERIFY]** `backend/app/api/pipeline.py` had `USER_CREDITS = 10` as a
module global: every caller shared one balance, it reset on every restart,
and `/credits` reported it regardless of who asked. Meanwhile the schema
ALREADY had the right primitives unused by the pipeline: `User.credits`
(default 1000) and `CreditTransaction` (amount/transaction_type/description
audit rows, already used by /api/credits/purchase).

**[FIX]** `backend/app/api/pipeline.py`:
- Deleted the `USER_CREDITS` global entirely; added `PIPELINE_RUN_COST = 1`.
- New `_debit_credits(db, user, amount, description)`: raises 402 when the
  caller's persisted balance cannot cover the cost, else decrements
  `user.credits` and writes a `CreditTransaction(amount=-1,
  transaction_type="usage")` row; both land in the request session's single
  commit (atomic).
- `/run` now depends on `get_db` and calls `_debit_credits` before creating
  the job — a refused run creates no job.
- `/credits` now returns the CALLER's persisted balance
  (`current_user.credits`), not a shared global.

**[TEST]** New `tests/test_em2_credit_ledger.py` — **6/6 PASS**:
- global USER_CREDITS attribute is gone (regression guard)
- /credits reports own persisted balance (1000 model default, not 10)
- /run debits exactly 1 credit AND writes exactly 1 usage audit row
- zero balance -> 402 AND no job created
- user A's run leaves user B's balance untouched
- 3 runs -> balance 997 AND exactly 3 audit rows summing to -3 (atomicity)

**[VERIFY-REGRESSION]** Full suite: **96 passed, 8 failed, 1 skipped** —
same 8 pre-existing failures, zero new.

**[COMMIT]** next.

---

### [2026-08-22] #4 — GAP-EM-3 + GAP-EM-4 FIXED: stream_run retry parity + structural design-token lint; suite driven to ZERO failures

**[VERIFY]** Confirmed `run()` had a 3-retry self-heal loop while
`stream_run()` (the path the UI uses) had none — a transient ValueError
killed the stream after 2 of 7 agents. Confirmed FrontendAgent's "moat" was
`if "backdrop-blur" not in code and "transition" not in code` — a string
search any text can pass and legitimate UIs can fail.

**[FIX] EM-3 (backend/agent_pipeline.py):**
- Extracted the retry policy into ONE function `_run_agent_with_retry()`
  (MAX_AGENT_RETRIES=3; ValueError retryable with error fed back to the
  agent; any other exception fails the pipeline). BOTH `run()` and
  `stream_run()` now route through it — no drift possible.
- stream_run retries resume IN-PLACE (resume-from-stage): `agent_start` is
  yielded once per stage, so SSE consumers never see duplicated events for a
  stage that eventually succeeds; on exhausted retries it yields one
  `agent_error` then `pipeline_complete` with status=failed.
- Default chain is now the documented 7-agent contract (planner, designer,
  frontend, backend, integration, qa, devops). SeleniumQAAgent stays defined
  for opt-in use but is not in the default chain (it made the chain 8 agents
  and its host-executed Playwright tests could never pass in CI).
- DesignerAgent now also emits DESIGN.md (human-readable Markdown rendered
  from the validated tokens via `_design_markdown()`), completing the
  generated-project artifact contract.

**[FIX] EM-4 (backend/agent_pipeline.py):**
- New `lint_frontend_design_tokens(code, design_json)` structural lint:
  module structure (import/export), component definition, >=3 styling
  applications (className/style/styled/css/sx), >=1 motion/interaction
  primitive (transition/animation/keyframes/motion./hover:/active:/focus:),
  and palette fidelity (at least one of the designer's hex colors must
  appear in the code). `extract_palette_colors()` pulls hexes from the
  validated designer tokens. FrontendAgent.run now raises ValueError with the
  full violation list instead of the string search.

**[FIX] Test fixture (tests/test_integration.py mock_nim_client):**
- Routing conditions matched on USER-message keywords ("plan", "design",
  "react", "docker", "test") that every later agent's prompt embeds — a
  landmine. All six branches now match on SYSTEM-prompt role strings only.
- Designer branch now yields valid JSON tokens (was Markdown, which failed
  DesignerAgent's JSON validation — the original cause of the 2-of-7 death).
- Frontend branch now yields a styled component that passes the EM-4 lint
  (palette colors, transitions, backdrop-blur, 3+ className applications).
- QA branch now yields a SELF-CONTAINED passing test (the old one imported
  backend.main/backend.database/backend.models which the generator never
  emits, so the host-executed pytest always failed and QA could never
  complete). Added a devops branch for the 7th agent.

**[FIX] tests/baseline/test_suite.py ROOT_DIR bug:** `parents[1]` resolved to
tests/ instead of the repo root, failing 5 baseline tests that audit files
which all exist and are correct. Now `parents[2]`.

**[TEST]**
- New tests/test_em3_stream_retry_parity.py — 7/7 PASS (run retries, stream
  retries mid-stream [the acceptance test], no duplicate SSE events on
  retry, exhausted retries fail loudly, fatal errors not retried in either
  path, both paths share _run_agent_with_retry, 7-agent chain contract).
- New tests/test_em4_design_token_lint.py — 14/14 PASS (compliant page
  passes with/without design, empty/plain-text fail, each violation category
  isolated, palette extraction, old string-search gate gone).
- The 3 previously-failing TestFullPipeline tests now PASS.

**[VERIFY-REGRESSION]** Full suite: **125 passed, 0 failed, 1 skipped** —
from 8 failures at baseline to ZERO.

**[COMMIT]** next.

---

### [2026-08-22] #5 — GAP-EM-5 FIXED: hardened Docker sandbox for sandbox_executor.py

**[VERIFY]** `backend/sandbox_executor.py` was a 50-line bare host subprocess
(`subprocess.run(["pytest", target])`) with zero isolation — generated,
untrusted test code ran with full host privileges.

**[FIX]** Rewrote the executor sharing the NU-3 hardened-container design
from neon_unified (do-not-reinvent rule):
- `isolation` mode: "auto" (default; Docker when daemon up, host fallback
  when down), "docker" (FAIL CLOSED when daemon unreachable — explicit
  BLOCKED message naming the refused fallback, never a silent host drop),
  "host" (explicit).
- Hardened container flags: `--network none --read-only --tmpfs /tmp
  --cpus 1.0 --memory 512m --workdir /project -v <project>:/project`,
  constant command-string list (no shell interpretation).
- Path safety: absolute paths and `..` traversal rejected before any exec;
  missing target = failure, never a silent pass.
- Public contract unchanged: `run_pytest()` still returns (success, output),
  so QAAgent/SeleniumQAAgent call sites are untouched.

**[TEST]** New tests/test_em5_sandbox_executor.py — **11/11 PASS**:
- Escape attempts blocked (the acceptance test): traversal, nested
  traversal, absolute path, shell-metachar path (verified exec is a list
  with shell=False and nothing runs for a bogus path), missing target.
- Hardened flags asserted on the generated docker command.
- Fail-closed: isolation=docker + daemon down -> BLOCKED (not host);
  auto + daemon down -> host fallback; daemon up -> container path used;
  container pytest failure is not a silent pass.

**[ENV NOTE]** Docker daemon is DOWN on this host (`docker info` -> 500
Internal Server Error on the DockerDesktopLinuxEngine pipe). So container
execution is unit-verified via mocked subprocess; the full-suite QA path
exercises the honest auto->host fallback (suite time rose 21s -> 70s
because the QA agent's generated tests now actually execute). When the
daemon is restored, the same code path runs containerized with no changes.

**[VERIFY-REGRESSION]** Full suite: **136 passed, 0 failed, 1 skipped**.

**[COMMIT]** next.
