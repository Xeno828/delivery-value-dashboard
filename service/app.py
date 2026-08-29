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
import traceback
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent" / "tools"))

import forecast as FC      # noqa: E402
import intake as IN        # noqa: E402
import metrics as MT       # noqa: E402
import orgconfig as OC     # noqa: E402
import selection as SEL    # noqa: E402

VERSION = "1.0"

#: Bounds, and each one is reported rather than applied quietly. A truncated
#: issue list reads as a complete one, and a forecast over half a team's
#: history looks exactly like a forecast over all of it.
MAX_BODY_BYTES = 4 * 1024 * 1024
MAX_ISSUES = 50_000
MAX_ASKS = 50
# An asked-for item count is bounded so a typo cannot start a simulation that
# runs for minutes. Stated in the refusal rather than clamped quietly, which is
# the same rule every other limit here follows. Matches scripts/serve_live.py,
# because the two answer the same question over different transports.
MAX_ITEMS = 5000

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


def route_slice(body):
    """Which contexts a forecast for this one would sample.

    The caller that needs this is a Forge resolver. It has to fetch the issues
    of every context in the slice before it can ask for a forecast over them,
    and it must not decide the slice itself — that decision is `team_slice`,
    which is the logic whose every failure is a plausible date rather than an
    error, and which exists in exactly one place for that reason.

    So the resolver asks. It sends the contexts it knows about, with no issues
    at all — this route needs none — and gets back the ids to fetch. One round
    trip against a service that answers in well under a second, in exchange for
    there being no second copy of the rule and no way to forecast from a
    narrower sample than the answer claims.
    """
    ds = body.get("dataset")
    contexts = ds.get("contexts") if isinstance(ds, dict) else None
    if not isinstance(contexts, list) or not contexts:
        raise Refused('send {"dataset": {"contexts": [...]}} — this route chooses '
                      'the slice and needs the contexts to choose from. No issues '
                      'are needed and none should be sent.')
    cid = body.get("contextId")
    if not isinstance(cid, str) or not cid.strip():
        raise Refused('send "contextId" — which context the slice is for')
    members, label = SEL.slice_for(contexts, cid.strip())
    if members is None:
        raise Refused("unknown context %r — no slice was chosen" % cid.strip(), 404)
    return {"contextIds": [c["id"] for c in members if c.get("id")], "slice": label}


def route_forecast_context(body):
    """A forecast for one context, with this service choosing the slice.

    `/v1/forecast` takes a flat list of issues and simulates them. That leaves
    the *slice* — which issues make up this team's history, how much work is
    outstanding, and whether the date on offer is a deadline or an artefact — to
    whoever calls it. Over loopback that caller is `scripts/serve_live.py`,
    which is Python and can use the same rules the tools use. Over Forge the
    caller is a Node resolver, which cannot; and the slice is the last thing in
    this repository that should be written twice, because every one of its
    failures is a plausible date rather than an error.

    So the caller sends what it has — the contexts, the issues, and which
    context the reader is looking at — and `selection.forecast_for` does the
    rest. This service still computes nothing: it validates, delegates, and
    passes the figures back. `tests/test_service.py` holds this route's answer
    against the same function called directly.
    """
    ds = clean_dataset(body)
    contexts = ds.get("contexts")
    if not isinstance(contexts, list) or not contexts:
        raise Refused('send "dataset.contexts" — the slice is chosen from them. '
                      'A forecast built from a single sprint refuses for want of '
                      'observations, so the sample is the team and only the '
                      'outstanding work is the selected context\'s.')
    cid = body.get("contextId")
    if not isinstance(cid, str) or not cid.strip():
        raise Refused('send "contextId" — which context this forecast is for')
    items = body.get("items")
    if items is not None:
        if (not isinstance(items, int) or isinstance(items, bool)
                or items <= 0 or items > MAX_ITEMS):
            raise Refused("items must be a whole number between 1 and %d — "
                          "nothing was simulated" % MAX_ITEMS)
    out = SEL.forecast_for(contexts, ds["issues"], ds.get("byContext") or {},
                           cid.strip(), items=items,
                           target=_iso_or_none(body, "target"),
                           org_cfg=ds.get("orgConfig") or {})
    if out is None:
        # A context this dataset does not describe is a 404 and not a 400: the
        # request was well formed and named something that is not here.
        raise Refused("unknown context %r — nothing was simulated" % cid.strip(), 404)

    # The forecast log — roadmap item 4c, ADR 0017. The caller sends the log it
    # holds; `update_log` adds this forecast's claims, resolves the ones whose
    # horizon has passed, trims and scores. This service still computes nothing
    # of its own: one tool function does all of it and both transports call it.
    #
    # Optional, and absent means the caller keeps no log — the forecast comes
    # back exactly as it did before, which is what `/v1/forecast` and every
    # existing caller rely on.
    log = body.get("log")
    if log is not None:
        if not isinstance(log, list):
            raise Refused('"log" must be the caller\'s forecast log, or absent')
        # **The latest date this caller's data can speak to**, which is one
        # rule with two answers. Over Forge the issues are read live, so it is
        # today. Over loopback the dataset is a file that stops where it stops,
        # and resolving a claim whose window runs past the last day the file
        # describes would count zero completions and call the forecast wrong —
        # a false verdict from missing data rather than a missed prediction.
        # Absent, it falls back to the forecast's own as-of, which is the
        # conservative end of the same rule.
        today = _iso_or_none(body, "today") or _iso_or_none(body, "asOf")
        out["calibration"] = FC.update_log(
            log, out.get("claims") or [], ds["issues"],
            today or (out.get("asked") or {}).get("as_of"))
    return out


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


def route_history(body):
    """One row per sprint, for a caller that cannot compute one.

    The caller that needs this is a Forge resolver. It holds the tenant's own
    contexts and issues and must not derive a history row itself — `CLAUDE.md`
    is explicit that nothing between a tool and a reader does arithmetic, and a
    resolver that counted completions would be the second implementation this
    repository spends most of its tests preventing.

    So it sends what it has and `metrics.history_series` does the rest. This
    service still computes nothing: it validates, delegates and passes the rows
    back. A row here is nine numbers and a sprint name; the issue text that
    produced them is refused at the door by `clean_dataset`, like every other
    route.

    The rows come back with their context id and the sprint's state attached,
    because the caller has to decide whether it may *record* each one — a sprint
    that closed before the app saw the board is shown and never stored. That
    decision is the caller's and is made in `forge/src/series.js`; this route
    supplies the two facts it needs and takes no view.
    """
    ds = clean_dataset(body)
    contexts = (body.get("dataset") or {}).get("contexts")
    if not isinstance(contexts, list) or not contexts:
        raise Refused('send {"dataset": {"contexts": [...], "issues": [...]}} — '
                      "a row is per sprint, and the sprints come from the contexts. "
                      "Nothing was calculated.")
    got = MT.history_series(contexts, ds.get("issues") or [])
    rows, skipped = got["rows"], got["skipped"]

    # Every row is returned to the caller, because what may be *recorded* is
    # every sprint this look could see. What is *shown* stops at the selected
    # context — a sprint does not get to be compared against its own future.
    cid = body.get("contextId")
    shown = MT.series_upto(rows, cid) if isinstance(cid, str) and cid else rows

    # The caller's store, if it has one, so the merged answer comes back in the
    # same round trip. Nothing is stored here — this service holds no state and
    # is not becoming a place a tenant's series lives. It is handed the rows the
    # caller already has, and it returns what a reader should see.
    stored = body.get("stored")
    if stored is not None and not isinstance(stored, dict):
        raise Refused('"stored" must be the caller\'s series object, or absent')
    merged = MT.merge_series(stored or {},
                             [{"sprintId": r["contextId"], "row": r["row"],
                               "asOf": r.get("asOf"),
                               "issuesSeen": r.get("issuesSeen")}
                              for r in shown],
                             body.get("statuses"))
    # What the board has, against the window that was kept — roadmap item 4b.
    # The caller knows both; the sentence is the tool's, because it states a
    # count a reader reads.
    board_sprints = body.get("boardSprints")
    window = body.get("window")

    return {
        "rows": rows,
        # Read off the lists they describe, never computed beside them. `offered`
        # is what the caller sent; `sprints` is what produced a row. The two
        # differing is the fact a reader needs and the one that was invisible.
        "offered": len(rows) + len(skipped),
        "sprints": len(rows),
        "skipped": skipped,
        "merged": merged["rows"],
        "orphaned": merged["orphaned"],
        "outsideWindow": merged.get("outsideWindow") or [],
        "note": " ".join(x for x in (
            MT.series_note(merged),
            MT.skipped_note(skipped),
            MT.window_note(board_sprints, len(rows) + len(skipped), window)) if x),
    }


ROUTES = {
    "/v1/facts": route_facts,
    "/v1/forecast": route_forecast,
    "/v1/forecast-context": route_forecast_context,
    "/v1/slice": route_slice,
    "/v1/ask": route_ask,
    "/v1/sequence": route_sequence,
    "/v1/history": route_history,
}


def meta():
    return {
        "service": "delivery-value-calculator",
        "version": VERSION,
        "computes": "nothing — every figure comes from agent/tools",
        "routes": sorted(ROUTES),
        "limits": {"maxBodyBytes": MAX_BODY_BYTES, "maxIssues": MAX_ISSUES,
                   "maxAsks": MAX_ASKS, "maxItems": MAX_ITEMS},
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
    """One request in, (status, dict) out. No sockets, so tests call it directly."""
    if method == "GET" and path == "/healthz":
        return 200, {"ok": True, "version": VERSION}
    if method == "GET" and path == "/v1/meta":
        who = authorised(headers, insecure)
        if not who:
            return 401, {"ok": False, "error": "unauthorised"}
        _seen(headers, who)
        return 200, {"ok": True, "result": meta()}

    fn = ROUTES.get(path)
    if fn is None:
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
