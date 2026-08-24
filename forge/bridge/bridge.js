/**
 * The Forge half of the dashboard's transport.
 *
 * `src/app.js` is the shipped product: one file, no dependencies, no network
 * call from `file://`. It must never import `@forge/bridge`, and the security
 * suite asserts all three. So the page looks for `window.__DVD_BRIDGE__` and
 * this script — bundled separately, and included only in the split build that
 * Forge serves — puts one there before the page runs.
 *
 * That is the whole seam. The page does not know what Forge is; this file does
 * not know what a sprint is.
 *
 * It must be a classic script, not a module: `app.js` is one, and a module is
 * deferred, so a module here would set the global *after* the page had already
 * decided it had no transport. `make forge-static` bundles it `--format=iife`
 * for that reason.
 */

import { invoke } from '@forge/bridge';

/**
 * Outside a Forge iframe there is nothing on the other end and `invoke`
 * neither resolves nor rejects — it waits. The connection check learned this
 * the hard way, sitting on "checking" for ever. A page that hangs is worse
 * than a page that says it is offline, so every call gets the same fifteen
 * seconds: generous for a cold start, short enough to be an answer.
 */
const TIMEOUT_MS = 15000;

const withTimeout = (promise, route) =>
  Promise.race([
    promise,
    new Promise((_, reject) => {
      setTimeout(
        () => reject(new Error(
          `invoke("${route}") did not answer within ${TIMEOUT_MS / 1000}s. Inside a Forge `
          + 'iframe that means the resolver did not respond; outside one there is nothing '
          + 'on the other end of the bridge at all.',
        )),
        TIMEOUT_MS,
      );
    }),
  ]);

window.__DVD_BRIDGE__ = {
  /** Shown in the page footer, so a reader can tell which connection produced
   *  the numbers in front of them. */
  name: 'Forge',

  /**
   * One question, by route name. The resolvers answer `{status, body}` — the
   * body is the contract `scripts/serve_live.py` defines and they return
   * unchanged; the status is what the same answer would have carried over
   * HTTP, because 404 for a sprint this site does not have and a failure to
   * answer at all are different things and the page says different words for
   * each.
   *
   * A resolver that throws rejects here, exactly as a dead server does for the
   * loopback transport, and the page treats both the same way.
   */
  invoke: (route, params) => withTimeout(invoke(route, params || {}), route),
};
