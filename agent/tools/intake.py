#!/usr/bin/env python3
"""
intake.py — forecasting a product ask before any of it exists.

The delivery forecaster (forecast.py) needs history of comparable work. A new
product ask has none — it has a description. The bridge between them is **how
many items this will decompose into**, and that number, not the delivery rate,
usually dominates the error.

That fact drives the whole design here:

  * Sizing is a distribution, never a point. Three methods, in a ladder of
    increasing evidence: t-shirt (initial intake) -> reference class (from your
    own completed epics) -> explicit min/likely/max (someone who has done the
    refinement).
  * The t-shirt scale is **calibrated from the team's own history**, not from a
    table someone wrote once. S/M/L/XL are quartiles of how epics on that board
    actually turned out. It maintains itself.
  * Every forecast reports **where its uncertainty comes from** — size versus
    delivery variability. If the range is nine weeks wide and eight of those
    come from not knowing the size, the answer is to refine the ask, not to
    argue about velocity. That attribution is the most useful number this file
    produces and nothing else in the toolchain provides it.
  * Two capacity scenarios, always both: *earliest possible* (dedicated, starts
    now) and *realistic* (queued behind current commitments, throughput
    discounted by the team's measured interruption rate). The gap between them
    is the cost of everything already in flight, which is the argument any
    prioritisation conversation actually needs.

Nothing here estimates value. Value is an input with a stated basis or it is
absent; this file will not invent one.

    python3 agent/tools/intake.py data/demo-bundle.json --board 42 --tshirt L
    python3 agent/tools/intake.py data/demo-bundle.json --board 42 --ask asks/INTAKE-014.json
    python3 agent/tools/intake.py data/demo-bundle.json --board 42 --sequence asks/*.json
"""

from __future__ import annotations

import argparse
import glob
import json
import pathlib
import random
import statistics
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Optional

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import forecast as F  # noqa: E402
import orgconfig as OC  # noqa: E402

TRIALS = 20_000
SEED = 20260816
PERCENTILES = (50, 70, 85, 95)

# Below these the answer is "not enough evidence", not a wider interval.
MIN_REFERENCE_EPICS = 5      # completed epics needed for a reference class
MIN_TSHIRT_EPICS = 8         # more, because it is split into four bands


# ---------------------------------------------------------------- structures
@dataclass
class Refusal:
    available: bool = False
    reason: str = ""
    have: int = 0
    need: int = 0

    def sentence(self) -> str:
        return ("No intake forecast: %s (%d observations, %d needed). "
                "A wider range would not fix this — the evidence is absent, not noisy."
                % (self.reason, self.have, self.need))


@dataclass
class Sizing:
    available: bool = True
    method: str = ""
    samples: list = field(default_factory=list)   # empirical item counts to draw from
    p50: float = 0.0
    p85: float = 0.0
    low: float = 0.0
    high: float = 0.0
    n: int = 0
    basis: str = ""
    caveat: str = ""


# ------------------------------------------------------------------ helpers
def _d(s):
    return date.fromisoformat(s[:10]) if s else None


def _pct(vals, p):
    if not vals:
        return None
    v = sorted(vals)
    k = (len(v) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def board_issues(dataset, board=None):
    """Every issue belonging to one board, across every sprint in the file."""
    ctxs = dataset.get("contexts") or []
    if not ctxs:
        return dataset["issues"], None
    if board is None:
        active = next((c for c in ctxs if c.get("sprintState") == "active"), ctxs[-1])
        board = active.get("boardId")
    mine = [c for c in ctxs if str(c.get("boardId")) == str(board)]
    ids = {c["id"] for c in mine}
    # The context returned is the board's *most recent* sprint, not the first
    # one listed. It supplies `asOfDate`, which sets the trailing window every
    # throughput sample is drawn from — take the earliest sprint on the board
    # and the forecast is built from a window that ended months ago.
    meta = None
    if mine:
        meta = next((c for c in mine if c.get("sprintState") == "active"), None) \
            or max(mine, key=lambda c: (c.get("endDate") or c.get("startDate") or ""))
    return [i for i in dataset["issues"] if i.get("contextId") in ids], meta


# =====================================================================
# 1. sizing — how many items will this decompose into?
# =====================================================================
def epic_sizes(issues, as_of=None, min_items=3, stale_days=30, done_ratio=0.9):
    """Item counts of *finished* epics on this board — the reference class.

    "Finished" is deliberately not "every item is Done". Real epics keep a
    straggler forever, and requiring perfection returns an empty reference
    class on most boards (it did here, on the first run). An epic qualifies
    when it has both:

        stopped growing  — nothing new raised against it in `stale_days`, and
        substantially landed — at least `done_ratio` of its items are Done.

    A part-done, still-growing epic is excluded, because counting it tells you
    how big it is *so far*, which systematically understates and is the most
    common way a reference class comes out optimistic.
    """
    today = _d(as_of) if as_of else None

    # Which field identifies an epic here, chosen once for the whole set.
    #
    # A bundle carries `epic`, the epic's own summary. A payload assembled for
    # the hosted calculator carries `epicKey` and cannot carry `epic` at all —
    # free text is stripped on the way out (`FREE_TEXT_FIELDS` in
    # service/app.py), which is the point of that boundary rather than an
    # oversight. Until this line, sizing over that route grouped nothing,
    # found no completed epics and refused: t-shirt scales and reference
    # classes were unavailable to it in principle.
    #
    # Chosen once rather than per issue, and that is the part worth being
    # careful about. `i.get("epicKey") or i.get("epic")` reads as the obvious
    # fallback and would split a single epic in two the moment one dataset
    # carried the key on some issues and the name on others — a twenty-item
    # epic arriving as two tens, which shrinks the t-shirt bands and reads
    # exactly like a team that works in smaller pieces.
    #
    # A key beats a name on its own merits, incidentally: two epics can share a
    # summary, and renaming one splits its own history in half.
    field = "epicKey" if any(i.get("epicKey") for i in issues) else "epic"

    by_epic = defaultdict(list)
    for i in issues:
        if i.get(field):
            by_epic[i[field]].append(i)
    if today is None:
        allc = [_d(i["created"]) for i in issues if i.get("created")]
        today = max(allc) if allc else date.today()

    out = []
    for name, items in by_epic.items():
        if len(items) < min_items:
            continue
        done = sum(1 for x in items if (x.get("statusCategory") or "") == "Done")
        if done / len(items) < done_ratio:
            continue
        newest = max((_d(x["created"]) for x in items if x.get("created")), default=None)
        if newest and (today - newest).days < stale_days:
            continue                      # still receiving work; not finished
        out.append({"epic": name, "grouped_by": field, "items": len(items), "done": done,
                    "last_raised": newest.isoformat() if newest else None})
    return sorted(out, key=lambda r: r["items"])


def tshirt_scale(sizes):
    """Derive S/M/L/XL bands from the team's own completed epics.

    Quartiles, not a table someone wrote in 2019. This means the scale means
    something different for each team — which is correct, and is why a shared
    numeric scale across teams never survives contact.
    """
    counts = [s["items"] for s in sizes]
    if len(counts) < MIN_TSHIRT_EPICS:
        return Refusal(reason="too few completed epics to calibrate a t-shirt scale",
                       have=len(counts), need=MIN_TSHIRT_EPICS)
    q1, q2, q3 = _pct(counts, 25), _pct(counts, 50), _pct(counts, 75)
    bands = {
        "S":  [c for c in counts if c <= q1],
        "M":  [c for c in counts if q1 < c <= q2],
        "L":  [c for c in counts if q2 < c <= q3],
        "XL": [c for c in counts if c > q3],
    }
    return {
        "available": True,
        "n": len(counts),
        "bands": {k: {"range": [min(v), max(v)], "median": _pct(v, 50), "n": len(v)}
                  for k, v in bands.items() if v},
        "samples": {k: v for k, v in bands.items() if v},
        "basis": "quartiles of %d completed epics on this board" % len(counts),
    }


def _triangular(lo, mode, hi, n, rng):
    return [rng.triangular(lo, hi, mode) for _ in range(n)]


def size_ask(ask, issues, rng=None):
    """Turn a product ask into a distribution of item counts."""
    rng = rng or random.Random(SEED)
    sizing = ask.get("sizing") or {}
    method = sizing.get("method", "reference-class")
    sizes = epic_sizes(issues, as_of=ask.get('_asOf'))
    # Named in the basis when it is not the obvious one. A reference class
    # assembled by issue key and one assembled by epic name are the same
    # method over the same board, but a reader checking the working needs to
    # know which column to look down.
    by_key = ", grouped by epic key" if sizes and sizes[0]["grouped_by"] == "epicKey" else ""

    if method == "explicit":
        lo, mode, hi = sizing.get("minItems"), sizing.get("likelyItems"), sizing.get("maxItems")
        if not all(isinstance(v, (int, float)) for v in (lo, mode, hi)) or not lo <= mode <= hi:
            return Refusal(reason="explicit sizing needs minItems <= likelyItems <= maxItems", have=0, need=3)
        s = _triangular(lo, mode, hi, 4000, rng)
        return Sizing(method="explicit", samples=s, n=3,
                      p50=_pct(s, 50), p85=_pct(s, 85), low=lo, high=hi,
                      basis=sizing.get("basis") or "supplied by the requester, no basis recorded",
                      caveat=("Nothing anchors these three numbers to how work on this board has "
                              "actually turned out. Compare them against the reference class before "
                              "relying on them."))

    if method == "tshirt":
        scale = tshirt_scale(sizes)
        if isinstance(scale, Refusal):
            return scale
        band = str(sizing.get("size", "")).upper()
        if band not in scale["samples"]:
            return Refusal(reason="t-shirt size %r has no calibrated band on this board "
                                  "(available: %s)" % (band, ", ".join(scale["samples"])),
                           have=0, need=1)
        s = scale["samples"][band]
        rng_s = [rng.choice(s) for _ in range(4000)]
        return Sizing(method="tshirt", samples=rng_s, n=len(s),
                      p50=_pct(s, 50), p85=_pct(s, 85), low=min(s), high=max(s),
                      basis="size %s = %d completed epics on this board, %d-%d items%s"
                            % (band, len(s), min(s), max(s), by_key),
                      caveat=("T-shirt sizing is an intake-stage estimate. It is expected to move "
                              "once the team refines the ask, and the forecast should be re-run "
                              "then rather than treated as a commitment. Its width here reflects "
                              "only how varied past %s epics were — not how wrong the T-shirt "
                              "judgement itself might be." % band))

    # reference class — every completed epic, no band filter
    if len(sizes) < MIN_REFERENCE_EPICS:
        return Refusal(reason="too few completed epics to form a reference class",
                       have=len(sizes), need=MIN_REFERENCE_EPICS)
    counts = [s["items"] for s in sizes]
    rng_s = [rng.choice(counts) for _ in range(4000)]
    return Sizing(method="reference-class", samples=rng_s, n=len(counts),
                  p50=_pct(counts, 50), p85=_pct(counts, 85), low=min(counts), high=max(counts),
                  basis="%d completed epics on this board, %d-%d items (median %.0f)%s"
                        % (len(counts), min(counts), max(counts), _pct(counts, 50), by_key),
                  caveat=("Assumes this ask is like the work this board has already done. If it is "
                          "a genuinely new kind of problem, the reference class does not apply and "
                          "you are guessing with extra steps."))


# =====================================================================
# 2. capacity — what is actually available to this ask
# =====================================================================
def interruption_rate(history):
    """Share of each sprint that arrived after planning, averaged.

    Capacity available to *planned* work is what is left after interruption.
    This is measured, not assumed, and it is why the realistic scenario is
    slower than the earliest-possible one.
    """
    rates = []
    for h in history or []:
        committed = h.get("committedItems")
        unplanned = h.get("unplannedItems")
        if committed and unplanned is not None:
            rates.append(unplanned / (committed + unplanned))
    return (sum(rates) / len(rates)) if rates else None


def queue_ahead(issues, as_of):
    """Items already committed and not finished — the work this ask sits behind.

    Mid-sprint additions are excluded because they are not a queue: they are
    interruption, and interruption is already modelled as a thinned throughput
    series. Counting them here as well would charge the ask for the same lost
    capacity twice.
    """
    cut = _d(as_of)
    return [i for i in issues
            if (i.get("statusCategory") or "") != "Done"
            and not i.get("addedMidSprint")
            and not (cut and _d(i.get("created")) and _d(i["created"]) > cut)]


def capacity(dataset, issues, as_of, scenario):
    """Throughput samples available to a new ask under one scenario."""
    samples = F.throughput_samples(issues, as_of=as_of, cfg=OC.from_dataset(dataset))
    if len(samples) < F.MIN_THROUGHPUT_SAMPLES or sum(samples) < F.MIN_COMPLETED_ITEMS:
        return Refusal(reason="too little delivery history on this team to forecast against",
                       have=sum(samples), need=F.MIN_COMPLETED_ITEMS)
    if scenario == "earliest":
        return {"samples": samples, "queue_items": 0, "discount": 0.0,
                "basis": "dedicated capacity from the start date, nothing queued ahead"}

    # Interruption is a property of *this* team, so the history has to come from
    # this board's contexts — not from whichever context happened to be last in
    # the file. A board with a 6% interruption rate should not inherit another
    # board's 30%.
    ids = {i.get("contextId") for i in issues}
    hist = []
    for c in (dataset.get("contexts") or []):
        if c["id"] not in ids:
            continue
        h = ((dataset.get("byContext") or {}).get(c["id"]) or {}).get("history") or []
        if len(h) > len(hist):
            hist = h
    rate = interruption_rate(hist) or 0.0
    q = queue_ahead(issues, as_of)
    # Interruption removes capacity from planned work; model it as a thinned
    # throughput series rather than a flat multiplier on the final date, so the
    # variance carries through the simulation properly.
    rng = random.Random(SEED)
    thinned = [v for v in samples]
    if rate > 0:
        thinned = [0 if rng.random() < rate else v for v in samples]
    return {"samples": thinned, "queue_items": len(q), "discount": round(rate, 3),
            "basis": ("queued behind %d committed items; throughput discounted by the measured "
                      "%.0f%% interruption rate" % (len(q), rate * 100))}


# =====================================================================
# 3. the forecast, and where its uncertainty comes from
# =====================================================================
def _simulate(size_samples, thr_samples, queue_items, trials, seed):
    """Working days until the ask itself is complete, having first cleared any
    queue ahead of it."""
    rng = random.Random(seed)
    out = []
    for _ in range(trials):
        target = queue_items + max(1, round(rng.choice(size_samples)))
        done, days = 0, 0
        while done < target and days < 900:
            done += rng.choice(thr_samples)
            days += 1
        out.append(days)
    out.sort()
    return out


def attribute_uncertainty(size_samples, thr_samples, queue_items, trials=6000, seed=SEED):
    """Split the width of the forecast between not knowing the size and normal
    delivery variability.

    Run three simulations: size frozen at its median, throughput frozen at its
    mean, and both varying. The two partial spreads are attributed
    proportionally. It is a decomposition, not an exact variance split — but it
    answers the question that matters: *which one should we go and reduce?*
    """
    med = _pct(size_samples, 50)
    mean_thr = sum(thr_samples) / len(thr_samples)
    frozen_thr = [mean_thr] * len(thr_samples)

    both = _simulate(size_samples, thr_samples, queue_items, trials, seed)
    delivery_only = _simulate([med], thr_samples, queue_items, trials, seed + 1)
    size_only = _simulate(size_samples, frozen_thr, queue_items, trials, seed + 2)

    def spread(a):
        return max(_pct(a, 95) - _pct(a, 50), 0.0)

    s_d, s_s = spread(delivery_only), spread(size_only)
    total = s_d + s_s
    if total <= 0:
        return {"available": False, "reason": "no measurable spread"}
    size_share = s_s / total
    return {
        "available": True,
        "total_spread_days": round(spread(both), 1),
        "size_share": round(size_share, 3),
        "delivery_share": round(1 - size_share, 3),
        "dominant": "size" if size_share >= 0.5 else "delivery",
        "reading": (
            "%.0f%% of the range comes from not knowing how big the ask is. "
            "Refining the ask will narrow this forecast far more than anything "
            "the delivery team does." % (size_share * 100)
            if size_share >= 0.5 else
            "%.0f%% of the range comes from normal delivery variability rather than "
            "sizing. The ask is understood well enough; the spread is what this team "
            "genuinely looks like." % ((1 - size_share) * 100)),
    }


def forecast_ask(dataset, ask, board=None, as_of=None, start_from=None, trials=TRIALS):
    issues, ctx = board_issues(dataset, board)
    cfg = OC.from_dataset(dataset)
    as_of = as_of or (ctx or {}).get("asOfDate") or (dataset.get("meta") or {}).get("asOfDate") \
        or date.today().isoformat()
    start_from = start_from or as_of

    ask.setdefault("_asOf", as_of)
    sizing = size_ask(ask, issues)
    if isinstance(sizing, Refusal):
        return {"available": False, "stage": "sizing", "refusal": asdict(sizing),
                "sentence": sizing.sentence()}

    out = {
        "available": True,
        "ask": {k: ask.get(k) for k in ("id", "title", "requestedBy", "neededBy")},
        "team": {"board": str(board) if board else None,
                 "boardName": (ctx or {}).get("boardName"),
                 "projectName": (ctx or {}).get("projectName")},
        "as_of": as_of,
        "sizing": {k: v for k, v in asdict(sizing).items() if k != "samples"},
        "scenarios": {},
    }

    for scenario in ("earliest", "realistic"):
        cap = capacity(dataset, issues, as_of, scenario)
        if isinstance(cap, Refusal):
            out["scenarios"][scenario] = {"available": False, "sentence": cap.sentence()}
            continue
        days = _simulate(sizing.samples, cap["samples"], cap["queue_items"], trials, SEED)
        begin = _d(start_from)
        pcts = {p: int(round(_pct(days, p))) for p in PERCENTILES}
        entry = {
            "available": True,
            "queue_items": cap["queue_items"],
            "interruption_discount": cap["discount"],
            "basis": cap["basis"],
            "working_days": pcts,
            "dates": {p: F.add_working_days(begin, n, cfg).isoformat() for p, n in pcts.items()},
        }
        if ask.get("neededBy"):
            budget = len(F.working_days(begin, _d(ask["neededBy"]), cfg)) - 1
            entry["needed_by"] = ask["neededBy"]
            entry["prob_by_needed"] = round(sum(1 for d in days if d <= budget) / len(days), 3)
        out["scenarios"][scenario] = entry

    real = out["scenarios"].get("realistic", {})
    if real.get("available"):
        cap = capacity(dataset, issues, as_of, "realistic")
        out["uncertainty"] = attribute_uncertainty(sizing.samples, cap["samples"], cap["queue_items"])
        e = out["scenarios"]["earliest"]["working_days"][85]
        r = real["working_days"][85]
        out["cost_of_queue_days"] = r - e
    return out


# =====================================================================
# 4. prioritisation — what does sequencing cost?
# =====================================================================
def sequence(dataset, asks, board=None, as_of=None, trials=8000):
    """For a set of asks against one team, what each ordering costs the others.

    Deliberately not a scoring formula. WSJF and its relatives multiply an
    unvalidated value estimate by an unvalidated size estimate and present the
    product as arithmetic. This returns the one thing that is actually
    computable — the delivery-date consequence of each ordering — and leaves
    the value judgement to whoever owns it, with their own stated basis
    alongside.
    """
    issues, ctx = board_issues(dataset, board)
    cfg = OC.from_dataset(dataset)
    as_of = as_of or (ctx or {}).get("asOfDate") or date.today().isoformat()
    cap = capacity(dataset, issues, as_of, "realistic")
    if isinstance(cap, Refusal):
        return {"available": False, "sentence": cap.sentence()}

    sized, skipped = [], []
    for a in asks:
        a.setdefault("_asOf", as_of)
        s = size_ask(a, issues)
        if isinstance(s, Refusal):
            skipped.append({"id": a.get("id"), "reason": s.reason})
        else:
            sized.append((a, s))
    if len(sized) < 2:
        return {"available": False,
                "sentence": "Sequencing needs at least two sizeable asks; %d supplied, %d skipped."
                            % (len(asks), len(skipped)), "skipped": skipped}

    begin = _d(as_of)
    rows = []
    for pos_first in range(len(sized)):
        order = [sized[pos_first]] + [x for k, x in enumerate(sized) if k != pos_first]
        queue = cap["queue_items"]
        seq = []
        for a, s in order:
            days = _simulate(s.samples, cap["samples"], queue, trials, SEED)
            p85 = int(round(_pct(days, 85)))
            seq.append({"id": a.get("id"), "title": a.get("title"),
                        "p85_days": p85, "p85_date": F.add_working_days(begin, p85, cfg).isoformat(),
                        "value": (a.get("valueEstimate") or {}).get("amount"),
                        "valueBasis": (a.get("valueEstimate") or {}).get("basis"),
                        "neededBy": a.get("neededBy")})
            queue += max(1, round(_pct(s.samples, 50)))
        rows.append({"first": sized[pos_first][0].get("id"), "order": seq})

    # what each ask costs the others by going first
    base = {r["first"]: r for r in rows}
    deltas = []
    for r in rows:
        others = [x for x in r["order"][1:]]
        deltas.append({
            "first": r["first"],
            "its_own_p85_date": r["order"][0]["p85_date"],
            "delays_others_by_days": sum(
                x["p85_days"] - next(y["p85_days"] for y in base[x["id"]]["order"] if y["id"] == x["id"])
                for x in others),
            "misses_a_needed_by": [x["id"] for x in r["order"]
                                   if x.get("neededBy") and x["p85_date"] > x["neededBy"]],
        })
    # The decision-forcing output: an ask that misses its date in EVERY ordering
    # is not a prioritisation problem. No sequence saves it, so the only levers
    # left are scope, capacity or the date — and saying so stops a planning
    # meeting from re-arranging a list that cannot be re-arranged into success.
    with_dates = {x["id"] for r in rows for x in r["order"] if x.get("neededBy")}
    unachievable = []
    for aid in sorted(with_dates):
        misses = all(any(x["id"] == aid and x["p85_date"] > x["neededBy"] for x in r["order"])
                     for r in rows)
        if misses:
            best = min((x for r in rows for x in r["order"] if x["id"] == aid),
                       key=lambda x: x["p85_date"])
            unachievable.append({"id": aid, "neededBy": best["neededBy"],
                                 "best_case_p85": best["p85_date"],
                                 "short_by_days": (
                                     _d(best["p85_date"]) - _d(best["neededBy"])).days})

    return {"available": True, "as_of": as_of,
            "unachievable_at_any_priority": unachievable,
            "team": {"board": str(board) if board else None, "boardName": (ctx or {}).get("boardName")},
            "queue_items": cap["queue_items"], "basis": cap["basis"],
            "orderings": rows, "comparison": deltas, "skipped": skipped,
            "note": ("Dates are 85th-percentile. No value score is computed: the delivery "
                     "consequence of each ordering is computable, the relative worth of the "
                     "asks is not.")}


# =====================================================================
# 5. readiness — is this ask refined enough to forecast at all?
# =====================================================================
REQUIRED = [
    ("title", "a one-line statement of what is being asked for"),
    ("team", "the team or board that would deliver it"),
    ("sizing", "a sizing method: tshirt, reference-class or explicit"),
]
RECOMMENDED = [
    ("problemStatement", "what problem this solves, so the ask can be challenged rather than only sized"),
    ("successMeasure", "how anyone would know afterwards whether it worked"),
    ("neededBy", "a date to forecast against, or an explicit 'no fixed date'"),
    ("valueEstimate", "an amount AND a stated basis, or nothing at all"),
    ("dependencies", "teams or systems outside this board, which the forecast cannot see"),
    ("assumptions", "what is being taken on trust, so it can be revisited when it changes"),
]


def readiness(ask):
    missing = [(k, why) for k, why in REQUIRED if not ask.get(k)]
    gaps = [(k, why) for k, why in RECOMMENDED if not ask.get(k)]
    value = ask.get("valueEstimate") or {}
    if value.get("amount") and not value.get("basis"):
        gaps.append(("valueEstimate.basis",
                     "an amount with no basis is a number someone will quote back at you"))
    return {
        "forecastable": not missing,
        "missing_required": [{"field": k, "why": w} for k, w in missing],
        "gaps": [{"field": k, "why": w} for k, w in gaps],
        "verdict": ("Not forecastable yet — " + ", ".join(k for k, _ in missing)) if missing
                   else ("Forecastable, with %d gap(s) that will widen or weaken it" % len(gaps)
                         if gaps else "Forecastable and complete"),
    }


# ------------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dataset")
    p.add_argument("--board", help="board id to forecast against")
    p.add_argument("--ask", help="a JSON intake record")
    p.add_argument("--sequence", nargs="*", help="two or more intake records to sequence")
    p.add_argument("--tshirt", help="shortcut: forecast a bare S/M/L/XL against the board")
    p.add_argument("--needed-by", help="date to test the t-shirt shortcut against")
    p.add_argument("--as-of")
    p.add_argument("--scale", action="store_true", help="print the calibrated t-shirt scale and exit")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    ds = json.load(open(a.dataset))
    issues, ctx = board_issues(ds, a.board)

    if a.scale:
        sc = tshirt_scale(epic_sizes(issues, as_of=a.as_of))
        print(json.dumps(sc if isinstance(sc, dict) else asdict(sc), indent=2, default=str))
        return

    if a.sequence:
        paths = [q for pat in a.sequence for q in sorted(glob.glob(pat))] or a.sequence
        asks = [json.load(open(q)) for q in paths]
        res = sequence(ds, asks, a.board, a.as_of)
        print(json.dumps(res, indent=2, default=str) if a.json else _fmt_sequence(res))
        return

    if a.tshirt:
        ask = {"id": "ADHOC", "title": "Unnamed %s ask" % a.tshirt.upper(),
               "team": a.board, "sizing": {"method": "tshirt", "size": a.tshirt},
               "neededBy": a.needed_by}
    elif a.ask:
        ask = json.load(open(a.ask))
    else:
        p.error("give --ask, --tshirt or --sequence")

    r = readiness(ask)
    res = forecast_ask(ds, ask, a.board, a.as_of)
    if a.json:
        print(json.dumps({"readiness": r, "forecast": res}, indent=2, default=str))
        return
    print(_fmt(ask, r, res))


def _fmt(ask, r, res):
    L = []
    L.append("Intake forecast — %s" % (ask.get("title") or ask.get("id") or "unnamed ask"))
    L.append("  readiness: %s" % r["verdict"])
    for m in r["missing_required"]:
        L.append("    ! missing %s — %s" % (m["field"], m["why"]))
    # Every gap is printed. Truncating the list while the verdict line still
    # counted them made the output disagree with itself, and a gap you cannot
    # see is a gap nobody fills.
    for g in r["gaps"]:
        L.append("    · gap %s — %s" % (g["field"], g["why"]))
    if not res.get("available"):
        L.append("  " + res.get("sentence", "no forecast"))
        return "\n".join(L)

    s = res["sizing"]
    L.append("")
    L.append("  size (%s): %.0f items at the median, %.0f at the 85th — range %.0f-%.0f"
             % (s["method"], s["p50"], s["p85"], s["low"], s["high"]))
    L.append("    basis: %s" % s["basis"])
    if s.get("caveat"):
        L.append("    caveat: %s" % s["caveat"])

    for name, label in (("earliest", "earliest possible (dedicated, starts now)"),
                        ("realistic", "realistic (queued, interruption-adjusted)")):
        sc = res["scenarios"].get(name, {})
        L.append("")
        L.append("  %s:" % label)
        if not sc.get("available"):
            L.append("    " + sc.get("sentence", "unavailable"))
            continue
        L.append("    %s" % sc["basis"])
        for p in PERCENTILES:
            L.append("      %2d%%  by %s  (%d working days)"
                     % (p, sc["dates"][p], sc["working_days"][p]))
        if sc.get("prob_by_needed") is not None:
            L.append("      probability of landing by %s: %.0f%%"
                     % (sc["needed_by"], sc["prob_by_needed"] * 100))

    if res.get("cost_of_queue_days") is not None:
        L.append("")
        L.append("  cost of the existing queue: %d working days at the 85th percentile"
                 % res["cost_of_queue_days"])
    u = res.get("uncertainty") or {}
    if u.get("available"):
        L.append("  uncertainty: %s dominates — %s" % (u["dominant"], u["reading"]))
    return "\n".join(L)


def _fmt_sequence(res):
    if not res.get("available"):
        return "  " + res.get("sentence", "unavailable")
    L = ["Sequencing %d asks on %s — %s"
         % (len(res["orderings"]), res["team"]["boardName"] or "the board", res["basis"])]
    if res.get("unachievable_at_any_priority"):
        L.append("")
        L.append("  NO ORDERING DELIVERS THESE BY THEIR DATE:")
        for u in res["unachievable_at_any_priority"]:
            L.append("    %s — needed %s, best case %s, short by %d days"
                     % (u["id"], u["neededBy"], u["best_case_p85"], u["short_by_days"]))
        L.append("    Sequencing cannot fix this. The levers are scope, capacity or the date.")
    for d in res["comparison"]:
        L.append("")
        L.append("  If %s goes first:" % d["first"])
        L.append("    it lands (85%%) %s" % d["its_own_p85_date"])
        L.append("    it delays the others by %d working days in total" % d["delays_others_by_days"])
        if d["misses_a_needed_by"]:
            L.append("    !! this ordering misses a needed-by date for: %s"
                     % ", ".join(d["misses_a_needed_by"]))
    L.append("")
    L.append("  " + res["note"])
    return "\n".join(L)


if __name__ == "__main__":
    main()
