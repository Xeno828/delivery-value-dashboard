# 0015 — A durable series stores what Jira forgets, and re-derivation is a labelled fallback

Roadmap item 4 is *durable sprint history*. The obvious reading is that the
product should keep more sprints than it currently does, because `history[]`
holds six and the README says it thins out if the fetcher misses a cycle. That
reading produces a cache of Jira, and a cache of a system that is still
authoritative is a second copy waiting to disagree with the first.

The right reading is narrower and it comes from asking one question of every
field in a history row: **if we throw this away, can Jira tell us again?**

## Two kinds of fact

Most of a history row survives being forgotten.

`completedItems`, `committedItems`, `unplannedItems` and `flowEfficiency` are
all derived from issue *dates* and from the changelog — when something was
created, started, resolved, and when the sprint field was set. None of those
move. Ask Jira for a sprint that closed a year ago and the same arithmetic
produces the same row.

One field does not survive, and it is the one the Team load card is about.
**`wipItems` is the count of items that had started and had not finished at the
moment the sprint closed.** That is not a property of the record; it is a
property of a moment that has passed. Every one of those issues has since moved
on, so a re-derivation reports zero — which is exactly the bug fixed in 1.36.0,
where a closed sprint reported no work in progress and a commitment met in full
and got better the further back a reader looked.

The forecast log is the same kind of fact for the same reason. A probability
that was published is not recoverable from the data it was computed over; if
nobody wrote it down when it was issued, there is nothing to score it against
later, and an unfalsifiable forecaster is a horoscope.

So the store is not "the last N sprints". It is **the facts Jira stops being
able to answer**, and it is small.

## What we checked, and the answer that is not quite yes

The re-derivable half rests on one assumption: that an issue carried out of a
closed sprint still answers to that sprint. It does. Jira's Sprint field is
multi-valued and retains completed sprints deliberately — Atlassian's own
guidance is that it exists to keep the record of where work was planned to
finish and did not, so that historic sprint reports stay accurate. A JQL
`sprint = <closed id>` returns the issue because the closed value is still in
the field. That is why `committedItems` re-derives correctly at any distance,
and it is why item 4 does not need to store the whole row.

**But it is reversible, and reversing it is a supported operation.** Reopen a
sprint, move its issues elsewhere, close it again, and the previous sprint
records are removed from those issues permanently. Nothing about that is
misuse; it is the documented way to tidy an issue's sprint field, and a team
that does it is not doing anything wrong.

The consequence is the part that decided this record. After that has happened,
a re-derived `committedItems` counts only the issues that still carry the
sprint — which is roughly the ones that finished in it. Commitment collapses
towards completion, and **predictability re-derives as better than it was**. It
is the same failure as the one 1.36.0 fixed, reached by a different route: a
plausible number, flattering, with nothing on screen to suggest it.

So re-derivation is correct by convention rather than by guarantee, and a
twelve-month trend built on it is trusting an administrator not to have tidied
anything in a year.

## The decision

**A sprint's row is written once, when the sprint closes, and read thereafter.**
The durable store holds it. Nothing re-derives a sprint that has already been
recorded, so the convention above stops mattering the day the app is installed.

**Re-derivation stays, for sprints that closed before we were there,** and it is
labelled as such rather than presented as equivalent. A row recovered from Jira
after the fact is a reconstruction: its `wipItems` is unknowable and is
**absent, not zero** — the rule in ADR 0010, applied to a field rather than a
tile. A trend chart that mixes recorded rows and reconstructed ones says which
are which, because the difference is not cosmetic and a reader comparing this
quarter against last year is comparing two different kinds of evidence.

**The store holds counts, never issue text.** A history row is nine numbers and
a sprint name. That is what makes this cheap on Forge — `storage:app` is already
granted for the recipient config (ADR 0014) so there is no new scope and no
reinstall — and it is what keeps item 4 from waiting on item 5. Nothing in the
store is an issue somebody could be denied sight of.

## What this rules out

**A cache of Jira's sprints.** Storing the issues, or the whole row, so the
dashboard can be fast or work offline. Jira remains authoritative for everything
it can still answer; duplicating that buys nothing and guarantees a divergence.

**Silently preferring the store.** If a stored row and a re-derivation disagree
about a re-derivable field, that is a fact worth surfacing, not a tie to break
quietly. Two answers to one question is the condition this repository treats as
a bug wherever else it appears.

**Filling `wipItems` with zero for a reconstructed sprint.** It is the cheapest
possible way to make a chart continuous and it states something false about a
team. Absent is not zero, and a Team load card that flatlines across the period
before install is a claim that nothing was ever in flight.

**Lifting the six-sprint cap first.** It was the obvious first slice — it is the
smallest, and the six hardcoded `6`s are silent truncations that `CLAUDE.md`
already forbids. It is deferred behind this record rather than done first,
because a twelve-month trend assembled by re-derivation is precisely the thing
the paragraph above says not to trust. Store first, then extend the window; the
cap is a parameter, and the footing under it is not.

## The cost

An app that has been installed for two weeks can say very little that a
twelve-month trend would say, and it cannot pretend otherwise — the honest
answer is a short recorded series beside a longer reconstructed one, with the
join visible. That is worse-looking than a chart that simply draws a year, and
it is the same trade the forecaster already makes when it refuses rather than
widening an interval: the product's argument is that its numbers can be
trusted, and a series that hides where its evidence changes character is not
that.
