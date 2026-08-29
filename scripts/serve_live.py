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
import re
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
import metrics as MT   # noqa: E402
import orgconfig as OC  # noqa: E402
# The slice — which issues a forecast reads and what it is told about them.
# It lived here until the hosted calculator needed the same rules; a slice
# defined in scripts/ is one the Forge route cannot reach, and the alternative
# was writing it a second time in JavaScript. agent/tools/selection.py has the
# reasoning. Imported rather than reimplemented, which is the whole point.
from selection import team_slice, forecast_for  # noqa: E402,F401

ASKS_DIR = ROOT / "data" / "asks"

# An asked-for item count is bounded so a typo cannot start a simulation that
# runs for minutes. The bound is stated in the error rather than clamped
# silently, and the forecaster reports separately when a trial runs out of its
# own horizon.
MAX_ASK_ITEMS = 5000


# ------------------------------------------------------------- forecasting
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


def window_membership_jql(start_date, end_date):
    """Which issues are *in* a window, as a JQL predicate.

    The membership ADR 0011 settled: resolved inside the window, or not
    resolved at all. `forge/src/jira.js` builds the identical string and
    `tests/test_service.py` compares them, because the membership is the half
    of the query that decides every figure. How each transport reaches a board
    is its own business — the resolver goes through `/board/{id}/issue`, this
    goes through the board's own filter — but which issues count must not
    differ.

    `resolutiondate` for both halves, never `resolution IS EMPTY`: it is the
    field the page reads as `resolved`, so this asks Jira exactly the question
    the page will answer. `resolution` would be a second opinion about what
    done means, arriving by neither the status category nor the org config.

    The upper bound is the day *after* the end, because Jira compares a bare
    date against midnight — `<= end` silently drops everything finished during
    the window's last day, which is a throughput series quietly missing its
    most recent day rather than an error.
    """
    end = datetime.date.fromisoformat(str(end_date)[:10])
    after = (end + datetime.timedelta(days=1)).isoformat()
    return ('(resolutiondate >= "%s" AND resolutiondate < "%s")'
            ' OR resolutiondate IS EMPTY' % (start_date, after))


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
        self._filters = {}   # board id -> the saved filter behind it
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
            as_of = datetime.date.today().isoformat()
            for b in self.boards:
                info = self.j.get("/rest/agile/1.0/board/%s" % b)
                proj = (info.get("location") or {})
                # A board that runs no sprints answers 400 here, and that is a
                # fact about the board rather than a failure. Everything else
                # is a failure and is re-raised — catching them all alike is
                # how a 403 from a missing scope once presented as "this board
                # has no sprints", which the Forge resolver paid a deploy cycle
                # for. See `sprintsFor()` in forge/src/index.js.
                try:
                    data = self.j.get("/rest/agile/1.0/board/%s/sprint" % b,
                                      state="active,closed")
                except Exception as err:            # noqa: BLE001 — re-raised below
                    if getattr(getattr(err, "response", None), "status_code", None) != 400:
                        raise
                    out.extend(window_entry(b, info.get("name"), proj.get("projectKey"),
                                            proj.get("projectName"), days, as_of)
                               for days in WINDOW_DAYS)
                    continue
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

    def _board_filter(self, board_id):
        """The saved filter behind a board, which is how plain JQL is scoped to
        one. The agile board-issue endpoint does this scoping itself and is what
        the Forge resolver uses; here the issues come back through
        `jira_pull()`, which owns the field mapping and the `started`
        derivation, and re-implementing that mapping to use a different
        endpoint would be a second implementation of it."""
        if board_id not in self._filters:
            conf = self.j.get("/rest/agile/1.0/board/%s/configuration" % board_id)
            self._filters[board_id] = (conf.get("filter") or {}).get("id")
        return self._filters[board_id]

    def context(self, cid):
        if cid in self._cache:
            return self._cache[cid]
        ctx = next((c for c in self.contexts() if c["id"] == cid), None)
        if ctx is None:
            return None
        if ctx.get("kind") == "window":
            filter_id = self._board_filter(ctx["boardId"])
            if not filter_id:
                # Said rather than worked around. Without the filter this could
                # only widen the query to the whole site, and a window labelled
                # with one board's name holding another's issues is the class of
                # wrong answer that looks right.
                return {"context": dict(ctx), "orgConfig": self.cfg, "issues": [],
                        "burndown": [], "history": [], "releases": [], "dora": None,
                        "error": "Board %s does not expose the filter behind it, so the "
                                 "issues on it cannot be scoped to. Nothing was queried."
                                 % ctx["boardId"]}
            jql = "filter = %s AND (%s) ORDER BY created ASC" % (
                filter_id, window_membership_jql(ctx["startDate"], ctx["endDate"]))
        else:
            jql = "sprint = %s ORDER BY created ASC" % ctx["_sprintId"]
        args = argparse.Namespace(jira_board=None, jira_jql=jql,
                                  sp_field=None, sprint_field=None)
        issues, _ = self.F.jira_pull(args)
        meta = dict(ctx)
        # A window carries no working-day list and never has one derived for
        # it. Its dates bound the selection and are not a clock: nothing
        # committed to finishing by the end of a rolling window, so nothing can
        # be behind it. ADR 0011; `contextWorkingDays()` in src/app.js is the
        # other half of honouring this.
        meta["workingDays"] = ([] if ctx.get("kind") == "window"
                               else self.F.working_days(ctx["startDate"], ctx["endDate"]))
        meta["asOfDate"] = ctx["asOfDate"] or ctx["endDate"]
        out = {
            "context": meta, "orgConfig": self.cfg, "issues": issues,
            # A burndown needs a committed scope and an end to burn down to. A
            # window has neither, so the series is empty and the tile says why
            # rather than drawing a line against a boundary nobody agreed to.
            "burndown": ([] if ctx.get("kind") == "window"
                         else self.F.build_burndown(issues, meta)),
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


# ------------------------------------------------------- recipient config
# Who a board's brief goes to. On Forge this lives in the app's own key-value
# store; over loopback there is no such thing, so it lives in a file beside the
# dataset — git-ignored, because account ids identify people even though they
# are not contact details.
#
# The point of implementing it here at all is that the page must not learn which
# transport it has (ADR 0009). A route the Forge resolver answers and this one
# refuses would be a page that behaves differently depending on how it was
# reached, and the config tile would be untestable in the browser suite, which
# is the only place its editing actually runs.
#
# There is no permission model over loopback and `canEdit` is therefore true.
# That is not a gap being waved through: this server binds to 127.0.0.1 and
# serves the person who started it, so "is this user a project administrator"
# has no meaning here. The Forge side asks Jira. See ADR 0014.
RECIPIENTS_FILE = pathlib.Path("data/recipients.local.json")
#: The durable series, over loopback. App storage on Forge, a git-ignored file
#: here — same rule, same body shapes, different shelf. ADR 0015, ADR 0009.
SERIES_FILE = pathlib.Path("data/series.local.json")
#: The forecast log, over loopback. App storage on Forge, a git-ignored file
#: here — the same rule and the same body shapes. ADR 0017.
FORECAST_LOG_FILE = pathlib.Path("data/forecast-log.local.json")
#: The operational log, over loopback. App storage on Forge, a git-ignored file
#: here — the same rule and the same body shapes. ADR 0021.
AUDIT_FILE = pathlib.Path("data/audit.local.json")
#: Mirrors AUDIT_EVENTS and MAX_AUDIT in forge/src/audit.js.
AUDIT_EVENTS = ("recipients.saved", "recipients.cleared",
                "brief.sent", "brief.refused")
MAX_AUDIT = 1000
AUDIT_SHOWN = 20

# A config bigger than this is refused rather than stored. Stated because a cap
# that truncates silently reads as one that accepted everything.
MAX_CONFIG_BYTES = 64 * 1024

# The two shapes an account id has actually come in, loosely. Deliberately not
# tight: Atlassian has shipped at least three, and a pattern tuned to today's
# rejects tomorrow's in a tenant with a valid config.
_ACCOUNT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{6,126}[A-Za-z0-9]$")
_ISSUE_KEY = re.compile(r"^[A-Z][A-Z0-9]{1,9}-[1-9][0-9]{0,9}$")
_AUDIENCES = ("exec", "team")


def recipient_problems(config):
    """A mirror of `problemsIn` in forge/src/recipients.js, in Python.

    A second implementation of a rule is the thing this repository most
    reliably regrets, and this is one — so it is the *same* kind of mirror as
    `orgconfig.validate` and `validateOrgConfig`, held to the same standard:
    `tests/fixtures/recipient-configs.json` is one set of cases, and
    `tests/test_service.py` runs both implementations over all of it and fails
    if they ever disagree about whether a config is usable.

    The browser cannot call JavaScript in `forge/src/`, and this server cannot
    call Node without becoming a Python program that needs Node. The alternative
    was for loopback to refuse the route, which would leave the editing half of
    the config tile exercised by nothing — it only ever runs in a browser, and
    the browser suite runs against this server.

    Change one, change both. The wording of a sentence may differ; whether a
    config is usable may not.
    """
    if not isinstance(config, dict):
        return ["the recipient config is not an object, so no board is configured."]
    boards = config.get("boards")
    if not isinstance(boards, dict):
        return ["the recipient config has no boards object, so no board is configured."]
    if not boards:
        return ["no board has recipients configured, so there is nobody to send to."]

    out = []
    for board_id, entry in boards.items():
        at = "board %s" % board_id
        if not isinstance(entry, dict):
            out.append("%s: the entry is not an object, so nothing is configured for it." % at)
            continue

        anchor = entry.get("anchorIssue")
        if not isinstance(anchor, str) or not _ISSUE_KEY.match(anchor):
            out.append("%s: anchorIssue is %s, which is not an issue key like ABC-123."
                       % (at, json.dumps(anchor)))

        named = [a for a in _AUDIENCES if a in entry]
        if not named:
            out.append("%s: neither exec nor team is configured, so this board has an "
                       "entry that sends nothing." % at)

        for audience in named:
            where = "%s, %s" % (at, audience)
            who = entry.get(audience)
            if not isinstance(who, dict):
                out.append("%s: expected an object with users and/or groups." % where)
                continue
            users = who.get("users") if isinstance(who.get("users"), list) else []
            groups = who.get("groups") if isinstance(who.get("groups"), list) else []
            for u in users:
                if not isinstance(u, str):
                    out.append("%s: %s is not an account id." % (where, json.dumps(u)))
                elif "@" in u:
                    out.append("%s: %r is an email address. Jira's notify endpoint takes "
                               "account ids and groups and has no field for an address."
                               % (where, u))
                elif not _ACCOUNT_ID.match(u):
                    out.append("%s: %r is not an account id." % (where, u))
            for g in groups:
                if not isinstance(g, str) or not g.strip():
                    out.append("%s: %s is not a group name." % (where, json.dumps(g)))
            if not users and not groups:
                out.append("%s: no users and no groups, so this audience sends to nobody."
                           % where)
    return out


def read_recipients():
    try:
        return json.loads(RECIPIENTS_FILE.read_text())
    except (OSError, ValueError):
        # Missing and unreadable both end as "nothing configured". A caller that
        # needs to tell those apart does not exist, and inventing an error state
        # for a file nobody has created yet is noise on first run.
        return None


def write_recipients(config):
    RECIPIENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RECIPIENTS_FILE.write_text(json.dumps(config, indent=2) + "\n")


def read_series(board_id):
    """One board's recorded rows. Missing and unreadable both read as empty.

    Keyed by board inside one file rather than a file per board: the Forge side
    is one key per board because two boards closing sprints in the same hour
    would otherwise be two writers of one value, and this side is a single
    process serialising its own writes. The shape on the wire is what the two
    transports have to agree about, and it does.
    """
    try:
        all_boards = json.loads(SERIES_FILE.read_text())
    except (OSError, ValueError):
        return {"version": 1, "sprints": {}}
    got = (all_boards or {}).get(str(board_id))
    if not isinstance(got, dict) or got.get("version") != 1:
        return {"version": 1, "sprints": {}}
    return got


def write_series(board_id, series):
    try:
        all_boards = json.loads(SERIES_FILE.read_text())
    except (OSError, ValueError):
        all_boards = {}
    if not isinstance(all_boards, dict):
        all_boards = {}
    all_boards[str(board_id)] = series
    SERIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    SERIES_FILE.write_text(json.dumps(all_boards, indent=2) + "\n")


def read_forecast_log(board_id):
    """One board's forecast log. Missing and unreadable both read as empty —
    a caller that needed to tell those apart does not exist, and inventing an
    error state for a file nobody has created yet is noise on first run."""
    try:
        all_boards = json.loads(FORECAST_LOG_FILE.read_text())
    except (OSError, ValueError):
        return []
    got = (all_boards or {}).get(str(board_id))
    return got if isinstance(got, list) else []


def write_forecast_log(board_id, log):
    try:
        all_boards = json.loads(FORECAST_LOG_FILE.read_text())
    except (OSError, ValueError):
        all_boards = {}
    if not isinstance(all_boards, dict):
        all_boards = {}
    all_boards[str(board_id)] = log
    FORECAST_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    FORECAST_LOG_FILE.write_text(json.dumps(all_boards, indent=2) + "\n")


def read_audit():
    try:
        got = json.loads(AUDIT_FILE.read_text())
    except (OSError, ValueError):
        return {"entries": [], "droppedTotal": 0}
    if not isinstance(got, dict):
        return {"entries": [], "droppedTotal": 0}
    entries = got.get("entries")
    return {"entries": entries if isinstance(entries, list) else [],
            "droppedTotal": got.get("droppedTotal") or 0}


def append_audit(event, actor, board_id, detail):
    """Mirrors `appendAudit` in forge/src/audit.js, bound included.

    Best-effort and never raised into the caller: an audit write that failed
    must not report a save that succeeded as failed.
    """
    if event not in AUDIT_EVENTS:
        return
    try:
        held = read_audit()
        entry = {"at": datetime.datetime.now(datetime.timezone.utc)
                        .isoformat().replace("+00:00", "Z"),
                 "event": event,
                 "actor": actor or "schedule",
                 "boardId": None if board_id is None else str(board_id),
                 "detail": detail or {}}
        entries = held["entries"] + [entry]
        over = max(len(entries) - MAX_AUDIT, 0)
        AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUDIT_FILE.write_text(json.dumps(
            {"entries": entries[over:],
             "droppedTotal": held["droppedTotal"] + over}, indent=2) + "\n")
    except OSError:
        pass


def series_recordable(sprint_state, prior, seen=None):
    """Whether this observation may be written. Mirrors `recordable` in
    `forge/src/series.js`, and `tests/test_service.py` runs the two over one
    shared list of cases — the same arrangement `validate()` has.

    Two implementations of a *policy* is a smaller liability than two
    implementations of a figure, and there is no third option: the decision has
    to be taken next to the store, and there are two stores.
    """
    if sprint_state not in ("active", "closed"):
        return False
    # A row is a fact about the board (ADR 0019). A view that sees fewer of the
    # sprint's issues than the row on file must not replace it; one that sees
    # more corrects a row a narrow reader recorded.
    before = (prior or {}).get("issuesSeen")
    if isinstance(before, int) and isinstance(seen, int) and seen < before:
        return False
    if prior and prior.get("final") is True:
        if isinstance(before, int) and isinstance(seen, int) and seen > before:
            return True
        return False
    if sprint_state == "closed" and not prior:
        return False
    return True


def series_for(backend, cid):
    """The trend series for the board `cid` belongs to, and the recording of it.

    The same three steps as the Forge resolver, in the same order: ask the tool
    for the rows, decide what may be kept, merge. Nothing here counts anything —
    `merge_series` and `series_note` are in `metrics.py`, and this calls them
    exactly as the calculator does for the other transport.
    """
    contexts = backend.contexts()
    ctx = next((c for c in contexts if c.get("id") == cid), None)
    if ctx is None:
        return None
    board = ctx.get("boardId")
    mine = [c for c in contexts
            if str(c.get("boardId")) == str(board) and (c.get("kind") or "sprint") == "sprint"]
    if not mine:
        return {"available": False, "rows": [], "note": "", "problems": [],
                "why": "this board reports a window at a time rather than a sprint, so "
                       "it has no sprint-by-sprint trend. A window is not a clock and "
                       "it is not a sprint either."}

    issues = []
    for c in mine:
        got = backend.context(c["id"]) or {}
        issues.extend(got.get("issues") or [])
    cfg = backend.org_config()
    got = MT.history_series(mine, issues)
    rows, skipped = got["rows"], got["skipped"]

    stored = read_series(board)
    fingerprint = series_fingerprint(cfg)
    wrote = False
    for r in rows:
        prior = (stored.get("sprints") or {}).get(str(r["contextId"]))
        if not series_recordable(r.get("sprintState"), prior, r.get("issuesSeen")):
            continue
        entry = {"row": {k: v for k, v in r["row"].items() if k in MT.ROW_FIELDS},
                 "observedOn": r.get("asOf"),
                 "final": r.get("sprintState") == "closed",
                 "statuses": fingerprint,
                 "issuesSeen": r.get("issuesSeen")}
        if prior == entry:
            continue
        stored = {"version": 1,
                  "sprints": dict(stored.get("sprints") or {}, **{str(r["contextId"]): entry})}
        wrote = True
    if wrote:
        write_series(board, stored)

    # Recorded from every row this look could see; shown only up to the
    # selected context, because a sprint is not compared against its own future.
    merged = MT.merge_series(stored,
                             [{"sprintId": r["contextId"], "row": r["row"],
                               "asOf": r.get("asOf"),
                               "issuesSeen": r.get("issuesSeen")}
                              for r in MT.series_upto(rows, cid)],
                             fingerprint)
    # A bundle carries every sprint it was built with, so what the board "has"
    # and what this window kept are the same number unless the config narrows
    # it. Passed anyway, so both transports produce the sentence the same way.
    window = (cfg or {}).get("trendSprints")
    return {"available": True, "rows": merged["rows"],
            "offered": len(rows) + len(skipped), "sprints": len(rows),
            "skipped": skipped,
            "outsideWindow": merged.get("outsideWindow") or [],
            "note": " ".join(x for x in (
                MT.series_note(merged),
                MT.skipped_note(skipped),
                MT.window_note(len(mine), len(rows) + len(skipped), window)) if x),
            "problems": []}


def series_fingerprint(cfg):
    """Mirrors `statusFingerprint` in `forge/src/series.js`. Order- and
    case-insensitive, because neither changes what the words mean and both
    change a naive join — a config re-saved in a different order would
    otherwise read as a recategorisation."""
    st = (cfg or {}).get("statuses") or {}

    def part(v):
        return ",".join(sorted(x.strip().lower() for x in (v or [])
                               if isinstance(x, str) and x.strip()))
    return "done=%s|prog=%s" % (part(st.get("done")), part(st.get("inProgress")))


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

            # The forecast log — roadmap item 4c, ADR 0017. Same body shape as
            # the Forge route and the same one tool function behind it; the
            # only difference is the shelf the log sits on. A what-if carries no
            # claims, so nothing is written for one.
            claims = got.get("claims") or []
            board = None
            for c in self.backend.contexts():
                if c.get("id") == cid:
                    board = c.get("boardId")
                    break
            if board is not None:
                log = read_forecast_log(board)
                today = (got.get("asked") or {}).get("as_of")
                cal = FC.update_log(log, claims,
                                    self.backend.context(cid).get("issues") or []
                                    if self.backend.context(cid) else [],
                                    today, seen=got.get("issuesSeen"))
                # Written only when it changed. This route runs on every panel
                # load, and rewriting an unchanged log is a file touched for
                # nothing.
                if cal["added"] or cal["dropped"] or cal["log"] != log:
                    write_forecast_log(board, cal["log"])
                got = dict(got, calibration=cal)
            return self._json(got)
        if path in ("api/sequence", "dist/api/sequence"):
            cid = urllib.parse.parse_qs(u.query).get("id", [""])[0]
            got = self.backend.sequence(cid)
            if got is None:
                return self._json({"error": "unknown context %r" % cid}, 404)
            return self._json(got)
        if path in ("api/users", "dist/api/users"):
            # The same body shape the Forge resolver returns, so the picker does
            # not learn which transport it has (ADR 0009). Over loopback there
            # is no directory to search — the dataset holds assignee display
            # names and no account ids at all — so this answers honestly rather
            # than inventing ids that would be stored and never work.
            return self._json({
                "available": False,
                "people": [],
                "note": "Looking a name up needs the site's user directory, and "
                        "there is none over a local connection. Account ids can "
                        "be pasted under Account IDs below; on Jira the name "
                        "search works.",
            })
        if path in ("api/names", "dist/api/names"):
            # Names for ids already stored, and the same answer as api/users for
            # the same reason: resolving an id to a name needs the site's user
            # directory, and a local connection has none. Returning an empty
            # people list with `available` true would read as "none of these ids
            # exists", which is a much stronger claim than "there is nowhere to
            # ask". ADR 0009 — the body shape is the contract, not the answer.
            return self._json({
                "available": False,
                "people": [],
                "note": "Showing a stored account id as a name needs the site's "
                        "user directory, and there is none over a local "
                        "connection. The ids under Account IDs are what will be "
                        "sent to; on Jira they are shown as names.",
            })
        if path in ("api/history", "dist/api/history"):
            cid = urllib.parse.parse_qs(u.query).get("id", [""])[0]
            got = series_for(self.backend, cid)
            if got is None:
                return self._json({"error": "unknown context %r" % cid}, 404)
            return self._json(got)
        if path in ("api/recipients", "dist/api/recipients"):
            config = read_recipients()
            held = read_audit()
            return self._json({
                "available": True,
                "config": config if config is not None else {"boards": {}},
                "problems": recipient_problems(config) if config is not None else [],
                "canEdit": True,
                # Administrators only on Forge; over loopback there is no
                # permission model at all and `canEdit` is always true, so the
                # log is always shown. The body shape is the contract either
                # way. ADR 0009, ADR 0021.
                "audit": list(reversed(held["entries"][-AUDIT_SHOWN:])),
                "auditTotal": len(held["entries"]),
                "auditDropped": held["droppedTotal"],
            })
        if path in ("api/context", "dist/api/context"):
            cid = urllib.parse.parse_qs(u.query).get("id", [""])[0]
            got = self.backend.context(cid)
            if got is None:
                return self._json({"error": "unknown context %r" % cid}, 404)
            return self._json(got)
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        """The one route that changes something.

        A POST rather than a GET with parameters, because a GET that mutates is
        a GET a browser, a proxy or a prefetch will make on its own. The bridge
        transport has no verb — `invoke()` names a route — so this asymmetry
        exists only on this side, and `src/app.js` does not see it.
        """
        u = urllib.parse.urlparse(self.path)
        path = u.path.lstrip("/")
        if path not in ("api/recipients", "dist/api/recipients"):
            return self._json({"error": "no such route"}, 404)

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._json({"error": "bad Content-Length"}, 400)
        if length > MAX_CONFIG_BYTES:
            return self._json({"available": True, "saved": False, "canEdit": True,
                               "problems": ["the configuration is larger than %d bytes, "
                                            "so nothing was saved." % MAX_CONFIG_BYTES]}, 413)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._json({"available": True, "saved": False, "canEdit": True,
                               "problems": ["that was not JSON, so nothing was saved."]}, 400)

        config = (payload or {}).get("config")
        problems = recipient_problems(config)
        if problems:
            # Refused whole. Storing a config with one broken board would leave
            # the file holding something no run can use, which is worse than
            # whatever it held before.
            return self._json({"available": True, "saved": False,
                               "canEdit": True, "problems": problems}, 400)

        before = read_recipients() or {}
        write_recipients(config)

        # One entry per board whose entry actually moved, mirroring the resolver:
        # a save writes the whole configuration, so recording the act would put
        # a row against boards nobody touched. ADR 0021.
        def counts(entry):
            e = entry or {}
            return {
                "exec": len((e.get("exec") or {}).get("users") or [])
                        + len((e.get("exec") or {}).get("groups") or []),
                "team": len((e.get("team") or {}).get("users") or [])
                        + len((e.get("team") or {}).get("groups") or []),
            }

        boards = set((before.get("boards") or {})) | set((config.get("boards") or {}))
        for bid in sorted(boards):
            was = (before.get("boards") or {}).get(bid)
            now = (config.get("boards") or {}).get(bid)
            if was == now:
                continue
            # Over loopback there is no user to attribute this to, and saying so
            # is better than inventing one. On Forge it is context.accountId.
            append_audit("recipients.saved" if now else "recipients.cleared",
                         "loopback", bid,
                         dict(counts(now), anchorSet=bool((now or {}).get("anchorIssue")))
                         if now else {})
        return self._json({"available": True, "saved": True, "config": config,
                           "problems": [], "canEdit": True})

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
