# A kanban context is a window, and a window is not a clock

A board that runs no sprints gets a **window**: a rolling stretch of calendar days, picked from the same dropdown a sprint is picked from. It holds the issues open at the as-of date together with those resolved inside it. It carries a start date and an end date, so the selection is bounded, reproducible and round-trips through an id. It carries **no working-day list**, so nothing on the page can pace against it.

That last sentence is the decision. Everything else follows from it.

## Why the withheld calendar is the point

The product models delivery as project → board → sprint, and a sprint is doing two jobs at once that a reader never separates. It is a *bound* — these issues and not others — and it is a *clock*, a fixed scope with a start and an end that delivery can be measured against. Every candidate kanban context supplies the first. The tempting ones also look like they supply the second, and they do not.

A window of thirty days has real dates. Expand them under the organisation config and you get twenty-two working days, which are also real. `m.timeElapsed` becomes 0.6, `m.paceGap` becomes `doneU/totalU − 0.6`, and the KPI strip prints **Pace vs clock: −18 pp** for a team that never committed to finishing anything by the end of that window. The figure is arithmetically correct and it is about nothing. It is the failure this repository keeps paying for: not a crash, a plausible number.

The machinery to refuse it already exists and was built for the same reason. `contextWorkingDays()` in `src/app.js` returns an empty list for a rollup on purpose — a rollup spans nineteen sprints, the days between the first start and the last end are a perfectly real list, and *how far through nineteen sprints are we* is not a pace. A window is the same shape one step further out. So a window is not a new mechanism; it is a second caller of the one [ADR 0010](0010-an-empty-selection-is-a-refusal.md) established, and the work is to give it the right sentence rather than to build it a parallel route.

Every figure that needs the clock is therefore dropped and named, not scored: pace, scope growth, the burndown, and — because two of its four components are those — the sprint health score, which falls below half its weight and refuses outright on any board without sprints. `docs/kanban-boards.md` names them one at a time.

## Membership, which decides every denominator

A window holds **the issues open at the as-of date, plus the issues resolved inside it**.

This is the set a standing team actually looks at, and it is what makes the flow measures honest. Cycle time, lead time, waiting, flow efficiency and throughput all read the resolved half. Ageing and work in progress read the open half. None of them needs a scope boundary, which is why they were already sprint-agnostic — the forecaster samples throughput over a rolling window of *days* and never over sprints, so the product's headline feature has always worked for these teams and only lacked somewhere to hang itself.

What it costs is stated rather than hidden: this set is not a scope, so **Delivered %** has no denominator and refuses alongside the clock-shaped figures. `doneCount / total` over a set defined partly by *being done* would rise when the window widens and fall when it narrows, which is a property of the question and not of the team.

Two other memberships were available. **Resolved-in-window only** gives an exact completed-work sample and loses ageing and work in progress entirely — the two things a team without sprints most wants, since they are the only measures that say anything about work that has not finished. **Anything touched in the window** is the most intuitive and the least reproducible: "touched" is a changelog fact, it cannot be recovered from the schema a bundle carries, and the two transports would have to agree about it issue by issue.

## What it rules out

**The board, unbounded, as-of today.** The simplest id and no window to choose. It also means lead-time distributions spanning years, an ageing chart whose oldest item is a ticket from 2019 that nobody will ever close, and — over Jira — pulling every issue the board has ever held to render one page. A bound is not a concession to the API; a measure over "all of history" is a different measure every month.

**A release, epic or version as the boundary.** This is closest to how some teams without sprints actually think, and it is the only option that would keep a burndown, because a release has a fixed scope and a target date. It is rejected on data rather than on principle: `epic` and `epicKey` are optional fields, `releases` is an optional block, and a board that carries neither — which is most of them — would fall back to having no context at all. If a team does carry them, the existing releases tile already reports them, and it reports them the same way on a board with sprints.

**A window with a clock.** Give the window its working-day list and most tiles keep rendering. That is the version that will be proposed again, because it looks like less work and it makes the page look complete. It is the one this record exists to refuse.

**A synthetic sprint.** Mapping a window onto `sprintLengthDays` and calling it a sprint is the same error with the evidence removed: the page would not know it was looking at an invention, and neither would the reader.

**A rollup that mixes a board with sprints and a board without.** Rollups are already keyed per project and board, so nothing has to be built to prevent this; it is recorded because a project-level view will be asked for. Every clock-shaped figure inside such a rollup would have to refuse, and the cause would differ per member board — which is a new mechanism, not a reuse of this one.

## A tile that can never say anything is not shown at all

[ADR 0010](0010-an-empty-selection-is-a-refusal.md) ruled out a single "no data" banner over the grid, because a banner throws away the two things the page still knows — what it has, and which tiles were already refusing for their own reasons. That reasoning holds and this is not that. A banner replaces the page; this leaves every tile that measures something exactly where it was.

The line is whether the condition can lift. A sprint with no dates may get its dates; a points view may get its estimates; an empty selection may get issues. Those refuse **in place**, addressed to a reader who can act on them. Three tiles on a flow board have no subject rather than no data — a burndown needs a scope somebody committed to, and the commitment-history and team-load charts read per-sprint snapshots of a board that takes none — and nothing will ever change that. Three permanent apologies across a third of the grid stop being a disclosure and become furniture, and they push the tiles that do measure this board below the fold.

The sprint-health chip left for the same reason, being a sprint-board figure sitting where the headline verdict goes, and it is the one thing here that came back **replaced** rather than hidden. **Flow health** occupies it: flow efficiency at 40% of the weight, blockers and ageing work at 30% each, through the same composition machinery. Replacing is the better answer where a genuine alternative measure exists, and it was available here precisely because the forecaster and the flow measures were never sprint-shaped. It was not available for the other three, which is the whole difference.

Two rules keep the replacement honest. The chip **names which composite it carries**, because *Flow health* and *Sprint health* are different quantities on different evidence and a chip reading the same for both invites comparing two boards that were never measured the same way. And flow efficiency is **load-bearing rather than merely heavy**: the half-weight floor would not catch its absence — 60% of the weight survives without it — but what survives is hygiene, so the score refuses outright rather than putting the missing measure in the name.

What keeps it from being the silent cap this repository has shipped three times is that nothing is dropped without being named. The context bar says it in the row that answers *which data am I looking at*; the tile picker lists all three with the reason and **disables** them rather than leaving them merely unticked, because a checkbox that can be ticked and does nothing is worse than one that says why it cannot be. The reader's own tile selection is masked rather than edited, so switching back to a sprint board restores the view intact.

## What it costs

The context id gains a second shape. `PROJ/42/8891` is a sprint; `PROJ/42/win:30d` is a window. `parseContextId()` in `forge/src/jira.js` and its counterpart in `scripts/serve_live.py` both have to return which one they parsed, and refuse anything that is neither — the existing regex requires `project/digits/digits` and would reject a window silently, which reads on screen as "unknown context". The context entry gains a `kind` field so the page never infers the answer from the shape of a string. Both transports send it and `tests/test_service.py` compares it, because a discriminator that only one producer sets is worse than none.

Two tiles refuse for a reason that is not the clock and is worth separating from it. *Can we trust the forecast?* and *Team load* both read per-sprint history snapshots, and a board with no sprints has none. That is a missing sample, not a missing calendar, and it must say so — the whole of [ADR 0010](0010-an-empty-selection-is-a-refusal.md)'s last section is about a disclosure that named the wrong cause three times.

`next_commitment` has to learn to refuse. It already can — `recommend_commitment()` returns *"sprint length is unknown"* below one working day — but `forecast.build()` never lets it: it passes `len(workingDays or working_days(start, end, cfg)) or 10`, and the `or 10` substitutes an invented ten-day sprint before the guard can fire. A window would reach it with twenty-two. This is a live defect today rather than a consequence of this decision: a dataset stating no sprint dates at all already reaches it, and reports a commitment sized against an invented two-week sprint. It is the first thing to fix, before any of this.

Finally, `started` stops being an acceptable omission over the Forge transport. Cycle time is a nicety for a team with a burndown and it is the primary measure for a team without one, and `forge/src/jira.js` currently leaves the field out because recognising the first transition into an in-progress status needs organisation config. The resolution is the one the same file already applies to `statusCategory`: the resolver sends the raw transitions and the page decides what they mean, under the single config it already holds. `docs/kanban-boards.md` sets out the alternative that was refused and why.
