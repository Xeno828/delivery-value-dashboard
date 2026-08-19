# Changelog

## 1.12.3

**The demo now shows the Monte Carlo tile, all three questions.** Four new scenes: *when* the outstanding work lands, the same history asked about **30 items that do not exist yet**, *how many* land by a chosen date with the next-sprint commitment, and *what each ordering of the asks costs the others* — including the asks that miss their date in every ordering and the two the tool could not size.

**Recording it required serving the page.** The tile is answered by `forecast.py` and `intake.py` over the live-mode connection, so `record_demo.py` now starts `serve_live.py` against the demo bundle and drives the page over http rather than `file://`. It serves **the same bundle the page displays** — a different one would have put a disagreement between the tile and the page on film, which is the exact failure this design exists to prevent.

Two small recorder capabilities came with it: typing into a field as a scene action, and waiting for a fetch to land so the video shows the answer rather than the *"running 20,000 simulations"* moment.

Both cuts re-recorded: 2m50s, 11 MB and 3.7 MB.


## 1.12.2

**The 320px reflow failure was a sparkline, not the tile.** With the header fixed, the stricter check found the real remaining offender on CI: the value card's *last 6 sprints* sparkline. A fixed 110px chart sits beside the headline figure in a flex row that cannot wrap, so at 320px the pair overflowed the page — and the endpoint marker made it worse, because a circle centred on the SVG's right edge paints its radius outside the box it belongs to. A 110px decoration measured 324px across on a 320px screen.

The row wraps now, the chart never exceeds its column, and `spark()` insets both axes by the marker's radius so nothing is drawn outside its own SVG. The sparkwrap's right edge at 320px moves from 323 to 283.

**The reflow check now names what overflows.** A bare *"323"* is not actionable, least of all when the cause is font metrics on a machine other than the one running the test — this reproduced on no local configuration, including with glyphs stretched 40%. The check reports the offending elements with their right edges, and CI identified the sparkline on the first run afterwards.

## 1.12.1

**Fixed a WCAG 1.4.10 reflow failure introduced by the third forecast mode.** Adding a *Sequence asks* button made the tile's segmented control 260px wide with `flex-wrap: nowrap` above it, so at a 380px viewport its right edge sat at 364 — inside the card, 16px from the screen. On CI's Linux font metrics those same three labels render wider and the page needed 399px, so it scrolled sideways and the accessibility suite failed.

The fix is structural rather than a shorter label: card headers, their tool groups and the segmented control all wrap now, the title block yields space before either wraps, and below 760px the tools take their own row. The control's right edge moved from 364 to 283 at 320px, and the layout holds with glyphs 40% wider than they render here.

**The suite was checking the wrong width.** WCAG 1.4.10 specifies **320 CSS pixels**; this checked 380, which is softer, and it passed on macOS while CI failed on Linux. It now checks both, and additionally asserts that no laid-out control comes within 8px of the 320px edge — because a control that just reaches the viewport passes on one machine and fails on the next, which is exactly what happened. Against the previous CSS the 320px checks fail and name the offending element; the 380px check still passes, which is the whole point of adding them.


## 1.12.0

**Ask sequencing is on the tile.** A third mode runs `intake.sequence()` for the selected board and shows what `make intake-sequence` shows: what each ordering of that board's outstanding asks costs the others. Asks come from `data/asks/`, matched to the board, and the view follows the dashboard's selection like the other two.

**It leads with the part that ends the argument.** Asks that miss their date in *every* ordering are printed first and separately, because that is not a prioritisation problem — no sequence saves them, and the only levers left are scope, capacity or the date. A planning meeting that spends an hour re-arranging a list which cannot be re-arranged into success is the thing this is meant to prevent.

**Asks it could not size are named, with the tool's reason.** On the demo bundle two of the four are dropped — *too few completed epics to calibrate a t-shirt scale*, *too few completed epics to form a reference class* — and both appear under the comparison rather than vanishing from it. A comparison of two asks that silently began as four reads as the whole picture.

**Still no value score, and still none coming.** The tool's closing sentence is printed verbatim: the delivery consequence of each ordering is computable, the relative worth of the asks is not.

**Honest edges.** A board with no recorded asks says so instead of returning an empty table. A live Jira connection declines with a reason — sizing needs the board's completed epics and its measured interruption rate, which a sprint-at-a-time pull does not carry — rather than assembling a partial dataset and returning a number built on it. And the tile no longer claims to print "the same output" as the terminal command: `make intake-sequence` defaults to a different bundle, so it names the tool and tells you to compare like for like before calling a difference a disagreement.


## 1.11.0

**The forecast tile takes an input, so it answers hypotheticals as well as the sprint in front of you.** *When* accepts an item count and *How many* accepts a date, both defaulting to the selected sprint's own figures. Ask for 30 items against the Storefront team's measured pace and the answer is 41 working days at the 85th percentile; ask how much lands by 31 October and it is 44 items. The same history, a different question.

**An asked-for figure is labelled as one.** The lead line reads *"30 items asked for — not this sprint's 4"*, because a hypothetical that looks like a status report is worse than no answer at all. The endpoint echoes `asked.default_items` and `asked.default_date` so the swap is always visible, and a one-click reset returns to the sprint's own numbers.

**Rejected input says so instead of quietly reverting.** An out-of-range count is refused with `400` at the server and an explanation in the tile — *"0" is not a whole number between 1 and 5000. Showing this sprint's own outstanding count instead.* Silently substituting a different number would return a figure answering a question nobody asked, which reads exactly like an answer to the one they did.

**A bug this feature would otherwise have shipped: the simulation's horizon was silent.** Each trial is abandoned after 400 working days, and a request beyond the team's pace returned every percentile at exactly 400 — uniform, precise and meaningless. Unreachable while the item count came from real sprint data; reachable the moment anyone can type a number. `forecast_completion()` now counts abandoned trials, returns `unfinished_fraction`, and names the horizon in its basis line whenever it is non-zero. The tile prints *"These dates are a floor"* above the table. This is the no-silent-caps rule applied to the forecaster itself, and it holds for the CLI and the agent too, not just the tile.


## 1.10.0

**The Monte Carlo forecast is on the dashboard, not just in a terminal.** A new tile answers the two questions `forecast.py` exists for — *when will this finish* and *how many will land by the date* — for whichever project, board and sprint is selected, and re-runs when that selection changes. The second question also carries the next-sprint commitment sizing, with the tool's note about the median printed as written.

**It is served, not reimplemented.** The tile calls `agent/tools/forecast.py` through a new `api/forecast` endpoint in `serve_live.py`. Nothing in the page computes a forecast; it formats values already in the payload and quotes the tool's own sentences. A second Monte Carlo written in JavaScript would be a second set of numbers, and the tile and a written brief would eventually disagree about the same sprint — the failure this project treats as worst. The trade is stated plainly: **the tile does not work in an emailed file**, where it shows an offline notice instead. It is the first thing here that needs the server to be useful.

**It samples the team's whole history, and says so.** A forecast built from one sprint refuses — on the demo board a single sprint offers 2 throughput observations against a threshold of 8, while the team's six sprints offer 55. So the sample is the team, sliced by `team` and falling back to project+board, and only the *outstanding count* comes from the selected sprint. Conflating those two is exactly the 1.8.0 bug that turned a 19-day forecast into 77 and looked entirely credible. A test pins both halves: the sample must be 55 observations and the remaining count must be 4.

**`build()` now samples every recorded day rather than a 90-day tail.** The old default silently discarded older history on a long import — a smaller sample, and one that can drop under the refusal thresholds for no stated reason. Both the tile and the CLI now pass the full span, because if they sampled different windows they would report different forecasts for the same sprint. **This changes nothing today**: every dataset in the repo spans 76–79 days, so full-history and 90-day sampling are byte-identical on all three, the recorded demo keeps its figures and `agent/snapshots/` stays valid. A test asserts that equality so the day a longer dataset lands, the divergence appears in the suite rather than in a forecast someone has already quoted.

More history means older throughput, and a team's pace from eight months ago may not describe it now. `size_stability()` already reports that drift, and the tile now shows the slice, the date span and the observation count — a wide window should be visible rather than implied.

**New coupling, deliberately.** `scripts/serve_live.py` now imports `agent/tools/forecast.py`; it is the first dependency from `scripts/` on the agent tools. That is the point of serving the real thing.


## 1.9.2

**The source badge denied live connections that were working.** With `make serve-live` running, the page said *"Demo data (no live connection)"* while the very same server was handing it eighteen sprints. Nothing was broken underneath — the probe succeeded, the contexts merged, the project/board/sprint bar appeared, switching worked. Only the badge was wrong, and it was wrong in the most damaging way available: stating as fact that the thing you were demonstrating was not happening.

The cause is that the badge reported one fact while claiming another. It read `meta.sourceLabel` — what the **loaded dataset** says about itself — and never consulted `S.live`, which is the only thing that knows whether a server answered. The bundled demo file labels itself "Demo data (no live connection)", so that string was printed verbatim whether or not a connection existed. The two are genuinely different questions: a live connection can serve demo data, which is exactly what `serve_live.py --bundle` is for.

Now the badge reports the connection when there is one — *"Live: bundle file sample-bundle.json"*, green rather than amber — and falls back to the dataset's own label when there is not. The tooltip states both, because "connected to a demo bundle" is the honest description and neither half should be dropped.

A test pins it in `tests/security.py`, which is the only suite holding both a browser and a running server. It loads the page over http against the live server and fails if the badge denies the connection; that failure was confirmed by reverting the fix, not assumed.


## 1.9.1

**The live-mode server dropped the connection on any 404 instead of sending it.** `log_message()` tested `"/api/" in a[0]` to decide whether a line was worth printing. Two callers reach it with different shapes: `log_request` passes the request line as a string, `log_error` passes an `HTTPStatus`. Membership against a non-string raises — and it raised *after* the 404 had been decided but *before* it was written, so the handler thread died and the client saw a dropped connection rather than a refusal. A browser asking for `/favicon.ico` was enough, which means it fired on every page load in live mode and filled the terminal with tracebacks. During a demo, that is the whole impression.

**The worse part is what it was hiding.** Three path-traversal checks in the security suite were passing *because* of it. They asserted only that `root:` did not appear in the response body, and a dropped connection has no body, so they passed without ever testing traversal. The protection itself was real — `SimpleHTTPRequestHandler.translate_path` collapses `..` before any file is opened, and the 404 was correct — but the tests were not proving it. A check that cannot tell "refused cleanly" from "crashed before answering" is not a check.

Those three now require an actual HTTP status (403 or 404) alongside the absent body, and a fourth asserts that a plain missing file returns a clean 404 rather than a dropped connection. All four fail against the unfixed server; that was verified by reverting the fix and re-running, not assumed.

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
