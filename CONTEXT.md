# Delivery Value Dashboard

The language of delivery measurement for a single team: what flowed, how long it waited, what it was worth, and what the evidence does and does not support saying about the future.

This glossary is opinionated on purpose. Several of the `_Avoid_` terms are not merely worse synonyms — they name concepts this project refuses to have (see `docs/adr/`).

## Language

### The work being measured

**Issue**:
One row of tracker data — the atomic unit everything else is derived from.
_Avoid_: Ticket, card, task, story (as a synonym; "story" is a `type` value, not the general term)

**Item**:
An issue counted as one, regardless of size. The default unit of volume everywhere, and the only unit a forecast uses.
_Avoid_: Unit of work

**Point**:
A story-point estimate carried on an issue. A display lens for whether scope growth mattered, never a forecasting input.
_Avoid_: Estimate (as a noun for size), effort

**Epic**:
A parent grouping of issues. Also the sample unit for sizing an ask, once it has stopped growing and is nearly complete — and, where one is declared a **candidate**, an ask itself.
_Avoid_: Initiative, feature (as a synonym)

**Board**:
The delivery unit a forecast is scoped to. Throughput, interruption rate and the t-shirt scale are all properties of one board and never transfer between boards. Every board is one of exactly two kinds, and which one it is decides what the page can say about it.
_Avoid_: Team (when the board is what's meant), squad

**Sprint board**:
A board that runs sprints. The only kind that has a committed scope and a clock, and therefore the only kind with a burndown, a pace and a sprint health score.
_Avoid_: Scrum board (Jira's name for one configuration of it; what matters here is only that sprints exist)

**Flow board**:
A board that runs no sprints, where work is pulled continuously. Detected rather than declared — Jira answers 400 for its sprint list — so the term covers any board whose sprints are absent, not just the one type Jira gives that name to.
_Avoid_: Kanban board (as the internal term; fine in copy addressed to a team that uses the word), continuous board, team without process

**Sprint**:
The bounded period a report covers on a sprint board. Both a bound and a clock: a fixed scope, with a start and an end that delivery can be measured against.
_Avoid_: Iteration, cycle (which means something else here)

**Window**:
The bounded period a report covers on a flow board — a rolling stretch of calendar days, holding the issues open at the as-of date plus those resolved inside it. A bound and **not** a clock: it deliberately carries no working-day list, because a team that never committed to finishing anything by its end cannot be behind it. Every figure that needs a clock is dropped and named rather than measured against the window.
_Avoid_: Rolling sprint, mini-sprint, period (unqualified), timebox (there is no box)

**Period**:
Whichever of the two a context is bounded by. The word to use when a sentence is true of both, so that no copy has to say "sprint" and mean either.
_Avoid_: Interval, span

**Context**:
One project + board + period — the slice of a bundle currently on screen. Its `kind` says which sort of period, and is sent rather than inferred from the shape of its id.
_Avoid_: View, scope (which means something else here). Note this is unrelated to "context" in the bounded-context sense used by `CONTEXT.md` and `docs/agents/domain.md`; when both meanings are in play, say **selected context** for this one.

**Bundle**:
Several contexts and their issues in one file, fetched up front so that switching is instant and offline.
_Avoid_: Dataset (too vague), export, cache

**Live mode**:
An optional local server the page discovers, allowing it to pull contexts the bundle does not contain. Not a connection to the tracker.
_Avoid_: Online mode, API mode, sync

### Flow and time

**Elapsed time**:
Time as a stakeholder experiences it, always in **calendar days**. An item raised 21 days ago is 21 days old.
_Avoid_: Business days, adjusted days

**Simulated time**:
Time inside a forecast, always in **working days**, because nothing completes on a Saturday. Never reported without its unit.
_Avoid_: Days (unqualified)

**Lead time**:
Elapsed time from an issue being created to being resolved — the whole wait, as the requester felt it.

**Cycle time**:
Elapsed time from an issue being started to being resolved — the part that was actively worked.

**Waiting**:
Lead time minus cycle time. On typical data this is most of the total, and it is the cheapest thing to fix.
_Avoid_: Idle time, dead time, blocked (which is a specific flag)

**Flow efficiency**:
Total cycle time over total lead time, across a set of completed issues. The share of the wait that was work. **40%** is the one threshold: below it the figure is worth saying, at or above it scores full marks in **Flow health**. Typical delivery data is around half that.
_Avoid_: Efficiency (unqualified), utilisation

**Ageing**:
How long an open issue has been alive, in calendar days.
_Avoid_: Staleness, rot

**Throughput**:
Items completed per working day, sampled across a trailing window. Zero days are part of the distribution, not gaps in it. Reported per **calendar week** where it is shown as a series, because a per-day chart on a board without a sprint boundary is mostly zeroes and reads as a team that keeps stopping.
_Avoid_: Velocity, capacity (which means something else here), productivity, output

**Cycle time percentile**:
What 50%, 85% or 95% of finished items came in under. The 85th is the figure to quote outward — a statement about the system, never a promise about one item.
_Avoid_: Average cycle time (a mean over a skewed distribution describes nothing), SLA, guarantee

**Cumulative flow**:
How many items sat in each status **category** on each day, stacked. Three bands and not one per column, because nothing in a dataset records which column an issue sat in on a given day. The limitation is printed on the tile.
_Avoid_: CFD as a first use (define it, then abbreviate), flow diagram (unqualified)

**Work in progress**:
Items started but unfinished at the end of a period. Half of team load, and derived from status alone.
_Avoid_: WIP as a first use (define it, then abbreviate), load (unqualified)

**Unplanned work**:
Items that arrived after planning. The other half of team load.
_Avoid_: Interrupts, ad-hoc work, BAU

**Scope growth**:
Work added to a sprint after it began, plotted as its own line so that "we were given more" stays distinguishable from "we were slow".
_Avoid_: Scope creep (it carries a verdict the data does not support)

**Interruption rate**:
Unplanned work as a share of all work taken on, measured per board and used to thin the throughput series in a forecast.
_Avoid_: Overhead, tax, drag

### What a report says

**Facts pack**:
The complete set of figures a report is permitted to state, computed once and quoted verbatim. Every number in every report comes from one.
_Avoid_: Summary, stats, metrics blob

**Snapshot**:
A facts pack stored with its date, so that a later report can say what changed.
_Avoid_: Archive, backup

**Diff**:
The change between two snapshots, with the direction that counts as good stated for each figure.
_Avoid_: Delta, trend (which implies more than two points)

**Durable series**:
The per-sprint rows the product recorded at the moment each sprint closed, together with when they were observed and under which status configuration. Not a cache: Jira stays authoritative for everything it can still answer, and a recorded row exists because four specific things can make a later re-derivation disagree with what was true. ADR 0015.
_Avoid_: History store, cache, archive (all three imply a copy of Jira, which is what it is not)

**Recorded row**:
A sprint's row written at the moment that sprint closed, when every figure in it was still observable.
_Avoid_: Real row, true row (they imply a reconstruction is false, and it is not — it is narrower)

**Reconstructed row**:
A sprint's row re-derived from Jira after the fact, for a sprint that closed before the app was there to record it. Not a worse row — on a site where nothing has been deleted, no sprint membership stripped and no status recategorised, it is the same row. It is a row with a **different warrant**, and a chart carrying both kinds says which are which, because a reader comparing this quarter against last year should see where the warrant changes. ADR 0015 lists the four things that make the two diverge.
_Avoid_: Backfilled, estimated, historical row, stale (none of which is what distinguishes it)

**Health score**:
A single weighted band that always shows its full working. There are two, one per board kind, and they are never the same quantity — see **Sprint health** and **Flow health**. Say which one is meant; a figure that says only "health" invites comparing two boards measured on different evidence.
_Avoid_: Rating, grade, RAG status (as the primary term)

**Sprint health**:
The health score of a sprint board: delivery pace, scope stability, blockers and ageing work. Two of the four need a clock, so it is not available on a flow board at all — not refused there, replaced.
_Avoid_: Health (unqualified), sprint score

**Flow health**:
The health score of a flow board: flow efficiency at 40% of the weight, with blockers and ageing work at 30% each. Flow efficiency is load-bearing rather than merely heavy — without it the score refuses outright, because what remains is hygiene and calling that *flow* health would put the missing measure in the name. None of the three reads work volume, so the points toggle cannot move it.
_Avoid_: Health (unqualified), kanban health, flow score

**Risk register**:
Risks computed from the data currently on screen, including the active filter — never typed by hand.
_Avoid_: Issues list (collides with Issue), concerns, RAID log

**Drill-down**:
The panel behind every figure listing the issues that produced it. The property that makes a number checkable rather than assertable.
_Avoid_: Detail view, popup

**Value basis**:
The stated justification attached to a value figure. A value without a basis is not reported.
_Avoid_: Rationale, source, assumption (which means something else here)

### Forecasting

**Forecast**:
A set of dated percentiles produced by simulating throughput against remaining work. Never a single date.
_Avoid_: Estimate, prediction, ETA, commitment

**Refusal**:
The answer returned when evidence falls below a threshold, stating what was needed and what was there. Quoted word for word, never paraphrased or softened into a wider range.
_Avoid_: Error, failure, no data (as the phrasing)

**Size stability**:
Whether items on this board are still interchangeable enough for counting them to mean anything — the one assumption item-based forecasting rests on.
_Avoid_: Consistency, variance (unqualified)

**Calibration**:
How past published forecasts scored against what actually happened. Without it a forecaster is unfalsifiable.
_Avoid_: Accuracy, hit rate

**Commitment recommendation**:
A next-sprint item count offered from the team's own recent throughput. An input to a planning conversation, not an assignment. It needs a cadence to size the sprint it is recommending, so on a flow board there is nothing to recommend against and it refuses.
_Avoid_: Target, quota, plan

### Intake

**Ask**:
A product request being weighed against others — the input to intake. What makes something an ask is that somebody declared it under consideration, not whether tickets exist for it: it is either a document written in `data/asks/`, or an epic on a board marked a **candidate**.
_Avoid_: Request, requirement, feature request, epic (unqualified — an epic is a tracker object, and only a declared candidate is an ask)

**Candidate**:
An issue somebody has declared to be under consideration, which is the declaration that makes it an ask. A state rather than an issue type — it becomes untrue when whoever declared it takes it back, never because the work has since started or finished. ADR 0028.
_Avoid_: Proposal, unstarted work, backlog item (candidacy is declared, or implied by a **band** unless somebody said no; never inferred from status or from an epic not having started)

**Sizing method**:
Which evidence an ask's size range was built from: **t-shirt**, **reference class**, or **explicit**. Recorded and reported with every forecast, because it bounds how far the answer can be trusted.
_Avoid_: Estimation approach

**T-shirt scale**:
S/M/L/XL bands derived from one board's own completed epics, in items. Never an organisation-wide scale — an "L" has never meant the same thing on two teams.
_Avoid_: Sizing scale (unqualified), points

**Band**:
The S, M, L or XL somebody put on an epic. It selects which quartile of the board's completed epics the ask is forecast against; it asserts no number of its own, which is what separates it from estimating in points. ADR 0029.
_Avoid_: Size estimate, t-shirt estimate (both imply the band is the size rather than the selector)

**Reference class**:
The board's completed epics used as the sample an ask is forecast against. The whole class when no band has been chosen, or none can be read — widest range, fewest assumptions — and one quartile of it when there is a band.
_Avoid_: Baseline, historical average

**Readiness**:
Whether an ask carries enough to be forecast at all, and which gaps will widen or weaken the answer if it is.
_Avoid_: Definition of ready, completeness score

**Queue ahead**:
Committed, unfinished work an ask must wait behind. Excludes mid-sprint additions, which are interruption and are already modelled elsewhere.
_Avoid_: Backlog (which is everything, not this)

**Capacity scenario**:
One of exactly two, always reported together — **earliest possible** (dedicated, nothing queued, a ceiling and not a plan) and **realistic** (queued and interrupted).
_Avoid_: Best case / worst case, optimistic / pessimistic

**Cost of the queue**:
The gap between the two scenarios, in working days. The figure to quote, because it prices what is already in flight.
_Avoid_: Delay, wait time

**Uncertainty attribution**:
The split of a forecast's spread between not knowing the size of the ask and normal delivery variability. It answers which one is worth going and reducing.
_Avoid_: Error bars, confidence (which means something else statistically)

**Sequence**:
An ordering of competing asks, reported by what each ordering costs the others in delivery terms. The ordering itself remains a human judgement — this project computes no priority score of any kind.
_Avoid_: Prioritisation, ranking, WSJF, value/effort score
