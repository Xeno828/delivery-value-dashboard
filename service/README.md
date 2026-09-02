# The calculator

A stateless HTTP wrapper around `agent/tools/`. Forge runs Node and cannot
execute the Python; rather than write a second Monte Carlo in JavaScript, the
Forge app posts the fields a calculation needs to this service and gets the
figures back. Reasoning: [ADR 0008](../docs/adr/0008-forge-calls-a-hosted-calculator.md).

**It does no arithmetic.** Every number comes from `metrics.py`, `forecast.py`
or `intake.py` — the same modules the CLI and the live-mode server call.

## What it holds

Nothing. No credential, no storage, no Jira access. Forge owns the OAuth grant
and does the pulling; this receives dates and status categories.

Free-text fields are **refused**, not ignored:

```
400  the payload carried summary. This service calculates from dates and status
     categories; issue text does not belong here and was not stored. Project the
     issues before sending them.
```

Accepting them quietly would make this a place customer text lives, which is
the one thing the projection exists to prevent. Forge re-attaches summaries by
key after the call, so nothing is missing from the rendered tile.

## Authentication, and what replaces it

Two modes, chosen with `SERVICE_AUTH`:

| | |
|---|---|
| `shared-secret` | One string, presented by every installation. Cannot tell one customer from another, which is what makes it the mode for local runs and the suite |
| `forge-token` | The Atlassian-issued invocation token. Tenant-aware, and this app holds no secret of its own |

A verifier returns *who the caller is* rather than a boolean, so the access log
can name the tenant a request was for — which is the entire point of the token
mode. The shared secret logs no tenant rather than a placeholder that reads
like one, because a single string every installation presents cannot identify
anybody.

### `forge-token` needs four values, and this repository does not guess them

| | |
|---|---|
| `FORGE_JWKS_URL` | where Atlassian publishes the signing keys |
| `FORGE_ISSUER` | the exact `iss` to require |
| `FORGE_AUDIENCE` | what goes in `aud` — the app id, the app ari, or something else |
| `FORGE_TENANT_CLAIM` | which claim carries the installation or tenant identity |

They are environment variables rather than constants precisely so that no value
nobody has confirmed lives in the source. **All four are now confirmed and
dated** in [hosting the calculator](../docs/hosting-the-calculator.md)
Appendix A — `aud` is the app id ARI, not the bare UUID, and the tenant claim
is `app.installationId`, which is **nested**. The verifier walks a dotted path
for exactly that reason: a flat lookup found no tenant in a real token and so
refused every one of them, while every token this suite mints carries a flat
claim and was accepted. Re-confirm against current Atlassian documentation and
record the date beside any deployment that sets them. The service refuses to start in this mode with any of them missing:
guessing one produces a verifier that rejects every real token, or — the case
that matters — accepts one minted for a different app.

The mechanics are proved without Atlassian. `tests/test_service.py` generates a
keypair, serves a JWKS from a local HTTP server and mints its own tokens, then
requires every one of these to be refused: expired, `nbf` in the future, wrong
`aud`, wrong `iss`, signed with a key outside the JWKS, `alg: none`, HMAC-signed
using the RSA public key as the secret, no `kid`, unknown `kid`, truncated, and
a valid signature carrying no tenant. What that cannot prove is the four values
above.

## Dependencies

Stdlib, except one: `PyJWT[crypto]`, in `service/requirements.txt`, used only by
`forge-token`. It is imported inside the verifier rather than at module scope,
so shared-secret mode runs and the suite passes on a host that never installed
it — the startup guard is what makes that safe, because the token mode cannot
serve unless the import works.

Deliberately not in `scripts/requirements.txt`: the security suite asserts the
fetcher's dependency list stays at one, and that is the list worth keeping
boring, since the fetcher is what holds a customer's credentials.

## Running it

```bash
SERVICE_SHARED_SECRET=$(openssl rand -hex 32) python3 service/app.py
python3 service/app.py --insecure          # local development only

# tenant-aware, once the four values are confirmed
pip install -r service/requirements.txt
SERVICE_AUTH=forge-token \
  FORGE_JWKS_URL=... FORGE_ISSUER=... FORGE_AUDIENCE=... FORGE_TENANT_CLAIM=... \
  python3 service/app.py
```

It refuses to start without a secret. An open calculator is free compute for
whoever finds it, and holding no data is not the same as needing no
authentication.

In production, `wsgi_app` is a plain WSGI callable running the identical code:

```bash
gunicorn -w 4 -b 0.0.0.0:8080 'service.app:wsgi_app'
```

## Routes

| | |
|---|---|
| `GET /healthz` | liveness. No auth, no data |
| `GET /v1/meta` | version, limits, which issue fields are accepted and refused |
| `POST /v1/facts` | `metrics.facts` |
| `POST /v1/forecast` | `forecast.build` over a slice the caller chose |
| `POST /v1/forecast-context` | `selection.forecast_for` — this service chooses the slice |
| `POST /v1/slice` | `selection.slice_for` — which contexts a forecast would sample. Metadata only; send no issues |
| `POST /v1/ask` | `intake.forecast_ask` |
| `POST /v1/sequence` | `intake.sequence` |

```jsonc
// POST /v1/forecast
{ "dataset": { "issues": [ … ], "meta": { … }, "orgConfig": { … } },
  "asOf": "2026-08-10", "remaining": 4, "target": "2026-08-14" }

// 200
{ "ok": true,
  "calendar": "5-day working week (mon, tue, wed, thu, fri), 0 holidays, …",
  "result": { … } }
```

`calendar` is on every response deliberately. Two forecasts of one board under
different working weeks are different forecasts, and the difference is
otherwise invisible to whoever reads the number.

## Sizing

Measured on this repository's own fixtures:

| | request | time | response |
|---|---|---|---|
| one team's forecast, 242-issue org | 16.2 KB | 0.25s | 32 KB |
| one team's forecast, 5,538-issue org | 16.3 KB | 0.74s | 32 KB |
| `intake.sequence`, 4 asks | | 3.07s | 5 KB |

A call is bounded by one team's history, not the organisation's size, which is
why the payload does not grow with the customer. `intake.sequence` is the only
call within an order of magnitude of a typical request timeout — check it
against the platform's limit before enabling that route on Forge.

## Two forecast routes, and why the second exists

`/v1/forecast` takes a flat list of issues and simulates them. Deciding *which*
issues — the slice — is left to the caller, which is right when the caller is
`scripts/serve_live.py`: it is Python, and it uses the same rules the tools do.

It is wrong when the caller is a Forge resolver running Node. The slice is
`team_slice` plus de-duplication by key plus taking outstanding work from the
selected context rather than the team plus suppressing a window's end date —
and every one of those rules exists because it was got wrong once, each time
returning a **credible date rather than an error**. It is the last logic in this
repository that should exist twice.

So it moved to `agent/tools/selection.py`, where `serve_live.py` and this
service both reach it, and `/v1/forecast-context` takes the contexts, the
issues and a context id and lets the tool do the choosing. This service still
computes nothing — `tests/test_service.py` holds the route's answer against
`selection.forecast_for` called directly, to the byte, exactly as it does for
the flat route against `forecast.build`.

**What that means for what this service sees.** A context carries the names a
board, sprint and team were given. Those are not issue text and are not refused
— the projection strips summaries, assignees, labels and epic names from
*issues*, which is the thing the boundary exists for — but they are customer
strings and they are worth naming rather than discovering. They have travelled
this route since `/v1/facts` shipped, since `meta.sprintName` is echoed back as
`generated_for`. Nothing here computes with them; `team_slice` compares team
labels for equality and the rest is display text passed through.

## Limits, and why they are loud

`maxIssues` 50,000, `maxAsks` 12, `maxItems` 5,000, `maxBodyBytes` 4 MB. Exceeding one is a `413`
with a sentence, never a truncated calculation: a forecast over half a team's
history looks exactly like a forecast over all of it.

The ask cap is the tool's, not this service's: it is `intake.MAX_ASKS`, and
the sentence is `intake.too_many_asks()`, so the file transport and the Forge
function refuse at the same number in the same words. Twelve because sequencing
is cubic in the ask count — 21 s natively, three and a half minutes on Forge —
and the fifty this service used to allow was a computation nobody had run.
ADR 0031.

## Two files, one of which travels

`service/routes.py` is every answer this service gives: the projection, the
caps, the refusals and one function per route, ending in `answer(path, body)`.
`service/app.py` is the socket in front of it — HTTP, the two auth verifiers,
the body limit — and adds no key to any envelope. The split exists because the
Forge function runs `routes.py` unchanged under WebAssembly and calls the same
`answer()`; `tests/test_wasm.py` holds the two byte for byte. Anything added
to `routes.py` has to import under Pyodide, which means no sockets, no
environment and no third-party module.

## Deploying

`service/Dockerfile` copies `agent/tools/`, `service/routes.py` and
`service/app.py` and nothing else — no `.env`, no `data/`, no `dist/`.
Non-root, no writes at runtime, so a read-only root filesystem works.

Stateless and sub-second suits scale-to-zero. Where it runs, what it costs and
in what order: [hosting the calculator](../docs/hosting-the-calculator.md).

```bash
bash service/provision-gcp.sh    # one-time: project, registries, federation
git push                         # .github/workflows/deploy.yml does the rest
```

`provision-gcp.sh` is the half only a person can do — it needs a billing
account and a browser. Everything after it is `deploy.yml`, which builds, runs
`service/smoke.sh`, runs `service/scan.sh`, and deploys to both regions only if
all of that passed.
The recommendation is Cloud Run in two regions on `SERVICE_AUTH=forge-token`,
which needs no secret store at all — the four `FORGE_*` values are
configuration, not credentials. Fargate is retired as a candidate there: it has
no scale-to-zero, so it bills 730 hours a month for a service busy for minutes.

For a local run or a shared-secret deployment, inject `SERVICE_SHARED_SECRET`
from the platform's secret store; the same value goes in the Forge app's remote
configuration.

**Data residency is yours, but the routing is not.** Pin a deployment per
region — and then let Forge choose between them. A `remotes` entry whose
`baseUrl` is an object of region-specific URLs is resolved per installation
from the customer's own Atlassian residency setting, so this app never decides
which region a tenant belongs in. That is the half of roadmap item 6 that moves
earlier if you take the Forge route, and it is smaller than it looks. It has
since been taken — [`../docs/roadmap.md`](../docs/roadmap.md) has the items and
what each of them is now.

## Logging

Method, path, status, issue *count*, duration. Never content. An access log
holding issue keys is a copy of the customer's backlog in a log aggregator.
Tracebacks go to the operator and never into a response, because they carry
field values.
