# Hosting the calculator

Where `service/` runs, what it costs, and the operational decisions that come with it.

`service/README.md` says the service is stateless and sub-second and that this suits scale-to-zero. That was right and it is not the hard part. The hard part is that **the calculator being reachable is not the same as the Forge app being able to call it**, and three things stand between those two states that the runbook did not know about. They are in §1, before the provider comparison, because two of them change what has to be built and one of them changes which provider wins.

The plan is a plan: nothing is deployed and no cloud account exists yet. The two code changes §1 turned up have landed and are pinned by the suite — §3 says what is done and what waits for the switchover.

---

## 1. Three findings that change the shape of the work

All three were found by reading Atlassian's current documentation against this repository's code on **2026-08-25**. Each was a claim this repository made that is not true, and none of them fails loudly — the first two produce a `401` and the third a security margin nobody chose. **The first two are fixed**; the third waits on evidence, for the reason in §1.3.

### 1.1 The resolver would not receive an invocation token even if the service verified one

`forge/manifest.yml` carries this comment:

> Declaring it as a `remote` rather than a bare egress URL is what gets each call an Atlassian-issued invocation token.

It does not. Declaring a remote is what makes the egress *permitted*. What attaches the Forge Invocation Token is **`invokeRemote()` from `@forge/api`**, and `callCalculator()` in [`forge/src/index.js:100`](../forge/src/index.js) does not use it:

```js
import api, { route, fetch } from '@forge/api';
…
const res = await fetch(`${process.env.CALCULATOR_URL ?? ''}${path}`, { … });
```

That is the plain external-fetch path. It sends the headers it is given and nothing else. Atlassian's [manifest reference for remotes](https://developer.atlassian.com/platform/forge/manifest-reference/remotes/) states the requirement directly: `compute` in the remote's `operations` array is "required for `invokeRemote` to work", and the `remotes` entry has no `operations` key today.

So the token mode is not blocked only on four environment values, as `docs/forge-deployment.md` §2 has it. It is blocked on four values **and two code changes**, and until both are made the switchover returns `401` on every call regardless of which auth mode the service runs in.

**Both have landed.** `callCalculator()` calls `invokeRemote('calculator', …)`, the remote declares `operations: [compute]`, and `permissions.external.fetch` is gone along with the `fetch` it authorised. The remote key is written as a literal so the suite can hold it against the manifest — the typo the egress rule used to be checked for has moved into the code, and the check moved with it.

There is a second consequence, and it is the one that settles §3: a URL read from `process.env.CALCULATOR_URL` is **one URL for every installation**. Region-pinned base URLs are resolved by Forge per install, from the manifest. A hardcoded environment URL cannot participate in that at all.

### 1.2 The tenant claim is nested, and the verifier looks it up flat

`_verify_forge_token()` in [`service/app.py:319`](../service/app.py) ends with:

```python
tenant = claims.get(_forge_env("FORGE_TENANT_CLAIM"))
if not isinstance(tenant, str) or not tenant.strip():
    return None
```

A flat `dict.get`. The FIT's top-level keys are `app`, `context`, `principal`, `icLabel`, `aud`, `iss`, `iat`, `nbf`, `exp`, `jti` — and **not one of them is a tenant identifier**. The installation identity lives at `app.installationId`; the site identity lives at `context.cloudId`. Both are nested one level down.

`claims.get("app.installationId")` returns `None`, so the verifier refuses. It refuses in the safe direction — no real token is ever accepted, rather than a wrong one being accepted — but the effect is that `SERVICE_AUTH=forge-token` rejects **100% of genuine traffic**, and the twelve rejection cases in `tests/test_service.py` all still pass, because every one of them mints a flat `tenant` claim of its own. The harness cannot see this; only a real token or Atlassian's published payload can.

`context.cloudId` is additionally the wrong choice here even though it reads like the more natural "tenant": Atlassian's [function-to-remote documentation](https://developer.atlassian.com/platform/forge/remote/calling-from-function/) notes that **no context is passed to `invokeRemote` when it is called from a backend function** — which is exactly how this app calls it. `app.installationId` is the right handle, and Atlassian says so for an unrelated reason: it is "guaranteed to always be available" and is the value remote storage should be keyed against.

**Landed.** `_claim_at()` walks a dotted path, and a claim name with no dot still reads flat, so the existing harness is not rewritten. The new case mints a token carrying `app.installationId` in the shape Atlassian publishes, and three more assert the walk refuses as firmly as the flat lookup did — a path that runs out, one that lands on an object, one that lands on blank. Reverting the walk to `claims.get()` fails the nested case and leaves the flat one passing, which is what makes the pair worth having.

### 1.3 The clock-skew allowance is larger than the token's whole life

`FORGE_LEEWAY_SECONDS = 30` in [`service/app.py:188`](../service/app.py). The documented example FIT carries `iat: 1700175149` and `exp: 1700175174` — a **25-second** lifetime. A 30-second leeway therefore roughly doubles the window in which a captured token is still accepted, from 25 seconds to about 55.

`docs/forge-deployment.md` §2 already states the rule this breaks: *"Check `exp` and `nbf` with a small clock skew allowance, not a generous one."* Thirty seconds is generous against a twenty-five-second token.

Recommended: **5 seconds**. But confirm the lifetime against a real token first — 25 s comes from a documentation example, not from a stated guarantee, and tightening a margin on the strength of a sample is how you build a verifier that rejects real traffic at the tail. This is the one finding of the three that should wait for evidence rather than lead the work.

---

## 2. The recommendation

**Google Cloud Run, request-based billing, `min-instances=0`, two services — `europe-west3` (Frankfurt) and `us-central1` — reached through region-pinned `baseUrl`s in the Forge manifest and authenticated with `SERVICE_AUTH=forge-token`.**

The cost case is not the reason, and pretending otherwise would be the plan's first lie. At every volume in §4 this workload is **inside or barely outside the free tier on four of the six providers considered**. AWS Lambda is cheaper than Cloud Run at the top tier — by about two dollars a month. Fly.io has a lower floor. Nothing here is chosen on price, because at this size price is not a real axis.

It is chosen on three things that are real:

1. **Scale-to-zero with a genuine zero.** The service is idle most of the day and the floor cost of "nothing is happening" is the only cost line that behaves like a subscription. Cloud Run's request-based billing charges nothing for an instance that is not a minimum instance and is not serving. AWS App Runner does not have this and its floor is §4's headline number.
2. **The container ships unchanged.** `service/Dockerfile` is a plain HTTP server on `$PORT`, non-root, read-only-capable. Cloud Run runs it as-is. Lambda would need a WSGI adapter between Forge and the tools, and this repository has a standing constraint that nothing between the tools and a reader may do arithmetic — an adapter does not do arithmetic, but it is one more thing that would have to be shown not to.
3. **Two regions is two `gcloud run deploy` invocations of one image.** Residency is day one (§5), and the thing that makes it cheap here is that Forge does the tenant→region routing itself. The provider only has to exist in both places.

Runners-up and why not, in §4.3.

---

## 3. The auth decision: `forge-token`, and it is no longer close

The handoff framed this as a genuine choice: confirm the four values and run tenant-aware, or add a bearer header from an encrypted Forge variable and launch on `shared-secret`. §1.1 collapses it.

**Recommendation: `forge-token`.** Three reasons, in order of weight.

**Residency routing needs `invokeRemote` and `invokeRemote` attaches the FIT.** This is the decisive one. The shared-secret route keeps `fetch(process.env.CALCULATOR_URL + path)`, which is one URL for every installation in the world. With EU and US both required on day one, that route would mean building tenant→region routing inside the app — and the app would have to identify the tenant to route on, which is precisely the capability the shared secret does not have. The cheap-looking option turns out to require inventing, badly, the mechanism the expensive-looking option gets for free.

**The work is comparable either way.** "Add a bearer header" sounds smaller than "confirm four values", but the four values are now confirmed (Appendix A) and the header route still needs the manifest edit, an encrypted variable, a rotation story, and its own tests. The token route needs `invokeRemote`, `operations: [compute]`, and a nested-claim lookup. Neither is a day's difference.

**It is the mode with no secret in it.** In `forge-token` mode the service holds nothing: the four `FORGE_*` values are configuration, not credentials — a public JWKS URL, a public issuer string, this app's own public id, and a claim name. There is no secret store to provision, nothing to rotate, and nothing that leaks if a deploy log is read. §6 is a much shorter section because of this, and that shortness is the argument.

**Keep `shared-secret`.** It is what makes the service testable without a Forge installation, `tests/test_service.py` depends on it, and the CI container job smoke-tests through it. It is not being launched on; it is not being removed.

### What has to be built before switchover

| | Where | Status |
|---|---|---|
| `operations: [compute]` on the remote | `forge/manifest.yml` | **done**, asserted |
| `invokeRemote('calculator', …)` replacing `fetch(CALCULATOR_URL …)` | `forge/src/index.js` | **done**, key asserted against the manifest |
| `permissions.external.fetch` removed with the `fetch` it authorised | `forge/manifest.yml` | **done** |
| Dotted-path tenant claim | `service/app.py` | **done**, nested case asserted |
| The manifest and resolver comments that said a `remote` declaration attaches the token | both | **done** |
| Region-pinned `baseUrl` object (§5) | `forge/manifest.yml` | **switchover only** |
| Leeway 30 s → 5 s (§1.3) | `service/app.py` | **deferred** until a real token is measured |

Everything but the last two has landed and is pinned by `tests/test_service.py`. The `baseUrl` cannot land early: the suite fails a real URL with the offline refusals still in place, and fails the reverse, so it moves exactly once (§13 step 6). `forge/manifest.yml` carries a locally registered app id that must never reach `HEAD` — **stage it by hand and check the diff**, because the file now has changes worth committing sitting beside a line that must not be.

**None of it is validated by `forge lint`,** which needs a CLI and an account this repository does not have. `make forge-lint` and a deploy to `development` are the confirmation, and the line most worth watching is the removed `permissions.external.fetch`: Atlassian's own example manifest for `invokeRemote` carries no such permission, but that is documentation rather than a lint run. It fails loudly at deploy if wrong, which is the acceptable direction.

---

## 4. Cost

### 4.1 The sizing model, and what it assumes

Every figure below rests on these. Change one and the arithmetic changes.

| | |
|---|---|
| Instance | **1 vCPU, 512 MiB**, concurrency **1** |
| Mean billable time per request | **0.5 s** |
| Response size | **32 KB** (`service/README.md`, both dataset sizes) |
| Regions | `us-central1` and `europe-west3` (see §5 on why Frankfurt) |
| Rates dated | **2026-08-25** |

Concurrency 1 is the pessimistic choice and is deliberate: the calculation is CPU-bound single-threaded CPython, so a second concurrent request on one vCPU does not run for free, and modelling it as if it did would understate cost. It also makes billable vCPU-seconds equal request duration, which keeps the arithmetic checkable.

0.5 s is above every individual measurement and below the slow route. The handoff measured `forecast.build` at 110 ms (233 issues) and 178 ms (92 issues); `service/README.md` measures the whole request at 0.25 s and 0.74 s for 242- and 5,538-issue organisations, and `intake.sequence` at 3.07 s. 0.5 s is a mix weighted toward forecasts with an allowance for container overhead. **512 MiB is 36× the measured 14 MB peak RSS** — it is the smallest tier that pairs with 1 vCPU, not a sizing judgement.

Volumes, both regions combined:

| Tier | Tenants | Calls/month |
|---|---|---|
| **Pilot** | 1–5 | 5,000 |
| **Early** | ~25 | 50,000 |
| **Marketplace** | 250+ | 500,000 |

### 4.2 Cloud Run, costed

Rates read from [cloud.google.com/run/pricing](https://cloud.google.com/run/pricing) on **2026-08-25**, services with request-based billing, `us-central1`:

| | |
|---|---|
| CPU, active | $0.000024 per vCPU-second |
| Memory, active | $0.0000025 per GiB-second |
| Requests | $0.40 per million |
| CPU, idle (minimum instances only) | $0.0000025 per vCPU-second |
| Free tier | 180,000 vCPU-s · 360,000 GiB-s · 2M requests per month |

Two caveats on those figures, both of which could move a number and neither of which changes a conclusion. The free tier is **per billing account, aggregated across projects** — so running EU and US does *not* double it; the figures below already treat it as one shared allowance. And the region selector on that page renders client-side, so what was read is the `us-central1` table; `europe-west3` appears in the same rate table's region list, but **confirm the EU rates in the console before the first EU deploy** rather than taking parity on trust.

Per request: 0.5 vCPU-s, 0.25 GiB-s.

| | Pilot (5k) | Early (50k) | Marketplace (500k) |
|---|---|---|---|
| vCPU-seconds | 2,500 | 25,000 | 250,000 |
| — chargeable | 0 | 0 | 70,000 |
| **CPU cost** | $0.00 | $0.00 | **$1.68** |
| GiB-seconds | 1,250 | 12,500 | 125,000 |
| **Memory cost** | $0.00 | $0.00 | $0.00 |
| **Request cost** | $0.00 | $0.00 | $0.00 |
| Egress @ 32 KB | 0.16 GB | 1.6 GB | 16 GB |
| **Egress cost** (~$0.12/GB) | ~$0.02 | ~$0.19 | **~$1.92** |
| Artifact Registry (~200 MB × few tags × 2 regions) | ~$0.10 | ~$0.10 | ~$0.10 |
| **Total, both regions** | **~$0.15** | **~$0.30** | **~$3.70** |

Two things worth reading off that table rather than past it.

**Egress overtakes compute.** At the Marketplace tier the data leaving the service costs more than the arithmetic that produced it. It is still four dollars, so it changes nothing — but it means the one thing that would actually move this bill is a response getting larger, not a forecast getting slower. The 32 KB response is flat across a 242-issue and a 5,538-issue organisation, which is why this stays boring.

**Cold-start insurance is the only expensive option on the menu.** Setting `min-instances=1` to eliminate cold starts costs, per region: 2,628,000 idle vCPU-seconds × $0.0000025 = **$6.57**, plus 0.5 GiB × 2,628,000 × $0.0000025 = **$3.29**, so **≈ $9.86/month per region, $19.72 for two** — five times the entire Marketplace-tier bill, to serve traffic that is already being served. Do not take it at launch. §7 has the latency budget that would justify revisiting it.

### 4.3 The runners-up

Costed on the same workload, same date, and rejected for stated reasons rather than on price.

**AWS Lambda (container image) + Function URL — the cheapest, and second overall.**
$0.20 per million requests and $0.0000166667 per GB-second on x86, after a free tier of 1M requests and 400,000 GB-seconds per month that does not expire. At 512 MB and 0.5 s that is 0.25 GB-s per request, so the Marketplace tier's 500,000 calls draw 125,000 GB-s and **cost nothing at all**; it stays free to roughly 1.6M calls a month. *Not chosen* because `service/app.py` is a WSGI application and Lambda needs an adapter in front of it — Mangum or the AWS Lambda Web Adapter — and this repository's standing rule is that nothing sits between the tools and a reader doing work. An adapter does not compute a figure, and it is still a component that would have to be proved not to, in a product whose entire pitch is that every number is traceable to one implementation. Container-image cold starts are also the worst of the set, against the latency budget in §7. It is a close second and the right fallback if Google is ruled out.

**Fly.io — the lowest floor.**
A `shared-cpu-1x` machine with 256 MB costs about **$1.94/month** while running, and a stopped machine is billed only for its root filesystem at **$0.15/GB/month** — so an auto-stopped ~200 MB image costs around **$0.03/month per region**. Multi-region is a `fly.toml` line rather than a second deployment. *Not chosen*, and not on technical merit: for an app that will go through Atlassian Marketplace review and be installed by administrators who read a security page, the hosting vendor's own compliance documentation becomes part of the sale. GCP, AWS and Azure clear that conversation without having it. Fly is a good product and this is a procurement reason, which is the honest thing to call it.

**Azure Container Apps — a coin flip with the winner.**
Consumption plan, genuine scale-to-zero by default, and a free grant of 180,000 vCPU-seconds, 360,000 GiB-seconds and 2M requests per subscription per month — the same shape and very nearly the same numbers as Cloud Run, at roughly $0.000024/vCPU-s and $0.000003/GiB-s in US East. *Not chosen* because it is indistinguishable from Cloud Run on this workload and there is no tiebreaker in its favour; picking it would be picking at random. Note that its rates here are from a secondary source dated around June 2026 and were not read off Microsoft's own table — if it ever becomes the front-runner, re-price it properly.

**AWS App Runner — rejected on its floor.**
$0.064 per vCPU-hour active and **$0.007 per GB-hour provisioned**, and the provisioned charge is the problem: the default is one provisioned container instance kept warm, and it bills whether or not anything calls it. The smallest configuration, 0.25 vCPU / 0.5 GB, floors at 0.5 × $0.007 × 730 = **$2.56/month per region**, $5.11 for two, serving zero requests; AWS's own worked example uses 1 vCPU / 2 GB, which floors at **$10.22/month per region**. Pausing the service to avoid it is a manual action, which is not a scale-to-zero story. This is the provider the plan exists to rule out: it costs more doing nothing than Cloud Run costs at 500,000 calls.

**AWS Fargate — rejected structurally, and deliberately not priced.**
A Fargate task bills for its entire lifetime, has no scale-to-zero, and needs a load balancer in front of it for public HTTPS, which bills hourly on its own. For a service that is busy for minutes a day that means paying for 730 hours a month twice over. Its rate tables render client-side and could not be read on 2026-08-25, and this repository's own rule is that undated prices read as current forever — so **no figure is quoted**, because the structure disqualifies it without one. It is named in `service/README.md` as a candidate; this is the plan retiring it.

---

## 5. Data residency: Forge does the routing, and that is the finding

Day one, EU and US, per the answer given.

The good news is larger than expected. Atlassian's [realm pinning for remotes](https://developer.atlassian.com/platform/forge/remote/remote-realm-pinning/) means **this is a manifest change, not a routing system**:

```yaml
remotes:
  - key: calculator
    baseUrl:
      default: "https://calculator-…-uc.a.run.app"
      US: "https://calculator-…-uc.a.run.app"
      EU: "https://calculator-…-ew.a.run.app"
    operations:
      - compute
```

Forge selects the region-specific URL **at install time**, from the customer's own Atlassian residency pinning. A tenant pinned to the EU gets the EU service; an unpinned tenant gets `default`. There is no tenant→region table to maintain, no routing logic in the app, and no possibility of the app getting it wrong — which is the strongest possible answer to "how do you keep a customer's data in their region", because the answer is that you never make the decision.

Three details that matter:

**`operations: [compute]` is doing two jobs.** It is what `invokeRemote` requires (§1.1), and it is also the declaration that this remote processes data without storing it. Atlassian's default, when `operations` is absent, is to assume the app **is** storing end-user data on the remote — which is the worst reading of a service that stores nothing, and it is the reading the manifest currently invites by omitting the key. Declaring `compute` states the true thing and is what keeps the app eligible for `PINNED` status.

**Converting `baseUrl` from a string to an object is a major version change.** So are adding a region and altering a URL. Each needs `--approve MAJOR_VERSION_RULE` and a reinstall, per `docs/forge-deployment.md` §1. This is an argument for choosing the final hostnames **once**: see §9 on why the plan launches on `*.run.app` and what that commits.

**EU means Frankfurt or Dublin.** Atlassian's EU realm is "Europe (Frankfurt) and Europe (Dublin)". `europe-west1` is Belgium, which is in the EU but is neither of those. Nothing in Atlassian's documentation requires the remote to sit in the same city as the Atlassian data — the requirement is regional — but if a customer's security review asks the question in those words, `europe-west3` (Frankfurt) is the answer that needs no explanation. **Recommend `europe-west3`** on that basis alone; the rate difference is immaterial at these volumes and should be confirmed in the console either way.

Cost of the second region: the compute is inside a shared free tier at Pilot and Early, and roughly doubles nothing at Marketplace because the free tier is drawn once. The real second-region cost is a second Artifact Registry copy and a second thing to deploy, monitor and rebuild — operational, not financial.

---

## 6. Public reachability, and what an IP allow-list is worth

Forge calls the remote from Atlassian's own infrastructure, so the endpoint is on the public internet with public HTTPS. That is not a choice and any plan that assumes a private VPC is wrong.

**Atlassian does publish egress ranges** — the *Outgoing connections* section of [IP addresses and domains for Atlassian cloud apps](https://support.atlassian.com/organization-administration/docs/ip-addresses-and-domains-for-atlassian-cloud-products/), which Forge Remote's own documentation points at. So the honest answer to "is there something worth allow-listing" is *yes, it exists*, followed immediately by *no, it is not worth it*, for reasons Atlassian states themselves:

- They explicitly **recommend against allow-listing region-specific ranges**, because latency-based routing means a customer's traffic can arrive from ranges tagged `global` that were not there last month. The supported use is to allow-list *all* networks for an app and direction.
- Those ranges carry every Atlassian customer's outbound traffic — webhooks, application links, integrations. An allow-list built from them admits all of Atlassian, not this app.
- They change, which makes the control a thing that silently starts rejecting real traffic on a schedule nobody owns.

So: **no IP allow-listing.** The access control is the invocation token, which proves the request came from Atlassian *and* was minted for this specific app — which is strictly more than an IP range can prove. Cloud Run's ingress stays `all`, its IAM invoker stays public, and `_verify_forge_token()` is the gate. That is the design `docs/forge-deployment.md` §2 already describes; this section exists to record that the alternative was checked rather than skipped.

An unauthenticated `/healthz` remains public. It returns `{"ok": true, "version": …}` and touches no data.

---

## 7. The latency budget, which is tighter than it looks

Worth writing down because it is the one place a hosting choice could break the product rather than cost money.

| | |
|---|---|
| Forge remote timeout, UI modules | **25 s** |
| Forge remote timeout, events and scheduled triggers | **5 s** |
| Retries, UI modules | **none** |
| Retries, events and triggers | 4 |
| FIT lifetime (documented example) | **25 s** |
| Slowest measured call, `intake.sequence` | **3.07 s** |

This app invokes from a backend function behind a UI module, so the budget is 25 s and there are no retries. Against that, a 3.07 s calculation plus a cold start plus a first-request JWKS fetch is comfortable — but note that the **token's life and the timeout are the same 25 seconds**, so a cold start does not merely delay the answer, it spends the token's remaining validity. A platform whose cold start ran to tens of seconds would produce an expired-token rejection that looks exactly like a misconfigured verifier. Cloud Run on a ~200 MB image starting a stdlib HTTP server is nowhere near that, which is why this is a budget and not a risk.

Two consequences for the runbook:

- **The first request after a scale-to-zero also pays for the JWKS fetch**, uncached, before it can verify anything. Two serial cold costs on one request. The cache TTL is 600 s (`FORGE_JWKS_TTL_SECONDS`), so this recurs whenever an instance is new, not once per deployment.
- **`intake.sequence` must not be wired to a scheduled trigger.** 3.07 s against a 5 s timeout with four retries is a route that will fail intermittently and re-run an expensive calculation four times when it does. `service/README.md` already flags this; it belongs here as a hosting constraint because the 5 s figure is a platform limit, not a service one.

### `/healthz` is unreachable on Cloud Run, and the service is fine

Found on the first deploy, where it presented as a completely dead service. It is not.

**Google's front end swallows the exact literal path `/healthz`.** A request to `https://…run.app/healthz` returns Google's own branded 404 page and never reaches the container — no access-log line, nothing. Every neighbouring path goes straight through to the service and gets *its* answer:

| Path | Answer |
|---|---|
| `/healthz` | Google's HTML 404 — never reaches the container |
| `/healthzz` | `{"ok": false, "error": "no such route: /healthzz"}` |
| `/healthz/` | `{"ok": false, "error": "no such route: /healthz/"}` |
| `/HEALTHZ` | `{"ok": false, "error": "no such route: /HEALTHZ"}` |
| `/health` | `{"ok": false, "error": "no such route: /health"}` |
| `/v1/meta` | `{"ok": false, "error": "unauthorised"}` — 401, the service working correctly |

**The product is unaffected.** Forge calls `/v1/facts`, `/v1/forecast`, `/v1/ask` and `/v1/sequence`, and none of them is intercepted. The container's own `HEALTHCHECK` is unaffected too, because it calls `127.0.0.1` from inside the container, where there is no front end in the path — and Cloud Run ignores a Docker `HEALTHCHECK` regardless, using its own TCP startup probe on `:8080`, which has succeeded on every revision.

What it does change is what a post-deploy probe can use, and this is the part worth keeping: **the deploy workflow probes `/v1/meta` and requires a `401`.** That is a better check than a health endpoint returning `200`, and not merely an available one — it proves the URL routes, the container is up and answering, *and* the authentication is switched on. An open health endpoint proves the first two and says nothing about the failure this whole service is built to avoid, which is a calculator that came up unauthenticated and looked perfectly healthy.

The wider lesson is the one this repository keeps relearning: the failure was silent and it pointed at the wrong thing. The deploy succeeded, the revision was `Ready`, `allUsers` had `run.invoker`, ingress was `all`, DNS resolved, and the startup probe passed — every signal green, and one `curl` saying the service was dead. What settled it was reading the container's own stderr and finding `GET / -> 404` in the service's own log format: the request had arrived, so routing was never the problem.

### The cold start, measured

The budget above was written from documentation. One observation against the deployed service, taken 2026-08-25 on a revision created seconds earlier, so the instance was genuinely cold:

| | Cold | Warm |
|---|---|---|
| us-central1 | **1.15 s** | 0.57 s |
| europe-west3 | **0.39 s** | 0.31 s |

Total wall time for a full `/v1/forecast` over TLS from a laptop, 92 issues, including the calculation itself. So the cold-start overhead is roughly half a second on top of the work, against a 25-second token life and a 25-second remote timeout. Comfortable — and the reason `min-instances=0` stays: the thing that would justify paying $9.86 a month per region to avoid cold starts is not happening.

Two honest limits on that number. It is one observation each, not a distribution, and it was taken from a machine on a domestic connection rather than from Atlassian's infrastructure, so the network component is not the one Forge will see. What it does rule out is the failure that mattered — a platform slow enough to start that the invocation token expires before the answer is produced. Nothing here is within an order of magnitude of that.

If p99 latency ever becomes a complaint, the fix is `min-instances=1` at $9.86/month/region (§4.2) — and it is worth knowing that the price of that fix is five times the entire bill before reaching for it.

---

## 8. Secrets: there are none, and that is the point

In `forge-token` mode the service holds no credential. What it needs is four values, none of which is secret:

| | Value | What it is |
|---|---|---|
| `FORGE_JWKS_URL` | `https://forge.cdn.prod.atlassian-dev.net/.well-known/jwks.json` | a public key-set URL |
| `FORGE_ISSUER` | `forge/invocation-token` | a fixed public string |
| `FORGE_AUDIENCE` | `ari:cloud:ecosystem::app/<app-uuid>` | this app's own public id |
| `FORGE_TENANT_CLAIM` | `app.installationId` | a claim name |

All four go in as **plain Cloud Run environment variables**, set on the service at deploy time from the CI workflow. No Secret Manager, no secret rotation, no secret in a deploy log, nothing to leak. `SERVICE_AUTH=forge-token` alongside them.

One secret does exist, and it is temporary. `service/provision-gcp.sh` mints `calculator-shared-secret` in Secret Manager — generated by `openssl`, piped straight in, never printed — so that step 3 of §13 can prove hosting works before Forge is involved. Only the runtime service account can read it, and only that one secret. It is deleted at step 5, and after that `SERVICE_SHARED_SECRET` is not set in production. The startup guard's own message names the mode it is missing configuration for, so a deploy that sets `SERVICE_AUTH=forge-token` and forgets a value fails to start with a sentence naming the value — which is the behaviour to want and is already tested.

`FORGE_AUDIENCE` is the exception worth handling carefully: it is not a secret, but it **is** the per-developer app id that `docs/forge-deployment.md` §1 says must never be committed. It reaches the service the same way it reaches the manifest — from wherever the team keeps the registered id — and it is set in the deploy workflow from a GitHub Actions **variable**, not a hardcoded value. Not because it is sensitive, but because a committed app id is the failure the suite already guards `HEAD` against, and a second copy in a workflow file is a second place for it to be committed from.

**Isolated Cloud is out of scope and should be stated.** Atlassian's FIT carries an `icLabel` claim for Isolated Cloud tenants, whose JWKS lives at a different, label-derived URL. A single `FORGE_JWKS_URL` serves commercial cloud only. That is correct for launch and it is a limit, not an oversight: if an Isolated Cloud customer ever appears, the verifier needs the label-templated lookup **and** the regex validation Atlassian requires (`^[a-z0-9_-]{1,50}$`, checked before the label is interpolated into a URL) — an unvalidated label there is a URL-injection that makes this service fetch keys from an attacker.

---

## 9. Hostnames, and the one thing to decide before the first install

Cloud Run gives every service a `*.run.app` URL with managed TLS, free. A custom domain through a Cloud Load Balancer costs roughly $18–25/month per region — five to six times the Marketplace-tier bill, per region, for a nicer hostname.

**Launch on the `*.run.app` URLs.** But note what that commits: changing a `baseUrl`, or converting its format, is a major version change requiring `--approve MAJOR_VERSION_RULE` and a reinstall on every tenant (§5). Moving to a custom domain later is therefore not a hosting change, it is a forced reinstall for every customer.

So the decision to take now is not which hostname, it is **whether a custom domain is ever wanted**. If the answer is yes, do it before the first external install, when the reinstall costs nothing. If the answer is no, `*.run.app` is a fine permanent address for a backend nobody types. The plan's position: **`*.run.app`, permanently**, because this endpoint is never seen by a human — the customer sees a Jira panel — and a forced reinstall is a real cost paid for a cosmetic one. Revisit only if a security review objects to the hostname, which would be an odd objection to a Google-operated domain.

---

## 10. Rebuild cadence — decided

`docs/forge-deployment.md` §3 leaves this open and calls it "a decision rather than a task". Taking it:

**A scheduled weekly rebuild, Mondays 03:00 UTC, that also deploys.** Implemented in [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml).

The reasoning is already in the runbook and holds: the base is `python:3.12-slim`, the service installs exactly one wheel, so essentially the entire attack surface is the base image — and a base image goes stale on its own schedule, not this repository's. A service that is deployed once and never rebuilt is running last quarter's OpenSSL by default.

The part the runbook does not say, and the reason the cadence includes the deploy: **a weekly rebuild that never ships is theatre.** It produces a green tick and a fresh image in a registry while the running service ages exactly as fast as it would have without it. So the schedule is: rebuild from the current base → run the existing `container` job smoke tests → run the scan (§11) → on green, deploy to both regions. On red, it stops and opens an issue; it does not deploy a stale image and it does not go quiet.

Weekly rather than daily because the service has no dependencies of its own to churn, and daily rebuilds of an unchanged Dockerfile produce noise that gets muted, which is worse than a slower cadence somebody still reads. Image tags carry the build date so a running revision can be aged at a glance.

The deploy is safe to automate precisely because it is the same image built from the same Dockerfile with no source change — and because the smoke tests that gate it already assert the things that would actually break: refuses to start with no secret, runs as uid 10001, refuses an unauthenticated request, returns a real forecast for an authenticated one, refuses issue text, and does not log issue text.

---

## 11. Scanning policy — decided

Also left open, and for a stated reason: "adding a scanner that fails the build on somebody else's CVE feed needs a policy decision about what blocks a merge." Taking it:

**Trivy in CI on every push and on the weekly rebuild. `HIGH` and `CRITICAL` with a fix available block. `HIGH` and `CRITICAL` with no fix available are reported and do not block. Everything below `HIGH` is reported and does not block.** Implemented in [`service/scan.sh`](../service/scan.sh), called by both workflows.

```bash
trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 delivery-value-calculator
trivy image --severity HIGH,CRITICAL --exit-code 0 delivery-value-calculator   # the full picture, printed
```

The line is **actionability, not severity**. A `CRITICAL` with a patched version in the base image is something a merge can fix, and blocking is what makes it get fixed. A `CRITICAL` with no upstream fix is not something a merge can fix, and blocking on it converts the gate into an obstacle people learn to bypass — at which point the gate stops catching the fixable ones too. The failure mode of a too-strict scanner is not a slower pipeline, it is a disabled scanner.

**Both commands run, and the second one is the reason this is a policy rather than a flag.** `--ignore-unfixed` on its own is a silent cap, which is the thing this repository has shipped three times and writes rules about. The unfixed findings are printed in full on every run, so the build says what it decided not to block on. A scan that quietly drops half its findings reads as a clean scan.

Trivy over `docker scout` because it runs in a container with no account, no login and no vendor-side rate limit, which matters for a weekly scheduled job that must not fail for reasons unrelated to the image.

**One thing this policy does not claim:** it scans the image, and the image is a base plus `PyJWT[crypto]`. It says nothing about `agent/tools/`, which is stdlib-only Python this repository wrote, and nothing about the Forge app's `@forge/*` dependencies, which CI audits separately. Naming the boundary here so a green scan is not read as a claim about the whole product.

---

## 12. Observability

The constraint to preserve: the access log records method, path, status, issue **count**, duration, and — in `forge-token` mode — the tenant. Never content. `service/README.md` puts it plainly: an access log holding issue keys is a copy of the customer's backlog in a log aggregator.

Cloud Run does not undo this on its own. Its automatic request logs carry method, URL path, status, latency, user agent and caller IP — **not request bodies**. The paths here are `/v1/forecast` and friends, which carry no data. So the platform's default logging is compatible with the constraint and needs no suppression.

Decisions:

- **`_Default` bucket, 30-day retention, no log sink to anywhere else.** Free at this volume — 500,000 requests at roughly 150 bytes a line is about 75 MB against a 50 GiB monthly allowance. No third-party aggregator: every one of them is another copy of the tenant identifiers, in another company, under another DPA, for a service that produces about two log lines a second at peak.
- **The tenant in the log is an installation ARI**, a pseudonymous identifier issued by Atlassian. It is not issue text, not an issue key, and not a person. It is the entire point of the token mode and it stays.
- **Tracebacks go to the operator and never into a response**, which is existing behaviour and must survive any structured-logging change, because a traceback carries field values.
- **Alert on one thing to start: the 5xx rate.** A `401` rate is not an alert — it is what a misconfigured `FORGE_AUDIENCE` looks like, and also what a probe looks like, and the switchover will generate some of both. Watch it during switchover, alert on 5xx.
- **`x-b3-traceid` is on every Forge request.** Logging it costs nothing and is the only way to correlate a Forge developer-console entry with a service log line. Not currently logged; worth adding when the log line is next touched, and explicitly safe — it is a trace id, not data.

---

## 13. The switchover, in order

Nothing here can be half-done: `tests/test_service.py` fails both a real `baseUrl` with the offline refusals still in place and the reverse. That is a feature and it dictates the sequence.

1. **Provision Google Cloud: `bash service/provision-gcp.sh`.** Eight stages, and every one of them is something only a person with the billing account can do — project, APIs, a registry per region, two service accounts, the GitHub federation, and the one temporary secret. It ends by writing four repository variables with `gh`. Re-running it is free; every create is guarded by its own describe.
2. **Push to `main`.** `.github/workflows/deploy.yml` builds the image, runs `service/smoke.sh`, runs `service/scan.sh`, and only then pushes to both regional registries and deploys. The scan policy (§11) and the weekly rebuild (§10) are in that workflow, so the first deployed image is one the policy has already passed — which is why this step is not "deploy, then add the gates later".
3. **Confirm hosting on its own.** Not `/healthz` — see §7. Post a real dataset to `/v1/forecast` with the shared secret and check a figure comes back. Nothing about Forge is involved yet, so a failure here is hosting and only hosting.

**Steps 1 to 3 are done.** Project `calculator-506614`, deployed 2026-08-25:

| Region | URL |
|---|---|
| us-central1 | `https://calculator-jtfw7qf4ea-uc.a.run.app` |
| europe-west3 | `https://calculator-jtfw7qf4ea-ey.a.run.app` |

Both refuse an unauthenticated caller with `401`, refuse a payload carrying `summary` with `400` and the sentence about it not being stored, and return a real forecast in 0.31s (EU) and 0.57s (US) warm. Cold numbers are in §7.

The shared secret is at version **2**; version 1 is disabled rather than destroyed. Version 1 is the one that carried the trailing newline described in the changelog for 1.20.2 — the same secret material, one byte longer. Both regions were cold-started with version 1 disabled to prove nothing still resolves it.

The check worth having made is stronger than "a figure came back". The forecast returned by **each region and by `forecast.build()` called directly are byte-identical**, all 5,825 of them. That is the seeded Monte Carlo holding across three machines in two continents, and it is the standing constraint — the service does no arithmetic — demonstrated rather than asserted. If a wrapper had rounded one percentile, this is where it would have shown.
4. **Run `make forge-lint` and deploy to `development`.** The code changes in §3's table are already in — `invokeRemote`, `operations: [compute]`, the nested tenant claim — but nothing has linted them, and the removed `fetch` permission is the line to watch. The calculator tiles still refuse here, correctly, because `baseUrl` is still `.invalid`.
5. **Confirm `FORGE_AUDIENCE` against the registered app id**, switch both services to `SERVICE_AUTH=forge-token`, and confirm they start. **Done, 2026-08-25.** Both regions run `forge-token` with all four values and no secret mounted at all. Three of the runbook's four "done when" conditions are now met — see below; only a real Forge call remains.

**What the live verifier was shown to do**, on 2026-08-25, against Atlassian's real key set rather than a signer the suite controls. Eight hand-made tokens, every one refused with `401`:

| Token | |
|---|---|
| No `Authorization` header | refused |
| `Bearer garbage` | refused |
| `alg: none`, correct `aud` and `iss` | refused |
| HMAC-forged, carrying a **real Atlassian `kid`** | refused |
| RS256 signed by a key Atlassian never issued, unknown `kid` | refused |
| RS256 signed by that key but carrying a **real Atlassian `kid`** | refused |
| Correct shape, expired | refused |
| Correct shape, wrong `aud` | refused |

The sixth is the one worth having. A token whose `kid` genuinely appears in Atlassian's published key set can only be refused by fetching that key and finding the signature does not verify against it — so it proves the JWKS URL is right, the fetch works from inside the container, and the signature check is real rather than a check of shape.

**The response times prove the cache and the algorithm pin as well**, which no status code could. Six refusals took **0 ms**: the algorithm is pinned before a key is ever looked up, so `alg: none` and the HMAC forgery are thrown out without Atlassian being contacted at all — which is what stops an attacker using this service to hammer Atlassian's endpoint. One took **164 ms**, the live JWKS fetch. One took **7 ms**, the cached key. That is exactly the behaviour `docs/forge-deployment.md` §2 specifies, observed in production rather than asserted in a test.

No traceback appeared for any of them: the verifier refused rather than raised, which is the 1.18.1 contract holding under real traffic.
6. **The atomic commit**: region-pinned `baseUrl`, the offline refusals removed from the forecast and ask-sequencing resolvers, the corrected manifest comment. Deploy with `--approve MAJOR_VERSION_RULE`, then **uninstall and install** — not upgrade — because the `baseUrl` format change is a major version change and Jira does not widen an existing installation on its own.
7. **Watch the first real token through.** This is the moment §2 of the runbook has been waiting for: `SERVICE_AUTH=forge-token` accepting a token Atlassian minted, with the installation ARI in the log line. Capture the token's real `exp - iat` here.
8. **Then, and only then, tighten the leeway** (§1.3) using the lifetime measured in step 7.

Step 7 is where the claim changes from *the mechanics are proved* to *it works*, and they are different claims. Everything before it is preparation.

---

## 14. Open questions

Not assumed, and each one changes something concrete.

1. **Is the volume model right?** §4.1 assumes roughly two calculator calls per dashboard open and 20 opens per tenant per working day. If a tenant's dashboard refreshes on a timer, or if the panel calls on every render, the multiplier changes and the Marketplace tier moves — though it would take about a 15× increase before the bill reaches $50/month, so this is a question about sizing, not about affordability.
2. **Is there a budget ceiling worth designing against?** On these numbers the answer is likely "no, spend the four dollars", but `min-instances` (§4.2) and a custom domain (§9) are both ten-to-twenty-times decisions and are the only two places where a ceiling would actually bind.
3. **Does a Marketplace listing require a named vendor-hosted region beyond EU and US?** Atlassian supports realm pinning for Australia, Canada, Germany, India, Japan, Singapore, South Korea, Switzerland and the UK. Each additional one is another deployment, another rebuild target — and adding a region later is a major version change and a reinstall. If any of these is foreseeable, adding it at step 6 of §13 is nearly free and adding it afterwards is not.
4. **Who owns the Google Cloud account, and is it a new organisation or a personal project?** This is a Marketplace product; a personal-account project is a single point of failure with no second admin, and the fix costs nothing at creation and is painful later.
5. **Does §1.3 stay open until a real token is measured?** The recommendation is yes. Confirm that is acceptable — it means launching with a 30-second leeway on a 25-second token for as long as step 7 takes.

---

## Appendix A — values confirmed, and the date

Read from Atlassian's own documentation on **2026-08-25**. [Forge Remote essentials](https://developer.atlassian.com/platform/forge/remote/essentials/) was last updated 2026-07-17; [Calling a remote backend from a Forge function](https://developer.atlassian.com/platform/forge/remote/calling-from-function/) and the [manifest remotes reference](https://developer.atlassian.com/platform/forge/manifest-reference/remotes/) 2026-06-19; [realm pinning](https://developer.atlassian.com/platform/forge/remote/remote-realm-pinning/) 2025-08-28.

| Variable | Value | Confirmed |
|---|---|---|
| `FORGE_JWKS_URL` | `https://forge.cdn.prod.atlassian-dev.net/.well-known/jwks.json` | 2026-08-25 |
| `FORGE_ISSUER` | `forge/invocation-token` | 2026-08-25 |
| `FORGE_AUDIENCE` | the app id ARI — `ari:cloud:ecosystem::app/<uuid>`, matching `app.id` in the manifest, **not** the bare UUID | 2026-08-25 |
| `FORGE_TENANT_CLAIM` | `app.installationId` — **nested**, see §1.2 | 2026-08-25 |

Also confirmed:

- **The FIT arrives as `Authorization: Bearer <jwt>`**, which is the header `_verify_forge_token()` already reads.
- **The signing algorithm** is asymmetric and Atlassian's own samples verify against the JWKS without pinning an algorithm; `RS256` is what `FORGE_ALGORITHMS` pins. Confirm the `alg` on a real token at step 7 of §13 — if Atlassian signs with something else, the pin refuses everything, safely and confusingly.
- **App-system and app-user tokens are separate headers** (`x-forge-oauth-system`, `x-forge-oauth-user`), sent only if the manifest opts in via `remotes.auth`, and each requires its own scope. **Do not enable either.** They exist so a remote can call Jira on the app's or the user's behalf; this service reaches no tracker and must not start holding an Atlassian OAuth token. This answers the runbook's open question about app-system versus user tokens: it is not a property of the FIT at all, it is two additional headers this app should decline.
- **The user token is not delivered to scheduled triggers**; the FIT is. Since neither optional token is enabled, this app's behaviour does not differ between a trigger and a resolver call.
- **The FIT lifetime in Atlassian's documented example is 25 seconds** (`iat` 1700175149, `exp` 1700175174). An example, not a guarantee — see §1.3.
- **Atlassian publishes egress IP ranges** and recommends against using them the way an allow-list would need to. §6.

## Appendix B — prices, dated

| Provider | Figure | Region | Read |
|---|---|---|---|
| Cloud Run | $0.000024/vCPU-s active, $0.0000025/GiB-s, $0.40/M requests, $0.0000025/vCPU-s idle; free 180k vCPU-s · 360k GiB-s · 2M req | us-central1 | 2026-08-25, vendor |
| AWS Lambda | $0.20/M requests, $0.0000166667/GB-s x86; free 1M req · 400k GB-s | us-east | 2026-08-25, secondary |
| AWS App Runner | $0.064/vCPU-hour active, $0.007/GB-hour provisioned | us-east-1/2, us-west-2, eu-west-1 | 2026-08-25, vendor |
| AWS Fargate | not quoted — rate table renders client-side, see §4.3 | — | — |
| Fly.io | ~$1.94/month `shared-cpu-1x` 256 MB running; $0.15/GB/month stopped rootfs | — | 2026-08-25, secondary |
| Azure Container Apps | ~$0.000024/vCPU-s, ~$0.000003/GiB-s; free 180k vCPU-s · 360k GiB-s · 2M req | US East | 2026-08-25, secondary, rates dated ~June 2026 |

"Secondary" means the vendor's own table renders client-side and could not be read directly. Those figures are directional and each is flagged where it is used. Re-price any provider before choosing it on the strength of a number in this table.
