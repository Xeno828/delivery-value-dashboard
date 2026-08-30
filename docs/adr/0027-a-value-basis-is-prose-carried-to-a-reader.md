# 0027 — A value basis is prose carried to a reader, never an input

`intake.sequence` compares orderings of competing asks. It returns the delivery
consequence of each ordering — which is computable — and prints each ask's
**value basis** beside it, which is not. The basis is the sentence saying *why*
a number is what it is, and it is the thing the value tile has always told a
reader to challenge.

Nothing carried one. `valueBasis` has been in the schema, the CSV importer, the
value tile and the security suite since long before any of this reached Jira,
and on Forge `issueFrom` hardcoded it to `''` because no Jira field held one.
[ADR 0025](0025-the-app-declares-a-business-value-field.md) closed with exactly
that gap named: *"The value basis a sequencing comparison needs is `valueBasis`,
which no Jira field carries and which this record does not invent."*

Decided 2026-08-30, and it was a product question rather than a coding one. The
app declares a second custom field, **Value Basis**, free text.

## Why free text is the design and not the cheap option

**Nothing computes on it, and nothing may.** `sequence()` reads
`valueEstimate.basis` into a row and prints it. There is no parse, no
comparison, no ranking, no arithmetic anywhere along the path. That is the whole
reason the field can be prose: it is carried to a person who is going to
exercise judgement, and the judgement is theirs.

An enumeration would be the obvious "better" shape — a dropdown of bases, tidy
and reportable — and it is the one that must be refused. A set of enumerated
bases is one join away from a table of weights, and a weight multiplied by a
size is [ADR 0004](0004-no-priority-score.md)'s priority score arriving by the
back door with a nicer name. The refusal is not that scoring is hard; it is that
the product does not have the evidence to justify one, and a dropdown makes that
missing evidence invisible instead of obvious.

**A sentence is falsifiable and a category is not.** *"Three enterprise renewals
at risk cited this in Q3"* can be checked, and argued with by somebody who was
in those conversations. *"Revenue — High"* cannot be wrong, which is exactly
what makes it useless to a reader deciding whether to believe the figure above
it.

## Why a field and not the issue description

The obvious alternative, and it was raised: an organisation that already writes
in outcomes has the basis in the description, so reading it from there would
cost nobody any typing.

**It would make "no basis recorded" unsayable.** `readiness()` reports *"an
amount with no basis is a number someone will quote back at you"* as a named
gap. That check only works if absence is detectable. Read from the description,
"nobody stated a basis" and "there is prose here that is about something else"
are the same string, and the app can never say which — so it would have to
either assert that a description *is* a basis, or drop the gap. The first is the
app inventing a convention on a customer's data and then quoting it back to them
as their own reasoning. The second gives up the check.

That is the same rule as [ADR 0010](0010-an-empty-selection-is-a-refusal.md): a
thing that was not measured has to be nameable as not measured, never quietly
filled with whatever was nearest.

**The duplication is the point.** The description is where you write things; the
basis field is where you sign one. An org that finds that bureaucratic is
telling us something true about how much they believe their own value figures.

## What it costs

**A minor version, and it upgraded on its own.** This was written expecting the
opposite — *"declaring a module is a major version and a forced reinstall"*,
which is what [ADR 0025](0025-the-app-declares-a-business-value-field.md) says
and what the `llm` module cost. The deploy settled it: **7.2.0**, no
`MAJOR_VERSION_RULE` approval, and the installation reporting *Up-to-date*
without `forge install --upgrade`.

The distinction is worth stating because the wrong half of it was about to be
written into two documents. **Introducing a module type is major; adding an
entry to one that is already declared is minor.** ADR 0025 was the first
`jira:customField` in this manifest and paid the major-version price for the
module block itself. This field is a second list entry under the same block, and
a second entry consents to nothing the tenant has not already consented to.
Scope changes are major for the same reason and remain so.

**A second screen configuration.** A Jira admin must add this field to a screen
before anyone can type in it, and that is a separate act from adding the value
field. A tenant will routinely have one and not the other, so the tile says
"no basis recorded" rather than treating a missing basis as a missing value.

**Nothing at the boundary, and that is worth stating rather than assuming.**
`valueBasis` is already in `NEVER_SEND` and in `FREE_TEXT_FIELDS`, so the
calculator receives the number with no sentence and no issue key beside it. The
rule predates the field. It matters more here than it did for the number: prose
about why work matters is the most quotable thing in a backlog.

## What this does not do

**It does not make sequencing work on Forge.** The `sequence` resolver refused
for two reasons and this answers one. An ask is a document with a problem, a
success measure, a needed-by date, a size and a value with a basis; an epic
carrying a value and a basis has two of those six. The refusal now names only
what is actually missing, because a refusal that outlives its reason is the same
failure as a figure that does.

**It does not let the app write a basis.** Same argument as the number: a basis
the app composed would be the app making the judgement, and then quoting itself.

## What it rules out

**An enumerated or scored basis**, now and later, for the reason above.

**Reading a basis out of the description, the summary, or a label.** Each is
prose the author did not offer as a basis.

**Matching the field by display name.** A site's own "Value Basis" field is not
this one — the module key is, which is why both finders match on the key and
why `tests/test_service.py` checks that neither module key is a substring of the
other. If one were, a sentence would be read as a number and a number as a
sentence, and both failures are silent.
