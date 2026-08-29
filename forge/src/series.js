/**
 * The durable sprint series. No Forge, no network, no storage.
 *
 * ADR 0015 has the argument. In one paragraph: a history row re-derives
 * correctly from Jira at any distance, because it is computed from dates that
 * do not move — so this is not a cache, and storing rows to make the page fast
 * would be a different decision with a different justification. Rows are
 * recorded because four things can make a later re-derivation disagree with
 * what was true, and none of them announces itself: an issue deleted, a
 * sprint's membership stripped by a reopen-and-reclose, a status recategorised
 * underneath the whole series, and a forecast that was published and is not
 * recoverable from anything.
 *
 * Everything here is a function of plain objects, so `tests/test_service.py`
 * can run it over the shapes a tenant will actually produce — including the
 * ones where a recorded row and a reconstruction disagree, which is the case
 * this module exists for.
 *
 * **This module decides what is kept. It decides nothing that is shown.** That
 * line was in the wrong place when this file was first written: `seriesNote`
 * lived here and counted rows into a sentence a reader reads — *"2 of these 3
 * sprints were rebuilt"* — which is a figure produced between a tool and a
 * reader, exactly what `CLAUDE.md` forbids, and it would have needed a second
 * implementation in Python the moment loopback answered the same route.
 *
 * So the merge, the disagreements and the note are `merge_series`,
 * `series_disagreements` and `series_note` in `agent/tools/metrics.py`, and
 * both transports get them from there. What is left here is storage policy and
 * validation: where a board's rows live, what a row may contain, and whether
 * this observation may be written at all. None of it is arithmetic and none of
 * it reaches a reader as a figure.
 *
 * `ROW_FIELDS` is mirrored in `metrics.py` and `tests/test_service.py` holds
 * the two lists together — a projection that admitted a field the tool did not
 * know about would store something nothing ever reads.
 */

/** The store's own shape version. Bumped when the *layout* changes, never
 *  because a row gained a field — a reader that finds an unknown field ignores
 *  it, and a reader that finds an unknown version refuses rather than guessing
 *  which half of the object it understands. */
export const SERIES_VERSION = 1;

/** One key per board. Not one per sprint: a board's series is read whole on
 *  every panel load and written on the rare occasions a sprint closes, so the
 *  read is the operation to make cheap. Not one key for everything either —
 *  two boards closing sprints in the same hour would then be two writers of one
 *  value, and the loser's row is lost with nothing to say so. */
export const seriesKey = (boardId) => `series:${String(boardId)}`;

/**
 * The only fields a stored row may carry.
 *
 * An allow-list, for the same reason as the projections in `people.js`: this
 * object is assembled from something derived from issues, and a deny-list is
 * one upstream change away from putting an issue summary into the app's own
 * store. Everything here is a count, a ratio, a currency total or a sprint
 * name. Nothing here is anything a reader could be denied sight of, which is
 * what keeps this off item 5's critical path.
 */
export const ROW_FIELDS = Object.freeze([
  'sprint',
  'committedSP', 'completedSP',
  'committedItems', 'completedItems', 'throughput',
  'wipItems', 'unplannedItems',
  'flowEfficiency', 'valueDelivered',
]);

/** The re-derivable fields, which is every count except the sprint's name.
 *  Comparing a recorded row against a re-derived one happens in
 *  `metrics.series_disagreements`, not here — see the header. */
const COMPARED = ROW_FIELDS.filter((f) => f !== 'sprint');

const isFiniteNumber = (v) => typeof v === 'number' && Number.isFinite(v);

/** The two fields the derivation is entitled to leave null, and why.
 *
 *  `flowEfficiency` is null when there is no lead time to divide by — a refusal
 *  to state a ratio rather than a gap in the row.
 *
 *  `valueDelivered` is null when nothing in the issue set carried a business
 *  value at all, which is every Forge tenant: Jira has no native value field,
 *  and the calculator is never sent one because `CALC_FIELDS` does not include
 *  it. Zero there would say the sprint delivered nothing worth anything, which
 *  is a much stronger claim than nobody having told us. A set that carries the
 *  field and sums to zero keeps its zero.
 *
 *  A null anywhere else is a row that should not be stored. */
const NULLABLE = new Set(['flowEfficiency', 'valueDelivered']);

/**
 * A row reduced to the fields above, with everything else dropped.
 */
export const rowProjection = (row) => {
  const out = {};
  if (!row || typeof row !== 'object') return out;
  for (const f of ROW_FIELDS) {
    if (row[f] !== undefined) out[f] = row[f];
  }
  return out;
};

/**
 * What is wrong with one row, as sentences. Empty means storable.
 *
 * Checked before writing rather than after reading, because a bad row in the
 * store is read by every panel load from then on, and the panel is not where
 * anybody wants to discover it.
 */
export const problemsInRow = (row) => {
  const out = [];
  const r = row && typeof row === 'object' ? row : null;
  if (!r) return ['the row is not an object.'];

  if (typeof r.sprint !== 'string' || !r.sprint.trim()) {
    out.push('the row has no sprint name, so nothing can be labelled with it.');
  }
  for (const f of COMPARED) {
    const v = r[f];
    if (v === null && NULLABLE.has(f)) continue;
    if (!isFiniteNumber(v)) {
      out.push(`${f} is ${v === undefined ? 'missing' : JSON.stringify(v)}, and every figure in a stored row must be a number — a row with a gap in it reads as a zero on a chart.`);
    }
  }
  // Not a range check on each count, which would be arbitrary, but the one
  // relation that is definitional: you cannot complete more than was in the
  // sprint. A row failing this was computed over the wrong slice, and the wrong
  // slice is this repository's most expensive class of bug.
  if (isFiniteNumber(r.completedItems) && isFiniteNumber(r.committedItems)
      && isFiniteNumber(r.unplannedItems)
      && r.completedItems > r.committedItems + r.unplannedItems) {
    out.push('more items completed than the sprint ever contained, so this row was computed over a different set of issues than it claims.');
  }
  const extra = Object.keys(r).filter((k) => !ROW_FIELDS.includes(k));
  if (extra.length) {
    out.push(`the row carries ${extra.join(', ')}, which the store does not hold — it keeps counts, never anything derived from issue text.`);
  }
  return out;
};

/**
 * A fingerprint of the status configuration a row was computed under.
 *
 * This is the fourth hazard in ADR 0015 and the only one this product can
 * detect. `started` is not a field Jira keeps; it is an issue's changelog
 * replayed through whichever statuses the configuration in force calls In
 * Progress. Recategorise one and every `wipItems` and `flowEfficiency` in the
 * series moves, retroactively, with no event marking it.
 *
 * Storing the fingerprint beside the row does not prevent that. It makes it
 * *visible*: a recorded row whose fingerprint differs from today's was computed
 * under a different idea of the word, and a reader comparing it against a
 * recent sprint is comparing two measurements, not one series.
 *
 * Order-insensitive and case-insensitive, because neither changes the meaning
 * and both change a naive join — a configuration re-saved with its statuses in
 * a different order would otherwise read as a change to what they mean.
 */
export const statusFingerprint = (orgConfig) => {
  const s = (orgConfig && orgConfig.statuses) || {};
  const part = (v) => (Array.isArray(v) ? v : [])
    .filter((x) => typeof x === 'string')
    .map((x) => x.trim().toLowerCase())
    .filter(Boolean)
    .sort()
    .join(',');
  return `done=${part(s.done)}|prog=${part(s.inProgress)}`;
};

/**
 * May this observation be written, and if not, why not.
 *
 * The rule ADR 0015 settles, in code. A row is *recorded* when the app saw the
 * sprint for itself; a row derived later, for a sprint that closed before the
 * app was installed, is a *reconstruction* and is never written. The difference
 * is not the row — on most sites they are identical — it is the warrant, and
 * writing a reconstruction into the store would launder one into the other and
 * make the series look complete from the day of install.
 *
 * So:
 *
 * - an **active** sprint may always be observed, and the observation replaces
 *   whatever was there. The row moves all week and the last one before the
 *   close is the useful one.
 * - a **closed** sprint may be observed only if we were already watching it.
 *   That is the whole test: a prior observation is the evidence that this
 *   installation saw the sprint run.
 * - a row already marked `final` is never rewritten. It was observed after the
 *   sprint closed, which is the best this can do, and a later observation of
 *   the same sprint has strictly less to go on.
 */
export const recordable = (entry, prior, seen) => {
  const state = entry && entry.sprintState;
  if (state !== 'active' && state !== 'closed') {
    return { record: false, why: `the sprint is ${state ? `"${state}"` : 'in no state this understands'}, which is neither running nor finished.` };
  }
  // A row is a fact about the board (ADR 0019), so a view that can see fewer of
  // the sprint's issues than the row already holds must not replace it — it
  // would overwrite a board fact with one reader's narrower version of it, and
  // every figure in the row would drop together in a way nothing could
  // distinguish from the team having delivered less.
  const before = prior && prior.issuesSeen;
  if (Number.isInteger(before) && Number.isInteger(seen) && seen < before) {
    return {
      record: false,
      why: `this view can see ${seen} of the sprint's issues and the row on file counts ${before}, so it would narrow a record of the whole board to one reader's part of it.`,
    };
  }
  if (prior && prior.final === true) {
    // The one exception, and it is the same rule read the other way: a view
    // that can see *more* than the row on file has more to go on, not less,
    // which is exactly the condition the sentence below denies. A row recorded
    // by a narrow reader is corrected the first time a wider one looks.
    if (Number.isInteger(before) && Number.isInteger(seen) && seen > before) {
      return { record: true, why: '' };
    }
    return { record: false, why: 'this sprint was already recorded after it closed, and a later look has less to go on, not more.' };
  }
  if (state === 'closed' && !prior) {
    return {
      record: false,
      why: 'this sprint closed before the app first saw this board, so its row is a reconstruction. It is shown, and it is not stored as though it had been observed.',
    };
  }
  return { record: true, why: '' };
};

/**
 * One stored entry, from an observation. Nothing derived here but the shape.
 *
 * `final` is the sprint's state at the moment of observation, not a judgement
 * about whether the row is good. A `final: true` row was seen after the sprint
 * closed; a `final: false` row is the last mid-flight look and says so, because
 * a reader is entitled to know the series' last point is a Wednesday rather
 * than a sprint end.
 */
export const entryFrom = (entry, row, observedOn, orgConfig, seen) => ({
  row: rowProjection(row),
  observedOn: observedOn || null,
  final: (entry && entry.sprintState) === 'closed',
  statuses: statusFingerprint(orgConfig),
  // How wide the view that produced this row was — a count, naming no issue.
  // Without it a row cannot say whether it is about the board or about one
  // reader's part of it, because every figure in the two versions differs in
  // exactly the same direction. ADR 0019.
  issuesSeen: Number.isInteger(seen) ? seen : null,
});

/** The store, with anything unreadable refused rather than half-read. A store
 *  this cannot parse is reported as absent — which produces a series of
 *  reconstructions and a sentence saying so, rather than a shorter series
 *  presented as complete. */
export const readSeries = (raw) => {
  if (!raw || typeof raw !== 'object') return { sprints: {}, problems: [] };
  if (raw.version !== SERIES_VERSION) {
    return {
      sprints: {},
      problems: [`the stored series is version ${JSON.stringify(raw.version)} and this app reads version ${SERIES_VERSION}, so none of it was used.`],
    };
  }
  const sprints = raw.sprints && typeof raw.sprints === 'object' ? raw.sprints : {};
  return { sprints, problems: [] };
};

/** The store, ready to write back, with one sprint's entry replaced. */
export const writeSeries = (existing, sprintId, entry) => ({
  version: SERIES_VERSION,
  sprints: { ...(existing.sprints || {}), [String(sprintId)]: entry },
});
