/**
 * Runs the pure half of the Forge resolver over a synthetic Jira response and
 * prints what the bridge would put on the wire.
 *
 * `forge/src/index.js` cannot run outside Forge — it imports the SDK and talks
 * to Jira. `forge/src/jira.js` is deliberately free of both, so the shapes it
 * builds can be produced here with nothing but Node and compared, in
 * `tests/test_service.py`, against what `scripts/serve_live.py` really returns
 * over `api/contexts` and `api/context`. One contract, two transports; this is
 * the half of that claim a machine can check.
 *
 *     node tests/forge_shapes.mjs
 */

import {
  contextEntry, contextsBody, contextBody, contextId, findStoryPointField,
  mergeOrgConfig, parseContextId, issueFrom, notFound, recentSprints,
  statusesFromJira, validateOrgConfig,
  DEFAULT_WINDOW_DAYS, WINDOW_DAYS, windowEntry, windowToken,
} from '../forge/src/jira.js';

/* The configs the Python and this must agree about. Read from a file both
   suites use, so the two cannot be given different cases. */
import { readFileSync } from 'node:fs';
const CASES = JSON.parse(readFileSync(new URL('./fixtures/org-configs.json', import.meta.url)));

/* A Jira site's own statuses. "Signed off" is the case orgconfig.py was
   written for: a site with that column and no "Done" column read every sprint
   as 0% complete under a blanket list. Jira knows better — its admins put it
   in the done category — and that is what makes this the site's answer rather
   than ours. */
const siteStatuses = [
  { name: 'To Do', statusCategory: { key: 'new' } },
  { name: 'In Review', statusCategory: { key: 'indeterminate' } },
  { name: 'With QA', statusCategory: { key: 'indeterminate' } },
  { name: 'Signed off', statusCategory: { key: 'done' } },
  { name: 'Shipped', statusCategory: { key: 'done' } },
  { name: '', statusCategory: { key: 'done' } },
];

const SITE = 'https://example.atlassian.net';

const board = {
  id: 2,
  name: 'Storefront Delivery',
  location: { projectKey: 'SFT', projectName: 'Storefront' },
};

/** Deliberately out of order, and one more than the cap, so the sorting and
 *  the limit are both exercised rather than assumed. */
const sprints = [
  { id: 41, name: 'Sprint 22', state: 'closed', goal: '', startDate: '2026-06-08T09:00:00.000Z', endDate: '2026-06-19T17:00:00.000Z' },
  { id: 43, name: 'Sprint 24', state: 'active', goal: 'Checkout stability', startDate: '2026-08-03T09:00:00.000Z', endDate: '2026-08-14T17:00:00.000Z' },
  { id: 42, name: 'Sprint 23', state: 'closed', goal: '', startDate: '2026-07-06T09:00:00.000Z', endDate: '2026-07-17T17:00:00.000Z' },
];

/** Two issues, and the difference between them is the point: SFT-1 was put in
 *  the sprint after it began and SFT-2 before. `addedMidSprint` false by
 *  default is not a silence, it is the claim that nothing was added, and the
 *  health score reads it as full marks for scope stability. */
const rawIssues = [
  {
    key: 'SFT-1',
    fields: {
      summary: 'Checkout drops the basket on retry',
      issuetype: { name: 'Bug' },
      status: { name: 'In Progress' },
      assignee: { displayName: 'A. Patel' },
      priority: { name: 'Highest' },
      parent: { key: 'SFT-100', fields: { summary: 'Checkout stability' } },
      created: '2026-08-05T11:02:00.000Z',
      resolutiondate: null,
      duedate: '2026-08-14',
      labels: ['payments'],
      flagged: true,
      customfield_10034: 5,
    },
    changelog: {
      histories: [
        { created: '2026-08-06T09:00:00.000Z', items: [{ field: 'Sprint', toString: 'Sprint 24' }] },
      ],
    },
  },
  {
    key: 'SFT-2',
    fields: {
      summary: 'Cart abandonment email',
      issuetype: { name: 'Story' },
      status: { name: 'Done' },
      assignee: null,
      priority: { name: 'Medium' },
      parent: null,
      created: '2026-07-28T08:00:00.000Z',
      resolutiondate: '2026-08-11T16:30:00.000Z',
      duedate: null,
      labels: [],
      flagged: false,
      customfield_10034: 3,
    },
    changelog: {
      histories: [
        { created: '2026-08-03T09:30:00.000Z', items: [{ field: 'Sprint', toString: 'Sprint 24' }] },
        { created: '2026-08-11T16:30:00.000Z', items: [{ field: 'status', toString: 'Done' }] },
      ],
    },
  },
];

/* Deliberately NOT customfield_10016. The previous version hardcoded that id,
   which is the common one — so a fixture using it would have passed against
   the bug. This site calls the field something else, as real sites do. */
const SP_FIELD = 'customfield_10034';

/* Jira's own /rest/api/3/field, near enough: a decoy whose name merely
   contains the word, the real one further down the list, and a second
   candidate after it — the first match in Jira's order wins, and it has to be
   the same one the Python fetcher would pick. */
const fieldList = [
  { id: 'customfield_10011', name: 'Story Points History' },
  { id: 'summary', name: 'Summary' },
  { id: SP_FIELD, name: 'Story Points' },
  { id: 'customfield_10099', name: 'Points' },
];

const entries = recentSprints(sprints, 6).map((sp) => contextEntry(board, sp, 'SFT'));
const selected = entries[0];

/* The round trip the page really makes: `contexts` reads boards from the list
   endpoint, `context` re-reads one board on its own. The two responses do not
   always describe `location` the same way, and an id that stops matching
   between them turns every sprint into "unknown context" — which is exactly
   what the first install did. The module's project key is the same answer
   both times, so the ids must agree even when the second response has no
   location at all. */
const bareBoard = { id: 2, name: 'Storefront Delivery' };
const reread = contextEntry(bareBoard, sprints.find((sp) => sp.id === 43), 'SFT');

console.log(JSON.stringify({
  contexts: contextsBody('Jira, project SFT — 1 board', entries),
  context: contextBody(selected, rawIssues.map((r) => issueFrom(r, {
    sprintStart: selected.startDate,
    siteUrl: SITE,
    storyPointField: findStoryPointField(fieldList),
  }))),
  storyPointField: {
    found: findStoryPointField(fieldList),
    // A site with no such field at all. Points must come back null rather than
    // zero: an estimate nobody recorded and an estimate nobody could read are
    // different facts, and only one of them belongs in a burndown.
    absent: findStoryPointField([{ id: 'summary', name: 'Summary' }]),
    whenAbsent: issueFrom(rawIssues[0], { storyPointField: null }).storyPoints,
    whenPresent: issueFrom(rawIssues[0], { storyPointField: SP_FIELD }).storyPoints,
    // Jira permits a text field to be pointed at here. Coercing "M" to 0 would
    // put a made-up figure into the burndown.
    whenNotANumber: issueFrom(
      { key: 'X-1', fields: { [SP_FIELD]: 'M' } }, { storyPointField: SP_FIELD },
    ).storyPoints,
    whenUnset: issueFrom({ key: 'X-2', fields: {} }, { storyPointField: SP_FIELD }).storyPoints,
  },
  // The id is the string the page round-trips, so it is checked both ways.
  roundTrip: { id: contextId('SFT', 2, 43), parsed: parseContextId('SFT/2/43') },
  rejects: ['', 'SFT/2', 'SFT/2/43/extra', '../../etc', 'SFT/x/43',
    // A window the picker never offered. Refused rather than clamped or
    // honoured: `win:99999d` would pull an unbounded slice of a board through
    // an id no dropdown can produce.
    'SFT/2/win:99999d', 'SFT/2/win:31d', 'SFT/2/win:0d', 'SFT/2/win:30',
    'SFT/2/win:-30d', 'SFT/2/win:030d']
    .map((bad) => [bad, parseContextId(bad)]),

  /* What a flow board is offered instead of a sprint. `scripts/serve_live.py`
     builds the identical entry, and `tests/test_service.py` compares the two
     value by value rather than field set by field set — the boundaries below
     are there because that is where two languages' date arithmetic disagrees
     if it is going to, and a shape check would never see it. */
  window: {
    days: WINDOW_DAYS,
    defaultDays: DEFAULT_WINDOW_DAYS,
    token: windowToken(DEFAULT_WINDOW_DAYS),
    roundTrip: parseContextId(contextId('SFT', 2, windowToken(DEFAULT_WINDOW_DAYS))),
    entries: WINDOW_DAYS.map((d) => windowEntry(board, d, '2026-08-24', 'SFT')),
    boundaries: [['2026-03-01', 30], ['2026-01-01', 90], ['2026-03-02', 14],
                 ['2024-03-01', 30]]
      .map(([asOf, d]) => windowEntry(board, d, asOf, 'SFT')),
    // Same reread problem the sprint id has: `contexts` reads boards from the
    // list endpoint and `context` re-reads one on its own, and the two do not
    // always describe `location` the same way.
    fromBareBoard: windowEntry({ id: 2, name: 'Storefront Delivery' },
      DEFAULT_WINDOW_DAYS, '2026-08-24', 'SFT').id,
  },
  notFound: notFound('SFT/2/999'),
  cap: recentSprints(sprints, 2).map((s) => s.name),
  orgConfig: {
    fromJira: statusesFromJira(siteStatuses),
    // What the site states wins over what Jira knows, one level down — a
    // stated `done` list keeps Jira's `inProgress` rather than emptying it.
    merged: mergeOrgConfig(
      { statuses: statusesFromJira(siteStatuses) },
      { statuses: { done: ['Signed off'] }, workingWeek: ['sun', 'mon', 'tue', 'wed', 'thu'] },
    ),
    // Every case in the shared fixture, judged usable or not. tests/
    // test_service.py runs the identical list through orgconfig.validate and
    // asserts the two verdicts match.
    verdicts: CASES.map((c) => [c.name, validateOrgConfig(c.config).length === 0]),
  },
  idSurvivesReread: { asked: selected.id, rebuilt: reread.id },
}, null, 2));
