# Decision records

Twenty decisions that explain why the product is shaped the way it is. Each one exists because the alternative was tried, argued for, or nearly shipped — none of them is a statement of general principle.

Read these before proposing a change that a constraint in `CLAUDE.md` appears to block. The constraint is the rule; the record is the reason, and the reason is what tells you whether your case is the exception.

| | Decision | The thing it rules out |
|---|---|---|
| [0001](0001-single-self-contained-html-file.md) | The dashboard is one self-contained HTML file | A framework, a build pipeline, a hosted URL nobody clicks |
| [0002](0002-bundle-not-live-query.md) | The page never queries Jira or Asana; data arrives as a bundle | A credential inside a file that gets forwarded |
| [0003](0003-the-dashboard-does-not-measure-people.md) | The dashboard does not measure people | League tables, throughput per head |
| [0004](0004-no-priority-score.md) | Intake returns delivery consequence, never a priority score | WSJF and everything of that family |
| [0005](0005-tools-compute-the-agent-narrates.md) | The tools compute; the agent only narrates | Any figure in a report that no tool produced |
| [0006](0006-forecast-in-items-not-points.md) | Forecasts count items, never story points | Six point-observations pretending to be a distribution |
| [0007](0007-refuse-rather-than-widen.md) | Below the evidence thresholds, refuse rather than widen the interval | An interval so wide it is technically true and practically useless |
| [0008](0008-forge-calls-a-hosted-calculator.md) | If we ship on Forge, Forge calls a hosted calculator | A second Monte Carlo, written in JavaScript |
| [0009](0009-one-contract-two-transports.md) | Live mode has two transports and one set of body shapes | A page that behaves differently depending on how it was reached |
| [0010](0010-an-empty-selection-is-a-refusal.md) | Unmeasured is refused or dropped, never scored zero | A score computed from empty denominators, in a chip with a verdict on it |
| [0011](0011-a-kanban-context-is-a-window-not-a-clock.md) | A board without sprints gets a window, and a window is not a clock | A pace measured against a boundary nobody committed to |
| [0012](0012-the-calculator-is-reached-by-invokeremote.md) | Forge reaches the calculator by `invokeRemote`, region-pinned | A shared secret over a URL the app builds itself |
| [0013](0013-the-brief-is-written-inside-the-tenant.md) | The scheduled brief is written by Forge LLMs in the tenant; only the file leaves | An API key, a third party, and every issue title going through it weekly |
| [0014](0014-jira-sends-the-brief-and-the-read-only-rule-bends.md) | Jira sends the brief; non-read scopes are allow-listed with reasons | A mail provider, recipients as email addresses, and a rule kept by memory |
| [0015](0015-a-durable-series-stores-what-jira-forgets.md) | Sprint rows are recorded when a sprint closes; re-derivation is a labelled fallback | A cache of Jira, a reconstruction written in as a recording, and a disagreement resolved quietly |
| [0016](0016-the-image-takes-debians-security-updates-at-build-time.md) | The calculator image applies Debian's security updates at build time | Loosening a gate that is telling the truth, and a suppression list as the first answer |
| [0017](0017-a-forecast-is-logged-as-a-count-not-a-promise.md) | A published forecast is logged as a count by a date, holding no issue identity | Recording issue keys to score "all of it lands by the 14th", and scoring a forecast the tool refused to make |
| [0018](0018-permission-mirroring-holds-by-accident-and-where-it-does-not.md) | Where reading as the viewer stops being enough, surveyed before anything is built | Fixing the brief first, and treating "we hold only counts" as a permission model |
| [0019](0019-a-recorded-row-is-a-fact-about-the-board.md) | A recorded row belongs to the board; a narrow view may not write one and a wider one repairs it | Re-deriving per reader, and letting whoever opened the panel last write the row |
| [0020](0020-the-anchor-issue-is-the-brief-s-access-control.md) | The anchor issue is the brief's permission model; offline impersonation is deferred, not rejected | Administer Jira to check recipients, and claiming item 5 is finished |

## Writing a new one

Prose, not a template. State the decision, what it costs, and what was rejected — the rejected options are the part a future reader needs, because they are the ones that will be proposed again. Number it sequentially and add a row above.

A record is not a changelog entry. `CHANGELOG.md` says what changed and which bug prompted it; a record here says why the shape of the thing is what it is, and stays true across many releases.
