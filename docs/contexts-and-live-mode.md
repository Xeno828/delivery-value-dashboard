# Filtering by project, board and sprint

The dashboard can hold many sprints at once and switch between them instantly. This describes how the data gets there, and why the page never talks to Jira itself.

---

## The constraint, stated plainly

**A browser page cannot use MCP, and cannot call Jira or Asana directly.**

- MCP is a protocol between an LLM host and a server. There is no client for it in a static HTML file.
- Jira and Asana reject cross-origin requests from browser pages.
- Any credential embedded in an HTML file is readable by everyone it is forwarded to.

So "pick a sprint and the page queries Jira" is not buildable as stated. What is buildable — and what this does — is two things that together feel the same:

1. **A bundle.** Several projects, boards and sprints are fetched *once* into a single file. Switching between them is instant, offline, and the file still emails as one attachment.
2. **Optional live mode.** If you deliberately start a small local server, the page finds it and can pull sprints the bundle does not contain, on demand.

Neither requires the page to hold a credential. Both degrade gracefully: with no server, you get whatever was bundled; with no bundle either, you get the single sprint the file was built with.

---

## Contexts

A **context** is one project + board + sprint. A bundle is a list of them plus the issues belonging to each.

The context bar appears above the filters whenever there is more than one, with three cascading pickers:

```
SOURCE  [JIRA]  |  Project [Highpeak Commerce ▾]  Board [Storefront Delivery ▾]  Sprint [Sprint 24 ● current (11) ▾]
```

- **Boards are scoped to the selected project**, and **sprints to the selected board**. Changing project moves you to that project's current sprint rather than stranding you on an empty combination.
- The active sprint is marked `● current`; the issue count is shown per sprint so you can see which are worth opening.
- Each board also offers **All N sprints** — a rollup across every sprint on that board. Flow, ageing, distribution, value and the risk register are all valid across it. The burndown and release cards are not, and say so rather than drawing something meaningless.

Everything else on the page — the unit toggle, the filters, drill-downs, exports — works exactly as before within the selected context.

---

## Route 1 — build a bundle with the fetcher

```bash
export JIRA_URL=https://your-domain.atlassian.net
export JIRA_EMAIL=you@company.com
export JIRA_TOKEN=…

python3 scripts/fetch_delivery_data.py \
  --jira-boards 42,43,51 \
  --sprints 6 \
  --out data/dashboard-data.json
```

Six sprints per board is the default and the recommended setting: enough history for the forecaster to work on any board you select, and enough past sprints to compare against. Three boards × six sprints lands around 500–1,500 issues and a few hundred KB.

Each context carries its own burndown and its own sprint history — and each context's history contains only sprints **up to and including itself**, so opening Sprint 21 shows you what was knowable at Sprint 21 rather than leaking the future into a past report.

Then drop the file onto the dashboard's upload panel, or serve the folder and open it with `?data=data/dashboard-data.json`.

## Route 2 — build a bundle through Claude, via MCP

This is where the MCP connection actually lives: **Claude** holds it, not the page.

With the Atlassian or Asana connectors enabled, ask in plain language:

> "Pull the last 6 sprints from boards 42, 43 and 51 and build a dashboard bundle."

Claude queries through the connector, writes a file in the same `schemaVersion: 2.0` shape, and you load it exactly as above. Same contract, nothing to install. The fetcher script stays as the scheduled, unattended path — cron cannot ask Claude for anything.

## Route 3 — live mode, for arbitrary drill-down

```bash
# offline demo, backed by an existing bundle
python3 scripts/serve_live.py --bundle data/sample-bundle.json

# live, querying Jira on demand
python3 scripts/serve_live.py --jira-boards 42,43 --sprints 6
```

Then open `http://127.0.0.1:8000/dist/delivery-value-dashboard.html`.

The page probes for `api/contexts` on load. If something answers, every sprint the server knows about appears in the picker — including ones not in the bundle, shown as stubs. Selecting a stub fetches just that sprint. Nothing is pulled until it is asked for, because pulling six months of every board up front is how a "live" dashboard becomes a slow one.

The server binds to `127.0.0.1` only and holds credentials in memory. It is a developer convenience, not something to deploy. If you find yourself wanting it behind a hostname with logins, you want a real BI tool — see the README.

### What happens without it

Nothing breaks. The probe is skipped entirely on `file://` origins, the context bar shows only bundled sprints, and the file behaves as it did before. This is deliberate: the emailed copy must stay silent and self-contained.

---

## Bundle format

Additive to the v1.0 schema. **v1.0 single-sprint files still load unchanged** — they are wrapped into one implicit context internally, and the context bar stays hidden because there is nothing to switch between.

```json
{
  "schemaVersion": "2.0",
  "meta": { "organisation": "…", "currency": "USD", "baseUrl": "…", "sourceLabel": "…" },
  "contexts": [
    { "id": "BLC/42/S24", "source": "jira",
      "projectKey": "BLC", "projectName": "Highpeak Commerce",
      "boardId": "42",    "boardName": "Storefront Delivery", "team": "Storefront Team",
      "sprintName": "Sprint 24", "sprintState": "active", "sprintGoal": "…",
      "startDate": "2026-08-03", "endDate": "2026-08-14", "asOfDate": "2026-08-10",
      "workingDays": ["2026-08-03", "…"], "issueCount": 22 }
  ],
  "defaultContextId": "BLC/42/S24",
  "issues": [ { "key": "BLC-401", "contextId": "BLC/42/S24", "…": "…" } ],
  "byContext": {
    "BLC/42/S24": { "burndown": [], "history": [], "releases": [], "dora": {} }
  }
}
```

| Field | Notes |
|---|---|
| `contexts[].id` | Any stable string. The fetcher uses `PROJECT/board/sprintId`. |
| `contexts[].sprintState` | `active` marks the sprint as current in the picker. |
| `issues[].contextId` | Which context an issue belongs to. Required in a bundle. |
| `byContext[id].history` | Sprints **up to and including** this one — never later ones. |
| `defaultContextId` | What opens first. Defaults to the active sprint if omitted. |

### Live-mode API

Two endpoints, same shapes:

```
GET api/contexts          -> { source, label, orgConfig, contexts: [ …context objects… ] }
GET api/context?id=<id>   -> { context, orgConfig, issues, burndown, history, releases, dora }
```

Implement these against anything you like — the page does not care what is behind them.

`orgConfig` is the organisation's calendar and status rules (see
[organisation-config.md](organisation-config.md)). **The server's copy wins.** It computed
the forecasts, so a page opened from a file baked with a different calendar adopts the
server's and says so in the footer — the alternative is the tile and the rest of the page
describing one sprint under two sets of rules. If your implementation omits it, the page
keeps the calendar it already had.

---

## Performance — measured, not estimated

Run it yourself: `make perf`. `tests/perf.py` instruments a real browser at four bundle sizes and prints a table.

| Bundle | File | Issues | Sprints | First load | Switch sprint | Filter keystroke | Unit toggle |
|---|---|---|---|---|---|---|---|
| single sprint | 15 KB | 22 | 1 | 25 ms | 31 ms | 15 ms | 27 ms |
| 3 boards × 6 sprints | 144 KB | 242 | 18 | 24 ms | 24 ms | 11 ms | 21 ms |
| 21 boards × 6 sprints | 892 KB | 1,754 | 126 | 35 ms | 39 ms | 22 ms | 69 ms |
| 66 boards × 6 sprints | 2.8 MB | 5,538 | 396 | 71 ms | 23 ms | 9 ms | 21 ms |

**Interaction cost is flat in dataset size.** Switching sprint takes about the same time with 22 issues as with 5,538, because only the selected sprint's issues are ever drawn — around a dozen. What costs time is redrawing the charts, and that is constant.

### Does trimming the sprint dropdown to the selected project help?

No, and the numbers are unambiguous. At 462 selectable contexts:

| Operation | Time |
|---|---|
| Building the sprint dropdown, scoped to the current board | **0.2 ms** |
| Building it unscoped, every context in the file | **0.2 ms** |
| One filter keystroke | 9 ms |
| Switching sprint | 23 ms |

The dropdown is already scoped — that is a usability decision, not a performance one, and it should stay for that reason. But the saving is 0.0 ms, or 0% of a single keystroke. Optimising it would be work spent on the wrong thing.

### Where the cost actually is

**Payload, not CPU.** At 5,538 issues the file is 2.8 MB, of which 79% is the issue array itself. Dropping every null field and the recomputable `workingDays` arrays saves 8% — not enough to justify a format change that would complicate every reader.

So the ceiling is delivery, not rendering: a 2.8 MB attachment is unpleasant to email and slow on a poor connection, long before anything on the page feels sluggish.

### What to do at scale

| Situation | Do this |
|---|---|
| Under ~2,000 issues | Nothing. Bundle everything, it is comfortably fast. |
| 2,000–6,000 issues | Still fine to use; consider splitting bundles per project so each recipient gets only what they need. |
| Above ~6,000 issues | Use live mode. Bundle the current sprint per board and let the server supply the rest on demand — the page already fetches a sprint only when it is selected. |
| Any size, if emailing | Keep the bundle under about 1 MB. That is roughly 20 boards × 6 sprints. |


## `GET api/forecast?id=<contextId>`

Returns the full output of `agent/tools/forecast.py` for one context — the same
structure the CLI prints with `--json`, plus a `sampled_from` block naming the slice.

```
{
  "inputs":      { "throughput_observations": 55, "window_days": 76,
                   "calendar": "5-day working week (mon…fri), 0 holidays, …", ... },
  "sprint_completion": { "percentiles": {"50": "2026-08-17", "85": "2026-08-20"}, ... },
  "capacity_to_target": { "percentiles": {"85": 1}, ... },
  "next_commitment":    { "recommended": 5, "note": "...", ... },
  "sampled_from": { "slice": "team 'Storefront Team'", "contexts": 6,
                    "first_resolved": "2026-05-26", "last_resolved": "2026-08-13" }
}
```

### Optional parameters

| Parameter | Replaces | Rejected when |
|---|---|---|
| `items=<n>` | the outstanding count for the selected context | not a whole number in 1–5000 |
| `date=<YYYY-MM-DD>` | the selected sprint's end date | not an ISO date |

Both are echoed back under `asked`, alongside `default_items` and `default_date`, so a
caller can always show what was swapped for what.

Bad input returns `400` with an `{"error": ...}` message rather than being ignored. A
silently dropped override returns a number answering a different question, which reads
exactly like an answer to the one asked.

An unknown id returns `404` with `{"error": "unknown context '<id>'"}`, the same shape
as `api/context`.

**The calendar is named in `inputs.calendar`,** because two forecasts of one board under
different working weeks are different forecasts and the difference is otherwise invisible.
Note that a shorter working week also means fewer throughput observations, so a board that
forecast happily under five days can return a refusal under four. That is the correct
answer, not a regression.

**The simulation horizon.** A single trial is abandoned after 400 working days. The share
of trials that hit it comes back as `sprint_completion.unfinished_fraction`, and is named
in the `basis` line whenever it is non-zero. Without that, a request far larger than the
team's pace returns every percentile at exactly 400 days — uniform, precise and
meaningless.

**What it samples.** Every issue belonging to the same *team* as the requested context,
across all of that team's sprints, over the full span of imported history — not the
90-day default and not the selected sprint alone. A single sprint yields too few
throughput observations to sample and the tool refuses; the team's whole record is what
makes an answer possible. Only the **remaining work** comes from the selected context.

Rollup ids (`roll:<projectKey>|<boardId>`) are synthesised by the dashboard and are
accepted here too: the outstanding count is then every open item across that board.

Forecasts are cached per context id for the process lifetime. Against a bundle this is
instant; against live Jira the first call for a team pulls every sprint on it and can
take a few seconds.


## `GET api/sequence?id=<contextId>`

Runs `intake.sequence()` for the board the context belongs to, against the asks in
`data/asks/` whose `team` matches that board id — the same call `make intake-sequence`
makes. Returns `unachievable_at_any_priority`, `comparison` (one row per ordering, with
`delays_others_by_days`), `skipped` (asks that could not be sized, each with its reason),
`basis` and `note`.

A board with no recorded asks returns `available: false` with a sentence saying so, not an
empty comparison. Unknown ids return `404`.

Only the bundle backend supports it. A live Jira connection returns `available: false`
with a reason: sizing an ask needs the board's completed epics and its measured
interruption rate, and a sprint-at-a-time pull does not carry either. Assembling a partial
dataset and returning a number built on it would be worse than declining.

**No value score is computed**, and none will be. The delivery consequence of an ordering
is computable; the relative worth of competing asks is a judgement that stays with the
people accountable for it.
