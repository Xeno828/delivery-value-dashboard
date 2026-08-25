# Changelog

## 1.17.1

**Sizing an ask could never work over the route Forge would use, and the reason was one field reaching nobody.**

`intake.py` builds its reference class by grouping this board's finished epics and reading how big each turned out. It grouped them by `epic` — the epic's own summary. `epic` is free text, so `clean_dataset()` in `service/app.py` strips it on arrival, along with summaries, assignees and labels. That boundary is deliberate and is not the thing to change: a calculator has no business holding issue titles.

So over that route the grouping saw nothing, `epic_sizes()` returned an empty list, and both the t-shirt scale and the reference class refused — for every board, every time. The refusals were accurate, which is why nothing looked broken. What was missing was the capability, not the number: everything `docs/product-intake.md` describes was unavailable in principle to the only route a Forge install could take.

**`epicKey` was already travelling for exactly this and being read by nobody.** The resolver emits it, `CALC_FIELDS` sends it, the calculator's allow-list accepts it, and nothing at either end looked at it. Sizing keys on it now when a dataset carries one — which is precisely when the names have been stripped — and falls back to the summary otherwise, so bundles are unaffected. A key is the better handle regardless: two epics can share a summary, and renaming one splits its own history in half.

**The field is chosen once for the whole issue set, not per issue, and that is the part that needed care.** `i.get("epicKey") or i.get("epic")` reads as the obvious fallback and would split a single epic in two the moment a dataset carried the key on some of its issues and the name on others. A twenty-item epic arriving as two tens shrinks every t-shirt band and reads exactly like a team that has started working in smaller pieces — a plausible wrong number in a forecasting input, arrived at by arithmetic. The test builds that dataset, shows the naive fallback really would have split it, and shows this one does not.

Where the grouping was by key rather than by name, the basis line says so. A reference class assembled by issue key and one assembled by epic name are the same method over the same board, but a reader checking the working needs to know which column to look down.

**What was verified and what was not.** `/v1/ask` is exercised end to end in `tests/test_service.py` against a payload with every free-text field stripped, and it now returns a reference-class sizing where it previously returned a refusal. The **hosted calculator is still not provisioned** — `remotes[0].baseUrl` in the Forge manifest points at `.invalid` — so this has not been run against a real deployment, and the Forge resolvers still answer the forecast and sequencing routes with the offline notice. What is proven is the code path, not the deployment.

The assertion added in 1.16.10 recording `epicKey` as a known loose end is retired, and the allow-list guard it sat in now checks fields read by `agent/tools/` against that directory rather than against `src/app.js`, since that is where this one is read.

## 1.17.0

**Four flow tiles, and none of them needed a sprint or a window.** Cycle time, ageing work in progress, weekly throughput and cumulative flow are all properties of issues and dates — which is why they were available all along rather than something the schema had to grow, and the same reason the forecaster worked on a flow board from the start.

**How long finished work took** plots every closed item on the day it finished against 50/85/95 percentile lines. It is ranked above the cumulative flow diagram deliberately, against the usual instinct: it yields a sentence a team can take outward — *85% of what we finish, we finish within N days* — it names outliers into the drill-down, which is this product's whole signature, and it is read correctly by people who have never seen one. Cumulative flow diagrams are famously looked at and taken nothing from.

**Work in progress, and how old it is** puts open work against those same lines. It is the only tile on the page describing work a stand-up can still change: an item above the 85th percentile has already outlived 85% of everything the board has ever finished, and it has not finished. **How much finishes each week** is the series the Monte Carlo samples, shown so the forecast can be checked rather than taken on trust — quiet weeks included, because a model that never samples a zero never predicts a stall.

**The cumulative flow diagram has three bands and says so on the tile.** Nothing in a dataset records which column an issue sat in on a given day, so the bands are the three status *categories*, derived from `created`, `started` and `resolved`. A per-column version needs `statusTransitions` from the Python fetcher as well as the Forge resolver. A three-band chart presented as a full one is a different picture of the same board, so the limitation is printed rather than left to be discovered — and removing that sentence fails a test.

**Little's Law is reconciled under it, with no verdict drawn.** Work in progress over throughput is how long the average item must be spending in progress; measured cycle time is how long the items that finished actually took. Where they disagree by more than a factor of two the tile states both figures and says they do not line up. It does not choose between the two honest readings — the open work really is sitting far longer than anything that has finished, or start dates are not recording when work began — because choosing would be a claim about a team resting on whichever reading the reader happened to assume.

**Shown by default only on a flow board; available on every board.** All four measure a sprint board perfectly well, and hiding a measure that works is the same error as showing one that does not. Presets gained a board-kind column rather than a fourth preset: the audience question and the board question are different axes, and crossing them would mean four presets to keep in step with two report templates. A reader who chose *Executive* keeps that choice across a board switch and gets the executive cut of whichever board they landed on; a custom set is left exactly as they left it.

**Every figure is computed in `agent/tools/metrics.py` first.** The page mirrors the percentile function because a browser cannot call Python, which is the same arrangement `orgconfig.py` has, and it is kept honest the same way — by comparing the two rather than trusting they were written to match. `tests/e2e.py` reads the figures off the rendered tiles and holds them to the facts pack.

Three things this turned up that are worth recording. The first mutation test **did not fail**: changing the percentile constant from 85 to 80 passed, because on the sample data those are the same number and the caption said "85%" as a literal beside whatever figure the constant produced. That is a mislabelled number rather than a wrong one, and harder to notice; the sentence is built from the constants now and the test compares two percentiles that differ. The four tiles were also invisible to `tests/a11y.py`, which runs against sprint data where they are off by default — the four newest charts would have been the four nothing ever contrast-checked. It shows them explicitly, and asserts that it did.

### Considered and left out

**Blocked time**, the measure everyone asks for: `flagged` is a boolean with no history, so the schema cannot say when an item was flagged. Not computable rather than not wanted. **Flow distribution by work type**, which is easy from `type` and implies a target mix nobody set — the family [ADR 0004](docs/adr/0004-no-priority-score.md) exists to refuse. **WIP limits**, which need a limit somebody stated. **A flow-efficiency trend line**: the waiting-versus-working chart already is the graph view, and a ratio of two noisy quantities over time moves mostly with how accurately `started` was recorded, so it invites reading a data-quality artefact as a delivery change. And no per-person cut of ageing work in progress ([ADR 0003](docs/adr/0003-the-dashboard-does-not-measure-people.md)), nor any "what to pull next" ordering ([ADR 0004](docs/adr/0004-no-priority-score.md)) — an ageing chart invites both.

## 1.16.13

**The Monte Carlo tile was forecasting a board with no sprints two and a half times too fast.** Found by asking whether it still worked rather than assuming it did, and it is the exact failure this repository names as its worst: not a crash, a credible number.

`forecast.build()` needed no change and never has — it samples throughput over a rolling window of *days* and has never wanted a sprint boundary. The slice assembled around it is what broke. `team_slice()` gathers every context belonging to a team, and on a sprint board that is that team's sprints, which do not overlap: no key appears twice, and the slice has been correct for as long as it has existed. A flow board's three contexts are 14, 30 and 90 days of the *same* board. Every issue in the short window is in the long ones as well, so the slice held each of them three times, `throughput_samples()` counted three completions on the day one item finished, and the 85th percentile came back at **four working days against a true ten**. `item_risk` listed the same issue three times over.

Issues are de-duplicated by key now: one issue is one item, however many contexts hold it. It is a no-op on a sprint board. The test asserts the strong form — the same board described by one window and by three must forecast identically, so duplication is provably not an input rather than merely reduced.

**And the tile was answering a question about a deadline nobody set.** A window's `endDate` is today, because that is what the end of *the last thirty days* means, and it was being passed through as the forecast's default target. So *will this land in time* was asked against an end that is always now, and answered **0%** — in the one tile whose job is to say when work will land, with a probability of nought a reader can quote. The capacity figure alongside it refused with *"the target date has passed"*, which sends someone looking for a date that was never set.

A window now supplies no default target. The forecast still runs and still says when the open work lands; it just states no probability against a date nobody chose. The capacity refusal says *"this period has no end date to forecast against"*, which is a different fact from a target that has been and gone — both said the latter, including for any dataset carrying no end date at all, so that is fixed for sprint boards too. The date control offers a date rather than pretending to remember one, and a date the reader does name is answered normally.

**Neither was reachable inside a Jira tenant**, because the Forge forecast resolver still answers with the no-calculator refusal ([ADR 0008](docs/adr/0008-forge-calls-a-hosted-calculator.md)). Both were reachable over loopback, which is the route the demo and every local check use.

`next_commitment` was already refusing correctly, for want of a cadence rather than a date — that guard was put back in 1.16.4 and this is the first thing to lean on it.

## 1.16.12

**A board with no sprints gets a health score of its own.** The chip carried nothing on a flow board as of 1.16.11, which was right while there was nothing to put in it — a sprint-board figure refusing in the position the headline verdict occupies is noise rather than disclosure. There is something to put in it now. **Flow health** is built on flow efficiency at 40% of the weight, with blockers and ageing work at 30% each, and it is the one place in this work where a figure is genuinely *replaced* rather than refused or hidden.

Flow efficiency carries it because on a board that committed to nothing it is the closest thing to *is this working* the data holds: the share of an item's life that was work rather than queue. The other two are the sprint score's own hygiene measures, unchanged, because they describe the same thing on any board.

**Three components, not four dressed up as four.** There is no honest fourth. Work in progress has no target to be scored against without a limit somebody set, and cycle-time spread already has an implementation in `size_stability()` that a page-side copy would have to be kept in step with — which is the failure this repository keeps paying for, not a shape to fill in for symmetry's sake.

**Both scores go through one machine.** The drop-and-name rule, the re-weighting, the half-weight floor and the bands are shared; only the parts list differs. Two composites computed two ways would be two things to keep honest, and the day they disagreed about what *Amber* means every colour on the page becomes something to check rather than read.

**Flow efficiency is load-bearing, not merely heavy, and the floor would not have caught it.** Drop it and 60% of the weight survives — comfortably above the half-weight floor — so the score would have been reported. What survives is blockers and ageing work, which is hygiene: the same remainder the sprint score already refuses to call health, and here it would have been worse, because the name would have been the part that was not taken. Removing that guard prints **Flow health: Off track (44/100, 2 of 3 measures)** with the flow measure listed as not measured directly above it, which is what the test asserts against. It refuses instead, names `started` as the thing that is missing rather than asking for more data, and says where that field comes from.

**The chip says which composite it is carrying.** *Flow health* and *Sprint health* are different quantities built on different evidence. A chip that read the same for both would invite comparing two boards that were never measured the same way, which is the mistake this whole area exists to prevent.

**One threshold, where there were two.** The executive card called flow efficiency under 40% worth saying and the risk register drew its line at 45%, so the same board could be reported as fine in one paragraph and a risk in the next. There is one number now, it is 40%, it is what scores full marks in the new composite, and it is printed in the disclosure rather than applied quietly — a threshold a reader cannot see is one they cannot argue with. The tooltip also says that none of these three measures reads work volume, so unlike sprint health the points toggle cannot move this figure.

## 1.16.11

**A board with no sprints shows the tiles that measure it, and not the three that never can.** They refused in place until now, which was the wrong call and is corrected rather than quietly reversed — [ADR 0011](docs/adr/0011-a-kanban-context-is-a-window-not-a-clock.md) records both halves.

The line is whether the condition can lift. A sprint with no dates may get its dates; a points view may get its estimates; an empty selection may get issues. Those refuse **in place**, addressed to a reader who can do something about it, and sit in the tile so it is clear which figure is missing from where. The burndown, the commitment-history chart and team load on a flow board are not that: a burndown needs a scope somebody committed to and a date to burn it down to, and the other two read per-sprint snapshots of a board that takes none. Nothing will ever change it. Three permanent apologies across a third of the grid stop being a disclosure and become furniture, and they push the tiles that do measure this board below the fold.

The sprint-health chip goes with them. It is a sprint-board figure by definition — `CONTEXT.md` says so — and *"Sprint health: not scored"* in the most prominent chip on the page is the noise rather than the disclosure. It is emptied as well as hidden, because the previous board's score left in the markup and its working left in the tooltip attribute is a stale figure one class away from being read.

**What stops this being the silent cap this repository has shipped three times is that nothing is dropped without being named, twice.** The context bar says *"rolling window, so no burndown, pace or sprint health"* in the row that already answers *which data am I looking at* — the same place and the same shape as the rollup's own note. The tile picker lists all three with the reason for each and **disables** them, rather than leaving them merely unticked: a checkbox that can be ticked and does nothing is worse than one that says why it cannot be. Tiles the reader turned off and tiles this board cannot support are counted separately, because rolling them together would send someone looking for a checkbox that is not there.

**The reader's tile selection is masked, never edited.** Switching to a flow board and back restores the view exactly, including a custom set and a custom order, because `S.shown` is untouched and the board's applicability is applied at paint time.

**This is not a kanban preset, and the difference matters.** The two presets are *audience* cuts — executive and team — taken from the agent's own report templates, and a board-kind preset would be a second axis crossed with the first: four to keep in step with two templates. Which tiles a board can support is a property of the board, applied on top of whichever audience cut the reader chose, so the two compose rather than multiply.

Three refusal sentences written for these tiles in 1.16.8 are gone, because the tiles no longer show them and prose nobody can reach is one edit from disagreeing with the prose they do read. Each reason now has one home.

## 1.16.10

**Cycle time works inside a Jira tenant.** The Forge resolver has never sent `started`, because the first transition into an in-progress status can only be recognised under organisation config and a resolver deciding that would be a third implementation of the rule. The page printed *"no completed items with both a start and a resolved date"*, which was true and which emptied the waiting-versus-working chart across every install. For a sprint that is a stated degradation. For a board with no sprints it is the measure, so it stopped being acceptable.

The resolver now sends **`statusTransitions`** — every move the issue made between statuses, as `{"to": "In Review", "at": "2026-08-04"}`, with the names left undecided — and the page picks the earliest one its own config calls in-progress. The rule still has one implementation and it is still not in a resolver. What changed is that the raw material travels, and the reason it must is the difference from `workingDays`: the page can derive a working-day list from dates already on the wire, and there was nothing on the wire from which to derive a start. Leaving that out was a gap, not a silence. It costs one changelog expansion the resolver was already doing for `addedMidSprint`, so no extra call and no new scope.

**Earliest, not first, and that distinction is the bug this could have shipped.** Jira does not return a changelog in date order. Taking the first in-progress transition in list order rather than the earliest by date moves every start date later — on the demo data, three days later for every issue — which shortens every cycle time and raises flow efficiency. A smaller wait and a more efficient team, arrived at by arithmetic, with nothing on screen to suggest it. `jira_pull()` in the Python has always taken the minimum for this reason; the page now mirrors it, the fixtures are deliberately out of order, and `tests/e2e.py` fails on the sort alone.

The list is uncapped, deliberately: a truncated transition list silently moves a start date later, which is the same wrong number by a different route.

**`epicKey` reaches no consumer, and writing the guard for this is how it surfaced.** The check that the resolver invents no field the page does not read had an allow-list, and `epicKey` was on it under the assumption it feeds the epic filter. It does not. Nothing in `src/app.js` reads it and nothing in `agent/tools/` does either — `intake.py` groups by `epic`, the free-text name, which is in `NEVER_SEND` and so never reaches the calculator at all. So it travels from the resolver, through the calculator's allow-list, to nobody, and epic-based sizing cannot work over that route as things stand. Whether it should key on `epicKey` instead is a change to `intake.py` rather than to a test, so it is named and asserted rather than quietly dropped — the assertion fails the day something does read it.

Every exception in that allow-list is now checked to be genuinely referenced in the code that justifies it, which is the same failure the guard exists to catch, one level up.

## 1.16.9

**The risk register was reporting a clean bill of health over rules it never ran.** Three of its eight rules depend on something beyond the issues on screen — scope growth needs a sprint to have added work to, the over-commitment rule needs four sprints of history, flow efficiency needs closed items carrying both a start and a resolved date — and each of them fails the same silent way: the condition is false, the rule vanishes, and *"No risks triggered against the current filters"* stands over a shorter examination than the reader thinks they are getting.

On a flow board two of the three can never run at all. But this is deliberately **not** a flow-board fix: a sprint board with no start dates, or any dataset that carries no `started` field, has been quietly not running these for as long as the register has existed. It now names them — *"2 rules were not run against this selection: scope growth — this board runs no sprints…; the commitment against recent delivery — this board runs no sprints to commit in. Nothing is claimed either way about them."* — and when nothing triggered, the sentence becomes *"No risks triggered by the rules that could be run here."*

It is the same rule as the capped lists in 1.16.3 and the dropped health components in 1.16.2, one level further out. Something that bounds what it examined has to say what it left out, and a register is a list of findings whose length is its whole message.

**The executive summary was dropping sentences without saying so.** Its pace line appears only when there is a clock and its scope line only when something was added, so on a sprint with no dates the first silently vanished and on a flow board both do, permanently. A summary that drops a claim reads as a summary that had nothing to claim — the same failure as a truncated list reading as a complete one. It now names what it withheld and why, once for both when they share a cause.

**Two sentences in the register were still measuring against a sprint.** *"N open items have outlived a full sprint"* and *"the item should be moved out of the sprint"* — the first is the fourteen-day threshold called after something that does not exist on this board, the second an instruction that cannot be followed on one.

A board where every rule ran says nothing about rules not run, which is what makes the note a disclosure rather than decoration, and `tests/e2e.py` asserts both directions.

## 1.16.8

**Every tile that would have stated a sprint-shaped figure on a flow board now says what it in particular cannot show.** Step 4. Not a banner over the grid — [ADR 0010](docs/adr/0010-an-empty-selection-is-a-refusal.md) ruled that out for the reason it throws away everything the page still knows, and that reasoning does not change because the cause is a board rather than an empty selection.

**Delivered read 55%.** A share of completed work needs a scope somebody committed to. A window's membership is *open now, plus resolved inside it*, so the denominator is partly defined by being in the numerator: widen the window and the share rises, narrow it and it falls, and neither movement is the team. The count of finished work is real and stays, in the sub-label and the drill-down. The percentage is withheld.

**Scope added read `0 · 0% growth`.** `addedMidSprint` is *the sprint field changed after the sprint began*, so on a board with no sprints every issue carries false and the guard returns nought. A zero there is the claim that nothing was added, about a period that does not exist. Both of those figures are what the tiles print again the moment the guard is removed, which is what the tests assert against.

**The executive summary states counts and withholds the share.** *"12 of 22 items are done (55%)"* has the same broken denominator; *"12 items were finished in this window and 10 are still open"* is honest, and is the more useful sentence for a board whose reader wants to know how much is in flight.

**Four tiles were naming a cause that would send a reader to fix the wrong thing.** The burndown printed *"No burndown series in the dataset"* — true of the bytes, and it invites a re-import that would not help, because a burndown plots a committed scope down to a date and this board commits to neither. The commitment-history chart and team load both asked for *"at least two sprints of history"*, which on a flow board is a request that can never be satisfied rather than a threshold that has not been met yet. Each now names the board, and each ends with the same *the evidence is absent, not noisy* clause the tools use.

**One tile was renamed rather than refused, and the distinction is the point.** *Likely to carry over* measures open work, which is measured on any board; only the label was sprint-shaped, because "carry over" names a boundary to carry over *into* and a flow board has none — work there does not roll forward, it continues. It reads **Still open**. Refusing a figure that is perfectly good would have been the same error in the other direction. For the same reason the ageing chart keeps its fourteen-day bands and its counts, and stops calling a fortnight a sprint: the measurement is identical and only the yardstick was named after something that does not exist here.

The risk register's unrun rules and the executive card's silently dropped sentences are the last of it, and are next.

## 1.16.7

**The page knows a window is not a clock.** Step 3, and the one that had to land before any real tenant saw a flow board. `contextWorkingDays()` derives a working-day list from any context carrying a start and an end — which is right for a sprint, right for a Forge sprint that arrives without one, and wrong for a window. Expanding a 30-day window gives twenty-two working days that are perfectly real and describe nothing, because nobody undertook to finish anything by the end of a rolling month.

Removing that guard in a mutation test is the whole argument for it: the page printed **Pace vs clock — −45 pp** for a board that had committed to nothing at all. Not an error, not a blank. A negative figure in percentage points, in the tile the dashboard was built to add, about a deadline nobody ever agreed to.

**Two guards, because one of them is two functions away from every reader.** The calendar is withheld in `contextWorkingDays()` *before* the sent list is consulted — a producer that shipped `workingDays` on a window would otherwise walk straight past the rule, and the figure would arrive looking like data rather than like a derivation. Neither transport sends one, and this no longer depends on that staying true. `derive()` then withholds `timeElapsed` at source as well, because `renderExec` reads `paceGap` directly and one place to be wrong is enough.

**Scope stability was the quiet one, and it failed upward.** `addedMidSprint` is *the sprint field changed after the sprint began*, and a board with no sprints has no such moment — so every issue in a window carries false, the divide-by-zero guard returns 0% growth, and the component read **100/100, "no mid-sprint additions"** for a board where the phrase has no referent. Left alone it kept the composite above its half-weight floor, and the header printed **Sprint health: Needs attention (63/100, 3 of 4 measures)** for a flow board. Exactly the shape [ADR 0009](docs/adr/0009-one-contract-two-transports.md) caught the resolver in when it defaulted the same field: not a silence, a claim that nothing was added.

With both measures dropped and named, what is left is 0.44 of the weight, and the score refuses whole. That is the answer rather than a gap — blockers and ageing work describe hygiene, not whether anything is going to land — and it is [ADR 0010](docs/adr/0010-an-empty-selection-is-a-refusal.md)'s existing rule reaching its fourth cause rather than a new mechanism.

**The fourth cause gets its own words, and only one set of them.** *"No sprint dates"* would have been the natural thing to reuse and it would have been a lie: a window has dates, they are in the picker beside the board's name, and a reader sent to find the missing ones would be looking for something plainly there. What is missing is the commitment. Both dropped measures have that same single cause, so the disclosure says it once — listing it twice, once for pace and once for scope, reads as two problems to fix, and it is one permanent fact about the board that no re-import will change.

**Three overlapping windows must never be rolled up.** A flow board is offered 14, 30 and 90 days of *itself*; the same issue is in all three. The rollup builder keys per project and board, so it would have built one — holding every issue three times, and every count on the page is a count of the issues in the selection. A board's throughput would have tripled. There is no honest rollup to build instead: "all three windows" is not a longer period, it is one period asked about three times, and the 90-day window already is the wide view.

The picker's third dropdown says **Window** rather than **Sprint** when that is what it lists. The remaining tiles — the burndown, Delivered %, the *Scope added* KPI, the executive card's dropped sentences and the risk register's unrun rules — still say sprint things on a flow board, and are the next step.

## 1.16.6

**A board that runs no sprints is offered something for the first time.** It was detected and declined: `sprintsFor()` caught Jira's 400, the footer counted it as *"N without sprints and not offered"*, and the picker left it out. It now gets three windows — 14, 30 and 90 days — and `context` resolves one into that board's issues over both transports. Step 2 of the flow-board plan, and offering and loading landed together on purpose: a picker entry whose id 404s is worse than a board that is honestly not offered.

**One membership, two ways of reaching a board.** The resolver fetches through `/board/{id}/issue`, which returns what is on the board now — the wrong question for a closed sprint and exactly the right one for a flow board, where there is no historical membership to recover. The loopback goes through the board's own saved filter, because its issues come back through `jira_pull()`, which owns the field mapping and the `started` derivation, and reaching a different endpoint would have meant a second copy of that mapping. How each transport finds the board is its own business; **which issues count is not**, so the membership predicate is one pure function mirrored in both languages and compared string for string.

That predicate reads `resolutiondate` for both halves rather than `resolution IS EMPTY`. It is the field the page reads as `resolved`, so Jira is asked exactly the question the page will answer from what comes back; `resolution` would be a third opinion about what "done" means, arriving by neither the status category nor the organisation config.

**Its upper bound is the day after the window ends, and that is not an off-by-one.** Jira compares a bare date against midnight, so `resolutiondate <= "2026-08-24"` drops everything finished during the window's last day. The symptom would have been a throughput series quietly missing its most recent day — a number, computed, slightly wrong, with nothing on screen to suggest it. Pinned by a test that fails on the comparison operator alone.

**The footer's one count became two, because one of them stopped being true.** *"N without sprints and not offered"* covered two different boards: one with no sprint support, which is a flow board and is now offered windows, and one that has sprints and has never started one, which has nothing to offer and is a different sentence for its owner to act on. Left merged, the second would have been described as the first the moment windows existed. That line is the only thing standing between a picker quietly missing a board and a project that genuinely does not have one, so it moved into `forge/src/jira.js` where a test can read it — a label only a deploy can check is a label nobody checks.

**The window's length is in the id; its dates are not.** `SFT/2/win:30d` means the same thing whenever it is asked, so a picker built at 23:59 and a context loaded at 00:01 agree about which context is meant and differ only in the dates the second one resolves. An id carrying the dates would have gone stale overnight and come back as "unknown context".

**A window still carries no working-day list, and its burndown is still empty.** Both are deliberate and both are only half-honoured until the page catches up: the loopback sends `workingDays: []` for a window and builds no burndown series, and `contextWorkingDays()` in `src/app.js` must still learn not to derive a list from a window's dates. Until it does, a window's dates would become a clock. That is the next step and nothing offers a window to the page before it lands.

[ADR 0009](docs/adr/0009-one-contract-two-transports.md) is corrected rather than left to age. It said this app issues no JQL of its own, and it now issues some. The claim that mattered is unchanged and is stated exactly: no text from the page reaches Jira, because the only caller input is a context id and `parseContextId` refuses anything but a canonical token naming one of the three offered lengths — so the set of queries this app can be made to issue is three date pairs per board, each built from the resolver's own clock.

## 1.16.5

**The two transports now agree what a window is, before either one offers a board a window.** Step 1 of the flow-board plan and deliberately nothing more: a flow board's context id, the `kind` that travels with every context, and a window entry built independently by `forge/src/jira.js` and `scripts/serve_live.py`. No board is offered a window yet and nothing on the page renders differently, because a picker entry whose id 404s is worse than a board that is honestly not offered. Offering and loading land together, next.

A flow board's id is `SFT/2/win:30d` where a sprint board's is `SFT/2/8891`, and `kind` is `"sprint"` or `"window"` on every entry both transports send. It is carried rather than recovered by re-reading the id, per [ADR 0011](docs/adr/0011-a-kanban-context-is-a-window-not-a-clock.md): a discriminator a consumer re-derives is a second implementation of the same fact, and the page would be the one holding the wrong copy. `BundleBackend` defaults it to `sprint` for bundles written before flow boards existed, where an absent value has exactly one honest reading, and the fetcher writes it so new bundles describe themselves.

**Two producers agreeing about which keys exist and disagreeing about what is in them is the harder bug, so the parity check compares values.** The existing one compares field sets, and that is precisely the hole `workingDays` went missing through — a whole Forge install rendering different figures from the same sprint while the shapes matched. The new check builds the same window in both languages and compares key by key and value by value, across month ends, a year end and a leap year, which is where JavaScript's millisecond arithmetic and Python's `timedelta` would part company if they were going to. Drifting the loopback's window by one day fails four checks; dropping `kind` from it fails another.

**`win:030d` named the same context as `win:30d`.** Found by the parse table, not by reasoning: `Number('030')` is 30, so two strings resolved to one window. The page keys everything on this id and round-trips it back to the transport, and one context with two spellings is one context nobody can round-trip — the same shape as the id mismatch that made every sprint read *"unknown context"* on the first install. A window token is now checked by rebuilding it rather than by trusting the match, so only the canonical spelling parses.

Window lengths outside the offered 14, 30 and 90 days are refused rather than clamped or honoured. `win:99999d` would otherwise pull an unbounded slice of a board through an id no dropdown can produce, and a request the product cannot make is a request it should not answer.

## 1.16.4

**A dataset that stated no sprint dates was told how many items to commit to.** `recommend_commitment()` has always held the right answer for this — *"sprint length is unknown"* — and `forecast.build()` never let it out. The call read `len(meta.workingDays or working_days(startDate, endDate, cfg)) or 10`, and that trailing `or 10` substituted a ten-working-day sprint before the guard could fire. So a file with no calendar in it came back **"Next sprint: commit to 9 items at 85% confidence"**, with *"20,000 simulated sprints of 10 working days"* printed underneath as its own basis.

Ten is the working length of the default fortnight, which is precisely what made it dangerous. Had it been 7 or 30 somebody would have queried it years ago; a plausible sprint length, stated in the basis line, reads as a fact the tool went and looked up. This is the class of failure this repository keeps finding — not a crash, a confident number computed against something nobody supplied — and it made a refusal that exists in the source unreachable from the only caller that matters.

The fallback is gone rather than improved. Reaching for `orgConfig.sprintLengthDays` instead was available and is the same bug wearing the config's clothes: `from_dataset()` merges the defaults, so by the time the figure arrives a stated 14 and an inherited 14 are indistinguishable, and a number nobody chose would go back out under the authority of one they did. `tests/test_agent.py` pins both directions — a dateless dataset refuses and carries no `recommended`, no `commit_at`, no `sprint_working_days` and no basis line to quote, while a dataset that does state its calendar still gets a figure sized against the length it actually stated. A fix that refused everything would pass the first three checks alone.

**Decided what the product offers a board that runs no sprints.** They are detected today and then declined — `sprintsFor()` catches Jira's 400, the picker counts them as *"N without sprints and not offered"*, and there the matter has rested. [ADR 0011](docs/adr/0011-a-kanban-context-is-a-window-not-a-clock.md) settles what they are offered instead: a **window**, a rolling stretch of calendar days holding the issues open at the as-of date plus those resolved inside it. It bounds the selection, it round-trips through an id, and it carries **no working-day list**.

That refusal to supply a calendar is the whole decision, and it came out of code that already does it. `contextWorkingDays()` withholds the day list from a rollup on purpose, because a date range spanning nineteen sprints is perfectly real and describes nothing — *how far through nineteen sprints are we* is not a pace. A window is that same argument one step further out. Give it its twenty-two working days and the KPI strip prints **Pace vs clock: −18 pp** for a team that never committed to finishing anything by the end of it. So a window is not a new mechanism; it is a second caller of [ADR 0010](docs/adr/0010-an-empty-selection-is-a-refusal.md)'s drop-and-name rule, and the work is to give it the right sentence.

Three consequences are worth stating before anyone builds against them. Sprint health **refuses whole** on such a board — delivery pace and scope stability both need the clock, and what remains falls below the half-weight floor at 0.44, which is the honest answer rather than a gap, because blockers and ageing describe hygiene rather than whether anything will land. **Delivered %** refuses too, and that one is not about the clock: a window's membership is partly defined by *being done*, so the share would rise as the window widened. And the KPI strip does **not** go as one the way it does over an empty selection — five of the eight are genuinely measured there, and suppressing them would be its own dishonesty.

`CONTEXT.md` takes the vocabulary first, per the standing rule that naming precedes renaming: *sprint board* and *flow board*, *sprint* and *window*, and *period* for the sentences true of both. `docs/kanban-boards.md` names every tile and every KPI as keeping, refusing or replaced, sets out the position on `started` over the Forge transport — the resolver sends raw status transitions and the page decides what they mean, as it already does for `statusCategory` — and records what is deliberately not in this pass. No renderer has changed yet.

## 1.16.2

**Reconciled with the per-site calendar work, which landed on `main` in parallel.** The two solve the same gap from opposite ends and they compose: the resolver sends the site's own config, and the page derives the day list under it. Neither now needs the other's half. Two things came out of reading them together.

The comment in `forge/src/jira.js` said `workingDays` was withheld because resolving organisation config in a resolver would be a fourth opinion arriving by a fourth route. That stopped being true the moment the resolver started resolving that config, and it plainly could compute the list now. It still must not, for the reason that outlasts the other: expanding a date range into working days is a *rule*, the rule already has two implementations kept in step by a test, and a third in a resolver is a third thing to keep in step in the one place nobody can run that test against a customer's tenant.

And the hole this ADR named in ADR 0009's parity check is closed rather than only noted. That check fed the bridge the loopback's own bodies, so any field the resolver omits was invisible to it — which is exactly how `workingDays` went missing across a whole install. `tests/e2e.py` now feeds it a body shaped the way the resolver really shapes one, with `workingDays`, `statusCategory` and `contextId` stripped, and requires the same footer, the same KPI strip and the same context list anyway. Removing the derivation fails it with *Pace vs clock — no sprint dates*, which is the symptom as it actually appeared. `started` is deliberately left in place: the resolver omits it too, but that absence is a stated degradation the page prints, not something it makes good.

**A missing calendar was scored as bad delivery.** Sprint health is built from four weighted measures, and Delivery pace carries the largest weight of the four — 34%, and the only one that looks forward. Over a sprint whose dates were not in the data it scored **0/100**, which took the sample sprint from 52 and *Needs attention* to 22 and **Off track**. A zero is a finding. "We do not know when this sprint runs" is not a finding about delivery, and it should not be able to change the colour of the chip. A component that could not be measured now leaves the composition and is named, and the ones that remain are re-weighted to sum to one.

**Most of those calendars were not missing.** `forge/src/jira.js` sends no `workingDays`, deliberately — which days are worked is organisation config, and resolving it in a resolver would be a fourth opinion arriving by a fourth route. But the page holds that config and already derives `statusCategory` from it for exactly that reason, so it derives the day list too, from the sprint's own start and end dates. Until it did, **every sprint in a Forge tenant lost the largest component of its health score**, *Pace vs clock* read `—` across the entire install, and the two transports rendered different figures from the same sprint — the thing [ADR 0009](docs/adr/0009-one-contract-two-transports.md) exists to prevent, and invisible to its parity test, because that test feeds the bridge the loopback's own bodies. A rollup keeps its empty list: its dates span every sprint in it, so a derived list would be perfectly real and would describe nothing.

**Read in story points, an unestimated dataset scored itself with two of the four measures broken in opposite directions.** Pace read 0/100 with a calendar that was present and correct, because `totalU` was zero; scope stability read **100/100 — "no mid-sprint additions"** out of the same nothing, because zero added out of zero total is 0% growth. Half the method, one component flattering and one punishing, and a number at the end of it. Below half the weight the score now refuses outright and says which measure the data does not carry, because what survives — blockers and ageing work — describes hygiene rather than whether the sprint will land.

**The disclosure was naming the wrong cause.** All three situations printed *"no sprint calendar"*: the sprint with no dates, the rollup that has dates and no single clock, and the points view whose calendar was fine. That tooltip exists so a reader can argue with the method, and one that names the wrong cause sends them to fix the wrong thing. There are three causes and there are now three sentences, in the tooltip and in the KPI tile's sub-label.

**The chip says when it is a partial score.** A figure built from three of four measures is a different quantity from one built from four, so it reads `(33/100, 3 of 4 measures)` and the disclosure prints the weights that actually multiplied — 33%, not the nominal 22%. Same rule as anywhere else here: a composition that bounds itself has to say what it dropped. `tests/e2e.py` asserts the printed weights sum to 100, which is what catches a re-weighting that silently does not.

[ADR 0010](docs/adr/0010-an-empty-selection-is-a-refusal.md) carries both halves now — the empty selection from 1.16.1, and the unmeasured component here. They are the same decision at two granularities: unmeasured is not zero.

## 1.16.1

**The dashboard scored an empty sprint 66 out of 100.** Open the page over a dataset with no issues in it and the header printed *"Sprint health: Needs attention (66/100)"* in an amber chip. Nothing had been measured. Every component of the score is a share of the selected issues, and the guards that keep each one off a divide-by-zero — `Math.max(items.length, 1)`, `? … : 0` — all resolve to good news: no blockers among nothing, no ageing work among nothing, no scope growth on nothing. Delivery pace contributed its neutral zero, the four weights summed, and out came a figure that looks exactly like the output of a calculation.

Sixty-six is the worst number it could have landed on. Zero would have looked broken and a hundred absurd; 66/100 looks computed, and it arrives in a band with a verdict attached.

**It is the state the Forge build opens in.** `forge/seed.json` carries no issues deliberately — 1.16.0 stopped shipping a demo company's sprints into a customer's Jira — so the app renders empty until the bridge answers, and stays empty for good if the bridge fails. For a customer opening the app for the first time inside their own tenant this may be the only state they ever see, and it was telling them their sprint needed attention. The same arithmetic is reachable with no Forge involved: the score is computed over the *filtered* items, so a search box matching nothing produces it too.

**Zero issues is now a refusal, and it was never only the health score.** The executive card opened *"0 of 0 items are done (0%)"*. The KPI strip printed eight tiles of zeros, four of them shares with an empty denominator. The ageing chart printed *"Nothing open has outlived a sprint. That is the healthy state."* The value card printed a `$0` hero over *"0 of the 0 completed items"*. The risk register reported *"No risks triggered against the current filters"* — a finding, over nothing examined. All six now say what the forecast tile and the flow-time chart have always said in this situation: what is missing, and that it is missing rather than thin. [ADR 0010](docs/adr/0010-an-empty-selection-is-a-refusal.md) records where the line sits, because it is not "hide everything at zero" — counts of an empty set that are honestly nil keep their nil, and *"Nothing open has outlived a sprint"* is a true and useful sentence when there are issues and none of them are open. It is only false when there was never anything to age.

**The grid is no longer faded over an empty context.** It used to drop to 0.45 opacity, which was the right instinct reached through the one channel that cannot carry a reason — and once the tiles explain themselves in words, fading them puts the only text on the page below the AA contrast floor. The fade is gone and `tests/a11y.py` now renders the empty selection in both themes, which is a state the sample data never reaches and no check had ever visited.

**The test sweeps for digits, not for wording.** `tests/e2e.py` drives the shipped page into the empty state twice — once with the Forge seed, once by filtering every issue out of a real dataset — and asserts that six named elements contain no numeral at all, that each refusal still ends with *the evidence is absent, not noisy* untrimmed, and that the score comes back the moment there are issues to score. A future change that reinstates a figure fails on the digit sweep whether or not it kept these sentences, and an over-eager fix that suppresses the score permanently fails on the other half.

## 1.16.0

**The dashboard inside Forge shows the customer's own Jira, not a demo company's.** Deployed, installed and observed on a real site: the picker offers that site's boards and sprints and the page renders its issues. It rendered before this — fully styled, with charts — but every number on it belonged to Highpeak Commerce, because the page reaches live mode over a same-origin `api/*` and a Forge Custom UI iframe has no such origin. It does now, and the thing that made it possible is a seam rather than a feature. [ADR 0009](docs/adr/0009-one-contract-two-transports.md) records it.

**One contract, two transports.** The page asks four questions by route name and gets `{ok, status, body}` back. Over `http(s)` that is the same-origin GET `scripts/serve_live.py` already answered; inside the iframe it is an `invoke()` that an adapter left on the window before the page loaded. The **bodies are the contract** — defined by `serve_live.py`, returned unchanged by the Forge resolvers — and the status is transport-level, because a 404 for a sprint this site does not have and a failure to answer at all are different things and the page says different words for each. On `file://` there is no transport, nothing is asked, and an emailed copy still produces a silent console.

**`src/app.js` does not know what Forge is, and the suite now insists on it.** It imports nothing, contains no `@forge/*` reference, and the root `package.json` still has no dependencies. The adapter is `forge/bridge/bridge.js`, bundled separately and linked only into the split build — and it has to be a *classic* script placed ahead of `app.js`, because `app.js` decides at load which transport it has and an ES module is deferred. An adapter that arrives afterwards is an adapter that never ran, and the symptom is a page that silently believes it is offline, which looks exactly like a broken resolver.

**Found by loading the real bundle, after the tests using a stub had all gone green: the adapter was never installing itself.** `@forge/bridge` connects to its host as a side effect of being loaded, and outside a Forge iframe that throws. An ES `import` is evaluated before any of the adapter's own code runs, so the throw aborted the file before it reached the assignment — the page fell back to the same-origin fetch with nothing but an uncaught error in the console to say why. Outside Forge that fallback is the right answer and it hid the fault completely; inside a real iframe the same throw would have left the dashboard looking merely offline, which is the failure this whole seam is meant to make impossible. It is CommonJS now, required inside a `try`, so the failure is caught and named and no transport is installed rather than a broken one. `tests/e2e.py` loads the bundled adapter rather than a stub and asserts all three: no uncaught error, a console line saying why, and a page that falls back instead of believing it is connected.

**Then the first real install came up blank, and the app had nothing to say about it.** Two separate faults, both of my making, and both the same shape.

`sprintsFor` caught *every* error from the sprint endpoint and reported it as "this board has no sprints". Jira does answer 400 for a kanban board, and skipping that is right — but a 403 from a scope that had not been consented to came back the same way, so the picker came up empty and read as a project with nothing in it. It distinguishes the two now: a 400 is a fact about the board, anything else is a failure and travels.

And a resolver that fails rejects `invoke()`, which the page was treating exactly as it treats a dead loopback server — silently, because over loopback nothing running is the normal case. Over the bridge it is not: something answered, and it said no. So the resolvers catch, and answer with Jira's own status and a sentence; `probeLive` reads that sentence instead of discarding it; and the context bar — the "which data am I looking at" row, where a reader is already looking — shows **NO DATA** and the reason, rather than the page being blank and the footer carrying the explanation nobody scrolls to.

**And the blank install was two Jira endpoints disagreeing about one board.** The context id is built from `board.location`, `contexts` reads boards from the list endpoint, and `context` re-reads one board on its own — and the two responses do not always describe `location` the same way. An id built from a response carrying `projectKey` was then compared against one built from a response without it, stopped matching, and every sprint came back as an unknown context. The id now falls back to the project key Forge's own module context supplies, which is the same answer both times, and the integrity check — this page may read only the boards of the project it is displayed in — is made against that module context rather than against a second Jira response. It was the right check made against the wrong authority.

**"Server returned 404" named none of the four things it meant.** The `context` resolver's refusals now say which: the id is not in project/board/sprint form (which is what a sprint that came with the file looks like), that board is not on this site, that board has no such sprint, or that board belongs to a different project than the id claims. Four situations, four fixes, and the alert quotes the sentence verbatim.

**The two transports are compared rather than assumed to agree.** `forge/src/jira.js` holds the Forge half as pure functions of a Jira response — no SDK, no network — precisely so a test can run it. `tests/test_service.py` drives it over fixtures and compares the envelopes, field for field, against what a running `serve_live.py` really puts on the wire. `tests/e2e.py` checks the other end: the same page, over both transports, fed the same bodies, must render the same footer, the same KPI strip, the same context list and the same issue count. Writing that test found four genuine mismatches before anything was deployed.

**A field defaulting to false was going to be a confidently wrong number, and it is the one thing the resolver computes.** `addedMidSprint` needs no organisation config — it is *the sprint field changed after the sprint began* — and leaving it out is not a silence. It is the claim that nothing was added: the health score reads it as full marks for scope stability, and nothing on the page says it was never measured. The resolver expands the changelog and reads it. What it does *not* send is deliberate and written down beside each one: no `statusCategory`, because which statuses mean done is config the page already holds; no `started`, because recognising an "In Progress" transition needs that same config, and the page prints *"no completed items with both a start and a resolved date"*, which is true, rather than a flow efficiency built on a rule a resolver invented; no burndown series, because that is Python and Python is not running here, and the page says so where the chart would be.

**The Forge build is seeded empty.** It used to carry the demo dataset, so the first thing a customer saw was a fictional company's 22 issues inside their own Jira. `forge/seed.json` carries none, the page holds one placeholder context until the bridge answers, and then opens on the site's newest sprint. A file built with no data of its own adopting the connection's is a general rule, not a Forge one — the same thing happens over loopback.

**Three scopes, and the first is one this app removed rather than granted a fortnight ago.** The connection check dropped a `boards` resolver instead of asking for `read:project:jira`, on the grounds that the scope existed purely to make a diagnostic more convenient, and the note it left said that if the real context picker ever needed to enumerate boards, this was the price and it was a decision to take on its own merits. This is that moment: the picker offers the boards of the project the page is open in, and the alternative is a product page that opens empty and asks an end user to type a numeric board id. `read:sprint:jira-software` and `read:jql:jira` are what `forge lint` demands for the one call that reads a sprint's issues; the JQL one looks broader than the rest and is worth understanding rather than waving through — that agile endpoint is JQL-backed underneath, and this app issues no JQL of its own.

**A check that forced a false word into a file has been replaced by one tied to the code.** `tests/test_service.py` asserted that `manifest.yml` still described itself as a scaffold, so a manifest that quietly looked finished could not be deployed. That stopped being true the moment the app was registered and reading a tenant's boards. What is still unfinished is nameable instead: the calculator has no host, `remotes[0].baseUrl` says `.invalid`, and the forecast resolvers answer with a refusal saying exactly that. The two are asserted as a biconditional, because both directions are a bug — a real `baseUrl` with the refusal still in place is a forecast tile that stays dark for no reason anybody can see.

**The connection check was meant to be deleted here and has been kept.** It is the only thing that shows the outbound payload for a single issue, and it now names which field this site calls story points — a confirmation rather than a diagnosis, since that is resolved by name now.

**A Forge tenant is measured under its own calendar now, not this tool's.** Every install was reported under the defaults — Monday to Friday, no holidays, fourteen-day sprints, and a fixed idea of the word "done" — because the organisation config travels inside a dataset and a Forge install has no dataset. A site with a *Signed off* column and no *Done* column read every sprint as 0% complete. That is the exact bug `orgconfig.py` was written for, reintroduced by a route with nowhere to read a config from.

**Which statuses mean done comes from Jira, because Jira knows.** Every status on a site carries a category its admins assigned, and `orgconfig.py` already trusts that as the fallback inside `category()` — *"a statement by the site rather than a guess here"*. With no config file above it, it is the primary source, and it is better than any list this project could ship: the *Signed off* site is right without being asked. The resolver is the producer on this route, so it resolves once and writes the answer into every response, exactly as the fetcher does.

**The working week, the holidays and the sprint length are stated on the project.** Jira has no notion of any of them, so a site sets an `orgConfig` property on its project — read with the scope the board picker already needed, and never written: this app asks for no scope that would let it. What the property does not state keeps what Jira said, then the documented defaults. And when there is no property at all the connection label says so, in the line the page prints in its footer, because a five-day week nobody chose reads exactly like one somebody did.

**A property that is not usable stops the request rather than being half applied.** The same refusal `load()` makes about a bad file, and for the same reason: a typo in `workingWeek` that quietly reverted to a five-day week would move every forecast in the product with nothing on screen saying so. That means a second validator, in JavaScript, which is the kind of duplication this repository normally refuses — so it is held the way the other one is. `tests/fixtures/org-configs.json` holds nineteen configs, thirteen of them unusable, and `tests/test_service.py` runs every one through both the resolver and `orgconfig.validate` and asserts the two verdicts match. Neither side can be handed an easier set than the other, and breaking either is a failing test rather than a divergence found in a customer's tenant.

**Story points are read from whichever field a site calls them, not from a hardcoded id.** The resolver assumed `customfield_10016`, which is the common one and is wrong everywhere else: every issue on such a site read as zero points, the burndown flattened in points mode, and nothing said why. It is discovered through `/rest/api/3/field` by display name now — the same three names and the same first-match traversal `scripts/fetch_delivery_data.py` uses, because two producers picking different fields would report two velocities for one board, and a test compares the two lists across the two languages. It turned out to need no new scope, which is what moved it from a decision to a patch.

**A site with no story-point field reports `null`, never `0`.** An estimate nobody recorded and an estimate nobody could read are different facts about a sprint, and only one belongs in a burndown. The same goes for a text field pointed at that slot: coercing "M" to zero would put a made-up figure on the chart. Where there is no field the connection label says so, and the page prints that line in its footer.

Not closed: the calculator is still not hosted, so the forecast and ask-sequencing tiles refuse and name that reason rather than showing a figure.

## 1.15.1

The three things the Forge work left unfinished now have runbooks — and two of them turned out to be partly closable rather than only documentable. [docs/forge-deployment.md](docs/forge-deployment.md) is the guide.

**The calculator's auth is a seam now, and the empty half fails closed.** `SERVICE_AUTH` selects between `shared-secret`, which is implemented and tested, and `forge-token`, which is not written yet and **refuses to start** rather than degrading to something weaker. An unknown mode refuses too. Both refuse every request as well as refusing to boot, so deleting the startup guard cannot quietly open the service — a calculator that came up unauthenticated would look healthy to everything watching it.

The Forge verifier is still not written, deliberately. Verifying RS256 needs a crypto library and a real token to test against, and neither exists here; shipping security code whose correctness nobody has observed is worse than an honest placeholder. What it has to check is written down instead — algorithm pinning, `kid` lookup with JWKS caching and rotation, `exp`/`nbf`, `aud`, `iss`, and actually using the tenant claim — along with the eleven forgery cases the tests must reject, including the `alg: none` and HMAC-signed-with-the-public-key confusions. The five facts that must be confirmed from Atlassian's current documentation are listed as facts to confirm, not guessed at.

**The Forge manifest is now checked against this repository on every push.** `forge lint` needs a CLI nobody here has, but it validates schema and would not check any of this: the manifest's scopes must match `SCOPES` in `jira_auth.py`, the egress rule must name a remote that is actually declared, no write or manage scope may appear, and no app id may be committed — `forge register` writes one, and committing it hands everyone who clones the repository a manifest aimed at somebody else's app.

**The container image is built and smoke-tested in CI.** A new job builds it, then asserts it refuses to start with no secret, runs as uid 10001, refuses an unauthenticated request, returns a real forecast for an authenticated one, refuses issue text with the right sentence, and does not log issue text.

**And a check that needs no Docker, because the Dockerfile is edited on machines that have none.** `tests/test_service.py` reconstructs the image's filesystem from the `COPY` lines and imports the service from it. The failure that catches is narrow and nasty: the Dockerfile stops copying a module the service imports, every other suite still passes because they run against a working tree where the file is present, and the container fails on its first request in production. It also asserts no dataset, config or credential file is baked in.

**The security suite flagged a literal secret in the new CI job, and was right again.** Second time in three releases. It is minted per run now. A scanner cannot tell a placeholder from a real credential, and a workflow that needs a hard-coded one teaches the habit.

Not closed, and not closable from here: registering the app, running `forge lint`, and building the image locally. All three need an account or a tool this machine does not have. Scheduled rebuilds for base-image CVEs are listed as a decision rather than a task — a scanner that fails the build on somebody else's feed needs a policy about what blocks a merge.


## 1.15.0

**If we ship on Forge, the forecast comes with us.** Forge runs Node and cannot execute `agent/tools/`, and the previous note in `forge/README.md` framed that as a choice between hosting the Python "anyway" and writing a second Monte Carlo in JavaScript. Measuring it settled the question rather differently, and [ADR 0008](docs/adr/0008-forge-calls-a-hosted-calculator.md) records it.

**The tools were already pure functions.** Every `open()` and `glob` in `metrics.py`, `forecast.py` and `intake.py` sits inside `main()`; the library entry points take a dict and return a dict. `service/app.py` is a second caller, not new logic — `serve_live.py` has been the first one since live mode shipped.

**A call is 16 KB and does not grow with the customer.** 16.2 KB for a 242-issue organisation and 16.3 KB for a 5,538-issue one, against 158 KB and 3.6 MB for the whole datasets, because a forecast needs one team's history rather than the organisation's. Compute is 0.25s and 0.74s respectively; `intake.sequence` is the slow one at 3.07s and the only call within an order of magnitude of a request timeout.

**No issue title has to leave Atlassian, and that is the finding the design rests on.** `forecast.build()` over a dataset stripped to `key, created, started, resolved, statusCategory, storyPoints, priority, dueDate, flagged, addedMidSprint` produces byte-identical figures. The only fields that differed were `summary` and `assignee`, echoed back inside `item_risk.items[]` for display — and the Forge app already holds those, so it re-attaches them by key after the call. Titles are the sensitive payload; it is why `data/dashboard-data.json` is git-ignored and most of what permission mirroring is about. `tests/test_service.py` asserts the projection rather than trusting the measurement to stay true.

**Free text is refused, not ignored.** A payload carrying `summary` gets a `400` saying the text does not belong here and was not stored. Accepting and dropping it quietly would make the service a place customer text arrives, which is the one thing the projection exists to prevent. The resolver asserts the same thing before sending, so it fails closed at both ends, and a test compares the two field lists across the two languages — the resolver deciding what leaves and the service deciding what is accepted must not drift.

**The service computes nothing and the suite proves it.** Its forecast output is compared byte for byte against `forecast.build()` called directly. A wrapper that computes one percentage is a second implementation, and the day it disagrees every number in the product becomes something a reader has to check rather than read. The rule that the agent never does arithmetic now says so about everything between the tools and a reader.

**It refuses to start without a shared secret.** An open calculator is free compute for whoever finds it, and holding no data is not the same as needing no authentication. `--insecure` exists for local development and says so on every request. Oversized payloads get the limit named and nothing calculated — a forecast over half a team's history looks exactly like a forecast over all of it. Tracebacks go to the operator, never into a response, because they carry field values.

**A refusal survives the trip.** Shortening a working week shortens the throughput sample, and a team that had just enough completion history under five days can fall under the threshold under four. The right answer there is *"too little completion history to sample from"*, not a thinner forecast, and the test pins that it reaches the caller with its sentence intact and its calendar named. Every response carries the calendar, because two forecasts of one board under different working weeks are different forecasts and the difference is otherwise invisible.

**The security suite caught a credential in the tests it did not like, and it was right.** The service tests had a literal bearer token; a scanner cannot tell that from a real one. It is generated per run now. A test that needs a hard-coded credential is a test teaching a bad habit.

**What is real and what is not.** The projection, the free-text assertion, the call and the re-attachment in `forge/src/index.js` are real and tested against the calculator. Forge itself has never run: no app registered, nothing deployed, and `manifest.yml` has not been through `forge lint`. The Forge-specific syntax needs checking against current Atlassian docs, particularly the `remotes` block and the invocation-token contract — the service authenticates with a bearer secret today, and the tenant-aware thing is the Atlassian-issued JWT.

**Costs, written down rather than discovered at listing time.** Egress forfeits the *Runs on Atlassian* badge, with no engineering answer — only the choice not to have two forecasts. Data residency becomes ours, pinned per region, which brings roadmap item 6 forward. And we would be operating a service, though a stateless sub-second one suits scale-to-zero.

Still not here, and still not automatable: registering the Atlassian app, and the Marketplace listing.


## 1.14.0

Phase 1 of the commercial roadmap — *make it connectable*. Two items: a Jira connection a customer can consent to, and the assumptions that are true of exactly one company.

**Jira connects over OAuth 2.0 (3LO).** `scripts/jira_auth.py` does the authorisation-code dance against a loopback listener, stores the grant, refreshes it, and resolves which granted site to query. The fetcher and the live server both use it: `--auth auto` prefers a stored grant and falls back to the API token, and **prints which one it used on every run** — the two see different sets of issues, and a file produced by the wrong one looks entirely legitimate.

The API-token path is not deprecated. It needs no app registration and is the right thing for pulling your own board. What it cannot be is a customer's connection: it carries the permissions of whoever generated it, cannot be scoped, and is revoked only by deleting it.

**A grant covering two sites is refused rather than resolved.** Silently picking the first is how a report about the wrong company gets produced, and it would look correct all the way to the meeting. Name one with `--jira-site` or `JIRA_SITE`.

**Scopes are `read:jira-work` and `read:jira-user`, and the suite now fails if a write scope appears.** An app that asks for write access to close a deal is an app whose consent screen makes the buyer's security reviewer stop and read.

**Which statuses mean done is configuration now, not code.** So are the working week, the holiday calendar and the sprint length — `config/organisation.json`, resolved by `agent/tools/orgconfig.py`. The heuristic that read "Done|Closed|Resolved" out of a status name is still there as a last resort, but a site with a *Signed off* column no longer reports every sprint as 0% complete.

**The config travels inside the dataset, and that is the load-bearing decision.** Whatever produces a file resolves the config once and writes it in as `orgConfig`. The page, `metrics.py`, `forecast.py`, `intake.py` and the live server all read it from there; none of them opens the config file. A config each consumer read separately would be a third opinion arriving by a different route, and the first symptom would be a facts pack and a dashboard reporting different flow efficiency for the same sprint — which shipped here once, as 25% against 22%, and was a units disagreement of exactly this shape.

The consequence is deliberate: an emailed copy carries the calendar it was built with. The numbers in it were computed under those rules.

**A status the config has never seen is named, not swallowed.** At the end of every fetch: *"1 status matched no rule in the config and were inferred: 'Awaiting sign-off'"*. This is the whole point of the feature. A site adds a column, no rule mentions it, those issues read as To Do, the burndown flattens, and the dashboard is confidently wrong with nothing on screen to say why. That is a churn-in-week-two bug and the customer never tells you which number they stopped believing.

**A bad config stops the run instead of falling back.** `workingWeek: ["mon", "funday"]` is refused by name, as is a status listed under both `done` and `inProgress`, a malformed holiday and a non-integer sprint length. A typo that quietly reverted to a five-day week would move every forecast in the product with nothing saying so.

**Holidays shorten working time only.** The Monte Carlo horizon, the sprint elapsed-percentage and the ideal burndown line all move; reported ages do not. An item raised 21 days ago is 21 days old whether or not the office was shut, and a holiday that shortened it would be the same lie of convenience as skipping weekends. Both halves are pinned by tests.

**A bug this found in the forecaster: it read `meta.workingDays` for one figure and recomputed the rest itself.** That field has carried an explicit list of working dates since it existed, and `metrics.py` has always honoured it. `forecast.py` honoured it in exactly one place — the next-sprint commitment, which used its length — while `throughput_samples`, `cycle_times`, `lead_times`, the percentile dates and the capacity horizon all built their own Monday-to-Friday span and ignored the list entirely. Nobody noticed because no producer had ever written a list that differed from Monday-to-Friday. The moment a holiday calendar could exist, one forecast output would have counted a sprint's working days differently from the four beside it, and all five would have been in the same JSON object. Same class as the 25%/22% bug, invisible in the same way. Everything now resolves through `orgconfig.py`.

**Adopting any of this changes no number.** A dataset with no `orgConfig` resolves to defaults that reproduce what was hard-coded before, and `tests/test_agent.py` asserts that spelling the defaults out leaves every forecast percentile identical.

**Two implementations, and a test that they agree.** `src/app.js` mirrors `orgconfig.py` because the browser cannot call Python. `tests/e2e.py` compares working days and status categories between them **under a config that is not the default** — a Sunday-to-Thursday week with two holidays and a custom status list — because two implementations of Monday-to-Friday agree by accident.

**The page says which calendar it used.** In the footer, in the same words `metrics.py` puts in the facts pack, so a reader comparing the two does not have to translate. When the live server's config differs from the one baked into the file, the server's wins — it computed the forecasts — and the footer says it was replaced rather than swapping it silently.

**The security suite stopped covering the credential path, and said so.** Its check was pinned to `os.environ.get("JIRA_TOKEN")` appearing in `serve_live.py`; that reading moved into the fetcher and the OAuth client, so the check would have passed while covering nothing. It now checks every script that can hold a credential, and adds six: the grant is git-ignored, created 0600 rather than widened afterwards, never printed, the redirect verifies `state`, the listener is loopback-only, and no write scope is requested.

**`forge/` is a scaffold and is marked as one.** Manifest, scopes and a resolver that returns refusals rather than numbers. It exists so the Forge-versus-Connect decision stays a decision: Forge runs Node and cannot call the Python tools, so taking that route means either hosting the Python anyway or writing a second Monte Carlo — and this project already refused the second implementation once, which is why the forecast tile shows an offline notice in an emailed file.

Not included, and not automatable from here: registering the Atlassian app and the Marketplace listing. Both need an Atlassian account and credentials that should not pass through anyone else's hands.


## 1.13.0

**The tiles can be put in your own order.** Each row of the **Tiles** popover has an up and a down arrow, and the order travels the way the tile selection already did: `?order=` in the URL, a `data-order` attribute on a saved copy, and nothing in browser storage — the file still has to survive being emailed. **Default order** puts it back.

**Arrows rather than drag and drop, and that is the feature rather than a shortcut.** Dragging is unusable from a keyboard, and this page is held to WCAG 2.2 AA. Two buttons per row are operable by anyone, and the accessibility suite now opens the popover — which nothing in it had ever done — and asserts a tile moves on `Enter` alone.

**The tiles move, not a CSS `order`.** Setting `order` in CSS moves the picture and leaves the tab order and the screen-reader reading order in the old sequence, so the page would read in an order nobody can see. `applyOrder()` re-appends the nodes instead, which also leaves charts, open table views and the forecast tile's fetched state untouched. `tests/e2e.py` compares DOM order against the chosen order on every move, so a later switch to CSS would fail rather than quietly reintroduce it.

**Focus survives the move, and the move is announced.** Reordering rebuilds the list, which destroys the button that was just pressed; without putting focus back it falls to the body, and inside a popover that reads as the popover having closed. When a tile reaches an end of the list its arrow is disabled and focus moves to the one it can still travel on. The tile that moved is somewhere down the page, usually behind the popover, so a live region says *"Team load moved to position 5 of 13"* — visibly as well as to a screen reader.

**Order and selection stay independent.** `?tiles=` says which tiles, `?order=` says in what sequence. Folding one into the other would mean un-ticking a tile silently reshuffled the page.

**A custom order can leave a row short, and the page says so rather than pretending otherwise.** Tiles keep their widths when they move; the twelve-column grid only fills exactly in orders that happen to add up. The default order does, and 1.12.5's check still holds it to that. The picker labels a custom order as custom; it does not refuse one.

An unreadable `?order=` fails the way `?tiles=` does. Unknown ids are dropped and any tile the list forgot is appended in its default position, so a truncated or hand-edited parameter yields the whole page in an odd sequence rather than a page missing tiles.

The popover went from 290px to 320px to fit a name beside two arrows, and it is anchored to the right edge — so the reflow check now measures it **open** at 320px as well as closed. Every check above it had measured it as `display:none`, which costs nothing and proves nothing.


## 1.12.5

**Two rows of the tile grid did not add up to 12, and the page had the holes to prove it.** The grid is twelve columns and every row is meant to fill them. The bottom band did not: *Release quality* at 4 columns beside *Team load* at 3 came to 7, so roughly 600x360px of empty page sat to the right of them at any desktop width. Both tiles are now 6, which is the whole fix at that size.

**Between 761 and 1180px it was worse, and for a subtler reason.** That breakpoint promoted every wide tile to full width and halved every narrow one — a span-7 going to 12 strands the span-5 it was paired with alone on a half-empty row. Four tiles were orphaned that way and the page ran a third taller than its content needed. It now halves everything instead of promoting anything, so the pairs stay pairs: 4557px of page becomes 3848px on the demo sprint, with no row left short.

**Cards stretch to their row rather than stopping where their content runs out.** *Releases & milestones* holds two releases and ended 128px above the bottom of the card beside it, and the gap read as a hole in the page rather than as a card with room in it. The contents stay top-aligned; only the box grows. Grid gaps and card padding came down slightly with it.

**The check is arithmetic, not a screenshot.** `tests/e2e.py` now sums the column span of every visible tile per row at 1500, 1100 and 700px and requires 12. Against the previous build it fails and names the rows — *rows [5] are [7]* at 1500, *rows [3, 9] are [6, 6]* at 1100 — which is how the second bug was found at all; nobody had looked at the page at that width.

The first version of that check read `grid-column-end`, which computes to `auto` when the span is written as `grid-column: span 7`. Every tile scored the fallback 12, so every two-tile row summed to 24 and the check could not have passed on any layout, correct or not. It reads `grid-column-start` now. A test that fails for a reason unrelated to the thing it is testing is worth as little as one that passes for the wrong reason.


## 1.12.4

**The theme button lied on a machine that prefers dark.** The opening theme comes from `prefers-color-scheme`, and that branch set the attribute directly instead of going through `setTheme()` — so on a dark-preferring machine the page opened dark under a button still reading *"Dark"*. The label names the theme pressing it switches **to**, and it is also the control's accessible name, so the one user who cannot see which theme is showing was told the opposite of what the control does. The preference branch now sets the label alongside the attribute; it still bypasses `render()`, which has no data to draw at that point in load.

The accessibility suite now opens a second page under an emulated dark preference and asserts the pair — attribute and label — on load and after a press. It fails against the previous build, which is why it is here.


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
