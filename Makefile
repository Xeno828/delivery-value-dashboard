BUNDLE ?= data/demo-intake-bundle.json
BOARD  ?= 42

.PHONY: build check test test-agent test-a11y test-security test-service test-wasm perf report intake intake-scale intake-sequence demo serve serve-live forge-static forge-deps forge-assets forge-lint forge-deploy forge-install forge-upgrade forge-uninstall forge-smoke bundle fetch clean

build:            ## assemble dist/delivery-value-dashboard.html from src/
	python3 build.py

check:            ## fail if dist/ is stale relative to src/
	python3 build.py --check

test: build       ## run every suite: browser, agent, accessibility, security, service, wasm
	python3 tests/e2e.py
	python3 tests/test_agent.py
	python3 tests/a11y.py
	python3 tests/security.py
	python3 tests/test_service.py
	python3 tests/test_wasm.py

test-a11y: build  ## accessibility only (WCAG 2.2 AA, both themes)
	python3 tests/a11y.py

test-security: build ## security only (XSS, pollution, traversal, secrets, deps)
	python3 tests/security.py

test-agent:       ## agent tools only: facts, forecast, refusals, backtest
	python3 tests/test_agent.py

test-service:     ## the routes and the Forge resolver: projection, refusals, jobs, no arithmetic
	python3 tests/test_service.py

# Regenerates forge/src/assets.js itself, from the Python as it is now, so it
# never tests last deploy's bundle. Needs node and `make forge-deps`.
test-wasm:        ## the same Python under WebAssembly, byte for byte
	python3 tests/test_wasm.py

perf: build       ## measure load and interaction cost at four bundle sizes
	@python3 scripts/make_sample_bundle.py --scale 7  --out /tmp/bundle-7.json  >/dev/null
	@python3 scripts/make_sample_bundle.py --scale 22 --out /tmp/bundle-22.json >/dev/null
	python3 tests/perf.py

demo: build       ## rebuild the story bundle and record both demo videos
	python3 scripts/make_demo_bundle.py
	python3 scripts/record_demo.py --out docs/demo.mp4
	@# The small cut is what people email. Produced here rather than by hand so
	@# the two videos cannot end up showing different versions of the product.
	ffmpeg -y -loglevel error -i docs/demo.mp4 -vf scale=1200:-2 -c:v libx264 \
	  -preset slow -crf 30 -pix_fmt yuv420p -movflags +faststart docs/demo-small.mp4
	@ls -lh docs/demo.mp4 docs/demo-small.mp4 | awk '{print "  " $$9 "  " $$5}'

report:           ## print the facts pack and forecast for the sample data
	python3 agent/tools/metrics.py data/sample-sprint.json --out agent/snapshots/facts-latest.json > /dev/null
	python3 agent/tools/forecast.py data/sample-multi-sprint.json --snapshots agent/snapshots/scope.json

intake:           ## forecast a product ask (ASK=data/asks/INTAKE-2026-014.json)
	@test -n "$(ASK)" || (echo "usage: make intake ASK=data/asks/INTAKE-2026-014.json"; exit 1)
	python3 agent/tools/intake.py $(BUNDLE) --ask $(ASK)

intake-scale:     ## print what S/M/L/XL mean on this board, in items
	python3 agent/tools/intake.py $(BUNDLE) --board $(BOARD) --scale

intake-sequence:  ## what each ordering of the outstanding asks costs the others
	python3 agent/tools/intake.py $(BUNDLE) --sequence data/asks/*.json

serve: build      ## preview at http://localhost:8000/dist/
	@echo "http://localhost:8000/dist/delivery-value-dashboard.html"
	python3 -m http.server 8000

serve-live: build ## serve with the live-mode API backed by the demo bundle
	python3 scripts/serve_live.py --bundle data/sample-bundle.json

forge-static: build forge-deps  ## stage the Forge static resource
	@mkdir -p forge/static/dashboard/build
	@# Not a copy of dist/, and it does not carry dist/'s data.
	@#
	@# A Forge iframe's CSP blocks inline style and script, so the same sources
	@# are linked rather than inlined. The seed is forge/seed.json — empty,
	@# because the point of the Forge build is the tenant's own sprints and a
	@# demo company's would sit in the picker beside them. --bridge links the
	@# transport adapter ahead of app.js, which is how the page finds one
	@# without importing anything.
	python3 build.py --split forge/static/dashboard/build \
	  --data forge/seed.json --bridge bridge.js
	@# @forge/bridge is CommonJS, so anything calling invoke() has to be bundled
	@# rather than copied. esbuild is a forge/ devDependency; the dashboard
	@# still has none.
	@#
	@# The bridge adapter cannot be a module: app.js is a classic script, a
	@# module is deferred, and an adapter that runs after the page has already
	@# decided it has no transport is an adapter that never ran.
	cd forge && npx --no-install esbuild bridge/bridge.js \
	  --bundle --format=iife --target=es2020 --outfile=static/dashboard/build/bridge.js
	@echo "staged forge/static/dashboard/build/index.html"

# Staging and linting as one target, because forgetting the first makes the
# second report a broken manifest rather than an unbuilt one — and because the
# Makefile lives at the repository root while the CLI has to run in forge/,
# which is its own small trap.
forge-deps:          ## install the Forge SDK (@forge/api, @forge/resolver)
	cd forge && npm install --no-fund --no-audit

# The Python runtime the function ships, generated and never committed. It is
# built from agent/tools/ and service/routes.py as they are *now*, so a deploy
# that skipped this step would ship the Python of the previous deploy under a
# manifest that says otherwise — hence forge-deploy depends on it. ADR 0031.
forge-assets: forge-deps  ## generate forge/src/assets.js: Pyodide, the tools, routes.py and a snapshot
	cd forge && node build-assets.mjs

forge-lint: forge-static forge-deps forge-assets  ## stage, install, generate, then run forge lint
	cd forge && forge lint

forge-deploy: forge-static forge-deps forge-assets ## stage, install, generate, then deploy to development
	cd forge && forge deploy -e development

# The CLI needs the manifest in the working directory and the manifest lives in
# forge/, so every one of these fails with "manifest-file-required" when run
# from the repository root — which is where the Makefile is. Hence the targets.
forge-install:    ## install the app on a site (first time)
	cd forge && forge install

forge-upgrade:    ## re-consent after a module or scope change
	cd forge && forge install --upgrade

forge-uninstall:  ## remove it; a development installation is disposable
	cd forge && forge uninstall

# Not in `make test`: it needs a deployed environment and a person's session.
# The first run opens a browser window to sign in; later runs are headless.
forge-smoke:      ## open the deployed app inside the dev site and check the page from inside its iframe
	python3 tests/forge_smoke.py

bundle:           ## regenerate the demo bundles (delivery + intake reference class)
	python3 scripts/make_sample_bundle.py
	python3 scripts/make_demo_bundle.py
	python3 scripts/make_intake_demo.py

fetch:            ## pull live data (needs .env — see docs/connecting-jira-asana.md)
	./scripts/refresh.sh

clean:
	rm -rf dist __pycache__ tests/__pycache__ tests/last-run.png

# Hyphenated targets were invisible here: the pattern matched ^[a-z]+ only, so
# test-agent, serve-live and every forge-* target were absent from the list.
help:
	@grep -E '^[a-z][a-z-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
