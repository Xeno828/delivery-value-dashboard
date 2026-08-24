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
 * It must end up a classic script, not a module: `app.js` is one, and a module
 * is deferred, so a module here would set the global *after* the page had
 * already decided it had no transport. `make forge-static` bundles it
 * `--format=iife` for that reason, and the source below is CommonJS for a
 * second reason given where it is required.
 */

/* CommonJS, and required inside a try, which is the whole reason this file is
   not written as a module.

   `@forge/bridge` connects to its host as a side effect of being loaded, and
   outside a Forge iframe that *throws* — "Unable to establish a connection with
   the Custom UI bridge". An ES `import` is evaluated before any code here runs,
   so the throw aborted this file before it could install anything, and the page
   fell back to the same-origin fetch with nothing but an uncaught error in the
   console to say why. That is the silent-failure shape this repository keeps
   paying for: inside a real iframe the same throw would leave the dashboard
   looking merely offline.

   A `require` inside a try runs where it is written, so the failure is caught,
   named, and left to the page to handle — no transport is installed, which is
   the correct answer outside Forge and an explained one inside it. */
let invoke = null;
try {
  ({ invoke } = require('@forge/bridge'));
} catch (err) {
  // The one place a console message earns its keep. There is no page to write
  // to yet, and every alternative is a dashboard that looks offline for a
  // reason nobody can find.
  console.error(
    'The Forge bridge did not initialise, so the dashboard has no transport to '
    + 'this site and will fall back to whatever it was built with. '
    + String((err && err.message) || err),
  );
}

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

/* Installed only when there is something to install. A transport whose every
   call fails is worse than no transport: the page would report itself
   connected and then show nothing. */
if (invoke) {
  window.__DVD_BRIDGE__ = {
    /** Shown in the page footer, so a reader can tell which connection
     *  produced the numbers in front of them. */
    name: 'Forge',

    /**
     * One question, by route name. The resolvers answer `{status, body}` — the
     * body is the contract `scripts/serve_live.py` defines and they return
     * unchanged; the status is what the same answer would have carried over
     * HTTP, because 404 for a sprint this site does not have and a failure to
     * answer at all are different things, and the page says different words
     * for each.
     *
     * A resolver that throws rejects here, exactly as a dead server does for
     * the loopback transport, and the page treats both the same way.
     */
    invoke: (route, params) => withTimeout(invoke(route, params || {}), route),
  };
}
