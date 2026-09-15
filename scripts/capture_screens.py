#!/usr/bin/env python3
"""
capture_screens.py — every screenshot of the product, from one pass.

The README's pictures and the demo film's frames used to come from two places:
`tests/shots.py` drove the import wizard over `file://`, and the film was a
screen recording of a different session. The two drifted — the README showed a
layout with the verdict above the headline band a fortnight after ADR 0032
moved it below — and nothing failed. Now one pass over the built file, served
by the live-mode server on the demo bundle, writes every picture: the ones the
README links (`--out docs/screenshots`) and the ones the film is cut from
(`record_demo.py` imports `capture()` and calls it into a scratch directory).
A picture the README shows and a picture the film shows are the same picture,
taken at the same moment, of the same build.

    python3 scripts/capture_screens.py                 # refresh docs/screenshots/
    python3 scripts/capture_screens.py --out /tmp/x    # everything, somewhere else

The forecast tile is answered by agent/tools/forecast.py over the live
connection, so this runs against `serve_live.py` rather than the file. The
server is started here and stopped on exit.
"""

import argparse
import contextlib
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "delivery-value-dashboard.html"
BUNDLE = ROOT / "data" / "demo-bundle.json"
FIXTURE = ROOT / "tests" / "fixtures" / "jira-export.csv"
W, H = 1600, 1000

# What the README links, by name. Everything else `capture()` writes is for the
# film and stays out of the repository — fourteen two-megapixel PNGs would
# double the size of every clone for pictures nobody opens by hand.
README_SHOTS = ("dashboard", "context-picker", "forecast", "import-mapping", "import-preview")

SETTLED = ("() => { const e = document.getElementById('forecast-body');"
           "  return e && !/Running 20,000|Simulating every/.test(e.textContent); }")


@contextlib.contextmanager
def live_server(port=8899, bundle=BUNDLE):
    """`serve_live.py` on the demo bundle, ready before the body runs."""
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "serve_live.py"),
         "--bundle", str(bundle), "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/api/contexts" % port, timeout=1).read()
                break
            except Exception:
                time.sleep(0.25)
        else:
            raise SystemExit("live-mode server did not start; the forecast tile needs it")
        yield "http://127.0.0.1:%d/dist/%s" % (port, DIST.name)
    finally:
        proc.terminate()


def _scroll_to(page, sel, top=28):
    """Put the element's top `top` pixels below the viewport's, so a card is
    framed with its heading rather than cut through its middle."""
    page.evaluate("([s, t]) => { const r = document.querySelector(s).getBoundingClientRect();"
                  "  window.scrollTo({top: window.scrollY + r.top - t, behavior: 'auto'}); }",
                  [sel, top])
    page.wait_for_timeout(250)


def _select(page, sel, want):
    opts = page.eval_on_selector_all(sel + " option", "n => n.map(e => e.textContent)")
    match = next((o for o in opts if want in o), None)
    if match is None:
        raise SystemExit("no option containing %r in %s: %s" % (want, sel, opts))
    page.select_option(sel, label=match)
    page.wait_for_timeout(600)


def _settle(page, timeout=30000):
    try:
        page.wait_for_function(SETTLED, timeout=timeout)
    except Exception:
        pass
    page.wait_for_timeout(300)


def capture(page, out_dir, only=None):
    """Write every picture into `out_dir`; return {name: path}.

    `page` is already on the built file with the demo bundle applied. The order
    matters: the wizard at the end replaces the loaded dataset, so it runs
    after every picture of the demo company.
    """
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    got, rects = {}, {}

    def shot(name, *marks, **kw):
        """Take the picture, and note where each of `marks` sits in it as a
        fraction of the frame, so the film can ring an element rather than a
        guessed rectangle. Written to rects.json beside the pictures."""
        if only and name not in only:
            return
        p = out_dir / (name + ".png")
        page.screenshot(path=str(p), **kw)
        got[name] = p
        rects[name] = {}
        for sel in marks:
            r = page.evaluate(
                "s => { const e = document.querySelector(s); if (!e) return null;"
                "  const r = e.getBoundingClientRect();"
                "  return [r.left / innerWidth, r.top / innerHeight,"
                "          r.width / innerWidth, r.height / innerHeight]; }", sel)
            if r:
                rects[name][sel] = r

    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(200)
    shot("dashboard", "#kpis", "#c-exec", "#ctxbar", "#kpis .kpi[data-kpi='0']",
         "#kpis .kpi[data-kpi='1']", "#kpis .kpi[data-kpi='2']", "#kpis .kpi[data-kpi='4']")

    # The toolbar and the context bar together, as the README shows them.
    bottom = page.evaluate("() => document.getElementById('ctxbar').getBoundingClientRect().bottom")
    shot("context-picker", clip={"x": 0, "y": 0, "width": W, "height": int(bottom) + 14})

    _scroll_to(page, "#c-burn")
    shot("burndown", "#c-burn")

    # A KPI's drill-down: the third tile is Blocked.
    page.evaluate("() => window.scrollTo(0, 0)")
    page.click("#kpis .kpi[data-kpi='2']")
    page.wait_for_timeout(600)
    shot("drilldown", "#panel")
    page.click("#p-done")
    # The click left the pointer over the tile, and a tile's tooltip follows
    # the pointer; it was in every picture after this one until the pointer
    # was moved off it.
    page.dispatch_event("#kpis .kpi[data-kpi='2']", "mouseleave")
    page.mouse.move(4, 600)
    page.wait_for_timeout(300)

    _scroll_to(page, "#c-flow")
    shot("flow", "#c-flow")

    _scroll_to(page, "#c-risk")
    shot("risks", "#c-risk")

    # The forecast tile, all three questions. Each is a run of the same tool the
    # agent uses, over the live connection, so each is waited for rather than
    # filmed mid-run.
    page.click('[data-fc="when"]')
    _settle(page)
    _scroll_to(page, "#c-pred")
    shot("forecast", "#c-pred", "#c-forecast")
    page.fill("#fc-items", "30")
    page.dispatch_event("#fc-items", "change")
    _settle(page)
    _scroll_to(page, "#c-pred")
    shot("forecast-30", "#c-forecast", "#fc-items")
    page.click('[data-fc="howmany"]')
    _settle(page)
    _scroll_to(page, "#c-pred")
    shot("forecast-howmany", "#c-forecast")
    page.click('[data-fc="sequence"]')
    _settle(page, timeout=60000)
    _scroll_to(page, "#c-forecast")
    shot("forecast-sequence", "#c-forecast")
    page.click('[data-fc="when"]')
    _settle(page)

    # The executive view: open the picker, choose, close, then look.
    page.evaluate("() => window.scrollTo(0, 0)")
    page.click("#btn-view")
    page.wait_for_timeout(300)
    shot("tiles-picker")
    page.click('[data-preset="exec"]')
    page.wait_for_timeout(300)
    page.click("#btn-view")
    page.wait_for_timeout(400)
    shot("exec-view", "#btn-view", "#kpis")
    page.click("#btn-view")
    page.click('[data-preset="all"]')
    page.click("#btn-view")
    page.wait_for_timeout(300)

    # The other boards in the same file.
    _select(page, "#c-board", "Platform & Infra")
    page.evaluate("() => window.scrollTo(0, 0)")
    shot("platform", "#kpis")
    _select(page, "#c-proj", "Highpeak Mobile")
    page.evaluate("() => window.scrollTo(0, 0)")
    shot("mobile-items", "#kpis", "#kpis .kpi[data-kpi='0']", "[data-unit=points]")
    page.click("[data-unit=points]")
    page.wait_for_timeout(400)
    shot("mobile-points", "#kpis", "#kpis .kpi[data-kpi='0']", "[data-unit=points]")
    page.click("[data-unit=items]")
    _select(page, "#c-proj", "Highpeak Commerce")
    _select(page, "#c-board", "Storefront Delivery")
    _select(page, "#c-sprint", "All 6 sprints")
    _scroll_to(page, "#c-flow")
    shot("rollup", "#c-flow")
    _select(page, "#c-sprint", "Sprint 24")

    page.evaluate("() => window.scrollTo(0, 0)")
    page.click("#btn-theme")
    page.wait_for_timeout(400)
    shot("dark", "#kpis")
    page.click("#btn-theme")
    page.wait_for_timeout(300)

    # Last: the wizard, on a raw Jira export. Applying it would replace the
    # demo company, which is why nothing is captured after this. The wizard is
    # a dialog over the page, so these are the viewport and not the full page
    # — a full-page capture is the dialog over three metres of dashboard.
    page.click("#btn-import")
    page.wait_for_timeout(300)
    shot("import-choose")
    page.set_input_files("#file", str(FIXTURE))
    page.wait_for_selector("#step-map:not(.hidden)")
    page.wait_for_timeout(400)
    shot("import-mapping", "#modal .mbox")
    page.click("#m-preview")
    page.wait_for_selector("#step-preview:not(.hidden)")
    page.wait_for_timeout(400)
    shot("import-preview", "#modal .mbox")
    if not only:
        # The film's, not the README's: docs/screenshots/ holds pictures only.
        (out_dir / "rects.json").write_text(json.dumps(rects, indent=1))
    return got


def open_page(browser, url, scale=2):
    """A page on the built file with the demo bundle loaded, at 2× so a frame
    the film zooms into is still sharp."""
    ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=scale)
    page = ctx.new_page()
    page.goto(url)
    page.wait_for_timeout(700)
    page.evaluate("d => window.DVD.applyDataset(d)", json.loads(BUNDLE.read_text()))
    page.wait_for_timeout(800)
    return page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "screenshots"),
                    help="where to write; the default writes only what the README links")
    ap.add_argument("--port", type=int, default=8899)
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    out = pathlib.Path(a.out)
    only = README_SHOTS if out.resolve() == (ROOT / "docs" / "screenshots").resolve() else None
    with live_server(a.port) as url, sync_playwright() as pw:
        b = pw.chromium.launch()
        page = open_page(b, url)
        got = capture(page, out, only=only)
        b.close()
    for name, p in got.items():
        print("  %-18s %5.0f KB" % (p.name, p.stat().st_size / 1024))


if __name__ == "__main__":
    main()
