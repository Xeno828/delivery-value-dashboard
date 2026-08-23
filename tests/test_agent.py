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
import intake as I            # noqa: E402
import metrics as M           # noqa: E402
import orgconfig as OC        # noqa: E402

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
# =====================================================================
# 5. intake — forecasting an ask that does not exist yet
# =====================================================================
def _intake_ds():
    p = ROOT / "data" / "demo-intake-bundle.json"
    if not p.exists():
        return None
    return json.load(open(p))


def test_intake_sizing():
    ds = _intake_ds()
    if ds is None:
        check("intake demo bundle exists", False, "run scripts/make_intake_demo.py")
        return
    issues, _ = I.board_issues(ds, "42")
    sizes = I.epic_sizes(issues, as_of="2026-08-10")
    check("finished epics form a reference class", len(sizes) >= I.MIN_REFERENCE_EPICS, len(sizes))
    check("still-growing epics are excluded",
          all(s["done"] / s["items"] >= 0.9 for s in sizes),
          [s["epic"] for s in sizes if s["done"] / s["items"] < 0.9][:2])

    scale = I.tshirt_scale(sizes)
    check("a t-shirt scale calibrates from the board's own history", scale.get("available"), scale)
    bands = scale["bands"]
    check("all four bands are populated", sorted(bands) == ["L", "M", "S", "XL"], sorted(bands))
    order = [bands[k]["median"] for k in ("S", "M", "L", "XL")]
    check("band medians increase S < M < L < XL", order == sorted(order), order)
    check("bands do not overlap",
          all(bands[a]["range"][1] < bands[b]["range"][0]
              for a, b in (("S", "M"), ("M", "L"), ("L", "XL"))),
          {k: bands[k]["range"] for k in bands})

    thin = I.tshirt_scale(sizes[:3])
    check("a thin history refuses a t-shirt scale rather than inventing bands",
          isinstance(thin, I.Refusal), type(thin).__name__)


def test_intake_scope():
    """The three ways a forecast can be built from the wrong slice of the file.

    All three were live defects. None of them fails loudly — each one just
    returns a plausible number computed against data that does not belong to
    the team being forecast, which is the worst failure mode a forecaster has.
    """
    ds = _intake_ds()
    if ds is None:
        return
    issues, ctx = I.board_issues(ds, "42")
    board_ctxs = [c for c in ds["contexts"] if str(c.get("boardId")) == "42"]
    latest = max(c.get("endDate") or c.get("startDate") or "" for c in board_ctxs)
    check("the board's most recent sprint supplies as-of, not its first",
          (ctx.get("endDate") or ctx.get("startDate")) == latest or
          ctx.get("sprintState") == "active",
          {"picked": ctx["id"], "latest": latest})

    # The trailing throughput window must land on data that exists. Anchoring
    # it to a stale sprint quietly forecast against a quarter with almost no
    # deliveries and returned 77 working days for a 16-item ask.
    as_of = ctx.get("asOfDate") or "2026-08-10"
    thr = F.throughput_samples(issues, as_of=as_of)
    check("throughput is drawn from a window with real delivery in it",
          thr and sum(thr) >= F.MIN_COMPLETED_ITEMS, sum(thr or [0]))
    check("the implied rate is a working team, not a stalled one",
          thr and sum(thr) / len(thr) > 0.4, round(sum(thr) / len(thr), 2) if thr else None)

    # Interruption belongs to the team being forecast.
    cap42 = I.capacity(ds, issues, as_of, "realistic")
    other = next((str(c["boardId"]) for c in ds["contexts"]
                  if str(c.get("boardId")) != "42"), None)
    if other:
        iss_o, ctx_o = I.board_issues(ds, other)
        cap_o = I.capacity(ds, iss_o, ctx_o.get("asOfDate") or as_of, "realistic")
        if not isinstance(cap42, I.Refusal) and not isinstance(cap_o, I.Refusal):
            check("interruption is measured per board, not inherited from the file",
                  cap42["discount"] != cap_o["discount"] or cap42["discount"] == 0,
                  {"board42": cap42["discount"], "board" + other: cap_o["discount"]})

    # Work raised after the forecast date cannot already be queued ahead of it.
    early = I.queue_ahead(issues, "2026-06-01")
    late = I.queue_ahead(issues, as_of)
    check("the queue only counts work that existed at the forecast date",
          len(early) <= len(late), {"2026-06-01": len(early), as_of: len(late)})


def test_intake_forecast():
    ds = _intake_ds()
    if ds is None:
        return
    ask = {"id": "T", "title": "t", "team": "42",
           "sizing": {"method": "tshirt", "size": "L"}, "neededBy": "2026-10-30"}
    r = I.forecast_ask(ds, dict(ask), board="42", as_of="2026-08-10")
    check("an intake forecast is produced", r.get("available"), r.get("sentence"))

    e, real = r["scenarios"]["earliest"], r["scenarios"]["realistic"]
    check("both scenarios are returned", e["available"] and real["available"])
    check("realistic is never earlier than earliest possible",
          real["working_days"][85] >= e["working_days"][85],
          (e["working_days"][85], real["working_days"][85]))
    check("the realistic scenario queues behind committed work", real["queue_items"] > 0,
          real["queue_items"])
    check("interruption is measured, not assumed", real["interruption_discount"] > 0,
          real["interruption_discount"])
    check("the cost of the existing queue is reported", r["cost_of_queue_days"] > 0,
          r["cost_of_queue_days"])
    days = [r["scenarios"]["realistic"]["working_days"][p] for p in I.PERCENTILES]
    check("percentiles are monotonic", days == sorted(days), days)

    again = I.forecast_ask(ds, dict(ask), board="42", as_of="2026-08-10")
    check("same ask, same answer",
          again["scenarios"]["realistic"]["dates"] == real["dates"])

    bigger = I.forecast_ask(ds, dict(ask, sizing={"method": "tshirt", "size": "XL"}),
                            board="42", as_of="2026-08-10")
    check("an XL ask lands later than an L ask",
          bigger["scenarios"]["realistic"]["working_days"][85] > real["working_days"][85],
          (real["working_days"][85], bigger["scenarios"]["realistic"]["working_days"][85]))


def test_intake_uncertainty_attribution():
    """The headline output: is the range driven by not knowing the size, or by
    normal delivery variability? If it cannot tell those apart it is useless."""
    ds = _intake_ds()
    if ds is None:
        return
    vague = {"id": "V", "title": "v", "team": "42", "neededBy": "2026-11-30",
             "sizing": {"method": "explicit", "minItems": 6, "likelyItems": 16, "maxItems": 55}}
    refined = {"id": "R", "title": "r", "team": "42", "neededBy": "2026-11-30",
               "sizing": {"method": "explicit", "minItems": 15, "likelyItems": 16, "maxItems": 18}}
    v = I.forecast_ask(ds, vague, board="42", as_of="2026-08-10")["uncertainty"]
    r = I.forecast_ask(ds, refined, board="42", as_of="2026-08-10")["uncertainty"]

    check("a vaguely sized ask is dominated by size uncertainty",
          v["dominant"] == "size", (v["dominant"], v["size_share"]))
    check("a refined ask is dominated by delivery variability",
          r["dominant"] == "delivery", (r["dominant"], r["size_share"]))
    check("refining an ask narrows the forecast",
          r["total_spread_days"] < v["total_spread_days"],
          (v["total_spread_days"], r["total_spread_days"]))
    check("the shares sum to one",
          abs(v["size_share"] + v["delivery_share"] - 1) < 0.01)
    check("the reading tells the reader what to do",
          "refin" in v["reading"].lower(), v["reading"][:60])


def test_intake_readiness_and_refusals():
    ds = _intake_ds()
    if ds is None:
        return
    bare = I.readiness({"title": "something"})
    check("an ask with no team or sizing is not forecastable", not bare["forecastable"],
          bare["verdict"])
    check("it names what is missing", len(bare["missing_required"]) >= 2,
          [m["field"] for m in bare["missing_required"]])

    complete = I.readiness(json.load(open(ROOT / "data" / "asks" / "INTAKE-2026-015.json")))
    check("a refined example ask is forecastable", complete["forecastable"], complete["verdict"])

    unbasis = I.readiness({"title": "t", "team": "42", "sizing": {"method": "tshirt"},
                           "valueEstimate": {"amount": 100000}})
    check("a value amount with no basis is called out",
          any(g["field"] == "valueEstimate.basis" for g in unbasis["gaps"]),
          [g["field"] for g in unbasis["gaps"]])

    bad = I.forecast_ask(ds, {"id": "X", "title": "x", "team": "42",
                              "sizing": {"method": "explicit", "minItems": 20,
                                         "likelyItems": 5, "maxItems": 10}},
                         board="42", as_of="2026-08-10")
    check("nonsensical explicit sizing is refused", not bad.get("available"), bad.get("sentence"))

    nohist = {"contexts": [], "issues": [{"key": "A-1", "summary": "s", "status": "Done",
                                          "statusCategory": "Done", "created": "2026-08-01",
                                          "resolved": "2026-08-02", "epic": "E"}]}
    thin = I.forecast_ask(nohist, {"id": "Y", "title": "y", "team": "x",
                                   "sizing": {"method": "reference-class"}}, as_of="2026-08-10")
    check("a team with no history refuses rather than guessing", not thin.get("available"))
    check("the refusal says the evidence is absent",
          "absent, not noisy" in (thin.get("sentence") or ""), thin.get("sentence"))


def test_intake_sequencing():
    ds = _intake_ds()
    if ds is None:
        return
    asks = [json.load(open(p)) for p in sorted((ROOT / "data" / "asks").glob("*.json"))]
    res = I.sequence(ds, asks, board="42", as_of="2026-08-10")
    check("sequencing runs on the example asks", res.get("available"), res.get("sentence"))
    check("every ordering is evaluated", len(res["orderings"]) == len(asks), len(res["orderings"]))
    check("no priority score is invented",
          all("score" not in json.dumps(o) for o in res["orderings"]))
    check("an ask that misses its date in every ordering is called out",
          isinstance(res["unachievable_at_any_priority"], list))
    if res["unachievable_at_any_priority"]:
        u = res["unachievable_at_any_priority"][0]
        check("it says how far short, in days", u["short_by_days"] > 0, u)
    check("each ordering reports what it costs the others",
          all("delays_others_by_days" in c for c in res["comparison"]))

    one = I.sequence(ds, asks[:1], board="42", as_of="2026-08-10")
    check("sequencing a single ask is refused", not one.get("available"), one.get("sentence"))


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


def test_full_history_window():
    """build() samples every recorded day rather than a 90-day tail, so the
    dashboard tile and the CLI cannot disagree about which history they used.

    On every dataset in this repo the two are identical, because none of them
    spans more than 90 days. That is the point of pinning it: the day a longer
    dataset lands, the divergence shows up here rather than in a forecast
    somebody has already quoted in a steering meeting.
    """
    for name in ("sample-bundle.json", "sample-multi-sprint.json", "demo-bundle.json"):
        ds = json.loads((ROOT / "data" / name).read_text())
        issues = ds["issues"]
        as_of = (ds.get("meta") or {}).get("asOfDate") or max(
            i["resolved"] for i in issues if i.get("resolved"))
        tail = F.throughput_samples(issues, as_of=as_of)
        whole = F.throughput_samples(
            issues, window_days=F.full_history_days(issues, as_of), as_of=as_of)
        check("%s: full history matches the 90-day tail" % name, tail == whole,
              "%d obs/%d items vs %d/%d" % (len(tail), sum(tail), len(whole), sum(whole)))
    # A trial that runs out of horizon is not a finished trial, and every
    # percentile silently reading exactly HORIZON is the worst kind of wrong
    # number: uniform, precise and meaningless.
    ds = json.loads((ROOT / "data" / "sample-multi-sprint.json").read_text())
    thr = F.throughput_samples(ds["issues"], as_of=ds["meta"]["asOfDate"])
    small = F.forecast_completion(10, thr, ds["meta"]["asOfDate"])
    check("a normal forecast finishes inside the horizon", small.unfinished_fraction == 0,
          small.unfinished_fraction)
    huge = F.forecast_completion(5000, thr, ds["meta"]["asOfDate"])
    check("a forecast that outruns the horizon reports it",
          huge.unfinished_fraction > 0 and "floor rather than an estimate" in huge.basis,
          huge.unfinished_fraction)
    check("the horizon is named in the basis, not just implied",
          str(F.HORIZON) in huge.basis, huge.basis[-90:])

    span = F.full_history_days(
        json.loads((ROOT / "data" / "sample-multi-sprint.json").read_text())["issues"],
        "2026-08-10")
    check("full_history_days reports the real span", span == 77, span)


# =====================================================================
# organisation config — the assumptions that differ per customer
# =====================================================================
def test_org_config():
    """Three things have to hold: nothing changes when the config is absent,
    the right things change when it is present, and a wrong config is refused
    rather than half-applied."""

    # ---- absent means unchanged. This is the whole adoption story: every file
    # that predates the config keeps producing the number it produced before.
    ds = json.loads((ROOT / "data" / "sample-multi-sprint.json").read_text())
    before = F.build(json.loads(json.dumps(ds)))
    tagged = json.loads(json.dumps(ds))
    tagged["orgConfig"] = json.loads(json.dumps(OC.DEFAULTS))
    after = F.build(tagged)
    check("spelling out the defaults changes no forecast figure",
          before["sprint_completion"]["percentiles"] == after["sprint_completion"]["percentiles"],
          (before["sprint_completion"]["percentiles"], after["sprint_completion"]["percentiles"]))

    # ---- present means applied. A shorter week must move the dates, or the
    # config is decorative and nobody finds out until a customer complains.
    short = json.loads(json.dumps(ds))
    short["orgConfig"] = {"workingWeek": ["mon", "tue", "wed", "thu"]}
    moved = F.build(short)
    check("a four-day week pushes the forecast out",
          moved["sprint_completion"]["percentiles"][85] >
          before["sprint_completion"]["percentiles"][85],
          (before["sprint_completion"]["percentiles"][85],
           moved["sprint_completion"]["percentiles"][85]))
    check("the forecast names the calendar it used",
          "4-day working week" in moved["inputs"]["calendar"], moved["inputs"]["calendar"])

    # ---- holidays are working-day only. An item raised 21 days ago is 21 days
    # old whether or not the office was shut. A holiday that shortened an age
    # would be the same lie of convenience as skipping weekends, and a silent
    # disagreement between these two units has shipped here once already.
    hol = OC.merge(OC.DEFAULTS, {"holidays": ["2026-08-05", "2026-08-06"]})
    check("holidays come out of the working week",
          len(OC.working_days("2026-08-03", "2026-08-07", hol)) == 3,
          OC.working_days_iso("2026-08-03", "2026-08-07", hol))
    check("holidays do not touch calendar elapsed time",
          M.elapsed_days("2026-08-03", "2026-08-07") == 4,
          M.elapsed_days("2026-08-03", "2026-08-07"))
    check("add_working_days skips holidays too",
          OC.add_working_days("2026-08-04", 1, hol).isoformat() == "2026-08-07",
          OC.add_working_days("2026-08-04", 1, hol).isoformat())

    # ---- statuses
    st = OC.Statuses(OC.merge(OC.DEFAULTS, {"statuses": {"done": ["Signed off"]}}))
    check("a configured status maps to done", st.category("Signed off") == "Done")
    check("matching ignores case and spacing", st.category("  signed   OFF ") == "Done")
    check("the inProgress list survives naming only done",
          st.category("In Review") == "In Progress", st.category("In Review"))
    # The quiet failure this exists to prevent: a column nobody configured, read
    # as To Do, flattening the burndown with nothing on screen to say why.
    st.category("Awaiting legal")
    check("an unknown status is recorded, not swallowed",
          st.unmatched == ["Awaiting legal"], st.unmatched)
    check("the tracker's own category is trusted over the fallback regex",
          OC.Statuses(OC.DEFAULTS).category("Parked", "Done") == "Done")

    # ---- refusing a bad config. Each of these has to be named rather than
    # silently corrected: a typo that fell back to a five-day week would move
    # every forecast in the product with nothing saying so.
    bad = [
        ({"workingWeek": []}, "workingWeek"),
        ({"workingWeek": ["mon", "funday"]}, "funday"),
        ({"holidays": ["not-a-date"]}, "not-a-date"),
        ({"sprintLengthDays": 0}, "sprintLengthDays"),
        ({"sprintLengthDays": 14.5}, "sprintLengthDays"),
        ({"statuses": {"done": ["Done"], "inProgress": ["done"]}}, "both"),
    ]
    for override, needle in bad:
        problems = OC.validate(OC.merge(OC.DEFAULTS, override))
        check("a bad config is refused and says why: %s" % needle,
              any(needle in p for p in problems), problems or "accepted")
    check("the shipped config is valid",
          OC.validate(OC.load(str(ROOT / "config" / "organisation.json"))) == [])

    # ---- the facts pack states its calendar, as the forecast does
    f = M.facts(json.loads((ROOT / "data" / "sample-sprint.json").read_text()))
    check("the facts pack names its calendar",
          "working week" in (f["meta"].get("calendar") or ""), f["meta"].get("calendar"))


if __name__ == "__main__":
    print("facts pack vs the dashboard")
    test_facts()
    print("reporting scope vs forecasting scope")
    test_reporting_scope()
    print("change detection")
    test_diff()
    print("forecast behaviour")
    test_forecast_behaviour()
    print("full-history sampling")
    test_full_history_window()
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
    print("intake — sizing")
    test_intake_sizing()
    print("intake — scope")
    test_intake_scope()
    print("intake — forecast")
    test_intake_forecast()
    print("intake — uncertainty attribution")
    test_intake_uncertainty_attribution()
    print("intake — readiness and refusals")
    test_intake_readiness_and_refusals()
    print("intake — sequencing")
    test_intake_sequencing()
    print("backtest")
    test_backtest()
    print("organisation config")
    test_org_config()

    print()
    if failures:
        print("%d check(s) failed: %s" % (len(failures), ", ".join(failures)))
        sys.exit(1)
    print("all agent checks passed")
