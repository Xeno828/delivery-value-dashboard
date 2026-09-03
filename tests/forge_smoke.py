#!/usr/bin/env python3
"""
The deployed app, checked from inside the tenant.

    python3 tests/forge_smoke.py            # headless once a session exists
    python3 tests/forge_smoke.py --headed   # watch it
    make forge-smoke

A deploy proves the manifest is valid and the bundle builds. It proves nothing
about what a reader sees inside Jira: whether the bridge answered, whether the
page opened in the refusal state or with the board's own figures, whether the
help layer that was rebuilt for the keyboard survived the split build and the
iframe's content-security policy. Those are only visible from inside the
iframe, and the iframe is cross-origin — a browser extension's script cannot
reach it, which is why the Forge route was validated by hand for two weeks.

A WebDriver-class tool can, because it drives the browser rather than running
inside the page. Playwright is what the other suites already use, so it is
what this one uses: it opens the project page on the dev site, finds the frame
in which the dashboard actually rendered, and asserts inside it.

**The login is yours.** Nothing here holds a password. The first run opens a
visible browser with its own profile under `.forge-smoke-profile/` — which is
git-ignored beside `.env` and `.jira-oauth.json`, because it holds the
Atlassian session cookies — and waits for you to sign in. Later runs reuse
the session headlessly until Atlassian expires it, at which point the window
opens again.

Not part of `make test`: it needs a deployed environment and a person's
session, and a suite that cannot run in CI must not look like one that did.
"""

import argparse
import os
import pathlib
import re
import stat
import sys
import time

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROFILE = ROOT / ".forge-smoke-profile"
SHOT = ROOT / "tests" / "forge-last-run.png"

# The development environment, and the site it is installed on. Override with
# the flags below; the ids come from `forge environments list` and the app id
# is read from the manifest so a re-registered app needs no edit here.
SITE = "one-atlas-zppb.atlassian.net"
PROJECT = "MOBL"
ENV_ID = "1943c780-3538-4a94-b837-0f7f132d4768"
LOGIN_WAIT_S = 8 * 60
CLAUSE = "the evidence is absent, not noisy"

failures = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  — " + str(detail)) if detail else ""), flush=True)
    if not ok:
        failures.append(name)


def app_id():
    m = re.search(r"app/([0-9a-f-]{36})", (ROOT / "forge" / "manifest.yml").read_text())
    if not m:
        sys.exit("forge/manifest.yml carries no app id — run `forge register` first")
    return m.group(1)


def signed_in_page(ctx, site):
    """The tab that is on the site and past the login, if any.

    Any tab, not the first: an identity provider can finish the sign-in in a
    tab or a popup of its own and leave the original where it was.
    """
    for p in ctx.pages:
        u = p.url
        if u.startswith("https://" + site + "/") and "/login" not in u:
            return p
    return None


def find_app_frame(page, timeout_s):
    """The frame the dashboard rendered in: the one with the grid in it.

    Located by content rather than by hostname, because the CDN the Custom UI
    resource is served from is Forge's to change and the grid's id is ours.
    """
    end = time.time() + timeout_s
    while time.time() < end:
        for f in page.frames:
            try:
                if f.evaluate("() => !!document.getElementById('grid')"):
                    return f
            except Exception:
                pass
        time.sleep(0.5)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--site", default=SITE)
    ap.add_argument("--project", default=PROJECT)
    ap.add_argument("--env-id", default=ENV_ID)
    ap.add_argument("--headed", action="store_true", help="show the browser even when a session exists")
    ap.add_argument("--no-login", action="store_true", help="fail rather than wait for a sign-in")
    a = ap.parse_args()

    PROFILE.mkdir(exist_ok=True)
    os.chmod(PROFILE, stat.S_IRWXU)
    aid = app_id()
    urls = ["https://%s/jira/software/c/projects/%s/apps/%s/%s" % (a.site, a.project, aid, a.env_id),
            "https://%s/jira/software/projects/%s/apps/%s/%s" % (a.site, a.project, aid, a.env_id)]

    console = []
    with sync_playwright() as pw:
        def launch(headless):
            ctx = pw.chromium.launch_persistent_context(
                str(PROFILE), headless=headless, viewport={"width": 1440, "height": 1000})
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.on("console", lambda m: console.append((m.type, m.location.get("url", ""), m.text)))
            page.on("pageerror", lambda e: console.append(("pageerror", "", str(e))))
            return ctx, page

        ctx, page = launch(headless=not a.headed)
        page.goto(urls[0], wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        if not signed_in_page(ctx, a.site):
            if a.no_login:
                ctx.close()
                sys.exit("not signed in to %s and --no-login was given" % a.site)
            if not a.headed:
                ctx.close()
                ctx, page = launch(headless=False)
                page.goto(urls[0], wait_until="domcontentloaded")
            print("\n  Sign in to %s in the browser window that just opened." % a.site, flush=True)
            print("  Waiting up to %d minutes; the session is kept in %s for next time.\n"
                  % (LOGIN_WAIT_S // 60, PROFILE.relative_to(ROOT)), flush=True)
            end = time.time() + LOGIN_WAIT_S
            last = 0
            while time.time() < end and not signed_in_page(ctx, a.site):
                time.sleep(1)
                if time.time() - last > 30:
                    last = time.time()
                    print("  waiting · tabs: %s" % [p.url[:80] for p in ctx.pages], flush=True)
            found = signed_in_page(ctx, a.site)
            if not found:
                page.screenshot(path=str(SHOT))
                ctx.close()
                sys.exit("no sign-in within %d minutes; the last tab state is in %s"
                         % (LOGIN_WAIT_S // 60, SHOT.relative_to(ROOT)))
            if found is not page:
                page = found
                page.on("console", lambda m: console.append((m.type, m.location.get("url", ""), m.text)))
                page.on("pageerror", lambda e: console.append(("pageerror", "", str(e))))
            print("  Signed in.\n", flush=True)

        print("the app page")
        frame = None
        for u in urls:
            if not page.url.startswith(u):
                page.goto(u, wait_until="domcontentloaded")
            frame = find_app_frame(page, 45)
            if frame:
                break
        check("the project page holds a frame with the dashboard in it", frame is not None,
              page.url if frame is None else frame.url)
        if frame is None:
            page.screenshot(path=str(SHOT), full_page=True)
            ctx.close()
            report()
        origin = re.match(r"https?://[^/]+", frame.url).group(0)
        check("the dashboard is served from a different origin than the Jira page",
              not frame.url.startswith("https://" + a.site), frame.url[:90])

        # The bridge answers after the page has rendered its seed. Wait for
        # either outcome — the board's figures, or the page's refusal — and
        # then for the context bar, which only the bridge can fill.
        state = frame.evaluate("""() => new Promise(done => {
          const t0 = Date.now();
          const look = () => {
            const kpis = document.querySelectorAll('#kpis .kpi').length;
            const refusal = !!document.querySelector('#kpis .refusal');
            const ctx = !document.getElementById('ctxbar').classList.contains('hidden');
            if ((kpis === 8 || refusal) && (ctx || Date.now() - t0 > 60000))
              return done({kpis, refusal, ctx, foot: document.getElementById('foot').innerText});
            if (Date.now() - t0 > 90000) return done({kpis, refusal, ctx, foot: document.getElementById('foot').innerText, timeout: true});
            setTimeout(look, 500);
          };
          look();
        })""")
        print("\nthe page, inside the frame")
        check("the KPI band settled into one state: eight tiles or one refusal",
              not state.get("timeout") and (state["kpis"] == 8) != state["refusal"], state)
        check("the context bar is showing, which only the bridge can fill", state["ctx"])
        print("  state: %s · %s" % ("eight KPI tiles" if state["kpis"] == 8 else "the refusal", state["foot"].split("\n")[0][:120]))
        if state["refusal"]:
            txt = frame.text_content("#kpis .refusal") or ""
            check("the refusal ends with its clause, untrimmed", CLAUSE in txt, txt[-70:])
        stray = frame.evaluate("c => [...document.querySelectorAll('.note')].filter(n => n.textContent.includes(c) && !n.closest('.refusal')).length", CLAUSE)
        check("no refusal is set in the note style", stray == 0, stray)

        # The iframe forbids inline style; a rule that did not reach the page
        # would leave the callout as plain text and the KPI bars unpainted.
        painted = frame.evaluate("""() => {
          const r = document.querySelector('.refusal, .fc-refusal');
          const rs = r ? getComputedStyle(r) : null;
          return { callout: rs ? rs.borderLeftWidth : null,
                   unpainted: [...document.querySelectorAll('[style]')].filter(e => e.style.length === 0).length };
        }""")
        check("the stylesheet reached the frame (a callout carries its 3px rule)",
              painted["callout"] in (None, "3px"), painted)
        check("every style attribute reached its element under the iframe's policy",
              painted["unpainted"] == 0, painted["unpainted"])

        print("\nthe help layer, without a pointer")
        marks = frame.eval_on_selector_all(".info", "n => n.map(e => e.tagName + ':' + (e.getAttribute('aria-label') || ''))")
        check("every help mark is a button named for what it explains",
              len(marks) >= 15 and all(m.startswith("BUTTON:About ") for m in marks), marks[:3])
        # Give the frame focus before asking what focus does inside it: the
        # first focus() into a cross-origin frame lands before the frame is the
        # focused one, and its focus event can go unfired. The skip link is a
        # harmless first stop.
        frame.focus("a.skip")
        frame.wait_for_timeout(200)
        frame.focus("#c-exec .info")
        frame.wait_for_timeout(300)
        tip_on = lambda: frame.evaluate("() => document.getElementById('tip').style.opacity === '1'")
        check("focusing a help mark shows its explanation",
              tip_on() and "What it is" in (frame.text_content("#tip") or ""), (frame.text_content("#tip") or "")[:60])
        check("and the tooltip is announced as the mark's description",
              frame.get_attribute("#c-exec .info", "aria-describedby") == "tip")
        frame.press("#c-exec .info", "Escape")
        frame.wait_for_timeout(200)
        check("Escape dismisses it", not tip_on())
        frame.focus("#t-health")
        frame.wait_for_timeout(300)
        check("the health chip is reachable and explains itself on focus",
              frame.evaluate("() => document.activeElement.id") == "t-health" and tip_on(),
              (frame.text_content("#tip") or "")[:60])
        frame.press("#t-health", "Escape")
        frame.wait_for_timeout(200)
        check("Escape dismisses the chip's explanation too", not tip_on(),
              frame.evaluate("() => [document.activeElement.id, document.getElementById('tip').style.opacity, (document.getElementById('tip').textContent || '').slice(0, 40)]"))
        check("the page has one main landmark and a skip link to the report",
              frame.evaluate("() => document.querySelectorAll('main').length === 1 && "
                             "document.querySelector('a.skip') && document.querySelector('a.skip').getAttribute('href') === '#grid'"))
        check("every table header declares its scope",
              frame.evaluate("() => [...document.querySelectorAll('table.tv th')].every(t => ['col','row'].includes(t.getAttribute('scope')))"))

        print("\nthe frame's own console")
        # The page writes style attributes and re-applies them through the CSSOM
        # where a policy discards them (src/app.js, "inline style, re-applied"),
        # so a strict host logs one violation per attribute by design. Counted
        # and printed rather than failed on, and never folded into the count of
        # everything else: a script error hiding among them is what this is for.
        ours = [c for c in console if c[0] in ("error", "pageerror") and (c[1].startswith(origin) or c[0] == "pageerror")]
        csp = [c for c in ours if "Content Security Policy" in c[2] and "inline style" in c[2]]
        errs = [c for c in ours if c not in csp]
        print("  %d inline-style policy report(s) from the frame, expected under a strict host" % len(csp))
        check("no other errors from the dashboard's frame", not errs, [e[2][:160] for e in errs[:3]])

        check("nothing is left open when the checks end", not tip_on(),
              frame.evaluate("() => [document.activeElement.id, document.getElementById('tip').style.opacity]"))
        page.screenshot(path=str(SHOT), full_page=False)
        print("\n  screenshot: %s" % SHOT.relative_to(ROOT))
        ctx.close()
    report()


def report():
    print()
    if failures:
        print("%d check(s) failed: %s" % (len(failures), ", ".join(failures)))
        sys.exit(1)
    print("all Forge smoke checks passed")
    sys.exit(0)


if __name__ == "__main__":
    main()
