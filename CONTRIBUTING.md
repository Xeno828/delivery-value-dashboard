# Contributing

## Build

```bash
make build     # src/ → dist/delivery-value-dashboard.html
make test      # build, then run the browser suite
make serve     # preview on localhost:8000
```

There is no bundler, no `npm install`, no transpile step. `build.py` substitutes four placeholders in `src/index.html`. That is deliberate — the deliverable is one file a non-developer can open, audit and email, and a toolchain is the fastest way to lose that.

## Layout

| Path | What lives there |
|---|---|
| `src/index.html` | Page structure and the four build placeholders |
| `src/styles.css` | All styling, including both colour themes |
| `src/app.js` | Metrics, charts, filters, drill-downs; exposes `window.DVD` |
| `src/import.js` | File parsing and the upload wizard; consumes `window.DVD` |
| `build.py` | The build |
| `dist/` | Committed build output — see below |

`dist/` is committed on purpose so the repository can be downloaded and used without running anything. CI fails if it is stale, so **run `make build` and commit the result** with any `src/` change.

## Rules worth keeping

1. **No runtime dependencies, no network calls.** No CDN, no fonts, no analytics. The file must work from a USB stick on a plane.
2. **No browser storage.** `localStorage` and cookies are out. "Nothing you load leaves your browser and nothing persists" is a promise the code has to keep literally.
3. **Charts follow the colour rules.** Categorical hues are assigned in fixed order and never cycled; sequential ramps are one hue; status colours (good / warning / serious / critical) are reserved for status and never reused as a series. Every palette change is re-validated for colour-vision deficiency against both surfaces. Never a dual-axis chart.
4. **Every chart has a table view.** Colour is never the only encoding, and every status chip carries an icon and a word.
5. **Every number traces to issues.** If you add a figure, make it clickable through to the rows behind it.
6. **Derived data is recomputed, never inherited.** When new issues arrive, recompute the burndown and the history row. Fresh numbers under a stale chart is the worst failure mode this tool has.
7. **Say what you cannot know.** Missing inputs get a stated warning, not a silent zero.

## Adding a metric

1. Compute it in `derive()` in `src/app.js` from the filtered issue list.
2. Render it, and give it a `data-tt` tooltip with *what it is*, *how to read it* and *how to improve it* — all three.
3. Wire a drill-down through `openDrill(title, subtitle, issues)`.
4. Add a table view via `S.tables.<key>` and `drawTable("<key>")`.
5. Add a check to `tests/e2e.py`.

## Adding an import format

`src/import.js` is organised as parse → map → coerce → assemble. To support another tracker, the usual change is only new entries in `SYN` (header synonyms) and possibly `parseDate`. Add a fixture under `tests/fixtures/` and a case in `tests/e2e.py`.

## Rules the suites enforce

Four suites run in CI and all must pass:

| Suite | What it guards |
|---|---|
| `tests/e2e.py` | The product works: import, context switching, units, drill-downs |
| `tests/test_agent.py` | The tools agree with the dashboard; the forecaster is honest and backtested |
| `tests/a11y.py` | WCAG 2.2 AA in both themes, including post-interaction states |
| `tests/security.py` | Hostile data cannot execute; nothing leaks; nothing persists |

Two rules worth stating because both were broken once and caught here:

8. **Escape at output, exactly once.** Renderers build HTML strings. Escape where the string is emitted, never at the point the value is collected — mixing the two produces double-escaping in some paths and none in others, which is how the risk register shipped a stored XSS. Any URL from data goes through `safeUrl()`: `esc()` neutralises markup, not a `javascript:` scheme.
9. **UI colour tokens are not chart colours.** `--s1`..`--s8` are the validated series palette and must not be changed for contrast reasons. Text and controls use `--link`, `--accent-bg`, `--info-ink`, which are free to be darker.

## Tests

`tests/e2e.py` drives a real Chromium via Playwright: parser unit checks, then the full wizard against Jira CSV, Asana CSV, XLSX and a merge file, then drill-downs. It asserts zero console errors. Keep it that way.

```bash
pip install playwright && playwright install chromium
make test          # all four suites
make test-a11y     # accessibility only
make test-security # security only
make perf          # timing at four bundle sizes (not part of `make test`)
```
