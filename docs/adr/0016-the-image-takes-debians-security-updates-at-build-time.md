# 0016 — The image takes Debian's security updates at build time

[ADR 0008](0008-forge-calls-a-hosted-calculator.md) put a calculator on Cloud
Run, and §11 of `docs/hosting-the-calculator.md` gave it a scanning policy:
**HIGH and CRITICAL findings with a fix available block; HIGH and CRITICAL with
no fix available are reported and do not.** The line is actionability rather
than severity, because a gate that blocks on things no merge can fix is a gate
people learn to route around.

That policy is not what this record changes. It is what this record is a
consequence of.

## What happened

On 2026-08-28 every push failed the gate, and the deploy workflow stopped
before it reached Google — so roadmap item 4a was finished, tested and unable
to reach a tenant, because the calculator could not ship.

The image had **19 HIGH and CRITICAL findings, of which 3 were fixable**, and
all three were one CVE: `CVE-2026-14456` in OpenSSL, present as `openssl`,
`libssl3t64` and `openssl-provider-legacy` at `3.5.6-1~deb13u2`, fixed in
`3.5.7-1~deb13u2`. The other sixteen had no upstream fix and blocked nothing,
exactly as the policy says they should.

It is worth being precise about that, because the failure was described twice —
in a session handoff, and then by an assistant repeating the handoff without
reading `service/scan.sh` — as *"the gate fails on unfixable findings, so it is
a policy question."* It was neither. The gate already runs `--ignore-unfixed`
and had found something real and fixable. A red build that is telling the truth
is the one case where changing the policy is the worst available move.

## Why the obvious fixes were not available

Four were checked against the actual images rather than reasoned about, and the
measurements are the argument.

**Rebuild against a current base — no.** The `python:3.12-slim` published at the
time (`sha256:09f7da3b…`) still shipped `3.5.6-1~deb13u2`. Every rebuild
produced exactly the image CI already had.

**Pin a newer base digest — nothing to pin.** No digest with the fix existed.

**Change the base — worse, or the same.**

| Base | HIGH+CRITICAL | of which fixable |
|---|---|---|
| `python:3.12-slim` (then) | 19 | **3 — the gate fails** |
| `python:3.13-slim` | 21 | 5 — fails |
| `python:3.12-alpine` | 2 | 2 — **fails, on the same CVE** |
| `distroless/python3-debian12` | 46 | 18 — fails |

Alpine is the interesting row. It carries far fewer findings in total, and it
fails the gate anyway, on `CVE-2026-14456` in `libcrypto3`/`libssl3` at
`3.5.7-r0` needing `3.5.8-r0`. **This was never a Debian problem.** The CVE had
landed recently and no base image of any distribution had been rebuilt for it,
so no base swap could have cleared it.

Distroless is the other one worth recording, because the intuition is exactly
backwards. `distroless/python3-debian12` is not a minimal surface here: it
carries a full Python 3.11 standard library pinned to Debian 12, and it scanned
at 46 HIGH/CRITICAL with 18 fixable. Distroless is a good answer to "ship no
shell and no package manager"; it is not, for Python, a good answer to "carry
fewer CVEs".

**Suppress the finding — refused.** Trivy will take a `.trivyignore` entry with
an expiry, and the exposure argument is even quite good: this CVE is unbounded
memory growth in OpenSSL's QUIC *server*, and this service is stateless HTTP
behind Cloud Run and never speaks QUIC. It is still the wrong move. The policy
blocks on fixable findings **so that they get fixed**, and the first time a
fixable finding is waved through with a good reason is the point at which the
gate becomes advisory. A suppression list is where a project keeps the things it
has decided not to do.

## The decision

**The image applies Debian's security updates at build time**, as the first
layer after `FROM`:

```dockerfile
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
```

Measured on the real Dockerfile: **3 fixable findings before, 0 after**;
`service/scan.sh` exits 0; `service/smoke.sh` passes unchanged; the image grows
from 52.6 MB to 56.5 MB.

`upgrade` and never `dist-upgrade` — this takes patched versions of packages
that are already present and must not add or remove one. The apt lists go in the
same layer, or they sit in the image doing nothing.

## What it costs, stated rather than discovered later

**"The base plus one wheel" needs a qualification now.** §11 says the scan
covers a base image and `PyJWT[crypto]`, and that is still true, but the base's
packages are no longer the versions the base image was published with. Anyone
reproducing a scan result needs to know that.

**A build takes whatever Debian has published that day.** This is a smaller
change than it sounds: `FROM python:3.12-slim` is an unpinned tag, so a build
already took whatever Docker Hub had published that day. It adds no new
non-determinism of consequence — but it does mean two builds of one commit can
differ, and if that ever needs to stop being true, the answer is to pin the base
by digest *and* keep this line, not to drop it.

**It does not touch the sixteen.** After this the image still carries sixteen
HIGH and CRITICAL findings with no upstream fix, including a CRITICAL in
`perl-base`. They are printed on every run and block nothing, which is the
policy working. This record does not improve that number and does not claim to.

**It is a mitigation for a lag, not a substitute for a current base.** The
weekly rebuild in §10 is still what keeps the running image fresh. If the
`python` image ever stops being rebuilt at all, this line hides the symptom of a
base that should have been abandoned — so the sixteen unfixable findings, and
their age, stay worth reading rather than scrolling past.

## What this rules out

**Loosening the gate.** Not now and not next time. The gate's value is that it
is not negotiable when it is inconvenient, and it was inconvenient here: it
blocked a finished feature from reaching a tenant for a day. That is the gate
working.

**Reading a red scan as a policy problem.** The first question is always which
findings block and whether they have a fix. Both are one command
(`service/scan.sh`) and the second pass prints exactly that. Two people in a row
described this failure as unfixable findings blocking a deploy without running
it.

**Suppression as the first answer.** If a fixable finding ever genuinely cannot
be fixed — a patched package that breaks the service, say — that is a decision
with a name and a date and an expiry, argued in its own record. It is not a line
quietly added to an ignore file.
