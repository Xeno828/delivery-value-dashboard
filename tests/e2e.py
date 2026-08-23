#!/usr/bin/env python3
"""
End-to-end smoke test. Renders dist/ in a real browser and walks the upload
wizard with the fixture files, asserting the dashboard actually changes.

    pip install playwright && playwright install chromium
    python3 tests/e2e.py
"""

import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "delivery-value-dashboard.html"
FIX = ROOT / "tests" / "fixtures"

failures = []
console = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  — " + str(detail)) if detail else ""))
    if not ok:
        failures.append(name)


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

        check("every tile is shown until someone says otherwise", vis() == TIDS, len(vis()))

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
              "5 hidden" in note and "Team load" in note, note[:70])

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
        check("an unrecognised tile list shows everything rather than a blank page",
              vis() == TIDS, len(vis()))

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
        b.close()

    print()
    if failures:
        print("%d check(s) failed: %s" % (len(failures), ", ".join(failures)))
        sys.exit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
