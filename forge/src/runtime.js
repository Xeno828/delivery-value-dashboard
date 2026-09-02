/**
 * The Python runtime inside the Forge function.
 *
 * `agent/tools/` and `service/routes.py` run here unchanged, under Pyodide —
 * CPython compiled to WebAssembly — so the figures a tenant reads are computed
 * by the same code the CLI, the dashboard's live mode and the hosted service
 * run. Nothing is rewritten and nothing leaves Atlassian. ADR 0031.
 *
 * How the runtime travels. Forge's bundler ships compiled JavaScript only and
 * rewrites Pyodide's own dynamic `import()` into something that fails, so the
 * five runtime files, the Python sources and a memory snapshot travel as
 * gzip-and-base64 strings inside `./assets.js`, a module `make forge-assets`
 * generates and git ignores. On first use in a container they are unpacked
 * to `/tmp` and the runtime is imported from there through a `Function`
 * constructor the bundler cannot see into. A warm container keeps the loaded
 * runtime in module scope, so the load is paid once per container.
 *
 * Two ways to load, one flag. The resolver function loads from the snapshot:
 * 1.3 s cold against 11 s, measured on Forge, which is the difference between
 * a first click that answers and one the adapter times out. The consumer
 * function loads plain, because on Forge's runtime everything computed after
 * a snapshot load runs 1.65× slower and the consumer runs for minutes. Same
 * bundle; `answer(path, body, { snapshot })` says which.
 *
 * What this file must never do is compute. `run()` hands a route name and a
 * body to `routes.answer` and returns the string Python serialised; `answer()`
 * parses it. `tests/test_wasm.py` holds that string byte for byte against the
 * same call made natively, which is the assertion the whole route rests on.
 *
 * CommonJS on purpose: `assets.js` is a generated CommonJS module and the
 * parity suite loads this file under plain Node, where the app's `.js` files
 * are CommonJS. Forge's bundler imports it from the ESM resolver without
 * complaint, as it did on the probe.
 */
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const zlib = require('node:zlib');

/**
 * What the snapshot was taken after, and what a plain load runs after writing
 * the sources: the sources on `sys.path`, `routes` imported, and one function
 * that takes a route and a JSON body and returns `[status, payload]` as JSON
 * with sorted keys. Sorted so the parity suite compares strings, not trees.
 *
 * Exported so `build-assets.mjs` runs exactly this before it snapshots. Two
 * copies of this string would be two runtimes that differ in what they have
 * imported, which is a difference no test would see until a route was missing.
 */
const BOOT = `
import json, sys
sys.path.insert(0, '/work/service')
import routes
def answer_json(path, body_json):
    status, payload = routes.answer(path, json.loads(body_json))
    return json.dumps([status, payload], sort_keys=True)
`;

/** Where the sources are written inside the WebAssembly filesystem. Fixed by
 *  `routes.py`, which finds the tools at `../agent/tools` relative to itself. */
const WORK = '/work';

let assets = null;
const loadAssets = () => {
  // Required lazily rather than at the top: the generator imports this file
  // for BOOT before assets.js exists, and a resolver that never touches the
  // runtime should not parse seventeen megabytes of base64 on cold start.
  if (!assets) assets = require('./assets.js');
  return assets;
};

/** The directory this bundle unpacks to, keyed by its content digest so a new
 *  deploy never reads a previous bundle's files out of a warm `/tmp`. */
const baseDir = () => path.join(os.tmpdir(), `shipping-forecast-${loadAssets().digest}`);

/** Unpack every file once per container. Idempotent: a marker file says it
 *  has been done, and a concurrent unpack writes the same bytes. */
const unpack = () => {
  const base = baseDir();
  const done = path.join(base, '.unpacked');
  if (fs.existsSync(done)) return base;
  for (const [name, b64] of Object.entries(loadAssets().files)) {
    const target = path.join(base, name);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, zlib.gunzipSync(Buffer.from(b64, 'base64')));
  }
  fs.writeFileSync(done, '');
  return base;
};

/**
 * Write the Python sources into the runtime's filesystem and run BOOT.
 *
 * Exported for the generator, which does the same before it snapshots. The
 * snapshot holds the *imported modules* and not the files, so a runtime
 * loaded from it needs neither step; a plain load needs both.
 */
const writeSources = (py, files) => {
  py.FS.mkdirTree(`${WORK}/agent/tools`);
  py.FS.mkdirTree(`${WORK}/service`);
  for (const [name, text] of Object.entries(files)) py.FS.writeFile(`${WORK}/${name}`, text);
  py.runPython(BOOT);
};

/** The Python sources as unpacked text, keyed by their path under WORK. */
const sourcesFrom = (base) => {
  const out = {};
  const dir = path.join(base, 'work');
  const walk = (d) => {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, entry.name);
      if (entry.isDirectory()) walk(p);
      else out[path.relative(dir, p)] = fs.readFileSync(p, 'utf8');
    }
  };
  walk(dir);
  return out;
};

// Module scope survives across invocations in a warm container. One runtime
// per container; the first caller's choice of load is the container's.
let runtime = null;   // Promise<pyodide>
let loadedWith = null; // 'snapshot' | 'plain'

/**
 * The loaded runtime, loading it on the first call.
 *
 * `snapshot: true` restores the memory image the generator took after BOOT;
 * `false` runs BOOT against freshly written sources. The undocumented Pyodide
 * options `_loadSnapshot` and `_makeSnapshot` are the dependency ADR 0031
 * accepts with its eyes open, and the parity suite is what would notice them
 * changing.
 */
const load = ({ snapshot }) => {
  if (runtime) return runtime;
  loadedWith = snapshot ? 'snapshot' : 'plain';
  runtime = (async () => {
    const base = unpack();
    // A `Function` rather than a bare `import()`: the bundler rewrites the
    // latter into a chunk request that does not exist at runtime.
    const mod = await new Function('u', 'return import(u)')(`file://${base}/pyodide/pyodide.mjs`);
    const opts = { indexURL: `${base}/pyodide/` };
    if (snapshot) opts._loadSnapshot = fs.readFileSync(path.join(base, 'snapshot.bin'));
    const py = await mod.loadPyodide(opts);
    if (!snapshot) writeSources(py, sourcesFrom(base));
    return py;
  })();
  // A failed load must not be cached as a runtime that will fail every call
  // for the life of the container.
  runtime.catch(() => { runtime = null; loadedWith = null; });
  return runtime;
};

/**
 * One route, answered by Python, as the string Python serialised:
 * `json.dumps([status, payload], sort_keys=True)`.
 *
 * The body crosses as a JSON string and comes back as one, so no value is
 * ever converted by the JavaScript–Python bridge on the way: a float that
 * crossed as a float would come back as whatever the bridge thought it was.
 */
const run = async (path_, body, { snapshot = true } = {}) => {
  const py = await load({ snapshot });
  py.globals.set('__path', String(path_));
  py.globals.set('__body', JSON.stringify(body ?? {}));
  try {
    return py.runPython('answer_json(__path, __body)');
  } finally {
    py.globals.delete('__path');
    py.globals.delete('__body');
  }
};

/** The same, parsed: `{ status, payload }`, the envelope `routes.answer` returns. */
const answer = async (path_, body, opts) => {
  const [status, payload] = JSON.parse(await run(path_, body, opts));
  return { status, payload };
};

/** Which load this container took, for a log line and for the parity suite. */
const state = () => ({ loaded: runtime !== null, loadedWith });

module.exports = { BOOT, WORK, answer, load, run, state, unpack, writeSources };
