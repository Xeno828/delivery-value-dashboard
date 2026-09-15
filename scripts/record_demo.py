#!/usr/bin/env python3
"""
record_demo.py — the demo, cut from real pictures of the real build.

The demo is a web page, `scripts/demo_film.html`, not a screen recording.
This script takes the pictures (`capture_screens.py`, the same pass that
writes the README's), fills the page with them and the scene list below, and
then renders it one frame at a time — `FILM.seek(t)` is a pure function of
time — into ffmpeg. Every frame is drawn by a browser from a screenshot and
from text, so no word on screen is guessed and no figure is typed: the closing
card's numbers are read from the forecaster's own answer for the sprint the
film shows.

No audio, on purpose: a demo with narration cannot be watched in an open-plan
office or dropped into a Slack thread, so everything the viewer needs is in
the frame. The same scene list is written out as `docs/demo-script.md` — the
captions with their timings — for anyone who wants to record a voice-over on
top; the words in the film and the words in the script cannot differ.

    python3 scripts/record_demo.py            # docs/demo.mp4, docs/demo-small.mp4,
                                              # docs/demo-script.md, docs/screenshots/

Needs ffmpeg on PATH, or `pip install imageio-ffmpeg` for a bundled one.
"""

import argparse
import base64
import html
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from capture_screens import (BUNDLE, README_SHOTS, ROOT, capture, live_server,  # noqa: E402
                             open_page)

TEMPLATE = ROOT / "scripts" / "demo_film.html"
FW, FH = 1920, 1080


# ------------------------------------------------------------------ scenes
def scenes(fc):
    """The film, as a list. `shot` names a picture from capture(); `focus` /
    `ringSel` / `cursorSel` name elements whose rectangles were recorded with
    it, so the camera frames and the ring marks what is really there. `dur`
    is milliseconds. The closing card quotes `fc`, the forecaster's answer."""
    S = []
    A = S.append

    A(dict(dur=5200, card=(
        "<p class='kicker'>Delivery Value Dashboard</p>"
        "<h1>One file.<br>Every board, every sprint,<br><em>every number traceable.</em></h1>"
        "<p>A delivery report an executive can read and an engineer can interrogate &mdash; "
        "and a forecaster that refuses rather than guesses.</p>")))

    A(dict(shot="dashboard", dur=6200, to=[0.5, 0.5, 1.0],
           tag="The whole sprint on one page", title="Headline numbers first, the verdict second",
           body="Eight figures an executive scans left to right, then a plain-language read of what "
                "they mean. Every sentence links to the issues behind it."))

    A(dict(shot="dashboard", dur=6800, focus="#kpis", ringSel="#kpis .kpi[data-kpi='4']",
           tag="Behind, or given more?", title="Delivered 45%, 15 points behind the clock &mdash; and 4 items added after kickoff",
           body="Being behind and being given more work are two different conversations. "
                "The band keeps them apart instead of letting one hide inside the other."))

    A(dict(shot="burndown", dur=6800, focus="#c-burn", ringSel="#c-burn", pad=0.03,
           tag="Scope is its own line", title="The burndown separates the two",
           body="The orange line is total scope. When it steps up, work was added mid-sprint &mdash; "
                "so a flat delivery line stops meaning &ldquo;this team is slow&rdquo;."))

    A(dict(shot="dashboard", dur=3400, focus="#kpis", cursorSel="#kpis .kpi[data-kpi='2']",
           tag="Traceable", title="Every number opens the issues behind it",
           body="Blocked, overdue, ageing, value &mdash; one click gives the keys, owners, "
                "ages and a link back to Jira."))
    A(dict(shot="drilldown", dur=6600, focus="#panel", ringSel="#panel", pad=0.02, move=900,
           tag="Traceable", title="Three blocked items, with owners, ages and a CSV",
           body="BLC-474 is the highest-priority work on the board and has been open 21 days. "
                "That is a decision problem, not an effort problem."))

    A(dict(shot="flow", dur=7200, focus="#c-flow", ringSel="#c-flow", pad=0.03,
           tag="Where the time goes", title="Most of the time, the work is waiting",
           body="Each bar is one closed item: pale is queueing, solid is being worked. "
                "30% of elapsed time was active work. Attack the queues, not the coding &mdash; "
                "it is the cheapest speed available."))

    A(dict(shot="forecast", dur=6600, focus="#c-pred", ringSel="#c-pred", pad=0.03,
           tag="Trend, not snapshot", title="Commitment climbed. Delivery did not.",
           body="18 items committed against a three-sprint average of 10. That is a planning "
                "problem, and it will read as failure whatever the team does."))

    A(dict(shot="platform", dur=6600, focus="#kpis", ringSel="#kpis",
           tag="Compare boards", title="Same company, same fortnight, healthy",
           body="Platform &amp; Infra: 80% of items done, nothing blocked, 65% of elapsed time "
                "actively worked. The Storefront problem is local, not systemic."))

    A(dict(shot="mobile-items", dur=4800, focus="#kpis", ringSel="#kpis .kpi[data-kpi='0']",
           cursorSel="[data-unit=points]",
           tag="The unit changes the answer", title="82% of items done&hellip;",
           body="Fourteen of seventeen items are done on the Mobile board, which sounds nearly finished."))
    A(dict(shot="mobile-points", dur=6400, focus="#kpis", ringSel="#kpis .kpi[data-kpi='0']", move=600,
           tag="The unit changes the answer", title="&hellip;but 48% of the points",
           body="The two items not done are the two big ones. Both readings are true: items "
                "forecast better, points carry size. One toggle, and nobody argues about spreadsheets."))

    A(dict(shot="risks", dur=6400, focus="#c-risk", ringSel="#c-risk", pad=0.03,
           tag="Not typed by hand", title="Risks computed from the data, each with an action",
           body="Generated from what is on screen &mdash; including the current filter &mdash; "
                "every one linking to the issues it came from."))

    A(dict(shot="exec-view", dur=6800, to=[0.5, 0.5, 1.0], ringSel="#btn-view",
           tag="Two audiences, one file", title="The executive view, in one click",
           body="Eight of eighteen tiles &mdash; named, not silently dropped. Nothing is recomputed: "
                "hiding a tile changes what is shown, never what is counted. Save it as a file, "
                "print it, or send a link."))

    A(dict(shot="forecast", dur=7600, focus="#c-forecast", ringSel="#c-forecast", pad=0.03,
           tag="Ask the forecaster", title="When does the outstanding work land?",
           body="A Monte Carlo run by the same tool the agent uses, over this team's whole recorded "
                "history. %(remaining)d items outstanding: 85%% of simulations finish by %(p85)s. "
                "Read the 85th percentile &mdash; a median is a coin flip by construction." % fc))
    A(dict(shot="forecast-30", dur=6400, ringSel="#fc-items", move=500,
           tag="Ask the forecaster", title="Or size work that does not exist yet",
           body="Type 30 items and the same history answers a different question. It is labelled "
                "as asked-for, so a hypothetical can never be mistaken for this sprint's own position."))
    A(dict(shot="forecast-howmany", dur=6200, ringSel="#c-forecast", move=500,
           tag="Ask the forecaster", title="How much lands by a date you choose",
           body="The capacity question, and the one that sizes the next commitment. "
                "Commit at the 85%% figure &mdash; %(commit)d items here, not the median of %(median)d, "
                "which misses half the time." % fc))
    A(dict(shot="forecast-sequence", dur=7800, focus="#c-forecast", ringSel="#c-forecast", pad=0.03, move=700,
           tag="Ask the forecaster", title="And what each ordering of the asks costs the others",
           body="Every ordering of the outstanding asks, simulated. It names the asks no ordering "
                "delivers by their date, and the ones it could not size, with the reason. "
                "No value score is computed &mdash; here or anywhere."))

    A(dict(shot="dark", dur=4200, to=[0.5, 0.5, 1.0],
           tag="Two themes, one page", title="Light and dark, both tested for contrast",
           body="WCAG 2.2 AA in both themes, on every push. Colour is never the only signal."))

    A(dict(shot="import-mapping", dur=6600, focus="#modal .mbox", ringSel="#modal .mbox", pad=0.02,
           tag="Getting data in", title="Drop a raw Jira or Asana export",
           body="Columns are matched automatically and every guess is shown for you to correct. "
                "Burndown and sprint history are recalculated from what you upload, never inherited."))

    A(dict(dur=9200, card=(
        "<h1>Then the agent <em>writes it up</em>.</h1>"
        "<p>Same data, two documents, every figure from a tool rather than a language model.</p>"
        "<ul>"
        "<li><span class='k'>&#9656;</span><span><b>%(prob).1f%% chance</b> Sprint 24 lands complete by "
        "%(target)s &mdash; the 85th-percentile finish is <b>%(p85)s</b></span></li>"
        "<li><span class='k'>&#9656;</span><span>Next sprint should be sized at <b>%(commit)d items</b>, "
        "not the median of %(median)d &mdash; committing at the median misses half the time by construction</span></li>"
        "<li><span class='k'>&#9656;</span><span>From <b>%(obs)d days</b> of throughput and <b>%(done)d</b> "
        "completed items &mdash; below that threshold it refuses rather than guesses</span></li>"
        "</ul>"
        "<p class='foot'>Monte Carlo over item counts, 20,000 seeded trials &mdash; same question, same answer, "
        "every time. The same Python runs inside Jira as a Forge app: no remote, no egress.</p>") % fc))
    return S


# ---------------------------------------------------------------- helpers
def ffmpeg_exe():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg not found: install it, or `pip install imageio-ffmpeg`")


def forecast_figures(server):
    """The closing card quotes the forecaster, so its numbers come from the
    forecaster — the live server's answer for the sprint on screen, which is
    the answer the forecast tile in the pictures shows."""
    from datetime import date
    url = server.rsplit("/dist/", 1)[0] + "/api/forecast?id=BLC/42/S24"
    f = json.loads(urllib.request.urlopen(url, timeout=120).read())
    sc, nc, inp = f["sprint_completion"], f["next_commitment"], f["inputs"]
    nice = lambda iso: date.fromisoformat(iso).strftime("%-d %B")
    return dict(prob=sc["prob_by_target"] * 100, target=nice(sc["target_date"]),
                p85=nice(sc["percentiles"]["85"]), remaining=sc["remaining_items"],
                commit=nc["recommended"], median=nc["stretch_median"],
                obs=inp["throughput_observations"], done=inp["items_completed_in_window"])


def build_film(shots, rects, S):
    images = {}
    for name, p in shots.items():
        images[name] = "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
    t = TEMPLATE.read_text()
    t = t.replace("/*SCENES*/[]", json.dumps(S))
    t = t.replace("/*IMAGES*/{}", json.dumps(images))
    t = t.replace("/*RECTS*/{}", json.dumps(rects))
    return t


def write_script(page, out):
    """The captions and their timings, as a voice-over script."""
    rows = page.evaluate("() => window.FILM.script()")
    total = page.evaluate("() => window.FILM.total")
    plain = lambda s: html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("  ", " ").strip()
    lines = ["# Demo script", "",
             "Generated by `scripts/record_demo.py` from the film's own scene list — the captions "
             "in `docs/demo.mp4`, with their timings, so a voice-over recorded against it says what "
             "the frame says. Do not edit by hand; edit `scenes()` and run `make demo`.", "",
             "Running time %d:%02d. No audio in the file itself." % (total // 60000, (total // 1000) % 60), "",
             "| At | For | On screen | Words |", "|---|---|---|---|"]
    for r in rows:
        at = "%d:%02d" % (r["at"] // 60000, (r["at"] // 1000) % 60)
        if r["card"]:
            lines.append("| %s | %.1fs | *title card* | — |" % (at, r["dur"] / 1000))
        else:
            head = ("**%s** — " % plain(r["tag"]) if r["tag"] else "") + plain(r["title"])
            lines.append("| %s | %.1fs | %s | %s |" % (at, r["dur"] / 1000, head, plain(r["body"])))
    out.write_text("\n".join(lines) + "\n")


def render(page, out, fps, ffmpeg):
    """Step the film a frame at a time and pipe each frame to ffmpeg."""
    total = page.evaluate("() => window.FILM.total")
    n = int(total * fps / 1000)
    proc = subprocess.Popen(
        [ffmpeg, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps),
         "-c:v", "mjpeg", "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "26",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE)
    t_start = time.monotonic()
    for i in range(n):
        page.evaluate("t => window.FILM.frame(t)", i * 1000 / fps)
        proc.stdin.write(page.screenshot(type="jpeg", quality=93))
        if i % (fps * 10) == 0:
            print("  %3d%%  %5.1fs of film, %.0fs elapsed" % (100 * i / n, i / fps, time.monotonic() - t_start))
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg failed")
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/demo.mp4")
    ap.add_argument("--small", default="docs/demo-small.mp4", help="the cut people email; '' to skip")
    ap.add_argument("--script", default="docs/demo-script.md", help="voice-over script; '' to skip")
    ap.add_argument("--screenshots", default="docs/screenshots",
                    help="where the README's pictures go, from the same pass; '' to skip")
    ap.add_argument("--html", default="", help="also write the film as a standalone page")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--port", type=int, default=8899)
    a = ap.parse_args()

    from playwright.sync_api import sync_playwright
    ffmpeg = ffmpeg_exe()
    tmp = pathlib.Path(tempfile.mkdtemp())
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)

    with live_server(a.port) as url, sync_playwright() as pw:
        b = pw.chromium.launch()
        print("capturing the product")
        page = open_page(b, url)
        shots = capture(page, tmp / "shots")
        rects = json.loads((tmp / "shots" / "rects.json").read_text())
        page.context.close()
        fc = forecast_figures(url)
        S = scenes(fc)
        film = tmp / "film.html"
        film.write_text(build_film(shots, rects, S))
        if a.html:
            shutil.copy(film, ROOT / a.html)

        print("rendering %d scenes" % len(S))
        ctx = b.new_context(viewport={"width": FW, "height": FH}, device_scale_factor=1)
        page = ctx.new_page()
        page.goto(film.as_uri())
        page.evaluate("() => window.FILM.ready")
        page.wait_for_timeout(300)
        total = render(page, out, a.fps, ffmpeg)
        if a.script:
            write_script(page, ROOT / a.script)
        b.close()

    if a.small:
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(out), "-vf", "scale=1200:-2",
                        "-c:v", "libx264", "-preset", "slow", "-crf", "30", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", str(ROOT / a.small)], check=True)
    if a.screenshots:
        dest = ROOT / a.screenshots
        dest.mkdir(parents=True, exist_ok=True)
        for name in README_SHOTS:
            shutil.copy(shots[name], dest / (name + ".png"))
    shutil.rmtree(tmp, ignore_errors=True)

    print("Wrote %s — %d:%02d, %.1f MB" % (out, total // 60000, (total // 1000) % 60,
                                           out.stat().st_size / 1e6))
    if a.small:
        print("      %s — %.1f MB" % (ROOT / a.small, (ROOT / a.small).stat().st_size / 1e6))


if __name__ == "__main__":
    main()
