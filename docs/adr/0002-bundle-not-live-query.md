# The page never queries Jira or Asana; data arrives as a bundle

"Pick a sprint and the page fetches it" is not buildable as stated: a static HTML file has no MCP client, both APIs reject cross-origin browser requests, and any embedded credential is readable by everyone the file is forwarded to. So contexts are fetched **up front** into a bundle, which makes switching instant and offline and keeps the file emailable.

Live mode is the deliberate escape hatch — a local server the user starts on purpose, bound to `127.0.0.1`, that the page discovers and can pull unbundled contexts from. It degrades in one direction only: without it you get what was bundled, and without a bundle you get the sprint the file was built with.

Considered and rejected: proxying the tracker through a hosted service (reintroduces the credential and the infrastructure the single-file decision exists to avoid). See `docs/contexts-and-live-mode.md`.
