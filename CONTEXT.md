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
A parent grouping of issues. Also the sample unit for sizing an ask, once it has stopped growing and is nearly complete.
_Avoid_: Initiative, feature (as a synonym)

**Board**:
The delivery unit a forecast is scoped to. Throughput, interruption rate and the t-shirt scale are all properties of one board and never transfer between boards.
_Avoid_: Team (when the board is what's meant), squad

**Sprint**:
The bounded period a report covers.
_Avoid_: Iteration, cycle (which means something else here)

**Context**:
One project + board + sprint — the slice of a bundle currently on screen.
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
Total cycle time over total lead time, across a set of completed issues. The share of the wait that was work.
_Avoid_: Efficiency (unqualified), utilisation

**Ageing**:
How long an open issue has been alive, in calendar days.
_Avoid_: Staleness, rot

**Throughput**:
Items completed per working day, sampled across a trailing window. Zero days are part of the distribution, not gaps in it.
_Avoid_: Velocity, capacity (which means something else here), productivity, output

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

**Health score**:
A single weighted band over delivery pace, scope stability, blockers and ageing work, which always shows its full working.
_Avoid_: Rating, grade, RAG status (as the primary term)

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
A next-sprint item count offered from the team's own recent throughput. An input to a planning conversation, not an assignment.
_Avoid_: Target, quota, plan

### Intake

**Ask**:
A described product request with no tickets written yet — the input to intake.
_Avoid_: Request, requirement, feature request, epic (which is a tracker object)

**Sizing method**:
Which evidence an ask's size range was built from: **t-shirt**, **reference class**, or **explicit**. Recorded and reported with every forecast, because it bounds how far the answer can be trusted.
_Avoid_: Estimation approach

**T-shirt scale**:
S/M/L/XL bands derived from one board's own completed epics, in items. Never an organisation-wide scale — an "L" has never meant the same thing on two teams.
_Avoid_: Sizing scale (unqualified), points

**Reference class**:
The board's completed epics used as the sample when no sizing judgement has been made at all. Widest range, fewest assumptions.
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
