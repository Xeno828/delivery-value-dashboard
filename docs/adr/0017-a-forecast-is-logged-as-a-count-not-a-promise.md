# 0017 — A forecast is logged as a count by a date, not as a promise about these items

Roadmap item 4c. [ADR 0015](0015-a-durable-series-stores-what-jira-forgets.md)
asked one question of every figure — *if we throw this away, can Jira tell us
again?* — and found four answers where it cannot. The first and least arguable
was **a forecast that was published**: nothing in Jira records that this product
once said *"85% confidence of nine items by the 14th"*, because it was derived
from the issues rather than stored among them, under a sample and a remaining
count that existed at that instant.

`score_calibration()` in `agent/tools/forecast.py` has been able to read a log
of those since the tools were written. Nothing has ever produced one. So the
forecaster has never been scored against its own history, and an unfalsifiable
forecaster is a horoscope — which is an uncomfortable thing to be, for a product
whose entire argument is that its numbers can be trusted.

## The thing that had to be decided

`build()` publishes three answers, and they are not equally loggable.

**`sprint_completion`** gives *"the probability all of it lands by the 14th"*.
This is the claim a reader remembers and the one a slide quotes. It is also the
one that cannot be resolved without knowing **which** items were outstanding
when it was made: "all of it" names a set, the set changes, and a resolution
that counted whatever the board held later would be answering a different
question with a straight face.

Recording the set means recording issue keys. That is the decision this record
turns on, and it is refused:

- **It would put customer-identifiable data in an app-level store.** The
  durable series was deliberately built to hold nine numbers and a sprint name
  so that *nothing in it is anything a reader could be denied sight of* — which
  is precisely what keeps item 4 from waiting on item 5's permission model. A
  log of issue keys is a list of what exists on a board, readable by anyone who
  can read the store, and it would put 4c on that critical path for the sake of
  a nicer sentence.
- **A key is not free text, and that is not the point.** `CALC_FIELDS` already
  sends `key` to the calculator, so this is not a new class of data leaving the
  tenant. It is a new class of data being *kept*, at app level, indefinitely,
  which is a different question with a different answer.

**`capacity_to_target`** gives *"p% confidence of at least N items by D"*. It
resolves from a count of completions in a window. It needs no issue identity at
all, and it yields four claims per forecast at four separated probabilities,
which is what calibration bucketing wants and what the ten-resolved-entry
threshold needs in order to be reachable this decade.

**`next_commitment`** is the same shape as capacity over a sprint rather than a
date, and is left for later rather than ruled out.

## The decision

**A published forecast is logged as its capacity claims: a count, a date, and a
probability.** One entry per percentile, each independently resolvable, holding
nothing that identifies an issue or a person. `CLAIM_FIELDS` is an allow-list
and `problems_in_claim` refuses an entry carrying anything else rather than
trimming it — the same shape as the series store, for the same reason.

**A refusal is not a claim.** Where the forecaster declined to state a figure,
nothing is logged. Recording a refusal as a prediction would score the
forecaster on answers it explicitly refused to give, which inverts the whole
point of it refusing.

**A claim's id is deterministic** — context, day, percentile. A panel load
produces a forecast, and so does the next one, and the weekly brief, and a
reader refreshing the tab. Without this the log would hold one prediction eleven
times and the scorer would count eleven observations, which is the way to make a
Brier score look excellent while measuring nothing.

**A claim is resolved once and never rescored.** The window it was about is
closed; recounting it later against a board whose issues have since moved would
quietly change a score that was already published.

**The window is `(madeOn, horizon]`.** An item finished the morning the forecast
was made was not predicted, it was history. One finished on the horizon itself
counts.

## What this cannot do, said here rather than found later

**The four claims from one forecast are not independent events.** The same
fortnight decides all four, and `score_calibration` treats them as separate
observations, which overstates `n` and understates the uncertainty on the Brier
score. The alternative is one claim per forecast, which needs four times as long
to reach a scoreable log. A score over correlated observations, labelled as
such, is a great deal better than the nothing this product has had for two
years — but it is not a confidence interval and must not be quoted as one.

**Work that moved off the board is not counted.** A resolution reads the board's
issues as they stand, so an item completed inside the window and since moved
elsewhere makes a claim resolve false because the work moved rather than because
it was late. This is the same gap ADR 0015 records for a stripped sprint
membership, and no reading of Jira closes it.

**A short log is not evidence of anything.** `score_calibration` refuses below
ten resolved entries and says so, and the sentence that carries that refusal
says how many are still waiting on their horizon — because *"too few resolved
forecasts"* and *"the forecaster is badly calibrated"* are different statements
and only one of them is a criticism.

**Nothing is wired yet.** This record and the functions under it decide what a
claim is and when it resolves. Where the log lives, who writes it and when it is
scored are the next slice — and the store is the one the series already uses, so
it costs no new scope.

## What this rules out

**Logging the completion probability by recording issue keys.** Named above. If
that claim is ever wanted badly enough, it is a decision to put item 4 behind
item 5, taken deliberately and written down — not a field quietly added to an
entry.

**Scoring a forecast the tool refused to make.**

**Resolving a claim early**, against a partial window, to get a score sooner.
The horizon is the claim.

**Quietly re-resolving.** If a resolution is ever found to be wrong, it is
corrected as an amendment that says so, the way a changelog entry is.
