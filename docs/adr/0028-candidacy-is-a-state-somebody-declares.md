# 0028 — Candidacy is a state somebody declares, and every organisation declares it differently

`intake.sequence` compares orderings of **asks**. Everything an ask needs has
arrived except the ask itself: an epic on a Jira board carries a title, a team,
a size from the board's own reference class, a value
([ADR 0025](0025-the-app-declares-a-business-value-field.md)), a basis
([ADR 0027](0027-a-value-basis-is-prose-carried-to-a-reader.md)) and a
needed-by date in `dueDate`. What nothing said was **which epics are being
weighed against each other**.

Decided 2026-08-30, and it was a product question. The app declares a
**Candidate** field, and `orgConfig.askField` lets a site use its own instead.

## Candidacy is a state, not a type

The obvious answer is "an ask is an issue type" — the answer this product
already gave once, for what counts as an item
([ADR 0024](0024-a-parent-and-its-subtasks-are-one-piece-of-work.md)). It is
wrong here.

An epic already committed and half built is not being weighed against anything.
It was weighed, months ago, and the answer was yes. Sequencing it again would
produce a table of orderings for decisions already taken — **worse than
refusing, because it would look like advice**. A type is a permanent property of
an issue; candidacy is a thing that becomes true and then stops being true.

So somebody has to say it, and the saying is what makes it an ask.

## The app declares a default and refuses to insist on it

**No site should have to adopt one convention to use this.** Different
organisations already have different ways of saying a thing is under
consideration: a discovery status, a checkbox, a single select, a stage on a
delivery workflow. A product that recognised only its own field would be asking
every customer to maintain a second copy of an answer they already record.

`orgConfig.askField` is therefore the whole point rather than an escape hatch:

- **`"app"`**, the default, reads the **Candidate** field this app declares. It
  works on any site with nobody creating anything, which matters because
  creating a field needs *Administer Jira* — refused by
  [ADR 0020](0020-the-anchor-issue-is-the-brief-s-access-control.md) and again
  by [ADR 0021](0021-the-audit-log-is-operational-and-says-so.md).
- **Any other value** names a field the site already has, matched by id and then
  by display name.

Matching a display name is a guess when the app picks the field and an
**instruction** when the organisation names one. That is the difference between
this and `findBusinessValueField`, which matches only on a module key precisely
because a site's own "Business Value" field is not ours.

## Why it is text, which is not what anyone wants

Forge cannot declare a checkbox. `jira:customField` offers `number`, `string`,
`user`, `group`, `date` and `datetime`; the two object variants need a custom UI
resource. And the app cannot create a native Jira checkbox, for the
*Administer Jira* reason above.

So the app's own field is text somebody types `Yes` into, and that is worse than
a checkbox. It is accepted because the alternative is either a scope this
product has twice refused, or a field the customer has to create before the
feature works at all. **A site that wants a checkbox points `askField` at one it
made itself**, which is the recommended path for anyone who cares — and is why
the override exists rather than being deferred.

## Three answers, not two

`Yes`, `Y` and `True`, case-insensitively, after trimming. Empty is not a
candidate. **Anything else is neither**: `candidate_answer` returns the string
somebody actually wrote, and the caller names it.

A field reading `Maybe`, or `Q3?`, or `ask Priya` is somebody trying to say
something. Reading it as a no would drop their epic out of the comparison
silently, which is how a sequencing table comes to be missing the ask the
meeting was about — the same class as a truncated list reading as a complete
one, which `CLAUDE.md` forbids by name.

## What it costs

**A minor version**, and it upgraded on its own — a second entry under a
`jira:customField` block that already existed, as
[ADR 0025](0025-the-app-declares-a-business-value-field.md)'s correction
records. No new scope: the field is read with the same grant that reads any
other field.

**A third screen configuration.** An admin must add this field to a screen
before anyone can answer it, separately from the value fields. The state every
board starts in is *the field exists and nobody has answered it*, which reads as
zero candidates and says so.

## Where candidacy is decided, and why it costs a mirror

Wiring this up made the choice concrete: the calculator could decide candidacy
itself, given one more field in the projection, and then `asks_from_issues`
would run server-side with no second implementation to keep in step. That is
the cheaper design and it is not available.

**Because of what the third answer is.** An answer this does not recognise is
reported back with the issue key *and the words somebody wrote* — "Maybe",
"Q3?", "ask Priya". That is free text about a customer's business, and it is
exactly what `NEVER_SEND` and `FREE_TEXT_FIELDS` exist to keep inside the
tenant. Deciding candidacy where the calculator is means sending the answers
there.

So `forge/src/jira.js` carries `candidateAnswer`, `candidateIssues` and
`asksFromIssues`, and `tests/test_service.py` runs them against the Python over
one shared set of cases — the same arrangement as the working week,
`counted_issues` and `validate`. Change one, change both.

**What crosses is an id, a sizing method, an amount and a date.** No title, no
basis, no answer. The calculator therefore echoes an ordering with no words in
it, and the resolver joins the title and the basis back on by id — a lookup,
not a calculation, and the same move `reattach` already makes for item risk.

**And the ask payload gets its own guard.** `assertNoFreeText` protects issues
because they are *projected* through an allow-list; an ask is built rather than
projected, so nothing was looking at it. `assertAsksCarryNoText` in the resolver
and `_refuse_ask_text` in the service both refuse one now — because `title` is
the field somebody will add, it being what a reader wants beside an ordering.
Before this, `/v1/sequence` and `/v1/ask` would have accepted a title, a problem
statement and a value basis without complaint, which made the projection's
guarantee "no customer text reaches the calculator, except through this other
door".

## What this does not do

**It does not render anything yet.** Recognition, assembly and the resolver are
done; the panel that shows an ordering is not. The `sequence` route answers, and
what reads it is the slice after this one.

**It does not infer candidacy from anything.** Not from status, not from
whether an epic has started, not from an empty `dueDate`. Every one of those
would be the app deciding what an organisation meant, and the thing being
recognised here is a decision somebody made.

*Amended 2026-08-31: it now infers candidacy from **one** thing, a t-shirt
band, for the reason and at the price set out at the foot of this record. The
list above is unchanged — none of those became inferences.*

## What it rules out

**An issue type as the marker**, for the reason above.

**A label.** Free text with no validation: a typo silently excludes an ask, and
the failure is invisible in exactly the way this record refuses elsewhere.

**Inferring "not yet started" as candidacy.** It would sequence whatever the
backlog happens to hold, which is not the same as what anybody proposed.

## Amendment: a t-shirt band declares candidacy, and "no" takes it back

Decided 2026-08-31, and it is an amendment rather than a footnote because it
**reverses this record's refusal to infer**. *What this does not do* says
candidacy is not inferred from anything. It is now inferred from one thing.

**The reason is the cost of the fourth field.** A tenant that wants everything
configures Business Value, Value Basis, Candidate and T-Shirt Size on four
screens before any of it does something, and three of the four are text because
Forge can declare neither a select nor a checkbox. Four screen configurations
before a feature works is what an evaluation meets first.

**And the inference is a small one.** Choosing a size for an epic is somebody
saying how big *this thing they are considering* would be. It is already a
statement about a piece of work being weighed rather than done, so charging them
a second field to be taken seriously buys nothing that the first field did not
already say.

**It is reversible out loud, which is what makes it safe.** `CANDIDATE_NO` —
`No`, `N`, `False` — was added with it, because the objection is real: a band
chosen during refinement would otherwise enter an epic into a comparison for
good, and the only way back out would be deleting the estimate to undo the
implication. Saying no beats a band. That is the difference between an inference
and a trap.

So `candidate_answer` has four answers where it had three:

    None    nothing was said — a band may speak for it
    True    somebody said yes
    False   somebody said no, and that beats a band
    str     something nobody can read, which is not a no, and a band may still
            speak for it

**`None` rather than `False` for silence is the load-bearing part.** An epic
nobody answered and an epic somebody declined were the same value before this
and are different facts, and only one of them may be overridden by a size. The
first version of this change kept the old three answers, and the fetcher's
"pull the candidates too" rule read `is not False` — which was true of silence
under the new contract, so every epic on the board became a candidate. The rule
is asked of `candidate_issues` now rather than re-derived, which also picks up
the epics a band declares.

## What the amendment does not change

**Nothing else is inferred.** Not from status, not from `resolved`, not from an
empty `dueDate`, not from an epic having children. One inference, from one
field, whose own meaning is about work under consideration.

**A size nobody can read declares nothing.** "Medium-ish" is named and falls
back to the whole reference class ([ADR 0029](0029-a-t-shirt-band-selects-a-reference-class.md));
it does not make an epic a candidate, because it is not a band.
