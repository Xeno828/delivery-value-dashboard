#!/usr/bin/env python3
"""
perf.py — measure where the dashboard's time actually goes.

Written to answer a specific question: does trimming the sprint dropdown to the
selected project help performance? Measuring beats arguing, and the answer is
in the numbers below rather than in anyone's intuition.

Each measurement runs in a real browser against real bundle sizes.

    python3 tests/perf.py                    # default bundles
    python3 tests/perf.py /tmp/bundle-22.json
"""

import json
import pathlib
import statistics
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "delivery-value-dashboard.html"

# The instrumentation runs inside the page so it measures what a user waits for,
# not what the automation harness waits for.
PROBE = """
(bundle) => {
  const t = {};
  const time = (k, fn) => {
    const a = performance.now();
    const r = fn();
    t[k] = +(performance.now() - a).toFixed(1);
    return r;
  };
  const med = (k, fn, n) => {
    const runs = [];
    for (let i = 0; i < n; i++) { const a = performance.now(); fn(i); runs.push(performance.now() - a); }
    runs.sort((x, y) => x - y);
    t[k] = +runs[Math.floor(runs.length / 2)].toFixed(1);
  };

  // 1. parse + normalise + first paint, as a fresh load would
  time("load_and_render", () => window.DVD.applyDataset(JSON.parse(JSON.stringify(bundle))));

  const D = window.DVD;
  const ctxs = D.debug.contexts().filter(c => !c.isRollup);

  // 2. switching sprint — the thing the context picker actually triggers
  med("switch_sprint", i => D.debug.selectContext(ctxs[i % ctxs.length].id), 12);

  // 3. a filter keystroke — the most frequent interaction there is
  med("filter_keystroke", i => D.debug.setFilter("q", i % 2 ? "check" : "pay"), 10);
  D.debug.setFilter("q", "");

  // 4. flipping the unit toggle — a full redraw of every chart
  med("unit_toggle", i => D.debug.setUnit(i % 2 ? "points" : "items"), 8);

  // 5. how long the sprint <select> itself takes to build, isolated
  med("build_sprint_options", () => {
    const all = D.debug.contexts();
    const cur = D.debug.view().ctx;
    const pl = c => c.projectName || c.projectKey || "";
    const bl = c => c.boardName || c.team || "";
    const list = all.filter(c => pl(c) === pl(cur) && bl(c) === bl(cur));
    const html = list.map(c => '<option value="' + c.id + '">' + c.sprintName + "</option>").join("");
    return html.length;
  }, 50);

  // 6. the same, unfiltered — what "show every sprint" would cost
  med("build_all_options", () => {
    const html = D.debug.contexts()
      .map(c => '<option value="' + c.id + '">' + c.sprintName + "</option>").join("");
    return html.length;
  }, 50);

  // 7. the heaviest realistic view: a rollup across every sprint on a board
  const roll = D.debug.contexts().find(c => c.isRollup);
  if (roll) {
    time("switch_to_rollup", () => D.debug.selectContext(roll.id));
    t.rollup_issues = D.debug.view().issues.length;
    med("filter_on_rollup", i => D.debug.setFilter("q", i % 2 ? "check" : "pay"), 8);
    D.debug.setFilter("q", "");
    med("unit_toggle_on_rollup", i => D.debug.setUnit(i % 2 ? "points" : "items"), 6);
    D.debug.setUnit("items");
    D.debug.selectContext(ctxs[0].id);
  }

  t.issues = D.data.issues.length;
  t.contexts = D.debug.contexts().length;
  t.in_view = D.debug.view().issues.length;
  return t;
}
"""


def run(page, path):
    bundle = json.loads(pathlib.Path(path).read_text())
    page.goto(DIST.as_uri())
    page.wait_for_timeout(500)
    return page.evaluate(PROBE, bundle)


def main():
    targets = sys.argv[1:] or [
        str(ROOT / "data" / "sample-sprint.json"),
        str(ROOT / "data" / "sample-bundle.json"),
        "/tmp/bundle-7.json",
        "/tmp/bundle-22.json",
    ]
    targets = [t for t in targets if pathlib.Path(t).exists()]

    rows = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page(viewport={"width": 1500, "height": 1000})
        page.on("pageerror", lambda e: print("  PAGEERROR", e))
        for t in targets:
            r = run(page, t)
            r["file"] = pathlib.Path(t).name
            r["kb"] = round(pathlib.Path(t).stat().st_size / 1024)
            rows.append(r)
        b.close()

    cols = [("file", 22), ("kb", 7), ("issues", 8), ("contexts", 9), ("in_view", 8),
            ("load_and_render", 16), ("switch_sprint", 14), ("filter_keystroke", 17),
            ("unit_toggle", 13), ("build_sprint_options", 21), ("build_all_options", 18),
            ("rollup_issues", 14), ("switch_to_rollup", 17), ("filter_on_rollup", 17),
            ("unit_toggle_on_rollup", 22)]
    print("\nAll timings in milliseconds, median of repeated runs.\n")
    print("".join(c.ljust(w) for c, w in cols))
    print("-" * sum(w for _, w in cols))
    for r in rows:
        print("".join(str(r.get(c, "")).ljust(w) for c, w in cols))

    big = rows[-1]
    print("\nAt the largest size (%d issues, %d contexts):" % (big["issues"], big["contexts"]))
    print("  building the scoped sprint dropdown : %.1f ms" % big["build_sprint_options"])
    print("  building an UNSCOPED dropdown       : %.1f ms" % big["build_all_options"])
    print("  a single filter keystroke           : %.1f ms" % big["filter_keystroke"])
    print("  switching sprint                    : %.1f ms" % big["switch_sprint"])
    print("  first load                          : %.1f ms" % big["load_and_render"])
    saving = big["build_all_options"] - big["build_sprint_options"]
    print("\n  Scoping the dropdown saves %.1f ms — %.2f%% of one filter keystroke."
          % (saving, 100.0 * saving / big["filter_keystroke"]))


if __name__ == "__main__":
    main()
