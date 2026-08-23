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

## Running it

```bash
SERVICE_SHARED_SECRET=$(openssl rand -hex 32) python3 service/app.py
python3 service/app.py --insecure          # local development only
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
