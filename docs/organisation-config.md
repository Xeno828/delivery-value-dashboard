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

## Where it is read

| Consumer | How it gets the config |
|---|---|
| `scripts/fetch_delivery_data.py` | `--org-config`, default `config/organisation.json`; writes it into the output |
| `scripts/serve_live.py` | from the bundle; `--org-config` in live-Jira mode only |
| `agent/tools/*.py` | `OC.from_dataset(dataset)` — never from a file |
| the dashboard | `orgConfig` in the loaded dataset, or the live server's, which wins and is named in the footer |
| the import wizard | keeps whatever is in play; an uploaded CSV carries no config and must not silently reset a customer's calendar |
