#!/usr/bin/env python3
"""
make_demo_bundle.py — a bundle authored to tell a story.

`make_sample_bundle.py` generates random data, which is fine for load testing
and useless for a demo: every click changes the numbers but none of them mean
anything. A demo on random data shows features, not value.

This plants specific, findable situations so that each selection in the demo
reveals something a viewer can act on:

  Storefront Delivery (BLC/42) — "failing" for reasons that are not effort
      Commitment has climbed from 11 to 18 items while delivery stayed flat
      around 10. Scope is injected mid-sprint. One highest-priority item has
      been blocked for 21 days. Flow efficiency ~22%: the work waits.

  Platform & Infra (BLC/43) — what good looks like
      Same organisation, same fortnight. Commitments sized to actuals, ~92%
      hit rate, flow efficiency ~60%, nothing blocked, nothing ageing. The
      contrast is the point: the Storefront problem is local, not systemic.

  Mobile Apps (MOB/51) — where the unit you pick changes the answer
      14 of 16 items done (88%) but only 37% of the points, because the two
      unfinished items are the two big ones. Items say "nearly there"; points
      say "the hard part is untouched". Both are true; the toggle shows both.

    python3 scripts/make_demo_bundle.py --out data/demo-bundle.json
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

AS_OF = "2026-08-10"
CURRENT_START = date(2026, 8, 3)


def wdays(a, b):
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


# --------------------------------------------------------------- the boards
BOARDS = [
    dict(
        projectKey="BLC", projectName="Highpeak Commerce",
        boardId="42", boardName="Storefront Delivery", team="Storefront Team",
        people=["Alex Rivera", "Priya Nair", "Jordan Lee", "Sam Okafor"],
        epics=["Checkout Stability", "Payments", "Catalogue", "Conversion", "Order Management"],
        goal="Ship checkout stability fixes and launch the cart abandonment email "
             "so conversion recovers before peak trading.",
        # per sprint, oldest first: committed items, completed items, injected, wait ratio
        plan=[(11, 11, 0, 0.55), (12, 12, 1, 0.55), (11, 9, 2, 0.62),
              (13, 10, 2, 0.68), (12, 8, 3, 0.74), (18, 12, 4, 0.78)],
        sizes=[3, 5, 3, 8, 2, 5, 3, 1, 5, 3, 8, 2, 3, 5, 1, 3, 2, 5, 3, 8],
    ),
    dict(
        projectKey="BLC", projectName="Highpeak Commerce",
        boardId="43", boardName="Platform & Infra", team="Platform Team",
        people=["Rowan Diaz", "Mei Tanaka", "Chidi Obi"],
        epics=["Observability", "Cost", "Reliability", "Developer Experience"],
        goal="Cut alert noise by half and finish the cost-attribution rollout.",
        plan=[(9, 8, 0, 0.42), (9, 9, 0, 0.40), (10, 9, 1, 0.41),
              (9, 9, 0, 0.38), (10, 9, 0, 0.39), (9, 8, 1, 0.40)],
        sizes=[3, 2, 5, 3, 2, 3, 5, 2, 3, 2, 3, 5, 2, 3, 3],
    ),
    dict(
        projectKey="MOB", projectName="Highpeak Mobile",
        boardId="51", boardName="Mobile Apps", team="Mobile Team",
        people=["Nadia Farouk", "Tom Ellery", "Sara Lindqvist", "Iyad Haddad"],
        epics=["Onboarding", "Push & Notifications", "Offline Mode", "App Performance"],
        goal="Land offline mode and the new onboarding flow ahead of the autumn release.",
        plan=[(12, 11, 1, 0.50), (13, 12, 0, 0.52), (12, 11, 1, 0.49),
              (14, 12, 2, 0.53), (13, 12, 1, 0.51), (16, 14, 1, 0.52)],
        # the last sprint's two unfinished items are the two 13s — items look
        # nearly done, points say the hard part has not started
        sizes=[2, 1, 2, 3, 1, 2, 2, 1, 3, 2, 1, 2, 2, 1, 13, 13],
    ),
]

WORK = {
    "Checkout Stability": ["Checkout crash on Safari when applying a promo code",
                           "Guest checkout session expires too early",
                           "Promo code stacking rules are inconsistent",
                           "Address autocomplete on the delivery step",
                           "Screen reader labels missing on the checkout form"],
    "Payments": ["Payment retry logic for declined cards",
                 "Refund webhook occasionally fires twice",
                 "Saved cards not shown for returning customers",
                 "Upgrade the payment SDK before deprecation",
                 "Gift card balance shows zero after partial use"],
    "Catalogue": ["Inventory sync race condition oversells limited stock",
                  "Search results ignore the in-stock filter",
                  "Product image CDN cache invalidation delay"],
    "Conversion": ["Cart abandonment email — template and send scheduling",
                   "Analytics events missing on the review-order step",
                   "Wishlist items lost when a guest signs in"],
    "Order Management": ["Order confirmation email missing the tax breakdown",
                         "Bulk order CSV import fails over 500 rows",
                         "Returns policy link in the footer"],
    "Observability": ["Halve alert noise on the checkout service",
                      "Trace sampling misses slow requests",
                      "Dashboards for the new ingest pipeline"],
    "Cost": ["Attribute spend to owning team", "Rightsize the staging cluster",
             "Delete orphaned snapshots"],
    "Reliability": ["Failover drill for the primary region",
                    "Retry budget on the pricing endpoint",
                    "Session token refresh race"],
    "Developer Experience": ["Cut CI wall time below eight minutes",
                             "One-command local environment",
                             "Flaky end-to-end test on the happy path"],
    "Onboarding": ["Rebuild the first-run flow", "Social sign-in on Android",
                   "Skip-for-now on the permissions screen"],
    "Push & Notifications": ["Quiet hours honour the device timezone",
                             "Deep link opens the wrong tab",
                             "Notification grouping on iOS"],
    "Offline Mode": ["Offline basket sync", "Conflict resolution on reconnect",
                     "Cache eviction policy"],
    "App Performance": ["Cold start under two seconds",
                        "Dark mode contrast on the basket screen",
                        "Image decode off the main thread"],
}

VALUE = {
    "Checkout crash on Safari when applying a promo code":
        (52200, "Retention: 1,340 abandoned checkouts/mo x $39 recovered"),
    "Cart abandonment email — template and send scheduling":
        (34800, "Conversion uplift: 2.1% of 41k monthly sessions x $40 AOV"),
    "Halve alert noise on the checkout service":
        (18400, "On-call time returned: 22 hrs/mo x $70 fully-loaded"),
    "Attribute spend to owning team":
        (31000, "Cloud spend identified as unowned and retired: $31k annualised"),
    "Rebuild the first-run flow":
        (44500, "Activation: +3.4pp on 18k monthly installs x $72 LTV"),
}


def build():
    rng = random.Random(7)
    contexts, issues, by_ctx = [], [], {}

    windows = [(CURRENT_START - timedelta(days=14 * k),
                CURRENT_START - timedelta(days=14 * k) + timedelta(days=11))
               for k in range(5, -1, -1)]

    for b in BOARDS:
        counter, board_hist = 400, []
        board_ctxs = []

        for ix, (start, end) in enumerate(windows):
            num = 19 + ix
            active = ix == len(windows) - 1
            cid = "%s/%s/S%d" % (b["projectKey"], b["boardId"], num)
            committed, completed, injected, wait = b["plan"][ix]
            as_of = AS_OF if active else end.isoformat()
            # The latest date anything in this sprint can have happened by.
            cap = min(end, date.fromisoformat(as_of))
            days = wdays(start, end)
            mine = []

            titles = [t for e in b["epics"] for t in WORK[e]]
            for n in range(committed):
                counter += 1
                title = titles[(ix * 5 + n) % len(titles)]
                epic = next(e for e in b["epics"] if title in WORK[e])
                pts = b["sizes"][n % len(b["sizes"])]
                done = n < completed
                # Pick started first, then derive created from the target wait
                # ratio, so flow efficiency comes out where the story needs it:
                #   cycle / lead = 1 - wait  =>  queue = cycle * wait / (1 - wait)
                active_days = rng.randint(2, 4)
                queue_days = max(1, round(active_days * wait / (1 - wait)))
                started = add_wd(start, n % 4)
                created = started - timedelta(days=queue_days)
                resolved = add_wd(started, active_days) if done else None
                # Clamped to the as-of date, not just to the sprint's end. In
                # the active sprint those differ, and three issues were being
                # written as `statusCategory: "Done"` with a resolution date
                # the day *after* the demo's as-of — work finished tomorrow.
                # Nothing read the dates, so it never showed; the trend row now
                # counts completion by date and the tile counts it by status,
                # and a fixture that disagrees with itself puts the two on
                # screen together saying different numbers.
                if resolved and resolved > cap:
                    resolved = cap
                if started > date.fromisoformat(as_of):
                    started = None
                mine.append(dict(
                    key="%s-%d" % (b["projectKey"], counter), summary=title,
                    type="Bug" if "crash" in title or "fails" in title or "ignore" in title else "Story",
                    status="Done" if done else ("In Progress" if started else "To Do"),
                    statusCategory="Done" if done else ("In Progress" if started else "To Do"),
                    assignee=b["people"][n % len(b["people"])],
                    storyPoints=pts, priority="Medium",
                    epic=epic, created=created.isoformat(),
                    started=started.isoformat() if started else None,
                    resolved=resolved.isoformat() if resolved else None,
                    dueDate=add_wd(start, 4 + (n % 6)).isoformat(),
                    flagged=False, addedMidSprint=False,
                    businessValue=VALUE.get(title, (0, ""))[0] if done else 0,
                    valueBasis=VALUE.get(title, (0, ""))[1] if done else "",
                    labels=[], contextId=cid))

            for n in range(injected):
                counter += 1
                cday = date.fromisoformat(days[2 + n % 4])
                done = n < injected // 2
                mine.append(dict(
                    key="%s-%d" % (b["projectKey"], counter),
                    summary="Unplanned: " + titles[(ix * 3 + n + 7) % len(titles)],
                    type="Bug", status="Done" if done else "In Progress",
                    statusCategory="Done" if done else "In Progress",
                    assignee=b["people"][n % len(b["people"])],
                    storyPoints=[1, 5, 2, 3][n % 4], priority="Highest",
                    epic=b["epics"][n % len(b["epics"])],
                    created=cday.isoformat(), started=cday.isoformat(),
                    resolved=add_wd(cday, 2).isoformat() if done else None,
                    dueDate=add_wd(cday, 3).isoformat(),
                    flagged=False, addedMidSprint=True, businessValue=0,
                    valueBasis="", labels=["unplanned"], contextId=cid))

            # --- the planted findings, on the Storefront board only ---
            if b["boardId"] == "42" and active:
                stuck = mine[6]
                stuck.update(summary="Inventory sync race condition oversells limited stock",
                             epic="Catalogue", priority="Highest", flagged=True,
                             status="In Progress", statusCategory="In Progress",
                             storyPoints=8, resolved=None,
                             created=(date.fromisoformat(AS_OF) - timedelta(days=21)).isoformat(),
                             started=(date.fromisoformat(AS_OF) - timedelta(days=6)).isoformat(),
                             dueDate=(date.fromisoformat(AS_OF) - timedelta(days=3)).isoformat(),
                             labels=["customer-impact", "blocked-external"])
                for k in (8, 9):
                    mine[k].update(flagged=True, resolved=None, statusCategory="In Progress",
                                   status="In Review")
                mine[10].update(started=None, status="To Do", statusCategory="To Do",
                                resolved=None, priority="High",
                                summary="Upgrade the payment SDK before deprecation",
                                created=(date.fromisoformat(AS_OF) - timedelta(days=41)).isoformat())

            issues.extend(mine)
            done_items = [i for i in mine if i["statusCategory"] == "Done"]
            planned_items = [i for i in mine if not i["addedMidSprint"]]

            ctx = dict(
                id=cid, source="jira",
                projectKey=b["projectKey"], projectName=b["projectName"],
                boardId=b["boardId"], boardName=b["boardName"], team=b["team"],
                sprintName="Sprint %d" % num,
                sprintState="active" if active else "closed",
                sprintGoal=b["goal"] if active else "",
                startDate=start.isoformat(), endDate=end.isoformat(),
                asOfDate=as_of, workingDays=days,
                issueCount=len(mine), doneCount=len(done_items))
            contexts.append(ctx)
            board_ctxs.append(ctx)

            # Counted by the fetcher's own derivation rather than a third copy
            # of it, which is what this was. Flow efficiency is the one figure
            # the demo scripts rather than derives — the plan above sets the
            # story it tells — so it is written over the derived one, named
            # here rather than left as a silent difference.
            row = history_row(mine, ctx["sprintName"], ctx["asOfDate"])
            row["flowEfficiency"] = round(1 - b["plan"][ix][3], 2)
            board_hist.append(row)

            by_ctx[cid] = dict(burndown=[], history=[], releases=[], dora=dict(
                deploymentFrequencyPerWeek=11 if b["boardId"] == "42" else 16,
                deploymentFrequencyTrend=[8, 9, 9, 10, 10, 11] if b["boardId"] == "42"
                                         else [12, 13, 14, 15, 15, 16],
                changeFailureRatePct=7 if b["boardId"] == "42" else 4,
                changeFailureRateTrend=[11, 10, 12, 9, 8, 7] if b["boardId"] == "42"
                                       else [7, 6, 6, 5, 5, 4],
                leadTimeForChangesDays=1.1 if b["boardId"] == "42" else 0.6,
                leadTimeForChangesTrend=[1.9, 1.8, 1.6, 1.4, 1.2, 1.1] if b["boardId"] == "42"
                                        else [1.1, 1.0, 0.9, 0.8, 0.7, 0.6],
                mttrMinutes=38 if b["boardId"] == "42" else 21,
                mttrTrend=[66, 58, 61, 47, 42, 38] if b["boardId"] == "42"
                          else [40, 34, 30, 26, 23, 21]))

        for k, ctx in enumerate(board_ctxs):
            by_ctx[ctx["id"]]["history"] = board_hist[max(0, k - 5):k + 1]

        # releases, on the current sprint only
        cur = board_ctxs[-1]
        by_ctx[cur["id"]]["releases"] = (
            [dict(name="v2.2.0", targetDate="2026-08-14", scopeIssues=14, doneIssues=9,
                  status="At Risk", note="Blocked by the inventory sync fix")]
            if b["boardId"] == "42" else
            [dict(name="p1.9", targetDate="2026-08-21", scopeIssues=9, doneIssues=8,
                  status="On Track", note="")])

    active = next(c for c in contexts if c["sprintState"] == "active")
    return dict(
        schemaVersion="2.0",
        meta=dict(organisation="Highpeak", currency="USD",
                  baseUrl="https://highpeak.atlassian.net", source="jira",
                  sourceLabel="Jira — 3 boards, last 6 sprints",
                  generatedAt="2026-08-10T09:15:00Z"),
        contexts=contexts, defaultContextId=active["id"],
        issues=issues, byContext=by_ctx)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/demo-bundle.json")
    a = ap.parse_args()

    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import rebuild_burndown as RB

    b = build()
    for c in b["contexts"]:
        mine = [i for i in b["issues"] if i["contextId"] == c["id"]]
        b["byContext"][c["id"]]["burndown"] = RB.rebuild({"meta": c, "issues": mine})

    p = pathlib.Path(a.out)
    p.write_text(json.dumps(b, separators=(",", ":")) + "\n")
    print("%s — %d contexts, %d issues, %d KB"
          % (p, len(b["contexts"]), len(b["issues"]), p.stat().st_size / 1024))


if __name__ == "__main__":
    main()
