#!/usr/bin/env python3
"""
make_sample_bundle.py — generate a demo multi-context bundle.

A bundle is one file holding several *contexts* — a context being one
project + board + sprint. The dashboard filters between them instantly and
offline, which is what makes "show me Sprint 22 on the other board" a click
rather than a re-fetch.

This produces plausible fake data for two projects, three boards and six
sprints each, so the context selector has something real to switch between.

    python3 scripts/make_sample_bundle.py --out data/sample-bundle.json
"""

import argparse
import json
import pathlib
import random
import sys
from datetime import date, timedelta

# One derivation of a sprint's trend row, shared with the fetcher and with the
# Forge route. A history row is a statement about the moment a sprint ended, and
# reading it off current issue status silently flatters every closed sprint.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "agent" / "tools"))
from metrics import history_row  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fetch_delivery_data import trend_window  # noqa: E402

TYPES = ["Story", "Bug", "Task"]
PRIOS = ["Highest", "High", "Medium", "Medium", "Low"]

BOARDS = [
    {"projectKey": "BLC", "projectName": "Highpeak Commerce",
     "boardId": "42", "boardName": "Storefront Delivery", "team": "Storefront Team",
     "people": ["Alex Rivera", "Priya Nair", "Jordan Lee", "Sam Okafor"],
     "epics": ["Checkout Stability", "Payments", "Catalogue", "Conversion", "Order Management"],
     "rate": [0, 0, 1, 1, 1, 2, 2, 3]},
    {"projectKey": "BLC", "projectName": "Highpeak Commerce",
     "boardId": "43", "boardName": "Platform & Infra", "team": "Platform Team",
     "people": ["Rowan Diaz", "Mei Tanaka", "Chidi Obi"],
     "epics": ["Observability", "Cost", "Reliability", "Developer Experience"],
     "rate": [0, 0, 0, 1, 1, 1, 2, 4]},
    {"projectKey": "MOB", "projectName": "Highpeak Mobile",
     "boardId": "51", "boardName": "Mobile Apps", "team": "Mobile Team",
     "people": ["Nadia Farouk", "Tom Ellery", "Sara Lindqvist", "Iyad Haddad"],
     "epics": ["Onboarding", "Push & Notifications", "Offline Mode", "App Performance"],
     "rate": [0, 0, 1, 1, 2, 2, 2, 3]},
]

SUMMARIES = [
    "Fix crash when applying a promo code", "Add address autocomplete to delivery",
    "Payment retry logic for declined cards", "Order confirmation email missing tax breakdown",
    "Refund webhook occasionally fires twice", "Search ignores the in-stock filter",
    "Inventory sync oversells limited stock", "Promo code stacking rules inconsistent",
    "Screen reader labels missing on checkout", "Upgrade SDK before deprecation",
    "Saved cards not shown for returning users", "Analytics events missing on review step",
    "Flaky end-to-end test on the happy path", "Shipping cut-off copy for bank holiday",
    "Gift card balance shows zero after partial use", "Server-side logging for the promo service",
    "Returns policy link in the footer", "Bulk CSV import fails over 500 rows",
    "Image CDN cache invalidation delay", "Wishlist lost when a guest signs in",
    "Rate limit on the pricing endpoint", "Session token refresh race",
    "Dark mode contrast on the basket screen", "Deep link opens the wrong tab",
]


def working_days(a, b):
    out, cur = [], a
    while cur <= b:
        if cur.weekday() < 5:
            out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def add_wd(d, n):
    cur = d
    while n > 0:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            n -= 1
    return cur


def build(seed=42, sprints=6, as_of="2026-08-10", scale=1):
    rng = random.Random(seed)
    global BOARDS
    if scale > 1:
        # Clone the board list to simulate a large organisation, so performance
        # can be measured against a realistic worst case rather than a guess.
        base = BOARDS[:3]
        BOARDS = []
        for n in range(scale):
            for b in base:
                c = dict(b)
                c["projectKey"] = "%s%d" % (b["projectKey"], n)
                c["projectName"] = "%s %d" % (b["projectName"], n)
                c["boardId"] = "%s%d" % (b["boardId"], n)
                c["boardName"] = "%s %d" % (b["boardName"], n)
                BOARDS.append(c)
    contexts, issues, by_ctx = [], [], {}
    counter = {b["boardId"]: 300 for b in BOARDS}

    # sprint windows: two-week sprints ending on the current one
    today = date.fromisoformat(as_of)
    current_start = date(2026, 8, 3)
    windows = []
    for k in range(sprints - 1, -1, -1):
        s = current_start - timedelta(days=14 * k)
        windows.append((s, s + timedelta(days=11)))

    for b in BOARDS:
        for ix, (start, end) in enumerate(windows):
            num = 24 - (len(windows) - 1 - ix)
            active = start <= today <= end
            ctx_id = "%s/%s/S%d" % (b["projectKey"], b["boardId"], num)
            days = working_days(start, end)
            ctx_asof = as_of if active else end.isoformat()
            # The latest date anything in this sprint can have happened by. For
            # a closed sprint that is its end; for the active one it is today,
            # and the two differ — which is how issues came to be written as
            # done with a resolution date in the future. Nothing read the dates
            # until the trend row started counting completion by them, and a
            # fixture whose status and dates disagree puts two different
            # completion figures on one screen.
            cap = min(end, date.fromisoformat(ctx_asof))

            planned = rng.randint(9, 16)
            ctx_issues = []
            for n in range(planned):
                counter[b["boardId"]] += 1
                key = "%s-%d" % (b["projectKey"], counter[b["boardId"]])
                created = start - timedelta(days=rng.randint(2, 30))
                # closed sprints finish most of their work; the active one is partial
                finish_p = 0.86 if not active else 0.55
                done = rng.random() < finish_p
                started = add_wd(max(created, start), rng.randint(0, 4))
                resolved = add_wd(started, rng.randint(1, 8)) if done else None
                if resolved and resolved > cap:
                    resolved, done = None, False
                if started > date.fromisoformat(ctx_asof):
                    started = None
                ctx_issues.append({
                    "key": key,
                    "summary": rng.choice(SUMMARIES),
                    "type": rng.choice(TYPES),
                    "status": "Done" if done else rng.choice(["To Do", "In Progress", "In Review"]),
                    "statusCategory": "Done" if done else rng.choice(["To Do", "In Progress"]),
                    "assignee": rng.choice(b["people"]),
                    "storyPoints": rng.choice([1, 2, 3, 3, 5, 5, 8]),
                    "priority": rng.choice(PRIOS),
                    "epic": rng.choice(b["epics"]),
                    "created": created.isoformat(),
                    "started": started.isoformat() if started else None,
                    "resolved": resolved.isoformat() if resolved else None,
                    "dueDate": add_wd(start, rng.randint(4, 10)).isoformat(),
                    "flagged": rng.random() < 0.09,
                    "addedMidSprint": False,
                    "businessValue": 0, "valueBasis": "", "labels": [],
                    "contextId": ctx_id,
                })
            # a couple of mid-sprint additions
            for _ in range(rng.randint(0, 3)):
                counter[b["boardId"]] += 1
                key = "%s-%d" % (b["projectKey"], counter[b["boardId"]])
                cday = date.fromisoformat(rng.choice(days[1:]))
                done = rng.random() < 0.5
                resolved = add_wd(cday, rng.randint(1, 4)) if done else None
                if resolved and resolved > cap:
                    resolved, done = None, False
                ctx_issues.append({
                    "key": key, "summary": "Unplanned: " + rng.choice(SUMMARIES),
                    "type": "Bug", "status": "Done" if done else "In Progress",
                    "statusCategory": "Done" if done else "In Progress",
                    "assignee": rng.choice(b["people"]),
                    "storyPoints": rng.choice([1, 2, 3, 5]),
                    "priority": rng.choice(["Highest", "High"]),
                    "epic": rng.choice(b["epics"]),
                    "created": cday.isoformat(),
                    "started": cday.isoformat(),
                    "resolved": resolved.isoformat() if resolved else None,
                    "dueDate": add_wd(cday, 4).isoformat(),
                    "flagged": False, "addedMidSprint": True,
                    "businessValue": 0, "valueBasis": "", "labels": ["unplanned"],
                    "contextId": ctx_id,
                })

            issues.extend(ctx_issues)
            done_items = [i for i in ctx_issues if i["statusCategory"] == "Done"]
            contexts.append({
                "id": ctx_id, "source": "jira",
                "projectKey": b["projectKey"], "projectName": b["projectName"],
                "boardId": b["boardId"], "boardName": b["boardName"], "team": b["team"],
                "sprintName": "Sprint %d" % num,
                "sprintState": "active" if active else "closed",
                "sprintGoal": "" if not active else
                    "Ship checkout stability fixes and launch the cart abandonment email.",
                "startDate": start.isoformat(), "endDate": end.isoformat(),
                "asOfDate": ctx_asof, "workingDays": days,
                "issueCount": len(ctx_issues), "doneCount": len(done_items),
            })
            by_ctx[ctx_id] = {"burndown": [], "history": [], "releases": [], "dora": None}

        # per-board sprint history, from the contexts just built
        board_ctxs = [c for c in contexts if c["boardId"] == b["boardId"]]
        hist = []
        for c in board_ctxs:
            mine = [i for i in issues if i["contextId"] == c["id"]]
            # The fetcher's own derivation, not a copy of it. This generator had
            # its own, and so did the demo generator, and both read work in
            # progress off *current* status — which for a closed sprint is
            # none of it. Four implementations of one fact; now one.
            hist.append(history_row(mine, c["sprintName"], c["asOfDate"]))
        for c in board_ctxs:
            upto = [h for h in hist if h["sprint"] <= c["sprintName"]]
            # The window, resolved by the same function the fetcher uses
            # rather than a six of this generator's own — which is how a bundle
            # and a live pull could disagree about how much history they carried
            # while both looking complete. This sample states no organisation
            # config, so it takes the default; `None` says that rather than
            # hiding it behind a variable that is always empty. Roadmap 4b.
            by_ctx[c["id"]]["history"] = upto[-trend_window(None):]
            by_ctx[c["id"]]["dora"] = {
                "deploymentFrequencyPerWeek": rng.randint(4, 14),
                "deploymentFrequencyTrend": [rng.randint(4, 14) for _ in range(6)],
                "changeFailureRatePct": rng.randint(4, 18),
                "changeFailureRateTrend": [rng.randint(4, 18) for _ in range(6)],
                "leadTimeForChangesDays": round(rng.uniform(0.8, 3.2), 1),
                "leadTimeForChangesTrend": [round(rng.uniform(0.8, 3.2), 1) for _ in range(6)],
                "mttrMinutes": rng.randint(25, 95),
                "mttrTrend": [rng.randint(25, 95) for _ in range(6)],
            }

    return {
        "schemaVersion": "2.0",
        "meta": {
            "organisation": "Highpeak", "currency": "USD",
            "baseUrl": "https://highpeak.atlassian.net",
            "source": "demo", "sourceLabel": "Demo bundle — 3 boards x 6 sprints",
            "generatedAt": "2026-08-10T09:15:00Z",
        },
        "contexts": contexts,
        "defaultContextId": next(c["id"] for c in contexts if c["sprintState"] == "active"),
        "issues": issues,
        "byContext": by_ctx,
    }


def main():
    # The burndown fill lives here rather than in the Makefile: a generator that
    # emits an incomplete file unless you remember a second command is a trap,
    # and it caught one — the browser suite failed on empty burndowns.
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import rebuild_burndown as RB

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/sample-bundle.json")
    ap.add_argument("--sprints", type=int, default=6)
    ap.add_argument("--scale", type=int, default=1,
                    help="clone the board set N times, for performance testing")
    a = ap.parse_args()
    b = build(sprints=a.sprints, scale=a.scale)
    for c in b["contexts"]:
        mine = [i for i in b["issues"] if i["contextId"] == c["id"]]
        b["byContext"][c["id"]]["burndown"] = RB.rebuild({"meta": c, "issues": mine})
    p = pathlib.Path(a.out)
    p.write_text(json.dumps(b, separators=(",", ":")) + "\n")
    print("%s — %d contexts, %d issues, %d KB"
          % (p, len(b["contexts"]), len(b["issues"]), p.stat().st_size / 1024))


if __name__ == "__main__":
    main()
