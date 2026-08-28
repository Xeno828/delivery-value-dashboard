# Changelog

## 1.36.0

**A closed sprint got better the longer ago it was, and nothing on screen said so.** Roadmap item 4 begins here, with a bug found on the way in. Every history row — the series behind the predictability chart and the Team load card — was derived from an issue's **current** status: `statusCategory == "Done"` for completion, `== "In Progress"` for work in progress. Both are facts about the fetch, not about the sprint. Three months after Sprint 23 closed nothing in it is in progress and everything anyone ever finished is done, so the row reported **no work in progress and a commitment met in full**, and the further back a reader looked the better the team appeared. This is the class `CLAUDE.md` says to shout about rather than the kind that fails: the output is plausible, and there is nothing about it to check.

**Rows are now derived from dates and keyed to a moment.** That moment is the sprint's own `asOfDate` — its completion date once closed, today while it is running. An item is completed if it resolved by then; it is work in progress if it started by then and had not resolved. An item that was never picked up is neither, because absent is not zero. Commitment and unplanned arrivals were already right: both come from `addedMidSprint`, which the puller reads out of the changelog, and a changelog does not move.

**There were four implementations of that one row; there is one.** The fetcher had two — the single-board path appending to the previous file and the bundle path rebuilding from Jira — and both fixture generators had their own. Only the single-board path was nearly right, and only because it reads the active sprint, where "now" and "the sprint's end" are close enough to hide it. All four now call `history_row()`. The demo generator still scripts its own `flowEfficiency`, because that figure is the story the demo is telling rather than something derived, and it writes over the derived one by name instead of leaving a silent difference.

**Both fixture generators were writing issues that were done tomorrow.** Marked `statusCategory: "Done"` with a resolution date after the as-of date — eleven of them across the two bundles, because the resolution date was clamped to the sprint's *end* while the as-of sat mid-sprint. Nothing read the dates, so nothing noticed. Now that the trend row counts completion by date while the Delivered tile counts it by status, a fixture that disagrees with itself would have put two different completion figures on one screen. Both are clamped to the as-of date.

**Two security checks stopped pinning a property and started pinning the generator.** *"the forecast samples the team but counts only the sprint's remaining work"* asserted `remaining_items == 4` and `throughput_observations == 55`, both copied out of a generated bundle. Regenerating it moved the first and the check failed for a reason unconnected to what it guards. Both figures are now read off the fixture, and the sampling half is asserted as a relationship — observations far exceeding the selected sprint's own working days — rather than a number.

**One field cannot be recovered later, and that is the case for item 4.** Completion, commitment and unplanned arrivals all re-derive correctly at any distance, because Jira keeps the dates and the changelog behind them. What was *in flight* when a sprint closed is gone the moment those issues move on. A stored series is therefore not a cache of Jira — it is the record of the facts Jira stops being able to answer. `docs/data-format.md` carries the rule.

## 1.35.0

**The read-only view of the recipients tile shows names too, which is the surface 1.34.0 said it had not fixed.** A reader who is not a project administrator sees the configuration and cannot change it — that is deliberate, and 1.28.0 records why: hiding it would make a misconfigured board and an unconfigured one look identical, and the person most likely to notice a wrong recipient is whoever is reading the panel. That argument only works if the recipients are legible. Until now they were a comma-separated run of `712020:5ad8ac88-…`, which is a list nobody can notice anything in. It resolves the stored ids exactly as the editable branch does, one row per id, name and state and id together.

**Users and groups are two facts and are no longer one cell.** They were concatenated into a single comma-separated list, which read as one kind of thing; only one of them is an account id, and only one of them can be dead. The groups are already human-readable and stay as text under the names.

**The ids are never lost when the lookup cannot answer.** The editable branch has a fallback for this — it unfolds the *Account IDs* field, which holds them. This branch has no such field, so it renders the ids themselves under the server's own sentence, verbatim: no directory over a local connection, or a reader without "Browse users and groups". An id is a poor answer to *who receives this*; a blank cell is a wrong one.

**A separate function rather than a flag on the existing one.** `wireBriefNames` does four things this does not — it owns removal, re-reads the field the ids came from, races its own requests, and unfolds the disclosure — and sharing it would have meant three parameters that switch its own behaviour off. What is left is the projection, and `showBriefNames` is it. Like the editable branch it never calls `render()`: a re-render on arrival would redraw the tile and fire the same lookup again.

**Structurally tested, and honestly so.** Over a local connection `canEdit` is always true, so no browser suite reaches this branch at all — it exists only on Forge, behind a permission. `picker_checks()` gains the fourth render path for the same attacker-set display name and asserts every name, note and id in it passes through the one `esc()`, plus that the branch calls the resolver rather than printing what it was given.

**`docs/roadmap.md` no longer has a section headed "Item 3, which is next".** Item 3 landed on 2026-08-26 and the table above that section said so, while the section body still described it as unstarted. The body is kept — it holds the correction that item 3 touched item 5, which the original plan did not record, and it now also records that sending through Jira narrowed that dependency without closing it. A section naming what is open replaces the plan-shaped part, and states the dependency facts without ranking them, for the same reason the product refuses to score competing asks.

## 1.34.0

**The account-ID field is folded away, and the named list is where recipients are edited.** 1.33.0 put names under the field and left the field as the thing you typed into. Seen in a tenant, that is the wrong way round: an administrator meets a box demanding `712020:5ad8ac88-…` before they meet anything they can read, and taking somebody off the list means finding their id inside a comma-separated string and deleting exactly that span of it. The list is now the primary view and the editable one — each row has a **×** that removes that person — and the field sits behind an *Account IDs* disclosure.

**Folded, not removed, and the distinction is the whole design.** `docs/forge-deployment.md` records why the field exists: an id must be pasteable where there is no directory to search, and a reader must be able to see exactly what will be stored. The second reason survives the fold, because each row still shows the id beside the name. The first does not — so **both lookups open the disclosure themselves the moment either is told there is no directory**, which is the state every loopback connection is in and the state a reader without "Browse users and groups" is in. Neither ever closes it: somebody who folded it away again meant it. The messages that used to say *"account ids can be entered directly"* now say where.

**Removal is by account id, not by position.** The field is free text and a list typed by hand repeats an id sooner or later; removing one of two identical entries by index leaves a recipient who looks removed and still receives the brief. Every copy of the id goes.

**Nothing here calls `render()` either.** The removal edits one field's value and rewrites one element. The tile is still a form somebody is part-way through, and the sentence naming who was removed says *"Save to apply it"* — the click changes the form, not the stored config.

The list is no longer inside the live region. A region that holds the rows reads all of them back on every refresh; the sentence above it is announced and the list is not, and focus lands on the button that took the removed row's place — or on the search box once the list is empty — rather than on nothing.

**A third render path for the same untrusted string.** A display name now reaches an *attribute* as well as text, in the remove button's `aria-label`, and the sentence confirming a removal is a fourth. `picker_checks()` covers all of them, and asserts the one `esc()` escapes both quote characters, which is the only reason it is safe in an attribute at all.

**Not changed: the read-only view.** A reader who cannot edit this board's recipients still sees raw ids in the summary table. Same problem, different surface, not fixed here. *(Fixed in 1.35.0.)*

## 1.33.0

**The recipient field shows who those ids are.** 1.32.0 gave the picker a name search, which stops anybody needing to *know* an account id to add one. It did nothing for the administrator who opens the tile next and finds `712020:5ad8ac88-…, 60ad2eb506bf0c006a432a17` in the field. A recipient list is a disclosure control, and one nobody can check is not doing its job — the only way to audit it was to paste an id into a user search by hand.

Each audience's ids are now resolved to names underneath the field, in the field's own order, so the two can be read straight down against each other. `GET /rest/api/3/user/bulk` answers the whole list in one request under `read:jira-user`, the scope the search already uses: no new scope, no consent screen, no reinstall.

**The field itself does not change, and neither does what is saved.** The names are a gloss written beside the ids, never over them. The same two reasons as last time: an id must still be pasteable where there is no directory to search, and a reader must be able to see exactly what will be stored.

**Three states, not a boolean.** An id can name a live account, a deactivated one, or nothing at all, and the last two have different fixes — reactivate the person, or delete the line. Collapsing them into one falsy flag is how *"no sprint calendar"* came to be printed for three unrelated causes in 1.28.0, so each row carries a `state` of `active`, `deactivated` or `unknown` and says which.

**Deactivated accounts are shown here and filtered out of the search, which is not an inconsistency.** The search drops them because adding one is a mistake being made now. This is the mistake already sitting in the config, quietly sending nothing at a weekly cadence. Hiding the row would leave a list of names that looks complete and correct while one of its recipients has not read anything for months — the single most useful thing this route can say.

**Every id asked about comes back with a row.** `user/bulk` omits the ids it cannot match rather than reporting them, so reading its response as the answer gives four names for five ids with no way to tell which one is missing: a list that looks complete and is not, which is the failure this codebase pays for most often. The unmatched ids are recovered by asking what came back for each id rather than by counting what came back.

The note above the list **says nothing when there is nothing wrong**. The names are directly below it, so *"3 recipients, named"* over three visible names is noise. It speaks only for what a reader cannot see by looking: an account that will never receive anything, an id that names nobody, and ids beyond the fiftieth, which are not looked up and are counted rather than dropped.

**`route` takes a `URLSearchParams`, which is how `accountId` is sent more than once.** The bulk endpoint has no comma-separated form, and Forge's `route` tag URI-encodes each substitution, so a hand-built query string would arrive with its separators escaped. Assembling the URL and passing it through `assumeTrustedRoute` would also work and would throw away the one guard `route` exists to provide; `tests/test_service.py` fails if that import ever appears.

**Nothing here calls `render()` either**, for the reason the search does not: the tile is a form somebody is part-way through, and re-rendering it to show a name would discard every unsaved edit in it. The lookup writes into one element and touches nothing else. It refreshes when the field loses focus rather than on every keystroke — an account id is thirty-odd characters, and looking one up half-typed asks about ids that do not exist and then says so, which reads as the field being wrong while it is being filled in.

**Two edits leave two lookups in flight, and the slower one must not land second.** Each request is numbered and only the newest may write its answer. Without that, an answer for ids the field no longer holds paints itself over the current one — a list describing something other than what the reader is looking at, which is the plausible-wrong-number class this repository fears most.

**A second render path for the same untrusted string.** `displayName` now arrives from `/user/bulk` as well as `/user/search`, and the id shown beside it is not safe either: the field is free text and the lookup runs before anything has been saved, so the id echoed back is whatever was typed. `ACCOUNT_ID` only refuses it at save time, which is after the row has been drawn. `picker_checks()` in `tests/security.py` covers all three strings; removing any one escape fails it.

Both transports answer the route. Over loopback there is still no directory, and it says so rather than returning an empty list — *"none of these ids exists"* is a far stronger claim than *"there is nowhere to ask"*.

**And the picker has now been used by a person.** The caveat 1.32.0 closed on — proved by its tests and by its route answering, never by a mouse — is retired for the search: a name typed into the tile on the dev site returns a match and puts the account id into the field. The names list added here still wants the same thirty seconds.

## 1.32.0

**A brief was delivered. Roadmap item 3 is done.**

```
INFO 2026-08-26T16:56:19.061Z  weekly brief: 1 board(s), 1 message(s) sent
```

Outgoing mail was switched on for the site and the next fire went straight through. Every stage of the path — the scheduled trigger, the recipient config in app storage, the board read as the app, the calculator's facts and forecast, Forge LLMs writing the prose, the figure guard passing it, the render, and Jira's own notification carrying it — is now proved against a real tenant rather than a stub. `docs/roadmap.md` moves item 3 to done.

The site setting was the last thing between the code and an inbox, and it is worth restating why that took so long to see: a bare `403` from `/notify` says nothing, and the app was discarding Jira's `errorMessages`. *"Outgoing emails disabled"* was in the response the whole time.

**The recipient picker takes a name now.** `searchUsers` shipped in 1.31.0 with no way to reach it; the tile has one. Each audience gets a search box beside its account-ID field: type a name, press Search or Enter, and the matches appear as buttons that append the id and say who was added.

**The field stays, and stays the thing that is saved.** Two reasons it is not replaced by chips: an id can still be pasted where there is no directory to search — over a local connection there is none — and a reader can always see exactly what will be stored rather than a set of chips standing in for it.

**Nothing in the picker calls `render()`, and that is the design rather than an oversight.** This tile is a form somebody is part-way through filling in. Re-rendering it to show a search result would throw away every unsaved edit in it, including the ones made before searching. The results are written into one element and the chosen id appended to the field directly. None of it is page state — it is a lookup somebody is doing, and it lives and dies inside the tile.

Enter in the search box searches rather than submitting the form around it. Without that, typing a name and pressing Enter saves the recipient list *without* the person just searched for, which reads as the search having failed.

**A display name is a new untrusted string**, set by the person it names and exactly as trustworthy as an issue summary — which is to say not at all, and the stored XSS in 1.4.0 came from two call sites that forgot it. Every name and every server note goes through the one `esc()`. `tests/security.py` grew a `picker_checks()` for it, structural rather than executed and honestly so: over a local connection there is no directory, so the browser suite cannot reach that render path. Removing either escape fails it.

The chosen person's identity travels by array index into a list this code just rendered, not through a `data-` attribute holding customer text.

**Not verified by eye.** The tile could not be reached with browser automation — synthetic scrolling moves the host page and not the frame, which is the same limitation that produced the phantom bug in 1.29.5 — so the picker is proved by its tests and by the route working, not by having been used. Worth a look before it is relied on.

## 1.31.0

**The recipient picker takes a name, not an account id.** The config still holds account ids — the notify endpoint accepts nothing else, and an id is not a contact detail — but nobody knows their colleagues' ids, and asking an administrator to paste `712020:5ad8ac88-…` is asking them to get it wrong somewhere a brief then silently goes nowhere. `searchUsers` looks a name up and the picker stores the id.

**That is not the thing [ADR 0014](docs/adr/0014-jira-sends-the-brief-and-the-read-only-rule-bends.md) refuses, and the difference is worth stating** because they look alike. Refused: the app takes an email address and decides which Jira account it belongs to — an identity claim it has no standing to make. This: a person types a name, Jira returns matches, and an administrator picks one. The claim is made by a human looking at a list, which is who should make it.

The search runs **as the reader**, so it offers the people that reader can already see in any user-picker on the site; Jira's "Browse users and groups" permission decides, not this app. Searching as the app would hand an administrator a directory their own account cannot browse. A 403 says so in those words rather than leaving a search box that silently returns nothing — that permission is granted on the site and is not something the manifest can ask for.

**What needed guarding is the projection.** `GET /rest/api/3/user/search` returns `emailAddress`, `avatarUrls`, `timeZone` and `locale` beside the id and the name. Each match is built from an **allow-list of two fields**: a deny-list is one Atlassian release away from leaking whatever they add next. Same reasoning and same shape as the calculator's `clean_dataset`. Deactivated accounts, app users and customer accounts are filtered out — a brief to a deactivated colleague goes nowhere, and without the filter this app's own account would be offered as a recipient of its own brief.

**A count that described a list turned out not to be read from it.** `shown` was `Math.min(usable.length, MAX_MATCHES)` — the same fact expressed twice, agreeing with the list only while the two expressions matched. Removing the cap left it reporting ten while sixteen came back, and the mutation went undetected until the assertion was rewritten to compare the count against the list's own length. It is `people.length` now. A figure that describes a list is read off the list.

Both transports answer the route. Over loopback there is no directory to search, so it says that plainly rather than returning nobody — a search box that answers "no matches" when it cannot search is worse than one that says it cannot.

**Also: the dev site's outgoing mail is off, and this is where to look.** Jira admin → System → **Outgoing Mail** (`/secure/admin/OutgoingMailServers.jspa`) shows `DISABLED` with an **Enable Outgoing Mail** button. It was disabled on 18 August. Nothing in the app can change that and nothing should; it is the last thing between the brief and an inbox.

## 1.30.0

**Item 3 runs end to end against a real tenant. The only thing between it and an inbox is a site setting.**

```
Jira refused the notification with 403. It said: Outgoing emails disabled.
```

Every stage before that ran on live data, and each was blocked by the one before it until it was fixed: the trigger reaching the handler, the recipient config read from app storage and validated, the board read **as the app**, the calculator's facts and a correctly-refusing forecast, Forge LLMs writing prose, the figure guard passing it, `emailBody` rendering it and `notifyPayload` assembling the send. `send:notification:jira` gets the app through the API gate; it does not make a site send mail, and that is a switch no app can declare. [ADR 0014](docs/adr/0014-jira-sends-the-brief-and-the-read-only-rule-bends.md) records it as a precondition for the Marketplace listing rather than something to discover in a support ticket a week after purchase.

**Six failures, none of them the obvious thing, each fixed with a test.**

*The reason existed and reached nobody — three times.* `weekly brief: 1 board(s), 0 message(s) sent` said nothing about why; the per-board reasons were in the returned object and logged nowhere. `composeSection` discarded `proseFrom`'s cause and substituted an empty string, so *no choices*, *stopped early* and *no text* all became "the model returned no prose at all". And `sendBrief` threw away Jira's `errorMessages`, leaving a 403 that could equally have been mail disabled, a missing project permission, or an ungranted scope — three unrelated fixes behind one number. All three now say which.

*`stop` is OpenAI's word.* Anthropic ends a normal completion with `end_turn`, so the truncation guard refused every good answer, three sections at a time. `FINISHED`, `TRUNCATED` and `DECLINED` are explicit lists now, and an unrecognised value is refused **and named** — naming `(end_turn)` is the only reason that took one deploy to find rather than several.

*The model declining is its own category.* `finish_reason: refusal` is neither a bug nor a truncation, and the message it first produced advised adding the value to `FINISHED`, which would have shipped whatever came back when the model had chosen not to answer.

*The model was shown a number and then refused for repeating it.* Figures are listed to it by key, and the key was `p85`; it wrote "85". No slot name contains a digit now — templates keep theirs, since the model never sees a template — and a test asserts it. The guard also had no way out: a weekly trigger would have sent the same prompt and got the same refusal for ever, so a section that fails is now shown the complaint and asked once more, and a model that breaks the rule twice is reported rather than softened.

*`/v1/forecast-context` nests its figures under `sprint_completion`.* `sectionsFor` was written against the flat `/v1/forecast` shape, so `fillSlots` refused for want of figures that were present under another key — the guard working perfectly over a mistake upstream of it. Checkable in this repository at any point and checked only after it failed in production. The test now takes its shapes **from the real tool**: a fixture written by hand would have been written from the same misunderstanding, agreed with the code, and proved nothing.

**Four of the six came from coding against a documented example instead of the SDK's own type declarations**, which were in `forge/node_modules` the whole time. `Content = string | ContentPart[]` — the example showed a string, so a completion whose text arrived as parts was reported as "no text". The types are authoritative; the examples are illustrations.

**And the mutation testing was lying.** It has been measured all session with `grep -c FAIL`. One mutation raised a `KeyError` and aborted the suite — a traceback contains no "FAIL", so a caught mutation read as an uncaught one. Measured by exit status now, and the test that crashed reports a failure instead. Some earlier "not caught" readings in this session may have been wrong the same way; the measurement was as untrustworthy as the synthetic-input results that produced the phantom scrolling bug.

**What the guard did on live output is the part worth keeping.** The model, told plainly not to, wrote figures into its prose. Nothing was sent. That is [ADR 0013](docs/adr/0013-the-brief-is-written-inside-the-tenant.md)'s central protection firing in production over a real board, and it is the one thing here that did not need fixing.

## 1.29.5

**There was no bug. The dashboard scrolls on Forge with a mouse, and 1.29.1 through 1.29.4 were chasing an artefact of how it was being tested.** Confirmed by the only instrument that could settle it: a person with a hand on one.

Both measurements those entries rested on were correct — the frame is fixed at its container height, 1040px, and the app's document is 1498px empty and taller with a sprint loaded, so it overflows. What was wrong was the third clause, *"and it does not scroll"*, which was never established and is false. A frame at fixed height with an overflowing document the reader scrolls is simply how a Custom UI page works.

**Every negative came from synthetic wheel and key events, which do not reach a cross-origin iframe** — the top document handles them. The evidence was in plain view from the first attempt and was read as noise: wheel aimed at the middle of the frame scrolled the *host* page by 78px, which is Jira's nav collapsing and has nothing to do with the app. Compounding it, the automation's screenshot coordinate space changed within the session (1456x827, then 1232x959), so clicks and scrolls were not landing where they appeared to; one click aimed at the centre of the page toggled a control at the top of it.

**What it cost.** Three fixes designed, deployed or nearly deployed, and reverted — `view.resize()` (a method that does not exist), `layout: blank` (moved the chrome and nothing else), `view.emitReadyEvent()` (no effect at 4s, 10s or 16s) — plus a fourth written and reverted unproven. App versions 6.2.0 through 6.8.0 are that thrashing, and four changelog entries argued about a symptom nobody had reproduced by hand.

**The rule, which is the only thing here worth keeping**, is now in `docs/forge-deployment.md` under a heading that says it rather than burying it:

> A negative result from synthetic input against an embedded frame is not evidence. Clicks may land where wheel and keys do not, and the coordinate space can shift between screenshots, so input does not go where it appears to. Before concluding that an embedded page *cannot* do something, establish that the input reached it — or ask a person with a mouse.

**What survives from that session, because it was measured rather than inferred:** the frame's height read from the parent document, and the app's own document read standalone at its CDN URL where it is same-origin. Both stand. So do the two genuine findings — PLAT's 2659 sprints triggering the no-silent-caps refusal exactly as designed, and the dashboard rendering real tenant figures for the first time.

**And the thing that was said to be blocked is not blocked.** The recipients tile is reachable; it always was. Configuring a board and proving the brief end to end is the next step and needs nothing new.

## 1.29.4

**`view.emitReadyEvent()` changed nothing** — 1040px at 4s, at 10s once a sprint had loaded, and at 16s, with zero give on the host page. Third host-side candidate eliminated, after a resize method that does not exist and a layout that only moved the chrome. Reverted; the app is on 6.8.0 with nothing experimental in it.

**And then the more important thing, which undermines two entries above.** Every *"it does not scroll"* result in 1.29.1 through 1.29.3 came from synthetic input, and at least one demonstrably went to the wrong document: wheel events aimed at the frame scrolled the **host** page by 78px — Jira's nav collapsing — which is direct evidence they were handled by the top document and never reached the frame at all. Synthetic key events were no better, and the automation cannot read a cross-origin frame's `scrollTop` to check.

So the state of knowledge is narrower than any of those entries implied:

| | |
|---|---|
| The frame is 1040px and does not grow | **Measured**, from the parent document |
| The app's document is 1498px empty, `overflow: visible`, all 17 tiles present | **Measured**, standalone at the same-origin CDN URL |
| A real reader cannot scroll inside the frame | **Not established** |

**It is entirely possible there is no bug at all** and the dashboard scrolls normally under a real mouse, in which case 1.29.1's "most of the dashboard is unreachable" is wrong and the whole thread of diagnosis was chasing an artefact of how it was being tested. Settling it takes five seconds and a hand on a mouse; it cannot be settled from here.

**A fix was written for the case where it is real, and reverted unproven.** If the host does suppress document scrolling, an element scroller is not the document, so the page can have its own — `html.in-forge .wrap { height: 100%; overflow-y: auto }`, the class set by the bridge adapter because `require('@forge/bridge')` resolving is the only reliable evidence of being inside a frame. It changes shipped behaviour and nothing available here can confirm it helps, so it is not in the tree.

**The rule this leaves behind is worth more than the bug.** Four diagnoses were offered across four entries and three were wrong, all of them downstream of one unexamined assumption: that synthetic input against an embedded frame does what a hand does. It does not, and a negative result from it is not evidence. `docs/forge-deployment.md` says so where the next person will look.

## 1.29.3

**1.29.2 was wrong, and this measures the thing both previous entries argued about.** The frame's own document was loaded standalone from the exact CDN URL the iframe uses — where it is same-origin and readable:

```
tilesInDom: 17,  briefTilePresent: true
htmlScrollHeight: 1498          ← with NO data loaded
html/body overflow: visible, height: auto
```

The document is **not constrained**. It is `overflow: visible`, sized to its content, 1498px empty and far taller with a sprint loaded, against a 1040px frame. **The content overflows**, which is what 1.29.1 said and what 1.29.2 talked itself out of.

**How the false correction happened, because the reasoning was the sound part.** 1.29.2 argued: clicks reach the frame, so wheel events must too, so a document that will not scroll cannot be overflowing. Every step follows. The premise was wrong — the automation's screenshot coordinate space changed between captures, 1456x827 and then 1232x959, so scroll and click coordinates were not landing where they appeared to. A click aimed at the middle of the page toggled a control at the top of it, which was the visible clue and was read as noise. A later scroll that finally *did* move something moved the host page by 78px — Jira's nav collapsing — and stopped, which is what a real negative looks like once the input lands.

The lesson is narrower than "be careful": **a negative result from synthetic input against an embedded frame is worthless without checking the coordinate space first.** Two of the three wrong turns in this bug came from trusting one.

**What is now measured rather than argued:** the document overflows, the frame does not grow, the embedded document does not scroll, and the host page has 78px of give and no more. Most of the dashboard is unreachable in a tenant. That is the bug, unchanged from 1.29.1, now with numbers behind it instead of inference.

**The cause is the host, not this app.** Atlassian documents automatic resizing for Custom UI — the frame grows to the content and the outer page scrolls — and the host performs it. `iframe-resizer` ships inside `@forge/bridge` but serves only the ADF renderer; nothing in the SDK sizes the app's own frame. So the host is not measuring this app, and the inner scrollbar is suppressed because it expects to resize instead of scroll.

**`view.emitReadyEvent()` is the untested candidate** — it exists, unlike the `view.resize()` of 1.29.1, and is plausibly what tells the host the app is ready to be measured. **Not shipped.** Three diagnoses have now been offered and two were wrong; the fourth gets tested before it is written down as an answer.

## 1.29.2

**`layout: blank` was the next hypothesis for the clipped Forge iframe, and it is wrong too.** `jira:projectPage` has no `viewportSize` property; the one that exists is `layout`, default `native`, with `blank` documented as "a completely empty canvas for full viewport customization". Deployed as 6.4.0 the frame measured **1016px** rather than 1040 — it recovered exactly the height of the chrome that disappeared — still `overflow: clip`, still with the host page unable to scroll. Reverted in 6.5.0.

**The useful part is what testing it revealed, because the original reading was backwards.** Clicks *do* reach the iframe — an accidental one hit the theme toggle inside it — so wheel events reach it too, and a document taller than its viewport would scroll. It does not scroll. So the content is **not overflowing the frame; it is being constrained to it**, which is a different bug with a different fix from the one recorded in 1.29.1.

If the host is constraining the embedded document to the frame's height, the fix belongs to this app: the split build needs its own scroll container, a `.wrap` that is `height: 100%` and `overflow-y: auto`, so the page scrolls inside the height it is given instead of relying on the document to grow.

**That is written down as the next experiment and not built.** Two confident diagnoses have now been wrong — a resize method that does not exist, and a layout that changes nothing — and the honest response to that is to confirm the mechanism first rather than ship a third guess. `docs/forge-deployment.md` says how: compare the embedded document's own `scrollHeight` against the frame's height. Overflowing and not scrolling is one bug; not overflowing is another.

## 1.29.1

**The scheduled trigger runs the new code, and the deploy is proved.** App 6.0.0 to the dev site — a scope change, so uninstall and reinstall rather than upgrade, per the runbook's own rule. With `interval: fiveMinute`:

```
INFO 2026-08-26T12:32:48.925Z  weekly brief not sent: the recipient config is not
an object, so no board is configured.
```

`INFO`, the handler's own words. That proves the trigger fires under 6.x, reads the app's key-value store, and refuses through `problemsIn` — everything up to the config check. The interval was restored to `week` and redeployed as 6.3.0.

**It did not get further, and the reason is a real bug in the Forge build that this found.** The Custom UI iframe is sized by a Jira class to its container — measured at 1040px, `overflow: clip` — and the host page cannot scroll. The dashboard is several thousand pixels tall, so **everything below the flow tiles is unreachable**: team load, business value, releases, risks, and the recipients tile. Not clipped visibly, not scrollable, absent. Wheel events over the frame do nothing; `Page_Down` and `End` with focus inside do nothing; Jira's full-screen control does not help.

The part that renders renders perfectly, which is why it survived every deploy since the Forge build existed. `docs/forge-deployment.md` has the reproduction and what has been ruled out.

**A fix was written and reverted rather than shipped.** The obvious cause is a missing `view.resize()`, and an adapter change calling it was written, tested and about to go — until the SDK's own type declarations showed `view` has **no resize method** at all. The guard around it (`typeof view.resize !== 'function'`) meant the code would have done nothing, silently, while reading like a repair and passing a test that asserted the call was present. It is reverted. The finding is recorded with what has been ruled out — the app's CSS is not the cause, and the same page scrolls correctly over loopback — and the first thing to try next is `viewportSize` on the `jira:projectPage` module.

Two smaller things the tenant taught, both recorded in the runbook:

**The no-silent-caps rule fired on real data, correctly.** Pointing the app at PLAT produced *"sprints on board 1: more than 20 pages. 1000 were read and none are reported, because a list cut short here would read as a complete one."* That board has **2659 sprints**. The rule that looked pedantic when it was written is the reason the page said so instead of forecasting from an arbitrary twenty pages.

**And the dashboard rendered real tenant numbers for the first time**: MOBL Sprint 1, 2 of 36 items done, 12 highest-priority open, the oldest at 319 days, from this site's own Jira over the bridge. 1.23.1 recorded that the pipe worked but no figure had travelled it. One has now.

**Still unproven: the app-level board read and the send.** Both need a board with recipients configured, and configuring one needs the tile that cannot be reached.

## 1.29.0

**The scheduled brief reads the board and sends it. Item 3 is built end to end.** The trigger walks the boards in the recipient config, resolves each one's project, pulls its current sprint or window, asks the calculator for the facts and the forecast, has the model write the prose, renders it and sends it through Jira. Every guard between those steps is the one already tested: prose carrying a figure sends nothing, an invalid config sends nothing, a refused forecast is carried verbatim, and one board failing does not take the rest with it.

**This reverses [ADR 0013](docs/adr/0013-the-brief-is-written-inside-the-tenant.md), and the record says so rather than quietly disagreeing with itself.** That addendum declined `asApp()` for three versions on the grounds that reading as the user is why a panel viewer can only see issues they could already see in Jira — permission mirroring, roadmap item 5, holding for free.

What changed is `restrict`. When the addendum was written, the app would have read a board with no user and mailed the result with nothing anywhere checking that the recipients could see any of it. Every notification now carries `restrict: {permissions: [{key: BROWSE}]}`, so **who may receive a brief is Jira's decision rather than this app's claim**.

**What is still true is the residual risk, and it is stated in both records.** `restrict` filters against the anchor issue, not against the issues named inside the message. Most boards share one permission scheme and are covered. A board using issue-level security is not: a recipient who may browse the anchor and not some other issue is still told about the other. Item 5 is narrowed here, not closed.

**The panel is untouched, and the authority is now something a read has to state.** `jira(as)` replaces nine `api.asUser()` call sites, defaulted to the user so a read added without thinking is added on the safe side; the scheduled path passes `'app'` at every hop rather than inheriting it. Two reads may never take it and a test names them: the permission check behind the recipient editor — which asks whether *this reader* may administer the project and would cheerfully answer yes to itself as the app — and the connection probe.

**That test exists because threading the mode introduced the same bug twice in one sitting.** `jira(as)` was left inside `editabilityFor` and inside the `context` resolver, neither of which has an `as`. Both bundle cleanly, because a free variable is not a syntax error, and both are a `ReferenceError` the first time a tenant opens the page — a class this repository has been bitten by before, where the failure is invisible until it is in front of a customer. It is structural now: every `jira(as)` must sit inside a function that declares one, and the check walks each call back to its enclosing function to prove it.

**`sectionsFor` chooses which figures each audience carries and does no arithmetic.** `facts` holds `items_done_pct` and it is deliberately unused: turning 0.6942 into "69%" is a calculation, and the moment this file does one, a figure in a brief is a figure no tool produced. Counts say the same thing and need none. The executive brief is shorter than the team's and carries the *same* numbers — two audiences reading different figures about one sprint is how a meeting becomes an argument about arithmetic.

**Unproven in a tenant, and that is the honest state.** Everything here is exercised against stubs and fixtures; nothing has read a real board as the app, and no brief has arrived in anyone's inbox. The cheapest way to settle it is the one that worked before — set `interval: fiveMinute`, deploy, watch `forge logs`, restore `week` — and it now needs a board with recipients configured against a real anchor issue.

## 1.28.0

**Each board now has its own recipients, set from the dashboard by a project administrator.** A new tile — *Who receives this board's brief* — reads the configuration over whichever transport the page has, and writes it back through the one route in the product that changes anything. One board can go to leadership and another to its own team, which is what item 3 always described and nothing could express.

**The gate is Jira's answer, not ours, and it fails closed.** `permissions.js` asks `/rest/api/3/mypermissions` for `ADMINISTER_PROJECTS` and accepts `havePermission === true` and nothing else — not truthy, exactly true. A shape change or a proxy that stringifies a body would otherwise make `"false"` a yes and turn every viewer into an administrator. It is asked again on the write rather than carried from the read, because the read happened whenever the tab was opened and permissions change. A check Jira could not answer is a refusal that says so, which is a different sentence from *you are not an administrator* and the reader can act on one of them.

**A viewer who cannot edit sees the configuration anyway.** Hiding it would make a misconfigured board and an unconfigured one identical, and the person most likely to notice a wrong recipient is whoever is reading the panel — not the administrator who set it and moved on.

**The tile validates nothing.** It sends what was typed and renders what came back. A third opinion about whether a config is usable, after the two that already exist, is precisely the failure this repository keeps paying for.

**Which brings up the two that exist.** `serve_live.py` needed the same validation in Python, and that is a second implementation of one rule — the thing this repository most reliably regrets. It is here on the same terms as `orgconfig.validate` and `validateOrgConfig`: `tests/fixtures/recipient-configs.json` is one set of nineteen cases, both implementations judge all of them, and a disagreement fails. The alternative was for loopback to refuse the route, which would leave the editing half of the tile exercised by nothing — it runs only in a browser, and the browser suite runs against that server.

The agreement test compares **verdicts**, not wording, and one consequence needed pinning separately. The rule that names an email address as an email address is *redundant* for the verdict — `@` is not in the account-id character class, so an address is refused either way — and exists solely so the sentence explains itself. Deleting it changes no verdict and would have broken nothing, which is exactly how a good message rots. Both implementations are now held to saying it.

**A GET that mutates is a GET a browser will make on its own**, so saving is a POST over loopback. The bridge has no verb — `invoke()` names a route — so the asymmetry lives in the two adapters and not in the caller: `LIVE.put` looks identical to the tile whichever transport answered. ADR 0009 intact.

**The route-parity test was hardcoding the answer and now derives it.** It listed four route names and asserted the page asked for nothing else; a fifth route meant editing the list. It reads `ROUTES` out of `src/app.js` instead, and gained the other half of the contract it was only ever checking one side of: every route the page can ask for must also be served by `serve_live.py`, or live mode works on Forge and silently does nothing locally — the same divergence ADR 0009 exists to stop, arriving from the other side.

**Found by looking at it rather than by a test.** The tile's first stylesheet used `--line` and `--surface`, which do not exist here. A missing custom property is not an error — it is a silent fallback — so every input drew a **pure white** border on a transparent field. Nothing failed, because white on near-black passes contrast comfortably, and it read as a deliberate high-contrast choice rather than a typo. The tokens are this stylesheet's own now (`--border`, `--surface-1`, `--text-secondary`), and the comment says to check a token exists before using it.

Verified end to end over loopback: an email address is refused with the sentence that explains why, a valid configuration saves, and the values survive a reload — read, write and read again, through the same contract Forge answers.

**Still not done, and it is the same one line as before.** Composing a brief means reading the board with no user, which ADR 0013 declined and `restrict` only partly answers. The trigger still refuses, and now it refuses with recipients configured and a send that works.

## 1.27.0

**The brief is an email now, and the send is written and proved against stubs.** `mailbody.js` renders one audience's brief as `subject`, `textBody` and `htmlBody`; `compose.js` takes figures to a sent message; `index.js` posts it to `/rest/api/3/issue/{key}/notify` as the app. Static HTML with inline styles and no `<style>` block — mail clients strip those and the ones that do not disagree about which — and a plain-text part beside it, so a client that refuses HTML gets the brief rather than an empty message.

**This is the first place issue text leaves for a page this repository does not control**, and it needed two different defences because escaping only answers one of them.

The first is the familiar one. A Jira summary is writable by anyone who can raise a ticket, a board name by anyone who can make a board, and the stored XSS in 1.4.0 came from two call sites interpolating `i.key` and `i.summary` directly. Every string passes through one `esc()` at the point of output — character for character the one in `src/app.js`, with a test holding the two together, because a second escaper covering four of the five characters is the shape this bug arrives in. URLs go through `safeUrl()`, so a `javascript:` board link is dropped rather than rendered.

**The second was found by writing the test and is a different bug entirely.** The subject line is a mail *header*, and a header ends at a newline. A board name carrying `\r\n` would have closed the Subject and begun whatever came after it — header injection, which escaping does nothing about: `&#10;` is harmless in a body and irrelevant in a header. Subjects are now flattened, stripped of C0 controls and capped at 200 characters with an ellipsis, because a truncated subject reads as a complete one. Jira very likely strips this too; that is not a reason to pass it on.

**Mutation testing earned its place here.** Removing the escape from the section body passed every assertion in the file. The fixture put hostile text in the board name and polite sentences everywhere else, so the path that actually carries issue text — a section's prose plus substituted figures, and `reattach` puts summaries back on `item_risk` rows before any of it is rendered — was never exercised. The fixture now carries markup in the body and the heading, and removing that escape fails two checks.

**Nothing reaches an inbox that the guards would have stopped.** Prose carrying a figure fails `brief.js` and sends **nothing** — not a shortened brief, not the sections that passed. A recipient config that does not validate sends nothing. A refused section is carried verbatim and set apart visually, because a refusal is a statement that was answered rather than a paragraph that happened to be short. And Jira refusing one audience does not take the other with it: they are separate messages to separate people, and at a weekly cadence the second would otherwise wait a week for somebody else's problem.

`restrict` is built inside `notifyPayload` rather than passed to it, so no call site can leave it out. A send assembled by hand that happens to omit it still succeeds, still delivers, and has quietly dropped the only permission filtering in the product.

**One decision was deliberately not taken, and the trigger stops in front of it.** Composing a brief means reading the board, every read in `index.js` is `api.asUser()`, and a scheduled run has no user to be. Making those `asApp()` is what [ADR 0013](docs/adr/0013-the-brief-is-written-inside-the-tenant.md) declined — reading as the user is why a panel viewer can only see issues they could already see in Jira. `restrict` moves that part-way: who *receives* is now checked by Jira. What is still unchecked is what the brief *says*, since the anchor's BROWSE gates delivery and not the issues named inside. Most boards share one permission scheme and are covered; one using issue-level security is not.

So the handler refuses with that sentence, and everything after the read is written, exercised and waiting. Turning it on is one line and a record saying why — writing it quietly would have spent a security property inside a commit about email formatting.

**`forge/src/compose.js` is a new file and the reason is testability, not tidiness.** `index.js` imports the Forge SDK and cannot be loaded outside Atlassian's runtime, so anything left in it is provable only by deploying and watching a tenant. The model and the send are injected there and the tests stub both, which is how the code that decides what reaches somebody's inbox gets exercised without one.

Also fixed: the assertion that the trigger's body makes no `asUser()` call was matching the comment that *explains* why it does not. Comments are stripped before the search now, and a real call still fails it.

## 1.26.0

**Jira sends the brief, so item 3 crosses no boundary at all.** ADR 0013 closed one of item 3's two crossings by writing the brief with Forge LLMs; it left the other open and said so, because mailing a file means a mail provider and Forge has no SMTP. It does not have to. `POST /rest/api/3/issue/{issueIdOrKey}/notify` sends through the same machinery Jira already uses to tell someone their issue was commented on, and the brief never leaves Atlassian. [ADR 0014](docs/adr/0014-jira-sends-the-brief-and-the-read-only-rule-bends.md).

**Recipients are Jira identities and cannot be email addresses**, which is a privacy improvement rather than a limitation. The `to` object takes `users` by `accountId`, `groups` and `groupIds` and has no field for an address, so the config holds no contact details at all — a leak of it discloses who is interested in a board, not how to reach them. `recipients.js` refuses an address rather than resolving it: looking one up would mean this app deciding that the person at that address is that Jira user, which is an identity claim it has no business making. The refusal says that, because it is the thing somebody will otherwise try to be helpful about.

**There is a `restrict` block, and it is constant.** `permissions: [{key: BROWSE}]` on every send, so Jira drops recipients who may not see the anchor issue — the only permission filtering in this product that is enforced by the platform rather than asserted by us. It is **partial** and is recorded as partial: it filters against the one anchor issue, not against every issue the brief names, so a reader who may browse the anchor and not some other issue is still told about the other. That gap is roadmap item 5 and nothing here closes it.

**The cost is attachments, and what ships instead is the view as static HTML.** The endpoint carries `subject`, `textBody` and `htmlBody` and nothing else, so the self-contained file — the artifact, and the roadmap's whole thesis — cannot travel this way. What goes is the tiles, the figures and the written brief rendered as static HTML in the message body. Email clients strip JavaScript regardless, so no interactivity was ever going to survive an inbox; what is lost is a file the reader can save and reopen. It still arrives in an inbox and opens without a login, which is the half of the thesis that was doing the work.

**The read-only scope rule became an allow-list, and that is a real constraint bending.** Every scope in `forge/manifest.yml` began with `read:` and `tests/test_service.py` asserted it. Two now do not: `send:notification:jira`, because there is no read-only way to send mail, and `storage:app`, because the recipient config lives in the app's own key-value store. Neither grants write access to customer data and neither can address anyone outside the site.

The rule was never the prefix — it was that reach gets added deliberately, by somebody who wrote down why. So the assertion moved rather than went: a non-read scope must now appear in a named allow-list **and** carry a justification beside it in the manifest, checked by the test. That is stricter than what it replaced, which would have waved through every read scope Atlassian ever adds without anyone looking. Adding `write:jira-work` fails it; deleting the comment above `send:notification:jira` fails it.

**Rejected: the Jira project property, which was the obvious home.** `orgConfig` already lives in one and Jira would enforce the project-admin permission on the write for us, which is better than checking it ourselves. It costs write access into the customer's project to save a setting. Trading *no access to customer data* for *narrow write access to it* to avoid implementing one permission check is the wrong direction, and the check is a dozen lines. Reading `orgConfig` from a project property is untouched.

**Project administrators decide who receives a board**, checked against Jira's own answer from `/rest/api/3/mypermissions` rather than inferred from group membership. Site admin was the first instinct and would have put one person between every team and their own board's recipients, which is how a feature stays switched off. A viewer without the permission sees the active configuration and cannot change it — hiding it would make a misconfigured board indistinguishable from an unconfigured one, and the person best placed to notice is the one reading the panel.

**What the validation refuses, and why each one is a real failure.** An audience with no recipients, because sending to nobody looks identical to sending successfully and at a weekly cadence nobody notices for a month. A board entry naming neither audience, because a board that is listed and silent reads as a board that is covered. A display name, because two people share one. A missing or malformed anchor issue, because Jira has no site-wide send and the anchor is also what `restrict` filters against. And one broken audience refuses the **whole board** including the audience that was fine — the entry was written by one person in one sitting, and sending half of what they asked for while saying nothing is exactly the failure this file exists to prevent. Every case mutation-tested.

**Not done, and none of it is started.** The static-HTML email body, the send itself, the config UI in the dashboard view, and the project-admin gate around it. What exists is the decision, the scopes, and the model that says who a board's brief goes to — the parts that are pure enough to test without a tenant. `forge lint` passes the new scopes as 0 errors, 0 warnings and one `MAJOR_VERSION_RULE` approval for the scope change, which per `docs/forge-deployment.md` is the case that needs a **reinstall** rather than an upgrade.

## 1.25.2

**The handler runs, and it refuses exactly as written.** Proved by shortening the interval rather than waiting a week — `interval: fiveMinute`, deployed as 5.2.0, three fires five minutes apart to the second:

```
INFO 2026-08-26T07:44:17.475Z  weekly brief not sent: no board is configured for this
installation to report on. A scheduled run has no user and no project context, so unlike
the panel it cannot infer one from where it was opened. no recipients are configured for
this installation. … no mail transport is declared, so there is nowhere to send it. …
```

`INFO`, not `ERROR`. That single word is the whole result: the same trigger that threw `TypeError: … reading 'functionKey'` twice on 2026-08-24 now reaches `index.weeklyBrief`, so the rewiring in 1.25.0 is confirmed in a tenant rather than argued from documentation. All three blockers came out, in the order they are written in — board first, because without it there is nothing to compute at all. The interval was restored to `week` and redeployed as 5.3.0; an interval change is a minor version, so neither switch needed an approval or a reinstall.

**This corrects 1.25.1, which drew the wrong conclusion from silence.** That entry reported zero invocations in thirty-one hours and offered two explanations — Forge disabling a trigger after consecutive failures, or the version 3 scope change leaving it unable to run. **Both are now excluded.** A trigger that fires three times on schedule is not disabled, and the installation it fired under is the one the scope change produced. The silence was a weekly interval that was not due, which was the dull explanation available the whole time and the one not reached for.

What remains genuinely unexplained is narrower and no longer alarming: why the only two fires under version 2 were two and a half hours apart under `interval: week`. No theory here survives contact with the rest of the timeline — a post-deploy fire would have produced one after version 4 and after 5.0.0, and neither happened. It is left as unexplained, because that is what it is.

**The lesson kept from 1.25.1 is the one that was actually right, and it is sharper now.** A trigger that fails writes a line and a trigger that has not come due writes nothing, so an absence of logs carries no information at all — it cannot even distinguish *broken* from *idle*. `docs/forge-deployment.md` now says to establish liveness by shortening the interval, which takes about ten minutes and answers the question outright, instead of reasoning about a cadence.

The near miss is worth stating plainly. The failure was real and the fix was right, but the *diagnosis* published in 1.25.1 was a plausible story fitted to missing data — the exact failure mode `CLAUDE.md` names as this project's worst, arriving in a changelog entry instead of a forecast.

## 1.25.1

**App version 5.0.0 is deployed to the dev site, and the platform confirmed the claim ADR 0013 rests on.** `forge lint` passed the `llm` module as *0 errors, 0 warnings, 1 approval* — `MAJOR_VERSION_RULE`, *"Change due to usage of core:llm module"* — and it deployed with `--approve`.

`forge eligibility` at 5.0.0 reports **exactly two findings, both the calculator**: *app is using remote services*, *app is egressing data*. Adding an Atlassian-hosted model added neither. That is Atlassian's own checker agreeing that the brief is written inside the tenant and the issue titles it reads do not leave — the cheapest evidence available for the decision, and better than an argument from documentation. The *Runs on Atlassian* badge is still forfeit for the reason ADR 0008 accepted deliberately, and nothing about that trade moved.

**A module upgrade takes, where a scope change does not, and the runbook now separates them.** `docs/forge-deployment.md` §"After changing a module or a scope, reinstall" was written after a scope change silently failed to widen an existing consent. A module added on its own behaves differently: `forge install --upgrade` moved the same installation id from `4 / Outdated app` to `5 / Up-to-date` with no uninstall.

Worth knowing because the upgrade prints *"The scopes or egress URLs in the manifest are different from the scopes in your most recent deployment"* immediately before succeeding — on a run where no scope had changed and the deploy was two minutes old. Read as the failure that section describes, it would send you into a reinstall for nothing. `forge install list` is the only thing that answers the question.

**The trigger did fire, twice, and failed both times — so the bug fixed in 1.25.0 is observed rather than predicted.** Seven days of `forge logs` hold exactly two entries, both on 2026-08-24, both this:

```
ERROR 2026-08-24T15:04:28.071Z  TypeError: Cannot read properties of undefined (reading 'functionKey')
    at Object.handler (@forge/resolver/out/index.js:31:33)
ERROR 2026-08-24T17:33:57.336Z  TypeError: Cannot read properties of undefined (reading 'functionKey')
```

That is the scheduled event reaching `resolver.getDefinitions()`, which reads `call.functionKey` off a payload that has no `call`. 1.25.0 reasoned it out of the platform documentation; this is the same failure with a timestamp on it.

**And then it stopped firing, which is the more useful finding.** Both fires happened under major version 2 (deployed 12:23Z, 4 scopes). Since version 3 — deployed 08-24T18:37Z, and the first with 7 scopes — there have been **zero invocations in over thirty-one hours**, spanning versions 3, 4 and 5, including four hours on version 4 before any of this work started and seven on version 5 after it. Under version 2 the cadence was roughly one fire every two and a half hours, which is itself not the weekly interval the manifest asks for.

Two explanations fit and nothing here separates them: Forge disabling a trigger after consecutive failures, or the version 3 scope change leaving it in a state where it does not run — the same scope change `docs/forge-deployment.md` already warns silently fails to widen an existing installation. **Recorded as unexplained rather than resolved**, because a plausible reason written down as a fact is exactly the failure this repository treats as its worst.

**The hazard is worth naming on its own.** A scheduled trigger that stops firing reports nothing at all. The two failures at least reached a log; thirty-one hours of silence is indistinguishable from an interval that has not elapsed, and if the platform does disable on failure then a fix deployed afterwards never gets the chance to prove itself while the app reports healthy throughout.

**So the fix is deployed and still unexercised.** Version 5 carries `Functions: 2` and `llm: 1` and the installation is on it, which is structural confirmation that the rewiring shipped — not that the handler has run. Those are different claims and this is the weaker one, exactly as 1.23.1 recorded for the forecast. The app was uninstalled and installed fresh on 2026-08-26 at 06:10Z to try to re-arm it; **the new installation ARI is not the one 1.23.1 quoted**, so the calculator's access log will name a different tenant from here on.

When it does fire it will refuse, with the three sentences it is written to refuse with, before making a single Jira call.

## 1.25.0

**The `llm` module is declared and the weekly brief has a handler — and wiring it found that the trigger had been failing on every fire.** `weekly-brief` had pointed at the `resolver` function since the day it was declared. Forge invokes a scheduled trigger's function directly with an event; `resolver.getDefinitions()` returns a dispatcher expecting `{ call: { functionKey } }` and does not recognise one. It has its own function now — `weekly-brief-fn`, `index.weeklyBrief` — and a test holds the two apart: the trigger's function must not be the resolver's, and the export it names must exist.

This was written as a prediction from the platform documentation. 1.25.1 records the log lines that show it happening, which are better evidence and change one word of it: not *would have failed*, **did fail**.

`forge lint` reports 0 errors, 0 warnings and one `MAJOR_VERSION_RULE` approval reading *"Change due to usage of core:llm module"*, which is the reinstall cost [ADR 0013](docs/adr/0013-the-brief-is-written-inside-the-tenant.md) predicted, stated by the platform rather than by us.

**The larger finding is that a scheduled send has no user, and that changes what item 3 depends on.** Every Jira call in the resolver is `api.asUser()`, and all of them throw in a trigger. The obvious repair is `asApp()` and it is the wrong one: reading as the user is *why* a viewer of the panel can only ever see issues they could already see in Jira. That is roadmap item 5, permission mirroring, holding for free because Jira enforces it on every request made on someone's behalf — and nothing else in this product establishes it.

A brief composed by the app and mailed to a list asserts that every recipient may see every issue the app can, with nothing behind the assertion. The failure is the quiet kind: a brief naming an issue from a project the reader cannot open looks exactly like one that does not. **So item 3 depends on item 5, and `docs/roadmap.md` said item 1 was its only dependency.** The ordering was already right — item 5 is described there as the most expensive thing to defer — but the dependency was not written down, and now it is.

The trigger does not reach for `asApp()` to get past the missing user. Two assertions hold that shape: the trigger's own body contains no `asUser()` call, and the file still makes them everywhere else. Converting the resolver wholesale to `asApp()` to make the trigger work would look like a fix and fails both.

**It refuses with three sentences and does no work first.** No board configured to report on, no recipients, no mail transport. The board is first because without it there is nothing to compute at all — a scheduled run has no user and no project context, so unlike the panel it cannot infer a board from where it was opened. All three are checked before a single Jira call, so a weekly run that cannot deliver costs one invocation rather than a board's worth of reads and a model completion nobody receives.

**What was deliberately not written is the pipeline itself.** Reading a board, calling the calculator, composing per audience and handing off to a transport — every piece of that exists and is tested except the two that do not exist at all. Writing it against an imagined recipient shape and an imagined transport produces code that compiles, ships, and is wrong in ways no test can catch, because there is nothing real to check it against.

**The prompt and the guard now have to want the same thing, and a test says so.** Figures reach the model as named values — `- throughput: 9` — never written into a sentence, because prose the model is shown is prose it copies, and a copied figure is refused by the guard the brief depends on. A prompt that cannot produce a passing answer would have failed every week for a reason invisible from the prompt. A refused figure is *named* to the model so it does not write around a gap it cannot see, but its sentence is withheld: handing over the wording is what invites the paraphrase ADR 0013 forbids.

A truncated completion is discarded rather than used — `finish_reason` anything but `stop` — because half a paragraph reads as a whole one and the reader has no way to tell. Every new assertion was mutation-tested, including that the manifest checks are read without PyYAML: it is not a dependency here, CI installs only `service/requirements.txt` for this suite, and adding a parser to the *service's* requirements to read a *Forge* file would put a package in the production image that nothing in it imports.

## 1.24.1

**Editing a README redeployed both Cloud Run regions, and now it does not.** `deploy.yml` filtered on `service/**`, so pointing `service/README.md` at the new roadmap doc in 1.24.0 rebuilt and shipped the calculator twice over. It came out green — the image was unchanged and every gate ran — which is the pipeline behaving exactly as `docs/hosting-the-calculator.md` §7 claims, but it is still a deploy nobody asked for and it would have recurred on every future edit.

Excluding `service/**.md` is provable rather than a guess: the Dockerfile copies `service/requirements.txt` and `service/app.py` **by name**, so nothing else under `service/` can reach the image.

**The narrowing is deliberately asymmetric, and that is the part worth reading.** `agent/tools/**.md` is *not* excluded, because that tree is copied wholesale — `COPY agent/tools/ /app/agent/tools/` — so a markdown file added there does ship, and skipping its deploy would leave the running service older than the source describing it. A path filter fails silently in both directions: too broad is noise, too narrow is a stale service, and only the second is dangerous. Neither shows up as a red run, which is why this is now a test rather than a comment.

`test_the_deploy_trigger_covers_everything_the_image_ships` reads the Dockerfile's `COPY` sources and asserts each one still triggers a deploy, that no exclusion reaches inside a directory copied wholesale, and that the README exclusion holds. Adding the tempting `!agent/tools/**.md` fails it, which is the whole point — it looks like the same tidy-up and is not.

## 1.24.0

**The commercial roadmap is in the repository now, and that is the smallest change here with the largest effect.** Four files have said *"roadmap item 1"* or *"roadmap item 6"* since 1.14.0 and none of them pointed at anything — the plan lived in an artifact outside the repo, so every session that set out to progress it began by asking where it was, and two in a row stalled on exactly that. `docs/roadmap.md` records the numbering those four references depend on and what is true of each item today. It deliberately does **not** restate the argument: that stays in the artifact, because two copies of an argument disagree eventually. The numbering had one trap worth writing down — seven numbered items, nine features, because item 6 is three of them, so a reader who counts headings gets seven and concludes the references are wrong.

Items 1 and 2 are done, and a third of item 6 landed early as a side effect of the Cloud Run work. **Item 3 — scheduled delivery of the two views — is next by the roadmap's own dependency rule rather than anyone's judgement**, and it is started here.

**It nearly became the first feature to send customer issue text out of the tenant, and it was one question away from doing so quietly.** Item 3 mails a written brief on a timer. `agent/SKILL.md` is an agent definition and nothing on a Forge schedule can execute one, so the obvious implementation is an API key, a third-party model endpoint and a declared egress — every issue title on the board through a provider the customer has no relationship with, weekly, to produce a paragraph. That was the plan of record for about an hour.

Forge LLMs is the answer instead: `@forge/llm` reached GA in July 2026 and runs Atlassian-hosted Claude inside the platform with no egress, so the model reads the tenant's real issue titles without them leaving the boundary the customer already agreed to when they filed the tickets. The brief is genuinely written rather than filled in from a template, and the crossing does not happen. [ADR 0013](docs/adr/0013-the-brief-is-written-inside-the-tenant.md) records it along with the tightening that was rejected on its own merits — projecting the issues before prompting, the way `service/app.py` does — because that projection exists to guard a crossing that no longer happens here, and a brief written without titles cannot say which piece of work is stuck.

**What still crosses is the file.** Mailing a self-contained HTML file hands issue titles to a mail provider, and Forge has no SMTP. One crossing rather than two, which is a materially easier thing to defend at Marketplace review. Adding the `llm` module is a major version upgrade and a forced reinstall for every tenant — free today because there are no external installs, and expensive after the first one, alongside the two other deferred major-version changes `forge/manifest.yml` already carries.

**The guard is the part that had to be right, and it is a rule rather than a check: the model never writes a number.** A brief is a template with named slots, tool output fills them by substitution in code, and the model writes only the sentences between. A model given figures will restate them, and a restatement is a second copy of a number that can disagree with the first — [ADR 0005](docs/adr/0005-tools-compute-the-agent-narrates.md)'s rule arriving at the one place ADR 0005 did not anticipate.

The alternative was to let the model write figures and check them afterwards against the tool output. It was rejected because checking that a numeral in prose matches a number in a dict means knowing which figure that numeral was meant to be, and getting that wrong in the permissive direction passes a wrong number — the failure class this repository treats as its worst, because it looks exactly like a correct one. Forbidding the numeral needs no such judgement.

**Refused sections never reach the model's output path at all.** Not summarised, not placed underneath, not softened. A model asked to write readable prose around *"too little completion history to sample from"* produces something that reads like a wide interval, which is the single thing that sentence exists to deny. So the tool's sentence is printed verbatim and what the model wrote about that section is discarded — the test feeds it deliberately confident prose about delivery being on track and asserts not a syllable of it survives. The refusal in that test is the one `forecast.Refusal.sentence()` really produces, piped through the JavaScript and compared on the way out; two hand-written copies of that string would have passed while the product paraphrased.

Four smaller things the tests pin, each of which was a plausible way to get this wrong. A figure the tools did not return refuses and comes back with **no** half-rendered text beside the complaint, because a caller reading `text` first would send *"Throughput was  items"* and the reader supplies the missing number themselves. A measured zero is a figure and not an absence — ADR 0010 applied backwards would refuse a correct brief. One unusable section stops the whole brief rather than shrinking it, because a brief that does not arrive is noticed and a brief that quietly lost a section is not. And the number-word list is finite, so `UNCHECKED` says out loud what it cannot catch — quantities carried without a numeral, and prose that contradicts a refusal rather than restating a figure. A bounded check that reads as a total one is the failure this repository has had twice.

The word list is matched whole-word rather than as a substring, which is the difference between a guard and a nuisance: *often* contains *ten*, *someone* contains *one*, *behalf* contains *half*. All three are in the fixture.

**What is not done.** Nothing is deployed and nothing has been mailed. The `weekly-brief` trigger declared in `forge/manifest.yml` since the app was registered still has no handler; the `llm` module is not declared; there is no mail provider, no recipient configuration, and no assembled file. What exists is the decision, and the half of it that is pure enough to test without a tenant. Per-tenant recipient configuration — which audience goes to which addresses — is the same unanswered question that leaves `intake.sequence` with no input on Forge: where a customer records something the product needs and Jira has no field for. Whatever answers one should answer both.

## 1.23.1

**A real Atlassian token has been through the verifier, and it was accepted.** App version 4.0.0, installed on a dev site, one page load:

```
POST /v1/slice            -> 200   0 issues  126ms  tenant=ari:cloud:ecosystem::installation/6cc978ae-…
POST /v1/forecast-context -> 200  36 issues    4ms  tenant=ari:cloud:ecosystem::installation/6cc978ae-…
```

That closes the last of the four conditions `docs/forge-deployment.md` §2 has carried since it was written. The mechanics were proved against a signer the suite controls; a token Atlassian actually minted has now been accepted, and attributed to the installation ARI that `forge install list` reports for that installation. Both halves of the design met for the first time — `invokeRemote` attached the token, `operations: [compute]` resolved the remote, and the **nested** `app.installationId` claim read correctly, which is the fault found in 1.19.0 shown fixed in production rather than in a test.

**Three details in those two lines are the design working, not noise.** `/v1/slice` carries **0 issues** because that route deliberately takes none — the resolver asks which contexts to sample before fetching anything. It took **126 ms** against the second call's **4 ms**: the first real token missed the JWKS cache and fetched Atlassian's keys, the second hit it. And both went to `us-central1`, because this site is not EU-pinned and `default` and `US` name the same service.

**What it did not prove is the numbers, and the timing says so.** A 20,000-trial Monte Carlo does not finish in 4 ms. The same shape simulates in 74 ms locally and refuses in 0.1 ms, so 4 ms is the refusal path plus HTTP — almost certainly *"too little completion history to sample from"*, which is exactly what a dev site with nothing finished on it should say, and is [ADR 0007](docs/adr/0007-refuse-rather-than-widen.md) working. The pipe is proved end to end. A figure travelling down it is not, and only a board with real completed work will settle that.

Recording the distinction rather than declaring victory, because *"the forecast returned 200"* and *"the forecast returned a forecast"* are different claims and this one is the weaker.

## 1.23.0

**The forecast is wired to the hosted calculator, and `remotes[0].baseUrl` names a real deployment for the first time.** Region-pinned — `europe-west3` for tenants pinned to the EU, `us-central1` otherwise — and Forge chooses between them per installation from the customer's own residency setting, so this app never decides where a tenant's numbers are computed. `forge lint` reports 0 errors and 0 warnings and one `MAJOR_VERSION_RULE` approval, which is exactly what converting a `baseUrl` format is supposed to raise.

**The resolver asks which contexts to sample rather than working them out, and that is the whole design.** A forecast samples a team's history and takes only its outstanding work from the selected sprint; which contexts are that team is `team_slice`, and it has been got wrong twice — 19 days reported as 77, and a team forecast 2.5 times too fast. Both returned a plausible date rather than failing.

That left a circle: the resolver must fetch the slice's issues before it can ask for a forecast over them, and the slice is the calculator's decision. `/v1/slice` breaks it. It takes the contexts and a context id, needs **no issues at all**, and returns the ids to fetch. One round trip against a service that answers in well under a second, in exchange for there being no second copy of the rule.

**The alternative was tempting and is the reason the test exists.** The resolver could have fetched the selected board and assumed that was the team. On Forge `team` is the board name, so it would be right almost always — and on the day two boards shared a name it would forecast over a narrower history than its own `sampled_from` line reported, with nothing on the page looking wrong. Almost always is what makes that dangerous.

Three assertions hold the shape: the route names exactly the contexts the forecast then counts, the resolver contains no team comparison of its own, and it stamps `contextId` on every issue it gathers. That last one matters more than it reads — `issueFrom` deliberately does not set one, because over the bridge the page re-tags them itself, and an issue reaching `selection.forecast_for` untagged is silently dropped from the sample. Reverting either of the last two fails its test.

**Sequencing still refuses, and now says the true reason.** It used to blame an unconfigured calculator, which stops being true the moment the forecast answers. `intake.sequence` compares orderings of a board's recorded *asks*, and a Jira site has no way to record one: no issue type means "ask", no field carries a value basis. That is a product question nobody has asked, not a plumbing gap, and the sentence says so.

**Still unproven, and it is the last thing.** No real Forge token has been through the verifier. The app has to be deployed with `--approve MAJOR_VERSION_RULE` and reinstalled — a `baseUrl` format change is a major version upgrade and Jira does not widen an existing installation on its own — and only then does a genuine token reach the service and a tenant appear in a log line.

## 1.22.0

**The slice moved to where both callers can reach it, and that is the whole change.** `team_slice` and `forecast_for` lived in `scripts/serve_live.py`. `service/Dockerfile` copies `agent/tools/` and `service/app.py` and nothing else, so the hosted calculator could not reach them — and the only other way to give a Forge tenant a forecast was to write the slice a second time in JavaScript. Of everything here, that is the last code that should have had two implementations: `serve_live.py` says so in its own docstring, and the reason is that its failures are all plausible dates rather than errors. Reading the wrong context turned a 19-day forecast into 77 (1.8.0). Counting a flow board's three overlapping windows as three contexts forecast a team 2.5 times too fast (1.16.13). Passing a window's end through as a target answered "0% by today" for a board that set no deadline (1.16.13 again). None of them failed.

They are `agent/tools/selection.py` now — a fifth tool module, and the first one that is not a calculation. `scripts/serve_live.py` imports them rather than defining them, so there is still exactly one implementation and the live-mode tests still guard it.

**`POST /v1/forecast-context` takes the contexts, the issues and a context id, and lets the tool choose.** The existing `/v1/forecast` is unchanged and still takes a slice the caller assembled — that is correct for `serve_live.py`, which is Python and uses the same rules. The new route is for callers that are not. The service still computes nothing: the test holds the route's answer against `selection.forecast_for` called directly, to the byte, exactly as the flat route is held against `FC.build`.

**It refuses rather than guessing, in the three places guessing would produce a number.** No `contexts` is a refusal, not a forecast over whatever arrived — the slice is the thing being asked for. An unknown context id is a `404` rather than an empty forecast, because the request was well formed and named something absent. An out-of-range `items` is refused rather than clamped, with the bound in the sentence.

**What this route lets the calculator see, said rather than discovered.** A context carries the names given to a board, a sprint and a team. They are not issue text and are not refused — the projection strips summaries, assignees, labels and epic names from *issues*, which is what that boundary is for — but they are customer strings. They have travelled this way since `/v1/facts` shipped, because `meta.sprintName` comes back as `generated_for`. Nothing computes with them: `team_slice` compares team labels for equality, and the rest is passed through for display.

**Still not wired to Forge.** `remotes[0].baseUrl` is `.invalid` and the resolvers still refuse. This is the piece that had to exist before that commit could be honest; the wiring is next, and sequencing is not part of it — a Jira tenant has nowhere for an ask to come from, which is a product question rather than a plumbing one.

## 1.21.0

**The calculator is tenant-aware in production.** Both regions run `SERVICE_AUTH=forge-token` with all four Atlassian values and, for the first time, **no secret mounted at all** — the service holds nothing. The startup guard is what proves the configuration: a service that came up is a service whose four values are present and whose PyJWT import worked.

**Three of the four values now have evidence beyond the documentation page they were read from.** Atlassian's JWKS was fetched live on 2026-08-25 and serves six RSA keys, every one `alg=RS256`, `use=sig`, with key ids prefixed `forge/invocation-token/`. That independently supports the URL, the issuer string, and the `RS256` pin in `service/app.py` — three things that were previously a single source each.

**Eight hand-made tokens were fired at the live service and every one was refused.** Not against a signer the suite controls this time: against Atlassian's real key set, from outside. `alg: none`, an HMAC forgery carrying a genuine Atlassian key id, expired, wrong audience, and — the one that matters — an RS256 token carrying a **real** Atlassian `kid` but signed with a key Atlassian never issued. That last one can only be refused by fetching the named key and finding the signature does not verify against it, so it proves the JWKS URL, the egress and the signature check together.

**The timings proved what no status code could.** Six of the eight refusals took **0 ms**: the algorithm is pinned before a key is looked up, so the forgeries are discarded without contacting Atlassian at all — which is what stops this service being used to hammer somebody else's endpoint. One took **164 ms**, the live fetch. One took **7 ms**, the cache. The behaviour `docs/forge-deployment.md` §2 specifies, observed in production. No traceback appeared for any of them, so the 1.18.1 contract — a verifier that cannot verify says no rather than raising — holds under real traffic.

**The auth mode is chosen by whether `FORGE_AUDIENCE` is set.** Unsetting one repository variable and re-running the deploy rolls the whole thing back to shared-secret. While the four values have never seen a real token, the rollback should be a variable rather than a code change made under pressure.

**What is still not proven, and it is the only thing left.** No real Forge token has been through this. `remotes[0].baseUrl` is still `.invalid`, the resolvers still refuse, and the tenant has never appeared in a log line. The verifier is now known to reject everything it should; that a genuine token is *accepted* remains untested and cannot be tested until the switchover.

## 1.20.3

**The cold start is measured rather than feared.** §7 argued from documentation that a slow-starting platform would be a correctness problem here and not merely a slow tile, because the Forge invocation token lives about 25 seconds and a cold start spends that budget. One observation each against the deployed service, on revisions created seconds earlier so the instances were genuinely cold: **1.15s** in us-central1 and **0.39s** in europe-west3, full `/v1/forecast` over TLS including the calculation. Roughly half a second of cold-start overhead against a twenty-five second budget. That is the argument for keeping `min-instances=0` and not paying $9.86 a month per region to avoid something that is not happening — and it is written down with its limits, since one observation from a domestic connection is not the network Forge will see.

**The shared secret is on version 2, and version 1 is disabled rather than destroyed.** Version 1 is the one that carried the trailing newline. Version 2 is the same secret material, one byte shorter. Both regions were cold-started with version 1 disabled before it was left that way, so nothing still resolving it is a fact rather than an assumption. Disabled and not destroyed because disabling is reversible and there was no reason to need the stronger action.

## 1.20.2

**The calculator is hosted.** us-central1 and europe-west3, scale-to-zero, both refusing unauthenticated callers and both refusing issue text at the door. The forecast each region returns and the one `forecast.build()` returns when called directly are byte-identical — 5,825 bytes, three machines, two continents, one answer. That is the seeded Monte Carlo and the no-arithmetic-in-the-wrapper rule demonstrated rather than asserted, and it is the check worth having made: a wrapper that rounded a single percentile would have shown up here.


**The service refused the correct credential, and could not have told you why.** `_verify_shared_secret` stripped the token it was *presented* and not the one it was *configured with*, so the two sides of the comparison were never comparable. Any secret store that appends a trailing newline — which is most of them, and every workflow built on `echo` or a piped `openssl rand` — produced a service that answered 401 to a caller sending exactly the right string, while looking perfectly configured from every angle an operator can see.

**It shipped, and the wizard is what shipped it.** `service/provision-gcp.sh` piped `openssl rand -hex 32` straight into Secret Manager. `openssl` prints a newline after the hex, `--data-file=-` stores every byte it is given, and Cloud Run injected all sixty-five. The stored secret really did end `0a`, so from the service's side the credential genuinely did not match — there is no log line it could have written that would have pointed at the cause.

Both halves are fixed. The wizard pipes through `tr -d '\n'`, and `_expected_secret()` strips, because stripping one side of a comparison and not the other is the bug rather than the newline being it. A secret whose surrounding whitespace is meaningful could never have authenticated against this service anyway — the presented side was already stripped.

**The strip must not manufacture a secret out of nothing**, so a whitespace-only value is still no value: it refuses to start and refuses every request, exactly as an unset one does. An open calculator is free compute for whoever finds it.

Four assertions pin it, and reverting the strip fails all four. The trailing-newline case is the one that shipped; the leading and surrounding cases are there because the asymmetry, not the newline, is what was wrong.

## 1.20.1

**The calculator is deployed and serving in us-central1, and the first deploy reported it as dead.** It was not. Google's front end swallows the exact literal path `/healthz` on Cloud Run: it answers with its own 404 page and the request never reaches the container. `/healthzz`, `/healthz/`, `/HEALTHZ` and `/health` all pass straight through and get the service's own JSON 404, and `/v1/meta` returns its own `401`. One path, intercepted, and it happened to be the one the post-deploy probe used.

**Every signal was green except the one that mattered.** The deploy succeeded, the revision was Ready, `allUsers` held `run.invoker`, ingress was `all`, DNS resolved to Google's front end, the startup probe passed on `:8080`, and billing was live — and a `curl` said 404. What settled it was the container's own stderr: `GET / -> 404  0 issues  0ms`, in `service/app.py`'s own access-log format. The request had arrived, so routing had never been the problem, and the search moved from "why is nothing serving" to "why is one path different".

**The probe is `/v1/meta` expecting a 401 now, and that is an upgrade rather than a workaround.** A health endpoint returning 200 proves the URL routes and the container is up. A 401 from `/v1/meta` proves both of those *and* that authentication is switched on — which is the failure this service is built to avoid, since a calculator that came up unauthenticated would look perfectly healthy to any check that only asked whether it answered.

**The product was never affected.** Forge calls `/v1/facts`, `/v1/forecast`, `/v1/ask` and `/v1/sequence`; none is intercepted. The container's `HEALTHCHECK` is unaffected too — it calls `127.0.0.1` from inside the container, where no front end is in the path, and Cloud Run ignores a Docker healthcheck anyway in favour of its own TCP probe.

**europe-west3 was left undeployed**, because the loop aborts on a failed region rather than carrying on to the next one. That is the right behaviour and it is why the second region is still missing: the failure was in the probe, and the probe ran before the loop moved on.

## 1.20.0

**The calculator has somewhere to be deployed from, and nothing on the way there holds a key.** `service/provision-gcp.sh` is an eight-stage wizard for the half of hosting only a person can do — billing, APIs, a registry in each region, two service accounts, the GitHub federation — and `.github/workflows/deploy.yml` is the half that should never be done by hand.

**Workload Identity Federation rather than a service account key.** GitHub mints a short-lived OIDC token saying which repository is running and Google exchanges it for a short-lived access token, so there is no long-lived credential in this repository to leak and none to rotate. The attribute condition pinning the trust to one repository is the entire security control — without it any GitHub repository's token would be accepted — so the wizard states that in the stage that creates it rather than leaving it as a flag somebody might drop.

**Two service accounts, because one would have to be able to do both jobs.** The deployer may push images and update services and may not read the secret; the runtime may read the one secret it needs and may not deploy anything. The `serviceAccountUser` grant is scoped to the runtime account rather than the project, so the deployer can run the service as that identity and as nothing else.

**The container checks moved out of the workflow and into `service/smoke.sh`.** They were inline in the `container` job, which was right while CI was the only thing that built the image. The weekly rebuild builds it too — from a base that has moved even when this repository has not — and it has to clear the same bar before it ships. Two copies of those assertions would be two things to keep in step, and the first time they disagreed the question would be which workflow to believe. `service/scan.sh` exists for the same reason and holds the §11 policy in one place.

**The weekly rebuild deploys, and that is the decision rather than the schedule.** A build that produces a fresh image and never ships it leaves the running service ageing exactly as fast as it would have without it. It is safe to run unattended because the gates in front of it are the ones that would catch a real breakage, and all of them run before a single byte reaches a registry.

**`--concurrency=1`, which looks wasteful and is not.** The calculation is CPU-bound single-threaded CPython and the container runs the stdlib threading server, so concurrent requests contend on the GIL rather than sharing a vCPU for free. Eight concurrent `intake.sequence` calls at 3.07s each would run past the roughly 25 seconds a Forge invocation token lives — a slow answer here is not a slow tile, it is an expired token and a refusal nobody can explain. Cloud Run answers a burst by starting more instances, which is faster per request and is exactly the model the costing assumed. `--timeout=30s` sits just past Forge's own 25s for the same reason: long enough never to cut short a call Forge would still accept, short enough not to keep billing for one it has abandoned.

**Found while writing it: both Google auth actions are on v3, not v2.** Pinning to the major that came to mind would have been a stale pin on the day it was written. Checked against the current releases instead.

**The deploy skips rather than fails when Google Cloud has not been provisioned.** A workflow that goes red on every push because a repository variable is unset teaches people to ignore a red tick, which costs more than it catches. It writes a summary saying which script to run instead.

**Still shared-secret, and still `.invalid`.** The first deployment runs `SERVICE_AUTH=shared-secret` deliberately, so hosting can be proved on its own before Forge is anywhere near it — otherwise the first test of the deployment is also the first test of the Forge wiring and a failure could be either. `remotes[0].baseUrl` is untouched and the resolvers still refuse; the suite still ties those two together.

## 1.19.0

**The hosted calculator has a plan, and writing it found that `forge-token` was never blocked only on four values — two of the three things in the way were code, and they are fixed.** [`docs/hosting-the-calculator.md`](docs/hosting-the-calculator.md) recommends Cloud Run, two regions, request-based billing, no minimum instances, and `SERVICE_AUTH=forge-token`. It costs three volume tiers against dated rates and takes the two decisions `docs/forge-deployment.md` §3 deliberately left open. [ADR 0012](docs/adr/0012-the-calculator-is-reached-by-invokeremote.md) records the part that will outlive the plan.

**The resolver would have received no invocation token, and the manifest said otherwise in a comment. Found and fixed.** Declaring a `remote` is what makes the egress permitted; what attaches the token is `invokeRemote()` from `@forge/api`, and `callCalculator()` called plain `fetch` against a `process.env.CALCULATOR_URL`, which sends no Authorization header at all. So pointing `baseUrl` at a real host would have returned 401 on every call, in either auth mode — the two halves of the design had never met, which is the same discovery 1.18.0 made from the other end.

It calls `invokeRemote('calculator', …)` now, the remote declares `operations: [compute]` — which Forge requires before it will resolve the key at all — and `permissions.external.fetch` is gone with the `fetch` it authorised. The suite used to check that the egress rule named a declared remote; there is no egress rule left, so the check follows the typo into the code and holds the literal key in `index.js` against the manifest's remotes. The key is written as a literal for that reason. Both new assertions were mutation-tested: a mistyped key and a missing `operations` each fail.

**And the URL going away is a gain.** A URL built in the resolver is one URL for every installation on earth; a `baseUrl` resolved from the manifest is chosen per install from the customer's own Atlassian residency setting. That is what makes EU-and-US a manifest shape rather than a routing system this app would have had to write, and it is why the auth question stopped being close. [ADR 0012](docs/adr/0012-the-calculator-is-reached-by-invokeremote.md).

**The token verifier would have rejected every real token, and the harness could not have shown it. Found and fixed.** `_verify_forge_token()` read the tenant with a flat `claims.get()`. The invocation token has no flat tenant claim: the installation identity is `app.installationId`, nested one level down, and `context.cloudId` is not merely a second option but absent entirely for the backend-function invocations this app makes. Every one of the twelve rejection cases mints its own flat claim, so all twelve passed against a verifier that could not read a real one. It failed in the safe direction — nothing wrong was ever accepted — and the tenant-aware mode still did not work.

This is the failure mode this repository names as its worst, wearing different clothes: not a wrong number, but a green suite describing a capability that was not there. No test written against a signer the suite controls could have caught it, because the signer would have to be wrong in the same way. Atlassian's published payload is the only evidence that could, so the new case is minted in that shape.

`_claim_at()` walks a dotted path. A claim name with no dot still reads flat, so the twelve cases are not rewritten to suit the fix — and reverting the walk fails the nested case while leaving the flat one green, which is what makes the pair worth having rather than one test that would pass either way. Three more assert the walk refuses as firmly as the flat lookup did: a path that runs out, one that lands on an object, one that lands on blank.

**And the clock-skew allowance is larger than the token's whole life. Found, not fixed, and that is the decision.** `FORGE_LEEWAY_SECONDS` is 30 against a documented token lifetime of 25 seconds, which roughly doubles the window a captured token is accepted in. The runbook's own instruction was "a small clock skew allowance, not a generous one". It stays at 30 rather than being tightened on the strength of a documentation example: 25 seconds is a sample, not a stated guarantee, and a margin cut to fit a sample is how a verifier starts rejecting real traffic at the tail. The first real token measures the lifetime, and that is the number to set it from — step 8 of the switchover.

**The four values are confirmed, with the date beside them.** `FORGE_JWKS_URL`, `FORGE_ISSUER`, `FORGE_AUDIENCE` — the app id ARI, not the bare UUID — and `FORGE_TENANT_CLAIM`, each read from Atlassian's current documentation on 2026-08-25 and recorded in Appendix A. The app-system and app-user token question the runbook left open turns out not to be a property of the token at all: they are two additional headers an app opts into, each needing its own scope, and this app should decline both — a calculator that reaches no tracker has no business holding an Atlassian OAuth token.

**Data residency is Forge's job, not the app's.** Region-pinned `baseUrl`s are resolved per install from the customer's own Atlassian residency setting, so EU and US on day one is a manifest shape rather than a routing system. The cost of that is a deadline: converting the `baseUrl` format, or adding a region, is a major version change and a reinstall, so every region this product will offer is nearly free to declare before the first external install and expensive afterwards.

**Rebuild cadence: weekly, and it deploys.** The base image goes stale on its own schedule and the service installs one wheel, so the attack surface is almost entirely the base. A rebuild that produces a fresh image and never ships it leaves the running service ageing exactly as fast as it would have — so the schedule rebuilds, smoke-tests, scans, and on green deploys both regions.

**Scan policy: fixable HIGH and CRITICAL block a merge; unfixable ones are printed and do not.** The line is actionability rather than severity. A CVE with no upstream fix is not something a merge can resolve, and a gate that blocks on it is one people learn to route around, at which point it stops catching the fixable findings too. Both scans run, and the unfiltered one prints in full — `--ignore-unfixed` alone is a silent cap, and a scan that quietly drops half its findings reads as a clean scan.

**Costed, and the conclusion is that cost is not the axis.** Roughly $0.15, $0.30 and $3.70 a month across the three tiers for both regions together, at us-central1 rates read on 2026-08-25 under stated assumptions. At the top tier egress costs more than the arithmetic does. Lambda is cheaper and was not chosen; Fly has a lower floor and was not chosen; App Runner floors at $2.56 to $10.22 per region serving nothing, and that is the one number in the comparison that decides anything.

## 1.18.1

**The token verifier raised where it should have refused, and CI found it on the first push.** `_verify_forge_token()` imported PyJWT at the top of the function. On a runner that had never installed it — which is every runner, since the CI step was not updated — the import threw instead of returning None, and the assertion that requests must not pass *even with the startup guard removed* was answered by an exception rather than by a rejection.

The contract is "a principal, or None". Raising is neither. A verifier that cannot verify has exactly one honest answer and it is no, so the import is caught and the function refuses. The startup guard still stops the process, and it now names the missing dependency rather than the configuration — those are different problems with different fixes, and the message has to name the one the operator actually has.

The regression is pinned by making `import jwt` fail on purpose, which is how CI produced it. CI installs `service/requirements.txt` before the calculator tests, which it should have done when the dependency was added.

The `container` job passed, so the image builds with the new `pip install` in it.

## 1.18.0

**The calculator can authenticate a tenant.** `SERVICE_AUTH=forge-token` was a mode that refused to start; it is written now, and with it the hosted calculator stops being blocked on code and starts being blocked only on somewhere to run.

A verifier returns **who the caller is** rather than a boolean, which is the whole point of moving off the shared secret: a check that validates a signature and ignores who the token was issued for has bought nothing. The tenant reaches the access log. The shared-secret mode logs no tenant rather than a placeholder, because one string presented by every installation cannot identify anybody, and a log that implies otherwise is worse than one that says nothing.

**Found while checking, and it changes the order of the remaining work.** `callCalculator()` in the Forge resolver sends no `Authorization` header at all — deliberately, since the design is for Forge to attach the token. But the only implemented mode wanted a bearer secret, so hosting the service on its own would have returned 401 on every call. The two halves did not meet, and section 2 of the runbook was never optional groundwork that could be deferred behind hosting.

**Four values are configuration, not constants, and are not guessed here.** `FORGE_JWKS_URL`, `FORGE_ISSUER`, `FORGE_AUDIENCE` and `FORGE_TENANT_CLAIM` must be confirmed against current Atlassian documentation. The service refuses to start in this mode with any of them missing, and refuses every request too — a guard that only exists at startup is a guard somebody removes. Guessing one produces a verifier that rejects every real token, or, in the case that matters, accepts one minted for a different app.

**The mechanics are proved against a signer the test controls.** `tests/test_service.py` generates a keypair, serves a JWKS from a local HTTP server and mints its own tokens, then requires every one of these to be refused: expired, `nbf` in the future, wrong `aud`, wrong `iss`, signed with a key outside the key set, `alg: none`, HMAC-signed using the RSA public key as the secret, no `kid`, unknown `kid`, truncated, a valid signature carrying no tenant, and one carrying a blank tenant. The HMAC forgery is assembled by hand, because `jwt.encode` refuses to use an asymmetric key as an HMAC secret — a good guard on the minting side and not one a verifier may lean on.

**Two cache properties are pinned, because both failures are silent.** Inside the re-fetch floor an unknown `kid` costs Atlassian nothing at all; past it, it costs exactly one fetch however many unknown ids arrive. An unknown `kid` is precisely what somebody would send in a loop if this were unbounded, and an uncached fetch per request would make Atlassian's endpoint this service's availability ceiling.

**Two of the mutation tests were worthless and it took a second look to notice.** The first tenant-binding mutation was malformed and silently changed nothing, so its clean run proved nothing — applied properly it fails two checks. And removing the algorithm pin altogether changed no verdict at all, because PyJWT's own `algorithms=` already refuses both forgeries: the pin is defence in depth, and no assertion about a *verdict* could ever have covered it. What the pin genuinely changes is observable — the token is thrown out before a key is looked up, so `alg: none` cannot be used to make this service fetch from Atlassian on somebody's behalf. That is what is asserted now, with a probe carrying a `kid` the cache has never seen, because the first version used a cached one and no fetch would have happened either way.

**The dependency.** `PyJWT[crypto]`, in a new `service/requirements.txt` — deliberately not in `scripts/requirements.txt`, because the security suite asserts the fetcher's dependency list stays at one and the fetcher is what holds a customer's credentials. It is imported inside the verifier rather than at module scope, so shared-secret mode still runs and the whole suite still passes on a host that never installed it; the startup guard is what makes that safe. The Dockerfile installs it before copying the source, CI audits it alongside the fetcher's, and `service/README.md` no longer says the service is stdlib-only.

**What this does not claim.** No real Forge token has been through this verifier, and none can be until the four values are confirmed and the service is hosted somewhere Forge can reach. The mechanics are proved; the deployment is not. `remotes[0].baseUrl` still points at `.invalid`, the forecast and sequencing resolvers still answer with the offline notice, and `tests/test_service.py` still ties those two together so neither can change without the other.

## 1.17.1

**Sizing an ask could never work over the route Forge would use, and the reason was one field reaching nobody.**

`intake.py` builds its reference class by grouping this board's finished epics and reading how big each turned out. It grouped them by `epic` — the epic's own summary. `epic` is free text, so `clean_dataset()` in `service/app.py` strips it on arrival, along with summaries, assignees and labels. That boundary is deliberate and is not the thing to change: a calculator has no business holding issue titles.

So over that route the grouping saw nothing, `epic_sizes()` returned an empty list, and both the t-shirt scale and the reference class refused — for every board, every time. The refusals were accurate, which is why nothing looked broken. What was missing was the capability, not the number: everything `docs/product-intake.md` describes was unavailable in principle to the only route a Forge install could take.

**`epicKey` was already travelling for exactly this and being read by nobody.** The resolver emits it, `CALC_FIELDS` sends it, the calculator's allow-list accepts it, and nothing at either end looked at it. Sizing keys on it now when a dataset carries one — which is precisely when the names have been stripped — and falls back to the summary otherwise, so bundles are unaffected. A key is the better handle regardless: two epics can share a summary, and renaming one splits its own history in half.

**The field is chosen once for the whole issue set, not per issue, and that is the part that needed care.** `i.get("epicKey") or i.get("epic")` reads as the obvious fallback and would split a single epic in two the moment a dataset carried the key on some of its issues and the name on others. A twenty-item epic arriving as two tens shrinks every t-shirt band and reads exactly like a team that has started working in smaller pieces — a plausible wrong number in a forecasting input, arrived at by arithmetic. The test builds that dataset, shows the naive fallback really would have split it, and shows this one does not.

Where the grouping was by key rather than by name, the basis line says so. A reference class assembled by issue key and one assembled by epic name are the same method over the same board, but a reader checking the working needs to know which column to look down.

**What was verified and what was not.** `/v1/ask` is exercised end to end in `tests/test_service.py` against a payload with every free-text field stripped, and it now returns a reference-class sizing where it previously returned a refusal. The **hosted calculator is still not provisioned** — `remotes[0].baseUrl` in the Forge manifest points at `.invalid` — so this has not been run against a real deployment, and the Forge resolvers still answer the forecast and sequencing routes with the offline notice. What is proven is the code path, not the deployment.

The assertion added in 1.16.10 recording `epicKey` as a known loose end is retired, and the allow-list guard it sat in now checks fields read by `agent/tools/` against that directory rather than against `src/app.js`, since that is where this one is read.

## 1.17.0

**Four flow tiles, and none of them needed a sprint or a window.** Cycle time, ageing work in progress, weekly throughput and cumulative flow are all properties of issues and dates — which is why they were available all along rather than something the schema had to grow, and the same reason the forecaster worked on a flow board from the start.

**How long finished work took** plots every closed item on the day it finished against 50/85/95 percentile lines. It is ranked above the cumulative flow diagram deliberately, against the usual instinct: it yields a sentence a team can take outward — *85% of what we finish, we finish within N days* — it names outliers into the drill-down, which is this product's whole signature, and it is read correctly by people who have never seen one. Cumulative flow diagrams are famously looked at and taken nothing from.

**Work in progress, and how old it is** puts open work against those same lines. It is the only tile on the page describing work a stand-up can still change: an item above the 85th percentile has already outlived 85% of everything the board has ever finished, and it has not finished. **How much finishes each week** is the series the Monte Carlo samples, shown so the forecast can be checked rather than taken on trust — quiet weeks included, because a model that never samples a zero never predicts a stall.

**The cumulative flow diagram has three bands and says so on the tile.** Nothing in a dataset records which column an issue sat in on a given day, so the bands are the three status *categories*, derived from `created`, `started` and `resolved`. A per-column version needs `statusTransitions` from the Python fetcher as well as the Forge resolver. A three-band chart presented as a full one is a different picture of the same board, so the limitation is printed rather than left to be discovered — and removing that sentence fails a test.

**Little's Law is reconciled under it, with no verdict drawn.** Work in progress over throughput is how long the average item must be spending in progress; measured cycle time is how long the items that finished actually took. Where they disagree by more than a factor of two the tile states both figures and says they do not line up. It does not choose between the two honest readings — the open work really is sitting far longer than anything that has finished, or start dates are not recording when work began — because choosing would be a claim about a team resting on whichever reading the reader happened to assume.

**Shown by default only on a flow board; available on every board.** All four measure a sprint board perfectly well, and hiding a measure that works is the same error as showing one that does not. Presets gained a board-kind column rather than a fourth preset: the audience question and the board question are different axes, and crossing them would mean four presets to keep in step with two report templates. A reader who chose *Executive* keeps that choice across a board switch and gets the executive cut of whichever board they landed on; a custom set is left exactly as they left it.

**Every figure is computed in `agent/tools/metrics.py` first.** The page mirrors the percentile function because a browser cannot call Python, which is the same arrangement `orgconfig.py` has, and it is kept honest the same way — by comparing the two rather than trusting they were written to match. `tests/e2e.py` reads the figures off the rendered tiles and holds them to the facts pack.

Three things this turned up that are worth recording. The first mutation test **did not fail**: changing the percentile constant from 85 to 80 passed, because on the sample data those are the same number and the caption said "85%" as a literal beside whatever figure the constant produced. That is a mislabelled number rather than a wrong one, and harder to notice; the sentence is built from the constants now and the test compares two percentiles that differ. The four tiles were also invisible to `tests/a11y.py`, which runs against sprint data where they are off by default — the four newest charts would have been the four nothing ever contrast-checked. It shows them explicitly, and asserts that it did.

### Considered and left out

**Blocked time**, the measure everyone asks for: `flagged` is a boolean with no history, so the schema cannot say when an item was flagged. Not computable rather than not wanted. **Flow distribution by work type**, which is easy from `type` and implies a target mix nobody set — the family [ADR 0004](docs/adr/0004-no-priority-score.md) exists to refuse. **WIP limits**, which need a limit somebody stated. **A flow-efficiency trend line**: the waiting-versus-working chart already is the graph view, and a ratio of two noisy quantities over time moves mostly with how accurately `started` was recorded, so it invites reading a data-quality artefact as a delivery change. And no per-person cut of ageing work in progress ([ADR 0003](docs/adr/0003-the-dashboard-does-not-measure-people.md)), nor any "what to pull next" ordering ([ADR 0004](docs/adr/0004-no-priority-score.md)) — an ageing chart invites both.

## 1.16.13

**The Monte Carlo tile was forecasting a board with no sprints two and a half times too fast.** Found by asking whether it still worked rather than assuming it did, and it is the exact failure this repository names as its worst: not a crash, a credible number.

`forecast.build()` needed no change and never has — it samples throughput over a rolling window of *days* and has never wanted a sprint boundary. The slice assembled around it is what broke. `team_slice()` gathers every context belonging to a team, and on a sprint board that is that team's sprints, which do not overlap: no key appears twice, and the slice has been correct for as long as it has existed. A flow board's three contexts are 14, 30 and 90 days of the *same* board. Every issue in the short window is in the long ones as well, so the slice held each of them three times, `throughput_samples()` counted three completions on the day one item finished, and the 85th percentile came back at **four working days against a true ten**. `item_risk` listed the same issue three times over.

Issues are de-duplicated by key now: one issue is one item, however many contexts hold it. It is a no-op on a sprint board. The test asserts the strong form — the same board described by one window and by three must forecast identically, so duplication is provably not an input rather than merely reduced.

**And the tile was answering a question about a deadline nobody set.** A window's `endDate` is today, because that is what the end of *the last thirty days* means, and it was being passed through as the forecast's default target. So *will this land in time* was asked against an end that is always now, and answered **0%** — in the one tile whose job is to say when work will land, with a probability of nought a reader can quote. The capacity figure alongside it refused with *"the target date has passed"*, which sends someone looking for a date that was never set.

A window now supplies no default target. The forecast still runs and still says when the open work lands; it just states no probability against a date nobody chose. The capacity refusal says *"this period has no end date to forecast against"*, which is a different fact from a target that has been and gone — both said the latter, including for any dataset carrying no end date at all, so that is fixed for sprint boards too. The date control offers a date rather than pretending to remember one, and a date the reader does name is answered normally.

**Neither was reachable inside a Jira tenant**, because the Forge forecast resolver still answers with the no-calculator refusal ([ADR 0008](docs/adr/0008-forge-calls-a-hosted-calculator.md)). Both were reachable over loopback, which is the route the demo and every local check use.

`next_commitment` was already refusing correctly, for want of a cadence rather than a date — that guard was put back in 1.16.4 and this is the first thing to lean on it.

## 1.16.12

**A board with no sprints gets a health score of its own.** The chip carried nothing on a flow board as of 1.16.11, which was right while there was nothing to put in it — a sprint-board figure refusing in the position the headline verdict occupies is noise rather than disclosure. There is something to put in it now. **Flow health** is built on flow efficiency at 40% of the weight, with blockers and ageing work at 30% each, and it is the one place in this work where a figure is genuinely *replaced* rather than refused or hidden.

Flow efficiency carries it because on a board that committed to nothing it is the closest thing to *is this working* the data holds: the share of an item's life that was work rather than queue. The other two are the sprint score's own hygiene measures, unchanged, because they describe the same thing on any board.

**Three components, not four dressed up as four.** There is no honest fourth. Work in progress has no target to be scored against without a limit somebody set, and cycle-time spread already has an implementation in `size_stability()` that a page-side copy would have to be kept in step with — which is the failure this repository keeps paying for, not a shape to fill in for symmetry's sake.

**Both scores go through one machine.** The drop-and-name rule, the re-weighting, the half-weight floor and the bands are shared; only the parts list differs. Two composites computed two ways would be two things to keep honest, and the day they disagreed about what *Amber* means every colour on the page becomes something to check rather than read.

**Flow efficiency is load-bearing, not merely heavy, and the floor would not have caught it.** Drop it and 60% of the weight survives — comfortably above the half-weight floor — so the score would have been reported. What survives is blockers and ageing work, which is hygiene: the same remainder the sprint score already refuses to call health, and here it would have been worse, because the name would have been the part that was not taken. Removing that guard prints **Flow health: Off track (44/100, 2 of 3 measures)** with the flow measure listed as not measured directly above it, which is what the test asserts against. It refuses instead, names `started` as the thing that is missing rather than asking for more data, and says where that field comes from.

**The chip says which composite it is carrying.** *Flow health* and *Sprint health* are different quantities built on different evidence. A chip that read the same for both would invite comparing two boards that were never measured the same way, which is the mistake this whole area exists to prevent.

**One threshold, where there were two.** The executive card called flow efficiency under 40% worth saying and the risk register drew its line at 45%, so the same board could be reported as fine in one paragraph and a risk in the next. There is one number now, it is 40%, it is what scores full marks in the new composite, and it is printed in the disclosure rather than applied quietly — a threshold a reader cannot see is one they cannot argue with. The tooltip also says that none of these three measures reads work volume, so unlike sprint health the points toggle cannot move this figure.

## 1.16.11

**A board with no sprints shows the tiles that measure it, and not the three that never can.** They refused in place until now, which was the wrong call and is corrected rather than quietly reversed — [ADR 0011](docs/adr/0011-a-kanban-context-is-a-window-not-a-clock.md) records both halves.

The line is whether the condition can lift. A sprint with no dates may get its dates; a points view may get its estimates; an empty selection may get issues. Those refuse **in place**, addressed to a reader who can do something about it, and sit in the tile so it is clear which figure is missing from where. The burndown, the commitment-history chart and team load on a flow board are not that: a burndown needs a scope somebody committed to and a date to burn it down to, and the other two read per-sprint snapshots of a board that takes none. Nothing will ever change it. Three permanent apologies across a third of the grid stop being a disclosure and become furniture, and they push the tiles that do measure this board below the fold.

The sprint-health chip goes with them. It is a sprint-board figure by definition — `CONTEXT.md` says so — and *"Sprint health: not scored"* in the most prominent chip on the page is the noise rather than the disclosure. It is emptied as well as hidden, because the previous board's score left in the markup and its working left in the tooltip attribute is a stale figure one class away from being read.

**What stops this being the silent cap this repository has shipped three times is that nothing is dropped without being named, twice.** The context bar says *"rolling window, so no burndown, pace or sprint health"* in the row that already answers *which data am I looking at* — the same place and the same shape as the rollup's own note. The tile picker lists all three with the reason for each and **disables** them, rather than leaving them merely unticked: a checkbox that can be ticked and does nothing is worse than one that says why it cannot be. Tiles the reader turned off and tiles this board cannot support are counted separately, because rolling them together would send someone looking for a checkbox that is not there.

**The reader's tile selection is masked, never edited.** Switching to a flow board and back restores the view exactly, including a custom set and a custom order, because `S.shown` is untouched and the board's applicability is applied at paint time.

**This is not a kanban preset, and the difference matters.** The two presets are *audience* cuts — executive and team — taken from the agent's own report templates, and a board-kind preset would be a second axis crossed with the first: four to keep in step with two templates. Which tiles a board can support is a property of the board, applied on top of whichever audience cut the reader chose, so the two compose rather than multiply.

Three refusal sentences written for these tiles in 1.16.8 are gone, because the tiles no longer show them and prose nobody can reach is one edit from disagreeing with the prose they do read. Each reason now has one home.

## 1.16.10

**Cycle time works inside a Jira tenant.** The Forge resolver has never sent `started`, because the first transition into an in-progress status can only be recognised under organisation config and a resolver deciding that would be a third implementation of the rule. The page printed *"no completed items with both a start and a resolved date"*, which was true and which emptied the waiting-versus-working chart across every install. For a sprint that is a stated degradation. For a board with no sprints it is the measure, so it stopped being acceptable.

The resolver now sends **`statusTransitions`** — every move the issue made between statuses, as `{"to": "In Review", "at": "2026-08-04"}`, with the names left undecided — and the page picks the earliest one its own config calls in-progress. The rule still has one implementation and it is still not in a resolver. What changed is that the raw material travels, and the reason it must is the difference from `workingDays`: the page can derive a working-day list from dates already on the wire, and there was nothing on the wire from which to derive a start. Leaving that out was a gap, not a silence. It costs one changelog expansion the resolver was already doing for `addedMidSprint`, so no extra call and no new scope.

**Earliest, not first, and that distinction is the bug this could have shipped.** Jira does not return a changelog in date order. Taking the first in-progress transition in list order rather than the earliest by date moves every start date later — on the demo data, three days later for every issue — which shortens every cycle time and raises flow efficiency. A smaller wait and a more efficient team, arrived at by arithmetic, with nothing on screen to suggest it. `jira_pull()` in the Python has always taken the minimum for this reason; the page now mirrors it, the fixtures are deliberately out of order, and `tests/e2e.py` fails on the sort alone.

The list is uncapped, deliberately: a truncated transition list silently moves a start date later, which is the same wrong number by a different route.

**`epicKey` reaches no consumer, and writing the guard for this is how it surfaced.** The check that the resolver invents no field the page does not read had an allow-list, and `epicKey` was on it under the assumption it feeds the epic filter. It does not. Nothing in `src/app.js` reads it and nothing in `agent/tools/` does either — `intake.py` groups by `epic`, the free-text name, which is in `NEVER_SEND` and so never reaches the calculator at all. So it travels from the resolver, through the calculator's allow-list, to nobody, and epic-based sizing cannot work over that route as things stand. Whether it should key on `epicKey` instead is a change to `intake.py` rather than to a test, so it is named and asserted rather than quietly dropped — the assertion fails the day something does read it.

Every exception in that allow-list is now checked to be genuinely referenced in the code that justifies it, which is the same failure the guard exists to catch, one level up.

## 1.16.9

**The risk register was reporting a clean bill of health over rules it never ran.** Three of its eight rules depend on something beyond the issues on screen — scope growth needs a sprint to have added work to, the over-commitment rule needs four sprints of history, flow efficiency needs closed items carrying both a start and a resolved date — and each of them fails the same silent way: the condition is false, the rule vanishes, and *"No risks triggered against the current filters"* stands over a shorter examination than the reader thinks they are getting.

On a flow board two of the three can never run at all. But this is deliberately **not** a flow-board fix: a sprint board with no start dates, or any dataset that carries no `started` field, has been quietly not running these for as long as the register has existed. It now names them — *"2 rules were not run against this selection: scope growth — this board runs no sprints…; the commitment against recent delivery — this board runs no sprints to commit in. Nothing is claimed either way about them."* — and when nothing triggered, the sentence becomes *"No risks triggered by the rules that could be run here."*

It is the same rule as the capped lists in 1.16.3 and the dropped health components in 1.16.2, one level further out. Something that bounds what it examined has to say what it left out, and a register is a list of findings whose length is its whole message.

**The executive summary was dropping sentences without saying so.** Its pace line appears only when there is a clock and its scope line only when something was added, so on a sprint with no dates the first silently vanished and on a flow board both do, permanently. A summary that drops a claim reads as a summary that had nothing to claim — the same failure as a truncated list reading as a complete one. It now names what it withheld and why, once for both when they share a cause.

**Two sentences in the register were still measuring against a sprint.** *"N open items have outlived a full sprint"* and *"the item should be moved out of the sprint"* — the first is the fourteen-day threshold called after something that does not exist on this board, the second an instruction that cannot be followed on one.

A board where every rule ran says nothing about rules not run, which is what makes the note a disclosure rather than decoration, and `tests/e2e.py` asserts both directions.

## 1.16.8

**Every tile that would have stated a sprint-shaped figure on a flow board now says what it in particular cannot show.** Step 4. Not a banner over the grid — [ADR 0010](docs/adr/0010-an-empty-selection-is-a-refusal.md) ruled that out for the reason it throws away everything the page still knows, and that reasoning does not change because the cause is a board rather than an empty selection.

**Delivered read 55%.** A share of completed work needs a scope somebody committed to. A window's membership is *open now, plus resolved inside it*, so the denominator is partly defined by being in the numerator: widen the window and the share rises, narrow it and it falls, and neither movement is the team. The count of finished work is real and stays, in the sub-label and the drill-down. The percentage is withheld.

**Scope added read `0 · 0% growth`.** `addedMidSprint` is *the sprint field changed after the sprint began*, so on a board with no sprints every issue carries false and the guard returns nought. A zero there is the claim that nothing was added, about a period that does not exist. Both of those figures are what the tiles print again the moment the guard is removed, which is what the tests assert against.

**The executive summary states counts and withholds the share.** *"12 of 22 items are done (55%)"* has the same broken denominator; *"12 items were finished in this window and 10 are still open"* is honest, and is the more useful sentence for a board whose reader wants to know how much is in flight.

**Four tiles were naming a cause that would send a reader to fix the wrong thing.** The burndown printed *"No burndown series in the dataset"* — true of the bytes, and it invites a re-import that would not help, because a burndown plots a committed scope down to a date and this board commits to neither. The commitment-history chart and team load both asked for *"at least two sprints of history"*, which on a flow board is a request that can never be satisfied rather than a threshold that has not been met yet. Each now names the board, and each ends with the same *the evidence is absent, not noisy* clause the tools use.

**One tile was renamed rather than refused, and the distinction is the point.** *Likely to carry over* measures open work, which is measured on any board; only the label was sprint-shaped, because "carry over" names a boundary to carry over *into* and a flow board has none — work there does not roll forward, it continues. It reads **Still open**. Refusing a figure that is perfectly good would have been the same error in the other direction. For the same reason the ageing chart keeps its fourteen-day bands and its counts, and stops calling a fortnight a sprint: the measurement is identical and only the yardstick was named after something that does not exist here.

The risk register's unrun rules and the executive card's silently dropped sentences are the last of it, and are next.

## 1.16.7

**The page knows a window is not a clock.** Step 3, and the one that had to land before any real tenant saw a flow board. `contextWorkingDays()` derives a working-day list from any context carrying a start and an end — which is right for a sprint, right for a Forge sprint that arrives without one, and wrong for a window. Expanding a 30-day window gives twenty-two working days that are perfectly real and describe nothing, because nobody undertook to finish anything by the end of a rolling month.

Removing that guard in a mutation test is the whole argument for it: the page printed **Pace vs clock — −45 pp** for a board that had committed to nothing at all. Not an error, not a blank. A negative figure in percentage points, in the tile the dashboard was built to add, about a deadline nobody ever agreed to.

**Two guards, because one of them is two functions away from every reader.** The calendar is withheld in `contextWorkingDays()` *before* the sent list is consulted — a producer that shipped `workingDays` on a window would otherwise walk straight past the rule, and the figure would arrive looking like data rather than like a derivation. Neither transport sends one, and this no longer depends on that staying true. `derive()` then withholds `timeElapsed` at source as well, because `renderExec` reads `paceGap` directly and one place to be wrong is enough.

**Scope stability was the quiet one, and it failed upward.** `addedMidSprint` is *the sprint field changed after the sprint began*, and a board with no sprints has no such moment — so every issue in a window carries false, the divide-by-zero guard returns 0% growth, and the component read **100/100, "no mid-sprint additions"** for a board where the phrase has no referent. Left alone it kept the composite above its half-weight floor, and the header printed **Sprint health: Needs attention (63/100, 3 of 4 measures)** for a flow board. Exactly the shape [ADR 0009](docs/adr/0009-one-contract-two-transports.md) caught the resolver in when it defaulted the same field: not a silence, a claim that nothing was added.

With both measures dropped and named, what is left is 0.44 of the weight, and the score refuses whole. That is the answer rather than a gap — blockers and ageing work describe hygiene, not whether anything is going to land — and it is [ADR 0010](docs/adr/0010-an-empty-selection-is-a-refusal.md)'s existing rule reaching its fourth cause rather than a new mechanism.

**The fourth cause gets its own words, and only one set of them.** *"No sprint dates"* would have been the natural thing to reuse and it would have been a lie: a window has dates, they are in the picker beside the board's name, and a reader sent to find the missing ones would be looking for something plainly there. What is missing is the commitment. Both dropped measures have that same single cause, so the disclosure says it once — listing it twice, once for pace and once for scope, reads as two problems to fix, and it is one permanent fact about the board that no re-import will change.

**Three overlapping windows must never be rolled up.** A flow board is offered 14, 30 and 90 days of *itself*; the same issue is in all three. The rollup builder keys per project and board, so it would have built one — holding every issue three times, and every count on the page is a count of the issues in the selection. A board's throughput would have tripled. There is no honest rollup to build instead: "all three windows" is not a longer period, it is one period asked about three times, and the 90-day window already is the wide view.

The picker's third dropdown says **Window** rather than **Sprint** when that is what it lists. The remaining tiles — the burndown, Delivered %, the *Scope added* KPI, the executive card's dropped sentences and the risk register's unrun rules — still say sprint things on a flow board, and are the next step.

## 1.16.6

**A board that runs no sprints is offered something for the first time.** It was detected and declined: `sprintsFor()` caught Jira's 400, the footer counted it as *"N without sprints and not offered"*, and the picker left it out. It now gets three windows — 14, 30 and 90 days — and `context` resolves one into that board's issues over both transports. Step 2 of the flow-board plan, and offering and loading landed together on purpose: a picker entry whose id 404s is worse than a board that is honestly not offered.

**One membership, two ways of reaching a board.** The resolver fetches through `/board/{id}/issue`, which returns what is on the board now — the wrong question for a closed sprint and exactly the right one for a flow board, where there is no historical membership to recover. The loopback goes through the board's own saved filter, because its issues come back through `jira_pull()`, which owns the field mapping and the `started` derivation, and reaching a different endpoint would have meant a second copy of that mapping. How each transport finds the board is its own business; **which issues count is not**, so the membership predicate is one pure function mirrored in both languages and compared string for string.

That predicate reads `resolutiondate` for both halves rather than `resolution IS EMPTY`. It is the field the page reads as `resolved`, so Jira is asked exactly the question the page will answer from what comes back; `resolution` would be a third opinion about what "done" means, arriving by neither the status category nor the organisation config.

**Its upper bound is the day after the window ends, and that is not an off-by-one.** Jira compares a bare date against midnight, so `resolutiondate <= "2026-08-24"` drops everything finished during the window's last day. The symptom would have been a throughput series quietly missing its most recent day — a number, computed, slightly wrong, with nothing on screen to suggest it. Pinned by a test that fails on the comparison operator alone.

**The footer's one count became two, because one of them stopped being true.** *"N without sprints and not offered"* covered two different boards: one with no sprint support, which is a flow board and is now offered windows, and one that has sprints and has never started one, which has nothing to offer and is a different sentence for its owner to act on. Left merged, the second would have been described as the first the moment windows existed. That line is the only thing standing between a picker quietly missing a board and a project that genuinely does not have one, so it moved into `forge/src/jira.js` where a test can read it — a label only a deploy can check is a label nobody checks.

**The window's length is in the id; its dates are not.** `SFT/2/win:30d` means the same thing whenever it is asked, so a picker built at 23:59 and a context loaded at 00:01 agree about which context is meant and differ only in the dates the second one resolves. An id carrying the dates would have gone stale overnight and come back as "unknown context".

**A window still carries no working-day list, and its burndown is still empty.** Both are deliberate and both are only half-honoured until the page catches up: the loopback sends `workingDays: []` for a window and builds no burndown series, and `contextWorkingDays()` in `src/app.js` must still learn not to derive a list from a window's dates. Until it does, a window's dates would become a clock. That is the next step and nothing offers a window to the page before it lands.

[ADR 0009](docs/adr/0009-one-contract-two-transports.md) is corrected rather than left to age. It said this app issues no JQL of its own, and it now issues some. The claim that mattered is unchanged and is stated exactly: no text from the page reaches Jira, because the only caller input is a context id and `parseContextId` refuses anything but a canonical token naming one of the three offered lengths — so the set of queries this app can be made to issue is three date pairs per board, each built from the resolver's own clock.

## 1.16.5

**The two transports now agree what a window is, before either one offers a board a window.** Step 1 of the flow-board plan and deliberately nothing more: a flow board's context id, the `kind` that travels with every context, and a window entry built independently by `forge/src/jira.js` and `scripts/serve_live.py`. No board is offered a window yet and nothing on the page renders differently, because a picker entry whose id 404s is worse than a board that is honestly not offered. Offering and loading land together, next.

A flow board's id is `SFT/2/win:30d` where a sprint board's is `SFT/2/8891`, and `kind` is `"sprint"` or `"window"` on every entry both transports send. It is carried rather than recovered by re-reading the id, per [ADR 0011](docs/adr/0011-a-kanban-context-is-a-window-not-a-clock.md): a discriminator a consumer re-derives is a second implementation of the same fact, and the page would be the one holding the wrong copy. `BundleBackend` defaults it to `sprint` for bundles written before flow boards existed, where an absent value has exactly one honest reading, and the fetcher writes it so new bundles describe themselves.

**Two producers agreeing about which keys exist and disagreeing about what is in them is the harder bug, so the parity check compares values.** The existing one compares field sets, and that is precisely the hole `workingDays` went missing through — a whole Forge install rendering different figures from the same sprint while the shapes matched. The new check builds the same window in both languages and compares key by key and value by value, across month ends, a year end and a leap year, which is where JavaScript's millisecond arithmetic and Python's `timedelta` would part company if they were going to. Drifting the loopback's window by one day fails four checks; dropping `kind` from it fails another.

**`win:030d` named the same context as `win:30d`.** Found by the parse table, not by reasoning: `Number('030')` is 30, so two strings resolved to one window. The page keys everything on this id and round-trips it back to the transport, and one context with two spellings is one context nobody can round-trip — the same shape as the id mismatch that made every sprint read *"unknown context"* on the first install. A window token is now checked by rebuilding it rather than by trusting the match, so only the canonical spelling parses.

Window lengths outside the offered 14, 30 and 90 days are refused rather than clamped or honoured. `win:99999d` would otherwise pull an unbounded slice of a board through an id no dropdown can produce, and a request the product cannot make is a request it should not answer.

## 1.16.4

**A dataset that stated no sprint dates was told how many items to commit to.** `recommend_commitment()` has always held the right answer for this — *"sprint length is unknown"* — and `forecast.build()` never let it out. The call read `len(meta.workingDays or working_days(startDate, endDate, cfg)) or 10`, and that trailing `or 10` substituted a ten-working-day sprint before the guard could fire. So a file with no calendar in it came back **"Next sprint: commit to 9 items at 85% confidence"**, with *"20,000 simulated sprints of 10 working days"* printed underneath as its own basis.

Ten is the working length of the default fortnight, which is precisely what made it dangerous. Had it been 7 or 30 somebody would have queried it years ago; a plausible sprint length, stated in the basis line, reads as a fact the tool went and looked up. This is the class of failure this repository keeps finding — not a crash, a confident number computed against something nobody supplied — and it made a refusal that exists in the source unreachable from the only caller that matters.

The fallback is gone rather than improved. Reaching for `orgConfig.sprintLengthDays` instead was available and is the same bug wearing the config's clothes: `from_dataset()` merges the defaults, so by the time the figure arrives a stated 14 and an inherited 14 are indistinguishable, and a number nobody chose would go back out under the authority of one they did. `tests/test_agent.py` pins both directions — a dateless dataset refuses and carries no `recommended`, no `commit_at`, no `sprint_working_days` and no basis line to quote, while a dataset that does state its calendar still gets a figure sized against the length it actually stated. A fix that refused everything would pass the first three checks alone.

**Decided what the product offers a board that runs no sprints.** They are detected today and then declined — `sprintsFor()` catches Jira's 400, the picker counts them as *"N without sprints and not offered"*, and there the matter has rested. [ADR 0011](docs/adr/0011-a-kanban-context-is-a-window-not-a-clock.md) settles what they are offered instead: a **window**, a rolling stretch of calendar days holding the issues open at the as-of date plus those resolved inside it. It bounds the selection, it round-trips through an id, and it carries **no working-day list**.

That refusal to supply a calendar is the whole decision, and it came out of code that already does it. `contextWorkingDays()` withholds the day list from a rollup on purpose, because a date range spanning nineteen sprints is perfectly real and describes nothing — *how far through nineteen sprints are we* is not a pace. A window is that same argument one step further out. Give it its twenty-two working days and the KPI strip prints **Pace vs clock: −18 pp** for a team that never committed to finishing anything by the end of it. So a window is not a new mechanism; it is a second caller of [ADR 0010](docs/adr/0010-an-empty-selection-is-a-refusal.md)'s drop-and-name rule, and the work is to give it the right sentence.

Three consequences are worth stating before anyone builds against them. Sprint health **refuses whole** on such a board — delivery pace and scope stability both need the clock, and what remains falls below the half-weight floor at 0.44, which is the honest answer rather than a gap, because blockers and ageing describe hygiene rather than whether anything will land. **Delivered %** refuses too, and that one is not about the clock: a window's membership is partly defined by *being done*, so the share would rise as the window widened. And the KPI strip does **not** go as one the way it does over an empty selection — five of the eight are genuinely measured there, and suppressing them would be its own dishonesty.

`CONTEXT.md` takes the vocabulary first, per the standing rule that naming precedes renaming: *sprint board* and *flow board*, *sprint* and *window*, and *period* for the sentences true of both. `docs/kanban-boards.md` names every tile and every KPI as keeping, refusing or replaced, sets out the position on `started` over the Forge transport — the resolver sends raw status transitions and the page decides what they mean, as it already does for `statusCategory` — and records what is deliberately not in this pass. No renderer has changed yet.

## 1.16.2

**Reconciled with the per-site calendar work, which landed on `main` in parallel.** The two solve the same gap from opposite ends and they compose: the resolver sends the site's own config, and the page derives the day list under it. Neither now needs the other's half. Two things came out of reading them together.

The comment in `forge/src/jira.js` said `workingDays` was withheld because resolving organisation config in a resolver would be a fourth opinion arriving by a fourth route. That stopped being true the moment the resolver started resolving that config, and it plainly could compute the list now. It still must not, for the reason that outlasts the other: expanding a date range into working days is a *rule*, the rule already has two implementations kept in step by a test, and a third in a resolver is a third thing to keep in step in the one place nobody can run that test against a customer's tenant.

And the hole this ADR named in ADR 0009's parity check is closed rather than only noted. That check fed the bridge the loopback's own bodies, so any field the resolver omits was invisible to it — which is exactly how `workingDays` went missing across a whole install. `tests/e2e.py` now feeds it a body shaped the way the resolver really shapes one, with `workingDays`, `statusCategory` and `contextId` stripped, and requires the same footer, the same KPI strip and the same context list anyway. Removing the derivation fails it with *Pace vs clock — no sprint dates*, which is the symptom as it actually appeared. `started` is deliberately left in place: the resolver omits it too, but that absence is a stated degradation the page prints, not something it makes good.

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

**The dashboard inside Forge shows the customer's own Jira, not a demo company's.** Deployed, installed and observed on a real site: the picker offers that site's boards and sprints and the page renders its issues. It rendered before this — fully styled, with charts — but every number on it belonged to Highpeak Commerce, because the page reaches live mode over a same-origin `api/*` and a Forge Custom UI iframe has no such origin. It does now, and the thing that made it possible is a seam rather than a feature. [ADR 0009](docs/adr/0009-one-contract-two-transports.md) records it.

**One contract, two transports.** The page asks four questions by route name and gets `{ok, status, body}` back. Over `http(s)` that is the same-origin GET `scripts/serve_live.py` already answered; inside the iframe it is an `invoke()` that an adapter left on the window before the page loaded. The **bodies are the contract** — defined by `serve_live.py`, returned unchanged by the Forge resolvers — and the status is transport-level, because a 404 for a sprint this site does not have and a failure to answer at all are different things and the page says different words for each. On `file://` there is no transport, nothing is asked, and an emailed copy still produces a silent console.

**`src/app.js` does not know what Forge is, and the suite now insists on it.** It imports nothing, contains no `@forge/*` reference, and the root `package.json` still has no dependencies. The adapter is `forge/bridge/bridge.js`, bundled separately and linked only into the split build — and it has to be a *classic* script placed ahead of `app.js`, because `app.js` decides at load which transport it has and an ES module is deferred. An adapter that arrives afterwards is an adapter that never ran, and the symptom is a page that silently believes it is offline, which looks exactly like a broken resolver.

**Found by loading the real bundle, after the tests using a stub had all gone green: the adapter was never installing itself.** `@forge/bridge` connects to its host as a side effect of being loaded, and outside a Forge iframe that throws. An ES `import` is evaluated before any of the adapter's own code runs, so the throw aborted the file before it reached the assignment — the page fell back to the same-origin fetch with nothing but an uncaught error in the console to say why. Outside Forge that fallback is the right answer and it hid the fault completely; inside a real iframe the same throw would have left the dashboard looking merely offline, which is the failure this whole seam is meant to make impossible. It is CommonJS now, required inside a `try`, so the failure is caught and named and no transport is installed rather than a broken one. `tests/e2e.py` loads the bundled adapter rather than a stub and asserts all three: no uncaught error, a console line saying why, and a page that falls back instead of believing it is connected.

**Then the first real install came up blank, and the app had nothing to say about it.** Two separate faults, both of my making, and both the same shape.

`sprintsFor` caught *every* error from the sprint endpoint and reported it as "this board has no sprints". Jira does answer 400 for a kanban board, and skipping that is right — but a 403 from a scope that had not been consented to came back the same way, so the picker came up empty and read as a project with nothing in it. It distinguishes the two now: a 400 is a fact about the board, anything else is a failure and travels.

And a resolver that fails rejects `invoke()`, which the page was treating exactly as it treats a dead loopback server — silently, because over loopback nothing running is the normal case. Over the bridge it is not: something answered, and it said no. So the resolvers catch, and answer with Jira's own status and a sentence; `probeLive` reads that sentence instead of discarding it; and the context bar — the "which data am I looking at" row, where a reader is already looking — shows **NO DATA** and the reason, rather than the page being blank and the footer carrying the explanation nobody scrolls to.

**And the blank install was two Jira endpoints disagreeing about one board.** The context id is built from `board.location`, `contexts` reads boards from the list endpoint, and `context` re-reads one board on its own — and the two responses do not always describe `location` the same way. An id built from a response carrying `projectKey` was then compared against one built from a response without it, stopped matching, and every sprint came back as an unknown context. The id now falls back to the project key Forge's own module context supplies, which is the same answer both times, and the integrity check — this page may read only the boards of the project it is displayed in — is made against that module context rather than against a second Jira response. It was the right check made against the wrong authority.

**"Server returned 404" named none of the four things it meant.** The `context` resolver's refusals now say which: the id is not in project/board/sprint form (which is what a sprint that came with the file looks like), that board is not on this site, that board has no such sprint, or that board belongs to a different project than the id claims. Four situations, four fixes, and the alert quotes the sentence verbatim.

**The two transports are compared rather than assumed to agree.** `forge/src/jira.js` holds the Forge half as pure functions of a Jira response — no SDK, no network — precisely so a test can run it. `tests/test_service.py` drives it over fixtures and compares the envelopes, field for field, against what a running `serve_live.py` really puts on the wire. `tests/e2e.py` checks the other end: the same page, over both transports, fed the same bodies, must render the same footer, the same KPI strip, the same context list and the same issue count. Writing that test found four genuine mismatches before anything was deployed.

**A field defaulting to false was going to be a confidently wrong number, and it is the one thing the resolver computes.** `addedMidSprint` needs no organisation config — it is *the sprint field changed after the sprint began* — and leaving it out is not a silence. It is the claim that nothing was added: the health score reads it as full marks for scope stability, and nothing on the page says it was never measured. The resolver expands the changelog and reads it. What it does *not* send is deliberate and written down beside each one: no `statusCategory`, because which statuses mean done is config the page already holds; no `started`, because recognising an "In Progress" transition needs that same config, and the page prints *"no completed items with both a start and a resolved date"*, which is true, rather than a flow efficiency built on a rule a resolver invented; no burndown series, because that is Python and Python is not running here, and the page says so where the chart would be.

**The Forge build is seeded empty.** It used to carry the demo dataset, so the first thing a customer saw was a fictional company's 22 issues inside their own Jira. `forge/seed.json` carries none, the page holds one placeholder context until the bridge answers, and then opens on the site's newest sprint. A file built with no data of its own adopting the connection's is a general rule, not a Forge one — the same thing happens over loopback.

**Three scopes, and the first is one this app removed rather than granted a fortnight ago.** The connection check dropped a `boards` resolver instead of asking for `read:project:jira`, on the grounds that the scope existed purely to make a diagnostic more convenient, and the note it left said that if the real context picker ever needed to enumerate boards, this was the price and it was a decision to take on its own merits. This is that moment: the picker offers the boards of the project the page is open in, and the alternative is a product page that opens empty and asks an end user to type a numeric board id. `read:sprint:jira-software` and `read:jql:jira` are what `forge lint` demands for the one call that reads a sprint's issues; the JQL one looks broader than the rest and is worth understanding rather than waving through — that agile endpoint is JQL-backed underneath, and this app issues no JQL of its own.

**A check that forced a false word into a file has been replaced by one tied to the code.** `tests/test_service.py` asserted that `manifest.yml` still described itself as a scaffold, so a manifest that quietly looked finished could not be deployed. That stopped being true the moment the app was registered and reading a tenant's boards. What is still unfinished is nameable instead: the calculator has no host, `remotes[0].baseUrl` says `.invalid`, and the forecast resolvers answer with a refusal saying exactly that. The two are asserted as a biconditional, because both directions are a bug — a real `baseUrl` with the refusal still in place is a forecast tile that stays dark for no reason anybody can see.

**The connection check was meant to be deleted here and has been kept.** It is the only thing that shows the outbound payload for a single issue, and it now names which field this site calls story points — a confirmation rather than a diagnosis, since that is resolved by name now.

**A Forge tenant is measured under its own calendar now, not this tool's.** Every install was reported under the defaults — Monday to Friday, no holidays, fourteen-day sprints, and a fixed idea of the word "done" — because the organisation config travels inside a dataset and a Forge install has no dataset. A site with a *Signed off* column and no *Done* column read every sprint as 0% complete. That is the exact bug `orgconfig.py` was written for, reintroduced by a route with nowhere to read a config from.

**Which statuses mean done comes from Jira, because Jira knows.** Every status on a site carries a category its admins assigned, and `orgconfig.py` already trusts that as the fallback inside `category()` — *"a statement by the site rather than a guess here"*. With no config file above it, it is the primary source, and it is better than any list this project could ship: the *Signed off* site is right without being asked. The resolver is the producer on this route, so it resolves once and writes the answer into every response, exactly as the fetcher does.

**The working week, the holidays and the sprint length are stated on the project.** Jira has no notion of any of them, so a site sets an `orgConfig` property on its project — read with the scope the board picker already needed, and never written: this app asks for no scope that would let it. What the property does not state keeps what Jira said, then the documented defaults. And when there is no property at all the connection label says so, in the line the page prints in its footer, because a five-day week nobody chose reads exactly like one somebody did.

**A property that is not usable stops the request rather than being half applied.** The same refusal `load()` makes about a bad file, and for the same reason: a typo in `workingWeek` that quietly reverted to a five-day week would move every forecast in the product with nothing on screen saying so. That means a second validator, in JavaScript, which is the kind of duplication this repository normally refuses — so it is held the way the other one is. `tests/fixtures/org-configs.json` holds nineteen configs, thirteen of them unusable, and `tests/test_service.py` runs every one through both the resolver and `orgconfig.validate` and asserts the two verdicts match. Neither side can be handed an easier set than the other, and breaking either is a failing test rather than a divergence found in a customer's tenant.

**Story points are read from whichever field a site calls them, not from a hardcoded id.** The resolver assumed `customfield_10016`, which is the common one and is wrong everywhere else: every issue on such a site read as zero points, the burndown flattened in points mode, and nothing said why. It is discovered through `/rest/api/3/field` by display name now — the same three names and the same first-match traversal `scripts/fetch_delivery_data.py` uses, because two producers picking different fields would report two velocities for one board, and a test compares the two lists across the two languages. It turned out to need no new scope, which is what moved it from a decision to a patch.

**A site with no story-point field reports `null`, never `0`.** An estimate nobody recorded and an estimate nobody could read are different facts about a sprint, and only one belongs in a burndown. The same goes for a text field pointed at that slot: coercing "M" to zero would put a made-up figure on the chart. Where there is no field the connection label says so, and the page prints that line in its footer.

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
