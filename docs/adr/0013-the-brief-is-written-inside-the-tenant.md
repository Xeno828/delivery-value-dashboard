# 0013 — The brief is written inside the tenant; only the file leaves

Roadmap item 3 sends the two views out on a schedule: *"Monday at nine, the
executive view to the leadership channel, the team view to the team's. Both
carry the narrative and the agent's written brief."* Everything before it either
ran on a reader's machine or handled numbers that had been stripped of text.
This is the first feature that takes customer issue text somewhere nobody is
looking, on a timer, with no human in the loop.

That is two questions, not one — who writes the brief, and who carries the file
— and they were nearly answered the same way.

## The brief is written by Forge LLMs, in Atlassian's runtime

`agent/SKILL.md` is an agent definition. It needs a model to execute it, and
nothing on a Forge schedule can execute one. The obvious answer is an API key,
a third-party endpoint and a declared egress — which would put every issue
title on this board through a provider the customer has no relationship with,
weekly, to produce a paragraph.

**Forge LLMs is the answer instead.** `@forge/llm` reached GA in July 2026 and
calls Atlassian-hosted Claude from inside a Forge runtime function with no
egress. The model reads the tenant's real issue titles and the brief is
genuinely written rather than filled in from a template — and the text never
crosses the boundary the customer already agreed to when they put the tickets
in Jira. It is declared as a module, `model: [claude]`, one per app.

The alternative that was rejected on its own merits is worth stating, because it
will be proposed again as a tightening: **project the issues before prompting**,
the way `service/app.py` does, so the model sees dates and status categories and
never a title. That projection exists to protect a boundary crossing. Inside
Atlassian's runtime there is no crossing to protect, and a brief written without
titles cannot say which piece of work is stuck — which is most of why anyone
reads it. The projection stays exactly where it is, guarding the calculator,
and does not spread to a place whose threat model is different.

### What this costs

Adding the module is a **major version upgrade**, which on this app means a
forced reinstall for every tenant rather than a silent upgrade. There are no
external installs today, so the cost is currently zero and becomes real the
moment there is one. It joins two other deferred major-version changes already
recorded in `forge/manifest.yml` — residency regions beyond EU/US, and the
permanent `*.run.app` hostname. If one is taken, all three should be considered
in the same breath.

It does **not** recover the *Runs on Atlassian* badge. Apps using Forge LLMs
qualify for it; this one is still disqualified by the calculator egress that
ADR 0008 accepted deliberately. Nothing about that trade has changed.

## The file leaves, and that is the crossing that remains

The self-contained HTML file carries issue titles by construction — that is what
makes it worth reading, and ADR 0001 is the reason it is a file at all. Mailing
it hands those titles to a mail provider. Forge has no SMTP, so this is a second
declared remote and a real egress, and it is the one boundary this feature
crosses.

It is the right crossing to make. The roadmap's own thesis is that the artifact
arrives in an inbox and opens without a login, against a market whose answer is
a dashboard URL nobody clicks. Delivering a link instead would keep the boundary
and lose the product.

Two alternatives were rejected:

**Slack.** *"The leadership channel"* reads literally as Slack, and a
self-contained file in Slack is an attachment nobody opens — so in practice it
becomes a summary plus a link, which is the dashboard URL with extra steps. The
egress is identical. Nothing is saved and the artifact argument is lost.

**Letting the calculator build the file.** It already receives the dataset, so
it looks like the natural place. It is the opposite: `clean_dataset()` *refuses*
free-text fields and says so in the response — *"issue text does not belong here
and was not stored"* — and `service/README.md` calls that projection the one
thing the boundary exists for. Rendering a brief there would invert the
service's entire argument to save one hop. The file is assembled in the Forge
runtime, which already holds the tenant's issues and the split build, and which
calls the calculator for figures exactly as the tile does today.

## The guard that matters more than either

A model writing prose over figures is a new way for this product to state a
number that no tool produced — the thing ADR 0005 exists to prevent, arriving by
a route ADR 0005 did not anticipate. Two failure modes are specific and both are
worse than a wrong paragraph:

**A softened refusal.** `CLAUDE.md` requires refusals printed verbatim, and the
closing clause — *the evidence is absent, not noisy* — is the entire point of
ADR 0007. A model asked to write readable prose around *"too little completion
history to sample from"* will paraphrase it into something that sounds like a
wide interval. **Refusal sentences are therefore inserted verbatim and are not
passed through the model at all.** Where a figure was refused, the brief carries
the refusal, not the model's account of it.

**A restated figure.** A model given the numbers will restate them, and a
restatement is a second copy that can disagree. Every figure in the brief comes
from the tool output by substitution, and the generated prose is checked against
that output before the brief is sent. Prose that introduces a numeral the tools
did not produce fails the check and the brief is not sent.

This keeps the existing contract rather than bending it. ADR 0005 says the tools
compute and the agent narrates; a narration that varies between runs over
figures that do not is exactly that contract, not an exception to it. The
seeded, reproducible Monte Carlo is untouched — `SEED` is fixed, trials stay at
20,000, and the numbers in two briefs generated from one dataset are identical
even when the sentences around them are not.

## What is still open

Per-tenant recipient configuration — which audience goes to which addresses —
does not exist and is not decided here. It is the same question item 3 raises
about where a customer records anything the product needs and Jira has no field
for, and it is the same question that leaves `intake.sequence` with no input on
Forge. Whatever answers one should answer both.

## Added when the trigger was wired: a scheduled send has no user

Wiring the handler turned up something this record did not anticipate, and it
changes what item 3 depends on.

**Scheduled triggers run with no user principal.** Every Jira call in
`forge/src/index.js` is `api.asUser()`, and all of them throw in a trigger. The
obvious repair is `asApp()`, and it is the wrong one.

Reading as the user is not an implementation detail here — it is the reason a
viewer of the panel can only ever see issues they could already see in Jira.
That is **roadmap item 5, permission mirroring**, holding for free because Jira
enforces it on every request the app makes on someone's behalf. Nothing in this
product establishes it any other way.

A scheduled brief has to read as the app. The moment that brief is mailed to a
list of addresses, the app is asserting that every recipient may see every issue
it can — an assertion with nothing behind it. The failure is quiet and it is the
bad kind: a brief that names an issue from a project the reader has no access to
looks exactly like a brief that does not.

So **item 3 depends on item 5**, and the roadmap does not say so — it lists item
1 as item 3's only dependency. That is an error in the plan rather than a
discovery about the platform, and the ordering was already right for a different
reason: item 5 is described there as the item most expensive to defer.

What follows from it, and is implemented:

- The trigger does **not** reach for `asApp()` to get past the missing user. It
  refuses, and one of the three sentences it refuses with is that no board is
  configured for it to read — which is true, and is the blocker that makes the
  rest unwritable rather than merely unsent.
- The panel's `asUser()` calls are untouched, and a test asserts both halves:
  the trigger's own body contains no `asUser()`, and the file still does
  everywhere else. Converting the file wholesale to `asApp()` to make the
  trigger work would pass a naive reading and fail that test.

The three blockers are checked before any Jira call, so a weekly run that cannot
deliver costs one invocation rather than a board of reads and a completion
nobody receives.

## Superseded in part: the app-level read was taken, deliberately

The addendum above said the trigger does not reach for `asApp()`, and for three
versions it did not. **It does now, and this records the reversal rather than
quietly contradicting it**, because a decision that changes without a reason
written down is one nobody can re-examine.

**What changed between the two positions is `restrict`.** When the addendum was
written, the app would have read a board with no user and mailed the result to a
list, with nothing anywhere checking that the recipients could see any of it.
[ADR 0014](0014-jira-sends-the-brief-and-the-read-only-rule-bends.md) put the
send through Jira, and every notification now carries
`restrict: {permissions: [{key: BROWSE}]}`. Jira drops recipients who cannot
browse the anchor issue. Who may *receive* a brief is now the platform's
decision rather than this app's claim.

**What is still true, and is the residual risk.** `restrict` filters against the
anchor issue, not against the issues named inside the message. A board whose
issues share one permission scheme is covered by that, and most do. A board
using issue-level security is not: a recipient who may browse the anchor and not
some other issue will still be told about the other. That is roadmap item 5 and
it remains open — this is a narrowing of the gap, not a closing of it.

**The panel is untouched, and that is the half worth protecting.** Reading as
the user is why a viewer can only ever see issues they could already see in
Jira, and every read the panel makes still does. The authority is now an
explicit parameter, defaulted to the user, so a read added without thinking is
added on the safe side; the scheduled path passes `'app'` at each call rather
than inheriting it from anything.

Two reads may never take it and a test says so by name: the permission check
behind the recipient editor, which asks whether *this reader* may administer the
project and would answer yes to itself as the app, and the connection probe.

That test exists because threading the mode through nine helpers introduced the
same bug twice in one sitting — `jira(as)` left in a function with no `as`,
which bundles cleanly, since a free variable is not a syntax error, and is a
`ReferenceError` the first time a tenant opens the page. It is checked
structurally now: every `jira(as)` must sit inside a function that declares one.
