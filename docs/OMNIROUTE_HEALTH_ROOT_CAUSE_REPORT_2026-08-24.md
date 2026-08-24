# NeonBuild / OmniRoute Live Semantic Preflight Report

**Revision:** 2 — evidence-aligned final update

**Date:** 2026-08-24

**Scope:** NeonBuild's real, non-mock generated-application pipeline through the local OmniRoute pathway

**Overall status:** **COMBO_CHAIN_BLOCKED**

**Browser generated-app E2E:** **NOT AUTHORIZED TO RUN YET**

## Executive verdict

NeonBuild's local pipeline implementation is materially stronger than the prior baseline: generated-project QA import isolation, frontend retry context, OmniRoute streaming handling, long phase timeouts, and provider route selection were corrected and committed. The relevant Python suites pass.

That does **not** establish production readiness for real generated applications. The strict live OmniRoute *normal-combo* chain has not yet completed with a semantically valid artifact at every stage. A transport-level HTTP `200`, a provider dashboard "connected" label, or NeonBuild's `/health` response is insufficient evidence: every model response must satisfy the contract of the pipeline stage that received it.

Therefore, the following remains deliberately gated:

- browser E2E of a live generated application;
- a claim that the generated application is production-ready;
- a claim that OmniRoute fallback/routing is healthy as an end-to-end combo chain.

## Exact preflight standard used

This is the required preflight, in order. It is intentionally stage-by-stage before any end-to-end browser claim.

| Gate | Required evidence | Current result |
| --- | --- | --- |
| 0. Live route reachability | OmniRoute configured at NeonBuild's local OpenAI-compatible endpoint; no mock provider | **Pass (transport/config only)** |
| 1. Planner | A real plan that parses and contains the required product requirements | **Observed passing in recorded jobs** |
| 2. Designer | Complete design tokens and required visual contract categories | **Observed passing in recorded jobs** |
| 3. Frontend | A single valid `App.tsx` response with runnable React component, product UI, and API-client contract | **Failing / not yet revalidated after latest routing change** |
| 4. Backend | Runnable API, validation, persistence/auth contract as required by the generated product | **Not authorized until frontend gate passes** |
| 5. Integration | Frontend/backend agreement, environment wiring, and deterministic repair where needed | **Not reached in a fully healthy live run** |
| 6. Preview | Faithful executable preview; no false-success mock fallback | **Not reached in a fully healthy live run** |
| 7. QA | Generated backend tests, frontend build, API smoke checks, and generated browser tests pass | **Earlier run exposed an import-layout defect; code fix committed; must be re-run live** |
| 8. DevOps | Deployable host-native web/mobile artifacts and configuration | **Not reached** |
| 9. Host-native generated-app run | The actual generated application starts and serves its API/preview without Docker | **Not reached** |
| 10. Browser E2E | Browser validates the real generated preview, primary flow, errors, and responsive UI | **Blocked by gates 3–9** |

### Required execution constraints

- `use_mock=false`; no synthetic success may count as a live result.
- OmniRoute is the provider path; it must use its normal routing/fallback policy rather than a single hard-coded NVIDIA key.
- Each node/phase has a **600-second** total upstream budget; a 120-second cutoff is not suitable for real app-generation work.
- Generated artifacts must be isolated in their project directory. No Docker is used on this machine (`SANDBOX_ISOLATION=host`).
- Event updates must stay visible to the user throughout the run, but status messages are not proof of artifact validity.
- A retry only passes when its returned artifact passes the node's validator; a second failure must remain diagnosable from persisted events.

## Recorded live evidence

The following job records are evidence from the real, non-mock path. They are not treated as successful E2E runs.

| Job | Furthest verified point | Failure / finding | Interpretation |
| --- | --- | --- | --- |
| `609965db4299` | Planner → Designer → Frontend → Backend → Integration → Preview | QA loaded the host/root `main.py` because the generated test used a bare `main` import, then failed with a missing `Base` attribute | A generated-project QA import-isolation defect, now addressed in source; requires live regression |
| `c694405d07af` | Planner → Designer | Frontend retries produced a static/non-component/non-API artifact rejected by the strict frontend validator | Correct rejection; semantic generation failure, not a UI success |
| `44392e8f10b1` | Planner → Designer | Frontend response was a ChatGPT Web refusal/non-code response and failed after retries | Correct rejection; provider transport availability did not yield a usable artifact |

An isolated Gemini frontend-route request was also observed to return HTTP `200` with approximately 4,796 output tokens in about 47 seconds. The invoking process did not remain attached long enough to capture and validate the full returned `App.tsx`. This is **promising provider telemetry, not a successful frontend gate**.

## Provider and routing findings

The issue is not simply "NVIDIA down". The normal-combo system must tolerate a provider being unavailable, but its alternatives must also generate valid stage-specific output.

| Path / provider observation | Latest measured behaviour | Effect on live combo health | Required remediation |
| --- | --- | --- | --- |
| NVIDIA NIM through OmniRoute | Account/credit/cooldown state was unavailable in the observed logs | Route is skipped or cannot contribute capacity | Restore account capacity separately; keep it optional in the combo, not a single point of failure |
| Alibaba/Qwen route | Observed HTTP `400`; associated connection state was stale/expired | Not a reliable fallback | Re-authenticate/repair provider configuration and re-probe with a minimal structured generation request |
| ChatGPT Web route | Transport was reachable, but frontend requests produced refusal/non-code content | Semantically unhealthy for the Frontend node | Restrict it to compatible stages or improve route/prompt/response handling; a `200` must not be promoted to success |
| Gemini route | Long response observed on the selected frontend route | Candidate fallback, but artifact not yet captured and structurally validated | Run the exact Frontend-node probe with full 600-second capture and strict validation, then include it in a complete combo run |
| LLM7 route | Observed expired authorization / HTTP `401` | Not usable until re-authenticated | Repair authorization, verify a minimal completion, then restore only after semantic probe passes |

### Root-cause analysis

1. **Credential/entitlement drift exists on more than one provider.** At least one provider was unavailable for account/cooldown reasons and other connections showed expired or malformed/stale configuration. This lowers fallback capacity.
2. **Transport success was previously too easy to overinterpret.** A connection can return HTTP `200` yet give a refusal, prose, truncated code, or a static scaffold. The former process lacked enough semantic evidence before declaring a route healthy.
3. **The frontend artifact is the present bottleneck.** Planner and Designer contracts passed in the recorded runs; the Frontend node correctly rejected non-runnable output. The strict validator is doing its job, but a capable route needs to be proven under the actual full prompt envelope.
4. **A separate QA layout defect was uncovered, not hidden.** Generated tests importing bare `main` could resolve to a host module rather than the generated backend. That was a harness defect, distinct from the provider issue, and source-level protections were added.
5. **Earlier short caller windows obscured long generation completion.** Node budgets are now ten minutes, but every invoking/testing process must also remain attached long enough to collect and validate the response.

## Remediations implemented in NeonBuild

These changes are committed in `4ef4ddd8474c9b4badaea97668a8ee4f9821ca63` (`fix: harden OmniRoute pipeline generation and QA`):

- QA bootstrap now targets generated `backend/main.py` explicitly and rejects ambiguous bare/dynamic `main` imports.
- QA repair distinguishes an import-layout failure from a genuine generated-backend failure.
- Frontend retry attempts retain the invalid artifact context for the next repair prompt.
- Frontend delivery is constrained to one compact `App.tsx` response envelope, reducing partial/multi-message artifacts.
- OmniRoute streaming is enabled by default, stops correctly on terminal stream markers, and honours a 600-second total deadline.
- The selected Gemini frontend route was updated, while keeping automatic/fallback route options available through OmniRoute.
- Pipeline jobs and append-only events are durable. SSE clients replay events by database ID, and worker leases support replica recovery; these are code-level deployment protections, separate from the live semantic generation gate.
- Production schema changes use Alembic. `create_all` is an explicit opt-in compatibility path for disposable local/test databases, not the production migration mechanism.

## Verification already completed

| Verification | Result |
| --- | --- |
| `backend/tests/test_agent_pipeline.py` | **31 passed** |
| `backend/tests/test_nim_client.py -vv` | **16 passed** |
| `backend/tests/test_mobile_targets.py` | **9 passed** |
| Combined recorded Python evidence | **56 passed** (Pydantic warnings only) |
| Local backend health after restart on port 8005 | `healthy`; inference configured for OmniRoute — configuration/reachability evidence only |
| Fresh frontend build invoked during final review | Compilation completed and reached type/lint validation; the caller window ended before a final clean completion line, so this report does **not** claim a fresh build pass |

## What must happen next — in strict order

1. Repair/re-authenticate any OmniRoute connection that fails a minimal real completion probe, without recording credentials in repository files or logs.
2. Capture a complete 600-second, exact Frontend-node response using the selected Gemini candidate route; validate it as an `App.tsx` artifact rather than trusting HTTP status.
3. Run the whole normal-combo pipeline with `use_mock=false`. Every stage must persist its real output and pass its own validator.
4. Start the actual generated app on the host; verify real API calls, persistence behavior, validation/error flows, and no mock-only UI.
5. Run generated backend tests, frontend production build, API smoke tests, and browser E2E against the generated preview.
6. Only after steps 1–5 pass, record an E2E success and update release readiness. If any stage fails, retain the artifact/event evidence, repair the specific stage or route, and repeat from the affected gate.

## Remaining independent production gaps

These are outside the OmniRoute semantic-health blocker and remain intentionally visible:

- Purchases return HTTP `503` until a real payment provider is integrated.
- The legacy `D:\god_ai\emergentsh` worktree remains intentionally untouched; its old staged-deletion/untracked-replacement recovery is not part of the authoritative standalone repository.
- Mobile targets have source/build-readiness contracts, but store signing, provisioning, and a macOS/Xcode or Android-SDK build are deployment-environment acceptance evidence, not proof produced by this Windows host-only run.

## Release statement

**Do not describe NeonBuild as fully production-ready or claim a real generated-app browser E2E pass at this time.** The local harness and regression coverage are improved, and the correct preflight is now explicit; however, the required healthy live OmniRoute normal-combo generation run remains the release gate.

This revision supersedes earlier contradictory provider counts, port assertions, and any implication that provider reachability alone proves live generation health. Git history preserves the prior report text for audit.
