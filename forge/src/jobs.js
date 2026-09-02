/**
 * Sequencing as a job. ADR 0031.
 *
 * Sequencing is cubic in the ask count and runs for minutes on Forge's CPU —
 * twelve asks is three and a half — so it is the one route that no longer
 * fits a synchronous resolver call. The `sequence` resolver validates and
 * projects as it always did, pushes one async event carrying the projection,
 * and returns a job id; a consumer function computes under a 900-second
 * budget and writes its answer to app storage; the `sequenceResult` resolver
 * collects it; and the adapter in `forge/bridge/bridge.js` polls, so the page
 * still asks one question and gets one `{status, body}` back.
 *
 * This file is the pure half of that: the keys, the guards, the refusal
 * sentences and the state machine a poll walks. No SDK, no storage, no
 * network, so `tests/test_service.py` runs it under plain Node over a matrix
 * of rows and holds every outcome. `index.js` does the reads and writes.
 *
 * Two rows per job, and the split is deliberate:
 *
 *   seqjob:<id>      written once by the resolver — who asked, when, the
 *                    words held back from the payload (`text`), and the keys
 *                    the page's body gets around the tool's answer
 *   seqresult:<id>   written by the consumer as it moves through started,
 *                    done, refused or failed
 *
 * A single row would have the consumer's `set` overwrite what the resolver
 * wrote, or the consumer reading a row to merge into it, which is a race.
 * Both carry a one-hour TTL and both are deleted when the result is
 * collected. The job row is bound to the asking account and the poll refuses
 * any other, so ADR 0018's mirroring holds by a comparison rather than by the
 * entropy of a job id.
 *
 * `text` is the titles and value bases of the asks — customer words, kept out
 * of the event and out of the consumer, held in the app's own storage inside
 * the tenant for the life of the job so the collector can join them back on.
 * The same storage already holds a board's recipient list (ADR 0014).
 */
import { createHash } from 'node:crypto';

/** The queue the manifest's `consumer` module names. One literal, imported by
 *  the resolver, so a mistyped queue key fails here and not inside a tenant. */
export const QUEUE_KEY = 'sequence-jobs';

/** The route the consumer is allowed to run. It runs what the event names,
 *  and the event is this app's — but a consumer that would run any route is
 *  a consumer one bug away from running the wrong one. */
export const CONSUMER_ROUTE = '/v1/sequence';

/** Documented: the per-event payload limit once the consuming function's
 *  timeout exceeds 55 seconds. A call is about 16 KB and does not grow with
 *  the customer; this refuses rather than truncates if one ever does. */
export const MAX_EVENT_BYTES = 100 * 1024;

/** Both rows' TTL, in the shape `kvs.set` takes, and the same hour in
 *  milliseconds for the poll to check against the row's own timestamp —
 *  because an expired row may still be readable for 48 hours. */
export const JOB_TTL = { value: 1, unit: 'HOURS' };
export const JOB_LIFETIME_MS = 60 * 60 * 1000;

export const jobKey = (jobId) => `seqjob:${jobId}`;
export const resultKey = (jobId) => `seqresult:${jobId}`;

/** What a job id has to look like before it is used in a storage key. Forge
 *  issues them; the page only ever hands one back. */
export const JOB_ID = /^[A-Za-z0-9._:-]{1,120}$/;

/**
 * The key a reload joins on: this context, this exact projection, this
 * account. A second request with the same key while the first is running
 * collects the running job rather than pushing another — one computation,
 * two collectors. A different account, a different board, or a board that
 * changed under the reader is a different key and its own job.
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
  `seqinflight:${requestDigest(contextId, request, accountId)}`;

/** The refusal for a payload the platform would not carry, or null. */
export const tooLarge = (request) => {
  const bytes = Buffer.byteLength(JSON.stringify(request), 'utf8');
  if (bytes <= MAX_EVENT_BYTES) return null;
  return `This sequencing would carry ${Math.ceil(bytes / 1024)} KB to the job that runs it, `
       + `and the platform carries ${MAX_EVENT_BYTES / 1024} KB. Nothing was sequenced rather `
       + 'than part of the board: a comparison over some of the issues reads as a '
       + 'comparison over all of them. Mark fewer epics as candidates, or sequence a '
       + 'shorter period.';
};

/**
 * The retry guard. A consumer killed at its timeout is re-invoked forty
 * seconds later with `retryContext`, and again forty seconds after the next
 * kill, for a day. The job that did not finish in fifteen minutes will not
 * finish in fifteen more; the honest answer is a refusal in the row and no
 * computation, written before anything is loaded.
 */
export const retryRefusal = (retryContext) => {
  const reason = String(retryContext?.retryReason ?? 'unknown');
  const count = Number(retryContext?.retryCount ?? 1);
  const why = reason === 'FUNCTION_TIME_OUT'
    ? 'it did not finish inside the platform’s fifteen-minute budget'
    : `the platform stopped it (${reason})`;
  return `Sequencing was started and ${why}. It was offered again`
       + `${count > 1 ? ` for the ${count}${count === 2 ? 'nd' : count === 3 ? 'rd' : 'th'} time` : ''}`
       + ' and refused rather than run again: a job that did not finish once will not '
       + 'finish by being repeated. Nothing was sequenced. Mark fewer epics as candidates '
       + 'and sequence those.';
};

/** The sentence for a consumer that threw. The cause goes to the app's log,
 *  never to the row: a traceback carries field values, and those are the
 *  customer's. */
export const FAILED_SENTENCE =
  'Sequencing failed inside the app before it finished, and nothing partial was '
  + 'returned. Reload to try again; the app’s own log says why.';

/** The refusal for an event naming a route the consumer does not run. */
export const wrongRoute = (route) =>
  `The sequencing job was asked to run ${JSON.stringify(route ?? null)}, and it runs `
  + `${CONSUMER_ROUTE} only. Nothing was computed.`;

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

/** The job row the resolver writes once. */
export const jobRow = ({ jobId, accountId, contextId, key, text, envelope, now }) => ({
  jobId,
  accountId: accountId ?? null,
  contextId,
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

const refusal = (job, sentence) => ({ available: false, ...(job.envelope ?? {}), sentence });

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
 * `finished` is the caller's cue to delete both rows and the in-flight key.
 * Deleted on collection, not on expiry, because a result served from storage
 * without saying when it was computed is the quiet wrongness ADR 0017
 * exists to stop — and a reader who wants the figure again recomputes it,
 * seeded, to the same answer.
 */
export const collect = ({ job, result, accountId, now }) => {
  if (!job) {
    return {
      status: 404,
      finished: false,
      body: {
        error: 'No sequencing job with that id is held. It may have been collected '
             + 'already, or expired an hour after it started; reload to start it again.',
      },
    };
  }
  if ((job.accountId ?? null) !== (accountId ?? null)) {
    return {
      status: 403,
      finished: false,
      body: {
        error: 'This sequencing was started by another account and can only be '
             + 'collected by the one that started it. Nothing was returned.',
      },
    };
  }
  const createdAt = Date.parse(job.createdAt);
  if (!Number.isFinite(createdAt) || now - createdAt > JOB_LIFETIME_MS) {
    return {
      status: 410,
      finished: true,
      body: {
        error: 'This sequencing job is more than an hour old and its result is no '
             + 'longer held. Reload to start it again.',
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
    return { status: 200, finished: true, body: refusal(job, result.sentence ?? FAILED_SENTENCE) };
  }
  if (result.status === 'done') {
    const envelope = result.envelope ?? {};
    if (envelope.ok === false) {
      // The route refused — the same `{ok: false, error}` the hosted service
      // would have sent, carried the same way the resolver carried it.
      return { status: 200, finished: true, body: refusal(job, envelope.error) };
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
    body: refusal(job, `The sequencing job is in a state this app does not recognise `
                       + `(${JSON.stringify(result.status)}). Nothing was returned.`),
  };
};
