# Closed SaaS, storage, and execution contract

EmergentSH has no public signup. `POST /api/auth/register` deliberately returns
403. At startup, the account named by `OWNER_EMAIL` and `OWNER_INITIAL_PASSWORD`
is bootstrapped or reconciled as the sole administrative account. The owner uses
`POST /api/auth/admin/users` to create paid customer credentials and can update,
disable, reset, and audit them. Customers can update only their own profile and
password. Password changes and disabling an account increment `auth_version`,
invalidating every older JWT.

The owner can obtain complete generated-app history through
`GET /api/pipeline/admin/history`; individual customer jobs, exports, previews and
events remain owner-scoped. Film history remains the OiiOii service's responsibility
because EmergentSH does not generate films; its corresponding owner history is
served from OiiOii's admin APIs. This prevents a duplicate, misleading film record
from being created by the app-generation service.

## 10 GiB combined storage envelope

The service uses a safe static allocation rather than two independent 10 GiB caps:

| Consumer | hard retained-artifact cap |
| --- | ---: |
| OiiOii film artifacts | 6.0 GiB |
| EmergentSH generated-app archives | 1.5 GiB |
| reserved system/headroom | 2.5 GiB |

The total is 10 GiB. `EMERGENT_ARTIFACT_QUOTA_BYTES=1610612736` is enforced before
queue admission (25 MiB reservation per pending/running job) and before final
archive persistence. Completed applications are ZIP-compressed and stored as a
content-addressed private object under `EMERGENT_ARTIFACT_OBJECT_STORE_PATH`, while
the database records the owner, audit metadata, SHA-256, quota usage and object key.
Their work directories are removed after
the archive is committed. Previews and exports read from the authenticated archive;
there is no public static preview mount.

## Concurrent requests

`PipelineJob` is a durable database queue. Every API replica claims work with an
atomic expiring lease; a lease permits only one worker to execute a job. The worker
loop starts at most `PIPELINE_WORKER_CONCURRENCY` jobs per replica (default 2), so
HTTP requests only enqueue jobs and cannot hold a provider/render connection open.
This is safe for concurrent requests and restart recovery. Capacity is bounded, not
unlimited: deploy more worker replicas only after sizing the provider/session quota
and database connection pool.

For a constrained single laptop, set `EMERGENT_SINGLE_NODE_MODE=true`. It
overrides worker concurrency to one durable job at a time without changing the
closed-SaaS model, compressed archive storage, or consumer-provider contract.

## Consumer endpoint contract

The default consumer endpoint is `http://127.0.0.1:8190/v1` (or
`http://host.docker.internal:8190/v1` inside Docker), with
`chat/session-pool/auto` as the chat route. The client preserves gateway response
metadata rather than fabricating provider/session claims. It does not call a live
provider in any provider-free verification path.
