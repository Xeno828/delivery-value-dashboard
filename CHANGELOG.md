# Changelog

## 1.16.2

**A missing calendar was scored as bad delivery.** Sprint health is built from four weighted measures, and Delivery pace carries the largest weight of the four — 34%, and the only one that looks forward. Over a sprint whose dates were not in the data it scored **0/100**, which took the sample sprint from 52 and *Needs attention* to 22 and **Off track**. A zero is a finding. "We do not know when this sprint runs" is not a finding about delivery, and it should not be able to change the colour of the chip. A component that could not be measured now leaves the composition and is named, and the ones that remain are re-weighted to sum to one.

**Most of those calendars were not missing.** `forge/src/jira.js` sends no `workingDays`, deliberately — which days are worked is organisation config, and resolving it in a resolver would be a fourth opinion arriving by a fourth route. But the page holds that config and already derives `statusCategory` from it for exactly that reason, so it derives the day list too, from the sprint's own start and end dates. Until it did, **every sprint in a Forge tenant lost the largest component of its health score**, *Pace vs clock* read `—` across the entire install, and the two transports rendered different figures from the same sprint — the thing [ADR 0009](docs/adr/0009-one-contract-two-transports.md) exists to prevent, and invisible to its parity test, because that test feeds the bridge the loopback's own bodies. A rollup keeps its empty list: its dates span every sprint in it, so a derived list would be perfectly real and would describe nothing.

**Read in story points, an unestimated dataset scored itself with two of the four measures broken in opposite directions.** Pace read 0/100 with a calendar that was present and correct, because `totalU` was zero; scope stability read **100/100 — "no mid-sprint additions"** out of the same nothing, because zero added out of zero total is 0% growth. Half the method, one component flattering and one punishing, and a number at the end of it. Below half the weight the score now refuses outright and says which measure the data does not carry, because what survives — blockers and ageing work — describes hygiene rather than whether the sprint will land.

**The disclosure was naming the wrong cause.** All three situations printed *"no sprint calendar"*: the sprint with no dates, the rollup that has dates and no single clock, and the points view whose calendar was fine. That tooltip exists so a reader can argue with the method, and one that names the wrong cause sends them to fix the wrong thing. There are three causes and there are now three sentences, in the tooltip and in the KPI tile's sub-label.

**The chip says when it is a partial score.** A figure built from three of four measures is a different quantity from one built from four, so it reads `(33/100, 3 of 4 measures)` and the disclosure prints the weights that actually multiplied — 33%, not the nominal 22%. Same rule as anywhere else here: a composition that bounds itself has to say what it dropped. `tests/e2e.py` asserts the printed weights sum to 100, which is what catches a re-weighting that silently does not.

[ADR 0010](docs/adr/0010-an-empty-selection-is-a-refusal.md) carries both halves now — the empty selection from 1.16.1, and the unmeasured component here. They are the same decision at two granularities: unmeasured is not zero.

## 1.16.1

**The dashboard scored an empty sprint 66 out of 100.** Open the page over a dataset with no issues in it and the header printed *"Sprint health: Needs attention (66/100)"* in an amber chip. Nothing had been measured. Every component of the score is a share of the selected issues, and the guards that keep each one off a divide-by-zero — `Math.max(items.length, 1)`, `? … : 0` — all resolve to good news: no blockers among nothing, no ageing work among nothing, no scope growth on nothing. Delivery pace contributed its neutral zero, the four weights summed, and out came a figure that looks exactly like the output of a calculation.

Sixty-six is the worst number it could have landed on. Zero would have looked broken and a hundred absurd; 66/100 looks computed, and it arrives in a band with a verdict attached.

**It is the state the Forge build opens in.** `forge/seed.json` carries no issues deliberately — 1.16.0 stopped shipping a demo company's sprints into a customer's Jira — so the app renders empty until the bridge answers, and stays empty for good if the bridge fails. For a customer opening the app for the first time inside their own tenant this may be the only state they ever see, and it was telling them their sprint needed attention. The same arithmetic is reachable with no Forge involved: the score is computed over the *filtered* items, so a search box matching nothing produces it too.

**Zero issues is now a refusal, and it was never only the health score.** The executive card opened *"0 of 0 items are done (0%)"*. The KPI strip printed eight tiles of zeros, four of them shares with an empty denominator. The ageing chart printed *"Nothing open has outlived a sprint. That is the healthy state."* The value card printed a `$0` hero over *"0 of the 0 completed items"*. The risk register reported *"No risks triggered against the current filters"* — a finding, over nothing examined. All six now say what the forecast tile and the flow-time chart have always said in this situation: what is missing, and that it is missing rather than thin. [ADR 0010](docs/adr/0010-an-empty-selection-is-a-refusal.md) records where the line sits, because it is not "hide everything at zero" — counts of an empty set that are honestly nil keep their nil, and *"Nothing open has outlived a sprint"* is a true and useful sentence when there are issues and none of them are open. It is only false when there was never anything to age.

**The grid is no longer faded over an empty context.** It used to drop to 0.45 opacity, which was the right instinct reached through the one channel that cannot carry a reason — and once the tiles explain themselves in words, fading them puts the only text on the page below the AA contrast floor. The fade is gone and `tests/a11y.py` now renders the empty selection in both themes, which is a state the sample data never reaches and no check had ever visited.

**The test sweeps for digits, not for wording.** `tests/e2e.py` drives the shipped page into the empty state twice — once with the Forge seed, once by filtering every issue out of a real dataset — and asserts that six named elements contain no numeral at all, that each refusal still ends with *the evidence is absent, not noisy* untrimmed, and that the score comes back the moment there are issues to score. A future change that reinstates a figure fails on the digit sweep whether or not it kept these sentences, and an over-eager fix that suppresses the score permanently fails on the other half.

## 1.16.0

**The dashboard inside Forge shows the customer's own Jira, not a demo company's.** It rendered before this — fully styled, with charts — but every number on it belonged to Highpeak Commerce, because the page reaches live mode over a same-origin `api/*` and a Forge Custom UI iframe has no such origin. It does now, and the thing that made it possible is a seam rather than a feature. [ADR 0009](docs/adr/0009-one-contract-two-transports.md) records it.

**One contract, two transports.** The page asks four questions by route name and gets `{ok, status, body}` back. Over `http(s)` that is the same-origin GET `scripts/serve_live.py` already answered; inside the iframe it is an `invoke()` that an adapter left on the window before the page loaded. The **bodies are the contract** — defined by `serve_live.py`, returned unchanged by the Forge resolvers — and the status is transport-level, because a 404 for a sprint this site does not have and a failure to answer at all are different things and the page says different words for each. On `file://` there is no transport, nothing is asked, and an emailed copy still produces a silent console.

**`src/app.js` does not know what Forge is, and the suite now insists on it.** It imports nothing, contains no `@forge/*` reference, and the root `package.json` still has no dependencies. The adapter is `forge/bridge/bridge.js`, bundled separately and linked only into the split build — and it has to be a *classic* script placed ahead of `app.js`, because `app.js` decides at load which transport it has and an ES module is deferred. An adapter that arrives afterwards is an adapter that never ran, and the symptom is a page that silently believes it is offline, which looks exactly like a broken resolver.

**Found by loading the real bundle, after the tests using a stub had all gone green: the adapter was never installing itself.** `@forge/bridge` connects to its host as a side effect of being loaded, and outside a Forge iframe that throws. An ES `import` is evaluated before any of the adapter's own code runs, so the throw aborted the file before it reached the assignment — the page fell back to the same-origin fetch with nothing but an uncaught error in the console to say why. Outside Forge that fallback is the right answer and it hid the fault completely; inside a real iframe the same throw would have left the dashboard looking merely offline, which is the failure this whole seam is meant to make impossible. It is CommonJS now, required inside a `try`, so the failure is caught and named and no transport is installed rather than a broken one. `tests/e2e.py` loads the bundled adapter rather than a stub and asserts all three: no uncaught error, a console line saying why, and a page that falls back instead of believing it is connected.

**The two transports are compared rather than assumed to agree.** `forge/src/jira.js` holds the Forge half as pure functions of a Jira response — no SDK, no network — precisely so a test can run it. `tests/test_service.py` drives it over fixtures and compares the envelopes, field for field, against what a running `serve_live.py` really puts on the wire. `tests/e2e.py` checks the other end: the same page, over both transports, fed the same bodies, must render the same footer, the same KPI strip, the same context list and the same issue count. Writing that test found four genuine mismatches before anything was deployed.

**A field defaulting to false was going to be a confidently wrong number, and it is the one thing the resolver computes.** `addedMidSprint` needs no organisation config — it is *the sprint field changed after the sprint began* — and leaving it out is not a silence. It is the claim that nothing was added: the health score reads it as full marks for scope stability, and nothing on the page says it was never measured. The resolver expands the changelog and reads it. What it does *not* send is deliberate and written down beside each one: no `statusCategory`, because which statuses mean done is config the page already holds; no `started`, because recognising an "In Progress" transition needs that same config, and the page prints *"no completed items with both a start and a resolved date"*, which is true, rather than a flow efficiency built on a rule a resolver invented; no burndown series, because that is Python and Python is not running here, and the page says so where the chart would be.

**The Forge build is seeded empty.** It used to carry the demo dataset, so the first thing a customer saw was a fictional company's 22 issues inside their own Jira. `forge/seed.json` carries none, the page holds one placeholder context until the bridge answers, and then opens on the site's newest sprint. A file built with no data of its own adopting the connection's is a general rule, not a Forge one — the same thing happens over loopback.

**Three scopes, and the first is one this app removed rather than granted a fortnight ago.** The connection check dropped a `boards` resolver instead of asking for `read:project:jira`, on the grounds that the scope existed purely to make a diagnostic more convenient, and the note it left said that if the real context picker ever needed to enumerate boards, this was the price and it was a decision to take on its own merits. This is that moment: the picker offers the boards of the project the page is open in, and the alternative is a product page that opens empty and asks an end user to type a numeric board id. `read:sprint:jira-software` and `read:jql:jira` are what `forge lint` demands for the one call that reads a sprint's issues; the JQL one looks broader than the rest and is worth understanding rather than waving through — that agile endpoint is JQL-backed underneath, and this app issues no JQL of its own.

**A check that forced a false word into a file has been replaced by one tied to the code.** `tests/test_service.py` asserted that `manifest.yml` still described itself as a scaffold, so a manifest that quietly looked finished could not be deployed. That stopped being true the moment the app was registered and reading a tenant's boards. What is still unfinished is nameable instead: the calculator has no host, `remotes[0].baseUrl` says `.invalid`, and the forecast resolvers answer with a refusal saying exactly that. The two are asserted as a biconditional, because both directions are a bug — a real `baseUrl` with the refusal still in place is a forecast tile that stays dark for no reason anybody can see.

**The connection check was meant to be deleted here and has been kept.** It is the only thing that shows the outbound payload for a single issue, and it is how you discover that `customfield_10016` is not this site's story-point field. That remains open and is the plausible-wrong-number class: on such a site every issue reads as zero points and the burndown flattens in points mode with nothing saying why. Items are unaffected, which is the default unit everywhere and the only unit the forecaster reads.

Not closed: the calculator is still not hosted, so the forecast and ask-sequencing tiles refuse and name that reason rather than showing a figure.

## 1.15.1

The three things the Forge work left unfinished now have runbooks — and two of them turned out to be partly closable rather than only documentable. [docs/forge-deployment.md](docs/forge-deployment.md) is the guide.

**The calculator's auth is a seam now, and the empty half fails closed.** `SERVICE_AUTH` selects between `shared-secret`, which is implemented and tested, and `forge-token`, which is not written yet and **refuses to start** rather than degrading to something weaker. An unknown mode refuses too. Both refuse every request as well as refusing to boot, so deleting the startup guard cannot quietly open the service — a calculator that came up unauthenticated would look healthy to everything watching it.

The Forge verifier is still not written, deliberately. Verifying RS256 needs a crypto library and a real token to test against, and neither exists here; shipping security code whose correctness nobody has observed is worse than an honest placeholder. What it has to check is written down instead — algorithm pinning, `kid` lookup with JWKS caching and rotation, `exp`/`nbf`, `aud`, `iss`, and actually using the tenant claim — along with the eleven forgery cases the tests must reject, including the `alg: none` and HMAC-signed-with-the-public-key confusions. The five facts that must be confirmed from Atlassian's current documentation are listed as facts to confirm, not guessed at.

**The Forge manifest is now checked against this repository on every push.** `forge lint` needs a CLI nobody here has, but it validates schema and would not check any of this: the manifest's scopes must match `SCOPES` in `jira_auth.py`, the egress rule must name a remote that is actually declared, no write or manage scope may appear, and no app id may be committed — `forge register` writes one, and committing it hands everyone who clones the repository a manifest aimed at somebody else's app.

**The container image is built and smoke-tested in CI.** A new job builds it, then asserts it refuses to start with no secret, runs as uid 10001, refuses an unauthenticated request, returns a real forecast for an authenticated one, refuses issue text with the right sentence, and does not log issue text.

**And a check that needs no Docker, because the Dockerfile is edited on machines that have none.** `tests/test_service.py` reconstructs the image's filesystem from the `COPY` lines and imports the service from it. The failure that catches is narrow and nasty: the Dockerfile stops copying a module the service imports, every other suite still passes because they run against a working tree where the file is present, and the container fails on its first request in production. It also asserts no dataset, config or credential file is baked in.

**The security suite flagged a literal secret in the new CI job, and was right again.** Second time in three releases. It is minted per run now. A scanner cannot tell a placeholder from a real credential, and a workflow that needs a hard-coded one teaches the habit.

Not closed, and not closable from here: registering the app, running `forge lint`, and building the image locally. All three need an account or a tool this machine does not have. Scheduled rebuilds for base-image CVEs are listed as a decision rather than a task — a scanner that fails the build on somebody else's feed needs a policy about what blocks a merge.


## 1.15.0

**If we ship on Forge, the forecast comes with us.** Forge runs Node and cannot execute `agent/tools/`, and the previous note in `forge/README.md` framed that as a choice between hosting the Python "anyway" and writing a second Monte Carlo in JavaScript. Measuring it settled the question rather differently, and [ADR 0008](docs/adr/0008-forge-calls-a-hosted-calculator.md) records it.

**The tools were already pure functions.** Every `open()` and `glob` in `metrics.py`, `forecast.py` and `intake.py` sits inside `main()`; the library entry points take a dict and return a dict. `service/app.py` is a second caller, not new logic — `serve_live.py` has been the first one since live mode shipped.

**A call is 16 KB and does not grow with the customer.** 16.2 KB for a 242-issue organisation and 16.3 KB for a 5,538-issue one, against 158 KB and 3.6 MB for the whole datasets, because a forecast needs one team's history rather than the organisation's. Compute is 0.25s and 0.74s respectively; `intake.sequence` is the slow one at 3.07s and the only call within an order of magnitude of a request timeout.

**No issue title has to leave Atlassian, and that is the finding the design rests on.** `forecast.build()` over a dataset stripped to `key, created, started, resolved, statusCategory, storyPoints, priority, dueDate, flagged, addedMidSprint` produces byte-identical figures. The only fields that differed were `summary` and `assignee`, echoed back inside `item_risk.items[]` for display — and the Forge app already holds those, so it re-attaches them by key after the call. Titles are the sensitive payload; it is why `data/dashboard-data.json` is git-ignored and most of what permission mirroring is about. `tests/test_service.py` asserts the projection rather than trusting the measurement to stay true.

**Free text is refused, not ignored.** A payload carrying `summary` gets a `400` saying the text does not belong here and was not stored. Accepting and dropping it quietly would make the service a place customer text arrives, which is the one thing the projection exists to prevent. The resolver asserts the same thing before sending, so it fails closed at both ends, and a test compares the two field lists across the two languages — the resolver deciding what leaves and the service deciding what is accepted must not drift.

**The service computes nothing and the suite proves it.** Its forecast output is compared byte for byte against `forecast.build()` called directly. A wrapper that computes one percentage is a second implementation, and the day it disagrees every number in the product becomes something a reader has to check rather than read. The rule that the agent never does arithmetic now says so about everything between the tools and a reader.

**It refuses to start without a shared secret.** An open calculator is free compute for whoever finds it, and holding no data is not the same as needing no authentication. `--insecure` exists for local development and says so on every request. Oversized payloads get the limit named and nothing calculated — a forecast over half a team's history looks exactly like a forecast over all of it. Tracebacks go to the operator, never into a response, because they carry field values.

**A refusal survives the trip.** Shortening a working week shortens the throughput sample, and a team that had just enough completion history under five days can fall under the threshold under four. The right answer there is *"too little completion history to sample from"*, not a thinner forecast, and the test pins that it reaches the caller with its sentence intact and its calendar named. Every response carries the calendar, because two forecasts of one board under different working weeks are different forecasts and the difference is otherwise invisible.

**The security suite caught a credential in the tests it did not like, and it was right.** The service tests had a literal bearer token; a scanner cannot tell that from a real one. It is generated per run now. A test that needs a hard-coded credential is a test teaching a bad habit.

**What is real and what is not.** The projection, the free-text assertion, the call and the re-attachment in `forge/src/index.js` are real and tested against the calculator. Forge itself has never run: no app registered, nothing deployed, and `manifest.yml` has not been through `forge lint`. The Forge-specific syntax needs checking against current Atlassian docs, particularly the `remotes` block and the invocation-token contract — the service authenticates with a bearer secret today, and the tenant-aware thing is the Atlassian-issued JWT.

**Costs, written down rather than discovered at listing time.** Egress forfeits the *Runs on Atlassian* badge, with no engineering answer — only the choice not to have two forecasts. Data residency becomes ours, pinned per region, which brings roadmap item 6 forward. And we would be operating a service, though a stateless sub-second one suits scale-to-zero.

Still not here, and still not automatable: registering the Atlassian app, and the Marketplace listing.


## 1.14.0

Phase 1 of the commercial roadmap — *make it connectable*. Two items: a Jira connection a customer can consent to, and the assumptions that are true of exactly one company.

**Jira connects over OAuth 2.0 (3LO).** `scripts/jira_auth.py` does the authorisation-code dance against a loopback listener, stores the grant, refreshes it, and resolves which granted site to query. The fetcher and the live server both use it: `--auth auto` prefers a stored grant and falls back to the API token, and **prints which one it used on every run** — the two see different sets of issues, and a file produced by the wrong one looks entirely legitimate.

The API-token path is not deprecated. It needs no app registration and is the right thing for pulling your own board. What it cannot be is a customer's connection: it carries the permissions of whoever generated it, cannot be scoped, and is revoked only by deleting it.

**A grant covering two sites is refused rather than resolved.** Silently picking the first is how a report about the wrong company gets produced, and it would look correct all the way to the meeting. Name one with `--jira-site` or `JIRA_SITE`.

**Scopes are `read:jira-work` and `read:jira-user`, and the suite now fails if a write scope appears.** An app that asks for write access to close a deal is an app whose consent screen makes the buyer's security reviewer stop and read.

**Which statuses mean done is configuration now, not code.** So are the working week, the holiday calendar and the sprint length — `config/organisation.json`, resolved by `agent/tools/orgconfig.py`. The heuristic that read "Done|Closed|Resolved" out of a status name is still there as a last resort, but a site with a *Signed off* column no longer reports every sprint as 0% complete.

**The config travels inside the dataset, and that is the load-bearing decision.** Whatever produces a file resolves the config once and writes it in as `orgConfig`. The page, `metrics.py`, `forecast.py`, `intake.py` and the live server all read it from there; none of them opens the config file. A config each consumer read separately would be a third opinion arriving by a different route, and the first symptom would be a facts pack and a dashboard reporting different flow efficiency for the same sprint — which shipped here once, as 25% against 22%, and was a units disagreement of exactly this shape.

The consequence is deliberate: an emailed copy carries the calendar it was built with. The numbers in it were computed under those rules.

**A status the config has never seen is named, not swallowed.** At the end of every fetch: *"1 status matched no rule in the config and were inferred: 'Awaiting sign-off'"*. This is the whole point of the feature. A site adds a column, no rule mentions it, those issues read as To Do, the burndown flattens, and the dashboard is confidently wrong with nothing on screen to say why. That is a churn-in-week-two bug and the customer never tells you which number they stopped believing.

**A bad config stops the run instead of falling back.** `workingWeek: ["mon", "funday"]` is refused by name, as is a status listed under both `done` and `inProgress`, a malformed holiday and a non-integer sprint length. A typo that quietly reverted to a five-day week would move every forecast in the product with nothing saying so.

**Holidays shorten working time only.** The Monte Carlo horizon, the sprint elapsed-percentage and the ideal burndown line all move; reported ages do not. An item raised 21 days ago is 21 days old whether or not the office was shut, and a holiday that shortened it would be the same lie of convenience as skipping weekends. Both halves are pinned by tests.

**A bug this found in the forecaster: it read `meta.workingDays` for one figure and recomputed the rest itself.** That field has carried an explicit list of working dates since it existed, and `metrics.py` has always honoured it. `forecast.py` honoured it in exactly one place — the next-sprint commitment, which used its length — while `throughput_samples`, `cycle_times`, `lead_times`, the percentile dates and the capacity horizon all built their own Monday-to-Friday span and ignored the list entirely. Nobody noticed because no producer had ever written a list that differed from Monday-to-Friday. The moment a holiday calendar could exist, one forecast output would have counted a sprint's working days differently from the four beside it, and all five would have been in the same JSON object. Same class as the 25%/22% bug, invisible in the same way. Everything now resolves through `orgconfig.py`.

**Adopting any of this changes no number.** A dataset with no `orgConfig` resolves to defaults that reproduce what was hard-coded before, and `tests/test_agent.py` asserts that spelling the defaults out leaves every forecast percentile identical.

**Two implementations, and a test that they agree.** `src/app.js` mirrors `orgconfig.py` because the browser cannot call Python. `tests/e2e.py` compares working days and status categories between them **under a config that is not the default** — a Sunday-to-Thursday week with two holidays and a custom status list — because two implementations of Monday-to-Friday agree by accident.

**The page says which calendar it used.** In the footer, in the same words `metrics.py` puts in the facts pack, so a reader comparing the two does not have to translate. When the live server's config differs from the one baked into the file, the server's wins — it computed the forecasts — and the footer says it was replaced rather than swapping it silently.

**The security suite stopped covering the credential path, and said so.** Its check was pinned to `os.environ.get("JIRA_TOKEN")` appearing in `serve_live.py`; that reading moved into the fetcher and the OAuth client, so the check would have passed while covering nothing. It now checks every script that can hold a credential, and adds six: the grant is git-ignored, created 0600 rather than widened afterwards, never printed, the redirect verifies `state`, the listener is loopback-only, and no write scope is requested.

**`forge/` is a scaffold and is marked as one.** Manifest, scopes and a resolver that returns refusals rather than numbers. It exists so the Forge-versus-Connect decision stays a decision: Forge runs Node and cannot call the Python tools, so taking that route means either hosting the Python anyway or writing a second Monte Carlo — and this project already refused the second implementation once, which is why the forecast tile shows an offline notice in an emailed file.

Not included, and not automatable from here: registering the Atlassian app and the Marketplace listing. Both need an Atlassian account and credentials that should not pass through anyone else's hands.


## 1.13.0

**The tiles can be put in your own order.** Each row of the **Tiles** popover has an up and a down arrow, and the order travels the way the tile selection already did: `?order=` in the URL, a `data-order` attribute on a saved copy, and nothing in browser storage — the file still has to survive being emailed. **Default order** puts it back.

**Arrows rather than drag and drop, and that is the feature rather than a shortcut.** Dragging is unusable from a keyboard, and this page is held to WCAG 2.2 AA. Two buttons per row are operable by anyone, and the accessibility suite now opens the popover — which nothing in it had ever done — and asserts a tile moves on `Enter` alone.

**The tiles move, not a CSS `order`.** Setting `order` in CSS moves the picture and leaves the tab order and the screen-reader reading order in the old sequence, so the page would read in an order nobody can see. `applyOrder()` re-appends the nodes instead, which also leaves charts, open table views and the forecast tile's fetched state untouched. `tests/e2e.py` compares DOM order against the chosen order on every move, so a later switch to CSS would fail rather than quietly reintroduce it.

**Focus survives the move, and the move is announced.** Reordering rebuilds the list, which destroys the button that was just pressed; without putting focus back it falls to the body, and inside a popover that reads as the popover having closed. When a tile reaches an end of the list its arrow is disabled and focus moves to the one it can still travel on. The tile that moved is somewhere down the page, usually behind the popover, so a live region says *"Team load moved to position 5 of 13"* — visibly as well as to a screen reader.

**Order and selection stay independent.** `?tiles=` says which tiles, `?order=` says in what sequence. Folding one into the other would mean un-ticking a tile silently reshuffled the page.

**A custom order can leave a row short, and the page says so rather than pretending otherwise.** Tiles keep their widths when they move; the twelve-column grid only fills exactly in orders that happen to add up. The default order does, and 1.12.5's check still holds it to that. The picker labels a custom order as custom; it does not refuse one.

An unreadable `?order=` fails the way `?tiles=` does. Unknown ids are dropped and any tile the list forgot is appended in its default position, so a truncated or hand-edited parameter yields the whole page in an odd sequence rather than a page missing tiles.

The popover went from 290px to 320px to fit a name beside two arrows, and it is anchored to the right edge — so the reflow check now measures it **open** at 320px as well as closed. Every check above it had measured it as `display:none`, which costs nothing and proves nothing.


## 1.12.5

**Two rows of the tile grid did not add up to 12, and the page had the holes to prove it.** The grid is twelve columns and every row is meant to fill them. The bottom band did not: *Release quality* at 4 columns beside *Team load* at 3 came to 7, so roughly 600x360px of empty page sat to the right of them at any desktop width. Both tiles are now 6, which is the whole fix at that size.

**Between 761 and 1180px it was worse, and for a subtler reason.** That breakpoint promoted every wide tile to full width and halved every narrow one — a span-7 going to 12 strands the span-5 it was paired with alone on a half-empty row. Four tiles were orphaned that way and the page ran a third taller than its content needed. It now halves everything instead of promoting anything, so the pairs stay pairs: 4557px of page becomes 3848px on the demo sprint, with no row left short.

**Cards stretch to their row rather than stopping where their content runs out.** *Releases & milestones* holds two releases and ended 128px above the bottom of the card beside it, and the gap read as a hole in the page rather than as a card with room in it. The contents stay top-aligned; only the box grows. Grid gaps and card padding came down slightly with it.

**The check is arithmetic, not a screenshot.** `tests/e2e.py` now sums the column span of every visible tile per row at 1500, 1100 and 700px and requires 12. Against the previous build it fails and names the rows — *rows [5] are [7]* at 1500, *rows [3, 9] are [6, 6]* at 1100 — which is how the second bug was found at all; nobody had looked at the page at that width.

The first version of that check read `grid-column-end`, which computes to `auto` when the span is written as `grid-column: span 7`. Every tile scored the fallback 12, so every two-tile row summed to 24 and the check could not have passed on any layout, correct or not. It reads `grid-column-start` now. A test that fails for a reason unrelated to the thing it is testing is worth as little as one that passes for the wrong reason.


## 1.12.4

**The theme button lied on a machine that prefers dark.** The opening theme comes from `prefers-color-scheme`, and that branch set the attribute directly instead of going through `setTheme()` — so on a dark-preferring machine the page opened dark under a button still reading *"Dark"*. The label names the theme pressing it switches **to**, and it is also the control's accessible name, so the one user who cannot see which theme is showing was told the opposite of what the control does. The preference branch now sets the label alongside the attribute; it still bypasses `render()`, which has no data to draw at that point in load.

The accessibility suite now opens a second page under an emulated dark preference and asserts the pair — attribute and label — on load and after a press. It fails against the previous build, which is why it is here.


## 1.12.3

**The demo now shows the Monte Carlo tile, all three questions.** Four new scenes: *when* the outstanding work lands, the same history asked about **30 items that do not exist yet**, *how many* land by a chosen date with the next-sprint commitment, and *what each ordering of the asks costs the others* — including the asks that miss their date in every ordering and the two the tool could not size.

**Recording it required serving the page.** The tile is answered by `forecast.py` and `intake.py` over the live-mode connection, so `record_demo.py` now starts `serve_live.py` against the demo bundle and drives the page over http rather than `file://`. It serves **the same bundle the page displays** — a different one would have put a disagreement between the tile and the page on film, which is the exact failure this design exists to prevent.

Two small recorder capabilities came with it: typing into a field as a scene action, and waiting for a fetch to land so the video shows the answer rather than the *"running 20,000 simulations"* moment.

Both cuts re-recorded: 2m50s, 11 MB and 3.7 MB.


## 1.12.2

**The 320px reflow failure was a sparkline, not the tile.** With the header fixed, the stricter check found the real remaining offender on CI: the value card's *last 6 sprints* sparkline. A fixed 110px chart sits beside the headline figure in a flex row that cannot wrap, so at 320px the pair overflowed the page — and the endpoint marker made it worse, because a circle centred on the SVG's right edge paints its radius outside the box it belongs to. A 110px decoration measured 324px across on a 320px screen.

The row wraps now, the chart never exceeds its column, and `spark()` insets both axes by the marker's radius so nothing is drawn outside its own SVG. The sparkwrap's right edge at 320px moves from 323 to 283.

**The reflow check now names what overflows.** A bare *"323"* is not actionable, least of all when the cause is font metrics on a machine other than the one running the test — this reproduced on no local configuration, including with glyphs stretched 40%. The check reports the offending elements with their right edges, and CI identified the sparkline on the first run afterwards.

## 1.12.1

**Fixed a WCAG 1.4.10 reflow failure introduced by the third forecast mode.** Adding a *Sequence asks* button made the tile's segmented control 260px wide with `flex-wrap: nowrap` above it, so at a 380px viewport its right edge sat at 364 — inside the card, 16px from the screen. On CI's Linux font metrics those same three labels render wider and the page needed 399px, so it scrolled sideways and the accessibility suite failed.

The fix is structural rather than a shorter label: card headers, their tool groups and the segmented control all wrap now, the title block yields space before either wraps, and below 760px the tools take their own row. The control's right edge moved from 364 to 283 at 320px, and the layout holds with glyphs 40% wider than they render here.

**The suite was checking the wrong width.** WCAG 1.4.10 specifies **320 CSS pixels**; this checked 380, which is softer, and it passed on macOS while CI failed on Linux. It now checks both, and additionally asserts that no laid-out control comes within 8px of the 320px edge — because a control that just reaches the viewport passes on one machine and fails on the next, which is exactly what happened. Against the previous CSS the 320px checks fail and name the offending element; the 380px check still passes, which is the whole point of adding them.


## 1.12.0

**Ask sequencing is on the tile.** A third mode runs `intake.sequence()` for the selected board and shows what `make intake-sequence` shows: what each ordering of that board's outstanding asks costs the others. Asks come from `data/asks/`, matched to the board, and the view follows the dashboard's selection like the other two.

**It leads with the part that ends the argument.** Asks that miss their date in *every* ordering are printed first and separately, because that is not a prioritisation problem — no sequence saves them, and the only levers left are scope, capacity or the date. A planning meeting that spends an hour re-arranging a list which cannot be re-arranged into success is the thing this is meant to prevent.

**Asks it could not size are named, with the tool's reason.** On the demo bundle two of the four are dropped — *too few completed epics to calibrate a t-shirt scale*, *too few completed epics to form a reference class* — and both appear under the comparison rather than vanishing from it. A comparison of two asks that silently began as four reads as the whole picture.

**Still no value score, and still none coming.** The tool's closing sentence is printed verbatim: the delivery consequence of each ordering is computable, the relative worth of the asks is not.

**Honest edges.** A board with no recorded asks says so instead of returning an empty table. A live Jira connection declines with a reason — sizing needs the board's completed epics and its measured interruption rate, which a sprint-at-a-time pull does not carry — rather than assembling a partial dataset and returning a number built on it. And the tile no longer claims to print "the same output" as the terminal command: `make intake-sequence` defaults to a different bundle, so it names the tool and tells you to compare like for like before calling a difference a disagreement.


## 1.11.0

**The forecast tile takes an input, so it answers hypotheticals as well as the sprint in front of you.** *When* accepts an item count and *How many* accepts a date, both defaulting to the selected sprint's own figures. Ask for 30 items against the Storefront team's measured pace and the answer is 41 working days at the 85th percentile; ask how much lands by 31 October and it is 44 items. The same history, a different question.

**An asked-for figure is labelled as one.** The lead line reads *"30 items asked for — not this sprint's 4"*, because a hypothetical that looks like a status report is worse than no answer at all. The endpoint echoes `asked.default_items` and `asked.default_date` so the swap is always visible, and a one-click reset returns to the sprint's own numbers.

**Rejected input says so instead of quietly reverting.** An out-of-range count is refused with `400` at the server and an explanation in the tile — *"0" is not a whole number between 1 and 5000. Showing this sprint's own outstanding count instead.* Silently substituting a different number would return a figure answering a question nobody asked, which reads exactly like an answer to the one they did.

**A bug this feature would otherwise have shipped: the simulation's horizon was silent.** Each trial is abandoned after 400 working days, and a request beyond the team's pace returned every percentile at exactly 400 — uniform, precise and meaningless. Unreachable while the item count came from real sprint data; reachable the moment anyone can type a number. `forecast_completion()` now counts abandoned trials, returns `unfinished_fraction`, and names the horizon in its basis line whenever it is non-zero. The tile prints *"These dates are a floor"* above the table. This is the no-silent-caps rule applied to the forecaster itself, and it holds for the CLI and the agent too, not just the tile.


## 1.10.0

**The Monte Carlo forecast is on the dashboard, not just in a terminal.** A new tile answers the two questions `forecast.py` exists for — *when will this finish* and *how many will land by the date* — for whichever project, board and sprint is selected, and re-runs when that selection changes. The second question also carries the next-sprint commitment sizing, with the tool's note about the median printed as written.

**It is served, not reimplemented.** The tile calls `agent/tools/forecast.py` through a new `api/forecast` endpoint in `serve_live.py`. Nothing in the page computes a forecast; it formats values already in the payload and quotes the tool's own sentences. A second Monte Carlo written in JavaScript would be a second set of numbers, and the tile and a written brief would eventually disagree about the same sprint — the failure this project treats as worst. The trade is stated plainly: **the tile does not work in an emailed file**, where it shows an offline notice instead. It is the first thing here that needs the server to be useful.

**It samples the team's whole history, and says so.** A forecast built from one sprint refuses — on the demo board a single sprint offers 2 throughput observations against a threshold of 8, while the team's six sprints offer 55. So the sample is the team, sliced by `team` and falling back to project+board, and only the *outstanding count* comes from the selected sprint. Conflating those two is exactly the 1.8.0 bug that turned a 19-day forecast into 77 and looked entirely credible. A test pins both halves: the sample must be 55 observations and the remaining count must be 4.

**`build()` now samples every recorded day rather than a 90-day tail.** The old default silently discarded older history on a long import — a smaller sample, and one that can drop under the refusal thresholds for no stated reason. Both the tile and the CLI now pass the full span, because if they sampled different windows they would report different forecasts for the same sprint. **This changes nothing today**: every dataset in the repo spans 76–79 days, so full-history and 90-day sampling are byte-identical on all three, the recorded demo keeps its figures and `agent/snapshots/` stays valid. A test asserts that equality so the day a longer dataset lands, the divergence appears in the suite rather than in a forecast someone has already quoted.

More history means older throughput, and a team's pace from eight months ago may not describe it now. `size_stability()` already reports that drift, and the tile now shows the slice, the date span and the observation count — a wide window should be visible rather than implied.

**New coupling, deliberately.** `scripts/serve_live.py` now imports `agent/tools/forecast.py`; it is the first dependency from `scripts/` on the agent tools. That is the point of serving the real thing.


## 1.9.2

**The source badge denied live connections that were working.** With `make serve-live` running, the page said *"Demo data (no live connection)"* while the very same server was handing it eighteen sprints. Nothing was broken underneath — the probe succeeded, the contexts merged, the project/board/sprint bar appeared, switching worked. Only the badge was wrong, and it was wrong in the most damaging way available: stating as fact that the thing you were demonstrating was not happening.

The cause is that the badge reported one fact while claiming another. It read `meta.sourceLabel` — what the **loaded dataset** says about itself — and never consulted `S.live`, which is the only thing that knows whether a server answered. The bundled demo file labels itself "Demo data (no live connection)", so that string was printed verbatim whether or not a connection existed. The two are genuinely different questions: a live connection can serve demo data, which is exactly what `serve_live.py --bundle` is for.

Now the badge reports the connection when there is one — *"Live: bundle file sample-bundle.json"*, green rather than amber — and falls back to the dataset's own label when there is not. The tooltip states both, because "connected to a demo bundle" is the honest description and neither half should be dropped.

A test pins it in `tests/security.py`, which is the only suite holding both a browser and a running server. It loads the page over http against the live server and fails if the badge denies the connection; that failure was confirmed by reverting the fix, not assumed.


## 1.9.1

**The live-mode server dropped the connection on any 404 instead of sending it.** `log_message()` tested `"/api/" in a[0]` to decide whether a line was worth printing. Two callers reach it with different shapes: `log_request` passes the request line as a string, `log_error` passes an `HTTPStatus`. Membership against a non-string raises — and it raised *after* the 404 had been decided but *before* it was written, so the handler thread died and the client saw a dropped connection rather than a refusal. A browser asking for `/favicon.ico` was enough, which means it fired on every page load in live mode and filled the terminal with tracebacks. During a demo, that is the whole impression.

**The worse part is what it was hiding.** Three path-traversal checks in the security suite were passing *because* of it. They asserted only that `root:` did not appear in the response body, and a dropped connection has no body, so they passed without ever testing traversal. The protection itself was real — `SimpleHTTPRequestHandler.translate_path` collapses `..` before any file is opened, and the 404 was correct — but the tests were not proving it. A check that cannot tell "refused cleanly" from "crashed before answering" is not a check.

Those three now require an actual HTTP status (403 or 404) alongside the absent body, and a fourth asserts that a plain missing file returns a clean 404 rather than a dropped connection. All four fail against the unfixed server; that was verified by reverting the fix and re-running, not assumed.

## 1.9.0

**Tiles can be turned off, so one file can be sent to two audiences.** The **Tiles** button picks which of the twelve tiles a view contains, with an **Executive** and a **Team** preset. Both keep *What this sprint means*: a view without the narrative is the wall of charts this page exists to replace, and sending an executive one is how a dashboard gets skimmed and ignored.

**The presets are the agent's two reports, not a fresh opinion.** Executive is shaped after `agent/templates/exec-brief.md` — will we make it, what changed, what it is worth, what we need from you. Team is shaped after `team-report.md` — where we are, unblock, ageing, flow, what to commit next. The page and the agent describing the same audience differently is a worse failure than either being slightly wrong on its own, so the two are pinned together by a test that asserts each preset's exact tile set.

**Visibility changes what is shown and nothing that is counted.** Every figure still comes from the same `derive()` over the same filtered issues whether its tile is on screen or not, so a tile that reappears agrees with the one beside it. There is a test that hides tiles and asserts the headline numbers are byte-identical afterwards, because the alternative — a view whose numbers depend on which tiles you left on — would be undetectable by eye and fatal to the whole premise.

**A saved view carries the data that is loaded, not the data the file shipped with.** *Save this view as a file* writes a standalone copy with the tile selection and the current dataset baked in. This is the subtle one: after an upload the dataset lives in memory, not in the seed script, so serialising the document alone would have handed someone a file that silently reverted to the demo sprint — correct-looking numbers about the wrong company, which is exactly the failure class this project treats as worst. The test loads a 242-issue bundle, saves a view, reopens the saved file and asserts it still reports 242.

**The view travels three ways** because the file is distributed three ways: baked into a saved copy, honoured by the print stylesheet so a PDF matches the screen, and encoded in the URL (`?view=exec`, `?tiles=…`) for when the file is hosted. **Not in browser storage** — the intended distribution method is email, which storage does not survive, and this file uses none.

**Hidden tiles are named, not counted.** The picker lists what it has dropped. A view that quietly omits a tile reads as a complete page to whoever receives it, which is the same no-silent-caps rule the flow-time chart already follows.

An unrecognised `?tiles=` value shows everything rather than an empty page — a blank dashboard reads as a broken file, not as a deliberate view.

## 1.8.2

**`PUSH.md` and `scripts/setup-on-mac.sh` are gone.** Both existed to get this repository from a delivered zip onto a remote for the first time. That has happened; neither can happen again. `setup-on-mac.sh` hard-coded `$HOME/Downloads/delivery-value-dashboard.zip` as its input, which is the clearest possible statement that its job was one-time.

Almost nothing was lost with `PUSH.md`, because almost everything in it was already in `README.md` — that `dist/` is committed on purpose, that `.env` and `data/dashboard-data.json` are git-ignored, how the fetcher is configured. Documentation that restates another file drifts from it, which is exactly what had happened: `PUSH.md` was corrected in 1.8.1 to say the Pages workflow is manual-only, and the README's deploy section was left still claiming Pages "publishes the demo dataset" with no mention of the trigger. **The README now carries the corrected statement**, including the part that matters — the job publishes the whole of `data/`, not a curated demo subset.

The rule this is an instance of: a document whose purpose is a one-time transition should be deleted when the transition completes, not left as a description of a world that no longer exists.

## 1.8.1

**The Pages workflow is manual-only now.** It triggered on every push to `main`, which meant the decision to publish was made by the act of committing rather than by anyone choosing to publish. The job copies the whole of `data/` into a public site. On a repository where the fetcher has been run, that folder holds real issue titles — the one thing the `.gitignore` entry for `data/dashboard-data.json` exists to keep out of git in the first place.

Nothing leaked. On a fresh repository the job fails at `configure-pages` because Pages is not enabled, which is what happened here. But that is GitHub's account setting standing in for a guard the workflow should have had itself: enable Pages for any reason later and the next commit publishes `data/`, with no step in between where a person decides. The trigger is now `workflow_dispatch` only, so publishing is a deliberate act every time.

This also removes a red cross from every push, which matters more than it sounds — a build badge that is always failing for a known-harmless reason is how a real failure goes unread.

`PUSH.md` said the workflow was "not enabled by default". That was true of GitHub Pages the feature and false of the workflow, which ran on all five pushes. Corrected.

## 1.8.0

**Product intake.** The agent can now forecast an ask before a single ticket exists for it — a described product request plus a named team, in; a sized range with two delivery scenarios and its uncertainty attributed, out. `agent/tools/intake.py`, `make intake`.

The portfolio decision that costs the most money is made at intake, and it is normally made on either a refusal ("we'll estimate it once it's refined", which means the decision gets made on nothing and refinement justifies it) or a bare number ("about six weeks", which is how a guess becomes a commitment in the retelling). This does neither.

**Sizing is a ladder and the rung is always declared.**

- `tshirt` — bands calibrated from the board's **own** completed epics, because an "L" has never meant the same thing on two teams. On the demo board: S 4–6, M 8–12, L 13–21, XL 24–38, cut as quartiles of 16 delivered epics. Fewer than eight completed epics and it refuses rather than cutting four bands from seven observations.
- `reference-class` — every completed epic on the board. Widest range, fewest assumptions.
- `explicit` — a refined min/likely/max as a triangular distribution.

Each prints its own caveat verbatim. The t-shirt caveat says the thing that matters: the band's width reflects only how varied past epics of that size were, **not how wrong the t-shirt judgement itself might be**. That error is bounded by refinement, not simulation, which is why an intake figure is never a commitment and the forecast is re-run afterwards.

**Two capacity scenarios, always both.** *Earliest possible* — dedicated capacity, nothing queued — is a ceiling, not a plan. *Realistic* queues the ask behind committed unfinished work and thins throughput by the board's measured interruption rate (12.4% on one demo board, 3.2% on another; neither number was chosen). Interruption is modelled as a thinned throughput series rather than a multiplier on the final date, so its variance survives into the percentiles. The gap between the two is reported as **the cost of the existing queue in working days** — 30 days on the demo ask, which is the number to quote when someone asks why it cannot start now.

**Uncertainty is attributed, not just stated.** Three simulations — both inputs varying, size frozen, throughput frozen — split the spread between *not knowing how big this is* and *normal delivery variability*. A vague ask on the demo data attributes 54% to size; the same ask refined attributes 10%, and the spread narrows from 34 working days to 19. The first result sends the ask back to refinement with a reason. The second stops a team being told to tighten up an estimate that was never the problem.

**A readiness gate runs first.** `title`, `team` and `sizing` are required or nothing is forecast at all. The rest are reported as gaps with their consequence stated — a value amount supplied without a basis is flagged specifically, because an unsourced number is the one most likely to be quoted back in a steering meeting. The failure mode of any intake tool is making an unchallenged ask look processed.

**Sequencing returns consequences, not a score.** Every ordering is evaluated for what it costs the other asks, and anything that misses its date *in every possible ordering* is reported first and separately — the conversation that otherwise happens six weeks late. **No WSJF, no weighted score, nothing of that family**, and the reasoning is in the code as well as the docs: those formulas multiply an unvalidated value estimate by an unvalidated size estimate and present the product as arithmetic. The delivery consequence of an ordering is computable and is returned; the relative worth of the asks is a judgement and stays with whoever owns it.

**Three scope bugs found while wiring the demo, all of which returned plausible wrong numbers rather than failing:**

- `board_issues()` returned the board's **first** context, not its most recent, so `asOfDate` came from a sprint that ended in June. The trailing throughput window then landed almost entirely in a quarter with no deliveries, and a 16-item ask forecast at **77 working days** instead of 19. This is the worst failure mode a forecaster has — a credible number computed against the wrong slice of the file.
- The interruption rate was read from whichever context happened to be last in the file, so a board could inherit another board's rate.
- `queue_ahead()` ignored its `as_of` argument and counted work raised after the forecast date as already queued ahead of the ask.

All three are now pinned by an `intake — scope` section in `tests/test_agent.py`, which asserts the throughput window contains real delivery, that the implied rate is a working team rather than a stalled one, and that interruption is measured per board.

**Also fixed:** the CLI printed at most four readiness gaps while the verdict line counted all of them, so the output disagreed with itself. Every gap is printed now — a gap you cannot see is a gap nobody fills.

**Added:** `docs/product-intake.md`, `agent/templates/intake-brief.md`, three worked asks in `data/asks/` (one per sizing method, one of which cannot be delivered on time at any priority), `scripts/make_intake_demo.py` and `data/demo-intake-bundle.json`.

The intake bundle is deliberately **separate** from the demo bundle. Intake needs finished epics to calibrate against; the demo bundle's epics are long-lived themes that never close. Adding delivered epics to the main bundle would have changed its throughput, and with it the forecast figures quoted in the demo video and the executive summary. `make bundle` now builds both.

## 1.7.0

**Overtime removed.** The organisation does not operate overtime, and charting hours implied a time-tracking regime that does not exist.

Deleting the line would have left a worse card than the one being fixed: "Sustainable pace" worked because of the pairing — output rising *funded by* overtime is borrowed. With the counterweight gone, "output per person" is a productivity-per-head metric with nothing to check it, which is the individual-performance framing this dashboard refuses everywhere else. So both series went.

The card is now **Team load**, built from two signals that come from issue status and nothing else:

- **Work in progress** — started but unfinished at each sprint's end. Rising WIP with flat completion means more is being started than finished.
- **Unplanned work** — items that arrived after planning. Rising interruption is a triage problem, not a capacity one.

`overtimeHrs` and `teamPutsSP` are gone from the schema, the fetcher, the import pipeline, the generators, the sample data and every document. No hours field remains anywhere.

**Accessibility suite** (`make test-a11y`) — WCAG 2.2 AA against the rendered page in both themes. Found and fixed on first run:

- 67 text nodes below 4.5:1 in light mode. `--muted` was 3.5:1; links and the primary button were 4.3–4.4:1. Fixed with **separate UI colour tokens** (`--link`, `--accent-bg`, `--info-ink`) so the validated chart palette is untouched — the series colours still pass their colour-vision checks unchanged.
- Executive-summary severity icons used white glyphs on every status colour; white on the warning yellow measures **1.8:1**. Glyph colour is now chosen per severity.
- Closing the drill-down panel dropped focus to the document. It now returns to whatever opened it (WCAG 2.4.3).
- The source chip was styled as a status chip, so it tripped the colour-never-alone rule despite not being a status.

**Security suite** (`make test-security`) — found a **real stored-XSS**: the risk register and executive bullets interpolated issue keys and summaries into HTML without escaping. A Jira summary is writable by anyone who can raise a ticket, so this was reachable in normal use. Fixed by moving to a single escape point at output. Also added a `safeUrl()` guard — `esc()` neutralises markup but not a `javascript:` scheme, and the issue `url` field went straight into an `href`.

Now covered: injection through every string field, prototype pollution via `__proto__` and `constructor.prototype`, zero network calls, zero persistence, live-server path traversal and loopback-only binding, XXE and entity-expansion and zip-slip in the XLSX reader, committed-secret scanning, and a dependency audit.

**Also fixed:** `make_sample_bundle.py` emitted a file with empty burndowns unless you remembered a second Makefile command. The browser suite caught it. The generator now completes its own output.

## 1.6.0

**A shareable demo, and an executive summary of the agent.**

- `docs/demo.mp4` — a ~110-second captioned walkthrough. No audio, deliberately: it can be watched in an open-plan office or dropped into a Slack thread. Recorded from the real built file by `scripts/record_demo.py`, so it cannot drift from the product.
- `docs/agent-executive-summary.md` — the agent for a leadership audience: the problem, the value in the terms it will be judged on, how it works, what it will not do, and a four-phase rollout.
- `scripts/make_demo_bundle.py` — a bundle **authored to tell a story** rather than randomly generated. Three boards with deliberately different situations: one over-committed with a 21-day blocker and 32% flow efficiency; one healthy at 67% with commitments sized to actuals; one where 82% of items done reads as 48% of points because the two unfinished items are the two big ones. A demo on random data shows features; this shows value.
- The closing card's forecast figures are generated by running the real forecaster against the demo bundle, not written by hand.
- Two encodes: `docs/demo.mp4` (1600px, 8.7 MB) and `docs/demo-small.mp4` (1200px, 2.9 MB) for email and Slack.
- `make demo` rebuilds both.

## 1.5.1

**Performance measured rather than assumed.** `tests/perf.py` (`make perf`) instruments a real browser at four bundle sizes and reports load, sprint-switch, filter-keystroke and unit-toggle cost.

Findings, at 5,538 issues across 396 sprints:

- Interaction cost is **flat in dataset size** — switching sprint costs the same with 22 issues as with 5,538, because only the selected sprint is ever drawn. Chart redraw dominates and is constant.
- Building the sprint dropdown costs **0.2 ms** whether scoped to the current board or listing all 462 contexts. Scoping it is a usability decision; as an optimisation it saves 0.0 ms.
- The real ceiling is **payload, not CPU**: 2.8 MB, 79% of it the issue array. Stripping null fields and recomputable `workingDays` saves 8% — not enough to justify complicating the format.

No optimisation was made, because none was warranted. The harness is committed so the next such question gets an answer instead of an argument.

`make bundle --scale N` can now clone the demo board set for load testing.

## 1.5.0

**Project, board and sprint filtering.** One file can now hold many sprints, and the dashboard switches between them instantly and offline.

- New `schemaVersion: 2.0` bundle format — `contexts[]`, `contextId` on each issue, per-context burndown/history/releases/DORA. **v1.0 files load unchanged** and hide the context bar, because there is nothing to switch between
- Cascading Project → Board → Sprint pickers, with the active sprint marked and issue counts shown; boards scope to the project and sprints to the board
- **All N sprints** rollup per board. Flow, ageing, distribution, value and risks are valid across it; the burndown and release cards explain why they are not, rather than drawing something meaningless
- Each context's sprint history contains only sprints up to and including itself, so opening a past sprint shows what was knowable then rather than leaking the future into it
- `fetch_delivery_data.py --jira-boards 42,43 --sprints 6` builds a bundle
- **Optional live mode**: `scripts/serve_live.py` exposes `api/contexts` and `api/context?id=`, backed either by a bundle file or by Jira on demand. The page probes for it, merges sprints it does not have as stubs, and fetches one only when selected. Skipped entirely on `file://`, so an emailed copy stays silent and self-contained

**Fixed:** live-loaded issues were being re-tagged with the wrong context id by `normalise()`, so a fetched sprint rendered as empty. Issue coercion is now separable from context assignment.

## 1.4.0

**The dashboard now measures in items by default, with a Points toggle.** This closes the last place where the dashboard and the forecasting agent reported the same sprint in different units.

- One Measure control in the filter row switches the burndown, the Delivered / Pace / Scope-added / Carry-over tiles, the per-person distribution and the commitment history between items and story points
- `burndown[]` now carries `remainingItems` / `scopeItems` / `idealItems` alongside the point series; `history[]` carries `committedItems` / `completedItems`
- Computed in all three places that build a burndown — the browser import, the fetcher, and the new `scripts/rebuild_burndown.py` — and pinned to the same answer by tests
- Table views show both units at once regardless of the toggle, so nothing is hidden by the current setting
- The health score, the executive narrative and the risk register all follow the active unit, and the health tooltip now states which unit it was scored on
- Datasets predating the toggle render in points and say why, rather than showing an empty chart

**Fixed by rebuilding the sample burndown from its own issues:** the hand-authored series claimed 47 points remaining where the issue list said 42. The chart and the issues underneath it can no longer disagree.

## 1.3.0

**Item counts made the unit end to end.** The forecaster never used story points; the recommendation layer still did, which was the same inconsistency wearing a different hat.

- `recommend_commitment()` — Monte Carlo over a simulated sprint, returning how many **items** to commit to at each confidence level. Recommends the 85% figure, not the median
- `size_stability()` — detects the one thing that breaks item counting: a team splitting work smaller, which raises throughput without raising output. Flags drift (cycle time falling while throughput rises) and spread (p85/p50 above ~4)
- `metrics.py` predictability is now item-primary; points are retained for continuity and explicitly marked as not a forecasting input
- Agent definition, team-report template and design outline updated to size commitments in items and to check size stability before quoting any forecast

## 1.2.0

**Reporting & forecasting agent** (`agent/`). Design outline in `docs/forecasting-agent.md`; runnable definition in `agent/SKILL.md`.

- Hard split between reporting (deterministic) and forecasting (probabilistic). The agent narrates and never computes — every figure comes from `agent/tools/metrics.py` or `agent/tools/forecast.py`
- Monte Carlo forecasting over **item throughput**, not story points: 20,000 seeded trials, percentile dates, probability against an existing target date, per-release forecasts
- Refuses rather than guesses below documented thresholds, and the refusal text is required verbatim
- Scope growth sampled from history where available; the frozen-scope assumption is stated inline where not
- Ageing risk reported on two clocks — active time and end-to-end — because the gap between them is the finding
- Change detection against a stored facts pack, with direction and whether it reads as better or worse
- Calibration scoring (Brier, bucketed) over a forecast log, published in the brief footer
- Walk-forward backtest with non-overlapping windows: coverage 50/67/83/100% against nominal 50/70/85/95%
- Worked example exec brief and team report in `agent/examples/`

**Fixes found by the new tests.** Facts pack and dashboard disagreed on flow efficiency (25% vs 22%) from mixing calendar and working days — units are now declared on every block. The facts pack counted twelve weeks of history as sprint scope, reporting 89% complete on a 55%-complete sprint — reporting scope and forecasting scope are now separate. An earlier backtest reported 38% coverage purely from overlapping windows and truncated horizons.

## 1.1.0

**Upload pipeline.** Replaces the previous strict-schema import, which failed on any real export.

- Reads `.csv`, `.tsv`, `.xlsx` and `.json`, including raw exports from Jira and Asana
- `.xlsx` parsed natively — zip and inflate via `DecompressionStream`, no library
- Column auto-matching against a synonym list, with a mapping step that shows every guess and lets you override it
- Date handling for ISO, Jira's `22/Jul/26 3:41 PM`, `Jul 22, 2026`, Excel serial numbers and all-numeric forms; day-first versus month-first is detected per column and **flagged when undecidable** rather than guessed silently
- Mid-sprint additions can be inferred from the sprint start date when no column exists
- Merge mode: layer a value-estimate file on top of a tracker export, updating only supplied fields
- Preview step with counts, the first rows as the dashboard will read them, and warnings for duplicate keys, ambiguous dates and every missing field with its consequence
- **Burndown and the current history row are recalculated from uploaded issues** rather than inherited — the previous behaviour left stale charts under fresh numbers

**Repository.** Split into `src/`, `data/`, `scripts/`, `docs/`, `tests/`, `dist/` with a dependency-free `build.py`, a Makefile, CI that fails on a stale `dist/`, an optional Pages workflow, and an end-to-end browser suite covering four export formats.

**Fixes.** SVG value labels no longer swallow clicks on the bars beneath them. KPI tiles lay out correctly. Cards no longer stretch to the tallest in their row.

## 1.0.0

First version. Single-file dashboard with cross-filtering, drill-downs on every element, table views, computed risk register, health score with disclosed method, dark mode, print layout, CSV export, and the Jira/Asana fetcher script.
