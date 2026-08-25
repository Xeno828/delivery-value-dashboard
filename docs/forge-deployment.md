# Finishing the Forge route

Three things in the Forge work were unfinished, and all three for the same reason: they needed an account, a platform or a tool that the code cannot supply itself. Section 1 is now done and is kept as the runbook for the next person who registers their own app. Sections 2 and 3 are still open. Each is what you need, what to do, and how to know it worked.

Nothing here is required to use the product. OAuth 2.0 (3LO) in [`scripts/jira_auth.py`](../scripts/jira_auth.py) is the working connection. This is the path to a Marketplace listing. Why the route is shaped this way: [ADR 0008](adr/0008-forge-calls-a-hosted-calculator.md).

**Do these in order.** Section 1 produces the app id that section 2 needs for the token audience, and section 3's image is what section 2's verifier ships inside.

---

## 1. Register the app and lint the manifest — done

The app is registered as **Shipping Forecast**, `forge lint` is clean, it deploys to `development` and installs on a dev site, and the dashboard inside the iframe reads that site's own boards, sprints and issues. The scopes are proven against real Jira rather than read off a documentation page.

Everything below still applies to anyone registering their own app, because the id is per-developer and never committed.

### You need

- An Atlassian account with developer access
- Node **22.x or 24.x** and `npm install -g @forge/cli`. The CLI warns on anything else and does not guarantee correct behaviour — Node 26 works today but is unsupported, and is worth ruling out first if the CLI does something inexplicable.
- A Jira Cloud site you can install a development app on

### Do

```bash
npm install -g @forge/cli
forge login                     # opens a browser
cd forge && forge register      # names the app, writes an id into manifest.yml
cd ..                           # the Makefile lives at the repository root
make forge-lint                 # stages the resource, installs the SDK, lints
make forge-deploy               # same, then deploys to development
```

`forge lint` is the step that matters. It validates the manifest against the current schema, which is the thing this repository cannot check for itself.

Three things will otherwise cost you a few minutes each, and the Makefile targets exist to absorb all three:

- The manifest references a static resource that `make forge-static` produces, and lint reports it as **missing** rather than unbuilt.
- `forge/src/index.js` imports `@forge/api` and `@forge/resolver`, so `forge deploy` fails at bundling until `npm install` has run in `forge/`. The error names the modules, not the missing install.
- `make` has to run from the repository root while the CLI has to run inside `forge/`, so a bare `make forge-lint` from the wrong directory just says there is no such target.

`forge/node_modules` is ignored. `forge/package-lock.json` is **not** — the repository ignores lockfiles generally because nothing else here ships npm packages, and that reasoning stops applying to code deployed into a customer's tenant. `tests/test_service.py` asserts the app depends on nothing outside `@forge/*`.

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

### After changing a module or a scope, reinstall — do not trust upgrade

`forge deploy` updates the code. **The installation stays bound to the manifest it was installed with**, so a module added after the first install does not appear, and a scope added after it is never silently granted. The failure has no error message: the old modules keep working and the new one is simply absent, which reads as a broken module rather than a stale install.

`forge install --upgrade` is the documented path and is worth trying first. When it does not take — and in development it may not — reset instead of investigating:

```bash
cd forge && forge uninstall     # then
cd forge && forge install
```

A development installation is disposable. Reaching for that early is cheaper than the diagnosis.

Two things that look like evidence and are not. An app **absent from Settings → Manage apps** does not mean it is uninstalled; development installs do not surface there the way Marketplace ones do. And **one module rendering while another does not** is the signature of a stale installation, not of a bad module — if any page draws, the app is installed and serving.

### The iframe forbids inline style and script, so the Forge build is not a copy

`dist/` is one self-contained file: one inline `<style>`, four inline `<script>` blocks, no external references at all. That is the product's defining property and it is the one thing a Forge Custom UI iframe will not serve — its CSP blocks both, **silently**. The page renders with the browser's default stylesheet, none of its JavaScript runs, and it looks like a broken build rather than a blocked one.

`make forge-static` therefore runs `build.py --split` rather than copying `dist/`. Same four sources, linked instead of inlined, plus the transport adapter and a different seed:

```
forge/static/dashboard/build/
  index.html      structure, with <link> and <script src>
  styles.css      byte-identical to src/styles.css
  app.js          byte-identical to src/app.js
  import.js       byte-identical to src/import.js
  bridge.js       forge/bridge/bridge.js, bundled; linked ahead of app.js
```

Two assemblies of one set of sources, never two sources — `tests/test_service.py` asserts the byte-equality, that nothing inline survives, and that the shipped single file stays inlined.

The JSON seed is still inline, as `type="application/json"`. It is data the page reads rather than script the browser executes, so a CSP should permit it. If it turns out not to, the symptom is a **styled page with no numbers on it**, and the fix is to fetch it rather than inline it.

### The bridge, and why the page does not know it is on Forge

The dashboard reaches live data through a transport it discovers rather than one it imports. Over `http(s)` that is a same-origin `GET api/…` answered by `serve_live.py`; inside this iframe there is no same-origin `api/` at all, so `forge/bridge/bridge.js` puts an `invoke()` on `window.__DVD_BRIDGE__` before the page loads and the page uses that. [ADR 0009](adr/0009-one-contract-two-transports.md) has the reasoning; the parts that will cost you an afternoon otherwise:

- **The adapter catches the SDK failing to load, and that is why it is CommonJS.** `@forge/bridge` connects to its host as a side effect of being loaded and throws outside a Forge iframe. As an ES `import` that ran before any of the adapter's own code, so the throw aborted it before it installed anything and the page quietly fell back to the same-origin fetch. Required inside a `try`, the failure is named in the console and no transport is installed instead of a broken one.
- **The adapter must be a classic script, linked before `app.js`.** `app.js` decides at load which transport it has. An ES module is deferred, so a module adapter sets the global *after* that decision — and the symptom is a page that silently believes it is offline, which looks exactly like a broken resolver. `make forge-static` bundles it `--format=iife` and `build.py --split --bridge` places the tag.
- **The Forge build is not seeded with the demo dataset.** It uses `forge/seed.json`, which is empty. The tenant's own sprints are the point, and Highpeak Commerce's would otherwise sit in the picker beside them — one click from being read as the customer's own numbers. The page carries one placeholder context until the bridge answers and then opens on the site's newest sprint.
- **The resolvers return `{status, body}`, not a body.** The body is the contract `serve_live.py` defines; the status is what the same answer would have carried over HTTP, because a 404 for a sprint this site does not have and a failure to answer at all are different things and the page says different words for each.
- **What the bridge does not carry is deliberate and is written down.** No `statusCategory` (the page categorises under its own config), no `started` (recognising an "In Progress" transition needs that config), no burndown series (that is Python, and Python is not running here). Each degrades to a sentence on the page rather than a zero. `addedMidSprint` is the exception that is computed, because false-by-default is not a silence — it is the claim that nothing was added, and the health score scores it as full marks.

### A deploy still proves less than it looks like

It proves the manifest is valid, the bundle builds and the static resources exist. It proves **nothing about permissions**, because at that point nothing has called Jira. A scope that is wrong fails at runtime, in a tenant.

### So there is a second page: the connection check

It was written to be deleted once the real bridge existed. It has been kept, and the reason changed rather than the plan being forgotten: it is the only thing that shows the outbound payload for one issue, and it now names which field this site calls story points. That used to be the diagnosis for a burndown that had flattened for no visible reason; it is a confirmation now, since the field is resolved by name rather than assumed — but a site whose field is called something else entirely still shows up here and nowhere else.

**Shipping Forecast — connection check** appears under Jira settings → Apps. It is not the product; it makes the calls a deploy leaves untested:

| | Answers |
|---|---|
| **1 Bridge** | Can a static resource reach a resolver at all — touches no Jira API, so a failure is the manifest or the bundle, never a scope |
| **2 Board read** | The exact call the product makes. Enter a board id; a 403 is a scope problem, a 404 is the wrong id |
| **3 Projection** | Shows the exact payload one issue would become. No summary, no assignee — the claim the architecture rests on, displayed rather than asserted |

A 403 after a scope change usually means the install needs re-running: Jira does not widen an existing consent on its own.

It is an **admin** page, not a second project page, for two reasons. Forge permits only one `jira:projectPage` per app — `forge lint` rejects a second. And a page that dumps board contents and outbound payloads belongs behind the admin gate rather than in front of every project's team.

**It asks for a board id rather than listing boards.** An earlier version offered them as buttons, and `forge lint` refused it: `GET /rest/agile/1.0/board` needs `read:project:jira`, which nothing else in this app requires. The scope was removed rather than granted — it would have existed purely to make a diagnostic more convenient, and it would have appeared on the consent screen of every install, in an app whose pitch is that it asks for almost nothing. If the real context picker ever needs to enumerate boards, that is the price, and it is a decision to take on its own merits.

It also degrades honestly. Outside a Forge iframe `invoke()` neither resolves nor rejects — it waits — so every call has a fifteen-second timeout and says so. The first version sat on *checking* indefinitely, which is the least useful thing a diagnostic can do.

Kept rather than deleted, per the note above. If it does go, take `forge/probe/`, the `connection-check` module and the two probe resolvers together.

### A scope change needs approving at deploy, and the CLI needs the right directory

Two things bite in the same minute, and they look like each other:

```
manifest-file-required — make sure you're in the top-level directory of your app
```

is `forge deploy` run from the repository root. The manifest is in `forge/`, the
Makefile is at the root, and `make forge-deploy` is what reconciles the two — it
also stages the static resources first, which a bare `forge deploy` does not, so
running the CLI by hand can deploy a bundle built before your last edit.

And a scope change makes the deploy ask for an approval it will not assume:

```bash
make forge-static
cd forge && forge deploy -e development --approve MAJOR_VERSION_RULE
```

`--approve` is deliberately not in the Makefile target. Auto-approving a major
version upgrade would also auto-approve the next scope change, silently, which is
the opposite of the allow-list's whole point. Type it when you mean it.

### After a scope change, reinstall

Adding the context picker added `read:project:jira`, `read:sprint:jira-software` and `read:jql:jira`. `forge lint` reports a scope change as a major version upgrade, and Jira does not widen an existing consent on its own — so after deploying, uninstall and install again rather than upgrading. The failure has no error message: the page renders and every Jira call comes back 403.

### Done when

`forge install` succeeds, all four sections of the connection check are green, and the project page shows **your** boards in the picker rather than a placeholder. That is the point at which the declared scopes are known to be sufficient.

Reached, on a dev site. Getting there took three deploys, and all three were the same lesson: every failure between the page and Jira was silent. A board whose sprints could not be read was reported as a board with no sprints; a resolver that threw was indistinguishable from a loopback server nobody had started; and a 404 said "server returned 404" for four situations with four different fixes. None of that was visible from the outside, and each cost a deploy cycle to find. The page says the reason now, in the context bar, and that is worth more here than anywhere else in this product — the deploy loop is slow and there is no console you can reach on a customer's tenant.

---

## 2. Verify the Forge invocation token — written, not yet confirmed against Atlassian

**Read [hosting the calculator](hosting-the-calculator.md) §1 before starting this.** The four values below are now confirmed and dated, and confirming them turned up three things this section did not know: the resolver used plain `fetch` and so would have received no token at all, the verifier read the tenant with a flat lookup against a claim that is nested, and the clock-skew allowance is longer than the token's whole life. The first two are fixed and pinned by the suite; the third is left at 30 seconds deliberately until a real token measures the lifetime. This section is otherwise still correct — it is the *"only you can do it"* framing that was wrong, because two of the three were code.


The calculator authenticates with a bearer shared secret today. That is honest and it works, but it is not tenant-aware: every installation presents the same string, so the service cannot tell one customer from another, and rotating it means redeploying everything at once.

The tenant-aware mechanism is the invocation token Forge attaches to a remote call — a JWT signed by Atlassian, carrying claims that identify the app and the installation.

### What is done

`_verify_forge_token()` is written and every mechanic below is proved by `tests/test_service.py`, which generates a keypair, serves a JWKS from a local HTTP server and mints its own tokens. A verifier now returns *who the caller is* rather than a boolean, so the access log names the tenant; the shared-secret mode returns no tenant rather than a placeholder, because one string presented by every installation cannot identify anybody.

### What is not, and it is the part only you can do

The four values that identify Atlassian's issuer are **configuration, not constants**, and the service refuses to start in this mode without them:

| | |
|---|---|
| `FORGE_JWKS_URL` | where the signing keys are published |
| `FORGE_ISSUER` | the exact `iss` value to require |
| `FORGE_AUDIENCE` | what goes in `aud` — the app id, the app ari, or something else |
| `FORGE_TENANT_CLAIM` | which claim carries the installation or tenant identity |

They are environment variables precisely so that no value nobody has confirmed lives in the source. Confirm each against current Atlassian documentation, and record the date beside the deployment that sets them. Guessing one produces a verifier that rejects every real token — or, the case that matters, accepts one minted for a different app.

Also still unconfirmed: whether the call presents an app-system token or a user token, and whether that differs between a scheduled trigger and a user-initiated resolver call.

**No real Forge token has been through this.** The mechanics are proved against a signer the test controls, which is the only way to test a verifier without one. That is a different claim from "it works", and it is the claim being made.

### What it has to check

Generic JWT verification, none of which is Forge-specific and all of which is routinely got wrong:

1. **Pin the algorithm.** Accept only the asymmetric algorithm Atlassian signs with. Reject `alg: none`, and reject an HMAC-signed token outright — the classic attack is to sign with HMAC using the public key as the secret, against a verifier that picks its algorithm from the header.
2. **Look the key up by `kid`** in Atlassian's JWKS. Reject a token with no `kid`, and reject an unknown `kid` rather than trying every key in the set.
3. **Cache the JWKS, and handle rotation.** Cache by `kid` with a TTL; on an unknown `kid`, re-fetch once, rate-limited. An uncached fetch per request makes Atlassian's endpoint your availability ceiling; a cache that never refreshes breaks on the next key rotation.
4. **Check `exp` and `nbf`** with a small clock skew allowance, not a generous one.
5. **Check `aud`** against your own app id. A valid token issued for a different app is still a valid token.
6. **Check `iss`** against Atlassian's issuer.
7. **Bind the tenant.** Take the installation or context claim and use it — that is the entire point of moving off the shared secret. A verifier that checks the signature and ignores who the token is for has bought you nothing.

### The dependency — done

`PyJWT[crypto]` is in `service/requirements.txt`, not `scripts/requirements.txt`: the security suite asserts the fetcher's dependency list stays at one, and the fetcher is what holds a customer's credentials, so that is the list worth keeping boring. The Dockerfile installs it before copying the source, CI audits it alongside the fetcher's, and `service/README.md` no longer claims the service is stdlib-only.

It is imported **inside** the verifier rather than at module scope, so shared-secret mode still runs and the suite still passes on a host that never installed it. The startup guard is what makes that safe: the token mode refuses to start if the import fails.

### Proved before it is trusted — done

The harness generates a keypair, serves a JWKS from a local HTTP server, and mints its own tokens. Every one of these is rejected, and the suite fails if any is not:

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

The HMAC forgery is assembled by hand rather than with `jwt.encode`, which refuses to use an asymmetric key as an HMAC secret. That is a good guard on the minting side and not one a verifier may rely on — an attacker writes those three lines.

Two properties of the key cache are pinned as well, because both failures are silent: inside the re-fetch floor an unknown `kid` costs Atlassian nothing at all, and past it costs exactly one fetch however many unknown ids arrive. An unknown `kid` is what somebody would send in a loop if this were unbounded.

An unknown `SERVICE_AUTH`, and a `forge-token` mode with any of its four values missing, both stop the process **and** refuse the request — a guard that only exists at startup is a guard somebody removes.

### Done when

`SERVICE_AUTH=forge-token` starts, **a real Forge remote call succeeds against it**, a hand-made token fails, and the tenant identity appears in the log line.

**All four, on 2026-08-25.** App version 4.0.0 on a dev site, and the calculator's access log:

```
POST /v1/slice            -> 200   0 issues  126ms  tenant=ari:cloud:ecosystem::installation/6cc978ae-…
POST /v1/forecast-context -> 200  36 issues    4ms  tenant=ari:cloud:ecosystem::installation/6cc978ae-…
```

The tenant is the installation ARI, and it matches what `forge install list` reports for that installation exactly. That is the claim this section has been unable to make since it was written: the mechanics were proved against a signer the suite controls, and now a token Atlassian actually minted has been accepted and attributed.

Three details in those two lines are worth reading rather than skipping. `/v1/slice` carries **0 issues**, because that route deliberately takes none — the resolver asks which contexts to sample before it fetches anything. It took **126 ms** against the second call's **4 ms**, which is the JWKS cache: the first real token missed and fetched Atlassian's keys, the second hit. And both went to `us-central1`, because this site is not pinned to the EU — the `default` and `US` base URLs are the same service.

Keep the shared-secret mode — it is what makes the service testable without a Forge installation.

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

The policy this section calls "a decision rather than a task" is taken in
[hosting the calculator](hosting-the-calculator.md) §11, and the rebuild cadence in §10.


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
