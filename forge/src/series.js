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
 * **Nothing here computes a row.** `history_row()` in `agent/tools/metrics.py`
 * does that, and on Forge it runs in the calculator, because a resolver that
 * derived its own figures would be the second implementation `CLAUDE.md`
 * forbids. This module decides what is kept, what may be written, and how a
 * kept row and a re-derived one are presented side by side.
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

/** The re-derivable fields, which is every count except the sprint's name. A
 *  recorded row and a reconstruction are compared on exactly these — see
 *  `disagreements`. */
const COMPARED = ROW_FIELDS.filter((f) => f !== 'sprint');

const isFiniteNumber = (v) => typeof v === 'number' && Number.isFinite(v);

/**
 * A row reduced to the fields above, with everything else dropped.
 *
 * `flowEfficiency` is allowed to be null and nothing else is: it is the one
 * figure the derivation itself declines to state when there is no lead time to
 * divide by, and a null there is a refusal rather than a gap. A null in any
 * other position is a row that should not be stored, and `problemsInRow` says
 * so rather than this function quietly substituting a zero.
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
    if (v === null && f === 'flowEfficiency') continue;
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
export const recordable = (entry, prior) => {
  const state = entry && entry.sprintState;
  if (state !== 'active' && state !== 'closed') {
    return { record: false, why: `the sprint is ${state ? `"${state}"` : 'in no state this understands'}, which is neither running nor finished.` };
  }
  if (prior && prior.final === true) {
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
export const entryFrom = (entry, row, observedOn, orgConfig) => ({
  row: rowProjection(row),
  observedOn: observedOn || null,
  final: (entry && entry.sprintState) === 'closed',
  statuses: statusFingerprint(orgConfig),
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

/**
 * Where a recorded row and a re-derived one disagree, by field.
 *
 * Every field compared is one that is supposed to re-derive identically, so a
 * disagreement is never noise — it is one of ADR 0015's four hazards having
 * happened to that sprint, and which field moved says a great deal about which
 * one it was. Commitment falling is a stripped sprint membership or a deleted
 * issue; work in progress moving with commitment unchanged is a status
 * recategorised underneath it.
 *
 * `flowEfficiency` is compared with a tolerance because it is a rounded ratio
 * and two roundings of the same quantity differ in the last place. Nothing else
 * is: these are counts, and a count that is off by one is off by one.
 */
export const disagreements = (recorded, reconstructed) => {
  const out = [];
  if (!recorded || !reconstructed) return out;
  for (const f of COMPARED) {
    const a = recorded[f];
    const b = reconstructed[f];
    if (a === undefined || b === undefined) continue;
    if (a === null && b === null) continue;
    if (f === 'flowEfficiency') {
      if (isFiniteNumber(a) && isFiniteNumber(b) && Math.abs(a - b) > 0.011) {
        out.push({ field: f, recorded: a, reconstructed: b });
      } else if ((a === null) !== (b === null)) {
        out.push({ field: f, recorded: a, reconstructed: b });
      }
      continue;
    }
    if (a !== b) out.push({ field: f, recorded: a, reconstructed: b });
  }
  return out;
};

/**
 * The series the page reads: recorded rows where we have them, reconstructions
 * where we do not, each saying which it is.
 *
 * `reconstructed` arrives in the order the sprints run and that order is kept,
 * because it is a chart's x-axis. A recorded row substitutes for the
 * reconstruction at the same position — it does not append, and it does not
 * reorder — so a series with one recorded sprint in the middle is still one
 * series.
 *
 * A recorded sprint that is not in `reconstructed` at all is **dropped, and
 * counted in the note**. It is a sprint this board no longer offers — deleted,
 * or moved to another board — and splicing it back in at a guessed position
 * would put a point on a chart at a date nothing else agrees with.
 */
export const mergeSeries = (stored, reconstructed, todayStatuses) => {
  const sprints = (stored && stored.sprints) || {};
  const list = Array.isArray(reconstructed) ? reconstructed : [];
  const seen = new Set();

  const rows = list.map(({ sprintId, row }) => {
    const key = String(sprintId);
    const kept = sprints[key];
    seen.add(key);
    if (!kept || !kept.row) {
      return { ...rowProjection(row), source: 'reconstructed' };
    }
    return {
      ...kept.row,
      source: 'recorded',
      observedOn: kept.observedOn || null,
      // Stated on the row rather than only in a note, because a chart may show
      // one sprint at a time and the note is above all of them.
      atSprintEnd: kept.final === true,
      differs: disagreements(kept.row, rowProjection(row)).map((d) => d.field),
      // Computed under a different idea of "in progress" than today's. Not an
      // error and not a disagreement — it is the reason a disagreement in
      // `wipItems` would be explicable rather than alarming.
      statusesMoved: typeof todayStatuses === 'string' && typeof kept.statuses === 'string'
        && kept.statuses !== todayStatuses,
    };
  });

  const orphaned = Object.keys(sprints).filter((k) => !seen.has(k));
  return { rows, orphaned };
};

/**
 * What the page says above the chart. Silent when there is nothing to say.
 *
 * Every sentence here is about something a reader cannot see by looking at the
 * chart, which is the same rule `nameNote` follows. "Six sprints, four
 * recorded" over six visible points is noise; a sprint whose recorded figures
 * disagree with Jira's own answer today is not.
 *
 * Counts are read off the rows they describe, never computed beside them.
 */
export const seriesNote = ({ rows, orphaned }) => {
  const out = [];
  const list = Array.isArray(rows) ? rows : [];
  const recorded = list.filter((r) => r.source === 'recorded');
  const rebuilt = list.filter((r) => r.source === 'reconstructed');

  if (recorded.length && rebuilt.length) {
    out.push(`${rebuilt.length} of these ${list.length} sprint${list.length === 1 ? '' : 's'} closed before this app saw the board, so ${rebuilt.length === 1 ? 'its row was' : 'their rows were'} rebuilt from Jira rather than recorded at the time. They agree unless something below says otherwise.`);
  }

  const midFlight = recorded.filter((r) => r.atSprintEnd === false);
  if (midFlight.length) {
    out.push(midFlight.length === 1
      ? 'One recorded sprint was last seen while it was still running, so its row is that day rather than the sprint\'s end.'
      : `${midFlight.length} recorded sprints were last seen while still running, so their rows are those days rather than the sprints' ends.`);
  }

  const moved = recorded.filter((r) => r.statusesMoved === true);
  if (moved.length) {
    out.push(`${moved.length === 1 ? 'One sprint was' : `${moved.length} sprints were`} recorded under a different set of "in progress" statuses than this site uses now. Work in progress and flow efficiency are measured against that word, so those points and the recent ones are not quite the same measurement.`);
  }

  const differing = recorded.filter((r) => (r.differs || []).length);
  if (differing.length) {
    const fields = [...new Set(differing.flatMap((r) => r.differs))].sort();
    out.push(`${differing.length === 1 ? 'One recorded sprint no longer matches' : `${differing.length} recorded sprints no longer match`} what Jira answers for ${differing.length === 1 ? 'it' : 'them'} today — ${fields.join(', ')}. The recorded figures are shown. A sprint reopened and closed again, or an issue deleted, changes what can be re-derived; the record of what was true does not change.`);
  }

  if ((orphaned || []).length) {
    out.push(`${orphaned.length === 1 ? 'One recorded sprint is' : `${orphaned.length} recorded sprints are`} no longer offered by this board and ${orphaned.length === 1 ? 'was' : 'were'} left out rather than placed at a guessed position.`);
  }

  return out.join(' ');
};
