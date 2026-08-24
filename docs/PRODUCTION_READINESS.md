# Production-readiness audit — 2026-08-24

> **Current live-generation gate (2026-08-24, revision 2):** The closed items below are recorded source/harness, workspace-browser, migration, and deployment checks. They do **not** prove that the current real OmniRoute normal-combo chain can generate a semantically valid full-stack application. The authoritative live status and its strict stage-by-stage preflight are in [OMNIROUTE_HEALTH_ROOT_CAUSE_REPORT_2026-08-24.md](OMNIROUTE_HEALTH_ROOT_CAUSE_REPORT_2026-08-24.md): **COMBO_CHAIN_BLOCKED**. In particular, the browser E2E entry below is not a pass for a newly generated app; generated-app browser E2E remains gated until the live semantic preflight passes.

> **Repository scope correction:** This document's `HISTORY_RECOVERY_BLOCKED` section describes the separate legacy `D:\god_ai\emergentsh` worktree. The authoritative standalone repository is `D:\god_ai\emergentsh-standalone-clean`, which has its configured Git remote and must not be confused with that legacy recovery exercise.

## Closed in this pass

| Area | Result | Evidence |
| --- | --- | --- |
| Frontend production build | Closed | `npm run build` completed successfully; `/`, `/workspace`, and `/_not-found` were emitted. |
| Browser E2E | Closed | `npm run e2e` completed: 2/2 Chromium workspace scenarios passed. |
| Database migration strategy | Closed for new deployments | Alembic configuration and initial revision `9936aa792817` are present. Production containers run `alembic upgrade head`; startup no longer calls `create_all` unless the explicit local-only `AUTO_CREATE_SCHEMA=true` switch is set. See `MIGRATIONS.md`. |
| Token-revocation schema | Closed | `token_revocations` is included in Alembic revision `9936aa792817`. |
| Multi-worker SSE delivery | Closed | Jobs and append-only events are stored in `pipeline_jobs` and `pipeline_events`. Each stream reads events by database ID, so independent clients and API replicas do not consume one another's events. `test_em7_durable_pipeline_stream.py` verifies replay from two independent sessions. |
| Crash-recoverable pipeline execution | Closed | Replica workers atomically lease durable jobs. Expired work can be reclaimed after process loss without double execution; migration `b724e18a09f1` adds lease and attempt metadata. |
| Scaled inference | Closed | `INFERENCE_PROVIDER=omniroute` makes OmniRoute the primary gateway and leaves NVIDIA key rotation outside NeonBuild. Strict mode fails closed. |
| Mobile source contracts | Closed | Active platform routing generates Expo/React Native or Flutter Android/iOS projects, CI, tests, identifiers, environment templates, build-readiness evidence, and an explicitly labelled interactive simulation. |
| Generated preview materialization | Closed | A required preview stage emits validated, offline, self-contained `index.html`; successful jobs no longer advertise an absent preview. |

## Still blocked by required external input

### Payments — `MONETIZER_BLOCKED`

`POST /api/credits/purchase` deliberately returns HTTP 503. This is the
correct fail-closed behaviour until a payment provider, merchant account,
product/price mapping, webhook signing secret, refund policy, and idempotency
requirements are selected and supplied. Do not enable `PAYMENTS_ENABLED` as a
way to bypass this: there is intentionally no charge/confirmation path yet.

### Git/worktree recovery — `HISTORY_RECOVERY_BLOCKED`

This checkout has one visible commit (`0d845bd`) and a mass staged deletion
plus untracked replacement state. No Git remote is configured. `git fsck`
also finds a very large set of unreachable objects, including material that is
unrelated to NeonBuild and may include secrets. These facts are insufficient
to identify an authoritative parent history safely.

Required operator input:

1. Provide the authoritative repository remote or a known-good clone/backup.
2. Preserve the current workspace and `.git` directory before attempting any
   reset, checkout, clean, or garbage collection.
3. Compare the supplied history with this extracted project in a separate
   worktree, then decide whether to transplant the NeonBuild files or restore
   the parent tree.
4. Rotate any credentials that appear in recovered historical objects; do not
   treat Git garbage as a safe secret store.

No destructive Git recovery has been performed in this pass.

## Verification performed

- Focused backend regressions: **29 passed** (`test_em1_auth_fail_closed`,
  `test_em2_credit_ledger`, and `test_em7_durable_pipeline_stream`).
- Python source compilation: `python -m compileall -q backend/app`.
- Alembic head: `9936aa792817`.
- Frontend production build: successful.
- Chromium Playwright workspace E2E: **2 passed**.
