# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two primary users, confirmed 2026-09-03, and design decisions are made for both:

- **The delivery manager or head of delivery.** Produces the fortnightly delivery report, defends its numbers when challenged, and sends the view on to leadership. Today that reporting costs about a day a fortnight and answers "what happened" when leadership is asking "what will happen, what will it cost, and what is it worth." This user needs every figure to carry its basis so it can be defended without recomputing it.
- **The executive or leadership reader.** Reads the headline band, the value figures, the risks and the written brief. Needs a reason to trust a figure, not a way to compute it. Scans left to right across a single band; a figure buried inside a chart card is a figure not read.

A third audience is real but secondary: the engineer or team lead who interrogates a number by clicking through to the issues behind it. Every tile, bar and risk must keep that drill-down, but the surface is not designed for them first.

## Product Purpose

The Delivery Value Dashboard turns a team's Jira or Asana data into a delivery report an executive can read and an engineer can interrogate, and forecasts when outstanding work will actually finish. It exists because most sprint dashboards report activity, and activity reporting fails to answer four questions: are we behind or were we given more; where does the time actually go; is the commitment realistic; and what is any of it worth.

Success is a report that leadership reads and trusts without a delivery manager spending a day assembling it, where every number on the page can be traced to the issues behind it and every forecast states the evidence it rests on. The commercial goal, per `docs/roadmap.md`, is a Marketplace app: *From File to Product*. All seven roadmap items are done as of 2026-09-03; the app is at 9.1.0 and eligible for *Runs on Atlassian*.

## Positioning

The mechanism a neighbouring dashboard cannot truthfully copy is **refusal**. The product refuses to say what the evidence cannot support: below a hard threshold it says "not enough data" rather than widening an interval; over an empty selection it refuses rather than reporting zero; when a component of a composite score cannot be measured it is dropped and named, never scored neutral. Refusals are printed verbatim and end by stating that the evidence is absent, not noisy.

Three refusals are product-defining and permanent:

- **No priority score.** No WSJF, no value-over-effort ratio. The delivery consequence of an ordering is computed and returned; the relative worth of competing asks stays with the people accountable for it. The value basis is free prose for that reason.
- **No hours, overtime or timesheet field.** Load is measured as work in progress and unplanned work, derived from issue status.
- **No ranking of individuals.** Throughput is a property of the system. Ownership counts are fine; league tables are not.

Everything else follows from one rule: **every figure comes from one implementation.** The same Python that runs on the command line computes the facts, the forecast and the sequencing inside the Forge function under WebAssembly, byte for byte. Nothing between the tools and a reader does arithmetic, including the agent that narrates the report.

## Operating Context

- **Lead surface: the Forge app inside Jira** (confirmed 2026-09-03). The dashboard renders in a Jira project page iframe titled *Delivery & Value*, reads the tenant's own boards, sprints and issues over the bridge, and computes every figure inside the Forge function with no remote and no egress. New work is designed for this surface first.
- **Second surface: the standalone HTML file.** One self-contained file in `dist/`, opened from disk or emailed. It makes zero network calls and uses zero browser storage because the threat model is that it gets forwarded. Live mode adds a local server for Monte Carlo tiles; without it those tiles show an offline notice.
- **One page, two homes.** The same `src/` builds both. The page never learns which transport it has.
- **Data arrives three ways:** a file upload through a three-step import wizard (choose, map, preview); a fetcher script on a schedule; or the Atlassian and Asana connectors through Claude. On Forge the data is the tenant's own boards.
- **Rituals it serves:** the fortnightly delivery review, the sprint commitment conversation (trailing three-sprint average offered as the next commitment), intake of a new ask before any of it exists, and a scheduled brief written inside the tenant and sent through Jira notifications.
- **Two kinds of board:** a sprint board has a committed scope and a clock and therefore a burndown, a pace and a health score; a flow board has a window and none of those. Which kind a board is decides what the page may say about it.
- **Two themes,** light and dark, both tested.

## Capabilities and Constraints

- **Name:** Delivery Value Dashboard; *Delivery & Value* as the Jira page title. Version 1.12.4 for the file, 9.1.0 for the Forge app. Licence MIT.
- **Views:** an eight-tile KPI band; burndown with scope as a separate line, in items by default with a Points display toggle; per-item elapsed time split into waiting and worked; committed against completed for six sprints; value with a stated basis and a count of unvalued items; ageing bands; a risk register computed from the data on screen; a sprint health score that shows its full working on hover; a Monte Carlo forecast tile with three modes (when will it finish, how many by a date, sequence asks); a cross-team roll-up that names its boards and refuses to forecast; a context bar with cascading Project → Board → Sprint pickers. Every tile opens a drill-down panel listing the issues, exporting to CSV.
- **Units are part of the figure.** Reported elapsed time is in calendar days; simulated time is in working days. Forecasts are in items, never points. Business value is counted at one hierarchy level only. A parent and its subtasks are one item. What was not counted is reported beside every figure.
- **No silent caps.** Any bounded list says what it dropped.
- **Terminology** is fixed by `CONTEXT.md` and the decision records in `docs/adr/`. *Issue*, *item*, *point*, *epic*, *board*, *sprint board*, *flow board*, *ask*, *candidate*, *value basis* are the terms; the glossary names what to avoid.
- **Technical:** four source files assembled by `build.py` into one HTML file; `dist/` is committed; no runtime dependencies, no CDN, no fonts fetched, no analytics, no browser storage. UI colour tokens are separate from the chart palette, which is validated for colour-vision deficiency independently. All issue-derived strings are escaped once at output.
- **Forge:** every scope is read-only except two named ones; the manifest declares no remote and must not gain one. The first external install, planned for September 2026, closes the window in which module and scope changes are free.
- **Undecided:** nothing product-level is open. The roadmap is complete; what follows it has not been written.

## Evidence on Hand

- **Demo videos:** `docs/demo.mp4` (three minutes) and `docs/demo-small.mp4`.
- **Screenshots:** `docs/screenshots/dashboard.png`, `docs/screenshots/context-picker.png`, `docs/screenshots/import-mapping.png`; `tests/last-run.png` from the browser suite.
- **Sample data:** `data/sample-bundle.json` and the demo bundles regenerated by `make bundle`; sample asks under `data/asks/`. Real tenant data in `data/dashboard-data.json` is git-ignored because it holds real issue titles.
- **The argument:** `docs/dashboard-review.md` is the full case written against the dashboard this replaced; `docs/agent-executive-summary.md` is the agent for a leadership audience; `CHANGELOG.md` records each decision and the bug that prompted it.
- **Absences not to fabricate:** no customer names, testimonials, case studies, benchmarks, pricing or Marketplace listing copy exist. The first external install has not happened.

## Product Principles

1. **Refuse before you round.** A figure the evidence cannot support is withheld in stated words, never approximated, zeroed or softened.
2. **Every number has a basis a reader can click.** A figure without its slice, span, unit and what was excluded is not finished.
3. **Compute once, quote everywhere.** One implementation produces every figure; every other layer, including the narrator, passes it through unchanged.
4. **Return the consequence, not the verdict.** The product computes what an ordering costs and leaves the judgement of worth, in prose, to the people accountable for it.
5. **Design for the reader who forwards it.** The file may be emailed and the app may be installed by a stranger; nothing may depend on a network, a store, or a person being present to explain it.

## Accessibility & Inclusion

WCAG 2.2 AA is the required standard, enforced by `tests/a11y.py` over the built page in both light and dark themes, including states an automated scanner would miss: the import wizard and the empty-selection refusals. Every text and control colour clears 4.5:1; pointer targets meet 2.5.8 AA; `prefers-reduced-motion` disables transitions. The chart palette is validated separately for colour-vision deficiency. The written brief and every report must read correctly with no colour at all, since they are also delivered as text.
