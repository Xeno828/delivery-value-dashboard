BUNDLE ?= data/demo-intake-bundle.json
BOARD  ?= 42

.PHONY: build check test test-agent test-a11y test-security perf report intake intake-scale intake-sequence demo serve serve-live bundle fetch clean

build:            ## assemble dist/delivery-value-dashboard.html from src/
	python3 build.py

check:            ## fail if dist/ is stale relative to src/
	python3 build.py --check

test: build       ## run every suite: browser, agent, accessibility, security
	python3 tests/e2e.py
	python3 tests/test_agent.py
	python3 tests/a11y.py
	python3 tests/security.py

test-a11y: build  ## accessibility only (WCAG 2.2 AA, both themes)
	python3 tests/a11y.py

test-security: build ## security only (XSS, pollution, traversal, secrets, deps)
	python3 tests/security.py

test-agent:       ## agent tools only: facts, forecast, refusals, backtest
	python3 tests/test_agent.py

perf: build       ## measure load and interaction cost at four bundle sizes
	@python3 scripts/make_sample_bundle.py --scale 7  --out /tmp/bundle-7.json  >/dev/null
	@python3 scripts/make_sample_bundle.py --scale 22 --out /tmp/bundle-22.json >/dev/null
	python3 tests/perf.py

demo: build       ## rebuild the story bundle and record docs/demo.mp4
	python3 scripts/make_demo_bundle.py
	python3 scripts/record_demo.py --out docs/demo.mp4

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

bundle:           ## regenerate the demo bundles (delivery + intake reference class)
	python3 scripts/make_sample_bundle.py
	python3 scripts/make_demo_bundle.py
	python3 scripts/make_intake_demo.py

fetch:            ## pull live data (needs .env — see docs/connecting-jira-asana.md)
	./scripts/refresh.sh

clean:
	rm -rf dist __pycache__ tests/__pycache__ tests/last-run.png

help:
	@grep -E '^[a-z]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2}'
