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

import argparse
import io
import json
import pathlib
import random
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent" / "tools"))

sys.path.insert(0, str(ROOT / "scripts"))

import forecast as F          # noqa: E402
import intake as I            # noqa: E402
import metrics as M           # noqa: E402
import orgconfig as OC        # noqa: E402
import fetch_delivery_data as FD   # noqa: E402

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

    # Two reasons there is no capacity answer, and they are not the same one.
    # A target that has passed is a date somebody set and missed; no target at
    # all is a period with no end to forecast against, which is what a rolling
    # window is. Both said "the target date has passed", which sends a reader
    # looking for a deadline nobody set — the same wrong-cause fault ADR 0010
    # found three times in the health score's disclosure.
    dateless = dict(ds, meta={k: v for k, v in ds["meta"].items() if k != "endDate"})
    no_target = F.build(dateless, as_of=ds["meta"]["asOfDate"])["capacity_to_target"]
    check("with no target at all, the refusal says there is no end date",
          no_target["reason"] == "this period has no end date to forecast against",
          no_target["reason"])
    passed = F.build(ds, as_of="2099-01-01")["capacity_to_target"]
    check("and a target that has been and gone still says exactly that",
          passed["reason"] == "the target date has passed", passed["reason"])


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

    # ...and build() must let that refusal through rather than inventing a
    # sprint to get past it. It used to pass `len(...) or 10`, so a dataset
    # that states no dates at all reported a commitment sized against a
    # ten-working-day sprint nobody chose — with the invented length printed
    # in its own basis line, which is what made it read as a measurement.
    dateless = dict(ds, meta={k: v for k, v in ds["meta"].items()
                              if k not in ("startDate", "endDate", "workingDays")})
    nc = F.build(dateless, as_of=ds["meta"]["asOfDate"])["next_commitment"]
    check("build refuses a commitment when the dataset states no sprint length",
          nc.get("available") is False and "sprint length is unknown" in nc.get("reason", ""),
          nc.get("reason"))
    check("the refused commitment carries no figure to quote and no invented length",
          not any(k in nc for k in ("recommended", "commit_at", "sprint_working_days", "basis")),
          sorted(nc))
    check("the refusal keeps the clause that says waiting will not fix it",
          "absent, not noisy" in F.Refusal(**nc).sentence(), F.Refusal(**nc).sentence())

    # The other direction, because a fix that refuses everything also passes
    # the three checks above: a dataset that does state its calendar still
    # gets a figure, sized against the length it actually stated.
    full = F.build(ds, as_of=ds["meta"]["asOfDate"])["next_commitment"]
    check("a dataset that states its calendar still gets a commitment",
          full.get("available") is True, full.get("reason", full.get("recommended")))
    check("the commitment is sized against the stated calendar, not a default",
          full["sprint_working_days"] == len(ds["meta"]["workingDays"]),
          (full["sprint_working_days"], len(ds["meta"]["workingDays"])))


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
# 3b. the forecast log — roadmap item 4c
# =====================================================================
def test_forecast_log():
    """What the forecaster said, written down so it can be scored.

    `score_calibration` has been able to read a log since the tools were
    written and nothing has ever produced one, so the forecaster has never been
    checked against its own history. These are the claims, and the last check
    here is the one that matters: what `claims_from` produces is what
    `score_calibration` reads.
    """
    cap = {"available": True, "target_date": "2026-09-11", "horizon_days": 10,
           "percentiles": {50: 9, 70: 7, 85: 5, 95: 3}, "samples": 40}
    made = "2026-08-28"
    claims = F.claims_from(cap, "MOBL/2/12", "2", made, "MOBL Cowboys")

    check("one claim per percentile, each separately falsifiable",
          [c["probability"] for c in claims] == [0.5, 0.7, 0.85, 0.95],
          [c["probability"] for c in claims])
    check("each states a count and a date a reader could check",
          all(str(c["claimItems"]) in c["label"] and c["horizon"] in c["label"]
              for c in claims), [c["label"] for c in claims])
    check("nothing is stored that identifies an issue or a person",
          all(set(c) <= set(F.CLAIM_FIELDS) for c in claims),
          sorted(set().union(*[set(c) for c in claims]) - set(F.CLAIM_FIELDS)))

    # A forecast that refused made no claim. Logging one anyway would score the
    # forecaster on a prediction it explicitly declined to make.
    check("a refusal is not logged as a prediction",
          F.claims_from({"available": False, "reason": "too little history"},
                        "MOBL/2/12", "2", made) == [], "refusal logged")
    check("and neither is an answer with no target date",
          F.claims_from({"available": True, "percentiles": {50: 9}},
                        "MOBL/2/12", "2", made) == [], "no-horizon logged")

    # A panel load produces a forecast; so does the next one, and the brief.
    # Same claim, same id, so a writer can skip what it already holds instead of
    # scoring one prediction eleven times and calling it eleven observations.
    again = F.claims_from(cap, "MOBL/2/12", "2", made, "MOBL Cowboys")
    check("re-publishing the same forecast produces the same ids",
          [c["id"] for c in again] == [c["id"] for c in claims],
          [c["id"] for c in claims][:2])
    check("and a different day is a different claim",
          F.claim_id("MOBL/2/12", "2026-08-29", 85) != F.claim_id("MOBL/2/12", made, 85),
          F.claim_id("MOBL/2/12", made, 85))

    # ---- the window ----
    #
    # (madeOn, horizon]. An item finished the morning the forecast was made was
    # not predicted, it was history; one finished on the horizon itself counts.
    edge = [{"resolved": made},                    # the day it was made — out
            {"resolved": "2026-08-29"},            # inside
            {"resolved": "2026-09-11"},            # the horizon itself — in
            {"resolved": "2026-09-12"},            # after — out
            {"resolved": None}]                    # never finished
    done, pending = F.resolve_claims(claims, edge, "2026-09-30")
    check("the window is open at the start and closed at the end",
          done[0]["observed"] == 2, [d["observed"] for d in done])
    check("a claim under its number resolves false",
          done[0]["resolved"] is False, done[0])
    check("and one at or over it resolves true",
          F.resolve_claims(
              F.claims_from({"available": True, "target_date": "2026-09-11",
                             "percentiles": {85: 2}}, "c", "2", made),
              edge, "2026-09-30")[0][0]["resolved"] is True, "")

    # ---- what it will not do ----
    still_open, pending = F.resolve_claims(claims, edge, "2026-09-01")
    check("a claim whose horizon has not passed is left alone",
          all(c["resolved"] is None for c in still_open),
          [c["resolved"] for c in still_open])
    check("and the reason says it is waiting, not that it failed",
          pending and "has not passed yet" in pending[0]["why"], pending[:1])

    # Scored once. Recounting later against a board whose issues have moved
    # would quietly change a score that was already published.
    settled = [dict(claims[0], resolved=True, observed=12)]
    rescored, _ = F.resolve_claims(settled, [], "2026-12-31")
    check("a claim already resolved is never rescored",
          rescored[0]["resolved"] is True and rescored[0]["observed"] == 12,
          rescored[0])

    # ---- validation, before writing rather than after reading ----
    good = claims[0]
    check("an honest claim has nothing wrong with it",
          F.problems_in_claim(good) == [], F.problems_in_claim(good))
    check("a probability of 0 or 1 is not a forecast",
          F.problems_in_claim(dict(good, probability=1)) != [], "")
    check("a horizon that is not after the claim is refused",
          any("no window" in x for x in
              F.problems_in_claim(dict(good, horizon=made))),
          F.problems_in_claim(dict(good, horizon=made)))
    check("an entry carrying issue text is refused rather than trimmed",
          any("never anything derived from issue text" in x for x in
              F.problems_in_claim(dict(good, summary="an issue title"))),
          F.problems_in_claim(dict(good, summary="x")))
    check("and something that is not an entry at all is refused readably",
          F.problems_in_claim("a claim") == ["the entry is not an object."],
          F.problems_in_claim("a claim"))

    # ---- the point of all of it ----
    #
    # A log this produced, read by the scorer that has been waiting for one.
    # Eleven forecasts at four percentiles, resolved against a board that
    # delivers about six items a fortnight — the low percentiles claim more
    # than that and miss, the high ones claim less and land, which is what a
    # calibrated forecaster looks like.
    log = []
    for k in range(11):
        day = "2026-0%d-01" % (k % 9 + 1)
        horizon = "2026-0%d-15" % (k % 9 + 1)
        log += F.claims_from({"available": True, "target_date": horizon,
                              "percentiles": {50: 9, 70: 7, 85: 5, 95: 3}},
                             "MOBL/2/%d" % k, "2", day)
        # Six completions inside each window.
        got = [{"resolved": "2026-0%d-1%d" % (k % 9 + 1, d)} for d in range(0, 6)]
        log[-4:], _ = F.resolve_claims(log[-4:], got, "2026-12-31")

    scored = F.score_calibration(log)
    check("the log this produces is one score_calibration can read",
          isinstance(scored, dict) and scored.get("available") is True, scored)
    check("it scores every entry, having resolved every one",
          scored["n"] == len(log), (scored["n"], len(log)))
    check("and it separates the percentiles that missed from the ones that hit",
          {b["stated"] for b in scored["buckets"]} >= {"50–59%", "90–99%"},
          [b["stated"] for b in scored["buckets"]])
    check("a Brier score comes back as a number, which is the whole point",
          isinstance(scored["brier_score"], float), scored["brier_score"])

    # The scorer's own refusal, quoted rather than softened. "Too few resolved
    # forecasts" is a different statement from a bad score and only one of them
    # criticises the forecaster.
    thin = F.score_calibration(log[:4])
    check("a log below the threshold refuses rather than scoring",
          isinstance(thin, F.Refusal), thin)
    note = F.calibration_note(thin, pending=[{"id": "x"}, {"id": "y"}])
    check("and the note says how many are needed and how many are waiting",
          "10 resolved forecasts needed" in note and "2 more are made" in note, note)
    check("a scored log gets the score, not the refusal",
          "Brier" in F.calibration_note(scored), F.calibration_note(scored))


# =====================================================================
# 3c. the search endpoint, which Atlassian removed
# =====================================================================
def test_which_issues_are_asks_and_who_decides():
    """Candidacy — roadmap item 7, ADR 0028.

    Sequencing compares orderings of *asks*, and until this nothing in a Jira
    site said which issues were being weighed against each other. Candidacy is a
    **state, not a type**: an epic already committed and half built is not a
    candidate, so "every epic" would have sequenced decisions already taken —
    worse than refusing, because it would look like advice.
    """
    lvl = lambda k, c, h=1: {"key": k, "hierarchyLevel": h, "candidate": c}

    # Yes, Y and True, case-insensitively, after trimming.
    for said in ("Yes", "yes", "  Y ", "true", "TRUE"):
        check("%r means candidate" % said,
              OC.candidate_answer({"candidate": said}) is True,
              OC.candidate_answer({"candidate": said}))
    for said in ("", "   ", None):
        check("%r means not, and says so as a boolean" % said,
              OC.candidate_answer({"candidate": said}) is False,
              OC.candidate_answer({"candidate": said}))

    # **Three answers, not two.** A value this does not understand is not a no.
    # An epic whose field says "Maybe" is somebody trying to say something, and
    # dropping it out of the comparison silently is how a sequencing table comes
    # to be missing the ask the meeting was about.
    check("an answer nobody can read is neither yes nor no",
          OC.candidate_answer({"candidate": "Maybe"}) == "Maybe",
          OC.candidate_answer({"candidate": "Maybe"}))

    asks, unreadable = OC.candidate_issues([
        lvl("E1", "Yes"), lvl("E2", "y"), lvl("E3", ""), lvl("E4", "Maybe"),
        lvl("S1", "Yes", 0),                       # below the level
        {"key": "OLD", "candidate": "Yes"},        # no level recorded at all
    ])
    check("candidates are the ones that said yes, at or above the level",
          [i["key"] for i in asks] == ["E1", "E2", "OLD"], [i["key"] for i in asks])
    check("a story below the level is not a candidate however it answers",
          "S1" not in [i["key"] for i in asks], [i["key"] for i in asks])
    # Every dataset written before levels existed would otherwise have no
    # candidates at all — the same reason an unlevelled issue still carries
    # value.
    check("an issue with no recorded level still qualifies",
          "OLD" in [i["key"] for i in asks], [i["key"] for i in asks])
    check("and the unreadable answers come back named, not dropped",
          unreadable == [{"key": "E4", "said": "Maybe"}], unreadable)

    # The level is configurable and separate from valueFromHierarchy: the two
    # questions are separate even where a site answers both the same way.
    asks2, _ = OC.candidate_issues([lvl("S1", "Yes", 0)],
                                   dict(OC.DEFAULTS, askFromHierarchy=0))
    check("the level a candidate must reach is the config's to set",
          [i["key"] for i in asks2] == ["S1"], [i["key"] for i in asks2])


def test_the_fetcher_reads_the_fields_this_app_declares():
    """Business value reaches a file, epics included — ADR 0025, 0026, 0027.

    The fetcher wrote `businessValue: 0` and `valueBasis: ""` on every issue of
    every pull ever made. Zero is not absent: `metrics` reports value as
    *unmeasured* when no issue carries the key and as a figure when they do, so
    a hardcoded 0 was the claim that the sprint delivered nothing worth
    anything — a much stronger statement than "nobody has told us", and the
    wrong one.

    Declaring the field is necessary and not sufficient, which is the lesson
    ADR 0026 records: **epics are not on a scrum board**, so a `sprint = N`
    search never returns the issue the value is recorded on. Driven through a
    stub transport, because none of this needs a Jira.
    """
    SITE_FIELDS = [
        {"id": "customfield_10016", "key": "com.pyxis:sp", "name": "Story Points"},
        # A site's own field of the same display name. Matching on the name
        # would read somebody else's numbers and report them as value.
        {"id": "customfield_10077", "key": "acme.custom:bv", "name": "Business Value"},
        {"id": "customfield_10090", "key": "a1b2__business-value", "name": "Business Value"},
        {"id": "customfield_10091", "key": "a1b2__value-basis", "name": "Value Basis"},
    ]

    class Stub:
        def __init__(self, site_fields=SITE_FIELDS):
            self.site_fields, self.asked = site_fields, []

        def get(self, path, **params):
            self.asked.append((path, params))
            if path == "/rest/api/3/field":
                return self.site_fields
            if path.endswith("/sprint"):
                return {"values": [{"id": 7, "name": "S1", "startDate": "2026-08-01",
                                    "endDate": "2026-08-14"}]}
            if path.endswith("/epic"):
                return {"values": [{"key": "E-1"}, {"key": "E-2"}], "isLast": True}
            if path == "/rest/api/3/issue/E-1":
                return _issue("E-1", "Epic", 1, "Done", "2026-08-07",
                              {"customfield_10090": 40000, "customfield_10091": "  three renewals  "})
            if path == "/rest/api/3/issue/E-2":          # finished outside the window
                return _issue("E-2", "Epic", 1, "Done", "2026-07-02",
                              {"customfield_10090": 99999})
            raise AssertionError("unexpected GET %s" % path)

        def post(self, path, json=None):
            class R:
                def raise_for_status(self): return None
                def json(self):
                    return {"issues": [
                        _issue("S-1", "Story", 0, "Done", "2026-08-05",
                               {"customfield_10090": 5000, "customfield_10091": "a guess"}),
                        _issue("S-2", "Story", 0, "To Do", None,
                               {"customfield_10077": 12345}),   # the *other* site's field
                    ]}
            return R()

    def _issue(key, typ, level, status, resolved, extra):
        f = {"summary": key, "issuetype": {"name": typ, "subtask": False,
                                           "hierarchyLevel": level},
             "status": {"name": status, "statusCategory": {"name": status}},
             "created": "2026-08-01", "resolutiondate": resolved, "labels": []}
        f.update(extra)
        return {"key": key, "fields": f, "changelog": {"histories": []}}

    def pull(site_fields=SITE_FIELDS):
        j = FD.Jira(Stub(site_fields), "https://x.atlassian.net")
        args = argparse.Namespace(jira_board=2, jira_jql=None, sp_field=None,
                                  sprint_field=None)
        keep, FD.connect_jira = FD.connect_jira, lambda a=None: j
        try:
            return j, FD.jira_pull(args)
        finally:
            FD.connect_jira = keep

    j, (issues, meta) = pull()
    by = {i["key"]: i for i in issues}

    check("the app's own field is found by key, not by display name",
          by["S-1"]["businessValue"] == 5000, by["S-1"]["businessValue"])
    check("and a site's own field of the same name is not read as value",
          by["S-2"]["businessValue"] is None, by["S-2"]["businessValue"])
    check("an issue with nothing recorded is null, not zero",
          by["S-2"]["businessValue"] is None, by["S-2"]["businessValue"])

    # Epics are not on a scrum board, so the value is on the issue the search
    # never returns. Credited to the period it finished in, and only that one.
    check("the epic that finished in the window is fetched and carries its value",
          by["E-1"]["businessValue"] == 40000, sorted(by))
    check("one that finished outside it is not credited to this sprint",
          "E-2" not in by, sorted(by))
    check("and the basis comes with it, trimmed",
          by["E-1"]["valueBasis"] == "three renewals", repr(by["E-1"]["valueBasis"]))

    # A field in the projection that nothing requests is absent on every issue
    # forever. The rule that caught `businessValue` on Forge for one deploy.
    epic_get = [p for p in j.t.asked if p[0] == "/rest/api/3/issue/E-1"][0]
    check("the value fields are asked for, not merely read",
          "customfield_10090" in epic_get[1]["fields"]
          and "customfield_10091" in epic_get[1]["fields"], epic_get[1]["fields"])

    # A site without the app installed — the ordinary case for the OAuth route,
    # which needs no app registration. The key is absent rather than zero, so
    # `metrics` reports value as unmeasured instead of as nil.
    _, (plain, _m) = pull([SITE_FIELDS[0], SITE_FIELDS[1]])
    check("with no such field on the site the key is omitted, not set to zero",
          all("businessValue" not in i for i in plain), plain[0])
    # `metrics.history_row` decides measured-vs-unmeasured on exactly this:
    # `any("businessValue" in i for i in issues)`. Absent means the row reports
    # `valueDelivered: None`; present means it reports a figure, which for a
    # site with no such field would have been a confident nil.
    check("which is the condition metrics keys unmeasured off",
          any("businessValue" in i for i in issues)
          and not any("businessValue" in i for i in plain),
          {"with field": any("businessValue" in i for i in issues),
           "without": any("businessValue" in i for i in plain)})
    src = (ROOT / "agent" / "tools" / "metrics.py").read_text()
    check("and that condition is still the one metrics uses",
          'any("businessValue" in i for i in issues)' in src,
          [l.strip() for l in src.splitlines() if "businessValue" in l][:2])

    # ---- and which field marks an ask is the organisation's to choose ----
    #
    # Candidacy is the one thing every organisation defines differently, so the
    # app declares a default and refuses to insist on it. ADR 0028.
    SITE = [{"id": "customfield_10741", "name": "Candidate",
             "key": "a1b2__DEVELOPMENT__candidate"},
            {"id": "customfield_10500", "name": "Ready for sequencing",
             "key": "customfield_10500"}]
    jj = FD.Jira.__new__(FD.Jira)
    check("'app' finds this app's own field by its module key",
          jj.find_ask_field("app", SITE) == "customfield_10741",
          jj.find_ask_field("app", SITE))
    check("and so does an unset config",
          jj.find_ask_field(None, SITE) == "customfield_10741",
          jj.find_ask_field(None, SITE))
    check("a named field is matched by id",
          jj.find_ask_field("customfield_10500", SITE) == "customfield_10500",
          jj.find_ask_field("customfield_10500", SITE))
    # Matching a display name is a guess when the app picks the field and an
    # instruction when the organisation names one. This is the second case.
    check("and by display name when the organisation named one",
          jj.find_ask_field("ready for sequencing", SITE) == "customfield_10500",
          jj.find_ask_field("ready for sequencing", SITE))
    check("a field the site does not have is None, not a guess",
          jj.find_ask_field("Nope", SITE) is None, jj.find_ask_field("Nope", SITE))

    # The three module keys are substring-matched, so none may contain another.
    keys = [FD.Jira.BUSINESS_VALUE_KEY, FD.Jira.VALUE_BASIS_KEY, FD.Jira.CANDIDATE_KEY]
    check("no module key is a substring of another",
          all(a == b or a not in b for a in keys for b in keys), keys)


def test_what_the_config_did_not_cover_is_recorded_with_its_evidence():
    """Which statuses were inferred, what each was read as, and on what.

    `unmatched` has always recorded *that* a status was uncovered. It never
    recorded what happened to it, which is the half a reader needs: "Awaiting
    sign-off was read as To Do" is actionable, "Awaiting sign-off matched no
    rule" invites the question this answers.

    It travels in the dataset because inference happens where the data is
    produced. Until it did, a reader of a file had no way to know it had
    happened — the fetcher printed the names once, to a terminal, to whoever
    ran the pull.
    """
    cfg = {"statuses": {"done": ["Done"], "inProgress": ["In Progress"]}}

    S = OC.Statuses(cfg)
    check("a configured status is not reported at all",
          (S.category("Done"), S.inferred) == ("Done", []), S.inferred)

    S = OC.Statuses(cfg)
    S.category("Awaiting sign-off")
    check("an uncovered one is, with what it was read as and from what",
          S.inferred == [{"status": "Awaiting sign-off", "readAs": "To Do",
                          "from": OC.Statuses.FROM_NAME}], S.inferred)

    # The tracker's own category is a statement by the site; the words in a name
    # are a guess here. A status reached down both paths must keep the stronger
    # reading whichever call happened last — reporting a guess for something the
    # tracker classified understates it, and the reverse overstates it.
    for order in (("hint-last", [None, "In Progress"]),
                  ("hint-first", ["In Progress", None])):
        label, hints = order
        S = OC.Statuses(cfg)
        for h in hints:
            S.category("Architecture Review", h)
        check("the tracker's reading wins over the name guess (%s)" % label,
              S.inferred == [{"status": "Architecture Review", "readAs": "In Progress",
                              "from": OC.Statuses.FROM_TRACKER}], S.inferred)

    # A status the tracker classified is still one the config does not name, so
    # it is still reported — `unmatched` deliberately does not, and that
    # difference is why both exist.
    S = OC.Statuses(cfg)
    S.category("Architecture Review", "In Progress")
    check("a status the tracker resolved is reported as inferred",
          [r["status"] for r in S.inferred] == ["Architecture Review"], S.inferred)
    check("and is still absent from unmatched, which means something else",
          S.unmatched == [], S.unmatched)

    # The fetcher writes it into the dataset, where the page reads it.
    src = (ROOT / "scripts" / "fetch_delivery_data.py").read_text()
    check("the fetcher puts it in the dataset's orgConfig, on both write paths",
          src.count('dict(CFG, inferredStatuses=STATUSES.inferred)') == 2,
          src.count('dict(CFG, inferredStatuses=STATUSES.inferred)'))


def test_a_bad_credential_fails_before_it_can_flatten_a_burndown():
    """An unauthenticated pull must stop, not degrade — found against live Jira.

    `/rest/api/3/field` answers **200 to an anonymous caller**: verified on
    2026-08-30 against a real site, which returned twenty-eight system fields
    and no custom ones with no credential at all. So a wrong token does not fail
    where the fetcher first touches Jira. `find_fields` finds no story-point
    field, prints a warning, and the run continues — every issue at zero points
    and a burndown that flattens with nothing saying why.

    On the day this was found the next call happened to be an agile endpoint
    that does demand auth, so the run died with a traceback. That ordering is
    luck. A token with partial permissions, or a site with anonymous agile read,
    gets a complete-looking dashboard instead.

    The same class the Forge path already guards: `forge/src/jira.js` on why the
    story-point field is discovered rather than hardcoded.
    """
    class Stub:
        """Answers `/myself` however the case wants, and counts data calls."""

        def __init__(self, me, boom=None):
            self.me, self.boom, self.paths = me, boom, []

        def get(self, path, **params):
            self.paths.append(path)
            if path == "/rest/api/3/myself":
                if self.boom:
                    raise RuntimeError(self.boom)
                return self.me
            return [{"id": "customfield_1", "name": "Story Points"}]

    def connection(me, boom=None):
        j = FD.Jira.__new__(FD.Jira)
        j.t, j.url = Stub(me, boom), "https://x.atlassian.net"
        return j

    # ---- somebody ----
    j = connection({"accountId": "abc", "displayName": "A Person"})
    me, why = j.whoami()
    check("a real identity comes back with no complaint",
          (me or {}).get("displayName") == "A Person" and why is None, (me, why))

    # ---- nobody, two ways ----
    j = connection({})                       # 200, but names no one
    me, why = j.whoami()
    check("an anonymous 200 is nobody, not somebody",
          me is None and "anonymous" in (why or ""), (me, why))

    j = connection(None, boom="401 Client Error: Unauthorized")
    me, why = j.whoami()
    check("and a refused request is nobody, carrying its reason",
          me is None and "401" in (why or ""), (me, why))

    # ---- and the run stops there ----
    #
    # The point of the check is not that it detects nobody; it is that nothing
    # downstream runs. A warning would have been the old behaviour.
    j = connection({})
    try:
        FD._verified(j, "API token, https://x")
        stopped = False
    except SystemExit as e:
        stopped, msg = True, str(e)
    check("an unauthenticated connection exits rather than warning", stopped, stopped)
    check("and says nothing was pulled",
          "Nothing was pulled" in msg, msg[:80])
    check("and says why the check has to come first",
          "anonymous" in msg and "zero points" in msg, msg[:200])
    check("no data call was made before the identity was known",
          j.t.paths == ["/rest/api/3/myself"], j.t.paths)

    # ---- and it names who, not only which credential ----
    j = connection({"accountId": "abc", "displayName": "A Person"})
    err = io.StringIO()
    keep, sys.stderr = sys.stderr, err
    try:
        FD._verified(j, "API token, https://x")
    finally:
        sys.stderr = keep
    check("a good connection says who it is, not just which credential",
          "A Person" in err.getvalue(), err.getvalue().strip())


def test_search_pages_by_token():
    """`/rest/api/3/search` was removed; `/search/jql` pages by token.

    Not a URL swap. The old endpoint paged by index and returned a `total`, and
    the loop stopped when `startAt >= total`. Against the new shape `total` is
    absent — so `body.get("total", 0)` is 0, the condition is true on the first
    pass, and the pull stops after one page. **One hundred issues reported as
    the whole board**, which is this repository's worst failure: not an error, a
    smaller number that looks exactly like the right one.

    Driven through a stub transport, because the mistake is in the *loop* and a
    loop can be tested without a Jira.
    """
    class Stub:
        """Pages by token, and never returns a `total` — as Jira now does."""

        def __init__(self, pages, isLast_on=None):
            self.pages, self.isLast_on = pages, isLast_on
            self.seen = []            # every body posted, in order
            self.paths = []

        def post(self, path, json=None):
            self.paths.append(path)
            self.seen.append(json)
            token = (json or {}).get("nextPageToken")
            idx = 0 if token is None else int(token)
            issues = self.pages[idx]
            body = {"issues": issues}
            if idx + 1 < len(self.pages):
                body["nextPageToken"] = str(idx + 1)
            if self.isLast_on == idx:
                body["isLast"] = True
            return _Resp(body)

    class _Resp:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self.body

    j = FD.Jira.__new__(FD.Jira)

    # Three pages of two. The old loop would have returned two issues.
    j.t = Stub([[{"key": "A"}, {"key": "B"}],
                [{"key": "C"}, {"key": "D"}],
                [{"key": "E"}]])
    got = j.search("sprint = 1", ["summary"])
    check("every page is followed, not just the first",
          [i["key"] for i in got] == ["A", "B", "C", "D", "E"],
          [i["key"] for i in got])
    check("and it posts to the endpoint that still exists",
          set(j.t.paths) == {"/rest/api/3/search/jql"}, set(j.t.paths))
    check("the first request carries no page token",
          "nextPageToken" not in j.t.seen[0], sorted(j.t.seen[0]))
    check("and every later one carries the token it was given",
          [b.get("nextPageToken") for b in j.t.seen[1:]] == ["1", "2"],
          [b.get("nextPageToken") for b in j.t.seen[1:]])
    check("the changelog is still expanded, which `started` depends on",
          all(b.get("expand") == "changelog" for b in j.t.seen),
          [b.get("expand") for b in j.t.seen][:1])
    check("no request asks for startAt, which the endpoint no longer takes",
          not any("startAt" in b for b in j.t.seen), j.t.seen[0])

    # `isLast` is documented as not returned by every operation, so a missing
    # token has to end it too — and where both are present they must agree.
    j.t = Stub([[{"key": "A"}], [{"key": "B"}], [{"key": "C"}]], isLast_on=1)
    check("isLast ends the walk even while a token is still offered",
          [i["key"] for i in j.search("q", ["summary"])] == ["A", "B"],
          "isLast honoured")

    # One page, no token, no total: the case the old loop got right by accident
    # and the new one must get right on purpose.
    j.t = Stub([[{"key": "A"}, {"key": "B"}]])
    check("a single page with no token and no total returns all of it",
          len(j.search("q", ["summary"])) == 2, "single page")

    # A server that keeps handing back a token must stop this, and it must
    # **raise** rather than return what it has — a short pull is a dashboard
    # that is wrong and looks right.
    class Endless:
        def __init__(self):
            self.n = 0

        def post(self, path, json=None):
            self.n += 1
            return _Resp({"issues": [{"key": "X%d" % self.n}],
                          "nextPageToken": str(self.n)})

    j.t = Endless()
    raised = False
    try:
        j.search("q", ["summary"])
    except RuntimeError as e:
        raised = "looks right" in str(e)
    check("an endless token stream raises rather than truncating",
          raised, "no runaway, no silent short pull")
    check("and it stopped at the stated cap rather than running on",
          j.t.n == FD.Jira.MAX_SEARCH_PAGES, j.t.n)


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


# =====================================================================
# 6. the trend series is a statement about a moment
# =====================================================================
def test_history_row_is_as_of_a_moment():
    """A history row read off *current* status flatters the team, silently.

    This is the bug this section exists for, and it shipped. The bundle path
    derived each closed sprint's row from `statusCategory` at fetch time:
    everything anyone had ever finished counted as completed *in that sprint*,
    and nothing was in progress, because months later nothing is. The further
    back a sprint was, the better it looked — a predictability chart showing a
    commitment met in full, and a Team load card showing no work in progress,
    both computed from data that was never asked the right question.

    Nothing about the output looked wrong, which is what makes it the class
    `CLAUDE.md` says to shout about rather than a rounding error.

    The sprint below is arranged so the two readings disagree by construction:
    one item was still in flight when the sprint closed and was finished five
    weeks later. It is completed today and it was not completed then.
    """
    END = "2026-01-16"          # the sprint closed here
    LATER = "2026-03-01"        # and this is when somebody re-read it

    issues = [
        # finished inside the sprint
        {"key": "A-1", "storyPoints": 3, "statusCategory": "Done",
         "created": "2026-01-02", "started": "2026-01-06", "resolved": "2026-01-10",
         "addedMidSprint": False, "businessValue": 100},
        # started inside the sprint, finished five weeks after it closed.
        # Its status *today* is Done; at the sprint's end it was in progress.
        {"key": "A-2", "storyPoints": 5, "statusCategory": "Done",
         "created": "2026-01-02", "started": "2026-01-12", "resolved": "2026-02-20",
         "addedMidSprint": False, "businessValue": 500},
        # committed and never picked up. Not done, and not work in progress
        # either — absent is not zero.
        {"key": "A-3", "storyPoints": 2, "statusCategory": "To Do",
         "created": "2026-01-02", "started": None, "resolved": None,
         "addedMidSprint": False, "businessValue": 0},
        # arrived after planning and finished before the end
        {"key": "A-4", "storyPoints": 1, "statusCategory": "Done",
         "created": "2026-01-13", "started": "2026-01-14", "resolved": "2026-01-15",
         "addedMidSprint": True, "businessValue": 50},
    ]

    row = M.history_row(issues, "Sprint 1", END)

    check("committed counts what was planned, not what survived",
          row["committedItems"] == 3, row)
    check("completed counts what finished by the sprint's end",
          row["completedItems"] == 2, row)
    check("throughput is the same figure, not a second opinion",
          row["throughput"] == row["completedItems"], row)
    check("an item still in flight at the end is work in progress",
          row["wipItems"] == 1, row)
    # Proved by moving the one variable rather than asserted: the item that was
    # never picked up becomes work in progress the moment it has a start date,
    # and nothing else about the sprint changes.
    started_too = [dict(i, started="2026-01-09") if i["key"] == "A-3" else i
                   for i in issues]
    check("an item never started is not work in progress; one that started is",
          row["wipItems"] == 1
          and M.history_row(started_too, "Sprint 1", END)["wipItems"] == 2,
          {"never_started": row["wipItems"],
           "if_it_had_started": M.history_row(started_too, "Sprint 1", END)["wipItems"]})
    check("unplanned work is counted from the changelog, not from status",
          row["unplannedItems"] == 1, row)
    check("points follow the same boundary as the counts",
          row["completedSP"] == 4.0 and row["committedSP"] == 10.0, row)
    check("value follows it too",
          row["valueDelivered"] == 150, row)

    # The regression itself. Re-reading the same closed sprint later must not
    # improve it — and under the old derivation it did, by exactly this much.
    later = M.history_row(issues, "Sprint 1", LATER)
    check("the fixture actually distinguishes the two readings",
          later["completedItems"] > row["completedItems"],
          "a fixture where both readings agree would pin nothing")
    check("so the row is keyed to the sprint's end, not to the fetch",
          row["completedItems"] == 2 and later["completedItems"] == 3,
          {"at_end": row["completedItems"], "re-read": later["completedItems"]})
    check("and the work in progress a late reader sees is none of it",
          row["wipItems"] == 1 and later["wipItems"] == 0,
          {"at_end": row["wipItems"], "re-read": later["wipItems"]})

    # One derivation, not two. The single-board path appends to the previous
    # file and the bundle path rebuilds from Jira; they used to compute this row
    # separately, and two implementations of one fact disagree eventually.
    appended = FD.build_history(issues, {"sprintName": "Sprint 1", "asOfDate": END}, None)
    check("the fetcher builds its row with the tool's function, not its own",
          appended[-1] == row, {"appended": appended[-1], "direct": row})
    check("and it is the tool's, so the calculator can produce the same row",
          FD.history_row is M.history_row, (FD.history_row, M.history_row))
    # This suite is promised to need nothing but Python 3, and importing the
    # fetcher above broke that: it called sys.exit() at import time when
    # `requests` was absent, so CI failed on a machine that had never installed
    # it while every developer machine passed. The dependency is needed to reach
    # a tracker and for nothing else.
    #
    # Proved in a subprocess with the import genuinely blocked, rather than by
    # looking for a `need_requests` symbol — the symbol existing says nothing
    # about whether importing the module still exits, which was the bug.
    blocked = subprocess.run(
        [sys.executable, "-c",
         "import sys\n"
         "class Block:\n"
         "    def find_spec(self, name, path=None, target=None):\n"
         "        if name == 'requests': raise ImportError('blocked for this test')\n"
         "sys.meta_path.insert(0, Block())\n"
         "sys.path[:0] = ['scripts', 'agent/tools']\n"
         "import fetch_delivery_data as F\n"
         "print('imported')\n"
         "try:\n"
         "    F.need_requests()\n"
         "except SystemExit as e:\n"
         "    print(e)\n"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    check("the fetcher imports with no tracker dependency installed",
          "imported" in blocked.stdout,
          (blocked.stdout.strip()[:120], blocked.stderr.strip()[-160:]))
    check("and still says how to install it at the point it is needed",
          "pip install requests" in blocked.stdout,
          " / ".join(blocked.stdout.split())[:160])


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
    print("the forecast log")
    test_forecast_log()
    print("which issues are asks")
    test_which_issues_are_asks_and_who_decides()
    print("the fields this app declares")
    test_the_fetcher_reads_the_fields_this_app_declares()
    print("statuses the config did not cover")
    test_what_the_config_did_not_cover_is_recorded_with_its_evidence()
    print("the fetcher's credential")
    test_a_bad_credential_fails_before_it_can_flatten_a_burndown()
    print("the search endpoint")
    test_search_pages_by_token()
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
    print("the trend series is about a moment")
    test_history_row_is_as_of_a_moment()

    print()
    if failures:
        print("%d check(s) failed: %s" % (len(failures), ", ".join(failures)))
        sys.exit(1)
    print("all agent checks passed")
