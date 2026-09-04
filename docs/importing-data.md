# Uploading your own data

Open the dashboard, click **Load data**, drop a file. The wizard is three steps and it never applies anything without showing you what it read first.

Accepted: `.csv`, `.tsv`, `.xlsx`, `.json` — including a raw export straight out of Jira or Asana, with whatever column names your instance happens to use.

Nothing is uploaded anywhere. The file is read in the browser, held in memory, and gone when the tab closes.

---

## Step 1 — choose a file

Drag and drop, browse, or paste text. A pasted block starting with `{` or `[` is read as JSON; anything else is read as delimited text with the delimiter sniffed from the header row (comma, semicolon, tab or pipe).

If the file is a full dashboard dataset — one you previously downloaded, or one the fetcher script wrote — the mapping step recognises it and no correction is needed.

## Step 2 — check the column mapping

Your column headings are matched against a synonym list, so `Issue key`, `Key`, `Task ID` and `gid` all find the key field, and `Custom field (Story Points)` finds story points. Every guess is shown with an example value from your file, and every one can be overridden from a dropdown.

Three fields are required: **key**, **summary**, **status**. Everything else degrades gracefully — the preview tells you exactly which cards go blank without it.

**Added mid-sprint** deserves a note. Almost no tracker exports this, so when no column matches, the wizard offers to infer it: anything created after the sprint start date counts as added. That is a proxy and it is labelled as one in the preview. It is also the field that makes the burndown's scope line work, which is the single most useful thing this dashboard adds over a stock Jira report — so infer it rather than leave it blank.

### Dates

Handled without configuration:

| Format | Example |
|---|---|
| ISO, with or without a time | `2026-08-03`, `2026-08-03T09:15:00.000+0100` |
| Jira's default | `22/Jul/26 3:41 PM` |
| Month name first | `Jul 22, 2026` |
| Excel serial numbers (from `.xlsx`) | `46022` |
| All-numeric | `13/08/2026`, `08/13/2026` |

All-numeric dates are the dangerous case. The wizard scans the whole column: if any value has a first part above 12, the column is day-first and that is certain. If nothing in the column disambiguates — every day is 12 or lower — it says so loudly in the preview rather than guessing quietly, because getting this backwards silently corrupts every elapsed-time figure on the page. Re-export with ISO dates if you see that warning.

### Sprint window

Pre-filled from your data: earliest start, latest end. It drives the burndown, the pace-vs-clock tile and the age bands, so correct it if the guess is wrong. Weekends are excluded; if your team observes public holidays, edit `workingDays()` in `src/app.js`.

### Replace or merge

- **Replace** — the uploaded rows become the whole dataset. Use this for a fresh sprint export.
- **Merge** — rows with a matching key are updated, new keys are added, and *only fields your file actually supplied* overwrite existing values. This is how you layer business-value estimates on top of a Jira export: upload the Jira file with **Replace**, then a two-column `key,businessValue,valueBasis` file with **Merge**. There is a template for exactly that in `data/templates/`.

## Step 3 — preview before applying

Counts, warnings, and the first eight rows exactly as the dashboard will read them. Warnings that matter:

| Warning | What it means |
|---|---|
| **Duplicate keys** | The same key appears twice. Every count is inflated until you de-duplicate. |
| **Ambiguous date format** | Day-first and month-first cannot be told apart, or the column contradicts itself. |
| **No story points** | The burndown, pace and distribution charts go flat. Item counts still work. |
| **No started date** | No cycle time, so the waiting-vs-working chart is empty. The fetcher script derives this from the Jira changelog. |
| **No business value** | The value card reads zero. Merge a value file. |
| **No release metrics** | DORA figures come from your CI/CD tool, not a tracker. |

Nothing is applied until you press **Apply to the dashboard**, and a ■ warning — duplicate keys, an ambiguous date format, no sprint window, no issues under the header — turns that button off and says why beside it. Fix the file, or the mapping, and come back.

A multi-sprint bundle (a JSON with `contexts[]`, the shape `make bundle` and the fetcher write) skips the mapping and the sprint window: it carries its own, per sprint, and loads whole. It always replaces what is loaded.

---

## What gets recalculated, and why that matters

The recomputed burndown carries **both an item series and a point series**, so the dashboard's Items/Points toggle works on uploaded data immediately.

When you upload a flat file, the **burndown and the current sprint's history row are recomputed from your issues** — they are not carried over from whatever was loaded before. Stale charts sitting under fresh numbers is worse than no charts, and it is the failure mode most import features ship with.

Under **Replace**, nothing else is carried forward. A flat file has no `releases[]`, no `dora{}`, no earlier sprints and no sprint goal, so the tiles that read those — *Releases & milestones*, *Release quality & speed*, *Can we trust the forecast?*, *Team load* — say the record is absent rather than showing the previously loaded dataset's under your new title. That is what happened before 1.79.25: a fresh export applied over the demo kept the demo's goal, its milestones and its release metrics, each labelled "from the record". A full JSON dataset brings its own blocks and they are used. The only things kept from what was loaded are the organisation's calendar (`orgConfig`) and its currency, because neither is a property of a file.

Under **Merge**, the loaded dataset is the base — goal, history, releases and release metrics included — and your rows are layered onto it.

---

## Getting a good export out of Jira

Issue Navigator → **Export** → *Export Excel CSV (all fields)*. Include at minimum:

`Issue key, Summary, Status, Assignee, Priority, Created, Resolved, Due Date, Custom field (Story Points), Parent summary`

The one thing a CSV export cannot give you is **when work actually started** — that lives in the changelog, not on the issue. Without it there is no cycle time and no waiting-vs-working split. Two options: add a "Development started" date field to your workflow, or use `scripts/fetch_delivery_data.py`, which reads the changelog and derives it. The second is less work.

## Getting a good export out of Asana

Project → **Export / Print** → *CSV*. The default export already carries `Task ID`, `Created At`, `Completed At`, `Start Date`, `Due Date`, `Assignee`, `Section/Column` and `Tags`, which is enough for everything except story points and value — add those as custom number fields named `Story Points` and `Business Value` and they map automatically.

## Browser support

`.xlsx` reading uses the built-in `DecompressionStream` API — Chrome 103+, Edge 103+, Safari 16.4+, Firefox 113+. On anything older the wizard says so and asks for a CSV instead. Everything else works in any browser from the last five years.
