# Finishing the Forge route

Three things in the Forge work are unfinished, and all three are unfinished for the same reason: they need an account, a platform or a tool that the code cannot supply itself. Each section below is a runbook — what you need, what to do, and how to know it worked.

Nothing here is required to use the product. OAuth 2.0 (3LO) in [`scripts/jira_auth.py`](../scripts/jira_auth.py) is the working connection. This is the path to a Marketplace listing. Why the route is shaped this way: [ADR 0008](adr/0008-forge-calls-a-hosted-calculator.md).

**Do these in order.** Section 1 produces the app id that section 2 needs for the token audience, and section 3's image is what section 2's verifier ships inside.

---

## 1. Register the app and lint the manifest

`forge/manifest.yml` has never been through `forge lint`, and no app has been registered. The Forge-specific syntax — the `remotes` block in particular — is written from documentation rather than from a successful run.

### You need

- An Atlassian account with developer access
- Node 18+ and `npm install -g @forge/cli`
- A Jira Cloud site you can install a development app on

### Do

```bash
npm install -g @forge/cli
forge login                     # opens a browser
cd forge && forge register      # names the app, writes an id into manifest.yml
cd ..                           # the Makefile lives at the repository root
make forge-lint                 # stages the static resource, then lints
```

`forge lint` is the step that matters. It validates the manifest against the current schema, which is the thing this repository cannot check for itself.

Two things that will otherwise cost you a few minutes each. The manifest references a static resource that `make forge-static` produces, and lint reports it as **missing** rather than unbuilt — `make forge-lint` stages it first, which is the only reason that target exists. And `make` has to run from the repository root while the CLI has to run inside `forge/`, so a bare `make forge-lint` from the wrong directory just says there is no such target.

### Then, before committing anything

`forge register` writes an `app.id` into `manifest.yml`. **Do not commit it.** It ties the manifest to one developer's Atlassian account, and everyone who clones the repository afterwards gets a manifest pointing at somebody else's app.

```bash
git diff forge/manifest.yml     # the id, and whatever --fix rewrote
```

Expect more than the id: `forge lint --fix` also rewrites the runtime and can add granular scopes. Keep those changes, drop the id line. The suite fails if an id reaches `HEAD`, but catching it there is worse than not committing it.

`tests/test_service.py` fails if an app id is committed, so this is caught, but catching it after the fact is worse than not doing it.

Keep the registered id somewhere your team shares — a password manager or the deployment repo — rather than in this one.

### What lint will not tell you

Several things have to agree with this repository, and a schema linter has no opinion on any of them. `tests/test_service.py` asserts each on every push:

| | Why |
|---|---|
| Every scope is read-only | An app asking for write access to close a deal is one whose consent screen stops a security reviewer |
| No scope outside a reviewed allow-list | Adding one should be a deliberate edit with a reason, not something a `--fix` run does quietly |
| The egress `remote:` names a declared remote | A typo here fails at runtime, in a tenant, not at build time |
| The manifest's resource path is what `make forge-static` writes | Lint calls a missing resource a broken manifest, not an unbuilt one |
| No app id in `HEAD` | Having one locally is correct; committing it points every clone at one developer's app |

Note the allow-list rather than parity with `SCOPES` in `jira_auth.py`. Forge uses granular scopes (`read:issue-details:jira`) and the 3LO client uses classic ones (`read:jira-work`); the two are equivalent in intent and can never be equal as strings. The first version of that check matched a single colon only, so granular scopes were invisible to it — including, had one appeared, a granular write scope.

### Done when

`forge lint` passes, `forge deploy -e development` succeeds, and `forge install` puts the app on a test site. At that point the project page renders and the resolver's `boardIssues` call returns real data — which is also the proof that the declared scopes are sufficient.

---

## 2. Verify the Forge invocation token

The calculator authenticates with a bearer shared secret today. That is honest and it works, but it is not tenant-aware: every installation presents the same string, so the service cannot tell one customer from another, and rotating it means redeploying everything at once.

The tenant-aware mechanism is the invocation token Forge attaches to a remote call — a JWT signed by Atlassian, carrying claims that identify the app and the installation.

### The seam is already there

`service/app.py` has two auth modes. `SERVICE_AUTH=forge-token` currently **refuses to start**:

```
SERVICE_AUTH=forge-token is not implemented yet, and this service will not
fall back to something weaker.
```

That refusal is deliberate. Fill in `_verify_forge_token(headers)` and remove the guard in `startup_problem()`; nothing else in the service changes, because every route already goes through `authorised()`.

I did not write this function. Verifying RS256 needs a crypto library, and there is no way to test a token verifier here without a real token to test against — shipping security code whose correctness nobody has observed is worse than shipping an honest placeholder.

### What it has to check

Generic JWT verification, none of which is Forge-specific and all of which is routinely got wrong:

1. **Pin the algorithm.** Accept only the asymmetric algorithm Atlassian signs with. Reject `alg: none`, and reject an HMAC-signed token outright — the classic attack is to sign with HMAC using the public key as the secret, against a verifier that picks its algorithm from the header.
2. **Look the key up by `kid`** in Atlassian's JWKS. Reject a token with no `kid`, and reject an unknown `kid` rather than trying every key in the set.
3. **Cache the JWKS, and handle rotation.** Cache by `kid` with a TTL; on an unknown `kid`, re-fetch once, rate-limited. An uncached fetch per request makes Atlassian's endpoint your availability ceiling; a cache that never refreshes breaks on the next key rotation.
4. **Check `exp` and `nbf`** with a small clock skew allowance, not a generous one.
5. **Check `aud`** against your own app id. A valid token issued for a different app is still a valid token.
6. **Check `iss`** against Atlassian's issuer.
7. **Bind the tenant.** Take the installation or context claim and use it — that is the entire point of moving off the shared secret. A verifier that checks the signature and ignores who the token is for has bought you nothing.

### What you must confirm from current Atlassian documentation

I am not going to guess these, and neither should the implementation:

- the JWKS endpoint URL
- the exact `iss` value
- what goes in `aud` — the app id, the app ari, or something else
- which claim carries the installation or tenant identity
- whether the call presents an app-system token or a user token, and whether that differs between a scheduled trigger and a user-initiated resolver call

Write each one down in a comment next to the check that uses it, with the date you confirmed it.

### The dependency

RS256 needs `PyJWT[crypto]`. Put it in a **new** `service/requirements.txt`, not `scripts/requirements.txt` — the security suite asserts the fetcher's dependency list stays at one, and that assertion is worth keeping. Then:

- add `pip install -r service/requirements.txt` to `service/Dockerfile`
- add `service/requirements.txt` to the `pip-audit` step in CI
- update `service/README.md`, which currently says the service is stdlib-only

### Prove it before you trust it

Generate a keypair in the test, serve a JWKS from a local HTTP server, and mint your own tokens. That tests the mechanics without needing Atlassian. Every one of these must be rejected:

| Token | Must be |
|---|---|
| Correctly signed, in date, right `aud` and `iss` | accepted |
| Expired | rejected |
| `nbf` in the future | rejected |
| Right signature, wrong `aud` | rejected |
| Right signature, wrong `iss` | rejected |
| Signed with a key not in the JWKS | rejected |
| `alg: none`, no signature | rejected |
| HMAC-signed using the RSA public key as the secret | rejected |
| No `kid` in the header | rejected |
| Unknown `kid` | rejected, after at most one JWKS refetch |
| Well-formed but truncated | rejected |

Add the same startup-refusal checks that exist for the current mode: an unknown `SERVICE_AUTH`, and a `forge-token` mode with its configuration missing, must both stop the process rather than serve.

### Done when

`SERVICE_AUTH=forge-token` starts, a real Forge remote call succeeds against it, a hand-made token fails, and the tenant identity from the token appears in the service's log line. Keep the shared-secret mode — it is what makes the service testable without a Forge installation.

---

## 3. Build and scan the container image

`service/Dockerfile` has never been built. It was written on a machine with no Docker.

### Already covered

Two checks exist, and between them the likely failure is already caught:

- **`tests/test_service.py`** reconstructs the image's filesystem from the Dockerfile's `COPY` lines and imports the service from it. This catches the narrow, nasty failure — the Dockerfile stops copying a module the service imports, and every other suite still passes because they run against a working tree where the file is present. It needs no Docker, so it runs where the Dockerfile actually gets edited.
- **The `container` job in CI** builds the real image and smoke-tests it: refuses to start with no secret, runs non-root, refuses an unauthenticated request, returns a real forecast for an authenticated one, refuses issue text, and does not log issue text.

So the first push after this lands is the real build. If it fails, it fails in CI rather than in a deploy.

### Do it locally too

```bash
docker build -f service/Dockerfile -t delivery-value-calculator .

# it must refuse to start with no secret
docker run --rm delivery-value-calculator ; echo "exit $?"   # expect non-zero

docker run -d --name calc -p 8080:8080 \
  -e SERVICE_SHARED_SECRET="$(openssl rand -hex 32)" \
  --read-only --tmpfs /tmp \
  delivery-value-calculator

curl -fsS http://127.0.0.1:8080/healthz
docker exec calc id -u          # expect 10001, never 0
docker rm -f calc
```

`--read-only` is worth keeping in the real deployment. The service writes nothing, so the claim is true, and a true claim is a cheap one to make in a security review.

### Scan it

Not yet in CI, because adding a scanner that fails the build on somebody else's CVE feed needs a policy decision about what blocks a merge:

```bash
docker scout cves delivery-value-calculator
# or
trivy image --severity HIGH,CRITICAL delivery-value-calculator
```

The base is `python:3.12-slim` and the service installs nothing, so the attack surface is the base image. Rebuild on a schedule rather than only on source changes — the image goes stale even when this repository does not. That is the argument for a weekly scheduled build, and it is the one gap here that is a decision rather than a task.

### Done when

The `container` job is green, a local scan is clean at HIGH and CRITICAL, and the image is pushed to a registry your platform can pull from.

---

## What is still not here

Registering the Marketplace listing, its review, and billing. Atlassian Console work with no code in this repository, and a commercial workstream rather than an engineering one.
