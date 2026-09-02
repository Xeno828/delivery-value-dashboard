#!/usr/bin/env python3
"""
test_wasm.py — the same Python, under WebAssembly, to the byte.

The Forge function runs `agent/tools/` and `service/routes.py` under Pyodide
rather than calling a hosted service that runs them natively. That is one
implementation of every figure only if the two runtimes agree, and nothing
but a test says they do: a CPython compiled to WebAssembly is a different
build of a different version of the interpreter, and the seed, the float
formatting and the dict order every figure depends on are all things a build
could change quietly. So this suite is the successor of the hosted service's
parity test and the only thing standing between two runtimes and a figure
that drifts between them unnoticed. ADR 0031.

What it does:

  1. Regenerates `forge/src/assets.js` with the generator a deploy uses, from
     the Python as it is now. A stale bundle would test last deploy's Python.
  2. Builds the bodies `tests/test_service.py` uses — every route, refusals
     included, and a sequencing with four asks — and answers each natively
     through `routes.answer`, serialised `json.dumps([status, payload],
     sort_keys=True)`.
  3. Answers the same bodies through `forge/src/runtime.js`, the loader the
     function ships, in a Node process per load mode: from the memory snapshot,
     which is what the resolver function does, and plain, which is what the
     consumer does.
  4. Compares the strings. Equal bytes or a failure that names the route.

Needs Node and the pinned `pyodide` package in forge/node_modules
(`make forge-deps`). Nothing else.

    python3 tests/test_wasm.py
"""

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent" / "tools"))
sys.path.insert(0, str(ROOT / "service"))
sys.path.insert(0, str(ROOT / "tests"))

import routes as RT      # noqa: E402
import intake as IN      # noqa: E402

failures = []


def check(name, ok, detail=""):
    print("  %s  %s%s" % ("PASS" if ok else "FAIL", name,
                          ("  — %s" % (detail,)) if detail and not ok else ""))
    if not ok:
        failures.append(name)


def _preconditions():
    node = shutil.which("node")
    check("node is installed", node is not None,
          "this suite runs the runtime the Forge function ships, which is Node")
    pkg = ROOT / "forge" / "node_modules" / "pyodide" / "package.json"
    check("the pinned pyodide package is installed under forge/", pkg.exists(),
          "run `make forge-deps`")
    if not node or not pkg.exists():
        return False
    pinned = json.loads((ROOT / "forge" / "package.json").read_text())["devDependencies"]["pyodide"]
    installed = json.loads(pkg.read_text())["version"]
    check("and it is the version package.json pins", pinned == installed,
          {"pinned": pinned, "installed": installed})
    return pinned == installed


def _generate():
    """The bundle a deploy ships, from the Python as it is now."""
    t0 = time.time()
    r = subprocess.run(["node", "build-assets.mjs"], cwd=ROOT / "forge",
                       capture_output=True, text=True, timeout=600)
    check("the generator produces forge/src/assets.js", r.returncode == 0,
          (r.stderr or r.stdout)[-400:])
    if r.returncode == 0:
        print("       %s (%.1fs)" % (r.stdout.strip(), time.time() - t0))
    return r.returncode == 0


def _cases():
    """Every route the suite for the hosted service exercises, same bodies."""
    from test_service import _intake_bodies, project, team_payload  # noqa: PLC0415
    full, team, meta = team_payload()
    ds = {"issues": project(team), "meta": meta, "orgConfig": full.get("orgConfig", {})}
    ctx_ds = {"issues": project(team), "contexts": full["contexts"],
              "orgConfig": full.get("orgConfig", {})}
    cid = full["contexts"][0]["id"]
    seq_ds, asks = _intake_bodies()
    return [
        {"name": "facts", "path": "/v1/facts", "body": {"dataset": ds}},
        {"name": "facts all", "path": "/v1/facts", "body": {"dataset": ds, "scope": "all"}},
        {"name": "forecast", "path": "/v1/forecast", "body": {"dataset": ds}},
        {"name": "forecast with target", "path": "/v1/forecast",
         "body": {"dataset": ds, "target": "2026-09-30", "remaining": 12}},
        {"name": "forecast-context", "path": "/v1/forecast-context",
         "body": {"dataset": ctx_ds, "contextId": cid}},
        {"name": "slice", "path": "/v1/slice",
         "body": {"dataset": {"contexts": full["contexts"]}, "contextId": cid}},
        {"name": "history", "path": "/v1/history",
         "body": {"dataset": ctx_ds, "contextId": cid}},
        {"name": "burndown", "path": "/v1/burndown", "body": {"dataset": ds}},
        {"name": "ask", "path": "/v1/ask",
         "body": {"dataset": seq_ds, "ask": asks[0], "board": "42", "asOf": "2026-08-10"}},
        # Four asks: what the demo bundle records, and about a second natively.
        {"name": "sequence %d asks" % len(asks), "path": "/v1/sequence",
         "body": {"dataset": seq_ds, "asks": asks, "board": "42", "asOf": "2026-08-10"}},
        # The resolver's door: the same body, validated and not computed. This
        # is the call the resolver function makes from its snapshot load.
        {"name": "sequence-check", "path": "/v1/sequence-check",
         "body": {"dataset": seq_ds, "asks": asks, "board": "42", "asOf": "2026-08-10"}},
        # Refusals are answers, and a refusal sentence that differs between the
        # runtimes is a page that says two things about one board.
        {"name": "refusal: free text", "path": "/v1/forecast",
         "body": {"dataset": {"issues": [dict(ds["issues"][0], summary="a title")],
                              "meta": {}}}},
        {"name": "refusal: over the ask cap", "path": "/v1/sequence",
         "body": {"dataset": seq_ds, "board": "42", "asOf": "2026-08-10",
                  "asks": [dict(asks[0], id="A%02d" % i) for i in range(IN.MAX_ASKS + 1)]}},
        {"name": "refusal: no such route", "path": "/v1/nope", "body": {}},
        {"name": "refusal: bad config", "path": "/v1/facts",
         "body": {"dataset": dict(ds, orgConfig={"sprintLengthDays": -1})}},
    ]


def _native(cases):
    out = {}
    for c in cases:
        body = json.loads(json.dumps(c["body"]))
        status, payload = RT.answer(c["path"], body)
        out[c["name"]] = json.dumps([status, payload], sort_keys=True)
    return out


def _wasm(cases, mode, tmp):
    cases_path = tmp / "cases.json"
    out_path = tmp / ("out-%s.json" % mode)
    cases_path.write_text(json.dumps(cases))
    r = subprocess.run(["node", str(ROOT / "tests" / "wasm_harness.mjs"),
                        str(cases_path), str(out_path), "--" + mode],
                       cwd=ROOT, capture_output=True, text=True, timeout=1200)
    check("the runtime answers every case from a %s load" % mode, r.returncode == 0,
          (r.stderr or r.stdout)[-600:])
    if r.returncode != 0:
        return None
    return json.loads(out_path.read_text())


def _digest(s):
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def test_parity():
    if not _preconditions() or not _generate():
        return
    cases = _cases()
    native = _native(cases)
    check("the native answers include a real sequencing, not a refusal",
          '"available": true' in native["sequence %d asks" % 4]
          if "sequence 4 asks" in native else True,
          native.get("sequence 4 asks", "")[:120])

    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        for mode in ("snapshot", "plain"):
            print("\nfrom a %s load" % mode)
            got = _wasm(cases, mode, tmp)
            if got is None:
                continue
            check("the runtime reports the load it took", got["mode"] == mode, got["mode"])
            print("       node %s, load %d ms, digest %s" % (got["node"], got["loadMs"], got["digest"]))
            # Every Python module the tools have is in the bundle. A module
            # added to agent/tools/ that the generator missed would import
            # natively and fail inside a tenant.
            shipped = {f for f in got["files"] if f.startswith("work/")}
            needed = {"work/agent/tools/%s" % p.name for p in (ROOT / "agent" / "tools").glob("*.py")}
            needed.add("work/service/routes.py")
            check("every Python module is in the bundle", needed <= shipped,
                  sorted(needed - shipped))
            check("and nothing that is not Python or the runtime is",
                  all(f.startswith(("pyodide/", "work/")) or f == "snapshot.bin"
                      for f in got["files"]),
                  [f for f in got["files"] if not f.startswith(("pyodide/", "work/"))])

            for c in cases:
                name = c["name"]
                same = got["results"].get(name) == native[name]
                check("%-28s %s  %5d ms" % (name, _digest(native[name]), got["timings"].get(name, -1)),
                      same,
                      {"native": native[name][:200],
                       "wasm": (got["results"].get(name) or "")[:200]})
            # The two runtimes agreeing on refusals is the cheap half; this is
            # the assertion that the sample is not all refusals.
            answered = [c["name"] for c in cases
                        if got["results"].get(c["name"], "").startswith("[200")]
            check("most cases answered rather than refused", len(answered) >= 8, answered)


if __name__ == "__main__":
    print("the same Python under WebAssembly")
    test_parity()
    print()
    if failures:
        print("%d check(s) failed: %s" % (len(failures), ", ".join(failures)))
        sys.exit(1)
    print("all WebAssembly parity checks passed")
