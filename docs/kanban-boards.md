# Boards without sprints

What the dashboard does for a **flow board** — a board that runs no sprints — and, tile by tile, what it says instead of the figures it cannot take. The decision behind it is [ADR 0011](adr/0011-a-kanban-context-is-a-window-not-a-clock.md); the vocabulary is in `CONTEXT.md`. This document is the implementation plan, and it describes work that has not been done yet. Nothing below ships until its row has a test.

---

## The shape of it

A flow board's context is a **window**: a rolling stretch of calendar days holding the issues open at the as-of date plus those resolved inside it. It has a start and an end. It has **no working-day list**, on purpose, and that is what stops eight figures on the page from measuring a team against a boundary it never agreed to.

The reader picks the window from the third dropdown, where a sprint would be — **Last 14 days**, **Last 30 days**, **Last 90 days**, with 30 the default. A fixed set rather than a free choice, for two reasons: two boards are comparable only if the question asked of them was the same, and a window nobody can name is a window nobody can reproduce. All three are calendar days, matching every other elapsed figure in the product.

```
sprint board:  PROJ/42/8891        kind: "sprint"
flow board:    PROJ/42/win:30d     kind: "window"
```

`kind` is sent by both transports and compared by `tests/test_service.py`. It is not inferred from the id — a discriminator recovered by regex is a second implementation of the same fact, and the page would be the one holding the wrong copy.

### Detection is already done

`sprintsFor()` in `forge/src/index.js` catches Jira's 400 for a board with no sprint support and returns `{skipped: 'does not use sprints'}`. Today those boards are counted and dropped: *"N without sprints and not offered"*. They become offered instead, with a window each. `JiraBackend.contexts()` in `scripts/serve_live.py` needs the same branch — today it enumerates `/board/{id}/sprint` and would return nothing at all.

The `contexts` resolver's 404 sentence — *"none of them uses sprints. This dashboard reports a sprint at a time, so there is nothing to show yet"* — stops being true and has to go.

---

## Every tile, and what it does

**Keeps** means the figure is measured and correct. **Refuses** means it prints a sentence naming why, ending in the same *the evidence is absent, not noisy* clause the tools use, and prints no digits. **Not shown** means the tile has no subject on this board at all and is left out of the grid, with the reason given in the tile picker and the fact of it in the context bar — see *Refusing in place, or not showing at all* below. **Replaced** means a different tile takes the slot — nothing does in this pass.

## Refusing in place, or not showing at all

Both, and the line between them is whether the condition can lift.

A tile refuses **in place** when the thing it needs might yet arrive: a sprint with no dates gets its dates, a points view gets its estimates, an empty selection gets issues. The refusal is addressed to a reader who can act on it, and it sits in the tile so they can see which figure is missing from where.

A tile is **not shown** when it has no subject on this board and never will. Three are: the burndown needs a scope somebody committed to and a date to burn it down to; the commitment-history chart and team load read per-sprint snapshots of a board that takes none. Three permanent apologies across a third of the grid are not a disclosure — they are furniture, and they push the tiles that do measure this board below the fold.

What stops that being a silent cap is that nothing is dropped without being named, in two places: the context bar says *"rolling window, so no burndown, pace or sprint health"* in the row that answers *which data am I looking at*, and the picker lists all three with the reason and disables them rather than leaving them merely unticked — a checkbox that can be ticked and does nothing is worse than one that says why it cannot be. The reader's own tile selection is never touched, so switching back to a sprint board restores the view intact.

The same reasoning took the sprint-health chip off a flow board — it is a sprint-board figure by definition, and *"Sprint health: not scored"* in the most prominent chip on the page is the noise rather than the disclosure. The chip is not empty now, though: it carries **Flow health** instead, which is the one place on this page where a tile is genuinely *replaced* rather than refused or hidden.

## Flow health

The same machine as sprint health — the drop-and-name rule, the re-weighting, the half-weight floor, the bands — over the measures a board without a commitment actually controls.

| Component | Weight | |
|---|---|---|
| Flow efficiency | 40% | The share of an item's life that was work rather than queue. Full marks at 40% of elapsed time; typical delivery data is around half that |
| Blockers | 30% | Unchanged from the sprint score — it describes the same thing on any board |
| Ageing work | 30% | Unchanged, and the fourteen-day threshold is stated in days rather than sprints |

Three components, not four dressed up as four. There is no honest fourth: work in progress has no target to be scored against without a limit somebody set, and cycle-time spread already has an implementation in `size_stability()` that a page-side copy would have to be kept in step with.

**Flow efficiency is load-bearing, not merely heavy, and the half-weight floor would not catch it.** Drop it and 60% of the weight survives — comfortably above the floor — but what is left is blockers and ageing work, which is hygiene. That is the same remainder the sprint score refuses to call health, and calling it *flow* health while the flow measure is the missing one would put the absent part in the name. So it refuses outright, names `started` as the thing that is missing rather than asking for more data, and points at `docs/data-format.md`.

The chip says which composite it is carrying. *Flow health* and *Sprint health* are different quantities on different evidence, and a chip that read the same for both would invite comparing two boards that were never measured the same way.

| Tile | On a flow board | The cause it names |
|---|---|---|
| `c-exec` What this period means | **Keeps, minus two sentences** | The pace sentence and the scope-growth sentence are dropped *and said*, not silently omitted |
| `c-kpis` Headline numbers | **Mixed — see below** | Per tile, in the sub-label |
| `c-burn` Burndown | **Not shown** | no committed scope — named in the picker |
| `c-dist` Where each person's work sits | **Keeps** | — |
| `c-flow` How long work takes, and what waits | **Keeps — and is the headline** | needs `started`; see below |
| `c-age` How long open work has been sitting | **Keeps, re-worded** | threshold stated in days, not sprints |
| `c-pred` Can we trust the forecast? | **Not shown** | no per-period history — named in the picker |
| `c-forecast` Monte Carlo forecast | **Keeps, minus `next_commitment` and the by-date question** | no cadence to size a commitment to; no end date to forecast against |
| `c-dora` Release quality & speed | **Keeps** | — |
| `c-load` Team load | **Not shown** | no per-period history — named in the picker |
| `c-value` Business value delivered | **Keeps** | — |
| `c-rel` Releases & milestones | **Keeps** | — |
| `c-risk` Risks and what to do about them | **Keeps, minus two rules** | the register names the rules it could not run |
| Sprint health (header chip) | **Replaced** by **Flow health** | built on flow efficiency; see below |

### The KPI strip

The strip does **not** go as one. It does over an empty selection, because there a mixed row invites the reader to trust the figures that still carry a number and none of them were measured. Here five of the eight are measured, and hiding them would be its own dishonesty. Each of the three that cannot be taken refuses in place, using the `paceUnknownShort` mechanism that already exists for exactly this.

| KPI | | |
|---|---|---|
| Delivered | **Refuses** | A window's membership is partly defined by *being done*, so the share would rise as the window widened. There is no scope here to be a share of |
| Pace vs clock | **Refuses** | this board does not use sprints, so there is no clock |
| Blocked | Keeps | |
| Top priority open | Keeps | |
| Scope added | **Refuses** | "mid-sprint" has no referent on this board |
| Likely to carry over | Keeps, **renamed** | The figure is open work and is fine; "carry over" names a boundary that does not exist. *Still open* |
| Past due date | Keeps | |
| Value closed | Keeps | |

### The health score refuses, and that is the answer

Delivery pace (0.34) and scope stability (0.22) both need the clock. Dropped under [ADR 0010](adr/0010-an-empty-selection-is-a-refusal.md)'s existing rule, blockers and ageing work survive with 0.44 of the weight — below the half-weight floor — so the whole score refuses. The existing sentence already carries the shape (*"built from four measures and only 2 of them could be taken here"*); it needs the flow-board cause added to the three that exist, and the same reasoning applies as the last time this went wrong: a disclosure that names the wrong cause sends the reader to fix the wrong thing.

This is worth stating plainly rather than treating as a gap. What is left after the two drops is blockers and ageing — hygiene, not whether anything is going to land. Calling that "health" on a board with no commitment is exactly the claim the remainder cannot carry.

### The two silent omissions to fix while we are here

Both are the same class of bug and neither is caused by this work; both become visible because of it.

`scopeAddedPct` guards to `0` when nothing was added, so the risk register's *"Scope grew after the sprint started"* rule simply never fires on a flow board. A register that reports "no risks triggered" over a rule it never ran is a finding over nothing examined — the same thing ADR 0010 found in the empty-selection register. The register names the rules it could not run.

`renderExec` drops its pace sentence whenever `paceGap` is null and its scope sentence whenever `addedU` is falsy. On a sprint with missing dates that is already a silent omission; on a flow board it is permanent. The card says which sentences it did not write.

---

## `started` over the Forge transport

Cycle time is a nicety for a team with a burndown and it is **the** measure for a team without one. `forge/src/jira.js` omits `started` today, and the page prints *"No completed items with both a start and a resolved date in this selection"* — which is true, and which on a flow board empties the one tile the board most needs.

**The resolver sends the raw status transitions; the page decides what they mean.** *(Done.)*

```
statusTransitions: [ { to: "In Progress", at: "2026-08-04" },
                     { to: "In Review",   at: "2026-08-07" }, … ]
```

The page takes the first whose `to` categorises as in-progress under the config it already holds, and uses it only when `started` is absent — precisely how it already treats `statusCategory` for a raw status name nobody resolved. One rule, one implementation, in the place that already owns it.

The alternative was for the resolver to compute `started` itself. It could: it now resolves the organisation config out of Jira's own status categories, and it already expands the changelog to read `addedMidSprint`, so there is no extra API call. It is refused for the reason recorded against `workingDays` in the same file — *the rule would then have three implementations*, `orgconfig.py`, its mirror in `src/app.js`, and a third in the one place nobody can run a test against a customer's tenant.

But the `workingDays` reasoning does not transfer whole, and the difference is why this needs a decision rather than a citation. `workingDays` can be left out because the page can *derive* it from `startDate` and `endDate`, which are already on the wire. Nothing on the wire lets the page derive `started`, so leaving it out is a real gap and not a silence. Sending the transitions closes the gap without adding the third implementation.

Costs, stated:

- A new optional field in `docs/data-format.md`. The Python fetcher does **not** emit it — it resolves `started` directly, because it is the producer of the whole dataset and the config travels inside the file it writes. `statusTransitions` is the raw form for a producer that is not allowed to decide.
- Payload. Status transitions only, `to` and date only, and **not capped** — a truncated transition list would silently move a start date later, which is a plausible wrong number in a field feeding cycle time. If a cap ever becomes necessary it is reported, per the no-silent-caps rule.
- It is not a flow-board feature. It fixes flow efficiency for every sprint in every Forge tenant too; a flow board is what makes it non-optional.

---

## What is not in this pass

The tile picker gains no kanban **preset**, and that is a different question from the one above. The two presets are *audience* cuts — executive and team — taken from the agent's own report templates, and a board-kind preset would be a second axis crossed with the first: four presets to keep in step with two templates. What a flow board does instead is narrower and needs no preset. Which tiles a board can support is a property of the board, applied on top of whichever audience cut the reader chose, so the two axes compose rather than multiply.

## The flow tiles

Four, and none of them needs a sprint or a window — every figure is a property of issues and dates, which is why they were available all along rather than something the schema had to grow. `agent/tools/metrics.py` computes each series under `flow` and the page draws the same one, held together by `tests/e2e.py` comparing the page's stated figures against the facts pack.

| Tile | What it is for |
|---|---|
| **How long finished work took** | Every closed item by the day it finished, against 50/85/95 percentile lines. The 85th is the sentence to take outward: *85% of what we finish, we finish within N days*. Outliers are clickable by name, which is what makes it checkable rather than assertable |
| **Work in progress, and how old it is** | Open work against those same lines. The only tile on the page describing work a stand-up can still change: an item above the 85th percentile has already outlived 85% of everything the board has finished, and it has not finished |
| **How much finishes each week** | The series the Monte Carlo samples, shown so the forecast can be checked rather than taken on trust. Quiet weeks stay in — a model that never samples a zero never predicts a stall |
| **Where the work has been sitting** | Cumulative flow. Middle band is work in progress, the gap between the top two lines is the queue |

They are **shown by default only on a flow board**, and offered on any board — a sprint team benefits from all four, and hiding a measure that works is the same error as showing one that does not. Ticking one on a sprint board puts the view into *custom*, which is what it is.

**The cumulative flow diagram has three bands, not one per column, and says so on the tile.** Nothing in a dataset records which column an issue sat in on a given day; the three bands are the status *categories*, derived from `created`, `started` and `resolved`. A per-column version needs the Forge resolver's `statusTransitions` from the Python fetcher too. A three-band chart presented as a full one is a different picture of the same board, so the limitation is printed rather than left to be discovered.

**Little's Law is reconciled under it, and no verdict is drawn.** Work in progress over throughput is how long the average item must be spending in progress; measured cycle time is how long the items that finished actually took. When they disagree by more than a factor of two the tile says so and gives both figures, because there are two honest readings — the open work really is sitting far longer than anything that has finished, or start dates are not recording when work began — and choosing between them would be a claim about a team built on whichever the reader assumed.

### What was considered and left out

- **Blocked time.** The measure everyone asks for, and `flagged` is a boolean with no history: the schema cannot say when an item was flagged. Not computable, rather than not wanted.
- **Flow distribution by work type.** Easy from `type`, and it implies a target mix nobody set. That is the family [ADR 0004](adr/0004-no-priority-score.md) exists to refuse.
- **WIP limits and control bands.** They need a limit somebody stated, and there is no config field for one.
- **A flow-efficiency trend line.** The waiting-versus-working chart already *is* the graph view, and a ratio of two noisy quantities plotted over time moves mostly with how accurately `started` was recorded — a data-quality artefact read as a delivery change.
- **Any per-person cut of ageing work in progress.** [ADR 0003](adr/0003-the-dashboard-does-not-measure-people.md).
- **A "what to pull next" ordering.** [ADR 0004](adr/0004-no-priority-score.md).

Forecasting inside Forge stays blocked on the hosted calculator either way ([ADR 0008](adr/0008-forge-calls-a-hosted-calculator.md)). Over loopback it works, and the forecaster itself needed no change — `forecast.build()` samples throughput over a rolling window of days and has never needed a sprint boundary. What did need changing was the *slice* around it, twice, and both were wrong numbers rather than failures:

- **`team_slice()` returns every context on the team, and a flow board's three windows are 14, 30 and 90 days of the same board.** Every issue was in the slice up to three times, so the throughput series counted three completions on the day one item finished and the 85th percentile came back two and a half times too early. Issues are de-duplicated by key: one issue is one item, however many contexts hold it. It is a no-op on a sprint board, where a team's sprints do not overlap.
- **A window's `endDate` is today, and it was being passed through as the forecast's default target.** *Will this land in time* was asked against an end that is always now and answered **0%** — a number a reader can quote, about a deadline nobody set. A window supplies no default target, the date control offers one instead of remembering one, and the capacity refusal says *"this period has no end date to forecast against"* rather than *"the target date has passed"*.

Both were reachable only over loopback, because the Forge forecast resolver still answers with the no-calculator refusal.

---

## The order to build it in

0. **`next_commitment`'s invented sprint length**, which is a live defect and not part of this work. `forecast.build()` passes `len(meta.workingDays or working_days(start, end, cfg)) or 10`, so a dataset stating no sprint dates gets a commitment recommendation sized against a ten-working-day sprint nobody chose — *"20,000 simulated sprints of 10 working days"*, printed as its own basis. `recommend_commitment()` already holds the correct refusal, *"sprint length is unknown"*, and the `or 10` makes it unreachable. A window would reach the same path with twenty-two. Fix it first so this work does not inherit it.
1. **Done.** `kind` and the window id, in `forge/src/jira.js`, `scripts/serve_live.py` and the fetcher, with the parity case in `tests/test_service.py`. The two producers build a window independently and are compared value by value, not field set by field set.
2. **Done.** Offering a window and loading one, together — a picker entry whose id 404s is worse than a board honestly not offered. `contexts` returns three windows for each flow board and `context` resolves one into that board's issues, over both transports: the resolver through `/board/{id}/issue`, the loopback through the board's own saved filter, both narrowed by the same membership predicate. The footer line separates *offered as rolling windows* from *has sprints and has never run one*, which were one count until windows existed.
3. **Done.** `contextWorkingDays()` returns `[]` for a window — checked *before* the sent list, so a producer that shipped one could not walk past the rule — and `derive()` withholds `timeElapsed` at source rather than relying on that one guard two functions away. Pace and scope stability are both dropped and named, which takes the composite below half its weight, so sprint health refuses whole. Overlapping windows are excluded from the rollup: the same issue is in all three, and rolling them up would have tripled every count on the page.
4. **Done.** The refusals, one tile at a time, each with the digit sweep the empty-selection tiles already have: the burndown, *Delivered*, *Scope added*, the commitment-history chart and team load. *Likely to carry over* was renamed rather than refused — the figure is open work and is measured either way; only the label named a boundary that does not exist. The ageing chart keeps its fourteen-day threshold and stops calling it a sprint.
5. **Done.** The register names every rule it could not run, and the summary names the sentences it did not write. Deliberately not flow-board-specific: a sprint board with no start date, or any dataset without `started`, has been quietly not running these for as long as the register has existed.
6. **Done.** `statusTransitions`, and the flow tile lighting up over the bridge. One loose end found while writing the guard for it: `epicKey` travels from the resolver through the calculator's allow-list to nobody — `intake.py` groups by `epic`, the free-text name, which is in `NEVER_SEND` and never reaches the calculator. Whether epic sizing should key on `epicKey` instead is a change to `intake.py`, so it is named and asserted rather than quietly dropped.
