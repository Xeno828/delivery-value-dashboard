/**
 * Shaping Jira's answers into the dashboard's dataset. No Forge, no network.
 *
 * Everything here is a pure function of a Jira response body, which is the
 * whole reason it is a separate file: `index.js` cannot be run outside Forge,
 * and the shapes below are the half that has to agree with
 * `scripts/serve_live.py`. `tests/test_service.py` runs these against fixtures
 * and compares the result to what the live server really returns, so the two
 * transports cannot drift into answering the same question differently.
 *
 * This module plays the fetcher's part, not the calculator's. Extracting a
 * field out of a Jira issue is what `scripts/fetch_delivery_data.py` does and
 * is not arithmetic; deciding what a status *means*, or what a burndown looks
 * like, is organisation config and calculation respectively, and neither
 * happens here. Where a field would need one of those it is left out, and the
 * page says so on the tile rather than showing a zero.
 */

/** The context id the whole product keys on: project, board, sprint. The same
 *  string `serve_live.py` builds, because the page round-trips it back to
 *  `context` and a second format would be a second product. */
export const contextId = (projectKey, boardId, sprintId) =>
  `${projectKey || '?'}/${boardId}/${sprintId}`;

/** Back out again, so `context` needs no state between calls. Returns null for
 *  anything that is not the shape above — a caller must refuse rather than
 *  query whatever the string happened to parse into. */
export const parseContextId = (id) => {
  const m = /^([^/]+)\/(\d+)\/(\d+)$/.exec(String(id ?? ''));
  return m ? { projectKey: m[1], boardId: m[2], sprintId: m[3] } : null;
};

/**
 * One selectable sprint. Field for field what `JiraBackend.contexts()` puts on
 * the wire, `_sprintId` included — the page ignores it, and dropping it here
 * would make a parity check pass against a shape neither side really sends.
 *
 * `workingDays` is deliberately absent. Which days are worked is organisation
 * config, and resolving it here would be a fourth opinion arriving by a fourth
 * route. `BundleBackend.contexts()` strips it for the same reason.
 */
export const contextEntry = (board, sprint) => {
  const loc = board.location || {};
  return {
    id: contextId(loc.projectKey, board.id, sprint.id),
    source: 'jira',
    projectKey: loc.projectKey ?? null,
    projectName: loc.projectName ?? null,
    boardId: String(board.id),
    boardName: board.name ?? null,
    // The board's name, as the live server does it. A Jira board has no team
    // field; the board is the closest thing to one, and the forecaster slices
    // its history by team, so the two must agree about what a team is.
    team: board.name ?? null,
    sprintName: sprint.name ?? null,
    sprintState: sprint.state ?? null,
    sprintGoal: sprint.goal || '',
    startDate: (sprint.startDate || '').slice(0, 10),
    endDate: (sprint.endDate || '').slice(0, 10),
    asOfDate: null,
    issueCount: 0,
    _sprintId: sprint.id,
  };
};

/** Newest first, then the same cap the live server applies — and the cap is
 *  reported by the caller rather than applied quietly, because a truncated
 *  list of sprints reads as a complete one. */
export const recentSprints = (sprints, limit) =>
  (sprints || [])
    .slice()
    .sort((a, b) => String(b.startDate || '').localeCompare(String(a.startDate || '')))
    .slice(0, limit);

/** The envelope `GET api/contexts` returns. */
export const contextsBody = (label, contexts) => ({
  source: 'jira',
  label,
  // Empty, and that is the honest answer rather than a convenient one. The
  // organisation config travels inside a dataset, and a Forge install has no
  // dataset — there is nowhere yet for a site to say which statuses mean done
  // or which days it works. Empty resolves to the documented defaults in
  // `orgConfigOf()`, and the page footer names the calendar it used. Inventing
  // one here would be the third opinion `config/organisation.json` exists to
  // prevent, arriving by a route nobody can see.
  orgConfig: {},
  contexts,
});

/**
 * One issue, in the dataset's schema.
 *
 * Three fields the fetcher produces are absent, each for a stated reason:
 *
 *   statusCategory  Which statuses mean done is organisation config. The raw
 *                   name goes out and `normaliseIssue()` categorises it under
 *                   the config the page is running, exactly as it does for any
 *                   file whose producer did not resolve it.
 *   started         The first transition into an "In Progress" status — which
 *                   needs that same config to recognise. Left out rather than
 *                   guessed: the page prints "no completed items with both a
 *                   start and a resolved date", which is true, and flow
 *                   efficiency stays silent rather than reporting a number
 *                   built on a rule this file made up.
 *   businessValue   Jira has no native value field, and the fetcher writes 0
 *                   here too.
 *   contextId       The page tags these itself in `loadContext()`, and does it
 *                   deliberately — "never let normalise() re-tag these". A
 *                   value sent from here would be overwritten, so sending one
 *                   would only invite the two to disagree.
 *
 * `addedMidSprint` is *not* in that list, and the difference matters. It needs
 * no config — it is "the sprint field changed after the sprint began" — and
 * defaulting it to false is not a silence, it is the claim that nothing was
 * added. The health score reads "no mid-sprint additions" and scores scope
 * stability at full marks, which is a confident wrong answer of exactly the
 * kind this repository keeps finding.
 */
export const issueFrom = (raw, opts) => {
  const o = opts || {};
  const f = raw.fields || {};
  const status = f.status || {};
  const parent = f.parent || {};
  const site = String(o.siteUrl || '').replace(/\/$/, '');
  return {
    key: raw.key,
    summary: f.summary ?? '',
    type: (f.issuetype || {}).name ?? null,
    status: status.name ?? null,
    assignee: (f.assignee || {}).displayName || 'Unassigned',
    // OPEN, and it returns a plausible wrong number rather than failing: the
    // story-point custom field id differs per Jira site. The Python fetcher
    // discovers it by display name via /rest/api/3/field; this hardcodes the
    // common one. On a site that uses a different id every issue reads as zero
    // points, the burndown flattens in points mode, and nothing says why. The
    // connection check shows it — storyPoints absent from the projected
    // payload means this id is wrong here. Fixing it needs a field-read scope,
    // so it is a decision, not a patch.
    storyPoints: f.customfield_10016 ?? 0,
    priority: (f.priority || {}).name ?? null,
    epic: (parent.fields || {}).summary ?? null,
    epicKey: parent.key ?? null,
    created: (f.created || '').slice(0, 10) || null,
    resolved: (f.resolutiondate || '').slice(0, 10) || null,
    dueDate: f.duedate ?? null,
    flagged: Boolean(f.flagged),
    addedMidSprint: addedMidSprint(raw, o.sprintStart),
    businessValue: 0,
    valueBasis: '',
    labels: f.labels || [],
    url: site && raw.key ? `${site}/browse/${encodeURIComponent(raw.key)}` : null,
  };
};

/**
 * Was this issue put into the sprint after it started?
 *
 * Compared as YYYY-MM-DD strings, which is what the Python fetcher does — so
 * an item added later on the day the sprint opened reads as committed in both.
 * Matching the existing behaviour matters more than being right about the edge
 * case: two producers disagreeing about one issue is worse than both being
 * generous about the same one.
 */
const addedMidSprint = (raw, sprintStart) => {
  const start = String(sprintStart || '').slice(0, 10);
  if (!start) return false;
  const histories = (raw.changelog || {}).histories || [];
  for (const h of histories) {
    const when = String(h.created || '').slice(0, 10);
    if (!when || when <= start) continue;
    for (const item of h.items || []) {
      if (String(item.field || '').toLowerCase() === 'sprint') return true;
    }
  }
  return false;
};

/**
 * The envelope `GET api/context?id=…` returns.
 *
 * The four series are empty because this app computes nothing. A burndown is
 * built by `build_burndown()` in Python, and Forge cannot run Python — it
 * would have to come from the hosted calculator, which is not provisioned. An
 * empty series is not a silent gap: the page prints "no burndown series in
 * this dataset" where the chart would be.
 */
export const contextBody = (entry, issues) => ({
  context: {
    ...entry,
    // What the live server does with an active sprint, quirk included: it has
    // no as-of date of its own, so the sprint's end stands in. Diverging here
    // would move every elapsed-percentage on the page relative to loopback.
    asOfDate: entry.asOfDate || entry.endDate || null,
    issueCount: issues.length,
  },
  orgConfig: {},
  issues,
  burndown: [],
  history: [],
  releases: [],
  dora: null,
});

/**
 * Not found, in the shape the loopback transport gives a 404 — and saying
 * which of the four reasons it was.
 *
 * The first version said only "unknown context", which is what the page then
 * put in front of a user as *"server returned 404"*. Four quite different
 * situations produce that answer and they have four different fixes; a reader
 * with the bare status has no way to tell a stale bookmark from a board that
 * has moved project.
 */
export const notFound = (id, why) => ({
  error: `No sprint on this site matches ${JSON.stringify(String(id))}`
    + (why ? ` — ${why}.` : '.'),
});
