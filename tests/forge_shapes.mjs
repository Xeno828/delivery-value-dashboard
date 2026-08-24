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
  contextEntry, contextsBody, contextBody, contextId, parseContextId,
  issueFrom, notFound, recentSprints,
} from '../forge/src/jira.js';

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
      customfield_10016: 5,
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
      customfield_10016: 3,
    },
    changelog: {
      histories: [
        { created: '2026-08-03T09:30:00.000Z', items: [{ field: 'Sprint', toString: 'Sprint 24' }] },
        { created: '2026-08-11T16:30:00.000Z', items: [{ field: 'status', toString: 'Done' }] },
      ],
    },
  },
];

const entries = recentSprints(sprints, 6).map((sp) => contextEntry(board, sp));
const selected = entries[0];

console.log(JSON.stringify({
  contexts: contextsBody('Jira, project SFT — 1 board', entries),
  context: contextBody(selected, rawIssues.map((r) => issueFrom(r, {
    sprintStart: selected.startDate,
    siteUrl: SITE,
  }))),
  // The id is the string the page round-trips, so it is checked both ways.
  roundTrip: { id: contextId('SFT', 2, 43), parsed: parseContextId('SFT/2/43') },
  rejects: ['', 'SFT/2', 'SFT/2/43/extra', '../../etc', 'SFT/x/43']
    .map((bad) => [bad, parseContextId(bad)]),
  notFound: notFound('SFT/2/999'),
  cap: recentSprints(sprints, 2).map((s) => s.name),
}, null, 2));
