# Connecting Jira and Asana

## Why the page cannot call them itself

Two hard constraints, neither of which has a clever workaround:

1. **CORS.** Jira and Asana both reject cross-origin requests originating from a browser page. This is deliberate on their side.
2. **Secrets.** Any token embedded in an HTML file is readable by everyone that file is forwarded to. A dashboard's whole value is that it gets shared.

So live data arrives via a small script that runs where the credentials already live. That is a feature: the credential boundary is explicit and auditable, rather than hidden in a page someone might email.

## Route 1 — the fetcher script

```bash
pip install -r scripts/requirements.txt

export JIRA_URL=https://your-domain.atlassian.net
export JIRA_EMAIL=you@company.com
export JIRA_TOKEN=…          # id.atlassian.com → Security → API tokens

python3 scripts/fetch_delivery_data.py --jira-board 42 --out data/dashboard-data.json
```

Asana:

```bash
export ASANA_TOKEN=…         # app.asana.com → My Settings → Apps → Developer
python3 scripts/fetch_delivery_data.py --asana-project 1201234567890
```

Both at once merges the two issue lists into one dataset.

Useful flags:

| Flag | Purpose |
|---|---|
| `--jira-jql "project = BLC AND sprint in openSprints()"` | Use raw JQL instead of a board |
| `--sp-field customfield_10016` | Force the story-point field if auto-discovery picks the wrong one |
| `--values-csv values.csv` | Merge business-value estimates from a side file |
| `--team`, `--org`, `--currency` | Header text and money formatting |

Then load the result: drag `data/dashboard-data.json` onto the upload panel, or serve the folder and open `index.html?data=data/dashboard-data.json`.

> The `?data=` route needs an HTTP server (`make serve`). Browsers block `fetch` from `file://` — that is a security feature, not a bug to route around.

### Scheduling

```bash
cp .env.example .env    # fill in credentials; .env is git-ignored
crontab -e
```

```
0 8 * * 1-5   cd /path/to/repo && ./scripts/refresh.sh >> /tmp/dashboard.log 2>&1
```

### What the fetcher can and cannot know

| Derived automatically | Needs a source you supply |
|---|---|
| Issues, status, assignee, points, priority, epic, dates | **Business value** — no tracker has it natively; use `--values-csv` or an Asana number field |
| **Cycle time**, from the first transition into an in-progress status in the changelog | **DORA metrics** — from your CI/CD tool |
| **Mid-sprint additions**, from when the sprint field was set | *(nothing)* — the schema carries no hours or timesheet field |
| Burndown, reconstructed from resolution dates | **Releases** — carried forward from the previous file |

The script never silently blanks a card it could not populate: it carries the previous file's values forward and prints what was missing to stderr.

## Route 2 — MCP connectors, once the format has proved itself

Connect the **Atlassian** and **Asana** connectors in Claude, then ask in plain language:

> "Pull Sprint 25 from the Storefront board and rebuild the dashboard data file."

Same JSON contract, no script to run, and the narrative can be regenerated at the same time. Keep the fetcher regardless — it is what runs at 08:00 on a weekday with nobody present.

## Route 3 — no connection at all

Export a CSV from Jira or Asana and upload it. See [importing-data.md](importing-data.md). This is the right starting point: prove which metrics people actually use before you build a pipeline for them.

## Security notes

- Credentials live only in the fetcher's environment. `.env` is git-ignored; keep it that way.
- `data/dashboard-data.json` is git-ignored by default because it contains real issue titles. Remove that line only if your repository is private and you have decided that is acceptable.
- The GitHub Pages workflow publishes the **demo** dataset. Do not enable it on a repository whose `data/` folder holds real issue data unless your plan supports private Pages.
- Use a scoped API token, not a password, and rotate it on the same schedule as everything else.
