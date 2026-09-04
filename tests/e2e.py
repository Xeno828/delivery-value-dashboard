#!/usr/bin/env python3
"""
End-to-end smoke test. Renders dist/ in a real browser and walks the upload
wizard with the fixture files, asserting the dashboard actually changes.

    pip install playwright && playwright install chromium
    python3 tests/e2e.py
"""

import datetime
import json
import pathlib
import re
import shutil
import subprocess
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "delivery-value-dashboard.html"
FIX = ROOT / "tests" / "fixtures"

failures = []
warnings = []
console = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  — " + str(detail)) if detail else ""))
    if not ok:
        failures.append(name)


def warn(name, ok, detail=""):
    """For a check that could not run rather than one that did not hold.

    Said out loud, never skipped in silence — a check that quietly did not run
    reads exactly like one that passed. But it is not a failure: the Forge
    bundle is an optional build artefact, `forge/static/` is git-ignored, and
    a clean clone that has never run `make forge-static` is not broken.
    """
    print(("  PASS  " if ok else "  WARN  ") + name + (("  — " + str(detail)) if detail else ""))
    if not ok:
        warnings.append(name)


def wizard(page, fixture, mode="replace"):
    """Run one file through choose -> map -> preview -> apply."""
    page.click("#btn-import")
    page.set_input_files("#file", str(FIX / fixture))
    page.wait_for_selector("#step-map:not(.hidden)", timeout=15000)
    mapped = page.eval_on_selector_all(
        '#map-body select', "n => n.filter(s => s.value !== '-1').map(s => s.dataset.field)")
    if mode == "merge":
        page.check('input[name="mergemode"][value="merge"]')
    page.click("#m-preview")
    page.wait_for_selector("#step-preview:not(.hidden)", timeout=10000)
    stats = page.eval_on_selector_all("#prev-stats div b", "n => n.map(e => e.textContent)")
    warns = page.eval_on_selector_all("#prev-warn .warn b", "n => n.map(e => e.textContent)")
    page.click("#m-apply")
    page.wait_for_timeout(700)
    return mapped, stats, warns


def open_picker(page):
    """Idempotent — the popover stays open across preset clicks and renders,
    so a bare click on the button is as likely to close it as open it."""
    if not page.is_visible("#view-pop"):
        page.click("#btn-view")
    page.wait_for_selector("#view-pop:not(.hidden)", timeout=5000)


def health_composition(b):
    """A component that could not be measured is dropped, not scored zero.

    Delivery pace carries the largest of the four weights. Over a sprint whose
    dates were unknown it scored 0/100 and dragged the sample sprint from 52
    and "Needs attention" to 22 and "Off track" — a verdict about delivery,
    produced by the absence of two dates. The disclosure that exists so a
    reader can argue with the method said "no sprint calendar", and said it for
    all three causes, including a rollup that has dates and a points view of
    issues nobody estimated.

    Both halves are pinned here: that the page derives the calendar when
    whatever produced the data did not, and that when it genuinely cannot the
    component leaves the composition instead of scoring it.
    """
    print("\n  health composition")

    CHIP = "() => document.getElementById('t-health').textContent.trim()"
    TT = "() => document.getElementById('t-health').dataset.tt"

    sample = json.loads((ROOT / "data" / "sample-sprint.json").read_text())
    bundle = json.loads((ROOT / "data" / "demo-bundle.json").read_text())

    def without(keys):
        d = json.loads(json.dumps(sample))
        for k in keys:
            d["meta"].pop(k, None)
        for c in d.get("contexts") or []:
            for k in keys:
                c.pop(k, None)
        return d

    page = b.new_page(viewport={"width": 1500, "height": 1000})
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(DIST.as_uri())
    page.wait_for_timeout(700)

    # ---------- baseline ----------
    page.evaluate("d => window.DVD.applyDataset(d)", sample)
    page.wait_for_timeout(500)
    full = page.evaluate(CHIP)
    check("a sprint with a calendar scores from all four measures",
          "/100)" in full and "measures" not in full, full)

    # ---------- the calendar is derived, not demanded ----------
    # forge/src/jira.js sends no workingDays on purpose — which days are worked
    # is organisation config, and resolving it in a resolver would be a fourth
    # opinion. The page derives it under ORG(), exactly as it already derives
    # statusCategory, which is why the score must come out identical. Before it
    # did, every sprint in a Forge tenant lost the largest component of its
    # health score and the two transports rendered different figures from the
    # same sprint.
    page.evaluate("d => window.DVD.applyDataset(d)", without(["workingDays"]))
    page.wait_for_timeout(500)
    check("the page derives the working days the producer left out",
          page.evaluate(CHIP) == full, (page.evaluate(CHIP), full))
    js = page.evaluate("""() => {
      const v = window.DVD.debug.view();
      return [v.meta.workingDays,
              window.DVD.workingDays(v.meta.startDate, v.meta.endDate, window.DVD.orgConfig())];
    }""")
    check("and derives exactly the list orgconfig.py would have written",
          js[0] == js[1] and len(js[0]) > 0, js[0][:3])

    # ---------- no dates at all: the component leaves the composition ----------
    page.evaluate("d => window.DVD.applyDataset(d)",
                  without(["workingDays", "startDate", "endDate"]))
    page.wait_for_timeout(500)
    chip, tt = page.evaluate(CHIP), page.evaluate(TT)
    check("a sprint with no dates drops delivery pace rather than scoring it 0",
          "Delivery pace — <b>not measured</b>" in tt, tt[:130])
    check("the chip says how many measures the score was built from",
          "3 of 4 measures" in chip, chip)
    check("and the score is what the three measured, not that capped by the fourth",
          "(33/100" in chip, chip)

    # No silent caps: the weights a reader is shown must be the weights that
    # multiplied, and they must add up. Printing the nominal 22% beside a
    # figure that was multiplied by 33% is a disclosure that does not reconcile.
    weights = [int(w) for w in re.findall(r"\((\d+)% weight\)", tt)]
    check("the disclosed weights are the re-weighted ones and sum to 100",
          len(weights) == 3 and 99 <= sum(weights) <= 101, weights)

    # ---------- a sprint that has not started ----------
    # `wd.indexOf(now)` fell through to 1 for any as-of date not in the list:
    # before the first day, after the last, or a weekend in between. A
    # tenant's board whose next sprint began in eleven days read "100%
    # elapsed", "-72 pp" and "Off track (29/100)" — a verdict about delivery
    # on a sprint in which no day had been worked. Found by
    # tests/forge_smoke.py, which is the only suite that looks inside the
    # tenant.
    future = json.loads(json.dumps(sample))
    future["meta"]["startDate"], future["meta"]["endDate"] = "2026-08-17", "2026-08-28"
    future["meta"].pop("workingDays", None)   # derived, as a Forge tenant's is
    page.evaluate("d => window.DVD.applyDataset(d)", future)
    page.wait_for_timeout(500)
    chip, tt = page.evaluate(CHIP), page.evaluate(TT)
    kpi = " ".join((page.text_content("#kpis .kpi:nth-child(2)") or "").split())
    verdict = " ".join((page.text_content("#exec-verdict") or "").split())
    check("a sprint that has not started drops delivery pace rather than scoring it",
          "Delivery pace — <b>not measured</b>" in tt, tt[:160])
    # Scope stability goes with it: nothing can have been added after a start
    # that has not happened, and it scored 100/100 for "no mid-sprint
    # additions" on such a sprint, seen in a tenant. Two of four weights gone
    # is under half, so the score refuses — a sprint that has not started has
    # no sprint health yet, and the chip says so rather than scoring hygiene.
    check("and scope stability with it, rather than scoring full marks for no additions",
          "Scope stability — <b>not measured</b>" in tt, tt[:260])
    check("so the score refuses rather than scoring the two measures left",
          "not scored" in chip and "the evidence is absent, not noisy" in tt, chip)
    added_tile = " ".join((page.text_content("#kpis .kpi:nth-child(5)") or "").split())
    check("the Scope added tile says the sprint has not started, and states no zero",
          "not started" in added_tile and not re.search(r"\d+ items? after kickoff|\d+% growth", added_tile), added_tile)
    check("and names the day the clock starts as the cause",
          "has not started" in tt and re.search(r"17 Aug|Aug 17", tt) is not None, tt[:220])
    check("the pace KPI says the sprint has not started, and states no figure",
          "not started" in kpi and not re.search(r"-?\d+ pp|\d+% elapsed", kpi), kpi)
    check("the verdict withholds the pace sentence and says why",
          "has not started" in verdict and "% elapsed" not in verdict, verdict[:200])
    # A Saturday inside the sprint is as far through as the working days
    # already passed — five of ten here — not the whole of it.
    sat = json.loads(json.dumps(sample))
    sat["meta"]["asOfDate"] = "2026-08-08"
    page.evaluate("d => window.DVD.applyDataset(d)", sat)
    page.wait_for_timeout(500)
    kpi = " ".join((page.text_content("#kpis .kpi:nth-child(2)") or "").split())
    check("a Saturday mid-sprint reads as half elapsed, not fully",
          "50% elapsed" in kpi, kpi)
    check("and the score is still built from all four measures",
          "/100)" in page.evaluate(CHIP) and "measures" not in page.evaluate(CHIP), page.evaluate(CHIP))

    # ---------- a rollup has dates and still has no clock ----------
    page.evaluate("d => window.DVD.applyDataset(d)", bundle)
    page.wait_for_timeout(500)
    roll = [c for c in page.evaluate("() => window.DVD.debug.contexts().map(c => c.id)")
            if c.startswith("roll:")][0]
    page.evaluate("i => window.DVD.debug.selectContext(i)", roll)
    page.wait_for_timeout(500)
    tt = page.evaluate(TT)
    check("a rollup drops delivery pace too",
          "Delivery pace — <b>not measured</b>" in tt, tt[:130])
    check("and says it is the rollup, not missing dates — it has dates",
          "rolls up" in tt and "not in the data" not in tt, tt[:190])
    check("the pace KPI names the same cause in its own words",
          "no single sprint clock" in page.text_content("#kpis .kpi:nth-child(2)"),
          page.text_content("#kpis .kpi:nth-child(2)"))

    # ---------- a measure the data does not carry ----------
    # Two of four components read work volume, so in points over an unestimated
    # dataset both are undefined — and they failed in opposite directions:
    # pace scored 0 for a calendar that was present and correct, scope
    # stability scored 100/100 for "no mid-sprint additions" out of nothing.
    unpriced = json.loads(json.dumps(sample))
    for i in unpriced["issues"]:
        i["storyPoints"] = 0
    page.evaluate("d => window.DVD.applyDataset(d)", unpriced)
    page.wait_for_timeout(500)
    check("issues with no estimates still score in items",
          "/100)" in page.evaluate(CHIP), page.evaluate(CHIP))
    page.evaluate("() => window.DVD.debug.setUnit('points')")
    page.wait_for_timeout(500)
    chip, tt = page.evaluate(CHIP), page.evaluate(TT)
    check("but reading them in points refuses rather than scoring half a method",
          "not scored" in chip, chip)
    check("the refusal names the measure, not the calendar",
          "story points" in tt and "sprint calendar" not in tt, tt[:170])
    check("it ends with the clause, untrimmed",
          "the evidence is absent, not noisy" in tt, tt[:200])
    check("and names the measure that would work",
          "Switch the measure to items" in tt, tt[:260])
    check("scope stability is not quietly given full marks for measuring nothing",
          "Scope stability — <b>not measured</b>" in tt, tt[:260])
    page.evaluate("() => window.DVD.debug.setUnit('items')")
    page.wait_for_timeout(400)


    # ---------- a board that runs no sprints ----------
    # The fourth cause, and the one most likely to be reported as the second.
    # A window *has* dates — they are in the picker, beside the board name — so
    # "no sprint dates" would send a reader looking for something that is
    # plainly there. What is missing is the commitment. ADR 0011.
    #
    # Expanding those dates under the org config would have produced twenty-two
    # perfectly real working days, `timeElapsed` of 0.6, and a Pace vs clock
    # figure about a team that never agreed to the deadline it was being
    # measured against. This is the block that stops that.
    flow = flow_board(sample)
    page.evaluate("d => window.DVD.applyDataset(d)", flow)
    page.wait_for_timeout(500)

    js = page.evaluate("""() => {
      const v = window.DVD.debug.view();
      return { kind: v.ctx.kind, days: v.meta.workingDays,
               start: v.meta.startDate, end: v.meta.endDate,
               derivable: window.DVD.workingDays(v.meta.startDate, v.meta.endDate,
                                                 window.DVD.orgConfig()).length };
    }""")
    check("the window is selected and knows what it is", js["kind"] == "window", js["kind"])
    check("it has real dates, so this is not the missing-dates case",
          bool(js["start"]) and bool(js["end"]), (js["start"], js["end"]))
    check("a working-day list could have been derived from them",
          js["derivable"] > 0, js["derivable"])
    check("and the page refuses to derive one anyway — a window is not a clock",
          js["days"] == [], js["days"][:3])

    # A producer that shipped `workingDays` on a window would walk straight
    # past a guard placed after the sent list. Neither transport sends one
    # today, and this does not depend on that staying true.
    sent = json.loads(json.dumps(flow))
    for c in sent["contexts"]:
        # Includes the as-of, so it is a list the page really could have paced against.
        c["workingDays"] = ["2026-07-13", "2026-07-14", "2026-07-15", c["endDate"]]
    page.evaluate("d => window.DVD.applyDataset(d)", sent)
    page.wait_for_timeout(500)
    check("a calendar sent for a window is refused as firmly as a derived one",
          page.evaluate("() => window.DVD.debug.view().meta.workingDays") == []
          and "no sprints on this board" in page.text_content("#kpis .kpi:nth-child(2)"),
          page.evaluate("() => window.DVD.debug.view().meta.workingDays"))
    check("and no pace figure appears with it",
          not re.search(r"-?\d+ pp", page.text_content("#kpis .kpi:nth-child(2)")),
          page.text_content("#kpis .kpi:nth-child(2)"))
    page.evaluate("d => window.DVD.applyDataset(d)", flow)
    page.wait_for_timeout(500)

    # Sprint health is a sprint-board figure. The chip carries the composite
    # this board *can* support instead, and says which one it is carrying —
    # "Flow health" and "Sprint health" are different quantities on different
    # scales of evidence, and a chip reading the same for both would invite
    # comparing two boards that were never measured the same way.
    chip, tt = page.evaluate(CHIP), page.evaluate(TT)
    check("the chip carries flow health, not sprint health",
          "Flow health:" in chip and "Sprint health" not in chip, chip)
    check("and scores it, rather than refusing", "/100)" in chip, chip)
    check("flow efficiency is the component it is built on",
          "Flow efficiency (40% weight)" in tt, tt[:200])
    check("with the same two hygiene measures the sprint score uses",
          "Blockers (30% weight)" in tt and "Ageing work (30% weight)" in tt, tt[:260])
    check("and none of the sprint-shaped ones",
          "Delivery pace" not in tt and "Scope stability" not in tt, tt[:260])
    weights = [int(w) for w in re.findall(r"\((\d+)% weight\)", tt)]
    check("the disclosed weights are three and sum to 100",
          len(weights) == 3 and sum(weights) == 100, weights)
    check("the threshold behind the score is shown, not applied quietly",
          "full marks at 40%" in tt, tt[-260:])
    check("and it says the points toggle cannot move this one",
          "does not move this score" in tt, tt[-200:])

    # Flow efficiency is load-bearing rather than merely heavy. Without it,
    # 60% of the weight survives — comfortably above the half-weight floor —
    # and what is left is hygiene. Calling that *flow* health while the flow
    # measure is the missing one would put the absent part in the name.
    nostart = json.loads(json.dumps(flow))
    for i in nostart["issues"]:
        i.pop("started", None)
    page.evaluate("d => window.DVD.applyDataset(d)", nostart)
    page.wait_for_timeout(500)
    chip, tt = page.evaluate(CHIP), page.evaluate(TT)
    check("without flow efficiency the score refuses rather than scoring the hygiene left over",
          "Flow health: not scored" in chip and "/100)" not in chip, chip)
    check("and names the start date as the thing that is missing",
          "both a start and a resolved date" in tt, tt[:260])
    check("it ends with the clause, untrimmed",
          "the evidence is absent, not noisy" in tt, tt[:400])
    check("and says where the missing field comes from",
          "docs/data-format.md" in tt, tt[:400])
    page.evaluate("d => window.DVD.applyDataset(d)", flow)
    page.wait_for_timeout(500)

    kpi = page.text_content("#kpis .kpi:nth-child(2)")
    check("the pace KPI names the board, not the calendar",
          "no sprints on this board" in kpi and "no sprint dates" not in kpi, kpi)
    check("and states no figure for it", not re.search(r"-?\d+ pp", kpi), kpi)

    # ---------- the tiles that would state a sprint-shaped figure ----------
    # Each says what *it* in particular cannot show. A single banner over the
    # grid was ruled out in ADR 0010 for the reason it throws away everything
    # the page still knows, and that reasoning does not change because the
    # cause is a board rather than an empty selection.
    def tile(sel):
        return page.text_content(sel)

    # Three tiles have no subject at all here, so they are not shown. Refusing
    # in place is right for a condition that might lift — a sprint gets its
    # dates, a points view gets its estimates. This one never lifts, and three
    # permanent apologies across a third of the grid push the tiles that do
    # measure this board below the fold.
    #
    # What keeps that from being a silent cap is that every one of them is
    # named, twice: in the row the reader is already reading, and in the picker
    # with the reason.
    gone = page.evaluate("""() => ['c-burn','c-pred','c-load']
      .map(id => id + ':' + document.getElementById(id).classList.contains('hidden'))""")
    check("the tiles with nothing to show on this board are not shown",
          gone == ["c-burn:true", "c-pred:true", "c-load:true"], gone)
    still = page.evaluate("""() => ['c-kpis','c-exec','c-flow','c-age','c-risk','c-value']
      .filter(id => document.getElementById(id).classList.contains('hidden'))""")
    check("and every tile that measures something still is", still == [], still)

    check("the context bar says the grid is short, where the reader is looking",
          "rolling window, so no burndown or pace" in page.text_content("#ctxbar"),
          page.text_content("#ctxbar")[:200])
    check("and no longer denies a health figure that now exists",
          "sprint health" not in page.text_content("#ctxbar"),
          page.text_content("#ctxbar")[:200])

    page.evaluate("() => document.getElementById('btn-view').click()")
    page.wait_for_timeout(300)
    picker = page.text_content("#vp-count")
    check("the picker names all three and why, rather than counting them",
          "3 not available on this board" in picker
          and "Burndown" in picker and "committed scope" in picker, picker[:260])
    check("and separates them from tiles the reader turned off",
          "hidden:" not in picker, picker[:260])
    disabled = page.evaluate("""() => ['c-burn','c-pred','c-load'].map(id =>
      document.querySelector('[data-tile=\"' + id + '\"]').disabled)""")
    check("their checkboxes say they cannot be turned on, rather than doing nothing",
          disabled == [True, True, True], disabled)
    page.evaluate("() => document.getElementById('btn-view').click()")
    page.wait_for_timeout(200)

    delivered = tile("#kpis .kpi:nth-child(1)")
    check("Delivered refuses: a window has no committed scope to be a share of",
          "no committed scope" in delivered, delivered)
    check("and prints no percentage", not re.search(r"\d", delivered), delivered)

    added = tile("#kpis .kpi:nth-child(5)")
    check("Scope added refuses rather than claiming nothing was added",
          "no sprint for work to be added to" in added, added)
    check("and prints no zero, which would read as a measurement",
          not re.search(r"\d", added), added)

    carry = tile("#kpis .kpi:nth-child(6)")
    check("open work keeps its figure and loses only the sprint-shaped label",
          carry.startswith("Still open") and re.search(r"\d", carry), carry)

    exec_v = tile("#exec-verdict")
    check("the summary states counts and withholds the share",
          "finished in this window" in exec_v and not re.search(r"\(\d+%\)", exec_v), exec_v[:160])

    age = tile("#age-chart")
    check("ageing measures the same days and stops calling them a sprint",
          "fortnight" in age and "sprint" not in age, age[-160:])

    # ---------- what was not examined, as opposed to examined and clear -----
    # "No risks triggered" over a rule that never executed is a clean bill of
    # health nobody checked. Three of the register's eight rules depend on
    # something beyond the issues on screen, and each of them failed silently:
    # the condition was false and the rule vanished.
    risk = tile("#risk-body")
    check("the register says which rules it could not run",
          "were not run against this selection" in risk, risk[-320:])
    check("and names scope growth as one of them",
          "scope growth — this board runs no sprints" in risk, risk[-320:])
    check("and the commitment rule as another",
          "commitment against recent delivery" in risk, risk[-320:])
    check("and claims nothing either way about them",
          "Nothing is claimed either way" in risk, risk[-120:])

    ex = tile("#exec-verdict")
    check("the summary says which sentences it did not write",
          "not reported for this board" in ex, ex[-200:])

    # The third silent rule, and the one a Forge tenant meets: without
    # `started` there is no cycle time, so the flow-efficiency rule cannot run.
    # It vanished without a word, on the measure a board with no sprints most
    # needs. This is what `statusTransitions` over the bridge is for.
    nostart = json.loads(json.dumps(flow))
    for i in nostart["issues"]:
        i.pop("started", None)
    page.evaluate("d => window.DVD.applyDataset(d)", nostart)
    page.wait_for_timeout(500)
    check("a dataset with no start dates says the flow-efficiency rule did not run",
          "flow efficiency — no closed item here carries both a start and a resolved date"
          in tile("#risk-body"), tile("#risk-body")[-260:])
    page.evaluate("d => window.DVD.applyDataset(d)", flow)
    page.wait_for_timeout(500)

    # The same rule on a sprint board: a register that ran everything says
    # nothing, so the note is a disclosure and not decoration.
    page.evaluate("d => window.DVD.applyDataset(d)", sample)
    page.wait_for_timeout(500)
    check("a board where every rule ran says nothing about rules not run",
          "were not run against this selection" not in tile("#risk-body"),
          tile("#risk-body")[-200:])
    check("and its summary withholds no sentence either",
          "Not reported here" not in tile("#exec-verdict"), tile("#exec-verdict")[-160:])
    page.evaluate("d => window.DVD.applyDataset(d)", flow)
    page.wait_for_timeout(500)

    # Three overlapping windows of one board must never be rolled up: the same
    # issue is in all three, so the rollup would hold it three times and every
    # count on the page would be a count of the issues in the selection.
    ids = page.evaluate("() => window.DVD.debug.contexts().map(c => c.id)")
    check("overlapping windows are not offered as a rollup",
          not [i for i in ids if i.startswith("roll:")], ids)
    check("all three windows are still offered", len([i for i in ids if "win:" in i]) == 3, ids)
    # ---------- the flow tiles are the default here, not an extra ----------
    FLOW = ["c-cycle", "c-wip", "c-thr", "c-cfd"]
    on = page.evaluate("""ids => ids.filter(i =>
      !document.getElementById(i).classList.contains('hidden'))""", FLOW)
    check("a flow board shows all four flow tiles by default", on == FLOW, on)

    cyc = tile("#cycle-chart")
    check("cycle time states the percentile a team can quote outward",
          re.search(r"85% of the \d+ items this board finished came in within", cyc), cyc[-220:])
    check("and the dots are individually openable, which is what makes it checkable",
          page.eval_on_selector_all("#cycle-chart [data-cyk]", "n => n.length") > 0)

    wip = tile("#wip-chart")
    check("ageing work in progress compares open work against what closed work took",
          "outlived 85%" in wip or "Nothing open has yet outlived" in wip, wip[-200:])

    thr = tile("#thr-chart")
    check("throughput names the mean and says quiet weeks are part of the series",
          "items a week" in thr and "checked" in thr, thr[-200:])

    cfd = tile("#cfd-chart")
    check("the cumulative flow diagram says it is three bands and not one per column",
          "Three bands, not one per column" in cfd, cfd[-220:])
    check("and says why, rather than leaving a reader to assume the board has three",
          "which column an issue sat in on a given day" in cfd, cfd[-220:])

    check("the picker calls the dropdown what it lists, and lists the windows",
          "Window" in page.text_content("#ctxbar")
          and "Sprint" not in page.text_content("#ctxbar"),
          page.text_content("#ctxbar")[:140])

    # And none of it leaks back into a sprint board.
    page.evaluate("d => window.DVD.applyDataset(d)", sample)
    page.wait_for_timeout(500)
    check("a sprint board is unaffected by any of it", page.evaluate(CHIP) == full,
          (page.evaluate(CHIP), full))
    check("and still calls its own composite by its own name",
          "Sprint health:" in page.evaluate(CHIP), page.evaluate(CHIP))

    check("no console errors while composing the score", not errs, errs[:2])
    page.close()


def flow_board(sample):
    """A bundle whose only board runs no sprints — three overlapping windows.

    Built from the sample sprint's own issues so the selection carries real
    volume: a window that refuses for want of *issues* would prove nothing
    about a window that refuses for want of a sprint, and those are different
    sentences. `addedMidSprint` is stripped for the reason the product gives —
    a board with no sprints has no moment after which work counts as added, so
    the resolver sends false and the page must not read that as "nothing was
    added".
    """
    issues = json.loads(json.dumps(sample["issues"]))
    end = sample["meta"]["asOfDate"]
    ctxs, tagged = [], []
    for days in (14, 30, 90):
        start = (datetime.date.fromisoformat(end)
                 - datetime.timedelta(days=days - 1)).isoformat()
        cid = "SFT/9/win:%dd" % days
        ctxs.append({
            "id": cid, "kind": "window", "source": "jira",
            "projectKey": "SFT", "projectName": "Storefront",
            "boardId": "9", "boardName": "Flow Board", "team": "Flow Board",
            "sprintName": "Last %d days" % days, "sprintState": "window",
            "sprintGoal": "", "startDate": start, "endDate": end,
            "asOfDate": end, "issueCount": len(issues),
        })
        for i in issues:
            c = dict(i, contextId=cid)
            c.pop("addedMidSprint", None)
            tagged.append(c)
    return {"meta": dict(sample["meta"], sprintName="Last 30 days",
                         startDate=ctxs[1]["startDate"], endDate=end,
                         workingDays=[]),
            "orgConfig": sample.get("orgConfig") or {},
            "contexts": ctxs, "issues": tagged, "byContext": {},
            "defaultContextId": "SFT/9/win:30d"}

def empty_selection(b):
    """Zero issues is a refusal, not a zero.

    The case that shipped was the sprint health score. With no items, every
    component of it fell to full marks or a neutral zero — no blockers among
    nothing, no ageing work among nothing, no scope growth on nothing — and the
    four weights summed to "Needs attention (66/100)". A figure that looks
    computed, is not, and arrives with a colour and a verdict attached.

    It is not a corner case. The Forge build opens in exactly this state:
    forge/seed.json carries no issues, the page renders before the bridge
    answers, and it stays there if the bridge never answers at all. So it is
    the reading most likely to be seen by someone who has never seen the
    product working.

    What is asserted here is the *absence of a number*, not the presence of a
    nicer one. A later change that reinstates any figure over an empty
    selection fails on the digit sweep whether or not it kept these words.
    """
    print("\n  empty selection")

    # The tiles that state a figure about the selected issues. Their refusals
    # carry no digits at all, which is what makes the sweep below decisive.
    FIGURE_TILES = ["#t-health", "#exec-verdict", "#kpis",
                    "#age-chart", "#value-body", "#risk-body"]
    CLAUSE = "the evidence is absent, not noisy"

    seed = json.loads((ROOT / "forge" / "seed.json").read_text())
    sample = json.loads((ROOT / "data" / "sample-sprint.json").read_text())

    page = b.new_page(viewport={"width": 1500, "height": 1000})
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(DIST.as_uri())
    page.wait_for_timeout(700)

    # ---------- the empty dataset the Forge build ships with ----------
    page.evaluate("d => window.DVD.applyDataset(d)", seed)
    page.wait_for_timeout(600)

    health = " ".join((page.text_content("#t-health") or "").split())
    check("the health score refuses over zero issues rather than scoring one",
          "not scored" in health, health)
    check("and prints no score beside the refusal",
          "/100" not in health and not any(c.isdigit() for c in health), health)

    for sel in FIGURE_TILES:
        txt = " ".join((page.text_content(sel) or "").split())
        digits = [c for c in txt if c.isdigit()]
        check("no figure survives an empty selection in %s" % sel, not digits,
              txt[:110])

    # Verbatim, including the closing clause. Softening it to "no data yet"
    # would leave the tile honest and the sentence useless — the clause is the
    # part that says a wider window would not fill this in.
    for sel in FIGURE_TILES:
        txt = " ".join((page.text_content(sel) or "").split())
        if sel == "#t-health":
            continue  # the chip is a label; its sentence lives in the tooltip
        check("the refusal in %s ends with the clause, untrimmed" % sel,
              CLAUSE in txt, txt[-70:])
    check("the health chip carries the refusal in its tooltip",
          CLAUSE in (page.get_attribute("#t-health", "data-tt") or ""),
          (page.get_attribute("#t-health", "data-tt") or "")[:110])

    # And in the callout, not in the note style. The words were right and the
    # type contradicted them: the KPI band's refusal was an 11.5px muted line
    # inside a full-width card, the smallest text on the page, beside charts
    # that kept drawing — the "dimming" ADR 0010 rules out, arrived at through
    # typography instead of opacity. One class carries every refusal now, and
    # a refusal set as a .note anywhere on the page fails here by name.
    for sel in FIGURE_TILES:
        if sel == "#t-health":
            continue
        check("the refusal in %s is set in the refusal callout" % sel,
              page.eval_on_selector_all(sel + " .refusal", "n => n.length") >= 1)
    stray = page.evaluate("""c => [...document.querySelectorAll('.note')]
        .filter(n => n.textContent.includes(c) && !n.closest('.refusal'))
        .map(n => (n.parentElement && n.parentElement.id) || n.className)""", CLAUSE)
    check("no refusal anywhere on the page is set in the note style", stray == [], stray[:4])
    kpi_px = page.evaluate("() => parseFloat(getComputedStyle("
                           "document.querySelector('#kpis .refusal')).fontSize)")
    check("the KPI band's refusal is not the smallest text on the page",
          kpi_px >= 12.5, kpi_px)

    # The specific sentences that were wrong, named so a regression is legible
    # rather than just a failing digit count.
    kpis = " ".join((page.text_content("#kpis") or "").split())
    check("the KPI strip goes as one, leaving no tile still carrying a figure",
          page.eval_on_selector_all("#kpis .kpi", "n => n.length") == 0, kpis[:90])
    age = " ".join((page.text_content("#age-chart") or "").split())
    check("the ageing chart no longer calls an empty selection the healthy state",
          "healthy state" not in age, age[:90])
    risk = " ".join((page.text_content("#risk-body") or "").split())
    check("the risk register does not report zero risks over zero issues",
          "No risks triggered" not in risk, risk[:90])

    # The page still says how many issues it has, and the tiles that were
    # already refusing still refuse in their own words. A blanket "no data"
    # banner over the whole grid would pass every check above and lose both.
    check("the footer still reports the count it is refusing to score",
          "showing 0" in page.text_content("#foot"), page.text_content("#foot")[:80])
    # The page-level statement, in the first tile. Ten identical callouts in
    # one viewport each said a true thing and none was read as the answer;
    # the band's now carries the cause and the one action that changes it.
    band = " ".join((page.text_content("#kpis") or "").split())
    check("the band carries the page-level refusal with the cause named",
          "Nothing to report for this selection" in band and "Nothing is loaded" in band, band[:160])
    check("and says what the tiles below are doing",
          "in its own words" in band and "record" in band, band[-160:])
    basis = " ".join((page.text_content("#exec-basis") or "").split())
    check("with nothing loaded the basis line names the source as the cause",
          "Nothing loaded" in basis and "filters" not in basis, basis[:100])
    check("the tiles that already refused keep their own sentences",
          "No burndown series" in page.text_content("#burn-chart"),
          page.text_content("#burn-chart")[:80])

    # ---------- data arrives: the score comes back ----------
    # Proving the refusal is a response to the evidence, not a switch someone
    # left off. This is the half that catches an over-eager fix.
    page.evaluate("d => window.DVD.applyDataset(d)", sample)
    page.wait_for_timeout(600)
    health = " ".join((page.text_content("#t-health") or "").split())
    check("the score returns as soon as there are issues to score",
          "/100" in health and "not scored" not in health, health)
    check("and the KPI strip comes back with it",
          page.eval_on_selector_all("#kpis .kpi", "n => n.length") == 8,
          page.eval_on_selector_all("#kpis .kpi", "n => n.length"))

    # ---------- a filter that matches nothing ----------
    # The score is computed over the *filtered* items, not the context, so a
    # filter matching nothing reaches the same undefined arithmetic by a route
    # that has nothing to do with Forge.
    page.evaluate("() => window.DVD.debug.setFilter('q', 'zzz-no-such-issue')")
    page.wait_for_timeout(500)
    health = " ".join((page.text_content("#t-health") or "").split())
    check("filtering every issue out refuses the same way an empty file does",
          "not scored" in health, health)
    check("and the KPI strip refuses with it",
          page.eval_on_selector_all("#kpis .kpi", "n => n.length") == 0,
          " ".join((page.text_content("#kpis") or "").split())[:90])
    # Same refusal, different cause, and the basis line has to say which. It
    # said "Nothing loaded from …" over a file with issues in it that a search
    # had excluded, which sends a reader to check the connection when the fix
    # is a click away in the filter row; and the footer said "showing 22" for
    # a selection with nothing in it, because it counted what the filter was
    # applied to rather than what survived it.
    basis = " ".join((page.text_content("#exec-basis") or "").split())
    check("a filter that matches nothing is named as the cause, not the source",
          "match the current filters" in basis and "Nothing loaded" not in basis, basis[:120])
    band = " ".join((page.text_content("#kpis") or "").split())
    check("the band's page-level refusal names the filter and the way back",
          "No issues match the current filters" in band and "Clear a filter" in band, band[:200])
    check("and the basis line says how many issues the filter excluded",
          re.search(r"among the \d+ loaded", basis) is not None, basis[:120])
    foot = " ".join((page.text_content("#foot") or "").split())
    check("the footer shows the filtered count against the loaded one",
          re.search(r"showing 0 of \d+ after filters", foot) is not None, foot[:120])
    # Which tiles a filter does not move. Under this same search ten tiles
    # refused while the burndown still said "10 left" and the releases still
    # said "9/14 issues", from the sprint's record; nothing said which was which.
    check("and names the tiles that read the record rather than the filtered issues",
          "do not follow the filters" in foot and "burndown" in foot, foot[-200:])
    caps = page.eval_on_selector_all("#c-burn .cap, #c-pred .cap, #c-dora .cap, #c-load .cap, #c-rel .cap",
                                     "n => n.map(e => e.textContent)")
    check("each record-fed tile's caption says it does not follow the filters",
          len(caps) == 5 and all("not the filtered issues" in c for c in caps),
          [c[-60:] for c in caps if "not the filtered issues" not in c])
    page.evaluate("() => window.DVD.debug.setFilter('q', '')")
    page.wait_for_timeout(400)

    check("no console errors in the empty state", not errs, errs[:2])
    page.close()


def exec_findings(b):
    """The findings' sentences hold at the edges of their own figures."""
    print("\n  exec findings")
    sample = json.loads((ROOT / "data" / "sample-sprint.json").read_text())
    page = b.new_page(viewport={"width": 1500, "height": 1000})
    page.goto(DIST.as_uri())
    page.wait_for_timeout(700)
    # Every closed item started the day it was raised: flow efficiency is 100%.
    # The finding printed "Only 100% of elapsed time on closed items was spent
    # actively working. The other 0% was queuing — waiting for review…" — a
    # good finding in a warning's words, seen in a tenant over one closed item.
    whole = json.loads(json.dumps(sample))
    for i in whole["issues"]:
        if i.get("resolved") and i.get("created"):
            i["started"] = i["created"]
    page.evaluate("d => window.DVD.applyDataset(d)", whole)
    page.wait_for_timeout(500)
    txt = " ".join((page.text_content("#exec-list") or "").split())
    check("a flow efficiency of 100% is not introduced with 'Only'",
          "100% of elapsed time" in txt and "Only 100%" not in txt, txt[:160])
    check("and does not report that 0% was queuing",
          "0% was queuing" not in txt and "None of it was queuing" in txt, txt[:220])
    # Nothing priced. The Value closed tile printed "$0" over "0 of 5 closed
    # items priced" in a tenant: a figure that reads as "delivered nothing of
    # value" where the truth is "nobody priced anything". A dash, and the count.
    unpriced = json.loads(json.dumps(sample))
    for i in unpriced["issues"]:
        i.pop("businessValue", None); i.pop("valueBasis", None)
    page.evaluate("d => window.DVD.applyDataset(d)", unpriced)
    page.wait_for_timeout(500)
    tile = " ".join((page.text_content("#kpis .kpi:nth-child(8)") or "").split())
    check("with nothing priced the value tile withholds its figure rather than printing a zero",
          "—" in tile and not re.search(r"[$£€]\s?0\b", tile), tile)
    check("and keeps the honest count of what was not priced",
          re.search(r"none of \d+ closed items priced", tile) is not None, tile)
    # Two caps against a named rule. Seven findings can fire and the list held
    # six; the register held nine risks and the critical rule fires per issue.
    seven = json.loads(json.dumps(sample))
    seven["history"][-3]["wipItems"], seven["history"][-1]["wipItems"] = 4, 9
    seven["history"][-3]["completedItems"], seven["history"][-1]["completedItems"] = 12, 10
    page.evaluate("d => window.DVD.applyDataset(d)", seven)
    page.wait_for_timeout(500)
    n = page.eval_on_selector_all("#exec-list li", "n => n.length")
    txt = " ".join((page.text_content("#exec-list") or "").split())
    check("all seven findings are listed when seven fire; the list has no cap",
          n == 7 and "Work in progress has risen" in txt, (n, txt[-120:]))
    many = json.loads(json.dumps(sample))
    openers = [i for i in many["issues"] if i.get("statusCategory") != "Done"][:11]
    for i in openers:
        i["priority"] = "Highest"; i["created"] = "2026-06-01"
    page.evaluate("d => window.DVD.applyDataset(d)", many)
    page.wait_for_timeout(500)
    rows = page.eval_on_selector_all("#risk-body .riskrow", "n => n.length")
    note = " ".join((page.text_content("#risk-body") or "").split())
    check("the risk register shows its nine most severe and says how many it did not show",
          rows == 9 and re.search(r"Showing the 9 most severe of 1\d risks", note) is not None, (rows, note[-200:]))
    page.evaluate("d => window.DVD.applyDataset(d)", sample)
    page.wait_for_timeout(300)
    check("under the cap the register says nothing about a cap",
          "most severe of" not in (page.text_content("#risk-body") or ""))
    page.close()


def wizard_notices(b):
    """A failure in the wizard is said in the wizard, never in a browser dialog.

    Four alert() calls: an unreadable file, an empty paste, unreadable text,
    and a required column left unmapped. A system dialog in a page whose whole
    voice is a sentence, announced to a screen reader as a nameless
    interruption, and invisible to any test that did not think to listen for
    it — Playwright dismisses them silently. Listened for here, so a fifth one
    cannot arrive unnoticed.
    """
    print("\n  wizard notices")
    page = b.new_page(viewport={"width": 1500, "height": 1000})
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    page.goto(DIST.as_uri())
    page.wait_for_timeout(700)
    page.click("#btn-import")
    page.wait_for_timeout(300)
    page.evaluate("() => { document.querySelector('#step-choose details').open = true; }")
    page.click("#m-paste")
    page.wait_for_timeout(200)
    n1 = " ".join((page.text_content("#m-notice-1") or "").split())
    check("an empty paste is answered in the wizard, not a browser dialog",
          "Nothing pasted" in n1 and not dialogs, (n1[:80], dialogs))
    page.fill("#paste", '{"issues": [')
    page.click("#m-paste")
    page.wait_for_timeout(200)
    n1 = " ".join((page.text_content("#m-notice-1") or "").split())
    check("unreadable text says so in the wizard's own callout",
          "Could not read that text" in n1 and not dialogs, (n1[:120], dialogs))
    check("and the notice is announced",
          page.get_attribute("#m-notice-1", "role") == "alert" and
          page.get_attribute("#m-notice-2", "role") == "alert")
    page.fill("#paste", "foo,bar\n1,2")
    page.click("#m-paste")
    page.wait_for_selector("#step-map:not(.hidden)", timeout=5000)
    check("a readable paste clears the notice",
          (page.text_content("#m-notice-1") or "").strip() == "")
    page.click("#m-preview")
    page.wait_for_timeout(300)
    n2 = " ".join((page.text_content("#m-notice-2") or "").split())
    check("required columns left unmapped are named in the wizard, not a dialog",
          "Pick a column for" in n2 and not dialogs and page.is_visible("#step-map"),
          (n2[:120], dialogs))
    page.keyboard.press("Escape")

    # ---------- a ■ warning turns Apply off (1.79.26) ----------
    def paste(text):
        page.click("#btn-import")
        page.evaluate("() => { document.querySelector('#step-choose details').open = true; }")
        page.fill("#paste", text)
        page.click("#m-paste")

    def apply_state():
        return page.evaluate("""() => {
            const b = document.querySelector('#m-apply');
            return { disabled: b.disabled, primary: b.classList.contains('primary'),
                     why: (document.querySelector('#m-apply-why').textContent || '').trim() };
        }""")

    paste("key,summary,status,created\n")
    page.wait_for_selector("#step-map:not(.hidden)", timeout=5000)
    page.click("#m-preview")
    page.wait_for_selector("#step-preview:not(.hidden)", timeout=5000)
    st = apply_state()
    check("a header with nothing under it cannot be applied",
          st["disabled"] and not st["primary"], st)
    check("and the reason is printed beside the button",
          st["why"].startswith("Apply is off until this is fixed: No issues."), st["why"])
    check("the reason is announced", page.get_attribute("#m-apply-why", "role") == "status")
    page.keyboard.press("Escape")

    paste("key,summary,status,created\nA-1,one,Done,2026-08-02\nA-1,two,Done,2026-08-03\nA-2,three,To Do,2026-08-04\n")
    page.wait_for_selector("#step-map:not(.hidden)", timeout=5000)
    page.fill("#w-start", "2026-08-01"); page.fill("#w-end", "2026-08-14")
    page.click("#m-preview")
    page.wait_for_selector("#step-preview:not(.hidden)", timeout=5000)
    st = apply_state()
    check("duplicate keys turn Apply off", st["disabled"] and not st["primary"], st)
    check("with the warning's first sentence beside it",
          "Duplicate keys. 1 key appears more than once" in st["why"], st["why"])
    page.keyboard.press("Escape")

    paste("key,summary,status,created\nA-1,one,Done,2026-08-02\nA-2,three,To Do,2026-08-04\n")
    page.wait_for_selector("#step-map:not(.hidden)", timeout=5000)
    page.fill("#w-start", "2026-08-01"); page.fill("#w-end", "2026-08-14")
    page.click("#m-preview")
    page.wait_for_selector("#step-preview:not(.hidden)", timeout=5000)
    st = apply_state()
    check("a clean preview has Apply back on, primary and unexplained",
          not st["disabled"] and st["primary"] and st["why"] == "", st)
    page.keyboard.press("Escape")

    # ---------- a bundle loads whole ----------
    paste((ROOT / "data" / "sample-bundle.json").read_text())
    page.wait_for_selector("#step-preview:not(.hidden)", timeout=5000)
    check("a bundle skips the mapping step", "hidden" in (page.get_attribute("#step-map", "class") or ""))
    stats = page.eval_on_selector_all("#prev-stats div", "n => n.map(e => e.textContent)")
    check("the preview counts its sprints", stats and stats[0] == "18sprints", stats)
    check("and says it loads whole",
          "loads whole" in (page.text_content("#prev-warn") or ""), page.text_content("#prev-warn")[:100])
    st = apply_state()
    check("Apply is on for a bundle", not st["disabled"] and st["primary"], st)
    page.click("#m-back2")
    check("Back from a bundle preview returns to the file step", page.is_visible("#step-choose"))
    page.click("#m-paste")
    page.wait_for_selector("#step-preview:not(.hidden)", timeout=5000)
    page.click("#m-apply"); page.wait_for_timeout(700)
    check("the applied bundle keeps its context bar",
          "hidden" not in (page.get_attribute("#ctxbar", "class") or ""))
    check("and opens on its active sprint, not a flattened one",
          "Sprint 24" in page.text_content("#t-title") and "233" not in page.text_content("#foot"),
          (page.text_content("#t-title"), page.text_content("#foot")[:60]))
    page.close()


def transports(b):
    """The two live-mode transports, and that the page cannot tell them apart.

    Live mode reaches its answers either over a same-origin GET, answered by
    scripts/serve_live.py, or over an invoke() an adapter left on the window —
    which is what a Forge Custom UI iframe has, because it has no same-origin
    `api/` at all. The page must not learn which it has.

    So this drives the *same page* against the *same data* twice, once each
    way, and compares what ends up on screen. The bridge run is fed the bodies
    the loopback run really received, so a difference in the rendering can only
    come from the transport itself. `tests/test_service.py` checks the other
    half — that the Forge resolver builds those bodies in the first place.
    """
    import json
    import subprocess
    import time
    import urllib.request

    print("\n  transports")

    # ---------- none: an emailed copy asks nothing ----------
    page = b.new_page()
    reqs = []
    page.on("request", lambda r: reqs.append(r.url))
    page.goto(DIST.as_uri())
    page.wait_for_timeout(700)
    check("a file:// copy has no transport at all",
          page.evaluate("() => window.DVD.debug.transport()") is None)
    check("and makes no request off the filesystem",
          [u for u in reqs if not u.startswith("file://")] == [],
          [u for u in reqs if not u.startswith("file://")][:3])
    page.close()

    port = 8734
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "serve_live.py"),
         "--bundle", "data/sample-bundle.json", "--port", str(port)],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    url = "http://127.0.0.1:%d/dist/delivery-value-dashboard.html" % port
    api = "http://127.0.0.1:%d/api/" % port
    try:
        deadline = time.time() + 20
        while True:
            try:
                with urllib.request.urlopen(api + "contexts", timeout=2) as r:
                    contexts_body = json.loads(r.read())
                break
            except Exception:
                if time.time() > deadline or proc.poll() is not None:
                    check("the live server comes up", False, "serve_live.py did not start")
                    return
                time.sleep(0.2)

        cid = contexts_body["contexts"][0]["id"]
        with urllib.request.urlopen(api + "context?id=" + cid, timeout=20) as r:
            context_body = json.loads(r.read())
        # The trend series, which is its own route on both transports. A Forge
        # context body carries `history: []` and always has — the resolver
        # computes nothing — so the rows come from here or the page has none.
        # Fetched rather than fabricated: the whole claim under test is that one
        # body renders identically whichever transport carried it.
        with urllib.request.urlopen(api + "history?id=" + cid, timeout=20) as r:
            history_body = json.loads(r.read())

        # A fingerprint of what the page decided, not of how it looks. The
        # footer carries the issue count and the sprint count; the KPI strip
        # carries the figures; the picker carries what is selectable.
        # The footer ends with a wall-clock render time, which differs between
        # two runs for reasons that are not the transport. Everything before it
        # is the part that describes the data.
        fingerprint = """() => ({
            foot: document.querySelector('#foot').innerText.split('· rendered')[0],
            kpis: document.querySelector('#kpis').innerText,
            contexts: window.DVD.data.contexts.map(c => c.id).sort(),
            issues: window.DVD.data.issues.length,
            ctx: window.DVD.debug.view().ctx.id
        })"""

        # ---------- a static host with nothing answering (1.79.28) ----------
        # Served from a plain file server the page has the loopback transport
        # and nobody on the other end. That is a file: both connection-fed
        # tiles stay off, and shown, the forecast offers no control it cannot
        # answer. Deciding this by protocol kept them on for any http host.
        sport = 8735
        sproc = subprocess.Popen([sys.executable, "-m", "http.server", str(sport), "--bind", "127.0.0.1"],
                                 cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(50):
                try:
                    urllib.request.urlopen("http://127.0.0.1:%d/" % sport, timeout=1); break
                except Exception:
                    time.sleep(0.1)
            sp = b.new_page(viewport={"width": 1500, "height": 1000})
            sp.goto("http://127.0.0.1:%d/dist/delivery-value-dashboard.html" % sport)
            sp.wait_for_timeout(900)
            check("a static host still yields the loopback transport",
                  sp.evaluate("() => window.DVD.debug.transport()") == "loopback")
            check("but with nothing answering, the forecast and brief tiles are off, as in a file",
                  sp.eval_on_selector("#c-forecast", "e => e.classList.contains('hidden')") and
                  sp.eval_on_selector("#c-brief", "e => e.classList.contains('hidden')"))
            check("and the view still reads as the preset",
                  "All sprint tiles" in (sp.text_content("#btn-view") or ""), sp.text_content("#btn-view"))
            sp.evaluate("() => window.DVD.debug.setShown(window.DVD.debug.tileIds())")
            sp.wait_for_timeout(400)
            check("shown without a connection, the forecast tile offers no control above its refusal",
                  sp.eval_on_selector_all("#forecast-body input, #forecast-body .seg", "n => n.length") == 0 and
                  "is not in this copy" in (sp.text_content("#forecast-body") or ""),
                  (sp.text_content("#forecast-body") or "")[:80])
            sp.close()
        finally:
            sproc.terminate()

        # ---------- loopback ----------
        page = b.new_page(viewport={"width": 1500, "height": 1000})
        page.goto(url)
        page.wait_for_timeout(900)
        check("over http the page finds the loopback transport",
              page.evaluate("() => window.DVD.debug.transport()") == "loopback",
              page.evaluate("() => window.DVD.debug.transport()"))
        check("and once a connection answers, the forecast and brief tiles come on",
              page.eval_on_selector("#c-forecast", "e => !e.classList.contains('hidden')") and
              page.eval_on_selector("#c-brief", "e => !e.classList.contains('hidden')"))
        check("with the view still reading as the preset it was",
              "All sprint tiles" in (page.text_content("#btn-view") or ""), page.text_content("#btn-view"))
        # Selected through the page's own entry point, not by poking state, so
        # the fetch really happens and the render is the one a user would get.
        page.evaluate("id => window.DVD.debug.selectContext(id)", cid)
        page.wait_for_timeout(1500)
        loop_print = page.evaluate(fingerprint)
        STARTS = ("() => window.DVD.debug.view().issues"
                  ".map(i => i.key + ':' + (i.started || '')).sort()")
        starts_loop = page.evaluate(STARTS)
        page.close()

        # ---------- bridge ----------
        stub = """
        window.__DVD_BRIDGE__ = {
          name: 'stub',
          invoke: (route, params) => {
            window.__stubCalls = (window.__stubCalls || []).concat(route);
            const bodies = %s;
            if (route === 'contexts') return Promise.resolve({status: 200, body: bodies.contexts});
            if (route === 'context') {
              return Promise.resolve(params.id === %s
                ? {status: 200, body: bodies.context}
                : {status: 404, body: {error: 'unknown context'}});
            }
            return Promise.resolve({status: 404, body: null});
          }
        };
        """ % (json.dumps({"contexts": contexts_body, "context": context_body}),
               json.dumps(cid))

        page = b.new_page(viewport={"width": 1500, "height": 1000})
        reqs = []
        page.on("request", lambda r: reqs.append(r.url))
        page.add_init_script(stub)
        page.goto(url)
        page.wait_for_timeout(400)
        check("a bridge on the window wins over the same-origin fetch",
              page.evaluate("() => window.DVD.debug.transport()") == "stub",
              page.evaluate("() => window.DVD.debug.transport()"))
        page.evaluate("id => window.DVD.debug.selectContext(id)", cid)
        page.wait_for_timeout(1200)
        bridge_print = page.evaluate(fingerprint)

        check("nothing is fetched from api/ when a bridge is present",
              [u for u in reqs if "/api/" in u] == [],
              [u for u in reqs if "/api/" in u][:3])
        # The forecast tile asks too, and gets a 404 from the stub — it is not
        # what this is testing, but a route the page invented would be.
        asked = set(page.evaluate("() => window.__stubCalls || []"))
        check("the bridge was asked for both context routes",
              {"contexts", "context"} <= asked, sorted(asked))
        # Derived from src/app.js rather than listed here. A hardcoded set is a
        # copy that has to be remembered, and the thing worth asserting is not
        # "these four names" but "the page invents nothing" — which stays true
        # as routes are added and stops being checked the moment the list here
        # drifts from the one over there.
        app_js = (ROOT / "src" / "app.js").read_text()
        block = re.search(r"^const ROUTES = \{(.*?)^\};", app_js, re.S | re.M)
        declared = set(re.findall(r"^\s{2}([a-zA-Z]\w*):", block.group(1), re.M)) if block else set()
        check("the page declares its routes in one place", len(declared) >= 4, sorted(declared))
        check("and for no route the loopback transport does not have",
              asked <= declared, sorted(asked - declared) or sorted(asked))

        # The other half of the same contract: every route the page can ask for
        # has to be answered by the loopback server too, or live mode works on
        # Forge and silently does nothing locally — which is exactly the
        # divergence ADR 0009 exists to stop, arriving from the other side.
        live_py = (ROOT / "scripts" / "serve_live.py").read_text()
        paths = set(re.findall(r'"(api/[\w-]+)"', live_py))
        missing = []
        for name in sorted(declared):
            m = re.search(r"^\s{2}%s: [^\n]*?\"(api/[\w-]+)" % re.escape(name),
                          block.group(1), re.M)
            if m and m.group(1) not in paths:
                missing.append((name, m.group(1)))
        check("every route the page can ask for is served over loopback too",
              not missing, missing)
        page.close()

        # ---------- the value tile counts against its own pool ----------
        #
        # Items and value are counted from two different sets (ADR 0026), and
        # the tile's "how many carry no estimate" line subtracted one from the
        # other. In a tenant that printed **"-1 of the 0 completed items carry
        # no value estimate"** — the first sprint where an epic delivered value
        # while the sprint's own items were all still open. Two sets, one
        # subtraction, no meaning, and a negative count on a customer's screen.
        page = b.new_page(viewport={"width": 1500, "height": 1000})
        page.goto(url)
        page.wait_for_timeout(1500)
        note = page.evaluate("""() => {
            const t = (document.querySelector('#value-body') || {}).innerText || '';
            const i = t.indexOf('Read this as a floor');
            return i < 0 ? '' : t.slice(i, i + 260).replace(/\s+/g, ' ');
        }""")
        check("the value tile has a floor note to check", note, note[:80])
        check("it states no negative count",
              "-1 " not in note and "- 1 " not in note, note[:140])
        check("and no count against a denominator of zero",
              " of the 0 " not in note, note[:140])
        check("it says value is recorded on epics and above",
              "epics and above" in note, note[:160])
        check("and that work below that level is not missing from the figure",
              "not missing from it" in note, note[:200])
        page.close()

        # ---------- the issue-type filter changes what is counted ----------
        #
        # Unlike its neighbours in that row it is not a display filter: it
        # changes what the page counts, and because the forecast is computed
        # where the page is not, the selection has to travel with the forecast
        # request. Without that the tiles count one set of issues and the
        # forecast another — both correct, disagreeing, and nothing on screen
        # saying which is which.
        page = b.new_page(viewport={"width": 1500, "height": 1000})
        seen = []
        page.on("request", lambda r: seen.append(r.url))
        page.goto(url)
        page.wait_for_timeout(1200)
        board = page.evaluate("""() => {
            const s = document.querySelector('#c-board');
            const opt = [...s.options].map(o => o.value).find(v => v && !v.startsWith('—'));
            s.value = opt; s.dispatchEvent(new Event('change', {bubbles: true}));
            return opt; }""")
        page.wait_for_timeout(3500)

        types = page.evaluate("""() => [...document.querySelectorAll(
            '#f-types input[type=checkbox]')].map(b => b.getAttribute('data-type'))""")
        check("the type filter offers the types this board actually uses",
              len(types) > 1, {"board": board, "types": types})
        check("and every one starts selected, because nothing is filtered yet",
              page.evaluate("""() => [...document.querySelectorAll(
                  '#f-types input[type=checkbox]')].every(b => b.checked)"""), types)

        before = page.evaluate("() => window.DVD.debug.view().issues.length")
        drop = types[0]
        page.evaluate("""t => {
            const b = [...document.querySelectorAll('#f-types input[type=checkbox]')]
                .find(x => x.getAttribute('data-type') === t);
            b.checked = false; b.dispatchEvent(new Event('change', {bubbles: true}));
        }""", drop)
        page.wait_for_timeout(3500)

        kpis = page.text_content("#kpis") or ""
        check("unticking a type changes what the page counts",
              page.evaluate("() => document.querySelector('#kpis').innerText") != ""
              and before > 0, {"before": before})
        check("the summary says how many of how many are selected",
              "of %d types" % len(types) in
              (page.text_content("#f-types summary") or ""),
              page.text_content("#f-types summary"))
        check("and the active-filter chip names them",
              drop not in (page.text_content("#f-chips") or ""),
              page.text_content("#f-chips"))

        # The half only a browser can check: the forecast is fetched again, with
        # the selection on it.
        asked = [u for u in seen if "api/forecast" in u and "types=" in u]
        check("the forecast is refetched with the selection",
              asked, [u.split("?")[-1] for u in seen if "api/forecast" in u][-2:])

        # Deselecting everything is a refusal, not everything and not zero.
        # ADR 0010: an empty selection has no denominator.
        page.evaluate("() => document.querySelector('#f-types-none').click()")
        page.wait_for_timeout(2500)
        check("selecting no types refuses rather than showing them all",
              "No types selected" in (page.text_content("#f-types summary") or ""),
              page.text_content("#f-types summary"))
        check("and the page says the evidence is absent rather than reporting zero",
              "evidence is absent" in (page.text_content("#exec-verdict") or ""),
              (page.text_content("#exec-verdict") or "")[:120])

        page.evaluate("() => document.querySelector('#f-types-all').click()")
        page.wait_for_timeout(2000)

        # ---------- the dropdowns follow the board ----------
        #
        # `dataset.built = "1"` built these once, on an element that outlives
        # every context switch — so a reader on their second board was offered
        # the first board's people and epics, and picking one filtered to
        # nothing. Found while adding the control above.
        others = page.evaluate("""() => [...document.querySelector('#c-board').options]
            .map(o => o.value).filter(v => v && !v.startsWith('—'))""")
        if len(others) > 1:
            first = page.evaluate("""() => [...document.querySelectorAll('#f-assignee option')]
                .map(o => o.value)""")
            page.evaluate("""v => { const s = document.querySelector('#c-board');
                s.value = v; s.dispatchEvent(new Event('change', {bubbles: true})); }""",
                others[1])
            page.wait_for_timeout(4000)
            second = page.evaluate("""() => [...document.querySelectorAll('#f-assignee option')]
                .map(o => o.value)""")
            check("switching board rebuilds the people filter for that board",
                  first != second, {"first": first[:3], "second": second[:3]})
            check("and rebuilds the type filter too",
                  page.evaluate("""() => document.querySelectorAll(
                      '#f-types input[type=checkbox]').length""") > 0, "types rebuilt")
        page.close()

        # ---------- a roll-up rolls up all of itself ----------
        #
        # Two bugs live here and only a real page finds either.
        #
        # A roll-up is assembled on the page from issues already loaded, and in
        # live mode a context arrives as a stub whose issues are fetched when
        # somebody selects it. So selecting a roll-up rolled up whichever
        # members happened to be open — a smaller number than its own header
        # claimed, with nothing saying so.
        #
        # And the fix has its own trap: `loadContext` ended `S.ctx = id`, so
        # filling in the members moved the reader to whichever one finished
        # last. The roll-up they asked for was gone, and the page looked like it
        # had simply ignored the click.
        page = b.new_page(viewport={"width": 1500, "height": 1000})
        page.goto(url)
        page.wait_for_timeout(1200)
        rolls = page.evaluate("""() => window.DVD.debug.view().contexts
            .filter(c => c.isCrossTeam).map(c => c.id)""")
        check("a project with several boards is offered a cross-team roll-up",
              len(rolls) >= 1, rolls)
        if rolls:
            page.evaluate("id => window.DVD.debug.selectContext(id)", rolls[0])
            page.wait_for_timeout(6000)
            got = page.evaluate("""() => {
                const v = window.DVD.debug.view();
                return { id: v.ctx.id, cross: !!v.ctx.isCrossTeam,
                         members: (v.ctx.members || []).length,
                         boards: (v.ctx.boards || []).length,
                         issues: v.issues.length,
                         loaded: (v.ctx.members || []).filter(m => {
                            const c = window.DVD.data.contexts.find(x => x.id === m);
                            return c && !c.stub; }).length };
            }""")
            check("selecting it leaves the reader on it, not on one of its members",
                  got["id"] == rolls[0] and got["cross"], got)
            check("and every member is loaded rather than only the ones already open",
                  got["loaded"] == got["members"] and got["members"] > 1, got)
            check("so the roll-up holds more issues than any one member",
                  got["issues"] > 0, got)
            check("it spans more than one board, which is what makes it cross-team",
                  got["boards"] > 1, got)

            lead = page.text_content("#exec-verdict") or ""
            check("and it says which boards it covers, by name",
                  "all boards" not in lead.lower() and "boards" in lead.lower()
                  and "cannot browse" in lead, lead[:200])

            # The forecast must refuse in the shape the tile reads, printing the
            # tool's own sentence — not "not available", which is what a
            # top-level-only refusal rendered as.
            fc = page.text_content("#c-forecast") or ""
            check("the forecast refuses with the tool's sentence, not a shrug",
                  "Pooling several teams" in fc and "not available" not in fc,
                  fc[-220:])
        page.close()

        # ---------- a figure may not claim a basis it does not have ----------
        #
        # `renderPred` printed "A commitment set from the last three actuals"
        # whatever the history held. The slice behind it — hist.slice(-4, -1) —
        # yields three entries only from four sprints or more; on a two-sprint
        # board it yields one, so the tile presented the average of a single
        # sprint as a three-sprint average. Two other call sites guard the same
        # figure with `hist.length >= 4`; this one did not.
        #
        # Seen first in a tenant, on a board with two sprints. That is the
        # failure class this repository is most afraid of: nothing errored and
        # the sentence read as computed.
        for n, phrase, wrong in ((2, "the last two actuals", "three actuals"),
                                 (1, "the last completed sprint", "three actuals")):
            short = ROOT / "dist" / (".basis-%d.json" % n)
            page_file = ROOT / "dist" / (".basis-%d.html" % n)
            hist = [{"sprint": "S%d" % (i + 1), "committedSP": 20, "completedSP": 10,
                     "committedItems": 10, "completedItems": 4, "throughput": 4,
                     "wipItems": 1, "unplannedItems": 0, "flowEfficiency": 0.3,
                     "valueDelivered": 0} for i in range(n + 1)]
            short.write_text(json.dumps({
                "schemaVersion": 2,
                "meta": {"organisation": "T", "team": "T", "sprintName": "S%d" % (n + 1),
                         "source": "demo", "sourceLabel": "fixture", "currency": "GBP",
                         "startDate": "2026-01-05", "endDate": "2026-01-16",
                         "asOfDate": "2026-01-16"},
                "issues": [], "burndown": [], "history": hist,
                "releases": [], "dora": None}))
            subprocess.run([sys.executable, "build.py", "--data", str(short),
                            "--out", str(page_file)], cwd=str(ROOT), check=True,
                           capture_output=True)
            try:
                page = b.new_page(viewport={"width": 1500, "height": 1000})
                # `file://`, deliberately: served from the same origin the page
                # finds the loopback API, switches to live mode and replaces
                # this history with the bundle's. An emailed copy is also the
                # honest shape for the case under test — a fixed history with
                # no transport behind it.
                page.goto(page_file.as_uri())
                page.wait_for_timeout(900)
                txt = page.text_content("#pred-chart") or ""
                check("with %d sprints of history the tile says %r" % (n, phrase),
                      phrase in txt, txt[-220:])
                check("and does not claim %r it does not have" % wrong,
                      wrong not in txt, txt[-220:])
                # The same average, described again two clauses later. The first
                # fix corrected the phrase carrying the figure and left this one
                # saying "a mean of three numbers" beside it.
                check("nor a mean of three numbers, in the clause after it",
                      "mean of three numbers" not in txt, txt[-220:])
                page.close()
            finally:
                short.unlink(missing_ok=True)
                page_file.unlink(missing_ok=True)

        # The label above the chart said "last six sprints" whatever it drew.
        # Six is the cap, not the count, and a caption stating a number the
        # chart does not show is the same false-basis failure one level up.
        html = (ROOT / "src" / "index.html").read_text()
        check("the predictability caption does not claim a sprint count",
              "last six sprints" not in html,
              [l.strip() for l in html.splitlines() if "Committed against" in l])

        # ---------- a file with no data of its own ----------
        # This is the path a Forge install really takes: the split build is
        # seeded from forge/seed.json, which carries no issues, so the page
        # holds one placeholder context until the transport answers. Untested,
        # it fails as a dashboard of nothing with the real sprints one click
        # away and no reason on screen to click.
        seeded = ROOT / "dist" / ".transport-test.html"
        subprocess.run([sys.executable, "build.py", "--data", "forge/seed.json",
                        "--out", str(seeded)], cwd=str(ROOT), check=True,
                       capture_output=True)
        try:
            page = b.new_page(viewport={"width": 1500, "height": 1000})
            page.goto("http://127.0.0.1:%d/dist/.transport-test.html" % port)
            page.wait_for_timeout(2000)
            ids = page.evaluate("() => window.DVD.data.contexts.map(c => c.id)")
            live_btn = " ".join((page.text_content("#c-live") or "").split())
            check("the refresh button names its source rather than printing the source id",
                  live_btn.startswith("Refresh from ") and
                  re.search(r"from (jira|asana|demo|bundle|server)$", live_btn) is None, live_btn)
            check("an empty file drops its placeholder once the connection answers",
                  "single" not in ids, ids[:3])
            check("and opens on one of the connection's own sprints",
                  page.evaluate("() => window.DVD.debug.view().ctx.id") in
                  [c["id"] for c in contexts_body["contexts"]],
                  page.evaluate("() => window.DVD.debug.view().ctx.id"))
            check("with that sprint's issues actually loaded",
                  page.evaluate("() => window.DVD.data.issues.length") > 0,
                  page.evaluate("() => window.DVD.data.issues.length"))
            # The seed's label used to read "this site's Jira — nothing loaded
            # yet", and nothing replaced it when the connection loaded a sprint:
            # a tenant's footer read "nothing loaded yet · 24 issues across 4
            # sprints". The label names the source; the page says the state.
            foot = " ".join((page.text_content("#foot") or "").split())
            basis = " ".join((page.text_content("#exec-basis") or "").split())
            check("once the connection has loaded a sprint, nothing on the page says nothing is loaded",
                  "nothing loaded" not in foot.lower() and "nothing loaded" not in basis.lower(),
                  (foot[:90], basis[:90]))
            check("and the footer names the source the issues came from",
                  "Generated from this site's Jira" in foot, foot[:90])
            page.close()
        finally:
            seeded.unlink(missing_ok=True)

        # ---------- the bridge, carrying what the bridge really carries ----------
        # The hole in the check below, named by ADR 0010: it feeds the stub the
        # loopback's own bodies, so any field the Forge resolver omits is
        # invisible to it. `workingDays` was exactly that — absent over the
        # bridge, supplied over loopback, and the page silently lost the
        # largest component of its health score in every tenant.
        #
        # So this feeds the stub a body shaped the way the resolver really
        # shapes one, and requires the same render anyway. What the page has to
        # make up for is stated in the strip list, and each entry is a field the
        # page is supposed to derive:
        #
        #   workingDays     derived from the sprint's dates under the config
        #   statusCategory  derived from the raw status name under the config
        #   contextId       tagged by loadContext(), never trusted from a body
        #
        # `started` is stripped too now, and replaced by the raw material the
        # resolver really sends: every move the issue made between statuses,
        # with the names undecided. Recognising an in-progress status is
        # organisation config, so the resolver will not decide it and the page
        # does — the same move it already makes for `statusCategory`.
        #
        # The transitions below are deliberately out of date order, because
        # Jira does not return a changelog in date order. A page taking the
        # *first* in-progress transition rather than the earliest would report
        # a later start, a shorter cycle time and a higher flow efficiency, and
        # the render would still look entirely reasonable.
        import copy
        forge_shaped = copy.deepcopy(context_body)
        forge_shaped["context"].pop("workingDays", None)
        for issue in forge_shaped["issues"]:
            for field in ("statusCategory", "contextId"):
                issue.pop(field, None)
            started = issue.pop("started", None)
            if started:
                later = (datetime.date.fromisoformat(started)
                         + datetime.timedelta(days=3)).isoformat()
                issue["statusTransitions"] = [
                    {"to": "In Review", "at": later},
                    {"to": "In Progress", "at": started},
                    {"to": "Done", "at": issue.get("resolved") or later},
                ]

        shaped_stub = """
        window.__DVD_BRIDGE__ = { name: 'stub', invoke: (route, params) => {
            const bodies = %s;
            if (route === 'contexts') return Promise.resolve({status: 200, body: bodies.contexts});
            if (route === 'context') return Promise.resolve({status: 200, body: bodies.context});
            if (route === 'history') return Promise.resolve({status: 200, body: bodies.history});
            return Promise.resolve({status: 404, body: null}); } };
        """ % json.dumps({"contexts": contexts_body, "context": forge_shaped,
                          "history": history_body})

        page = b.new_page(viewport={"width": 1500, "height": 1000})
        page.add_init_script(shaped_stub)
        page.goto(url)
        page.wait_for_timeout(400)
        page.evaluate("id => window.DVD.debug.selectContext(id)", cid)
        page.wait_for_timeout(1200)
        shaped_print = page.evaluate(fingerprint)
        wd = page.evaluate("() => window.DVD.debug.view().meta.workingDays.length")
        starts_shaped = page.evaluate(STARTS)
        page.close()

        check("the page fills in the working days the resolver does not send",
              wd > 0, wd)
        # The trend tiles on a Forge-shaped body have nothing to draw unless the
        # series route supplies it: `history` in a context body is empty on that
        # transport and always has been. This is the check that would have
        # failed before the route existed — the tiles rendered "needs at least
        # two sprints" in every tenant and nothing said why.

        check("and resolves `started` out of the raw transitions, earliest first",
              starts_shaped == starts_loop, {"served": starts_loop[:4],
                                             "forge-shaped": starts_shaped[:4]})
        for field in ("foot", "kpis", "contexts", "issues", "ctx"):
            check("a Forge-shaped body renders the same %s as a served one" % field,
                  loop_print[field] == shaped_print[field],
                  {"served": str(loop_print[field])[:120],
                   "forge-shaped": str(shaped_print[field])[:120]})


        # ---------- the sequencing tile, over a Forge-shaped body ----------
        #
        # Value and its basis sit on every row of every ordering and nothing had
        # ever read them, so the figure ADR 0027 exists to let a reader
        # challenge was computed, carried across two transports and shown to
        # nobody. The notes are ADR 0028's disclosures, and they matter most
        # beside a refusal: a board whose only candidacy answers were unreadable
        # refuses *and* has the reason to hand.
        XSSY = '<img src=x onerror="window.__seq=1">'
        seq_body = {
            "available": True, "as_of": "2026-08-14",
            "asks_considered": 2, "board": "42", "boardName": "Storefront",
            "queue_items": 7, "basis": "queued behind 7 committed items",
            "note": "Dates are 85th-percentile.",
            "orderings": [{"first": "E1", "order": [
                {"id": "E1", "title": "Saved cards", "p85_days": 30,
                 "p85_date": "2026-10-01", "value": 210000,
                 "valueBasis": "1,900 abandonments a month", "neededBy": "2026-10-30"},
                {"id": "E2", "title": XSSY, "p85_days": 50,
                 "p85_date": "2026-11-20", "value": None, "valueBasis": ""},
            ]}],
            "comparison": [{"first": "E1", "its_own_p85_date": "2026-10-01",
                            "delays_others_by_days": 12, "misses_a_needed_by": []}],
            "skipped": [],
            "unachievable_at_any_priority": [],
            "notes": {"unreadable": [{"key": "E9", "said": XSSY}],
                      "delivered": [{"id": "E7", "resolved": "2026-08-01"}]},
        }
        seq_stub = """
        window.__DVD_BRIDGE__ = { name: 'stub', invoke: (route, params) => {
            const bodies = %s;
            if (route === 'contexts') return Promise.resolve({status: 200, body: bodies.contexts});
            if (route === 'context') return Promise.resolve({status: 200, body: bodies.context});
            if (route === 'sequence') return Promise.resolve({status: 200, body: bodies.sequence});
            return Promise.resolve({status: 404, body: null}); } };
        """ % json.dumps({"contexts": contexts_body, "context": forge_shaped,
                          "sequence": seq_body})
        page = b.new_page(viewport={"width": 1500, "height": 1400})
        page.add_init_script(seq_stub)
        page.goto(url)
        page.wait_for_timeout(500)
        page.evaluate("id => window.DVD.debug.selectContext(id)", cid)
        page.wait_for_timeout(900)
        page.evaluate("""() => [...document.querySelectorAll('button')]
            .find(b => /Sequence asks/i.test(b.textContent)).click()""")
        page.wait_for_timeout(900)
        tile = page.text_content("#c-forecast")

        check("the ask's worth is on the page at last",
              "210,000" in tile.replace(" ", " "), tile[:200])
        check("and the sentence a reader is meant to challenge is beside it",
              "1,900 abandonments a month" in tile, tile[:300])
        # An unpriced ask says so rather than showing a zero, and carries no
        # basis it does not have.
        check("an unpriced ask reads as not priced, never as nil",
              "not priced" in tile, tile[:400])
        check("the disclosures are named beside the answer",
              "could not be read" in tile and "E9" in tile
              and "already been delivered" in tile and "E7" in tile, tile[:600])
        # An ask title and a candidacy answer are both written by whoever can
        # edit an issue. `esc()` at output, once.
        check("hostile text in a title or an answer is escaped, not run",
              page.evaluate("() => window.__seq === undefined")
              and page.evaluate("() => !document.querySelector('#c-forecast img')"),
              tile[:120])
        page.close()

        # ---------- and a refusal still shows what was reached for ----------
        refused_body = {"available": False, "board": "42", "boardName": "Storefront",
                        "sentence": "Nothing on this board is marked as a candidate.",
                        "notes": {"unreadable": [{"key": "E9", "said": "Maybe"}],
                                  "delivered": []}}
        page = b.new_page(viewport={"width": 1500, "height": 1000})
        page.add_init_script(seq_stub.replace(json.dumps(seq_body), json.dumps(refused_body)))
        page.goto(url)
        page.wait_for_timeout(500)
        page.evaluate("id => window.DVD.debug.selectContext(id)", cid)
        page.wait_for_timeout(900)
        page.evaluate("""() => [...document.querySelectorAll('button')]
            .find(b => /Sequence asks/i.test(b.textContent)).click()""")
        page.wait_for_timeout(900)
        refused_tile = page.text_content("#c-forecast")
        check("a refusal carries the tool's sentence verbatim",
              "marked as a candidate" in refused_tile, refused_tile[:200])
        check("and still names the answer nobody could read",
              "E9" in refused_tile and "could not be read" in refused_tile,
              refused_tile[:300])
        page.close()


        # ---------- the value tile states which of three, and stops guessing ----------
        #
        # It said "No completed item carries a value estimate. If this site has
        # just installed the app, its Business Value field exists but a Jira
        # administrator has to add it to a screen" — one hedge over two states
        # with different fixes, and over a *file*, which has no app and no
        # screen. `editmeta` knows; the body carries it; this reads it.
        #
        # And it is carried on the context rather than the dataset, because a
        # body key nothing assigns is dropped in silence — which is how the
        # config whitelist and `asks_considered` both got here.
        unpriced = json.loads(json.dumps(forge_shaped))
        for i in unpriced.get("issues", []):
            i.pop("businessValue", None)

        def value_tile_with(setup):
            body = dict(unpriced)
            if setup is not None:
                body["setup"] = setup
            stub = """
            window.__DVD_BRIDGE__ = { name: 'stub', invoke: (route) => {
                const bodies = %s;
                if (route === 'contexts') return Promise.resolve({status: 200, body: bodies.contexts});
                if (route === 'context') return Promise.resolve({status: 200, body: bodies.context});
                return Promise.resolve({status: 404, body: null}); } };
            """ % json.dumps({"contexts": contexts_body, "context": body})
            pg = b.new_page(viewport={"width": 1500, "height": 1000})
            pg.add_init_script(stub)
            pg.goto(url)
            pg.wait_for_timeout(500)
            pg.evaluate("id => window.DVD.debug.selectContext(id)", cid)
            pg.wait_for_timeout(1100)
            text = pg.text_content("#value-body") or ""
            pg.close()
            return text

        off = value_tile_with({"businessValue": "off-screen", "valueBasis": "off-screen"})
        check("a field on no screen is stated, not guessed at",
              "is on none of this board's epic screens" in off and "if this site" not in off.lower(),
              off[:260])
        absent = value_tile_with({"businessValue": "absent", "valueBasis": "absent"})
        check("and a field the site does not have is a different sentence",
              "no Business Value field from this app" in absent, absent[:260])
        ready = value_tile_with({"businessValue": "ready", "valueBasis": "ready"})
        check("a field that is answerable blames nobody",
              "Nothing completed here carries a value estimate yet" in ready
              and "administrator" not in ready, ready[:260])
        # The transport with no Jira behind it: a file's value came from a file
        # and there is no screen to send anybody to.
        none = value_tile_with(None)
        check("and a body that says nothing about fields invents no administrator",
              "administrator" not in none and "screen" not in none, none[:260])

        # ---------- and it says what the board still needs ----------
        #
        # The app used to hedge across two states with different fixes — "if
        # this site has just installed the app, its field exists but an admin
        # has to add it to a screen". `editmeta` knows which, so this says which.
        needs_body = {"available": False, "board": "42", "boardName": "Storefront",
                      "sentence": "Nothing on this board is marked as a candidate.",
                      "setup": {"businessValue": "ready", "valueBasis": "off-screen",
                                "candidate": "off-screen", "tshirt": "absent"},
                      "notes": {"unreadable": [], "delivered": [], "unsized": []}}
        page = b.new_page(viewport={"width": 1500, "height": 1000})
        page.add_init_script(seq_stub.replace(json.dumps(seq_body), json.dumps(needs_body)))
        page.goto(url)
        page.wait_for_timeout(500)
        page.evaluate("id => window.DVD.debug.selectContext(id)", cid)
        page.wait_for_timeout(900)
        page.evaluate("""() => [...document.querySelectorAll('button')]
            .find(b => /Sequence asks/i.test(b.textContent)).click()""")
        page.wait_for_timeout(900)
        needs = page.text_content("#c-forecast")
        check("a field that exists but is on no screen names the admin's job",
              "adds Value Basis, Candidate" in needs and "no scope lets" in needs,
              needs[:400])
        check("and a field that is not on the site at all is a different sentence",
              "T-Shirt Size" in needs and "not on this site at all" in needs,
              needs[:500])
        check("a field that is ready is not listed as a job",
              "Business Value" not in needs.split("Before this board")[1][:400],
              needs[:500])
        # Two of the four are enough to put an epic forward. Listing all four as
        # blockers would overstate what a reader has to do.
        check("and it says which of them actually gates sequencing",
              "Only Candidate or T-Shirt Size is needed" in needs, needs[:600])
        page.close()

        # Nothing to say once a board is set up: a checklist of things that are
        # fine is furniture.
        ready_body = dict(needs_body, setup={"businessValue": "ready", "valueBasis": "ready",
                                             "candidate": "ready", "tshirt": "ready"})
        page = b.new_page(viewport={"width": 1500, "height": 1000})
        page.add_init_script(seq_stub.replace(json.dumps(seq_body), json.dumps(ready_body)))
        page.goto(url)
        page.wait_for_timeout(500)
        page.evaluate("id => window.DVD.debug.selectContext(id)", cid)
        page.wait_for_timeout(900)
        page.evaluate("""() => [...document.querySelectorAll('button')]
            .find(b => /Sequence asks/i.test(b.textContent)).click()""")
        page.wait_for_timeout(900)
        check("a board with every field ready is told nothing about setup",
              "Before this board can be sequenced" not in page.text_content("#c-forecast"),
              page.text_content("#c-forecast")[:200])
        page.close()

        # ---------- a transport that answered, and refused ----------
        # The failure this shipped with: `contexts` came back 404 with a
        # sentence, probeLive returned without reading it, and the customer got
        # a blank dashboard and an alert saying "server returned 404". A
        # connection that does not exist is silent on purpose; one that exists
        # and said no has a reason, and the page has to show it.
        refusing = """
        window.__DVD_BRIDGE__ = { name: 'stub', invoke: (route) =>
          Promise.resolve(route === 'contexts'
            ? {status: 404, body: {error: 'Project SFT has 2 boards, and none of them uses sprints.'}}
            : {status: 404, body: {error: 'No sprint on this site matches "single".'}}) };
        """
        page = b.new_page(viewport={"width": 1500, "height": 1000})
        page.add_init_script(refusing)
        page.goto(url)
        page.wait_for_timeout(900)
        bartext = page.text_content("#ctxbar")
        check("a refusal is put on the page, not swallowed",
              "none of them uses sprints" in bartext, bartext[:110])
        check("and the source row says there is no data rather than naming one",
              "NO DATA" in bartext, bartext[:60])
        check("the refusal is escaped, not parsed",
              page.evaluate("""() => !document.querySelector('#ctxbar').innerHTML
                  .includes('<img')"""))
        page.close()

        # ---------- a transport that answered, then failed one sprint ----------
        # `loadContext` reported its failure with alert(): a system dialog in a
        # page whose voice is a sentence, invisible to a test that did not
        # listen for it. It is said in the context bar now, where the reader
        # just acted, in the page's own callout. The same stub serves a
        # recipients route that is simply not there — a copy served by a plain
        # static server — which used to print "The server did not answer about
        # recipients (404)." as if a status code were a sentence.
        failing = """
        window.__DVD_BRIDGE__ = { name: 'stub', invoke: (route) => Promise.resolve(
          route === 'contexts'
            ? {status: 200, body: {source: 'jira', label: 'stub', contexts: [
                {id: 'B/1/S1', kind: 'sprint', boardId: '1', boardName: 'Board', projectKey: 'B',
                 projectName: 'B', sprintName: 'S1', sprintState: 'active',
                 startDate: '2026-08-03', endDate: '2026-08-14', asOfDate: '2026-08-10', issueCount: 3}]}}
            : route === 'recipients' ? {status: 404, body: null}
            : {status: 404, body: {error: 'Sprint S1 could not be read: the board is archived.'}}) };
        """
        dialogs = []
        page = b.new_page(viewport={"width": 1500, "height": 1000})
        page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
        page.add_init_script(failing)
        page.goto(url)
        page.wait_for_timeout(1200)
        # The served copy has data of its own, so the stub's sprint arrives as
        # an unselected stub rather than replacing a placeholder; selecting it
        # is what asks the connection for it, and what fails.
        page.evaluate("() => window.DVD.debug.selectContext('B/1/S1')")
        page.wait_for_timeout(900)
        bar = " ".join((page.text_content("#ctxbar") or "").split())
        check("a sprint that could not be loaded is said in the context bar, in the page's own callout",
              "Could not load that sprint" in bar and "board is archived" in bar and
              page.eval_on_selector_all("#ctxbar .refusal", "n => n.length") == 1, bar[:200])
        check("and not in a browser dialog", not dialogs, dialogs)
        brief = " ".join((page.text_content("#brief-body") or "").split())
        check("a served copy with no recipient route says so, not a status code as a sentence",
              "served without a recipient list" in brief and "(404)" not in brief, brief[:200])
        check("and the status is still on the page, in the note beneath",
              "answered 404" in brief, brief[-140:])
        page.close()

        # ---------- the real adapter, not the stub ----------
        # Everything above uses a stub bridge, and a stub cannot fail the way
        # the real one did: `@forge/bridge` connects to its host when it loads,
        # and outside a Forge iframe that throws. As an ES import that aborted
        # the adapter before it installed anything, and the only trace was an
        # uncaught error in the console — the page just quietly had no
        # transport. Inside a real iframe the same throw would read as a
        # dashboard that is merely offline.
        staged = ROOT / "forge" / "static" / "dashboard" / "build" / "bridge.js"
        if not staged.exists():
            # Reported, not skipped in silence — but a warning rather than a
            # failure. forge/static/ is git-ignored and built by `make
            # forge-static`, which needs the Forge SDK under forge/; a clean
            # clone that has never run it is not a broken checkout, and CI does
            # not run it at all. Failing here made `make test` red on a fresh
            # worktree for a reason that had nothing to do with the change.
            warn("the bundled adapter was checked (needs make forge-static)",
                 False, "forge/static/dashboard/build/bridge.js is not staged")
        else:
            import functools, http.server, threading
            H = functools.partial(http.server.SimpleHTTPRequestHandler,
                                  directory=str(staged.parent))
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8735), H)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                errs, logs = [], []
                page = b.new_page(viewport={"width": 1500, "height": 1000})
                page.on("pageerror", lambda e: errs.append(str(e)))
                page.on("console",
                        lambda m: logs.append(m.text) if m.type == "error" else None)
                page.goto("http://127.0.0.1:8735/index.html")
                page.wait_for_timeout(1500)
                check("the real adapter raises no uncaught error outside Forge",
                      errs == [], [e[:90] for e in errs][:2])
                check("and says why it did not install itself",
                      any("Forge bridge did not initialise" in t for t in logs),
                      [t[:70] for t in logs][:2])
                check("so the page falls back rather than believing it is connected",
                      page.evaluate("() => window.DVD.debug.transport()") == "loopback",
                      page.evaluate("() => window.DVD.debug.transport()"))
                page.close()
            finally:
                srv.shutdown()

        # The point of all of it.
        for field in ("foot", "kpis", "contexts", "issues", "ctx"):
            check("the two transports render the same %s" % field,
                  loop_print[field] == bridge_print[field],
                  {"loopback": str(loop_print[field])[:120],
                   "bridge": str(bridge_print[field])[:120]})
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()



def strict_style_csp(b):
    """A host may forbid inline style, and the page must lose no colour to it.

    The split build exists because a Forge Custom UI iframe's CSP blocks inline
    `<style>` and `<script>`. What that fix did not cover is the *attribute*
    form: `style-src` without `unsafe-inline` also discards every
    `style="..."` the renderers write, and it discards it silently — the
    attribute stays in the DOM, the declarations never reach the element.

    That is not a blank page, which is why it shipped and sat there. It is a
    page that renders correctly and loses the coloured half of itself: the fill
    inside every KPI progress bar, the severity disc beside each narrative
    point, every chart legend swatch. A bar keeps its track and a disc keeps
    its glyph, so it reads as a design decision rather than as a refusal.

    Pinned against the permissive host rather than against fixed numbers: the
    claim is not that the fill is 36px, it is that the two hosts paint the same
    page. Served over http rather than file:// because a CSP arrives in a
    header.
    """
    print("\n  a host that forbids inline style")

    import functools, http.server, tempfile, threading

    CSP = ("default-src 'none'; script-src 'self' 'unsafe-eval'; style-src 'self'; "
           "img-src 'self' data:; connect-src 'self'")

    # The same sources the Forge resource is built from, seeded with the demo
    # data so there is something to colour. Built here rather than read out of
    # forge/static/, which is git-ignored and needs the Forge SDK to stage.
    out = pathlib.Path(tempfile.mkdtemp(prefix="dvd-csp-"))
    subprocess.run([sys.executable, str(ROOT / "build.py"), "--split", str(out),
                    "--data", "data/sample-sprint.json"],
                   cwd=str(ROOT), check=True, capture_output=True)

    class Strict(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header("Content-Security-Policy", CSP)
            http.server.SimpleHTTPRequestHandler.end_headers(self)

        def log_message(self, *a):
            pass

    class Permissive(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    # What the tiles are actually made of. Every one of these gets its colour
    # or its length from a style attribute and from nothing else.
    PAINT = """() => {
      const g = s => { const e = document.querySelector(s); return e ? [
        getComputedStyle(e).width, getComputedStyle(e).backgroundColor] : null; };
      return {
        bar: g('.kpi .k-bar > i'),
        disc: g('.narr .ic'),
        swatch: g('.legend .swatch'),
        unpainted: Array.from(document.querySelectorAll('[style]'))
                        .filter(e => e.style.length === 0).length
      };
    }"""

    servers, seen = [], {}
    try:
        for name, handler, port in (("strict", Strict, 8736), ("permissive", Permissive, 8737)):
            srv = http.server.ThreadingHTTPServer(
                ("127.0.0.1", port),
                functools.partial(handler, directory=str(out)))
            servers.append(srv)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            page = b.new_page(viewport={"width": 1500, "height": 1000})
            page.goto("http://127.0.0.1:%d/index.html" % port)
            page.wait_for_timeout(900)
            seen[name] = page.evaluate(PAINT)
            page.close()
    finally:
        for srv in servers:
            srv.shutdown()

    strict, permissive = seen["strict"], seen["permissive"]

    # The fixture has to be one where a missing style attribute would show. A
    # transparent bar on a page with no bars would pass this whether or not the
    # fix is in.
    check("the sample page has a bar, a disc and a swatch to lose",
          all(permissive[k] for k in ("bar", "disc", "swatch")), permissive)
    check("every style attribute reached the element it was written for",
          strict["unpainted"] == 0,
          "%d element(s) kept an attribute the policy discarded" % strict["unpainted"])
    for part in ("bar", "disc", "swatch"):
        check("the %s is painted the same under a policy that forbids inline style" % part,
              strict[part] == permissive[part],
              {"strict": strict[part], "permissive": permissive[part]})

    shutil.rmtree(out, ignore_errors=True)


def main():
    if not DIST.exists():
        sys.exit("build first: python3 build.py")

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page(viewport={"width": 1500, "height": 1000})
        page.on("pageerror", lambda e: console.append("PAGEERROR " + str(e)))
        page.on("console", lambda m: console.append("CONSOLE " + m.text) if m.type == "error" else None)
        page.goto(DIST.as_uri())
        page.wait_for_timeout(800)

        # ---------- baseline ----------
        check("dashboard renders", page.is_visible("#kpis .kpi"))
        check("22 demo issues loaded", "22 issues" in page.text_content("#foot"),
              page.text_content("#foot")[:60])

        # ---------- context bar hidden for a single-sprint file ----------
        check("context bar is hidden when there is nothing to switch between",
              "hidden" in (page.get_attribute("#ctxbar", "class") or ""))

        # ---------- unit toggle ----------
        check("items is the default measure",
              page.get_attribute("[data-unit=items]", "aria-pressed") == "true")
        items_tile = page.text_content("#kpis .kpi:nth-child(1)")
        check("delivered tile reads in items", "22 items" in items_tile, items_tile[:60])
        # The delta under a share names the two counts it compares; it read
        # "+63% vs last sprint" under "55%", one glyph over two denominators.
        check("the delivered delta names the counts it compares",
              re.search(r"\d+ done vs \d+ last sprint", items_tile) is not None
              and "% vs last sprint" not in items_tile, items_tile[:90])
        pace_tile = page.text_content("#kpis .kpi:nth-child(2)")
        check("the pace tile says its figure in the verdict's words",
              re.search(r"\d+ percentage points? (behind|ahead of) the clock|level with the clock",
                        pace_tile) is not None, pace_tile[:90])
        check("and keeps the unit spelt out, never as points",
              "percentage point" in pace_tile and not re.search(r"\d+ points? (behind|ahead)", pace_tile),
              pace_tile[:90])
        burn_items = page.eval_on_selector_all("#burn-chart polyline", "n => n.length")
        page.click("[data-unit=points]"); page.wait_for_timeout(500)
        pts_tile = page.text_content("#kpis .kpi:nth-child(1)")
        check("switching to points changes the delivered tile", pts_tile != items_tile)
        check("points tile reads in story points", "83 story points" in pts_tile, pts_tile[:60])
        # The score moved from 52 to 57 with the toggle and the chip did not say
        # which measure it was scored in; it says so when the reader has left
        # the default, which is when it moved.
        chip_pts = " ".join((page.text_content("#t-health") or "").split())
        check("the health chip says it is scored in points once the measure is points",
              "/100" in chip_pts and "in story points" in chip_pts, chip_pts)
        # The per-person caption said "Story points per person" whichever
        # measure was selected, over bars that read "6 items".
        check("the per-person caption follows the measure into points",
              "Story points per person" in page.text_content("#c-dist .cap"),
              page.text_content("#c-dist .cap")[:50])
        check("the burndown still renders in points",
              page.eval_on_selector_all("#burn-chart polyline", "n => n.length") == burn_items)
        check("the footer states the active measure",
              "measured in story points" in page.text_content("#foot"),
              page.text_content("#foot")[-60:])
        page.click("[data-table=burn]"); page.wait_for_timeout(200)
        hdr = page.text_content("#burn-table")
        check("the burndown table carries both units",
              "Remaining items" in hdr and "Remaining pts" in hdr, hdr[:120])
        page.click("[data-table=burn]")
        page.click("[data-unit=items]"); page.wait_for_timeout(500)
        check("switching back restores items",
              page.text_content("#kpis .kpi:nth-child(1)") == items_tile)
        check("and the chip drops the measure again in the default",
              "in story points" not in (page.text_content("#t-health") or ""),
              page.text_content("#t-health"))

        # ---------- the dashboard agrees with the agent's facts pack ----------
        agent = json.load(open(ROOT / "tests" / "agent-facts.json"))
        # The flow figures the two implementations both compute. `metrics.py`
        # has `_pctile` and `src/app.js` has `pctile`, because the browser
        # cannot call Python — the same arrangement as `orgconfig.py` and its
        # mirror, and kept honest the same way: by comparing them rather than
        # trusting that they were written to match.
        page.evaluate("() => window.DVD.debug.setShown(window.DVD.debug.tileIds())")
        page.wait_for_timeout(500)
        cyc = page.text_content("#cycle-chart")
        # Both percentiles, because on this dataset p80 and p85 are the same
        # number — a drift in the constant would have gone straight past a
        # check that read only one of them. p50 and p85 differ here, so a
        # change to either end of CYCLE_PCTS fails.
        check("the cycle-time percentiles on the page are the ones the facts pack states",
              ("85%% of the %d items" % agent["flow"]["samples"]) in cyc
              and ("within %g calendar days" % agent["flow"]["cycle_p85"]) in cyc
              and ("50%% of them within %g" % agent["flow"]["cycle_p50"]) in cyc,
              (agent["flow"]["cycle_p50"], agent["flow"]["cycle_p85"], cyc[-200:]))
        thr = page.text_content("#thr-chart")
        check("weekly throughput on the page is the mean the facts pack states",
              ("%g items a week" % agent["flow"]["throughput_mean_per_week"]) in thr,
              (agent["flow"]["throughput_mean_per_week"], thr[-160:]))

        check("dashboard item completion matches the agent",
              ("%d items" % agent["delivery"]["items_total"]) in page.text_content("#kpis .kpi:nth-child(1)"),
              agent["delivery"]["items_total"])
        last = [b for b in json.load(open(ROOT / "data" / "sample-sprint.json"))["burndown"]
                if b["remainingItems"] is not None][-1]
        check("burndown item remainder matches the open-item count",
              last["remainingItems"] == agent["delivery"]["items_total"] - agent["delivery"]["items_done"],
              (last["remainingItems"], agent["delivery"]["items_total"] - agent["delivery"]["items_done"]))

        # ---------- unit-ish checks on the parser ----------
        d = page.evaluate("""() => {
            const I = window.DVDImport;
            return {
              jira:  I.parseDate('22/Jul/26 3:41 PM', 'dmy'),
              iso:   I.parseDate('2026-08-03T09:15:00.000+0100', 'dmy'),
              serial:I.parseDate('46022', 'dmy'),
              dmy:   I.parseDate('13/08/2026', 'dmy'),
              mdy:   I.parseDate('08/13/2026', 'mdy'),
              order: I.detectOrder(['01/02/2026','13/02/2026']).order,
              amb:   I.detectOrder(['01/02/2026','03/04/2026']).certain,
              conflict: I.detectOrder(['13/02/2026','02/29/2026']).certain,
              na:    I.detectOrder(['22/Jul/26','2026-08-03']).certain,
              flag:  [I.toBool('Impediment'), I.toBool('No'), I.toBool('')],
              num:   I.toNum('1,250.5')
            };
        }""")
        check("Jira date format", d["jira"] == "2026-07-22", d["jira"])
        check("ISO with timezone", d["iso"] == "2026-08-03", d["iso"])
        check("Excel serial date", d["serial"] == "2025-12-31", d["serial"])
        check("day-first date", d["dmy"] == "2026-08-13", d["dmy"])
        check("month-first date", d["mdy"] == "2026-08-13", d["mdy"])
        check("column order detected", d["order"] == "dmy", d["order"])
        check("undecidable order is reported", d["amb"] is False, d["amb"])
        check("contradictory order is reported", d["conflict"] is False, d["conflict"])
        check("non-numeric dates are not flagged", d["na"] is True, d["na"])
        check("boolean coercion", d["flag"] == [True, False, False], d["flag"])
        check("number coercion", d["num"] == 1250.5, d["num"])

        # ---------- Jira CSV ----------
        mapped, stats, warns = wizard(page, "jira-export.csv")
        for f in ["key", "summary", "status", "created", "resolved", "storyPoints",
                  "assignee", "priority", "epic", "flagged", "started"]:
            check("jira csv maps " + f, f in mapped)
        check("mid-sprint flag resolved",
              page.evaluate("() => window.DVDImport.W.map.addedMidSprint") is not None)
        check("jira csv row count", stats[0] == "22", stats)
        check("jira csv points parsed", float(stats[2]) > 0, stats)
        check("jira csv applied", "jira-export.csv" in page.text_content("#foot"),
              page.text_content("#foot")[:80])
        # A sprint with no predecessor shows no delta. It used to print
        # "→ no change" — a comparison that was never made, stated as a result.
        check("a sprint with nothing to compare against prints no delta, not 'no change'",
              "no change" not in page.text_content("#kpis .kpi:nth-child(1)"),
              page.text_content("#kpis .kpi:nth-child(1)")[:90])
        check("burndown rebuilt, not inherited",
              page.eval_on_selector_all("#burn-chart polyline", "n => n.length") >= 3)
        check("charts have data", page.eval_on_selector_all("#dist-chart rect[data-drill]", "n => n.length") > 0)
        # Replace means replace. A fresh export applied over the demo used to
        # keep the demo's goal, five sprints of its history, its milestones and
        # its release metrics under the new title — each captioned "from the
        # record", which is why a reader believed them. 1.79.25.
        check("replace drops the previous dataset's sprint goal",
              "checkout" not in (page.text_content("#t-goal") or "").lower(),
              page.text_content("#t-goal"))
        check("replace drops the previous dataset's history, so no 'last sprint' delta",
              "last sprint" not in page.text_content("#kpis .kpi:nth-child(1)"),
              page.text_content("#kpis .kpi:nth-child(1)")[:90])
        rel = page.text_content("#rel-body") or ""
        check("replace drops the previous dataset's milestones",
              "v2.2.0" not in rel and "No release record in this file" in rel, rel[:120])
        dora = page.text_content("#dora-body") or ""
        check("and its release metrics, which the tile says in the tool's words",
              "No release record in this file" in dora and "absent, not noisy" in dora, dora[:140])
        pred = page.text_content("#pred-chart") or ""
        check("the predictability tile says how many sprints the record holds",
              page.eval_on_selector_all("#pred-chart rect", "n => n.length") == 0 and
              "holds 1 sprint," in pred and "absent, not noisy" in pred, pred[:140])
        check("a record refusal is set in the refusal callout, not a note",
              page.eval_on_selector_all("#rel-body .fc-refusal, #dora-body .fc-refusal, #pred-chart .fc-refusal",
                                        "n => n.length") == 3)

        # ---------- merge a value-only file ----------
        before = page.text_content("#kpis")
        wizard(page, "value-estimates.csv", mode="merge")
        after = page.text_content("#kpis")
        check("merge changed the value tile", before != after)
        check("merge kept all 22 issues", "22 issues" in page.text_content("#foot"),
              page.text_content("#foot")[:70])

        # ---------- merge keeps the loaded record ----------
        page.reload(); page.wait_for_timeout(700)
        wizard(page, "value-estimates.csv", mode="merge")
        check("merge over the demo keeps its sprint goal",
              "checkout" in (page.text_content("#t-goal") or "").lower(), page.text_content("#t-goal"))
        check("merge keeps its milestones", "v2.2.0" in (page.text_content("#rel-body") or ""))
        check("merge keeps its release metrics", "Releases per week" in (page.text_content("#dora-body") or ""))
        check("merge keeps its history", page.eval_on_selector_all("#pred-chart rect", "n => n.length") > 0)

        # ---------- a JSON dataset brings its own record ----------
        page.reload(); page.wait_for_timeout(700)
        seed = json.loads((ROOT / "data" / "sample-sprint.json").read_text())
        own = {"schemaVersion": "1.0",
               "meta": dict(seed["meta"], sprintGoal="Goal carried by the file", sprintName="File sprint"),
               "issues": seed["issues"][:6],
               "releases": [{"name": "File release", "targetDate": seed["meta"]["endDate"],
                             "scopeIssues": 6, "doneIssues": 2, "status": "On track"}]}
        page.click("#btn-import")
        page.evaluate("() => { document.querySelector('#step-choose details').open = true; }")
        page.fill("#paste", json.dumps(own))
        page.click("#m-paste")
        page.wait_for_selector("#step-map:not(.hidden)", timeout=5000)
        page.click("#m-preview")
        page.wait_for_selector("#step-preview:not(.hidden)", timeout=5000)
        page.click("#m-apply"); page.wait_for_timeout(700)
        check("a JSON dataset's own goal is what appears",
              "Goal carried by the file" in (page.text_content("#t-goal") or ""), page.text_content("#t-goal"))
        check("and its own releases", "File release" in (page.text_content("#rel-body") or ""),
              (page.text_content("#rel-body") or "")[:100])
        check("what it does not carry is refused, not inherited",
              "No release record in this file" in (page.text_content("#dora-body") or ""))

        # ---------- Asana CSV ----------
        page.reload(); page.wait_for_timeout(700)
        mapped, stats, warns = wizard(page, "asana-export.csv")
        for f in ["key", "summary", "assignee", "created", "started", "dueDate", "businessValue"]:
            check("asana csv maps " + f, f in mapped)
        check("asana csv applied", "asana-export.csv" in page.text_content("#foot"))

        # ---------- XLSX ----------
        page.reload(); page.wait_for_timeout(700)
        mapped, stats, warns = wizard(page, "jira-export.xlsx")
        check("xlsx parsed", stats[0] == "22", stats)
        check("xlsx maps dates", "created" in mapped and "resolved" in mapped)
        xd = page.evaluate("() => window.DVD.data.issues[0].created")
        check("xlsx serial dates decoded", isinstance(xd, str) and xd.startswith("2026-"), xd)

        # ---------- drill-down still works on uploaded data ----------
        page.click("#kpis button:nth-child(1)")
        page.wait_for_timeout(400)
        check("drill-down works after upload", page.is_visible("#panel.on"))
        check("drill lists issues", page.eval_on_selector_all("#p-body .issue", "n => n.length") > 0)
        page.click("#p-done")

        # ---------- reload demo ----------
        page.click("#btn-import"); page.click("#m-sample"); page.wait_for_timeout(500)
        check("demo data restores", "22 issues" in page.text_content("#foot"))

        # ---------- multi-context bundle ----------
        # Passed in as an object, not fetched: browsers block fetch() from
        # file:// — the same restriction that makes live mode need a server.
        bundle = json.loads((ROOT / "data" / "sample-bundle.json").read_text())
        page.goto(DIST.as_uri()); page.wait_for_timeout(600)
        page.evaluate("d => window.DVD.applyDataset(d)", bundle)
        page.wait_for_timeout(700)
        check("context bar appears for a bundle",
              "hidden" not in (page.get_attribute("#ctxbar", "class") or ""))
        projects = page.eval_on_selector_all("#c-proj option", "n => n.map(e => e.textContent)")
        check("both projects are offered", len(projects) == 2, projects)
        sprints = page.eval_on_selector_all("#c-sprint option", "n => n.map(e => e.textContent)")
        check("six sprints plus a rollup are offered", len(sprints) == 7, sprints)
        check("the active sprint is marked", any("current" in s for s in sprints), sprints)
        check("bundle defaults to the active sprint",
              "Sprint 24" in page.text_content("#t-title"), page.text_content("#t-title"))

        before = page.text_content("#foot")
        page.select_option("#c-sprint", label=[s for s in sprints if "Sprint 21" in s][0])
        page.wait_for_timeout(600)
        check("selecting a past sprint changes the view",
              "Sprint 21" in page.text_content("#t-title"), page.text_content("#t-title"))
        check("the issue count changes with the sprint", page.text_content("#foot") != before)
        check("charts redraw for the selected sprint",
              page.eval_on_selector_all("#burn-chart polyline", "n => n.length") >= 3)
        check("drill-down works on a past sprint",
              page.eval_on_selector_all("#dist-chart rect[data-drill]", "n => n.length") > 0)

        page.select_option("#c-sprint", label=[s for s in sprints if s.startswith("All")][0])
        page.wait_for_timeout(600)
        check("the rollup spans every sprint on the board",
              "All 6 sprints" in page.text_content("#t-title"), page.text_content("#t-title"))
        check("the rollup explains why it has no burndown",
              "rolls up" in page.text_content("#burn-chart"), page.text_content("#burn-chart")[:70])
        check("the rollup still shows flow and ageing",
              page.eval_on_selector_all("#age-chart rect[data-band]", "n => n.length") > 0)

        page.select_option("#c-proj", label="Highpeak Mobile"); page.wait_for_timeout(600)
        boards = page.eval_on_selector_all("#c-board option", "n => n.map(e => e.textContent)")
        check("boards are scoped to the selected project", boards == ["Mobile Apps"], boards)
        check("switching project lands on a real sprint",
              "Sprint" in page.text_content("#t-title"), page.text_content("#t-title"))

        # a v1 single-sprint file still loads unchanged
        page.evaluate("d => window.DVD.applyDataset(d)",
                      json.loads((ROOT / "data" / "sample-sprint.json").read_text()))
        page.wait_for_timeout(600)
        check("a v1 file still loads and hides the context bar",
              "hidden" in (page.get_attribute("#ctxbar", "class") or "") and
              "22 issues" in page.text_content("#foot"), page.text_content("#foot")[:60])

        # ---------- tile visibility: building a view for one audience ----------
        TIDS = page.evaluate("() => window.DVD.debug.tileIds()")
        vis = lambda: page.evaluate(
            "ids => ids.filter(i => !document.getElementById(i).classList.contains('hidden'))", TIDS)

        # The four flow tiles measure any board — cycle time, ageing work in
        # progress, weekly throughput and cumulative flow are properties of
        # issues and dates — so they are offered here and tickable. They are
        # only shown by default on a board that runs no sprints, where they are
        # the main event rather than four more tiles on a grid of thirteen.
        FLOW = ["c-cycle", "c-wip", "c-thr", "c-cfd"]
        default = page.evaluate("() => window.DVD.debug.presets().all")
        check("a sprint board shows everything except the flow tiles",
              vis() == default and not [t for t in FLOW if t in vis()], vis())
        check("but every tile, flow ones included, has a checkbox",
              sorted(page.eval_on_selector_all("[data-tile]", "n => n.map(x => x.dataset.tile)"))
              == sorted(TIDS), len(TIDS))
        check("and none of them is disabled — a sprint board supports them all",
              page.eval_on_selector_all("[data-tile]", "n => n.filter(x => x.disabled).length") == 0)

        kpi_before = page.text_content("#kpis")
        open_picker(page)
        check("the picker opens", page.is_visible("#view-pop") and
              page.get_attribute("#btn-view", "aria-expanded") == "true")
        check("there is a checkbox per tile",
              page.eval_on_selector_all("[data-tile]", "n => n.length") == len(TIDS))
        # The button read "Tiles · Everything" on a sprint board while the
        # popover beneath it said "4 hidden": the flow tiles a sprint board does
        # not draw. The label names what the preset shows and carries the count
        # whenever anything is hidden, whoever hid it.
        btn = " ".join((page.text_content("#btn-view") or "").split())
        check("the Tiles button does not say Everything while tiles are hidden",
              "Everything" not in btn, btn)
        check("it names the set it shows and counts it",
              "All sprint tiles" in btn and re.search(r"\b\d+ of %d\b" % len(TIDS), btn) is not None, btn)
        check("the popover's preset carries the same name",
              "All sprint tiles" in (page.text_content('[data-preset="all"]') or ""),
              page.text_content('[data-preset="all"]'))

        page.click('[data-preset="exec"]')
        page.wait_for_timeout(200)
        ex = vis()
        check("the executive view is the agent's exec-brief shape",
              ex == ["c-kpis", "c-exec", "c-pred", "c-dora",
                     "c-value", "c-rel", "c-risk"], ex)   # no forecast: this is a file
        check("the executive view keeps the narrative",
              "c-exec" in ex and len(page.text_content("#exec-list").strip()) > 40)
        # A view that quietly drops tiles reads as a whole page to whoever gets it.
        note = page.text_content("#vp-count")
        check("hidden tiles are named, not just counted",
              "hidden" in note and "Team load" in note, note[:90])

        page.click('[data-preset="team"]')
        page.wait_for_timeout(200)
        tm = vis()
        check("the team view is the agent's team-report shape",
              tm == ["c-kpis", "c-exec", "c-burn", "c-dist", "c-flow", "c-age",
                     "c-pred", "c-load", "c-risk"], tm)
        check("the team view keeps the narrative too", "c-exec" in tm)

        # The whole feature is only safe if it changes what is shown and
        # nothing that is counted.
        check("hiding tiles does not change what is computed",
              page.text_content("#kpis") == kpi_before)

        # ---------- a saved view is a working file, with the loaded data ----------
        page.evaluate("d => window.DVD.applyDataset(d)",
                      json.loads((ROOT / "data" / "sample-bundle.json").read_text()))
        page.wait_for_timeout(700)
        loaded_issues = page.evaluate("() => window.DVD.data.issues.length")
        open_picker(page)
        page.click('[data-preset="exec"]')
        page.wait_for_timeout(200)
        with page.expect_download() as dl:
            page.click("#vp-save")
        saved = ROOT / "tests" / "saved-view.tmp.html"
        dl.value.save_as(str(saved))
        check("saving a view produces a file", saved.exists() and saved.stat().st_size > 100_000,
              saved.stat().st_size if saved.exists() else 0)

        p2 = b.new_page(viewport={"width": 1500, "height": 1000})
        p2errs = []
        p2.on("pageerror", lambda e: p2errs.append(str(e)))
        p2.goto(saved.as_uri())
        p2.wait_for_timeout(900)
        v2 = p2.evaluate("ids => ids.filter(i => !document.getElementById(i).classList.contains('hidden'))", TIDS)
        check("the saved copy opens on the view it was saved with", v2 == ex, v2)
        # The trap this guards: after an upload the dataset lives in memory, so
        # serialising the page alone hands someone a file that quietly reverted
        # to the demo sprint — right-looking numbers about the wrong company.
        check("the saved copy carries the loaded data, not the demo seed",
              p2.evaluate("() => window.DVD.data.issues.length") == loaded_issues,
              (p2.evaluate("() => window.DVD.data.issues.length"), loaded_issues))
        check("the saved copy renders its charts", p2.is_visible("#kpis .kpi"))
        check("the saved copy raises no page errors", not p2errs, p2errs[:2])
        p2.close()
        saved.unlink()

        # ---------- the view travels in the URL, and bad input fails safe ----------
        page.goto(DIST.as_uri() + "?view=exec")
        page.wait_for_timeout(700)
        check("?view=exec applies on load", vis() == ex, vis())
        page.goto(DIST.as_uri() + "?tiles=not-a-tile,nonsense")
        page.wait_for_timeout(700)
        check("an unrecognised tile list shows the default view rather than a blank page",
              vis() == default, len(vis()))

        # ---------- tile order ----------
        # The order is a property of the view exactly as the selection is, and
        # it travels the same way. Two things matter beyond it working. The DOM
        # order has to follow the visual order: a CSS `order` would move the
        # picture and leave the tab order and the screen-reader reading order
        # in the old sequence, so the page would read in an order nobody can
        # see. And a garbled ?order= has to yield the whole page in an odd
        # sequence rather than a page missing tiles.
        page.goto(DIST.as_uri())
        page.wait_for_timeout(800)
        dom_order = lambda: page.eval_on_selector_all("#grid > *", "n => n.map(e => e.id)")
        order = lambda: page.evaluate("() => window.DVD.debug.order()")
        check("the default order is the source order", order() == TIDS, order()[:3])
        # ADR 0032: the executive scans a row of figures before reading a
        # paragraph. The band was second, under a 437px verdict card, and sat
        # at y=717 on a 1440-wide screen and y=1735 on a phone.
        check("the KPI band is the first tile, before the verdict",
              TIDS[:2] == ["c-kpis", "c-exec"], TIDS[:2])
        band_y = page.evaluate("() => document.getElementById('c-kpis').getBoundingClientRect().top + scrollY")
        check("and it starts inside the first screen at 1500 wide", band_y < 300, band_y)
        # The chrome above the band was the tallest thing on the page: a
        # 175px toolbar at 1440 and 218px at 1280, its action cluster wrapping
        # to three rows beside the title. The goal moved into the verdict
        # card, the health chip to the band's end, Print and Export behind
        # one control.
        top_h = page.eval_on_selector(".topbar", "e => e.getBoundingClientRect().height")
        check("the toolbar is one row at 1500 wide", top_h < 110, top_h)
        check("the health chip sits at the band's end, not in the toolbar",
              page.eval_on_selector("#t-health", "e => e.closest('#c-kpis') !== null && e.closest('.topbar') === null"))
        check("the sprint goal sits in the verdict card",
              page.eval_on_selector("#t-goal", "e => e.closest('#c-exec') !== null") and
              "Sprint goal" in (page.text_content("#c-exec") or ""))
        check("Print and Export CSV wait behind More",
              not page.is_visible("#btn-print") and not page.is_visible("#btn-export") and page.is_visible("#btn-more"))
        page.click("#btn-more")
        page.wait_for_timeout(150)
        check("and appear when it opens, with focus on the first",
              page.is_visible("#btn-print") and page.evaluate("() => document.activeElement.id") == "btn-export")
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)
        check("Escape closes More and returns focus to it",
              not page.is_visible("#btn-print") and page.evaluate("() => document.activeElement.id") == "btn-more")
        page.set_viewport_size({"width": 1280, "height": 900})
        page.wait_for_timeout(300)
        tops = page.eval_on_selector_all("#kpis .kpi", "n => [...new Set(n.map(e => Math.round(e.getBoundingClientRect().top)))]")
        check("at 1280 wide the band is one row of eight", len(tops) == 1, tops)
        page.set_viewport_size({"width": 1100, "height": 900})
        page.wait_for_timeout(300)
        # A tile without a delta used to be a line shorter than one with, so the
        # two rows of four differed by the delta alone. The placeholder keeps
        # its height; rows may still differ where a long sub-line wraps.
        # One baseline per row (1.79.27): within a row of the band, the value
        # tops and the bar tops agree on every tile, whatever the sub-line or
        # the delta did. Grouped by the tile's own top so it holds at any width.
        bl = page.evaluate("""() => [...document.querySelectorAll('#kpis .kpi')].map(e => {
            const top = s => Math.round(e.querySelector(s).getBoundingClientRect().top);
            return { row: Math.round(e.getBoundingClientRect().top), val: top('.k-val'), bar: top('.k-bar') };
        })""")
        rows = {}
        for t in bl:
            rows.setdefault(t["row"], []).append(t)
        check("every KPI value in a row sits on one baseline",
              rows and all(max(x["val"] for x in r) - min(x["val"] for x in r) <= 1 for r in rows.values()),
              {k: [x["val"] for x in r] for k, r in rows.items()})
        check("and every KPI bar in a row ends on one line",
              rows and all(max(x["bar"] for x in r) - min(x["bar"] for x in r) <= 1 for r in rows.values()),
              {k: [x["bar"] for x in r] for k, r in rows.items()})
        dh = page.eval_on_selector_all("#kpis .kpi", "n => n.map(e => { const d = e.querySelector('.k-delta'); return d ? [d.textContent.length, Math.round(d.getBoundingClientRect().height)] : null; })")
        check("a tile without a delta keeps the delta's height",
              all(x is not None and (x[0] > 0 or x[1] >= 16) for x in dh), dh)
        page.set_viewport_size({"width": 1500, "height": 1000})
        page.wait_for_timeout(300)
        check("the tiles sit in the DOM in that order", dom_order() == TIDS, dom_order()[:3])

        open_picker(page)
        check("the first tile cannot move up or to the top, and the last cannot move down or to the bottom",
              page.eval_on_selector('[data-move=up][data-move-id="%s"]' % TIDS[0], "e => e.disabled") and
              page.eval_on_selector('[data-move=top][data-move-id="%s"]' % TIDS[0], "e => e.disabled") and
              page.eval_on_selector('[data-move=down][data-move-id="%s"]' % TIDS[-1], "e => e.disabled") and
              page.eval_on_selector('[data-move=bottom][data-move-id="%s"]' % TIDS[-1], "e => e.disabled"))
        check("each row has one Move button opening a menu, not a pair of arrows",
              page.eval_on_selector_all("[data-move-menu]", "n => n.length") == len(TIDS) and
              page.eval_on_selector_all("#vp-list .vp-menu[role=menu] [role=menuitem]", "n => n.length") == 4 * len(TIDS))

        kpi_pre_order = page.text_content("#kpis")
        # Two moves up, each through the row's menu; the list rebuilds and the
        # menu closes after each, so it is opened again for the second.
        for _ in range(2):
            page.click('[data-move-menu="c-risk"]')
            page.click('[data-move=up][data-move-id="c-risk"]')
            page.wait_for_timeout(200)
        page.wait_for_timeout(300)
        moved = order()
        check("a tile moves up two places", moved.index("c-risk") == TIDS.index("c-risk") - 2,
              moved[-4:])
        # "Put this first" is one choice, not seventeen presses.
        page.click('[data-move-menu="c-risk"]')
        page.click('[data-move=top][data-move-id="c-risk"]')
        page.wait_for_timeout(300)
        check("a tile moves to the top in one move", order()[0] == "c-risk", order()[:2])
        page.click('[data-move-menu="c-risk"]')
        page.click('[data-move=bottom][data-move-id="c-risk"]')
        page.wait_for_timeout(300)
        check("and to the bottom in one", order()[-1] == "c-risk", order()[-2:])
        moved = order()
        check("the DOM order follows the visual order", dom_order() == moved, dom_order()[-4:])
        # Same guarantee the tile picker makes: the view changes, the numbers
        # behind it do not.
        check("reordering does not change what is computed",
              page.text_content("#kpis") == kpi_pre_order)
        check("a custom order is named in the picker, not left to be noticed",
              "Custom order" in page.text_content("#vp-count"), page.text_content("#vp-count")[-40:])
        check("the order travels in the URL", "order=c-kpis" in page.url, page.url[-70:])

        # The popover measured 761px with no bound: at a 720px-tall viewport its
        # two actions were off-screen, and at 375 wide its left edge was at -10.
        page.set_viewport_size({"width": 1280, "height": 720})
        page.wait_for_timeout(300)
        box = page.eval_on_selector("#view-pop", "e => { const r = e.getBoundingClientRect(); return [r.top, r.bottom, r.left, innerHeight]; }")
        check("the picker stays inside a short viewport and scrolls instead",
              box[1] <= box[3] and page.eval_on_selector("#view-pop", "e => e.scrollHeight > e.clientHeight"), box)
        page.set_viewport_size({"width": 375, "height": 812})
        page.wait_for_timeout(300)
        left = page.eval_on_selector("#view-pop", "e => e.getBoundingClientRect().left")
        check("on a phone the picker is a sheet inside the viewport", left >= 0, left)
        page.set_viewport_size({"width": 1500, "height": 1000})
        page.wait_for_timeout(300)
        # A Move menu opened from a scrolling popover is not clipped by it.
        page.click('[data-move-menu="c-risk"]')
        page.wait_for_timeout(150)
        menu = page.eval_on_selector('[data-move-menu="c-risk"] + .vp-menu', "e => { const r = e.getBoundingClientRect(); return [getComputedStyle(e).position, r.width, r.height, r.left]; }")
        check("a Move menu escapes the popover's scroll box", menu[0] == "fixed" and menu[1] > 0 and menu[2] > 0 and menu[3] >= 8, menu)
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)

        page.click("#vp-order-reset")
        page.wait_for_timeout(300)
        check("the default order can be restored", order() == TIDS and dom_order() == TIDS, order()[:3])
        check("restoring it drops the parameter rather than spelling out the default",
              "order=" not in page.url, page.url[-40:])

        page.goto(DIST.as_uri() + "?order=c-risk,c-exec,not-a-tile")
        page.wait_for_timeout(800)
        restored = order()
        check("a partial order is honoured", restored[:2] == ["c-risk", "c-exec"], restored[:4])
        check("an unrecognised id is dropped without dropping a tile",
              sorted(restored) == sorted(TIDS), len(restored))
        check("the DOM follows an order that arrived in the URL", dom_order() == restored)

        # Selection and order are independent on purpose. Folding the order into
        # ?tiles= would mean un-ticking a tile silently reshuffled the page.
        page.evaluate("() => window.DVD.debug.setTiles(window.DVD.debug.presets().exec)")
        page.wait_for_timeout(300)
        check("hiding tiles leaves the order alone", order() == restored, order()[:3])

        # The clone carries the tiles already in sequence, but the copy reorders
        # itself on load — without data-order it would put them straight back.
        with page.expect_download() as dl2:
            open_picker(page)
            page.click("#vp-save")
        saved2 = ROOT / "tests" / "saved-order.tmp.html"
        dl2.value.save_as(str(saved2))
        p3 = b.new_page(viewport={"width": 1500, "height": 1000})
        p3.goto(saved2.as_uri())
        p3.wait_for_timeout(900)
        check("a saved copy opens in the order it was saved in",
              p3.eval_on_selector_all("#grid > *", "n => n.map(e => e.id)") == restored,
              p3.eval_on_selector_all("#grid > *", "n => n.map(e => e.id)")[:3])
        p3.close()
        saved2.unlink()

        # ---------- the forecast tile offline ----------
        # Opened from disk there is no server, so the tile must say so rather
        # than showing a number, a spinner that never resolves, or a blank card.
        page.goto(DIST.as_uri())
        page.wait_for_timeout(900)
        # In a saved copy the forecast and the brief can only refuse, so both
        # are off in every preset and one tick away; the picker says why.
        check("a saved copy hides the forecast and the brief by default",
              page.eval_on_selector("#c-forecast", "e => e.classList.contains('hidden')") and
              page.eval_on_selector("#c-brief", "e => e.classList.contains('hidden')"))
        check("and still reads as the preset it is, not a custom view",
              "All sprint tiles" in (page.text_content("#btn-view") or ""), page.text_content("#btn-view"))
        open_picker(page)
        vp = " ".join((page.text_content("#vp-count") or "").split())
        check("the picker says the two are off because this is a saved copy",
              "off in a saved copy" in vp and "Monte Carlo forecast" in vp, vp[-220:])
        page.keyboard.press("Escape")
        page.evaluate("() => window.DVD.debug.setShown(window.DVD.debug.tileIds())")
        page.wait_for_timeout(400)
        fb = " ".join((page.text_content("#forecast-body") or "").split())
        check("shown, the forecast tile says it is not in this copy, in the reader's words",
              "is not in this copy" in fb and "make" not in fb and "forecast.py" not in fb, fb[:120])
        check("the offline forecast tile shows no percentile figures",
              "% of simulations" not in fb and "Confidence" not in fb, fb[:90])
        page.focus("#c-forecast .info")
        page.wait_for_timeout(250)
        check("how to run the connection is behind the tile's help mark",
              "make serve-live" in (page.text_content("#tip") or ""), (page.text_content("#tip") or "")[-120:])
        page.keyboard.press("Escape")
        brief = " ".join((page.text_content("#brief-body") or "").split())
        check("the brief tile in a saved copy prints no status code", "404" not in brief and "answered" not in brief, brief[:120])

        # ---------- the page and the tools agree about the calendar ----------
        # The page mirrors agent/tools/orgconfig.py in JavaScript, because the
        # browser cannot call Python. That duplication is accepted here the same
        # way derive() duplicating metrics.py is accepted — on condition that a
        # test proves they agree, and under a config that is NOT the default,
        # since two implementations of "Mon to Fri" agree by accident.
        sys.path.insert(0, str(ROOT / "agent" / "tools"))
        import orgconfig as OC  # noqa: E402

        cfg = OC.merge(OC.DEFAULTS, {
            "workingWeek": ["sun", "mon", "tue", "wed", "thu"],
            "holidays": ["2026-08-05", "2026-08-12"],
            "sprintLengthDays": 10,
            "statuses": {"done": ["Signed off", "Shipped"],
                         "inProgress": ["With QA", "In Review"]},
        })
        ds = json.loads((ROOT / "data" / "sample-sprint.json").read_text())
        ds["orgConfig"] = cfg
        page.goto(DIST.as_uri())
        page.wait_for_timeout(700)
        page.evaluate("d => window.DVD.applyDataset(d)", ds)
        page.wait_for_timeout(700)

        check("the page adopts the config the dataset carries",
              page.evaluate("() => window.DVD.orgConfig().sprintLengthDays") == 10,
              page.evaluate("() => window.DVD.orgConfig()"))

        # ---- every key the dataset states, not the four that once existed ----
        #
        # `orgConfigOf` named four keys and dropped the rest, while its own
        # comment said it merged as the Python does. `countSubtasks`,
        # `countedTypes`, `valueFromHierarchy` and `trendSprints` were each
        # added to the defaults and to the code that reads them, and never to
        # the merge — so a dataset that set one had it silently discarded and
        # the page fell back to its own default. Three of the four decide what
        # the page *counts*: a site setting `countSubtasks: true` had subtasks
        # counted in the facts pack and dropped from the dashboard.
        #
        # **The check above could not have caught it.** It builds its config
        # with `OC.merge(OC.DEFAULTS, ...)` and overrides only the calendar, so
        # the counting keys held their defaults — and a dropped default and the
        # fallback default are the same number. Hence a config that moves them.
        counting = OC.merge(cfg, {"countSubtasks": True,
                                  "countedTypes": ["Story", "Bug"],
                                  "valueFromHierarchy": 0,
                                  "trendSprints": 12})
        ds2 = json.loads((ROOT / "data" / "sample-sprint.json").read_text())
        ds2["orgConfig"] = counting
        page.evaluate("d => window.DVD.applyDataset(d)", ds2)
        page.wait_for_timeout(700)
        seen = page.evaluate("() => window.DVD.orgConfig()")
        for k in ("countSubtasks", "countedTypes", "valueFromHierarchy", "trendSprints"):
            check("the page keeps %s from the dataset rather than its own default" % k,
                  seen.get(k) == counting[k],
                  {"page": seen.get(k), "dataset": counting[k]})

        # The whole merge, key for key, against the Python one. `version` is
        # dropped from both sides: it is a schema marker rather than an
        # assumption anything acts on, and it is the one key ORG_DEFAULTS does
        # not carry — so the page has it only when a dataset states it, while
        # the tools always do.
        py_merged = {k: v for k, v in OC.merge(OC.DEFAULTS, counting).items()
                     if k != "version"}
        js_merged = {k: v for k, v in seen.items() if k != "version"}
        check("the page's merged config matches orgconfig.merge exactly",
              js_merged == py_merged, {"page": js_merged, "py": py_merged})

        # And the counting rule that reads them moves with it — otherwise the
        # keys could arrive and change nothing, which is the same bug wearing a
        # different face.
        subtask_kept = page.evaluate(
            "() => window.DVD.countedIssues("
            "  [{key:'A',isSubtask:true,type:'Story'}], window.DVD.orgConfig()"
            ").kept.length")
        check("and countedIssues acts on the value that arrived",
              subtask_kept == 1, subtask_kept)

        # ---------- the page says which statuses it had to infer ----------
        #
        # An unrecognised status is the quiet way these numbers go wrong: an
        # "Awaiting sign-off" column reads as To Do, the burndown stops moving,
        # and a flat burndown looks exactly like a team that delivered nothing.
        # Before this the page said nothing at all — the fetcher printed the
        # names once, to a terminal, to whoever ran the pull.
        wf = json.loads((ROOT / "data" / "sample-sprint.json").read_text())
        wf["orgConfig"] = OC.merge(OC.DEFAULTS, {
            "statuses": {"done": ["Done"], "inProgress": ["In Progress"]}})
        wf["issues"] = [dict(wf["issues"][0], key="WF-1", status="Awaiting sign-off",
                             statusCategory=None)]
        page.evaluate("d => window.DVD.applyDataset(d)", wf)
        page.wait_for_timeout(700)

        rows = page.evaluate("() => window.DVD.inferredStatuses()")
        names = [r["status"] for r in rows]
        check("a status the config does not name is recorded as inferred",
              "Awaiting sign-off" in names, names)
        check("with what it was read as",
              [r for r in rows if r["status"] == "Awaiting sign-off"][0]["readAs"] == "To Do",
              rows)
        check("and the chip appears, counting them",
              page.is_visible("#btn-workflow")
              and "inferred" in page.inner_text("#btn-workflow"),
              page.inner_text("#btn-workflow"))
        page.click("#btn-workflow")
        page.wait_for_timeout(200)
        pop = page.inner_text("#wf-pop")
        check("the panel names the status and what happened to it",
              "Awaiting sign-off" in pop and "To Do" in pop, pop[:160])

        # A status name is written by anyone who can configure a workflow, and
        # it reaches innerHTML here. `esc()` at output, once — the rule a stored
        # XSS was shipped for breaking twice.
        hostile = '<img src=x onerror="window.__wf=1">'
        wf2 = json.loads(json.dumps(wf))
        wf2["issues"] = [dict(wf["issues"][0], key="WF-2", status=hostile,
                              statusCategory=None)]
        page.evaluate("d => window.DVD.applyDataset(d)", wf2)
        page.wait_for_timeout(500)
        page.click("#btn-workflow")
        page.wait_for_timeout(300)
        check("a hostile status name is escaped rather than executed",
              page.evaluate("() => window.__wf === undefined")
              and page.evaluate("() => !document.querySelector('#wf-pop img')"),
              page.inner_text("#wf-pop")[:120])

        # The record is per dataset. Without a reset, a second upload reports
        # the first file's statuses — which is a claim about the wrong board.
        clean = json.loads((ROOT / "data" / "sample-sprint.json").read_text())
        clean["orgConfig"] = OC.merge(OC.DEFAULTS, {"statuses": {
            "done": sorted({i.get("status") for i in clean["issues"]
                            if i.get("statusCategory") == "Done"}),
            "inProgress": sorted({i.get("status") for i in clean["issues"]
                                  if i.get("statusCategory") == "In Progress"})}})
        for i in clean["issues"]:
            i["statusCategory"] = i.get("statusCategory")
        page.evaluate("d => window.DVD.applyDataset(d)", clean)
        page.wait_for_timeout(700)
        check("nothing carries over from the previously loaded dataset",
              hostile not in json.dumps(page.evaluate("() => window.DVD.inferredStatuses()")),
              page.evaluate("() => window.DVD.inferredStatuses()"))

        # And a producer's own record travels in the data, because inference
        # happens upstream for a fetched file and the page cannot re-derive
        # what it never saw.
        stated = json.loads((ROOT / "data" / "sample-sprint.json").read_text())
        stated["orgConfig"] = OC.merge(OC.DEFAULTS, {"inferredStatuses": [
            {"status": "Awaiting legal", "readAs": "To Do",
             "from": "the tracker's own category"}]})
        page.evaluate("d => window.DVD.applyDataset(d)", stated)
        page.wait_for_timeout(700)
        got = page.evaluate("() => window.DVD.inferredStatuses()")
        check("the page reports what the producer inferred, not only its own",
              any(r["status"] == "Awaiting legal"
                  and r["from"] == "the tracker's own category" for r in got), got)

        # ---------- and a reader can say what a status means ----------
        #
        # It edits the *data*, not the view. A view-level toggle would have two
        # people reading different completion figures from one file with nothing
        # saying why — the disagreement the config lives inside the data to
        # prevent — and it has nowhere to live, since this page may use no
        # browser storage.
        ed = json.loads((ROOT / "data" / "sample-sprint.json").read_text())
        ed["orgConfig"] = OC.merge(OC.DEFAULTS, {
            "statuses": {"done": ["Done"], "inProgress": ["In Progress"]}})
        ed["issues"] = [
            dict(ed["issues"][0], key="ED-1", status="Accepted", statusCategory="In Progress",
                 statusTransitions=[{"to": "Peer read", "at": "2026-08-04"}]),
            dict(ed["issues"][0], key="ED-2", status="In Progress", statusCategory="In Progress",
                 statusTransitions=[]),
        ]
        page.evaluate("d => window.DVD.applyDataset(d)", ed)
        page.wait_for_timeout(700)
        page.click("#btn-workflow")
        page.wait_for_timeout(250)

        offered = page.evaluate(
            "() => [...document.querySelectorAll('#wf-pop select[data-wf]')]"
            ".map(s => s.getAttribute('data-wf'))")
        # A status that appears only in an issue's history still moves `started`,
        # and through it every cycle-time and flow figure. Leaving it out of the
        # mapping would drop it from the config on apply.
        check("a status seen only in a transition is offered too",
              "Peer read" in offered, offered)
        # The config's own defaults are not offered: Closed, Doing, QA and the
        # rest are names most boards never use, and sixteen rows bury the five
        # a reader came to check.
        check("and generic config defaults this board never uses are not",
              "Doing" not in offered and "Shipped" not in offered, offered)

        page.select_option("#wf-pop select[data-wf='Accepted']", "Done")
        page.click("#wf-apply")
        page.wait_for_timeout(800)

        cfg_after = page.evaluate("() => window.DVD.orgConfig()")
        check("the reader's answer goes into the dataset's own config",
              "Accepted" in cfg_after["statuses"]["done"], cfg_after["statuses"])
        # normaliseIssue keeps a statusCategory the producer resolved, because
        # re-deriving it under a different config is how one issue gets two
        # answers. Applying a mapping is a reader saying that answer is wrong.
        cat = page.evaluate(
            "() => window.DVD.data.issues.filter(i => i.key === 'ED-1')[0].statusCategory")
        check("and the producer's own category is overridden, not kept",
              cat == "Done", cat)
        check("nothing is reported as inferred over a mapping somebody stated",
              page.evaluate("() => window.DVD.inferredStatuses()") == [], "not empty")
        check("the chip says the workflow was set here",
              "set here" in page.inner_text("#btn-workflow"),
              page.inner_text("#btn-workflow"))
        # The footer is the half that survives printing, and a PDF in a board
        # pack must not claim to be the file it came from.
        check("and the footer says these figures no longer match the file",
              "no longer match the file" in page.inner_text("#foot"),
              page.inner_text("#foot")[-200:])

        page.click("#btn-workflow")
        page.wait_for_timeout(250)
        page.click("#wf-reset")
        page.wait_for_timeout(800)
        back = page.evaluate("() => window.DVD.orgConfig()")
        check("reset restores the file's own mapping",
              back["statuses"]["done"] == ["Done"]
              and page.evaluate(
                  "() => window.DVD.data.issues.filter(i => i.key === 'ED-1')[0].statusCategory")
              == "In Progress",
              back["statuses"])
        check("and the inferred disclosure comes back with it",
              [r["status"] for r in page.evaluate("() => window.DVD.inferredStatuses()")]
              == ["Accepted", "Peer read"],
              page.evaluate("() => window.DVD.inferredStatuses()"))

        # The checks below were written against `ds` and read the page's live
        # config, and every block since has loaded a dataset of its own. Put it
        # back rather than leaving them measuring whatever ran last.
        page.evaluate("d => window.DVD.applyDataset(d)", ds)
        page.wait_for_timeout(700)

        js_days = page.evaluate(
            "a => window.DVD.workingDays(a[0], a[1], window.DVD.orgConfig())",
            ["2026-08-01", "2026-08-16"])
        py_days = OC.working_days_iso("2026-08-01", "2026-08-16", cfg)
        check("the page's working days match orgconfig.py exactly",
              js_days == py_days, {"js": js_days, "py": py_days})

        NAMES = ["Signed off", "signed OFF", "Shipped", "With QA", "In Review",
                 "Done", "To Do", "Awaiting legal", ""]
        js_cat = page.evaluate(
            "ns => ns.map(n => window.DVD.statusCategoryOf(n, window.DVD.orgConfig()))", NAMES)
        py_cat = [OC.Statuses(cfg).category(n) for n in NAMES]
        check("the page categorises statuses exactly as orgconfig.py does",
              js_cat == py_cat, list(zip(NAMES, js_cat, py_cat)))

        check("the page describes the calendar in the same words the tools use",
              page.evaluate("() => window.DVD.orgSummary(window.DVD.orgConfig())")
              == OC.summary(cfg),
              (page.evaluate("() => window.DVD.orgSummary(window.DVD.orgConfig())"),
               OC.summary(cfg)))

        # A reader comparing the page against a written brief should not have to
        # guess which days were counted.
        check("the calendar is stated on the page, not only in the config file",
              "5-day working week" in page.text_content("#foot"),
              page.text_content("#foot")[-140:])

        # A file with no config keeps the behaviour it had before the feature.
        plain = json.loads((ROOT / "data" / "sample-sprint.json").read_text())
        page.evaluate("d => window.DVD.applyDataset(d)", plain)
        page.wait_for_timeout(500)
        check("a dataset with no config falls back to a plain five-day week",
              page.evaluate("a => window.DVD.workingDays(a[0], a[1])",
                            ["2026-08-03", "2026-08-09"])
              == ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07"],
              page.evaluate("a => window.DVD.workingDays(a[0], a[1])",
                            ["2026-08-03", "2026-08-09"]))

        # ---------- the grid leaves no holes ----------
        # A row of tiles whose spans sum to less than 12 leaves a hole as wide
        # as the columns it skipped and as tall as the row. The bottom band
        # summed to 7 and put roughly 600x360px of empty page beside Team load,
        # and the 761-1180px band orphaned four tiles on half-empty rows. The
        # arithmetic is easy to get wrong by hand and invisible until someone
        # looks at the page on the right size of screen, so it is asserted.
        row_spans = """() => {
          const g = document.getElementById('grid'), rows = {};
          [...g.children].filter(c => !c.classList.contains('hidden')).forEach(c => {
            const top = Math.round(c.offsetTop);
          // The span lands on grid-column-start in the computed style;
          // grid-column-end reads 'auto' and silently scores every tile 12.
            const cs = getComputedStyle(c);
            const raw = /span/.test(cs.gridColumnStart) ? cs.gridColumnStart : cs.gridColumnEnd;
            const m = String(raw).match(/\\d+/);
            rows[top] = (rows[top] || 0) + (m ? +m[0] : 12);
          });
          return Object.keys(rows).sort((a, b) => a - b).map(k => rows[k]);
        }"""
        for width in (1500, 1100, 700):
            page.set_viewport_size({"width": width, "height": 1000})
            page.wait_for_timeout(300)
            spans = page.evaluate(row_spans)
            short = [i for i, n in enumerate(spans) if n != 12]
            check("every tile row fills all 12 columns at %dpx" % width, not short,
                  "rows %s are %s" % (short, [spans[i] for i in short]) if short else "")
        # ---------- a phone does not open on blank paper ----------
        # The card header's title block yields to the tools with a 220px flex
        # basis. Below 760px the header stacks, so a basis written as a width
        # became a height: every header on a 375px screen was 220px tall over
        # 40-90px of content, about 1,900px of nothing in a 10,700px page, and
        # the first figure was more than a screen down. Measured as the gap
        # between the box and the bottom of its last child, so the check is
        # about the content and not about a number that moves with the copy.
        page.set_viewport_size({"width": 375, "height": 812})
        page.wait_for_timeout(300)
        slack = page.evaluate("""() => [...document.querySelectorAll('.card > .card-hd > div:first-child')]
          .filter(e => e.offsetParent !== null && e.children.length)
          .map(e => {
            const box = e.getBoundingClientRect();
            const last = Math.max(...[...e.children].map(k => k.getBoundingClientRect().bottom));
            return Math.round(box.height - (last - box.top));
          })""")
        check("no card header on a phone is taller than what it says",
              bool(slack) and max(slack) <= 12,
              "largest gap %spx under a heading, over %d headers" % (max(slack) if slack else None, len(slack)))

        # ---------- small things the fourth critique read (1.79.30) ----------
        page.set_viewport_size({"width": 1500, "height": 1000})
        page.wait_for_timeout(300)
        levels = page.eval_on_selector_all("h1,h2,h3,h4,h5,h6", "n => n.map(e => +e.tagName[1])")
        check("heading levels never skip in document order, popovers included",
              levels and levels[0] == 1 and all(b <= a + 1 for a, b in zip(levels, levels[1:])), levels[:8])
        check("the Types filter label is set like its neighbours",
              page.eval_on_selector("#f-types-lab", "e => getComputedStyle(e).textTransform") == "uppercase")
        pl = page.eval_on_selector_all("#pred-chart text.axis-lab", "n => n.map(e => e.textContent)")
        check("the predictability axis names sprints the way the context bar does",
              any(t.startswith("Sprint ") for t in pl) and not any(re.fullmatch(r"S\d+", t) for t in pl), pl[:6])
        page.set_viewport_size({"width": 1280, "height": 800})
        page.wait_for_timeout(300)
        tb = page.eval_on_selector(".topbar", "e => Math.round(e.getBoundingClientRect().height)")
        check("at 1280 wide the toolbar is one row too", tb < 110, "%spx" % tb)
        # A preset that shows one tile of a shared row without the other still
        # sums every row to twelve — the Executive preset stranded DORA.
        sums = """() => { const rows = {};
          [...document.querySelectorAll('#grid > *')].filter(c => !c.classList.contains('hidden')).forEach(c => {
            const t = Math.round(c.offsetTop), m = /span (\\d+)/.exec(getComputedStyle(c).gridColumnStart || '');
            rows[t] = (rows[t] || 0) + (m ? +m[1] : 12); });
          return Object.values(rows); }"""
        page.set_viewport_size({"width": 1500, "height": 1000})
        for v in ("exec", "team"):
            page.goto(DIST.as_uri() + "?view=" + v); page.wait_for_timeout(700)
            rs = page.evaluate(sums)
            check("the %s preset leaves no short row" % v, rs and all(r == 12 for r in rs), rs)
        page.goto(DIST.as_uri()); page.wait_for_timeout(700)
        page.set_viewport_size({"width": 375, "height": 812})
        page.wait_for_timeout(300)

        # ---------- the first figure is on a phone's first screen (1.79.29) ----------
        page.evaluate("() => window.scrollTo(0, 0)")
        first = page.eval_on_selector("#kpis .kpi", "e => Math.round(e.getBoundingClientRect().top)")
        check("on a phone the first KPI tile starts inside the first screen, with room to read it",
              first < 560, "first tile at %spx of an 812px viewport" % first)
        check("the filter row is folded behind one line on a phone",
              page.is_visible("#f-toggle") and not page.is_visible("#f-assignee") and
              page.get_attribute("#f-toggle", "aria-expanded") == "false")
        check("which says no filter is active", (page.text_content("#f-toggle") or "").strip() == "Filters · none active",
              page.text_content("#f-toggle"))
        page.click("#f-toggle"); page.wait_for_timeout(150)
        check("opening it shows the filters", page.is_visible("#f-assignee") and
              page.get_attribute("#f-toggle", "aria-expanded") == "true")
        page.evaluate("() => window.DVD.debug.setFilter('q', 'checkout')"); page.wait_for_timeout(300)
        check("and the line counts what is active",
              (page.text_content("#f-toggle") or "").strip() == "Filters · 1 active", page.text_content("#f-toggle"))
        page.evaluate("() => window.DVD.debug.setFilter('q', '')"); page.wait_for_timeout(300)
        page.click("#f-toggle"); page.wait_for_timeout(150)
        check("the Tiles button drops its detail on a phone, and keeps it in its title",
              not page.is_visible("#btn-view .btn-detail") and "hidden" in (page.get_attribute("#btn-view", "title") or ""))
        labs = page.eval_on_selector_all("#burn-chart text.axis-lab[text-anchor=middle]",
                                         "n => n.map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right)]; })")
        labs.sort()
        check("the burndown's date labels do not collide on a phone",
              len(labs) >= 3 and all(labs[i + 1][0] >= labs[i][1] - 1 for i in range(len(labs) - 1)), labs)
        # With a context bar as well: three pickers, no repeated dates or source.
        bundle = json.loads((ROOT / "data" / "sample-bundle.json").read_text())
        page.evaluate("d => window.DVD.applyDataset(d)", bundle)
        page.wait_for_timeout(700)
        page.evaluate("() => window.scrollTo(0, 0)")
        first = page.eval_on_selector("#kpis .kpi", "e => Math.round(e.getBoundingClientRect().top)")
        check("with the context bar showing, the first tile is still inside the first screen",
              page.is_visible("#ctxbar") and first < 700, "first tile at %spx" % first)
        check("the context bar keeps its three pickers on a phone",
              page.is_visible("#c-proj") and page.is_visible("#c-board") and page.is_visible("#c-sprint"))
        check("and drops the dates the title block already states", not page.is_visible("#ctxbar .ctx-meta"))
        page.click("#btn-import"); page.click("#m-sample"); page.wait_for_timeout(500)
        page.set_viewport_size({"width": 1500, "height": 1000})
        page.wait_for_timeout(300)
        check("above 760px the filter row is the row: no fold, detail on the Tiles button",
              not page.is_visible("#f-toggle") and page.is_visible("#f-assignee") and
              page.is_visible("#btn-view .btn-detail"))

        check("no console errors", not console, console[:3])
        page.screenshot(path=str(ROOT / "tests" / "last-run.png"), full_page=True)

        empty_selection(b)
        health_composition(b)
        exec_findings(b)
        wizard_notices(b)
        transports(b)
        strict_style_csp(b)

        b.close()

    print()
    if warnings:
        print("%d warning(s): %s" % (len(warnings), ", ".join(warnings)))
    if failures:
        print("%d check(s) failed: %s" % (len(failures), ", ".join(failures)))
        sys.exit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
