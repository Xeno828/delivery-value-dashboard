# 0019 — A recorded row is a fact about the board, not about the reader

[ADR 0018](0018-permission-mirroring-holds-by-accident-and-where-it-does-not.md)
surveyed roadmap item 5 and deliberately decided nothing, leaving one question
at the front: **does a recorded sprint row belong to the board, or to the
reader?** This answers it. It belongs to the board.

## What that costs, said first

A row is shown to readers who cannot see every issue it counts. Under
issue-level security, a viewer who may browse ten of a sprint's forty issues is
shown *"committed 40"* — an aggregate over thirty issues they were not granted.

That is a real disclosure and it is accepted, for three reasons.

**What leaks is a count.** [ADR 0015](0015-a-durable-series-stores-what-jira-forgets.md)
and [ADR 0017](0017-a-forecast-is-logged-as-a-count-not-a-promise.md) both
refused issue identity, and both said the reason was to keep item 4 off item 5's
critical path. This is that path arriving. A number is smaller than a title; the
distinction is what makes this decision arguable rather than plainly wrong.

**On the common configuration it discloses nothing.** Jira permissions are
usually project-level: everyone who can open the board can read all of its
issues. Issue-level security schemes exist and are the exception.

**The alternative makes the feature pointless.** Showing a recorded row only
where the reader's own view agrees means the row is re-derived per reader, which
is what the store exists to stop — and it would reintroduce the bug 4a was built
to fix, where a closed sprint reads better the longer ago it was.

## What follows from it, which is the part with teeth

Deciding the row belongs to the board is not a decision to change nothing. It
makes a row recorded by a narrow reader **wrong** — not a disclosure, simply
false, because it claims to be about the board and is about one reader's part of
it. Every figure in such a row is smaller in the same direction, so nothing
inside it distinguishes a restricted view from a team that delivered less.

So:

**A row records how wide the view that produced it was.** `issuesSeen`, a count,
naming no issue. Without it the store cannot tell its own facts apart from one
reader's version of them.

**A narrower view never replaces a row.** `recordable` refuses, and says which
numbers it compared. Before this, whichever reader happened to open the panel
last wrote the row.

**A wider view corrects one.** This is the single exception to ADR 0015's rule
that a final row is never rewritten, and it is that rule read the other way: the
reason given there is that *"a later look has less to go on, not more"*, which a
wider view falsifies. A row recorded by a restricted reader is repaired the
first time somebody with full sight of the board opens the panel.

**A reader who sees less is told so.** Not a refusal — the figures are the
board's and the board is what was asked about — but a sentence: the row is about
the whole board, your own view is narrower, and the difference is issue-level
security rather than a delivery problem.

**And that reader's row is not also reported as an unexplained disagreement.**
ADR 0015 has a sentence for a recorded row that no longer matches Jira, offering
a reopened sprint or a deleted issue as causes. A narrowed view differs on every
count for a known reason, so it is excluded from that sentence. One cause, one
sentence — the rule this repository has now had to apply three times.

## The forecast log, addressed the same day and not the same way

A claim is the board's for the same reasons a row is, and the thought it needed
turned out to matter: **a row is observed repeatedly and can be widened; a claim
is made once and resolved once, and is never rescored.** So the irreversible
hazard is not publishing a narrow claim — it is *resolving* a good one from a
view that cannot see the work, which marks a correct forecast wrong with no
second chance. That asymmetry, not the disclosure, is what shapes it.

Two gates, not one:

**Publishing.** A claim made over a narrower view than the log's widest is not
added. It would score the forecaster on a prediction it never made about the
whole board. The reader is told, with both numbers — and on a board whose
issues were genuinely archived, that sentence is the only signal the log's idea
of the board has gone stale.

**Resolving.** A claim is left *pending* rather than resolved when the resolving
view is narrower than the view that made it. The horizon has passed and the
claim will settle the moment somebody who can see what it was about opens the
tile. This is the gate that matters, because the other one is recoverable and
this one is not.

**A claim with no recorded width still resolves.** Entries written before this
rule carry none, and refusing to score them would make the rule retroactively
delete the evidence it exists to protect.

## What this does not fix

**Nothing detects a reader who sees *more* than the record.** That is the
harmless direction — the row under-reports rather than over-reports — and it is
repaired by the widening rule rather than announced.

**Nothing distinguishes a restricted view from a board that lost issues.**
`issuesSeen` compares two counts. A sprint that genuinely lost thirty issues and
a reader who cannot see thirty produce the same comparison. The sentence says
issue-level security because that is the far more likely cause of the two given
the row was recorded wider, but it is an inference and not a measurement.

**The assumption is not enforced anywhere.** This product cannot ask Jira
whether a project uses issue-level security. It can only notice that two views
disagreed, which is what it now does.
