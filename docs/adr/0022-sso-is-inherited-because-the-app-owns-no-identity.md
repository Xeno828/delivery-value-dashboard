# 0022 — SSO is inherited, because this app owns no identity

Roadmap item 6 lists SSO beside the audit log and data residency, in phase 3,
*"make it defensible"*. It is the last of the three untouched.

There is nothing to build. That is the finding, and it is not an excuse — it is
a claim about the product's shape that can be falsified, so this record says
what would falsify it and the security suite checks each one.

## Why there is nothing to build

**This product has no login.** Every surface it has belongs to somebody else's
authentication:

- **The panel** is a Forge module inside Jira. The person reading it was
  authenticated by Atlassian before the app was invoked, and `context.accountId`
  is Atlassian's answer rather than ours. Whatever authentication policy the
  customer's organisation enforces — an external IdP, SAML, enforced two-step —
  governs it completely, and the app neither participates in it nor can weaken
  it.
- **The calculator** authenticates *callers*, never people. Its two modes are a
  shared secret and Atlassian's own invocation token, it serves no HTML, and
  there is no page anybody could sign in to. Nobody has an account on it.
- **The built file** is a file. There is nobody to authenticate and nothing to
  authenticate them against, which is the whole of ADR 0001's threat model: it
  gets emailed, and whoever has it has it.

So SSO here is the same shape data residency turned out to be — satisfied by
where the thing runs rather than by anything this repository wrote. The
difference is that residency arrived as a side effect of a decision (ADR 0012)
and this arrived by never having built a login in the first place.

## What would falsify it, and is therefore checked

A claim like this is worth what enforces it. `sso_checks()` in
`tests/security.py` asserts the app must *not* have each of these:

**No Atlassian credential, ever.** No password, API token, `Authorization`
header or Basic auth anywhere in `forge/src`. This is not a preference: it is a
hard Marketplace security requirement, and the reason given for it is exactly
the reason SSO exists — an app holding a user's API token makes its REST
activity indistinguishable from the customer's own, and holds a credential no
IdP can see and no administrator can revoke centrally.

**No session of its own.** No cookie, no minted token, nothing that would
outlive Atlassian's own answer about who this is.

**No authentication module in the manifest**, and every Jira read through
`asUser()` or `asApp()` — platform authority that this app cannot export,
replay or hold.

**No environment credential in the installed app.** `process.env` appears in
`index.js` exactly once, in a comment explaining why reaching for
`process.env.CALCULATOR_URL` was wrong (ADR 0012). The check reads code and not
prose, because an earlier version of this same suite failed on a comment saying
*not* to do the thing — the identical mistake it made about `dist-upgrade` in
the Dockerfile.

## The one path that bypasses an IdP, named rather than hidden

`scripts/fetch_delivery_data.py` can authenticate with a **personal API token**
out of `JIRA_TOKEN`. That is a credential no IdP stands in front of and no
administrator can revoke centrally — precisely the thing the Marketplace rule
above forbids an app from holding.

It is not in the app. It is an operator's own tool, run on their own machine,
against their own account, to produce a file. The property that matters is that
it stays there, so the suite asserts the token path exists only in `scripts/`
and that nothing in `forge/` reads an environment credential at all.

`scripts/jira_auth.py` exists to offer the alternative and already argues it:
the OAuth grant is *"consented, revocable, refreshable"* and scoped, where a
personal token is none of those. This record does not remove the token path —
it is the only route that works with no app registration, and that is worth
keeping for the person evaluating the product — but if this ever ships as a
supported route rather than an operator's convenience, OAuth is the one to
support and the token path is the one to drop.

## What this does not claim

**Not that the product is compliant with anything.** It says the app introduces
no authentication of its own, so the customer's own policy is not weakened by
installing it. That is a smaller and more defensible statement than "supports
SSO", which invites the reader to imagine a configuration screen.

**Not that access control is solved.** Authentication is who you are;
authorisation is what you may see, and that is roadmap item 5, where three
exposures are answered by accepting a disclosure and naming it
([ADR 0018](0018-permission-mirroring-holds-by-accident-and-where-it-does-not.md),
[0019](0019-a-recorded-row-is-a-fact-about-the-board.md),
[0020](0020-the-anchor-issue-is-the-brief-s-access-control.md)). SSO being free
says nothing about those.

**Not that item 6 is finished as sold.** Residency is done, the activity log is
built and is explicitly not a compliance record
([ADR 0021](0021-the-audit-log-is-operational-and-says-so.md)), and this piece
required no work. A buyer asking about all three gets three honest answers, two
of which are shorter than they expect and one of which is a caveat.

## What this rules out

**Building a login.** Any screen this product puts in front of a person to
authenticate them is a credential outside the customer's IdP and a step
backwards from where it stands today.

**Storing an Atlassian credential in the app**, under any framing, including
"just for the scheduled trigger". `asApp()` exists for that and holds nothing.

**Answering a security questionnaire's SSO question with "yes".** The honest
answer is that the app has no separate identity and inherits the organisation's
authentication entirely — which is a better answer, and a different one.
