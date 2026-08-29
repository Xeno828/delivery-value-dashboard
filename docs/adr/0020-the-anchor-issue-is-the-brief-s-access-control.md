# 0020 — The anchor issue is the brief's access control, and impersonation is deferred

[ADR 0018](0018-permission-mirroring-holds-by-accident-and-where-it-does-not.md)
surveyed roadmap item 5 and found three exposures.
[ADR 0019](0019-a-recorded-row-is-a-fact-about-the-board.md) answered two of
them — the durable series and the forecast log — by deciding a recorded figure
is a fact about the **board**. This answers the third, the same way, and records
the research that decided it so nobody has to do it twice.

## The exposure, stated exactly

The weekly brief counts issues. `restrict: [{ key: 'BROWSE' }]` makes Jira drop
recipients who cannot browse **the anchor issue** — and only that one, because
`POST /rest/api/3/issue/{issueIdOrKey}/notify` hangs off a single issue. So a
recipient who may browse the anchor and not some other issue on the board is
still sent aggregates that counted the other. ADR 0014 recorded this gap when
the send was built and did not claim to solve it.

What is disclosed is narrower than that sentence suggests, and checking it was
worth doing. Every section in `sectionsFor` is counts, dates and units, and
`briefMessages` hands the model **only those figures**. No issue key and no
summary reaches a recipient, and none reaches the model either. The disclosure
is an aggregate: *"12 of 22 items finished"* over a set the reader may not see
all of.

## What was investigated, and what it found

Three routes, and the second of them corrects something this repository has
twice written down as impossible.

**Restricting against every issue the brief counts — not available.** The notify
endpoint notifies *about* an issue; there is no set form and no project form.
This is structural and ADR 0014 already says so.

**Checking each recipient's permission — available and worse than the problem.**
`POST /rest/api/3/permissions/check` takes an `accountId`, so the app could ask
whether a given recipient may browse given issues. Two things kill it. Checking
permissions for **another** user requires the *Administer Jira* global
permission, which is an enormous grant beside the read-only rule this app keeps
and would be the single largest thing in any security review of it. And the
endpoint's own documentation warns that a user shown as having a permission in
project context *"may not have the permission for any or all issues"* — so
having paid that price, the answer would still not be the one being asked for.

**Composing per recipient — possible, and this repository has said twice that it
is not.** ADR 0018 called it *"a different product"*. That was wrong. Forge
supports **offline user impersonation**: `api.asUser(accountId)` calls an
Atlassian API as any user, enabled by declaring scopes as a map with
`allowImpersonation: true`, and the documented motivating case is impersonating
a user from a scheduled trigger — which is precisely the brief's situation. A
brief composed as each recipient would mirror permissions exactly, with no
aggregate leak at all.

Two constraints, and one unknown, all of which are the reason it is deferred
rather than the reason it was dismissed:

- **An app cannot impersonate a user who does not have access to the app**, and
  for an app not distributed through the Marketplace that means app
  contributors only. It cannot be validated against an ordinary recipient on the
  development site this product currently runs on.
- **Every send multiplies.** One facts pack and one forecast per recipient
  rather than per audience, on a scheduled trigger that must not be expensive.
- **Unverified:** whether `asUser(accountId)` works inside a Forge scheduled
  trigger's own runtime. The documentation describes it for *events*, where the
  account id comes off the payload, and for *remote* backends exchanging a
  system token for a user token. The trigger case needs a spike, and this record
  does not assume it.

## The decision

**The anchor issue is the brief's access control, and the residual aggregate
leak is accepted.**

That is not a new mechanism. It is naming the one that already exists: the
administrator names the anchor, Jira enforces browse permission on it at send
time, and ADR 0014 already tells them what they are choosing —
*"whoever may browse this issue may receive the brief, so choose one whose
audience is the audience."* This record makes that the stated permission model
rather than an incidental property of how the send works.

The leak that remains is a recipient who may browse the anchor and not
everything counted, receiving aggregates. It is accepted for the reasons
ADR 0019 accepted the same thing about the stores, and one more:

- **It is a count, never an identity.** The same property ADR 0015 and ADR 0017
  were built to preserve.
- **On the common configuration it discloses nothing**, because project-level
  permissions mean anyone who can browse the anchor can browse the board.
- **It is strictly weaker than the exposure already accepted.** A recipient of
  the brief has been vouched for twice — an administrator put them on the list,
  and Jira confirmed they can browse the anchor. A panel reader has been vouched
  for once. Answering this one more strictly than the stores would be incoherent.

**Impersonation is deferred, not rejected**, and the manifest declares no
`allowImpersonation` today. `tests/test_service.py` fails if one appears without
this record being revisited — the same shape as the non-read scope allow-list.

## What would change the decision

Written down because the answer is contingent, and the next reader should be
able to tell whether the ground has moved.

**If the brief ever names an issue.** The moment a key or a summary reaches a
recipient, this stops being an aggregate leak and impersonation stops being
optional. The check that the brief names no issue is in `tests/test_service.py`
for exactly this reason.

**If a customer runs issue-level security and says so.** This product cannot ask
Jira whether a project uses it. A customer who does, and who cares, is a reason
to build the impersonated path for them rather than a reason to have built it
for everyone.

**If the app is distributed through the Marketplace.** That removes the
contributor-only restriction and makes the impersonated path testable against a
real recipient, which is the thing that cannot be done today.

## What this rules out

**Administer Jira, for any reason short of a separate decision.** It is the
largest grant discussed anywhere in this repository and it was considered here
only to be refused.

**Sending the brief to recipients Jira did not confirm.** `restrict` stays on
every send, constant and not configurable. ADR 0014.

**Claiming item 5 is finished.** Three exposures are now answered — two by
ADR 0019 and one here — and every one of them was answered by accepting a
disclosure and naming it. That is a coherent position and it is not a permission
model. The roadmap's 5–8 weeks was for building one.
