/**
 * Runs the pure half of sequencing-as-a-job — forge/src/jobs.js — over a
 * matrix of rows and prints every outcome, for tests/test_service.py to hold.
 *
 * `forge/src/index.js` cannot run outside Forge. `jobs.js` is deliberately
 * free of the SDK, so the state machine a poll walks, the guards and the
 * sentences can be produced here with nothing but Node. ADR 0031.
 *
 *     node tests/jobs_shapes.mjs
 */
import {
  CONSUMER_ROUTE, FAILED_SENTENCE, JOB_ID, JOB_LIFETIME_MS, JOB_TTL, MAX_EVENT_BYTES,
  QUEUE_KEY, collect, inflightKey, jobKey, jobRow, reattachAsks, resultKey, resultRow,
  retryRefusal, tooLarge, wrongRoute,
} from '../forge/src/jobs.js';

const NOW = Date.parse('2026-09-02T12:00:00Z');
const text = { E1: { title: 'Saved cards', basis: '1,900 abandonments' }, E2: { title: 'Search' } };
const envelope = {
  board: '42', boardName: 'Checkout', asks_considered: 2,
  setup: { candidate: 'on-screen' }, notes: { unreadable: [], delivered: [], unsized: [] },
};
const job = jobRow({
  jobId: 'job-1', accountId: 'acc-A', contextId: 'BLC/42/S24', key: 'seqinflight:abc',
  text, envelope, now: NOW - 30_000,
});
const answer = {
  ok: true, calendar: 'five-day week', version: '1.0',
  result: {
    available: true,
    orderings: [{ first: 'E1', order: [{ id: 'E1', p85_days: 12 }, { id: 'E2', p85_days: 30 }] }],
    comparison: [{ first: 'E1', delays_others_by_days: 3 }],
  },
};
const toolRefusal = {
  ok: true, calendar: 'five-day week', version: '1.0',
  result: { available: false, sentence: 'Sequencing needs at least two sizeable asks; 2 supplied, 2 skipped.', skipped: [] },
};

const outcomes = {
  'no job': collect({ job: null, result: null, accountId: 'acc-A', now: NOW }),
  'another account': collect({ job, result: null, accountId: 'acc-B', now: NOW }),
  'no account at all': collect({ job, result: null, accountId: null, now: NOW }),
  'queued': collect({ job, result: null, accountId: 'acc-A', now: NOW }),
  'started': collect({ job, result: resultRow('started', {}, NOW - 10_000), accountId: 'acc-A', now: NOW }),
  'expired': collect({ job, result: resultRow('started', {}, NOW), accountId: 'acc-A', now: NOW + JOB_LIFETIME_MS + 1 }),
  'done': collect({
    job: JSON.parse(JSON.stringify(job)),
    result: resultRow('done', { http: 200, envelope: JSON.parse(JSON.stringify(answer)) }, NOW),
    accountId: 'acc-A', now: NOW,
  }),
  'done, tool refused': collect({
    job, result: resultRow('done', { http: 200, envelope: toolRefusal }, NOW), accountId: 'acc-A', now: NOW,
  }),
  'done, route refused': collect({
    job, result: resultRow('done', { http: 413, envelope: { ok: false, error: '13 asks is more than the 12 one sequencing compares.' } }, NOW),
    accountId: 'acc-A', now: NOW,
  }),
  'refused on retry': collect({
    job, result: resultRow('refused', { sentence: retryRefusal({ retryCount: 1, retryReason: 'FUNCTION_TIME_OUT' }) }, NOW),
    accountId: 'acc-A', now: NOW,
  }),
  'failed': collect({ job, result: resultRow('failed', { sentence: FAILED_SENTENCE }, NOW), accountId: 'acc-A', now: NOW }),
  'unknown state': collect({ job, result: resultRow('teleported', {}, NOW), accountId: 'acc-A', now: NOW }),
};

const small = { dataset: { issues: [{ key: 'K-1' }] }, asks: [{ id: 'E1' }] };
const issue = (i) => ({
  key: `K-${i}`, created: '2026-01-01', started: '2026-01-03', resolved: '2026-01-09',
  statusCategory: 'done', status: 'Done', storyPoints: 3, priority: 'Medium', flagged: false,
  addedMidSprint: false, contextId: 'BLC/42/S24', epicKey: `E-${i % 9}`, type: 'Story', isSubtask: false,
});
// A sprint's worth — what the sequence resolver actually sends, every field
// a projection can carry — and a whole large board, which it never does.
const realistic = { dataset: { issues: Array.from({ length: 120 }, (_, i) => issue(i)) }, asks: [{ id: 'E1' }, { id: 'E2' }] };
const big = { dataset: { issues: Array.from({ length: 4000 }, (_, i) => issue(i)) } };
const exactly = { pad: 'x'.repeat(MAX_EVENT_BYTES - JSON.stringify({ pad: '' }).length) };
const overByOne = { pad: 'x'.repeat(MAX_EVENT_BYTES - JSON.stringify({ pad: '' }).length + 1) };

console.log(JSON.stringify({
  constants: { QUEUE_KEY, CONSUMER_ROUTE, MAX_EVENT_BYTES, JOB_TTL, JOB_LIFETIME_MS, JOB_ID: JOB_ID.source },
  keys: { job: jobKey('job-1'), result: resultKey('job-1') },
  inflight: {
    same: inflightKey('BLC/42/S24', small, 'acc-A') === inflightKey('BLC/42/S24', small, 'acc-A'),
    otherAccount: inflightKey('BLC/42/S24', small, 'acc-A') !== inflightKey('BLC/42/S24', small, 'acc-B'),
    otherContext: inflightKey('BLC/42/S24', small, 'acc-A') !== inflightKey('BLC/42/S25', small, 'acc-A'),
    otherBody: inflightKey('BLC/42/S24', small, 'acc-A') !== inflightKey('BLC/42/S24', big, 'acc-A'),
    example: inflightKey('BLC/42/S24', small, 'acc-A'),
  },
  tooLarge: {
    small: tooLarge(small),
    realistic: tooLarge(realistic),
    realisticBytes: Buffer.byteLength(JSON.stringify(realistic)),
    big: tooLarge(big),
    bigBytes: Buffer.byteLength(JSON.stringify(big)),
    exactly: tooLarge(exactly),
    overByOne: tooLarge(overByOne),
  },
  retry: {
    timeout: retryRefusal({ retryCount: 1, retryReason: 'FUNCTION_TIME_OUT' }),
    second: retryRefusal({ retryCount: 2, retryReason: 'FUNCTION_TIME_OUT' }),
    other: retryRefusal({ retryCount: 1, retryReason: 'FUNCTION_OUT_OF_MEMORY' }),
  },
  wrongRoute: wrongRoute('/v1/forecast'),
  reattach: reattachAsks(JSON.parse(JSON.stringify(answer.result)), text),
  jobIdAccepts: ['a1b2c3-d4', '01234567-89ab-cdef-0123-456789abcdef', '../x', 'x y', '', 'a'.repeat(121)]
    .map((s) => [s, JOB_ID.test(s)]),
  outcomes,
}, null, 1));
