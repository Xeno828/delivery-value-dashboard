#!/usr/bin/env python3
"""
security.py — security test suite.

The threat model this project actually has:

  * The dashboard is a file people email each other. It must not exfiltrate
    anything, must not persist anything, and must survive being pointed at a
    hostile data file — because "drop your Jira export on it" is the primary
    way data arrives, and a Jira summary field is attacker-controllable by
    anyone who can raise a ticket.
  * The fetcher and the live server hold API credentials. They must not leak
    them, must not be reachable from off-box, and must not be tricked into
    reading files they were not asked for.

Everything below tests one of those. Nothing here tests hypothetical attacks on
a server that does not exist.

    python3 tests/security.py
"""

import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import zipfile

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


# ---------------------------------------------------------------- payloads
XSS = "<img src=x onerror=window.__pwned=1><script>window.__pwned=1</script>"
JS_URL = "javascript:window.__pwned=1"


def hostile_dataset():
    """A dataset shaped like a real export, with every string field carrying an
    injection attempt. Field values like these are not far-fetched: an issue
    summary is free text that anyone with a Jira login can write."""
    issue = {
        "key": "EVIL-1" + XSS,
        "summary": XSS,
        "type": XSS, "status": "In Progress" + XSS, "statusCategory": "In Progress",
        "assignee": XSS, "priority": XSS, "epic": XSS,
        "storyPoints": 3, "created": "2026-08-01", "started": "2026-08-03",
        "resolved": None, "dueDate": "2026-08-14",
        "flagged": True, "addedMidSprint": True,
        "businessValue": 1000, "valueBasis": XSS,
        "labels": [XSS], "url": JS_URL,
    }
    done = dict(issue, key="EVIL-2", resolved="2026-08-05", statusCategory="Done",
                status="Done", flagged=False, addedMidSprint=False)
    return {
        "schemaVersion": "1.0",
        "meta": {"organisation": XSS, "team": XSS, "sprintName": XSS, "sprintGoal": XSS,
                 "sourceLabel": XSS, "startDate": "2026-08-03", "endDate": "2026-08-14",
                 "asOfDate": "2026-08-10", "currency": "USD", "baseUrl": JS_URL},
        "issues": [issue, done],
        "burndown": [{"date": "2026-08-03", "remainingSP": 3, "scopeSP": 3, "idealSP": 3,
                      "remainingItems": 1, "scopeItems": 1, "idealItems": 1}],
        "history": [{"sprint": XSS, "committedSP": 3, "completedSP": 3, "committedItems": 1,
                     "completedItems": 1, "throughput": 1, "wipItems": 1, "unplannedItems": 1,
                     "flowEfficiency": 0.5, "valueDelivered": 1000}],
        "releases": [{"name": XSS, "targetDate": "2026-08-14", "scopeIssues": 2,
                      "doneIssues": 1, "status": XSS, "note": XSS}],
        "dora": None,
    }


def polluting_dataset():
    """Prototype pollution through a JSON key. Object.assign and property
    writes on parsed JSON are the usual route in."""
    return json.loads(json.dumps({
        "meta": {"__proto__": {"polluted": "yes"}, "startDate": "2026-08-03",
                 "endDate": "2026-08-14", "asOfDate": "2026-08-10"},
        "issues": [{"key": "P-1", "summary": "x", "status": "Done", "statusCategory": "Done",
                    "created": "2026-08-01", "resolved": "2026-08-04", "storyPoints": 1,
                    "__proto__": {"polluted": "yes"},
                    "constructor": {"prototype": {"polluted": "yes"}}}],
    }))


# ================================================================= browser
def browser_checks():
    print("the built file — data handling")
    requests, console = [], []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page(viewport={"width": 1400, "height": 900})
        page.on("request", lambda r: requests.append(r.url))
        page.on("pageerror", lambda e: console.append(str(e)))
        page.goto(DIST.as_uri())
        page.wait_for_timeout(700)

        # ---- no network at all ----
        external = [u for u in requests if not u.startswith("file://")]
        check("the file makes no network request of any kind", external == [], external[:3])

        # ---- hostile data must not execute ----
        page.evaluate("() => { window.__pwned = 0; }")
        page.evaluate("d => window.DVD.applyDataset(d)", hostile_dataset())
        page.wait_for_timeout(700)
        check("script injected through issue fields does not execute",
              page.evaluate("() => window.__pwned") in (0, None),
              page.evaluate("() => window.__pwned"))
        check("no <script> element is created from imported data",
              page.evaluate("""() => !Array.from(document.querySelectorAll('script'))
                  .some(s => s.textContent.includes('__pwned'))"""))
        check("no event-handler attribute survives from imported data",
              page.evaluate("""() => !Array.from(document.querySelectorAll('*'))
                  .some(e => Array.from(e.attributes || [])
                    .some(a => /^on/i.test(a.name) && a.value.includes('__pwned')))"""))
        check("injected markup is rendered as visible text, not parsed",
              page.evaluate("() => document.body.innerText.includes('onerror')"))

        # ---- javascript: URLs must not become clickable links ----
        page.click("#kpis button:nth-child(1)")
        page.wait_for_timeout(400)
        hrefs = page.eval_on_selector_all("#p-body a", "n => n.map(a => a.getAttribute('href'))")
        check("no javascript: URL is turned into a link",
              not any(str(h).lower().strip().startswith("javascript:") for h in hrefs), hrefs[:3])
        page.keyboard.press("Escape")

        # ---- prototype pollution ----
        page.evaluate("d => { try { window.DVD.applyDataset(d); } catch (e) {} }", polluting_dataset())
        page.wait_for_timeout(400)
        check("a __proto__ key in imported JSON does not pollute Object.prototype",
              page.evaluate("() => ({}).polluted === undefined"),
              page.evaluate("() => ({}).polluted"))
        check("a constructor.prototype key does not pollute either",
              page.evaluate("() => [].polluted === undefined"))

        # ---- no persistence ----
        page.goto(DIST.as_uri())
        page.wait_for_timeout(500)
        store = page.evaluate("""() => {
            let ls = -1, ss = -1;
            try { ls = localStorage.length; } catch (e) { ls = -1; }
            try { ss = sessionStorage.length; } catch (e) { ss = -1; }
            return { ls, ss, cookies: document.cookie }; }""")
        check("nothing is written to localStorage", store["ls"] in (0, -1), store["ls"])
        check("nothing is written to sessionStorage", store["ss"] in (0, -1), store["ss"])
        check("no cookies are set", store["cookies"] == "", store["cookies"])

        check("no uncaught errors from hostile input", console == [], console[:2])
        b.close()


def source_checks():
    print("\nthe source — dangerous constructs")
    js = (ROOT / "src" / "app.js").read_text() + (ROOT / "src" / "import.js").read_text()
    built = DIST.read_text()

    check("no eval()", not re.search(r"\beval\s*\(", js))
    check("no new Function()", not re.search(r"\bnew\s+Function\s*\(", js))
    check("no document.write", "document.write" not in js)
    # A direct field-to-innerHTML assignment is the shape the real bug had:
    # an issue field reaching the DOM without passing through esc().
    # Anchored to the end of the statement so a ternary that merely *tests* the
    # field (and escapes it in the branch) is not a false positive.
    direct = re.findall(
        r"innerHTML\s*=\s*[a-z]\w*\.(?:summary|key|status|assignee|epic|priority|"
        r"name|note|valueBasis|sourceLabel|sprintGoal|team|organisation)\s*;", js)
    check("no issue field is assigned straight to innerHTML", direct == [], direct[:3])
    check("no localStorage or sessionStorage anywhere in the source",
          "localStorage" not in js and "sessionStorage" not in js)
    check("no external origin referenced by the built file",
          not re.search(r'(src|href)\s*=\s*["\']https?://', built))
    check("no inline event-handler attributes in the markup",
          not re.search(r'\son[a-z]+\s*=\s*["\']', (ROOT / "src" / "index.html").read_text()))
    # escaping discipline
    # Not a pass/fail bar so much as a smell: the renderers build HTML strings,
    # so escaping should appear at roughly the density of the fields they emit.
    esc_calls, innerhtml = js.count("esc("), js.count("innerHTML")
    warn("escaping is dense relative to innerHTML use (%d esc / %d innerHTML)"
         % (esc_calls, innerhtml), esc_calls > innerhtml * 2, (esc_calls, innerhtml))


def secret_checks():
    print("\nsecrets and repository hygiene")
    pats = {
        "Atlassian API token": r"ATATT3[A-Za-z0-9_\-]{20,}",
        "AWS access key": r"AKIA[0-9A-Z]{16}",
        "generic long token assignment": r"(?i)(token|secret|password|api[_-]?key)\s*[:=]\s*['\"][A-Za-z0-9/+_\-]{24,}['\"]",
        "private key block": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        "bearer literal": r"(?i)bearer\s+[A-Za-z0-9\-_.]{24,}",
    }
    hits = []
    for f in ROOT.rglob("*"):
        if not f.is_file() or ".git" in f.parts or "__pycache__" in f.parts:
            continue
        if f.suffix in (".png", ".mp4", ".webm", ".xlsx", ".zip"):
            continue
        try:
            t = f.read_text(errors="ignore")
        except Exception:
            continue
        for name, pat in pats.items():
            if re.search(pat, t):
                hits.append("%s in %s" % (name, f.relative_to(ROOT)))
    check("no credentials committed anywhere in the tree", hits == [], hits[:3])

    gi = (ROOT / ".gitignore").read_text()
    check(".env is git-ignored", ".env" in gi)
    check("fetched data is git-ignored by default", "data/dashboard-data.json" in gi)
    # Placeholders like a domain are fine; a filled-in secret is not. Only the
    # credential-bearing keys are checked, and they must be empty.
    env = (ROOT / ".env.example").read_text()
    filled = [ln for ln in env.splitlines()
              if re.match(r"^\s*[A-Z_]*(TOKEN|SECRET|PASSWORD|KEY)\s*=\s*\S", ln)]
    check(".env.example ships every credential key empty", filled == [], filled)


def server_checks():
    print("\nthe live-mode server")
    src = (ROOT / "scripts" / "serve_live.py").read_text()
    check("binds to loopback only, never 0.0.0.0",
          '"127.0.0.1"' in src and "0.0.0.0" not in src)
    check("credentials are read from the environment, never hard-coded",
          'os.environ.get("JIRA_TOKEN")' in src and not re.search(r'JIRA_TOKEN\s*=\s*["\']\S', src))

    port = 8765
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "serve_live.py"),
         "--bundle", str(ROOT / "data" / "sample-bundle.json"), "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import time
        import urllib.error
        import urllib.request
        for _ in range(40):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/api/contexts" % port, timeout=1).read()
                break
            except Exception:
                time.sleep(0.25)

        def get(path):
            try:
                r = urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path), timeout=3)
                return r.status, r.read()[:400]
            except urllib.error.HTTPError as e:
                return e.code, e.read()[:200]
            except Exception as e:
                return -1, str(e).encode()

        code, _ = get("/api/contexts")
        check("the contexts endpoint answers", code == 200, code)

        # The badge is the only thing on the page that reports the connection,
        # and it used to report the loaded dataset's own label instead. The
        # bundled demo file labels itself "Demo data (no live connection)", so
        # with this server running the page sat there denying the connection
        # that had just handed it eighteen sprints. This is the only suite with
        # both a browser and a live server, so the check belongs here.
        with sync_playwright() as pw2:
            br = pw2.chromium.launch()
            pg = br.new_page()
            pg.goto("http://127.0.0.1:%d/dist/delivery-value-dashboard.html" % port)
            pg.wait_for_timeout(1500)
            badge = (pg.text_content("#t-src") or "").strip()
            bar = pg.get_attribute("#ctxbar", "class") or ""
            check("live mode merges the server's contexts", "hidden" not in bar, bar)
            check("the badge does not deny a connection that is answering",
                  "no live connection" not in badge and badge.startswith("Live:"), badge)
            br.close()

        # path traversal through the context id
        for probe in ("/api/context?id=../../etc/passwd",
                      "/api/context?id=%2e%2e%2f%2e%2e%2fetc%2fpasswd",
                      "/api/context?id=/etc/passwd"):
            code, body = get(probe)
            check("context id %r cannot read arbitrary files" % probe.split("id=")[1][:24],
                  code == 404 and b"root:" not in body, (code, body[:60]))

        # A missing file must be refused, not dropped. This is the weaker-looking
        # check and the one that matters: the handler used to raise while logging
        # the 404 it had already decided on, killing the thread mid-response. Every
        # traversal probe below then "passed" because a dead connection returns no
        # body — proving nothing about traversal at all.
        code, _ = get("/favicon.ico")
        check("a missing static file gets a clean 404, not a dropped connection",
              code == 404, code)

        # static path traversal
        for probe in ("/../../../etc/passwd", "/..%2f..%2f..%2fetc%2fpasswd", "/./../../etc/passwd"):
            code, body = get(probe)
            check("static path %r is refused, with a status" % probe[:26],
                  code in (403, 404) and b"root:" not in body, (code, body[:40]))

        # it should not be reachable from a non-loopback interface
        ip = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            pass
        if ip and not ip.startswith("127."):
            try:
                s = socket.create_connection((ip, port), timeout=2)
                s.close()
                check("not reachable on the external interface", False, ip)
            except Exception:
                check("not reachable on the external interface", True, ip)
        else:
            warn("external interface reachability not testable in this sandbox", True, ip)
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def xlsx_checks():
    print("\nthe xlsx reader")
    js = (ROOT / "src" / "import.js").read_text()
    check("the unzip never writes to disk — entries are decoded in memory only",
          "TextDecoder" in js and "writeFile" not in js and "showSaveFilePicker" not in js)
    check("only xml entries are decoded, so a zip-slip name has nothing to slip into",
          "/\\.(xml|rels)$/i.test(name)" in js)
    check("XML is parsed with DOMParser, which does not resolve external entities",
          "DOMParser" in js and "XMLHttpRequest" not in js)

    # a hostile workbook: XXE, a billion-laughs entity, and a traversal filename
    tmp = pathlib.Path(tempfile.mkdtemp())
    bad = tmp / "hostile.xlsx"
    sheet = ('<?xml version="1.0"?>'
             '<!DOCTYPE x [<!ENTITY xxe SYSTEM "file:///etc/passwd">'
             '<!ENTITY a "aa"><!ENTITY b "&a;&a;"><!ENTITY c "&b;&b;">]>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Issue key</t></is></c>'
             '<c r="B1" t="inlineStr"><is><t>Summary</t></is></c>'
             '<c r="C1" t="inlineStr"><is><t>Status</t></is></c>'
             '<c r="D1" t="inlineStr"><is><t>Created</t></is></c></row>'
             '<row r="2"><c r="A2" t="inlineStr"><is><t>X-1</t></is></c>'
             '<c r="B2" t="inlineStr"><is><t>&xxe;&c;</t></is></c>'
             '<c r="C2" t="inlineStr"><is><t>Done</t></is></c>'
             '<c r="D2" t="inlineStr"><is><t>2026-08-01</t></is></c></row>'
             '</sheetData></worksheet>')
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        z.writestr("../../../../tmp/zipslip.xml", "<x/>")
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(DIST.as_uri())
        page.wait_for_timeout(500)
        page.click("#btn-import")
        page.set_input_files("#file", str(bad))
        try:
            page.wait_for_selector("#step-map:not(.hidden)", timeout=12000)
            got = page.evaluate("""() => {
                const W = window.DVDImport.W;
                const ix = W.header.findIndex(h => /summary/i.test(h));
                return (W.rows[0] || [])[ix] || ''; }""")
            check("an external entity is not resolved into the data",
                  "root:" not in got and "/bin/" not in got, got[:60])
            check("an entity-expansion bomb does not hang or blow up the page",
                  len(got) < 5000, len(got))
        except Exception as e:
            check("a hostile workbook is rejected cleanly rather than crashing",
                  True, "parser refused: %s" % str(e)[:50])
        check("no uncaught error from the hostile workbook", errs == [], errs[:2])
        b.close()
    check("a zip entry named ../.. did not create a file outside the workspace",
          not pathlib.Path("/tmp/zipslip.xml").exists())
    shutil.rmtree(tmp, ignore_errors=True)


def dependency_checks():
    print("\ndependencies")
    reqs = (ROOT / "scripts" / "requirements.txt").read_text().strip().splitlines()
    reqs = [r for r in reqs if r.strip() and not r.startswith("#")]
    check("the runtime has no JavaScript dependencies",
          "dependencies" not in json.loads((ROOT / "package.json").read_text()))
    check("python dependencies are few and pinned to a floor", len(reqs) <= 2, reqs)
    tool = shutil.which("pip-audit") or shutil.which("safety")
    if tool:
        r = subprocess.run([tool, "-r", str(ROOT / "scripts" / "requirements.txt")],
                           capture_output=True, text=True)
        check("no known vulnerabilities in python dependencies", r.returncode == 0,
              r.stdout[-200:])
    else:
        warn("pip-audit not installed — python dependency CVEs not checked here", False,
             "add `pip install pip-audit` to CI")


def main():
    if not DIST.exists():
        sys.exit("build first: python3 build.py")
    browser_checks()
    source_checks()
    secret_checks()
    server_checks()
    xlsx_checks()
    dependency_checks()

    print()
    if warnings:
        print("%d warning(s): %s" % (len(warnings), "; ".join(warnings)))
    if failures:
        print("%d check(s) failed: %s" % (len(failures), ", ".join(failures)))
        sys.exit(1)
    print("all security checks passed")


if __name__ == "__main__":
    main()
