/**
 * Runs the pure half of simulations-as-jobs — forge/src/jobs.js — over a
 * matrix of rows and prints every outcome, for tests/test_service.py to hold.
 *
 * `forge/src/index.js` cannot run outside Forge. `jobs.js` is deliberately
 * free of the SDK, so the state machine a poll walks, the guards, the payload
 * chunking and the sentences can be produced here with nothing but Node.
 * ADR 0031.
 *
 *     node tests/jobs_shapes.mjs
 */
import {
  CONSUMER_ROUTES, JOB_ID, JOB_LIFETIME_MS, JOB_TTL, KIND_OF, MAX_PAYLOAD_BYTES,
  PAYLOAD_CHUNK_BYTES, QUEUE_KEY, chunkPayload, collect, failedSentence, forecastRefusal,
  inflightKey, jobKey, jobRow, joinPayload, payloadKey, reattachAsks, resultKey, resultRow,
  retryRefusal, riskKeys, tooLarge, wrongRoute,
} from '../forge/src/jobs.js';

const NOW = Date.parse('2026-09-02T12:00:00Z');
const text = { E1: { title: 'Saved cards', basis: '1,900 abandonments' }, E2: { title: 'Search' } };
const envelope = {
  board: '42', boardName: 'Checkout', asks_considered: 2,
  setup: { candidate: 'on-screen' }, notes: { unreadable: [], delivered: [], unsized: [] },
};
const job = jobRow({
  jobId: 'job-1', route: '/v1/sequence', accountId: 'acc-A', contextId: 'BLC/42/S24',
  board: '42', key: 'jobinflight:abc', text, envelope, now: NOW - 30_000,
});
const fcJob = jobRow({
  jobId: 'job-2', route: '/v1/forecast-context', accountId: 'acc-A', contextId: 'BLC/42/S24',
  board: '42', key: 'jobinflight:def', text: {}, envelope: {}, now: NOW - 30_000,
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
const fcAnswer = {
  ok: true, calendar: 'five-day week', version: '1.0',
  result: {
    sprint_completion: { available: true, percentiles: { 85: '2026-10-01' } },
    item_risk: { items: [{ key: 'BLC-7' }, { key: 'BLC-9' }, { key: 'BLC-7' }, { key: 'not a key' }] },
    calibration: { added: 1, dropped: 0, log: [{ id: 'c1' }] },
    asked: { items: 9 }, sampled_from: {}, inputs: {},
  },
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
  'failed': collect({ job, result: resultRow('failed', { sentence: failedSentence('sequence') }, NOW), accountId: 'acc-A', now: NOW }),
  'unknown state': collect({ job, result: resultRow('teleported', {}, NOW), accountId: 'acc-A', now: NOW }),
  'forecast done': collect({
    job: fcJob, result: resultRow('done', { http: 200, envelope: JSON.parse(JSON.stringify(fcAnswer)) }, NOW),
    accountId: 'acc-A', now: NOW,
  }),
  'forecast route refused': collect({
    job: fcJob, result: resultRow('done', { http: 400, envelope: { ok: false, error: 'send "dataset.contexts" — the slice is chosen from them.' } }, NOW),
    accountId: 'acc-A', now: NOW,
  }),
  'forecast refused on retry': collect({
    job: fcJob, result: resultRow('refused', { sentence: retryRefusal({ retryCount: 1, retryReason: 'FUNCTION_TIME_OUT' }, 'forecast') }, NOW),
    accountId: 'acc-A', now: NOW,
  }),
  'forecast failed': collect({ job: fcJob, result: resultRow('failed', {}, NOW), accountId: 'acc-A', now: NOW }),
};

const small = { dataset: { issues: [{ key: 'K-1' }] }, asks: [{ id: 'E1' }] };
const issue = (i) => ({
  key: `K-${i}`, created: '2026-01-01', started: '2026-01-03', resolved: '2026-01-09',
  statusCategory: 'done', status: 'Done', storyPoints: 3, priority: 'Medium', flagged: false,
  addedMidSprint: false, contextId: 'BLC/42/S24', epicKey: `E-${i % 9}`, type: 'Story', isSubtask: false,
});
// A sprint's worth, a whole large board (what a forecast carries), and one
// that no board should be.
const realistic = { dataset: { issues: Array.from({ length: 120 }, (_, i) => issue(i)) }, asks: [{ id: 'E1' }, { id: 'E2' }] };
const big = { dataset: { issues: Array.from({ length: 4000 }, (_, i) => issue(i)) } };
const huge = { dataset: { issues: Array.from({ length: 16000 }, (_, i) => issue(i)) } };
const exactly = { pad: 'x'.repeat(MAX_PAYLOAD_BYTES - JSON.stringify({ pad: '' }).length) };
const overByOne = { pad: 'x'.repeat(MAX_PAYLOAD_BYTES - JSON.stringify({ pad: '' }).length + 1) };

const bigChunks = chunkPayload(big);
let shortJoin = null;
try { joinPayload(bigChunks.slice(1).map((s) => ({ s })), bigChunks.length); } catch (e) { shortJoin = String(e.message); }

console.log(JSON.stringify({
  constants: {
    QUEUE_KEY, CONSUMER_ROUTES, KIND_OF, MAX_PAYLOAD_BYTES, PAYLOAD_CHUNK_BYTES, JOB_TTL,
    JOB_LIFETIME_MS, JOB_ID: JOB_ID.source,
  },
  keys: { job: jobKey('job-1'), result: resultKey('job-1'), payload: payloadKey('p-1', 3) },
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
    big: tooLarge(big, 'forecast'),
    bigBytes: Buffer.byteLength(JSON.stringify(big)),
    huge: tooLarge(huge, 'forecast'),
    hugeBytes: Buffer.byteLength(JSON.stringify(huge)),
    exactly: tooLarge(exactly),
    overByOne: tooLarge(overByOne),
  },
  chunks: {
    bigCount: bigChunks.length,
    bigMaxRow: Math.max(...bigChunks.map((s) => Buffer.byteLength(JSON.stringify({ s })))),
    roundTrip: JSON.stringify(joinPayload(bigChunks.map((s) => ({ s })), bigChunks.length)) === JSON.stringify(big),
    smallCount: chunkPayload(small).length,
    shortJoin,
  },
  retry: {
    timeout: retryRefusal({ retryCount: 1, retryReason: 'FUNCTION_TIME_OUT' }),
    second: retryRefusal({ retryCount: 2, retryReason: 'FUNCTION_TIME_OUT' }),
    other: retryRefusal({ retryCount: 1, retryReason: 'FUNCTION_OUT_OF_MEMORY' }),
    forecast: retryRefusal({ retryCount: 1, retryReason: 'FUNCTION_TIME_OUT' }, 'forecast'),
  },
  failed: { sequence: failedSentence('sequence'), forecast: failedSentence('forecast') },
  wrongRoute: wrongRoute('/v1/facts'),
  forecastRefusal: forecastRefusal('why'),
  riskKeys: riskKeys(fcAnswer.result),
  reattach: reattachAsks(JSON.parse(JSON.stringify(answer.result)), text),
  jobIdAccepts: ['a1b2c3-d4', '01234567-89ab-cdef-0123-456789abcdef', '../x', 'x y', '', 'a'.repeat(121)]
    .map((s) => [s, JOB_ID.test(s)]),
  outcomes,
}, null, 1));
