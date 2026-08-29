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

import orgconfig as OC

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


# Working days come from the organisation config that travels in the dataset,
# not from a rule written here. `cfg=None` means the defaults — a five-day week
# and no holidays — so a file predating the config forecasts exactly as before.
#
# The config is threaded explicitly through every function that needs it rather
# than held in module state. This module is imported by a long-lived server that
# serves more than one dataset, and a forecast built with the previous request's
# calendar is the kind of wrong answer that looks completely right.
def working_days(start: date, end: date, cfg=None):
    return OC.working_days(start, end, cfg or OC.DEFAULTS)


def add_working_days(start: date, n: int, cfg=None) -> date:
    return OC.add_working_days(start, n, cfg or OC.DEFAULTS)


def _pct(sorted_vals, p):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


# ---------------------------------------------------------- sample extraction
def throughput_samples(issues, window_days: int = 90, as_of: Optional[str] = None, cfg=None):
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
    return [per_day.get(day, 0) for day in working_days(start, end, cfg)]


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


def cycle_times(issues, cfg=None):
    """Active working days from start to resolution, for completed items."""
    out = []
    for i in issues:
        s, r = _d(i.get("started")), _d(i.get("resolved"))
        if s and r and r >= s:
            out.append(len(working_days(s, r, cfg)))
    return sorted(out)


def lead_times(issues, cfg=None):
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
            out.append(len(working_days(c, r, cfg)))
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
                        seed: int = SEED,
                        cfg=None):
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
        percentiles={p: add_working_days(begin, n, cfg).isoformat() for p, n in pcts.items()},
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
        budget = len(working_days(begin, _d(target_date), cfg)) - 1
        fc.target_date = target_date
        fc.prob_by_target = round(sum(1 for d in day_counts if d <= budget) / len(day_counts), 3)
    return fc


def forecast_count_by_date(samples, start_from: str, target_date: str,
                           trials: int = TRIALS, seed: int = SEED, cfg=None):
    """How much will be finished by a fixed date? The capacity question."""
    if len(samples) < MIN_THROUGHPUT_SAMPLES or sum(samples) < MIN_COMPLETED_ITEMS:
        return Refusal(reason="too little completion history to sample from",
                       have=sum(samples), need=MIN_COMPLETED_ITEMS)
    begin, end = _d(start_from), _d(target_date)
    horizon = max(len(working_days(begin, end, cfg)) - 1, 0)
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


def item_risk(issues, as_of: str, cfg=None):
    """Per-item completion risk from the empirical cycle-time distribution.

    For each open, started item: of historically completed items, what share
    took longer than this one already has? That share is a crude survival
    estimate — low means the item is well past normal and unlikely to finish
    without intervention. It is not a hazard model and must not be described
    as a probability of completion.
    """
    cyc = cycle_times(issues, cfg)
    lead = lead_times(issues, cfg)
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
        active = (len(working_days(s, today, cfg)) - 1) if s else None
        alive = (len(working_days(c, today, cfg)) - 1) if c else None
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


def size_stability(issues, as_of=None, window_days: int = 120, cfg=None):
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
        cyc = sorted(len(working_days(_d(i["started"]), _d(i["resolved"]), cfg)) for i in half)
        span = max(1, len(working_days(_d(half[0]["resolved"]), _d(half[-1]["resolved"]), cfg)))
        stats.append({"n": len(half), "median_cycle": _pct(cyc, 50),
                      "p85_cycle": _pct(cyc, 85), "items_per_day": round(len(half) / span, 3)})
    a, b = stats
    cycle_change = (b["median_cycle"] - a["median_cycle"]) / a["median_cycle"] if a["median_cycle"] else 0
    rate_change = (b["items_per_day"] - a["items_per_day"]) / a["items_per_day"] if a["items_per_day"] else 0

    all_cyc = sorted(len(working_days(_d(i["started"]), _d(i["resolved"]), cfg)) for i in inwin)
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
# ---------------------------------------------------------------- the log
#
# Roadmap item 4c. `score_calibration()` below has been able to read a forecast
# log since the tools were written and nothing has ever produced one, so the
# forecaster has never been scored against its own history. ADR 0017 has the
# argument; the short version is that an unfalsifiable forecaster is a
# horoscope, and the only thing standing between this one and falsifiability is
# somebody writing down what it said.
#
# **What is logged is the capacity answer, not the completion probability.**
# `forecast_completion` produces "probability all of it lands by the 14th",
# which is the more natural-sounding claim and the one that cannot be resolved
# without knowing *which* items were outstanding when it was made. Recording
# issue keys would put customer-identifiable data in an app-level store and put
# item 4 on item 5's critical path, which is the thing 4a was careful to avoid.
#
# `forecast_count_by_date` states "p% confidence of at least N items by D",
# which resolves from a count of completions in a window and needs no issue
# identity at all. It also yields four claims per forecast rather than one, at
# four separated probabilities, which is what calibration bucketing wants.

#: The only fields a logged claim carries. An allow-list, for the reason the
#: series store has one: this is assembled from something derived from issues,
#: and a deny-list is one upstream change away from putting an issue summary
#: into it. Nothing here identifies an issue or a person.
CLAIM_FIELDS = ("id", "contextId", "boardId", "madeOn", "horizon", "kind",
                "probability", "claimItems", "label", "resolved", "observed",
                "seed", "trials")


def claim_id(context_id, made_on, percentile):
    """Deterministic, so re-publishing the same forecast does not duplicate it.

    A panel load produces a forecast; so does the next one, and the weekly
    brief, and a reader refreshing the tab. Keyed on what makes a claim the
    same claim — the context, the day it was made, and which percentile it is —
    an idempotent writer can skip one it already holds instead of scoring the
    same prediction eleven times and calling it eleven observations.
    """
    return "%s|%s|p%d" % (context_id, made_on, int(percentile))


def claims_from(capacity, context_id, board_id, made_on, label_board=None):
    """The falsifiable claims one published capacity forecast makes.

    `capacity` is what `forecast_count_by_date` returned — or a refusal, in
    which case there is nothing to log and nothing is logged. A forecast that
    declined to state a figure made no claim, and recording it as one would
    score the forecaster on predictions it explicitly refused to make.

    One entry per percentile, each independently resolvable. They are not
    independent *events* — the same fortnight decides all four — and
    `score_calibration` treats them as separate observations, which slightly
    overstates `n`. Said here rather than hidden: the alternative is one claim
    per forecast, which needs four times as long to reach the ten resolved
    entries the scorer requires, and a Brier score over correlated observations
    is still a great deal better than no score at all.
    """
    if not capacity or not capacity.get("available"):
        return []
    horizon = capacity.get("target_date")
    pct = capacity.get("percentiles") or {}
    if not horizon or not pct:
        return []

    out = []
    for p, n in sorted(pct.items(), key=lambda kv: int(kv[0])):
        p = int(p)
        out.append({
            "id": claim_id(context_id, made_on, p),
            "contextId": context_id,
            "boardId": board_id,
            "madeOn": made_on,
            "horizon": horizon,
            "kind": "capacity",
            "probability": round(p / 100.0, 2),
            "claimItems": int(n),
            "label": "at least %d item%s completed on %s by %s"
                     % (int(n), "" if int(n) == 1 else "s",
                        label_board or board_id, horizon),
            # Unresolved until the horizon has passed and completions in the
            # window have been counted. `score_calibration` skips these, which
            # is why an unresolved log scores nothing rather than scoring zero.
            "resolved": None,
            "observed": None,
            "seed": SEED,
            "trials": TRIALS,
        })
    return out


def problems_in_claim(entry):
    """What is wrong with one logged claim, as sentences. Empty means storable.

    Checked before writing rather than after reading. A bad entry in the log is
    read by every scoring run from then on, and a calibration score is the last
    figure anybody would think to check.
    """
    out = []
    if not isinstance(entry, dict):
        return ["the entry is not an object."]
    for f in ("id", "contextId", "madeOn", "horizon", "label"):
        if not isinstance(entry.get(f), str) or not entry[f].strip():
            out.append("%s is missing, and a claim nobody can identify cannot "
                       "be resolved later." % f)
    p = entry.get("probability")
    if not isinstance(p, (int, float)) or isinstance(p, bool) or not 0 < p < 1:
        out.append("probability is %r, and a claim scored at 0 or 1 is not a "
                   "forecast." % (p,))
    n = entry.get("claimItems")
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        out.append("claimItems is %r, and the claim is a count of items." % (n,))
    if entry.get("resolved") not in (True, False, None):
        out.append("resolved is %r; it is true, false, or not yet known."
                   % (entry.get("resolved"),))
    if entry.get("madeOn") and entry.get("horizon") \
            and str(entry["horizon"]) <= str(entry["madeOn"]):
        out.append("the horizon is not after the day the claim was made, so "
                   "there is no window for anything to happen in.")
    extra = [k for k in entry if k not in CLAIM_FIELDS]
    if extra:
        out.append("the entry carries %s, which the log does not hold — it "
                   "keeps counts and dates, never anything derived from issue "
                   "text." % ", ".join(sorted(extra)))
    return out


def resolve_claims(entries, issues, today):
    """Score every claim whose horizon has passed, from completions in its window.

    Returns `(entries, pending)` — the entries with `resolved` and `observed`
    filled in where they could be, and the ones left alone with the reason.

    **A claim is only ever resolved once.** An entry that already carries a
    verdict is returned untouched: the window it was about is closed, and
    recounting it later against a board whose issues have since moved would
    quietly change a score that was already published.

    **Counted in the window `(madeOn, horizon]`.** The forecast was made on
    `madeOn` and describes what happens after it, which is exactly how
    `forecast_count_by_date` builds its horizon — an item already finished that
    morning was not predicted, it was history.

    **What this cannot see, and does not pretend to.** The issues handed in are
    the board's issues now. An item completed inside the window and since moved
    to another board is not counted, so a claim can resolve false because the
    work moved rather than because it was late. That is the same class of gap
    ADR 0015 records for a stripped sprint membership, and there is no
    reading of Jira that closes it — a resolution is a statement about the
    board as it stands.
    """
    pending, out = [], []
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        if e.get("resolved") is not None:
            out.append(e)
            continue
        horizon, made = e.get("horizon"), e.get("madeOn")
        if not horizon or not made:
            out.append(e)
            pending.append({"id": e.get("id"),
                            "why": "it carries no window to resolve over"})
            continue
        if str(today) < str(horizon):
            out.append(e)
            pending.append({"id": e.get("id"),
                            "why": "its horizon of %s has not passed yet" % horizon})
            continue
        observed = sum(1 for i in (issues or [])
                       if i.get("resolved")
                       and str(made) < str(i["resolved"])[:10] <= str(horizon))
        done = dict(e)
        done["observed"] = observed
        done["resolved"] = observed >= int(e.get("claimItems") or 0)
        out.append(done)
    return out, pending


def calibration_note(scored, pending=None):
    """What a reader is told above a calibration score, or instead of one.

    The scorer's own refusal is quoted rather than softened — *"too few
    resolved forecasts"* is a different statement from a bad score, and only
    one of them is a criticism of the forecaster.
    """
    waiting = len(pending or [])
    if isinstance(scored, Refusal):
        base = ("Not scored yet: %d of the %d resolved forecasts needed."
                % (scored.have, scored.need))
        return (base + " %d more %s made and waiting on %s horizon."
                % (waiting, "is" if waiting == 1 else "are",
                   "its" if waiting == 1 else "their")) if waiting else base
    if not isinstance(scored, dict) or not scored.get("available"):
        return ""
    return ("Scored over %d resolved forecast%s — Brier %s, %s."
            % (scored["n"], "" if scored["n"] == 1 else "s",
               scored["brier_score"], scored["interpretation"]))


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


#: How many entries a board's log keeps. Roughly a year of daily forecasts at
#: four claims each, which is more than `score_calibration` needs and small
#: enough to sit in one stored value. Unresolved claims are never dropped — a
#: claim waiting on its horizon is the only kind that cannot be replaced by
#: making another one.
MAX_LOG = 400


def trim_log(log, keep=MAX_LOG):
    """The log, bounded, oldest resolved entries first. Reports what it dropped.

    No silent caps: a log that quietly forgets its oldest entries reads as a
    complete history, and a Brier score over a window nobody chose is a figure
    with an invented basis. The count comes back so the caller can say it.

    Unresolved claims survive regardless of age. One waiting on a horizon is
    evidence not yet collected; dropping it discards the only observation that
    cannot be re-made.
    """
    entries = [e for e in (log or []) if isinstance(e, dict)]
    if len(entries) <= keep:
        return entries, 0
    unresolved = [e for e in entries if e.get("resolved") is None]
    resolved = sorted((e for e in entries if e.get("resolved") is not None),
                      key=lambda e: str(e.get("horizon") or ""))
    room = max(keep - len(unresolved), 0)
    dropped = len(resolved) - room
    kept = unresolved + (resolved[-room:] if room else [])
    # Back into the order they were made, so a reader scrolling the log is not
    # handed the unresolved ones first by accident of how they were trimmed.
    kept.sort(key=lambda e: (str(e.get("madeOn") or ""), str(e.get("id") or "")))
    return kept, max(dropped, 0)


def update_log(log, claims, issues, today, keep=MAX_LOG):
    """One board's forecast log, brought up to date, and what it now scores.

    Everything item 4c does to a log happens here, in one function, because
    every step of it is arithmetic or a judgement about evidence and neither
    belongs in a resolver or an HTTP wrapper. Both transports call this.

    In order:

    **New claims are added by id, and an id already held is left alone.** A
    forecast published twice in a day is one claim. Re-adding it would replace a
    claim that may already carry a resolution, and would let a board that is
    looked at often out-score one that is looked at rarely.

    **Claims whose horizon has passed are resolved**, from completions in their
    own window. `resolve_claims` never touches one that already has a verdict.

    **The log is trimmed**, and what was dropped is reported rather than
    silently forgotten.

    **What is left is scored**, or refused with the scorer's own sentence when
    there is not enough of it. Those are different statements and only one of
    them is a criticism of the forecaster.
    """
    held = {e.get("id"): e for e in (log or []) if isinstance(e, dict)}
    added = 0
    for c in claims or []:
        if not isinstance(c, dict) or not c.get("id"):
            continue
        if c["id"] in held:
            continue
        if problems_in_claim(c):
            # Refused rather than stored. A bad entry is read by every scoring
            # run from then on, and a calibration score is the last figure
            # anybody would think to check.
            continue
        held[c["id"]] = c
        added += 1

    resolved, pending = resolve_claims(list(held.values()), issues, today)
    kept, dropped = trim_log(resolved, keep)
    scored = score_calibration(kept)
    return {
        "log": kept,
        "added": added,
        "dropped": dropped,
        "pending": pending,
        "calibration": (asdict(scored) if hasattr(scored, "__dataclass_fields__")
                        else scored),
        "note": calibration_note(scored, pending),
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
    # Resolved once, from the dataset, and passed down. Nothing below re-reads
    # it and nothing reaches for a file of its own.
    cfg = OC.from_dataset(dataset)
    as_of = as_of or meta.get("asOfDate") or date.today().isoformat()
    target = target or meta.get("endDate")
    open_items = [i for i in issues if (i.get("statusCategory") or "") != "Done"]
    remaining = remaining if remaining is not None else len(open_items)

    if window_days is None:
        window_days = full_history_days(issues, as_of)
    samples = throughput_samples(issues, window_days=window_days, as_of=as_of, cfg=cfg)
    growth = scope_growth_history(snapshots)

    def out(x):
        return asdict(x) if hasattr(x, "__dataclass_fields__") else x

    # How long the next sprint is, in working days: the list the dataset states
    # if it carries one, else derived from its own dates under the resolved
    # config — the same two steps, in the same order, that the page takes in
    # contextWorkingDays().
    #
    # There is deliberately no third step. This line ended `... or 10`, which
    # put an invented sprint in front of the refusal recommend_commitment()
    # already holds: a dataset stating no dates at all came back "commit to 9
    # items", with "20,000 simulated sprints of 10 working days" printed as its
    # own basis. Ten is the working length of the default fortnight, which is
    # exactly what made it read as a measurement rather than a substitution,
    # and it made that refusal unreachable from here.
    #
    # Reaching for cfg["sprintLengthDays"] instead is the same bug in the
    # config's clothes. `from_dataset()` merges DEFAULTS, so a stated 14 and an
    # inherited 14 are indistinguishable by the time they arrive here, and a
    # figure nobody chose would go back out under the authority of one they
    # did. Below one working day the honest answer is that we do not know the
    # cadence, which is what the refusal says.
    sprint_days = len(meta.get("workingDays") or working_days(
        _d(meta.get("startDate")), _d(meta.get("endDate")), cfg))

    return {
        "generated_for": meta.get("sprintName"),
        "as_of": as_of,
        "inputs": {
            "open_items": len(open_items),
            "throughput_observations": len(samples),
            "items_completed_in_window": sum(samples),
            "window_days": window_days,
            "scope_growth_samples": len(growth),
            # Named in the output because two forecasts of the same board under
            # different calendars are different forecasts, and the difference is
            # otherwise invisible.
            "calendar": OC.summary(cfg),
        },
        "sprint_completion": out(forecast_completion(
            remaining, samples, as_of, target_date=target, scope_growth=growth, cfg=cfg)),
        # Two reasons there is no answer here and they are not the same reason.
        # A target that has passed is a date somebody set and missed; no target
        # at all is a period with no end to forecast against, which is what a
        # rolling window is. Both produced "the target date has passed", which
        # sends a reader looking for a deadline that was never set.
        "capacity_to_target": out(forecast_count_by_date(samples, as_of, target, cfg=cfg))
        if target and target > as_of else
        out(Refusal(reason=("the target date has passed" if target else
                            "this period has no end date to forecast against"),
                    have=0, need=1)),
        "item_risk": out(item_risk(issues, as_of, cfg=cfg)),
        "next_commitment": out(recommend_commitment(samples, sprint_days)),
        "size_stability": out(size_stability(issues, as_of, cfg=cfg)),
        "releases": [
            {"name": r["name"], "target": r["targetDate"],
             "forecast": out(forecast_completion(
                 max((r.get("scopeIssues") or 0) - (r.get("doneIssues") or 0), 0),
                 samples, as_of, target_date=r["targetDate"], scope_growth=growth, cfg=cfg))}
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
