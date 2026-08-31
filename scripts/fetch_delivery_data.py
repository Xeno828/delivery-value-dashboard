#!/usr/bin/env python3
"""
fetch_delivery_data.py
======================
Pulls delivery data from Jira and/or Asana and writes the JSON file that
delivery-value-dashboard.html reads.

Why this script exists
----------------------
A browser page cannot call Jira or Asana directly. Both APIs reject
cross-origin browser requests, and any credential embedded in an HTML file is
readable by anyone that file is forwarded to. This script keeps the token on
your machine and produces a plain, inspectable JSON file. Nothing about the
dashboard depends on this script — it is one of several ways to produce the
same file.

Install
-------
    pip install requests

Jira — two ways in
------------------
**OAuth (a customer's site).** A consented, scoped, revocable grant. Register
the app once, then:

    python fetch_delivery_data.py --jira-board 42        # uses the stored grant

See scripts/jira_auth.py for the one-time setup. If the grant covers more than
one site, name it with --jira-site; the script refuses to guess.

**API token (your own board).** No app registration, unchanged, still fine:

    export JIRA_URL=https://your-domain.atlassian.net
    export JIRA_EMAIL=you@company.com
    export JIRA_TOKEN=...        # id.atlassian.com > Security > API tokens

    python fetch_delivery_data.py --jira-board 42 --out dashboard-data.json
    python fetch_delivery_data.py --jira-jql 'project = BLC AND sprint in openSprints()'

`--auth auto` (the default) prefers a stored grant and falls back to the token.
Whichever it used is printed, because the two see different sets of issues.

Organisation config
-------------------
Which statuses mean done, which days are worked, the holiday calendar and the
sprint length come from config/organisation.json (--org-config to point
elsewhere). The resolved config is written into the output as `orgConfig` so
the dashboard and the agent's tools read the same one — see
docs/organisation-config.md.

Asana
-----
    export ASANA_TOKEN=...       # app.asana.com > My Settings > Apps > Developer

    python fetch_delivery_data.py --asana-project 1201234567890

Both at once (results are merged into one issue list):
    python fetch_delivery_data.py --jira-board 42 --asana-project 1201234567890

Custom fields
-------------
Story points and sprint live in customfield_* IDs that differ per Jira site.
The script discovers them by name; override with --sp-field / --sprint-field
if your site names them unusually.
"""

import argparse
import json
import os
import pathlib
import sys
from collections import defaultdict
from datetime import date, datetime

# Imported, but not required to import *this*. `requests` is needed to talk to a
# tracker and for nothing else, and a module that calls sys.exit() at import
# time is a module nothing can import to test — which is exactly what happened:
# `tests/test_agent.py` pulled this in to check one function and broke the
# promise that `make test-agent` needs nothing but Python 3. The message it used
# to print at import is printed by `need_requests()` at the point of use, which
# is where somebody can act on it.
try:
    import requests
except ImportError:                                     # pragma: no cover
    requests = None


def need_requests():
    """The dependency, or the sentence that says how to get it."""
    if requests is None:
        sys.exit("Install the dependency first:  pip install requests")
    return requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent" / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))

import orgconfig as OC  # noqa: E402
# One derivation of a sprint's trend row, and it lives in a tool rather than
# here: a Forge tenant has no Python, so its rows come from the calculator,
# which ships agent/tools/ and nothing else. ADR 0015.
from metrics import history_row  # noqa: E402

TIMEOUT = 45

# The organisation config for this run, resolved once in main(). Module state is
# safe here in a way it would not be in agent/tools: this is a single-shot CLI
# that pulls one site and exits, whereas the tools are imported by a server that
# handles several datasets in one process and must be handed their config.
CFG = OC.DEFAULTS
STATUSES = OC.Statuses(CFG)


def configure(cfg):
    global CFG, STATUSES
    CFG = cfg
    STATUSES = OC.Statuses(cfg)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def d(value):
    """Any Jira/Asana timestamp -> YYYY-MM-DD, or None."""
    if not value:
        return None
    return str(value)[:10]


def working_days(start, end):
    """Working days between two ISO dates, inclusive, per the organisation
    config — including its holiday calendar. Written into the dataset as
    `meta.workingDays` so every consumer reads the same list rather than
    recomputing it against a calendar of its own."""
    if not start or not end:
        return []
    return OC.working_days_iso(start, end, CFG)


def report_unmatched():
    """Name every status the config did not cover.

    This is the quiet failure mode of the whole feature. A site adds an
    "Awaiting sign-off" column, no rule mentions it, those issues read as To Do,
    the burndown flattens, and the dashboard is confidently wrong with nothing
    on screen to say so. Printing the names costs one line and turns it into a
    two-minute config edit.
    """
    names = STATUSES.unmatched
    if not names:
        return
    print("  note: %d status%s matched no rule in the config and were inferred: %s"
          % (len(names), "" if len(names) == 1 else "es", ", ".join(repr(n) for n in names)),
          file=sys.stderr)
    print("        add each to statuses.done or statuses.inProgress in your "
          "organisation config, or confirm it belongs in To Do.", file=sys.stderr)


def status_category(name, category=None):
    """Which of To Do / In Progress / Done a tracker status means.

    Configured per organisation, because "done" is a local word: a site with a
    "Signed off" column and no "Done" column had every sprint reading 0%
    complete. Names the config has never seen are recorded and printed at the
    end of the run rather than quietly becoming To Do.
    """
    return STATUSES.category(name, category)


# --------------------------------------------------------------------------
# Jira
# --------------------------------------------------------------------------
class _TokenTransport:
    """The original path: a personal API token over HTTP basic auth.

    Still here, still supported. It needs no app registration and is the right
    thing for pulling your own board — but the token carries whoever generated
    it and cannot be scoped or revoked per-integration, which is why a
    customer's site is connected with OAuth instead.
    """

    def __init__(self, url, email, token):
        self.url = url.rstrip("/")
        self.s = need_requests().Session()
        self.s.auth = (email, token)
        self.s.headers.update({"Accept": "application/json"})

    def get(self, path, **params):
        r = self.s.get(self.url + path, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()

    def post(self, path, json=None):
        return self.s.post(self.url + path, json=json, timeout=TIMEOUT)


class Jira:
    """The Jira surface this script needs, over either transport.

    `url` is the *browsable* site — it goes into issue deep links and
    `meta.baseUrl`. Under OAuth the requests go to api.atlassian.com instead,
    which is not a URL a human can click, so the two are kept apart.
    """

    def __init__(self, transport, browse_url):
        self.t = transport
        self.url = (browse_url or "").rstrip("/")

    def get(self, path, **params):
        return self.t.get(path, **params)

    def whoami(self):
        """Who this connection is authenticated as — `(identity, None)`, or
        `(None, why)` for nobody.

        **A Jira site answers `/rest/api/3/field` anonymously.** Verified
        against a live site on 2026-08-30: no credential at all returns 200 and
        twenty-eight system fields, with every custom field missing. So a wrong
        credential does not fail where this script first touches Jira.
        `find_fields` finds no story-point field, prints *"! No story-point
        field found — points will be 0"*, and the run carries on: every issue at
        zero points, a burndown that flattens, and one warning line standing
        between that and a reader.

        That is the plausible-wrong-number class — not an error, a smaller
        number that looks exactly like the right one — and it is the same lesson
        `forge/src/jira.js` records about discovering the story-point field
        rather than hardcoding an id. One identity check before any data call
        turns it into a sentence.

        `/rest/api/3/myself` is the endpoint that names you, and an anonymous
        caller gets no `accountId` from it.
        """
        try:
            me = self.get("/rest/api/3/myself")
        except Exception as exc:                        # any failure here is "nobody"
            return None, str(exc)
        if not (me or {}).get("accountId"):
            return None, "the site answered but named nobody — an anonymous read"
        return me, None

    def find_fields(self, sp_hint=None, sprint_hint=None):
        """Locate the story-point and sprint custom fields by display name."""
        fields = self.get("/rest/api/3/field")
        sp = sp_hint
        sprint = sprint_hint
        for f in fields:
            nm = (f.get("name") or "").lower()
            if not sp and nm in ("story points", "story point estimate", "points"):
                sp = f["id"]
            if not sprint and nm == "sprint":
                sprint = f["id"]
        return sp, sprint

    #: The module keys the Forge app declares its own fields under. Mirrors
    #: BUSINESS_VALUE_KEY and VALUE_BASIS_KEY in `forge/src/jira.js`; ADR 0025
    #: and ADR 0027. Change one, change both.
    BUSINESS_VALUE_KEY = "business-value"
    VALUE_BASIS_KEY = "value-basis"
    CANDIDATE_KEY = "candidate"

    def find_ask_field(self, ask_field, fields=None):
        """The field that says an issue is an ask — ours, or the site's own.

        `"app"` is this app's declared **Candidate** field, matched by module
        key. Anything else names a field the site already has, matched by id
        first and then by display name: a checkbox called "Ready for
        sequencing", a single select, a discovery flag. Matching a display name
        is a guess when the app picks the field and an instruction when the
        organisation names one, and this is the second case. ADR 0028.
        """
        if fields is None:
            fields = self.get("/rest/api/3/field")
        named = str(ask_field or "app").strip()
        if not named or named.lower() == "app":
            for f in fields or []:
                if self.CANDIDATE_KEY in str(f.get("key") or f.get("id") or ""):
                    return f.get("id")
            return None
        for f in fields or []:
            if str(f.get("id") or "") == named:
                return f.get("id")
        want = named.lower()
        for f in fields or []:
            if str(f.get("name") or "").strip().lower() == want:
                return f.get("id")
        return None

    def find_app_fields(self, fields=None):
        """This app's own Business Value and Value Basis fields on this site.

        **Matched on the field's key, not its display name.** A Forge custom
        field's key carries the module key that declared it, so it identifies
        *this app's* field rather than any field a site happens to have called
        "Business Value" — and a site with one of its own is exactly the case
        where matching a display name reads somebody else's numbers and reports
        them as value. `find_fields` above matches story points by name because
        that is a field this app did not create and cannot identify any other
        way; the difference is worth keeping.

        `(None, None)` when the Forge app is not installed on this site, which
        is the ordinary case for the OAuth route — pulling your own board needs
        no app registration. That is reported rather than treated as "nobody has
        recorded a value", because the two have entirely different fixes.
        """
        if fields is None:
            fields = self.get("/rest/api/3/field")
        value = basis = None
        for f in fields or []:
            key = str(f.get("key") or f.get("id") or "")
            if value is None and self.BUSINESS_VALUE_KEY in key:
                value = f.get("id")
            if basis is None and self.VALUE_BASIS_KEY in key:
                basis = f.get("id")
        return value, basis

    def board_epics(self, board_id, fields, cap=200):
        """The board's epics as issues — ADR 0026.

        **Epics are not on a scrum board.** *"Epic issues do not belong to the
        scrum boards"* is Jira's own description of the design, so a
        `sprint = N` search never returns one, and the epic carrying the value
        is exactly the issue that never arrives. Declaring the field was
        necessary and not sufficient on Forge for this reason, and the same is
        true here.

        Capped, and what the cap dropped is returned rather than swallowed: a
        board whose epics were truncated would report less value than it
        delivered, with nothing saying so.
        """
        listed, start = [], 0
        for _ in range(20):
            try:
                page = self.get("/rest/agile/1.0/board/%s/epic" % board_id,
                                startAt=start, maxResults=50)
            except Exception:
                # A board with no epic support answers 4xx here. That is not an
                # error, it is a board without epics, and it has no value to
                # report.
                break
            vals = page.get("values") or []
            listed.extend(vals)
            start += len(vals)
            if not vals or page.get("isLast") or len(listed) >= cap:
                break
        out = []
        for e in listed[:cap]:
            try:
                out.append(self.get("/rest/api/3/issue/%s" % e["key"], fields=",".join(fields)))
            except Exception:
                pass          # one unreadable epic is not a reason to report no value
        return out, max(len(listed) - cap, 0)

    def active_sprint(self, board_id):
        data = self.get("/rest/agile/1.0/board/%s/sprint" % board_id, state="active")
        vals = data.get("values") or []
        if not vals:
            data = self.get("/rest/agile/1.0/board/%s/sprint" % board_id,
                            state="closed", maxResults=1)
            vals = data.get("values") or []
        return vals[0] if vals else None

    #: A page count no real board reaches, so a server that kept handing back a
    #: token stops this rather than looping for ever. Community reports of
    #: `nextPageToken` arriving when the page was in fact the last are the
    #: reason this exists at all — and it raises rather than returning what it
    #: has, because a short pull is a dashboard that is wrong and looks right.
    MAX_SEARCH_PAGES = 200

    def search(self, jql, fields, expand="changelog"):
        """Every issue matching `jql`, paged.

        `/rest/api/3/search/jql`, because `/rest/api/3/search` **has been
        removed** — it answers *"The requested API has been removed. Please
        migrate to the /rest/api/3/search/jql API."* This was not a URL swap:

        **The new endpoint pages by token, not by index.** `startAt` and `total`
        are gone. The old loop stopped when `startAt >= total`, and against the
        new shape `total` is absent, so `body.get("total", 0)` returned 0, the
        condition was true on the first pass, and it would have stopped after
        one page — one hundred issues reported as the whole board. That is the
        failure this repository fears most, so the stop condition is now the
        absence of a token and nothing else.

        **There is no total to check the result against.** The old code could
        have compared what it collected against what Jira said existed; nothing
        can now. So the only guard left is the page cap above, and it raises.
        """
        out, token = [], None
        for page_no in range(self.MAX_SEARCH_PAGES):
            body = {"jql": jql, "maxResults": 100, "fields": fields,
                    "expand": expand}
            if token:
                body["nextPageToken"] = token
            page = self.t.post("/rest/api/3/search/jql", json=body)
            page.raise_for_status()
            got = page.json()
            issues = got.get("issues") or []
            out.extend(issues)
            token = got.get("nextPageToken")
            # Both conditions, because `isLast` is documented as not returned by
            # every operation and a missing token is the reliable end marker.
            if not token or got.get("isLast") is True or not issues:
                return out
        raise RuntimeError(
            "search returned more than %d pages for %r. %d issues were read and "
            "none are reported: a board pulled short is a dashboard that is "
            "wrong and looks right." % (self.MAX_SEARCH_PAGES, jql, len(out)))


def _verified(j, how):
    """Prove the connection is somebody, before a single figure is pulled.

    The check exists because the first data call cannot be trusted to fail. See
    `Jira.whoami`. It is also where the run says *who* it is, which the note in
    `connect_jira` about silent fallback already wanted: knowing a personal
    token was used matters less than knowing whose.
    """
    me, why = j.whoami()
    if not me:
        sys.exit(
            "Jira refused the credential — %s.\n"
            "  %s\n"
            "Nothing was pulled.\n"
            "\n"
            "This is checked before any data call on purpose. A Jira site answers\n"
            "/rest/api/3/field to an anonymous caller, so an unauthenticated run\n"
            "would otherwise find no story-point field, warn once, and go on to\n"
            "produce a dashboard with every issue at zero points that looks\n"
            "complete." % (how, why))
    print("Jira: %s, as %s" % (how, me.get("displayName") or me.get("accountId")),
          file=sys.stderr)
    return j


def connect_jira(args=None):
    """An OAuth grant if one is stored, otherwise the API token from the env.

    Which one was used is printed, because a run that quietly fell back to a
    personal token would pull a different set of issues — everything that
    account can see rather than everything the grant was scoped to — and the
    resulting file looks exactly as legitimate.
    """
    site = getattr(args, "jira_site", None)
    prefer_token = os.environ.get("JIRA_TOKEN") and os.environ.get("JIRA_EMAIL") \
        and getattr(args, "auth", "auto") == "token"

    if getattr(args, "auth", "auto") != "token":
        import jira_auth
        if jira_auth.TokenStore().read() or getattr(args, "auth", "auto") == "oauth":
            sess = jira_auth.OAuthSession(site)
            return _verified(Jira(sess, sess.url), "OAuth grant, site %s (%s)"
                             % (sess.site.get("name") or sess.cloud_id, sess.url))

    url, email, token = (os.environ.get("JIRA_URL"), os.environ.get("JIRA_EMAIL"),
                         os.environ.get("JIRA_TOKEN"))
    if not (url and email and token):
        sys.exit("No Jira connection. Either\n"
                 "  python3 scripts/jira_auth.py login        (OAuth, for a customer site)\n"
                 "or set JIRA_URL, JIRA_EMAIL and JIRA_TOKEN  (personal API token)")
    how = ("API token (--auth token), %s" if prefer_token else "API token, %s") % url
    return _verified(Jira(_TokenTransport(url, email, token), url), how)


def jira_pull(args):
    j = connect_jira(args)
    sp_field, sprint_field = j.find_fields(args.sp_field, args.sprint_field)
    if not sp_field:
        print("! No story-point field found — points will be 0. "
              "Pass --sp-field customfield_XXXXX to fix.", file=sys.stderr)

    sprint = None
    if args.jira_board:
        sprint = j.active_sprint(args.jira_board)
        if not sprint:
            sys.exit("No active or recent sprint on board %s" % args.jira_board)
        jql = "sprint = %s ORDER BY created ASC" % sprint["id"]
    else:
        jql = args.jira_jql

    fields = ["summary", "issuetype", "status", "assignee", "priority", "parent",
              "created", "resolutiondate", "duedate", "labels", "flagged"]
    for f in (sp_field, sprint_field):
        if f:
            fields.append(f)

    # This app's own fields, if the Forge app is installed on this site. Absent
    # is the ordinary case for the OAuth route — pulling your own board needs no
    # app registration — and it is reported rather than read as "nobody has
    # recorded a value". ADR 0025, ADR 0027.
    bv_field, vb_field = j.find_app_fields()
    # Which field marks an ask is config, and it is deliberately not one
    # convention every site must adopt. ADR 0028.
    ask_field_id = j.find_ask_field(CFG.get("askField"))
    # Three states, three sentences — the same distinction ADR 0025 draws on the
    # Forge tile, because they have entirely different fixes.
    if not bv_field:
        print("  note: this site has no Business Value field from this app, so "
              "value is reported as unmeasured rather than as nil. Install the "
              "Forge app on the site, or supply --values-csv.", file=sys.stderr)
    elif not vb_field:
        print("  note: Business Value is on this site but Value Basis is not, so "
              "figures will arrive with no stated basis beside them.",
              file=sys.stderr)
    for extra in (bv_field, vb_field, ask_field_id):
        if extra:
            fields.append(extra)

    def value_of_raw(f):
        """A number, or None when nobody has recorded one.

        None and not zero, and the distinction is the whole reason this is a
        function: a field nobody filled in and a piece of work genuinely worth
        nothing are different facts. Mirrors `valueOf` in `forge/src/jira.js`.
        """
        if not bv_field:
            return None
        raw = f.get(bv_field)
        if raw in (None, ""):
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def candidate_of_raw(f):
        """The raw answer, trimmed — a string, never a verdict.

        Whether it means yes is `orgconfig.candidate_answer`, which has three
        answers rather than two. Deciding here would throw away the third before
        anything could report it. A select or checkbox on a site's own field
        arrives as an object; those two shapes are read, and anything else is
        left empty rather than becoming `[object Object]` on somebody's epic.
        """
        if not ask_field_id:
            return ""
        raw = f.get(ask_field_id)
        if isinstance(raw, str):
            return raw.strip()
        if isinstance(raw, dict) and isinstance(raw.get("value"), str):
            return raw["value"].strip()
        if isinstance(raw, list) and raw and isinstance(raw[0], dict) \
                and isinstance(raw[0].get("value"), str):
            return raw[0]["value"].strip()
        return ""

    def basis_of_raw(f):
        """The sentence under the number, or '' when there is none.

        A non-string is not coerced: the app declares this field as text, so
        anything else means the field being read is not the one declared, and
        `str()` would put a dict's repr under a currency figure on an executive
        dashboard. Mirrors `basisOf` in `forge/src/jira.js`.
        """
        if not vb_field:
            return ""
        raw = f.get(vb_field)
        return raw.strip() if isinstance(raw, str) else ""

    def build(it, sprint_start):
        f = it["fields"]
        # first transition into an "In Progress" category = start of active work
        started = None
        for h in (it.get("changelog", {}).get("histories") or []):
            for item in h.get("items", []):
                if item.get("field") == "status" and \
                   status_category(item.get("toString")) == "In Progress":
                    cand = d(h.get("created"))
                    if not started or cand < started:
                        started = cand
        # added mid-sprint = the sprint field was set after the sprint began
        mid = False
        if sprint_start:
            for h in (it.get("changelog", {}).get("histories") or []):
                for item in h.get("items", []):
                    if item.get("field", "").lower() == "sprint" and \
                       d(h.get("created")) > sprint_start:
                        mid = True
        status = f.get("status") or {}
        out = {
            "key": it["key"],
            "summary": f.get("summary") or "",
            "type": (f.get("issuetype") or {}).get("name"),
            # Jira's own answer, not a guess from the type's name — a site can
            # call a subtask anything. Recorded on every issue so a consumer can
            # decide; `orgconfig.counted_issues` is what decides. ADR 0024.
            "isSubtask": bool((f.get("issuetype") or {}).get("subtask")),
            # Jira levels its issue types: subtask -1, story 0, epic 1, and a
            # site with a higher tier puts initiatives above that. Business
            # value is counted at one level and not several. ADR 0025.
            "hierarchyLevel": (f.get("issuetype") or {}).get("hierarchyLevel"),
            "status": status.get("name"),
            "statusCategory": status_category(status.get("name"),
                                              (status.get("statusCategory") or {}).get("name")),
            "assignee": (f.get("assignee") or {}).get("displayName") or "Unassigned",
            "storyPoints": (f.get(sp_field) if sp_field else 0) or 0,
            "priority": (f.get("priority") or {}).get("name"),
            "epic": (f.get("parent") or {}).get("fields", {}).get("summary"),
            "created": d(f.get("created")),
            "started": started,
            "resolved": d(f.get("resolutiondate")),
            "dueDate": d(f.get("duedate")),
            "flagged": bool(f.get("flagged")),
            "addedMidSprint": mid,
            "labels": f.get("labels") or [],
            "url": "%s/browse/%s" % (j.url, it["key"]),
        }
        # **The keys are absent when the site has no such field**, and that is
        # deliberate: `metrics` reports value as *unmeasured* when no issue
        # carries the key and as a figure when they do. Writing 0 — which this
        # did for every pull ever made — is the claim that the sprint delivered
        # nothing worth anything, which is a much stronger statement than
        # "nobody has told us", and only one of them was ever true here.
        if bv_field:
            out["businessValue"] = value_of_raw(f)
        if vb_field:
            out["valueBasis"] = basis_of_raw(f)
        if ask_field_id:
            out["candidate"] = candidate_of_raw(f)
        return out

    sprint_start = d(sprint.get("startDate")) if sprint else None
    raw = j.search(jql, fields)
    issues = [build(it, sprint_start) for it in raw]

    # The epics that *finished* inside this sprint — ADR 0026. A `sprint = N`
    # search never returns an epic, so the issue carrying the value is the one
    # that never arrives; declaring the field was necessary and not sufficient
    # on Forge for exactly this reason. Value is credited to the period an epic
    # completed in, because that is the only moment about it this product can
    # date: an epic spans sprints, and spreading its value across them by
    # counting its children would be the double count the level rule prevents.
    #
    # The board and the window come from an argument when the caller resolved
    # the sprint itself: the multi-board path passes a jql and no board, so
    # without this it would read the value fields and never fetch the issues
    # that carry them — the same silent half-fix ADR 0026 was written for, on
    # the one path that produces the richer dataset.
    epic_board = getattr(args, "epic_board", None) or args.jira_board
    window = getattr(args, "epic_window", None) or (
        (sprint.get("startDate"), sprint.get("endDate")) if sprint else None)
    if bv_field and epic_board and window:
        start, end = d(window[0]), d(window[1])
        seen = {i["key"] for i in issues}
        epics, dropped = j.board_epics(epic_board, fields)
        added = 0
        for e in epics:
            if e["key"] in seen:
                continue
            iss = build(e, sprint_start)
            done = iss.get("resolved")
            in_window = bool(start and end and done and start <= done <= end)
            # **A candidate is pulled whenever it was raised.** The window is
            # the right rule for value — an epic's value belongs to the period
            # it completed in, ADR 0026 — and exactly the wrong one here: a
            # candidate is being weighed against other things precisely because
            # nobody has done it, so it has no resolution date to fall inside
            # anything. Filtering on the window found none of them and reported
            # "no candidates" as though it were a fact about the board.
            #
            # An unreadable answer counts as reached-for too, or the epic whose
            # field says "Maybe" is dropped before anything can name it.
            is_candidate = OC.candidate_answer(iss) is not False
            if not (in_window or is_candidate):
                continue
            issues.append(iss)
            added += 1 if in_window else 0
        if added:
            print("  %d epic%s finished in this sprint and carried value"
                  % (added, "" if added == 1 else "s"), file=sys.stderr)
        if dropped:
            print("! %d epic%s beyond the cap were not read — value may be "
                  "understated" % (dropped, "" if dropped == 1 else "s"), file=sys.stderr)

    # What was found, and what could not be read. An answer this does not
    # understand is not a no: an epic whose field says "Maybe" is somebody
    # trying to say something, and dropping it out of a sequencing comparison
    # silently is how the table comes to be missing the ask the meeting was
    # about. ADR 0028.
    if ask_field_id:
        cands, unreadable = OC.candidate_issues(issues, CFG)
        print("  %d candidate%s for sequencing" % (len(cands), "" if len(cands) == 1 else "s"),
              file=sys.stderr)
        for u in unreadable:
            print("! %s answers %r, which is not Yes, Y or True — it is not counted "
                  "as a candidate and it is not a no either"
                  % (u["key"], u["said"]), file=sys.stderr)
    else:
        print("  note: no field marks an ask on this site, so nothing can be "
              "sequenced. Install the Forge app for its Candidate field, or set "
              "orgConfig.askField to a field you already have.", file=sys.stderr)

    meta = {}
    if sprint:
        meta = {
            "sprintName": sprint.get("name"),
            "sprintGoal": sprint.get("goal") or "",
            "startDate": d(sprint.get("startDate")),
            "endDate": d(sprint.get("endDate")),
            "baseUrl": j.url,
            "source": "jira",
            "sourceLabel": "Live: Jira board %s" % args.jira_board,
        }
    return issues, meta


# --------------------------------------------------------------------------
# Asana
# --------------------------------------------------------------------------
def asana_pull(args):
    token = os.environ.get("ASANA_TOKEN")
    if not token:
        sys.exit("Set ASANA_TOKEN before using --asana-project")
    s = need_requests().Session()
    s.headers.update({"Authorization": "Bearer " + token})

    fields = ("gid,name,completed,completed_at,created_at,due_on,start_on,assignee.name,"
              "memberships.section.name,tags.name,custom_fields.name,"
              "custom_fields.number_value,custom_fields.display_value,permalink_url")
    issues, url = [], "https://app.asana.com/api/1.0/tasks"
    params = {"project": args.asana_project, "opt_fields": fields, "limit": 100}
    while url:
        r = s.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        body = r.json()
        for t in body.get("data", []):
            cf = {c.get("name", "").lower(): c for c in (t.get("custom_fields") or [])}

            def num(*names):
                for n in names:
                    if n in cf and cf[n].get("number_value") is not None:
                        return cf[n]["number_value"]
                return 0

            def txt(*names):
                for n in names:
                    if n in cf and cf[n].get("display_value"):
                        return cf[n]["display_value"]
                return ""

            section = ""
            for m in (t.get("memberships") or []):
                section = (m.get("section") or {}).get("name") or section
            issues.append({
                "key": "ASA-" + t["gid"][-6:],
                "summary": t.get("name") or "",
                "type": txt("type", "work type") or "Task",
                "status": "Done" if t.get("completed") else (section or "To Do"),
                "statusCategory": "Done" if t.get("completed") else status_category(section),
                "assignee": (t.get("assignee") or {}).get("name") or "Unassigned",
                "storyPoints": num("story points", "points", "estimate"),
                "priority": txt("priority") or "Medium",
                "epic": section or "",
                "created": d(t.get("created_at")),
                "started": d(t.get("start_on")),
                "resolved": d(t.get("completed_at")),
                "dueDate": d(t.get("due_on")),
                "flagged": any((tag.get("name", "").lower() in ("blocked", "blocker"))
                               for tag in (t.get("tags") or [])),
                "addedMidSprint": False,
                "businessValue": num("business value", "value"),
                "valueBasis": txt("value basis", "basis"),
                "labels": [tag.get("name") for tag in (t.get("tags") or [])],
                "url": t.get("permalink_url"),
            })
        nxt = body.get("next_page")
        url, params = (nxt.get("uri"), None) if nxt else (None, None)
    return issues, {"source": "asana", "sourceLabel": "Live: Asana project %s" % args.asana_project}


# --------------------------------------------------------------------------
# bundles — several project/board/sprint contexts in one file
# --------------------------------------------------------------------------
def jira_bundle(args):
    """Pull the last N sprints from each named board into one bundle.

    One file, many contexts, filtered instantly in the browser. The alternative
    — a fetch per sprint — makes "show me the previous sprint" a round trip to
    a terminal, which is the thing that stops people looking.
    """
    j = connect_jira(args)
    sp_field, sprint_field = j.find_fields(args.sp_field, args.sprint_field)

    boards = [b.strip() for b in (args.jira_boards or "").split(",") if b.strip()]
    contexts, issues, by_ctx = [], [], {}

    for b in boards:
        info = j.get("/rest/agile/1.0/board/%s" % b)
        loc = info.get("location") or {}
        data = j.get("/rest/agile/1.0/board/%s/sprint" % b, state="active,closed")
        sprints = sorted(data.get("values") or [],
                         key=lambda s: s.get("startDate") or "", reverse=True)[:args.sprints]
        sprints.reverse()                                  # oldest first, for history
        board_history = []

        for sp in sprints:
            cid = "%s/%s/%s" % (loc.get("projectKey", "P"), b, sp["id"])
            print("  %s — %s" % (info.get("name"), sp.get("name")), file=sys.stderr)
            sub = argparse.Namespace(jira_board=None,
                                     jira_jql="sprint = %s ORDER BY created ASC" % sp["id"],
                                     sp_field=sp_field, sprint_field=sprint_field,
                                     # This path resolves its own sprint, so it
                                     # hands the epic pass the board and window
                                     # jira_pull would otherwise have derived.
                                     epic_board=b,
                                     epic_window=(sp.get("startDate"), sp.get("endDate")))
            iss, _ = jira_pull(sub)
            for i in iss:
                i["contextId"] = cid
            issues.extend(iss)

            ctx = {
                # Which sort of period this context is bounded by. Written so a
                # bundle describes itself rather than leaving a consumer to
                # recover it from the id — see ADR 0011. Bundles written before
                # this field existed hold only sprints, and `BundleBackend`
                # defaults them.
                "id": cid, "kind": "sprint", "source": "jira",
                "projectKey": loc.get("projectKey"), "projectName": loc.get("projectName"),
                "boardId": b, "boardName": info.get("name"), "team": info.get("name"),
                "sprintName": sp.get("name"), "sprintState": sp.get("state"),
                "sprintGoal": sp.get("goal") or "",
                "startDate": d(sp.get("startDate")), "endDate": d(sp.get("endDate")),
                "asOfDate": (date.today().isoformat() if sp.get("state") == "active"
                             else d(sp.get("completeDate")) or d(sp.get("endDate"))),
                "issueCount": len(iss),
            }
            ctx["workingDays"] = working_days(ctx["startDate"], ctx["endDate"])
            contexts.append(ctx)

            # As of the sprint's own end, never as of this fetch. `asOfDate` is
            # today for the active sprint and the completion date for a closed
            # one, which is exactly the boundary each row is a statement about.
            board_history.append(history_row(iss, ctx["sprintName"], ctx["asOfDate"]))
            by_ctx[cid] = {"burndown": build_burndown(iss, ctx),
                           "history": [], "releases": [], "dora": None}

        # each context sees history up to and including itself — never the future
        for k, ctx in enumerate([c for c in contexts if c["boardId"] == b]):
            by_ctx[ctx["id"]]["history"] = board_history[max(0, k - 5):k + 1]

    return contexts, issues, by_ctx, j.url


# --------------------------------------------------------------------------
# derived series
# --------------------------------------------------------------------------
def build_burndown(issues, meta):
    """Reconstruct a daily burndown from resolution dates and mid-sprint adds.
    This is an approximation: it assumes an issue's points leave the chart on
    its resolution date. If your Jira has a real sprint report API you trust,
    substitute it here."""
    days = meta.get("workingDays") or working_days(meta.get("startDate"), meta.get("endDate"))
    if not days:
        return []
    planned = [i for i in issues if not i.get("addedMidSprint")]
    base_p = sum(i["storyPoints"] for i in planned)
    base_i = len(planned)

    added_by_day, done_by_day = defaultdict(lambda: [0.0, 0]), defaultdict(lambda: [0.0, 0])
    for i in issues:
        if i.get("addedMidSprint") and i.get("created"):
            added_by_day[i["created"]][0] += i["storyPoints"]
            added_by_day[i["created"]][1] += 1
        if i.get("resolved"):
            done_by_day[i["resolved"]][0] += i["storyPoints"]
            done_by_day[i["resolved"]][1] += 1

    as_of = meta.get("asOfDate") or date.today().isoformat()
    out = []
    scope_p, rem_p, scope_i, rem_i = base_p, base_i, base_p, base_i
    scope_p, rem_p = base_p, base_p
    scope_i, rem_i = base_i, base_i
    n = len(days)
    for k, day in enumerate(days):
        add = added_by_day.get(day, [0.0, 0])
        scope_p += add[0]; rem_p += add[0]
        scope_i += add[1]; rem_i += add[1]
        dn = done_by_day.get(day, [0.0, 0])
        rem_p -= dn[0]
        rem_i -= dn[1]
        future = day > as_of
        frac = (1 - k / (n - 1)) if n > 1 else 0
        # Both units, always. The dashboard's toggle needs the item series and
        # the forecasting agent works in items; a points-only burndown puts the
        # two tools in different units by construction.
        out.append({
            "date": day,
            "remainingSP": None if future else round(rem_p, 1),
            "scopeSP": None if future else round(scope_p, 1),
            "idealSP": round(base_p * frac, 1),
            "remainingItems": None if future else rem_i,
            "scopeItems": None if future else scope_i,
            "idealItems": round(base_i * frac, 1),
        })
    return out


def trend_window(cfg):
    """How many sprints of trend the dataset keeps.

    One reader, so the fetcher and both bundle generators cannot disagree about
    the window — which is exactly how four implementations of `history_row` came
    about before 1.36.0 collapsed them into one.
    """
    n = (cfg or {}).get("trendSprints")
    return n if isinstance(n, int) and not isinstance(n, bool) and n >= 2 \
        else OC.DEFAULTS["trendSprints"]


def build_history(issues, meta, previous, cfg=None):
    """Append this sprint to whatever history the previous file held, so the
    trend survives across refreshes.

    The single-board path fetches the *active* sprint, so its as-of is today —
    which is why this one was very nearly right where the bundle path was not.
    It is stated rather than assumed all the same: the row is about a moment
    and the moment has a name.
    """
    hist = list((previous or {}).get("history") or [])
    row = history_row(issues, meta.get("sprintName") or date.today().isoformat(),
                      meta.get("asOfDate") or date.today().isoformat())
    hist = [h for h in hist if h.get("sprint") != row["sprint"]]
    hist.append(row)
    # The window the config states, not a constant. Six was hardcoded here and
    # in two generators, and every one of them dropped the older rows without
    # saying so — a chart of the last six sprints of a twenty-sprint board reads
    # as the whole record. `trendSprints` travels inside the data like every
    # other assumption this file resolves. Roadmap item 4b.
    keep = trend_window(cfg)
    return hist[-keep:]


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--jira-board", help="Jira board id — pulls the active sprint")
    p.add_argument("--jira-boards", help="comma-separated board ids — pulls a multi-sprint BUNDLE")
    p.add_argument("--sprints", type=int, default=6,
                   help="sprints per board when building a bundle (default 6)")
    p.add_argument("--jira-jql", help="Raw JQL instead of a board")
    p.add_argument("--asana-project", help="Asana project gid")
    p.add_argument("--sp-field", help="Story-point custom field id, e.g. customfield_10016")
    p.add_argument("--sprint-field", help="Sprint custom field id")
    p.add_argument("--out", default="dashboard-data.json")
    p.add_argument("--team", default="")
    p.add_argument("--org", default="")
    p.add_argument("--currency", default="USD")
    p.add_argument("--values-csv",
                   help="Optional CSV of key,businessValue,valueBasis to merge in")
    p.add_argument("--org-config", default=str(ROOT / "config" / "organisation.json"),
                   help="Which statuses mean done, the working week, holidays and "
                        "sprint length (default config/organisation.json)")
    p.add_argument("--auth", choices=("auto", "oauth", "token"), default="auto",
                   help="auto uses a stored OAuth grant if there is one, else the "
                        "API token in the environment")
    p.add_argument("--jira-site", help="Which granted site to pull, by name, url or "
                                       "cloudid — required when a grant covers several")
    args = p.parse_args()

    # Resolved before anything is pulled, because it decides what "done" means
    # and which days count. A config that cannot be read stops the run rather
    # than silently reverting to the defaults and producing a plausible file.
    if os.path.exists(args.org_config):
        configure(OC.load(args.org_config))
        print("Config: %s — %s" % (args.org_config, OC.summary(CFG)), file=sys.stderr)
    else:
        print("Config: %s not found, using defaults — %s"
              % (args.org_config, OC.summary(CFG)), file=sys.stderr)

    if not (args.jira_board or args.jira_boards or args.jira_jql or args.asana_project):
        p.error("Give at least one of --jira-board, --jira-boards, --jira-jql, --asana-project")

    # ---- bundle mode ----
    if args.jira_boards:
        print("Building a bundle: %d sprint(s) per board" % args.sprints, file=sys.stderr)
        contexts, issues, by_ctx, base_url = jira_bundle(args)
        active = next((c for c in contexts if c["sprintState"] == "active"), contexts[-1])
        out = {
            "schemaVersion": "2.0",
            "meta": {
                "organisation": args.org, "currency": args.currency,
                "baseUrl": base_url,
                "source": "jira",
                "sourceLabel": "Live: Jira boards %s, last %d sprints"
                               % (args.jira_boards, args.sprints),
                "generatedAt": datetime.utcnow().isoformat() + "Z",
            },
            # The config that produced these numbers ships inside them. A
            # consumer that resolved its own would be a second opinion arriving
            # by a different route, and the first sign of trouble would be the
            # page and the facts pack disagreeing about the same sprint.
            "orgConfig": dict(CFG, inferredStatuses=STATUSES.inferred),
            "contexts": contexts,
            "defaultContextId": active["id"],
            "issues": issues,
            "byContext": by_ctx,
        }
        with open(args.out, "w") as fh:
            json.dump(out, fh, indent=1)
        print("Wrote %s — %d contexts, %d issues"
              % (args.out, len(contexts), len(issues)))
        report_unmatched()
        return

    previous = {}
    if os.path.exists(args.out):
        try:
            previous = json.load(open(args.out))
        except Exception:
            previous = {}

    issues, meta = [], {}
    if args.jira_board or args.jira_jql:
        i, m = jira_pull(args)
        issues += i
        meta.update(m)
    if args.asana_project:
        i, m = asana_pull(args)
        issues += i
        if not meta:
            meta.update(m)
        else:
            meta["sourceLabel"] = meta.get("sourceLabel", "") + " + " + m["sourceLabel"]
            meta["source"] = "jira+asana"

    # merge externally-maintained value estimates
    if args.values_csv and os.path.exists(args.values_csv):
        import csv
        vals = {r["key"]: r for r in csv.DictReader(open(args.values_csv))}
        for i in issues:
            if i["key"] in vals:
                i["businessValue"] = float(vals[i["key"]].get("businessValue") or 0)
                i["valueBasis"] = vals[i["key"]].get("valueBasis", "")

    meta.setdefault("startDate", min([i["created"] for i in issues if i["created"]] or [None]))
    meta.setdefault("endDate", date.today().isoformat())
    meta["asOfDate"] = date.today().isoformat()
    meta["generatedAt"] = datetime.utcnow().isoformat() + "Z"
    meta["organisation"] = args.org or (previous.get("meta") or {}).get("organisation", "")
    meta["team"] = args.team or (previous.get("meta") or {}).get("team", "")
    meta["currency"] = args.currency
    meta["workingDays"] = working_days(meta.get("startDate"), meta.get("endDate"))

    out = {
        "schemaVersion": "1.0",
        "meta": meta,
        # What the config did not cover, and what each of those was read as.
        # Inference happens here, where the data is produced, and a reader of
        # the file had no way to know it had happened: the note below prints
        # once, to a terminal, to whoever ran the pull. It travels now.
        "orgConfig": dict(CFG, inferredStatuses=STATUSES.inferred),
        "issues": issues,
        "burndown": build_burndown(issues, meta),
        "history": build_history(issues, meta, previous, CFG),
        # Neither Jira nor Asana knows these. Keep whatever was there before so a
        # refresh never silently blanks a card; fill them from your CI/CD tool.
        "releases": (previous.get("releases") or []),
        "dora": previous.get("dora"),
    }

    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)
    done = sum(1 for i in issues if i["statusCategory"] == "Done")
    print("Wrote %s — %d issues (%d done), sprint %r"
          % (args.out, len(issues), done, meta.get("sprintName", "n/a")))
    if not out["dora"]:
        print("  note: no DORA metrics — that card will show as unavailable. "
              "Add them to the JSON from your deployment tooling.", file=sys.stderr)
    if any("businessValue" in i for i in issues) \
            and all(not i.get("businessValue") for i in issues):
        # The field is readable and empty, which is a different fact from the
        # field being absent — that one is reported where it is discovered.
        print("  note: the value field is on this site but no issue carries a "
              "figure. An admin must add it to a screen before anyone can fill "
              "it in, and the tile says so.", file=sys.stderr)
    report_unmatched()


if __name__ == "__main__":
    main()
