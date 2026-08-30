# 0026 — Items and value are counted from two different sets

[ADR 0025](0025-the-app-declares-a-business-value-field.md) declared a Business
Value field and decided it is counted at epic level and above. It was deployed,
an administrator added it to a screen, a number went onto an epic, the epic was
marked Done — and the dashboard showed nothing.

Two things were wrong, and neither was visible from the code that had just been
written.

## Epics are not on a scrum board

*"Epic issues do not belong to the scrum boards"* is Jira's own description of
the design. `/rest/agile/1.0/board/{id}/sprint/{sprintId}/issue` returns the
issues **in** a sprint, and an epic is not one of them — its children are. So
the fetch that every figure on the page is built from could never have returned
the thing the value was recorded on.

Declaring a field was necessary and nowhere near sufficient, and nothing in the
code said so: the projection read the field, the field was real, and the answer
was empty.

**The board's epics are fetched separately**, listed from
`/rest/agile/1.0/board/{id}/epic` and then read as issues for their fields. That
costs a scope — `read:epic:jira-software`, read-only like every other — which
`forge lint` demanded rather than a tenant reporting no value. Adding it made
the app a major version and needed `install --upgrade`, which is a reason to do
it while there are no external installs rather than after.

**An epic is credited to the period it finished in.** An epic spans sprints, so
its resolution date is the only moment about it this product can honestly date.
Spreading its value across sprints by counting its children would be exactly the
double count [ADR 0025](0025-the-app-declares-a-business-value-field.md) exists
to prevent. An entry with no dates gets no epics, rather than every epic the
board has ever finished.

## Items and value cannot come from one filtered list

This is the part that would have failed silently even once the epics arrived,
and it is the reason this record exists rather than a paragraph in ADR 0025.

An epic is a **container of items**, so it must be excluded from item counts for
precisely the reason a subtask is
([ADR 0024](0024-a-parent-and-its-subtasks-are-one-piece-of-work.md)): counting
a parent alongside its children reports the same delivery twice. The exclusion
is symmetric — subtasks below the line, epics above it, and the unit of work in
between.

But an epic is also the **only place value is recorded**. So reading value off
the filtered items reads it off a list the item rule has just emptied of
everything that carries any.

So there are two sets, and every consumer has to read the right one:

| | |
|---|---|
| `counted_issues` | what counts as an **item** — no subtasks, no epics |
| `value_issues` | what carries **value** — epics and above only |

`facts`, `history_row` and the page all read both, and the split is why
`history_row` had to change too: it had never applied the item rule at all,
while `facts` applied it at its own top. A trend row counted an epic as an item
while the facts pack beside it did not — two answers to one question about one
sprint, and the kind of disagreement this repository normally catches by having
one implementation rather than two readers.

## What it cost to get wrong twice

**The tile printed "−1 of the 0 completed items carry no value estimate."** The
footnote subtracted the item pool from the value pool: `done` holds items, which
never include an epic; `items` holds the value pool, which is only epics. Two
sets, one subtraction, no meaning, and a negative count on a customer's screen —
seen in a tenant on the first sprint where an epic delivered value while the
sprint's own items were all still open.

**And the click-through threw**, for the same reason: it looked the clicked row
up in the item pool, and the thing just clicked is by definition not in it.

Both are the same mistake made twice: a split introduced in one place and not
followed to every reader of the thing that was split. The tests that now pin
them are in `tests/e2e.py`, because a negative count needs a rendered page to be
seen at all.

## What the tile says now

Value has three empty states and they have three different fixes, so it names
which — nothing priced; nothing priced *at the level value is counted at*; or
the field not yet on a screen, which every installation is in on the day it
upgrades. And the footnote says where value lives:

> Value is recorded on epics and above, so work below that level is not counted
> here and is not missing from it.

That sentence matters more than the arithmetic. Without it, somebody who prices
a story sees a figure that ignores it and is given no reason.

## What this rules out

**One filtered list for both measures.** They are counted at different levels
and therefore from different sets; a single list cannot serve both, and the two
attempts to make it do so are recorded above.

**Rolling a story's value up to its parent epic.** A story below the line
contributes nothing rather than being folded upward. Folding would claim that an
epic's value *is* the sum of its children's, and would double-count the moment
somebody priced both.

**Reading an epic's value from its children's `parent` field.** Jira returns a
parent summary object — key, summary, status — and no custom fields. There is no
route to the value except fetching the epic.
