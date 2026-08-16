#!/usr/bin/env python3
"""
rebuild_burndown.py — recompute a dataset's burndown in BOTH units from its issues.

The burndown in a hand-authored dataset drifts from the issues underneath it.
This regenerates it so the chart and the issue list cannot disagree, and emits
item counts alongside story points so the dashboard's unit toggle has something
to switch to.

Mirrors the algorithm in src/import.js (buildBurndown) and
scripts/fetch_delivery_data.py (build_burndown). If you change one, change all
three — tests/test_agent.py pins them to the same answer.

    python3 scripts/rebuild_burndown.py data/sample-sprint.json
"""

import argparse
import json
import pathlib
from collections import defaultdict
from datetime import date, timedelta


def _d(s):
    return date.fromisoformat(s[:10]) if s else None


def working_days(a, b):
    out, cur = [], a
    while cur <= b:
        if cur.weekday() < 5:
            out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def in_sprint(i, start):
    """Same rule as the facts pack: in scope unless finished before the start."""
    r = i.get("resolved")
    return not (start and r and _d(r) < _d(start))


def rebuild(ds):
    meta = ds["meta"]
    start, end = meta.get("startDate"), meta.get("endDate")
    as_of = meta.get("asOfDate") or end
    days = meta.get("workingDays") or working_days(_d(start), _d(end))
    if not days:
        return []

    issues = [i for i in ds["issues"] if in_sprint(i, start)]

    def base(unit):
        return sum((i.get("storyPoints") or 0) if unit == "points" else 1
                   for i in issues if not i.get("addedMidSprint"))

    added, done = {}, {}
    for i in issues:
        pts = i.get("storyPoints") or 0
        if i.get("addedMidSprint") and i.get("created"):
            a = added.setdefault(i["created"], [0, 0])
            a[0] += pts
            a[1] += 1
        if i.get("resolved"):
            r = done.setdefault(i["resolved"], [0, 0])
            r[0] += pts
            r[1] += 1

    baseP, baseI = base("points"), base("items")
    scopeP, scopeI, remP, remI = baseP, baseI, baseP, baseI
    n = len(days)
    out = []
    for k, day in enumerate(days):
        prev = days[k - 1] if k else None
        for d0, (p, c) in added.items():
            if d0 <= day and (prev is None or d0 > prev):
                scopeP += p; remP += p
                scopeI += c; remI += c
        for d0, (p, c) in done.items():
            if d0 <= day and (prev is None or d0 > prev):
                remP -= p
                remI -= c
        future = day > as_of
        frac = (1 - k / (n - 1)) if n > 1 else 0
        out.append({
            "date": day,
            "remainingSP": None if future else round(remP, 1),
            "scopeSP": None if future else round(scopeP, 1),
            "idealSP": round(baseP * frac, 1),
            "remainingItems": None if future else remI,
            "scopeItems": None if future else scopeI,
            "idealItems": round(baseI * frac, 1),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("datasets", nargs="+")
    a = ap.parse_args()
    for path in a.datasets:
        p = pathlib.Path(path)
        ds = json.loads(p.read_text())
        ds["burndown"] = rebuild(ds)
        p.write_text(json.dumps(ds, indent=1) + "\n")
        last = [b for b in ds["burndown"] if b["remainingItems"] is not None][-1]
        print("%s — %d days; at %s: %s items / %s points remaining"
              % (p.name, len(ds["burndown"]), last["date"],
                 last["remainingItems"], last["remainingSP"]))


if __name__ == "__main__":
    main()
