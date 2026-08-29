/**
 * What this app did, and who asked for it. No Forge, no network, no storage.
 *
 * Roadmap item 6's audit log, and ADR 0021 is explicit about which half of that
 * word this is. **It is operational, not a compliance artefact.** An app writing
 * its own log into its own storage, which it can also rewrite, is not
 * tamper-evident, and no amount of care here makes it so — Jira's audit API is
 * read-only (`GET /rest/api/2/auditing/record`, Administer Jira), so there is
 * no write path into a log this app cannot alter. Saying that plainly is worth
 * more than a log that implies otherwise.
 *
 * What it is good for is the question an administrator actually asks: *when did
 * the recipient list change, who changed it, and did last Monday's brief go
 * out?* Every one of those is an act of this app with an authority already
 * established — a project administrator, checked by `permissions.js` and
 * re-checked on the write, or the scheduled trigger. None of them is a figure
 * derived from issues, which is why this needed none of roadmap item 5.
 */

/** The only fields an entry may carry. An allow-list, like every other store
 *  here: this is written from paths that hold recipient ids and issue-derived
 *  figures, and a deny-list is one edit away from keeping either. */
export const AUDIT_FIELDS = Object.freeze([
  'at', 'event', 'actor', 'boardId', 'detail',
]);

/** The events this log knows. A closed set, so an entry whose meaning nobody
 *  wrote down cannot be appended — a log with unexplained rows in it is read
 *  by guessing, which is the opposite of the point. */
export const AUDIT_EVENTS = Object.freeze([
  'recipients.saved',
  'recipients.cleared',
  'brief.sent',
  'brief.refused',
]);

/** How many entries are kept. Deliberately larger than the forecast log's
 *  bound: these are rare — a configuration change and a weekly send — so a
 *  thousand is years of them, and the cost of keeping them is a stored value
 *  nobody reads on the hot path. */
export const MAX_AUDIT = 1000;

/** One key per installation, not per board. A recipient save writes the whole
 *  configuration across every board at once, so per-board keys would split one
 *  act into several rows that only look like several acts. */
export const AUDIT_KEY = 'audit';

const isCount = (v) => Number.isInteger(v) && v >= 0;

/**
 * One entry, or null when it would be a row nobody could read.
 *
 * `detail` is **counts and field names only**. What the list is *now* is on the
 * tile, always, for anybody who can open it; what this answers is when it
 * changed and who changed it. Keeping the ids of everyone ever added would
 * grow a store with identities to answer a question the tile already answers,
 * which is a poor trade — and it is a decision that can be taken later without
 * unpicking this one. ADR 0021.
 *
 * `actor` is the one identity here and it is unavoidable: an audit entry
 * without an actor records that something happened and not who did it.
 */
export const auditEntry = ({ at, event, actor, boardId, detail }) => {
  if (!AUDIT_EVENTS.includes(event)) return null;
  if (typeof at !== 'string' || !at.trim()) return null;
  return {
    at,
    event,
    // The scheduled trigger has no user, and says so rather than borrowing one.
    actor: typeof actor === 'string' && actor.trim() ? actor.trim() : 'schedule',
    boardId: boardId == null ? null : String(boardId),
    detail: detail && typeof detail === 'object' ? detail : {},
  };
};

/**
 * What is wrong with an entry, as sentences. Empty means storable.
 *
 * Same shape as every other store's validator, and for the same reason: a bad
 * row is read by everybody who opens the log from then on, and a log is
 * precisely the thing nobody re-checks.
 */
export const problemsInAuditEntry = (e) => {
  const out = [];
  if (!e || typeof e !== 'object') return ['the entry is not an object.'];
  if (!AUDIT_EVENTS.includes(e.event)) {
    out.push(`event is ${JSON.stringify(e.event)}, which is not one this log knows — an entry nobody wrote down the meaning of is read by guessing.`);
  }
  if (typeof e.at !== 'string' || !e.at.trim()) {
    out.push('at is missing, and an entry with no time is not an audit entry.');
  }
  if (typeof e.actor !== 'string' || !e.actor.trim()) {
    out.push('actor is missing, so this records that something happened and not who did it.');
  }
  const extra = Object.keys(e).filter((k) => !AUDIT_FIELDS.includes(k));
  if (extra.length) {
    out.push(`the entry carries ${extra.join(', ')}, which this log does not hold.`);
  }
  // Counts and field names. Anything else is either an identity nobody decided
  // to keep or a figure derived from issues, and neither belongs in a store
  // that grows without bound.
  const d = e.detail || {};
  const bad = Object.entries(d).filter(([, v]) =>
    !(isCount(v) || typeof v === 'boolean'
      || (Array.isArray(v) && v.every((x) => typeof x === 'string'))));
  if (bad.length) {
    out.push(`detail.${bad[0][0]} is ${JSON.stringify(bad[0][1])}; this log keeps counts, flags and field names.`);
  }
  return out;
};

/**
 * The log with one entry appended, bounded, and **saying what it forgot**.
 *
 * `droppedTotal` is cumulative and lives in the store, not in the answer to one
 * read. That is the difference between a log that admits it is a window and a
 * log that quietly becomes one: a reader who arrives after the ten thousandth
 * event should be told that 9,000 rows are gone, not shown a tidy thousand.
 * An audit log that silently forgets is worse than no audit log, because the
 * absence of a row reads as the absence of the event.
 */
export const appendAudit = (stored, entry, keep = MAX_AUDIT) => {
  const held = stored && typeof stored === 'object' ? stored : {};
  const entries = Array.isArray(held.entries) ? held.entries : [];
  const problems = problemsInAuditEntry(entry);
  if (problems.length) {
    return { entries, droppedTotal: held.droppedTotal || 0, problems, wrote: false };
  }
  const next = entries.concat([entry]);
  const over = Math.max(next.length - keep, 0);
  return {
    entries: over ? next.slice(over) : next,
    droppedTotal: (held.droppedTotal || 0) + over,
    problems: [],
    wrote: true,
  };
};

/** What the tile says above the rows. Silent unless something is missing from
 *  them — the rows speak for themselves, and a count of visible rows over a
 *  visible list is noise. */
export const auditNote = (stored) => {
  const gone = (stored && stored.droppedTotal) || 0;
  if (!gone) return '';
  return `${gone} older ${gone === 1 ? 'entry has' : 'entries have'} been dropped `
    + `to keep this log bounded, and ${gone === 1 ? 'it is' : 'they are'} not `
    + 'recoverable. This log is operational rather than a compliance record; it '
    + 'is written by this app into its own storage and nothing outside the app '
    + 'can attest to it.';
};
