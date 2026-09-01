# 0031 — The forecast runs inside the Forge function, and the calculator is retired

[ADR 0008](0008-forge-calls-a-hosted-calculator.md) chose a hosted calculator because Forge could not run `agent/tools/` and the alternative was a second implementation of the forecast. Its amendment of 2026-09-01 records that a third shape exists and measures it: the same Python, unchanged, under Pyodide — CPython compiled to WebAssembly — inside the Forge function, every figure byte-identical to native, nothing leaving Atlassian. That amendment left the choice to the person accountable for it.

**Decided 2026-09-01: the app takes that shape.** The forecast, the facts and the sequencing run inside the Forge function; the hosted calculator is retired; the `remotes` block leaves the manifest; the app becomes eligible for the *Runs on Atlassian* badge and is `PINNED` for data residency by construction. The settled design was reached in three rounds of questions, each answered against a measurement or a documented limit rather than a preference, and the rounds are what this record preserves. The evidence is `docs/research/2026-09-01-runs-on-atlassian-badge.md` §6 and `docs/research/2026-09-01-forge-async-events.md`.

The property this trades on is the one every record here rests on: **one implementation of every figure.** The Python moves; nothing is rewritten. What it costs is a forecast about ten times slower on Forge's CPU, a seven-second cold load per container, and one route that no longer fits a synchronous call.

## Sequencing is asynchronous, and only sequencing

The bridge adapter gives every call fifteen seconds. Sequencing four asks takes 13.6 s warm on Forge and about 21 s cold, and the cap is fifty asks at roughly 3.4 s each. No synchronous resolver answers that, and today the page's *"No sequencing for this selection"* is what a cold start already produces on the dev site.

So the `sequence` resolver validates, projects, and pushes one async event carrying the projection; a consumer function runs the tools with a 900-second class budget; the result waits in app storage; and **the adapter polls and hands the page one final `{ok, status, body}`**. The page is untouched and so is [ADR 0009](0009-one-contract-two-transports.md)'s contract, because the adapter is the one script permitted to know what Forge is, and the body shapes it returns are the ones `serve_live.py` already produces synchronously. The file transport does not change at all.

Facts and the forecast stay synchronous. At 480 issues they answer in about 1.3 s warm and 9 s cold, inside the adapter's clock. Forecast time against a large board has not been measured on Forge; it will be, on the probe below, before the forecast route moves, and if it does not fit it takes the same async shape.

## The consumer's contract

- **Budget: 300 seconds and 1,024 MB**, declared on the consumer function. Fifty asks is about 177 s cold on the probe's container, and Forge bills a crashed run at the lower of the declared timeout and measured time, so the budget sits near the need rather than at the ceiling. The adapter's own ceiling is five minutes, matching it.
- **Two guards against a run that cannot finish.** Before simulating, the consumer times the first ask's forecast and refuses, in the tools' own words, if the ask count at that rate would exceed the budget. On entry it reads Forge's retry context, and on any retry it writes a refusal to the job row and returns without computing — because Forge retries a timed-out event automatically for a day, and a consumer without that guard is re-invoked every fifteen minutes for something nobody sees.
- **The event carries the projection.** A consumer cannot read Jira as the viewer, so the resolver projects as it does today and passes the result on. A call is about 16 KB and does not grow with the customer; the documented limit is 100 KB per event once the function's timeout exceeds 55 s, and the resolver refuses with a sentence above it rather than truncating. A storage detour for the payload earns its place only if that refusal ever fires.
- **The job row.** Key-value storage under an unguessable job key, a status the consumer moves through started, done and refused, a timestamp, and the asking account. The poll resolver refuses any other account, so [ADR 0018](0018-permission-mirroring-holds-by-accident-and-where-it-does-not.md)'s mirroring holds by a comparison rather than by entropy. The row is deleted on collection and carries a one-hour TTL; the poll checks the row's own timestamp, because an expired row may still be readable for 48 hours. Forge's job-stats API is not used: it carries counts, no payload and no documented lifetime, and the row must exist to hold the result regardless.

## How the runtime travels

Forge's bundler ships only compiled JavaScript and rewrites Pyodide's own dynamic import into something that fails. The runtime's five files and the Python sources therefore travel as base64 inside a generated module, unpacked to `/tmp` on first invocation and loaded from there; a warm container keeps the loaded runtime. That module is **generated at deploy, never committed**: `make forge-deploy` produces it from the pinned `pyodide` npm package (314.0.6 at the time of writing) and from the Python read straight out of `agent/tools/` and `service/`. A committed copy of the Python is a second copy, and a second copy drifts.

The pure half of `service/app.py` — the projection, the caps, the refusals — moves into its own module that both the hosted service and the function import. The HTTP server and the two auth verifiers stay behind in `app.py` and go when the calculator does.

## How it is proven, and in what order

A sixth suite runs the tools under Pyodide in local Node and asserts the answer equals native Python byte for byte over the fixtures `tests/test_service.py` already uses. CI runs it on every push. That assertion is the successor of the hosted service's parity test and the only thing standing between two runtimes and a figure that drifts between them unnoticed.

Before the real app is touched, a second throwaway app on the dev site settles what documentation cannot: whether adding a consumer module is a major version — the versioning page's list says minor, and this repository's rule is that a deploy decides — the forecast's time against a large board, whether the service's validation layer imports under Pyodide, and whether Pyodide's undocumented snapshot cuts the cold load. If the deploy says major, the consumer module is declared in the real manifest early, pointing at a function that does nothing yet, so the major version lands while the only installation is `development`.

Then routes move **one per commit**, deployed to development and clicked on the dev site before the next, with the calculator answering everything not yet moved. There is no runtime switch: git is the switch, each deploy has one change to blame, and a switch that outlives the migration is a second code path nobody tests. The `remotes` block is removed in its own final commit, which is also the deploy that classifies removing a remote for this app. Until then the badge is not earned, and [ADR 0012](0012-the-calculator-is-reached-by-invokeremote.md) and [ADR 0030](0030-the-manifest-commits-to-its-hostnames-and-realms-once.md) stay true; at that commit they are marked superseded by this one, and the calculator's three services, three registries, region loop and realm guard go with them.

## Rejected

**A hard refusal at two or three asks, keeping the resolver synchronous.** Cheapest to build, and it sells a sequencing tile that refuses the case it exists for while the file transport keeps fifty.

**Pyodide's snapshot as the answer to sequencing.** It can only shorten the cold load. The warm 3.4 s per ask is the problem, and no start-up trick changes it.

**Pyodide in the Custom UI iframe.** Needs `unsafe-eval` in the content security policy, a major version; runs at less than half speed in a hidden tab; and the weekly brief has no browser to run in.

**Polling in the page.** It would teach `src/app.js` what a job is, which is a transport detail, and the single file would carry it to every reader who never has one.

**Caching a result by board and dataset.** A figure served from storage without saying when it was computed is the quiet wrongness [ADR 0017](0017-a-forecast-is-logged-as-a-count-not-a-promise.md) exists to stop, and the seed already makes a recompute identical.

**Committing the generated runtime module.** Eighteen megabytes in git, and a second copy of the Python.

**Moving every route in one deploy.** One change to blame per deploy is worth more than one fewer deploy.

Not decided here: when this lands relative to the first external trial. The whole route is minor versions by the documentation, so it can land on either side of that date without a reinstall; the probe's deploy says whether that holds.
