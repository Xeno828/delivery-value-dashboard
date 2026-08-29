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
  windowMembershipJql, contextsLabel,
} from '../forge/src/jira.js';

/* The configs the Python and this must agree about. Read from a file both
   suites use, so the two cannot be given different cases. */
import {
  SERIES_VERSION, seriesKey, ROW_FIELDS, rowProjection, problemsInRow,
  statusFingerprint, recordable, entryFrom, readSeries, writeSeries,
} from '../forge/src/series.js';

import {
  AUDIT_EVENTS, AUDIT_FIELDS, MAX_AUDIT, appendAudit, auditEntry, auditNote,
  problemsInAuditEntry,
} from '../forge/src/audit.js';

import { readFileSync } from 'node:fs';
const CASES = JSON.parse(readFileSync(new URL('./fixtures/org-configs.json', import.meta.url)));
/* The series policy cases, run identically by scripts/serve_live.py. */
const SERIES_CASES = JSON.parse(readFileSync(new URL('./fixtures/series-cases.json', import.meta.url)));

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

const TODAY = '2026-08-10';
const entries = recentSprints(sprints, 6).map((sp) => contextEntry(board, sp, 'SFT', TODAY));
const selected = entries[0];

/* The round trip the page really makes: `contexts` reads boards from the list
   endpoint, `context` re-reads one board on its own. The two responses do not
   always describe `location` the same way, and an id that stops matching
   between them turns every sprint into "unknown context" — which is exactly
   what the first install did. The module's project key is the same answer
   both times, so the ids must agree even when the second response has no
   location at all. */
const bareBoard = { id: 2, name: 'Storefront Delivery' };
const reread = contextEntry(bareBoard, sprints.find((sp) => sp.id === 43), 'SFT', TODAY);


/* ---------------------------------------------------------------------------
   The durable sprint series — ADR 0015.

   What is checked here is storage policy and the projection, which is all this
   module now decides. The merge, the disagreements and the note moved to
   `agent/tools/metrics.py` when it became clear the note counts rows into a
   sentence a reader reads, and a figure produced between a tool and a reader is
   the thing this repository spends most of its tests preventing.
   --------------------------------------------------------------------------- */
const good = {
  sprint: 'Sprint 22', committedSP: 34, completedSP: 25,
  committedItems: 13, completedItems: 10, throughput: 10,
  wipItems: 3, unplannedItems: 2, flowEfficiency: 0.33, valueDelivered: 12000,
};
const STATUSES_NOW = { statuses: { done: ['Done', 'Shipped'], inProgress: ['In Progress', 'In Review'] } };

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
  /* The raw material for `started`, with the names undecided. The resolver
     will not say which of these is a start — that is organisation config —
     and the page applies its own rule to them, exactly as it does to a raw
     status name. The out-of-order history is the trap: Jira does not return
     the changelog in date order, so a page taking the *first* in-progress
     transition rather than the *earliest* would report a later start, a
     shorter cycle time and a higher flow efficiency. */
  statusTransitions: {
    fromFixture: issueFrom(rawIssues[1], {}).statusTransitions,
    outOfOrder: issueFrom({
      key: 'X-1',
      fields: {},
      changelog: {
        histories: [
          { created: '2026-08-06T09:00:00.000Z', items: [{ field: 'status', toString: 'In Review' }] },
          { created: '2026-08-04T09:00:00.000Z', items: [{ field: 'Sprint', toString: 'Sprint 24' }] },
          { created: '2026-08-05T10:00:00.000Z', items: [{ field: 'status', toString: 'With QA' }] },
          { created: '2026-08-09T10:00:00.000Z', items: [{ field: 'status', toString: 'Signed off' }] },
        ],
      },
    }, {}).statusTransitions,
    // No changelog at all is an empty list, not a missing key: a consumer
    // testing `Array.isArray` must not have to test for undefined as well.
    noChangelog: issueFrom({ key: 'X-2', fields: {} }, {}).statusTransitions,
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
    /* Which issues are in the window. The membership is the half of the query
       that decides every figure, so it is the half both transports must build
       identically — how each of them reaches a board is its own business. */
    jql: WINDOW_DAYS.map((d) => {
      const e = windowEntry(board, d, '2026-08-24', 'SFT');
      return [e.startDate, e.endDate, windowMembershipJql(e.startDate, e.endDate)];
    }),
  },

  /* The footer line, and the only thing between a picker quietly missing a
     board and a project that genuinely has none. Pure, so it is checked here
     rather than left to a deploy. */
  labels: {
    plain: contextsLabel({ projectKey: 'SFT', boards: 1 }),
    flow: contextsLabel({ projectKey: 'SFT', boards: 3, flowBoards: 1 }),
    unstarted: contextsLabel({ projectKey: 'SFT', boards: 3, sprintBoardsWithNoSprints: 2 }),
    both: contextsLabel({
      projectKey: 'SFT', boards: 4, flowBoards: 1, sprintBoardsWithNoSprints: 2,
      hasStoryPointField: false, statedCalendar: false,
    }),
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
  // The moment a sprint's figures are about, resolved as the fetcher resolves
  // it. It was null for every sprint, so a Forge series rested on `endDate`
  // alone and a sprint started without one produced no row.
  asOf: {
    active: contextEntry(board, { id: 9, name: 'Running', state: 'active',
      startDate: '2026-08-03T00:00:00Z', endDate: '2026-08-14T00:00:00Z' },
      'SFT', TODAY).asOfDate,
    // A running sprint nobody gave an end date. This is the shape that reached
    // a tenant and produced no row at all.
    activeNoEnd: contextEntry(board, { id: 10, name: 'Open ended', state: 'active',
      startDate: '2026-08-03T00:00:00Z' }, 'SFT', TODAY).asOfDate,
    // Closed sprints take the day they actually completed, not the day they
    // were planned to. The two differ whenever a sprint runs over.
    closed: contextEntry(board, { id: 11, name: 'Done late', state: 'closed',
      startDate: '2026-07-06T00:00:00Z', endDate: '2026-07-17T00:00:00Z',
      completeDate: '2026-07-21T09:12:00Z' }, 'SFT', TODAY).asOfDate,
    closedNoComplete: contextEntry(board, { id: 12, name: 'Done', state: 'closed',
      startDate: '2026-07-06T00:00:00Z', endDate: '2026-07-17T00:00:00Z' },
      'SFT', TODAY).asOfDate,
    closedNothing: contextEntry(board, { id: 13, name: 'Undated', state: 'closed' },
      'SFT', TODAY).asOfDate,
  },
  /* The operational log — ADR 0021. Entries are acts of this app with an
     authority already established, never a figure derived from issues, which
     is why none of it needed roadmap item 5. */
  audit: (() => {
    const at = '2026-08-29T09:00:00.000Z';
    const saved = auditEntry({ at, event: 'recipients.saved', actor: 'acct-1',
      boardId: 2, detail: { exec: 2, team: 1, anchorSet: true } });
    const many = { entries: Array.from({ length: MAX_AUDIT + 5 },
      (_, i) => ({ ...saved, actor: `a${i}` })), droppedTotal: 0 };
    const trimmed = appendAudit(many, saved);
    const again = appendAudit({ entries: trimmed.entries,
      droppedTotal: trimmed.droppedTotal }, saved);
    return {
      events: [...AUDIT_EVENTS],
      fields: [...AUDIT_FIELDS],
      max: MAX_AUDIT,
      saved,
      // An event nobody wrote the meaning of, and an entry with no time.
      unknownEvent: auditEntry({ at, event: 'something.happened', actor: 'a' }),
      noTime: auditEntry({ at: '', event: 'brief.sent', actor: 'a' }),
      // A scheduled run has no user and says so rather than borrowing one.
      noActor: auditEntry({ at, event: 'brief.sent', boardId: 2 }),
      problems: problemsInAuditEntry(saved),
      // detail keeps counts, flags and field names — never a recipient.
      identityDetail: problemsInAuditEntry({ ...saved,
        detail: { added: '712020:5ad8ac88' } }),
      extraField: problemsInAuditEntry({ ...saved, subject: 'Weekly brief' }),
      trimmed: { kept: trimmed.entries.length, over: trimmed.droppedTotal,
                 droppedTotal: trimmed.droppedTotal },
      trimmedAgain: { droppedTotal: again.droppedTotal },
      noteEmpty: auditNote({ entries: [], droppedTotal: 0 }),
      noteDropped: auditNote({ entries: [], droppedTotal: 12 }),
    };
  })(),
  series: {
    version: SERIES_VERSION,
    key: seriesKey(42),
    fields: ROW_FIELDS,
    // The projection is what keeps issue text out of the app's own store. An
    // allow-list, so whatever a caller hands it, only these survive.
    projected: Object.keys(rowProjection({
      ...good, summary: 'Inventory sync race condition oversells stock',
      assignee: 'A. Person', issues: ['SFT-1'],
    })),
    problems: {
      good: problemsInRow(good),
      missing: problemsInRow({ ...good, wipItems: undefined }),
      notANumber: problemsInRow({ ...good, completedItems: '10' }),
      nullEfficiency: problemsInRow({ ...good, flowEfficiency: null }),
      // Every Forge tenant. Jira has no value field and the calculator is never
      // sent one, so this arrives null and must not be refused — nor stored as
      // a zero, which would claim the sprint delivered nothing of worth.
      nullValue: problemsInRow({ ...good, valueDelivered: null }),
      nullCount: problemsInRow({ ...good, completedItems: null }),
      impossible: problemsInRow({ ...good, completedItems: 99 }),
      extra: problemsInRow({ ...good, summary: 'an issue title' }),
      notAnObject: problemsInRow('Sprint 22'),
    },
    // The shared case lists. tests/test_service.py runs the identical files
    // through the loopback server's mirrors and asserts the two agree.
    recordable: SERIES_CASES.recordable.map(
      (c) => [c.name, recordable({ sprintState: c.state }, c.prior,
                                 c.seen ?? undefined).record]),
    recordableWhy: SERIES_CASES.recordable
      .filter((c) => !c.record)
      .map((c) => [c.name, recordable({ sprintState: c.state }, c.prior,
                                      c.seen ?? undefined).why]),
    fingerprints: SERIES_CASES.fingerprints.map(
      (c) => [c.name, statusFingerprint(c.config)]),
    entry: entryFrom({ sprintState: 'closed' }, good, '2026-07-17', STATUSES_NOW, 22),
    midEntry: entryFrom({ sprintState: 'active' }, good, '2026-07-15', STATUSES_NOW, 22),
    read: {
      empty: readSeries(null),
      wrongVersion: readSeries({ version: 99, sprints: { 22: { row: good } } }),
      good: readSeries(writeSeries({ sprints: {} }, 'SFT/2/22',
        entryFrom({ sprintState: 'closed' }, good, '2026-07-17', STATUSES_NOW))),
    },
    written: writeSeries({ sprints: {} }, 'SFT/2/22',
      entryFrom({ sprintState: 'closed' }, good, '2026-07-17', STATUSES_NOW)),
  },
}, null, 2));
