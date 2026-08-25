#!/usr/bin/env python3
"""
test_service.py — the hosted calculator.

Three things have to hold, and the first is the one the whole design rests on:

  1. The projection loses nothing. Forge sends dates and status categories and
     keeps the issue titles inside the tenant. If a calculation quietly needs a
     field the projection drops, the Forge build returns a different number
     from the CLI and nothing says so.
  2. The service computes nothing. Its answer must equal the tool called
     directly, or there are two implementations again and the whole point of
     hosting the Python is gone.
  3. It refuses rather than half-answers. Bad auth, free text, a bad config, an
     oversized payload — each is a sentence and no number.

Needs nothing but Python 3.

    python3 tests/test_service.py
"""

import datetime
import json
import pathlib
import re
import secrets
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent" / "tools"))
sys.path.insert(0, str(ROOT / "service"))
# The loopback transport's own module, imported rather than only launched, so
# the window it builds can be compared against the resolver's directly.
sys.path.insert(0, str(ROOT / "scripts"))

import app as SVC        # noqa: E402
import forecast as FC    # noqa: E402
import orgconfig as OC   # noqa: E402
import serve_live as LIVE  # noqa: E402

failures = []
#: Generated per run rather than written down. A literal token in a test file is
#: indistinguishable from a real one to a secret scanner — the security suite
#: flagged exactly that — and a test that needs a hard-coded credential is a
#: test teaching a bad habit.
SECRET = secrets.token_hex(16)
AUTH = {"Authorization": "Bearer " + SECRET}


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  — " + str(detail)) if detail else ""))
    if not ok:
        failures.append(name)


def call(method, path, body=None, headers=None):
    raw = json.dumps(body).encode() if body is not None else b""
    return SVC.handle(method, path, raw, headers if headers is not None else AUTH)


def team_payload(path="data/sample-bundle.json"):
    """One team's slice, projected — exactly what the Forge resolver sends."""
    full = json.loads((ROOT / path).read_text())
    ctx = full["contexts"][0]
    ids = {c["id"] for c in full["contexts"]
           if c.get("projectKey") == ctx.get("projectKey")
           and c.get("boardId") == ctx.get("boardId")}
    team = [i for i in full["issues"] if i.get("contextId") in ids]
    meta = {"asOfDate": ctx.get("asOfDate"), "startDate": ctx.get("startDate"),
            "endDate": ctx.get("endDate"), "workingDays": ctx.get("workingDays")}
    return full, team, meta


def project(issues):
    return [{k: v for k, v in i.items()
             if k in SVC.CALC_FIELDS and v is not None} for i in issues]


# =====================================================================
def test_projection_loses_nothing():
    """The measurement the architecture is built on, asserted rather than recalled.

    Everything a calculation reads survives the projection. The only fields that
    may differ are the ones item_risk echoes back for display, which Forge
    re-attaches by key from the copy it never sent.
    """
    ECHOED = {"summary", "assignee"}

    for path in ("data/sample-bundle.json", "data/sample-multi-sprint.json"):
        full = json.loads((ROOT / path).read_text())
        thin = dict(full)
        thin["issues"] = project(full["issues"])

        a = FC.build(json.loads(json.dumps(full)))
        b = FC.build(json.loads(json.dumps(thin)))

        diffs = []

        def walk(x, y, p=""):
            if isinstance(x, dict) and isinstance(y, dict):
                for k in set(x) | set(y):
                    walk(x.get(k), y.get(k), p + "/" + str(k))
            elif isinstance(x, list) and isinstance(y, list):
                if len(x) != len(y):
                    diffs.append("%s length %d vs %d" % (p, len(x), len(y)))
                for i, (u, v) in enumerate(zip(x, y)):
                    walk(u, v, "%s[%d]" % (p, i))
            elif x != y and p.rsplit("/", 1)[-1] not in ECHOED:
                diffs.append("%s: %r != %r" % (p, x, y))

        walk(a, b)
        check("every computed figure survives the projection — %s" % path.split("/")[-1],
              diffs == [], diffs[:3])

    # And the payload is worth sending: bounded by a team, not by the customer.
    full, team, meta = team_payload()
    kb = len(json.dumps({"dataset": {"issues": project(team), "meta": meta}},
                        separators=(",", ":"))) / 1024.0
    check("one team's call stays small", kb < 64, "%.1f KB" % kb)


def test_field_lists_agree():
    """The projection exists in two languages and they must not drift.

    forge/src/index.js decides what leaves the tenant; service/app.py decides
    what is accepted. If the resolver's list grows a field the service refuses,
    every Forge call fails. If the service's list grows one the resolver never
    sends, a figure silently changes.
    """
    js = (ROOT / "forge" / "src" / "index.js").read_text()

    def js_list(name):
        m = re.search(name + r"\s*=\s*\[(.*?)\];", js, re.S)
        return sorted(re.findall(r"'([^']+)'", m.group(1))) if m else None

    check("the resolver's CALC_FIELDS matches the service's",
          js_list("CALC_FIELDS") == sorted(SVC.CALC_FIELDS),
          {"js": js_list("CALC_FIELDS"), "py": sorted(SVC.CALC_FIELDS)})
    check("the resolver's NEVER_SEND matches what the service refuses",
          js_list("NEVER_SEND") == sorted(SVC.FREE_TEXT_FIELDS),
          {"js": js_list("NEVER_SEND"), "py": sorted(SVC.FREE_TEXT_FIELDS)})


def test_service_computes_nothing():
    """The service's answer is the tool's answer, to the byte."""
    full, team, meta = team_payload()
    ds = {"issues": project(team), "meta": meta, "orgConfig": full.get("orgConfig", {})}

    status, out = call("POST", "/v1/forecast", {"dataset": json.loads(json.dumps(ds))})
    direct = FC.build(json.loads(json.dumps(ds)))
    check("the forecast endpoint answers", status == 200, out.get("error"))
    check("the endpoint agrees with the tool called directly",
          json.dumps(out.get("result"), sort_keys=True) == json.dumps(direct, sort_keys=True))
    check("every answer names the calendar behind it",
          "working week" in (out.get("calendar") or ""), out.get("calendar"))

    status, facts = call("POST", "/v1/facts", {"dataset": json.loads(json.dumps(ds))})
    check("the facts endpoint answers", status == 200, facts.get("error"))
    check("the facts pack carries its own calendar too",
          "working week" in ((facts.get("result") or {}).get("meta", {}).get("calendar") or ""))


def test_config_travels_in_the_payload():
    """A different calendar is a different answer — including, sometimes, no answer."""
    # Enough history for both calendars to clear the evidence threshold.
    full = json.loads((ROOT / "data" / "sample-multi-sprint.json").read_text())
    base = {"issues": project(full["issues"]), "meta": full.get("meta", {})}

    _, five = call("POST", "/v1/forecast", {"dataset": dict(base, orgConfig={})})
    _, four = call("POST", "/v1/forecast",
                   {"dataset": dict(base, orgConfig={"workingWeek": ["mon", "tue", "wed", "thu"]})})
    check("a four-day week changes the answer",
          five["result"]["sprint_completion"]["percentiles"] !=
          four["result"]["sprint_completion"]["percentiles"],
          (five["result"]["sprint_completion"]["percentiles"][85],
           four["result"]["sprint_completion"]["percentiles"][85]))
    check("and the response says which calendar it used",
          "4-day working week" in four["calendar"], four["calendar"])

    # Worth pinning on its own: shortening the week shortens the sample, and a
    # team that had just enough completion history under five days can fall
    # under the threshold under four. The right answer there is the refusal,
    # not a thinner forecast — and it has to survive the trip through HTTP with
    # its sentence intact, because "not enough data" and "wide interval" are
    # different statements and only one of them is true.
    _, team, meta = team_payload()
    thin = {"issues": project(team), "meta": meta,
            "orgConfig": {"workingWeek": ["mon", "tue", "wed", "thu"]}}
    status, out = call("POST", "/v1/forecast", {"dataset": thin})
    sc = out["result"]["sprint_completion"]
    check("a shorter week can cross the refusal threshold, and the tool refuses",
          status == 200 and sc.get("available") is False, sc)
    check("the refusal reaches the caller unsoftened",
          "too little completion history" in (sc.get("reason") or ""), sc.get("reason"))
    check("a refusal still names the calendar that produced it",
          "4-day working week" in out["calendar"], out["calendar"])

    status, bad = call("POST", "/v1/forecast",
                       {"dataset": dict(base, orgConfig={"workingWeek": ["funday"]})})
    check("a bad config is refused, not corrected",
          status == 400 and "funday" in bad["error"], (status, bad.get("error")))


def test_refusals():
    full, team, meta = team_payload()
    ds = {"issues": project(team), "meta": meta}

    check("no auth is refused", call("POST", "/v1/forecast", {"dataset": ds}, {})[0] == 401)
    check("a wrong token is refused",
          call("POST", "/v1/forecast", {"dataset": ds},
               {"Authorization": "Bearer nope"})[0] == 401)
    check("health needs no auth", SVC.handle("GET", "/healthz", b"", {})[0] == 200)
    check("meta does need auth", SVC.handle("GET", "/v1/meta", b"", {})[0] == 401)

    # The one that matters: issue text must bounce, not be quietly dropped. A
    # service that accepts and ignores it is a service customer text reaches.
    leaky = json.loads(json.dumps(ds))
    leaky["issues"][0]["summary"] = "Fix the thing the CEO complained about"
    status, out = call("POST", "/v1/forecast", {"dataset": leaky})
    check("free text is refused rather than ignored",
          status == 400 and "summary" in out["error"], (status, out.get("error", "")[:60]))
    check("the refusal says the text was not stored",
          "was not stored" in out["error"], out["error"][:80])

    over = {"issues": [{"key": "K-%d" % i} for i in range(SVC.MAX_ISSUES + 1)], "meta": {}}
    status, out = call("POST", "/v1/forecast", {"dataset": over})
    check("an oversized payload is refused with the limit named",
          status == 413 and str(SVC.MAX_ISSUES) in out["error"], (status, out.get("error", "")[:60]))
    check("and says nothing was calculated rather than truncating",
          "Nothing was calculated" in out["error"], out["error"][:70])

    check("a bad route is a 404", call("POST", "/v1/nope", {})[0] == 404)
    check("GET on a POST route is a 405", call("GET", "/v1/forecast")[0] == 405)
    status, out = SVC.handle("POST", "/v1/forecast", b"{not json", AUTH)
    check("a malformed body is refused", status == 400 and "not JSON" in out["error"])
    status, out = call("POST", "/v1/sequence", {"dataset": ds, "asks": []})
    check("sequencing with no asks says why",
          status == 400 and "at least two" in out["error"], out.get("error", "")[:70])
    status, out = call("POST", "/v1/forecast", {"dataset": ds, "asOf": "last tuesday"})
    check("a malformed date is refused", status == 400 and "YYYY-MM-DD" in out["error"])


def test_no_internals_leak():
    """A traceback carries field values, and those are the customer's."""
    status, out = call("POST", "/v1/forecast", {"dataset": {"issues": "not a list"}})
    check("a broken payload gets a sentence, not a stack trace",
          status == 400 and "Traceback" not in json.dumps(out), out)
    status, out = call("POST", "/v1/ask", {"dataset": {"issues": [], "meta": {}},
                                           "ask": {"id": "X", "title": "t"}})
    check("an internal failure never returns a traceback",
          "Traceback" not in json.dumps(out) and "File \"" not in json.dumps(out), out)


def test_auth_seam_fails_closed():
    """Swapping the verifier must be a contained change that cannot fail open.

    The shared secret is a placeholder for Atlassian's invocation token. The one
    thing that must not happen during that swap is a configuration which serves
    requests without checking anything — a calculator that came up
    unauthenticated looks healthy to everything watching it.
    """
    import os
    saved = dict(os.environ)
    try:
        # the mode that is not written yet must stop the process, not degrade
        os.environ["SERVICE_AUTH"] = "forge-token"
        problem = SVC.startup_problem()
        check("an unimplemented auth mode refuses to start",
              problem and "not implemented" in problem, problem)
        check("and says where the specification lives",
              problem and "forge-deployment" in problem, problem)
        # even if the startup guard were removed, requests must not pass
        check("the unimplemented verifier refuses every request",
              SVC.authorised({"Authorization": "Bearer anything"}) is False)

        os.environ["SERVICE_AUTH"] = "typo-mode"
        problem = SVC.startup_problem()
        check("an unknown auth mode refuses to start", bool(problem), problem)
        check("an unknown auth mode refuses every request",
              SVC.authorised({"Authorization": "Bearer anything"}) is False)

        os.environ["SERVICE_AUTH"] = "shared-secret"
        os.environ.pop("SERVICE_SHARED_SECRET", None)
        check("the implemented mode still refuses to start with no secret",
              bool(SVC.startup_problem()))
        check("and refuses every request while unconfigured",
              SVC.authorised({"Authorization": "Bearer anything"}) is False)

        os.environ["SERVICE_SHARED_SECRET"] = SECRET
        check("a configured service may start", SVC.startup_problem() is None)
        check("every declared mode has a verifier",
              sorted(SVC.VERIFIERS) == sorted(SVC.AUTH_MODES), sorted(SVC.VERIFIERS))
    finally:
        os.environ.clear()
        os.environ.update(saved)


def test_forge_manifest_matches_the_code():
    """`forge lint` needs a CLI nobody here has. These are the parts of the
    manifest that have to agree with this repository, which a linter would not
    check anyway — it validates schema, not whether the scopes match the OAuth
    client or the egress rule points at a remote that exists."""
    man = (ROOT / "forge" / "manifest.yml").read_text()

    # Atlassian has two scope vocabularies — classic (`read:jira-work`) and
    # granular (`read:issue-details:jira`) — and the granular ones carry an extra
    # colon. The first version of this matched a single colon only, so every
    # granular scope was invisible to both checks below. `forge lint --fix` then
    # added two, and this passed while describing a manifest that no longer
    # existed. A write scope in the granular vocabulary would have sailed past it.
    scope_strs = sorted(set(re.findall(r"^\s+- ([a-z]+:[\w:-]+)$", man, re.M)))
    check("scopes are found in both vocabularies", len(scope_strs) >= 2, scope_strs)

    # The check that actually matters, and the one a reviewer will look for.
    check("every scope is read-only",
          all(s.startswith("read:") for s in scope_strs),
          [s for s in scope_strs if not s.startswith("read:")] or scope_strs)

    # An allow-list rather than parity with jira_auth.SCOPES: Forge wants
    # granular scopes and the 3LO client uses classic ones, so the two lists are
    # equivalent in intent and cannot be equal as strings. Adding a scope must be
    # a deliberate edit here, with a reason, rather than something a --fix run
    # can do quietly.
    ALLOWED = {
        "read:jira-work",                  # classic: read issues, boards, sprints
        "read:jira-user",                  # classic: display names on thecharts
        "read:issue-details:jira",         # granular equivalent of the issue read
        "read:board-scope:jira-software",  # granular: the board the resolver pages
        # The three the context picker cost, each demanded by `forge lint` for a
        # call the product cannot do without. read:project:jira enumerates the
        # boards of the project the page is open in — the scope this app removed
        # from the connection check rather than granted, taken now on its own
        # merits (ADR 0009). The other two are what GET
        # /board/{id}/sprint/{sid}/issue requires; that agile endpoint is
        # JQL-backed underneath, which is why a JQL read appears in an app that
        # issues no JQL of its own.
        "read:project:jira",
        "read:sprint:jira-software",
        "read:jql:jira",
    }
    check("no scope outside the reviewed allow-list",
          set(scope_strs) <= ALLOWED, sorted(set(scope_strs) - ALLOWED) or "none")

    declared = re.findall(r"^remotes:\s*$\n(?:\s+- key:\s*(\S+)\s*$)", man, re.M)
    referenced = re.findall(r"^\s+- remote:\s*(\S+)\s*$", man, re.M)
    check("the egress rule points at a remote that is declared",
          referenced and set(referenced) <= set(declared),
          {"declared": declared, "referenced": referenced})

    # `forge register` writes an app id into the manifest, and having one locally
    # is the correct state for anyone who has registered. Only committing it is
    # the problem — it hands everyone who clones the repository a manifest aimed
    # at one person's app. So check what is in HEAD, not what is on disk; the
    # first version of this asserted on the working tree and failed the suite for
    # exactly the person following the runbook properly.
    committed = subprocess.run(["git", "show", "HEAD:forge/manifest.yml"],
                               cwd=str(ROOT), capture_output=True, text=True)
    if committed.returncode == 0:
        clean = not re.search(r"^\s*id:\s*ari:", committed.stdout, re.M)
        check("no app id is committed", clean,
              "" if clean else "an app id is in HEAD — remove it before pushing")
    else:
        check("no app id is committed", True, "skipped: not a git checkout")

    # `forge lint` reports a missing resource, which reads as a broken manifest
    # rather than an unbuilt one. The path it wants and the path `make
    # forge-static` writes have to be the same string, or the next person spends
    # an afternoon on it.
    # Every declared resource, not just the first — the probe added a second and
    # a check that reads one would have gone quiet at exactly that moment.
    block = re.search(r"^resources:\s*$\n((?:(?:\s+#.*|\s+-?\s*\w+:.*)\n)+)", man, re.M)
    declared = ["forge/" + p.rstrip("/")
                for p in re.findall(r"^\s+path:\s*(\S+)\s*$", block.group(1), re.M)] if block else []
    check("the manifest declares resource paths", len(declared) >= 1, declared)

    mk = (ROOT / "Makefile").read_text()
    staged = re.findall(r"forge/static/\S*", mk)
    unstaged = [d for d in declared if not any(t.startswith(d) for t in staged)]
    check("the Makefile stages every path the manifest references",
          unstaged == [], {"unstaged": unstaged, "makefile": sorted(set(staged))})
    check("the staged resources are git-ignored, not committed twice",
          "forge/static/" in (ROOT / ".gitignore").read_text())

    # Forge's packager validates the literal <html> element in every static
    # resource's index.html. Browsers imply html/head/body when they are absent,
    # so a page that renders perfectly in a browser is rejected at deploy with
    # "Invalid index.html file" — which names the file and not the reason.
    for path in declared:
        src_dir = {"forge/static/dashboard/build": ROOT / "src",
                   "forge/static/probe": ROOT / "forge" / "probe"}.get(path)
        if src_dir is None:
            continue
        html = src_dir / "index.html"
        if not html.exists():
            continue
        text = html.read_text()
        ok = re.search(r"<html[\s>]", text, re.I) and re.search(r"</html>", text, re.I)
        check("%s has an explicit <html> root" % html.relative_to(ROOT), bool(ok),
              "" if ok else "Forge rejects a resource whose index.html omits it, "
                            "even though a browser renders it fine")


    # This used to assert the word SCAFFOLD appeared, so a manifest that looked
    # finished could not quietly be deployed. It stopped being true the moment
    # the app was registered, deployed and reading a tenant's own boards — and a
    # check that forces a false word into a file is worse than no check.
    #
    # What is still unfinished is nameable instead, and can be tied to the code
    # rather than to prose: the calculator has no host, `remotes[0].baseUrl`
    # says `.invalid`, and the forecast resolvers answer with a refusal that
    # says so. Asserted as a biconditional, because both directions are a bug —
    # a real baseUrl with the refusal still in place is a forecast tile that
    # stays dark for no reason anybody can see.
    idx = (ROOT / "forge" / "src" / "index.js").read_text()
    placeholder = ".invalid" in man
    refuses = "NO_CALCULATOR" in idx
    check("an unhosted calculator and a refusing forecast go together",
          placeholder == refuses,
          "manifest says unhosted=%s, resolver refuses=%s" % (placeholder, refuses))


def test_split_build_has_no_inline_assets():
    """A Forge Custom UI iframe blocks inline <style> and <script>, silently.

    The page renders with the browser's default stylesheet and none of its
    JavaScript runs, which reads as a broken build rather than a blocked one —
    it cost a deploy cycle to identify. `build.py --split` emits the same
    sources as linked files instead.

    The property asserted here is that the split output contains nothing inline
    and that its assets are byte-identical to src/. The second half is the one
    that matters: two assemblies of one set of sources, never two sources.
    """
    import shutil, subprocess, tempfile
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([sys.executable, "build.py", "--split", tmp],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=120)
        check("the split build runs", r.returncode == 0, (r.stderr or r.stdout)[-200:])
        if r.returncode != 0:
            return

        html = (pathlib.Path(tmp) / "index.html").read_text()
        inline_style = re.findall(r"<style[\s>]", html)
        # A script with no src, unless it is the JSON seed the page reads as data
        inline_script = re.findall(r"<script(?![^>]*(?:src=|type=\"application/json\"))", html)
        check("the split page has no inline <style>", inline_style == [], inline_style)
        check("the split page has no inline <script>", inline_script == [], inline_script)

        for name in ("styles.css", "app.js", "import.js"):
            emitted = pathlib.Path(tmp) / name
            check("%s is emitted alongside" % name, emitted.exists(),
                  "" if emitted.exists() else "missing from the split output")
            if emitted.exists():
                check("%s is byte-identical to src/" % name,
                      emitted.read_bytes() == (ROOT / "src" / name).read_bytes(),
                      "" if emitted.read_bytes() == (ROOT / "src" / name).read_bytes()
                      else "the split build is transforming a source, not just moving it")
            check("%s is linked from the page" % name, name in html,
                  "" if name in html else "emitted but never referenced")

        # The single-file build is the product and must stay inlined.
        dist = (ROOT / "dist" / "delivery-value-dashboard.html").read_text()
        check("the shipped single file is still fully inlined",
              "<style" in dist and 'href="styles.css"' not in dist)


def _serve_live_bodies(port=8731):
    """What `scripts/serve_live.py` really puts on the wire, for both routes.

    The envelope for `api/contexts` is built inside the request handler rather
    than by a backend method, so reading it means going through a socket. It is
    the contract, so it is read from where the contract lives.
    """
    import time
    import urllib.request

    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "serve_live.py"),
         "--bundle", "data/sample-bundle.json", "--port", str(port)],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        base = "http://127.0.0.1:%d/" % port
        deadline = time.time() + 20
        while True:
            try:
                with urllib.request.urlopen(base + "api/contexts", timeout=2) as r:
                    contexts = json.loads(r.read())
                break
            except Exception:
                if time.time() > deadline or proc.poll() is not None:
                    return None, None
                time.sleep(0.2)
        cid = contexts["contexts"][0]["id"]
        with urllib.request.urlopen(base + "api/context?id=" + cid, timeout=10) as r:
            context = json.loads(r.read())
        return contexts, context
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_the_two_transports_answer_the_same_shape():
    """One contract, two transports.

    The page reaches live mode either over a same-origin GET answered by
    `serve_live.py` or over `invoke()` answered by the Forge resolver. Which one
    it has must not change what it renders, so the *bodies* the two produce have
    to be the same shape — the status a reply carries is transport-level and
    each supplies its own, but the body is the product.

    The Forge half is `forge/src/jira.js`, kept free of the SDK and of the
    network precisely so it can be run here. `tests/forge_shapes.mjs` drives it
    over a synthetic Jira response and prints what the bridge would return.

    A key that appears on one side and not the other is the whole failure mode:
    the page reads `j.burndown` and gets undefined, draws nothing, and the
    difference is a chart that is missing rather than an error anybody sees.
    """
    node = subprocess.run(["node", str(ROOT / "tests" / "forge_shapes.mjs")],
                          cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    if node.returncode != 0:
        # Reported, never skipped silently. A parity check that quietly did not
        # run reads exactly like one that passed.
        check("the Forge shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    forge = json.loads(node.stdout)

    live_contexts, live_context = _serve_live_bodies()
    if live_contexts is None:
        check("the live server answers, to compare against", False,
              "serve_live.py did not come up")
        return

    check("api/contexts and the contexts resolver return the same envelope",
          sorted(live_contexts) == sorted(forge["contexts"]),
          {"live": sorted(live_contexts), "forge": sorted(forge["contexts"])})

    check("api/context and the context resolver return the same envelope",
          sorted(live_context) == sorted(forge["context"]),
          {"live": sorted(live_context), "forge": sorted(forge["context"])})

    # The context entry is the object the page merges into its own list and
    # keys everything else on. Two fields are compared out, and both are
    # properties of a bundle rather than of the contract:
    #
    #   workingDays  which days are worked is organisation config. The bundle
    #                backend strips it for the same reason the resolver never
    #                builds it — a third place resolving it is the divergence
    #                the config exists to prevent.
    #   doneCount    written when a bundle is built. Neither live backend emits
    #                it; the page counts done items out of the issues it holds,
    #                and `m.doneCount` is that count, not this field.
    #
    # Anything else missing is a real gap, and the symptom is a picker entry
    # with a blank where a board name should be.
    live_entry = live_contexts["contexts"][0]
    forge_entry = forge["contexts"]["contexts"][0]
    missing = sorted(set(live_entry) - set(forge_entry) - {"workingDays", "doneCount"})
    check("the Forge context entry carries every field the live one does",
          missing == [], missing)

    # And the id format, because the page hands it straight back to `context`.
    # Two formats would be two products.
    check("both build the same context id shape",
          re.fullmatch(r"[^/]+/\d+/\d+", str(forge_entry["id"])) is not None
          and re.fullmatch(r"[^/]+/[^/]+/[^/]+", str(live_entry["id"])) is not None,
          {"live": live_entry["id"], "forge": forge_entry["id"]})
    check("a malformed context id is refused rather than parsed",
          all(parsed is None for _, parsed in forge["rejects"]),
          [bad for bad, parsed in forge["rejects"] if parsed is not None])
    # The bug the first install hit: `contexts` builds ids from the board *list*
    # endpoint and `context` re-reads one board on its own, and the two do not
    # always carry `location`. An id that stops matching between them makes
    # every sprint "unknown context" — a 404 that looks like a stale bookmark
    # and is really two Jira endpoints disagreeing.
    check("an id built from the board list survives being rebuilt from a re-read",
          forge["idSurvivesReread"]["asked"] == forge["idSurvivesReread"]["rebuilt"],
          forge["idSurvivesReread"])
    check("an id round-trips through the resolver's parser",
          forge["roundTrip"]["parsed"] == {"kind": "sprint", "projectKey": "SFT",
                                           "boardId": "2", "sprintId": "43"},
          forge["roundTrip"])

    # The context object, which is separate from the entry in the picker and
    # was not compared until ADR 0010 found what was hiding in it: the live
    # server adds `workingDays` and the resolver does not, so every Forge
    # sprint arrived without the day list its pace figure is a share of.
    #
    # It is still absent, deliberately — expanding a date range into working
    # days is a rule with two implementations already, and a third in a
    # resolver is a third thing to keep in step. The page derives it. What
    # changed is that the absence is now named here rather than unnoticed, and
    # `tests/e2e.py` renders a Forge-shaped body to prove the page really does
    # fill it.
    # `doneCount` is compared out for the reason given above the entry check:
    # it is written when a bundle is built, neither live backend emits it, and
    # the page counts done items out of the issues it holds.
    live_ctx, forge_ctx = live_context["context"], forge["context"]["context"]
    absent_ctx = sorted(set(live_ctx) - set(forge_ctx) - {"doneCount"})
    check("workingDays is the only field of the context object the page makes good",
          absent_ctx == ["workingDays"], absent_ctx)

    # The issue schema. The resolver plays the fetcher's part here, so what it
    # emits has to be fields the page already reads — an invented name is a
    # field nothing renders, and a missing one is a tile that quietly says zero.
    #
    # Checked against the page's own column list rather than against whichever
    # fields one bundle happens to carry. `sample-bundle.json` has no `url` on
    # its issues, and comparing to it would have called a schema field an
    # invention.
    #
    # Two fields are read by the page without being displayed, so they are not
    # in the column list and are named here instead — each checked to be
    # genuinely referenced in `src/app.js`, so an exception cannot outlive the
    # code that justified it. That is this guard's own failure mode, one level
    # up.
    #
    #   contextId           tagged on the way in by loadContext()
    #   statusTransitions   raw material for `started`, consumed by
    #                       normaliseIssue() and then never shown
    app_js = (ROOT / "src" / "app.js").read_text()
    cols = re.search(r"const ISSUE_COLS = \[(.*?)\];", app_js, re.S)
    read_by_page = {"contextId", "statusTransitions"}
    for f in sorted(read_by_page):
        check("the page really reads %s, so allowing it here is not a loophole" % f,
              re.search(r"\b%s\b" % f, app_js) is not None, f)

    # `epicKey` is not one of them, and writing the check above is how that
    # surfaced. Nothing in `src/app.js` reads it and nothing in `agent/tools/`
    # does either — `intake.py` groups by `epic`, the free-text name, which is
    # in NEVER_SEND and so never reaches the calculator at all. It travels from
    # the resolver, through the calculator's allow-list, to nobody.
    #
    # Allowed here rather than quietly dropped: whether epic sizing should key
    # on it is a change to `intake.py`, not to this test. Named, so the next
    # reader does not assume it is load bearing, and asserted so that the day
    # something does read it this stops being true and says so.
    check("epicKey still reaches no consumer, which is a known loose end",
          re.search(r"\bepicKey\b", app_js) is None
          and not any(re.search(r"\bepicKey\b", f.read_text())
                      for f in (ROOT / "agent" / "tools").glob("*.py")),
          "something reads epicKey now — move it into read_by_page")

    schema = set(re.findall(r'"(\w+)"', cols.group(1))) | read_by_page | {"epicKey"}
    forge_issue = forge["context"]["issues"][0]
    invented = sorted(set(forge_issue) - schema)
    check("the Forge issue invents no field the page does not read",
          invented == [], invented)

    # Absent on purpose, each with a reason written next to it in
    # forge/src/jira.js: the page derives statusCategory under its own config,
    # tags contextId itself on the way in, and says out loud that it has no
    # start dates rather than reporting a flow efficiency built on a rule the
    # resolver invented. This list changing is the thing to notice — it means a
    # field stopped being sent and nothing said why.
    live_issue = live_context["issues"][0]
    absent = sorted(set(live_issue) & schema - set(forge_issue))
    check("the fields the resolver leaves out are only the ones it explains",
          absent == ["contextId", "started", "statusCategory"], absent)

    # The one default that is a claim rather than a silence. False everywhere
    # means "nothing was added mid-sprint", the health score reads it as full
    # marks for scope stability, and nothing on the page says it was never
    # measured.
    added = [i["addedMidSprint"] for i in forge["context"]["issues"]]
    check("addedMidSprint is read from the changelog, not defaulted",
          added == [True, False], added)

    # The story-point field id differs per Jira site and there is no id that is
    # right everywhere. Hardcoding the common one made every issue on any other
    # site read as zero points, flattening the burndown in points mode with
    # nothing on the page saying why — the plausible-wrong-number class, and the
    # reason this is checked rather than eyeballed.
    sp = forge["storyPointField"]
    check("the story-point field is discovered by name, not assumed",
          sp["found"] == "customfield_10034", sp["found"])
    check("and the first match in Jira's own order wins, as the fetcher does",
          sp["found"] != "customfield_10099", sp)
    check("a site with no story-point field reports null, never zero",
          sp["absent"] is None and sp["whenAbsent"] is None, sp)
    check("an issue with the field unset is a genuine zero",
          sp["whenUnset"] == 0, sp["whenUnset"])
    check("a non-numeric estimate is not coerced into the burndown",
          sp["whenNotANumber"] is None, sp["whenNotANumber"])

    # The list of names is the contract between the two producers: a site with
    # both "Story Points" and "Points" must resolve to the same field down both
    # routes, or one board reports two different velocities.
    fetcher = (ROOT / "scripts" / "fetch_delivery_data.py").read_text()
    names = re.search(r'nm in \((.*?)\)', fetcher, re.S)
    py_names = set(re.findall(r'"([^"]+)"', names.group(1))) if names else set()
    jira_js = (ROOT / "forge" / "src" / "jira.js").read_text()
    js_block = re.search(r"STORY_POINT_FIELD_NAMES = \[(.*?)\]", jira_js, re.S)
    js_names = set(re.findall(r"'([^']+)'", js_block.group(1))) if js_block else set()
    check("both producers look for the same field names",
          py_names and py_names == js_names,
          {"fetcher": sorted(py_names), "resolver": sorted(js_names)})

    check("no story-point field id is hardcoded anywhere in the Forge app",
          not re.search(r"customfield_\d+", jira_js.replace("`customfield_10016`", ""))
          and not re.search(r"customfield_\d+",
                            (ROOT / "forge" / "src" / "index.js").read_text()),
          "an id that differs per site cannot be written down")

    # ---- the organisation config, resolved per site rather than assumed ----
    #
    # Before this, every Forge tenant was measured under the defaults: Monday
    # to Friday, no holidays, and a fixed idea of the word "done". A site with
    # a "Signed off" column read every sprint as 0% complete — the bug
    # orgconfig.py was written for, reintroduced by a route that had nowhere to
    # read a config from.
    org = forge["orgConfig"]
    check("done comes from the site's own status categories, not a fixed list",
          org["fromJira"]["done"] == ["Shipped", "Signed off"], org["fromJira"])
    check("and in-progress with it",
          org["fromJira"]["inProgress"] == ["In Review", "With QA"], org["fromJira"])
    check("a status with no name is not admitted to either list",
          all(n.strip() for lst in org["fromJira"].values() for n in lst),
          org["fromJira"])
    # An omission is not a claim that nothing is in progress.
    check("what a site states wins, one level down, as the Python merges",
          org["merged"]["statuses"] == {"done": ["Signed off"],
                                        "inProgress": ["In Review", "With QA"]},
          org["merged"])

    # The second implementation this introduces, and the test that makes it
    # survivable. src/app.js already mirrors orgconfig.py because the browser
    # cannot call Python; the Forge resolver now mirrors its *validation*,
    # because a bad config must stop the request rather than be half-applied.
    # Both are run over one shared list of cases so neither can be given an
    # easier set than the other.
    cases = json.loads((ROOT / "tests" / "fixtures" / "org-configs.json").read_text())
    js = dict(org["verdicts"])
    disagreed, wrong = [], []
    for c in cases:
        py_ok = not OC.validate(OC.merge(OC.DEFAULTS, c["config"]))
        expected = c.get("usable", True)
        if js[c["name"]] != py_ok:
            disagreed.append({c["name"]: {"resolver": js[c["name"]], "orgconfig.py": py_ok}})
        if py_ok != expected:
            wrong.append(c["name"])
    check("the resolver and orgconfig.py agree on every config in the fixture",
          disagreed == [], disagreed[:3])
    check("and the fixture's own expectations hold", wrong == [], wrong)
    check("the fixture carries configs that must be refused, not only good ones",
          sum(1 for c in cases if not c.get("usable", True)) >= 10,
          sum(1 for c in cases if not c.get("usable", True)))

    check("the sprint cap keeps the newest, not the first Jira listed",
          forge["cap"] == ["Sprint 24", "Sprint 23"], forge["cap"])



def test_the_two_transports_agree_about_windows():
    """A flow board's window must be one object, not two that look alike.

    A board that runs no sprints is offered a window instead — ADR 0011 — and
    the window is built independently by `forge/src/jira.js` and by
    `scripts/serve_live.py`, because neither transport can call the other. So
    the two are compared here **value by value**, not field set by field set.

    That distinction is the whole point of this test. The parity check above
    compares which keys exist, and that is what let `workingDays` go missing
    across a whole Forge install while the shapes still matched. Two producers
    agreeing about which keys a window has and disagreeing about where a
    30-day window starts would render two different pages from one id, and
    nothing on either page would say so.

    The boundary cases are month ends, a year end and a leap year, which is
    where JavaScript's millisecond arithmetic and Python's `timedelta` would
    diverge if they were going to.
    """
    node = subprocess.run(["node", str(ROOT / "tests" / "forge_shapes.mjs")],
                          cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    if node.returncode != 0:
        check("the Forge shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    forge = json.loads(node.stdout)["window"]

    check("both transports offer the same windows",
          forge["days"] == LIVE.WINDOW_DAYS, (forge["days"], LIVE.WINDOW_DAYS))
    check("both default to the same window",
          forge["defaultDays"] == LIVE.DEFAULT_WINDOW_DAYS,
          (forge["defaultDays"], LIVE.DEFAULT_WINDOW_DAYS))
    check("both spell the id's third part the same way",
          forge["token"] == LIVE.window_token(LIVE.DEFAULT_WINDOW_DAYS),
          (forge["token"], LIVE.window_token(LIVE.DEFAULT_WINDOW_DAYS)))

    board = dict(board_id=2, board_name="Storefront Delivery",
                 project_key="SFT", project_name="Storefront")
    mine = {e["id"]: e for e in
            (LIVE.window_entry(days=d, as_of="2026-08-24", **board)
             for d in LIVE.WINDOW_DAYS)}
    for entry in forge["entries"]:
        peer = mine.get(entry["id"])
        check("the loopback builds the same window as the resolver: %s" % entry["id"],
              peer == entry,
              {k: (entry.get(k), peer.get(k) if peer else None)
               for k in set(entry) | set(peer or {})
               if not peer or entry.get(k) != peer.get(k)})

    # Where two languages' date arithmetic disagrees if it is going to. The
    # list here is the same list the .mjs builds, in the same order, because a
    # case only one side runs is a case neither side is checked on.
    for asOf, days, entry in zip(["2026-03-01", "2026-01-01", "2026-03-02", "2024-03-01"],
                                 [30, 90, 14, 30], forge["boundaries"]):
        peer = LIVE.window_entry(days=days, as_of=asOf, **board)
        check("a %d-day window ending %s starts on the same day both sides" % (days, asOf),
              peer["startDate"] == entry["startDate"] and peer == entry,
              (entry["startDate"], peer["startDate"]))

    check("a window covers the calendar days it says it does",
          all((datetime.date.fromisoformat(e["endDate"])
               - datetime.date.fromisoformat(e["startDate"])).days + 1 == d
              for d, e in zip(LIVE.WINDOW_DAYS, forge["entries"])),
          [(e["startDate"], e["endDate"]) for e in forge["entries"]])

    check("a window id survives the board being re-read without its location",
          forge["fromBareBoard"] == forge["entries"][1]["id"],
          (forge["fromBareBoard"], forge["entries"][1]["id"]))
    check("a window id parses back to the window it names",
          forge["roundTrip"] == {"kind": "window", "projectKey": "SFT",
                                 "boardId": "2", "windowDays": 30},
          forge["roundTrip"])

    # Which issues are in the window. This is the half of the query that
    # decides every figure on the page, so it is the half that must be
    # identical — how each transport reaches a board is its own business, and
    # they genuinely differ: the resolver goes through `/board/{id}/issue` and
    # the loopback scopes plain JQL by the board's own saved filter.
    for start, end, forge_jql in forge["jql"]:
        mine_jql = LIVE.window_membership_jql(start, end)
        check("both transports ask for the same issues over %s..%s" % (start, end),
              mine_jql == forge_jql, (forge_jql, mine_jql))

    # The bound that is easy to get wrong and impossible to see: Jira compares
    # a bare date against midnight, so `resolutiondate <= end` drops everything
    # finished during the window's last day. A throughput series quietly
    # missing its most recent day is not an error anybody notices.
    for start, end, forge_jql in forge["jql"]:
        after = (datetime.date.fromisoformat(end) + datetime.timedelta(days=1)).isoformat()
        check("the window's last day is included, not cut at midnight (%s)" % end,
              ('resolutiondate < "%s"' % after) in forge_jql
              and ("<= \"%s\"" % end) not in forge_jql, forge_jql)

    check("membership is read from the field the page reads as `resolved`",
          all("resolution IS EMPTY" not in q and "resolutiondate IS EMPTY" in q
              for _, _, q in forge["jql"]),
          [q for _, _, q in forge["jql"]])


    # Every id the picker cannot produce is refused rather than clamped,
    # honoured or read as a sprint. `win:030d` is the one worth naming: it
    # parsed as 30 until the token was required to be canonical, so one context
    # had two spellings and the page keys everything on this string.
    rejected = dict((bad, parsed) for bad, parsed in json.loads(node.stdout)["rejects"])
    for bad in ("SFT/2/win:99999d", "SFT/2/win:31d", "SFT/2/win:0d",
                "SFT/2/win:30", "SFT/2/win:-30d", "SFT/2/win:030d"):
        check("the resolver refuses %s rather than answering it" % bad,
              rejected.get(bad) is None, rejected.get(bad))


def test_the_footer_accounts_for_every_board():
    """A board not offered has to be said, not merely not shown.

    This sentence is the only thing between a picker quietly missing a board
    and a project that genuinely does not have one, and on screen the two are
    identical. It is a pure function in `forge/src/jira.js` for exactly that
    reason — a label only a deploy can check is a label nobody checks.

    Three counts, not two. A board with no sprint support is a flow board and
    is offered a window each; a board that has sprints and has never run one
    has nothing to offer and is a different sentence for its owner to act on.
    They were one count until windows existed, and left that way the second
    would have been described as the first.
    """
    node = subprocess.run(["node", str(ROOT / "tests" / "forge_shapes.mjs")],
                          cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    if node.returncode != 0:
        check("the Forge shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    labels = json.loads(node.stdout)["labels"]

    check("a project whose boards all run sprints says only that",
          labels["plain"] == "Jira, project SFT — 1 board", labels["plain"])
    check("a flow board is counted as offered, not as dropped",
          "1 without sprints and shown as rolling windows" in labels["flow"]
          and "not offered" not in labels["flow"], labels["flow"])
    check("a sprint board that has never run one is named as not offered",
          "2 with sprints enabled but none started, and not offered" in labels["unstarted"],
          labels["unstarted"])
    check("the two are different sentences, not one count",
          "rolling windows" not in labels["unstarted"]
          and "none started" not in labels["flow"],
          (labels["flow"], labels["unstarted"]))
    check("every board is accounted for when both kinds are present",
          labels["both"].startswith("Jira, project SFT — 4 boards")
          and "1 without sprints" in labels["both"]
          and "2 with sprints enabled" in labels["both"], labels["both"])
    check("the points and calendar notes still survive alongside them",
          "no story-point field" in labels["both"]
          and "orgConfig property" in labels["both"], labels["both"])



def test_every_context_says_which_kind_it_is():
    """`kind` is carried on the wire, by both transports, on every entry.

    ADR 0011 forbids recovering it by re-reading the id: a discriminator
    recovered by regex is a second implementation of the same fact, and the
    page would be the one holding the wrong copy. So it is sent — including by
    the bundle backend, over bundles written before flow boards existed, where
    every context is a sprint and an absent value has exactly one honest
    reading. A loopback answer that omitted the field while the resolver sent
    it is the divergence ADR 0009 exists to stop.
    """
    bundle = LIVE.BundleBackend(ROOT / "data" / "sample-bundle.json")
    entries = bundle.contexts()
    check("the bundle backend has contexts to answer with", len(entries) > 1, len(entries))
    check("every context the loopback sends says which kind it is",
          all(c.get("kind") == "sprint" for c in entries),
          sorted({c.get("kind") for c in entries}))
    check("the bundle file itself predates the field, so this is the backend's doing",
          all("kind" not in c for c in json.loads(
              (ROOT / "data" / "sample-bundle.json").read_text())["contexts"]))

    node = subprocess.run(["node", str(ROOT / "tests" / "forge_shapes.mjs")],
                          cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    if node.returncode != 0:
        check("the Forge shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    forge = json.loads(node.stdout)
    check("and every context the resolver sends says so too",
          all(c.get("kind") == "sprint" for c in forge["contexts"]["contexts"]),
          sorted({c.get("kind") for c in forge["contexts"]["contexts"]}))
    check("a sprint entry and a window entry differ only where they must",
          sorted(set(forge["contexts"]["contexts"][0]) - {"_sprintId"})
          == sorted(forge["window"]["entries"][0]),
          sorted(set(forge["contexts"]["contexts"][0]) ^ set(forge["window"]["entries"][0])))



def test_the_resolver_sends_the_raw_material_for_started():
    """`started` is the first transition into an in-progress status, and which
    statuses those are is organisation config.

    So the resolver does not decide. It sends the transitions with their names
    undecided and the page applies its own rule, which is the same move it
    already makes for `statusCategory`. The alternative — the resolver
    resolving it, which it now plainly could — is refused for the reason
    recorded against `workingDays`: a third implementation of the rule, in the
    one place nobody can run a test against a customer's tenant.

    What makes this different from `workingDays`, and why it needed deciding
    rather than citing: the page can derive a working-day list from dates
    already on the wire, and nothing on the wire let it derive `started`. That
    absence was a real gap rather than a silence, and on a board with no
    sprints cycle time is not a nicety, it is the measure.
    """
    node = subprocess.run(["node", str(ROOT / "tests" / "forge_shapes.mjs")],
                          cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    if node.returncode != 0:
        check("the Forge shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    out = json.loads(node.stdout)
    st = out["statusTransitions"]

    check("the resolver still sends no `started` of its own",
          all("started" not in i for i in out["context"]["issues"]),
          [sorted(i) for i in out["context"]["issues"]][:1])
    check("and sends the transitions instead",
          all(isinstance(i.get("statusTransitions"), list)
              for i in out["context"]["issues"]),
          [i.get("statusTransitions") for i in out["context"]["issues"]])
    check("an issue with no changelog gets an empty list, not a missing key",
          st["noChangelog"] == [], st["noChangelog"])

    check("only status changes are sent, not every field the changelog holds",
          all(t["to"] != "Sprint 24" for t in st["outOfOrder"])
          and len(st["outOfOrder"]) == 3, st["outOfOrder"])
    check("the names are the site's own, undecided",
          {t["to"] for t in st["outOfOrder"]} == {"In Review", "With QA", "Signed off"},
          st["outOfOrder"])
    check("each carries a date, in calendar days",
          all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", t["at"]) for t in st["outOfOrder"]),
          st["outOfOrder"])

    # The trap, stated here so the page's rule has something to be right
    # about: Jira does not return the changelog in date order. A consumer
    # taking the first in-progress transition rather than the earliest reports
    # a later start, a shorter cycle time and a higher flow efficiency — all
    # plausible, none checkable. `tests/e2e.py` asserts the page takes the
    # earliest; this asserts the resolver really does hand it a list where the
    # two answers differ.
    check("the fixture really is out of date order, so the page's rule is tested",
          [t["at"] for t in st["outOfOrder"]] != sorted(t["at"] for t in st["outOfOrder"]),
          [t["at"] for t in st["outOfOrder"]])
    check("and the two readings of it genuinely disagree",
          st["outOfOrder"][0]["at"] != min(t["at"] for t in st["outOfOrder"]),
          st["outOfOrder"])



def _window_bundle(windows=(14, 30, 90)):
    """A flow board's contexts and issues, one copy of the issue set per window.

    That is what a real fetch produces: the windows overlap completely, so an
    issue inside the 14-day one is inside the 30- and 90-day ones as well.
    """
    sample = json.loads((ROOT / "data" / "sample-multi-sprint.json").read_text())
    end = sample["meta"]["asOfDate"]
    ctxs, issues = [], []
    for days in windows:
        c = LIVE.window_entry(board_id=9, board_name="Flow Board", project_key="SFT",
                              project_name="Storefront", days=days, as_of=end)
        ctxs.append(c)
        issues.extend(dict(i, contextId=c["id"]) for i in sample["issues"])
    return ctxs, issues


def test_the_forecaster_counts_one_issue_once():
    """The Monte Carlo tile, on a board whose contexts overlap.

    `team_slice()` gathers every context belonging to the same team, which on a
    sprint board is that team's sprints — they do not overlap, and no key
    appears twice in one slice. A flow board's three windows are 14, 30 and 90
    days of the *same* board, so every issue in the short one is in the long
    ones too and the slice held each of them three times.

    Nothing failed. `throughput_samples()` counted three completions on the day
    one item finished, the forecaster read a team delivering three times as
    fast, and the 85th percentile came back correspondingly early — on this
    fixture, four working days against a true ten. `item_risk` listed the same
    issue three times over. A smaller number, arrived at by arithmetic, with
    nothing on screen to suggest it.
    """
    ctxs, issues = _window_bundle()
    cid = ctxs[1]["id"]
    got = LIVE.forecast_for(ctxs, issues, {}, cid)

    distinct = len({i["key"] for i in issues})
    check("the fixture really does hold each issue three times",
          len(issues) == distinct * 3, (len(issues), distinct))
    risky = [i["key"] for i in got["item_risk"]["items"]]
    check("and the risk list names each issue once",
          len(risky) == len(set(risky)), sorted(risky)[:6])

    # The strongest form of it: the same board, described by one window instead
    # of three, must forecast identically. Duplication is then provably not an
    # input rather than merely reduced.
    one_ctxs, one_issues = _window_bundle(windows=(30,))
    alone = LIVE.forecast_for(one_ctxs, one_issues, {}, one_ctxs[0]["id"])
    check("the sample counts each completed item once, not once per window",
          got["inputs"]["items_completed_in_window"]
          == alone["inputs"]["items_completed_in_window"],
          (got["inputs"]["items_completed_in_window"],
           alone["inputs"]["items_completed_in_window"]))
    for field in ("percentiles", "days", "samples", "remaining_items"):
        check("three overlapping windows forecast the same %s as one" % field,
              got["sprint_completion"][field] == alone["sprint_completion"][field],
              (got["sprint_completion"][field], alone["sprint_completion"][field]))


def test_a_window_is_not_a_deadline_to_the_forecaster():
    """ADR 0011 has to hold in the forecaster as much as on the page.

    A window's `endDate` is today, not a date anybody undertook to finish by.
    It was passed through as the forecast's default target, so *will this land
    in time* was asked against an end that is always now — and answered
    **0%**, in the one tile whose job is to say when work will land. A
    probability of nought is a number a reader can quote, and it was quoting a
    deadline nobody set.
    """
    ctxs, issues = _window_bundle()
    got = LIVE.forecast_for(ctxs, issues, {}, ctxs[1]["id"])
    sc = got["sprint_completion"]

    check("a window sets no target for the forecast to answer against",
          sc["target_date"] is None, sc["target_date"])
    check("so no probability of hitting one is stated",
          sc["prob_by_target"] is None, sc["prob_by_target"])
    check("and the date control is offered no default to remember",
          got["asked"]["default_date"] is None, got["asked"])
    check("the capacity refusal names the right cause, not a date that passed",
          got["capacity_to_target"]["reason"] == "this period has no end date to forecast against",
          got["capacity_to_target"])
    check("a commitment still refuses, for want of a cadence rather than a date",
          got["next_commitment"]["reason"] == "sprint length is unknown",
          got["next_commitment"])
    check("and the forecast itself is produced, because none of it needed a sprint",
          sc["available"] is True and sc["percentiles"], sc.get("reason", sc.get("percentiles")))

    # A caller who names a date gets it answered — the window withholds a
    # default, it does not refuse the question.
    asked = LIVE.forecast_for(ctxs, issues, {}, ctxs[1]["id"], target="2026-09-30")
    check("a date the reader asks for is honoured",
          asked["capacity_to_target"].get("available") is True,
          asked["capacity_to_target"])

    # And a sprint board still has its own end to fall back on.
    d = json.loads((ROOT / "data" / "demo-bundle.json").read_text())
    sprint = LIVE.forecast_for(d["contexts"], d["issues"], d.get("byContext") or {},
                               d["contexts"][1]["id"])
    check("a sprint board still forecasts against its own end date",
          sprint["asked"]["default_date"] is not None
          and sprint["sprint_completion"]["target_date"] is not None,
          (sprint["asked"]["default_date"], sprint["sprint_completion"]["target_date"]))


def test_forge_app_dependencies():
    """This code runs inside a customer's Jira tenant, so what it depends on is
    a security question rather than a packaging one.

    The dashboard itself has no JavaScript dependencies at all — the security
    suite asserts that against the root package.json. The Forge app needs two,
    and the guard here is that it needs only those two: an unrelated package
    added to this manifest would ship into every tenant the app is installed in.
    """
    pkg_path = ROOT / "forge" / "package.json"
    check("the Forge app declares its dependencies", pkg_path.exists(),
          "" if pkg_path.exists() else
          "missing package.json — the bundler cannot resolve @forge/* without it")
    if not pkg_path.exists():
        return
    pkg = json.loads(pkg_path.read_text())

    deps = pkg.get("dependencies") or {}
    foreign = sorted(d for d in deps if not d.startswith("@forge/"))
    check("every Forge dependency is an Atlassian SDK package", foreign == [], foreign)

    # Both source trees: the resolver and the Custom UI probe import different
    # SDK packages, and a missing one fails at bundle time with an error that
    # names the module rather than the omission.
    sources = [ROOT / "forge" / "src" / "index.js", ROOT / "forge" / "probe" / "probe.js",
               ROOT / "forge" / "bridge" / "bridge.js"]
    # Both spellings. The bridge adapter is CommonJS on purpose — it has to
    # catch the SDK failing to connect, which an `import` evaluated before any
    # of its code cannot — so a check that only knew about `from '…'` would
    # have gone quiet at exactly the moment a new dependency appeared.
    imported = set()
    for src in sources:
        if src.exists():
            text = src.read_text()
            imported |= set(re.findall(r"from '(@forge/[\w-]+)'", text))
            imported |= set(re.findall(r"require\(\s*'(@forge/[\w-]+)'", text))
    missing = sorted(imported - set(deps))
    check("every SDK package the resolver imports is declared",
          missing == [], missing or sorted(imported))

    check("the app is private, so it cannot be published by accident",
          pkg.get("private") is True, pkg.get("private"))

    # A deployed app with unpinned transitive dependencies is a supply-chain
    # hole. The repository ignores lockfiles generally, because nothing else
    # here ships npm packages; this one is un-ignored deliberately.
    lock = ROOT / "forge" / "package-lock.json"
    check("the Forge lockfile is kept", lock.exists(),
          "" if lock.exists() else
          "no package-lock.json — transitive versions are unpinned")
    gi = (ROOT / ".gitignore").read_text()
    check("and is exempt from the blanket lockfile ignore",
          "!forge/package-lock.json" in gi)


def test_dockerfile_copies_everything_the_service_imports():
    """Reconstruct the image's filesystem from its COPY lines and boot from it.

    The failure this catches is narrow and nasty: the Dockerfile stops copying a
    module the service imports — a new file under agent/tools, say — and every
    other suite in this repository still passes, because they all run against a
    working tree where the file is present. The container then fails on its
    first request in production.

    CI builds the real image and smoke-tests it. This runs everywhere, including
    on machines with no Docker, which is where the Dockerfile actually gets
    edited.
    """
    import os, shutil, tempfile
    df = (ROOT / "service" / "Dockerfile").read_text()
    copies = re.findall(r"^COPY\s+(\S+)\s+(\S+)\s*$", df, re.M)
    check("the Dockerfile has COPY instructions to check", len(copies) >= 2, copies)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        for src, dst in copies:
            s, d = ROOT / src, tmp / dst.lstrip("/").replace("app/", "", 1)
            if s.is_dir():
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(s, d)

        r = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, 'service'); import app; "
             "print(app.VERSION); print(sorted(app.VERIFIERS))"],
            cwd=tmp, capture_output=True, text=True, timeout=60,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        check("the service imports cleanly from the image's files alone",
              r.returncode == 0, (r.stderr or r.stdout)[-200:])

        shipped = {p.relative_to(tmp).as_posix() for p in tmp.rglob("*") if p.is_file()}
        needed = {"agent/tools/%s.py" % m for m in
                  ("metrics", "forecast", "intake", "orgconfig")}
        check("every tool module is in the image", needed <= shipped,
              sorted(needed - shipped) or "all present")

        # Nothing that could carry a credential or a customer's issue titles.
        leaked = sorted(p for p in shipped
                        if p.startswith(("data/", "dist/", ".env", "config/"))
                        or p.endswith((".env", ".jira-oauth.json")))
        check("no credential or dataset is baked into the image",
              leaked == [], leaked)


def test_refuses_to_start_unauthenticated():
    """A calculator that came up open would look perfectly healthy."""
    env = {k: v for k, v in __import__("os").environ.items()
           if k != "SERVICE_SHARED_SECRET"}
    r = subprocess.run([sys.executable, str(ROOT / "service" / "app.py"), "--port", "0"],
                       env=env, capture_output=True, text=True, timeout=30)
    check("it refuses to start without a shared secret",
          r.returncode != 0 and "Refusing to start" in (r.stdout + r.stderr),
          (r.returncode, (r.stdout + r.stderr)[:80]))


if __name__ == "__main__":
    import os
    os.environ["SERVICE_SHARED_SECRET"] = SECRET

    print("the projection")
    test_projection_loses_nothing()
    print("two languages, one field list")
    test_field_lists_agree()
    print("the service computes nothing")
    test_service_computes_nothing()
    print("the config travels in the payload")
    test_config_travels_in_the_payload()
    print("refusals")
    test_refusals()
    print("nothing internal leaks out")
    test_no_internals_leak()
    print("the auth seam")
    test_auth_seam_fails_closed()
    print("the Forge manifest")
    test_forge_manifest_matches_the_code()
    print("the split build")
    test_split_build_has_no_inline_assets()
    print("one contract, two transports")
    test_the_two_transports_answer_the_same_shape()
    print("a board without sprints")
    test_the_two_transports_agree_about_windows()
    test_every_context_says_which_kind_it_is()
    test_the_footer_accounts_for_every_board()
    test_the_resolver_sends_the_raw_material_for_started()
    print("the forecast over a board with no sprints")
    test_the_forecaster_counts_one_issue_once()
    test_a_window_is_not_a_deadline_to_the_forecaster()
    print("the Forge app's dependencies")
    test_forge_app_dependencies()
    print("the container image")
    test_dockerfile_copies_everything_the_service_imports()
    print("startup")
    test_refuses_to_start_unauthenticated()

    print()
    if failures:
        print("%d check(s) failed: %s" % (len(failures), ", ".join(failures)))
        sys.exit(1)
    print("all service checks passed")
