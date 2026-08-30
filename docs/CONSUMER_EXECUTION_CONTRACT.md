# EmergentSH Consumer Execution Contract

## Production invariant

Every customer app-build job follows one authenticated durable path:

```text
authenticated POST /api/pipeline/run
  -> durable PipelineJob
  -> AgentPipeline worker
  -> AsyncOmniRouteClient
  -> http://127.0.0.1:8190/v1/chat/completions
```

`INFERENCE_PROVIDER=omniroute` is the required production setting. The
compatibility value `auto` resolves to OmniRoute as well; selecting `nim` now
fails closed. Upstream provider keys, provider choice, session routing, and
capacity belong behind the gateway, not in EmergentSH.

When the FastAPI process runs inside Windows Docker, its
`host.docker.internal:8190/v1` compose value is the container-network alias
for the host's canonical `127.0.0.1:8190/v1` gateway. It is not a second
provider or alternate execution lineage.

## Mock and desktop policy

`use_mock=true` is rejected whenever `APP_ENV` is `production` or `prod`.
Gateway failure is an honest job failure, never a fallback to direct NVIDIA NIM
or a fake generated application.

The legacy PySide desktop launcher is intentionally disabled by default and is
always disabled in production. It can only be launched with the explicit local
development flag `EMERGENT_ENABLE_LEGACY_DESKTOP=true`. Until it submits
authenticated durable SaaS jobs through the shared client, it is not a customer
execution surface and cannot be used for production certification.
