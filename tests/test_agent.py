#!/usr/bin/env python3
"""
Tests for the reporting/forecasting agent's deterministic tools.

Two jobs:
  1. Assert the facts pack agrees with the numbers the dashboard displays. Two
     implementations of the same arithmetic is a liability; this is the thing
     that catches them drifting apart.
  2. Assert the forecast behaves like a forecast — stable, monotonic, honest
     about thin data — and then BACKTEST it against history, because a
     forecaster nobody scores is a horoscope.

    python3 tests/test_agent.py
"""

import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent" / "tools"))

import forecast as F          # noqa: E402
import metrics as M           # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  — " + str(detail)) if detail else ""))
    if not ok:
        failures.append(name)


def near(a, b, tol=0.005):
    return a is not None and b is not None and abs(a - b) <= tol


# =====================================================================
# 1. the facts pack agrees with what the dashboard puts on screen
# =====================================================================
def test_facts():
    ds = json.load(open(ROOT / "data" / "sample-sprint.json"))
    f = M.facts(ds)

    d = f["delivery"]
    check("item count", d["items_total"] == 22, d["items_total"])
    check("items done", d["items_done"] == 12, d["items_done"])
    check("points done / total", (d["points_done"], d["points_total"]) == (41, 83),
          (d["points_done"], d["points_total"]))
    check("sprint elapsed", near(d["time_elapsed_pct"], 0.60), d["time_elapsed_pct"])
    check("pace gap is negative and ~11pts", near(d["pace_gap_pts"], -0.106, 0.002), d["pace_gap_pts"])

    s = f["scope"]
    check("scope added items", s["added_items"] == 4, s["added_items"])
    check("scope growth ~12%", near(s["growth_pct"], 0.1216, 0.001), s["growth_pct"])

    fl = f["flow"]
    check("flow efficiency matches the dashboard's 22%", near(fl["flow_efficiency"], 0.22, 0.005),
          fl["flow_efficiency"])
    check("flow unit is declared", fl.get("unit") == "calendar days", fl.get("unit"))

    r = f["risk"]
    check("oldest open item", r["oldest_open"]["key"] == "BLC-438", r["oldest_open"])
    check("oldest open age", r["oldest_open"]["days"] == 41, r["oldest_open"])
    check("age bands match the dashboard",
          [len(r["age_bands"][b]) for b in ("0-7", "8-14", "15-30", "30+")] == [1, 6, 2, 1],
          {b: len(v) for b, v in r["age_bands"].items()})
    check("blocked list", sorted(r["blocked"]) == ["BLC-421", "BLC-429", "BLC-441"], r["blocked"])

    p = f["predictability"]
    check("items are the primary predictability unit", p["primary_unit"] == "items", p["primary_unit"])
    check("trailing 3-sprint average, in items",
          near(p["items"]["trailing_3_sprint_avg_completed_items"], 9.0, 0.05),
          p["items"]["trailing_3_sprint_avg_completed_items"])
    check("over-commitment is expressed in items",
          near(p["items"]["commitment_vs_trailing_avg"], 1.0, 0.01),
          p["items"]["commitment_vs_trailing_avg"])
    check("points are retained but marked non-forecasting",
          "not a forecasting input" in p["points"]["status"], p["points"]["status"])
    check("the points figure still matches the dashboard",
          near(p["points"]["trailing_3_sprint_avg_completed"], 35.7, 0.05),
          p["points"]["trailing_3_sprint_avg_completed"])

    v = f["value"]
    check("value closed", v["closed_estimate"] == 87000, v["closed_estimate"])
    check("unpriced completed items are counted", v["items_without_estimate"] == 10,
          v["items_without_estimate"])
    check("no change section without a previous snapshot", f["changes"] is None)


def test_reporting_scope():
    """The facts pack reports the sprint; the forecaster uses all history.
    Conflating them puts '89% complete' on a report about a sprint that is
    55% complete."""
    one = M.facts(json.load(open(ROOT / "data" / "sample-sprint.json")))
    many_ds = json.load(open(ROOT / "data" / "sample-multi-sprint.json"))
    many = M.facts(many_ds)

    check("12 weeks of history does not inflate the sprint's item count",
          many["delivery"]["items_total"] == one["delivery"]["items_total"] == 22,
          (many["delivery"]["items_total"], one["delivery"]["items_total"]))
    check("completion is identical with or without the history file",
          many["delivery"]["items_done"] == one["delivery"]["items_done"])
    check("flow efficiency is identical too",
          near(many["flow"]["flow_efficiency"], one["flow"]["flow_efficiency"], 0.001),
          (many["flow"]["flow_efficiency"], one["flow"]["flow_efficiency"]))
    check("the pack declares what it counted",
          many["meta"]["issues_in_scope"] == 22 and many["meta"]["issues_in_file"] == 92,
          (many["meta"]["issues_in_scope"], many["meta"]["issues_in_file"]))

    all_scope = M.facts(many_ds, scope="all")
    check("--scope all still available for a period report",
          all_scope["delivery"]["items_total"] == 92, all_scope["delivery"]["items_total"])

    samples = F.throughput_samples(many_ds["issues"], as_of=many_ds["meta"]["asOfDate"])
    check("the forecaster still sees the full history", sum(samples) > 50, sum(samples))


def test_diff():
    ds = json.load(open(ROOT / "data" / "sample-sprint.json"))
    now = M.facts(ds)
    before = json.loads(json.dumps(now))
    before["delivery"]["items_done"] = 8
    before["delivery"]["points_done"] = 28
    before["risk"]["blocked"] = ["BLC-421", "BLC-499"]
    before["meta"]["as_of"] = "2026-08-07"

    d = M.diff(now, before)
    moved = {m["metric"]: m for m in d["moved"]}
    check("diff detects completed items moving", "items completed" in moved, list(moved))
    check("diff labels an increase in completion as better",
          moved.get("items completed", {}).get("reading") == "better")
    check("diff tracks blockers that cleared",
          d["list_changes"]["blocked"]["cleared"] == ["BLC-499"], d["list_changes"].get("blocked"))
    check("diff tracks new blockers",
          sorted(d["list_changes"]["blocked"]["new"]) == ["BLC-429", "BLC-441"],
          d["list_changes"].get("blocked"))


# =====================================================================
# 2. the forecast behaves like a forecast
# =====================================================================
def test_forecast_behaviour():
    ds = json.load(open(ROOT / "data" / "sample-multi-sprint.json"))
    issues = ds["issues"]
    as_of = ds["meta"]["asOfDate"]
    samples = F.throughput_samples(issues, as_of=as_of)

    check("throughput window has enough observations", len(samples) >= 30, len(samples))
    check("zero-throughput days are kept", 0 in samples,
          "a model that never samples zero will never predict a stall")

    a = F.forecast_completion(10, samples, as_of)
    b = F.forecast_completion(10, samples, as_of)
    check("same inputs give the same answer", a.percentiles == b.percentiles)

    days = [a.days[p] for p in F.PERCENTILES]
    check("percentiles are monotonic", days == sorted(days), days)
    check("p85 is later than p50", a.days[85] > a.days[50], a.days)

    more = F.forecast_completion(25, samples, as_of)
    check("more remaining work finishes later", more.days[85] > a.days[85],
          (a.days[85], more.days[85]))

    growth = F.scope_growth_history(json.load(open(ROOT / "agent" / "snapshots" / "scope.json")))
    grown = F.forecast_completion(10, samples, as_of, scope_growth=growth)
    check("scope growth pushes the date out", grown.days[85] >= a.days[85],
          (a.days[85], grown.days[85]))
    check("scope assumption is stated in the basis", "scope growth applied" in grown.basis, grown.basis)
    check("frozen-scope assumption is stated when unknown", "scope assumed frozen" in a.basis, a.basis)

    probable = F.forecast_completion(10, samples, as_of, target_date=ds["meta"]["endDate"])
    check("probability against an existing date is produced",
          probable.prob_by_target is not None and 0 <= probable.prob_by_target <= 1,
          probable.prob_by_target)


def test_commitment_sizing():
    """Commitment recommendations must be in items, from a distribution."""
    ds = json.load(open(ROOT / "data" / "sample-multi-sprint.json"))
    samples = F.throughput_samples(ds["issues"], as_of=ds["meta"]["asOfDate"])

    rec = F.recommend_commitment(samples, 10)
    check("commitment is sized in items", rec["unit"] == "items", rec["unit"])
    check("the recommendation is the 85% figure, not the median",
          rec["recommended"] == rec["commit_at"][85], (rec["recommended"], rec["commit_at"][85]))
    check("the 85% commitment is below the median",
          rec["recommended"] < rec["stretch_median"], (rec["recommended"], rec["stretch_median"]))
    check("higher confidence means a smaller commitment",
          rec["commit_at"][95] <= rec["commit_at"][85] <= rec["commit_at"][50], rec["commit_at"])
    check("a longer sprint allows a bigger commitment",
          F.recommend_commitment(samples, 20)["recommended"] > rec["recommended"])
    check("commitment sizing refuses on thin data",
          isinstance(F.recommend_commitment([0, 1, 0], 10), F.Refusal))
    check("commitment sizing refuses without a sprint length",
          isinstance(F.recommend_commitment(samples, 0), F.Refusal))


def test_size_stability():
    """Item counting assumes items are interchangeable. Detect when they stop being."""
    real = F.size_stability(json.load(open(ROOT / "data" / "sample-multi-sprint.json"))["issues"],
                            as_of="2026-08-10")
    check("size stability is assessable on 12 weeks", real.get("available"))
    check("the sample team is safe to count", real["safe_to_count_items"], real["warnings"])
    check("spread is reported as p85/p50", real["p85_over_p50"] is not None, real["p85_over_p50"])

    # a team that starts splitting: cycle time halves AND throughput doubles
    def item(n, start, resolved):
        return {"key": "S-%d" % n, "statusCategory": "Done",
                "created": start, "started": start, "resolved": resolved}

    splitting = []
    n = 0
    for wk in range(6):                       # slow half: 2 items/week, 10 days each
        for j in range(2):
            n += 1
            d0 = F.add_working_days(F._d("2026-04-06"), wk * 5)
            splitting.append(item(n, d0.isoformat(), F.add_working_days(d0, 10).isoformat()))
    for wk in range(6):                       # fast half: 6 items/week, 1 day each
        for j in range(6):
            n += 1
            d0 = F.add_working_days(F._d("2026-06-15"), wk * 5)
            splitting.append(item(n, d0.isoformat(), F.add_working_days(d0, 1).isoformat()))

    sp = F.size_stability(splitting, as_of="2026-07-31", window_days=180)
    check("splitting work smaller is caught, not read as speed",
          not sp["safe_to_count_items"], sp["warnings"])
    check("the warning names splitting as the likely cause",
          any("split" in w for w in sp["warnings"]), sp["warnings"])
    check("a genuine slowdown is described differently from splitting",
          sp["median_cycle_change"] < 0 and sp["throughput_change"] > 0,
          (sp["median_cycle_change"], sp["throughput_change"]))
    check("size stability refuses on too few items",
          isinstance(F.size_stability(splitting[:4]), F.Refusal))


def test_refusals():
    thin = json.load(open(ROOT / "data" / "sample-sprint.json"))
    samples = F.throughput_samples(thin["issues"], as_of=thin["meta"]["asOfDate"])
    r = F.forecast_completion(10, samples, thin["meta"]["asOfDate"])
    check("one sprint of data is refused, not stretched", isinstance(r, F.Refusal), type(r).__name__)
    check("the refusal says the data is absent, not noisy",
          "absent, not noisy" in r.sentence(), r.sentence())

    r2 = F.forecast_completion(0, [1] * 40, "2026-08-10")
    check("nothing outstanding is refused", isinstance(r2, F.Refusal))
    r3 = F.forecast_completion(5, [0] * 40, "2026-08-10")
    check("a stalled team is refused rather than forecast", isinstance(r3, F.Refusal))

    thin_cycles = [{"key": "A", "statusCategory": "Done", "started": "2026-08-03",
                    "resolved": "2026-08-05", "created": "2026-08-01"}]
    check("ageing risk refuses on too few cycle samples",
          isinstance(F.item_risk(thin_cycles, "2026-08-10"), F.Refusal))


def test_item_risk_units():
    ds = json.load(open(ROOT / "data" / "sample-multi-sprint.json"))
    ir = F.item_risk(ds["issues"], ds["meta"]["asOfDate"])
    check("item risk is available on 12 weeks of data", ir.get("available"))
    check("both time measures are reported",
          ir["cycle_p85_days"] is not None and ir["lead_p85_days"] is not None,
          (ir["cycle_p85_days"], ir["lead_p85_days"]))
    unstarted = [r for r in ir["items"] if r["active_days"] is None]
    check("an unstarted item is not given a duration forecast",
          all("cannot be forecast" in r["verdict"] for r in unstarted),
          [r["key"] for r in unstarted])
    check("the two measures are explained rather than reconciled silently",
          "queue time" in ir["note"])


# =====================================================================
# 3. calibration scoring actually discriminates
# =====================================================================
def test_calibration():
    rng = random.Random(3)
    honest = [{"probability": p, "resolved": rng.random() < p}
              for p in [0.1, 0.3, 0.5, 0.7, 0.9] * 12]
    liar = [{"probability": 0.9, "resolved": rng.random() < 0.3} for _ in range(60)]

    h, l = F.score_calibration(honest), F.score_calibration(liar)
    check("an honest forecaster scores well", h["brier_score"] < 0.20, h["brier_score"])
    check("an overconfident forecaster is caught", l["brier_score"] > 0.30, l["brier_score"])
    check("the verdict tells you to stop publishing",
          "not calibrated" in l["interpretation"], l["interpretation"])
    check("too few resolved forecasts is refused",
          isinstance(F.score_calibration(honest[:5]), F.Refusal))


# =====================================================================
# 4. backtest — would this forecast have been right?
# =====================================================================
def test_backtest():
    """Walk forward through history with NON-OVERLAPPING horizons.

    Two methodological points, both of which are easy to get wrong and both of
    which make a forecaster look better than it is:

      1. Only score a cutoff if a full horizon of real data exists after it.
         Otherwise the actual count is truncated by the file ending rather than
         by the team, and every forecast looks optimistic.
      2. Do not overlap horizons. Sliding a 15-day window forward two days at a
         time gives you ten trials that are really one, so a single slow
         fortnight is counted ten times and the coverage figure is fiction.

    Non-overlapping windows leave few trials, so this is a smoke test that the
    forecaster is not wildly miscalibrated — not a calibration proof. Real
    calibration comes from scoring published forecasts in production, which is
    what `score_calibration` and the forecast log are for.
    """
    ds = json.load(open(ROOT / "data" / "sample-multi-sprint.json"))
    issues = [i for i in ds["issues"] if i.get("resolved")]
    days = sorted({i["resolved"] for i in issues})
    last_day = days[-1]

    HORIZON = 5                       # one working week
    hits = {p: 0 for p in F.PERCENTILES}
    trials, skipped = 0, 0
    detail = []

    cut = days[len(days) // 3]        # warm-up period first, then walk forward
    while True:
        horizon_end = F.add_working_days(F._d(cut), HORIZON).isoformat()
        if horizon_end > last_day:
            skipped += 1
            break
        past = [i for i in issues if i["resolved"] <= cut]
        samples = F.throughput_samples(past, as_of=cut)
        if len(samples) >= F.MIN_THROUGHPUT_SAMPLES and sum(samples) >= F.MIN_COMPLETED_ITEMS:
            fc = F.forecast_count_by_date(samples, cut, horizon_end)
            if getattr(fc, "available", False):
                actual = sum(1 for i in issues if cut < i["resolved"] <= horizon_end)
                trials += 1
                detail.append((cut, fc.percentiles[50], fc.percentiles[85], actual))
                for p in F.PERCENTILES:
                    if actual >= fc.percentiles[p]:
                        hits[p] += 1
        cut = horizon_end             # next window starts where this one ended

    print("        %d non-overlapping windows of %d working days (%d skipped for a short horizon)"
          % (trials, HORIZON, skipped))
    for c, p50, p85, act in detail:
        print("          from %s: forecast >=%d (p50) / >=%d (p85), actual %d"
              % (c, p50, p85, act))
    check("backtest ran on enough independent windows", trials >= 5, trials)

    if trials:
        cov = {p: round(hits[p] / trials, 2) for p in F.PERCENTILES}
        print("        coverage: " + "  ".join("p%d=%.0f%%" % (p, cov[p] * 100) for p in F.PERCENTILES))
        check("the 95% floor is cleared far more often than the 50% floor",
              cov[95] >= cov[50], cov)
        check("the 95% floor is rarely missed", cov[95] >= 0.75, cov)
        check("coverage is monotonic across percentiles",
              [cov[p] for p in F.PERCENTILES] == sorted(cov[p] for p in F.PERCENTILES), cov)
        check("the forecaster is not absurdly optimistic at the median", cov[50] >= 0.25, cov)


if __name__ == "__main__":
    print("facts pack vs the dashboard")
    test_facts()
    print("reporting scope vs forecasting scope")
    test_reporting_scope()
    print("change detection")
    test_diff()
    print("forecast behaviour")
    test_forecast_behaviour()
    print("commitment sizing")
    test_commitment_sizing()
    print("item-size stability")
    test_size_stability()
    print("refusals")
    test_refusals()
    print("ageing risk")
    test_item_risk_units()
    print("calibration scoring")
    test_calibration()
    print("backtest")
    test_backtest()

    print()
    if failures:
        print("%d check(s) failed: %s" % (len(failures), ", ".join(failures)))
        sys.exit(1)
    print("all agent checks passed")
