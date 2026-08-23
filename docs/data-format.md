# Data format

One row per issue drives every chart on the page. You do **not** need these exact column names when uploading — the wizard matches your headings (see [importing-data.md](importing-data.md)). These are the internal names, used in the templates and by the fetcher script.

## Issue fields

| Field | Type | Required | Drives |
|---|---|---|---|
| `key` | string | **yes** | Identity, deep links, de-duplication |
| `summary` | string | **yes** | Every list and drill-down |
| `status` | string | **yes** | Status filter, stage grouping |
| `statusCategory` | `To Do` / `In Progress` / `Done` | no | Completion; inferred from `status` if absent |
| `assignee` | string | no | Person filter, distribution chart |
| `storyPoints` | number | no | Burndown, pace, distribution, commitment |
| `type` | string | no | Type filter |
| `priority` | string | no | Top-priority-open tile, risk register |
| `epic` | string | no | Epic filter |
| `created` | date | **yes** | Ageing, lead time |
| `started` | date | no | Cycle time, waiting-vs-working split |
| `resolved` | date | no | Burndown, completion, value |
| `dueDate` | date | no | Overdue tile and risk |
| `flagged` | boolean | no | Blocked tile and risk |
| `addedMidSprint` | boolean | no | The scope line on the burndown |
| `businessValue` | number | no | Value card |
| `valueBasis` | string | no | The justification shown under each value figure |
| `labels` | array or `;`-separated | no | Shown in drill-downs |
| `url` | string | no | Deep link; built from `meta.baseUrl` if absent |

Dates are ISO `YYYY-MM-DD` internally. On upload, several other formats are recognised and converted.

## Units

The dashboard reads volume in **items by default**, with a Points toggle in the filter row. Items is the default because it is the unit the forecasting agent uses, and because it cannot be inflated by estimating generously. Points remain available and remain the better lens for one specific question — whether scope growth actually mattered — because item counts treat a one-line copy change and an eight-point hotfix as equal.

Separately, and not affected by the toggle: **elapsed time is reported in calendar days** (an item raised 21 days ago is 21 days old) while **the forecaster simulates in working days**. Every figure carries its unit.

## The three fields that do disproportionate work

- **`started`** — without it there is no cycle time, and the waiting-vs-working chart (the most useful thing on the page) is empty.
- **`addedMidSprint`** — without it the burndown's scope line is flat, and scope growth stays invisible. This is what separates *"we were slow"* from *"we were given more"*.
- **`valueBasis`** — a value figure without a stated basis should not be on an executive dashboard. The card counts only items that have one.

## Optional blocks

### `meta`

```json
{
  "organisation": "Highpeak Commerce",
  "team": "Storefront Team",
  "sprintName": "Sprint 24",
  "sprintGoal": "One sentence, shown in the header",
  "startDate": "2026-08-03",
  "endDate": "2026-08-14",
  "asOfDate": "2026-08-10",
  "source": "jira",
  "sourceLabel": "Live: Jira board 42",
  "baseUrl": "https://your-domain.atlassian.net",
  "currency": "USD",
  "workingDays": ["2026-08-03", "..."]
}
```

`sourceLabel` is shown in the header badge and in the footer. The badge is green when `source` is anything other than `demo`. `workingDays` is recomputed on upload from the organisation config — the working week and the holiday calendar both come from `orgConfig` below, and no longer from a rule written in `src/app.js`.

### `orgConfig`

```json
{
  "version": 1,
  "statuses": {
    "done": ["Done", "Closed", "Resolved", "Complete", "Completed", "Shipped"],
    "inProgress": ["In Progress", "In Review", "Review", "Testing", "Test", "QA", "Doing"]
  },
  "workingWeek": ["mon", "tue", "wed", "thu", "fri"],
  "holidays": [],
  "sprintLengthDays": 14
}
```

Top-level, a sibling of `meta` — not inside it, because `meta.organisation` is already the company's name.

The assumptions that differ per customer, resolved once by whatever produced the file and written into it. Every consumer — the page, `metrics.py`, `forecast.py`, `intake.py`, the live server — reads it from here rather than from a config file of its own, so the tools and the dashboard cannot end up describing the same sprint under two different calendars. Full reference in [organisation-config.md](organisation-config.md).

Absent means the defaults above, which reproduce what was hard-coded before the block existed, so every file that predates it reads exactly as it did.

Holidays shorten **working** time only. Reported elapsed time stays in calendar days — see Units above.

### `burndown[]`

```json
{ "date": "2026-08-07",
  "remainingSP": 51,    "scopeSP": 83, "idealSP": 41.1,
  "remainingItems": 15, "scopeItems": 22, "idealItems": 10 }
```

**Both units, always.** The dashboard's Items/Points toggle switches between the two series, and the forecasting agent works in items — a burndown that exists only in story points puts the two tools in different units by construction.

`remaining*` and `scope*` are `null` for days in the future. On upload the whole array is **recalculated from your issues**, never inherited. A dataset predating the toggle still renders in points; the burndown card says so and `scripts/rebuild_burndown.py` backfills the item series.

### `history[]` — last six sprints, drives every trend

```json
{ "sprint": "Sprint 23", "committedSP": 46, "completedSP": 34,
  "committedItems": 12, "completedItems": 8, "throughput": 8,
  "wipItems": 6, "unplannedItems": 3, "flowEfficiency": 0.33, "valueDelivered": 58000 }
```

`committedItems` / `completedItems` drive the predictability chart in items mode; `throughput` is kept as their alias for older files.

`wipItems` (started but unfinished at sprint end) and `unplannedItems` (arrived after planning) drive the **Team load** card. Both come from issue status.

**There is no hours or overtime field, deliberately.** The organisation does not operate overtime, and carrying such a field would imply a time-tracking regime that does not exist. An earlier version of this dashboard charted output-per-person against recorded overtime; both were removed. Output per person, with no counterweight, is a productivity-per-head number, and this dashboard does not measure people.

### `releases[]`

```json
{ "name": "v2.2.0", "targetDate": "2026-08-14", "scopeIssues": 14,
  "doneIssues": 9, "status": "At Risk", "note": "Blocked by BLC-429" }
```

`status` is matched loosely: anything containing "risk" reads amber, "late" or "off" reads red, everything else green.

### `dora{}`

```json
{ "deploymentFrequencyPerWeek": 11, "deploymentFrequencyTrend": [8,9,9,10,10,11],
  "changeFailureRatePct": 7,        "changeFailureRateTrend": [11,10,12,9,8,7],
  "leadTimeForChangesDays": 1.1,    "leadTimeForChangesTrend": [1.9,1.8,1.6,1.4,1.2,1.1],
  "mttrMinutes": 38,                "mttrTrend": [66,58,61,47,42,38] }
```

These come from your CI/CD tooling, not from Jira. Trend arrays are oldest-first and drive the sparklines and the improving/worsening word.

## Computed in the browser, never stored

Completion, pace against the clock, scope growth, ageing bands, lead and cycle time, flow efficiency, the health score, the executive narrative and the risk register are all derived at render time from the filtered issue set. Filter to one person and every one of them recomputes for that person.

## Templates

- `data/templates/issues-template.csv` — the flat format, with two worked rows
- `data/templates/dashboard-data-template.json` — the full structure
- `data/templates/value-estimates-template.csv` — for the merge path
- `data/sample-sprint.json` — the demo dataset, and the best worked example
