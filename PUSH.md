# Pushing this to git

The repository is already initialised with its full history on `main`, so there is nothing to stage or write a message for. Two commands.

**On a Mac, one command does all of it** — unpack, verify the history survived the download, run the tests that need no browser, optionally re-author the commits as you, and push:

```bash
chmod +x scripts/setup-on-mac.sh && ./scripts/setup-on-mac.sh
```

It refuses rather than overwrites if the destination exists. Override the paths with `ZIP=` and `DEST=`. The rest of this file is the manual version.

## GitHub, with the `gh` CLI

```bash
unzip delivery-value-dashboard.zip
cd delivery-value-dashboard

gh repo create delivery-value-dashboard --private --source=. --push
```

That creates the remote and pushes in one step. Drop `--private` for a public repo.

## GitHub, GitLab, Bitbucket, or anything else

Create an empty repository in the web UI first — **no README, no .gitignore, no licence**, or the first push will be rejected as a non-fast-forward. Then:

```bash
unzip delivery-value-dashboard.zip
cd delivery-value-dashboard

git remote add origin git@github.com:<you>/delivery-value-dashboard.git
git push -u origin main
```

## Before you push, two things worth a look

**Check the commit is attributed the way you want.** It is currently authored by the git identity that was set in the build environment:

```bash
git log -1 --format='%an <%ae>'
```

To claim it as your own:

```bash
git -c user.name="Your Name" -c user.email="you@company.com" commit --amend --reset-author --no-edit
```

**Decide about `dist/`.** The built dashboard is committed deliberately, so the repository is usable without running anything — download and open. CI enforces that it stays current (`make check` fails if `src/` changed and `dist/` was not rebuilt). If your team would rather build artefacts never be committed, remove it before the first push:

```bash
git rm --cached dist/delivery-value-dashboard.html
echo "dist/" >> .gitignore
git commit -m "Do not track build output"
```

Be aware that this also breaks the GitHub Pages workflow's assumption and the "clone and open it" instruction in the README.

## What is in the first commit

75 files, roughly 15 MB — most of which is the demo video.

| | |
|---|---|
| `src/` | Dashboard source: metrics, charts, drill-downs, the import wizard |
| `dist/` | The built single-file dashboard (173 KB) |
| `CLAUDE.md` | The standing constraints, for any agent session opened in this repo |
| `agent/` | The agent definition, its three deterministic tools (facts, delivery forecasting, product intake), templates and worked examples |
| `scripts/` | Jira/Asana fetcher, live-mode server, bundle generators, demo recorder |
| `tests/` | Four suites — product, agent, accessibility, security — plus the perf harness |
| `docs/` | Every explanatory document, the demo video and screenshots |
| `data/` | Demo datasets, worked product-intake asks, and import templates |
| `.github/` | CI running all four suites, and an optional Pages workflow |

## After the first push

CI will run on the next push or pull request. It needs nothing configured — no secrets, no environment. It builds, fails if `dist/` is stale, then runs all four suites and a dependency audit.

The Pages workflow is **not** enabled by default and publishes only the demo dataset. Do not enable it on a repository whose `data/` folder holds real issue titles unless your plan supports private Pages.

`.env` is git-ignored, as is `data/dashboard-data.json` — the file the fetcher writes, which contains real issue titles. Both are deliberate; check they survive any `.gitignore` edits you make.
