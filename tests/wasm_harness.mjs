// The Node half of tests/test_wasm.py. Loads the runtime the Forge function
// ships — forge/src/runtime.js over the generated forge/src/assets.js — and
// answers every case in a file, in one load mode, writing what Python
// serialised. The Python half compares it with the same call made natively.
//
// One process per load mode, because a container holds one runtime and so
// does this module: `runtime.js` caches the first load for the life of the
// process, exactly as it does on Forge.
//
//   node tests/wasm_harness.mjs cases.json out.json --snapshot
//   node tests/wasm_harness.mjs cases.json out.json --plain
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';

const require = createRequire(import.meta.url);
const HERE = path.dirname(new URL(import.meta.url).pathname);
const runtime = require(path.join(HERE, '..', 'forge', 'src', 'runtime.js'));
const assets = require(path.join(HERE, '..', 'forge', 'src', 'assets.js'));

const [casesPath, outPath, modeFlag] = process.argv.slice(2);
if (!casesPath || !outPath || !['--snapshot', '--plain'].includes(modeFlag)) {
  console.error('usage: node tests/wasm_harness.mjs cases.json out.json --snapshot|--plain');
  process.exit(2);
}
const snapshot = modeFlag === '--snapshot';
const cases = JSON.parse(fs.readFileSync(casesPath, 'utf8'));

const t0 = performance.now();
await runtime.load({ snapshot });
const loadMs = Math.round(performance.now() - t0);

const results = {};
const timings = {};
for (const c of cases) {
  const t = performance.now();
  // `run`, not `answer`: the string Python serialised, untouched by
  // JSON.parse and JSON.stringify on this side, is what is compared.
  results[c.name] = await runtime.run(c.path, c.body, { snapshot });
  timings[c.name] = Math.round(performance.now() - t);
}

fs.writeFileSync(outPath, JSON.stringify({
  mode: runtime.state().loadedWith,
  digest: assets.digest,
  files: Object.keys(assets.files).sort(),
  node: process.version,
  loadMs,
  timings,
  results,
}));
