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


# --------------------------------------------------------------- backends
class BundleBackend:
    """Reads an existing bundle file. Used for demos, tests, and for working
    offline on a plane with last week's pull."""

    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.data = json.loads(self.path.read_text())
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
        if path in ("api/context", "dist/api/context"):
            cid = urllib.parse.parse_qs(u.query).get("id", [""])[0]
            got = self.backend.context(cid)
            if got is None:
                return self._json({"error": "unknown context %r" % cid}, 404)
            return self._json(got)
        return SimpleHTTPRequestHandler.do_GET(self)

    def log_message(self, fmt, *a):
        if "/api/" in (a[0] if a else ""):
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
