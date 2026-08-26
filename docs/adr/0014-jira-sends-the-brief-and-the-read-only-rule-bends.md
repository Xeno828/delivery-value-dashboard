# 0014 — Jira sends the brief, and the read-only rule bends by allow-list

Roadmap item 3 needs three things it does not have: somewhere to record who
receives a board's brief, a way to send it, and a rule about who may change
that. This settles all three, and one of them costs a constraint this project
has held since the first commit.

## Jira sends the mail, so nothing leaves

ADR 0013 closed one of item 3's two boundary crossings by writing the brief with
Forge LLMs instead of a third-party model. It left the other open and said so:
mailing a file hands issue titles to a mail provider, Forge has no SMTP, and
that was going to be a second declared remote.

It does not have to be. `POST /rest/api/3/issue/{issueIdOrKey}/notify` sends
mail through the same machinery Jira already uses to tell someone their issue
was commented on. **The brief never leaves Atlassian.** Item 3 crosses no
boundary at all, which is not where this started.

Three properties of that endpoint decided the shape of everything below.

**Recipients are Jira identities, never email addresses.** The `to` object takes
`users` by `accountId`, `groups`, `groupIds`, and the issue's own
assignee/reporter/watchers/voters. There is no field for an arbitrary address.
So the app never holds an email address, the recipient config contains no
contact details, and a leak of that config discloses who is interested in a
board rather than how to reach them. An external transport would have required
the opposite.

**There is a `restrict` object**, taking `groups`, `groupIds` and `permissions`
such as `BROWSE`. Jira drops recipients who lack the permission at send time.
That is permission filtering enforced by the platform rather than asserted by
us — and it is the first thing in this product that pushes back on the item 5
dependency ADR 0013 identified. It is **partial**: it restricts against the one
issue the notification hangs off, not against every issue named in the brief. A
reader who may browse the anchor issue and not another is still told about the
other. Item 5 is not solved here and this record does not claim it is.

**No attachments.** Only `subject`, `textBody` and `htmlBody`. The
self-contained HTML file — the artifact, and the roadmap's whole thesis — cannot
travel this way.

That is the real cost and it is worth stating rather than absorbing. What ships
is the two views rendered as **static HTML in the message body**: the tiles, the
figures and the written brief, with no interactivity. Email clients strip
JavaScript regardless, so an interactive dashboard was never going to survive an
inbox; what is lost is the file a reader can save and reopen, not behaviour they
would have had. It still arrives in an inbox and opens without a login, which is
the part of the thesis that was doing the work. Delivering the actual file
remains available later, by the external transport this record declines to
build now, and it is a smaller decision once there is a reason for it.

## The read-only rule becomes an allow-list, not a memory

`CLAUDE.md` said every scope is read-only and `tests/test_service.py` asserted
it as `startswith("read:")`. Two scopes here are not:

| Scope | Why | What it does not grant |
|---|---|---|
| `send:notification:jira` | The send itself. There is no read-only way to send mail | No read or write of issue data. It cannot address anyone outside the site |
| `storage:app` | Where the recipient config lives — the app's own key-value store | No access to any Jira data whatsoever. It is the app's own shelf |

**The rule is not deleted, it is made explicit.** The test now holds a list of
permitted scopes in which every non-`read:` entry must appear with a written
justification, and any scope outside the list fails. That is the shape the file
already used for the read scopes, extended rather than invented — adding a scope
stays a deliberate edit with a reason, which is what the rule was protecting.

The argument for the original rule survives intact and is worth restating,
because it is the reason this is an allow-list and not a shrug: *an app that
asks for write access to close a deal is one whose consent screen stops a
security reviewer.* Neither scope here is write access to customer data.
`send:notification:jira` is the one a reviewer will look hardest at, and rightly
— an app that can email people is a spam vector in a way a read scope is not.
What answers that is not the scope list but the two facts above: recipients
cannot be addresses outside the site, and `restrict` lets Jira drop those who
should not receive it.

**Rejected: writing the config to a Jira project property.** It is the obvious
home — `orgConfig` already lives in one — and Jira would enforce the
project-admin permission on the write for us, which is better than checking it
ourselves. It needs a write scope into Jira to do it. Trading *no access to
customer data* for *narrow write access to customer data* to avoid implementing
one permission check is the wrong direction, and the check is a dozen lines.
Reading `orgConfig` from a project property is unaffected and stays exactly as
it is.

## Project admins decide who receives a board

A recipient list is a disclosure control: it decides who is told what is on a
board. It is not a display preference and it does not belong to whoever has the
page open.

**Project administrators**, checked against Jira's own answer — the app asks
`/rest/api/3/mypermissions` for `ADMINISTER_PROJECTS` and believes what it is
told, rather than inferring from group membership. A viewer without it sees the
active configuration and cannot change it; showing nothing would make a
misconfigured board indistinguishable from an unconfigured one, and the person
best placed to notice is the one reading the panel.

Site admins were the first instinct, and the app already has a `jira:adminPage`
to hang it on. Rejected because it puts one person between every team and their
own board's recipients, which is how a feature stays switched off. Project admin
is the smallest authority that can answer *should this person be told what is on
this board*, and it is per project, which is the granularity the config has.

## What this does not decide

Which board a scheduled run reports on is still unanswered, and it is still the
blocker that makes the rest unwritable. The recipient config resolves *per
board*, so the two are related but not the same: this record says who a board's
brief goes to, not which boards a weekly run walks.

## Added when the send was built: one decision is still not taken

The send works and is proved. What is not written is the read in front of it,
and that is deliberate rather than unfinished.

Composing a brief means reading the board, and every read in `forge/src/index.js`
is `api.asUser()`. A scheduled run has no user to be, so those reads have to
become `asApp()` — which is exactly what ADR 0013's addendum declined, on the
grounds that reading as the user is *why* a panel viewer can only ever see
issues they could already see in Jira.

**This record moves that position part-way and not all the way.** `restrict`
means Jira now drops recipients who may not browse the anchor issue, so the
app's claim about who may *receive* a brief is checked by the platform rather
than trusted. What is still not checked is what the brief *says*: the anchor's
BROWSE permission gates delivery, not the issues named inside the message. A
board whose issues share one permission scheme — most of them — is covered by
that. A board using issue-level security is not.

So the trigger stops before the read, with three sentences saying so, and the
whole path after it — compose, render, payload, send — is written and tested
against stubs in `forge/src/compose.js`. Turning it on is one line and a record
saying why. Writing it quietly would have spent a security property inside a
commit about email formatting, which is how properties get spent.

**`forge/src/compose.js` exists for that reason and is worth keeping that way.**
`index.js` imports the Forge SDK and cannot be loaded outside Atlassian's
runtime, so anything left in it is provable only by deploying and watching a
tenant. The code that decides what reaches somebody's inbox is not code to find
out about that way, so the model and the send are injected and the tests supply
stubs for both.

## Added when it first ran: the site has to allow outgoing mail

`send:notification:jira` gets the app through the API gate. It does not make
the site send anything. Proved on 2026-08-26, when every stage of the brief
worked against a real tenant and the final call came back:

```
Jira refused the notification with 403. It said: Outgoing emails disabled.
```

That is a **site setting**, not a scope, not a permission scheme and nothing an
app can declare. A tenant with outgoing mail switched off — the default on many
sandbox and dev sites, and a deliberate choice on some real ones — installs this
app, configures recipients, and gets nothing, weekly, for ever.

Two consequences.

**The app must quote Jira rather than paraphrase it.** A bare *"Jira refused the
notification with 403"* is indistinguishable between mail being disabled, the app
user lacking Browse on the project, and a scope that was never granted. All three
have different fixes and only the body says which. `sendBrief` captures
`errorMessages` and puts them in the log, capped and newline-stripped. That one
line turned a fourth round of guessing into an answer.

**It belongs in the listing, not in a support ticket.** Requiring outgoing mail
is a precondition a buyer can check before installing, and the kind of thing that
otherwise surfaces as *"the app does not work"* a week after purchase. It goes
next to the egress declaration Marketplace review already reads.
