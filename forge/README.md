# Forge scaffold

**Not wired up. Never deployed.** The working Jira connection is OAuth 2.0
(3LO) — `scripts/jira_auth.py`, with `--auth oauth` on the fetcher.

## Why this directory exists

Roadmap item 1 says *"a Forge or Connect app"*, and the roadmap itself calls
that the one genuinely open decision in phase 1. Writing the manifest down —
the scopes, the module types, the resolver boundary — makes the decision
cheaper to take later and keeps the argument from being settled by accident by
whoever writes the first working version.

## What porting actually costs

The numbers come from three dependency-free Python modules. Forge runs Node in
Atlassian's sandbox and cannot call them. That leaves two options:

| | What it means | What it costs |
|---|---|---|
| **Forge as a data path** | Forge pulls issues, the Python still computes | Needs somewhere for the Python to run, so the Marketplace listing stops being the whole deployment |
| **Port the tools to JS** | A second Monte Carlo, a second facts pack | Two implementations of one number. The tile and the written brief will eventually disagree about the same sprint |

The project already refused option 2 once: the forecast tile shows an offline
notice in an emailed file rather than recomputing itself in the browser,
because the alternative was two simulations. The same reasoning applies here
and is why nothing in `src/index.js` computes anything.

## If you do pick this route

1. `npm install -g @forge/cli && forge login`
2. `forge register` — writes an app id into `manifest.yml`. **Do not commit
   it**; it ties the manifest to one Atlassian account.
3. Build the static resource into `static/dashboard/build`. `dist/` is a single
   self-contained HTML file, so this is mostly a copy — but note that a Forge
   iframe is not an emailed file, and the security suite's no-network,
   no-storage assertions are about the file, not about this.
4. Keep the scopes in `manifest.yml` identical to `SCOPES` in
   `scripts/jira_auth.py`. Two routes seeing different issues is a bug that
   looks like a data problem.

## What is not here

Nothing about the Marketplace listing, its review, or billing. That is Atlassian
Console work with no code in this repository.
