# One contract, two transports

The dashboard's live mode asks four questions — what contexts exist, one context's issues, a forecast, an ask sequencing. It now has two ways to ask them, and the page cannot tell which one it has.

Over `http(s)` a same-origin `GET api/…` reaches `scripts/serve_live.py`. Inside a Forge Custom UI iframe there is no same-origin `api/` at all, so an adapter bundled with the Forge build leaves an `invoke()` on `window.__DVD_BRIDGE__` before the page loads, and the page uses that instead. On `file://` there is no transport, the page asks nothing, and an emailed copy produces a silent console exactly as it always has.

The seam is a route name and an envelope. `src/app.js` calls `LIVE.get("context", {id})` and gets `{ok, status, body}` back. The **body shapes are the contract**, defined by `serve_live.py` and returned unchanged by the Forge resolvers. The status is transport-level: a 404 for a sprint this site does not have and a failure to answer at all are different things, the page says different words for each, and each transport supplies its own.

## What this rules out

**The page learning what Forge is.** `src/app.js` is the shipped product. It must not import `@forge/bridge`, the root `package.json` must stay dependency-free, and the built file must keep making zero network calls from `file://` — the security suite asserts all three, and now also asserts that no module syntax and no `@forge/*` import appears in the page's own sources at all. The adapter is `forge/bridge/bridge.js`, bundled separately and linked only into the split build.

It is CommonJS, and it requires the SDK inside a `try`. That is not a style choice: `@forge/bridge` connects to its host as a side effect of being loaded and throws outside a Forge iframe, and an `import` is evaluated before any of the adapter's own code — so the throw aborted the file before it installed anything and the page silently fell back to the same-origin fetch. Caught, the failure is named in the console and no transport is installed, which is correct outside Forge and explained inside it.

It also has to be a *classic* script, linked ahead of `app.js`. `app.js` decides at load which transport it has, and an ES module is deferred — an adapter that arrives afterwards is an adapter that never ran, and the symptom is a page that silently believes it is offline. `build.py --split --bridge` places the tag; `make forge-static` bundles it `--format=iife`.

**Two implementations of the same answer.** The alternative that was available and refused: let the Forge resolvers return whatever shape suited them and reshape it in the page. That is one product behaving differently depending on how it was reached, which is the same class of failure [ADR 0005](0005-tools-compute-the-agent-narrates.md) exists to prevent — and it would have surfaced as a chart that is present over one transport and missing over the other, with nothing on screen to say why.

So the shapes are checked rather than intended. `forge/src/jira.js` holds the Forge half as pure functions of a Jira response — no SDK, no network — precisely so `tests/test_service.py` can run them against fixtures and compare the envelopes, field for field, with what a running `serve_live.py` really puts on the wire. `tests/e2e.py` checks the other end: the same page, over both transports, against the same bodies, must render the same footer, the same KPI strip and the same context list.

## What the Forge side leaves out, and why that is not a gap

The resolver plays the *fetcher's* part, not the calculator's. Pulling a field out of a Jira issue is what `scripts/fetch_delivery_data.py` does; deciding what a status means, or what a burndown looks like, is organisation config and calculation, and neither happens in a resolver.

So `statusCategory` is absent and the page categorises the raw status name under its own config, as it already does for any file whose producer did not resolve it. `started` is absent because recognising the first transition into an "In Progress" status needs that same config — and the page prints *"no completed items with both a start and a resolved date"*, which is true, rather than a flow efficiency built on a rule the resolver invented. The burndown series is empty because it is Python that is not running, and the page says *"no burndown series in this dataset"* where the chart would be.

`addedMidSprint` is deliberately **not** in that list, and the difference is the whole point. It needs no config — it is *the sprint field changed after the sprint began* — and defaulting it to false is not a silence. It is the claim that nothing was added: the health score reads it as full marks for scope stability, and nothing on the page says it was never measured. That is a plausible wrong number, so the resolver expands the changelog and reads it.

The organisation config itself is empty over the bridge, and that is the honest answer rather than a convenient one. Config travels inside a dataset, and a Forge install has no dataset — there is nowhere yet for a site to say which statuses mean done or which days it works. Empty resolves to the documented defaults and the page footer names the calendar it used. Somewhere for a site to state its own is the next decision, not this one.

## What it cost

`read:project:jira`, `read:sprint:jira-software` and `read:jql:jira`, all read-only, all on the consent screen of every install.

The first is the one to argue about, because this app removed it once already. A `boards` resolver was dropped from the connection check rather than granted it, on the grounds that the scope existed purely to make a diagnostic more convenient — and the note it left said that if the real context picker ever needed to enumerate boards, this was the price and it was a decision to take on its own merits. This is that moment. The product's picker offers the boards of the project the page is open in, and `GET /rest/agile/1.0/board` needs it. The alternative is a product page that opens empty and asks an end user to type a numeric board id, which is a diagnostic, not a product.

The other two are what `forge lint` demands for `GET /board/{id}/sprint/{sid}/issue` — the one call that reads a sprint's issues, and there is no cheaper endpoint: the board-issue endpoint returns what is on the board now rather than what a closed sprint contained, and recovering the sprint from an issue means reading a custom field whose id differs per site. `read:jql:jira` looks broader than the rest and is worth understanding rather than waving through: that agile endpoint is JQL-backed underneath. This app issues no JQL of its own — its four routes take no query from the page.

The rule the allow-list in `tests/test_service.py` encodes still holds. Adding a scope is a deliberate edit with a reason written next to it, not something a `--fix` run can do quietly.
