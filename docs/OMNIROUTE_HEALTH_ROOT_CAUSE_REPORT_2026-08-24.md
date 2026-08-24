# NeonBuild and OmniRoute health, root-cause, and remediation report

**Report date:** 2026-08-24  
**Scope:** NeonBuild live generation path, OmniRoute runtime, provider credentials, fallback routes, and local development health.  
**Docker:** deliberately excluded.

## Executive conclusion

NeonBuild's implementation is healthy at the application level, but live AI generation is currently blocked by OmniRoute.

The failure is not simply that every upstream provider independently expired. The active OmniRoute runtime reports that its credential cryptography is unavailable:

```text
cryptography.status = missing_or_invalid
cryptography.provider = aes-256-gcm
```

That prevents reliable decryption and use of the stored provider credentials. The dashboard can still display stored provider records, model catalogues, and old status badges, but real completion requests fail.

There is also a multi-process/split-brain configuration risk: an old OmniRoute listener occupies port 20128 while the clean dashboard/runtime is on port 20130. The active port-20130 process itself advertises `OMNIROUTE_BASE_URL=http://localhost:20128/v1`.

**Current production conclusion:**

| Area | Status |
|---|---|
| NeonBuild backend code and tests | Healthy |
| NeonBuild frontend production build | Healthy |
| NeonBuild UI server | Healthy |
| NeonBuild live inference readiness | Blocked by OmniRoute |
| OmniRoute process/control plane | Running |
| OmniRoute credential decryption/data plane | Unhealthy |
| Confirmed healthy text-generation providers now | 0 |
| Historically proven provider today | NVIDIA NIM, currently disabled |

## Evidence collected

### NeonBuild health

The running backend returns HTTP 200 from `/health`:

```json
{
  "status": "healthy",
  "inference_provider": "omniroute",
  "inference_configured": true
}
```

The running process uses:

```text
INFERENCE_PROVIDER=omniroute
INFERENCE_STRICT_MODE=true
OMNIROUTE_BASE_URL=http://127.0.0.1:20130/v1
OMNIROUTE_TIMEOUT_SECONDS=600
```

Validation completed on 2026-08-24:

```text
python -m pytest backend/tests -q  -> 50 passed
python -m pytest tests -q          -> 139 passed, 1 skipped
npm run build                       -> completed successfully
```

The Next.js build produced static routes for `/`, `/workspace`, and `/_not-found`. The frontend is serving on port 3006.

### Exact live NeonBuild-to-OmniRoute probe

Using the running backend process environment in memory, without exposing the gateway key, the following request was made:

```text
POST http://127.0.0.1:20130/v1/chat/completions
model: auto/best-coding
max_tokens: 8
```

Result:

```text
HTTP 401
The API Key appears to be invalid or may have expired.
```

The gateway key is present in the NeonBuild process. It also matches the active on-disk OmniRoute API-key record named `neon`, which has no recorded revocation or expiry. The live OmniRoute runtime nevertheless rejects it. This proves that the active runtime and the expected on-disk credential state are not operating in the same effective context.

### OmniRoute control-plane health

The active clean runtime at port 20130 responds to:

```text
/api/monitoring/health -> HTTP 200
version                -> 3.7.1
configured providers   -> 98
active providers       -> 82
monitored providers    -> 22
```

The same response reports:

```text
cryptography.status = missing_or_invalid
```

It also reports failed local providers with `fetch failed`, HTTP 404, or 5xx-style errors.

## Root-cause analysis

### 1. Storage encryption is not valid in the active runtime

The active port-20130 Node process does not have `STORAGE_ENCRYPTION_KEY` in its environment. The local OmniRoute `.env` file contains two `STORAGE_ENCRYPTION_KEY` entries. The process-level omission, duplicate file entries, and monitoring result `missing_or_invalid` establish that the runtime is not loading a valid, unambiguous key for the encrypted credential store.

Consequences:

- provider records may be visible but their secrets cannot be used reliably;
- OAuth refresh cannot complete reliably because refresh tokens are encrypted;
- API-key providers return authentication errors;
- dashboard badges are stale metadata rather than proof of completion capability;
- a gateway API key may exist in SQLite but be rejected by the running gateway.

### 2. Keep-alive/token refresh is not a universal credential repair mechanism

Historical OmniRoute logs show that the health service did run. It previously refreshed Google, Kimi Coding, Kiro AWS, Cline, and other OAuth tokens. The logs also explicitly show:

```text
No valid refresh token available for provider: github
No valid refresh token available for provider: kilocode
```

The service can refresh an OAuth token only if a decryptable, valid refresh token exists and the provider still accepts it. It cannot generate a new API key, restore a revoked key, recover a provider without a refresh token, clear a quota exhaustion, or fix the gateway's own API-key/encryption context.

### 3. Multiple OmniRoute instances create an operational split brain

Observed listeners:

```text
20128 -> older Node process, HTTP requests time out
20130 -> clean OmniRoute runtime/dashboard, responsive
20131 -> older Node process
20132 -> older Node process
```

NeonBuild itself is explicitly configured for port 20130, so it is not directly falling back to 20128. However, the port-20130 runtime advertises `OMNIROUTE_BASE_URL=http://localhost:20128/v1`. The old 20128 process is unresponsive. This makes the control-plane/data-plane topology ambiguous and must be removed before a reliable recovery can be claimed.

### 4. NeonBuild has a readiness-observability gap

NeonBuild's `/health` endpoint currently treats the existence of `OMNIROUTE_API_KEY` as evidence that inference is configured. It therefore reports healthy even though an actual completion returns HTTP 401. This does not create the provider failures, but it hides the failure from users and operators.

## Provider audit

The following results are based on actual completion attempts where the provider exposed a testable model. A green dashboard badge is not accepted as a health result.

| Provider | Direct result | Current verdict |
|---|---|---|
| NVIDIA NIM | 49 successful calls earlier today; latest failure 403; connection now disabled | Historically strongest, but unavailable now |
| GitHub Copilot | Unsupported stale aliases; `gpt-4.1` returned 402 monthly quota exhausted; refresh state also problematic | Unavailable |
| OpenAI Codex | `gpt-5.6-sol` returned 401 | OAuth reauthentication required |
| Antigravity | Direct fallback requests returned 401 | OAuth reauthentication required |
| Kimi Coding | `kimi-coding-default` returned 401 | Unavailable |
| Kiro | `claude-opus-4.7` returned 403 invalid bearer token | Unavailable |
| OpenRouter | Direct calls returned 401 missing authentication header | Credential/routing attachment broken |
| Fireworks | `kimi-k2p6` returned 401 invalid API key | Unavailable |
| Cohere | Tested models returned 401 invalid API key | Unavailable |
| Gemini AI Studio | `gemini-2.5-flash` returned 400 invalid API key | Unavailable |
| Alibaba/DashScope | `qwen-max` returned 401 | Unavailable |
| nScale | `QwQ-32B` returned 401 invalid/expired token | Unavailable |
| PublicAI | Tested model returned 401 | Unavailable |
| Morph | Tested model returned 401 | Unavailable |
| Maritalk | `sabia-3` returned 401 | Unavailable |
| Bytez | Tested model returned 401 | Unavailable |
| Groq | `llama-3.3-70b-versatile` returned 401 | Unavailable |
| Mistral | `codestral-2508` returned 401 | Unavailable |
| Local engines | LM Studio, vLLM, compatible engines, Triton, and others report fetch/404/5xx failures | Unavailable |
| ComfyUI | Connected but image-oriented | Not a text-generation fallback |

Providers with a connection record but no successful direct completion must be treated as **unverified**, not healthy. This includes several gateway and web-provider records such as AgentRouter, Amazon Q, Reka, Vertex AI, Cloudflare Workers AI, AI/ML API, Novita, Nous Research, and Perplexity Web.

## Recommended remediation plan

### Phase A: preserve and normalize the runtime

1. Preserve the existing backup:

   `C:\Users\Admin\.omniroute\reauth-backups\20260824-091743`

2. Identify the old port-20128 process by PID and command line.
3. Stop only the verified stale OmniRoute process after confirming it is not the canonical production process.
4. Choose one canonical OmniRoute instance and port. Use port 20130 or a new documented port, but not both 20128 and 20130 simultaneously.
5. Start the canonical runtime with an explicit environment file and deterministic working directory.

### Phase B: restore encrypted credential access

1. Ensure there is **one** `STORAGE_ENCRYPTION_KEY` line in `C:\Users\Admin\.omniroute\.env`.
2. Use the original key that encrypted the current database. Do not rotate it until existing credentials are intentionally migrated or re-entered.
3. Ensure the canonical process inherits that key.
4. Verify the monitoring acceptance condition:

   ```text
   /api/monitoring/health
   cryptography.status = healthy
   ```

5. Do not use credential-reset commands that erase encrypted columns unless intentionally discarding the provider store.

### Phase C: reissue and verify the NeonBuild gateway key

1. In the same canonical OmniRoute runtime, create or reissue a gateway endpoint key for NeonBuild.
2. Update only the NeonBuild backend process environment with that key.
3. Restart the backend.
4. Run a tiny authenticated completion against `auto/best-coding`.
5. Require HTTP 200 before changing the production fallback chains.

### Phase D: repair providers in priority order

Recommended restoration order:

1. NVIDIA NIM
2. OpenAI Codex
3. Antigravity
4. Kimi Coding
5. Kiro
6. GitHub Copilot
7. OpenRouter
8. Fireworks
9. Cohere
10. Gemini
11. Alibaba
12. Groq
13. Mistral

OAuth providers without a valid refresh token need interactive sign-in. API-key providers need their actual current keys replaced; keep-alive cannot generate new API keys.

### Phase E: rebuild provider routes only from proof

For every candidate model, require:

1. model catalogue check;
2. direct non-stream completion;
3. streamed completion;
4. timeout/latency check;
5. deliberate primary failure and successful fallback.

Only successful models may be inserted into `auto/best-coding` and `auto/best-reasoning`. Remove stale first-priority models from those combos.

### Phase F: make NeonBuild readiness truthful

Split status into:

- `/health`: process, database, and service liveness;
- `/readiness`: authenticated OmniRoute completion, valid gateway credential, healthy cryptography, at least one healthy primary route, and one fallback route.

NeonBuild must not report inference-ready based only on `bool(OMNIROUTE_API_KEY)`.

## Final acceptance criteria

The recovery is complete only when all of the following pass:

- one canonical OmniRoute listener is active;
- `cryptography.status` is healthy;
- NeonBuild's gateway key returns HTTP 200 from the active OmniRoute instance;
- at least two independent text-generation providers pass a direct completion;
- `auto/best-coding` and `auto/best-reasoning` each pass real completion tests;
- a forced primary-provider failure falls back successfully;
- a fresh NeonBuild full-stack job completes with live providers;
- generated preview, backend/API smoke tests, and browser E2E pass;
- NeonBuild readiness reports failure if OmniRoute stops accepting completions.

## Final status

```text
NeonBuild code/tests/frontend: healthy
NeonBuild live AI generation: blocked by OmniRoute
OmniRoute control plane: reachable
OmniRoute credential decryption: unhealthy
OmniRoute gateway key: rejected by active runtime
Confirmed healthy live general-purpose providers: 0
```

The primary remediation is not a broad provider-by-provider reauth attempt. First restore a single canonical OmniRoute runtime with the correct storage encryption key, then validate the gateway key, then repair only the providers that still fail direct completions.
