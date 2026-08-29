# 0018 — Permission mirroring holds by accident, and here is where it does not

Roadmap item 5. The roadmap describes it as *"under-estimated"* and *"untested"*
and gives it 5–8 weeks, and both of those are said in this repository more
confidently than anything about it has ever been checked. This record checks it.

It decides very little. Item 5's failure is a **disclosure** — a reader told
something about work they are not entitled to see — and the first thing to get
right about a disclosure is knowing exactly where it can happen. Fixing the
wrong one first is worse than fixing none.

## What holds today, and why it is not a design

**The panel mirrors permissions completely, and for free.** Every Jira read on
the panel path is `api.asUser()`, so Jira itself decides what comes back. A
viewer who cannot browse an issue never receives it, so no figure on the page
was ever computed over it. This is not a mechanism this product built; it is a
property of reading as the person asking, and it costs nothing as long as
nothing is *kept*.

That last clause is the whole of this record.

## The three places it does not hold

### 1. The durable series stores what one viewer could see, and shows it to everyone

Roadmap item 4a, delivered 2026-08-29, and this record is the first thing to
say it out loud.

`resolver.define('history')` fetches the board's issues **as the viewer**, sends
them to the calculator, and stores the resulting rows under `series:<boardId>`
in app storage. The next reader — any reader — is shown those rows.

So a viewer who can browse forty issues records *"committed 40"*. A viewer who
can browse ten opens the same board and is shown *"committed 40"*, which is a
statement about thirty issues they may not see. Before the series existed, that
second viewer's trend was re-derived from their own visible issues on every
load, and mirroring held for free exactly as it does on the rest of the page.
**Item 4a converted a property into an assumption**, and this is the first
record to notice.

It is worth being precise about how bad it is. What leaks is an *aggregate* — a
count, not a key or a title, because [ADR 0015](0015-a-durable-series-stores-what-jira-forgets.md)
deliberately kept the store to nine numbers and a sprint name. A count over
issues you cannot see is a much weaker disclosure than their titles, and on the
common Jira configuration — project-level permissions, where everyone who can
see the board can see all of its issues — it discloses nothing at all. It is
still a figure computed over work a reader has not been granted, presented to
them as fact.

**And it collides with a decision ADR 0015 already took.** That record says a
recorded row and a re-derivation that disagree are both kept, the recorded
figures are shown, and the fields that moved are named — because a disagreement
means one of four hazards happened. Issue-level security is a fifth cause of
exactly that disagreement, and for that cause showing the recorded figure is the
wrong answer. Item 5 will have to reopen that decision, and this is written down
now so that it is a reversal made deliberately rather than a contradiction
discovered later.

### 2. The forecast log has the same shape

Roadmap item 4c, delivered the same day. `resolver.define('forecast')` fetches
the slice's issues as the viewer, and the capacity claims derived from them are
written to `forecastlog:<boardId>` and scored for every reader. A claim of *"at
least 9 items by the 14th"* made by somebody who could see the whole board is
resolved and displayed to somebody who cannot.

The same mitigation applies for the same reason — [ADR 0017](0017-a-forecast-is-logged-as-a-count-not-a-promise.md)
refused to record issue keys, precisely so this item would not be waiting on a
permission model — and the same aggregate leak remains.

### 3. The brief tells recipients aggregates over issues they may not browse

Roadmap item 3, and the one that was already known. [ADR 0014](0014-jira-sends-the-brief-and-the-read-only-rule-bends.md)
records that `restrict: [{key: BROWSE}]` filters recipients against **the anchor
issue only**, not against every issue the brief counts.

Checking what the brief actually says narrows this considerably, and the check
had never been made. Every section in `sectionsFor` is counts, dates and units —
`{{done}} of {{total}} items finished`, `{{added}} items were added`, `{{n}}
items are flagged as blocked` — and `briefMessages` hands the model **only those
figures**. No issue key and no summary reaches a recipient, and none reaches the
model either.

That is worth recording because the roadmap and ADR 0013 both describe the model
as reading the tenant's issue titles. Whatever was intended, **that is not what
shipped**: the prompt is a list of numbers. The egress argument in ADR 0013 is
unaffected — it is about where the model runs — but the sentence overstates what
the model is given, and anyone reasoning about item 5 from it would start from a
worse position than the code is actually in.

## What this record decides

**Nothing about the fix.** Three things instead:

**The exposure is an inventory, not a hunt.** Every app-level store is now
declared in `tests/test_service.py` with the authority its contents were
computed under and what it therefore exposes — the same shape as the non-read
scope allow-list, which requires a scope to be listed *and* justified. A fourth
store cannot appear silently.

**Aggregates, never identity.** Both stores hold counts by deliberate earlier
decisions (ADR 0015, ADR 0017), and that stays true whatever item 5 does. It is
the difference between a disclosure that is arguable and one that is not.

**The panel path stays `asUser()`.** `jira(as)` defaults to `'user'` so that a
read added without thinking is added on the safe side, and nothing here changes
that. The scheduled brief remains the only `asApp()` caller, for the reason
ADR 0013 gives.

## What is still open, stated as questions rather than answered

- **Does a recorded row belong to the board or to the reader?** If the board:
  the aggregate leak is accepted and documented as an assumption about the
  customer's permission scheme, with something that detects when the assumption
  is false. If the reader: recorded rows are shown only where the reader's own
  view agrees, which reverses part of ADR 0015 and makes a stored series much
  less useful.
- **Can this product tell the two cases apart at all?** A recorded row larger
  than a viewer's re-derivation means either issue-level security or one of
  ADR 0015's four hazards. Distinguishing them may need something Jira does not
  offer, in which case the honest answer is a refusal rather than a guess.
- **Is `restrict` against a set of issues possible?** ADR 0014 says the notify
  endpoint takes one issue. If a brief cannot be restricted against everything
  it counts, the alternative is composing per recipient, which is a different
  product.

## What this rules out

**Fixing the brief first.** It is the exposure that was already written down and
the one that leaks least — counts only, no identity, and a recipient who can
browse the anchor issue is on the board already. The two stores are newer, less
examined, and were created by work that explicitly claimed to be staying off
item 5's critical path.

**Treating "we hold only counts" as the whole answer.** It was the right
constraint and it is not a permission model. A count is smaller than a title; it
is not nothing.

**Estimating item 5 from this record.** It surveys three exposures and resolves
none. The roadmap's 5–8 weeks was never tested and still is not.
