# Organisation configuration

Four things were baked into the code and are true of exactly one company. This
is where they are decided now.

| Setting | What it decides | Default |
|---|---|---|
| `statuses.done` | Which tracker statuses count as finished | `Done, Closed, Resolved, Complete, Completed, Shipped` |
| `statuses.inProgress` | Which count as started but unfinished | `In Progress, In Review, Review, Testing, Test, QA, Doing` |
| `workingWeek` | Which days of the week are worked | `mon`–`fri` |
| `holidays` | Which of those days are not | none |
| `sprintLengthDays` | How long a sprint is, in calendar days | `14` |
| `trendSprints` | `6` | How many sprints the predictability and load trends show. Two is the floor because a trend needs two points; forty is the ceiling because every sprint in the window is a sprint's worth of issues fetched. What it cuts is named on the page rather than implied. |

The file lives at `config/organisation.json`. Validate it with

```bash
python3 agent/tools/orgconfig.py config/organisation.json
```

which prints the resolved config and the one-line summary the dashboard and the
facts pack both show, and exits non-zero with a sentence per problem if it is
not usable.

## The config travels inside the data

This is the part worth understanding, because it is not the obvious design.

The fetcher resolves the config **once** and writes it into the dataset it
produces, as a top-level `orgConfig` block. Everything downstream — the
dashboard, `metrics.py`, `forecast.py`, `intake.py`, the live-mode server —
reads it from there. None of them opens `config/organisation.json`.

```
config/organisation.json
        │  read once, by the producer
        ▼
   dashboard-data.json  ──►  "orgConfig": { … }
        │                          │
        ├── the page reads it      ├── metrics.py reads it
        └── the live server        └── forecast.py, intake.py
```

The reason is the failure this project has already had. `metrics.py` and the
browser's `derive()` compute the same figures twice, deliberately, and the
suite asserts they match. A config each of them read separately would be a
third opinion arriving by a different route, and the first symptom would be a
facts pack and a dashboard reporting different flow efficiency for the same
sprint — which shipped once, as 25% against 22%, and was a units disagreement
of exactly this kind.

A consequence worth stating: **an emailed copy carries the calendar it was
built with.** That is correct. The numbers in it were computed under those
rules, and re-interpreting them under the recipient's rules would change the
figures without changing the file.

## Units are unchanged

Holidays and the working week affect **working days only** — the Monte Carlo
horizon, the sprint elapsed-percentage, the burndown's ideal line.

Reported elapsed time stays in **calendar days**. An item raised 21 days ago is
21 days old whether or not the office was shut. Making a holiday shorten an
item's age would be the same lie of convenience as skipping weekends, and the
test suite pins both halves of that.

## Statuses the config has never seen

A status matching no rule falls through to the tracker's own category if there
is one, and to a name-matching heuristic if there is not. Either way **it is
recorded and printed at the end of the run**:

```
  note: 1 status matched no rule in the config and were inferred: 'Awaiting sign-off'
        add each to statuses.done or statuses.inProgress in your organisation
        config, or confirm it belongs in To Do.
```

This is the quiet failure the whole feature exists to prevent. A site adds an
*Awaiting sign-off* column, no rule mentions it, those issues read as To Do, the
burndown flattens, and the dashboard is confidently wrong with nothing on
screen to say why. That is a churn-in-week-two bug, and the customer never
tells you which number they stopped believing.

## A worked example

A four-day week, two shutdown days, a sign-off column and three-week sprints:

```json
{
  "version": 1,
  "statuses": {
    "done": ["Done", "Signed off", "Released"],
    "inProgress": ["In Progress", "In Review", "With QA", "Awaiting sign-off"]
  },
  "workingWeek": ["mon", "tue", "wed", "thu"],
  "holidays": ["2026-12-24", "2026-12-25"],
  "sprintLengthDays": 21
}
```

Everything is optional. A file naming only `holidays` keeps the default week,
the default statuses and 14-day sprints. Naming only `statuses.done` keeps the
default `inProgress` list — an empty list would claim no status is in progress,
which nobody means by omission.

## What a bad config does

It stops the run. Nothing is half-applied and nothing falls back:

```
config/organisation.json is not a usable organisation config:
  - workingWeek contains 'funday' — use mon/tue/wed/thu/fri/sat/sun
  - 'done' appears in both statuses.done and statuses.inProgress
```

A typo that silently reverted to a five-day week would move every forecast in
the product with nothing on screen saying so — which is worse than not starting.

## Adopting it changes nothing

A dataset with no `orgConfig` resolves to the defaults, and the defaults
reproduce exactly what was hard-coded before this existed. `tests/test_agent.py`
asserts that spelling the defaults out changes no forecast figure, so every
file produced before this feature still reads the same.

## Two implementations, one behaviour

`agent/tools/orgconfig.py` is the reference. `src/app.js` mirrors it in
JavaScript, because the browser cannot call Python. `tests/e2e.py` asserts the
two agree — working days and status categories alike — **under a config that is
not the default**, since two implementations of "Monday to Friday" agree by
accident. Change one, change both.

`forge/src/jira.js` mirrors one part of it: `validate()`. A Forge install has
no config file, so a site states its calendar in a Jira project property, and a
property that is not usable has to stop the request rather than be half
applied — the same reason `load()` refuses a bad file. `tests/test_service.py`
runs both over the shared cases in `tests/fixtures/org-configs.json` and
asserts they agree about which are usable. Add a case there rather than to
either side.

## On Forge, where there is no file to read

The resolver is the producer, so it resolves the config once and writes it into
every response, exactly as the fetcher does. It has two sources.

**Which statuses mean done comes from Jira.** Every status on a Jira site
carries a category its admins assigned, and this file already trusts that as
the fallback in `category()` — *"a statement by the site rather than a guess
here"*. With no config file above it, it is the primary source, and it is
better than any list this project could ship: a site with a **Signed off**
column and no **Done** column gets it right without being asked, which is the
case that prompted this whole module.

**The working week, the holidays and the sprint length come from the project.**
Jira has no notion of any of them, so a site states them in a project property
named `orgConfig`, read with the scope the board picker already needs. This app
never writes it and asks for no scope that would let it.

```bash
# read-only for the app; a project admin sets it once
curl -u you@example.com:$JIRA_TOKEN -X PUT \
  -H 'Content-Type: application/json' \
  "$JIRA_URL/rest/api/3/project/SFT/properties/orgConfig" \
  -d '{"workingWeek":["sun","mon","tue","wed","thu"],
       "holidays":["2026-08-05"],
       "sprintLengthDays":10}'
```

A `statuses` block is accepted there too, for a site whose Jira categories are
wrong. Anything the property does not state keeps what Jira said, then the
documented defaults — and **when the property is absent the connection label
says so**, so a five-day week nobody chose does not read like one somebody did.

An unusable property is refused by name, and nothing is measured under it.

## Where it is read

| Consumer | How it gets the config |
|---|---|
| `scripts/fetch_delivery_data.py` | `--org-config`, default `config/organisation.json`; writes it into the output |
| `scripts/serve_live.py` | from the bundle; `--org-config` in live-Jira mode only |
| `forge/src/index.js` | Jira's own status categories, plus the `orgConfig` project property; written into every response |
| `agent/tools/*.py` | `OC.from_dataset(dataset)` — never from a file |
| the dashboard | `orgConfig` in the loaded dataset, or the live server's, which wins and is named in the footer |
| the import wizard | keeps whatever is in play; an uploaded CSV carries no config and must not silently reset a customer's calendar |
