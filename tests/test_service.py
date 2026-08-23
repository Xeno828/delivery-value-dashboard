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

import json
import pathlib
import re
import secrets
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent" / "tools"))
sys.path.insert(0, str(ROOT / "service"))

import app as SVC        # noqa: E402
import forecast as FC    # noqa: E402
import orgconfig as OC   # noqa: E402

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
    print("startup")
    test_refuses_to_start_unauthenticated()

    print()
    if failures:
        print("%d check(s) failed: %s" % (len(failures), ", ".join(failures)))
        sys.exit(1)
    print("all service checks passed")
