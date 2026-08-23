#!/usr/bin/env python3
"""
jira_auth.py — OAuth 2.0 (3LO) against Jira Cloud.

Replaces the personal API token in `.env` with a consented, revocable,
refreshable grant. The token is the customer's, issued to your app, scoped to
what you asked for, and they can withdraw it from their Atlassian account page
without telling you. A personal token can do none of those things: it carries
the permissions of whoever generated it, cannot be scoped, and is revoked only
by deleting it.

Both paths still work. The API-token path is not deprecated here — it is the
right thing for a one-off pull on your own board, needs no app registration,
and every existing `.env` keeps working. OAuth is what a customer's site can be
connected to.

What you have to do yourself
----------------------------
Register the app — this cannot be done from here, and the credentials must not
pass through anyone else's hands:

  1. developer.atlassian.com > Console > Create > OAuth 2.0 integration
  2. Permissions > Jira API > add  read:jira-work  and  read:jira-user
  3. Authorization > Callback URL:  http://127.0.0.1:8721/callback
  4. Settings > copy the client id and secret

     export JIRA_OAUTH_CLIENT_ID=...
     export JIRA_OAUTH_CLIENT_SECRET=...

Then

    python3 scripts/jira_auth.py login      # opens a browser, stores the grant
    python3 scripts/jira_auth.py status     # which sites, which scopes, expiry
    python3 scripts/jira_auth.py logout     # forgets the grant locally

The grant lands in `.jira-oauth.json`, mode 0600, git-ignored alongside `.env`.
It is a credential: it is never printed, never logged, and never written into
the dashboard file. `refresh_token` rotates on every use, which is Atlassian's
behaviour and not something to work around — the store is rewritten each time.

Marketplace listing is a separate step
--------------------------------------
This is the Connect/3LO half of roadmap item 1, and it is the half that lives
in this repository. Distribution — a Marketplace listing, its review, and
billing — is an Atlassian Console task with no code here. `forge/` holds the
scaffold for the other route.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import pathlib
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from datetime import datetime, timedelta, timezone

try:
    import requests
except ImportError:
    sys.exit("Install the dependency first:  pip install requests")

AUTH_HOST = "https://auth.atlassian.com"
API_HOST = "https://api.atlassian.com"
TIMEOUT = 45

#: Read-only, and deliberately the shortest list that produces the dashboard.
#: An app that asks for write access to close a deal is an app whose consent
#: screen makes the buyer's security reviewer stop and read.
SCOPES = ["read:jira-work", "read:jira-user", "offline_access"]

DEFAULT_PORT = 8721
DEFAULT_REDIRECT = "http://127.0.0.1:%d/callback" % DEFAULT_PORT
STORE_PATH = pathlib.Path(
    os.environ.get("JIRA_OAUTH_STORE")
    or (pathlib.Path(__file__).resolve().parent.parent / ".jira-oauth.json"))

#: Refresh this far before the token actually expires. A pull that starts with
#: fifty seconds left on the clock and takes a minute would otherwise fail
#: halfway through, having already written nothing.
EXPIRY_MARGIN = timedelta(minutes=5)


def _now():
    return datetime.now(timezone.utc)


def _client():
    cid = os.environ.get("JIRA_OAUTH_CLIENT_ID")
    secret = os.environ.get("JIRA_OAUTH_CLIENT_SECRET")
    if not (cid and secret):
        sys.exit("Set JIRA_OAUTH_CLIENT_ID and JIRA_OAUTH_CLIENT_SECRET.\n"
                 "Create them at developer.atlassian.com > Console > "
                 "OAuth 2.0 integration — see the header of this file.")
    return cid, secret


# --------------------------------------------------------------------- store
class TokenStore:
    """The grant on disk. Treated as a credential at every step."""

    def __init__(self, path=STORE_PATH):
        self.path = pathlib.Path(path)

    def read(self):
        if not self.path.exists():
            return None
        try:
            return json.loads(self.path.read_text())
        except (ValueError, OSError):
            return None

    def write(self, data):
        # Created 0600 before anything is written to it. Writing first and
        # chmod-ing after leaves a world-readable refresh token on disk for as
        # long as the write takes, which is a race worth not having.
        fd = os.open(str(self.path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh, indent=1)
        os.chmod(str(self.path), 0o600)

    def clear(self):
        if self.path.exists():
            self.path.unlink()


# ---------------------------------------------------------------- the dance
def authorize_url(client_id, redirect_uri, state):
    q = urllib.parse.urlencode({
        "audience": "api.atlassian.com",
        "client_id": client_id,
        "scope": " ".join(SCOPES),
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "prompt": "consent",
    })
    return AUTH_HOST + "/authorize?" + q


def _token_request(payload):
    r = requests.post(AUTH_HOST + "/oauth/token", json=payload, timeout=TIMEOUT)
    if r.status_code >= 400:
        # Atlassian's body names the cause (bad redirect, wrong secret, revoked
        # grant) and none of it is secret. Printing the status alone turns a
        # two-minute fix into an afternoon.
        sys.exit("Atlassian refused the token request (%d): %s"
                 % (r.status_code, r.text[:400]))
    return r.json()


def _store_grant(store, tok, sites=None):
    expires = _now() + timedelta(seconds=int(tok.get("expires_in") or 3600))
    data = store.read() or {}
    data.update({
        "access_token": tok["access_token"],
        "refresh_token": tok.get("refresh_token") or data.get("refresh_token"),
        "expires_at": expires.isoformat(),
        "scope": tok.get("scope") or " ".join(SCOPES),
    })
    if sites is not None:
        data["sites"] = sites
    store.write(data)
    return data


def accessible_resources(access_token):
    r = requests.get(API_HOST + "/oauth/token/accessible-resources",
                     headers={"Authorization": "Bearer " + access_token,
                              "Accept": "application/json"},
                     timeout=TIMEOUT)
    r.raise_for_status()
    return [{"id": s["id"], "name": s.get("name"), "url": s.get("url")}
            for s in r.json()]


class _Catcher(http.server.BaseHTTPRequestHandler):
    """One-shot loopback listener for the redirect. 127.0.0.1 only."""

    result = {}

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        q = urllib.parse.parse_qs(u.query)
        _Catcher.result = {k: v[0] for k, v in q.items()}
        body = (b"<!doctype html><meta charset=utf-8>"
                b"<title>Connected</title>"
                b"<body style='font:15px system-ui;padding:3rem;max-width:34rem'>"
                b"<h1 style='font-size:1.3rem'>Jira connected.</h1>"
                b"<p>You can close this tab and go back to the terminal.</p>")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass  # the query string holds the authorisation code


def login(port=DEFAULT_PORT, open_browser=True):
    client_id, client_secret = _client()
    redirect = "http://127.0.0.1:%d/callback" % port
    state = secrets.token_urlsafe(24)
    url = authorize_url(client_id, redirect, state)

    srv = http.server.HTTPServer(("127.0.0.1", port), _Catcher)
    _Catcher.result = {}
    t = threading.Thread(target=srv.handle_request, daemon=True)
    t.start()

    print("Open this to authorise, if it has not opened already:\n\n  %s\n" % url)
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    print("Waiting for the redirect on %s ..." % redirect)
    t.join(timeout=300)
    srv.server_close()

    got = _Catcher.result
    if not got:
        sys.exit("No redirect arrived within five minutes. Check that the app's "
                 "callback URL is exactly %s" % redirect)
    if got.get("error"):
        sys.exit("Atlassian returned an error: %s — %s"
                 % (got["error"], got.get("error_description", "")))
    # Compared with compare_digest rather than == so a mismatch cannot be
    # narrowed down by timing. The check itself is the point: without it this
    # endpoint accepts an authorisation code from anyone who can reach loopback.
    if not secrets.compare_digest(got.get("state", ""), state):
        sys.exit("The state parameter did not match. Nothing was stored.")

    tok = _token_request({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": got["code"],
        "redirect_uri": redirect,
    })
    sites = accessible_resources(tok["access_token"])
    store = TokenStore()
    _store_grant(store, tok, sites)
    print("\nStored in %s (mode 0600). Sites you granted:" % store.path.name)
    for s in sites:
        print("  %s  %s  cloudid=%s" % (s["name"], s["url"], s["id"]))
    if not sites:
        print("  (none — the grant carries no Jira site, so nothing can be pulled)")
    return sites


def ensure_token(store=None):
    """A valid access token, refreshing if it is close to expiry.

    Returns (access_token, data) or exits with what to do about it.
    """
    store = store or TokenStore()
    data = store.read()
    if not data or not data.get("refresh_token"):
        sys.exit("Not connected. Run:  python3 scripts/jira_auth.py login")

    try:
        expires = datetime.fromisoformat(data.get("expires_at"))
    except (TypeError, ValueError):
        expires = _now()
    if expires - EXPIRY_MARGIN > _now() and data.get("access_token"):
        return data["access_token"], data

    client_id, client_secret = _client()
    tok = _token_request({
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": data["refresh_token"],
    })
    data = _store_grant(store, tok)
    return data["access_token"], data


def resolve_cloud_id(data, wanted=None):
    """Which site to query, named rather than guessed.

    A grant covering two sites and a script that silently picks the first is
    how a report about the wrong company gets produced — and it would look
    entirely correct.
    """
    sites = data.get("sites") or []
    wanted = wanted or os.environ.get("JIRA_CLOUD_ID") or os.environ.get("JIRA_SITE")
    if wanted:
        for s in sites:
            if wanted in (s["id"], s.get("name"), s.get("url")):
                return s["id"], s
        sys.exit("No granted site matches %r. Granted: %s"
                 % (wanted, ", ".join(s.get("name") or s["id"] for s in sites) or "none"))
    if not sites:
        sys.exit("The grant covers no Jira site. Re-run login and pick one.")
    if len(sites) > 1:
        sys.exit("The grant covers %d sites — name one with JIRA_SITE or "
                 "--jira-site:\n  %s"
                 % (len(sites),
                    "\n  ".join("%s  %s" % (s.get("name"), s.get("url")) for s in sites)))
    return sites[0]["id"], sites[0]


class OAuthSession:
    """A requests-shaped session pointed at one granted Jira site.

    Exposes `.get`/`.post` taking the same `/rest/...` paths the API-token
    client uses, so callers do not care which of the two they were handed.
    """

    def __init__(self, site=None):
        token, data = ensure_token()
        self.cloud_id, self.site = resolve_cloud_id(data, site)
        self.base = "%s/ex/jira/%s" % (API_HOST, self.cloud_id)
        # The browsable site URL, for issue deep links in the dashboard. The
        # api.atlassian.com base is not clickable by a human.
        self.url = (self.site.get("url") or "").rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({"Authorization": "Bearer " + token,
                               "Accept": "application/json"})

    def _retry_auth(self):
        token, _ = ensure_token()
        self.s.headers["Authorization"] = "Bearer " + token

    def get(self, path, **params):
        r = self.s.get(self.base + path, params=params, timeout=TIMEOUT)
        if r.status_code == 401:
            self._retry_auth()
            r = self.s.get(self.base + path, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()

    def post(self, path, json=None):
        r = self.s.post(self.base + path, json=json, timeout=TIMEOUT)
        if r.status_code == 401:
            self._retry_auth()
            r = self.s.post(self.base + path, json=json, timeout=TIMEOUT)
        return r


def status():
    store = TokenStore()
    data = store.read()
    if not data:
        print("Not connected. Run:  python3 scripts/jira_auth.py login")
        return 1
    try:
        expires = datetime.fromisoformat(data["expires_at"])
        left = expires - _now()
        when = ("expired" if left.total_seconds() < 0
                else "%d min left" % (left.total_seconds() // 60))
    except (KeyError, TypeError, ValueError):
        when = "unknown expiry"
    print("Connected — %s, access token %s" % (store.path.name, when))
    print("Scopes: %s" % data.get("scope", "?"))
    for s in data.get("sites") or []:
        print("  %s  %s  cloudid=%s" % (s.get("name"), s.get("url"), s["id"]))
    print("\nNo token is printed here. Revoke at id.atlassian.com > "
          "Account settings > Connected apps.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=("login", "logout", "status", "sites"))
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help="loopback port for the redirect (default %d)" % DEFAULT_PORT)
    ap.add_argument("--no-browser", action="store_true",
                    help="print the URL instead of opening it")
    a = ap.parse_args()

    if a.action == "login":
        login(port=a.port, open_browser=not a.no_browser)
    elif a.action == "logout":
        TokenStore().clear()
        print("Local grant forgotten. It is still listed at id.atlassian.com > "
              "Connected apps until you revoke it there.")
    elif a.action == "sites":
        token, data = ensure_token()
        for s in accessible_resources(token):
            print("%s  %s  cloudid=%s" % (s.get("name"), s.get("url"), s["id"]))
    else:
        return status()
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
