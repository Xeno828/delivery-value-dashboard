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
import os
import pathlib
import re
import secrets
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent" / "tools"))
sys.path.insert(0, str(ROOT / "service"))
# The loopback transport's own module, imported rather than only launched, so
# the window it builds can be compared against the resolver's directly.
sys.path.insert(0, str(ROOT / "scripts"))

import app as SVC        # noqa: E402
import forecast as FC
import selection as SEL    # noqa: E402
import orgconfig as OC   # noqa: E402
import serve_live as LIVE  # noqa: E402
import intake as IN        # noqa: E402

failures = []
#: Generated per run rather than written down. A literal token in a test file is
#: indistinguishable from a real one to a secret scanner — the security suite
#: flagged exactly that — and a test that needs a hard-coded credential is a
#: test teaching a bad habit.
SECRET = secrets.token_hex(16)
AUTH = {"Authorization": "Bearer " + SECRET}


# The only scopes in this app that do not begin with `read:`, and the reason
# each is tolerable. ADR 0014 has the argument; this is the enforcement.
#
# `send:notification:jira` — the send. No read or write of issue data, and the
#   notify endpoint has no field for an address outside the site.
# `storage:app`            — the app's own key-value store, where a board's
#   recipient list lives. No access to Jira data at all.
#
# Adding to this set is a deliberate act with a record behind it. Anything not
# in it fails, which is stricter than the `startswith("read:")` it replaced:
# that would have waved through every future read scope unexamined.
NON_READ_ALLOWED = {"send:notification:jira", "storage:app"}


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

    # ---------- the slice, which is the part with the history of being wrong ----
    #
    # /v1/forecast takes a flat issue list and leaves the slice to the caller.
    # That is fine over loopback, where the caller is Python and uses the same
    # rules the tools do. It is not fine over Forge, where the caller is a Node
    # resolver: the only ways to give it a forecast are to write the slice a
    # second time in JavaScript, or to move the slice where both callers can
    # reach it. The first is what ADR 0005 and ADR 0008 exist to refuse, of the
    # one piece of logic whose failures are all plausible dates rather than
    # errors — 19 days became 77 in 1.8.0, and a flow board forecast 2.5x too
    # fast in 1.16.13.
    #
    # So it lives in agent/tools/selection.py, and this is the assertion that
    # keeps the route honest about it: the endpoint's answer is the function's
    # answer, to the byte, exactly as the flat route above must equal FC.build.
    ctx_ds = {"issues": project(team), "contexts": full["contexts"],
              "orgConfig": full.get("orgConfig", {})}
    cid = full["contexts"][0]["id"]
    status, out = call("POST", "/v1/forecast-context",
                       {"dataset": json.loads(json.dumps(ctx_ds)), "contextId": cid})
    out_ctx = out
    direct = SEL.forecast_for(json.loads(json.dumps(full["contexts"])),
                              json.loads(json.dumps(project(team))), {}, cid,
                              org_cfg=full.get("orgConfig", {}))
    check("the context forecast endpoint answers", status == 200, out.get("error"))
    check("and agrees with selection.forecast_for called directly",
          json.dumps(out.get("result"), sort_keys=True) == json.dumps(direct, sort_keys=True))
    check("it reports which slice it sampled",
          bool(((out.get("result") or {}).get("sampled_from") or {}).get("slice")),
          (out.get("result") or {}).get("sampled_from"))

    # ---------- /v1/slice must name exactly what the forecast samples ---------
    #
    # The Forge resolver has to fetch the issues of every context in the slice
    # before it can ask for a forecast over them, and it must not decide the
    # slice itself. So it asks — and the only thing that makes that safe is this
    # route naming the same contexts the forecast then filters to. If it named
    # fewer, the resolver would send fewer issues and the forecast would run
    # over a narrower sample than `sampled_from` reports, which is the silent
    # narrowing this repository keeps paying for.
    status, sl = call("POST", "/v1/slice",
                      {"dataset": {"contexts": json.loads(json.dumps(full["contexts"]))},
                       "contextId": cid})
    check("the slice endpoint answers", status == 200, sl.get("error"))
    members, label = SEL.slice_for(json.loads(json.dumps(full["contexts"])), cid)
    check("and agrees with selection.slice_for called directly",
          (sl.get("result") or {}).get("contextIds") == [c["id"] for c in members]
          and (sl.get("result") or {}).get("slice") == label,
          sl.get("result"))
    check("the slice it names is the slice the forecast counted",
          len((sl.get("result") or {}).get("contextIds") or [])
          == ((out_ctx.get("result") or {}).get("sampled_from") or {}).get("contexts"),
          {"slice": (sl.get("result") or {}).get("contextIds"),
           "sampled": ((out_ctx.get("result") or {}).get("sampled_from") or {})})

    # It needs no issues, and saying so matters: a caller that sent a board's
    # issues here would be shipping data to a route that has no use for it.
    status, _ = call("POST", "/v1/slice", {"dataset": {}, "contextId": cid})
    check("the slice endpoint refuses without contexts", status == 400)
    status, _ = call("POST", "/v1/slice",
                     {"dataset": {"contexts": json.loads(json.dumps(full["contexts"]))},
                      "contextId": "no-such-context"})
    check("an unknown context has no slice, and is a 404", status == 404)

    # An unknown context is a 404 and not a zero. The request was well formed
    # and named something this dataset does not describe, and a forecast for a
    # context nobody selected is the 1.8.0 fault with a different cause.
    status, out = call("POST", "/v1/forecast-context",
                       {"dataset": json.loads(json.dumps(ctx_ds)),
                        "contextId": "no-such-context"})
    check("an unknown context id is refused, not forecast", status == 404, (status, out))

    # The slice is not optional. Without contexts this route cannot know which
    # issues are the team's, and guessing is what produces a credible wrong
    # number — so it refuses rather than forecasting everything it was sent.
    status, out = call("POST", "/v1/forecast-context",
                       {"dataset": {"issues": project(team)}, "contextId": cid})
    check("a context forecast with no contexts refuses", status == 400, (status, out))

    for bad in (0, -1, 5001, "30", True):
        status, _ = call("POST", "/v1/forecast-context",
                         {"dataset": json.loads(json.dumps(ctx_ds)),
                          "contextId": cid, "items": bad})
        check("items=%r is refused rather than clamped" % (bad,), status == 400)

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

    Both modes are written now. The one thing that must not happen in either is
    a configuration which serves requests without checking anything — a
    calculator that came up unauthenticated looks healthy to everything
    watching it. So every way of being misconfigured is checked here, and each
    one has to stop the process *and* refuse the request, because a guard that
    only exists at startup is a guard somebody removes.
    """
    import os
    saved = dict(os.environ)
    try:
        # The token mode, with none of the four values it needs. Configuration
        # rather than constants, precisely so this file carries no value nobody
        # has confirmed against Atlassian — which means it can be absent.
        os.environ["SERVICE_AUTH"] = "forge-token"
        for k in SVC.FORGE_ENV:
            os.environ.pop(k, None)
        problem = SVC.startup_problem()
        check("an unconfigured token mode refuses to start",
              problem and all(k in problem for k in SVC.FORGE_ENV), problem)
        check("and says where the specification lives",
              problem and "forge-deployment" in problem, problem)
        # even if the startup guard were removed, requests must not pass
        check("and its verifier refuses every request while unconfigured",
              SVC.authorised({"Authorization": "Bearer anything"}) is None)

        # And on a host where the crypto library is not installed at all. This
        # is how CI found it: the import sat at the top of the verifier, so a
        # runner without PyJWT got an exception where the line above expects a
        # refusal. "A principal, or None" is the contract; raising is neither,
        # and a verifier that cannot verify has one honest answer.
        import sys as _sys
        had = _sys.modules.get("jwt", "absent")
        _sys.modules["jwt"] = None              # makes `import jwt` raise
        try:
            check("a host with no crypto library refuses rather than raising",
                  SVC.authorised({"Authorization": "Bearer anything"}) is None)
            # With the four values present, so it is the missing library the
            # guard is refusing over rather than the configuration — the two
            # are different problems with different fixes and the message has
            # to name the one the operator actually has.
            for k in SVC.FORGE_ENV:
                os.environ[k] = "set-for-this-check"
            problem = SVC.startup_problem()
            check("and the startup guard names the missing dependency",
                  problem and "PyJWT" in problem, problem)
        finally:
            for k in SVC.FORGE_ENV:
                os.environ.pop(k, None)
            if had == "absent":
                _sys.modules.pop("jwt", None)
            else:
                _sys.modules["jwt"] = had

        os.environ["SERVICE_AUTH"] = "typo-mode"
        problem = SVC.startup_problem()
        check("an unknown auth mode refuses to start", bool(problem), problem)
        check("an unknown auth mode refuses every request",
              SVC.authorised({"Authorization": "Bearer anything"}) is None)

        os.environ["SERVICE_AUTH"] = "shared-secret"
        os.environ.pop("SERVICE_SHARED_SECRET", None)
        check("the implemented mode still refuses to start with no secret",
              bool(SVC.startup_problem()))
        check("and refuses every request while unconfigured",
              SVC.authorised({"Authorization": "Bearer anything"}) is None)

        os.environ["SERVICE_SHARED_SECRET"] = SECRET
        check("a configured service may start", SVC.startup_problem() is None)
        check("every declared mode has a verifier",
              sorted(SVC.VERIFIERS) == sorted(SVC.AUTH_MODES), sorted(SVC.VERIFIERS))

        # ---------- a secret store's trailing newline must not lock everyone out
        #
        # This shipped. `openssl rand -hex 32` prints a newline after the hex,
        # Secret Manager stored all 65 bytes, Cloud Run injected all 65, and the
        # deployment answered 401 to a caller presenting exactly the right
        # secret. The verifier stripped the token it was *given* and not the one
        # it was *configured with*, so the two sides were never comparable — and
        # from inside the service the credential really did not match, which is
        # why nothing it could log would have pointed at the cause.
        #
        # Every secret store and every echo-based workflow does this, so the
        # asymmetry is the bug rather than the newline.
        for label, stored in [("a trailing newline", SECRET + "\n"),
                              ("a leading newline", "\n" + SECRET),
                              ("surrounding whitespace", "  " + SECRET + "  \n")]:
            os.environ["SERVICE_SHARED_SECRET"] = stored
            who = SVC.authorised({"Authorization": "Bearer " + SECRET})
            check("a secret stored with %s still authenticates" % label,
                  bool(who) and who.get("mode") == "shared-secret", who)

        # And the strip must not turn a blank secret into a configured one: an
        # open calculator is free compute for whoever finds it.
        os.environ["SERVICE_SHARED_SECRET"] = "   \n  "
        check("a whitespace-only secret is no secret, and refuses to start",
              bool(SVC.startup_problem()))
        check("and refuses every request",
              SVC.authorised({"Authorization": "Bearer    "}) is None)
        os.environ["SERVICE_SHARED_SECRET"] = SECRET
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

    # This was `all(s.startswith("read:"))` until 1.26.0, and the rule it stood
    # for was never the prefix — it was that reach is added deliberately, by
    # somebody who wrote down why. Two scopes now need to be non-read (ADR 0014),
    # so the assertion moved to the allow-list below, where a non-read scope has
    # to be named *and* carry a justification. Weaker as a slogan, identical in
    # what it actually stops, and it fails on a scope nobody argued for — which
    # `startswith` did not: `read:` is also the prefix of every read scope
    # Atlassian will ever add.
    non_read = [s for s in scope_strs if not s.startswith("read:")]
    check("every non-read scope is one of the two ADR 0014 permitted",
          set(non_read) <= NON_READ_ALLOWED,
          sorted(set(non_read) - NON_READ_ALLOWED) or non_read)

    # A reason in the manifest, beside the scope, not only in the record. A
    # scope somebody adds by copying the line above it is exactly what this
    # catches: the comment block has to mention it by name.
    for scope in sorted(NON_READ_ALLOWED):
        if scope not in scope_strs:
            continue
        before = man.split("- %s" % scope)[0]
        commented = [ln for ln in before.rsplit("\n\n", 1)[-1].split("\n")
                     if ln.strip().startswith("#")]
        check("%s carries a written reason in the manifest" % scope,
              len(commented) >= 2, len(commented))

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
    } | NON_READ_ALLOWED
    check("no scope outside the reviewed allow-list",
          set(scope_strs) <= ALLOWED, sorted(set(scope_strs) - ALLOWED) or "none")

    declared = re.findall(r"^remotes:\s*$\n(?:\s+- key:\s*(\S+)\s*$)", man, re.M)
    referenced = re.findall(r"^\s+- remote:\s*(\S+)\s*$", man, re.M)
    check("any egress rule points at a remote that is declared",
          set(referenced) <= set(declared),
          {"declared": declared, "referenced": referenced})

    # That check used to require an egress rule to exist, because the calculator
    # was reached with `fetch` and `permissions.external.fetch.backend` named the
    # remote. It is reached with `invokeRemote` now — the only call that attaches
    # the invocation token — so there is no egress rule left to check and the
    # typo it guarded against has moved into the code. `invokeRemote` names its
    # remote with a string, and a mistyped one fails at runtime, inside a tenant,
    # which is exactly what the old assertion existed to prevent.
    idx_src = (ROOT / "forge" / "src" / "index.js").read_text()
    invoked = set(re.findall(r"invokeRemote\(\s*'([^']+)'", idx_src))
    check("every remote invokeRemote names is declared in the manifest",
          bool(invoked) and invoked <= set(declared),
          {"declared": declared, "invoked": sorted(invoked)})

    # `operations: [compute]` is required before Forge will resolve a remote key
    # for `invokeRemote` at all, so without it the calculator route fails in a
    # tenant with nothing here to have caught it. It is also the declaration that
    # this remote computes without storing: absent, Forge assumes the app stores
    # end-user data on the remote, which is both untrue and the reading that
    # costs the app its data-residency PINNED status.
    block = re.search(r"^remotes:\s*$\n((?:[ \t]+.*\n|\n)*)", man, re.M)
    ops = block.group(1) if block else ""
    check("the calculator remote declares operations: [compute]",
          re.search(r"^\s+operations:\s*$\n\s+- compute\s*$", ops, re.M) is not None,
          ops.strip() or "no remotes block found")

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
    # The forecast resolver must ASK for the slice, not choose one.
    #
    # `team_slice` decides which contexts a forecast samples, and it is the last
    # logic here that should exist twice: its failures are all plausible dates
    # rather than errors. The resolver therefore calls /v1/slice, fetches
    # exactly the contexts it names, and sends them to /v1/forecast-context.
    # A resolver that filtered by team itself would be the second
    # implementation, and it would be invisible — the numbers would still look
    # like numbers.
    idx_js = (ROOT / "forge" / "src" / "index.js").read_text()
    for route in ("/v1/slice", "/v1/forecast-context"):
        check("the resolver calls %s" % route, route in idx_js)
    check("the resolver never reads a team label of its own",
          ".team" not in idx_js and "team ===" not in idx_js,
          "a team comparison in the resolver is a second team_slice")

    # An issue reaching the calculator without a contextId is dropped from the
    # sample by selection.forecast_for, silently — the forecast would then run
    # over less history than `sampled_from` reports. issueFrom deliberately does
    # not set one (the page re-tags), so the resolver must.
    check("the resolver stamps contextId on the issues it gathers",
          "contextId: entry.id" in idx_js,
          "untagged issues are silently excluded from the slice")

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

    # `epicKey` is read by the tools rather than by the page, which is why it
    # is checked against a different file. Writing this check is how it was
    # found reaching nobody at all: `intake.py` grouped completed epics by
    # `epic`, the free-text name, and `epic` never reaches the calculator
    # because free text is stripped on the way in. Sizing over that route
    # therefore grouped nothing and refused, for every board, always. It groups
    # on the key now — see `test_epic_sizing_survives_the_projection`.
    read_by_tools = {"epicKey"}
    tools = "".join(f.read_text() for f in sorted((ROOT / "agent" / "tools").glob("*.py")))
    for f in sorted(read_by_tools):
        check("%s is read by agent/tools, so sending it is not a loophole either" % f,
              re.search(r"\b%s\b" % f, tools) is not None, f)

    schema = set(re.findall(r'"(\w+)"', cols.group(1))) | read_by_page | read_by_tools
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



def test_epic_sizing_survives_the_projection():
    """Intake's reference class, over the payload the calculator really receives.

    Sizing an ask means grouping this board's finished epics and reading how
    big they turned out. `intake.py` grouped them by `epic` — the epic's own
    summary — and `epic` is free text, so `clean_dataset()` strips it on the
    way in. That boundary is deliberate and is not the thing to change: the
    calculator has no business holding issue titles.

    The consequence was that sizing over this route grouped nothing, found no
    completed epics and refused, every time, for every board. Not a wrong
    number — the refusal was accurate — but the t-shirt scale and the reference
    class that `docs/product-intake.md` describes were unavailable in principle
    to the one route Forge would use.

    `epicKey` is the field that was already travelling for this and reaching
    nobody. Grouping keys on it when a dataset carries one, which is exactly
    when the names have been stripped.
    """
    full = json.loads((ROOT / "data" / "demo-intake-bundle.json").read_text())
    as_of = (full.get("meta") or {}).get("asOfDate")

    # The bundle's own answer, by epic name — the baseline this must reproduce.
    named = IN.epic_sizes(full["issues"], as_of=as_of)
    check("the fixture has a reference class worth grouping", len(named) >= 5, len(named))

    # The same board as the calculator sees it: free text gone, key present.
    keyed_issues = []
    for i in full["issues"]:
        row = {k: v for k, v in i.items() if k not in SVC.FREE_TEXT_FIELDS}
        row["epicKey"] = ("EPIC-%d" % (sorted({x.get("epic") for x in full["issues"]
                                               if x.get("epic")}).index(i["epic"]) + 1)
                          ) if i.get("epic") else None
        keyed_issues.append(row)

    keyed = IN.epic_sizes(keyed_issues, as_of=as_of)
    check("the same board groups to the same epics by key as by name",
          sorted(r["items"] for r in keyed) == sorted(r["items"] for r in named),
          (sorted(r["items"] for r in keyed), sorted(r["items"] for r in named)))
    check("and says which field it grouped on",
          {r["grouped_by"] for r in keyed} == {"epicKey"}
          and {r["grouped_by"] for r in named} == {"epic"},
          ({r["grouped_by"] for r in keyed}, {r["grouped_by"] for r in named}))

    # Chosen once for the set, not per issue. `epicKey or epic` reads as the
    # obvious fallback and splits one epic in two the moment a dataset carries
    # the key on some issues and the name on others — a twenty-item epic
    # arriving as two tens, which shrinks the t-shirt bands and reads exactly
    # like a team that has started working in smaller pieces.
    # Take one epic and give half its issues the key and half the name. Under
    # a per-issue fallback that epic becomes two groups; under one field
    # chosen for the set it stays one, and the half carrying the other field
    # drops out the same way an issue with no epic at all always has.
    target = keyed[-1]["epic"]
    members = [r for r in keyed_issues if r.get("epicKey") == target]
    check("the epic being split really is one group to begin with",
          len(members) >= 4, len(members))
    mixed = [dict(r) for r in keyed_issues]
    for r in mixed:
        if r.get("epicKey") == target and members.index(
                next(m for m in members if m["key"] == r["key"])) % 2 == 0:
            r.pop("epicKey", None)
            r["epic"] = "the same epic, by name"

    rows = IN.epic_sizes(mixed, as_of=as_of)
    check("one field is chosen for the whole set, not per issue",
          len({r["grouped_by"] for r in rows}) == 1, {r["grouped_by"] for r in rows})
    check("so the split epic is never counted as two",
          len([r for r in rows if r["epic"] in (target, "the same epic, by name")]) <= 1,
          [r["epic"] for r in rows if r["epic"] in (target, "the same epic, by name")])

    # The hazard demonstrated rather than asserted in the abstract: the naive
    # `epicKey or epic` really would have produced one more group here.
    naive = {}
    for r in mixed:
        k = r.get("epicKey") or r.get("epic")
        if k:
            naive.setdefault(k, []).append(r)
    check("and the per-issue fallback really would have split it",
          target in naive and "the same epic, by name" in naive,
          sorted(k for k in naive if "same epic" in str(k) or k == target))

    # And the whole way through the service, which is the route that was dead.
    ok, body = call("POST", "/v1/ask", {
        "dataset": {"issues": keyed_issues, "meta": {"asOfDate": as_of}},
        "ask": {"title": "A new thing", "board": "any",
                "sizing": {"method": "reference-class"}},
        "asOf": as_of,
    })
    sizing = ((body.get("result") or {}).get("sizing") or {})
    check("/v1/ask sizes an ask from a payload carrying no epic names at all",
          body.get("ok") and sizing.get("method") == "reference-class",
          {"ok": body.get("ok"), "sizing": str(sizing)[:150]})
    check("and the basis says it grouped by key, so the working can be followed",
          "grouped by epic key" in (sizing.get("basis") or ""), sizing.get("basis"))



# =====================================================================
# the Forge invocation token
# =====================================================================
def _jwt_available():
    try:
        import jwt                                          # noqa: F401,PLC0415
        import cryptography                                 # noqa: F401,PLC0415
        return True
    except Exception:                                       # noqa: BLE001
        return False


def test_forge_token_verification():
    """SERVICE_AUTH=forge-token, proved without Atlassian.

    A keypair is generated here, a JWKS is served from a local HTTP server, and
    the tokens are minted in the test. That exercises every mechanic — algorithm
    pinning, key lookup by `kid`, cache and rotation, `exp`, `nbf`, `aud`,
    `iss`, tenant binding — against a signer this test controls, which is the
    only way to test a verifier without a real token to test against.

    What it does **not** prove is the four values that identify Atlassian's
    issuer: the JWKS URL, the `iss`, what belongs in `aud`, and which claim
    carries the tenant. Those are configuration, the service refuses to start
    without them, and confirming them against current Atlassian documentation
    is a step no test here can do for you.
    """
    if not _jwt_available():
        # Reported, never skipped silently. A security test that quietly did
        # not run reads exactly like one that passed.
        check("PyJWT with its crypto extra is installed, so the verifier can be tested",
              False, "pip install -r service/requirements.txt")
        return

    import http.server
    import threading
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    KID = "test-key-1"

    def jwk_of(k, kid):
        pub = jwt.algorithms.RSAAlgorithm.to_jwk(k.public_key(), as_dict=True)
        pub.update({"kid": kid, "use": "sig", "alg": "RS256"})
        return pub

    served = {"keys": [jwk_of(key, KID)]}
    fetches = {"n": 0}

    class JWKS(http.server.BaseHTTPRequestHandler):
        def do_GET(self):                                   # noqa: N802
            fetches["n"] += 1
            body = json.dumps(served).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):                          # keep the run quiet
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), JWKS)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d/jwks" % srv.server_address[1]

    ISS, AUD, TENANT_CLAIM = "https://forge.example/iss", "ari:app/abc", "installationId"
    env = {"SERVICE_AUTH": "forge-token", "FORGE_JWKS_URL": url, "FORGE_ISSUER": ISS,
           "FORGE_AUDIENCE": AUD, "FORGE_TENANT_CLAIM": TENANT_CLAIM}
    old_env = {k: os.environ.get(k) for k in env}

    def mint(k=key, kid=KID, alg="RS256", **over):
        now = int(time.time())
        claims = {"iss": ISS, "aud": AUD, "exp": now + 300, "nbf": now - 5,
                  TENANT_CLAIM: "tenant-abc"}
        claims.update(over)
        return jwt.encode(claims, k, algorithm=alg, headers={"kid": kid})

    def bearer(tok):
        return {"Authorization": "Bearer " + tok}

    try:
        os.environ.update(env)
        SVC._jwks_cache.update({"keys": {}, "fetched_at": 0.0, "last_attempt": 0.0})

        check("the token mode starts once its four values are configured",
              SVC.startup_problem() is None, SVC.startup_problem())

        who = SVC.authorised(bearer(mint()))
        check("a correctly signed, in-date token is accepted",
              bool(who) and who.get("mode") == "forge-token", who)
        check("and it carries the tenant, which is the point of the mode",
              (who or {}).get("tenant") == "tenant-abc", who)

        now = int(time.time())
        rejects = [
            ("expired", mint(exp=now - 60, nbf=now - 600)),
            ("nbf in the future", mint(nbf=now + 600, exp=now + 900)),
            ("right signature, wrong aud", mint(aud="ari:app/somebody-else")),
            ("right signature, wrong iss", mint(iss="https://not-atlassian.example")),
            ("signed with a key not in the JWKS", mint(k=other)),
            ("no kid in the header", jwt.encode({"iss": ISS, "aud": AUD,
                                                 "exp": now + 300,
                                                 TENANT_CLAIM: "t"}, key,
                                                algorithm="RS256")),
            ("well-formed but truncated", mint()[:-8]),
            ("no tenant claim at all", mint(**{TENANT_CLAIM: None})),
            ("an empty tenant claim", mint(**{TENANT_CLAIM: "   "})),
        ]
        for name, tok in rejects:
            check("a token that is %s is rejected" % name,
                  SVC.authorised(bearer(tok)) is None, name)

        # The two that are attacks rather than mistakes, and the reason the
        # algorithm is pinned before a key is ever looked up.
        unsigned = jwt.encode({"iss": ISS, "aud": AUD, "exp": now + 300,
                               TENANT_CLAIM: "t"}, key=None, algorithm="none",
                              headers={"kid": KID})
        check("a token with alg:none and no signature is rejected",
              SVC.authorised(bearer(unsigned)) is None, "alg:none")

        # The classic: sign with HMAC using the RSA *public* key as the shared
        # secret, against a verifier that takes its algorithm from the header.
        # The public key is public, so this is free to construct.
        # Assembled by hand rather than with `jwt.encode`, which refuses to use
        # an asymmetric key as an HMAC secret — a good guard on the *minting*
        # side, and not one a verifier may rely on. An attacker writes these
        # three lines.
        import base64
        import hashlib
        import hmac as _hmac
        from cryptography.hazmat.primitives import serialization
        pub_pem = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo)
        b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=")
        signing = (b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": KID}).encode())
                   + b"." + b64(json.dumps({"iss": ISS, "aud": AUD, "exp": now + 300,
                                            TENANT_CLAIM: "t"}).encode()))
        forged = (signing + b"." + b64(_hmac.new(pub_pem, signing,
                                                 hashlib.sha256).digest())).decode()
        check("an HMAC-signed token using the public key as the secret is rejected",
              SVC.authorised(bearer(forged)) is None, "HS256 with the public key")

        check("a request with no Authorization header at all is rejected",
              SVC.authorised({}) is None)

        # ---------- the tenant claim is nested in a real token ----------
        #
        # Every token minted above carries a *flat* tenant claim, and that is
        # why twelve rejection cases could pass against a verifier that could
        # not read a real one. The invocation token has no flat tenant claim at
        # all: the installation identity is `app.installationId`, one level
        # down, and `context.cloudId` — the other candidate — is not delivered
        # to the backend-function invocations this app makes, so on this route
        # it is always absent. A flat `claims.get()` found neither, so the mode
        # refused 100% of genuine traffic while this suite stayed green.
        #
        # It failed in the safe direction — nothing wrong was ever accepted —
        # and it still meant the tenant-aware mode did not work. Nothing minted
        # by a signer this test controls could have shown it; only Atlassian's
        # published payload could, which is why the shape is copied from it.
        INSTALL = ("ari:cloud:ecosystem::installation/"
                   "0a3a7799-53ae-4a5b-9e7e-03338980abb5")
        os.environ["FORGE_TENANT_CLAIM"] = "app.installationId"
        nested = mint(**{TENANT_CLAIM: None,
                         "app": {"id": AUD, "installationId": INSTALL}})
        who = SVC.authorised(bearer(nested))
        check("a nested tenant claim is read, as a real token carries it",
              bool(who) and who.get("tenant") == INSTALL, who)

        # The walk has to refuse as firmly as the flat lookup did. A path that
        # runs out, or lands on an object, or lands on blank, is a call this
        # service cannot attribute — and attributing calls is the whole reason
        # this mode exists.
        for name, tok in [
            ("a dotted path whose object is absent",
             mint(**{TENANT_CLAIM: None})),
            ("a dotted path that lands on an object rather than a string",
             mint(**{TENANT_CLAIM: None,
                     "app": {"installationId": {"id": INSTALL}}})),
            ("a dotted path that lands on a blank string",
             mint(**{TENANT_CLAIM: None, "app": {"installationId": "   "}})),
        ]:
            check("%s is rejected" % name,
                  SVC.authorised(bearer(tok)) is None, name)

        # And a claim name with no dot in it still reads flat, so the twelve
        # cases above are not rewritten to suit the fix.
        os.environ["FORGE_TENANT_CLAIM"] = TENANT_CLAIM
        check("a claim name with no dot in it still reads flat",
              (SVC.authorised(bearer(mint())) or {}).get("tenant") == "tenant-abc")

        # The algorithm pin is defence in depth: PyJWT's own `algorithms=`
        # already refuses both forgeries above, so removing the pin changes no
        # verdict and no mutation of it would fail. What the pin *does* change
        # is observable, and is the property worth having — the token is thrown
        # out before a key is looked up, so an attacker cannot use `alg: none`
        # to make this service fetch from Atlassian's endpoint on their behalf.
        # It also means the rejection is this service's rather than a library
        # default somebody widens later.
        # Carrying a `kid` this service has never seen, so that without the
        # pin the verifier would go and fetch looking for it. With `kid` set to
        # a key already cached the check proves nothing, because no fetch would
        # happen either way — which is what the first version of it did.
        probe = (b64(json.dumps({"alg": "HS256", "typ": "JWT",
                                 "kid": "never-seen"}).encode())
                 + b"." + b64(json.dumps({"iss": ISS, "aud": AUD, "exp": now + 300,
                                          TENANT_CLAIM: "t"}).encode()))
        probe = (probe + b"." + b64(_hmac.new(pub_pem, probe,
                                              hashlib.sha256).digest())).decode()
        SVC._jwks_cache["last_attempt"] = 0.0
        before = fetches["n"]
        check("and that token is rejected", SVC.authorised(bearer(probe)) is None)
        check("a token whose algorithm is not pinned is refused before any key is fetched",
              fetches["n"] == before, (before, fetches["n"]))
        # The floor was opened to make that check mean something; close it
        # again, because the cache assertions below depend on a recent attempt
        # and a test that quietly changes a precondition for the next one is
        # its own kind of wrong answer.
        SVC._jwks_cache["last_attempt"] = time.time()

        # ---------- the cache, and rotation ----------
        before = fetches["n"]
        for _ in range(5):
            SVC.authorised(bearer(mint()))
        check("the key set is cached rather than fetched per request",
              fetches["n"] == before, (before, fetches["n"]))

        # An unknown kid is exactly what somebody would send in a loop if this
        # were unbounded, so it is rate limited by when the last fetch was
        # attempted — not by whether the kid was found. Both halves of that are
        # worth pinning: inside the floor an unknown kid costs Atlassian
        # nothing at all, and past it costs one fetch however many arrive.
        before = fetches["n"]
        for _ in range(4):
            SVC.authorised(bearer(mint(kid="nope")))
        check("inside the refetch floor an unknown kid triggers no fetch at all",
              fetches["n"] == before, (before, fetches["n"]))

        SVC._jwks_cache["last_attempt"] = 0.0
        before = fetches["n"]
        for _ in range(4):
            SVC.authorised(bearer(mint(kid="nope")))
        check("past the floor it refetches once, not once per attempt",
              fetches["n"] == before + 1, (before, fetches["n"]))

        # Rotation: a new key appears under a new kid, and the floor is what
        # keeps it from being picked up instantly — so the floor is dropped to
        # prove the refetch works rather than waiting thirty seconds for it.
        served["keys"] = [jwk_of(other, "test-key-2")]
        SVC._jwks_cache["last_attempt"] = 0.0
        rotated = SVC.authorised(bearer(mint(k=other, kid="test-key-2")))
        check("a rotated key is picked up on the next unknown kid",
              bool(rotated) and rotated.get("tenant") == "tenant-abc", rotated)
        check("and the key it replaced stops verifying",
              SVC.authorised(bearer(mint(k=key, kid=KID))) is None)

        # ---------- misconfiguration must not serve ----------
        for missing in SVC.FORGE_ENV:
            keep = os.environ.pop(missing)
            problem = SVC.startup_problem()
            os.environ[missing] = keep
            check("without %s the service refuses to start" % missing,
                  problem is not None and missing in problem, problem)
    finally:
        srv.shutdown()
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        SVC._jwks_cache.update({"keys": {}, "fetched_at": 0.0, "last_attempt": 0.0})


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


def test_the_brief_never_states_a_figure():
    """The scheduled brief's guard: the model writes the sentences, never the
    numbers.

    Roadmap item 3 mails a written brief out weekly with nobody reading it
    first, which makes it the one place in this product where a model's prose
    reaches a customer unreviewed. `forge/src/brief.js` answers that by never
    letting the model near a figure — values are substituted from tool output
    and prose carrying a numeral is refused. ADR 0013.

    The refusal case is the one that matters most and it is checked against the
    real sentence rather than a copy: `forecast.Refusal.sentence()` produces it
    here, it is piped through the JavaScript, and it has to come back
    identical. A test holding two hand-written copies of that string would pass
    while the product paraphrased.
    """
    refusal = FC.Refusal(reason="too little completion history to sample from",
                         have=2, need=6).sentence()

    node = subprocess.run(["node", str(ROOT / "tests" / "brief_shapes.mjs")],
                          input=json.dumps({"refusal": refusal}),
                          capture_output=True, text=True, cwd=str(ROOT))
    if node.returncode != 0:
        check("the brief shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    b = json.loads(node.stdout)

    # Prose a model may write. Each of these contains a word that *contains* a
    # number word — often, someone, behalf, phone — so a substring check would
    # refuse all of them and the guard would be a nuisance rather than a guard.
    usable = [name for name, probs in b["usable"].items() if probs]
    check("prose with no figure in it is usable", not usable, usable)

    # Every way a figure can arrive: digits, a percentage, a decimal, a
    # thousands separator, a word, a capitalised word, a fraction, a slot the
    # model placed itself, and nothing at all.
    slipped = [name for name, probs in b["carriesAFigure"].items() if not probs]
    check("prose carrying a figure is refused, however it is spelled",
          not slipped, slipped)

    # The refusal, byte for byte, and the model's prose nowhere near it.
    sec = b["refusedSection"]
    check("a refused section prints the tool's sentence verbatim",
          sec.get("text") == refusal,
          (sec.get("text", "")[:60], refusal[:60]))
    check("a refused section keeps the clause that is the point of the refusal",
          "absent, not noisy" in sec.get("text", ""))
    check("a refused section discards what the model wrote about it",
          "on track" not in sec.get("text", "")
          and "finish early" not in sec.get("text", ""))
    check("a refused section says it refused", sec.get("refused") is True)

    # A slot the tools did not fill stops the brief, and does not come back
    # half-rendered beside the complaint — a caller reading `text` first would
    # send "Throughput was  items", which a reader completes themselves.
    check("a figure the tools did not return refuses",
          "problems" in b["missingSlot"] and "text" not in b["missingSlot"],
          list(b["missingSlot"]))
    check("a figure the tools did return is substituted",
          b["filled"].get("text") == "Throughput was 9 items against 12 committed.",
          b["filled"])
    # Written as `x === undefined || x === null || x === ""` rather than `!x`
    # for this one case: a measured zero is a figure, and refusing it would be
    # ADR 0010 applied backwards — silence where there was a real observation.
    check("a measured zero is a figure, not a missing one",
          b["filledWithZero"].get("text") == "Unplanned work was 0 items.",
          b["filledWithZero"])

    # One bad section stops the whole brief rather than shrinking it. A brief
    # that does not arrive is noticed; a brief that quietly lost a section is
    # not, and at a weekly cadence nobody goes looking.
    check("one unusable section stops the whole brief",
          b["brokenBrief"]["sent"] is False and b["brokenBrief"]["problems"],
          b["brokenBrief"].get("problems"))
    check("the complaint names the section it came from",
          any(p.startswith("Forecast:") for p in b["brokenBrief"]["problems"]),
          b["brokenBrief"]["problems"])

    # A refusal is not a broken section. It is the product working.
    check("a brief carrying a refusal is still sent",
          b["briefWithARefusal"]["sent"] is True
          and b["briefWithARefusal"]["refusedSections"] == ["Forecast"],
          b["briefWithARefusal"].get("refusedSections"))
    check("the refusal reaches the sent brief intact",
          refusal in b["briefWithARefusal"]["text"])

    # The guard is bounded and has to say so. A number-word list cannot be
    # complete and a check that reads as total is how a truncated list gets
    # mistaken for a full one — the failure this repository has had twice.
    check("the guard states what it does not catch", bool(b["unchecked"].strip()))

    # The instruction and the check must describe one rule. A prompt that
    # invites a figure and a guard that forbids one produces a brief that fails
    # every week for a reason invisible from the prompt.
    rule = b["proseRule"].lower()
    check("the model is told the rule the guard enforces",
          "number" in rule and "words" in rule and "digits" in rule, rule[:80])


def test_the_deploy_trigger_covers_everything_the_image_ships():
    """A file that reaches the image must reach the deploy.

    `deploy.yml` filters on paths, and a path filter fails silently in one
    direction: too broad and you get a rebuild nobody asked for, which is
    noise; too narrow and the image content changes while the running service
    does not, which is a service quietly older than the source that describes
    it. Only the second one is dangerous, and neither shows up as a red run.

    The filter was narrowed once, to stop `service/README.md` redeploying both
    regions. That is safe because the Dockerfile copies `service/` by *file
    name* and a README is not one of them. It would not be safe for
    `agent/tools/`, which is copied as a whole directory — a markdown file
    added there does ship. This asserts that asymmetry rather than leaving it
    to the comment that explains it.
    """
    wf = ROOT / ".github" / "workflows" / "deploy.yml"
    if not wf.exists():
        check("deploy.yml is present", False, str(wf))
        return

    text = wf.read_text()
    # Deliberately parsed by hand rather than with PyYAML: `on:` is the YAML 1.1
    # boolean and safe_load turns the key into True, which is the sort of thing
    # that makes a test fail for a reason unrelated to what it checks.
    block = re.search(r"^\s*paths:\n((?:\s*-\s*'[^']*'\s*(?:#.*)?\n|\s*#.*\n|\s*\n)+)",
                      text, re.M)
    if not block:
        check("the deploy workflow filters on paths", False, "no paths: block")
        return
    patterns = re.findall(r"-\s*'([^']*)'", block.group(1))
    positive = [p for p in patterns if not p.startswith("!")]
    negative = [p[1:] for p in patterns if p.startswith("!")]

    check("the deploy trigger has path patterns", bool(positive), patterns)

    def matches(pattern, path):
        """GitHub's glob, narrowly: ** spans separators, * does not."""
        rx, i = "", 0
        while i < len(pattern):
            if pattern.startswith("**", i):
                rx, i = rx + ".*", i + 2
            elif pattern[i] == "*":
                rx, i = rx + "[^/]*", i + 1
            else:
                rx, i = rx + re.escape(pattern[i]), i + 1
        return re.fullmatch(rx, path) is not None

    dockerfile = (ROOT / "service" / "Dockerfile").read_text()
    copies = re.findall(r"^COPY\s+(\S+)\s+\S+", dockerfile, re.M)
    check("the Dockerfile has COPY sources to check", bool(copies), copies)

    # Every file the image ships triggers a deploy when it changes.
    for src in copies:
        if src.endswith("/"):
            continue
        covered = any(matches(p, src) for p in positive)
        excluded = any(matches(n, src) for n in negative)
        check("a change to %s deploys" % src, covered and not excluded,
              {"covered": covered, "excluded": excluded})

    # A directory copied wholesale ships whatever is put in it later, so no
    # exclusion may reach inside one. This is the assertion that would have
    # stopped `!agent/tools/**.md` — which looks like the same tidy-up as the
    # one above and is not.
    for src in copies:
        if not src.endswith("/"):
            continue
        reaching = [n for n in negative if n.startswith(src)]
        check("no exclusion reaches inside %s, which ships wholesale" % src,
              not reaching, reaching)

    # And the narrowing that prompted all this still holds.
    check("editing the service README does not redeploy",
          any(matches(n, "service/README.md") for n in negative),
          negative)


def _manifest_item(text, key):
    """The scalar fields of the manifest list item introduced by `- key: <key>`.

    Regex rather than PyYAML, deliberately and for the same reason
    `test_forge_manifest_matches_the_code` does it: yaml is not a dependency of
    this repository, CI installs only `service/requirements.txt` for this suite,
    and adding a parser to the *service's* requirements to read a *Forge* file
    would put a package in the production image that nothing in it imports.
    """
    m = re.search(r"^(\s+)-\s*key:\s*%s\s*$" % re.escape(key), text, re.M)
    if not m:
        return {}
    field_indent = len(m.group(1)) + 2
    out = {}
    for line in text[m.end():].split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if len(line) - len(line.lstrip()) < field_indent:
            break
        f = re.match(r"\s+([A-Za-z]\w*):\s*(\S*)\s*$", line)
        if f:
            out[f.group(1)] = f.group(2)
    return out


def test_the_weekly_brief_is_wired_to_its_own_function():
    """A scheduled trigger is not a resolver call, and the manifest said it was.

    `weekly-brief` pointed at the `resolver` function from the day it was
    declared. Forge invokes a scheduled trigger's function directly with an
    event; `resolver.getDefinitions()` returns a dispatcher that expects
    `{ call: { functionKey } }` and would not have recognised one, so the first
    fire would have failed — in a tenant, on a timer, with nobody watching.

    Nothing caught it because a trigger that is declared and never runs looks
    exactly like one that works. That is the failure mode this asserts against:
    the trigger's function must not be the resolver's.
    """
    man = (ROOT / "forge" / "manifest.yml").read_text()

    check("the weekly brief trigger is declared",
          re.search(r"^\s+scheduledTrigger:\s*$", man, re.M)
          and re.search(r"-\s*key:\s*weekly-brief\s*$", man, re.M))
    trig = _manifest_item(man, "weekly-brief")

    # Forge accepts only these four, and `week` is the cadence item 3 describes.
    check("the trigger's interval is one Forge accepts",
          trig.get("interval") in ("fiveMinute", "hour", "day", "week"),
          trig.get("interval"))

    # Only `function:` entries carry a handler, so an adjacent key/handler pair
    # is one of them wherever it appears.
    functions = dict(re.findall(r"-\s*key:\s*(\S+)\s*\n\s+handler:\s*(\S+)", man))
    resolver_fn = [k for k, h in functions.items() if h == "index.handler"]
    check("the resolver's own function is still index.handler", resolver_fn,
          functions)
    check("the trigger does NOT point at the resolver's function",
          trig.get("function") not in resolver_fn,
          {"trigger": trig.get("function"), "resolver": resolver_fn})
    check("the trigger's function exists in the manifest",
          trig.get("function") in functions, functions)

    handler = functions.get(trig.get("function"), "")
    check("the trigger's handler is a plain export, not the dispatcher",
          handler.startswith("index.") and handler != "index.handler", handler)

    # ...and the export it names is really there. A handler naming a function
    # that does not exist fails at the first fire, which is a week after a
    # deploy nobody is still watching.
    src = (ROOT / "forge" / "src" / "index.js").read_text()
    exported = handler.split(".", 1)[1] if "." in handler else ""
    check("index.js exports the function the trigger names",
          re.search(r"export\s+const\s+%s\s*=" % re.escape(exported), src),
          exported)

    # Scheduled triggers run with no user principal, so `asUser()` throws in
    # one. The trigger's own path must not depend on it — and the panel's must
    # keep it, because reading as the user is what makes a viewer unable to see
    # an issue they could not see in Jira.
    after = src.split("export const %s" % exported, 1)[-1]
    # Comments stripped first. The trigger's body *discusses* asUser() at
    # length — why reading as the user is what makes permission mirroring hold,
    # and why asApp() is not a free repair — and a naive substring search reads
    # that explanation as the thing it warns against.
    code = re.sub(r"/\*.*?\*/", "", after, flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)
    check("the trigger's own body makes no asUser() call",
          "asUser()" not in code, code[:160])
    check("the panel's reads are still asUser()",
          "asUser()" in re.sub(r"/\*.*?\*/", "", src, flags=re.S))


def test_the_llm_module_matches_the_model_the_code_asks_for():
    """A model the app has not declared fails inside a tenant, on a timer.

    `forge lint` refuses a `chat()` call with no `llm` module, but it cannot
    know which model string the code passes — so a declared family and a
    requested model that is not in it is a runtime failure a deploy would not
    show. ADR 0013.
    """
    man = (ROOT / "forge" / "manifest.yml").read_text()
    block = re.search(
        r"^\s+llm:\s*$\n\s+-\s*key:\s*(\S+)\s*$\n\s+model:\s*$\n((?:\s+-\s*\S+\s*$\n?)+)",
        man, re.M)
    check("the llm module is declared", bool(block))
    if not block:
        return
    families = re.findall(r"-\s*(\S+)", block.group(2))
    check("it declares a model family", bool(families), families)
    check("only one llm module, which is all Forge permits",
          len(re.findall(r"^\s+llm:\s*$", man, re.M)) == 1)

    node = subprocess.run(["node", str(ROOT / "tests" / "brief_shapes.mjs")],
                          input=json.dumps({"refusal": "R"}),
                          capture_output=True, text=True, cwd=str(ROOT))
    if node.returncode != 0:
        check("the brief shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    b = json.loads(node.stdout)
    check("the model the code asks for is in a declared family",
          any(b["model"].startswith(f) for f in families),
          {"model": b["model"], "declared": families})

    # @forge/llm has to be a declared dependency or the bundle will not build.
    pkg = json.loads((ROOT / "forge" / "package.json").read_text())
    check("@forge/llm is a declared dependency",
          "@forge/llm" in pkg.get("dependencies", {}),
          list(pkg.get("dependencies", {})))


def test_the_brief_prompt_can_produce_an_answer_its_own_guard_accepts():
    """The instruction and the check must want the same thing.

    The guard refuses prose carrying a figure. So the prompt must not hand the
    model a figure already written into a sentence — prose it is shown is prose
    it copies, and a copied figure is refused by the very guard this brief
    depends on. A prompt that cannot produce a passing answer fails every week
    for a reason nothing in the prompt reveals.
    """
    node = subprocess.run(["node", str(ROOT / "tests" / "brief_shapes.mjs")],
                          input=json.dumps({"refusal": "R"}),
                          capture_output=True, text=True, cwd=str(ROOT))
    if node.returncode != 0:
        check("the brief shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    b = json.loads(node.stdout)

    msgs = b["messages"]
    check("the prompt is a system message and a user message",
          [m["role"] for m in msgs] == ["system", "user"],
          [m["role"] for m in msgs])
    check("the model is given the rule the guard enforces",
          b["proseRule"] in msgs[0]["content"])

    # Figures arrive as named values, one per line — never as a sentence.
    user = msgs[1]["content"]
    check("figures are named, not written into prose",
          "- throughput: 9" in user and "- committed: 12" in user, user[:90])

    # A refused figure is named so the model does not write around a gap it
    # cannot see, but its sentence is withheld: handing over the wording is
    # what invites the paraphrase ADR 0013 forbids.
    check("a refused figure is named to the model", "forecast" in user)
    check("but its refusal sentence is not handed over",
          "absent, not noisy" not in user and "No forecast:" not in user, user[-140:])

    # The four states a completion comes back in.
    r = b["responses"]
    check("a finished completion yields trimmed prose",
          r["ok"].get("prose") == "Throughput fell against the previous sprint.",
          r["ok"])
    check("a truncated completion is discarded, not used",
          "problems" in r["truncated"] and "prose" not in r["truncated"],
          r["truncated"])
    for state in ("empty", "noChoices", "rubbish"):
        check("a %s completion yields no prose" % state,
              "prose" not in r[state], r[state])

    # And nothing the model returns may bypass the guard on its way in.
    check("the prompt's own text would pass the guard it asks for",
          not [w for w in b["numberWords"] if (" %s " % w) in msgs[0]["content"].lower()],
          msgs[0]["content"][:100])


def test_a_scheduled_run_that_cannot_deliver_says_so_before_doing_work():
    """Three blockers, checked before a single Jira call.

    A trigger fires with nobody watching, so it must be cheap when it can do
    nothing. All three of these are real today, and the order matters: without a
    board there is nothing to compute at all, which is why it is first — the
    other two are about where the answer goes.
    """
    node = subprocess.run(["node", str(ROOT / "tests" / "brief_shapes.mjs")],
                          input=json.dumps({"refusal": "R"}),
                          capture_output=True, text=True, cwd=str(ROOT))
    if node.returncode != 0:
        check("the brief shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    b = json.loads(node.stdout)["blockers"]

    check("nothing configured names all three blockers",
          len(b["nothingConfigured"]) == 3, b["nothingConfigured"])
    check("the missing board is named first",
          "board" in b["nothingConfigured"][0], b["nothingConfigured"][0])
    check("each thing supplied removes exactly one blocker",
          [len(b["scopeOnly"]), len(b["scopeAndRecipients"]), len(b["allThree"])] == [2, 1, 0],
          {k: len(v) for k, v in b.items()})

    # Every sentence has to say what is absent rather than what to do about it —
    # this text is what a future reader finds in a log line, and "TODO" in a log
    # is not a fact about the run.
    for sentence in b["nothingConfigured"]:
        check("the blocker reads as a fact, not a to-do",
              "TODO" not in sentence and len(sentence) > 40, sentence)

    # The handler returns its reasons rather than throwing: a scheduled trigger
    # is not retried, and a thrown error is a failed invocation with the reason
    # only in a stack trace.
    src = (ROOT / "forge" / "src" / "index.js").read_text()
    body = src.split("export const weeklyBrief", 1)[-1]
    check("the handler returns its reasons rather than throwing",
          "return { sent: false" in body and "throw" not in body.split("};")[0],
          body[:160])


def test_a_boards_recipients_are_validated_before_anyone_is_told():
    """A recipient list decides who is told what is on a board.

    The failures that matter are not crashes. They are a brief reaching someone
    it should not, and a brief reaching nobody while the board looks configured
    — and at a weekly cadence the second one goes unnoticed for a month. Every
    case below is a way an administrator gets this wrong, and they arrive one at
    a time, so each is reported rather than the first stopping the rest.

    ADR 0014.
    """
    node = subprocess.run(["node", str(ROOT / "tests" / "brief_shapes.mjs")],
                          input=json.dumps({"refusal": "R"}),
                          capture_output=True, text=True, cwd=str(ROOT))
    if node.returncode != 0:
        check("the brief shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    r = json.loads(node.stdout)["recipients"]

    check("a well-formed config has no problems", r["goodProblems"] == [],
          r["goodProblems"])
    check("both audiences item 3 describes are offered",
          r["audiences"] == ["exec", "team"], r["audiences"])

    # The notify endpoint's own shape, built in one place so no caller
    # assembles `users` from parts and gets it wrong where only a tenant sees.
    sends = r["sends"]["sends"]
    check("a board resolves to one send per configured audience",
          [x["audience"] for x in sends] == ["exec", "team"], sends)
    check("users are wrapped as accountId objects",
          sends[0]["to"]["users"] == [{"accountId": "5b10a2844c20165700ede21g"}],
          sends[0]["to"])
    check("groups are wrapped as name objects",
          sends[0]["to"]["groups"] == [{"name": "leadership"}], sends[0]["to"])
    check("the anchor issue travels with each send",
          all(x["anchorIssue"] == "SFT-1" for x in sends), sends)
    # An audience with only groups must not carry an empty `users` key — the
    # endpoint reads presence, not length.
    check("an audience with no users omits the key entirely",
          "users" not in r["groupsOnly"]["sends"][0]["to"],
          r["groupsOnly"]["sends"][0]["to"])

    # Every way this is got wrong, each caught on its own.
    for name in ("email", "displayName", "emptyAudience", "noAudience",
                 "noAnchor", "badAnchor", "notAnObject"):
        check("a config with %s is refused" % name, len(r["each"][name]) >= 1,
              r["each"][name])

    # The one that would be most tempting to be helpful about. An address
    # cannot be delivered by this endpoint at all, and resolving it would mean
    # this app claiming the person at that address is that Jira user.
    check("an email address says why it cannot work rather than being resolved",
          "no field for an address" in " ".join(r["each"]["email"]),
          r["each"]["email"])
    check("an audience that sends to nobody says so in those terms",
          "indistinguishable" in " ".join(r["each"]["emptyAudience"]),
          r["each"]["emptyAudience"])

    # One broken audience refuses the whole board, including the audience that
    # was fine: the entry was written by one person in one sitting, and sending
    # half of what they asked for while saying nothing is the failure here.
    check("one broken audience refuses the whole board",
          "problems" in r["partiallyBroken"] and "sends" not in r["partiallyBroken"],
          list(r["partiallyBroken"]))

    check("an unconfigured board is named, not silently skipped",
          "problems" in r["unconfigured"]
          and "99" in " ".join(r["unconfigured"]["problems"]),
          r["unconfigured"])
    for name in ("empty", "notAnObject", "noBoardsKey"):
        check("a %s config is refused" % name, len(r[name]) >= 1, r[name])

    # A config that does not validate offers no boards at all, rather than the
    # ones that happened to parse — a partly-walked run is a partly-informed
    # reader who cannot tell.
    check("a config that does not validate offers no boards to walk",
          r["boardsFromBroken"] == [], r["boardsFromBroken"])
    check("a config that does validate offers every board",
          r["boards"] == ["2", "7"], r["boards"])

    # Constant, not configurable. This is the only permission filtering in the
    # product that is enforced rather than promised, and the first thing that
    # would be switched off by someone whose brief did not arrive.
    check("every send is restricted to those who may BROWSE the anchor",
          r["restrict"] == {"permissions": [{"key": "BROWSE"}]}, r["restrict"])


def test_the_brief_reaches_an_inbox_without_carrying_a_payload():
    """The email body is a new output surface for issue text.

    Every issue-derived string in this product went to a page this repository
    controls, until this one. A brief lands in a mail client rendered by
    software nobody here chose, and a Jira summary is writable by anyone who can
    raise a ticket — the stored XSS in 1.4.0 came from two call sites
    interpolating `i.key` and `i.summary` directly.

    Two distinct bugs are checked, because escaping only answers one of them:
    markup in the HTML body, and a newline in the *subject*, which is a mail
    header and ends where the newline is. ADR 0014.
    """
    node = subprocess.run(["node", str(ROOT / "tests" / "brief_shapes.mjs")],
                          input=json.dumps({"refusal": "R"}),
                          capture_output=True, text=True, cwd=str(ROOT))
    if node.returncode != 0:
        check("the brief shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    m = json.loads(node.stdout)["mail"]

    # The same five characters src/app.js escapes, character for character. A
    # second escaper covering four of the five is the shape this bug arrives in.
    app_js = (ROOT / "src" / "app.js").read_text()
    check("the email escaper matches the page's, character for character",
          m["escAll"] == "&amp;&lt;&gt;&quot;&#39;", m["escAll"])
    check("and the page still escapes those five",
          all(e in app_js for e in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;")))

    html = m["body"]["htmlBody"]
    check("hostile markup does not survive into the HTML body",
          "<script>" not in html and "onmouseover=\"x\"" not in html,
          html[:120])
    check("the board name is still present, escaped rather than dropped",
          "&lt;script&gt;" in html, html[:160])

    # The path a polite fixture never exercises. A section's text is prose plus
    # substituted figures, and a figure can carry issue text — `reattach` puts
    # summaries back on item_risk rows before any of this is rendered. Removing
    # the escape here passed every other assertion in this file.
    body_only = html.split("Blocked:", 1)[-1] if "Blocked:" in html else ""
    check("hostile text inside a section body is escaped",
          body_only and "<script>" not in body_only
          and 'onmouseover="x"' not in body_only, body_only[:120])
    check("and a hostile section heading is escaped too",
          'onerror="alert(1)"' not in html and "&lt;img" in html,
          html[:200])

    # A tracker URL arrives from the same data as everything else.
    check("only http(s) URLs survive",
          m["safeUrl"]["https"] and not m["safeUrl"]["javascript"]
          and not m["safeUrl"]["data"] and not m["safeUrl"]["empty"],
          m["safeUrl"])
    check("a javascript: board link is dropped, not rendered",
          "javascript:" not in html)

    # A refusal is a statement that was answered, not a paragraph that happened
    # to be short, and it must not be styled as prose.
    check("a refusal is set apart from the prose around it",
          "border-left" in html and "absent, not noisy" in html)

    # The plain-text part is text. `&amp;` in it is a bug, not a precaution.
    text = m["body"]["textBody"]
    check("the plain-text part is not HTML-escaped",
          "&amp;" not in text and "&lt;" not in text, text[:120])
    check("the plain-text part still carries the refusal verbatim",
          "absent, not noisy" in text)

    # Header injection. Escaping does nothing about this one.
    subject = m["headerInjection"]
    check("a newline in a board name cannot break out of the subject header",
          "\n" not in subject and "\r" not in subject, repr(subject))
    check("the injected header text is flattened, not silently dropped",
          "Bcc:" in subject, subject)
    check("an over-long subject is capped visibly rather than silently",
          len(m["longSubject"]) <= 200 and m["longSubject"].endswith("\u2026"),
          (len(m["longSubject"]), m["longSubject"][-3:]))

    # Built in one place so no call site can leave the restriction out.
    check("every notification payload carries the BROWSE restriction",
          m["payload"].get("restrict") == {"permissions": [{"key": "BROWSE"}]},
          m["payload"])
    check("and carries the four fields the endpoint reads",
          set(m["payload"]) == {"subject", "textBody", "htmlBody", "to", "restrict"},
          sorted(m["payload"]))


def test_nothing_is_sent_that_the_guards_would_have_stopped():
    """Compose, render, send — with the model and the send stubbed.

    `forge/src/compose.js` exists so this path can be run at all: `index.js`
    imports the Forge SDK and cannot be loaded outside Atlassian's runtime, so
    anything left in it is provable only by deploying and watching. The code
    that decides what reaches an inbox is not code to find out about that way.
    """
    node = subprocess.run(["node", str(ROOT / "tests" / "brief_shapes.mjs")],
                          input=json.dumps({"refusal": "R"}),
                          capture_output=True, text=True, cwd=str(ROOT))
    if node.returncode != 0:
        check("the brief shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    p = json.loads(node.stdout)["pipeline"]

    ok = p["usable"]
    check("each configured audience gets its own message",
          [r["audience"] for r in ok["out"]["results"]] == ["exec", "team"],
          ok["out"])
    check("both were sent", all(r["sent"] for r in ok["out"]["results"]),
          ok["out"])
    check("the subjects name the audience",
          ok["subjects"][0].startswith("Executive")
          and ok["subjects"][1].startswith("Team"), ok["subjects"])
    check("every send is against the configured anchor issue",
          ok["anchors"] == ["SFT-1", "SFT-1"], ok["anchors"])
    check("the refused section is carried and named, not dropped",
          all(r["refusedSections"] == ["Forecast"] for r in ok["out"]["results"]),
          ok["out"])
    check("the refusal reaches the HTML body verbatim",
          "absent, not noisy" in ok["html"], ok["html"][-120:])

    # The one that matters most. brief.js refusing prose that carries a figure
    # is already covered; this asserts nothing reaches an inbox when it does.
    check("prose that fails the guard sends nothing at all",
          p["guarded"]["sends"] == 0, p["guarded"])
    check("and says which section stopped it",
          any("Delivery" in " ".join(r.get("reasons", []))
              for r in p["guarded"]["out"]["results"]),
          p["guarded"]["out"])

    check("a config that does not validate sends nothing",
          p["badConfig"]["sends"] == 0 and "reasons" in p["badConfig"]["out"],
          p["badConfig"]["out"])

    # One audience failing must not take the other with it: they are separate
    # messages to separate people, and a weekly cadence means the second
    # audience would wait a week for someone else's problem.
    jr = p["jiraRefuses"]
    check("Jira refusing one audience still attempts the other",
          jr["attempts"] == 2, jr)
    check("and the failure is reported with Jira's own status",
          jr["out"]["results"][0]["sent"] is False
          and "403" in " ".join(jr["out"]["results"][0]["reasons"])
          and jr["out"]["results"][1]["sent"] is True,
          jr["out"])


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
    print("epic sizing over the calculator's payload")
    test_epic_sizing_survives_the_projection()
    print("the forecast over a board with no sprints")
    test_the_forecaster_counts_one_issue_once()
    test_a_window_is_not_a_deadline_to_the_forecaster()
    print("the Forge invocation token")
    test_forge_token_verification()
    print("the scheduled brief")
    test_the_brief_never_states_a_figure()
    print("the Forge app's dependencies")
    test_forge_app_dependencies()
    print("the weekly brief")
    test_the_weekly_brief_is_wired_to_its_own_function()
    test_the_llm_module_matches_the_model_the_code_asks_for()
    test_the_brief_prompt_can_produce_an_answer_its_own_guard_accepts()
    test_a_scheduled_run_that_cannot_deliver_says_so_before_doing_work()
    print("who a boards brief goes to")
    test_a_boards_recipients_are_validated_before_anyone_is_told()
    print("the brief as an email")
    test_the_brief_reaches_an_inbox_without_carrying_a_payload()
    test_nothing_is_sent_that_the_guards_would_have_stopped()
    print("the deploy trigger")
    test_the_deploy_trigger_covers_everything_the_image_ships()
    print("the container image")
    test_dockerfile_copies_everything_the_service_imports()
    print("startup")
    test_refuses_to_start_unauthenticated()

    print()
    if failures:
        print("%d check(s) failed: %s" % (len(failures), ", ".join(failures)))
        sys.exit(1)
    print("all service checks passed")
