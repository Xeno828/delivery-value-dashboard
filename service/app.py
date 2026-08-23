#!/usr/bin/env python3
"""
app.py — the hosted calculator.

Forge runs Node and cannot execute agent/tools/. Rather than write a second
Monte Carlo in JavaScript, the Forge app posts the fields a calculation needs
to this service, which imports the existing Python unchanged. One
implementation of every figure. See docs/adr/0008-forge-calls-a-hosted-calculator.md.

What this is
------------
A calculator. It holds no credential, stores nothing, and cannot reach Jira —
the Forge app owns the grant and does the pulling. It receives dates and status
categories and returns numbers.

**It does no arithmetic of its own.** Every figure comes from metrics.py,
forecast.py or intake.py, exactly as the dashboard and the CLI get theirs. The
moment this file computes a percentage, there are two answers to one question
and no way to tell which the customer is reading.

Routes
------
    GET  /healthz            liveness; no auth, no data
    GET  /v1/meta            version, limits, the calendar defaults
    POST /v1/facts           metrics.facts
    POST /v1/forecast        forecast.build
    POST /v1/ask             intake.forecast_ask
    POST /v1/sequence        intake.sequence

Every POST takes {"dataset": {...}, ...} and returns
{"ok": true, "calendar": "...", "result": {...}} or {"ok": false, "error": "..."}.

`calendar` is on every response on purpose: two forecasts of one board under
different working weeks are different forecasts, and the difference is
otherwise invisible to whoever reads the number.

Running it
----------
    SERVICE_SHARED_SECRET=$(openssl rand -hex 32) python3 service/app.py

It refuses to start without a secret. An open calculator is free compute for
anyone who finds it, and the fact that it holds no data does not make it
something to leave unauthenticated. `--insecure` exists for local development
and says so on every request.

Deployment
----------
`wsgi_app` is a plain WSGI callable, so gunicorn or any WSGI host runs the same
code the built-in server does:

    gunicorn -w 4 -b 0.0.0.0:8080 'service.app:wsgi_app'

Stateless and sub-second, so scale-to-zero suits it. See service/README.md.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import pathlib
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent" / "tools"))

import forecast as FC      # noqa: E402
import intake as IN        # noqa: E402
import metrics as MT       # noqa: E402
import orgconfig as OC     # noqa: E402

VERSION = "1.0"

#: Bounds, and each one is reported rather than applied quietly. A truncated
#: issue list reads as a complete one, and a forecast over half a team's
#: history looks exactly like a forecast over all of it.
MAX_BODY_BYTES = 4 * 1024 * 1024
MAX_ISSUES = 50_000
MAX_ASKS = 50

#: Fields a calculation reads. Anything else in an incoming issue is dropped
#: before the tools see it — not for size, but because free text has no
#: business being here at all. Forge holds the summaries and re-attaches them
#: by key after the call, so nothing is lost from the rendered tile.
CALC_FIELDS = frozenset((
    "key", "created", "started", "resolved", "statusCategory", "status",
    "storyPoints", "priority", "dueDate", "flagged", "addedMidSprint",
    "contextId", "epicKey",
))

#: Fields refused outright if they arrive. A caller sending issue summaries to
#: a calculator is a caller with a bug, and accepting them quietly would make
#: this service a place customer text lives — which is the whole thing the
#: projection exists to avoid.
FREE_TEXT_FIELDS = ("summary", "assignee", "epic", "labels", "url", "valueBasis")


class Refused(Exception):
    """A bad request, with the sentence to send back."""

    def __init__(self, sentence, status=400):
        super().__init__(sentence)
        self.sentence = sentence
        self.status = status


# ------------------------------------------------------------------- auth
def _expected_secret():
    return os.environ.get("SERVICE_SHARED_SECRET") or ""


def authorised(headers, insecure=False):
    if insecure:
        return True
    want = _expected_secret()
    if not want:
        return False
    got = str(headers.get("Authorization") or "")
    if not got.startswith("Bearer "):
        return False
    # Constant-time: a byte-by-byte comparison lets a caller find the secret one
    # character at a time by measuring how long the rejection took.
    return hmac.compare_digest(got[len("Bearer "):].strip(), want)


# ------------------------------------------------------------- validation
def _clean_issue(raw, offenders):
    if not isinstance(raw, dict):
        raise Refused("every issue must be an object")
    for f in FREE_TEXT_FIELDS:
        if f in raw:
            offenders.add(f)
    return {k: v for k, v in raw.items() if k in CALC_FIELDS}


def clean_dataset(body):
    """The dataset the tools will see, or a refusal saying what was wrong."""
    ds = body.get("dataset")
    if not isinstance(ds, dict):
        raise Refused("send {\"dataset\": {...}} — nothing was calculated")
    issues = ds.get("issues")
    if not isinstance(issues, list):
        raise Refused("dataset.issues must be a list — nothing was calculated")
    if len(issues) > MAX_ISSUES:
        raise Refused("%d issues is over this service's limit of %d. Nothing was "
                      "calculated: a forecast over a truncated history looks "
                      "exactly like a forecast over all of it."
                      % (len(issues), MAX_ISSUES), 413)

    offenders = set()
    clean = {
        "issues": [_clean_issue(i, offenders) for i in issues],
        "meta": ds.get("meta") if isinstance(ds.get("meta"), dict) else {},
        "orgConfig": ds.get("orgConfig") if isinstance(ds.get("orgConfig"), dict) else {},
    }
    for optional in ("releases", "contexts", "byContext", "history"):
        if isinstance(ds.get(optional), (list, dict)):
            clean[optional] = ds[optional]

    if offenders:
        raise Refused(
            "the payload carried %s. This service calculates from dates and "
            "status categories; issue text does not belong here and was not "
            "stored. Project the issues before sending them."
            % ", ".join(sorted(offenders)))

    problems = OC.validate(OC.from_dataset(clean))
    if problems:
        raise Refused("the organisation config in this payload is not usable: "
                      + "; ".join(problems))
    return clean


def _iso_or_none(body, key):
    v = body.get(key)
    if v is None:
        return None
    from datetime import date
    try:
        date.fromisoformat(str(v)[:10])
    except ValueError:
        raise Refused("%s must be YYYY-MM-DD, not %r — nothing was calculated"
                      % (key, v))
    return str(v)[:10]


# ------------------------------------------------------------------ routes
def route_facts(body):
    ds = clean_dataset(body)
    scope = body.get("scope") or "sprint"
    if scope not in ("sprint", "all"):
        raise Refused("scope must be 'sprint' or 'all'")
    prev = body.get("previous") if isinstance(body.get("previous"), dict) else None
    return MT.facts(ds, previous=prev, scope=scope)


def route_forecast(body):
    ds = clean_dataset(body)
    remaining = body.get("remaining")
    if remaining is not None:
        if not isinstance(remaining, int) or isinstance(remaining, bool) or remaining < 0:
            raise Refused("remaining must be a whole number of items, or absent "
                          "to use the dataset's own outstanding count")
    window = body.get("windowDays")
    if window is not None and (not isinstance(window, int) or window <= 0):
        raise Refused("windowDays must be a positive whole number of days")
    return FC.build(ds,
                    as_of=_iso_or_none(body, "asOf"),
                    remaining=remaining,
                    target=_iso_or_none(body, "target"),
                    snapshots=body.get("snapshots"),
                    window_days=window)


def route_ask(body):
    ds = clean_dataset(body)
    ask = body.get("ask")
    if not isinstance(ask, dict):
        raise Refused("send an \"ask\" object — see docs/product-intake.md")
    return IN.forecast_ask(ds, dict(ask), board=body.get("board"),
                           as_of=_iso_or_none(body, "asOf"))


def route_sequence(body):
    ds = clean_dataset(body)
    asks = body.get("asks")
    if not isinstance(asks, list) or not asks:
        raise Refused("send a non-empty \"asks\" list. Sequencing compares the "
                      "outstanding asks against each other, so it needs at least two.")
    if len(asks) > MAX_ASKS:
        raise Refused("%d asks is over this service's limit of %d. Nothing was "
                      "sequenced: a comparison of some of the asks reads as a "
                      "comparison of all of them." % (len(asks), MAX_ASKS), 413)
    return IN.sequence(ds, [dict(a) for a in asks], board=body.get("board"),
                       as_of=_iso_or_none(body, "asOf"))


ROUTES = {
    "/v1/facts": route_facts,
    "/v1/forecast": route_forecast,
    "/v1/ask": route_ask,
    "/v1/sequence": route_sequence,
}


def meta():
    return {
        "service": "delivery-value-calculator",
        "version": VERSION,
        "computes": "nothing — every figure comes from agent/tools",
        "routes": sorted(ROUTES),
        "limits": {"maxBodyBytes": MAX_BODY_BYTES, "maxIssues": MAX_ISSUES,
                   "maxAsks": MAX_ASKS},
        "acceptedIssueFields": sorted(CALC_FIELDS),
        "rejectedIssueFields": sorted(FREE_TEXT_FIELDS),
        "defaultCalendar": OC.summary(OC.DEFAULTS),
    }


# ---------------------------------------------------------------- dispatch
def handle(method, path, raw_body, headers, insecure=False):
    """One request in, (status, dict) out. No sockets, so tests call it directly."""
    if method == "GET" and path == "/healthz":
        return 200, {"ok": True, "version": VERSION}
    if method == "GET" and path == "/v1/meta":
        if not authorised(headers, insecure):
            return 401, {"ok": False, "error": "unauthorised"}
        return 200, {"ok": True, "result": meta()}

    fn = ROUTES.get(path)
    if fn is None:
        return 404, {"ok": False, "error": "no such route: %s" % path}
    if method != "POST":
        return 405, {"ok": False, "error": "%s takes POST" % path}
    if not authorised(headers, insecure):
        return 401, {"ok": False, "error": "unauthorised"}
    if raw_body is None or len(raw_body) > MAX_BODY_BYTES:
        return 413, {"ok": False, "error":
                     "body over the %d-byte limit. Send one team's slice rather "
                     "than the whole dataset — a forecast needs one team's "
                     "history." % MAX_BODY_BYTES}
    try:
        body = json.loads(raw_body or b"{}")
    except ValueError as e:
        return 400, {"ok": False, "error": "body is not JSON: %s" % e}
    if not isinstance(body, dict):
        return 400, {"ok": False, "error": "body must be a JSON object"}

    try:
        result = fn(body)
    except Refused as r:
        return r.status, {"ok": False, "error": r.sentence}
    except Exception:
        # The traceback goes to the operator, never to the caller: it would
        # carry field values, and those are the customer's.
        traceback.print_exc(file=sys.stderr)
        return 500, {"ok": False, "error": "the calculation failed. Nothing partial "
                                           "was returned."}

    cfg = OC.from_dataset(body.get("dataset") or {})
    return 200, {"ok": True, "calendar": OC.summary(cfg), "version": VERSION,
                 "result": result}


# -------------------------------------------------------------------- WSGI
def wsgi_app(environ, start_response):
    """So gunicorn runs exactly the code the built-in server runs."""
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    body = environ["wsgi.input"].read(min(length, MAX_BODY_BYTES + 1)) if length else b""
    headers = {"Authorization": environ.get("HTTP_AUTHORIZATION", "")}
    status, payload = handle(environ.get("REQUEST_METHOD", "GET"),
                             environ.get("PATH_INFO", "/"), body, headers,
                             insecure=os.environ.get("SERVICE_INSECURE") == "1")
    out = json.dumps(payload).encode()
    start_response("%d " % status, [("Content-Type", "application/json"),
                                    ("Content-Length", str(len(out))),
                                    ("Cache-Control", "no-store")])
    return [out]


class Handler(BaseHTTPRequestHandler):
    insecure = False
    server_version = "delivery-value-calculator/" + VERSION

    def _run(self, method):
        started = time.time()
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        body = self.rfile.read(length) if 0 < length <= MAX_BODY_BYTES else (
            b"" if length == 0 else None)
        status, payload = handle(method, self.path.split("?")[0], body,
                                 self.headers, self.insecure)
        out = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(out)
        # Shape and outcome, never content. An access log holding issue keys is
        # a copy of the customer's backlog in someone's log aggregator.
        n = 0
        try:
            n = len(json.loads(body or b"{}").get("dataset", {}).get("issues", []))
        except Exception:
            pass
        sys.stderr.write("%s %s -> %d  %d issues  %.0fms%s\n"
                         % (method, self.path.split("?")[0], status, n,
                            1000 * (time.time() - started),
                            "  [INSECURE]" if self.insecure else ""))

    def do_GET(self):
        self._run("GET")

    def do_POST(self):
        self._run("POST")

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)))
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"),
                    help="127.0.0.1 by default; a container needs 0.0.0.0")
    ap.add_argument("--insecure", action="store_true",
                    help="accept unauthenticated requests. Local development only.")
    a = ap.parse_args()

    if not a.insecure and not _expected_secret():
        sys.exit("Refusing to start without SERVICE_SHARED_SECRET.\n"
                 "An open calculator is free compute for whoever finds it, and\n"
                 "holding no data is not the same as needing no authentication.\n\n"
                 "  SERVICE_SHARED_SECRET=$(openssl rand -hex 32) python3 service/app.py\n"
                 "  python3 service/app.py --insecure     # local development only")
    Handler.insecure = a.insecure

    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print("Calculator on http://%s:%d" % (a.host, a.port))
    print("  %s" % meta()["computes"])
    print("  auth: %s" % ("NONE — --insecure" if a.insecure else "bearer shared secret"))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
