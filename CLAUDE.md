# Working in this repository

Read this before changing anything. Most of what follows is a constraint that was arrived at the hard way, and the reason is given so you can tell when it genuinely does not apply rather than guessing.

`CONTRIBUTING.md` covers the mechanics. This file covers the things that will look like arbitrary preferences until you break one.

---

## The commands

```bash
make build         # assemble src/ into dist/delivery-value-dashboard.html
make check         # fail if dist/ is stale — this is what CI runs
make test          # all five suites: e2e, agent, a11y, security, service
make test-agent    # agent tools only, no browser needed
make test-service  # the hosted calculator, no browser needed
make report        # facts pack + delivery forecast for the sample data
make intake ASK=data/asks/INTAKE-2026-014.json
```

The browser suites need Playwright (`pip install playwright && playwright install chromium`). `make test-agent` needs nothing but Python 3.

**`dist/` is committed on purpose** so the repository is usable without a build step. If you change anything in `src/`, run `make build` and commit the result in the same commit. CI fails otherwise.

## Architecture in one paragraph

`src/` is four files assembled by `build.py` into a single self-contained HTML file. `agent/tools/` is five dependency-free Python modules — `metrics.py` (facts), `forecast.py` (Monte Carlo on work that exists), `intake.py` (forecasting an ask before any of it exists), `selection.py` (which issues a forecast reads, and what it is told about them), `orgconfig.py` (the per-organisation assumptions the others read out of the dataset). `agent/SKILL.md` is the agent definition; it narrates what the tools return and computes nothing. `scripts/` fetches and generates data. `service/` is a stateless HTTP wrapper over those same tools, for a Forge build that cannot run Python — it computes nothing of its own. `tests/` is five suites. `forge/` is deployed: the app is registered, the dashboard renders inside the iframe and reads the tenant's own boards over the bridge in `forge/bridge/bridge.js`; the hosted calculator it would call for a forecast is not provisioned, so that one tile refuses and says why.

---

## Standing constraints

These are product decisions, not style. Violating one is a bug even when the tests pass.

**No hours, overtime, or timesheet field. Anywhere.** Not in the schema, the fetcher, the import pipeline, the UI, or a document. The organisation does not operate overtime, and a field for it implies a time-tracking regime that does not exist. Team load is measured as work in progress and unplanned work, both derived from issue status. If a metric seems to need effort data, it is the wrong metric.

**Never rank or compare individuals.** Throughput is a property of the system, not the person. The data cannot support the claim, and the first report that makes it is the last report anyone reads. Ownership counts are fine; league tables are not.

**Never compute a priority score.** No WSJF, no weighted shortest job first, no value-over-effort ratio, nothing of that family. They multiply an unvalidated value estimate by an unvalidated size estimate and present the product as arithmetic. The delivery consequence of an ordering is computable and must be returned; the relative worth of competing asks is a judgement that stays with the people accountable for it.

**Nothing between the tools and a reader may do arithmetic either.** The rule below applies to the agent, and equally to `service/app.py` and the Forge resolver: they validate, delegate and pass figures through. `tests/test_service.py` asserts the service's answer equals the tool called directly, byte for byte. A wrapper that computes one percentage is a second implementation, and the day it disagrees, every number in the product becomes something to check rather than read.

**The agent never does arithmetic.** Every figure in every report comes from a tool. This is enforced structurally — the tools emit numbers, the agent quotes them, the tests assert the tools agree with the dashboard. The moment the agent computes a percentage itself, nothing in the report is auditable and its entire value is gone.

**Live mode has two transports and one set of body shapes.** The page asks four questions by route name and gets `{ok, status, body}` back, over a same-origin `GET` answered by `serve_live.py` or over an `invoke()` an adapter left on the window. The *bodies* are the contract and the Forge resolvers return them unchanged; the status is transport-level. `src/app.js` must never learn which it has, must never import `@forge/bridge`, and the adapter stays a separate script linked only into the split build. `docs/adr/0009-one-contract-two-transports.md`.

**The built file makes zero network calls and uses zero browser storage.** No CDN, no fonts, no analytics, no `localStorage`, no cookies. The threat model is that this file gets emailed. The security suite asserts all of it.

**Credentials live only in the fetcher's environment.** `.env` is git-ignored. So is `.jira-oauth.json`, the OAuth grant, which holds a rotating refresh token and is created mode 0600. So is `data/dashboard-data.json`, because it contains real issue titles. Check all three survive any `.gitignore` edit. The live-mode server and the OAuth redirect listener both bind to `127.0.0.1` only, and the OAuth scopes stay read-only. The security suite asserts every one of these by name.

**Every Forge scope is read-only except two, and those two are named.** `send:notification:jira` sends the brief and `storage:app` holds the recipient config; the rule the prefix stood for — that reach is added deliberately by somebody who wrote down why — is now enforced as an allow-list in `tests/test_service.py`, where a non-read scope must be listed *and* carry a justification beside it in `forge/manifest.yml`. Neither grants write access to customer data, and neither can address anyone outside the site. That is stricter than the `startswith("read:")` it replaced, which would have waved through every read scope Atlassian ever adds. `docs/adr/0014-jira-sends-the-brief-and-the-read-only-rule-bends.md`.

**Refusals are printed verbatim, never softened.** When a tool returns a refusal, the agent quotes the sentence as written. *"Not enough data"* and *"wide interval"* are different statements and only one of them is true. The refusal sentences all end with some form of *the evidence is absent, not noisy* — that clause is the point, do not trim it.

**An empty selection is a refusal, not a zero.** Over zero issues a share has no denominator, and the guards that keep those ratios finite (`Math.max(items.length, 1)`, `? … : 0`) return good news rather than silence. The sprint health score summed four of them into *"Needs attention (66/100)"* for a page with nothing on it, which is the state the Forge build opens in. Tiles that would state a figure about the selected issues refuse instead, in the same words and with the same closing clause the tools use. Counts of an empty set that are honestly nil keep their nil; claims that depend on having looked do not. The same rule applies inside a composite figure: a component that could not be measured is **dropped and named**, never scored zero or a neutral middle, and the survivors are re-weighted — the health score's largest component read 0/100 for a missing calendar and turned an Amber sprint Red. Below half the weight the composite refuses. Say which cause it was; *"no sprint calendar"* was printed for three different ones, including a calendar that was present and correct. `docs/adr/0010-an-empty-selection-is-a-refusal.md`.

**The organisation config travels inside the data, never beside it.** Which statuses mean done, which days are worked, the holiday calendar and the sprint length are resolved once by whatever produced the file and written into it as `orgConfig`. The page, the three tools that consume it and the live server all read it from there; none of them opens `config/organisation.json`. A config read separately by each consumer is a third opinion arriving by a different route, and its first symptom is the facts pack and the dashboard disagreeing about the same sprint. `src/app.js` mirrors `orgconfig.py` in JavaScript because the browser cannot call Python — `tests/e2e.py` asserts the two agree under a *non-default* config, since two implementations of Mon–Fri agree by accident. Change one, change both. On Forge there is no file to resolve from, so the resolver resolves it out of Jira's own status categories plus an `orgConfig` project property and writes it into every response — same rule, different source. `forge/src/jira.js` mirrors `validate()` only, and `tests/test_service.py` runs both over one shared set of cases.

**Every figure carries its unit.** Reported elapsed time is in **calendar days** (an item raised 21 days ago is 21 days old; saying 15 because of weekends is a lie of convenience). Simulated time is in **working days** (nothing completes on a Saturday). These two disagreeing silently is a real bug that shipped once — the facts pack and the dashboard reported 25% and 22% flow efficiency for the same sprint.

---

## Conventions that are load-bearing

**Forecasts are in items, never story points.** Six sprints is six point-observations, which cannot support a distribution; the same sprints hold roughly sixty items. Item counting also cannot be inflated by estimating generously. The dashboard has a Points toggle for display, but the forecaster only ever reads item counts.

**Monte Carlo is seeded and reproducible.** `SEED` is fixed, trials are 20,000. Same inputs, same answer, every time — a forecast that moves when nothing changed is not a forecast. Do not introduce unseeded randomness into anything that produces a published figure.

**Zero-throughput days stay in the sample.** Dropping them is the most common way a Monte Carlo turns optimistic. A model that never samples zero will never predict a stall.

**Refusal thresholds are hard, not advisory.** Below them the honest answer is "not enough data", not a wider interval. They are listed in `docs/forecasting-agent.md` §5 and `docs/product-intake.md`.

**No silent caps.** If code bounds its own output — top-N, truncation, sampling — it must say what was dropped. A truncated list reads as a complete one. This has bitten twice: a readiness printer that showed four gaps while the summary line counted five, and a backtest that quietly overlapped its windows.

**UI colour tokens are separate from the chart palette.** `--link`, `--accent-bg`, `--info-ink` exist so contrast fixes never touch the series colours, which are validated for colour-vision deficiency independently. Do not "simplify" them back together.

**Escape at output, once.** All issue-derived strings pass through a single `esc()` at the point of output, and URLs through `safeUrl()`. A Jira summary is writable by anyone who can raise a ticket. A stored XSS shipped here because two call sites interpolated `i.key` and `i.summary` directly.

---

## When you change something

1. **Run the suite that guards it**, not just the fast one. Changing `src/` means `make test`. Changing `agent/tools/` means `make test-agent`. Changing anything user-facing means both, plus `make test-a11y`.
2. **Add the test before you claim the fix.** Every entry in `CHANGELOG.md` that says "found and fixed" has a test pinning it. That is why the list is trustworthy.
3. **Write the changelog entry as prose, not a bullet of the diff.** The changelog records the *decision and the bug that prompted it*. It is the most-read file here after the README.
4. **If you find a bug that returns a plausible wrong number rather than failing, say so loudly.** That class is the worst failure mode this project has — a forecast computed against the wrong slice of data looks exactly like a correct one. Three of them shipped in the intake work and are documented in `CHANGELOG.md` under 1.8.0.

## Where to read more

| Question | File |
|---|---|
| What the dashboard does and why HTML | `README.md` |
| Every schema field and what it drives | `docs/data-format.md` |
| The agent's design, guardrails, evaluation | `docs/forecasting-agent.md` |
| Forecasting an ask before it exists | `docs/product-intake.md` |
| The agent definition itself | `agent/SKILL.md` |
| Why each rule above exists | `CHANGELOG.md` |
| What "done" means here, and which days count | `docs/organisation-config.md` |
| Connecting a customer's Jira with OAuth | `docs/connecting-jira-asana.md` |
| What a term means, and which words to avoid | `CONTEXT.md` |
| Why Forge would call a hosted calculator | `docs/adr/0008-forge-calls-a-hosted-calculator.md` |
| How the page reaches live data over two transports | `docs/adr/0009-one-contract-two-transports.md` |
| Why a tile with nothing to count says so instead | `docs/adr/0010-an-empty-selection-is-a-refusal.md` |
| Why a board without sprints gets a window, not a clock | `docs/adr/0011-a-kanban-context-is-a-window-not-a-clock.md` |
| Why Forge reaches the calculator by `invokeRemote`, region-pinned | `docs/adr/0012-the-calculator-is-reached-by-invokeremote.md` |
| Why the scheduled brief is written inside the tenant | `docs/adr/0013-the-brief-is-written-inside-the-tenant.md` |
| Why Jira sends the brief, and which scopes are not read-only | `docs/adr/0014-jira-sends-the-brief-and-the-read-only-rule-bends.md` |
| Why the durable series stores so little, and what a reconstructed sprint may not claim | `docs/adr/0015-a-durable-series-stores-what-jira-forgets.md` |
| Why the image upgrades its own base packages, and what the scan gate does and does not block | `docs/adr/0016-the-image-takes-debians-security-updates-at-build-time.md` |
| Which commercial roadmap item something is, and what is done | `docs/roadmap.md` |
| What the dashboard does for a board with no sprints | `docs/kanban-boards.md` |
| Finishing the Forge route — the three unfinished pieces | `docs/forge-deployment.md` |
| Where the hosted calculator runs, what it costs, and in what order | `docs/hosting-the-calculator.md` |
| The decisions behind the constraints above | `docs/adr/` |

## Agent skills

### Issue tracker

Issues live as GitHub issues on `Xeno828/delivery-value-dashboard`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical roles, each label string equal to its name. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: the glossary in `CONTEXT.md` and the decision records in `docs/adr/`, both at the repo root. See `docs/agents/domain.md`.
