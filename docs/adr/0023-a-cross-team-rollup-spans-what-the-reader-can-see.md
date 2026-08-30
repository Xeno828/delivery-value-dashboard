# 0023 — A cross-team roll-up spans what the reader can see, names it, and does not forecast

Roadmap item 7 is *"cross-team roll-up and intake sequencing"*, phase 4,
*"sell it upward"*, recorded as **blocked on 4 and 5**. Item 4 is done and item 5
has had a first pass, so the question was whether item 7 can start.

It can, and the dependency was wrong for both halves — differently for each.

## What already exists, which is more than the roadmap implies

**Intake sequencing is built.** `intake.sequence()` compares orderings of a
board's outstanding asks, with a CLI (`make intake-sequence`), a service route
(`/v1/sequence`), a page renderer and tests. It works wherever asks exist as
files in `data/asks/`.

**A roll-up exists and is not this one.** `roll:<projectKey>|<boardId>` spans one
board's sprints — *"All 6 sprints"*. That is a cross-**sprint** roll-up. Item 7
asks for cross-**team**, which in this product means across boards, because a
Jira board is the closest thing to a team it has.

## Why the stated dependency was wrong

**Sequencing is blocked on a product question, and it is not items 4 or 5.**
The Forge resolver already refuses, in its own words: there is *"no issue type
that means [an ask] and no field that carries a value basis"*. Where a
customer's asks come from inside Jira has never been decided. No amount of
durable history or permission mirroring answers it, and this record does not
answer it either — inventing a convention for what an ask is, in an ADR about
roll-ups, is exactly how a product acquires a feature nobody asked for.

**The roll-up's dependency on item 5 is real in shape and is answerable now.**
A cross-team roll-up shows several teams' figures to one reader, which is a
disclosure question by construction. But the panel reads Jira as the viewer, so
a board the reader cannot browse never reaches the page at all — mirroring holds
for free, exactly as it does everywhere else on that path.

What does *not* hold for free is the consequence: **a programme total computed
over the boards a reader happens to see is a smaller, plausible number, and
nothing on the page would say a team is missing.** That is this repository's
most-feared failure — it does not fail, it returns a credible wrong answer.

## The thing that decides the design

**This app cannot know which boards it is not seeing.**
`/rest/agile/1.0/board?projectKeyOrId=…` is read with the viewer's authority, so
it returns the boards they may browse and says nothing about the rest. Learning
the true count would mean reading the board list as the *app*, which
[ADR 0018](0018-permission-mirroring-holds-by-accident-and-where-it-does-not.md)
keeps off the panel path — and which would itself tell a reader that boards exist
they are not entitled to see.

So detection is not available. The answer is to make it unnecessary.

## The decision

**A cross-team roll-up spans the boards this reader can see, and names them.**

Not a count — the names. A reader looking at *"Storefront Delivery, Payments,
Platform"* can tell what the figure covers and, more to the point, can tell what
it does not. *"3 boards"* cannot be checked by anybody; three names can be
checked by everybody who knows the programme. It converts an undetectable
omission into a visible list, which is the only honest move available when the
omission itself cannot be measured.

It also means two readers may see different totals under the same name, and
that is fine precisely because the name is not the same: each is labelled with
its own members.

**A cross-team roll-up does not forecast, and the refusal is not a placeholder.**
`team_slice` selects by team label. Handed a synthesised cross-team context it
would pick *one* team's label and forecast that team — a forecast over a
narrower sample than its own heading claims, which is the failure mode
`selection.py` exists to prevent and which CHANGELOG 1.8.0 records costing a
19-day forecast that read 77.

Beyond the implementation hazard there is a modelling one. Pooling several
teams' throughput samples assumes the teams are interchangeable — that an item
finished by Payments is evidence about how fast Platform finishes items. Nothing
in this product establishes that, and a Monte Carlo will happily produce a
confident date from the pooled sample. So the roll-up reports **facts** — what
is in flight, what completed, across the boards named — and the forecast tile
refuses with a sentence saying which of the two reasons it is.

**Windows are excluded**, for the reason already documented for the per-board
roll-up: a flow board is offered 14, 30 and 90 days of itself and those overlap
completely, so a roll-up holding all three counts the same issue three times.

## What this does not decide

**Whether a cross-team roll-up should ever forecast.** If a customer wants a
programme date, the honest construction is probably per-team forecasts combined
by the reader rather than a pooled sample, and that is a piece of work with its
own record.

**What an ask is inside Jira.** Sequencing stays refused on Forge until somebody
decides. It works today wherever asks are files.

**Roll-up across projects.** This is within one project, because that is what a
panel is opened in. Across projects is a different selection problem and a
different permission question.

## What this rules out

**A total that does not say what it covers.** Any figure this roll-up shows
carries the boards it was computed over, or it is not shown.

**Reading the board list as the app to count what the reader is missing.** It
would work, and it would be the first thing on the panel path to read with
authority the reader does not have, to tell them about something they are not
entitled to. The list of names does the honest half of that job.

**Pooling teams into one forecast because the machinery would accept it.**
`team_slice` would return something. That is the danger, not the feature.

## Superseded in part: half of that refusal has been answered

The refusal quoted above named two things. One of them now exists.
[ADR 0027](0027-a-value-basis-is-prose-carried-to-a-reader.md) declares a Value
Basis field, so the resolver's sentence no longer says no field carries one —
which means the words quoted here are no longer the words in
`forge/src/index.js`, and a reader who goes looking for them should know why.

**The argument this record makes is unchanged.** Sequencing was never blocked on
items 4 or 5, and it is still not. What remains missing is the *ask* — nothing
in a Jira site marks an issue as a request being weighed against others, and the
problem, the success measure and the needed-by date have no field either. That
is still a product question, and this record still does not answer it.
