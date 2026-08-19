#!/usr/bin/env python3
"""
serve_live.py — optional live mode for the dashboard.

The dashboard is a static file and stays that way. This serves it, plus two
small endpoints it will use *if it finds them*:

    GET  api/contexts            -> every project/board/sprint available
    GET  api/context?id=<id>     -> that sprint's issues and derived series

If this is not running, the dashboard silently falls back to whatever contexts
were bundled into the file. Nothing breaks; you just cannot reach sprints that
were not fetched.

Two backends:

    # offline / demo — serve straight out of an existing bundle
    python3 scripts/serve_live.py --bundle data/sample-bundle.json

    # live — query Jira on demand (credentials from the environment or .env)
    python3 scripts/serve_live.py --jira-boards 42,43 --sprints 6

Binds to 127.0.0.1 only. This holds API credentials in memory; it is a
developer convenience, not a service to deploy. If you find yourself wanting to
put it behind a hostname, you want a real BI tool instead — see the README.
"""

import argparse
import json
import os
import pathlib
import sys
import threading
import urllib.parse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
# The forecast endpoint runs the real tool rather than reimplementing it. This
# is the only place scripts/ depends on agent/tools/, and it is deliberate: a
# second implementation of the Monte Carlo is a second set of numbers, and the
# whole point of serving it from here is that the page and the agent cannot
# disagree about the same sprint.
sys.path.insert(0, str(ROOT / "agent" / "tools"))
import forecast as FC  # noqa: E402


# ------------------------------------------------------------- forecasting
def team_slice(contexts, ctx):
    """Every context belonging to the same team as `ctx`.

    A forecast built from one sprint refuses — on the demo board a single sprint
    offers 2 throughput observations against a threshold of 8. The team's whole
    history offers 55. So the sample is the team, and only the *remaining work*
    comes from the selected sprint.

    `team` is a free-text label, so fall back to project+board when it is absent.
    Slicing by team rather than board matters when a team runs two boards: the
    request is for everything known about that team, not a convenient subset.
    """
    team = (ctx.get("team") or "").strip()
    if team:
        return [c for c in contexts if (c.get("team") or "").strip() == team], "team %r" % team
    return ([c for c in contexts
             if c.get("projectKey") == ctx.get("projectKey")
             and c.get("boardId") == ctx.get("boardId")],
            "board %s/%s" % (ctx.get("projectKey"), ctx.get("boardId")))


def forecast_for(contexts, issues, byContext, cid):
    """Run the real forecaster for one context. Returns None for an unknown id.

    The slice is the thing to get right, and getting it wrong produces a
    credible wrong number rather than an error — see CHANGELOG 1.8.0, where
    reading the wrong context turned a 19-day forecast into 77.
    """
    ctx = next((c for c in contexts if c["id"] == cid), None)
    roll_members = None
    if ctx is None and cid.startswith("roll:"):
        # The dashboard synthesises one rollup per board client-side, so the
        # server has never seen this id. It is still a real question — "when
        # does everything open on this board land" — so answer it rather than
        # bouncing the caller. Key format: roll:<projectKey>|<boardId>.
        key = cid[len("roll:"):]
        proj, _, board = key.partition("|")
        roll_members = [c for c in contexts
                        if str(c.get("projectKey") or c.get("projectName") or "") == proj
                        and str(c.get("boardId") or c.get("boardName") or "") == board]
        if not roll_members:
            return None
        latest = max(roll_members, key=lambda c: str(c.get("endDate") or ""))
        ctx = dict(latest)
        ctx["sprintName"] = "All %d sprints" % len(roll_members)
    if ctx is None:
        return None
    members, slice_label = team_slice(contexts, ctx)
    member_ids = {c["id"] for c in members}
    team_issues = [i for i in issues if i.get("contextId") in member_ids]
    # Remaining work is the selected context's, never the team's — the sample is
    # wide, the outstanding count is narrow. A rollup's "selected context" is
    # every sprint it spans.
    remaining_ids = ({c["id"] for c in roll_members} if roll_members else {cid})
    remaining = len([i for i in issues
                     if i.get("contextId") in remaining_ids
                     and (i.get("statusCategory") or "") != "Done"])
    as_of = ctx.get("asOfDate") or ctx.get("endDate")
    meta = {"sprintName": ctx.get("sprintName"), "startDate": ctx.get("startDate"),
            "endDate": ctx.get("endDate"), "asOfDate": as_of,
            "workingDays": ctx.get("workingDays")}
    ds = {"issues": team_issues, "meta": meta,
          "releases": (byContext.get(cid) or {}).get("releases", [])}
    out = FC.build(ds, as_of=as_of, remaining=remaining, target=ctx.get("endDate"))
    resolved = sorted(x for x in (FC._d(i["resolved"]) for i in team_issues
                                  if i.get("resolved")) if x)
    out["sampled_from"] = {
        "slice": slice_label,
        "contexts": len(members),
        "first_resolved": resolved[0].isoformat() if resolved else None,
        "last_resolved": resolved[-1].isoformat() if resolved else None,
    }
    return out


# --------------------------------------------------------------- backends
class BundleBackend:
    """Reads an existing bundle file. Used for demos, tests, and for working
    offline on a plane with last week's pull."""

    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.data = json.loads(self.path.read_text())
        self._fc = {}   # forecasts, per context id, for the process lifetime
        self.label = "bundle file %s" % self.path.name
        self.source = (self.data.get("meta") or {}).get("source", "bundle")

    def contexts(self):
        return [{k: v for k, v in c.items() if k != "workingDays"}
                for c in self.data.get("contexts", [])]

    def context(self, cid):
        by = (self.data.get("byContext") or {}).get(cid, {})
        ctx = next((c for c in self.data["contexts"] if c["id"] == cid), None)
        if ctx is None:
            return None
        return {
            "context": ctx,
            "issues": [i for i in self.data["issues"] if i.get("contextId") == cid],
            "burndown": by.get("burndown", []), "history": by.get("history", []),
            "releases": by.get("releases", []), "dora": by.get("dora"),
        }

    def forecast(self, cid):
        if cid not in self._fc:
            self._fc[cid] = forecast_for(self.data.get("contexts", []),
                                         self.data.get("issues", []),
                                         self.data.get("byContext") or {}, cid)
        return self._fc[cid]


class JiraBackend:
    """Queries Jira on demand. Sprint lists are cheap; issues are fetched only
    when a sprint is actually selected, and cached for the process lifetime."""

    def __init__(self, board_ids, sprints):
        import fetch_delivery_data as F
        self.F = F
        url, email, token = (os.environ.get("JIRA_URL"), os.environ.get("JIRA_EMAIL"),
                             os.environ.get("JIRA_TOKEN"))
        if not (url and email and token):
            sys.exit("Set JIRA_URL, JIRA_EMAIL and JIRA_TOKEN (or use --bundle)")
        self.j = F.Jira(url, email, token)
        self.boards = [b.strip() for b in board_ids.split(",") if b.strip()]
        self.sprints = sprints
        self.source = "jira"
        self.label = "Jira, boards " + ", ".join(self.boards)
        self._ctx = None
        self._cache = {}
        self._lock = threading.Lock()

    def contexts(self):
        with self._lock:
            if self._ctx is not None:
                return self._ctx
            out = []
            for b in self.boards:
                info = self.j.get("/rest/agile/1.0/board/%s" % b)
                proj = (info.get("location") or {})
                data = self.j.get("/rest/agile/1.0/board/%s/sprint" % b, state="active,closed")
                sprints = sorted(data.get("values") or [],
                                 key=lambda s: s.get("startDate") or "", reverse=True)[:self.sprints]
                for sp in sprints:
                    out.append({
                        "id": "%s/%s/%s" % (proj.get("projectKey", "?"), b, sp["id"]),
                        "source": "jira",
                        "projectKey": proj.get("projectKey"), "projectName": proj.get("projectName"),
                        "boardId": b, "boardName": info.get("name"),
                        "team": info.get("name"),
                        "sprintName": sp.get("name"), "sprintState": sp.get("state"),
                        "sprintGoal": sp.get("goal") or "",
                        "startDate": (sp.get("startDate") or "")[:10],
                        "endDate": (sp.get("endDate") or "")[:10],
                        "asOfDate": None, "issueCount": 0,
                        "_sprintId": sp["id"],
                    })
            self._ctx = out
            return out

    def context(self, cid):
        if cid in self._cache:
            return self._cache[cid]
        ctx = next((c for c in self.contexts() if c["id"] == cid), None)
        if ctx is None:
            return None
        args = argparse.Namespace(jira_board=None, jira_jql="sprint = %s ORDER BY created ASC" % ctx["_sprintId"],
                                  sp_field=None, sprint_field=None)
        issues, _ = self.F.jira_pull(args)
        meta = dict(ctx)
        meta["workingDays"] = self.F.working_days(ctx["startDate"], ctx["endDate"])
        meta["asOfDate"] = ctx["asOfDate"] or ctx["endDate"]
        out = {
            "context": meta, "issues": issues,
            "burndown": self.F.build_burndown(issues, meta),
            "history": [], "releases": [], "dora": None,
        }
        ctx["issueCount"] = len(issues)
        self._cache[cid] = out
        return out

    def forecast(self, cid):
        """Unlike the bundle, this has to fetch. A forecast needs the team's
        whole history, so every sprint on the team is pulled — slow the first
        time, cached after, and the reason the endpoint can take a few seconds
        against live Jira."""
        if not hasattr(self, "_fc"):
            self._fc = {}
        if cid in self._fc:
            return self._fc[cid]
        all_ctx = self.contexts()
        ctx = next((c for c in all_ctx if c["id"] == cid), None)
        if ctx is None:
            return None
        members, _ = team_slice(all_ctx, ctx)
        issues = []
        for m in members:
            got = self.context(m["id"])
            if got:
                issues.extend(got["issues"])
        self._fc[cid] = forecast_for(all_ctx, issues, {}, cid)
        return self._fc[cid]


# ---------------------------------------------------------------- handler
class Handler(SimpleHTTPRequestHandler):
    backend = None

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        path = u.path.lstrip("/")
        if path in ("api/contexts", "dist/api/contexts"):
            b = self.backend
            return self._json({"source": b.source, "label": b.label, "contexts": b.contexts()})
        if path in ("api/forecast", "dist/api/forecast"):
            cid = urllib.parse.parse_qs(u.query).get("id", [""])[0]
            got = self.backend.forecast(cid)
            if got is None:
                return self._json({"error": "unknown context %r" % cid}, 404)
            return self._json(got)
        if path in ("api/context", "dist/api/context"):
            cid = urllib.parse.parse_qs(u.query).get("id", [""])[0]
            got = self.backend.context(cid)
            if got is None:
                return self._json({"error": "unknown context %r" % cid}, 404)
            return self._json(got)
        return SimpleHTTPRequestHandler.do_GET(self)

    def log_message(self, fmt, *a):
        # Two callers, two shapes: log_request passes the request line as a
        # string, log_error passes an HTTPStatus. Testing membership against a
        # non-string raises, and it raised *after* the 404 had been decided but
        # before it was sent — so the handler thread died and the client saw a
        # dropped connection rather than a refusal. A browser asking for
        # /favicon.ico was enough to trigger it on every page load.
        if "/api/" in str(a[0] if a else ""):
            sys.stderr.write("  %s\n" % (fmt % a))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", help="serve from an existing bundle file (offline/demo)")
    ap.add_argument("--jira-boards", help="comma-separated Jira board ids, queried live")
    ap.add_argument("--sprints", type=int, default=6, help="sprints per board to offer")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()

    if a.bundle:
        Handler.backend = BundleBackend(a.bundle)
    elif a.jira_boards:
        Handler.backend = JiraBackend(a.jira_boards, a.sprints)
    else:
        ap.error("give --bundle or --jira-boards")

    os.chdir(ROOT)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print("Serving %s" % Handler.backend.label)
    print("  http://127.0.0.1:%d/dist/delivery-value-dashboard.html" % a.port)
    print("  %d contexts offered" % len(Handler.backend.contexts()))
    print("Ctrl-C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
