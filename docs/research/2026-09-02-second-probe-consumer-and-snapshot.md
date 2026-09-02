# The second probe: a consumer, a snapshot, and how sequencing really scales

*Measured 2026-09-01 and 2026-09-02 on a throwaway Forge app, `wasm-probe-2`, deployed to its own `development` environment and installed on the dev site. Companion to `2026-09-01-runs-on-atlassian-badge.md` §6, which established that the tools run under Pyodide in a Forge function at all, and to `2026-09-01-forge-async-events.md`, which is what Atlassian's documentation says. This note is what the platform did. Nothing here is inferred from a document; where a document said one thing and the deploy said another, the deploy is recorded.*

## Summary

- **A consumer module is a minor version.** 2.0.0 to 2.1.0 on adding `consumer`, a second `function` and `timeoutSeconds: 300`; 3.1.0 to 3.2.0 on raising it to 900. **Adding a remote is major** — the linter says *"Change due to data residency or egress modification"* and stops for `--approve MAJOR_VERSION_RULE` — and **removing it is minor**, 3.0.0 to 3.1.0. Both settled by deploy on this app, which is the rule `CLAUDE.md` sets.
- **Sequencing is cubic in the ask count, not linear.** Natively: 2 asks 0.17 s, 4 asks 1.1 s, 8 asks 7.0 s, 12 asks 21 s, 16 asks 48 s. Fifty asks did not finish in ten minutes natively and would take hours on Forge. Every earlier figure that priced sequencing per ask, including ADR 0031's, is wrong by this shape.
- **Forge's CPU is ten times native for the plain runtime.** 4 asks 11.2 s, 8 asks 68 s, 12 asks 209 s, 16 asks 479 s, in the consumer under a 900-second budget. Twenty asks would be about 940 s and does not fit.
- **A memory snapshot cuts the cold start from 11 s to 1.3 s, and costs 1.65× on every computation afterwards** — measured A/B in one container. Locally the two runtimes are identical in speed, so this is Forge's runtime, not Pyodide's. The trade suits the synchronous resolver function and not the consumer.
- **A timed-out consumer is retried within about 40 seconds**, not the fifteen-minute ceiling the documentation gives, and again 40 seconds after the next kill. `retryContext` arrives as documented. `getJob().cancel()` stopped it; `getStats()` reported zeros for a job mid-retry and is no use as a status source.
- **The service's validation layer imports under Pyodide unchanged**, and the forecast barely grows with board size: 1.5 s at 480 issues, 2.8 s at 4,800.

## 1. The app

Node v24.18.0, Linux arm64, two CPUs, `memoryMB: 1024`. Pyodide 314.0.6 (Python 3.14.2) with the five runtime files, the five tools, `service/app.py`, two datasets, fifty asks and a 30 MB memory snapshot, all gzip-and-base64 inside a generated 17.0 MB `assets.js` (44.8 MB raw). Unpacked to `/tmp/probe/` on first invocation, 0.4 s. The native reference is Python 3.14.7 on an M3 Pro, same bodies, SHA-256 of `json.dumps(sort_keys=True)`; every hash below matched.

The datasets are the demo intake bundle projected the way the Forge resolver projects — free-text fields dropped, `epicKey` carried — and cloned tenfold for the large board. Stripping the text without carrying `epicKey` made every ask unsizeable and sequencing refused in 0.00 s with *"Sequencing needs at least two sizeable asks; 4 supplied, 4 skipped"*; worth knowing, because it is what a resolver that forgot the key would produce.

Deploys: 2.0.0 webtrigger + `storage:app`; 2.1.0 consumer; 2.2.0, 2.3.0 code; 3.0.0 remote added (approved); 3.1.0 remote removed; 3.2.0 `timeoutSeconds` 300 to 900. The scope was declared from the first deploy so that no later deploy mixed a scope change into a classification.

## 2. Cold start, plain and from a snapshot

| | Plain | Snapshot |
|---|---|---|
| unpack to `/tmp` | 0.41 s | 0.42–0.46 s |
| `loadPyodide()` | 8.5 s | 0.82–0.94 s |
| write sources + `import app` | 2.0 s | — (in the snapshot) |
| **total** | **11.0 s** | **1.26–1.48 s** |
| RSS after | 324 MB | 347 MB |

The snapshot is `pyodide.makeMemorySnapshot()` after `loadPyodide({ _makeSnapshot: true })`, the sources written and `app` imported, on this Mac under Node 26; loaded on Forge under Node 24 with `_loadSnapshot`, figures identical. Both options are marked `@ignore` in Pyodide's type definitions. The consumer function runs in its own container: its first job had no cached runtime while the webtrigger's did, and the push-to-start latency was 0.3 to 3 s.

## 3. Facts and forecast, warm

| Route | 480 issues | 4,800 issues |
|---|---|---|
| `route_facts` | 0.30 s | 2.49 s |
| `route_forecast` | 1.52 s | 2.78 s |

Native: 0.02/0.22 s and 0.12/0.22 s. Cold plus the large forecast on a plain runtime is 13.8 s against the adapter's 15-second clock; from a snapshot it is about 6 s even at the snapshot's 1.65× penalty.

## 4. Sequencing

| Asks | Native | Forge plain | Forge snapshot runtime |
|---|---|---|---|
| 2 | 0.17 s | | |
| 4 | 1.14 s | 11.2–12.1 s | 18.6–18.9 s |
| 6 | 3.07 s | | |
| 8 | 7.0 s | 68.2 s | 117.9 s |
| 12 | 21.4 s | 208.6 s | |
| 16 | 48.3 s | 479.1 s | |
| 50 | > 600 s, abandoned | | |

The twelve and sixteen-ask jobs were pushed together and both started within a second of each other in different containers — the sixteen-ask one paid a fresh 9.1 s plain load — so consumers run concurrently unless `concurrency` is declared. The A/B is honest: the 4-ask plain figure of 11.2 s and the snapshot figure of 18.8 s came from one consumer container, the runtime unloaded and reloaded between them; the 8-ask pair likewise. Locally the same two runs take 3.39 s and 3.36 s. Between 8 and 16 asks native time grows 6.9×, between 6 and 12 it grows 7.0×; the exponent is a little under three.

## 5. Timeout, retry and cancel

Sixteen asks under `timeoutSeconds: 300`, plain runtime. Attempt one started at 22:03:28Z and was killed at 300 s. Retry one started at 22:09:08Z, forty seconds after the kill, carrying `retryContext: { retryCount: 1, retryReason: "FUNCTION_TIME_OUT", retryData: null, retentionWindow: { startTime: 22:03:27.998Z, remainingTimeMs: 86061314 } }`. Retry two started at 22:14:50Z, forty-two seconds after the second kill. The row the consumer writes at the top of each attempt survives the kill, so a poller sees `started` with a fresh timestamp and a rising `retryCount` — and nothing else, for a day, unless the consumer reads the context and stops. `queue.getJob(id).cancel()` at 22:19:21Z during retry two returned nothing and no retry three appeared. `getStats(jobId)` answered `{ success: 0, inProgress: 0, failed: 0 }` while retry two was running.

## 6. Storage

`kvs.set(key, row, { ttl: { value: 1, unit: 'HOURS' } })` and `kvs.get(key)` behaved; the SDK types `ttl` as `{ value, unit: 'SECONDS' | 'MINUTES' | 'HOURS' | 'DAYS' }`.

## What this changes

Three numbers in ADR 0031 are wrong and one decision rests on them: the consumer's budget was set at 300 s for fifty asks on a per-ask estimate. Fifty asks is unreachable on any transport; a 900-second consumer on the plain runtime holds about sixteen, and a stated refusal above a measured count replaces the first-ask timing guard, because the shape is known and a count is deterministic. The snapshot belongs on the resolver function only. The retry guard is more urgent than the record said: the first retry comes in forty seconds.

## Not done, and cleanup

The app is installed on the dev site as installation `f52bde9e-c4c6-4251-9c18-5e77b46d6229`, development environment, version 3.2.0. Removing it is `forge uninstall` followed by deleting the app in the developer console, which the CLI cannot do. No production environment was touched. Nothing in the repository's own `forge/` directory was changed.
