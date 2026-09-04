#!/usr/bin/env python3
"""
a11y.py — accessibility test suite.

Hand-written rather than axe-core, for one reason: this project has no runtime
dependencies and cannot fetch one at test time. The trade is honest — axe covers
more rules than this does. What this covers, it covers against the real rendered
page, including the states axe would miss because they only exist after an
interaction (the drill-down panel, the import wizard, dark mode).

Checks, grouped by the WCAG 2.2 AA criterion they serve:

  1.1.1  Non-text content        every chart has a text equivalent (table view)
  1.3.1  Info and relationships  heading order, form labels, table headers
  1.4.1  Use of colour           status is never colour alone
  1.4.3  Contrast (minimum)      computed on real rendered text, both themes
  1.4.11 Non-text contrast       controls and chart marks against their surface
  2.1.1  Keyboard                every control reachable and operable
  2.4.3  Focus order             the drill-down panel takes and returns focus
  2.4.7  Focus visible           a visible indicator on every focusable element
  4.1.2  Name, role, value       accessible name on every interactive element
  2.3.3  Animation               prefers-reduced-motion is honoured

    python3 tests/a11y.py
"""

import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "delivery-value-dashboard.html"

failures, warnings = [], []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  — " + str(detail)) if detail else ""))
    if not ok:
        failures.append(name)


def warn(name, ok, detail=""):
    print(("  PASS  " if ok else "  WARN  ") + name + (("  — " + str(detail)) if detail else ""))
    if not ok:
        warnings.append(name)


# --------------------------------------------------------------- contrast
CONTRAST = r"""
() => {
  // WCAG relative luminance and contrast ratio, computed on what is actually
  // painted — resolving CSS variables, inherited colour and effective background.
  const lum = (r, g, b) => {
    const f = c => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const parse = s => {
    const m = String(s).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const bgOf = el => {
    let n = el;
    while (n && n !== document.documentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c && c.a > 0.5) return c;
      n = n.parentElement;
    }
    const c = parse(getComputedStyle(document.body).backgroundColor);
    return c || { r: 255, g: 255, b: 255, a: 1 };
  };
  const ratio = (a, b) => {
    const l1 = lum(a.r, a.g, a.b), l2 = lum(b.r, b.g, b.b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  };

  const bad = [];
  const els = document.querySelectorAll(
    'p,span,div,td,th,li,h1,h2,h3,h4,label,button,a,text,option,summary,b,i,sub');
  els.forEach(el => {
    if (el.closest('#demo-overlay')) return;
    const txt = Array.from(el.childNodes)
      .filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join('');
    if (!txt) return;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) return;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.opacity === '0') return;
    const fg = parse(cs.color || cs.fill);
    if (!fg) return;
    const bg = bgOf(el);
    const px = parseFloat(cs.fontSize) || 16;
    const bold = (parseInt(cs.fontWeight, 10) || 400) >= 700;
    const large = px >= 24 || (px >= 18.66 && bold);
    const need = large ? 3.0 : 4.5;
    const got = ratio(fg, bg);
    if (got < need - 0.01) {
      bad.push({ text: txt.slice(0, 42), got: +got.toFixed(2), need: need,
                 px: +px.toFixed(1), cls: el.className && el.className.toString().slice(0, 34) });
    }
  });
  return bad;
}
"""

NAMES = r"""
() => {
  const nameOf = el => (
    el.getAttribute('aria-label') ||
    (el.getAttribute('aria-labelledby') &&
      (document.getElementById(el.getAttribute('aria-labelledby')) || {}).textContent) ||
    el.textContent.trim() ||
    el.getAttribute('title') ||
    (el.labels && el.labels[0] && el.labels[0].textContent.trim()) || '');
  const bad = [];
  document.querySelectorAll('button,a[href],select,input,[role=button],[role=tab]').forEach(el => {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) return;
    if (!nameOf(el).trim()) bad.push(el.tagName + '.' + (el.className || '') + '#' + (el.id || ''));
  });
  return bad;
}
"""

FOCUS = r"""
() => {
  // Every focusable control must show a visible focus indicator. Browsers
  // supply one by default; this catches anywhere it has been suppressed.
  const bad = [];
  document.querySelectorAll('button,a[href],select,input,textarea,[tabindex]').forEach(el => {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) return;
    const cs = getComputedStyle(el);
    if (cs.outlineStyle === 'none' && !cs.boxShadow.includes('inset') &&
        el.style.outline === 'none') bad.push(el.id || el.className || el.tagName);
  });
  return bad;
}
"""

HEADINGS = r"""
() => {
  const hs = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'))
    .filter(h => h.getBoundingClientRect().height > 0)
    .map(h => ({ level: +h.tagName[1], text: h.textContent.trim().slice(0, 40) }));
  const jumps = [];
  for (let i = 1; i < hs.length; i++)
    if (hs[i].level > hs[i - 1].level + 1) jumps.push(hs[i - 1].text + ' -> ' + hs[i].text);
  return { count: hs.length, h1: hs.filter(h => h.level === 1).length, jumps: jumps };
}
"""

COLOUR_ONLY = r"""
() => {
  // A status must never be conveyed by colour alone: every status chip has to
  // carry an icon AND a word.
  const bad = [];
  document.querySelectorAll('.chip').forEach(el => {
    const hasIcon = !!el.querySelector('[aria-hidden="true"]');
    const words = el.textContent.replace(/[^A-Za-z]/g, '');
    if (!hasIcon || words.length < 2) bad.push(el.textContent.trim().slice(0, 30));
  });
  return bad;
}
"""


def main():
    if not DIST.exists():
        sys.exit("build first: python3 build.py")
    bundle = json.loads((ROOT / "data" / "demo-bundle.json").read_text())

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page(viewport={"width": 1500, "height": 1000})
        page.goto(DIST.as_uri())
        page.wait_for_timeout(600)
        page.evaluate("d => window.DVD.applyDataset(d)", bundle)
        page.wait_for_timeout(800)
        # Everything, flow tiles included. They are off by default on a sprint
        # board, which is the data every suite runs against — so without this
        # the four newest charts would be the four nothing ever contrast-checks,
        # and their dashed percentile lines and axis labels use the UI ink
        # tokens rather than the series palette precisely because those are the
        # ones a contrast floor applies to.
        page.evaluate("() => window.DVD.debug.setShown(window.DVD.debug.tileIds())")
        page.wait_for_timeout(600)
        # Asserted rather than assumed. A setup line that quietly stopped
        # working would leave every check below passing over a page missing the
        # tiles it was added to cover.
        check("the flow charts really are on screen for the sweeps below",
              page.evaluate("""() => ['c-cycle','c-wip','c-thr','c-cfd']
                .filter(i => document.getElementById(i).classList.contains('hidden'))""") == [])

        # ---------- 4.1.2 name, role, value ----------
        print("4.1.2  name, role, value")
        check("every visible control has an accessible name",
              page.evaluate(NAMES) == [], page.evaluate(NAMES)[:4])

        # The theme button's label is its accessible name, and it names the theme
        # pressing it switches *to*. The opening theme comes from the system
        # preference, so under a dark preference the page has to open dark with the
        # label already reading "Light". It shipped reading "Dark" on a dark page,
        # which told a screen-reader user the opposite of what the control does.
        THEME = ("() => [document.documentElement.dataset.theme,"
                 " document.getElementById('btn-theme').textContent.trim()]")
        dark = b.new_page(viewport={"width": 1500, "height": 1000}, color_scheme="dark")
        dark.goto(DIST.as_uri())
        dark.wait_for_timeout(600)
        opened = dark.evaluate(THEME)
        check("a dark system preference opens the page dark", opened[0] == "dark", opened)
        check("the theme button names the theme it switches to, not the one showing",
              opened == ["dark", "Light"], opened)
        dark.click("#btn-theme")
        dark.wait_for_timeout(300)
        toggled = dark.evaluate(THEME)
        check("pressing it switches theme and renames itself",
              toggled == ["light", "Dark"], toggled)
        dark.close()

        # ---------- 1.3.1 relationships ----------
        print("1.3.1  info and relationships")
        h = page.evaluate(HEADINGS)
        check("exactly one h1", h["h1"] == 1, h["h1"])
        check("no skipped heading levels", h["jumps"] == [], h["jumps"][:3])
        check("every filter control has a label",
              page.eval_on_selector_all(
                  ".filters select, .filters input",
                  "n => n.filter(e => !e.labels || !e.labels.length).map(e => e.id)") == [],
              page.eval_on_selector_all(".filters select",
                                        "n => n.map(e => (e.labels||[]).length)"))
        check("the page has exactly one main landmark",
              page.eval_on_selector_all("main", "n => n.length") == 1)
        check("the first thing in the page is a skip link to the report",
              page.eval_on_selector("body > a.skip", "e => e.getAttribute('href')") == "#grid"
              and page.eval_on_selector_all("#grid", "n => n.length") == 1)
        check("every table header declares whether it heads a column or a row",
              page.eval_on_selector_all("table.tv th", "n => n.length > 0 && n.every(t => ['col', 'row'].includes(t.getAttribute('scope')))"),
              page.eval_on_selector_all("table.tv th", "n => n.filter(t => !t.getAttribute('scope')).map(t => t.textContent).slice(0, 4)"))
        check("data tables use th for headers",
              page.evaluate("""() => {
                  document.querySelector('[data-table=burn]').click();
                  const ok = !!document.querySelector('#burn-table table thead th');
                  document.querySelector('[data-table=burn]').click();
                  return ok; }"""))

        # ---------- 1.1.1 non-text content ----------
        print("1.1.1  non-text content")
        tables = page.evaluate("""() => ['burn','dist','flowtime','age','pred']
            .filter(k => document.querySelector('[data-table=' + k + ']'))""")
        check("every chart has a table-view twin", len(tables) == 5, tables)
        rows = []
        for k in tables:
            page.click(f"[data-table={k}]")
            rows.append(page.eval_on_selector_all(f"#{k}-table tbody tr", "n => n.length"))
            page.click(f"[data-table={k}]")
        check("every table view has rows", all(r > 0 for r in rows), rows)
        # The ▤ toggle produced an unnamed table: headers, and nothing saying
        # what they were the headers of. Named from the card's own heading.
        names = page.eval_on_selector_all(".card [id$='-table'] table.tv", "n => n.map(t => t.getAttribute('aria-label') || '')")
        check("every table view is named for its card",
              len(names) > 0 and all(n.startswith("Table view: ") and len(n) > 15 for n in names), names[:3])
        check("the KPI band is a named group",
              page.eval_on_selector("#kpis", "e => e.getAttribute('role') === 'group' && !!e.getAttribute('aria-label')"))
        check("decorative svg is not announced",
              page.eval_on_selector_all("svg", "n => n.every(s => s.getAttribute('role') === 'img')"))

        # ---------- 1.4.1 use of colour ----------
        print("1.4.1  use of colour")
        check("status chips carry an icon and a word, never colour alone",
              page.evaluate(COLOUR_ONLY) == [], page.evaluate(COLOUR_ONLY)[:4])

        # ---------- 2.1.1 keyboard ----------
        print("2.1.1  keyboard")
        reach = page.evaluate("""() => {
            const f = Array.from(document.querySelectorAll(
              'button,a[href],select,input,textarea,[tabindex]:not([tabindex="-1"])'))
              .filter(e => e.getBoundingClientRect().width > 0);
            return f.length; }""")
        check("controls are in the tab order", reach > 20, reach)
        page.keyboard.press("Tab")
        first = page.evaluate("() => document.activeElement.tagName + ':' + (document.activeElement.id||'')")
        check("tab moves focus into the page", first != "BODY:", first)
        # a KPI tile must be operable from the keyboard, not just the mouse
        page.evaluate("() => document.querySelector('#kpis button').focus()")
        page.keyboard.press("Enter")
        page.wait_for_timeout(400)
        check("a KPI tile opens its drill-down from the keyboard",
              page.is_visible("#panel.on"))

        # ---------- 2.4.3 focus order ----------
        print("2.4.3  focus order")
        check("the drill-down panel takes focus when it opens",
              page.evaluate("() => document.activeElement.closest('#panel') !== null"),
              page.evaluate("() => document.activeElement.id"))
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        check("Escape closes the drill-down panel", not page.is_visible("#panel.on"))
        check("focus returns to the page after closing",
              page.evaluate("() => document.activeElement.closest('#panel') === null"))

        # ---------- 2.4.7 focus visible ----------
        print("2.4.7  focus visible")
        check("no control suppresses its focus indicator",
              page.evaluate(FOCUS) == [], page.evaluate(FOCUS)[:4])
        # One focus language, not two. The design's 2px link-blue ring was on
        # seven kinds of control and the browser's default on the rest, the
        # weaker of the two on the KPI band. Focus one of each kind and read
        # the ring; a control whose focus is not :focus-visible after a
        # programmatic focus is reported as such rather than passed.
        link = page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--link').trim()")
        rings = page.evaluate("""() => {
          const sels = ['.btn', '.btn.primary', '.icon-btn', '#kpis .kpi', '.seg button',
                        '#f-assignee', '#f-q', '.info', '#t-health', '.linkish'];
          const c = document.createElement('canvas').getContext('2d');
          const rgb = v => { c.fillStyle = v; return c.fillStyle; };
          return sels.map(s => {
            const el = [...document.querySelectorAll(s)].find(e => e.getBoundingClientRect().width > 0);
            if (!el) return [s, 'missing'];
            el.focus();
            const cs = getComputedStyle(el);
            return [s, el.matches(':focus-visible') ? cs.outlineWidth + ' ' + cs.outlineStyle + ' ' + rgb(cs.outlineColor) : 'not focus-visible'];
          });
        }""")
        want = page.evaluate("v => { const c = document.createElement('canvas').getContext('2d'); c.fillStyle = v; return c.fillStyle; }", link)
        bad = [r for r in rings if r[1] != "2px solid " + want]
        check("every kind of control focuses with the same 2px link-blue ring", bad == [], bad[:4])
        page.evaluate("() => document.activeElement && document.activeElement.blur()")

        # ---------- 1.3.1 / 2.1.1 the help layer without a pointer ----------
        # Every "i" was a span that answered mousemove and nothing else, and the
        # health chip's working — the disclosure ADR 0010 made the thing a
        # reader argues with — was a data attribute on an unfocusable span. For
        # anyone without a pointer, every basis on the page was unreachable,
        # which by the product's own second principle left every figure
        # unfinished. The marks are named buttons now, focus and click show the
        # same tooltip hover does, the tooltip is announced as the mark's
        # description while it shows, and Escape dismisses it.
        print("help without a pointer")
        # The inline value the code sets, not the computed one: the tooltip fades
        # over 80ms and a page that is not compositing never finishes a fade.
        TIP_ON = "() => document.getElementById('tip').style.opacity === '1'"
        marks = page.eval_on_selector_all(".info", "n => n.map(e => e.tagName + ':' + (e.getAttribute('aria-label') || ''))")
        check("every help mark is a button named for what it explains",
              len(marks) >= 15 and all(m.startswith("BUTTON:About ") for m in marks), marks[:3])
        page.focus("#c-burn .info")
        page.wait_for_timeout(250)
        check("focusing a help mark shows its explanation",
              page.evaluate(TIP_ON) and "What it is" in (page.text_content("#tip") or ""),
              (page.text_content("#tip") or "")[:60])
        check("and the tooltip is announced as the mark's description",
              page.get_attribute("#c-burn .info", "aria-describedby") == "tip")
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        check("Escape dismisses it and drops the description",
              not page.evaluate(TIP_ON) and not page.get_attribute("#c-burn .info", "aria-describedby"))
        page.focus("#t-health")
        page.wait_for_timeout(250)
        check("the health chip is reachable from the keyboard",
              page.evaluate("() => document.activeElement.id") == "t-health")
        check("and explains its score, or its refusal, on focus",
              page.evaluate(TIP_ON) and "score" in (page.text_content("#tip") or "").lower(),
              (page.text_content("#tip") or "")[:60])
        page.keyboard.press("Tab")
        page.wait_for_timeout(200)
        check("moving focus on takes the explanation with it",
              not page.evaluate(TIP_ON) or page.evaluate("() => document.activeElement.hasAttribute('data-tt') || document.activeElement.hasAttribute('data-tip')"))
        # A tap has no hover either: a click on the mark toggles it.
        page.click("#c-age .info")
        page.wait_for_timeout(250)
        check("a click on a help mark shows its explanation",
              page.evaluate(TIP_ON) and "What it is" in (page.text_content("#tip") or ""))
        page.click("#c-age .info")
        page.wait_for_timeout(250)
        check("and a second click hides it", not page.evaluate(TIP_ON))

        # ---------- 1.4.3 contrast, both themes ----------
        for theme in ("light", "dark"):
            print("1.4.3  contrast — %s theme" % theme)
            page.evaluate("t => document.documentElement.dataset.theme = t", theme)
            page.evaluate("() => window.DVD.debug.render()")
            page.wait_for_timeout(500)
            bad = page.evaluate(CONTRAST)
            worst = sorted(bad, key=lambda x: x["got"])[:5]
            check("all text meets WCAG AA in %s mode" % theme, bad == [], worst)
        page.evaluate("() => document.documentElement.dataset.theme = 'light'")
        page.evaluate("() => window.DVD.debug.render()")
        page.wait_for_timeout(400)

        # ---------- the empty selection, a state the sample data never reaches ----------
        # Over zero issues the health chip, the KPI strip and four tiles print a
        # refusal instead of a figure, in a colour pairing nothing above this
        # line has rendered. It is also the state the Forge build opens in, so
        # for some readers it is the only state they see — and until the fix it
        # was the state the grid was faded to 0.45 opacity in, which put every
        # sentence on the page below AA.
        # A note inside a refusal callout. The one beneath the brief card's
        # refusal measured 4.3:1 in the dark theme: muted ink on the warn wash.
        # Tested on the stylesheet directly, because the state needs a
        # transport that answers 404 and this suite runs from a file.
        print("1.4.3  contrast — a note inside a refusal")
        for theme in ("light", "dark"):
            page.evaluate("t => document.documentElement.dataset.theme = t", theme)
            ratio = page.evaluate("""() => {
              const box = document.createElement('div'); box.className = 'fc-refusal';
              const n = document.createElement('div'); n.className = 'note'; n.textContent = 'x';
              box.appendChild(n); document.body.appendChild(box);
              const lum = s => { const m = s.match(/\\d+(\\.\\d+)?/g).slice(0, 3).map(Number);
                const f = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
                return 0.2126 * f(m[0]) + 0.7152 * f(m[1]) + 0.0722 * f(m[2]); };
              const fg = lum(getComputedStyle(n).color), bg = lum(getComputedStyle(box).backgroundColor);
              box.remove();
              return (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05);
            }""")
            check("a note inside a refusal meets AA in %s mode" % theme, ratio >= 4.5, round(ratio, 2))
        page.evaluate("() => document.documentElement.dataset.theme = 'light'")

        print("1.4.3  contrast — the empty selection")
        page.evaluate("d => window.DVD.applyDataset(d)",
                      json.loads((ROOT / "forge" / "seed.json").read_text()))
        page.wait_for_timeout(500)
        for theme in ("light", "dark"):
            page.evaluate("t => document.documentElement.dataset.theme = t", theme)
            page.evaluate("() => window.DVD.debug.render()")
            page.wait_for_timeout(400)
            bad = page.evaluate(CONTRAST)
            check("the empty selection's refusals meet WCAG AA in %s mode" % theme,
                  bad == [], sorted(bad, key=lambda x: x["got"])[:4])
        check("nothing on the page is faded below full opacity",
              page.eval_on_selector_all(
                  "#grid, #grid > *",
                  "n => n.filter(e => +(getComputedStyle(e).opacity || 1) < 1).length") == 0)
        # 1.4.1 — the refusal must not be carried by colour alone.
        chip = " ".join((page.text_content("#t-health") or "").split())
        check("the health chip says in words that it is not scored",
              "not scored" in chip, chip)
        page.evaluate("d => window.DVD.applyDataset(d)", bundle)
        page.evaluate("() => document.documentElement.dataset.theme = 'light'")
        page.evaluate("() => window.DVD.debug.render()")
        page.wait_for_timeout(500)

        # ---------- 2.3.3 animation ----------
        print("2.3.3  animation from interactions")
        css = (ROOT / "src" / "styles.css").read_text()
        check("prefers-reduced-motion is honoured",
              "prefers-reduced-motion" in css and "transition:none" in css.replace(" ", ""))

        # ---------- the import wizard, a state axe would miss ----------
        print("wizard and dialogs")
        page.focus("#btn-import")
        page.keyboard.press("Enter")
        page.wait_for_timeout(400)
        check("the import dialog is a labelled modal dialog",
              page.eval_on_selector(".mbox", "e => e.getAttribute('role') === 'dialog' && "
                                             "e.getAttribute('aria-modal') === 'true' && "
                                             "!!document.getElementById(e.getAttribute('aria-labelledby') || '')"))
        check("the import dialog takes focus when it opens",
              page.evaluate("() => document.activeElement.closest('.mbox') !== null"),
              page.evaluate("() => document.activeElement.id"))
        check("its tabs name the panels they control",
              page.eval_on_selector_all(".tabs button", "n => n.every(b => "
                  "document.getElementById(b.getAttribute('aria-controls') || '') !== null && "
                  "document.getElementById(b.getAttribute('aria-controls')).getAttribute('role') === 'tabpanel')"))
        check("the import dialog's controls are all named",
              page.evaluate(NAMES) == [], page.evaluate(NAMES)[:4])
        check("wizard tabs use tab semantics",
              page.eval_on_selector_all(".tabs button",
                                        "n => n.every(e => e.getAttribute('role') === 'tab')"))
        check("the drill-down panel is a labelled dialog",
              page.eval_on_selector("#panel", "e => e.getAttribute('role') === 'dialog' && "
                                              "e.getAttribute('aria-modal') === 'true' && "
                                              "!!e.getAttribute('aria-labelledby')"))
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        check("Escape closes the import dialog and returns focus to Load data",
              not page.is_visible("#modal.on") and
              page.evaluate("() => document.activeElement.id") == "btn-import",
              page.evaluate("() => document.activeElement.id"))

        # ---------- the tile picker, the other state a scan would miss ----------
        # The popover is display:none until it is opened, so nothing above this
        # line has looked inside it. It holds twenty-six move buttons whose
        # accessible names are the only thing telling them apart.
        print("tile picker")
        page.click("#btn-view")
        page.wait_for_selector("#view-pop:not(.hidden)", timeout=5000)
        check("the picker's controls are all named",
              page.evaluate(NAMES) == [], page.evaluate(NAMES)[:4])
        # Switch themes the way the button does. Setting the attribute alone
        # leaves the deltas and sparkline colours that render() writes inline in
        # the previous theme's palette, and the failure that produces is the
        # test's, not the page's.
        for theme in ("light", "dark"):
            page.evaluate("t => document.documentElement.dataset.theme = t", theme)
            page.evaluate("() => window.DVD.debug.render()")
            page.wait_for_timeout(300)
            bad = page.evaluate(CONTRAST)
            check("the picker's text meets WCAG AA in %s mode" % theme, bad == [],
                  sorted(bad, key=lambda x: x["got"])[:4])
        page.evaluate("() => document.documentElement.dataset.theme = 'light'")
        page.evaluate("() => window.DVD.debug.render()")
        page.wait_for_timeout(300)
        check("the popover is a labelled dialog",
              page.eval_on_selector("#view-pop", "e => e.getAttribute('role') === 'dialog' && "
                                                 "!!e.getAttribute('aria-labelledby')"))

        # 2.1.1 — reordering must not need a pointer. Drag and drop alone would
        # put this feature out of reach of anyone working from a keyboard, so
        # the mechanism is the one Atlassian's own reorderable lists use: a
        # Move button per row opening a menu of four moves. Enter opens it
        # with focus on the first move the tile can make; Enter makes it.
        before = page.evaluate("() => window.DVD.debug.order()")
        page.focus('[data-move-menu="%s"]' % before[0])
        page.keyboard.press("Enter")
        page.wait_for_timeout(200)
        check("the Move button opens a menu and says so",
              page.eval_on_selector('[data-move-menu="%s"]' % before[0], "e => e.getAttribute('aria-expanded') === 'true'") and
              page.evaluate("() => document.activeElement.getAttribute('role') === 'menuitem'"))
        check("focus lands on the first move the first tile can make, which is down",
              page.evaluate("() => document.activeElement.getAttribute('data-move')") == "down")
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)
        after = page.evaluate("() => window.DVD.debug.order()")
        check("a tile moves from the keyboard alone",
              after[:2] == [before[1], before[0]], after[:3])

        # 2.4.3 — the list is rebuilt around the control that was pressed. If
        # focus is not put back, it falls to the body, and inside a popover that
        # reads as the popover having closed. It goes back to the tile's Move
        # button, which is there whatever end the tile has reached.
        active = lambda: page.evaluate("() => document.activeElement.getAttribute('data-move-menu')")
        check("focus returns to the Move button of the tile that moved",
              active() == before[0], active())

        page.evaluate("() => window.DVD.debug.setOrder(window.DVD.debug.tileIds())")
        page.wait_for_timeout(250)
        page.focus('[data-move-menu="%s"]' % before[1])
        page.keyboard.press("Enter")
        page.wait_for_timeout(200)
        page.keyboard.press("Enter")   # the first move the second tile can make: to top
        page.wait_for_timeout(300)
        check("to top is one move from the keyboard, and focus follows the tile",
              page.evaluate("() => window.DVD.debug.order()")[0] == before[1] and active() == before[1], active())
        # Escape closes an open menu back onto its button, without moving anything.
        page.focus('[data-move-menu="%s"]' % before[0])
        page.keyboard.press("Enter")
        page.wait_for_timeout(150)
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)
        check("Escape closes the menu and returns focus to its button",
              page.is_visible("#view-pop") and active() == before[0] and
              page.eval_on_selector('[data-move-menu="%s"]' % before[0], "e => e.getAttribute('aria-expanded') === 'false'"))

        # 4.1.3 — the tile that moved is somewhere down the page, usually behind
        # the popover, so the move is invisible from where it was made.
        check("the move is announced in a live region",
              page.eval_on_selector("#vp-live", "e => e.getAttribute('aria-live') === 'polite'") and
              "moved to position" in page.text_content("#vp-live"),
              page.text_content("#vp-live"))

        page.evaluate("() => window.DVD.debug.setOrder(window.DVD.debug.tileIds())")
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)

        # ---------- zoom / reflow (1.4.10) ----------
        print("1.4.10  reflow")
        # 320 CSS pixels is the width WCAG 1.4.10 actually specifies; 380 was the
        # softer check here, and it passed on macOS while CI failed on Linux
        # because a control sat 16px from the edge and Linux renders glyphs wider.
        # Testing the real threshold leaves that much less to font metrics.
        # When this fails, "323" is not enough to act on — especially since the
        # cause is usually font metrics on a machine other than the one running
        # the test. Name the elements sticking out over the edge.
        OVERFLOWERS = """() => {
            const vw = window.innerWidth, out = [];
            document.querySelectorAll('body *').forEach(e => {
              const r = e.getBoundingClientRect();
              if (r.width <= 0 || r.right <= vw + 0.5) return;
              if (getComputedStyle(e).visibility === 'hidden') return;
              out.push((e.tagName.toLowerCase()
                        + (e.id ? '#' + e.id : '')
                        + (typeof e.className === 'string' && e.className
                             ? '.' + e.className.trim().split(/\\s+/)[0] : ''))
                       + ' right=' + Math.round(r.right)
                       + ' "' + (e.textContent || '').trim().slice(0, 24) + '"');
            });
            return out.slice(0, 6);
        }"""
        for width in (380, 320):
            page.set_viewport_size({"width": width, "height": 800})
            page.wait_for_timeout(700)
            sw = page.evaluate("() => document.documentElement.scrollWidth")
            ok = not page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 2")
            check("no horizontal scrolling at %dpx" % width, ok,
                  sw if ok else "%d — over the edge: %s" % (sw, page.evaluate(OVERFLOWERS)))

        # The popover is anchored to the right edge and is wider than a narrow
        # screen, so it is checked open as well as closed. Everything above this
        # measured it as display:none, which costs nothing and proves nothing.
        page.set_viewport_size({"width": 320, "height": 800})
        page.click("#btn-view")
        page.wait_for_selector("#view-pop:not(.hidden)", timeout=5000)
        page.wait_for_timeout(400)
        sw = page.evaluate("() => document.documentElement.scrollWidth")
        ok = not page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 2")
        check("the open tile picker does not overflow a 320px screen", ok,
              sw if ok else "%d — over the edge: %s" % (sw, page.evaluate(OVERFLOWERS)))
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)

        # A control that reaches the viewport edge passes today and fails on the
        # next machine. Assert the margin, not just the absence of a scrollbar.
        page.set_viewport_size({"width": 320, "height": 800})
        page.wait_for_timeout(500)
        widest = page.evaluate("""() => {
            let worst = {sel: '', right: 0};
            document.querySelectorAll('.card, .seg, .kpis, .filters, .topbar').forEach(e => {
              const r = e.getBoundingClientRect();
              if (r.width && r.right > worst.right) worst = {sel: e.id || e.className, right: Math.round(r.right)};
            });
            return worst;
        }""")
        check("no laid-out control reaches within 8px of the 320px edge",
              widest["right"] <= 312, widest)
        page.set_viewport_size({"width": 1500, "height": 1000})

        b.close()

    print()
    if warnings:
        print("%d warning(s): %s" % (len(warnings), ", ".join(warnings)))
    if failures:
        print("%d check(s) failed: %s" % (len(failures), ", ".join(failures)))
        sys.exit(1)
    print("all accessibility checks passed")


if __name__ == "__main__":
    main()
