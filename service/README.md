# service/

One file, `routes.py`: the projection that keeps a customer's words out of a
calculation, the caps, the refusal sentences, and one function per route,
ending in `answer(path, body)`. It computes nothing — every figure comes from
`agent/tools/` — and it is what the Forge function runs unchanged under
WebAssembly, packed into a generated module by `forge/build-assets.mjs` at
deploy. `tests/test_wasm.py` holds its answer under that runtime against the
same call made natively, byte for byte, and `tests/test_service.py` holds its
answer against the tool called directly.

Anything added here has to import under Pyodide: no sockets, no environment,
no third-party module. The suite asserts it.

The directory is named for what used to be beside this file. From 2026-08-25
to 2026-09-03 `app.py` put a socket and two auth verifiers in front of the
same routes and ran on Cloud Run in three regions as the hosted calculator
the Forge app reached over a remote. [ADR 0031](../docs/adr/0031-the-forecast-runs-inside-the-forge-function.md)
retired it; [docs/hosting-the-calculator.md](../docs/hosting-the-calculator.md)
is the record of what ran and what it cost.
