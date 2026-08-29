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
    page.evaluate("() => window.DVD.debug.setFilter('q', '')")
    page.wait_for_timeout(400)

    check("no console errors in the empty state", not errs, errs[:2])
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

        # ---------- loopback ----------
        page = b.new_page(viewport={"width": 1500, "height": 1000})
        page.goto(url)
        page.wait_for_timeout(400)
        check("over http the page finds the loopback transport",
              page.evaluate("() => window.DVD.debug.transport()") == "loopback",
              page.evaluate("() => window.DVD.debug.transport()"))
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
            check("an empty file drops its placeholder once the connection answers",
                  "single" not in ids, ids[:3])
            check("and opens on one of the connection's own sprints",
                  page.evaluate("() => window.DVD.debug.view().ctx.id") in
                  [c["id"] for c in contexts_body["contexts"]],
                  page.evaluate("() => window.DVD.debug.view().ctx.id"))
            check("with that sprint's issues actually loaded",
                  page.evaluate("() => window.DVD.data.issues.length") > 0,
                  page.evaluate("() => window.DVD.data.issues.length"))
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
        burn_items = page.eval_on_selector_all("#burn-chart polyline", "n => n.length")
        page.click("[data-unit=points]"); page.wait_for_timeout(500)
        pts_tile = page.text_content("#kpis .kpi:nth-child(1)")
        check("switching to points changes the delivered tile", pts_tile != items_tile)
        check("points tile reads in story points", "83 story points" in pts_tile, pts_tile[:60])
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
        check("burndown rebuilt, not inherited",
              page.eval_on_selector_all("#burn-chart polyline", "n => n.length") >= 3)
        check("charts have data", page.eval_on_selector_all("#dist-chart rect[data-drill]", "n => n.length") > 0)

        # ---------- merge a value-only file ----------
        before = page.text_content("#kpis")
        wizard(page, "value-estimates.csv", mode="merge")
        after = page.text_content("#kpis")
        check("merge changed the value tile", before != after)
        check("merge kept all 22 issues", "22 issues" in page.text_content("#foot"),
              page.text_content("#foot")[:70])

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

        page.click('[data-preset="exec"]')
        page.wait_for_timeout(200)
        ex = vis()
        check("the executive view is the agent's exec-brief shape",
              ex == ["c-exec", "c-kpis", "c-pred", "c-forecast", "c-dora",
                     "c-value", "c-rel", "c-risk"], ex)
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
              tm == ["c-exec", "c-kpis", "c-burn", "c-dist", "c-flow", "c-age",
                     "c-pred", "c-forecast", "c-load", "c-risk"], tm)
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
        check("the tiles sit in the DOM in that order", dom_order() == TIDS, dom_order()[:3])

        open_picker(page)
        check("the first tile cannot move up and the last cannot move down",
              page.eval_on_selector('[data-move=up][data-move-id="%s"]' % TIDS[0], "e => e.disabled") and
              page.eval_on_selector('[data-move=down][data-move-id="%s"]' % TIDS[-1], "e => e.disabled"))

        kpi_pre_order = page.text_content("#kpis")
        page.click('[data-move=up][data-move-id="c-risk"]')
        page.click('[data-move=up][data-move-id="c-risk"]')
        page.wait_for_timeout(300)
        moved = order()
        check("a tile moves up two places", moved.index("c-risk") == TIDS.index("c-risk") - 2,
              moved[-4:])
        check("the DOM order follows the visual order", dom_order() == moved, dom_order()[-4:])
        # Same guarantee the tile picker makes: the view changes, the numbers
        # behind it do not.
        check("reordering does not change what is computed",
              page.text_content("#kpis") == kpi_pre_order)
        check("a custom order is named in the picker, not left to be noticed",
              "Custom order" in page.text_content("#vp-count"), page.text_content("#vp-count")[-40:])
        check("the order travels in the URL", "order=c-exec" in page.url, page.url[-70:])

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
        fb = " ".join((page.text_content("#forecast-body") or "").split())
        check("the forecast tile explains itself with no live connection",
              "needs the live-mode connection" in fb, fb[:90])
        check("the offline forecast tile shows no percentile figures",
              "% of simulations" not in fb and "Confidence" not in fb, fb[:90])
        check("the offline tile names how to get one", "make serve-live" in fb, fb[-80:])

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
        page.set_viewport_size({"width": 1500, "height": 1000})
        page.wait_for_timeout(300)

        check("no console errors", not console, console[:3])
        page.screenshot(path=str(ROOT / "tests" / "last-run.png"), full_page=True)

        empty_selection(b)
        health_composition(b)
        transports(b)

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
