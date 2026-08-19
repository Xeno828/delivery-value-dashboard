# The dashboard is one self-contained HTML file

The audience for a delivery report is executives who will not install anything and engineers who will not trust a number they cannot open. A single file with no build step, no server, no runtime dependencies, no network calls and no browser storage satisfies both, and survives the way these reports actually travel — forwarded as an email attachment to someone outside the organisation.

The cost is real: no npm ecosystem, hand-rolled SVG charts, and a build step that concatenates `src/` into `dist/` (committed, so the repo is usable without running it). We took that over any framework, because the threat model is the file leaving the building and every dependency is something that either phones home or fails to load when it does.

`README.md` makes the fuller argument; the security suite enforces the zero-network, zero-storage half.
