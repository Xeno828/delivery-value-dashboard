# Delivery Value Dashboard

A single self-contained HTML file that turns Jira or Asana data into a report an executive can read and an engineer can interrogate. Every number on the page clicks through to the issues behind it.

No install, no build step, no server, no internet connection, no runtime dependencies. Open the file.

```bash
git clone <your-fork-url> && cd delivery-value-dashboard
make build && open dist/delivery-value-dashboard.html
```

**[▶ Watch the 2-minute demo](docs/demo.mp4)** ([lighter 2.9 MB version](docs/demo-small.mp4)) · **[Executive summary of the agent](docs/agent-executive-summary.md)**

---

## What it does differently

Most sprint dashboards report activity. This one is built around the four questions activity reporting fails to answer:

- **Are we behind, or were we given more?** The burndown plots scope as a separate line, so mid-sprint additions are visible instead of being absorbed into a flat delivery line. It reads in **items by default**, with a Points toggle — items is the unit the forecaster uses, and it cannot be inflated by estimating generously.
- **Where does the time actually go?** Each closed item is one bar split into *waiting in a queue* and *actively worked*. On typical data most of the elapsed time is queueing — the cheapest thing to fix and the thing standard lead/cycle charts hide.
- **Is the commitment realistic?** Committed against completed for six sprints, with the trailing three-sprint average offered as the next commitment.
- **What is any of it worth?** Value figures carry a stated basis, and the card says how many completed items carry no estimate — so the number reads as a floor, not a total.

Every tile, bar and risk opens a panel listing the underlying issues with owner, points, age and an elapsed-time breakdown, and exports to CSV. The health score shows its full working on hover. The risk register is computed from the data on screen, including the current filter — not typed by hand.

[docs/dashboard-review.md](docs/dashboard-review.md) is the full argument, written against the dashboard this replaced.

![The dashboard](docs/screenshots/dashboard.png)

## Getting data in

Three routes, in the order you should adopt them.

### 0. Pick a project, board or sprint — once the data is there

The dashboard holds many sprints at once. A context bar above the filters gives cascading **Project → Board → Sprint** pickers, plus an **All N sprints** rollup per board. Switching is instant and offline.

The page never talks to Jira itself — it cannot; MCP has no browser client and both APIs block cross-origin requests. Instead the sprints are bundled into the file up front, by the fetcher or by Claude through the Atlassian/Asana connectors. If you additionally run `make serve-live`, the page finds the local server and can pull sprints the bundle does not contain, on demand.

Full detail: [docs/contexts-and-live-mode.md](docs/contexts-and-live-mode.md).

### 1. Upload a file — works immediately

**Load data** → drop a `.csv`, `.tsv`, `.xlsx` or `.json` file. A raw export straight out of Jira or Asana is fine; column names are matched automatically and every guess is shown for you to correct before anything is applied.

The wizard is three steps: choose → map → preview. The preview shows counts, the first rows as the dashboard will read them, and warnings for duplicate keys, ambiguous date formats, and each missing field with its consequence stated. Burndown and sprint history are **recalculated** from what you upload rather than inherited, so you never get fresh numbers under a stale chart.

![Column mapping step](docs/screenshots/import-mapping.png)

Full detail: [docs/importing-data.md](docs/importing-data.md).

### 2. Fetcher script — for regular refreshes

```bash
pip install -r scripts/requirements.txt
cp .env.example .env          # add your API token; .env is git-ignored

./scripts/refresh.sh          # one sprint  -> data/dashboard-data.json

# or a bundle: several boards, six sprints each, one file
python3 scripts/fetch_delivery_data.py --jira-boards 42,43,51 --sprints 6 \
  --out data/dashboard-data.json
```

Then drop that file onto the upload panel, or `make serve` and open `?data=data/dashboard-data.json`. Schedule it with cron for a hands-off morning refresh.

The script derives two things a CSV export cannot give you: **cycle time**, from the first transition into an in-progress status in the Jira changelog, and **mid-sprint additions**, from when the sprint field was set.

### 3. MCP connectors — once the format has proved itself

Connect the Atlassian and Asana connectors in Claude and ask in plain language: *"pull Sprint 25 and rebuild the dashboard data."* Same JSON contract, nothing to run. Keep the fetcher for scheduled refreshes.

Full detail: [docs/connecting-jira-asana.md](docs/connecting-jira-asana.md).

## Repository layout

```
├── CLAUDE.md             the constraints, for any agent working in here
├── src/
│   ├── index.html        page structure + build placeholders
│   ├── styles.css        all styling, both colour themes
│   ├── app.js            metrics, charts, filters, drill-downs
│   └── import.js         file parsing + the upload wizard
├── dist/
│   └── delivery-value-dashboard.html    ← built output, committed
├── data/
│   ├── sample-sprint.json               demo dataset and worked example
│   ├── asks/                            worked product-intake requests
│   └── templates/                       CSV + JSON starting points
├── scripts/
│   ├── fetch_delivery_data.py           Jira + Asana → JSON
│   ├── rebuild_burndown.py              recompute a burndown in both units
│   ├── make_sample_bundle.py            random bundle, for load testing
│   ├── make_demo_bundle.py              authored bundle, for the demo
│   ├── record_demo.py                   records docs/demo.mp4
│   ├── serve_live.py                    optional live-mode server
│   ├── refresh.sh                       cron-friendly wrapper
│   └── requirements.txt
├── docs/
│   ├── dashboard-review.md              why it is built this way
│   ├── importing-data.md                the upload pipeline
│   ├── data-format.md                   every field and what it drives
│   ├── connecting-jira-asana.md         live data, and why not from the page
│   ├── contexts-and-live-mode.md        project/board/sprint filtering
│   ├── product-intake.md                forecasting an ask before it exists
│   ├── agent-executive-summary.md       the agent, for a leadership audience
│   ├── demo.mp4                         2-minute captioned walkthrough (8.7 MB)
│   ├── demo-small.mp4                   same, 1200px / 2.9 MB, for email
│   └── forecasting-agent.md             the agent's design outline
├── agent/                               reporting & forecasting agent
│   ├── SKILL.md                         the agent definition — runnable
│   ├── tools/metrics.py                 deterministic facts pack
│   ├── tools/forecast.py                Monte Carlo forecasting
│   ├── tools/intake.py                  product-intake sizing and forecasting
│   ├── templates/                       exec brief + team report + intake brief
│   └── snapshots/                       facts packs, scope history, forecast log
├── tests/
│   ├── e2e.py                           browser suite, 45 checks
│   ├── test_agent.py                    facts, forecast, refusals, backtest
│   ├── perf.py                          timing harness, four bundle sizes
│   ├── a11y.py                          WCAG 2.2 AA, both themes
│   ├── security.py                      hostile-data, secrets and server checks
│   └── fixtures/                        realistic Jira/Asana/XLSX exports
├── build.py                             the whole build, ~60 lines
└── Makefile
```

`dist/` is committed on purpose: the repository can be downloaded and used without running anything. CI fails if it is stale, so run `make build` and commit the result alongside any `src/` change.

## Commands

| Command | Does |
|---|---|
| `make build` | Assemble `src/` into `dist/delivery-value-dashboard.html` |
| `make test` | Build, then run the browser end-to-end suite |
| `make serve` | Preview on `localhost:8000` |
| `make check` | Fail if `dist/` is stale (what CI runs) |
| `make fetch` | Pull live data using `.env` |
| `make test-agent` | Agent tools only — facts, forecast, refusals, backtest |
| `make report` | Print the facts pack and forecast for the sample data |
| `make serve-live` | Serve with the live-mode API, backed by the demo bundle |
| `make bundle` | Regenerate the demo bundles, including the intake reference class |
| `make intake` | Forecast a product ask — `ASK=data/asks/INTAKE-2026-014.json` |
| `make intake-scale` | Print what S/M/L/XL mean on a board, in items |
| `make intake-sequence` | What each ordering of the outstanding asks costs the others |
| `make perf` | Measure load and interaction cost at four bundle sizes |
| `make demo` | Rebuild the story bundle and re-record the demo video |
| `make test-a11y` | Accessibility only — WCAG 2.2 AA, both themes |
| `make test-security` | Security only — XSS, pollution, traversal, secrets, deps |

## The reporting & forecasting agent

`agent/` holds an agent that turns the same dataset into an executive brief and a team report, and forecasts when outstanding work will actually finish.

Its one architectural rule: **the agent never does arithmetic.** Every figure comes from `agent/tools/metrics.py` (facts) or `agent/tools/forecast.py` (Monte Carlo over item throughput, seeded, 20,000 trials). The agent narrates, diffs against the previous snapshot, and frames the decision. That boundary is what makes a report from a language model auditable.

```bash
make report        # facts pack + forecast for the sample data
make test-agent    # including a walk-forward backtest of the forecaster
```

It refuses rather than guesses: on a single sprint of data the forecaster returns *"too little completion history to sample from — a wider confidence interval would not fix this, the data is absent, not noisy."* On twelve weeks it returns a 4% probability of the sprint landing complete, and an 85th-percentile finish eight working days late.

### Forecasting an ask before any of it exists

The same engine answers the question that arrives *before* the tickets do: a described product ask plus a named team, in, and a sized range with two delivery scenarios out.

```bash
make intake-scale                                    # what S/M/L/XL mean on this team, in items
make intake ASK=data/asks/INTAKE-2026-014.json       # one ask, both scenarios
make intake-sequence                                 # what each ordering costs the others
```

T-shirt bands are calibrated from the board's own completed epics rather than assumed, because an "L" has never meant the same thing on two teams. Every forecast returns **earliest possible** and **realistic** — the difference between them is the cost of the existing queue, in working days, which is the number to quote when someone asks why it cannot start now. And it attributes the uncertainty: *61% of this range is not knowing how big the ask is* sends it back to refinement, while *83% is normal delivery variability* says the estimate was never the problem.

No priority score is computed — not WSJF, not anything of that family. The delivery consequence of each ordering is computable and is returned; the relative worth of competing asks is a judgement and stays with the people who own it.

Design outline, question inventory, guardrails, failure modes and rollout: [docs/forecasting-agent.md](docs/forecasting-agent.md). Intake method and thresholds: [docs/product-intake.md](docs/product-intake.md).

## Deploying

- **Email it.** One file. This is the intended distribution method.
- **Shared drive.** Drop `dist/delivery-value-dashboard.html` next to `dashboard-data.json`.
- **GitHub Pages.** `.github/workflows/pages.yml` publishes the built file and the whole of `data/`. It never runs on its own — it is `workflow_dispatch` only, so you start it from the Actions tab and it publishes at no other time. Do not run it on a repository where the fetcher has written real issue titles unless your plan supports private Pages. CI itself needs nothing configured: no secrets, no environment.
- **Board pack.** The **Print** button lays the page out cleanly to PDF.

## Why HTML rather than PowerPoint or a BI tool

PowerPoint is a snapshot: no drill-down, no filtering, stale on export. Its one advantage — surviving a board pack — is covered by the print stylesheet.

A hosted BI tool (Power BI, Tableau, Looker) is the right destination once this is a standing report across many teams with row-level permissions. It costs licences, a pipeline and an owner. Don't start there; prove which metrics people actually use first. Migration is easy later because the data contract is already explicit.

Single-file HTML sits on the right rung: no infrastructure, no licences, works offline, and emails as an attachment.

## Security & accessibility

Both are tested, not asserted. `make test` runs all four suites; `make test-a11y` and `make test-security` run them individually.

**Accessibility** — WCAG 2.2 AA against the rendered page in both themes, including states a static scan misses (the drill-down panel, the import wizard). Covers accessible names, heading order, form labels, table twins for every chart, colour-never-alone, computed text contrast, keyboard operation, focus order and return, focus visibility, reduced motion, and reflow at 380px.

**Security** — the threat model is that this file gets emailed, and that its data comes from a tracker where any user can write an issue summary. The suite feeds it a dataset with an injection attempt in every string field and asserts nothing executes; checks prototype pollution, `javascript:` URLs, zero network calls, zero persistence; probes the live server for path traversal and non-loopback reachability; feeds the XLSX reader a workbook carrying an XXE, an entity-expansion bomb and a zip-slip filename; and scans the tree for committed credentials.

Both suites found real bugs on their first run. See the changelog.

## Privacy

- No network calls from the built file. No CDN, no fonts, no analytics, no telemetry.
- No `localStorage`, no cookies, no persistence of any kind. Uploaded files are read in the browser and discarded when the tab closes.
- Credentials exist only in the fetcher's environment.
- `data/dashboard-data.json` is git-ignored by default because it contains real issue titles.

## Known limits

- The reconstructed burndown assumes an issue's points leave the chart on its resolution date. If your Jira has a sprint report you trust more, substitute it in `build_burndown()`.
- `history[]` keeps the last six sprints and grows one row per refresh; run the fetcher at least once per sprint or the trend charts thin out.
- Team load is measured as work in progress and unplanned work, both from issue status. There is no hours or overtime field anywhere in the schema, by design — see [docs/data-format.md](docs/data-format.md).
- Value figures are planning-time forecasts, never reconciled against actuals. That is a process gap, not a tooling one — close it at 90 days.
- `.xlsx` reading needs `DecompressionStream` (Chrome/Edge 103+, Safari 16.4+, Firefox 113+). Older browsers are told to use CSV.

## Licence

MIT — see [LICENSE](LICENSE).
