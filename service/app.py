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
    POST /v1/history         metrics.history_series
    POST /v1/burndown        metrics.burndown

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
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

# Everything a route needs, and it is imported rather than defined so the Forge
# function and this file cannot drift: `routes.py` is the module that travels
# into the WebAssembly runtime, and this file is the socket in front of it.
# Re-exported by name so `tests/test_service.py` and the Dockerfile smoke test
# keep reading `app.X` — one seam, two doors. ADR 0031.
from routes import (  # noqa: E402,F401
    ASK_TEXT_FIELDS, CALC_FIELDS, FREE_TEXT_FIELDS, MAX_ISSUES, MAX_ITEMS,
    ROUTES, VERSION, Refused, answer, check_sequence, clean_dataset,
    route_ask, route_burndown, route_facts, route_forecast,
    route_forecast_context, route_history, route_sequence, route_slice,
)
import intake as IN        # noqa: E402  — for the ask cap `meta()` reports
import orgconfig as OC     # noqa: E402

#: The one bound that is HTTP's rather than the calculation's, so it stays
#: with the socket. Reported rather than applied quietly, like the others.
MAX_BODY_BYTES = 4 * 1024 * 1024

# ------------------------------------------------------------------- auth
#
# Two modes, selected by SERVICE_AUTH, and a seam between them so swapping one
# for the other is a contained change rather than surgery on every route.
#
#   shared-secret   one string, presented by every installation. Simple, and
#                   it cannot tell one customer from another — which is what
#                   makes it the mode for local runs and the test suite rather
#                   than the mode for a tenant.
#   forge-token     the Atlassian-issued invocation token. Tenant-aware, and
#                   this app holds no secret of its own. Needs four facts about
#                   Atlassian's issuer that are configuration rather than
#                   constants, and RS256, which is the one dependency this
#                   service has — see docs/forge-deployment.md § 2.
#
# A verifier now returns *who the caller is* rather than a boolean, because the
# whole point of the token mode is being able to say which tenant asked. A
# rejection is None; nothing downstream reads anything but truthiness, so the
# shared-secret path is unchanged by it.
#
# The property that matters: an unknown or misconfigured mode is a refusal to
# start, never a request that sails through. Failing open here would be
# invisible — the service would look perfectly healthy.
AUTH_MODES = ("shared-secret", "forge-token")


def _auth_mode():
    return os.environ.get("SERVICE_AUTH") or "shared-secret"


def _expected_secret():
    """The configured shared secret, with surrounding whitespace removed.

    The strip is not cosmetic and it is not a convenience. `_verify_shared_secret`
    already strips the *presented* token, and stripping one side of a comparison
    but not the other means the two are not comparable: a secret store that
    appends a trailing newline — which is most of them, and every workflow built
    on `echo` or a piped `openssl rand` — produces a service that refuses every
    correct credential while looking perfectly configured.

    That shipped. `service/provision-gcp.sh` piped `openssl rand -hex 32`
    straight into Secret Manager, which stored the 64 hex characters and the
    newline `openssl` prints after them; Cloud Run injected all 65 bytes; and
    the deployment answered 401 to a caller presenting exactly the right secret.
    Nothing in the running service could have told you that, because from its
    side the credential genuinely did not match.

    A secret whose leading or trailing whitespace is meaningful cannot be
    authenticated by this service in any case, since the presented side is
    stripped before comparison. Stripping both makes the two sides agree about
    what is being compared.
    """
    return (os.environ.get("SERVICE_SHARED_SECRET") or "").strip()


def _verify_shared_secret(headers):
    want = _expected_secret()
    if not want:
        return False
    got = str(headers.get("Authorization") or "")
    if not got.startswith("Bearer "):
        return False
    # Constant-time: a byte-by-byte comparison lets a caller find the secret one
    # character at a time by measuring how long the rejection took.
    return hmac.compare_digest(got[len("Bearer "):].strip(), want)


# ------------------------------------------------- the Forge invocation token
#
# Four facts about Atlassian's issuer that this repository must not guess, and
# does not: they are configuration, required at startup in this mode, and the
# service refuses to come up without them. Guessing any of them produces a
# verifier that rejects every real token — or, worse, one that accepts a token
# minted for a different app.
#
#   FORGE_JWKS_URL       where the signing keys are published
#   FORGE_ISSUER         the exact `iss` value to require
#   FORGE_AUDIENCE       what goes in `aud` — the app id, the app ari, or other
#   FORGE_TENANT_CLAIM   which claim carries the installation or tenant identity
#
# Confirm each against current Atlassian documentation and record the date you
# confirmed it beside the deployment that sets them. They are environment
# variables rather than constants here precisely so that this file carries no
# value nobody has checked.
FORGE_ENV = ("FORGE_JWKS_URL", "FORGE_ISSUER", "FORGE_AUDIENCE", "FORGE_TENANT_CLAIM")

#: The only algorithm accepted, pinned rather than read from the token.
#:
#: A verifier that picks its algorithm from the header is the textbook failure:
#: `alg: none` strips the signature entirely, and an HMAC-signed token verified
#: with the RSA *public* key as the shared secret passes, because the public key
#: is public. Both are rejected before a key is even looked up.
FORGE_ALGORITHMS = ("RS256",)

#: Allowed clock skew on `exp` and `nbf`. Small on purpose — a generous window
#: is an expired token that still works, which is the thing `exp` is for.
FORGE_LEEWAY_SECONDS = 30

#: How long a fetched key set is trusted, and the shortest gap between fetches.
#:
#: An uncached fetch per request makes Atlassian's endpoint this service's
#: availability ceiling. A cache that never refreshes breaks silently at the
#: next key rotation, which is the failure you meet months later. So: cached by
#: `kid` with a TTL, and one re-fetch permitted when a `kid` is unknown, rate
#: limited so an attacker cannot use unknown key ids to drive traffic at
#: Atlassian on this service's behalf.
FORGE_JWKS_TTL_SECONDS = 600
FORGE_JWKS_MIN_REFETCH_SECONDS = 30

_jwks_cache = {"keys": {}, "fetched_at": 0.0, "last_attempt": 0.0}
_jwks_lock = threading.Lock()


def _forge_env(name):
    return os.environ.get(name) or ""


def _fetch_jwks(url):
    """The key set, as `{kid: jwk}`. Separated so the test can serve its own."""
    with urllib.request.urlopen(url, timeout=FORGE_JWKS_FETCH_TIMEOUT) as r:
        body = json.loads(r.read().decode("utf-8"))
    out = {}
    for k in body.get("keys") or []:
        kid = k.get("kid")
        if kid:
            out[kid] = k
    return out


FORGE_JWKS_FETCH_TIMEOUT = 5


def _jwk_for(kid, url, now):
    """The signing key for one `kid`, re-fetching at most once and not often.

    Returns None rather than raising, because every caller turns a missing key
    into the same answer: this token is not verifiable, so it is rejected.
    """
    with _jwks_lock:
        fresh = (now - _jwks_cache["fetched_at"]) < FORGE_JWKS_TTL_SECONDS
        if fresh and kid in _jwks_cache["keys"]:
            return _jwks_cache["keys"][kid]
        # Unknown kid, or a stale cache. One attempt, and not more often than
        # the floor — an unknown kid is exactly what an attacker would send
        # repeatedly if this were unbounded.
        if (now - _jwks_cache["last_attempt"]) < FORGE_JWKS_MIN_REFETCH_SECONDS:
            return _jwks_cache["keys"].get(kid) if fresh else None
        _jwks_cache["last_attempt"] = now
        try:
            keys = _fetch_jwks(url)
        except Exception:                       # noqa: BLE001 — see below
            # Never surfaced and never distinguished from a bad token. Which of
            # the two it was is useful to an operator in a log and useful to an
            # attacker in a response.
            return None
        _jwks_cache["keys"] = keys
        _jwks_cache["fetched_at"] = now
        return keys.get(kid)


def _claim_at(claims, path):
    """The claim at a dotted path, or None.

    The invocation token has no flat tenant claim. The installation identity is
    `app.installationId` and the site identity is `context.cloudId`, both nested
    one level below the top of the payload, and neither is reachable with a flat
    `claims.get()`. That is what this replaces, and the failure it replaces was
    invisible: the verifier refused every genuine token while every token the
    suite mints — all of which carry a flat claim — was accepted, so nothing in
    the harness could tell the difference. Only Atlassian's published payload
    can, which is why the fix arrives with a nested case beside it.

    A path with no dot in it is a single-element walk, so a flat claim name goes
    on working. `context.cloudId` resolves too, and is the wrong choice here for
    a reason worth stating: no context is delivered to the backend-function
    invocations this app makes, so on this route that claim is always absent.
    """
    node = claims
    for part in str(path or "").split("."):
        if not part or not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def _verify_forge_token(headers):
    """The Atlassian-issued invocation token, or None.

    Returns the tenant this call is for, which is the entire point of moving
    off the shared secret: a verifier that checks a signature and ignores who
    the token was issued for has bought nothing at all.

    Every rejection returns None. None of them says *why* in the response —
    which check failed is useful to an operator reading a log and useful to
    somebody probing the endpoint, and only one of those is a customer.
    """
    # Imported here rather than at module scope so the service still runs, and
    # still passes its suite, in shared-secret mode on a host that has not
    # installed the crypto dependency. The startup guard is what makes that
    # safe: this mode cannot serve unless the import works.
    #
    # Caught rather than allowed to propagate, and that is not tidiness. This
    # function's contract is "a principal, or None" — a *refusal*. Raising on a
    # host without the library made it neither, and the assertion that requests
    # must not pass even with the startup guard removed was answered by an
    # exception rather than by a rejection. A verifier that cannot verify has
    # exactly one honest answer and it is no.
    try:
        import jwt                              # noqa: PLC0415
    except Exception:                           # noqa: BLE001
        return None

    raw = str(headers.get("Authorization") or "")
    if not raw.startswith("Bearer "):
        return None
    token = raw[len("Bearer "):].strip()
    if not token:
        return None

    try:
        head = jwt.get_unverified_header(token)
    except Exception:                           # noqa: BLE001
        return None

    # Pinned before a key is looked up, so `alg: none` and the HMAC-with-the-
    # public-key trick are refused by this service rather than left to the
    # library's defaults.
    if head.get("alg") not in FORGE_ALGORITHMS:
        return None
    kid = head.get("kid")
    if not kid:
        return None

    jwk = _jwk_for(kid, _forge_env("FORGE_JWKS_URL"), time.time())
    if jwk is None:
        return None
    try:
        key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
        claims = jwt.decode(
            token, key=key,
            algorithms=list(FORGE_ALGORITHMS),
            audience=_forge_env("FORGE_AUDIENCE"),
            issuer=_forge_env("FORGE_ISSUER"),
            leeway=FORGE_LEEWAY_SECONDS,
            options={"require": ["exp", "iss", "aud"],
                     "verify_exp": True, "verify_nbf": True,
                     "verify_aud": True, "verify_iss": True,
                     "verify_signature": True},
        )
    except Exception:                           # noqa: BLE001
        return None

    tenant = _claim_at(claims, _forge_env("FORGE_TENANT_CLAIM"))
    if not isinstance(tenant, str) or not tenant.strip():
        # A signature that verifies against an unknown tenant is a call this
        # service cannot attribute, and attributing calls is why this mode
        # exists. Refused rather than served anonymously.
        return None
    return {"mode": "forge-token", "tenant": tenant.strip()}


def _shared_secret_principal(headers):
    """The shared-secret verifier, in the shape the seam now returns.

    One tenant, unnamed, because a single string presented by every
    installation cannot identify one. That is the limitation the token mode
    exists to remove, and saying `None` here is how the log line stays honest
    about it.
    """
    return {"mode": "shared-secret", "tenant": None} if _verify_shared_secret(headers) else None


VERIFIERS = {"shared-secret": _shared_secret_principal, "forge-token": _verify_forge_token}


def startup_problem(insecure=False):
    """Why this configuration must not serve, or None if it may.

    Checked before the socket is opened. A misconfigured deploy should fail to
    come up; one that comes up unauthenticated looks healthy to every dashboard
    that is watching it.
    """
    if insecure:
        return None
    mode = _auth_mode()
    if mode not in AUTH_MODES:
        return ("SERVICE_AUTH=%r is not a mode this service has. Use one of: %s"
                % (mode, ", ".join(AUTH_MODES)))
    if mode == "forge-token":
        missing = [k for k in FORGE_ENV if not _forge_env(k)]
        if missing:
            # The same rule the shared secret has: a mode that cannot verify
            # must not serve. Guessing any of these produces a verifier that
            # rejects every real token, or — the case that matters — accepts one
            # minted for a different app.
            return ("SERVICE_AUTH=forge-token needs %s, and this service will not "
                    "fall back to something weaker.\nConfirm each against current "
                    "Atlassian documentation — docs/forge-deployment.md section 2 "
                    "lists what they are." % ", ".join(missing))
        try:
            import jwt  # noqa: F401,PLC0415
        except Exception:                       # noqa: BLE001
            return ("SERVICE_AUTH=forge-token needs PyJWT with its crypto extra, "
                    "which is not importable here.\n"
                    "  pip install -r service/requirements.txt")
        return None
    if not _expected_secret():
        return ("Refusing to start without SERVICE_SHARED_SECRET.\n"
                "An open calculator is free compute for whoever finds it, and\n"
                "holding no data is not the same as needing no authentication.\n\n"
                "  SERVICE_SHARED_SECRET=$(openssl rand -hex 32) python3 service/app.py\n"
                "  python3 service/app.py --insecure     # local development only")
    return None


def authorised(headers, insecure=False):
    """Who this caller is, or None. Truthy exactly where it used to be True."""
    if insecure:
        return {"mode": "insecure", "tenant": None}
    verify = VERIFIERS.get(_auth_mode())
    if verify is None:
        return None
    return verify(headers)


def meta():
    return {
        "service": "delivery-value-calculator",
        "version": VERSION,
        "computes": "nothing — every figure comes from agent/tools",
        "routes": sorted(ROUTES),
        "limits": {"maxBodyBytes": MAX_BODY_BYTES, "maxIssues": MAX_ISSUES,
                   "maxAsks": IN.MAX_ASKS, "maxItems": MAX_ITEMS},
        "acceptedIssueFields": sorted(CALC_FIELDS),
        "rejectedIssueFields": sorted(FREE_TEXT_FIELDS),
        "defaultCalendar": OC.summary(OC.DEFAULTS),
    }


# ---------------------------------------------------------------- dispatch
#
# Who the current request is for, so the access log can say it. Kept beside the
# request rather than returned from `handle()` because `handle()` is the seam
# every test calls directly and its two-value contract is worth not disturbing
# for a log line.
#
# Thread-local: the built-in server is threading, so a module-level variable
# would attribute one tenant's request to another under any concurrency at all
# — which is a worse failure in a log than having no tenant in it.
_current = threading.local()


def _seen(headers, who):
    _current.who = who


def caller():
    """The principal on this thread, or None. For the access log only."""
    return getattr(_current, "who", None)




def handle(method, path, raw_body, headers, insecure=False):
    """One request in, (status, dict) out. No sockets, so tests call it directly.

    Everything after the body is parsed is `routes.answer`, which is the same
    function the Forge function calls. What this adds is the wire: the health
    and meta routes, the method check, who is asking, and how big the body is.
    """
    if method == "GET" and path == "/healthz":
        return 200, {"ok": True, "version": VERSION}
    if method == "GET" and path == "/v1/meta":
        who = authorised(headers, insecure)
        if not who:
            return 401, {"ok": False, "error": "unauthorised"}
        _seen(headers, who)
        return 200, {"ok": True, "result": meta()}

    if path not in ROUTES:
        return 404, {"ok": False, "error": "no such route: %s" % path}
    if method != "POST":
        return 405, {"ok": False, "error": "%s takes POST" % path}
    who = authorised(headers, insecure)
    if not who:
        return 401, {"ok": False, "error": "unauthorised"}
    _seen(headers, who)
    if raw_body is None or len(raw_body) > MAX_BODY_BYTES:
        return 413, {"ok": False, "error":
                     "body over the %d-byte limit. Send one team's slice rather "
                     "than the whole dataset — a forecast needs one team's "
                     "history." % MAX_BODY_BYTES}
    try:
        body = json.loads(raw_body or b"{}")
    except ValueError as e:
        return 400, {"ok": False, "error": "body is not JSON: %s" % e}
    return answer(path, body)


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
        # The tenant, where the auth mode can name one. This is the whole
        # reason for the token mode: a shared secret presented by every
        # installation cannot say who is asking, so it logs no tenant rather
        # than a placeholder that reads like one.
        who = caller() or {}
        tenant = who.get("tenant")
        sys.stderr.write("%s %s -> %d  %d issues  %.0fms%s%s\n"
                         % (method, self.path.split("?")[0], status, n,
                            1000 * (time.time() - started),
                            ("  tenant=%s" % tenant) if tenant else "",
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

    problem = startup_problem(a.insecure)
    if problem:
        sys.exit(problem)
    Handler.insecure = a.insecure

    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print("Calculator on http://%s:%d" % (a.host, a.port))
    print("  %s" % meta()["computes"])
    print("  auth: %s" % ("NONE — --insecure" if a.insecure else _auth_mode()))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
