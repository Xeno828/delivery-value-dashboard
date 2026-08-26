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
| 3 | Scheduled delivery of the two views | 2 — make it arrive | 3–4 wk | **Built end to end**, one board's config away from proof |
| 4 | Durable sprint history | 3 — make it defensible | 3–4 wk | Open |
| 5 | Permission mirroring | 3 — make it defensible | 5–8 wk | Open |
| 6 | SSO, audit log, data residency | 3 — make it defensible | 6–10 wk | **Residency done**, SSO and audit open |
| 7 | Cross-team roll-up and intake sequencing | 4 — sell it upward | 4–6 wk | Open, blocked on 4 and 5 |

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
logic to get wrong. ADR 0012, `docs/hosting-the-calculator.md` §5. **SSO and the
audit log are untouched**, and the audit log still depends on item 5 — a log over
data with no permission model records the wrong thing convincingly.

## Item 3, which is next

Next by the roadmap's own rule rather than anyone's judgement: its only stated
dependency is item 1, and the whole of phase 3 sits behind it.

*"Monday at nine: the executive view to the leadership channel, the team view to
the team's. Both carry the narrative and the agent's written brief."*

Four-fifths of the **content** exists — both presets in `src/app.js`, both report
templates in `agent/templates/`. The delivery is wired but does not deliver: the
`weekly-brief` trigger now has its own function and handler, the `llm` module is
declared, and the handler refuses with three sentences naming what is missing —
no board configured to report on, no recipients, no mail transport.

**One correction to the plan, found by wiring it.** The roadmap gives item 3 a
single dependency, item 1. It also touches **item 5** — narrowed since, not
resolved. A scheduled trigger
runs with no user principal, so it cannot read Jira as the viewer the way the
panel does — and reading as the viewer is exactly what makes permission
mirroring hold for free today. A brief composed by the app and mailed to a list
asserts that every recipient may see every issue the app can, which nothing here
establishes. ADR 0013 has the detail. The ordering was already right; the
dependency was not written down.

It is also the first item that sends customer issue text out of the tenant — to
a mail provider, once. It nearly sent it twice: the brief is written by a model,
and the obvious way to do that is an API key and a third party. Forge LLMs
(`@forge/llm`, GA July 2026) runs Atlassian-hosted Claude inside the platform
with no egress, so the model reads the tenant's issue titles without them
leaving the boundary the customer already agreed to. ADR 0013 records both — the
crossing that was avoided and the one that remains.

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
- **Permission mirroring is under-estimated.** Untested — item 5 has not started.
  Plan against the upper bound, which is the same argument the forecaster makes
  about sprint commitments.
- **Scheduled delivery may be the whole product.** Now live rather than
  hypothetical, since item 3 is what is being built. If engagement spikes after
  it, the original's instruction is to treat that as evidence to *accelerate*
  phase 3, not to defer it: without phase 3 the product cannot be sold to anyone
  whose security review has teeth.

## Keeping this honest

Update the State column when an item lands, and say in `CHANGELOG.md` which item
it was. Do not restate the argument here — that is the artifact's job, and two
copies of an argument disagree eventually. If the plan itself changes, the
artifact is what changes; this file follows.
