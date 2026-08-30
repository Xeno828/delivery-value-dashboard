# 0025 — The app declares a Business Value field, and counts it at one level

Jira has no native field for what a piece of work is worth. So `businessValue`
has been hardcoded to `0` in the Forge projection since it was written, and
[ADR 0024](0024-a-parent-and-its-subtasks-are-one-piece-of-work.md) made
`valueDelivered` report **absent rather than nil** for exactly that reason — a
sprint that delivered nothing worth anything and a sprint nobody priced are
different statements, and only one of them is a criticism.

This is the field that makes it a figure. Decided 2026-08-30: the value belongs
on **epics and anything above them**, and deliberately not on stories.

## Declared, not created

A `jira:customField` module makes Jira create *"a locked instance of each custom
field defined in the manifest"* when the app is installed. That matters more
than it sounds:

**It costs no scope.** Creating a field through `POST /rest/api/3/field` needs
the *Administer Jira* global permission — the grant
[ADR 0020](0020-the-anchor-issue-is-the-brief-s-access-control.md) refused for
checking recipients and [ADR 0021](0021-the-audit-log-is-operational-and-says-so.md)
refused again for reading the audit log. Declaring one needs nothing the app did
not already hold.

**The app never writes it.** `readOnly` is left false so a person edits the value
in Jira's own UI. What work is worth is a judgement made by whoever is
accountable for it; an app that wrote the number would be making that judgement,
and it would need `write:jira-work` to do it.

**It is found by key, not by name.** A Forge custom field's key carries the
module key that declared it, so `findBusinessValueField` identifies *this app's*
field. `findStoryPointField` beside it matches on three known display names
because it is looking for a field this app did not create and cannot identify
any other way — the difference is worth keeping. A site that already has its own
field called "Business Value" is precisely the case where matching on a name
reads somebody else's numbers and reports them as delivered value.

**An unset field is `null`, not `0`.** The distinction is the whole reason
`valueOf` is a function: a field nobody has filled in and work genuinely worth
nothing are different facts, and the tools already act on the difference.

## Counted at one level, and only one

**The manifest cannot restrict a field to issue types** — no such property
exists. So the field is available wherever an administrator puts it, and *which
levels count* is the app's rule rather than the customer's configuration. That
is the right way round: relying on their field context to prevent a double count
would be relying on a setting nobody checks.

An epic worth £40k and its five stories at £8k each are **one piece of value and
six rows**. Summing both reports £80k — the subtask double count of ADR 0024,
one tier up, and with money on it.

So `orgConfig.valueFromHierarchy` defaults to **1**. Jira levels its issue types:
subtask −1, story and task and bug 0, epic 1, and a site with a higher tier puts
initiatives and themes above that. One means epic and everything above it.

**A level rather than a list of type names**, for the reason `countedTypes`
defaults to empty: naming types means naming them per site, and a site that adds
"Initiative" above Epic would silently stop counting the tier it cares most
about. `hierarchyLevel` is a field Jira already publishes on every issue type,
and the deprecation notice that once threatened it was cancelled and was about
`issueLinks` rather than this.

**An issue with no recorded level is counted.** Every dataset written before
levels were captured carries none — including this repository's own sample
bundle, whose value sits on stories — and reading absence as "below the line"
would zero them all.

## Three ways this tile is empty, and three sentences

The value tile had one sentence for every empty state, and on Forge it was
always the wrong one. It now says which:

- **Nothing carries a value.** The field is there and nobody has filled it in.
- **Nothing that carries one counts.** Every priced item sits below the level —
  an epic's stories, say — and the sentence says so rather than implying the
  work was worthless.
- **The field is not on a screen.** *"For the field to be visible on issues, a
  Jira admin must first add it to screens."* The module cannot do that and no
  scope grants it, so the tile names the action and says plainly that the app
  cannot do it for them.

The third is the state **every installation is in on the day it upgrades**, and
it is the one a reader would otherwise take as "we delivered nothing of value".

## What it costs

**A major version upgrade and a forced reinstall for every tenant.** Declaring a
module always is. It is free today because there are no external installs and
expensive after the first — the same argument the `llm` module was added under,
and the reason this lands now rather than when someone asks for it.

**Business value reaches the calculator**, and that is a decision rather than a
field addition. It is the most commercially sensitive figure in the product. It
travels as a *number* with no label: `valueBasis` — the sentence explaining what
the number means — stays in `FREE_TEXT_FIELDS` and is refused at the door, so a
currency amount arrives with no issue key beside it and no basis. The calculator
stores nothing.

**A second implementation of the level rule**, in JavaScript, for the page. Same
arrangement as the working week and as `counted_issues`: change one, change both.

## What this does not do

**It does not roll a story's value up to its epic.** A story below the line
contributes nothing, rather than being added to its parent. Folding them up
would be a much stronger claim — that an epic's value *is* the sum of its
children's — and it would double-count the moment somebody prices both.

**It does not decide what an ask is for sequencing.** That is still open. The
value basis a sequencing comparison needs is `valueBasis`, which no Jira field
carries and which this record does not invent.

## What this rules out

**Creating the field through the REST API.** It needs Administer Jira.

**Writing values from the app.** Value is somebody's judgement, and a
`write:jira-work` scope to record it is a poor trade for saving an admin one
screen configuration.

**Matching the field by its display name.** A site's own "Business Value" field
is not this one.

**Counting value at more than one level**, by configuration or otherwise. The
line moves; there is only ever one of it.
