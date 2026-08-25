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
nobody has confirmed lives in the source. **Confirm each against current
Atlassian documentation and record the date beside the deployment that sets
them.** The service refuses to start in this mode with any of them missing:
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
| `POST /v1/forecast` | `forecast.build` |
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

## Limits, and why they are loud

`maxIssues` 50,000, `maxAsks` 50, `maxBodyBytes` 4 MB. Exceeding one is a `413`
with a sentence, never a truncated calculation: a forecast over half a team's
history looks exactly like a forecast over all of it.

## Deploying

`service/Dockerfile` copies `agent/tools/` and `service/app.py` and nothing
else — no `.env`, no `data/`, no `dist/`. Non-root, no writes at runtime, so a
read-only root filesystem works.

Stateless and sub-second suits scale-to-zero (Cloud Run, Fargate, Fly). Inject
`SERVICE_SHARED_SECRET` from the platform's secret store; the same value goes
in the Forge app's remote configuration.

**Data residency is yours now.** Pin a deployment per region and route each
tenant to its own — this is the half of roadmap item 6 that moves earlier if
you take the Forge route.

## Logging

Method, path, status, issue *count*, duration. Never content. An access log
holding issue keys is a copy of the customer's backlog in a log aggregator.
Tracebacks go to the operator and never into a response, because they carry
field values.
