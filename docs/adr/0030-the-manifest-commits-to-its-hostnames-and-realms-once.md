# 0030 — The manifest commits to its hostnames and its realms once, before anybody installs

> **Superseded on 2026-09-03 by [ADR 0031](0031-the-forecast-runs-inside-the-forge-function.md).** The hostnames and realms this record committed to left the manifest with the `remotes` block; there is nothing to pin. The window it describes still matters — a remote added after the first external install is a major version — and that is now the reason there will not be one.

Two entries in `forge/manifest.yml` are free to change today and a forced reinstall for every customer tomorrow. `baseUrl` is one value with one shape; the realms it is keyed by are the other. Changing either is a major version — `forge lint` says so in those words — and the window in which that costs nothing closes at the **first external install**, expected September 2026.

Decided 2026-08-31, with the only installation still `development` on the dev site. Both halves were settled by running something rather than by reasoning about it, which is the rule `CLAUDE.md` sets for exactly this class of question.

## The calculator keeps its `*.run.app` hostnames, permanently

`docs/hosting-the-calculator.md` §9 already argued this and its argument is not the one that decided it. §9 weighs a custom domain as cosmetics — the endpoint is never seen by a human, the customer sees a Jira panel — and concludes that a forced reinstall is a real cost paid for a nicer hostname.

**The better argument for a domain is indirection, and it nearly won.** A custom domain is the only layer between the manifest and the infrastructure: with one, moving provider, moving region or rebuilding the project is a DNS change; without one, every one of those is a major version and a reinstall on every tenant. That mattered because the cloud project is a personal-account project with no organisation and no second admin, and putting it under an organisation is deliberately deferred until nearer a public release — scheduling the one piece of infrastructure work most likely to disturb a hostname for after customers exist.

**It collapsed on a fact.** Google's project migration documentation states that on a move into an organisation, *"Project ID and number: Stays the same. API keys, service names, and hardcoded IDs remain unchanged"*, and *"Data and resources: Stays the same"*. The Cloud Run hostnames derive from the project, so the migration cannot move them. The only thing that ever could is **recreating** the project instead of moving it — and that is now a thing this project declines to do, written down here, rather than a risk worth £30–40 a month to insure against.

**What this costs, stated plainly.** There is no indirection. Leaving Google Cloud, or recreating the project for any reason, is a major version and a forced reinstall for every customer. That is accepted with open eyes, and the mitigation is a rule rather than a purchase: **move the project, never recreate it.**

### What it rules out

**A custom domain via a load balancer**, at roughly $18–25 per region per month — about ten times the entire current bill. The real argument for it is recorded above so that nobody re-proposes it as a cosmetic upgrade and gets refused for the wrong reason; the case that would reopen it is a decision to leave Google Cloud, or a security review that objects to the hostname, which would be an odd objection to a Google-operated domain.

**Cloud Run's direct domain mappings**, the load-balancer-free path that would have made the above nearly free. It does not exist for this deployment: the feature is preview, Google states it is not production-ready, and its supported-region list excludes `europe-west3`, which is where the EU service runs.

## Three realms — `US`, `EU` and `GB` — and the UK gets its own service

Atlassian's realms are not a short list and **the United Kingdom is not inside `EU`**. `EU` is Frankfurt and Dublin; `GB` is London. Germany, Switzerland, Canada, Australia, India, Japan, Singapore and South Korea are each their own realm too. The manifest declared `default`, `US` and `EU`, and the first customer — trialling in September — is a UK company.

**`GB` is the key, confirmed by running the linter and then by a control.** Adding `GB:` to `baseUrl` passes `forge lint`; substituting `ZZ:` fails it with `MANIFEST_INVALID_RULE` and a schema error naming `regionalBaseUrl`. The control is the point: acceptance means nothing unless a bogus key is rejected, and Atlassian's manifest reference documents only `US` and `EU`, so every other key is an inference until something validates it. Adding the realm also printed its own price — *"This deployment triggers a major version upgrade … Change due to data residency or egress modification"*.

**`GB` points at a London service, not at Frankfurt.** Pointing it at the existing `europe-west3` service would have been one line and no new infrastructure, and it would have been a quiet lie: a tenant pinned to the United Kingdom pinned there for a reason, and after Brexit that reason is frequently that Germany is not the United Kingdom. Declaring support for a realm while computing somewhere else would break the strongest sentence this product has for a security review — that the app never decides which region a tenant's numbers are computed in, because Forge decides at install time and there is nothing here to get wrong.

### The thing nobody has written down

**What a tenant pinned to an undeclared realm actually gets is unknown.** `docs/hosting-the-calculator.md` §5 says an *unpinned* tenant falls to `default`; it says nothing about a tenant pinned to a realm the app never declared, and neither does Atlassian's realm-pinning page or its manifest reference. The two candidates are a refused install — a lost sale, loud and survivable — and a silent fall-through to `default`, which for a German or Swiss customer means their numbers are computed in Iowa under a routing decision they never made. One of those is a sales problem and the other falsifies the sentence above.

A question is open with Atlassian on it. **If the answer is the silent one, `DE` and `CH` are added before the window closes**; if it is a refused install, further realms stay sales-led, added when a named customer needs one and priced as the major version they are.

### What it rules out

**Declaring all twelve realms speculatively.** Each is another Cloud Run service to deploy, monitor, rebuild and scan, and the burden lands on one person. Four more of them for customers who do not exist is a standing operational cost bought with a guess.

**Leaving `GB` undeclared and finding out in September.** The first install is the event that makes this expensive; discovering the answer from the first customer's tenant is discovering it one day too late.

## A third region is a change to the deploy workflow, never a hand-deployment

`.github/workflows/deploy.yml` iterates `for region in us-central1 europe-west3` and names both again in its summary table. A London service created by hand would be invisible to it and would **stop receiving new calculator versions on the next push**, while every check stayed green — a UK tenant reading answers from a stale service, which is this repository's worst failure class by its own definition: a plausible wrong number that looks exactly like a correct one.

So the region is added by editing that loop, in the same commit that adds `GB:` to the manifest, pushed and watched before `forge deploy` — the push-first rule from `CLAUDE.md`'s architecture paragraph, which holds at three regions exactly as it does at two. A check that fails when the manifest declares a realm the workflow does not deploy to makes the drift impossible rather than merely documented.
