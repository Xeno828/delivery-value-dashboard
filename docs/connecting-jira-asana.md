# Connecting Jira and Asana

## Why the page cannot call them itself

Two hard constraints, neither of which has a clever workaround:

1. **CORS.** Jira and Asana both reject cross-origin requests originating from a browser page. This is deliberate on their side.
2. **Secrets.** Any token embedded in an HTML file is readable by everyone that file is forwarded to. A dashboard's whole value is that it gets shared.

So live data arrives via a small script that runs where the credentials already live. That is a feature: the credential boundary is explicit and auditable, rather than hidden in a page someone might email.

## Route 0 — OAuth 2.0 (3LO), for a customer's site

The fetcher below authenticates with a personal API token. That is right for
your own board and wrong for anyone else's: the token carries the permissions
of whoever generated it, cannot be scoped, and is revoked only by deleting it.
A customer connecting their Jira needs a grant they consented to, that is
scoped to what you asked for, and that they can withdraw without telling you.

### One-time setup

This part cannot be automated, and the credentials should not pass through
anyone else's hands:

1. **developer.atlassian.com → Console → Create → OAuth 2.0 integration**
2. **Permissions → Jira API →** add `read:jira-work` and `read:jira-user`.
   Read-only, deliberately. An app that asks for write access to close a deal
   is an app whose consent screen makes the buyer's security reviewer stop and
   read.
3. **Authorization → Callback URL:** `http://127.0.0.1:8721/callback`
4. **Settings →** copy the client id and secret into your environment:

```bash
export JIRA_OAUTH_CLIENT_ID=…
export JIRA_OAUTH_CLIENT_SECRET=…
```

### Connecting

```bash
python3 scripts/jira_auth.py login      # opens a browser, stores the grant
python3 scripts/jira_auth.py status     # sites, scopes, expiry — never the token
python3 scripts/jira_auth.py logout     # forgets it locally
```

Then the fetcher uses it automatically:

```bash
python3 scripts/fetch_delivery_data.py --jira-board 42 --out data/dashboard-data.json
```

`--auth auto` (the default) prefers a stored grant and falls back to the API
token. Which one it used is printed on every run, because the two see different
sets of issues and a file produced by the wrong one looks entirely legitimate.
Force either with `--auth oauth` or `--auth token`.

If a grant covers more than one Jira site the fetcher **refuses to guess** —
name one with `--jira-site` or `JIRA_SITE`. Silently picking the first is how a
report about the wrong company gets produced.

### Where the grant lives

`.jira-oauth.json`, created mode 0600, git-ignored alongside `.env`. It holds
an access token and a rotating refresh token. Nothing prints either one; the
security suite asserts that, along with the file being ignored, the redirect
listener binding to loopback only, the `state` parameter being verified, and
the scopes staying read-only.

Revoking is the customer's to do, at **id.atlassian.com → Account settings →
Connected apps**. `logout` only forgets the local copy.

### What this is not

This is the Connect/3LO half of the connection work — the half that lives in
this repository. A Marketplace listing, its review and billing are Atlassian
Console tasks with no code here. `forge/` holds a scaffold for the other route
and a note on what porting to it would cost.

## Route 1 — the fetcher script, with an API token

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
