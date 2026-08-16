#!/usr/bin/env python3
"""
make_intake_demo.py — add a history of *finished* epics to the demo bundle.

Why this exists as a separate file rather than a change to make_demo_bundle.py:

The intake forecaster builds its reference class from epics that have finished.
The main demo bundle has none — its epics are long-lived themes ("Payments",
"Checkout Stability") that never close, which is realistic for many boards and
useless for demonstrating reference-class sizing. Adding finished epics to the
main bundle would change its throughput, which would change the delivery
forecast quoted in the demo video and the executive brief.

So this writes a *separate* bundle. The main demo is untouched and its published
figures stay valid; the intake demo gets a board with a real delivery history
behind it.

The epics below are named as deliverables rather than themes, because that is
the shape a reference class needs: things that started, finished, and can be
counted afterwards.

    python3 scripts/make_intake_demo.py
"""

import argparse
import json
import pathlib
import random
from datetime import date, timedelta

# Sixteen finished deliverables on the Storefront board, spread over the year
# before the demo window. Sizes are deliberately skewed — a few small, most
# middling, a long tail — because that is what real epic sizes look like and a
# symmetric spread would make the t-shirt bands meaningless.
FINISHED = [
    ("One-click reorder", 4), ("Basket persistence across devices", 5),
    ("Postcode lookup provider swap", 5), ("Order status webhooks", 6),
    ("Guest checkout revamp", 8), ("Apple Pay rollout", 9),
    ("Promotions engine v2", 11), ("Returns self-service portal", 12),
    ("Address book redesign", 13), ("Fraud screening integration", 15),
    ("PSD2 strong customer authentication", 18), ("Subscriptions billing", 21),
    ("Catalogue re-platform phase 1", 24), ("Multi-currency pricing", 27),
    ("Checkout accessibility programme", 31), ("Warehouse integration rewrite", 38),
]

PEOPLE = ["Alex Rivera", "Priya Nair", "Jordan Lee", "Sam Okafor"]
TYPES = ["Story", "Bug", "Task"]


def add_wd(d, n):
    cur = d
    while n > 0:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            n -= 1
    return cur


def build(bundle, board="42", seed=11):
    rng = random.Random(seed)
    ctxs = [c for c in bundle["contexts"] if str(c.get("boardId")) == str(board)]
    if not ctxs:
        raise SystemExit("board %s not found in the bundle" % board)
    closed = [c for c in ctxs if c.get("sprintState") != "active"]
    if not closed:
        raise SystemExit("no closed sprints on board %s to attach history to" % board)

    # Anchor the history well before the demo window so every epic reads as
    # "stopped growing" — the reference class excludes anything still active.
    window_start = min(date.fromisoformat(c["startDate"]) for c in ctxs)
    key = 9000
    added = []

    for ix, (name, size) in enumerate(FINISHED):
        # spread the epics backwards over the preceding year
        epic_end = window_start - timedelta(days=45 + ix * 19)
        epic_start = epic_end - timedelta(days=rng.randint(14, 70))
        ctx = closed[ix % len(closed)]
        for n in range(size):
            key += 1
            created = epic_start + timedelta(days=rng.randint(0, 6))
            started = add_wd(created, rng.randint(0, 4))
            resolved = add_wd(started, rng.randint(1, 9))
            if resolved > epic_end:
                resolved = epic_end
            added.append({
                "key": "BLC-%d" % key,
                "summary": "%s — part %d" % (name, n + 1),
                "type": rng.choice(TYPES),
                "status": "Done", "statusCategory": "Done",
                "assignee": PEOPLE[n % len(PEOPLE)],
                "storyPoints": rng.choice([1, 2, 3, 3, 5, 5, 8]),
                "priority": "Medium",
                "epic": name,
                "created": created.isoformat(),
                "started": started.isoformat(),
                "resolved": resolved.isoformat(),
                "dueDate": add_wd(created, 10).isoformat(),
                "flagged": False, "addedMidSprint": False,
                "businessValue": 0, "valueBasis": "", "labels": ["delivered"],
                # Tagged to a closed context so context filtering still works,
                # but every date sits before the demo window, so the delivery
                # forecaster's trailing-window throughput is unaffected.
                "contextId": ctx["id"],
            })

    bundle["issues"] = added + bundle["issues"]
    bundle["meta"] = dict(bundle["meta"])
    bundle["meta"]["sourceLabel"] = "Demo — Jira, 3 boards, with delivered epic history"
    for c in ctxs:
        c["issueCount"] = len([i for i in bundle["issues"] if i["contextId"] == c["id"]])
    return bundle, len(added)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/demo-bundle.json")
    ap.add_argument("--out", default="data/demo-intake-bundle.json")
    ap.add_argument("--board", default="42")
    a = ap.parse_args()

    src = pathlib.Path(a.src)
    if not src.exists():
        raise SystemExit("run scripts/make_demo_bundle.py first")
    bundle, n = build(json.loads(src.read_text()), a.board)
    out = pathlib.Path(a.out)
    out.write_text(json.dumps(bundle, separators=(",", ":")) + "\n")
    print("%s — added %d issues across %d finished epics on board %s (%d KB)"
          % (out, n, len(FINISHED), a.board, out.stat().st_size / 1024))


if __name__ == "__main__":
    main()
