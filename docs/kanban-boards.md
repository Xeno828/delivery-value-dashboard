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

The same reasoning takes the sprint-health chip off a flow board. It is a sprint-board figure by definition, and *"Sprint health: not scored"* in the most prominent chip on the page is the noise rather than the disclosure.

| Tile | On a flow board | The cause it names |
|---|---|---|
| `c-exec` What this period means | **Keeps, minus two sentences** | The pace sentence and the scope-growth sentence are dropped *and said*, not silently omitted |
| `c-kpis` Headline numbers | **Mixed — see below** | Per tile, in the sub-label |
| `c-burn` Burndown | **Not shown** | no committed scope — named in the picker |
| `c-dist` Where each person's work sits | **Keeps** | — |
| `c-flow` How long work takes, and what waits | **Keeps — and is the headline** | needs `started`; see below |
| `c-age` How long open work has been sitting | **Keeps, re-worded** | threshold stated in days, not sprints |
| `c-pred` Can we trust the forecast? | **Not shown** | no per-period history — named in the picker |
| `c-forecast` Monte Carlo forecast | **Keeps, minus `next_commitment`** | no cadence to size a commitment to |
| `c-dora` Release quality & speed | **Keeps** | — |
| `c-load` Team load | **Not shown** | no per-period history — named in the picker |
| `c-value` Business value delivered | **Keeps** | — |
| `c-rel` Releases & milestones | **Keeps** | — |
| `c-risk` Risks and what to do about them | **Keeps, minus two rules** | the register names the rules it could not run |
| Sprint health (header chip) | **Not shown** | a sprint-board figure; the context bar says so |

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

The flow tiles a team on a flow board actually wants — a cycle-time distribution with its percentiles, ageing work in progress, a cumulative flow diagram — are a second pass with their own vocabulary, their own tests and their own figures computed in `agent/tools/`, never in a renderer. Two constraints govern that pass before a line of it is written: an ageing-work-in-progress view invites a per-person cut, and [ADR 0003](adr/0003-the-dashboard-does-not-measure-people.md) forbids it; a "what should we pull next" ordering invites a priority score, and [ADR 0004](adr/0004-no-priority-score.md) forbids that.

Forecasting inside Forge stays blocked on the hosted calculator either way ([ADR 0008](adr/0008-forge-calls-a-hosted-calculator.md)). Over loopback it works today, and it works for a flow board unchanged — `forecast.build()` samples throughput over a rolling window of days and has never needed a sprint boundary.

---

## The order to build it in

0. **`next_commitment`'s invented sprint length**, which is a live defect and not part of this work. `forecast.build()` passes `len(meta.workingDays or working_days(start, end, cfg)) or 10`, so a dataset stating no sprint dates gets a commitment recommendation sized against a ten-working-day sprint nobody chose — *"20,000 simulated sprints of 10 working days"*, printed as its own basis. `recommend_commitment()` already holds the correct refusal, *"sprint length is unknown"*, and the `or 10` makes it unreachable. A window would reach the same path with twenty-two. Fix it first so this work does not inherit it.
1. **Done.** `kind` and the window id, in `forge/src/jira.js`, `scripts/serve_live.py` and the fetcher, with the parity case in `tests/test_service.py`. The two producers build a window independently and are compared value by value, not field set by field set.
2. **Done.** Offering a window and loading one, together — a picker entry whose id 404s is worse than a board honestly not offered. `contexts` returns three windows for each flow board and `context` resolves one into that board's issues, over both transports: the resolver through `/board/{id}/issue`, the loopback through the board's own saved filter, both narrowed by the same membership predicate. The footer line separates *offered as rolling windows* from *has sprints and has never run one*, which were one count until windows existed.
3. **Done.** `contextWorkingDays()` returns `[]` for a window — checked *before* the sent list, so a producer that shipped one could not walk past the rule — and `derive()` withholds `timeElapsed` at source rather than relying on that one guard two functions away. Pace and scope stability are both dropped and named, which takes the composite below half its weight, so sprint health refuses whole. Overlapping windows are excluded from the rollup: the same issue is in all three, and rolling them up would have tripled every count on the page.
4. **Done.** The refusals, one tile at a time, each with the digit sweep the empty-selection tiles already have: the burndown, *Delivered*, *Scope added*, the commitment-history chart and team load. *Likely to carry over* was renamed rather than refused — the figure is open work and is measured either way; only the label named a boundary that does not exist. The ageing chart keeps its fourteen-day threshold and stops calling it a sprint.
5. **Done.** The register names every rule it could not run, and the summary names the sentences it did not write. Deliberately not flow-board-specific: a sprint board with no start date, or any dataset without `started`, has been quietly not running these for as long as the register has existed.
6. **Done.** `statusTransitions`, and the flow tile lighting up over the bridge. One loose end found while writing the guard for it: `epicKey` travels from the resolver through the calculator's allow-list to nobody — `intake.py` groups by `epic`, the free-text name, which is in `NEVER_SEND` and never reaches the calculator. Whether epic sizing should key on `epicKey` instead is a change to `intake.py`, so it is named and asserted rather than quietly dropped.
