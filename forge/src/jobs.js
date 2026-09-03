/**
 * Simulations as jobs. ADR 0031, corrected 2026-09-03.
 *
 * Two routes run for longer than a resolver call may: sequencing, which is
 * cubic in the ask count and takes minutes, and the forecast, which walks
 * every one of 20,000 trials day by day until the open items complete — on a
 * board with a long, sparse history that is millions of draws and twelve
 * seconds on Forge's CPU, measured, against a fifteen-second adapter clock
 * with Jira reads around it. So both take the same shape. The resolver
 * validates and projects as it always did, writes the projection to storage,
 * pushes one event naming it, and returns a job id; a consumer function
 * computes under a 900-second budget and writes its answer to storage; the
 * `jobResult` resolver collects it; and the adapter in
 * `forge/bridge/bridge.js` polls, so the page still asks one question and
 * gets one `{status, body}` back.
 *
 * This file is the pure half of that: the keys, the guards, the refusal
 * sentences, the payload chunking and the state machine a poll walks. No SDK,
 * no storage, no network, so `tests/test_service.py` runs it under plain Node
 * over a matrix of rows and holds every outcome. `index.js` does the reads
 * and writes.
 *
 * Three kinds of row per job, and the split is deliberate:
 *
 *   jobpayload:<pid>:<n>  the projection, in chunks under the store's 240 KiB
 *                         value limit — written by the resolver, read once and
 *                         deleted by the consumer. A forecast carries a team's
 *                         whole history, which is past the event's 100 KB
 *                         limit on any real board; one path for both kinds.
 *   job:<id>              written once by the resolver — the kind, who asked,
 *                         when, the words held back from the payload (`text`),
 *                         and the keys the page's body gets around the answer
 *   jobresult:<id>        written by the consumer as it moves through started,
 *                         done, refused or failed
 *
 * A single row would have the consumer's `set` overwrite what the resolver
 * wrote, or the consumer reading a row to merge into it, which is a race.
 * All carry a one-hour TTL and all are deleted when the result is collected.
 * The job row is bound to the asking account and the poll refuses any other,
 * so ADR 0018's mirroring holds by a comparison rather than by the entropy of
 * a job id.
 *
 * `text` is the titles and value bases of the asks — customer words, kept out
 * of the event and out of the consumer, held in the app's own storage inside
 * the tenant for the life of the job so the collector can join them back on.
 * A forecast holds none: its at-risk items are re-read from Jira by key, as
 * the asking user, at collection, because a team's history is too many
 * titles for a row and too many to hold at all.
 */
import { createHash } from 'node:crypto';

/** The queue the manifest's `consumer` module names. One literal, imported by
 *  the resolver, so a mistyped queue key fails here and not inside a tenant. */
export const QUEUE_KEY = 'simulations';

/** The routes the consumer runs, and the kind each job is. It runs what the
 *  event names, and the event is this app's — but a consumer that would run
 *  any route is a consumer one bug away from running the wrong one. */
export const CONSUMER_ROUTES = ['/v1/sequence', '/v1/forecast-context'];
export const KIND_OF = { '/v1/sequence': 'sequence', '/v1/forecast-context': 'forecast' };

/** One chunk of payload, comfortably under the store's 240 KiB per value once
 *  the chunk is itself JSON-encoded inside a row. */
export const PAYLOAD_CHUNK_BYTES = 160 * 1024;

/** The most a projection may be — the hosted service's own body limit, so a
 *  body the calculator would have refused is refused here too, with a
 *  sentence. Twenty-six chunks. */
export const MAX_PAYLOAD_BYTES = 4 * 1024 * 1024;

/** All rows' TTL, in the shape `kvs.set` takes, and the same hour in
 *  milliseconds for the poll to check against the row's own timestamp —
 *  because an expired row may still be readable for 48 hours. */
export const JOB_TTL = { value: 1, unit: 'HOURS' };
export const JOB_LIFETIME_MS = 60 * 60 * 1000;

export const jobKey = (jobId) => `job:${jobId}`;
export const resultKey = (jobId) => `jobresult:${jobId}`;
export const payloadKey = (payloadId, n) => `jobpayload:${payloadId}:${n}`;

/** What a job id has to look like before it is used in a storage key. Forge
 *  issues them; the page only ever hands one back. */
export const JOB_ID = /^[A-Za-z0-9._:-]{1,120}$/;

/**
 * The key a reload joins on: this context, this exact projection, this
 * account. A second request with the same key while the first is running
 * collects the running job rather than pushing another — one computation,
 * two collectors. A different account, a different board, a different
 * question of the same board, or a board that changed under the reader is a
 * different key and its own job.
 */
const requestDigest = (contextId, request, accountId) => {
  const h = createHash('sha256');
  h.update(String(contextId ?? ''));
  h.update(' ');
  h.update(String(accountId ?? ''));
  h.update(' ');
  h.update(JSON.stringify(request));
  return h.digest('hex').slice(0, 32);
};
// One expression, so the store inventory in tests/test_service.py can read
// the key's prefix off this line the way it reads every other store's.
export const inflightKey = (contextId, request, accountId) =>
  `jobinflight:${requestDigest(contextId, request, accountId)}`;

const noun = (kind) => (kind === 'forecast' ? 'forecast' : 'sequencing');

/** The refusal for a payload the app would not hold, or null. */
export const tooLarge = (request, kind = 'sequence') => {
  const bytes = Buffer.byteLength(JSON.stringify(request), 'utf8');
  if (bytes <= MAX_PAYLOAD_BYTES) return null;
  return `This ${noun(kind)} would carry ${Math.ceil(bytes / 1024)} KB to the job that runs `
       + `it, and the app holds ${MAX_PAYLOAD_BYTES / 1048576} MB for one. Nothing was `
       + 'computed rather than part of the board: an answer over some of the issues '
       + 'reads as an answer over all of them. Select a shorter period.';
};

/** The projection as the strings the resolver writes, one row each. */
export const chunkPayload = (request) => {
  const text = JSON.stringify(request);
  const chunks = [];
  for (let i = 0; i < text.length; i += PAYLOAD_CHUNK_BYTES) {
    chunks.push(text.slice(i, i + PAYLOAD_CHUNK_BYTES));
  }
  return chunks;
};

/** The projection back, from the rows the consumer read, or a throw that
 *  names the gap — a payload short a chunk is a board short its issues. */
export const joinPayload = (rows, expected) => {
  if (rows.length !== expected || rows.some((r) => typeof r?.s !== 'string')) {
    const got = rows.filter((r) => typeof r?.s === 'string').length;
    throw new Error(`payload: ${got} of ${expected} chunks were readable`);
  }
  return JSON.parse(rows.map((r) => r.s).join(''));
};

/**
 * The retry guard. A consumer killed at its timeout is re-invoked forty
 * seconds later with `retryContext`, and again forty seconds after the next
 * kill, for a day. The job that did not finish in fifteen minutes will not
 * finish in fifteen more; the honest answer is a refusal in the row and no
 * computation, written before anything is loaded.
 */
export const retryRefusal = (retryContext, kind = 'sequence') => {
  const reason = String(retryContext?.retryReason ?? 'unknown');
  const count = Number(retryContext?.retryCount ?? 1);
  const why = reason === 'FUNCTION_TIME_OUT'
    ? 'it did not finish inside the platform’s fifteen-minute budget'
    : `the platform stopped it (${reason})`;
  const what = noun(kind);
  return `${what[0].toUpperCase()}${what.slice(1)} was started and ${why}. It was offered again`
       + `${count > 1 ? ` for the ${count}${count === 2 ? 'nd' : count === 3 ? 'rd' : 'th'} time` : ''}`
       + ' and refused rather than run again: a job that did not finish once will not '
       + `finish by being repeated. Nothing was computed.${kind === 'sequence'
         ? ' Mark fewer epics as candidates and sequence those.' : ' Select a shorter period.'}`;
};

/** The sentence for a consumer that threw. The cause goes to the app's log,
 *  never to the row: a traceback carries field values, and those are the
 *  customer's. */
export const failedSentence = (kind = 'sequence') =>
  `The ${noun(kind)} failed inside the app before it finished, and nothing partial `
  + 'was returned. Reload to try again; the app’s own log says why.';
export const FAILED_SENTENCE = failedSentence('sequence');

/** The refusal for an event naming a route the consumer does not run. */
export const wrongRoute = (route) =>
  `The job was asked to run ${JSON.stringify(route ?? null)}, and this consumer runs `
  + `${CONSUMER_ROUTES.join(' and ')} only. Nothing was computed.`;

/**
 * The forecast body a reader gets when nothing was simulated: the three
 * questions each refused with the same sentence, and the rest empty. The
 * shape the page reads for a refusal, unchanged from the resolver's own.
 */
export const forecastRefusal = (sentence) => ({
  sprint_completion: { available: false, reason: sentence },
  capacity_to_target: { available: false, reason: sentence },
  next_commitment: { available: false, reason: sentence },
  asked: {}, sampled_from: {}, inputs: {},
});

/**
 * Put the title and the basis back beside each ordering, by id.
 *
 * The tool answered with ids because that is all it was given. These are the
 * words that never left, joined on — a lookup, not a calculation, and the only
 * reason a reader sees a basis beside an ordering at all. Moved here from the
 * resolver because the join now happens on collection, not on the call.
 */
export const reattachAsks = (result, text) => {
  for (const ordering of result?.orderings ?? []) {
    for (const row of ordering.order ?? []) {
      const local = (text ?? {})[row.id];
      if (!local) continue;
      row.title = local.title;
      row.valueBasis = local.basis;
    }
  }
  for (const d of result?.deltas ?? []) {
    const local = (text ?? {})[d.first];
    if (local) d.title = local.title;
  }
  return result;
};

/** The issue keys a forecast names in its risk list — what the collector
 *  re-reads from Jira to put the titles back. Validated to Jira's key shape
 *  before any of them goes into a query. */
export const riskKeys = (result) => {
  const items = result?.item_risk?.items;
  if (!Array.isArray(items)) return [];
  return [...new Set(items.map((i) => i?.key).filter((k) => typeof k === 'string'
    && /^[A-Z][A-Z0-9_]*-\d+$/.test(k)))];
};

/** The job row the resolver writes once. */
export const jobRow = ({ jobId, kind, route, accountId, contextId, board, key, text, envelope, now }) => ({
  jobId,
  kind: kind ?? KIND_OF[route] ?? 'sequence',
  route,
  accountId: accountId ?? null,
  contextId,
  board: board ?? null,
  key,
  createdAt: new Date(now).toISOString(),
  text: text ?? {},
  envelope: envelope ?? {},
});

/** The result row the consumer writes as it goes. */
export const resultRow = (status, fields, now) => ({
  status,
  at: new Date(now).toISOString(),
  ...fields,
});

const refusal = (job, sentence) => (job.kind === 'forecast'
  ? forecastRefusal(sentence)
  : { available: false, ...(job.envelope ?? {}), sentence });

/**
 * One poll: what the page gets for this job, and whether the rows are done.
 *
 *   status  body                                   finished
 *   404     no such job                             no   (nothing to delete)
 *   403     another account's job                   no   (and it stays theirs)
 *   410     older than an hour                      yes
 *   202     { pending, jobId, stage, since }        no
 *   200     the tool's answer, or a refusal         yes
 *
 * `finished` is the caller's cue to delete the rows and the in-flight key.
 * Deleted on collection, not on expiry, because a result served from storage
 * without saying when it was computed is the quiet wrongness ADR 0017
 * exists to stop — and a reader who wants the figure again recomputes it,
 * seeded, to the same answer.
 *
 * A sequencing body is assembled here in full. A forecast body is the tool's
 * answer as computed; `index.js` puts the at-risk items' titles back from a
 * Jira read and writes the calibration log, both of which need the SDK.
 */
export const collect = ({ job, result, accountId, now }) => {
  if (!job) {
    return {
      status: 404,
      finished: false,
      body: {
        error: 'No job with that id is held. It may have been collected already, or '
             + 'expired an hour after it started; reload to start it again.',
      },
    };
  }
  if ((job.accountId ?? null) !== (accountId ?? null)) {
    return {
      status: 403,
      finished: false,
      body: {
        error: 'This job was started by another account and can only be collected '
             + 'by the one that started it. Nothing was returned.',
      },
    };
  }
  const createdAt = Date.parse(job.createdAt);
  if (!Number.isFinite(createdAt) || now - createdAt > JOB_LIFETIME_MS) {
    return {
      status: 410,
      finished: true,
      body: {
        error: 'This job is more than an hour old and its result is no longer held. '
             + 'Reload to start it again.',
      },
    };
  }
  if (!result || result.status === 'started') {
    return {
      status: 202,
      finished: false,
      body: {
        pending: true,
        jobId: job.jobId,
        stage: result ? result.status : 'queued',
        since: result?.at ?? job.createdAt,
      },
    };
  }
  if (result.status === 'refused' || result.status === 'failed') {
    return { status: 200, finished: true, body: refusal(job, result.sentence ?? failedSentence(job.kind)) };
  }
  if (result.status === 'done') {
    const envelope = result.envelope ?? {};
    if (envelope.ok === false) {
      // The route refused — the same `{ok: false, error}` the hosted service
      // would have sent, carried the same way the resolver carried it.
      return { status: 200, finished: true, body: refusal(job, envelope.error) };
    }
    if (job.kind === 'forecast') {
      return { status: 200, finished: true, body: envelope.result ?? {} };
    }
    // The tool's answer, refusal or figures, with the words joined back on
    // and the same keys around it `scripts/serve_live.py` adds. A tool
    // refusal (`available: false`) rides through here untouched.
    return {
      status: 200,
      finished: true,
      body: { ...reattachAsks(envelope.result ?? {}, job.text), ...(job.envelope ?? {}) },
    };
  }
  return {
    status: 200,
    finished: true,
    body: refusal(job, `The job is in a state this app does not recognise `
                       + `(${JSON.stringify(result.status)}). Nothing was returned.`),
  };
};
