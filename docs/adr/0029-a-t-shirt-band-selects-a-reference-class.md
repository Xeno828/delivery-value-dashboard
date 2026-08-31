# 0029 — A t-shirt band selects a reference class; it does not estimate a size

Every ask assembled from a Jira board drew the same distribution. Sizing was
`reference-class` — the item counts of every epic the board had completed — and
a reference class is a property of the *board*, not of the ask. So two
candidates sized identically, and the orderings compared them only by queue
position and by the dates they carried. A sequencing table where nothing is
bigger than anything else says less than it appears to.

Decided 2026-08-31, after the question was asked plainly: some organisations
already t-shirt their epics, and doing so ought to improve the comparison.

## The band is a selector

`tshirt_scale` builds S/M/L/XL from **quartiles of the epics this board has
already completed**. On the demo board that is:

| Band | From | Means |
|---|---|---|
| S | 4 completed epics | 4–6 items |
| M | 4 | 8–12 items |
| L | 4 | 13–21 items |
| XL | 4 | 24–38 items |

So "L" does not mean a number somebody wrote in a table in 2019. It means *like
this board's third-quartile epics*, and it means something different on every
board, which is correct and is why a shared numeric scale across teams never
survives contact.

**This is what separates it from estimating in points**, which
[ADR 0006](0006-forecast-in-items-not-points.md) refuses for forecasting. A
band does not assert a size; it chooses which slice of observed delivery an ask
is compared against. An optimist who calls everything S still gets a
distribution made of real item counts — they have picked the wrong four epics to
be compared with, which is a visible, arguable mistake rather than an invisible
inflation. The estimate selects; it does not invent.

The caveat `size_ask` already carried says the rest of it: the width of a banded
forecast reflects only how varied that board's past L epics were, and not how
wrong the L judgement itself might be. That limit is real and is printed.

## Each ask its own way, and the row says which

An epic with a band is sized off that band. An epic without one is sized off the
whole reference class, which is what every ask did before this existed. **Both
appear in the same comparison**, so every ordering row now carries
`sizing_method` and `sizing_basis`, and the tile shows them in a *Sized by*
column.

The alternatives were considered and are worse. All-or-nothing per board would
let one unsized epic disable the feature for everybody, and nobody would know
why. Sequencing only the sized asks would silently narrow what is being weighed,
which is the truncation this repository forbids by name. Mixing two
distributions is defensible; mixing them quietly is not.

## Three answers again

`S`, `M`, `L`, `XL`, case-insensitively after trimming. Absent is absent.
**Anything else is neither**: an epic whose field says "Medium-ish" or
"2 sprints" falls back to the whole reference class *and is named*, because
sizing it off everything is a wider answer than the one that was meant, and a
reader who typed something should be told it did not land.

## What it costs

**Eight completed epics, not five.** `MIN_TSHIRT_EPICS` is 8 against
`MIN_REFERENCE_EPICS` 5, because the history is split four ways. A board with
too few refuses in those words, and the ask appears in `skipped` with the reason
rather than vanishing.

**A fourth declared field**, and a fourth screen configuration. As with
candidacy, `orgConfig.sizeField` points at whatever a site already uses, and
text is a poor control — Forge cannot declare a select, so a real one the
customer made is better and is the recommended path.

## What this does not do

**It does not make sizing mandatory.** No band is not a gap to be filled in; it
is the previous behaviour, and it is honest.

**It does not infer a band.** Not from story points, not from an epic's current
child count, not from how long similar-sounding epics took. Each would be this
product deciding how big somebody's ask is, and the whole point is that it does
not know.

## What it rules out

**A numeric size on the ask.** `explicit` sizing exists for a caller who has
min/likely/max and takes responsibility for them; a number typed into a Jira
field would be the same thing without the responsibility, and it is the
inflatable unit item counting was chosen to avoid.

**Ranking by size.** A band feeds the forecast and nothing else. It does not
order the asks, and combining it with value would be the priority score
[ADR 0004](0004-no-priority-score.md) refuses.
