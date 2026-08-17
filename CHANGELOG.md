# Changelog

## 1.9.0

**Tiles can be turned off, so one file can be sent to two audiences.** The **Tiles** button picks which of the twelve tiles a view contains, with an **Executive** and a **Team** preset. Both keep *What this sprint means*: a view without the narrative is the wall of charts this page exists to replace, and sending an executive one is how a dashboard gets skimmed and ignored.

**The presets are the agent's two reports, not a fresh opinion.** Executive is shaped after `agent/templates/exec-brief.md` — will we make it, what changed, what it is worth, what we need from you. Team is shaped after `team-report.md` — where we are, unblock, ageing, flow, what to commit next. The page and the agent describing the same audience differently is a worse failure than either being slightly wrong on its own, so the two are pinned together by a test that asserts each preset's exact tile set.

**Visibility changes what is shown and nothing that is counted.** Every figure still comes from the same `derive()` over the same filtered issues whether its tile is on screen or not, so a tile that reappears agrees with the one beside it. There is a test that hides tiles and asserts the headline numbers are byte-identical afterwards, because the alternative — a view whose numbers depend on which tiles you left on — would be undetectable by eye and fatal to the whole premise.

**A saved view carries the data that is loaded, not the data the file shipped with.** *Save this view as a file* writes a standalone copy with the tile selection and the current dataset baked in. This is the subtle one: after an upload the dataset lives in memory, not in the seed script, so serialising the document alone would have handed someone a file that silently reverted to the demo sprint — correct-looking numbers about the wrong company, which is exactly the failure class this project treats as worst. The test loads a 242-issue bundle, saves a view, reopens the saved file and asserts it still reports 242.

**The view travels three ways** because the file is distributed three ways: baked into a saved copy, honoured by the print stylesheet so a PDF matches the screen, and encoded in the URL (`?view=exec`, `?tiles=…`) for when the file is hosted. **Not in browser storage** — the intended distribution method is email, which storage does not survive, and this file uses none.

**Hidden tiles are named, not counted.** The picker lists what it has dropped. A view that quietly omits a tile reads as a complete page to whoever receives it, which is the same no-silent-caps rule the flow-time chart already follows.

An unrecognised `?tiles=` value shows everything rather than an empty page — a blank dashboard reads as a broken file, not as a deliberate view.

## 1.8.2

**`PUSH.md` and `scripts/setup-on-mac.sh` are gone.** Both existed to get this repository from a delivered zip onto a remote for the first time. That has happened; neither can happen again. `setup-on-mac.sh` hard-coded `$HOME/Downloads/delivery-value-dashboard.zip` as its input, which is the clearest possible statement that its job was one-time.

Almost nothing was lost with `PUSH.md`, because almost everything in it was already in `README.md` — that `dist/` is committed on purpose, that `.env` and `data/dashboard-data.json` are git-ignored, how the fetcher is configured. Documentation that restates another file drifts from it, which is exactly what had happened: `PUSH.md` was corrected in 1.8.1 to say the Pages workflow is manual-only, and the README's deploy section was left still claiming Pages "publishes the demo dataset" with no mention of the trigger. **The README now carries the corrected statement**, including the part that matters — the job publishes the whole of `data/`, not a curated demo subset.

The rule this is an instance of: a document whose purpose is a one-time transition should be deleted when the transition completes, not left as a description of a world that no longer exists.

## 1.8.1

**The Pages workflow is manual-only now.** It triggered on every push to `main`, which meant the decision to publish was made by the act of committing rather than by anyone choosing to publish. The job copies the whole of `data/` into a public site. On a repository where the fetcher has been run, that folder holds real issue titles — the one thing the `.gitignore` entry for `data/dashboard-data.json` exists to keep out of git in the first place.

Nothing leaked. On a fresh repository the job fails at `configure-pages` because Pages is not enabled, which is what happened here. But that is GitHub's account setting standing in for a guard the workflow should have had itself: enable Pages for any reason later and the next commit publishes `data/`, with no step in between where a person decides. The trigger is now `workflow_dispatch` only, so publishing is a deliberate act every time.

This also removes a red cross from every push, which matters more than it sounds — a build badge that is always failing for a known-harmless reason is how a real failure goes unread.

`PUSH.md` said the workflow was "not enabled by default". That was true of GitHub Pages the feature and false of the workflow, which ran on all five pushes. Corrected.

## 1.8.0

**Product intake.** The agent can now forecast an ask before a single ticket exists for it — a described product request plus a named team, in; a sized range with two delivery scenarios and its uncertainty attributed, out. `agent/tools/intake.py`, `make intake`.

The portfolio decision that costs the most money is made at intake, and it is normally made on either a refusal ("we'll estimate it once it's refined", which means the decision gets made on nothing and refinement justifies it) or a bare number ("about six weeks", which is how a guess becomes a commitment in the retelling). This does neither.

**Sizing is a ladder and the rung is always declared.**

- `tshirt` — bands calibrated from the board's **own** completed epics, because an "L" has never meant the same thing on two teams. On the demo board: S 4–6, M 8–12, L 13–21, XL 24–38, cut as quartiles of 16 delivered epics. Fewer than eight completed epics and it refuses rather than cutting four bands from seven observations.
- `reference-class` — every completed epic on the board. Widest range, fewest assumptions.
- `explicit` — a refined min/likely/max as a triangular distribution.

Each prints its own caveat verbatim. The t-shirt caveat says the thing that matters: the band's width reflects only how varied past epics of that size were, **not how wrong the t-shirt judgement itself might be**. That error is bounded by refinement, not simulation, which is why an intake figure is never a commitment and the forecast is re-run afterwards.

**Two capacity scenarios, always both.** *Earliest possible* — dedicated capacity, nothing queued — is a ceiling, not a plan. *Realistic* queues the ask behind committed unfinished work and thins throughput by the board's measured interruption rate (12.4% on one demo board, 3.2% on another; neither number was chosen). Interruption is modelled as a thinned throughput series rather than a multiplier on the final date, so its variance survives into the percentiles. The gap between the two is reported as **the cost of the existing queue in working days** — 30 days on the demo ask, which is the number to quote when someone asks why it cannot start now.

**Uncertainty is attributed, not just stated.** Three simulations — both inputs varying, size frozen, throughput frozen — split the spread between *not knowing how big this is* and *normal delivery variability*. A vague ask on the demo data attributes 54% to size; the same ask refined attributes 10%, and the spread narrows from 34 working days to 19. The first result sends the ask back to refinement with a reason. The second stops a team being told to tighten up an estimate that was never the problem.

**A readiness gate runs first.** `title`, `team` and `sizing` are required or nothing is forecast at all. The rest are reported as gaps with their consequence stated — a value amount supplied without a basis is flagged specifically, because an unsourced number is the one most likely to be quoted back in a steering meeting. The failure mode of any intake tool is making an unchallenged ask look processed.

**Sequencing returns consequences, not a score.** Every ordering is evaluated for what it costs the other asks, and anything that misses its date *in every possible ordering* is reported first and separately — the conversation that otherwise happens six weeks late. **No WSJF, no weighted score, nothing of that family**, and the reasoning is in the code as well as the docs: those formulas multiply an unvalidated value estimate by an unvalidated size estimate and present the product as arithmetic. The delivery consequence of an ordering is computable and is returned; the relative worth of the asks is a judgement and stays with whoever owns it.

**Three scope bugs found while wiring the demo, all of which returned plausible wrong numbers rather than failing:**

- `board_issues()` returned the board's **first** context, not its most recent, so `asOfDate` came from a sprint that ended in June. The trailing throughput window then landed almost entirely in a quarter with no deliveries, and a 16-item ask forecast at **77 working days** instead of 19. This is the worst failure mode a forecaster has — a credible number computed against the wrong slice of the file.
- The interruption rate was read from whichever context happened to be last in the file, so a board could inherit another board's rate.
- `queue_ahead()` ignored its `as_of` argument and counted work raised after the forecast date as already queued ahead of the ask.

All three are now pinned by an `intake — scope` section in `tests/test_agent.py`, which asserts the throughput window contains real delivery, that the implied rate is a working team rather than a stalled one, and that interruption is measured per board.

**Also fixed:** the CLI printed at most four readiness gaps while the verdict line counted all of them, so the output disagreed with itself. Every gap is printed now — a gap you cannot see is a gap nobody fills.

**Added:** `docs/product-intake.md`, `agent/templates/intake-brief.md`, three worked asks in `data/asks/` (one per sizing method, one of which cannot be delivered on time at any priority), `scripts/make_intake_demo.py` and `data/demo-intake-bundle.json`.

The intake bundle is deliberately **separate** from the demo bundle. Intake needs finished epics to calibrate against; the demo bundle's epics are long-lived themes that never close. Adding delivered epics to the main bundle would have changed its throughput, and with it the forecast figures quoted in the demo video and the executive summary. `make bundle` now builds both.

## 1.7.0

**Overtime removed.** The organisation does not operate overtime, and charting hours implied a time-tracking regime that does not exist.

Deleting the line would have left a worse card than the one being fixed: "Sustainable pace" worked because of the pairing — output rising *funded by* overtime is borrowed. With the counterweight gone, "output per person" is a productivity-per-head metric with nothing to check it, which is the individual-performance framing this dashboard refuses everywhere else. So both series went.

The card is now **Team load**, built from two signals that come from issue status and nothing else:

- **Work in progress** — started but unfinished at each sprint's end. Rising WIP with flat completion means more is being started than finished.
- **Unplanned work** — items that arrived after planning. Rising interruption is a triage problem, not a capacity one.

`overtimeHrs` and `teamPutsSP` are gone from the schema, the fetcher, the import pipeline, the generators, the sample data and every document. No hours field remains anywhere.

**Accessibility suite** (`make test-a11y`) — WCAG 2.2 AA against the rendered page in both themes. Found and fixed on first run:

- 67 text nodes below 4.5:1 in light mode. `--muted` was 3.5:1; links and the primary button were 4.3–4.4:1. Fixed with **separate UI colour tokens** (`--link`, `--accent-bg`, `--info-ink`) so the validated chart palette is untouched — the series colours still pass their colour-vision checks unchanged.
- Executive-summary severity icons used white glyphs on every status colour; white on the warning yellow measures **1.8:1**. Glyph colour is now chosen per severity.
- Closing the drill-down panel dropped focus to the document. It now returns to whatever opened it (WCAG 2.4.3).
- The source chip was styled as a status chip, so it tripped the colour-never-alone rule despite not being a status.

**Security suite** (`make test-security`) — found a **real stored-XSS**: the risk register and executive bullets interpolated issue keys and summaries into HTML without escaping. A Jira summary is writable by anyone who can raise a ticket, so this was reachable in normal use. Fixed by moving to a single escape point at output. Also added a `safeUrl()` guard — `esc()` neutralises markup but not a `javascript:` scheme, and the issue `url` field went straight into an `href`.

Now covered: injection through every string field, prototype pollution via `__proto__` and `constructor.prototype`, zero network calls, zero persistence, live-server path traversal and loopback-only binding, XXE and entity-expansion and zip-slip in the XLSX reader, committed-secret scanning, and a dependency audit.

**Also fixed:** `make_sample_bundle.py` emitted a file with empty burndowns unless you remembered a second Makefile command. The browser suite caught it. The generator now completes its own output.

## 1.6.0

**A shareable demo, and an executive summary of the agent.**

- `docs/demo.mp4` — a ~110-second captioned walkthrough. No audio, deliberately: it can be watched in an open-plan office or dropped into a Slack thread. Recorded from the real built file by `scripts/record_demo.py`, so it cannot drift from the product.
- `docs/agent-executive-summary.md` — the agent for a leadership audience: the problem, the value in the terms it will be judged on, how it works, what it will not do, and a four-phase rollout.
- `scripts/make_demo_bundle.py` — a bundle **authored to tell a story** rather than randomly generated. Three boards with deliberately different situations: one over-committed with a 21-day blocker and 32% flow efficiency; one healthy at 67% with commitments sized to actuals; one where 82% of items done reads as 48% of points because the two unfinished items are the two big ones. A demo on random data shows features; this shows value.
- The closing card's forecast figures are generated by running the real forecaster against the demo bundle, not written by hand.
- Two encodes: `docs/demo.mp4` (1600px, 8.7 MB) and `docs/demo-small.mp4` (1200px, 2.9 MB) for email and Slack.
- `make demo` rebuilds both.

## 1.5.1

**Performance measured rather than assumed.** `tests/perf.py` (`make perf`) instruments a real browser at four bundle sizes and reports load, sprint-switch, filter-keystroke and unit-toggle cost.

Findings, at 5,538 issues across 396 sprints:

- Interaction cost is **flat in dataset size** — switching sprint costs the same with 22 issues as with 5,538, because only the selected sprint is ever drawn. Chart redraw dominates and is constant.
- Building the sprint dropdown costs **0.2 ms** whether scoped to the current board or listing all 462 contexts. Scoping it is a usability decision; as an optimisation it saves 0.0 ms.
- The real ceiling is **payload, not CPU**: 2.8 MB, 79% of it the issue array. Stripping null fields and recomputable `workingDays` saves 8% — not enough to justify complicating the format.

No optimisation was made, because none was warranted. The harness is committed so the next such question gets an answer instead of an argument.

`make bundle --scale N` can now clone the demo board set for load testing.

## 1.5.0

**Project, board and sprint filtering.** One file can now hold many sprints, and the dashboard switches between them instantly and offline.

- New `schemaVersion: 2.0` bundle format — `contexts[]`, `contextId` on each issue, per-context burndown/history/releases/DORA. **v1.0 files load unchanged** and hide the context bar, because there is nothing to switch between
- Cascading Project → Board → Sprint pickers, with the active sprint marked and issue counts shown; boards scope to the project and sprints to the board
- **All N sprints** rollup per board. Flow, ageing, distribution, value and risks are valid across it; the burndown and release cards explain why they are not, rather than drawing something meaningless
- Each context's sprint history contains only sprints up to and including itself, so opening a past sprint shows what was knowable then rather than leaking the future into it
- `fetch_delivery_data.py --jira-boards 42,43 --sprints 6` builds a bundle
- **Optional live mode**: `scripts/serve_live.py` exposes `api/contexts` and `api/context?id=`, backed either by a bundle file or by Jira on demand. The page probes for it, merges sprints it does not have as stubs, and fetches one only when selected. Skipped entirely on `file://`, so an emailed copy stays silent and self-contained

**Fixed:** live-loaded issues were being re-tagged with the wrong context id by `normalise()`, so a fetched sprint rendered as empty. Issue coercion is now separable from context assignment.

## 1.4.0

**The dashboard now measures in items by default, with a Points toggle.** This closes the last place where the dashboard and the forecasting agent reported the same sprint in different units.

- One Measure control in the filter row switches the burndown, the Delivered / Pace / Scope-added / Carry-over tiles, the per-person distribution and the commitment history between items and story points
- `burndown[]` now carries `remainingItems` / `scopeItems` / `idealItems` alongside the point series; `history[]` carries `committedItems` / `completedItems`
- Computed in all three places that build a burndown — the browser import, the fetcher, and the new `scripts/rebuild_burndown.py` — and pinned to the same answer by tests
- Table views show both units at once regardless of the toggle, so nothing is hidden by the current setting
- The health score, the executive narrative and the risk register all follow the active unit, and the health tooltip now states which unit it was scored on
- Datasets predating the toggle render in points and say why, rather than showing an empty chart

**Fixed by rebuilding the sample burndown from its own issues:** the hand-authored series claimed 47 points remaining where the issue list said 42. The chart and the issues underneath it can no longer disagree.

## 1.3.0

**Item counts made the unit end to end.** The forecaster never used story points; the recommendation layer still did, which was the same inconsistency wearing a different hat.

- `recommend_commitment()` — Monte Carlo over a simulated sprint, returning how many **items** to commit to at each confidence level. Recommends the 85% figure, not the median
- `size_stability()` — detects the one thing that breaks item counting: a team splitting work smaller, which raises throughput without raising output. Flags drift (cycle time falling while throughput rises) and spread (p85/p50 above ~4)
- `metrics.py` predictability is now item-primary; points are retained for continuity and explicitly marked as not a forecasting input
- Agent definition, team-report template and design outline updated to size commitments in items and to check size stability before quoting any forecast

## 1.2.0

**Reporting & forecasting agent** (`agent/`). Design outline in `docs/forecasting-agent.md`; runnable definition in `agent/SKILL.md`.

- Hard split between reporting (deterministic) and forecasting (probabilistic). The agent narrates and never computes — every figure comes from `agent/tools/metrics.py` or `agent/tools/forecast.py`
- Monte Carlo forecasting over **item throughput**, not story points: 20,000 seeded trials, percentile dates, probability against an existing target date, per-release forecasts
- Refuses rather than guesses below documented thresholds, and the refusal text is required verbatim
- Scope growth sampled from history where available; the frozen-scope assumption is stated inline where not
- Ageing risk reported on two clocks — active time and end-to-end — because the gap between them is the finding
- Change detection against a stored facts pack, with direction and whether it reads as better or worse
- Calibration scoring (Brier, bucketed) over a forecast log, published in the brief footer
- Walk-forward backtest with non-overlapping windows: coverage 50/67/83/100% against nominal 50/70/85/95%
- Worked example exec brief and team report in `agent/examples/`

**Fixes found by the new tests.** Facts pack and dashboard disagreed on flow efficiency (25% vs 22%) from mixing calendar and working days — units are now declared on every block. The facts pack counted twelve weeks of history as sprint scope, reporting 89% complete on a 55%-complete sprint — reporting scope and forecasting scope are now separate. An earlier backtest reported 38% coverage purely from overlapping windows and truncated horizons.

## 1.1.0

**Upload pipeline.** Replaces the previous strict-schema import, which failed on any real export.

- Reads `.csv`, `.tsv`, `.xlsx` and `.json`, including raw exports from Jira and Asana
- `.xlsx` parsed natively — zip and inflate via `DecompressionStream`, no library
- Column auto-matching against a synonym list, with a mapping step that shows every guess and lets you override it
- Date handling for ISO, Jira's `22/Jul/26 3:41 PM`, `Jul 22, 2026`, Excel serial numbers and all-numeric forms; day-first versus month-first is detected per column and **flagged when undecidable** rather than guessed silently
- Mid-sprint additions can be inferred from the sprint start date when no column exists
- Merge mode: layer a value-estimate file on top of a tracker export, updating only supplied fields
- Preview step with counts, the first rows as the dashboard will read them, and warnings for duplicate keys, ambiguous dates and every missing field with its consequence
- **Burndown and the current history row are recalculated from uploaded issues** rather than inherited — the previous behaviour left stale charts under fresh numbers

**Repository.** Split into `src/`, `data/`, `scripts/`, `docs/`, `tests/`, `dist/` with a dependency-free `build.py`, a Makefile, CI that fails on a stale `dist/`, an optional Pages workflow, and an end-to-end browser suite covering four export formats.

**Fixes.** SVG value labels no longer swallow clicks on the bars beneath them. KPI tiles lay out correctly. Cards no longer stretch to the tallest in their row.

## 1.0.0

First version. Single-file dashboard with cross-filtering, drill-downs on every element, table views, computed risk register, health score with disclosed method, dark mode, print layout, CSV export, and the Jira/Asana fetcher script.
