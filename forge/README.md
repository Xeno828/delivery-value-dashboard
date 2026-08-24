# The Forge app

**Registered, deployed to development, and reading a real tenant's data.** The
other Jira connection is OAuth 2.0 (3LO) — `scripts/jira_auth.py`, with
`--auth oauth` on the fetcher — and it is not going away: it needs no app
registration and is the right thing for pulling your own board. Nothing here is
needed to use the product.

## What this is for

Roadmap item 1 says *"a Forge or Connect app"*, and the roadmap calls that the
one genuinely open decision in phase 1. This directory exists so choosing Forge
is a decision rather than a rewrite.

## The four files

| | |
|---|---|
| `manifest.yml` | Modules, resources, scopes and the egress declaration |
| `src/index.js` | The resolvers. Talks to Jira, calls the calculator, computes nothing |
| `src/jira.js` | The shaping, as pure functions of a Jira response. No SDK, no network — which is what lets `tests/test_service.py` run it and compare its output with the live server's |
| `bridge/bridge.js` | The transport adapter. Puts an `invoke()` on `window.__DVD_BRIDGE__` so `src/app.js` can reach a resolver without importing anything |

The last one is the seam, and [ADR 0009](../docs/adr/0009-one-contract-two-transports.md)
is why it is shaped that way. `src/app.js` is the shipped product: dependency-free,
no network call from `file://`, and it must not learn what Forge is. So the page
looks for a transport on the window and this puts one there — bundled as a
classic script (a module is deferred, and an adapter that arrives after the page
has decided it is offline is an adapter that never ran) and linked only into the
split build.

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

**Real, and observed rather than assumed:** the app is registered, `forge lint`
is clean, it deploys to development and installs on a dev site, and the
dashboard renders inside the iframe showing that site's own boards, sprints and
issues. The scopes have been proven against real Jira rather than read off a
documentation page.

**Real, and tested without Forge:** `src/jira.js` — every shape the bridge puts
on the wire, compared field for field against a running `serve_live.py` in
`tests/test_service.py`. And `src/index.js`'s projection, free-text assertion,
calculator call and re-attachment by key, which `tests/test_service.py` asserts
loses nothing a calculation reads.

**Not hosted:** the calculator. `remotes[0].baseUrl` still says `.invalid` and
no environment has been provisioned, so the forecast and the ask-sequencing
answer with a refusal naming that reason. The test suite ties the two together,
so a real `baseUrl` with the refusal still in place fails rather than shipping a
tile that is dark for no visible reason.

**Known, and it returns a plausible wrong number rather than failing:** story
points are read from `customfield_10016`. That id differs per Jira site; the
Python fetcher discovers it by display name, this hardcodes the common one. On a
site that uses a different id every issue reads as zero points and the burndown
flattens in points mode with nothing saying why. Items — the default unit
everywhere, and the only unit the forecaster reads — are unaffected. Fixing it
needs a field-read scope, so it is a decision rather than a patch, and the
connection check shows it: `storyPoints` absent from the projected payload means
the id is wrong for that site.

**Absent on purpose from what is committed:** the app `id`. `forge register`
writes one and it ties the manifest to a single Atlassian account. Having one
locally is correct; strip it before `git add` and restore it after.

## If you take this route

Step-by-step runbooks for all of it, including what `forge lint` will not tell
you: [docs/forge-deployment.md](../docs/forge-deployment.md).

1. `npm install -g @forge/cli && forge login && forge register`
2. Deploy `service/` somewhere and point `remotes[0].baseUrl` at it, then turn
   the two refusals in `src/index.js` back into `compute()` calls — the
   projection and re-attachment they need are already written and tested.
3. Replace the calculator's shared-secret check with verification of the Forge
   invocation token. `service/app.py` uses a bearer secret today, which is
   honest and works, but the tenant-aware thing is the Atlassian-issued JWT.
4. `make forge-static` builds the dashboard into `static/dashboard/build`. It
   is **not** a copy of `dist/`: this iframe's CSP blocks inline style and
   script, so `build.py --split` links them instead; the seed is `seed.json`
   rather than the demo dataset, because the tenant's own sprints are the point
   and a demo company's would sit in the picker beside them; and `--bridge`
   links the adapter ahead of `app.js`.
5. Keep the scopes in `manifest.yml` identical to `SCOPES` in
   `scripts/jira_auth.py`. Two routes seeing different issues is a bug that
   presents as a data problem.
6. Keep `CALC_FIELDS` in `src/index.js` identical to `CALC_FIELDS` in
   `service/app.py`. They are compared by eye today; if this route is taken,
   pin them with a test.

## Still not here

The Marketplace listing, its review, and billing. Atlassian Console work with no
code in this repository.
