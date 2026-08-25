#!/usr/bin/env python3
"""
metrics.py — the deterministic facts pack.

Everything the reporting agent is allowed to state as fact comes from here.
The agent does not add, subtract, average or estimate. It reads this JSON and
writes prose. That division is the entire trust model: if a number in a report
is wrong, it is wrong in this file and can be fixed here, once, for everyone.

It intentionally duplicates the dashboard's browser-side `derive()`. Two
implementations of the same arithmetic is a liability, so `tests/test_agent.py`
asserts they agree on the sample dataset. If they ever diverge, that test fails
before a report does.

Adds one thing the dashboard cannot: a **diff against the previous snapshot**,
which is what a report is actually about. A dashboard shows a state; a report
has to say what changed since the last one and whether that is good.

    python3 agent/tools/metrics.py data/sample-sprint.json
    python3 agent/tools/metrics.py data/x.json --previous snapshots/2026-08-07.json
"""

from __future__ import annotations

import argparse
import datetime
import json
from collections import defaultdict
from datetime import date, timedelta

import orgconfig as OC


# ------------------------------------------------------------------- helpers
def _d(s):
    return date.fromisoformat(s[:10]) if s else None


def working_days(a, b, cfg=None):
    """Working dates, per the organisation config the dataset carries.

    `cfg=None` is a five-day week with no holidays, which is what was written
    here before the config existed — a file predating it computes as before.
    """
    return OC.working_days(a, b, cfg or OC.DEFAULTS)


def elapsed_days(a, b):
    """CALENDAR days between two dates.

    Deliberately calendar, not working, days — and the rule is worth stating
    because the two tools here use different units on purpose:

      * Anything reported to a human as "how long has this been sitting" is in
        calendar days. An item raised 21 days ago is 21 days old; telling a
        stakeholder it is 15 days old because of weekends is a lie of
        convenience, and it is what the dashboard shows.
      * Anything *simulated* — the Monte Carlo in forecast.py — runs on working
        days, because no work completes on a Saturday. Those outputs are always
        labelled "working days".

    Mixing them silently is how two tools built from one dataset end up
    disagreeing in a meeting. Every figure the agent emits must carry its unit.
    """
    return max((_d(b) - _d(a)).days, 0) if a and b else None


def pct(n, d):
    return round(n / d, 4) if d else 0.0


def _pctile(vals, p):
    if not vals:
        return None
    v = sorted(vals)
    k = (len(v) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (k - lo), 2)


def is_done(i):
    return (i.get("statusCategory") or "") == "Done"


def in_sprint(i, start):
    """Is this issue part of the period being reported on?

    Reporting scope and forecasting scope are NOT the same set, and conflating
    them is a real error rather than a rounding one. The facts pack must count
    only the current period, or "89% complete" appears on a report about a
    sprint that is 55% complete. The forecaster must see everything, because a
    throughput distribution needs months of history to exist at all.

    Rule: an issue belongs to the period unless it was already finished before
    the period began. Anything still open, or closed during it, is in scope.
    """
    if not start:
        return True
    r = i.get("resolved")
    return not (r and _d(r) < _d(start))


# --------------------------------------------------------------------- facts
def facts(ds, previous=None, scope="sprint"):
    meta = ds.get("meta", {})
    # One resolution, from the file, shared by everything below. The dashboard
    # reads the same block out of the same file, which is what keeps this pack
    # and the page from disagreeing about which days were worked.
    cfg = OC.from_dataset(ds)
    as_of = meta.get("asOfDate") or meta.get("endDate") or date.today().isoformat()
    end = meta.get("endDate")
    start = meta.get("startDate")

    all_issues = ds["issues"]
    issues = ([i for i in all_issues if in_sprint(i, start)]
              if scope == "sprint" else list(all_issues))

    done = [i for i in issues if is_done(i)]
    openi = [i for i in issues if not is_done(i)]
    sp = lambda xs: round(sum(x.get("storyPoints") or 0 for x in xs), 1)

    added = [i for i in issues if i.get("addedMidSprint")]
    flagged = [i for i in issues if i.get("flagged")]
    critical = [i for i in openi if str(i.get("priority") or "").lower() in ("highest", "critical", "p1")]
    overdue = [i for i in openi if i.get("dueDate") and _d(i["dueDate"]) < _d(as_of)]
    unstarted = [i for i in openi if not i.get("started")]

    cyc = [elapsed_days(i["started"], i["resolved"]) for i in done if i.get("started") and i.get("resolved")]
    lead = [elapsed_days(i["created"], i["resolved"]) for i in done if i.get("created") and i.get("resolved")]
    cyc = [c for c in cyc if c is not None]
    lead = [l for l in lead if l is not None]

    # --- the flow figures a board without a sprint boundary is read on -------
    #
    # These are computed here rather than in the page for the reason every
    # figure is: the agent quotes, it does not calculate, and a chart whose
    # numbers no tool produced is a chart nobody can check. The page draws the
    # same series from the same issues and `tests/test_agent.py` holds the two
    # to the same answers.
    #
    # None of them needs a sprint. That is not a coincidence — it is why the
    # forecaster worked on a flow board from the start, and why these were
    # available all along rather than something the schema had to grow.

    # Cycle time per closed item, dated, so the scatterplot can be checked
    # against the pack a line at a time and an outlier can be named.
    cycle_items = sorted(
        ({"key": i["key"], "resolved": i["resolved"],
          "days": elapsed_days(i["started"], i["resolved"])}
         for i in done if i.get("started") and i.get("resolved")),
        key=lambda r: (r["resolved"], r["key"]))
    cycle_items = [r for r in cycle_items if r["days"] is not None]

    # Items finished per calendar week, keyed by the Monday. Weeks, not days:
    # a per-day series over a flow board is mostly zeroes and reads as a team
    # that keeps stopping. Zero weeks stay in — the same rule the forecaster's
    # throughput sampling follows, and for the same reason.
    per_week = {}
    finished = sorted(_d(i["resolved"]) for i in done if i.get("resolved"))
    if finished:
        first = finished[0] - datetime.timedelta(days=finished[0].weekday())
        last = finished[-1] - datetime.timedelta(days=finished[-1].weekday())
        w = first
        while w <= last:
            per_week[w.isoformat()] = 0
            w += datetime.timedelta(days=7)
        for r in finished:
            per_week[(r - datetime.timedelta(days=r.weekday())).isoformat()] += 1
    weeks = [{"week_starting": k, "items": v} for k, v in sorted(per_week.items())]

    # Work in progress at the as-of date: started, not yet finished. Derived
    # from dates rather than from status, so it means the same thing on a board
    # whose columns this tool has never seen.
    wip_now = len([i for i in openi if i.get("started")])

    # How the open work is ageing against what finished work actually took.
    # An item past the 85th percentile is late *now*, before it is late.
    cyc_p85 = _pctile(cyc, 85)
    ageing_wip = sorted(
        ({"key": i["key"], "status": i.get("status"),
          "age_days": elapsed_days(i["created"], as_of)}
         for i in openi if i.get("created")),
        key=lambda r: -(r["age_days"] or 0))
    past_p85 = ([r for r in ageing_wip if cyc_p85 is not None and (r["age_days"] or 0) > cyc_p85]
                if cyc_p85 is not None else [])

    # Cumulative flow, at the only granularity this schema can honestly carry.
    # A real CFD has one band per column; the bands below are the three status
    # *categories*, because nothing in a dataset records which column an issue
    # sat in on a given day. Said out loud in `bands`, so a reader who expects
    # seven columns learns why they got three rather than assuming the board
    # has three. The Forge resolver's `statusTransitions` would support the
    # finer version; the Python fetcher does not emit them yet.
    cfd = []
    if all_dates := sorted({d for i in issues for d in
                            (i.get("created"), i.get("started"), i.get("resolved")) if d}):
        span_start, span_end = _d(all_dates[0]), _d(as_of)
        day = span_start
        while day <= span_end:
            iso = day.isoformat()
            todo = ip = dn = 0
            for i in issues:
                c, st, r = i.get("created"), i.get("started"), i.get("resolved")
                if not c or c > iso:
                    continue
                if r and r <= iso:
                    dn += 1
                elif st and st <= iso:
                    ip += 1
                else:
                    todo += 1
            cfd.append({"date": iso, "to_do": todo, "in_progress": ip, "done": dn})
            day += datetime.timedelta(days=1)

    # Little's Law as a reconciliation, not as a prediction and not as a
    # verdict. Work in progress divided by throughput is how long the average
    # item must be spending in progress; measured cycle time is how long the
    # items that *finished* actually took. On a healthy board they land near
    # each other.
    #
    # When they do not, there are two honest readings and this tool does not
    # choose between them: the open work is genuinely sitting far longer than
    # anything that has finished — the case the ageing chart shows by name — or
    # the start dates are not recording when work really began. Both are worth
    # knowing and they are not the same problem, so the two figures are
    # returned side by side and `agrees` says only whether they line up.
    thr_per_day = (sum(w["items"] for w in weeks) / (len(weeks) * 7.0)) if weeks else None
    implied = (wip_now / thr_per_day) if thr_per_day else None
    cyc_p50 = _pctile(cyc, 50)
    littles = {
        "wip_now": wip_now,
        "throughput_items_per_day": round(thr_per_day, 2) if thr_per_day else None,
        "implied_cycle_days": round(implied, 1) if implied else None,
        "measured_cycle_p50": cyc_p50,
        # A factor of two either way. Tighter would fire on ordinary variation;
        # looser would never fire at all.
        "agrees": (None if implied is None or cyc_p50 in (None, 0)
                   else 0.5 <= implied / cyc_p50 <= 2.0),
    }

    wdays = meta.get("workingDays") or [d.isoformat() for d in working_days(_d(start), _d(end), cfg)]
    elapsed = pct(wdays.index(as_of) + 1, len(wdays)) if as_of in wdays else (1.0 if wdays else None)

    ages = {}
    for band, lo, hi in (("0-7", 0, 7), ("8-14", 7, 14), ("15-30", 14, 30), ("30+", 30, 10 ** 6)):
        ages[band] = [i["key"] for i in openi
                      if i.get("created") and lo < (elapsed_days(i["created"], as_of) or 0) <= hi]

    by_person = defaultdict(lambda: {"done": 0, "open": 0, "donePts": 0.0, "openPts": 0.0})
    for i in issues:
        b = by_person[i.get("assignee") or "Unassigned"]
        k = "done" if is_done(i) else "open"
        b[k] += 1
        b[k + "Pts"] = round(b[k + "Pts"] + (i.get("storyPoints") or 0), 1)

    hist = ds.get("history") or []
    last3 = [h.get("completedSP") for h in hist[-4:-1] if h.get("completedSP") is not None]
    last3_items = [h.get("throughput") for h in hist[-4:-1] if h.get("throughput") is not None]
    committed = hist[-1].get("committedSP") if hist else sp([i for i in issues if not i.get("addedMidSprint")])
    committed_items = len([i for i in issues if not i.get("addedMidSprint")])

    valued = [i for i in done if (i.get("businessValue") or 0) > 0]

    f = {
        "meta": {
            "sprint": meta.get("sprintName"),
            "team": meta.get("team"),
            "organisation": meta.get("organisation"),
            "goal": meta.get("sprintGoal"),
            "start": start, "end": end, "as_of": as_of,
            "source": meta.get("sourceLabel"),
            "currency": meta.get("currency", "USD"),
            "scope": scope,
            "issues_in_scope": len(issues),
            "issues_in_file": len(all_issues),
            # Stated, not assumed. Sprint elapsed-percentage below is a share of
            # working days, so the calendar behind it belongs in the pack.
            "calendar": OC.summary(cfg),
        },
        "delivery": {
            "items_total": len(issues), "items_done": len(done),
            "items_done_pct": pct(len(done), len(issues)),
            "points_total": sp(issues), "points_done": sp(done), "points_open": sp(openi),
            "points_done_pct": pct(sp(done), sp(issues)),
            "time_elapsed_pct": elapsed,
            "pace_gap_pts": round(pct(sp(done), sp(issues)) - elapsed, 4) if elapsed is not None else None,
        },
        "scope": {
            "added_items": len(added), "added_points": sp(added),
            "growth_pct": pct(sp(added), sp(issues) - sp(added)),
            "added_keys": [i["key"] for i in added],
        },
        "risk": {
            "unit": "calendar days",
            "blocked": [i["key"] for i in flagged],
            "top_priority_open": [i["key"] for i in critical],
            "overdue": [i["key"] for i in overdue],
            "never_started": [i["key"] for i in unstarted],
            "age_bands": ages,
            "oldest_open": max(
                ({"key": i["key"], "days": elapsed_days(i["created"], as_of)} for i in openi if i.get("created")),
                key=lambda r: r["days"] or 0, default=None),
        },
        "flow": {
            "unit": "calendar days",
            "cycle_p50": _pctile(cyc, 50), "cycle_p85": _pctile(cyc, 85),
            "cycle_p95": _pctile(cyc, 95),
            "lead_p50": _pctile(lead, 50), "lead_p85": _pctile(lead, 85),
            "flow_efficiency": pct(sum(cyc), sum(lead)) if lead and sum(lead) else None,
            "samples": len(cyc),
            "cycle_items": cycle_items,
            "throughput_per_week": weeks,
            "throughput_mean_per_week": (
                round(sum(w["items"] for w in weeks) / len(weeks), 1) if weeks else None),
            "wip_now": wip_now,
            "ageing_wip": ageing_wip,
            "ageing_past_cycle_p85": [r["key"] for r in past_p85],
            "cumulative_flow": {
                "bands": ["to_do", "in_progress", "done"],
                "granularity": "status category",
                "why": ("one band per status category, not per column — no dataset records "
                        "which column an issue sat in on a given day"),
                "series": cfd,
            },
            "littles_law": littles,
        },
        "predictability": {
            # ITEMS is the primary unit. Every forecast and every commitment
            # recommendation is in items, because a throughput distribution needs
            # tens of observations and six sprints only ever supplies six point
            # figures. Points are retained below for continuity with existing
            # reporting — they are not a forecasting input and must never be
            # quoted as one.
            "primary_unit": "items",
            "items": {
                "committed_items": committed_items,
                "completed_items": len(done),
                "trailing_3_sprint_avg_completed_items": (
                    round(sum(last3_items) / len(last3_items), 1) if last3_items else None),
                "commitment_vs_trailing_avg": (
                    round(committed_items / (sum(last3_items) / len(last3_items)) - 1, 3)
                    if last3_items and committed_items else None),
                "hit_rates": [
                    {"sprint": h["sprint"], "completed_items": h.get("throughput")}
                    for h in hist if h.get("throughput") is not None],
                "note": ("For the commitment figure to recommend, use forecast.py's "
                         "recommend_commitment() — a distribution over simulated sprints "
                         "beats a mean of three numbers."),
            },
            "points": {
                "committed_points": committed,
                "trailing_3_sprint_avg_completed": round(sum(last3) / len(last3), 1) if last3 else None,
                "commitment_vs_trailing_avg": (
                    round(committed / (sum(last3) / len(last3)) - 1, 3) if last3 and committed else None),
                "hit_rates": [
                    {"sprint": h["sprint"], "rate": pct(h.get("completedSP") or 0, h.get("committedSP") or 0)}
                    for h in hist],
                "status": "reported for continuity; not a forecasting input",
            },
        },
        "value": {
            "closed_estimate": round(sum(i.get("businessValue") or 0 for i in valued)),
            "items_with_estimate": len(valued),
            "items_without_estimate": len(done) - len(valued),
            "bases": [{"key": i["key"], "amount": i["businessValue"], "basis": i.get("valueBasis") or ""}
                      for i in valued],
        },
        "people": dict(by_person),
        "dora": ds.get("dora"),
        "releases": ds.get("releases") or [],
    }
    f["changes"] = diff(f, previous) if previous else None
    return f


# ---------------------------------------------------------------------- diff
WATCH = [
    ("delivery.items_done", "items completed", 1, "up"),
    ("delivery.points_done", "points completed", 1, "up"),
    ("delivery.pace_gap_pts", "pace against the clock", 0.03, "up"),
    ("scope.added_points", "points added mid-sprint", 1, "down"),
    ("value.closed_estimate", "estimated value closed", 1, "up"),
    ("flow.flow_efficiency", "flow efficiency", 0.03, "up"),
]


def _get(d, path):
    cur = d
    for k in path.split("."):
        cur = (cur or {}).get(k)
    return cur


def diff(now, before):
    """What changed since the previous snapshot, and which direction is good.

    A report that restates the same state every week gets skimmed then ignored.
    Movement, and only movement, is the news.
    """
    out = {"since": (before.get("meta") or {}).get("as_of"), "moved": [], "list_changes": {}}
    for path, label, threshold, good in WATCH:
        a, b = _get(before, path), _get(now, path)
        if a is None or b is None:
            continue
        delta = round(b - a, 4)
        if abs(delta) < threshold:
            continue
        direction = "up" if delta > 0 else "down"
        out["moved"].append({
            "metric": label, "from": a, "to": b, "delta": delta,
            "direction": direction,
            "reading": "better" if direction == good else "worse",
        })
    for key in ("blocked", "top_priority_open", "overdue", "never_started"):
        was = set((before.get("risk") or {}).get(key) or [])
        now_set = set((now.get("risk") or {}).get(key) or [])
        if was != now_set:
            out["list_changes"][key] = {
                "new": sorted(now_set - was),
                "cleared": sorted(was - now_set),
                "still_there": sorted(now_set & was),
            }
    return out


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--previous", help="a previous facts pack, for the change section")
    ap.add_argument("--out", help="write the facts pack here as well as printing it")
    ap.add_argument("--scope", choices=("sprint", "all"), default="sprint",
                    help="'sprint' counts only work not already finished before the sprint "
                         "started (the default, and what a sprint report means); "
                         "'all' counts every row in the file")
    a = ap.parse_args()

    ds = json.load(open(a.dataset))
    prev = json.load(open(a.previous)) if a.previous else None
    f = facts(ds, prev, a.scope)
    text = json.dumps(f, indent=2, default=str)
    if a.out:
        open(a.out, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
