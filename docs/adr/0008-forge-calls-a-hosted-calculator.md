# If we ship on Forge, Forge calls a hosted calculator

Forge runs Node in Atlassian's sandbox and cannot execute `agent/tools/`. The obvious readings of that are both bad: port the Monte Carlo to JavaScript, or drop the forecast from the Forge build. The first is a second implementation of a number we already compute, which is the thing [0005](0005-tools-compute-the-agent-narrates.md) exists to prevent and which we already refused once when the forecast tile chose an offline notice over recomputing itself in the browser. The second sells a delivery product with the delivery forecast removed.

So the Forge app pulls the issues, projects them to the fields a calculation needs, and posts that to a small hosted service that imports the existing Python unchanged. One implementation of every figure, still.

Three measurements made the decision rather than the argument:

**The tools are already pure functions.** Every `open()` and `glob` in `metrics.py`, `forecast.py` and `intake.py` is inside `main()`. The library entry points take a dict and return a dict, and `serve_live.py` has been a thin HTTP wrapper over exactly those calls since live mode shipped. The service is not new code so much as a second caller.

**A call is 16 KB and does not grow with the customer.** A forecast needs one team's history, not the organisation's: 16.2 KB for a 242-issue file and 16.3 KB for a 5,538-issue one, against 158 KB and 3.6 MB for the whole datasets. Compute is 0.25s for the small file and 0.74s for the large; `intake.sequence` is the slow one at 3.07s and the only call within an order of magnitude of a request timeout.

**No issue title has to leave Atlassian.** Running `forecast.build()` against a dataset stripped to `key, created, started, resolved, statusCategory, storyPoints, priority, dueDate, flagged, addedMidSprint` produces byte-identical figures. The only fields that differed were `summary` and `assignee`, echoed back inside `item_risk.items[]` for display, and Forge already holds those — it re-attaches them by key after the call. Titles are the sensitive payload here; it is why `data/dashboard-data.json` is git-ignored and most of what permission mirroring is about.

That last point is what makes the service defensible rather than merely possible. It holds no credential, stores nothing, and cannot reach Jira: Forge owns the grant and does the pulling. It is a calculator that receives dates and status categories. On the credential axis this is *better* than the fetcher we ship today, which holds the token itself.

The costs are real and none of them is a surprise. Egress disqualifies the app from the **Runs on Atlassian** badge, which is a marketing loss with no engineering answer. The egress declaration is something Marketplace review will read. Data residency stops being Atlassian's problem and becomes ours, pinned per region — that is already roadmap item 6, so it moves earlier rather than appearing from nowhere. And we would be operating a service: uptime, deploys, someone carrying a pager. Stateless and sub-second means scale-to-zero fits, which keeps that bill and that pager quiet.

Rejected: **porting the tools to JavaScript.** It buys the badge and costs the property the whole product rests on. Two implementations of a seeded Monte Carlo will eventually disagree about one sprint, and the day they do, every number in the product becomes something a reader has to check rather than read.

Rejected: **the Forge app storing pulled issues in Forge storage and computing there.** Same second-implementation problem, plus it turns a stateless calculator into a data controller inside Atlassian's platform, which is the harder half of permission mirroring brought forward with none of the benefit.

Not decided here: whether we ship on Forge at all. OAuth 2.0 (3LO) in `scripts/jira_auth.py` is the working connection and needs none of this. This records what the Forge route costs, so that choosing it stays a decision.

`service/` is the calculator, `forge/` the app that calls it, and `docs/organisation-config.md` explains why the calendar travels in the payload rather than being configured at either end.
