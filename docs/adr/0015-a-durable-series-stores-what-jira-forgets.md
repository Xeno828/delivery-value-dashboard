# 0015 — A durable series stores what Jira forgets, and re-derivation is a labelled fallback

Roadmap item 4 is *durable sprint history*. The obvious reading is that the
product should keep more sprints than it currently does, because `history[]`
holds six and the README says it thins out if the fetcher misses a cycle. That
reading produces a cache of Jira, and a cache of a system that is still
authoritative is a second copy waiting to disagree with the first.

The right reading is narrower and it comes from asking one question of every
field in a history row: **if we throw this away, can Jira tell us again?**

## A first answer to that question, which was wrong

The first version of this record argued that `wipItems` — items started and
unfinished when the sprint closed — was the irrecoverable field, on the grounds
that a re-derivation reports zero because every one of those issues has since
moved on.

That was true of the derivation being replaced in the same release, which read
work in progress off an issue's *current* status. It is not true of the one that
replaced it. `history_row()` counts an item as in progress if it started on or
before the as-of date and had not resolved by then, and `started` and `resolved`
are dates that do not move. Asked about a sprint that closed a year ago, it
gives the same answer it would have given on the day. The test that pins 1.36.0
demonstrates exactly this: the same issue list read as of the sprint's end and
as of six weeks later produces one work-in-progress count and then zero, and the
first of those is correct at any distance.

So the 1.36.0 fix removed the premise this record was built on. **Reconstruction
works.** The case for storing a series is real, but it is a different and
narrower case, and it is set out below rather than resting on a field that turns
out to re-derive fine.

## What actually cannot be recovered

Four things, in descending order of how certain they are.

**A forecast that was published.** Nothing in Jira records that this product
once said *"85% confidence of nine items by the 14th"*. It is not derivable from
the issues, because it was derived from them — under a sample, a seed and a
remaining-work count that existed at that instant. If nobody wrote it down when
it was issued there is nothing to score it against, and an unfalsifiable
forecaster is a horoscope. `score_calibration()` has been able to read this file
since the tools were written and nothing has ever produced one.

**Anything about an issue that has been deleted.** Not moved, not closed —
deleted. It leaves no changelog behind it, so a sprint it was committed to
re-derives one item lighter, and the commitment it was part of quietly shrinks.

**`committedItems`, after sprint membership is stripped.** Jira's Sprint field
is multi-valued and retains completed sprints deliberately, so that historic
sprint reports stay accurate — which is why commitment re-derives correctly in
the normal case. But reopening a sprint, moving its issues elsewhere and closing
it again removes those records permanently, and that is Atlassian's documented
way to tidy an issue's sprint field rather than a misuse. Afterwards a
re-derived commitment counts roughly the issues that finished in the sprint,
**so predictability reconstructs as better than it was** — plausible, flattering,
and with nothing on screen to suggest it.

**Any figure whose meaning depends on the status categorisation in force at the
time.** This is the subtle one and it is the reason the other three are not the
whole argument. `started` is not stored by Jira; it is recovered by replaying an
issue's changelog and taking the first transition into a status that **today's**
configuration calls In Progress. Recategorise a workflow status, or edit
`orgConfig.statuses`, and every past sprint's `started` moves — and with it
`wipItems` and `flowEfficiency`, retroactively, across the whole series, with no
event anywhere marking the change. It is the same hazard that made the
organisation config travel inside the dataset rather than beside it: one answer,
resolved once, at the point the data was produced. A recorded row is that rule
applied to time instead of to transport.

There is a fifth reason that is not a correctness one and is labelled as such:
reconstructing twenty-six sprints of issues on every panel read is expensive,
and Forge has an invocation budget. That is an argument for caching, not for
recording, and it must not be allowed to masquerade as one of the four above.

## The decision

**A sprint's row is written once, when the sprint closes, and read thereafter.**
The durable store holds it, together with the date it was observed and the
status configuration it was computed under. Nothing re-derives a sprint that has
already been recorded, so the four hazards above stop applying the day the app
is installed.

**Re-derivation stays, for sprints that closed before we were there,** and it is
labelled as such rather than presented as equivalent. A reconstructed row is not
a worse row — for a site that has not deleted issues, stripped sprint
membership or recategorised a status, it is the same row. It is a row with a
different warrant, and a reader comparing this quarter against last year should
be able to see where the warrant changes.

**Where a recorded row and a reconstruction disagree, say so.** Do not silently
prefer the store. A disagreement means one of the four things above has happened
to that sprint, and which one it was is more useful than either number: it is
the only signal this product will ever get that a status was recategorised
underneath a year of history.

**The store holds counts, never issue text.** A history row is nine numbers, a
sprint name and two provenance fields. That is what makes this cheap on Forge —
`storage:app` is already granted for the recipient config (ADR 0014) so there is
no new scope and no reinstall — and it is what keeps item 4 from waiting on
item 5. Nothing in the store is an issue anybody could be denied sight of.

## What this rules out

**A cache of Jira's sprints.** Storing the issues, so the dashboard can be fast
or work offline. Jira remains authoritative for everything it can still answer;
duplicating that buys latency and guarantees a divergence. The cost argument is
real and is not this record's argument.

**Recording a reconstruction.** Reading a closed sprint the app never observed,
deriving its row and writing that into the store as though it had been recorded
at the time. It would make the series look complete from the day of install, and
it would launder a reconstruction's warrant into a recorded row's. If it is
written at all it is written as what it is.

**Resolving a disagreement quietly.** Preferring the store, or preferring Jira,
where the two differ about a re-derivable field. Two answers to one question is
the condition this repository treats as a bug everywhere else.

**Lifting the six-sprint cap first.** It was the obvious first slice — it is the
smallest, and the six hardcoded `6`s are silent truncations that `CLAUDE.md`
already forbids. It is deferred behind the store because a twelve-month trend is
where the four hazards have had the most time to happen, and the window is a
parameter while the footing under it is not.

## The cost

An app installed two weeks ago can say very little that a twelve-month trend
would say, and it cannot pretend otherwise — the honest answer is a short
recorded series beside a longer reconstructed one, with the join visible. That
is worse-looking than a chart that simply draws a year, and it is the same trade
the forecaster already makes when it refuses rather than widening an interval.
The product's argument is that its numbers can be trusted, and a series that
hides where its evidence changes character is not that.

The second cost is smaller and worth naming: this record was written once with
the wrong reason at the top of it, and the wrong reason was more compelling than
the right ones. *"That figure is gone forever"* argues for a store in one
sentence; *"that figure is stable unless one of four things happens, and you
will not be told when they do"* is the true claim and it takes a page. The page
is the honest length.
