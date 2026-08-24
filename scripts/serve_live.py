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
import datetime
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
import intake as IN    # noqa: E402
import orgconfig as OC  # noqa: E402

ASKS_DIR = ROOT / "data" / "asks"

# An asked-for item count is bounded so a typo cannot start a simulation that
# runs for minutes. The bound is stated in the error rather than clamped
# silently, and the forecaster reports separately when a trial runs out of its
# own horizon.
MAX_ASK_ITEMS = 5000


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


def forecast_for(contexts, issues, byContext, cid, items=None, target=None, org_cfg=None):
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
    actual_remaining = len([i for i in issues
                            if i.get("contextId") in remaining_ids
                            and (i.get("statusCategory") or "") != "Done"])
    # An asked-for item count or date replaces the sprint's own, so the same
    # history can answer "what if it were 30 items" or "what about by then".
    # The defaults are still reported, so the tile can show what was swapped.
    remaining = actual_remaining if items is None else items
    as_of = ctx.get("asOfDate") or ctx.get("endDate")
    meta = {"sprintName": ctx.get("sprintName"), "startDate": ctx.get("startDate"),
            "endDate": ctx.get("endDate"), "asOfDate": as_of,
            "workingDays": ctx.get("workingDays")}
    # The bundle's own config, carried onto the slice. Building this dict
    # without it would forecast the customer's board against a calendar they do
    # not keep — a different answer, arrived at silently, from the same data.
    ds = {"issues": team_issues, "meta": meta,
          "orgConfig": org_cfg or {},
          "releases": (byContext.get(cid) or {}).get("releases", [])}
    eff_target = target or ctx.get("endDate")
    out = FC.build(ds, as_of=as_of, remaining=remaining, target=eff_target)
    out["asked"] = {
        "items": items, "date": target,
        "default_items": actual_remaining, "default_date": ctx.get("endDate"),
        "as_of": as_of,
    }
    resolved = sorted(x for x in (FC._d(i["resolved"]) for i in team_issues
                                  if i.get("resolved")) if x)
    out["sampled_from"] = {
        "slice": slice_label,
        "contexts": len(members),
        "first_resolved": resolved[0].isoformat() if resolved else None,
        "last_resolved": resolved[-1].isoformat() if resolved else None,
    }
    return out


def load_asks(board):
    """Every recorded ask for one board. Read per request rather than cached:
    an ask is a file somebody edits, and a stale sequence is worse than a slow
    one."""
    out = []
    if not ASKS_DIR.is_dir():
        return out
    for f in sorted(ASKS_DIR.glob("*.json")):
        try:
            a = json.loads(f.read_text())
        except ValueError:
            continue
        if str(a.get("team") or "") == str(board):
            out.append(a)
    return out


def sequence_for(data, cid):
    """What each ordering of this board's outstanding asks costs the others.

    Same tool the terminal runs for `make intake-sequence`, same output. It is
    not a priority score and never becomes one: the delivery consequence of an
    ordering is computable, the relative worth of the asks is not.
    """
    contexts = data.get("contexts", [])
    ctx = next((c for c in contexts if c["id"] == cid), None)
    if ctx is None and cid.startswith("roll:"):
        proj, _, board = cid[len("roll:"):].partition("|")
        ctx = next((c for c in contexts
                    if str(c.get("projectKey") or "") == proj
                    and str(c.get("boardId") or "") == board), None)
    if ctx is None:
        return None
    board = ctx.get("boardId")
    asks = load_asks(board)
    if not asks:
        return {"available": False, "board": str(board),
                "boardName": ctx.get("boardName"),
                "sentence": "No asks are recorded for this board. Sequencing compares the "
                            "outstanding asks against each other, so it needs at least two; "
                            "add them under data/asks/ and they appear here."}
    res = IN.sequence(data, [dict(a) for a in asks], board=board,
                      as_of=ctx.get("asOfDate") or ctx.get("endDate"))
    res.setdefault("board", str(board))
    res.setdefault("boardName", ctx.get("boardName"))
    res["asks_considered"] = len(asks)
    return res


# ------------------------------------------------------------ flow boards
#
# A board that runs no sprints gets a **window** instead of one: a rolling
# stretch of calendar days that bounds the selection and is deliberately not a
# clock. ADR 0011 has the reasoning; `docs/kanban-boards.md` has the plan.
#
# These three constants and the builder below are mirrored in
# `forge/src/jira.js`, and `tests/test_service.py` compares the two producers
# key by key and value by value rather than only checking that the field sets
# match. Two producers agreeing about which keys exist and disagreeing about
# where a 30-day window starts is the harder bug, and a shape check cannot see
# it — which is the same hole ADR 0009's parity test had for `workingDays`.

WINDOW_DAYS = [14, 30, 90]
DEFAULT_WINDOW_DAYS = 30


def window_token(days):
    """The third part of a flow board's context id. Prefixed rather than bare,
    so a sprint id and a window length can never be read as each other."""
    return "win:%dd" % days


def window_entry(board_id, board_name, project_key, project_name, days, as_of):
    """One selectable window, in the shape the sprint entry above uses.

    Field for field a sprint context minus `_sprintId`, so the picker and every
    renderer read one shape and not two. Three of those fields are named for
    sprints and hold a window's answer — `sprintName`, `sprintState` and
    `sprintGoal` — which is deliberate: they are the contract both transports
    and every committed fixture already agree about, and renaming them to say
    "period" would be a second product for the sake of a word.

    `startDate` and `endDate` are real and bound the selection. They must never
    become a clock: no working-day list is built here or sent, and the page owes
    a window an explicit refusal rather than the derivation it performs for a
    sprint.

    `as_of` is passed rather than read from the clock, because an entry that
    moves with the wall clock cannot be compared against another producer's.
    """
    end = datetime.date.fromisoformat(str(as_of)[:10])
    # Inclusive of both ends, so a 30-day window covers 30 calendar days
    # rather than 31. Calendar days, like every other elapsed figure here.
    start = end - datetime.timedelta(days=days - 1)
    return {
        "id": "%s/%s/%s" % (project_key or "?", board_id, window_token(days)),
        "kind": "window",
        "source": "jira",
        "projectKey": project_key,
        "projectName": project_name,
        "boardId": str(board_id),
        "boardName": board_name,
        "team": board_name,
        "sprintName": "Last %d days" % days,
        # Not a Jira sprint state, and not null: the picker's state chip
        # switches on this, and the rollup already occupies the same slot.
        "sprintState": "window",
        "sprintGoal": "",
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "asOfDate": end.isoformat(),
        "issueCount": 0,
    }


# --------------------------------------------------------------- backends
class BundleBackend:
    """Reads an existing bundle file. Used for demos, tests, and for working
    offline on a plane with last week's pull."""

    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.data = json.loads(self.path.read_text())
        self._fc = {}   # forecasts, per context id, for the process lifetime
        self._seq = {}  # ask sequencing, per context id
        self.label = "bundle file %s" % self.path.name
        self.source = (self.data.get("meta") or {}).get("source", "bundle")

    def org_config(self):
        return OC.from_dataset(self.data)

    def contexts(self):
        # `kind` is defaulted rather than inferred. Bundles written before
        # flow boards existed carry no such field, and every context in one is
        # a sprint — so an absent value has exactly one honest reading. This is
        # not the thing ADR 0011 forbids: what is banned is recovering the kind
        # by re-reading the *id*, because that makes the discriminator a second
        # implementation of the same fact. Defaulting a field the producer
        # predates is what the page already does for `statusCategory`.
        #
        # It is defaulted here, in the backend, so that both transports put the
        # field on the wire. A loopback answer that omitted it while the Forge
        # resolver sent it is precisely the divergence ADR 0009 exists to stop.
        return [dict({"kind": "sprint"},
                     **{k: v for k, v in c.items() if k != "workingDays"})
                for c in self.data.get("contexts", [])]

    def context(self, cid):
        by = (self.data.get("byContext") or {}).get(cid, {})
        ctx = next((c for c in self.data["contexts"] if c["id"] == cid), None)
        if ctx is None:
            return None
        return {
            "context": ctx,
            "orgConfig": OC.from_dataset(self.data),
            "issues": [i for i in self.data["issues"] if i.get("contextId") == cid],
            "burndown": by.get("burndown", []), "history": by.get("history", []),
            "releases": by.get("releases", []), "dora": by.get("dora"),
        }

    def sequence(self, cid):
        if cid not in self._seq:
            self._seq[cid] = sequence_for(self.data, cid)
        return self._seq[cid]

    def forecast(self, cid, items=None, target=None):
        key = (cid, items, target)
        if key not in self._fc:
            self._fc[key] = forecast_for(self.data.get("contexts", []),
                                         self.data.get("issues", []),
                                         self.data.get("byContext") or {},
                                         cid, items, target,
                                         org_cfg=OC.from_dataset(self.data))
        return self._fc[key]


class JiraBackend:
    """Queries Jira on demand. Sprint lists are cheap; issues are fetched only
    when a sprint is actually selected, and cached for the process lifetime."""

    def __init__(self, board_ids, sprints, cfg=None, site=None, auth="auto"):
        import fetch_delivery_data as F
        self.F = F
        self.cfg = cfg or OC.DEFAULTS
        # The server and the fetcher categorise statuses the same way because
        # they are the same code, configured once, here.
        F.configure(self.cfg)
        self.j = F.connect_jira(argparse.Namespace(jira_site=site, auth=auth))
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
                        "kind": "sprint",
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
            "context": meta, "orgConfig": self.cfg, "issues": issues,
            "burndown": self.F.build_burndown(issues, meta),
            "history": [], "releases": [], "dora": None,
        }
        ctx["issueCount"] = len(issues)
        self._cache[cid] = out
        return out

    def org_config(self):
        return self.cfg

    def sequence(self, cid):
        """Sequencing sizes asks against the board's completed epics and its
        interruption history, which a sprint-at-a-time Jira pull does not carry.
        Rather than assemble a partial dataset and return a number built on it,
        say what is missing."""
        return {"available": False,
                "sentence": "Ask sequencing needs a bundled dataset — it sizes asks against "
                            "the board's completed epics and its measured interruption rate, "
                            "which this live Jira connection does not pull. Run the fetcher to "
                            "a bundle and serve that, or use `make intake-sequence`."}

    def forecast(self, cid, items=None, target=None):
        """Unlike the bundle, this has to fetch. A forecast needs the team's
        whole history, so every sprint on the team is pulled — slow the first
        time, cached after, and the reason the endpoint can take a few seconds
        against live Jira."""
        if not hasattr(self, "_fc"):
            self._fc = {}
        key = (cid, items, target)
        if key in self._fc:
            return self._fc[key]
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
        self._fc[key] = forecast_for(all_ctx, issues, {}, cid, items, target,
                                     org_cfg=self.cfg)
        return self._fc[key]


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
            return self._json({"source": b.source, "label": b.label,
                               "orgConfig": b.org_config(), "contexts": b.contexts()})
        if path in ("api/forecast", "dist/api/forecast"):
            qs = urllib.parse.parse_qs(u.query)
            cid = qs.get("id", [""])[0]
            # Reject bad input rather than quietly forecasting something else.
            # A silently ignored override is worse than an error: the number
            # comes back looking like the answer to the question asked.
            items = qs.get("items", [""])[0].strip()
            if items:
                if not items.isdigit() or not (1 <= int(items) <= MAX_ASK_ITEMS):
                    return self._json({"error": "items must be a whole number between 1 and %d"
                                                % MAX_ASK_ITEMS}, 400)
                items = int(items)
            else:
                items = None
            target = qs.get("date", [""])[0].strip() or None
            if target:
                try:
                    datetime.date.fromisoformat(target)
                except ValueError:
                    return self._json({"error": "date must be YYYY-MM-DD"}, 400)
            got = self.backend.forecast(cid, items, target)
            if got is None:
                return self._json({"error": "unknown context %r" % cid}, 404)
            return self._json(got)
        if path in ("api/sequence", "dist/api/sequence"):
            cid = urllib.parse.parse_qs(u.query).get("id", [""])[0]
            got = self.backend.sequence(cid)
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
    ap.add_argument("--org-config", default=str(ROOT / "config" / "organisation.json"),
                    help="organisation config for live Jira mode; a bundle carries its own")
    ap.add_argument("--auth", choices=("auto", "oauth", "token"), default="auto")
    ap.add_argument("--jira-site", help="which granted site to serve, when a grant covers several")
    a = ap.parse_args()

    if a.bundle:
        # A bundle carries the config it was built with. Overriding it here
        # would report the file under rules it was not produced under.
        Handler.backend = BundleBackend(a.bundle)
    elif a.jira_boards:
        cfg = OC.load(a.org_config) if os.path.exists(a.org_config) else OC.DEFAULTS
        Handler.backend = JiraBackend(a.jira_boards, a.sprints, cfg=cfg,
                                      site=a.jira_site, auth=a.auth)
    else:
        ap.error("give --bundle or --jira-boards")

    os.chdir(ROOT)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print("Serving %s" % Handler.backend.label)
    print("  calendar: %s" % OC.summary(Handler.backend.org_config()))
    print("  http://127.0.0.1:%d/dist/delivery-value-dashboard.html" % a.port)
    print("  %d contexts offered" % len(Handler.backend.contexts()))
    print("Ctrl-C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
