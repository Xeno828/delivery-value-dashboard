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

Jira
----
    export JIRA_URL=https://your-domain.atlassian.net
    export JIRA_EMAIL=you@company.com
    export JIRA_TOKEN=...        # id.atlassian.com > Security > API tokens

    python fetch_delivery_data.py --jira-board 42 --out dashboard-data.json
    python fetch_delivery_data.py --jira-jql 'project = BLC AND sprint in openSprints()'

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
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

try:
    import requests
except ImportError:
    sys.exit("Install the dependency first:  pip install requests")

TIMEOUT = 45


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def d(value):
    """Any Jira/Asana timestamp -> YYYY-MM-DD, or None."""
    if not value:
        return None
    return str(value)[:10]


def working_days(start, end):
    """Weekdays between two ISO dates, inclusive. Replace with your own
    calendar if the team observes public holidays."""
    if not start or not end:
        return []
    a, b, out = date.fromisoformat(start), date.fromisoformat(end), []
    while a <= b:
        if a.weekday() < 5:
            out.append(a.isoformat())
        a += timedelta(days=1)
    return out


def status_category(name, category=None):
    if category:
        c = category.lower()
        if "done" in c or "complete" in c:
            return "Done"
        if "progress" in c:
            return "In Progress"
        return "To Do"
    n = (name or "").lower()
    if re.search(r"done|closed|resolved|complete|shipped", n):
        return "Done"
    if re.search(r"progress|review|test|doing|qa", n):
        return "In Progress"
    return "To Do"


# --------------------------------------------------------------------------
# Jira
# --------------------------------------------------------------------------
class Jira:
    def __init__(self, url, email, token):
        self.url = url.rstrip("/")
        self.s = requests.Session()
        self.s.auth = (email, token)
        self.s.headers.update({"Accept": "application/json"})

    def get(self, path, **params):
        r = self.s.get(self.url + path, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()

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

    def active_sprint(self, board_id):
        data = self.get("/rest/agile/1.0/board/%s/sprint" % board_id, state="active")
        vals = data.get("values") or []
        if not vals:
            data = self.get("/rest/agile/1.0/board/%s/sprint" % board_id,
                            state="closed", maxResults=1)
            vals = data.get("values") or []
        return vals[0] if vals else None

    def search(self, jql, fields, expand="changelog"):
        out, start = [], 0
        while True:
            page = self.s.post(
                self.url + "/rest/api/3/search",
                json={"jql": jql, "startAt": start, "maxResults": 100,
                      "fields": fields, "expand": [expand]},
                timeout=TIMEOUT,
            )
            page.raise_for_status()
            body = page.json()
            out.extend(body.get("issues", []))
            start += len(body.get("issues", []))
            if start >= body.get("total", 0) or not body.get("issues"):
                break
        return out


def jira_pull(args):
    url = os.environ.get("JIRA_URL")
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_TOKEN")
    if not (url and email and token):
        sys.exit("Set JIRA_URL, JIRA_EMAIL and JIRA_TOKEN before using --jira-*")

    j = Jira(url, email, token)
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

    raw = j.search(jql, fields)
    issues, added_mid = [], []
    sprint_start = d(sprint.get("startDate")) if sprint else None

    for it in raw:
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
        issues.append({
            "key": it["key"],
            "summary": f.get("summary") or "",
            "type": (f.get("issuetype") or {}).get("name"),
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
            # Jira has no native value field. Point --value-field at a numeric
            # custom field, or maintain values in a side CSV — see README.
            "businessValue": 0,
            "valueBasis": "",
            "labels": f.get("labels") or [],
            "url": "%s/browse/%s" % (j.url, it["key"]),
        })

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
    s = requests.Session()
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
    url, email, token = (os.environ.get("JIRA_URL"), os.environ.get("JIRA_EMAIL"),
                         os.environ.get("JIRA_TOKEN"))
    if not (url and email and token):
        sys.exit("Set JIRA_URL, JIRA_EMAIL and JIRA_TOKEN")
    j = Jira(url, email, token)
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
                                     sp_field=sp_field, sprint_field=sprint_field)
            iss, _ = jira_pull(sub)
            for i in iss:
                i["contextId"] = cid
            issues.extend(iss)

            ctx = {
                "id": cid, "source": "jira",
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

            done = [i for i in iss if i["statusCategory"] == "Done"]
            planned = [i for i in iss if not i.get("addedMidSprint")]
            board_history.append({
                "sprint": ctx["sprintName"],
                "committedSP": round(sum(i["storyPoints"] for i in planned), 1),
                "completedSP": round(sum(i["storyPoints"] for i in done), 1),
                "committedItems": len(planned), "completedItems": len(done),
                "throughput": len(done),
                "wipItems": len([i for i in iss if i["statusCategory"] == "In Progress"]),
                "unplannedItems": len([i for i in iss if i.get("addedMidSprint")]),
                "flowEfficiency": None,
                "valueDelivered": round(sum(i.get("businessValue") or 0 for i in done)),
            })
            by_ctx[cid] = {"burndown": build_burndown(iss, ctx),
                           "history": [], "releases": [], "dora": None}

        # each context sees history up to and including itself — never the future
        for k, ctx in enumerate([c for c in contexts if c["boardId"] == b]):
            by_ctx[ctx["id"]]["history"] = board_history[max(0, k - 5):k + 1]

    return contexts, issues, by_ctx


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


def build_history(issues, meta, previous):
    """Append this sprint to whatever history the previous file held, so the
    six-sprint trends survive across refreshes."""
    hist = list((previous or {}).get("history") or [])
    done = [i for i in issues if i["statusCategory"] == "Done"]
    lead = [(i, (date.fromisoformat(i["resolved"]) - date.fromisoformat(i["created"])).days)
            for i in done if i.get("resolved") and i.get("created")]
    cyc = [(i, (date.fromisoformat(i["resolved"]) - date.fromisoformat(i["started"])).days)
           for i in done if i.get("resolved") and i.get("started")]
    tot_lead, tot_cyc = sum(v for _, v in lead), sum(v for _, v in cyc)
    row = {
        "sprint": meta.get("sprintName") or date.today().isoformat(),
        "committedSP": round(sum(i["storyPoints"] for i in issues
                                 if not i.get("addedMidSprint")), 1),
        "completedSP": round(sum(i["storyPoints"] for i in done), 1),
        "committedItems": len([i for i in issues if not i.get("addedMidSprint")]),
        "completedItems": len(done),
        "throughput": len(done),
        # Work in progress and interruption, both from issue status. No hours
        # field: the organisation does not operate overtime, and carrying one
        # would imply a time-tracking regime that does not exist.
        "wipItems": len([i for i in issues if i["statusCategory"] == "In Progress"]),
        "unplannedItems": len([i for i in issues if i.get("addedMidSprint")]),
        "flowEfficiency": round(tot_cyc / tot_lead, 2) if tot_lead else None,
        "valueDelivered": round(sum(i.get("businessValue") or 0 for i in done), 0),
    }
    hist = [h for h in hist if h.get("sprint") != row["sprint"]]
    hist.append(row)
    return hist[-6:]


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
    args = p.parse_args()

    if not (args.jira_board or args.jira_boards or args.jira_jql or args.asana_project):
        p.error("Give at least one of --jira-board, --jira-boards, --jira-jql, --asana-project")

    # ---- bundle mode ----
    if args.jira_boards:
        print("Building a bundle: %d sprint(s) per board" % args.sprints, file=sys.stderr)
        contexts, issues, by_ctx = jira_bundle(args)
        active = next((c for c in contexts if c["sprintState"] == "active"), contexts[-1])
        out = {
            "schemaVersion": "2.0",
            "meta": {
                "organisation": args.org, "currency": args.currency,
                "baseUrl": os.environ.get("JIRA_URL", "").rstrip("/"),
                "source": "jira",
                "sourceLabel": "Live: Jira boards %s, last %d sprints"
                               % (args.jira_boards, args.sprints),
                "generatedAt": datetime.utcnow().isoformat() + "Z",
            },
            "contexts": contexts,
            "defaultContextId": active["id"],
            "issues": issues,
            "byContext": by_ctx,
        }
        with open(args.out, "w") as fh:
            json.dump(out, fh, indent=1)
        print("Wrote %s — %d contexts, %d issues"
              % (args.out, len(contexts), len(issues)))
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
        "issues": issues,
        "burndown": build_burndown(issues, meta),
        "history": build_history(issues, meta, previous),
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
    if all(not i.get("businessValue") for i in issues):
        print("  note: no business value on any issue — use --values-csv or an "
              "Asana number field to populate the value card.", file=sys.stderr)


if __name__ == "__main__":
    main()
