#!/usr/bin/env python3
"""
forecast.py — the deterministic forecasting engine.

The agent NEVER computes a forecast. It calls this, quotes the numbers, and
explains them. Every function here is pure, seeded, and testable, so the same
question asked twice gives the same answer — which is the whole basis on which
anyone will believe a forecast that came out of a language model.

Method: Monte Carlo over historical **item throughput**, not story points.

Why not points: six sprints of history is six data points. Six observations
cannot support a distribution. The same six sprints contain roughly sixty
completed items, and counting items per day gives thirty to sixty observations
— enough to sample from. Item-count forecasting also sidesteps estimate
inflation entirely, since it never reads an estimate.

    python3 agent/tools/forecast.py data/sample-sprint.json --remaining 10
    python3 agent/tools/forecast.py data/sample-sprint.json --json
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Optional

# ---------------------------------------------------------------- thresholds
# Below these, the honest answer is "not enough data", not a wider interval.
MIN_THROUGHPUT_SAMPLES = 8      # distinct periods with an observation
MIN_COMPLETED_ITEMS = 10        # items with a resolution date
MIN_CYCLE_SAMPLES = 6           # items with both a start and a resolution
TRIALS = 20_000
# How far a single simulated trial is allowed to run before it is abandoned.
# A trial that hits this has not finished, and saying so matters: without it
# every percentile reads exactly HORIZON and looks like an answer. Reported as
# unfinished_fraction, and named in the basis line whenever it is not zero.
HORIZON = 400                   # working days
SEED = 20260816                 # fixed: same inputs must give the same answer
PERCENTILES = (50, 70, 85, 95)


# ---------------------------------------------------------------- structures
@dataclass
class Refusal:
    """Returned instead of a forecast when the data cannot support one.
    The agent must surface this verbatim rather than paraphrasing around it."""
    available: bool = False
    reason: str = ""
    have: int = 0
    need: int = 0

    def sentence(self) -> str:
        return ("No forecast: %s (%d observations, %d needed). "
                "A wider confidence interval would not fix this — the data is absent, not noisy."
                % (self.reason, self.have, self.need))


@dataclass
class DateForecast:
    available: bool = True
    remaining_items: int = 0
    percentiles: dict = field(default_factory=dict)   # {85: "2026-08-19"}
    days: dict = field(default_factory=dict)          # {85: 7}
    prob_by_target: Optional[float] = None
    target_date: Optional[str] = None
    scope_growth_applied: float = 0.0
    samples: int = 0
    method: str = "monte-carlo-throughput"
    basis: str = ""
    # Share of trials that ran out of simulated horizon without finishing. Any
    # value above zero means these dates are a floor, not an estimate — see
    # HORIZON below.
    unfinished_fraction: float = 0.0


@dataclass
class CountForecast:
    available: bool = True
    horizon_days: int = 0
    target_date: str = ""
    percentiles: dict = field(default_factory=dict)   # {85: 6} items
    samples: int = 0
    method: str = "monte-carlo-throughput"
    basis: str = ""


# ---------------------------------------------------------------- date utils
def _d(s):
    return date.fromisoformat(s[:10]) if s else None


def working_days(start: date, end: date):
    out, cur = [], start
    while cur <= end:
        if cur.weekday() < 5:
            out.append(cur)
        cur += timedelta(days=1)
    return out


def add_working_days(start: date, n: int) -> date:
    cur, left = start, n
    while left > 0:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            left -= 1
    return cur


def _pct(sorted_vals, p):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


# ---------------------------------------------------------- sample extraction
def throughput_samples(issues, window_days: int = 90, as_of: Optional[str] = None):
    """Items completed per working day over the trailing window.

    Zero-throughput days are included deliberately. Dropping them is the most
    common way a Monte Carlo forecast turns optimistic: real teams have days
    where nothing finishes, and a model that never samples zero will never
    predict a stall.
    """
    resolved = [_d(i["resolved"]) for i in issues if i.get("resolved")]
    resolved = [r for r in resolved if r]
    if not resolved:
        return []
    end = _d(as_of) if as_of else max(resolved)
    start = max(min(resolved), end - timedelta(days=window_days))
    per_day = Counter(resolved)
    return [per_day.get(day, 0) for day in working_days(start, end)]


def full_history_days(issues, as_of: Optional[str] = None) -> int:
    """Every day of imported history, for callers that want the whole record
    rather than the trailing window.

    The 90-day default above is right for "how is this team going lately". It is
    wrong when the question is "use everything we have", because it discards
    older sprints silently — a smaller sample, and one that can drop under the
    refusal thresholds for no stated reason. Callers that want the full record
    ask for it explicitly and report the span they used.
    """
    resolved = [_d(i["resolved"]) for i in issues if i.get("resolved")]
    resolved = [r for r in resolved if r]
    if not resolved:
        return 0
    end = _d(as_of) if as_of else max(resolved)
    return max((end - min(resolved)).days, 0)


def cycle_times(issues):
    """Active working days from start to resolution, for completed items."""
    out = []
    for i in issues:
        s, r = _d(i.get("started")), _d(i.get("resolved"))
        if s and r and r >= s:
            out.append(len(working_days(s, r)))
    return sorted(out)


def lead_times(issues):
    """Working days from creation to resolution, for completed items.

    Kept separate from cycle time on purpose. The dashboard ages open work from
    its creation date; this module's cycle risk measures from the start date.
    They answer different questions and will disagree — so the agent reports
    both rather than letting a reader discover the discrepancy themselves.
    """
    out = []
    for i in issues:
        c, r = _d(i.get("created")), _d(i.get("resolved"))
        if c and r and r >= c:
            out.append(len(working_days(c, r)))
    return sorted(out)


def scope_growth_history(snapshots):
    """Historical mid-sprint scope growth, as a multiplier per period.

    Needs the snapshot archive (see docs/forecasting-agent.md § data contract).
    Without it, forecasts assume scope is frozen — which it never is, so the
    agent must say so rather than quietly under-forecasting.
    """
    out = []
    for s in snapshots or []:
        base = s.get("committedItems") or 0
        added = s.get("addedItems") or 0
        if base:
            out.append(1.0 + added / base)
    return out


# --------------------------------------------------------------- the forecast
def forecast_completion(remaining_items: int,
                        samples,
                        start_from: str,
                        target_date: Optional[str] = None,
                        scope_growth=None,
                        trials: int = TRIALS,
                        seed: int = SEED):
    """When will `remaining_items` be finished? Percentiles, not a date."""
    if len(samples) < MIN_THROUGHPUT_SAMPLES or sum(samples) < MIN_COMPLETED_ITEMS:
        return Refusal(reason="too little completion history to sample from",
                       have=sum(samples), need=MIN_COMPLETED_ITEMS)
    if remaining_items <= 0:
        return Refusal(reason="nothing is outstanding", have=0, need=1)
    if all(v == 0 for v in samples):
        return Refusal(reason="nothing has completed in the observed window",
                       have=0, need=MIN_COMPLETED_ITEMS)

    rng = random.Random(seed)
    growth = list(scope_growth or [])
    day_counts, unfinished = [], 0

    for _ in range(trials):
        target = remaining_items
        if growth:
            target = target * rng.choice(growth)
        done, days = 0.0, 0
        while done < target and days < HORIZON:
            done += rng.choice(samples)
            days += 1
        if done < target:
            unfinished += 1
        day_counts.append(days)

    day_counts.sort()
    begin = _d(start_from)
    pcts = {p: int(round(_pct(day_counts, p))) for p in PERCENTILES}
    fc = DateForecast(
        remaining_items=remaining_items,
        days=pcts,
        percentiles={p: add_working_days(begin, n).isoformat() for p, n in pcts.items()},
        scope_growth_applied=(statistics.mean(growth) - 1.0) if growth else 0.0,
        samples=len(samples),
        unfinished_fraction=round(unfinished / float(trials), 4),
        basis=("%d working-day observations, %d items completed in the window%s%s"
               % (len(samples), sum(samples),
                  "; historical scope growth applied" if growth else
                  "; scope assumed frozen (no snapshot history available)",
                  ("; %.0f%% of simulations had not finished within the %d working-day "
                   "horizon, so these dates are a floor rather than an estimate"
                   % (100.0 * unfinished / float(trials), HORIZON)) if unfinished else "")),
    )
    if target_date:
        budget = len(working_days(begin, _d(target_date))) - 1
        fc.target_date = target_date
        fc.prob_by_target = round(sum(1 for d in day_counts if d <= budget) / len(day_counts), 3)
    return fc


def forecast_count_by_date(samples, start_from: str, target_date: str,
                           trials: int = TRIALS, seed: int = SEED):
    """How much will be finished by a fixed date? The capacity question."""
    if len(samples) < MIN_THROUGHPUT_SAMPLES or sum(samples) < MIN_COMPLETED_ITEMS:
        return Refusal(reason="too little completion history to sample from",
                       have=sum(samples), need=MIN_COMPLETED_ITEMS)
    begin, end = _d(start_from), _d(target_date)
    horizon = max(len(working_days(begin, end)) - 1, 0)
    if horizon <= 0:
        return Refusal(reason="the target date is not in the future", have=0, need=1)

    rng = random.Random(seed)
    totals = sorted(sum(rng.choice(samples) for _ in range(horizon)) for _ in range(trials))
    # Percentiles are inverted here: p95 is the PESSIMISTIC end for a date
    # forecast but the OPTIMISTIC end for a count. Report the low tail as the
    # commitment-safe number.
    return CountForecast(
        horizon_days=horizon,
        target_date=target_date,
        percentiles={p: int(round(_pct(totals, 100 - p))) for p in PERCENTILES},
        samples=len(samples),
        basis="%d working days remaining; %d working-day observations sampled"
              % (horizon, len(samples)),
    )


def item_risk(issues, as_of: str):
    """Per-item completion risk from the empirical cycle-time distribution.

    For each open, started item: of historically completed items, what share
    took longer than this one already has? That share is a crude survival
    estimate — low means the item is well past normal and unlikely to finish
    without intervention. It is not a hazard model and must not be described
    as a probability of completion.
    """
    cyc = cycle_times(issues)
    lead = lead_times(issues)
    if len(cyc) < MIN_CYCLE_SAMPLES:
        return Refusal(reason="too few items with both a start and an end date",
                       have=len(cyc), need=MIN_CYCLE_SAMPLES)

    p50, p85 = _pct(cyc, 50), _pct(cyc, 85)
    l50, l85 = (_pct(lead, 50), _pct(lead, 85)) if lead else (None, None)
    today = _d(as_of)
    rows = []
    for i in issues:
        if (i.get("statusCategory") or "") == "Done":
            continue
        s, c = _d(i.get("started")), _d(i.get("created"))
        active = (len(working_days(s, today)) - 1) if s else None
        alive = (len(working_days(c, today)) - 1) if c else None
        if active is None and alive is None:
            continue
        longer = (sum(1 for v in cyc if v > active) / len(cyc)) if active is not None else None
        longer_lead = (sum(1 for v in lead if v > alive) / len(lead)) if (alive is not None and lead) else None
        past_cycle = active is not None and active > p85
        past_lead = alive is not None and l85 is not None and alive > l85
        rows.append({
            "key": i["key"],
            "summary": i.get("summary", ""),
            "assignee": i.get("assignee"),
            "started": i.get("started"),
            "active_days": active,
            "alive_days": alive,
            "share_of_past_items_that_took_longer_once_started": (
                round(longer, 3) if longer is not None else None),
            "share_of_past_items_that_took_longer_end_to_end": (
                round(longer_lead, 3) if longer_lead is not None else None),
            "past_p85_active": past_cycle,
            "past_p85_end_to_end": past_lead,
            "verdict": (
                "never started — it cannot be forecast, only scheduled" if active is None else
                "beyond the 85th percentile of active time on anything this team has finished"
                if past_cycle else
                "active time is normal, but it has been alive longer than 85% of finished work "
                "— the delay is upstream of the team, not inside it" if past_lead else
                "past the typical item" if active > p50 else "within normal range"),
        })
    rows.sort(key=lambda r: -((r["alive_days"] or 0)))
    return {
        "available": True,
        "cycle_p50_days": round(p50, 1),
        "cycle_p85_days": round(p85, 1),
        "lead_p50_days": round(l50, 1) if l50 is not None else None,
        "lead_p85_days": round(l85, 1) if l85 is not None else None,
        "samples": len(cyc),
        "items": rows,
        "basis": ("empirical cycle times of %d completed items; end-to-end times of %d"
                  % (len(cyc), len(lead))),
        "note": ("Active time measures from the start date; end-to-end measures from creation. "
                 "The dashboard's ageing chart uses the end-to-end measure. When the two "
                 "disagree, the gap is queue time and that is the finding."),
    }


def recommend_commitment(samples, sprint_working_days: int,
                         trials: int = TRIALS, seed: int = SEED):
    """How many items can this team commit to in a sprint, and at what confidence?

    This replaces "commit to the trailing three-sprint average in points". A
    points average is a mean of six numbers; this is a distribution over
    thousands of simulated sprints, in the same unit the forecast uses.

    The number to commit to is the **85% figure**, not the 50%. Committing at
    the median means missing the commitment half the time by construction, and
    a team that misses half its commitments stops being believed regardless of
    how much it delivers.
    """
    if len(samples) < MIN_THROUGHPUT_SAMPLES or sum(samples) < MIN_COMPLETED_ITEMS:
        return Refusal(reason="too little completion history to size a commitment",
                       have=sum(samples), need=MIN_COMPLETED_ITEMS)
    if sprint_working_days <= 0:
        return Refusal(reason="sprint length is unknown", have=0, need=1)

    rng = random.Random(seed)
    totals = sorted(sum(rng.choice(samples) for _ in range(sprint_working_days))
                    for _ in range(trials))
    return {
        "available": True,
        "unit": "items",
        "sprint_working_days": sprint_working_days,
        "commit_at": {p: int(_pct(totals, 100 - p)) for p in PERCENTILES},
        "recommended": int(_pct(totals, 15)),          # the 85%-confidence figure
        "stretch_median": int(_pct(totals, 50)),
        "samples": len(samples),
        "basis": ("%d simulated sprints of %d working days, sampling %d observed days"
                  % (trials, sprint_working_days, len(samples))),
        "note": ("Commit to the 85% figure. The median is a coin flip by construction — "
                 "a team that misses half its commitments stops being believed."),
    }


def size_stability(issues, as_of=None, window_days: int = 120):
    """Is item-count forecasting still safe for this team?

    Counting items assumes items are roughly interchangeable in size. That
    assumption is the method's one real weakness, and it breaks in a specific,
    detectable way: a team starts splitting work smaller, throughput rises, and
    the forecast reads it as the team getting faster. Nothing got faster. The
    unit shrank.

    Two checks:
      1. **Drift.** Compare the first and second half of the window. If median
         cycle time fell materially WHILE throughput rose, the gain is splitting,
         not speed, and any forecast built on the newer rate is optimistic.
      2. **Spread.** p85/p50 of cycle time. Above about 4, items vary so widely
         that one of them is worth five of another, and item counting loses its
         meaning regardless of drift.
    """
    done = [i for i in issues if i.get("resolved") and i.get("started")]
    if len(done) < MIN_CYCLE_SAMPLES * 2:
        return Refusal(reason="too few completed items to test size stability",
                       have=len(done), need=MIN_CYCLE_SAMPLES * 2)

    end = _d(as_of) if as_of else max(_d(i["resolved"]) for i in done)
    start = end - timedelta(days=window_days)
    inwin = sorted([i for i in done if start <= _d(i["resolved"]) <= end],
                   key=lambda i: i["resolved"])
    if len(inwin) < MIN_CYCLE_SAMPLES * 2:
        return Refusal(reason="too few completed items inside the window",
                       have=len(inwin), need=MIN_CYCLE_SAMPLES * 2)

    mid = len(inwin) // 2
    halves = (inwin[:mid], inwin[mid:])
    stats = []
    for half in halves:
        cyc = sorted(len(working_days(_d(i["started"]), _d(i["resolved"]))) for i in half)
        span = max(1, len(working_days(_d(half[0]["resolved"]), _d(half[-1]["resolved"]))))
        stats.append({"n": len(half), "median_cycle": _pct(cyc, 50),
                      "p85_cycle": _pct(cyc, 85), "items_per_day": round(len(half) / span, 3)})
    a, b = stats
    cycle_change = (b["median_cycle"] - a["median_cycle"]) / a["median_cycle"] if a["median_cycle"] else 0
    rate_change = (b["items_per_day"] - a["items_per_day"]) / a["items_per_day"] if a["items_per_day"] else 0

    all_cyc = sorted(len(working_days(_d(i["started"]), _d(i["resolved"]))) for i in inwin)
    p50, p85 = _pct(all_cyc, 50), _pct(all_cyc, 85)
    spread = (p85 / p50) if p50 else None

    warnings = []
    if cycle_change <= -0.30 and rate_change >= 0.20:
        warnings.append(
            "Median cycle time fell %d%% while throughput rose %d%%. The apparent speed-up is "
            "most likely items being split smaller, not work going faster — treat any forecast "
            "built on the recent rate as optimistic and re-baseline."
            % (round(-cycle_change * 100), round(rate_change * 100)))
    if cycle_change >= 0.40:
        warnings.append(
            "Median cycle time rose %d%% across the window. Item counting still works, but the "
            "older half of the sample no longer describes how this team behaves."
            % round(cycle_change * 100))
    if spread and spread > 4:
        warnings.append(
            "Cycle time p85 is %.1fx the median. Items vary so widely that one is worth several "
            "of another, and counting them treats those as equal. Right-size the backlog before "
            "leaning on these forecasts." % spread)

    return {
        "available": True,
        "unit": "working days",
        "window_days": window_days,
        "items_examined": len(inwin),
        "earlier_half": a, "later_half": b,
        "median_cycle_change": round(cycle_change, 3),
        "throughput_change": round(rate_change, 3),
        "p85_over_p50": round(spread, 2) if spread else None,
        "safe_to_count_items": not warnings,
        "warnings": warnings,
        "basis": "%d completed items, split into two halves by resolution date" % len(inwin),
    }


# ------------------------------------------------------------- calibration
def score_calibration(forecast_log):
    """Score past forecasts against what actually happened.

    Without this the agent is unfalsifiable, and an unfalsifiable forecaster is
    a horoscope. Every published forecast is appended to the log with its
    probability and its resolution criterion; this reads back the resolved ones.

    Each entry: {"probability": 0.85, "resolved": true/false, "label": "..."}
    """
    resolved = [e for e in forecast_log if e.get("resolved") is not None]
    if len(resolved) < 10:
        return Refusal(reason="too few resolved forecasts to score calibration",
                       have=len(resolved), need=10)

    brier = sum((e["probability"] - (1.0 if e["resolved"] else 0.0)) ** 2
                for e in resolved) / len(resolved)
    buckets = {}
    for e in resolved:
        b = min(int(e["probability"] * 10) * 10, 90)
        buckets.setdefault(b, []).append(1 if e["resolved"] else 0)

    return {
        "available": True,
        "n": len(resolved),
        "brier_score": round(brier, 4),
        "interpretation": ("well calibrated" if brier <= 0.12 else
                           "usable but drifting" if brier <= 0.20 else
                           "not calibrated — stop quoting probabilities until this is fixed"),
        "buckets": [
            {"stated": "%d–%d%%" % (b, b + 9),
             "actual": round(sum(v) / len(v), 3),
             "n": len(v),
             "bias": ("over-confident" if sum(v) / len(v) < b / 100.0 - 0.1 else
                      "under-confident" if sum(v) / len(v) > (b + 10) / 100.0 else
                      "on target")}
            for b, v in sorted(buckets.items())
        ],
    }


# ------------------------------------------------------------------ assembly
def build(dataset, as_of=None, remaining=None, target=None, snapshots=None,
          window_days=None):
    """window_days=None means every day of imported history, which is the
    default here because a forecast should use the whole record it was given.
    Pass an integer to restrict it. The window actually used is reported in
    `inputs`, so a wide sample is visible rather than implied."""
    issues = dataset["issues"]
    meta = dataset.get("meta", {})
    as_of = as_of or meta.get("asOfDate") or date.today().isoformat()
    target = target or meta.get("endDate")
    open_items = [i for i in issues if (i.get("statusCategory") or "") != "Done"]
    remaining = remaining if remaining is not None else len(open_items)

    if window_days is None:
        window_days = full_history_days(issues, as_of)
    samples = throughput_samples(issues, window_days=window_days, as_of=as_of)
    growth = scope_growth_history(snapshots)

    def out(x):
        return asdict(x) if hasattr(x, "__dataclass_fields__") else x

    return {
        "generated_for": meta.get("sprintName"),
        "as_of": as_of,
        "inputs": {
            "open_items": len(open_items),
            "throughput_observations": len(samples),
            "items_completed_in_window": sum(samples),
            "window_days": window_days,
            "scope_growth_samples": len(growth),
        },
        "sprint_completion": out(forecast_completion(
            remaining, samples, as_of, target_date=target, scope_growth=growth)),
        "capacity_to_target": out(forecast_count_by_date(samples, as_of, target))
        if target and target > as_of else
        out(Refusal(reason="the target date has passed", have=0, need=1)),
        "item_risk": out(item_risk(issues, as_of)),
        "next_commitment": out(recommend_commitment(
            samples, len(meta.get("workingDays") or working_days(
                _d(meta.get("startDate")), _d(meta.get("endDate")))) or 10)),
        "size_stability": out(size_stability(issues, as_of)),
        "releases": [
            {"name": r["name"], "target": r["targetDate"],
             "forecast": out(forecast_completion(
                 max((r.get("scopeIssues") or 0) - (r.get("doneIssues") or 0), 0),
                 samples, as_of, target_date=r["targetDate"], scope_growth=growth))}
            for r in dataset.get("releases", [])
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--as-of")
    ap.add_argument("--remaining", type=int)
    ap.add_argument("--target")
    ap.add_argument("--snapshots", help="JSON array of per-sprint scope snapshots")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args()

    ds = json.load(open(a.dataset))
    snaps = json.load(open(a.snapshots)) if a.snapshots else None
    res = build(ds, a.as_of, a.remaining, a.target, snaps)

    if a.json:
        print(json.dumps(res, indent=2))
        return

    print("Forecast for %s, as at %s" % (res["generated_for"], res["as_of"]))
    print("  inputs: %(open_items)d open, %(throughput_observations)d day observations, "
          "%(items_completed_in_window)d completed in window" % res["inputs"])
    sc = res["sprint_completion"]
    if not sc.get("available"):
        print("  " + Refusal(**{k: v for k, v in sc.items() if k in
                               ("available", "reason", "have", "need")}).sentence())
    else:
        print("  finishing %d open items:" % sc["remaining_items"])
        for p in PERCENTILES:
            print("    %2d%% by %s  (%d working days)" % (p, sc["percentiles"][str(p)]
                  if str(p) in sc["percentiles"] else sc["percentiles"][p],
                  sc["days"][str(p)] if str(p) in sc["days"] else sc["days"][p]))
        if sc.get("prob_by_target") is not None:
            print("    probability all of it lands by %s: %.0f%%"
                  % (sc["target_date"], sc["prob_by_target"] * 100))
    cap = res["capacity_to_target"]
    if cap.get("available"):
        print("  items expected complete by %s:" % cap["target_date"])
        for p in PERCENTILES:
            v = cap["percentiles"][str(p)] if str(p) in cap["percentiles"] else cap["percentiles"][p]
            print("    %2d%% confidence of at least %d items" % (p, v))
    nc = res["next_commitment"]
    if nc.get("available"):
        print("  next sprint commitment (%d working days):" % nc["sprint_working_days"])
        print("    recommend %d items at 85%% confidence (median would be %d — a coin flip)"
              % (nc["recommended"], nc["stretch_median"]))
    ss = res["size_stability"]
    if ss.get("available"):
        print("  size stability: %s (p85/p50 = %s, cycle drift %+.0f%%, throughput %+.0f%%)"
              % ("item counting is safe" if ss["safe_to_count_items"] else "SUSPECT",
                 ss["p85_over_p50"], ss["median_cycle_change"] * 100, ss["throughput_change"] * 100))
        for w in ss["warnings"]:
            print("    ! " + w)
    ir = res["item_risk"]
    if ir.get("available"):
        late = [r for r in ir["items"] if r["past_p85_active"] or r["past_p85_end_to_end"]]
        print("  active time p50 %.1fd / p85 %.1fd · end-to-end p50 %sd / p85 %sd"
              % (ir["cycle_p50_days"], ir["cycle_p85_days"],
                 ir["lead_p50_days"], ir["lead_p85_days"]))
        print("  %d open item(s) beyond the 85th percentile on at least one measure:" % len(late))
        for r in late[:6]:
            print("    %-9s active %s / alive %s — %s"
                  % (r["key"],
                     ("%dd" % r["active_days"]) if r["active_days"] is not None else "never",
                     ("%dd" % r["alive_days"]) if r["alive_days"] is not None else "?",
                     r["verdict"]))


if __name__ == "__main__":
    main()
