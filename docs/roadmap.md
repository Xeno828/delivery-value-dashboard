# The commercial roadmap

Four places in this repository say *"roadmap item 1"*, *"roadmap item 6"*, and for
two years none of them pointed at anything. The roadmap lived outside the
repository, which meant every session that tried to progress it began by asking
where it was. This file ends that.

**The prose original is an artifact — *From File to Product*, drafted 17 August
2026, revised 19 August, against v1.12.3.** It carries the argument: why the
Marketplace and not a desktop store, why the service produces the file rather
than replacing it, what the plan will not do and what that refusal costs. Read
it for the reasoning. This file is the part the code needs: the numbering, and
what is true today.

## The numbering, which is load-bearing

Seven numbered items, nine features — item 6 is three. That reconciliation
matters because a reader who counts headings gets seven and concludes the
references are wrong.

| # | Item | Phase | Size at planning time | State |
|---|---|---|---|---|
| 1 | OAuth app on the Marketplace | 1 — make it connectable | 4–6 wk | **Done** |
| 2 | Organisation configuration | 1 — make it connectable | 2–3 wk | **Done** |
| 3 | Scheduled delivery of the two views | 2 — make it arrive | 3–4 wk | **Done** — delivered 2026-08-26 |
| 4 | Durable sprint history | 3 — make it defensible | 3–4 wk | **Done** — 2026-08-29 |
| 5 | Permission mirroring | 3 — make it defensible | 5–8 wk | **First pass done** — three exposures answered by accepting and naming them; no permission model built |
| 6 | SSO, audit log, data residency | 3 — make it defensible | 6–10 wk | **Done** — residency, activity log and SSO, all 2026-08-29; two of the three needed no engineering |
| 7 | Cross-team roll-up and intake sequencing | 4 — sell it upward | 4–6 wk | **Roll-up done** 2026-08-30. Sequencing has a size, a value and a basis; it has no way to read an *ask* |

Sizes are engineering weeks at planning time, never reconciled against actuals —
the same caveat the dashboard puts on its own value figures. They are a floor.
Summed: 27–41 weeks.

**The order is by dependency, not by score.** The product refuses to compute a
priority score (ADR 0004), so ranking its own roadmap with one would be
incoherent. Where two items could swap, the original states why they do not.

## What is done, and how it differs from what was planned

**Item 1 shipped as both routes, not one.** The roadmap called the Forge/Connect
choice "the one genuinely open decision in phase 1". It resolved as *both*: OAuth
2.0 3LO in `scripts/jira_auth.py` for pulling your own board with no app
registration, and a Forge app for the tenant install. `forge/README.md` has the
comparison. The Forge app is at 4.0.0, installed, reading the tenant's own boards
over `forge/bridge/bridge.js`.

**Item 2 shipped inverted, and it was the better shape.** The plan was to
*expose* assumptions that were baked into the code. What landed instead resolves
them once, at the point the data is produced, and writes them into the dataset as
`orgConfig` — so the page, the three tools that read it and the live server all
read one resolved answer rather than each opening a config file. A config read
separately by each consumer is a third opinion arriving by a different route.
`docs/organisation-config.md`, and the constraint in `CLAUDE.md`.

**A third of item 6 arrived early, as a side effect of item 1.** Putting the
calculator on Cloud Run made data residency ours rather than Atlassian's — which
the roadmap had at weeks 10–24. It landed better than "pinned per region": Forge
resolves a region-specific `baseUrl` per installation from the customer's own
residency setting, so the app never routes tenants itself and there is no routing
logic to get wrong. ADR 0012, `docs/hosting-the-calculator.md` §5.

**The other two thirds landed on 2026-08-29, and neither cost what this file
said it would.** Item 6 was priced at 6–10 weeks for three features. One arrived
as a side effect, one needed a day, and one needed nothing built — which is
worth saying plainly rather than reading as three things going quickly.

*The audit log.* This file said it *"still depends on item 5 — a log over data
with no permission model records the wrong thing convincingly."* That was wrong
twice. **Most of an audit log never depended on item 5**, because the events an
administrator asks about are acts of this app with an authority already
enforced, not figures derived from issues. And the constraint that actually
shapes it was never written down here — **Jira's audit API is read-only**, so
there is no log this app can write to that it cannot also alter, and reading
Jira's own needs *Administer Jira*. So what exists is an **activity log**, and
it is called that because that is what it is: written by the app into its own
storage, not tamper-evident, and saying so on the tile.
[ADR 0021](adr/0021-the-audit-log-is-operational-and-says-so.md). The record a
security review actually wants — one the app could not have falsified — needs
events emitted to a sink the customer controls, and is unsized.

*SSO.* Nothing to build, and that is a claim rather than an excuse: this product
owns **no identity**, so the customer's own authentication policy governs it
entirely. [ADR 0022](adr/0022-sso-is-inherited-because-the-app-owns-no-identity.md)
lists what would falsify that and `tests/security.py` checks each one.

## Item 3 — how it landed, and what it moved

Delivered 2026-08-26, and kept here rather than deleted because the two things
it changed about the *plan* are not recorded anywhere else.

*"Monday at nine: the executive view to the leadership channel, the team view to
the team's. Both carry the narrative and the agent's written brief."*

It reads that way now, with one substitution the plan did not anticipate: there
is no channel and no mail provider. Jira sends the brief itself, as a
notification about an anchor issue, so the audience is whoever may already
browse that issue. ADR 0014 has the argument and the two non-read scopes it
cost. `CHANGELOG.md` 1.25.0 through 1.34.0 is the running account.

**One correction to the plan, found by wiring it.** The roadmap gives item 3 a
single dependency, item 1. It also touches **item 5** — narrowed since, not
resolved. A scheduled trigger runs with no user principal, so it cannot read
Jira as the viewer the way the panel does — and reading as the viewer is exactly
what makes permission mirroring hold for free today. A brief composed by the app
and mailed to a list asserts that every recipient may see every issue the app
can, which nothing here establishes. ADR 0013 has the detail. Sending through
Jira narrowed it — the notification is delivered against an issue, so a
recipient who cannot browse it gets nothing — but it did not close it: the
*content* is still composed against everything the app can read. The ordering
was already right; the dependency was not written down.

**The egress it nearly had.** It is the first item that sends customer issue
text anywhere, and it nearly sent it twice: the brief is written by a model, and
the obvious way to do that is an API key and a third party. Forge LLMs
(`@forge/llm`, GA July 2026) runs Atlassian-hosted Claude inside the platform
with no egress, so the model reads the tenant's issue titles without them
leaving the boundary the customer already agreed to. ADR 0013 records both — the
crossing that was avoided and the one that remains.

## What is open, and what the order says

Nothing is picked here. The order is by dependency, and the dependencies are
these:

- **4, durable sprint history** is **done** — see the three parts below.
  **5, permission mirroring** is started: [ADR 0018](adr/0018-permission-mirroring-holds-by-accident-and-where-it-does-not.md)
  surveys where reading as the viewer stops being enough and fixes none of it,
  which for an item whose failure is a disclosure is the right first move. It
  found three exposures, **two of them created by item 4** — the series store
  and the forecast log both keep figures computed from whichever viewer's read
  produced them and show those figures to every later reader.
  [ADR 0019](adr/0019-a-recorded-row-is-a-fact-about-the-board.md) answers the
  first: a recorded row belongs to the **board**, so the aggregate leak is
  accepted and named, a narrow view may no longer write a row that claims to be
  the board's, a wider view repairs one, and a reader whose own sight is
  narrower is told which of the two they are looking at. The **forecast log**
  is answered the same day and not the same way: a claim is made once and
  resolved once and never rescored, so the gate that matters there is
  *resolution* — a narrow view leaves a claim pending rather than scoring a
  good forecast wrong with no second chance. The **brief** is answered by
  [ADR 0020](adr/0020-the-anchor-issue-is-the-brief-s-access-control.md): the
  anchor issue *is* its access control, administrator-chosen and Jira-enforced,
  and the residual aggregate leak is accepted for the same reasons as the
  stores'.

  **That is a first pass, not the item.** All three exposures were answered by
  accepting a disclosure and naming it, which is a coherent position and is not
  a permission model — and the 5–8 weeks was for building one. The research
  that would start it is in ADR 0020: Forge supports offline user
  impersonation, so composing a brief per recipient is possible and was twice
  written down here as impossible. It is deferred, with the three things that
  would change that decision written down and a test that fails if the
  manifest quietly enables it.
- **7**'s roll-up half is **done and wired**: `rollteams:<project>` is offered as
  *"— all boards —"*, names the boards it covers, and refuses to forecast
  ([ADR 0023](adr/0023-a-cross-team-rollup-spans-what-the-reader-can-see.md)).
  **Sequencing is half-answered.** The product question — *what is an ask?* —
  got its first answer on 2026-08-29: an ask is an **issue type**, at story
  level or epic level. Acting on that turned up a bug older than the question
  (subtasks were counted as items, [ADR 0024](adr/0024-a-parent-and-its-subtasks-are-one-piece-of-work.md))
  and produced the reader's own type filter, a declared **Business Value** field
  ([ADR 0025](adr/0025-the-app-declares-a-business-value-field.md)) and the
  two-pool split ([ADR 0026](adr/0026-items-and-value-are-counted-from-two-different-sets.md)).
  So an ask now has a **size** and a **value** — and, since 2026-08-30, a
  **value basis**: a second declared field, free text, on the argument that
  nothing computes on a basis and nothing may
  ([ADR 0027](adr/0027-a-value-basis-is-prose-carried-to-a-reader.md)). An
  enumerated basis would have been one join away from the weight
  [ADR 0004](adr/0004-no-priority-score.md) refuses.
  **What is still missing is the ask itself.** An ask is a document with a
  problem, a success measure, a needed-by date, a size and a value with a basis;
  an epic carrying a value and a basis has two of those six, and nothing in a
  Jira site marks an issue as a request being weighed against others. The
  `sequence` resolver still refuses and now names only that. Product decision,
  not a coding task.
- **7** was recorded as blocked on both 4 and 5, and was wrong about each.
  [ADR 0023](adr/0023-a-cross-team-rollup-spans-what-the-reader-can-see.md) has
  it. **Intake sequencing is built** — `intake.sequence()`, a CLI, a service
  route, a renderer and tests — and refuses on Forge for a reason that has
  nothing to do with items 4 or 5: nobody has decided **what an ask is inside
  Jira**, and there is no issue type that means one. **The cross-team roll-up**
  did depend on item 5 in shape, and item 5's first pass answers it: the panel
  reads as the viewer, so a board they cannot browse never arrives, and the
  roll-up **names the boards it covers** because this app cannot know which ones
  it is not seeing. It reports facts and refuses to forecast — pooling several
  teams' throughput assumes they are interchangeable, and `team_slice` would
  have returned one team's contexts under a heading claiming the programme.
- The **audit log** in item 6 was recorded here as blocked on **5** alone, and
  was not — see the correction above and
  [ADR 0021](adr/0021-the-audit-log-is-operational-and-says-so.md). The
  operational half is built. The half a security review is asking for —
  a record the app *could not have falsified* — needs events emitted to a sink
  the customer controls, and is unsized.
- **SSO**, the other third of item 6, needed nothing built.
  [ADR 0022](adr/0022-sso-is-inherited-because-the-app-owns-no-identity.md):
  this product owns **no identity** — the panel is opened by somebody Atlassian
  already authenticated, the calculator authenticates callers rather than
  people, and the built file is a file. The customer's own authentication
  policy governs it entirely and the app cannot weaken it. What that record
  adds is the list of things that would falsify the claim, each one now checked
  in `tests/security.py`, and the one path that bypasses an IdP — the fetcher's
  personal API token — named and kept out of the app.

So 4 and 5 each unblock 7, and only 5 also unblocks the audit log. That is a
dependency fact, not a recommendation — where two items could swap, the choice
is the reader's, and the original states why the sequence it gives is the one it
gives. What this file will not do is score them; that is the same refusal the
product makes about competing asks (ADR 0004), and a backlog is not a better
place for it than a roadmap.

The one figure worth carrying into that choice: **item 5 is the item the
original itself flags as under-estimated**, at 5–8 weeks and untested. Plan
against the upper bound.

## Item 4, in three parts

The changelog says *"roadmap item 4a"*, and this is where that letter is
defined. **It is a decomposition of the work, not a change to the numbering.**
The seven items and nine features above are unchanged and the artifact does not
name these parts — they are the order [ADR 0015](adr/0015-a-durable-series-stores-what-jira-forgets.md)
arrived at once the item was looked at closely, and they are lettered only so
that a changelog entry can say which piece it delivered.

| | Part | State |
|---|---|---|
| 4a | Record the figures a later re-derivation can disagree with | **Done** — 2026-08-29 |
| 4b | Lift the six-sprint window | **Done** — 2026-08-29 |
| 4c | The forecast log | **Done** — 2026-08-29; wired on both transports, waiting on horizons |

**4a is done and in a tenant.** A board's sprint rows are recorded when the app
sees them and re-derived, labelled as such, when it was not there; a recorded
row and Jira's answer today are shown side by side where they disagree, with
neither winning. `forge/src/series.js` decides what is kept, `metrics.py`
decides what is shown, and the store holds nine numbers and a sprint name —
which is what keeps item 4 off item 5's critical path. `CHANGELOG.md` 1.36.0
through 1.40.1.

**4b is the six-sprint window**, and it was deliberately second. It was the
obvious first slice — the hardcoded `6`s are silent truncations that
`CLAUDE.md` already forbids — and ADR 0015 deferred it behind the store because
a twelve-month trend is where the hazards the store exists for have had the most
time to happen. The window is a parameter; the footing under it was not.

**Done.** `trendSprints` travels inside the resolved config like every other
assumption, defaulting to six and bounded at forty because each sprint in the
window is a sprint's worth of issues fetched. The three producers that kept a
six of their own now read one answer. Both truncations are named rather than
implied: a board with more sprints than the window says so, and a *recorded*
sprint older than the window is no longer reported as **"no longer offered by
this board"** — which it never was, and which the trend said about four sprints
of any board with a store deeper than its window.

**4c is the forecast log**, and it is the only part whose subject is
*genuinely* irrecoverable: nothing in Jira records that this product once said
*"85% confidence of nine items by the 14th"*. `score_calibration()` has been
able to read such a file since the tools were written and nothing has ever
produced one, so the forecaster cannot be scored against its own history.

**Started.** [ADR 0017](adr/0017-a-forecast-is-logged-as-a-count-not-a-promise.md)
settles what a logged claim is, and it is not the claim a slide would quote:
*"the probability all of it lands by the 14th"* cannot be resolved without
recording which issues were outstanding, and recording issue keys would put
customer-identifiable data in an app-level store and put item 4 behind item 5's
permission model. So a forecast is logged as its **capacity** claims — *"p%
confidence of at least N items by D"* — which resolve from a count and hold no
issue identity. The functions and their tests are in `agent/tools/forecast.py`
beside the scorer that has been waiting for them.

**Wired.** A published forecast writes its claims to the board's log — app
storage on Forge, a git-ignored file over loopback, one key per board and no
new scope. A **what-if** writes nothing: the tile's sliders are not a
prediction anybody made, and `claim_id` would have let one overwrite the day's
real forecast. Claims resolve when their horizon passes, against the latest
date each transport's data can speak to, and the tile prints the scorer's own
sentence — including its refusal, because *"too few resolved forecasts"* and
*"badly calibrated"* are different statements.

The part nobody can hurry: a log needs ten **resolved** forecasts before it
scores anything, and a claim resolves only after its horizon. On a fortnightly
board that is a few weeks of ordinary use before the first Brier score exists.
Until then the tile says how many are waiting, which is the honest state.

## What stands between here and a Marketplace listing

Asked on 2026-08-30 and answered from the repository rather than from memory,
because two of these are not on the numbered list at all.

**Engineering.** One thing: **sequencing needs a way to read an ask out of
Jira**. The value basis it also needed was answered on 2026-08-30
([ADR 0027](adr/0027-a-value-basis-is-prose-carried-to-a-reader.md)); what is
left is that no issue is marked as a request being weighed against others, and
the problem, success measure and needed-by date have no field either. That is a
product decision before it is a build. Everything else either works or is a
decision rather than a build. Item 5 is a first pass — all three exposures
answered by *accepting a disclosure and naming it*, which is a coherent position
and is not the permission model its 5–8 weeks was for.

**Two decisions that are cheap now and expensive after the first external
install.** Both are irreversible in the same way: changing them later is a major
version and a forced reinstall for every customer.

1. **A custom domain, or `*.run.app` for ever?** §9 of
   `docs/hosting-the-calculator.md`. Free to decide today.
2. **Which residency regions?** EU and US exist. Nine more are available and
   each is another deployment. §5, §14.

**And one that already bit.** The app has been through two major versions on
the dev site this week — the `llm` module and `read:epic:jira-software` — both
free because nothing external is installed. Every remaining module or scope is
in the same window, and the window closes at the first install.

**Console and commercial, with no code in this repository.** The app has never
been deployed to `production`; there is one installation, `development`, on the
dev site. The listing, Atlassian's review and billing are all Console work.
`docs/forge-deployment.md` says so under *"What is still not here"*.

**What a security review will probe**, all documented, none of them blockers:
the activity log is **not tamper-evident** and says so
([ADR 0021](adr/0021-the-audit-log-is-operational-and-says-so.md)); item 5
accepts an aggregate disclosure rather than enforcing per-issue permissions
(ADRs [0018](adr/0018-permission-mirroring-holds-by-accident-and-where-it-does-not.md)–[0020](adr/0020-the-anchor-issue-is-the-brief-s-access-control.md));
and the calculator image carries sixteen HIGH and CRITICAL findings with no
upstream fix, reported and blocking nothing exactly as
[ADR 0016](adr/0016-the-image-takes-debians-security-updates-at-build-time.md)
intends. The answers that would have been problems are all clean: no credential
collected, no login of its own
([ADR 0022](adr/0022-sso-is-inherited-because-the-app-owns-no-identity.md)),
every scope read-only bar the two named and justified.

## Assets held but unclaimed

Neither needs engineering, both are currently undersold.

- **A forecaster that refuses.** Almost no Jira app ships a seeded, reproducible
  Monte Carlo that declines below a data threshold instead of widening the
  interval until it is meaningless. ADR 0007. *"It tells you when it does not
  know"* is a rare thing to say truthfully, and the refusal sentences are already
  written to say it.
- **Accessibility, already tested.** WCAG 2.2 AA, verified in both themes on
  every push. A published VPAT is roughly a fortnight of documentation and it
  unlocks public-sector and large-enterprise procurement — a commercial advantage
  sitting inside a test file.

## The three standing refusals

Each has a decision record, each is in `CLAUDE.md` as a constraint, and some
buyer will ask you to break each one.

| Refusal | Record |
|---|---|
| Never rank or compare individuals | [ADR 0003](adr/0003-the-dashboard-does-not-measure-people.md) |
| Never compute a priority score | [ADR 0004](adr/0004-no-priority-score.md) |
| No hours, overtime or timesheets | `CLAUDE.md`, and `docs/data-format.md` for the absent schema |

The price is real: a share of buyers want exactly these and those deals are lost.
The original's argument is that sold apologetically they read as missing
features, and sold as the reason the numbers can be trusted they are a wedge with
the engineering-leadership buyer — and that the lost deals would have churned
when the data failed to support the claim.

## Risks the original names

Recorded here because three of the four have moved since drafting.

- **Atlassian owns the channel.** Unchanged. Mitigation held: the forecasting
  tools are dependency-free Python the app calls, so the engine stays portable
  even when the distribution is not.
- **The single-file promise fights the hosted service.** *This has now happened
  twice.* The Monte Carlo tile was the first, on purpose (ADR 0008). Item 3 is the
  second. The mitigation is unchanged and now load-bearing: the security suite
  stays the arbiter — no network calls, no browser storage in the produced file —
  and every future feature answers the fork out loud. A tile that degrades to an
  honest notice is acceptable; three of them is a dashboard URL with extra steps.
- **Permission mirroring is under-estimated.** Still untested, and the first
  pass does not test it: ADRs 0018–0020 surveyed three exposures and answered
  each by accepting a disclosure and naming it, which is a coherent position
  and is not the permission model the 5–8 weeks was for. So none of that
  estimate has been spent against the thing that was estimated, and the risk
  stands where it was drafted. Plan against the upper bound, which is the same
  argument the forecaster makes about sprint commitments.
- **Scheduled delivery may be the whole product.** Delivered 2026-08-26, and
  still untested as a claim: there is one installation, `development`, on the
  dev site, so there is no engagement to read either way. The original's
  instruction was to treat a spike after item 3 as evidence to *accelerate*
  phase 3 rather than defer it — and that contingency never got to fire, because
  phase 3 was built out first, items 4 and 6 done and 5 a first pass, before
  there was anybody whose engagement could be measured. The reason it was not
  deferred is unchanged and never depended on the signal: without phase 3 the
  product cannot be sold to anyone whose security review has teeth. What is
  still open is the half the first real installs will answer — whether item 3 is
  what customers actually value.

## Keeping this honest

Update the State column when an item lands, and say in `CHANGELOG.md` which item
it was. Do not restate the argument here — that is the artifact's job, and two
copies of an argument disagree eventually. If the plan itself changes, the
artifact is what changes; this file follows.
