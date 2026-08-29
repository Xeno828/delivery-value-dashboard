# 0021 — The audit log is operational, and says so

Roadmap item 6 lists an audit log, and `docs/roadmap.md` has said since it was
written that it *"still depends on item 5 — a log over data with no permission
model records the wrong thing convincingly."*

That dependency is wrong twice, and finding out which way took one afternoon of
reading Atlassian's documentation rather than the weeks the roadmap allots.

## The dependency was wrong

**Most of an audit log never depended on item 5.** The events an administrator
actually asks about are *when did the recipient list change, who changed it, and
did last Monday's brief go out?* Every one of those is an act of **this app**,
with an authority already established and already enforced — a project
administrator, checked by `permissions.js` and re-checked on the write, or the
scheduled trigger, which has no user and says so. None of them is a figure
derived from issues. The roadmap's sentence is about logging *access to data*,
which is a different feature and the one part that genuinely would have needed a
permission model.

**And the real constraint was never written down.** Two facts settle the shape
of this and neither appears anywhere in the roadmap:

- **Jira will not accept an audit record from an app.**
  `GET /rest/api/2/auditing/record` is read-only; there is no POST. So there is
  no log this app can write to that it cannot also alter.
- **Reading Jira's own audit log needs the *Administer Jira* global
  permission**, which [ADR 0020](0020-the-anchor-issue-is-the-brief-s-access-control.md)
  refused hours earlier for a different feature and refuses again here.

## The decision

**Build the operational log. Say plainly that it is not a compliance record.**

`forge/src/audit.js` holds four events — `recipients.saved`,
`recipients.cleared`, `brief.sent`, `brief.refused` — in app storage under one
key, with a bound. The recipients tile shows the recent tail to administrators.

The honesty is not a caveat bolted on; it is the reason the record exists. An
app writing its own log into its own storage, which it can also rewrite,
best-effort, is **not tamper-evident**. A tile presenting that as an audit trail
would be the most convincing wrong thing in this product — and this repository's
whole argument is that its numbers can be trusted, which is worth nothing if one
of them is a claim about its own integrity. So the tile says it, `auditNote`
says it, and `tests/test_service.py` asserts both still do.

### What the entries hold, and what they deliberately do not

**Counts, flags and field names — plus one identity, the actor.** That one is
unavoidable: an entry without it records that something happened and not who did
it. `problemsInAuditEntry` refuses anything else, so a recipient's account id
cannot reach a store that grows without bound.

The split is deliberate and worth stating, because the other choice is
defensible. *What the recipient list is* stays on the tile, where anybody who
can open it reads the current answer. *When it changed and who changed it* is
what this answers. Keeping every id ever added would grow a store of identities
to answer a question already answered, and it can be decided later without
unpicking this.

**A closed set of events.** An entry whose meaning nobody wrote down is read by
guessing, which is the opposite of an audit log's purpose.

**The bound is cumulative and visible.** `droppedTotal` lives in the store, not
in the answer to one read, so a reader arriving after the ten-thousandth event
is told nine thousand rows are gone rather than shown a tidy thousand. **An
audit log that silently forgets is worse than none**, because the absence of a
row reads as the absence of the event.

**Writing never fails the act it records.** A save that succeeded and an audit
write that failed must not report the save as failed. That is also, honestly,
part of why this is operational rather than compliance: a log that can be
dropped is a log that can have gaps nobody knows about.

**Administrators only.** It carries the account id of whoever changed a
recipient list, and `canEdit` — Jira's answer, already asked on that route — is
the right gate for it.

## What this does not do, and what would

**It is not the thing a security review is asking for.** That question is
*"can you show me a record you could not have falsified?"*, and the answer here
is no. The route that would answer it is **emitting events to the customer's own
sink** — a SIEM or webhook they control, outside this app's reach once sent. The
app already does declared egress to the calculator, so the mechanism exists;
what does not exist is the configuration, the delivery guarantees, and the
decision to send customer events off-platform, which is a bigger crossing than
anything in ADR 0013 and deserves its own record.

**It does not log access.** Who *read* which figures is unlogged, and that is
the part the roadmap's dependency was actually about. It is also the part that
would newly store user identity against data, which is worth wanting for a
reason rather than by default.

## What this rules out

**Administer Jira**, again, and for the second time in a day. Reading Jira's
audit log would need it and this app does not have a use for it that survives
the question *what else does that grant?*

**Calling this an audit log without qualification** — in the tile, the note, the
README or a Marketplace listing. It is an activity log. The word *audit* is what
a buyer's security team reads as a promise.

**Trimming quietly.** The bound may change; its visibility may not.
