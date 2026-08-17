#!/usr/bin/env python3
"""
record_demo.py — record a captioned, shareable walkthrough.

No audio, on purpose: a demo with narration cannot be watched in an open-plan
office or dropped into a Slack thread. Everything the viewer needs is burned
into the frame.

The script drives the real built file against `data/demo-bundle.json`, which is
authored so each selection reveals something rather than merely changing
something (see make_demo_bundle.py).

    python3 scripts/record_demo.py --out docs/demo.mp4

Requires ffmpeg on PATH for the webm -> mp4 conversion.
"""

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "delivery-value-dashboard.html"
BUNDLE = ROOT / "data" / "demo-bundle.json"
W, H = 1600, 1000

# --------------------------------------------------------------- the chrome
OVERLAY = r"""
() => {
  if (document.getElementById('demo-overlay')) return;
  const css = document.createElement('style');
  css.textContent = `
    #demo-overlay{position:fixed;inset:0;z-index:9999;pointer-events:none;
      font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
    #demo-cap{position:absolute;left:0;right:0;bottom:0;padding:22px 40px 26px;
      background:linear-gradient(to top,rgba(8,8,10,.94) 62%,rgba(8,8,10,0));
      color:#fff;opacity:0;transition:opacity .35s}
    #demo-cap.on{opacity:1}
    #demo-cap h2{margin:0;font-size:31px;font-weight:640;letter-spacing:-.015em;line-height:1.2}
    #demo-cap p{margin:7px 0 0;font-size:19px;line-height:1.42;color:#d7d7d2;max-width:1180px}
    #demo-cap .tag{display:inline-block;font-size:12.5px;font-weight:700;letter-spacing:.09em;
      text-transform:uppercase;color:#7fb2f0;margin-bottom:7px}
    #demo-ring{position:absolute;border:3px solid #3987e5;border-radius:12px;opacity:0;
      transition:all .3s cubic-bezier(.4,0,.2,1);
      outline:9999px solid rgba(10,10,14,.40)}
    #demo-ring.on{opacity:1}
    #demo-dot{position:absolute;width:22px;height:22px;border-radius:50%;
      background:rgba(57,135,229,.30);border:2.5px solid #6aa6ee;opacity:0;
      transition:all .3s cubic-bezier(.4,0,.2,1);transform:translate(-50%,-50%)}
    #demo-dot.on{opacity:1}
    #demo-card{position:absolute;inset:0;background:#0b0b0d;color:#fff;opacity:0;
      transition:opacity .45s;display:flex;align-items:center;justify-content:center}
    #demo-card.on{opacity:1}
    #demo-card .inner{max-width:1080px;padding:0 60px}
    #demo-card h1{margin:0;font-size:56px;font-weight:650;letter-spacing:-.028em;line-height:1.08}
    #demo-card h1 em{font-style:normal;color:#7fb2f0}
    #demo-card p{margin:20px 0 0;font-size:23px;line-height:1.5;color:#c9c9c3}
    #demo-card ul{margin:26px 0 0;padding:0;list-style:none;display:grid;gap:13px}
    #demo-card li{font-size:21px;color:#e9e9e4;display:grid;grid-template-columns:30px 1fr;gap:12px}
    #demo-card li b{color:#fff}
    #demo-card .k{color:#7fb2f0;font-weight:700}
    #demo-prog{position:absolute;top:0;left:0;height:4px;background:#3987e5;width:0%;
      transition:width .5s linear}
  `;
  document.head.appendChild(css);
  const o = document.createElement('div');
  o.id = 'demo-overlay';
  o.innerHTML = '<div id="demo-prog"></div><div id="demo-ring"></div><div id="demo-dot"></div>' +
                '<div id="demo-cap"></div><div id="demo-card"><div class="inner"></div></div>';
  document.body.appendChild(o);
}
"""

CAPTION = r"""
([tag, title, body]) => {
  const c = document.getElementById('demo-cap');
  c.innerHTML = (tag ? '<span class="tag">' + tag + '</span>' : '') +
                '<h2>' + title + '</h2>' + (body ? '<p>' + body + '</p>' : '');
  c.classList.add('on');
}
"""

SCROLL = r"""
(sel) => {
  const el = sel && document.querySelector(sel);
  if (el) el.scrollIntoView({block: 'center', behavior: 'smooth'});
}
"""

HIGHLIGHT = r"""
(sel) => {
  const ring = document.getElementById('demo-ring');
  const dot = document.getElementById('demo-dot');
  if (!sel) { ring.classList.remove('on'); dot.classList.remove('on'); return; }
  const el = document.querySelector(sel);
  if (!el) { ring.classList.remove('on'); return; }
  const r = el.getBoundingClientRect();
  const pad = 8;
  ring.style.left = (r.left - pad) + 'px';
  ring.style.top = (r.top - pad) + 'px';
  ring.style.width = (r.width + pad * 2) + 'px';
  ring.style.height = (r.height + pad * 2) + 'px';
  ring.classList.add('on');
  dot.style.left = (r.left + r.width / 2) + 'px';
  dot.style.top = (r.top + r.height / 2) + 'px';
  dot.classList.add('on');
}
"""

CARD = r"""
([html]) => {
  const c = document.getElementById('demo-card');
  if (!html) { c.classList.remove('on'); return; }
  c.querySelector('.inner').innerHTML = html;
  c.classList.add('on');
}
"""


def build_cards(fc):
    """Opening and closing cards. The closing figures come from the real
    forecaster run against the demo bundle — see the --forecast argument."""
    open_card = (
        "<h1>One file.<br>Every board, every sprint,<br><em>every number traceable.</em></h1>"
        "<p>A delivery dashboard an executive can read and an engineer can interrogate — "
        "plus an agent that turns it into a written brief and a forecast.</p>")
    close_card = (
        "<h1>Then the agent <em>writes it up</em>.</h1>"
        "<p>Same data, two documents, every figure from a tool rather than a language model.</p>"
        "<ul>"
        "<li><span class='k'>&#9656;</span><span><b>%(prob).1f%% chance</b> Sprint 24 lands complete by 14 August "
        "&mdash; the 85th-percentile finish is <b>%(p85nice)s</b></span></li>"
        "<li><span class='k'>&#9656;</span><span>Next sprint should be sized at <b>%(commit)d items</b>, "
        "not the median of %(median)d &mdash; committing at the median misses half the time by construction</span></li>"
        "<li><span class='k'>&#9656;</span><span>From <b>%(obs)d days</b> of throughput and <b>%(done)d</b> completed items "
        "&mdash; below that threshold it refuses rather than guesses</span></li>"
        "</ul>"
        "<p style='margin-top:26px;font-size:19px;color:#8f8f89'>Monte Carlo over item counts, "
        "20,000 seeded trials. Same question, same answer, every time.</p>") % fc
    return open_card, close_card


def scenes(fc):
    open_card, close_card = build_cards(fc)
    S = []
    A = S.append
    A(dict(card=open_card, dwell=4.6, hide_ring=True))
    A(dict(card=None, dwell=0.5))

    A(dict(tag="The read", title="Plain language first, charts second",
           body="Every sprint opens with what the numbers mean and which issues to look at. "
                "The health score shows its full working on hover, so it can be argued with.",
           hl="#c-exec", dwell=6.2))

    A(dict(tag="Behind, or given more?", title="The burndown separates the two",
           body="The orange line is total scope. When it steps up, work was added mid-sprint — "
                "so a flat delivery line stops meaning “this team is slow”.",
           hl="#c-burn", dwell=6.4))

    A(dict(tag="Traceable", title="Every number opens the issues behind it",
           body="Blocked, overdue, ageing, value — one click gives the keys, owners, "
                "elapsed-time breakdown and a link back to Jira.",
           click="#kpis button:nth-child(3)", hl=None, dwell=5.0))
    A(dict(hl="#panel", dwell=3.6, tag="Traceable", title="Every number opens the issues behind it",
           body="Three items flagged, one of them the highest-priority work that has been open 21 days."))
    A(dict(click="#p-done", dwell=0.8))

    A(dict(tag="Step back in time", title="Any previous sprint, instantly",
           body="Sprint 24 back to Sprint 21 on the same board. Each sprint shows only the history "
                "available at the time — a past report cannot borrow the future.",
           select=("#c-sprint", "Sprint 21"), hl="#ctxbar", dwell=6.2))

    A(dict(tag="Trend, not snapshot", title="Commitment climbed. Delivery did not.",
           body="Back on the current sprint: 18 items committed against a three-sprint average of 10. "
                "That is a planning problem, and it will read as failure whatever the team does.",
           select=("#c-sprint", "Sprint 24"), hl="#c-pred", dwell=6.6))

    A(dict(tag="Compare boards", title="Same company, same fortnight, healthy",
           body="Platform &amp; Infra: 80% of items done, nothing blocked, and 67% of elapsed time "
                "spent actually working. The Storefront problem is local, not systemic.",
           select=("#c-board", "Platform & Infra"), hl="#kpis", dwell=6.6))

    A(dict(tag="Compare projects", title="A different project entirely",
           body="Highpeak Mobile — a separate Jira project, in the same file, one click away.",
           select_project="Highpeak Mobile", hl="#ctxbar", dwell=5.4))

    A(dict(tag="The unit changes the answer", title="82% of items… but 48% of the points",
           body="Fourteen of seventeen items are done, which sounds nearly finished. "
                "The two that are not are the two big ones.",
           hl="#kpis .kpi:nth-child(1)", dwell=5.6))
    A(dict(click="[data-unit=points]", hl="#kpis .kpi:nth-child(1)", dwell=5.4,
           tag="The unit changes the answer", title="Switch to points and the story flips",
           body="Both readings are true. Items forecast better; points carry size. "
                "One control, and nobody has to argue about which spreadsheet is right."))
    A(dict(click="[data-unit=items]", dwell=0.6))

    A(dict(tag="Six sprints at once", title="Roll a whole board up",
           body="Flow, ageing, distribution and value hold across the rollup. "
                "The burndown says why it cannot, rather than drawing something meaningless.",
           select=("#c-sprint", "All 6 sprints"), hl="#c-flow", dwell=6.2))

    A(dict(tag="The finding that pays", title="Most of the time, the work is waiting",
           body="Each bar is one closed item: pale is queueing, solid is being worked. "
                "Attack the queues, not the coding — it is the cheapest speed available.",
           select_project="Highpeak Commerce", select=("#c-board", "Storefront Delivery"),
           hl="#c-flow", dwell=7.0))

    A(dict(tag="Not typed by hand", title="Risks computed from the data, each with an action",
           body="Generated from what is on screen — including the current filter — every one "
                "linking to the issues it came from.",
           hl="#c-risk", dwell=6.4))

    # The popover is deliberately left open across preset clicks in the product,
    # which is right for using it and wrong for filming it — it sits over the
    # view it just produced. So: open, choose, close, and only then show the
    # result. The ring stays off the popover; a floating panel over a ringed
    # card reads as two things happening at once.
    A(dict(tag="Two audiences, one file", title="Turn tiles off and send the view",
           body="Twelve tiles, two presets — shaped after the agent's own executive brief and "
                "team report, so the page and the write-up agree about what matters.",
           click="#btn-view", hl=None, dwell=6.0))
    A(dict(click='[data-preset="exec"]', dwell=0.6))
    A(dict(tag="Two audiences, one file", title="The executive view, in one click",
           body="Five tiles hidden — and named, not silently dropped. Nothing is recomputed: "
                "hiding a tile changes what is shown, never what is counted. Save it as a "
                "standalone file, or print it, and the narrative goes with it.",
           click="#btn-view", hl="#c-exec", dwell=7.4))
    # Put the page back before the closing card, so the last frame of the
    # product is the whole product rather than a filtered view of it.
    A(dict(click="#btn-view", dwell=0.4))
    A(dict(click='[data-preset="all"]', dwell=0.4))
    A(dict(click="#btn-view", dwell=0.4))

    A(dict(card=close_card, dwell=9.0, hide_ring=True))
    return S


def run(page, S, total):
    elapsed = 0.0
    for sc in S:
        # Caption first, then the action. The other order leaves half a second
        # of video where the words describe the previous scene.
        if sc.get("title"):
            page.evaluate(CAPTION, [sc.get("tag", ""), sc["title"], sc.get("body", "")])
        if "card" in sc:
            if sc["card"]:
                page.evaluate("() => window.scrollTo({top: 0, behavior: 'auto'})")
            page.evaluate(CARD, [sc["card"]])
            if sc["card"]:
                page.evaluate(CAPTION, ["", "", ""])
                page.evaluate("() => document.getElementById('demo-cap').classList.remove('on')")
                page.evaluate(HIGHLIGHT, None)
        if sc.get("hide_ring"):
            page.evaluate(HIGHLIGHT, None)
        if sc.get("select_project"):
            page.select_option("#c-proj", label=sc["select_project"])
            page.wait_for_timeout(700)
        if sc.get("select"):
            sel, want = sc["select"]
            opts = page.eval_on_selector_all(sel + " option", "n => n.map(e => e.textContent)")
            match = next((o for o in opts if want in o), None)
            if match:
                page.select_option(sel, label=match)
                page.wait_for_timeout(750)
        if sc.get("click"):
            page.click(sc["click"])
            page.wait_for_timeout(550)
        if "hl" in sc:
            # Scroll first: a ring drawn around an element below the fold is a
            # ring nobody sees. Measure only once the scroll has settled.
            if sc["hl"] and sc["hl"] not in ("#panel",):
                page.evaluate(SCROLL, sc["hl"])
                page.wait_for_timeout(700)
            page.evaluate(HIGHLIGHT, sc["hl"])
            page.wait_for_timeout(340)
        elapsed += sc["dwell"]
        page.evaluate("(p) => document.getElementById('demo-prog').style.width = p + '%'",
                      min(100, 100 * elapsed / total))
        page.wait_for_timeout(int(sc["dwell"] * 1000))


def forecast_json(path):
    """The closing card quotes the forecaster, so the numbers on it have to come
    from the forecaster. This used to read a file somebody produced by hand,
    which meant `make demo` could not be run from a clean checkout and the card
    could drift from the tool without anything failing. Now it runs the tool.

    An explicit --forecast file is still honoured if it exists.
    """
    if path.exists():
        return path.read_text()
    out = subprocess.run(
        [sys.executable, str(ROOT / "agent" / "tools" / "forecast.py"),
         str(ROOT / "data" / "sample-multi-sprint.json"),
         "--snapshots", str(ROOT / "agent" / "snapshots" / "scope.json"), "--json"],
        capture_output=True, text=True, check=True).stdout
    f = json.loads(out)
    card = dict(prob=f["sprint_completion"]["prob_by_target"],
                p85=f["sprint_completion"]["percentiles"]["85"],
                commit=f["next_commitment"]["recommended"],
                median=f["next_commitment"]["stretch_median"],
                obs=f["inputs"]["throughput_observations"],
                done=f["inputs"]["items_completed_in_window"])
    return json.dumps(card)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/demo.mp4")
    ap.add_argument("--forecast", default="/tmp/fc.json",
                    help="JSON of real forecaster output for the closing card")
    a = ap.parse_args()

    fc = json.loads(forecast_json(pathlib.Path(a.forecast)))
    from datetime import date as _d
    def nice(iso):
        d = _d.fromisoformat(iso)
        return d.strftime("%-d %B")
    fc = dict(prob=fc["prob"] * 100, p85=fc["p85"], p85nice=nice(fc["p85"]),
              commit=fc["commit"], median=fc["median"], obs=fc["obs"], done=fc["done"])
    S = scenes(fc)
    total = sum(s["dwell"] for s in S)
    print("%d scenes, %.0f seconds" % (len(S), total))

    tmp = pathlib.Path(tempfile.mkdtemp())
    bundle = json.loads(BUNDLE.read_text())
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--force-device-scale-factor=1"])
        ctx = b.new_context(viewport={"width": W, "height": H},
                            record_video_dir=str(tmp),
                            record_video_size={"width": W, "height": H})
        t_ctx = time.monotonic()
        page = ctx.new_page()
        page.goto(DIST.as_uri())
        page.wait_for_timeout(700)
        page.evaluate("d => window.DVD.applyDataset(d)", bundle)
        page.wait_for_timeout(700)
        page.evaluate(OVERLAY)
        # Show the opening card with the fade disabled, so the trimmed video
        # starts on a solid title rather than a half-transparent one.
        page.evaluate("() => { const c = document.getElementById('demo-card');"
                      "c.style.transition = 'none'; }")
        page.evaluate(CARD, [S[0]["card"]])
        page.wait_for_timeout(150)
        page.evaluate("() => { document.getElementById('demo-card').style.transition = ''; }")
        # Recording began when the context was created, so the first couple of
        # seconds are page load. Note the offset and trim it off in ffmpeg
        # rather than shipping a video that opens on setup.
        lead_in = time.monotonic() - t_ctx
        run(page, S, total)
        page.wait_for_timeout(400)
        ctx.close()
        b.close()

    webm = next(tmp.glob("*.webm"))
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("ffmpeg"):
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-ss", "%.2f" % max(lead_in - 0.25, 0), "-i", str(webm),
            "-vf", "scale=1600:-2,fps=24", "-c:v", "libx264", "-preset", "slow",
            "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(out)], check=True)
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        shutil.copy(webm, out.with_suffix(".webm"))
        sys.exit("ffmpeg not found — left the raw webm beside the target")

    print("Wrote %s — %.1f MB" % (out, out.stat().st_size / 1e6))


if __name__ == "__main__":
    main()
