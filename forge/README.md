# Forge scaffold

**Not deployed. No app registered.** The working Jira connection is OAuth 2.0
(3LO) — `scripts/jira_auth.py`, with `--auth oauth` on the fetcher. Nothing here
is needed to use the product.

## What this is for

Roadmap item 1 says *"a Forge or Connect app"*, and the roadmap calls that the
one genuinely open decision in phase 1. This directory exists so choosing Forge
later is a decision rather than a rewrite.

## The functionality is not the problem

An earlier version of this file said the choice was "host the Python anyway or
write a second Monte Carlo", and treated the first as a concession. That was too
pessimistic, and measuring it settled the question — see
[ADR 0008](../docs/adr/0008-forge-calls-a-hosted-calculator.md):

- **The tools are already pure functions.** Every `open()` and `glob` in
  `metrics.py`, `forecast.py` and `intake.py` is inside `main()`.
- **A call is 16 KB and does not grow with the customer** — 16.2 KB for a
  242-issue org, 16.3 KB for a 5,538-issue one, because a forecast needs one
  team's history rather than the organisation's.
- **No issue title has to leave Atlassian.** `forecast.build()` over a dataset
  stripped to dates and status categories produces byte-identical figures. The
  only fields that differed were `summary` and `assignee`, echoed back for
  display, and this app re-attaches those by key from the copy it already holds.

So the Forge route keeps the full product. Forge pulls the issues and renders
the panel; `service/app.py` runs the same Python everything else runs.

## What it does cost

| | |
|---|---|
| **Runs on Atlassian badge** | Forfeited. Egress disqualifies it, and there is no engineering answer — only the choice not to have two forecasts |
| **Marketplace review** | The egress declaration in `manifest.yml` will be read |
| **Data residency** | Becomes yours, pinned per region. Roadmap item 6 moves earlier rather than appearing from nowhere |
| **Operations** | You run a service. Stateless and sub-second, so scale-to-zero keeps the bill and the pager quiet |

## What is real here and what is not

**Real, and tested:** `src/index.js` — the projection, the free-text assertion,
the call to the calculator and the re-attachment by key. `tests/test_service.py`
asserts the projection loses nothing a calculation reads, using the same field
list this file uses.

**Never run:** Forge itself. No app registered, nothing deployed, and
`manifest.yml` has not been through `forge lint`. Platform manifest schemas
move — check the Forge-specific syntax against current Atlassian docs before
trusting it, particularly the `remotes` block and the invocation-token contract
the calculator's auth would key off.

**Absent on purpose:** the app `id`. `forge register` writes one and it ties the
manifest to a single Atlassian account.

## If you take this route

1. `npm install -g @forge/cli && forge login && forge register`
2. Deploy `service/` somewhere and point `remotes[0].baseUrl` at it.
3. Replace the calculator's shared-secret check with verification of the Forge
   invocation token. `service/app.py` uses a bearer secret today, which is
   honest and works, but the tenant-aware thing is the Atlassian-issued JWT.
4. Build the dashboard into `static/dashboard/build`. `dist/` is a single
   self-contained file so this is close to a copy — but a Forge iframe is not an
   emailed file, and the security suite's no-network, no-storage assertions are
   about the file, not about this.
5. Keep the scopes in `manifest.yml` identical to `SCOPES` in
   `scripts/jira_auth.py`. Two routes seeing different issues is a bug that
   presents as a data problem.
6. Keep `CALC_FIELDS` in `src/index.js` identical to `CALC_FIELDS` in
   `service/app.py`. They are compared by eye today; if this route is taken,
   pin them with a test.

## Still not here

The Marketplace listing, its review, and billing. Atlassian Console work with no
code in this repository.
