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
import metrics as MT     # noqa: E402
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
    # `.team` as a bare substring was too blunt, and the recipient audiences are
    # what showed it: a board's brief goes to an `exec` and a `team` audience,
    # so reading `entry.team.users` to count recipients tripped a check about
    # the *forecast slice*. Two unrelated meanings of one word, and the check
    # was guarding neither precisely. What it is actually for is the resolver
    # deciding which contexts a forecast samples, so it looks for that: a
    # comparison of team labels, or a context's team read for anything other
    # than an audience's recipient list.
    team_reads = [m.group(0) for m in re.finditer(r"\.team\b(?!\?\.(users|groups))",
                                                 idx_js)]
    check("the resolver never reads a team label of its own",
          not team_reads and "team ===" not in idx_js,
          {"reads": team_reads[:4],
           "why": "a team comparison in the resolver is a second team_slice"})

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

    # `content` is `string | ContentPart[]` in the SDK's own declarations. This
    # was written against the published example, which shows only the string,
    # so the array form reported "the model returned no text" for a completion
    # that had text in it — found in a tenant, on a timer, after the guards it
    # was blocking had all been proved.
    check("content delivered as text parts is read, not refused",
          r["partsArray"].get("prose") == "Delivery slowed against last sprint.",
          r["partsArray"])
    # A part this does not understand is skipped rather than stringified:
    # "[object Object]" in somebody's inbox is worse than a refusal.
    check("a part that is not text is skipped, not stringified",
          r["mixedParts"].get("prose") == "Only this.", r["mixedParts"])
    check("an empty parts array is still no text",
          "prose" not in r["emptyParts"], r["emptyParts"])

    # `stop` is OpenAI's word for a finished completion. Anthropic says
    # `end_turn`, so a `!== 'stop'` guard refused every good answer as
    # truncated — three sections at a time, in a tenant, on a timer. Listed
    # explicitly now instead of inferred from one sample.
    fr = r["finishReasons"]
    check("end_turn is a finished completion, not a truncated one",
          fr["end_turn"] == "accepted", fr)
    check("and so are stop and stop_sequence",
          fr["stop"] == "accepted" and fr["stop_sequence"] == "accepted", fr)
    check("max_tokens and length are still refused as truncation",
          fr["max_tokens"] == "truncated" and fr["length"] == "truncated", fr)
    # An unknown reason is refused rather than accepted: it might be a
    # truncation this does not recognise, and half a brief reads like a whole
    # one. It is *named* in the message, which is the only reason the end_turn
    # case took one deploy to find rather than several.
    check("an unrecognised finish reason is refused and named",
          fr["tool_use"] == "unrecognised", fr)

    # The model declining is its own category, and the distinction is not
    # cosmetic: the first version of the unrecognised-reason message advised
    # adding the value to FINISHED, which for `refusal` would have meant
    # shipping whatever came back when the model had chosen not to answer.
    check("a model refusal is reported as a refusal, not a truncation",
          fr["refusal"] == "declined", fr)
    check("and so is a content filter",
          fr["content_filter"] == "declined", fr)
    check("declined never overlaps finished or truncated",
          not (set(r["declinedList"]) & (set(r["finishedList"]) | set(r["truncatedList"]))),
          {"declined": r["declinedList"], "finished": r["finishedList"],
           "truncated": r["truncatedList"]})
    check("the two lists do not overlap",
          not (set(r["finishedList"]) & set(r["truncatedList"])),
          {"finished": r["finishedList"], "truncated": r["truncatedList"]})

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

    # A scheduled run has no page to render an error into, so a reason that is
    # not logged reaches nobody. The first real run in a tenant reported
    # "1 board(s), 0 message(s) sent" and nothing else — a summary nobody can
    # act on, with every reason sitting unread in the returned object.
    check("the handler logs why a board sent nothing, not only how many did",
          re.search(r"console\.log\(`weekly brief, board \$\{board\.boardId\}", body),
          body[-300:])

    # ...and no issue key goes into it. `CLAUDE.md` forbids one reaching a log:
    # an access log holding issue keys is a copy of part of the backlog. The
    # anchor's key was in the send-failure sentence until the logging existed,
    # which is how a safe field becomes an unsafe one — by something else
    # starting to read it.
    check("no reason sentence carries an issue key",
          "notification for ${anchorIssue}" not in src,
          [ln for ln in src.split("\n") if "anchorIssue" in ln and "reason" in ln][:2])


def test_a_stored_id_can_be_shown_as_a_name():
    """The search stops anyone needing to know an account id. This stops the
    field being unreadable to whoever opens the tile next.

    A recipient list is a disclosure control, and one nobody can check is not
    doing its job: `712020:5ad8ac88-…, 60ad2eb506bf0c006a432a17` is a list an
    administrator can only take on trust.

    What is guarded here is the same projection discipline as the search — the
    bulk endpoint returns `emailAddress` too — plus the two states that only
    exist on this side. An id can resolve to a **deactivated** account, or to
    **nothing at all**, and those are different facts with different fixes. The
    search filters deactivated people out because adding one is a mistake being
    made now; here the mistake is already in the config, quietly sending
    nothing, and hiding the row would leave a list that looks complete.
    """
    node = subprocess.run(["node", str(ROOT / "tests" / "brief_shapes.mjs")],
                          input=json.dumps({"refusal": "R"}),
                          capture_output=True, text=True, cwd=str(ROOT))
    if node.returncode != 0:
        check("the brief shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    n = json.loads(node.stdout)["names"]
    rows = n["mixed"]["people"]

    # An allow-list of three fields. `state` is the third and it is a state, not
    # a flag: two booleans would let "deactivated" and "no such account" be read
    # as each other, which is how "no sprint calendar" came to be printed for
    # three unrelated causes.
    fields = {k for row in rows for k in row}
    check("a named id carries an account id, a display name and a state, and "
          "nothing else", fields == {"accountId", "displayName", "state"},
          sorted(fields))
    for leaked in ("example.com", "avatarUrls", "timeZone", "locale", "emailAddress"):
        check("no %s survives the name projection" % leaked,
              leaked not in n["serialised"], n["serialised"][:160])

    # Every id asked about gets a row, in the order it was asked about. Four
    # names against five ids, with no way to tell which one is missing, is the
    # list-that-looks-complete this repository pays for most often.
    check("every id asked about comes back with a row",
          [r["accountId"] for r in rows] == n["asked"],
          [[r["accountId"] for r in rows], n["asked"]])

    state = {r["accountId"]: r["state"] for r in rows}
    check("a deactivated account is shown rather than filtered out",
          state.get("a2") == "deactivated", state)
    check("an id that matches no account says so in its own words",
          state.get("ghost") == "unknown", state)
    check("and the two are not the same state",
          state.get("a2") != state.get("ghost"), state)
    check("a live account is not marked as either",
          state.get("a1") == "active", state)
    check("an id that matched nothing carries no invented name",
          [r["displayName"] for r in rows if r["state"] == "unknown"] == [""], rows)

    # The note speaks only for what a reader cannot see by looking. The names
    # are listed directly beneath it.
    check("nothing wrong is said quietly, which is to say not at all",
          n["quietNote"] == "", n["quietNote"])
    check("a deactivated account is named as one in the note",
          "deactivated" in n["mixedNote"], n["mixedNote"])
    check("and says the brief reaches nobody there, rather than implying it",
          "reaches nobody" in n["mixedNote"], n["mixedNote"])
    check("an unresolvable id is named separately, not folded into the same "
          "sentence", "matches no account" in n["mixedNote"], n["mixedNote"])

    # No silent caps.
    check("the ids asked about in one call are capped",
          n["asking"] == n["max"], [n["asking"], n["max"]])
    check("and the remainder is counted, not dropped",
          n["over"] == 3, n["over"])
    check("and the note says how many were not looked up",
          str(n["over"]) in n["overNote"] and str(n["max"]) in n["overNote"],
          n["overNote"])
    check("a repeated id is asked about once", n["deduped"]["ask"] == ["a1", "a2"],
          n["deduped"])
    check("and deduplicating does not invent a remainder",
          n["deduped"]["over"] == 0, n["deduped"])

    # `user/bulk` paginates: the list is under `values`. Reading the envelope as
    # the answer would return no names for every id and the tile would state,
    # with confidence, that none of them exists.
    check("a response that is not a list is refused rather than read as empty",
          "problems" in n["notAList"], n["notAList"])

    src = (ROOT / "forge" / "src" / "index.js").read_text()
    block = src.split("resolver.define('namesFor'", 1)[-1].split("}));", 1)[0]
    check("the resolver exists", "user/bulk" in block, block[:160])
    # As the reader, like the search. As the app it would show names out of a
    # directory this reader may not browse.
    check("the name lookup runs as the reader, not as the app",
          "asUser()" in block and "jira(" not in block, block[:200])
    # The one way to send `accountId` more than once without hand-building a
    # URL and reaching for assumeTrustedRoute, which would throw away the only
    # guard `route` provides.
    # `route` hands a URLSearchParams through in query position without a second
    # round of encoding, which is the only way to send `accountId` repeatedly.
    # Building the query as a string works too and costs the one guard `route`
    # exists to provide, so the escape hatch must not be imported.
    imports = "".join(re.findall(r"^import .*?;$", src, flags=re.M | re.S))
    check("the repeated parameter goes through route, not around it",
          "URLSearchParams" in block and "assumeTrustedRoute" not in imports,
          [block[:120], imports[:120]])
    check("no new scope: the search's own scope covers this",
          "read:jira-user" in (ROOT / "forge" / "manifest.yml").read_text(), "")

    # One contract, two transports. The body shape is the contract; the page
    # must not learn which one answered.
    live = (ROOT / "scripts" / "serve_live.py").read_text()
    check("the loopback server answers the same route",
          "api/names" in live, "no api/names route")
    check("and says there is no directory rather than returning nobody",
          "user directory" in live.split("api/names", 1)[-1][:900], "")
    app = (ROOT / "src" / "app.js").read_text()
    check("the page names the route once, in the map that encodes it",
          app.count("namesFor:") == 1 and 'LIVE.get("namesFor"' in app, "")
    # Prose about @forge/bridge is everywhere in this file and is the point; an
    # import of it is the thing ADR 0009 forbids, and a substring check cannot
    # tell them apart.
    check("and the tile does not import a bridge to reach it",
          not re.search(r"""(?:^|[^\w])(?:import|require)\s*\(?\s*['"]@forge/bridge""",
                        app), "")

    # The tile is a form somebody is part-way through. Re-rendering it to show a
    # name would discard every unsaved edit in it, which is the rule the search
    # was written under and the one a second lookup is most likely to break.
    names_fn = app.split("function wireBriefNames", 1)[-1].split("\n}", 1)[0]
    check("the name lookup never re-renders the page",
          "render()" not in names_fn, [ln.strip() for ln in names_fn.split("\n")
                                       if "render()" in ln])
    # Two edits leave two lookups in flight; the slower one landing second would
    # paint names for ids the field no longer holds.
    check("a stale answer cannot overwrite a newer one",
          "latest" in names_fn and names_fn.count("mine !== latest") >= 2,
          names_fn[:200])

    # The list is the editable view now: the account-ID field is folded away
    # behind a disclosure so an administrator never meets it. Folded, not
    # removed — an id must still be pasteable where there is no directory to
    # search, and it is still the only thing the save reads.
    fields = app.split("function briefAudienceFields", 1)[-1].split("\n}", 1)[0]
    check("the account-ID field is still in the form",
          '-u" type="text"' in fields, fields[-400:])
    check("and is folded behind a disclosure rather than dropped",
          "<details" in fields and fields.index("<details")
          < fields.index('-u" type="text"'), "")
    check("and is still the only thing the save reads",
          'briefList(val("#br-" + a + "-u"))' in app, "")

    # A folded field with no directory to search is a tile nobody can configure
    # at all, so both lookups unfold it themselves. Never the other way: a
    # reader who folded it away again meant it.
    search_fn = app.split("function wireBriefSearch", 1)[-1].split("\n}", 1)[0]
    for who, body in (("the name list", names_fn), ("the search", search_fn)):
        check("%s unfolds the field when there is no directory" % who,
              "raw.open = true" in body, body[:200])
        check("and never folds it back", "raw.open = false" not in body, "")

    # Removing somebody used to mean deleting the right span of a comma
    # separated string. It is a button on their row now.
    check("each row carries a control that removes that person",
          "br-rm" in names_fn and "aria-label=\"Remove " in names_fn,
          names_fn[:200])
    check("and the removal is by account id, not by position",
          "filter(x => x !== p.accountId)" in names_fn,
          [ln.strip() for ln in names_fn.split("\n") if "filter(x" in ln])
    check("and it says what it removed, because saving is still a separate act",
          "Removed <b>" in names_fn, "")
    # A deleted control that leaves focus on nothing sends a keyboard reader
    # back to the top of the document.
    check("and focus lands somewhere after the button it was on is gone",
          "settle" in names_fn and ".focus()" in names_fn, "")



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


def test_the_brief_reads_the_shape_the_context_route_really_returns():
    """The forecast figures are nested, and this read them flat.

    `/v1/forecast` answers with `remaining_items` and `percentiles` at the top
    level. `/v1/forecast-context` — the route the scheduled brief actually
    calls — answers with `{sprint_completion, item_risk, next_commitment, ...}`
    and puts them inside the first. `sectionsFor` was written against the flat
    one, so in a tenant it produced *"the brief asks for remaining,
    landing_date and the tools did not return it"*: `fillSlots` refusing
    exactly as designed, over figures that were present under another key.

    **The shapes here come from the real tool**, not from a fixture written by
    hand. A fixture would have been written from the same misunderstanding that
    caused the bug, agreed with the code, and proved nothing — which is the
    whole reason this was found in production rather than here.
    """
    ds = json.loads((ROOT / "data" / "sample-bundle.json").read_text())
    cid = (ds.get("contexts") or [{}])[0].get("id")
    issues = [{k: v for k, v in i.items() if k in SVC.CALC_FIELDS} for i in ds["issues"]]
    base = {"dataset": {"issues": issues, "contexts": ds["contexts"],
                        "orgConfig": ds.get("orgConfig", {}), "meta": {}},
            "contextId": cid}
    available = SVC.route_forecast_context(base)

    thin = {**base, "dataset": {**base["dataset"], "issues": issues[:3]}}
    refused = SVC.route_forecast_context(thin)

    check("the context route nests its figures under sprint_completion",
          "sprint_completion" in available and "remaining_items" not in available,
          sorted(available))
    check("and the thin dataset really does refuse",
          available["sprint_completion"]["available"] is True
          and refused["sprint_completion"]["available"] is False,
          {"thin": refused["sprint_completion"]})
    # No `sentence` survives serialisation — `Refusal.sentence()` is a Python
    # method. Whatever the brief prints has to be built from `reason`.
    check("a refusal carries reason but no sentence",
          "reason" in refused["sprint_completion"]
          and "sentence" not in refused["sprint_completion"],
          sorted(refused["sprint_completion"]))

    node = subprocess.run(["node", str(ROOT / "tests" / "brief_shapes.mjs")],
                          input=json.dumps({"refusal": "R",
                                            "forecasts": {"available": available,
                                                          "refused": refused}}),
                          capture_output=True, text=True, cwd=str(ROOT))
    if node.returncode != 0:
        check("the brief shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    fs = json.loads(node.stdout)["forecastSection"]

    # `.get` throughout, not `[...]`. A missing key is the failure this test
    # exists to catch, and raising a KeyError aborts the whole suite with a
    # traceback instead of reporting it — which read as "the mutation was not
    # caught" when the mutation was caught and the measurement was wrong.
    got = fs["available"]["figures"]
    want = available["sprint_completion"]
    check("the brief reads remaining_items from where the tool puts it",
          got.get("remaining") == want["remaining_items"],
          {"brief": got, "tool": want["remaining_items"]})
    # The tool keys percentiles by int; JSON makes them strings on the way to
    # node. `sectionsFor` reads both, and so does this.
    pct = want["percentiles"]
    p85 = pct.get(85, pct.get("85"))
    check("and the 85th percentile date from where the tool puts it",
          got.get("landing_date") == p85, {"brief": got, "tool": p85})
    check("no figure the brief asks for is missing",
          got and all(v is not None for v in got.values()), got)

    # Verbatim, and only the tool's words — the same thing `fcRefusal` in
    # src/app.js does with the same fields. Composing the fuller sentence here
    # would be a second implementation of Refusal.sentence() in a second
    # language.
    said = fs["refused"]["refusal"] or ""
    check("a refused forecast quotes the tool's reason verbatim",
          refused["sprint_completion"]["reason"] in said, said)
    check("and carries have and need beside it",
          str(refused["sprint_completion"]["have"]) in said
          and str(refused["sprint_completion"]["need"]) in said, said)
    check("a refused forecast asks for no figures at all",
          fs["refused"]["figures"] == {}, fs["refused"])


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

    # Every way the model can give nothing usable keeps its own words. The
    # first live run in a tenant reported "the model returned no prose at all"
    # three times — which is what all four causes collapsed into, because the
    # reason from `proseFrom` was replaced by an empty string that then tripped
    # the empty-prose guard. A reason that names nothing is a reason nobody can
    # act on, and this is the second time in one session that shape appeared.
    mf = json.loads(node.stdout)["modelFailures"]
    for name in ("noChoices", "truncated", "emptyText", "rubbish"):
        check("a %s response is reported as itself" % name,
              mf[name] and "no prose at all" not in " ".join(mf[name]),
              mf[name])
    check("a truncated completion still says it was truncated",
          "stopped early" in " ".join(mf["truncated"]), mf["truncated"])

    # Asking again when the guard refuses. In a tenant the model wrote "two"
    # and "85" into every section despite the rule and nothing was sent — and a
    # weekly trigger would have repeated the same prompt for ever, so the
    # refusal was permanent rather than a bad week.
    rt = json.loads(node.stdout)["retries"]
    check("prose that passes first time costs one call",
          rt["firstTimeCalls"] == 1 and rt["firstTime"], rt)
    check("a model that breaks the rule is asked again, and its answer used",
          rt["relentsCalls"] == 2
          and rt["relents"] == "Throughput fell against the previous sprint.", rt)
    check("a model that breaks it twice is reported, not softened",
          rt["stubbornCalls"] == 2 and rt["stubborn"], rt)

    # The values are listed to the model by key, so a key with a digit in it
    # hands it a number to copy. `p85` did exactly that, and the model wrote
    # "85". Templates may carry digits — the model never sees a template.
    slots = json.loads(node.stdout)["slotNames"]
    digity = [s for s in slots if any(c.isdigit() for c in s)]
    check("no slot name contains a digit", not digity, digity or slots)

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


def js_problems_for(config):
    """`problemsIn` from forge/src/recipients.js, over one config."""
    script = (
        "import { problemsIn } from '../forge/src/recipients.js';"
        "let b='';process.stdin.on('data',d=>b+=d);"
        "process.stdin.on('end',()=>console.log(JSON.stringify(problemsIn(JSON.parse(b)))));"
    )
    r = subprocess.run(["node", "--input-type=module", "-e", script],
                       input=json.dumps(config), capture_output=True, text=True,
                       cwd=str(ROOT / "tests"))
    return json.loads(r.stdout) if r.returncode == 0 else ["node failed: " + r.stderr[-120:]]


def test_the_two_recipient_validators_agree():
    """`recipients.js` and `serve_live.recipient_problems` are one rule, twice.

    That is the thing this repository most reliably regrets, and it is here for
    the reason `orgconfig.validate` and `validateOrgConfig` are: the browser
    cannot call JavaScript in `forge/src/`, and the loopback server cannot call
    Node without becoming a Python program that needs Node. The alternative was
    for loopback to refuse the route, which would leave the editing half of the
    config tile exercised by nothing — it runs only in a browser, and the
    browser suite runs against that server.

    So the mirror is tolerated on one condition, which is this test: one set of
    cases, both implementations, and a disagreement about whether a config is
    usable fails. The wording of a sentence may differ between them; the verdict
    may not.
    """
    cases = json.loads((ROOT / "tests" / "fixtures" / "recipient-configs.json").read_text())
    check("the shared recipient cases are present", len(cases) >= 15, len(cases))
    check("and cover both verdicts",
          any(c["usable"] for c in cases) and any(not c["usable"] for c in cases))

    node = subprocess.run(["node", str(ROOT / "tests" / "brief_shapes.mjs")],
                          input=json.dumps({"refusal": "R"}),
                          capture_output=True, text=True, cwd=str(ROOT))
    if node.returncode != 0:
        check("the brief shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    js = dict(json.loads(node.stdout)["recipients"]["verdicts"])

    disagreed, wrong = [], []
    for case in cases:
        py_ok = not LIVE.recipient_problems(case["config"])
        js_ok = js.get(case["name"])
        if js_ok is None:
            disagreed.append((case["name"], "missing from the JavaScript run"))
            continue
        if py_ok != js_ok:
            disagreed.append((case["name"], {"python": py_ok, "javascript": js_ok}))
        # And both have to be *right*, not merely equal: two mirrors that are
        # identically wrong agree perfectly.
        if py_ok != case["usable"]:
            wrong.append((case["name"], {"expected": case["usable"], "got": py_ok}))

    check("the two validators agree on every case", not disagreed, disagreed)
    check("and both match what the fixture says each case is", not wrong, wrong)

    # Verdicts are the contract; wording is not, and this test is written that
    # way on purpose. One consequence is worth pinning separately: the address
    # rule is *redundant* for the verdict — `@` is not in the account-id
    # character class, so an address is refused either way — and it exists
    # solely so the sentence explains itself. Deleting it therefore changes no
    # verdict and breaks nothing above, which is exactly how a good message
    # rots. An administrator who pasted an address needs to be told that this
    # endpoint has no field for one, not that their id looks wrong.
    address = {"boards": {"2": {"anchorIssue": "SFT-1",
                                "exec": {"users": ["josh@example.com"]}}}}
    said = " ".join(LIVE.recipient_problems(address)).lower()
    check("the loopback validator names the address as an address",
          "email address" in said, said[:120])
    js_said = " ".join(js_problems_for(address)).lower()
    check("and so does the Forge one", "email address" in js_said, js_said[:120])


def test_every_jira_read_states_whose_authority_it_uses():
    """`jira(as)` is only safe if `as` is in scope where it is written.

    Threading the mode through nine helpers introduced this bug twice in one
    sitting: `jira(as)` was left inside `editabilityFor` and inside the
    `context` resolver, neither of which has an `as`. Both bundle cleanly — a
    free variable is not a syntax error — and both are a ReferenceError the
    first time a tenant opens the page.

    So the check is structural: every `jira(as)` must sit inside a function that
    declares `as`, and the two reads whose authority is not negotiable must
    still say `asUser()` in so many words.
    """
    src = (ROOT / "forge" / "src" / "index.js").read_text()
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)

    # Every function that declares `as` as its own parameter, by name.
    declaring = set(re.findall(r"const (\w+) = async \([^)]*\bas\b[^)]*\)", code))
    check("helpers thread the authority explicitly", len(declaring) >= 8,
          sorted(declaring))

    # Walk each `jira(` call back to the nearest enclosing `const NAME = async (`.
    orphans = []
    for m in re.finditer(r"\bjira\(as\)", code):
        before = code[:m.start()]
        owner = None
        for fn in re.finditer(r"const (\w+) = async \(([^)]*)\)", before):
            owner = fn
        if owner is None or "as" not in [p.strip().split("=")[0].strip()
                                         for p in owner.group(2).split(",")]:
            orphans.append(owner.group(1) if owner else "top level")
    check("every jira(as) sits in a function that declares `as`", not orphans,
          orphans)

    # The panel's own reads, which must never become the app's.
    edit = code.split("const editabilityFor", 1)[-1].split("};", 1)[0]
    check("the permission check asks as the user, in so many words",
          "api.asUser()" in edit and "jira(" not in edit, edit[:140])
    check("and the connection probe does too",
          "asUser()" in code.split("probeBoardIssues", 1)[-1][:900])

    # The trigger's own reads are the app's, stated at the call site rather
    # than inherited. ADR 0013's addendum is the record for that.
    trigger = code.split("const boardFigures", 1)[-1].split("export const weeklyBrief", 1)[0]
    for helper in ("boardProject", "projectContexts", "storyPointFieldFor",
                   "orgConfigFor", "issuesForEntry"):
        check("%s is called with 'app' in the scheduled path" % helper,
              re.search(r"%s\([^)]*'app'\)" % helper, trigger), trigger[:160])

    # Default is the safe one, so a read added without thinking is a user read.
    check("the default authority is the user's",
          re.search(r"const jira = \(as\) => \(as === 'app' \? api\.asApp\(\) : api\.asUser\(\)\)",
                    code))


def test_a_name_can_be_looked_up_without_the_directory_leaking():
    """Nobody knows their colleagues' account ids, and the config needs one.

    So the picker searches by name and stores the id. That is *not* the thing
    ADR 0014 refuses — the app is not deciding which Jira user an email address
    belongs to; a person types a name, Jira returns matches, and an
    administrator picks one. The identity claim is made by the human looking at
    the list, which is who should make it.

    What this guards is the projection. `GET /rest/api/3/user/search` returns
    `emailAddress`, `avatarUrls`, `timeZone` and `locale` among others, and the
    recipient config must hold none of them.
    """
    node = subprocess.run(["node", str(ROOT / "tests" / "brief_shapes.mjs")],
                          input=json.dumps({"refusal": "R"}),
                          capture_output=True, text=True, cwd=str(ROOT))
    if node.returncode != 0:
        check("the brief shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    p = json.loads(node.stdout)["people"]

    # An allow-list of two fields, because a deny-list is one Atlassian release
    # away from leaking whatever they add next.
    fields = {k for person in p["mixed"]["people"] for k in person}
    check("a match carries an account id and a display name and nothing else",
          fields == {"accountId", "displayName"}, sorted(fields))
    for leaked in ("example.com", "avatarUrls", "timeZone", "locale", "emailAddress"):
        check("no %s survives the projection" % leaked,
              leaked not in p["serialised"], p["serialised"][:160])

    # Real, active humans only.
    names = [x["displayName"] for x in p["mixed"]["people"]]
    check("a deactivated account is not offered", "Old Colleague" not in names, names)
    check("an app user is not offered — including this app's own",
          "Shipping Forecast" not in names, names)
    check("a customer account is not offered", "A Customer" not in names, names)
    check("and a nameless account is not offered", all(n.strip() for n in names), names)
    check("the person who does match is offered", names == ["Mitch Davis"], names)

    # No silent caps: a picker showing the first ten of sixteen invites picking
    # the wrong Mitch.
    check("the list is capped",
          len(p["overflowing"]["people"]) == p["max"], p["overflowing"])
    # The count is read off the list, not computed beside it. Written as its
    # own arithmetic it agreed with the list only while the two expressions
    # matched — removing the cap left it claiming ten while sixteen came back.
    check("and the count it reports is the length of the list it returned",
          p["overflowing"]["shown"] == len(p["overflowing"]["people"])
          and p["mixed"]["shown"] == len(p["mixed"]["people"]),
          {"overflow": p["overflowing"]["shown"], "mixed": p["mixed"]["shown"]})
    check("and says how many it did not show",
          str(p["overflowing"]["matched"]) in p["overflowNote"]
          and str(p["max"]) in p["overflowNote"], p["overflowNote"])
    check("and does not offer a page that does not exist",
          "no second page" in p["overflowNote"], p["overflowNote"])

    # The note earns its place by distinguishing states a count cannot.
    check("no matches at all reads differently from no usable matches",
          p["nothing"] != p["allInactive"], [p["nothing"], p["allInactive"]])
    check("all-inactive says why nobody is offered",
          "goes nowhere" in p["allInactive"], p["allInactive"])
    check("one match does not say '1 matches'", p["one"] == "One match.", p["one"])

    # Jira answering with something that is not a list is a refusal, not a crash.
    check("a response that is not a list is refused",
          "problems" in p["notAList"], p["notAList"])

    # Both transports answer the route, and loopback answers honestly rather
    # than inventing ids that would be stored and never work.
    live = (ROOT / "scripts" / "serve_live.py").read_text()
    check("the loopback server answers the same route",
          "api/users" in live, "no api/users route")
    check("and says there is no directory rather than returning nobody",
          "no directory" in live or "user directory" in live, "")

    # The search is made as the reader, so it returns the people that reader is
    # allowed to see. Searching as the app would offer a directory their own
    # account cannot browse.
    src = (ROOT / "forge" / "src" / "index.js").read_text()
    block = src.split("resolver.define('searchUsers'", 1)[-1].split("}));", 1)[0]
    check("the name search runs as the reader, not as the app",
          "asUser()" in block and "jira(" not in block, block[:200])


def series_checks():
    """The durable sprint series — ADR 0015, roadmap item 4.

    Two halves, and the split is the design. `forge/src/series.js` decides what
    is **kept**: where a board's rows live, what a row may contain, and whether
    an observation may be written at all. `agent/tools/metrics.py` decides what
    is **shown**: the merge, the disagreements and the note. The note counts
    rows into a sentence a reader reads, and a figure produced between a tool
    and a reader is the thing this repository spends most of its tests
    preventing — so it is not in the JavaScript, and there is exactly one of it.

    What remains duplicated is *policy*, in two places because the decision has
    to be taken next to the store and there are two stores. Both are run below
    over one shared file.
    """
    print("the durable sprint series")
    node = subprocess.run(["node", str(ROOT / "tests" / "forge_shapes.mjs")],
                          cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    if node.returncode != 0:
        check("the Forge shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    shapes = json.loads(node.stdout)
    S = shapes["series"]
    cases = json.loads((ROOT / "tests" / "fixtures" / "series-cases.json").read_text())

    # ---- the store holds counts, never issue text ----
    #
    # The property that keeps item 4 off item 5's critical path: nothing in this
    # store is something a reader could be denied sight of, so a permission
    # model is not a prerequisite for having one.
    check("a stored row carries only counts, a name and a currency total",
          S["projected"] == S["fields"], S["projected"])
    check("issue text handed to the projection does not survive it",
          not any(f in S["projected"] for f in ("summary", "assignee", "issues")),
          S["projected"])
    check("and a row that carries any is refused rather than trimmed",
          any("never anything derived from issue text" in x
              for x in S["problems"]["extra"]), S["problems"]["extra"])
    # One allow-list, mirrored, because the tool and the store must agree about
    # what a row is. A field admitted by one and unknown to the other is either
    # stored and never read, or read and never stored.
    check("both languages agree on which fields a row has",
          list(S["fields"]) == list(MT.ROW_FIELDS),
          {"js": S["fields"], "py": list(MT.ROW_FIELDS)})

    # ---- a bad row is caught before it is written, not after it is read ----
    check("an honest row has nothing wrong with it", S["problems"]["good"] == [],
          S["problems"]["good"])
    check("a missing figure is refused, not defaulted to zero",
          any("wipItems is missing" in x for x in S["problems"]["missing"]),
          S["problems"]["missing"])
    check("a figure that is not a number is refused",
          len(S["problems"]["notANumber"]) == 1, S["problems"]["notANumber"])
    check("a null flow efficiency is the derivation refusing, and is allowed",
          S["problems"]["nullEfficiency"] == [], S["problems"]["nullEfficiency"])
    check("a null value delivered is absent rather than nil, and is allowed",
          S["problems"]["nullValue"] == [], S["problems"]["nullValue"])
    check("but a null count is refused, because a count is never absent",
          any("completedItems is null" in x for x in S["problems"]["nullCount"]),
          S["problems"]["nullCount"])
    check("completing more than the sprint contained is refused as a wrong slice",
          any("different set of issues" in x for x in S["problems"]["impossible"]),
          S["problems"]["impossible"])
    check("something that is not a row at all is refused readably",
          S["problems"]["notAnObject"] == ["the row is not an object."],
          S["problems"]["notAnObject"])

    # ---- policy, run over one shared list by both transports ----
    #
    # The same arrangement `validate()` has. A policy that differed between
    # transports would mean a sprint recorded down one route and reconstructed
    # down the other, with the page saying different things about one board
    # depending on how it was reached.
    js_rec = {name: got for name, got in S["recordable"]}
    for c in cases["recordable"]:
        want, name = c["record"], c["name"]
        check("recordable, both transports: %s" % name,
              js_rec.get(name) is want
              and LIVE.series_recordable(c["state"], c["prior"], c.get("seen")) is want,
              {"want": want, "js": js_rec.get(name),
               "py": LIVE.series_recordable(c["state"], c["prior"], c.get("seen"))})
    check("every refusal to record says which of the reasons it was",
          all(why.strip() for _, why in S["recordableWhy"]), S["recordableWhy"])
    check("a sprint that closed before we saw it is named a reconstruction",
          any("reconstruction" in why for _, why in S["recordableWhy"]),
          S["recordableWhy"])

    js_fp = {name: got for name, got in S["fingerprints"]}
    for c in cases["fingerprints"]:
        check("status fingerprint, both transports: %s" % c["name"],
              js_fp.get(c["name"]) == LIVE.series_fingerprint(c["config"]),
              {"js": js_fp.get(c["name"]), "py": LIVE.series_fingerprint(c["config"])})
    fps = [got for _, got in S["fingerprints"]]
    check("reordering and recasing the same statuses is not a change",
          fps[0] == fps[1], fps[:2])
    check("dropping a status from 'in progress' is",
          fps[0] != fps[2], (fps[0], fps[2]))
    check("blank entries mean nothing and do not count as a change",
          fps[0] == fps[4], (fps[0], fps[4]))

    # ---- what a written entry is ----
    e = S["entry"]
    check("an entry keeps the row, when it was observed, under which statuses, "
          "and how wide the view was",
          sorted(e) == ["final", "issuesSeen", "observedOn", "row", "statuses"],
          sorted(e))
    check("and the view width is a count, naming no issue",
          isinstance(e["issuesSeen"], int), e["issuesSeen"])
    check("a sprint seen after it closed is final; one seen running is not",
          e["final"] is True and S["midEntry"]["final"] is False,
          (e["final"], S["midEntry"]["final"]))
    check("an unreadable store version is used for nothing",
          S["read"]["wrongVersion"]["sprints"] == {}
          and len(S["read"]["wrongVersion"]["problems"]) == 1,
          S["read"]["wrongVersion"])
    check("and no store at all is not a problem, it is an empty series",
          S["read"]["empty"] == {"sprints": {}, "problems": []}, S["read"]["empty"])
    check("what was written reads back", list(S["read"]["good"]["sprints"]) == ["SFT/2/22"],
          S["read"]["good"])
    # ---- the moment a sprint's figures are about ----
    #
    # `contextEntry` reported `asOfDate: null` for every sprint, so a Forge
    # series rested entirely on `endDate`. A sprint started without one produced
    # no row, the trend lost a point, and the tile said "needs at least two
    # sprints of history" on a board with two. It also dated a closed sprint to
    # when it was *planned* to end rather than when it did.
    #
    # Held against the fetcher's rule rather than restated, because the two
    # producers disagreeing about which day a sprint's figures belong to is the
    # whole of this bug.
    a = shapes["asOf"]
    check("a running sprint is measured as of today",
          a["active"] == "2026-08-10", a["active"])
    check("including one nobody gave an end date — the case that produced no row",
          a["activeNoEnd"] == "2026-08-10", a["activeNoEnd"])
    check("a closed sprint takes the day it completed, not the day it was due",
          a["closed"] == "2026-07-21", a["closed"])
    check("falling back to the planned end only when Jira recorded no completion",
          a["closedNoComplete"] == "2026-07-17", a["closedNoComplete"])
    check("and a sprint with no dates at all reports none rather than inventing one",
          a["closedNothing"] is None, a["closedNothing"])

    # The fetcher's own rule, run over the same four sprints. Two producers, one
    # answer — the arrangement `validate()` and `orgConfig` already have.
    def fetcher_as_of(sp, today):
        """scripts/fetch_delivery_data.py, lines 481-482, as a function."""
        if sp.get("state") == "active":
            return today
        return ((sp.get("completeDate") or "")[:10]
                or (sp.get("endDate") or "")[:10] or None)
    cases = [
        ("active", {"state": "active", "endDate": "2026-08-14T00:00:00Z"}),
        ("activeNoEnd", {"state": "active"}),
        ("closed", {"state": "closed", "endDate": "2026-07-17T00:00:00Z",
                    "completeDate": "2026-07-21T09:12:00Z"}),
        ("closedNoComplete", {"state": "closed", "endDate": "2026-07-17T00:00:00Z"}),
        ("closedNothing", {"state": "closed"}),
    ]
    for name, sp in cases:
        check("both producers date %s the same way" % name,
              a[name] == fetcher_as_of(sp, "2026-08-10"),
              {"forge": a[name], "fetcher": fetcher_as_of(sp, "2026-08-10")})

    check("one key per board, so two boards closing at once are two writers",
          S["key"] == "series:42", S["key"])

    # ---- the merge and the note, which exist once, in Python ----
    good = dict(zip(MT.ROW_FIELDS,
                    ["Sprint 22", 34, 25, 13, 10, 10, 3, 2, 0.33, 12000]))
    entry = {"row": good, "observedOn": "2026-07-17", "final": True, "statuses": "a"}
    stored = {"version": 1, "sprints": {"S22": entry}}
    rebuilt = [{"sprintId": "S21", "row": dict(good, sprint="Sprint 21")},
               {"sprintId": "S22", "row": good},
               {"sprintId": "S23", "row": dict(good, sprint="Sprint 23")}]

    m = MT.merge_series(stored, rebuilt, "a")
    check("a recorded row substitutes at its own position, never appends",
          [r["source"] for r in m["rows"]]
          == ["reconstructed", "recorded", "reconstructed"],
          [r["source"] for r in m["rows"]])
    check("and the sprints stay in the order the board runs them",
          [r["sprint"] for r in m["rows"]]
          == ["Sprint 21", "Sprint 22", "Sprint 23"], [r["sprint"] for r in m["rows"]])
    # Silent only when there is genuinely nothing a chart cannot show: every
    # sprint recorded, at its own end, under today's statuses, all agreeing.
    all_recorded = {"version": 1, "sprints": {
        r["sprintId"]: {"row": r["row"], "observedOn": "2026-07-17",
                        "final": True, "statuses": "a"} for r in rebuilt}}
    check("a fully recorded, fully agreeing series says nothing at all",
          MT.series_note(MT.merge_series(all_recorded, rebuilt, "a")) == "",
          MT.series_note(MT.merge_series(all_recorded, rebuilt, "a")))
    check("and a series with two of its three rebuilt is worth a sentence",
          "2 of these 3 sprints" in MT.series_note(m), MT.series_note(m))

    # A commitment that shrank: a reopened sprint, or a deleted issue. The
    # recorded figures are drawn and the fields that moved are named — no winner
    # is picked, because which field moved is more useful than either number.
    shrunk = [dict(r, row=dict(good, committedItems=10, committedSP=25))
              if r["sprintId"] == "S22" else r for r in rebuilt]
    ms = MT.merge_series(stored, shrunk, "a")
    check("a recorded row that no longer matches Jira keeps its own figures",
          ms["rows"][1]["committedItems"] == 13, ms["rows"][1])
    check("...and names the fields that moved rather than picking a winner",
          sorted(ms["rows"][1]["differs"]) == ["committedItems", "committedSP"],
          ms["rows"][1]["differs"])
    note = MT.series_note(ms)
    check("the note states the disagreement and which figures are shown",
          "no longer matches" in note and "committedItems" in note
          and "recorded figures are shown" in note, note)

    # A rounded ratio differing in the last place is two roundings of one
    # quantity, not a disagreement. Every other field is a count.
    check("a rounded ratio differing in the last place is not a disagreement",
          MT.series_disagreements(good, dict(good, flowEfficiency=0.34)) == [],
          MT.series_disagreements(good, dict(good, flowEfficiency=0.34)))
    check("a flow efficiency that really moved is",
          [d["field"] for d in MT.series_disagreements(good, dict(good, flowEfficiency=0.19))]
          == ["flowEfficiency"], "")
    check("two refusals to state one figure are agreement, not a difference",
          MT.series_disagreements(dict(good, valueDelivered=None),
                                  dict(good, valueDelivered=None)) == [], "")
    check("but a figure appearing where there was none is reported",
          [d["field"] for d in MT.series_disagreements(dict(good, valueDelivered=None), good)]
          == ["valueDelivered"], "")

    moved = MT.merge_series(stored, rebuilt, "b")
    check("a row recorded under different 'in progress' statuses says so",
          moved["rows"][1]["statusesMoved"] is True
          and m["rows"][1]["statusesMoved"] is False,
          (moved["rows"][1]["statusesMoved"], m["rows"][1]["statusesMoved"]))
    check("and the note calls it a change of measurement, not an error",
          "not quite the same measurement" in MT.series_note(moved),
          MT.series_note(moved))

    mid = MT.merge_series({"version": 1, "sprints": {"S22": dict(entry, final=False)}},
                          rebuilt, "a")
    check("a row last seen mid-sprint is not claimed as the sprint's end",
          mid["rows"][1]["atSprintEnd"] is False, mid["rows"][1])
    check("and the note says which day it is instead",
          "still running" in MT.series_note(mid), MT.series_note(mid))

    orphan = MT.merge_series(
        {"version": 1, "sprints": {"S22": entry, "S19": entry}}, rebuilt, "a")
    check("a recorded sprint the board no longer offers is dropped and counted",
          orphan["orphaned"] == ["S19"] and len(orphan["rows"]) == 3,
          orphan["orphaned"])
    check("and the note says it was left out rather than placed at a guess",
          "no longer offered by this board" in MT.series_note(orphan),
          MT.series_note(orphan))

    # ---- a sprint is never compared against its own future ----
    #
    # The bundle path has always sliced `history` per context; the served route
    # returns the whole board, and without this it drew a trend running months
    # past the sprint on screen and compared that sprint's delivery against a
    # row from after it. It read as a perfectly ordinary chart, and the
    # transport-parity check in tests/e2e.py is what caught it.
    ordered = [{"contextId": "B/1/S%d" % n, "row": {"sprint": "S%d" % n}}
               for n in range(19, 25)]
    check("the series stops at the selected sprint",
          [r["contextId"] for r in MT.series_upto(ordered, "B/1/S21")]
          == ["B/1/S19", "B/1/S20", "B/1/S21"],
          [r["contextId"] for r in MT.series_upto(ordered, "B/1/S21")])
    check("the latest sprint sees all of it",
          len(MT.series_upto(ordered, "B/1/S24")) == 6, "")
    check("the earliest sees only itself",
          len(MT.series_upto(ordered, "B/1/S19")) == 1, "")
    # A context this series is not about leaves the rows alone. Returning an
    # empty trend would read as a team with no history rather than as a question
    # asked of the wrong board.
    check("an id that is not in the series does not silently empty it",
          len(MT.series_upto(ordered, "OTHER/9/S1")) == 6, "")
    check("and neither does no id at all",
          len(MT.series_upto(ordered, None)) == 6, "")

    # ---- one round trip, and the service still computes nothing of its own ----
    bundle = json.loads((ROOT / "data" / "sample-bundle.json").read_text())
    proj = [{k: v for k, v in i.items() if k in SVC.CALC_FIELDS}
            for i in bundle["issues"]]
    served = SVC.route_history({"dataset": {"contexts": bundle["contexts"],
                                            "issues": proj,
                                            "orgConfig": bundle.get("orgConfig")}})
    direct = MT.history_series(bundle["contexts"], proj)["rows"]

    # ---- the order is the data's, not the caller's ----
    #
    # The bug this pins reached a tenant. A bundle lists a board's sprints
    # oldest first; the Forge resolver gets them from `recentSprints`, which
    # sorts newest first so the picker offers the current sprint at the top.
    # `series_upto` truncates by position, so on Forge the newest sprint
    # truncated the series to one row and the tile said "needs at least two
    # sprints of history" on a board with plenty — while the same board over
    # loopback drew six. A page behaving differently depending on how it was
    # reached is what ADR 0009 exists to prevent, and the parity check in
    # tests/e2e.py could not see it: it feeds both transports the same
    # loopback bodies, so an ordering the resolver alone produces is invisible
    # to it.
    bundle_ctx = [c for c in bundle["contexts"] if str(c.get("boardId")) == "42"]
    oldest_first = MT.history_series(bundle_ctx, proj)["rows"]
    newest_first = MT.history_series(list(reversed(bundle_ctx)), proj)["rows"]
    check("the series is ordered by the sprints, not by the caller",
          oldest_first == newest_first,
          {"asc": [r["contextId"] for r in oldest_first][:3],
           "desc": [r["contextId"] for r in newest_first][:3]})
    check("and it runs oldest first, which is the direction a chart reads",
          [r["contextId"] for r in oldest_first]
          == sorted(r["contextId"] for r in oldest_first),
          [r["contextId"] for r in oldest_first])
    check("so the newest sprint sees the whole series down either route",
          len(MT.series_upto(oldest_first, "BLC/42/S24")) == len(bundle_ctx)
          and len(MT.series_upto(newest_first, "BLC/42/S24")) == len(bundle_ctx),
          (len(MT.series_upto(newest_first, "BLC/42/S24")), len(bundle_ctx)))
    # A context with no dates at all sorts last rather than first: an undated
    # row at the head of a trend silently shifts every point after it.
    undated = MT.history_series(
        bundle_ctx + [{"id": "BLC/42/SX", "kind": "sprint", "sprintName": "No dates",
                       "asOfDate": None, "endDate": None, "startDate": None}], proj)
    check("a context with no dates does not sort to the head of the series",
          not undated["rows"] or undated["rows"][0]["contextId"] != "BLC/42/SX",
          [r["contextId"] for r in undated["rows"]][:2])
    # And it is named rather than lost. This is the bug that reached the tenant:
    # a sprint with no end date left the series with nothing saying so, and the
    # tile reported "needs at least two sprints of history" on a board with two.
    check("a sprint that cannot be dated is named, not silently dropped",
          [x["contextId"] for x in undated["skipped"]] == ["BLC/42/SX"],
          undated["skipped"])
    check("and the reason says it is a missing date, not missing sprints",
          "no end date" in MT.skipped_note(undated["skipped"])
          and "No dates" in MT.skipped_note(undated["skipped"]),
          MT.skipped_note(undated["skipped"]))
    check("nothing skipped means nothing said",
          MT.skipped_note([]) == "" and MT.skipped_note(None) == "",
          MT.skipped_note([]))
    # A window is not a point on a trend, and is reported as excluded rather
    # than quietly absent — ADR 0011.
    windowed = MT.history_series(
        bundle_ctx + [{"id": "BLC/42/w30", "kind": "window", "sprintName": "30 days",
                       "endDate": "2026-08-10"}], proj)
    check("a flow window is excluded from a sprint trend, and says so",
          [x["contextId"] for x in windowed["skipped"]] == ["BLC/42/w30"]
          and "window is not a point" in MT.skipped_note(windowed["skipped"]),
          windowed["skipped"])

    check("the service's rows are the tool's rows, called directly",
          served["rows"] == direct, (len(served["rows"]), len(direct)))
    check("and its merged view is the tool's merge of them",
          served["merged"] == MT.merge_series(
              {}, [{"sprintId": r["contextId"], "row": r["row"]} for r in direct],
              None)["rows"], served["sprints"])
    # Jira has no value field and CALC_FIELDS carries none, so the calculator
    # can only ever answer null here. Zero would say the sprint delivered
    # nothing worth anything, which is a much stronger claim.
    check("value delivered comes back absent, never zero, over the calculator",
          all(r["row"]["valueDelivered"] is None for r in served["rows"]),
          [r["row"]["valueDelivered"] for r in served["rows"][:3]])
    upto = SVC.route_history({"dataset": {"contexts": bundle["contexts"],
                                          "issues": proj,
                                          "orgConfig": bundle.get("orgConfig")},
                              "contextId": "BLC/42/S21"})
    check("the route records every sprint it saw but shows only up to the selection",
          len(upto["rows"]) == len(served["rows"]) and len(upto["merged"]) == 3,
          {"rows": len(upto["rows"]), "shown": len(upto["merged"])})

    check("a history request with no contexts is refused, not answered emptily",
          _refuses(lambda: SVC.route_history({"dataset": {"issues": []}})),
          "no contexts")
    check("issue text sent to the history route is refused like everywhere else",
          _refuses(lambda: SVC.route_history(
              {"dataset": {"contexts": bundle["contexts"],
                           "issues": [dict(proj[0], summary="a title")]}})),
          "free text")


def _refuses(fn):
    """Whether a route refused. Reported by exception type, not by grepping a
    sentence — a refusal that changed its wording would otherwise start
    reporting as a route that answered."""
    try:
        fn()
    except SVC.Refused:
        return True
    except Exception:
        return False
    return False


def test_the_image_takes_debians_security_updates():
    """The base lags Debian, and the build has to close the gap.

    `service/scan.sh` blocks on HIGH and CRITICAL findings that have a fix
    available. Debian publishes a patched package before the `python` image is
    rebuilt to include it, so for the length of that lag every build produces an
    image the gate correctly refuses — and deploys stop. That happened on
    2026-08-28: CVE-2026-14456 in OpenSSL, fixed in 3.5.7-1~deb13u2, with
    python:3.12-slim still shipping 3.5.6-1~deb13u2 and no newer digest to pin.

    Checked here rather than only in CI because CI needs Docker and this is
    where the Dockerfile is edited. What CI proves is that the resulting image
    scans clean; what this proves is that the line is still there and still says
    why. ADR 0016.
    """
    df = (ROOT / "service" / "Dockerfile").read_text()
    # The instructions, not the prose around them. Half this file is a comment
    # explaining why `dist-upgrade` is the wrong verb, and a check that greps
    # the whole text fails on the sentence saying not to do the thing.
    steps = "\n".join(l for l in df.splitlines() if not l.lstrip().startswith("#"))

    check("the image applies Debian's security updates",
          "apt-get upgrade" in steps,
          [l.strip() for l in steps.splitlines() if "apt-get" in l])

    # `upgrade`, never `dist-upgrade`: this takes patched versions of packages
    # already present and must not add or remove one. A dist-upgrade can change
    # what is in a calculator image without anybody deciding to.
    check("it upgrades what is there rather than resolving a new package set",
          "dist-upgrade" not in steps,
          [l.strip() for l in steps.splitlines() if "upgrade" in l])

    # In the same layer, or the lists sit in the published image for no reason.
    check("and deletes the apt lists in the same layer",
          "rm -rf /var/lib/apt/lists/*" in steps,
          [l.strip() for l in df.splitlines() if "apt/lists" in l])

    # Before the wheel and the source, so everything above is built on the
    # patched base and the layer caches independently of the app changing.
    check("the upgrade runs before anything is installed on top of it",
          steps.index("apt-get upgrade") < steps.index("COPY"),
          (steps.index("apt-get upgrade"), steps.index("COPY")))

    # The reason, in the file. A bare `apt-get upgrade` reads as belt-and-braces
    # and is the first line somebody removes when trimming an image; the CVE and
    # the record are what make it a decision rather than a habit.
    check("the line says which lag it exists for, and names the record",
          "CVE-2026-14456" in df and "ADR 0016" in df,
          [l.strip() for l in df.splitlines() if "CVE-" in l or "ADR " in l])

    # The policy itself, which this does not change and must not be read as
    # changing. Unfixable findings have never blocked, and the failure of
    # 2026-08-28 was misread twice as though they had.
    scan = (ROOT / "service" / "scan.sh").read_text()
    check("the gate still blocks only on findings that have a fix",
          "--ignore-unfixed" in scan and "--exit-code 1" in scan,
          [l.strip() for l in scan.splitlines() if "ignore-unfixed" in l])
    check("and still prints everything HIGH and CRITICAL, fixable or not",
          "--exit-code 0" in scan,
          [l.strip() for l in scan.splitlines() if "exit-code 0" in l])


def forecast_log_checks():
    """The forecast log, wired — roadmap item 4c, ADR 0017.

    The claims themselves are covered in `tests/test_agent.py`, which needs no
    browser and no server. What is checked here is the wiring: that the service
    computes none of it, that a what-if writes nothing, and that both transports
    keep the log on their own shelf behind one set of body shapes.
    """
    print("the forecast log")
    bundle = json.loads((ROOT / "data" / "sample-bundle.json").read_text())
    proj = [{k: v for k, v in i.items() if k in SVC.CALC_FIELDS}
            for i in bundle["issues"]]
    ds = {"contexts": bundle["contexts"], "issues": proj,
          "byContext": bundle.get("byContext") or {},
          "orgConfig": bundle.get("orgConfig")}
    cid = "BLC/42/S24"

    # ---- the service computes none of it ----
    served = SVC.route_forecast_context({"dataset": ds, "contextId": cid})
    direct = SEL.forecast_for(bundle["contexts"], proj, bundle.get("byContext") or {},
                              cid, org_cfg=bundle.get("orgConfig"))
    check("with no log the route answers exactly as it always did",
          served == direct, "forecast body changed")
    check("a default forecast carries the claims it makes",
          len(served.get("claims") or []) == len(FC.PERCENTILES),
          len(served.get("claims") or []))

    # A what-if is not a published prediction — nobody said it. It is also not
    # merely untidy: `claim_id` is keyed on context, day and percentile, so a
    # what-if with a different target would take the same id as the day's real
    # forecast and overwrite a claim somebody made with one nobody did.
    whatif = SVC.route_forecast_context({"dataset": ds, "contextId": cid, "items": 20})
    check("a what-if makes no claim at all", (whatif.get("claims") or []) == [],
          whatif.get("claims"))
    after = SVC.route_forecast_context({"dataset": ds, "contextId": cid,
                                        "items": 20, "log": []})
    check("and so it adds nothing to a log",
          (after.get("calibration") or {}).get("added") == 0,
          (after.get("calibration") or {}).get("added"))

    # ---- the log the route returns is the tool's, called directly ----
    withlog = SVC.route_forecast_context({"dataset": ds, "contextId": cid, "log": []})
    cal = withlog["calibration"]
    same = FC.update_log([], direct.get("claims") or [], proj,
                        (direct.get("asked") or {}).get("as_of"))
    check("the route's calibration is update_log called directly",
          cal == same, {"route": cal.get("added"), "direct": same.get("added")})
    check("a first forecast adds every claim it made",
          cal["added"] == len(FC.PERCENTILES), cal["added"])
    check("and publishing the same forecast again adds none",
          SVC.route_forecast_context(
              {"dataset": ds, "contextId": cid, "log": cal["log"]}
          )["calibration"]["added"] == 0, "re-added")

    # ---- it refuses rather than scoring a young log ----
    check("a log below the threshold is refused with the scorer's own sentence",
          "10 resolved forecasts needed" in cal["note"], cal["note"])
    check("and the sentence separates 'not yet' from 'badly calibrated'",
          "Not scored yet" in cal["note"] and "calibrated" not in cal["note"],
          cal["note"])

    # ---- the bound, and what it says it dropped ----
    filler = [dict((cal["log"] or [{}])[0], id="old-%d" % i, madeOn="2026-01-01",
                   horizon="2026-01-15", resolved=True, observed=1)
              for i in range(FC.MAX_LOG + 50)]
    kept, dropped = FC.trim_log(filler)
    check("the log is bounded", len(kept) == FC.MAX_LOG, len(kept))
    check("and says how many it dropped rather than forgetting quietly",
          dropped == 50, dropped)
    unresolved = [dict(filler[0], id="waiting-%d" % i, resolved=None, observed=None)
                  for i in range(5)]
    kept2, _ = FC.trim_log(filler + unresolved)
    check("a claim still waiting on its horizon is never dropped",
          all(any(k["id"] == u["id"] for k in kept2) for u in unresolved),
          len(kept2))

    # ---- one shelf each, and the same body shape on both ----
    live = (ROOT / "scripts" / "serve_live.py").read_text()
    check("loopback keeps the log in a git-ignored file",
          "forecast-log.local.json" in live,
          [l.strip() for l in live.splitlines() if "forecast-log" in l][:1])
    ignored = (ROOT / ".gitignore").read_text()
    check("and that file is git-ignored, like every other local store",
          any(pat in ignored for pat in ("data/*.local.json", "forecast-log.local.json")),
          [l for l in ignored.splitlines() if "local" in l])
    idx = (ROOT / "forge" / "src" / "index.js").read_text()
    check("Forge keeps it in app storage, one key per board",
          "forecastlog:" in idx,
          [l.strip() for l in idx.splitlines() if "forecastlog" in l][:1])
    # The scope it does not need. `storage:app` was granted for the recipient
    # config and the series already uses it; a log of counts adds nothing.
    manifest = (ROOT / "forge" / "manifest.yml").read_text()
    check("and needs no scope the app did not already hold",
          manifest.count("storage:app") == 1, manifest.count("storage:app"))

    # ---- a claim is the board's too, and the score is the fragile part ----
    #
    # ADR 0019 made a sprint row a fact about the board. A claim is the same,
    # with one difference that decides the design: a row is observed repeatedly
    # and can be widened, while a claim is made once and **resolved once, never
    # rescored**. So the irreversible hazard is not publishing a narrow claim,
    # it is resolving a good one against a view that cannot see the work — which
    # marks a correct forecast wrong with no second chance.
    cap = {"available": True, "target_date": "2026-09-11",
           "percentiles": {50: 9, 85: 5}}
    wide = FC.claims_from(cap, "M/2/12", "2", "2026-08-28", "B", seen=40)
    check("a claim records how wide the view that published it was",
          [c["issuesSeen"] for c in wide] == [40, 40],
          [c["issuesSeen"] for c in wide])
    check("and the width is a count, inside the allow-list, naming no issue",
          "issuesSeen" in FC.CLAIM_FIELDS and FC.problems_in_claim(wide[0]) == [],
          FC.problems_in_claim(wide[0]))

    published = FC.update_log([], wide, [], "2026-09-01", seen=40)
    check("a first claim publishes with nothing to compare against",
          published["added"] == 2 and published["narrowed"] == [],
          published["added"])

    # Publishing: a narrower view is not the board's claim, it is one reader's.
    narrow = FC.claims_from(cap, "M/2/13", "2", "2026-08-29", "B", seen=10)
    held = FC.update_log(published["log"], narrow, [], "2026-09-01", seen=10)
    check("a claim from a narrower view is not added to the board's log",
          held["added"] == 0 and len(held["narrowed"]) == 2, held["narrowed"])
    check("and the reader is told, with both widths, that it was held back",
          "made over 10" in held["note"] and "made over 40" in held["note"],
          held["note"])
    check("a reader whose view is wide enough is told nothing about it",
          "not added to the log" not in published["note"], published["note"])

    # Resolving: the half that cannot be undone.
    landed = [{"resolved": "2026-09-0%d" % d} for d in range(1, 9)]
    by_narrow = FC.update_log(published["log"], [], landed, "2026-09-30", seen=10)
    check("a narrow view does not resolve a claim made over a wider board",
          all(e["resolved"] is None for e in by_narrow["log"]),
          [e["resolved"] for e in by_narrow["log"]])
    check("...and says why, rather than leaving it looking merely unresolved",
          any("cannot see" in p["why"] for p in by_narrow["pending"]),
          [p["why"][:80] for p in by_narrow["pending"]][:1])
    by_wide = FC.update_log(published["log"], [], landed, "2026-09-30", seen=40)
    check("a view as wide as the claim resolves it",
          [e["resolved"] for e in by_wide["log"]] == [False, True],
          [e["resolved"] for e in by_wide["log"]])
    check("and counts the completions it could see",
          [e["observed"] for e in by_wide["log"]] == [8, 8],
          [e["observed"] for e in by_wide["log"]])

    # An unknown width is not treated as narrow. A log written before this rule
    # existed carries no `issuesSeen`, and refusing to score any of it would
    # make the rule retroactively delete two years of evidence.
    legacy = [dict(wide[0], id="legacy", issuesSeen=None)]
    old, _ = FC.resolve_claims(legacy, landed, "2026-09-30", seen=1)
    check("a claim with no recorded width still resolves",
          old[0]["resolved"] is not None, old[0]["resolved"])

    # The forecast route carries the width, or none of the above can fire.
    check("the forecast tells its caller how wide the view it sampled was",
          isinstance(direct.get("issuesSeen"), int), direct.get("issuesSeen"))
    check("and the claims it emits carry the same number",
          all(c["issuesSeen"] == direct["issuesSeen"]
              for c in (direct.get("claims") or [])),
          [c.get("issuesSeen") for c in (direct.get("claims") or [])][:2])

    # Written only when it moved: this route runs whenever the tile is opened.
    check("neither transport rewrites a log that did not change",
          "cal.added || cal.dropped" in idx
          and 'cal["added"] or cal["dropped"]' in live,
          "unconditional write")


def window_checks():
    """The trend window — roadmap item 4b.

    Six was hardcoded in three producers and cut the older sprints in all of
    them without saying so, which is the silent cap `CLAUDE.md` forbids: a
    chart of six sprints from a board with twenty reads as a complete record.
    The window is a stated setting now, and both kinds of truncation are named.
    """
    print("the trend window")
    node = subprocess.run(["node", str(ROOT / "tests" / "forge_shapes.mjs")],
                          cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    if node.returncode != 0:
        check("the Forge shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return

    # ---- the setting, in both languages ----
    check("the default window is stated in the config, not in code",
          OC.DEFAULTS["trendSprints"] == 6, OC.DEFAULTS.get("trendSprints"))
    for n, ok in ((2, True), (6, True), (40, True), (1, False), (41, False),
                  (0, False), ("six", False), (True, False)):
        problems = OC.validate(dict(OC.DEFAULTS, trendSprints=n))
        check("trendSprints=%r is %s" % (n, "accepted" if ok else "refused"),
              (problems == []) is ok, problems)

    # ---- no producer keeps its own six ----
    #
    # The fetcher and both generators had one each. Four implementations of one
    # window is how four implementations of `history_row` happened.
    fetcher = (ROOT / "scripts" / "fetch_delivery_data.py").read_text()
    check("the fetcher takes its window from the config",
          "trend_window(cfg)" in fetcher and "hist[-6:]" not in fetcher,
          [l.strip() for l in fetcher.splitlines() if "hist[-" in l])
    check("and resolves it in one place both generators can call",
          "def trend_window(" in fetcher, "trend_window missing")
    idx = (ROOT / "forge" / "src" / "index.js").read_text()
    check("the Forge picker asks for the stated window",
          "trendWindow(" in idx and "recentSprints(got.sprints, keep)" in idx,
          [l.strip() for l in idx.splitlines() if "recentSprints(" in l])

    # ---- the two truncations, each named ----
    #
    # Recorded-but-not-shown had exactly one sentence before this, and it was
    # the wrong one for the commoner cause: a board with ten recorded sprints
    # and a six-sprint window reported four of them as "no longer offered by
    # this board", which was not true of any of them.
    stored = {"version": 1, "sprints": {
        "B/1/S%d" % n: {"row": {"sprint": "S%d" % n},
                        "observedOn": "2026-0%d-01" % n,
                        "final": True, "statuses": "a"} for n in range(1, 10)}}
    shown = [{"sprintId": "B/1/S%d" % n, "row": {"sprint": "S%d" % n},
              "asOf": "2026-0%d-01" % n} for n in range(5, 10)]

    m = MT.merge_series(stored, shown, "a")
    check("a recorded sprint older than the window is not called missing",
          m["orphaned"] == [], m["orphaned"])
    check("it is named as outside the window instead",
          m["outsideWindow"] == ["B/1/S1", "B/1/S2", "B/1/S3", "B/1/S4"],
          m["outsideWindow"])
    note = MT.series_note(m)
    check("and the sentence says which setting brings it back",
          "trendSprints" in note and "no longer offered" not in note, note)

    # A sprint inside the range that was asked for, which the board did not
    # offer. Deleted, or moved — and a different sentence.
    gone = [x for x in shown if x["sprintId"] != "B/1/S7"]
    m2 = MT.merge_series(stored, gone, "a")
    check("a sprint missing from inside the window still reads as missing",
          m2["orphaned"] == ["B/1/S7"], m2["orphaned"])
    check("and is not blamed on the window",
          "no longer offered by this board" in MT.series_note(m2)
          and "trendSprints" in MT.series_note(m2), MT.series_note(m2))

    # ---- what the board has, against what the trend shows ----
    check("a board with more sprints than the window says so",
          "20 sprints" in MT.window_note(20, 6, 6)
          and "most recent 6" in MT.window_note(20, 6, 6), MT.window_note(20, 6, 6))
    check("and names the setting rather than implying a limit",
          "trendSprints is 6" in MT.window_note(20, 6, 6), MT.window_note(20, 6, 6))
    check("a board inside its window says nothing at all",
          MT.window_note(6, 6, 6) == "" and MT.window_note(3, 3, 6) == "",
          MT.window_note(6, 6, 6))
    check("one sprint over is still worth a sentence, singular",
          "1 older one is" in MT.window_note(7, 6, 6), MT.window_note(7, 6, 6))
    check("nonsense counts produce no sentence rather than a wrong one",
          MT.window_note(None, 6, 6) == "" and MT.window_note("20", 6, 6) == "",
          MT.window_note(None, 6, 6))


#: Every app-level store, with the authority its contents were computed under
#: and what that therefore exposes. Roadmap item 5, ADR 0018.
#:
#: The shape is the non-read scope allow-list's: a store must be listed *and*
#: carry a justification, so a fourth one cannot appear without somebody
#: writing down what it discloses. Anything in app storage is readable by every
#: viewer of the tile, so the question for each is always the same — was this
#: computed over issues that every reader of it may see?
APP_LEVEL_STORES = {
    "recipients": {
        "authority": "admin",
        "exposes": "who a board's brief goes to. Written by a project "
                   "administrator and shown to viewers who cannot edit it, "
                   "which is deliberate (CHANGELOG 1.28.0) — a misconfigured "
                   "board and an unconfigured one look identical otherwise.",
        "mirrors": True,
    },
    "series:": {
        "authority": "user",
        "exposes": "sprint counts computed from whichever viewer's read "
                   "recorded them, shown to every later reader. Under "
                   "issue-level security a narrow viewer is shown aggregates "
                   "over issues they cannot browse. ADR 0018 §1.",
        "mirrors": False,
    },
    # Not app storage at all: a Jira *project property*, so Jira enforces who
    # may read it and mirroring holds the same way it does for issues. Listed
    # because the scan finds it and an inventory with a silent exception is not
    # an inventory — and because "it is not our store" is exactly the reasoning
    # that should be written down rather than assumed by the next reader.
    "orgConfig": {
        "authority": "jira",
        "exposes": "which statuses mean done, the working week and the "
                   "holidays — a project property read under the reader's own "
                   "authority, holding no issue-derived figure at all.",
        "mirrors": True,
    },
    # Roadmap item 6's operational log. Every entry is an act of *this app* with
    # an authority already established — a project administrator checked by
    # permissions.js, or the scheduled trigger — and none is a figure derived
    # from issues, which is why it needed nothing from item 5. The one identity
    # it holds is the actor, and it is sent to administrators only. ADR 0021.
    "audit": {
        "authority": "admin",
        "exposes": "when a recipient list changed and who changed it, and "
                   "whether a brief went out. Counts and field names, plus the "
                   "actor's account id; sent only to readers Jira says may "
                   "edit the configuration it describes.",
        "mirrors": True,
    },
    "forecastlog:": {
        "authority": "user",
        "exposes": "capacity claims derived from whichever viewer's read "
                   "published them, scored for every later reader. Same shape "
                   "as the series. ADR 0018 §2.",
        "mirrors": False,
    },
}


def permission_mirroring_checks():
    """Where reading as the viewer stops being enough — roadmap item 5.

    The panel mirrors permissions for free: every Jira read on that path is
    `api.asUser()`, so Jira decides what comes back and no figure was ever
    computed over an issue the reader cannot see. That property survives only
    as long as nothing is *kept*, and item 4 kept two things.

    This does not test a fix. It pins the inventory, so the exposure is a list
    somebody maintains rather than something the next session rediscovers.
    """
    print("permission mirroring")
    idx = (ROOT / "forge" / "src" / "index.js").read_text()

    # ---- the default is the safe side ----
    check("a Jira read is made as the viewer unless it says otherwise",
          "const jira = (as) => (as === 'app' ? api.asApp() : api.asUser());" in idx,
          [l.strip() for l in idx.splitlines() if "const jira =" in l])

    # The scheduled brief is the only thing that may read as the app, because it
    # is the only thing with no user to be. ADR 0013.
    app_reads = [l.strip() for l in idx.splitlines()
                 if "'app'" in l and ("issuesForEntry" in l or "projectContexts" in l
                                      or "orgConfigFor" in l or "boardProject" in l
                                      or "storyPointFieldFor" in l)]
    check("app-authority reads exist only on the scheduled path",
          len(app_reads) == 5, app_reads)

    # ---- every app-level store is declared ----
    #
    # kvs.get/set keys, from the source rather than from memory. A store that
    # appears without an entry here fails this, which is the point.
    # Read off the key declarations themselves rather than followed back from
    # the `kvs` call sites: a call site names a local, and resolving locals with
    # a regex found the *function* `forecastLogKey` instead of the `forecastlog:`
    # it builds — a check that passed by matching the wrong thing.
    #
    # Across all of forge/src, not just index.js: `seriesKey` is declared in
    # series.js, and scanning one file found two of the three stores while
    # reporting success. The guard below is why that showed.
    named = set()
    for src in sorted((ROOT / "forge" / "src").glob("*.js")):
        for m in re.finditer(r"(?:export\s+)?const\s+\w*(?:Key|KEY)\s*=\s*"
                             r"(?:\([^)]*\)\s*=>\s*)?[`'\"]([A-Za-z][\w-]*:?)",
                             src.read_text()):
            named.add(m.group(1))
    check("the key declarations were found at all, or this checks nothing",
          len(named) >= len(APP_LEVEL_STORES), sorted(named))
    undeclared = {n for n in named if n not in APP_LEVEL_STORES}
    check("every app-level store is declared with what it exposes",
          not undeclared, {"undeclared": sorted(undeclared),
                           "declared": sorted(APP_LEVEL_STORES)})
    check("and each declaration says whether it mirrors permissions",
          all(isinstance(v.get("mirrors"), bool) and v.get("exposes")
              for v in APP_LEVEL_STORES.values()),
          sorted(APP_LEVEL_STORES))

    # ---- the two that do not mirror hold aggregates, never identity ----
    #
    # This is what keeps the exposure arguable rather than plain. Both were
    # deliberate (ADR 0015, ADR 0017) and both stay true whatever item 5 does.
    check("the series store holds counts and a sprint name, nothing else",
          list(MT.ROW_FIELDS) == ["sprint", "committedSP", "completedSP",
                                  "committedItems", "completedItems", "throughput",
                                  "wipItems", "unplannedItems", "flowEfficiency",
                                  "valueDelivered"], list(MT.ROW_FIELDS))
    check("and the forecast log holds no issue identity either",
          not any(f in FC.CLAIM_FIELDS for f in ("key", "keys", "issues",
                                                 "summary", "assignee")),
          list(FC.CLAIM_FIELDS))

    # ---- impersonation is deferred, and a deferral needs a guard ----
    #
    # ADR 0020: composing the brief per recipient would mirror permissions
    # exactly, and Forge can do it — `asUser(accountId)` with
    # `allowImpersonation: true` on the scopes. It is deferred rather than
    # rejected, for reasons that could change. So the manifest declaring one
    # must mean somebody revisited that record, not that a line got added to
    # get something working.
    manifest = (ROOT / "forge" / "manifest.yml").read_text()
    check("the app declares no offline user impersonation",
          "allowImpersonation" not in manifest,
          [l.strip() for l in manifest.splitlines() if "mpersonat" in l])
    # And the largest grant this repository has ever discussed, refused in the
    # same record: checking another user's permissions needs Administer Jira.
    check("and asks for no administer-Jira grant to check recipients",
          not any(w in manifest for w in ("manage:jira-configuration",
                                          "ADMINISTER", "admin:jira")),
          [l.strip() for l in manifest.splitlines()
           if "manage:" in l or "admin" in l.lower()])

    # ---- the brief names no issue, and neither does its prompt ----
    #
    # ADR 0014 records that `restrict` filters against the anchor issue alone,
    # which is a disclosure only to the extent the brief says something about
    # the others. It says counts. Checked because ADR 0013 describes the model
    # as reading issue titles and the code has never done that.
    brief = (ROOT / "forge" / "src" / "brief.js").read_text()
    compose = (ROOT / "forge" / "src" / "compose.js").read_text()
    prompt = brief.split("export const briefMessages", 1)[1].split("\n};", 1)[0]
    check("the model is given the figures and nothing else",
          "Object.entries(figures" in prompt
          and not any(w in prompt for w in ("summary", "issueKey", "titles")),
          [l.strip() for l in prompt.splitlines() if "figures" in l][:2])
    sections = compose.split("export const sectionsFor", 1)[1].split("\n};", 1)[0]
    check("and no section template names an issue",
          not any(w in sections for w in ("{{key}}", "{{summary}}", "{{title}}")),
          [l.strip() for l in sections.splitlines() if "template:" in l])



def audit_log_checks():
    """The operational log — roadmap item 6, ADR 0021.

    Two things are checked, and the second matters more than the first. That the
    log records what it says it does; and that **nothing anywhere claims it is a
    compliance record**, because it cannot be one: this app writes it into its
    own storage, which it can also rewrite, and Jira's audit API is read-only so
    there is no log it could write to that it cannot alter.
    """
    print("the operational log")
    node = subprocess.run(["node", str(ROOT / "tests" / "forge_shapes.mjs")],
                          cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    if node.returncode != 0:
        check("the Forge shapes can be produced (needs node)", False,
              (node.stderr or node.stdout)[-200:])
        return
    A = json.loads(node.stdout)["audit"]

    # ---- a closed set of events, so no row is read by guessing ----
    check("only events whose meaning was written down are accepted",
          A["unknownEvent"] is None, A["unknownEvent"])
    check("and both transports know the same ones",
          A["events"] == list(LIVE.AUDIT_EVENTS),
          {"js": A["events"], "py": list(LIVE.AUDIT_EVENTS)})
    check("an entry with no time is not an audit entry",
          A["noTime"] is None, A["noTime"])

    # ---- the actor, which is the one identity here ----
    #
    # Unavoidable: an entry without one records that something happened and not
    # who did it. The scheduled trigger says so rather than borrowing a user.
    check("an entry names who did it", A["saved"]["actor"] == "acct-1",
          A["saved"]["actor"])
    check("and a run with no user says schedule rather than inventing one",
          A["noActor"]["actor"] == "schedule", A["noActor"]["actor"])

    # ---- counts and field names, never a recipient ----
    check("detail holding an identity is refused rather than trimmed",
          any("counts, flags and field names" in x for x in A["identityDetail"]),
          A["identityDetail"])
    check("a well-formed entry has nothing wrong with it",
          A["problems"] == [], A["problems"])
    check("and one carrying a field this log does not hold is refused",
          any("does not hold" in x for x in A["extraField"]), A["extraField"])

    # ---- the bound, which an audit log may not apply silently ----
    #
    # The absence of a row reads as the absence of the event, so a log that
    # forgets must say how much. Cumulative and in the store, not in the answer
    # to one read: a reader arriving after the ten thousandth event should be
    # told 9,000 are gone.
    check("the log is bounded", A["trimmed"]["kept"] == A["max"], A["trimmed"])
    check("and the count of what it forgot is cumulative, not per-read",
          A["trimmed"]["droppedTotal"] == A["trimmed"]["over"]
          and A["trimmedAgain"]["droppedTotal"] > A["trimmed"]["droppedTotal"],
          {"first": A["trimmed"], "again": A["trimmedAgain"]})
    check("a log that forgot nothing says nothing about it",
          A["noteEmpty"] == "", A["noteEmpty"])
    check("and one that forgot says so, and that it is not recoverable",
          "not recoverable" in A["noteDropped"], A["noteDropped"])

    # ---- the honesty, which is the point ----
    #
    # A tile presenting this as a compliance artefact would be the most
    # convincing wrong thing in the product.
    check("the note says the app wrote it and nothing else can attest to it",
          "nothing outside the app can attest" in A["noteDropped"],
          A["noteDropped"])
    js = (ROOT / "src" / "app.js").read_text()
    tile = js.split("function auditHtml", 1)[1].split("\n}", 1)[0]
    check("and so does the tile, whether or not anything was dropped",
          "attest" in tile and "operational record" in tile,
          [l.strip() for l in tile.splitlines() if "attest" in l])
    check("nothing calls it an audit log in the compliance sense",
          "compliance" not in tile.lower()
          or "rather than" in tile or "not" in tile, tile[:200])

    # ---- who may read it ----
    #
    # It carries the account id of whoever changed a recipient list. A reader
    # who may not change one has no business with that, and `canEdit` is Jira's
    # answer to exactly that question and is already asked on this route.
    idx = (ROOT / "forge" / "src" / "index.js").read_text()
    recip = idx.split("resolver.define('recipients'", 1)[1].split("}));", 1)[0]
    check("the log is sent to administrators only",
          "rights.canEdit ? await auditFor()" in recip,
          [l.strip() for l in recip.splitlines() if "auditFor" in l])
    # Sliced on the function's own closing brace, not on the first `};` inside
    # it — `return { ... };` comes first and cut the body short of its catch,
    # so the check was reading half a function and reporting on the half.
    reader = idx.split("const auditFor = async", 1)[1].split("\n};", 1)[0]
    check("and reading it never takes the tile down with it",
          "catch" in reader,
          [l.strip() for l in reader.splitlines() if "catch" in l or "return" in l][:3])
    check("nor does writing it ever fail a save it was recording",
          "catch" in idx.split("const audit = async", 1)[1].split("\n};", 1)[0],
          "audit() does not swallow")

    # ---- one shelf each, same body shape ----
    live = (ROOT / "scripts" / "serve_live.py").read_text()
    check("loopback keeps it in a git-ignored file",
          "audit.local.json" in live,
          [l.strip() for l in live.splitlines() if "audit.local" in l][:1])
    check("Forge keeps it in app storage under one key",
          "AUDIT_KEY = 'audit'" in (ROOT / "forge" / "src" / "audit.js").read_text(),
          "AUDIT_KEY")
    check("and it needs no scope the app did not already hold",
          (ROOT / "forge" / "manifest.yml").read_text().count("storage:app") == 1,
          "storage:app")


def cross_team_checks():
    """The cross-team roll-up — roadmap item 7, ADR 0023.

    Two things are checked. That a roll-up says which boards it covers, by
    name — because this app cannot know which boards a reader is *not* seeing,
    so an omission cannot be detected and must be made unnecessary to detect.
    And that it refuses to forecast, which matters more: `team_slice` selects by
    team label and would happily return one team's contexts for a cross-team
    context, producing a forecast over a narrower sample than its own heading
    claims. That is the fault CHANGELOG 1.8.0 records turning a 19-day answer
    into 77.
    """
    print("the cross-team roll-up")
    bundle = json.loads((ROOT / "data" / "sample-bundle.json").read_text())
    contexts = bundle["contexts"]

    ctx, members = SEL.resolve_context(contexts, "rollteams:BLC")
    check("a cross-team roll-up resolves to every sprint in the project",
          members and len(members) == len([c for c in contexts
                                           if c.get("projectKey") == "BLC"
                                           and (c.get("kind") or "sprint") == "sprint"]),
          len(members or []))
    check("and is marked as one, rather than recognised by re-reading its id",
          ctx.get("isCrossTeam") is True, ctx)

    # Names, not a count. "3 boards" can be checked by nobody; three names can
    # be checked by anybody who knows the programme.
    boards = SEL.cross_team_boards(members)
    check("it names the boards it covers",
          boards == sorted(set(c.get("boardName") for c in members)), boards)
    check("and the label lists them rather than counting them",
          all(b in SEL.cross_team_label(members) for b in boards),
          SEL.cross_team_label(members))
    check("the label says the boards are the ones this reader can see",
          "you can see" in SEL.cross_team_label(members),
          SEL.cross_team_label(members))

    # **No team label.** This is the guard, not a tidy-up: `team_slice` selects
    # by one, so a cross-team context carrying a team would be sliced to that
    # single team and forecast under a heading claiming the programme.
    check("a cross-team context carries no team label for team_slice to find",
          ctx.get("team") == "", repr(ctx.get("team")))

    # Windows overlap completely — 14, 30 and 90 days of one board — so a
    # roll-up holding all three counts the same issue three times. The
    # per-board roll-up in src/app.js excludes them for the same reason.
    windowed = contexts + [{"id": "BLC/9/w30", "kind": "window", "projectKey": "BLC",
                            "boardId": "9", "boardName": "Flow", "endDate": "2026-08-10"}]
    check("a flow board's windows are not rolled up",
          all((c.get("kind") or "sprint") == "sprint"
              for c in SEL.cross_team_members(windowed, "BLC")),
          [c["id"] for c in SEL.cross_team_members(windowed, "BLC")
           if c.get("kind") == "window"])

    # ---- the refusal, which is the point ----
    out = SEL.forecast_for(contexts, bundle["issues"], bundle.get("byContext") or {},
                           "rollteams:BLC", org_cfg=bundle.get("orgConfig"))
    check("a cross-team roll-up does not forecast",
          out.get("available") is False and "sprint_completion" not in out,
          sorted(out))
    check("and says it is about pooling teams, not about missing data",
          "throughput" in out["sentence"] and "one board at a time" in out["sentence"],
          out["sentence"])
    check("the refusal names the boards it would have pooled",
          all(b in out["sentence"] for b in boards), out["sentence"])
    check("and carries them as data, not only in prose",
          out.get("boards") == boards, out.get("boards"))

    # Everything that forecast before still forecasts. A guard that refused one
    # thing and broke another would be worse than the hazard it prevents.
    for cid in ("BLC/42/S24", "roll:BLC|42"):
        got = SEL.forecast_for(contexts, bundle["issues"],
                               bundle.get("byContext") or {}, cid,
                               org_cfg=bundle.get("orgConfig"))
        check("%s still forecasts" % cid,
              got is not None and "sprint_completion" in got, sorted(got or {}))

    # An unknown project is not a roll-up over nothing. Returning an empty
    # programme would be a total of zero presented as a fact.
    check("a project with no sprints is not rolled up into an empty programme",
          SEL.resolve_context(contexts, "rollteams:NOSUCH") is None,
          SEL.resolve_context(contexts, "rollteams:NOSUCH"))

    # The two roll-up kinds are different questions and must not share an id
    # that the wrong one could answer.
    check("the two roll-up prefixes are distinct",
          SEL.CROSS_TEAM_PREFIX != "roll:"
          and not SEL.CROSS_TEAM_PREFIX.startswith("roll:"),
          SEL.CROSS_TEAM_PREFIX)
    percontext, permembers = SEL.resolve_context(contexts, "roll:BLC|42")
    check("and the per-board roll-up still means one board's sprints",
          percontext.get("isCrossTeam") is not True
          and len({c.get("boardId") for c in permembers}) == 1,
          {c.get("boardId") for c in permembers})


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
    print("whose authority a read uses")
    test_every_jira_read_states_whose_authority_it_uses()
    print("the weekly brief")
    test_the_weekly_brief_is_wired_to_its_own_function()
    test_the_llm_module_matches_the_model_the_code_asks_for()
    test_the_brief_prompt_can_produce_an_answer_its_own_guard_accepts()
    test_a_scheduled_run_that_cannot_deliver_says_so_before_doing_work()
    print("finding a person by name")
    test_a_name_can_be_looked_up_without_the_directory_leaking()
    print("reading a stored id back as a name")
    test_a_stored_id_can_be_shown_as_a_name()
    print("who a boards brief goes to")
    test_a_boards_recipients_are_validated_before_anyone_is_told()
    print("one rule, two validators")
    test_the_two_recipient_validators_agree()
    print("the shape the context route returns")
    test_the_brief_reads_the_shape_the_context_route_really_returns()
    print("the brief as an email")
    test_the_brief_reaches_an_inbox_without_carrying_a_payload()
    test_nothing_is_sent_that_the_guards_would_have_stopped()
    print("the deploy trigger")
    test_the_deploy_trigger_covers_everything_the_image_ships()
    series_checks()
    forecast_log_checks()
    window_checks()
    permission_mirroring_checks()
    audit_log_checks()
    cross_team_checks()
    print("the container image")
    test_dockerfile_copies_everything_the_service_imports()
    test_the_image_takes_debians_security_updates()
    print("startup")
    test_refuses_to_start_unauthenticated()

    print()
    if failures:
        print("%d check(s) failed: %s" % (len(failures), ", ".join(failures)))
        sys.exit(1)
    print("all service checks passed")
