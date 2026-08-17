# Working in this repository

Read this before changing anything. Most of what follows is a constraint that was arrived at the hard way, and the reason is given so you can tell when it genuinely does not apply rather than guessing.

`CONTRIBUTING.md` covers the mechanics. This file covers the things that will look like arbitrary preferences until you break one.

---

## The commands

```bash
make build         # assemble src/ into dist/delivery-value-dashboard.html
make check         # fail if dist/ is stale — this is what CI runs
make test          # all four suites: e2e, agent, a11y, security
make test-agent    # agent tools only, no browser needed
make report        # facts pack + delivery forecast for the sample data
make intake ASK=data/asks/INTAKE-2026-014.json
```

The browser suites need Playwright (`pip install playwright && playwright install chromium`). `make test-agent` needs nothing but Python 3.

**`dist/` is committed on purpose** so the repository is usable without a build step. If you change anything in `src/`, run `make build` and commit the result in the same commit. CI fails otherwise.

## Architecture in one paragraph

`src/` is four files assembled by `build.py` into a single self-contained HTML file. `agent/tools/` is three dependency-free Python modules — `metrics.py` (facts), `forecast.py` (Monte Carlo on work that exists), `intake.py` (forecasting an ask before any of it exists). `agent/SKILL.md` is the agent definition; it narrates what the tools return and computes nothing. `scripts/` fetches and generates data. `tests/` is four suites.

---

## Standing constraints

These are product decisions, not style. Violating one is a bug even when the tests pass.

**No hours, overtime, or timesheet field. Anywhere.** Not in the schema, the fetcher, the import pipeline, the UI, or a document. The organisation does not operate overtime, and a field for it implies a time-tracking regime that does not exist. Team load is measured as work in progress and unplanned work, both derived from issue status. If a metric seems to need effort data, it is the wrong metric.

**Never rank or compare individuals.** Throughput is a property of the system, not the person. The data cannot support the claim, and the first report that makes it is the last report anyone reads. Ownership counts are fine; league tables are not.

**Never compute a priority score.** No WSJF, no weighted shortest job first, no value-over-effort ratio, nothing of that family. They multiply an unvalidated value estimate by an unvalidated size estimate and present the product as arithmetic. The delivery consequence of an ordering is computable and must be returned; the relative worth of competing asks is a judgement that stays with the people accountable for it.

**The agent never does arithmetic.** Every figure in every report comes from a tool. This is enforced structurally — the tools emit numbers, the agent quotes them, the tests assert the tools agree with the dashboard. The moment the agent computes a percentage itself, nothing in the report is auditable and its entire value is gone.

**The built file makes zero network calls and uses zero browser storage.** No CDN, no fonts, no analytics, no `localStorage`, no cookies. The threat model is that this file gets emailed. The security suite asserts all of it.

**Credentials live only in the fetcher's environment.** `.env` is git-ignored. So is `data/dashboard-data.json`, because it contains real issue titles. Check both survive any `.gitignore` edit. The live-mode server binds to `127.0.0.1` only.

**Refusals are printed verbatim, never softened.** When a tool returns a refusal, the agent quotes the sentence as written. *"Not enough data"* and *"wide interval"* are different statements and only one of them is true. The refusal sentences all end with some form of *the evidence is absent, not noisy* — that clause is the point, do not trim it.

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
