/**
 * Shaping Jira's answers into the dashboard's dataset. No Forge, no network.
 *
 * Everything here is a pure function of a Jira response body, which is the
 * whole reason it is a separate file: `index.js` cannot be run outside Forge,
 * and the shapes below are the half that has to agree with
 * `scripts/serve_live.py`. `tests/test_service.py` runs these against fixtures
 * and compares the result to what the live server really returns, so the two
 * transports cannot drift into answering the same question differently.
 *
 * This module plays the fetcher's part, not the calculator's. Extracting a
 * field out of a Jira issue is what `scripts/fetch_delivery_data.py` does and
 * is not arithmetic; deciding what a status *means*, or what a burndown looks
 * like, is organisation config and calculation respectively, and neither
 * happens here. Where a field would need one of those it is left out, and the
 * page says so on the tile rather than showing a zero.
 */

/** The context id the whole product keys on: project, board, period. The same
 *  string `serve_live.py` builds, because the page round-trips it back to
 *  `context` and a second format would be a second product.
 *
 *  The third part is a sprint id on a sprint board and a window token on a
 *  flow board — see `windowToken` and ADR 0011. */
export const contextId = (projectKey, boardId, period) =>
  `${projectKey || '?'}/${boardId}/${period}`;

/**
 * The windows a flow board is offered, in calendar days.
 *
 * A fixed set rather than a free choice, for two reasons. Two boards are
 * comparable only if the question asked of each was the same one, and a window
 * nobody can name is a window nobody can reproduce. Calendar days, matching
 * every other elapsed figure in the product.
 *
 * `scripts/serve_live.py` holds the same list and `tests/test_service.py`
 * compares them, because a window one transport offers and the other rejects
 * is an id that works until the page is opened the other way.
 */
export const WINDOW_DAYS = [14, 30, 90];
export const DEFAULT_WINDOW_DAYS = 30;

/** The third part of a flow board's id. Prefixed rather than bare, so that a
 *  sprint id and a window length can never be read as each other. */
export const windowToken = (days) => `win:${days}d`;

/**
 * Back out again, so `context` needs no state between calls.
 *
 * Returns null for anything that is not one of the two shapes — a caller must
 * refuse rather than query whatever the string happened to parse into — and
 * `kind` says which one it was rather than leaving the caller to re-test the
 * string. That is the ADR 0011 rule in miniature: the discriminator is
 * carried, not recovered, because a second reading of the same string is a
 * second implementation of the same fact.
 *
 * A window length outside `WINDOW_DAYS` is refused, not clamped and not
 * honoured. `win:99999d` would otherwise pull an unbounded slice of a board
 * through an id the picker never offered, and a request the product cannot
 * make is a request it should not answer.
 */
export const parseContextId = (id) => {
  const m = /^([^/]+)\/(\d+)\/([^/]+)$/.exec(String(id ?? ''));
  if (!m) return null;
  const [, projectKey, boardId, period] = m;
  if (/^\d+$/.test(period)) {
    return { kind: 'sprint', projectKey, boardId, sprintId: period };
  }
  const w = /^win:(\d+)d$/.exec(period);
  if (w) {
    const days = Number(w[1]);
    // Canonical form only, checked by rebuilding the token rather than by
    // trusting the match. `Number('030')` is 30, so `win:030d` and `win:30d`
    // both parsed and named one context by two strings — and the page keys
    // everything on this id and round-trips it. A second spelling of the same
    // context is the shape of the bug that made every sprint read "unknown
    // context" once already.
    if (windowToken(days) === period && WINDOW_DAYS.includes(days)) {
      return { kind: 'window', projectKey, boardId, windowDays: days };
    }
  }
  return null;
};

/** Calendar-day arithmetic on a YYYY-MM-DD string, in UTC so that the answer
 *  does not depend on where the resolver happens to run. Mirrors the plain
 *  `date - timedelta` the Python does; the parity test compares the strings
 *  rather than trusting that two languages agree about a month boundary. */
const shiftDays = (iso, n) => {
  const t = Date.parse(`${iso}T00:00:00Z`);
  if (Number.isNaN(t)) return null;
  return new Date(t + n * 86400000).toISOString().slice(0, 10);
};

/**
 * One selectable sprint. Field for field what `JiraBackend.contexts()` puts on
 * the wire, `_sprintId` included — the page ignores it, and dropping it here
 * would make a parity check pass against a shape neither side really sends.
 *
 * `workingDays` is deliberately absent, and the reason has changed since it
 * first was. It used to be that resolving organisation config here would be a
 * fourth opinion arriving by a fourth route — but this resolver now resolves
 * that config, out of Jira's own status categories and the project property,
 * so it plainly could compute the list.
 *
 * It must not, and the reason is the one that outlasts the other: expanding a
 * date range into working days is a *rule*, and the rule already has two
 * implementations — `orgconfig.py` and its mirror in `src/app.js`, kept honest
 * by a test that runs both under a non-default config. A third here would be a
 * third thing to keep in step, in the one place nobody can run the test
 * against a customer's tenant.
 *
 * So the page derives it from `startDate`/`endDate` under the config this
 * resolver sent, exactly as it already derives `statusCategory` from a raw
 * status name — see `contextWorkingDays()` in `src/app.js`. `BundleBackend`
 * strips the field for its own reasons and the page fills it the same way.
 *
 * Leaving it out is a silence, not a gap — but only because the page fills it.
 * Before it did, every sprint in a tenant lost the largest component of its
 * health score, *Pace vs clock* read as no sprint dates across a whole
 * install, and the two transports rendered different figures from one sprint.
 * `tests/e2e.py` now feeds the bridge a body shaped the way this file really
 * shapes one, rather than the loopback's own, and requires the same render.
 *
 * `fallbackProjectKey` exists because the id has to survive a round trip and
 * the id is built from `board.location`. The board *list* endpoint and the
 * single-board read do not always describe `location` the same way, and the
 * page asks `contexts` via the first and `context` via the second — so an id
 * built from a response carrying `projectKey` was compared against one built
 * from a response without it, stopped matching, and every sprint came back
 * "unknown context". Forge's own module context knows the project, and it is
 * the same answer both times.
 */
export const contextEntry = (board, sprint, fallbackProjectKey, today) => {
  const loc = board.location || {};
  const projectKey = loc.projectKey ?? fallbackProjectKey ?? null;
  return {
    id: contextId(projectKey, board.id, sprint.id),
    // Carried, not recovered from the id. See `parseContextId`.
    kind: 'sprint',
    source: 'jira',
    projectKey,
    projectName: loc.projectName ?? null,
    boardId: String(board.id),
    boardName: board.name ?? null,
    // The board's name, as the live server does it. A Jira board has no team
    // field; the board is the closest thing to one, and the forecaster slices
    // its history by team, so the two must agree about what a team is.
    team: board.name ?? null,
    sprintName: sprint.name ?? null,
    sprintState: sprint.state ?? null,
    sprintGoal: sprint.goal || '',
    startDate: (sprint.startDate || '').slice(0, 10),
    endDate: (sprint.endDate || '').slice(0, 10),
    // The moment this sprint's figures are a statement about, resolved exactly
    // as `scripts/fetch_delivery_data.py` resolves it: today for a running
    // sprint, the completion date for a finished one, and the planned end only
    // if Jira recorded no completion.
    //
    // This was `null`, and the divergence it caused reached a tenant. A Forge
    // series therefore rested entirely on `endDate` — so a sprint started
    // without one produced no row at all, the trend silently lost a point, and
    // the tile reported thin data on a board that had two sprints. It also
    // meant a closed sprint was dated to when it was *planned* to end rather
    // than when it did, which are different days whenever a sprint runs over.
    //
    // `today` is passed in rather than read here, because this module has no
    // clock — the same reason `windowEntry` takes one.
    asOfDate: sprint.state === 'active'
      ? (today || null)
      : ((sprint.completeDate || '').slice(0, 10)
         || (sprint.endDate || '').slice(0, 10) || null),
    issueCount: 0,
    _sprintId: sprint.id,
  };
};

/**
 * One selectable window: what a flow board is offered in place of a sprint.
 *
 * Field for field the sprint entry above, minus `_sprintId`, so the picker and
 * every renderer read one shape and not two. `scripts/serve_live.py` builds
 * the identical object and `tests/test_service.py` compares them key by key
 * and value by value — not merely field sets, because two producers agreeing
 * about which keys exist and disagreeing about where a 30-day window starts
 * is the harder bug and the one a shape check cannot see.
 *
 * Three of those fields are named for sprints and hold a window's answer. That
 * is deliberate and it is not a rename waiting to happen: `sprintName`,
 * `sprintState` and `sprintGoal` are the contract two transports and every
 * committed fixture already agree about, and renaming them to say "period"
 * would be a second product for the sake of a word. `CONTEXT.md` settles what
 * the page *calls* these; the wire keeps the name it has.
 *
 * `startDate` and `endDate` are real and bound the selection. They must never
 * become a clock: a window carries no working-day list, and the page owes it
 * an explicit refusal rather than the derivation it performs for a sprint.
 * ADR 0011 is the whole of the reasoning; `contextWorkingDays()` in
 * `src/app.js` is where it has to be honoured.
 *
 * `asOf` is passed rather than read from a clock here, because an entry that
 * changes with the wall clock cannot be compared against another producer's.
 */
export const windowEntry = (board, days, asOf, fallbackProjectKey) => {
  const loc = board.location || {};
  const projectKey = loc.projectKey ?? fallbackProjectKey ?? null;
  const end = String(asOf || '').slice(0, 10);
  return {
    id: contextId(projectKey, board.id, windowToken(days)),
    kind: 'window',
    source: 'jira',
    projectKey,
    projectName: loc.projectName ?? null,
    boardId: String(board.id),
    boardName: board.name ?? null,
    team: board.name ?? null,
    sprintName: `Last ${days} days`,
    // Not a Jira sprint state, and not null: the picker's state chip switches
    // on this, and the rollup already occupies the same slot with "rollup".
    sprintState: 'window',
    sprintGoal: '',
    // Inclusive of both ends, so a 30-day window really covers 30 calendar
    // days rather than 31. Calendar days, like every other elapsed figure.
    startDate: shiftDays(end, -(days - 1)),
    endDate: end,
    asOfDate: end,
    issueCount: 0,
  };
};

/**
 * Which issues are *in* a window, as a JQL predicate.
 *
 * The membership ADR 0011 settled: **resolved inside the window, or not
 * resolved at all**. The open half is what makes ageing and work in progress
 * mean anything on a flow board, and the resolved half is what cycle time,
 * lead time and throughput are measured over.
 *
 * It reads `resolutiondate` for both halves rather than `resolution IS EMPTY`,
 * and the difference is not cosmetic. `resolutiondate` is the field
 * `issueFrom` maps to `resolved`, so this asks Jira exactly the question the
 * page will answer from the data it gets back. `resolution` is a second
 * opinion about what "done" means, arriving by a route that is neither the
 * organisation config nor the status category — which is the shape of thing
 * this product has a standing rule against.
 *
 * The upper bound is the day *after* the window's end, because Jira compares a
 * bare date against midnight: `resolutiondate <= "2026-08-24"` silently drops
 * everything finished during the last day of the window. That is a plausible
 * wrong number — a throughput series quietly missing its most recent day —
 * rather than a failure, so it is stated here and pinned by a test.
 *
 * Returns the predicate alone, with no ordering and no board scoping. Each
 * transport reaches a board its own way — the resolver through
 * `/board/{id}/issue`, the loopback through the board's own filter — and the
 * *membership* is the half that has to be identical. `scripts/serve_live.py`
 * builds the same string and `tests/test_service.py` compares them.
 *
 * Nothing here is drawn from the page. The only input is a window entry the
 * resolver built itself, from a length `parseContextId` already refused unless
 * it was one of `WINDOW_DAYS` in canonical spelling — so the set of JQL this
 * app can be made to issue is three date pairs per board, and no text from a
 * caller reaches Jira.
 */
export const windowMembershipJql = (startDate, endDate) => {
  const after = shiftDays(endDate, 1);
  return `(resolutiondate >= "${startDate}" AND resolutiondate < "${after}")`
    + ' OR resolutiondate IS EMPTY';
};

/** Newest first, then the same cap the live server applies — and the cap is
 *  reported by the caller rather than applied quietly, because a truncated
 *  list of sprints reads as a complete one. */
export const recentSprints = (sprints, limit) =>
  (sprints || [])
    .slice()
    .sort((a, b) => String(b.startDate || '').localeCompare(String(a.startDate || '')))
    .slice(0, limit);

/**
 * The display names Jira sites give the story-point field.
 *
 * The same three `scripts/fetch_delivery_data.py` matches, in the same order,
 * because the two producers must not disagree about which field holds points
 * on one site. "Story Points" is the classic company-managed name, "Story
 * point estimate" the team-managed one, and "Points" is common on sites that
 * renamed it.
 */
export const STORY_POINT_FIELD_NAMES = ['story points', 'story point estimate', 'points'];

/**
 * Which custom field holds story points on *this* site, from `/rest/api/3/field`.
 *
 * The id differs per site and there is no id that is right everywhere — the
 * previous version hardcoded `customfield_10016`, the common one, and on any
 * other site every issue read as zero points and the burndown flattened with
 * nothing saying why. That is the plausible-wrong-number class: not a failure,
 * an answer that looks computed.
 *
 * First match in the order Jira returns, which is what the Python fetcher does.
 * Mirroring the traversal matters as much as mirroring the list: a site with
 * both "Story Points" and "Points" defined must resolve to the same one down
 * both routes, or the same board reports two different velocities.
 *
 * Returns null when the site has no such field, and null is not an id to guess
 * around — the caller says so rather than substituting one.
 */
export const findStoryPointField = (fields) => {
  for (const f of fields || []) {
    const name = String(f.name ?? '').trim().toLowerCase();
    if (STORY_POINT_FIELD_NAMES.includes(name)) return f.id ?? null;
  }
  return null;
};

/** One issue's business value, or null when nobody has recorded one.
 *
 *  Null rather than zero, and the distinction is the whole reason this is a
 *  function. A field nobody has filled in and a piece of work genuinely worth
 *  nothing are different facts; `metrics.facts` reports value as *unmeasured*
 *  for the first and as zero for the second, and collapsing them here would
 *  make that impossible one layer down. */
const valueOf = (fields, fieldId) => {
  if (!fieldId) return null;
  const raw = fields[fieldId];
  if (raw === null || raw === undefined || raw === '') return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
};

/** The module key of this app's own business-value field, as declared in
 *  `forge/manifest.yml`. ADR 0025. */
export const BUSINESS_VALUE_KEY = 'business-value';

/**
 * This app's own Business Value field, from `/rest/api/3/field`.
 *
 * Matched on the field's **key** and not its name. A Forge custom field's key
 * carries the module key that declared it, so it identifies *this app's* field
 * rather than any field a site happens to have called "Business Value" — and a
 * site that already has one of its own is exactly the case where matching on a
 * display name would read somebody else's numbers and report them as value.
 *
 * `findStoryPointField` above matches on names because it is looking for a
 * field this app did not create and cannot identify any other way. The
 * difference is worth keeping: one is a guess with three known spellings, the
 * other is a fact.
 */
export const findBusinessValueField = (fields) => {
  for (const f of fields || []) {
    const key = String(f.key ?? f.id ?? '');
    if (key.includes(BUSINESS_VALUE_KEY)) return f.id ?? null;
  }
  return null;
};

/** The module key of this app's own Value Basis field, as declared in
 *  `forge/manifest.yml`. ADR 0027. */
export const VALUE_BASIS_KEY = 'value-basis';

/**
 * This app's own Value Basis field, from `/rest/api/3/field`.
 *
 * Matched on the key for the same reason `findBusinessValueField` is, and the
 * two keys are checked against each other in `tests/test_service.py`: neither
 * module key is a substring of the other, and if a later rename made one of
 * them so, this would read a sentence into the number field or a currency
 * amount into the basis. Both would render. Neither would look wrong.
 */
export const findValueBasisField = (fields) => {
  for (const f of fields || []) {
    const key = String(f.key ?? f.id ?? '');
    if (key.includes(VALUE_BASIS_KEY)) return f.id ?? null;
  }
  return null;
};

/** One issue's value basis, or `''` when nobody has written one.
 *
 *  `''` and not null, because that is what the schema has always said this
 *  field is (`docs/data-format.md`) and what every other producer writes — the
 *  page renders `valueBasis || "no basis recorded"` and has since before any
 *  of this reached Jira.
 *
 *  **A non-string is not coerced.** This app declares the field as
 *  `type: string`, so anything else means the field being read is not the one
 *  declared; `String(raw)` would put `[object Object]` under a currency figure
 *  on an executive dashboard, which is the plausible-wrong-answer class this
 *  repository fears. Absent is the honest reading and the page already has a
 *  sentence for it. */
const basisOf = (fields, fieldId) => {
  if (!fieldId) return '';
  const raw = fields[fieldId];
  return typeof raw === 'string' ? raw.trim() : '';
};

/** The module key of this app's own Candidate field. ADR 0028. */
export const CANDIDATE_KEY = 'candidate';

/**
 * The field that says whether an issue is an ask, which is not always ours.
 *
 * `askField` is `'app'` — this app's declared **Candidate** field, found by its
 * module key like the other two — or the name of a field the site already has.
 * A site with a checkbox called "Ready for sequencing", or a single select, or
 * a discovery flag, points the config at it and keeps working the way it
 * already works. Candidacy is the one thing here that every organisation
 * defines differently, so the app declares a default and refuses to insist on
 * it.
 *
 * A named field is matched by **id first, then display name**, and matching a
 * display name is safe here for the reason it is unsafe elsewhere: when the app
 * picks a field by name it is guessing, and when the organisation names one it
 * is an instruction.
 */
export const findAskField = (fields, askField) => {
  const named = String(askField ?? 'app').trim();
  if (!named || named.toLowerCase() === 'app') {
    for (const f of fields || []) {
      if (String(f?.key ?? f?.id ?? '').includes(CANDIDATE_KEY)) return f.id ?? null;
    }
    return null;
  }
  for (const f of fields || []) if (String(f?.id ?? '') === named) return f.id ?? null;
  const want = named.toLowerCase();
  for (const f of fields || []) {
    if (String(f?.name ?? '').trim().toLowerCase() === want) return f.id ?? null;
  }
  return null;
};

/** One issue's raw candidacy answer, trimmed, or `''`.
 *
 *  The *string*, not a verdict. Whether it means yes is
 *  `orgconfig.candidate_answer`, which has three answers rather than two — a
 *  field reading "Maybe" is somebody trying to say something, and reading it as
 *  a no would drop their epic out of a comparison silently. Deciding here would
 *  throw that away before anything could report it.
 *
 *  A non-string is not coerced, for the same reason `basisOf` does not: a site
 *  may point `askField` at a select or a checkbox, whose value is an object,
 *  and `String(raw)` would make `[object Object]` an unrecognised answer
 *  reported against somebody's epic. */
const candidateOf = (fields, fieldId) => {
  if (!fieldId) return '';
  const raw = fields[fieldId];
  if (typeof raw === 'string') return raw.trim();
  // The shapes Jira uses for a checkbox or a single select, which is what a
  // site pointing at its own field most often has.
  if (raw && typeof raw === 'object' && typeof raw.value === 'string') return raw.value.trim();
  if (Array.isArray(raw) && raw.length && typeof raw[0]?.value === 'string') {
    return raw[0].value.trim();
  }
  return '';
};

/* ----------------------------------------------------------------- asks
 *
 * Which issues are asks, and the ask payload the calculator is allowed to see.
 * Mirrors `orgconfig.candidate_answer`, `orgconfig.candidate_issues` and
 * `intake.asks_from_issues`. Change one, change both — `tests/test_service.py`
 * runs the two over one shared set of cases.
 *
 * **Why this is decided here and not in the calculator.** Sending the candidate
 * answers would be simpler: the dataset already crosses, and one more field
 * would let `asks_from_issues` run server-side with no mirror to maintain. It
 * cannot, because of what the answer *is*. An answer this does not recognise is
 * reported back with the issue key and **the words somebody wrote** — "Maybe",
 * "Q3?", "ask Priya" — and that is free text about a customer's business. The
 * disclosure is the reason the rule has three answers rather than two, and it
 * is exactly the thing `NEVER_SEND` exists to keep inside the tenant.
 *
 * So candidacy is decided in here, and what crosses is an id, a sizing method,
 * an amount and a date. No title, no basis, no answer.
 */
/** The module key of this app's own T-Shirt Size field. ADR 0029. */
export const SIZE_KEY = 'tshirt-size';

/** The field carrying an ask's band — ours, or one the site already has.
 *  Same rule and same reasoning as `findAskField`. */
export const findSizeField = (fields, sizeField) => {
  const named = String(sizeField ?? 'app').trim();
  if (!named || named.toLowerCase() === 'app') {
    for (const f of fields || []) {
      if (String(f?.key ?? f?.id ?? '').includes(SIZE_KEY)) return f.id ?? null;
    }
    return null;
  }
  for (const f of fields || []) if (String(f?.id ?? '') === named) return f.id ?? null;
  const want = named.toLowerCase();
  for (const f of fields || []) {
    if (String(f?.name ?? '').trim().toLowerCase() === want) return f.id ?? null;
  }
  return null;
};

/** The raw band answer, trimmed. A select or checkbox arrives as an object. */
const sizeOf = (fields, fieldId) => {
  if (!fieldId) return '';
  const raw = fields[fieldId];
  if (typeof raw === 'string') return raw.trim();
  if (raw && typeof raw === 'object' && typeof raw.value === 'string') return raw.value.trim();
  if (Array.isArray(raw) && raw.length && typeof raw[0]?.value === 'string') {
    return raw[0].value.trim();
  }
  return '';
};

/** The bands `tshirt_scale` calibrates. Mirrors `orgconfig.TSHIRT_BANDS`. */
export const TSHIRT_BANDS = ['S', 'M', 'L', 'XL'];

/** `null`, a band, or the unrecognised string somebody wrote.
 *  Mirrors `orgconfig.tshirt_answer`. */
export const tshirtAnswer = (issue) => {
  const raw = (issue || {}).tshirt;
  if (typeof raw !== 'string' || !raw.trim()) return null;
  const band = raw.trim().toUpperCase();
  return TSHIRT_BANDS.includes(band) ? band : raw.trim();
};

export const CANDIDATE_YES = ['yes', 'y', 'true'];
/** And the way to say no out loud, which exists because a band implies
 *  candidacy: without it, sizing an epic in refinement would enter it into a
 *  comparison and the only way out would be deleting the size. */
export const CANDIDATE_NO = ['no', 'n', 'false'];

/** `null` (nothing said), `true`, `false` (said no), or the words nobody can
 *  read. Mirrors `orgconfig.candidate_answer`; four answers, each a different
 *  fact, and `null` rather than `false` for silence is the point of the split. */
export const candidateAnswer = (issue) => {
  const raw = (issue || {}).candidate;
  if (typeof raw !== 'string' || !raw.trim()) return null;
  const said = raw.trim().toLowerCase();
  if (CANDIDATE_YES.includes(said)) return true;
  if (CANDIDATE_NO.includes(said)) return false;
  return raw.trim();
};

/** The declared candidates, and the answers nobody can read. */
export const candidateIssues = (issues, cfg) => {
  let floor = cfg?.askFromHierarchy;
  if (typeof floor !== 'number' || !Number.isFinite(floor)) floor = 1;
  const asks = [];
  const unreadable = [];
  for (const i of issues || []) {
    const lvl = i?.hierarchyLevel;
    // An issue with no recorded level still qualifies, for the same reason it
    // still carries value: every dataset written before levels existed would
    // otherwise have no candidates at all.
    if (typeof lvl === 'number' && Number.isFinite(lvl) && lvl < floor) continue;
    const ans = candidateAnswer(i);
    if (ans !== null && ans !== true && ans !== false) {
      unreadable.push({ key: i?.key, said: ans });
    }
    if (ans === false) continue;          // said no; a band does not override it
    const band = tshirtAnswer(i);
    // A band declares candidacy too — choosing a size is somebody saying how
    // big this thing they are considering would be, and charging them a second
    // screen configuration to be taken seriously buys nothing. ADR 0028's
    // amendment.
    if (ans === true || (band !== null && TSHIRT_BANDS.includes(band))) asks.push(i);
  }
  return { asks, unreadable };
};

/**
 * `{ asks, text, notes }` — the wire payload, the words that stay here, and
 * what a reader has to be told.
 *
 * `asks` is what the calculator gets and it carries **no free text**: an id, a
 * sizing method, an amount and a needed-by date. `text` is the title and the
 * basis, held in the tenant and joined back onto the answer by id — which is a
 * lookup, not a calculation, and is the only reason a reader sees a basis
 * beside an ordering at all.
 *
 * `team` is omitted rather than sent. `sequence` never reads it — the board is
 * a separate argument — and a board's name is a customer's word for a customer's
 * team.
 */
export const asksFromIssues = (issues, cfg) => {
  const { asks: cands, unreadable } = candidateIssues(issues, cfg);
  const asks = [];
  const text = {};
  const delivered = [];
  const unsized = [];
  for (const i of cands) {
    const band = tshirtAnswer(i);
    const known = band !== null && TSHIRT_BANDS.includes(band);
    if (band !== null && !known) unsized.push({ id: i.key, said: band });
    const a = {
      id: i.key,
      // Each ask its own way, and the row says which. A band picks one quartile
      // of this board's completed epics; no band takes all of them. Two
      // distributions in one table that does not say so read as one.
      sizing: known ? { method: 'tshirt', size: band } : { method: 'reference-class' },
    };
    const amount = i.businessValue;
    // Present or absent, never half: `readiness` asks for an amount and a basis
    // or nothing at all. The basis is not on the wire, so the calculator sees a
    // bare amount and the tenant puts the sentence back.
    if (typeof amount === 'number' && Number.isFinite(amount) && amount) {
      a.valueEstimate = { amount };
    }
    if (i.dueDate) a.neededBy = i.dueDate;
    asks.push(a);
    text[i.key] = { title: i.summary || i.key, basis: String(i.valueBasis ?? '').trim() };
    // Candidacy is declared and un-declaring it belongs to whoever declared it.
    // ADR 0028 refuses to infer it from status, so a delivered candidate is
    // still an ask and is named instead.
    if (i.resolved) delivered.push({ id: i.key, resolved: i.resolved });
  }
  return { asks, text, notes: { unreadable, delivered, unsized } };
};

/* ------------------------------------------------------------------ config

   The assumptions that are true of exactly one company: which statuses mean
   done, which days are worked, which of those are holidays, how long a sprint
   is. `agent/tools/orgconfig.py` is the one place they are decided, and the
   resolved answer travels inside the dataset as `orgConfig` so every consumer
   reads the same one.

   A Forge install has no dataset, so this resolver is the producer and has to
   resolve it — and until it did, every tenant was measured under the defaults:
   Monday to Friday, no holidays, fourteen-day sprints, and a fixed idea of the
   word "done". A site with a *Signed off* column read every sprint as 0%
   complete. That is a blanket ruling applied to sites that never agreed to it.

   Two sources, in the order the Python resolves them:

     Jira        Every status on a Jira site carries a category its admins
                 assigned. orgconfig.py already trusts that as "a statement by
                 the site rather than a guess here" — it is the fallback its
                 own category() reaches for. Here there is no config file above
                 it, so it is the primary source, and it is authoritative
                 because the customer wrote it.

     A project   Jira has no notion of a working week, a holiday calendar or a
     property    sprint length, so those have to be stated. `orgConfig` on the
                 project, readable with the scope the board picker already
                 needs. Absent, the defaults apply and the footer says so.

   ---------------------------------------------------------------------- */

/** Where a site states what Jira cannot tell us. Read-only: this app never
 *  writes it, and asks for no scope that would let it. */
export const CONFIG_PROPERTY_KEY = 'orgConfig';

/**
 * The site's own answer to "which statuses mean done", from its own statuses.
 *
 * Jira's category keys are `new`, `indeterminate` and `done`. Only the last
 * two become lists — "To Do" is what a status falls to when it is in neither,
 * so enumerating it would add a third list the schema does not have and the
 * page does not read.
 *
 * Names, not ids, because that is what the schema and the page match on, and
 * because two projects on one site may define separate statuses with the same
 * name and the same meaning.
 */
export const statusesFromJira = (statuses) => {
  const done = new Set();
  const inProgress = new Set();
  for (const st of statuses || []) {
    const name = String(st?.name ?? '').trim();
    if (!name) continue;
    const key = String(st?.statusCategory?.key ?? '').toLowerCase();
    if (key === 'done') done.add(name);
    else if (key === 'indeterminate') inProgress.add(name);
  }
  // Sorted so the same site produces the same config on every call — a config
  // that reordered itself would make every response look changed.
  return { done: [...done].sort(), inProgress: [...inProgress].sort() };
};

const DAY_NAMES = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const MAX_SPRINT_DAYS = 90;
/** Mirrors orgconfig.MAX_TREND_SPRINTS. */
export const MAX_TREND_SPRINTS = 40;
const normName = (v) => String(v ?? '').trim().replace(/\s+/g, ' ').toLowerCase();

/**
 * Every problem with a config a site stated, as sentences. Empty means usable.
 *
 * A mirror of `orgconfig.validate()`, and it exists for the reason that
 * function does: a bad config must stop the run rather than fall back. A typo
 * in `workingWeek` that quietly reverted to a five-day week would move every
 * forecast in the product with nothing on screen saying so.
 *
 * It checks only the keys a site actually stated, because that is all this
 * source supplies — everything else comes from the defaults the page already
 * holds. `tests/test_service.py` runs the same good and bad configs through
 * both this and the Python and asserts they agree about which are usable, so
 * the two cannot drift into accepting different files.
 */
export const validateOrgConfig = (cfg) => {
  const p = [];
  const c = cfg || {};

  if ('workingWeek' in c) {
    if (!Array.isArray(c.workingWeek) || !c.workingWeek.length) {
      p.push('workingWeek must be a non-empty list of day names');
    } else {
      const bad = c.workingWeek.filter((d) => !DAY_NAMES.includes(normName(d)));
      if (bad.length) {
        p.push(`workingWeek contains ${bad.map((b) => JSON.stringify(b)).join(', ')}`
          + ` — use ${DAY_NAMES.join('/')}`);
      }
    }
  }

  if ('statuses' in c) {
    const st = c.statuses;
    if (st === null || typeof st !== 'object' || Array.isArray(st)) {
      p.push('statuses must be an object with done and inProgress lists');
    } else {
      for (const key of ['done', 'inProgress']) {
        if (!(key in st)) continue;
        if (!Array.isArray(st[key])) {
          p.push(`statuses.${key} must be a list of status names`);
        } else if (st[key].some((x) => !String(x ?? '').trim())) {
          p.push(`statuses.${key} contains an empty name`);
        }
      }
      const done = new Set((Array.isArray(st.done) ? st.done : []).map(normName));
      const wip = (Array.isArray(st.inProgress) ? st.inProgress : []).map(normName);
      const both = [...new Set(wip.filter((x) => x && done.has(x)))].sort();
      if (both.length) {
        // Preferring one list silently would make "done" mean different things
        // in the burndown and in the ageing chart.
        p.push(`${both.map((b) => JSON.stringify(b)).join(', ')} appears in both `
          + 'statuses.done and statuses.inProgress');
      }
    }
  }

  if ('holidays' in c) {
    if (!Array.isArray(c.holidays)) {
      p.push('holidays must be a list of YYYY-MM-DD dates');
    } else {
      for (const h of c.holidays) {
        const t = String(h ?? '');
        const d = /^\d{4}-\d{2}-\d{2}$/.test(t) ? new Date(`${t}T00:00:00Z`) : null;
        if (!d || Number.isNaN(d.getTime()) || d.toISOString().slice(0, 10) !== t) {
          p.push(`holidays contains ${JSON.stringify(h)}, which is not a YYYY-MM-DD date`);
        }
      }
    }
  }

  if ('sprintLengthDays' in c) {
    const n = c.sprintLengthDays;
    if (typeof n !== 'number' || !Number.isInteger(n) || n < 1 || n > MAX_SPRINT_DAYS) {
      p.push('sprintLengthDays must be a whole number of calendar days between '
        + `1 and ${MAX_SPRINT_DAYS}`);
    }
  }

  // Mirrors orgconfig.validate. Two is the floor because a trend needs two
  // points to be one; the ceiling is latency, since every sprint in the window
  // is a sprint's worth of issues fetched.
  // Mirrors orgconfig.validate. A parent and its subtasks are one piece of
  // work and several rows, so which of them count is the organisation's answer
  // and travels with its config. ADR 0024.
  if ('countSubtasks' in c && typeof c.countSubtasks !== 'boolean') {
    p.push('countSubtasks must be true or false');
  }
  if ('countedTypes' in c) {
    const t = c.countedTypes;
    if (!Array.isArray(t) || !t.every((x) => typeof x === 'string')) {
      p.push('countedTypes must be a list of issue type names, or empty for '
        + 'every type');
    }
  }

  if ('trendSprints' in c) {
    const n = c.trendSprints;
    if (typeof n !== 'number' || !Number.isInteger(n) || n < 2 || n > MAX_TREND_SPRINTS) {
      p.push('trendSprints must be a whole number of sprints between 2 and '
        + `${MAX_TREND_SPRINTS}`);
    }
  }

  return p;
};

/**
 * What the site said, over what Jira knows. One level down, as the Python
 * merges — a stated `statuses` block naming only `done` keeps Jira's own
 * `inProgress`, because an omission is not a claim that nothing is in
 * progress.
 */
export const mergeOrgConfig = (fromJira, stated) => {
  const out = { ...(fromJira || {}) };
  for (const [k, v] of Object.entries(stated || {})) {
    if (v === null || v === undefined) continue;
    if (k === 'statuses' && v && typeof v === 'object' && !Array.isArray(v)) {
      out.statuses = { ...(out.statuses || {}) };
      for (const [sk, sv] of Object.entries(v)) if (sv !== null) out.statuses[sk] = sv;
    } else {
      out[k] = v;
    }
  }
  return out;
};

/** The envelope `GET api/contexts` returns. */
/** Said in the line the page prints in its footer, so a site with no
 *  story-point field reads as a site with no story-point field rather than as
 *  a team that estimated everything at zero. */
export const POINTS_NOTE = 'no story-point field on this site, so points are not reported';

/** The other half of the config, and the half Jira cannot answer. Named when
 *  it is defaulted, because a five-day week nobody chose reads exactly like
 *  one somebody did. */
export const CALENDAR_NOTE = `working week and holidays are this tool's defaults — set an `
  + `${CONFIG_PROPERTY_KEY} property on the project to state your own`;

/**
 * The "which data am I looking at" line, and the place every board that was
 * *not* offered has to be accounted for.
 *
 * It lives here rather than in the resolver so a test can read it. That is not
 * tidiness: this sentence is the only thing standing between a picker quietly
 * missing a board and a project that genuinely does not have one, and the two
 * look identical on screen. This repository has shipped a silently truncated
 * list three times.
 *
 * The counts are three, not two, and separating them is the point. A board
 * with no sprint support is a flow board and is now offered a window each; a
 * board that has sprints and has never run one has nothing to offer and is a
 * different sentence for its owner to act on. They were one count until
 * windows existed, and reporting them together would have described the second
 * as the first.
 */
export const contextsLabel = ({
  projectKey, boards, flowBoards = 0, sprintBoardsWithNoSprints = 0,
  hasStoryPointField = true, statedCalendar = true,
}) => `Jira, project ${projectKey} — ${boards} board`
  + (boards === 1 ? '' : 's')
  + (flowBoards ? `, ${flowBoards} without sprints and shown as rolling windows` : '')
  + (sprintBoardsWithNoSprints
    ? `, ${sprintBoardsWithNoSprints} with sprints enabled but none started, and not offered`
    : '')
  + (hasStoryPointField ? '' : `; ${POINTS_NOTE}`)
  + (statedCalendar ? '' : `; ${CALENDAR_NOTE}`);

export const contextsBody = (label, contexts, orgConfig) => ({
  source: 'jira',
  label,
  // Resolved once, here, and written into every response — the same rule the
  // dataset producers follow. The page, and anything downstream of it, reads
  // this rather than deciding for itself.
  orgConfig: orgConfig || {},
  contexts,
});

/**
 * One issue, in the dataset's schema.
 *
 * Three fields the fetcher produces are absent, each for a stated reason:
 *
 *   statusCategory  Which statuses mean done is organisation config. The raw
 *                   name goes out and `normaliseIssue()` categorises it under
 *                   the config the page is running, exactly as it does for any
 *                   file whose producer did not resolve it.
 *   started         The first transition into an "In Progress" status — which
 *                   needs that same config to recognise, so this file does not
 *                   recognise it. It sends the raw transitions instead and the
 *                   page decides what they mean, exactly as it does for a raw
 *                   status name. See `statusTransitions` below.
 *   contextId       The page tags these itself in `loadContext()`, and does it
 *                   deliberately — "never let normalise() re-tag these". A
 *                   value sent from here would be overwritten, so sending one
 *                   would only invite the two to disagree.
 *
 * `addedMidSprint` is *not* in that list, and the difference matters. It needs
 * no config — it is "the sprint field changed after the sprint began" — and
 * defaulting it to false is not a silence, it is the claim that nothing was
 * added. The health score reads "no mid-sprint additions" and scores scope
 * stability at full marks, which is a confident wrong answer of exactly the
 * kind this repository keeps finding.
 */
export const issueFrom = (raw, opts) => {
  const o = opts || {};
  const f = raw.fields || {};
  const status = f.status || {};
  const parent = f.parent || {};
  const site = String(o.siteUrl || '').replace(/\/$/, '');
  return {
    key: raw.key,
    summary: f.summary ?? '',
    type: (f.issuetype || {}).name ?? null,
    // Jira's own flag rather than a guess from the type's name, which a site
    // can call anything. Recorded on every issue; `counted_issues` decides what
    // to do with it. ADR 0024.
    isSubtask: Boolean((f.issuetype || {}).subtask),
    // Jira levels its issue types: subtask -1, story 0, epic 1, initiatives
    // above. Business value is counted at one level and not several. ADR 0025.
    hierarchyLevel: (f.issuetype || {}).hierarchyLevel ?? null,
    status: status.name ?? null,
    assignee: (f.assignee || {}).displayName || 'Unassigned',
    // Read from whichever field this site calls story points, discovered by
    // display name rather than assumed. `null` where the site has no such
    // field at all — distinguishable in the payload from a genuine zero, and
    // reported in the connection label the page prints in its footer, because
    // an estimate nobody recorded and an estimate nobody could read are
    // different facts about a sprint.
    storyPoints: pointsOf(f, o.storyPointField),
    priority: (f.priority || {}).name ?? null,
    epic: (parent.fields || {}).summary ?? null,
    epicKey: parent.key ?? null,
    created: (f.created || '').slice(0, 10) || null,
    resolved: (f.resolutiondate || '').slice(0, 10) || null,
    dueDate: f.duedate ?? null,
    flagged: Boolean(f.flagged),
    addedMidSprint: addedMidSprint(raw, o.sprintStart),
    statusTransitions: statusTransitions(raw),
    // This app's own Business Value field, where the site has it on a screen and
    // somebody has filled it in — ADR 0025. It read a hardcoded 0 before,
    // because Jira has no native field for what work is worth and this app had
    // not declared one.
    //
    // `null` and not 0 when the field is absent or empty. The two are different
    // facts and the tools already act on the difference: `valueDelivered` comes
    // back *unmeasured* rather than nil when nothing carried a value, because
    // "this sprint delivered nothing worth anything" is a much stronger claim
    // than "nobody has told us".
    businessValue: valueOf(f, o.businessValueField),
    // The sentence under the number — ADR 0027. Hardcoded `''` before, because
    // no Jira field carried one; the app declares that field now too.
    //
    // It is deliberately *not* an input to anything. Nothing sizes, ranks or
    // scores on this string: it is carried to a reader and printed beside the
    // figure it explains, which is the whole reason it is free text and not an
    // enumeration. An enumeration is one join away from a priority score.
    valueBasis: basisOf(f, o.valueBasisField),
    // Whether somebody has put this forward as an ask — ADR 0028. The raw
    // answer, not a verdict: `orgconfig.candidate_answer` decides, and it has
    // three answers rather than two.
    candidate: candidateOf(f, o.askFieldId),
    // The band, where the site has the field and somebody chose one — ADR 0029.
    // A selector for which of this board's completed epics an ask is compared
    // against, never a number of its own.
    tshirt: sizeOf(f, o.sizeFieldId),
    labels: f.labels || [],
    url: site && raw.key ? `${site}/browse/${encodeURIComponent(raw.key)}` : null,
  };
};

const pointsOf = (fields, fieldId) => {
  if (!fieldId) return null;
  const raw = fields[fieldId];
  if (raw === undefined || raw === null || raw === '') return 0;
  const n = Number(raw);
  // A non-numeric estimate is not a zero. Jira permits a text custom field to
  // be pointed at here, and coercing "M" to 0 would put a made-up figure into
  // the burndown.
  return Number.isFinite(n) ? n : null;
};

/**
 * Every move this issue made between statuses, with the names undecided.
 *
 * `started` is the first transition into an in-progress status, and which
 * statuses those are is organisation config. The resolver could resolve it —
 * it resolves that config already, and it expands the changelog anyway for
 * `addedMidSprint`, so this costs no call — and it must not, for the reason
 * recorded against `workingDays`: the rule would then have a third
 * implementation, in the one place nobody can run a test against a customer's
 * tenant.
 *
 * The `workingDays` argument does not transfer whole, though, and the
 * difference is why this needed deciding rather than citing. `workingDays` can
 * be left out because the page can *derive* it from `startDate` and `endDate`,
 * which are already on the wire. Nothing on the wire let the page derive
 * `started`, so leaving it out was a real gap rather than a silence — and on a
 * board with no sprints, cycle time is not a nicety, it is the measure. So the
 * raw material goes out and the page applies its own rule, which is the same
 * move `statusCategory` already makes.
 *
 * Uncapped, deliberately. A truncated transition list would silently move a
 * start date later and shorten a cycle time — a smaller number, arrived at by
 * arithmetic, with nothing to say it was cut. If a cap ever becomes necessary
 * it is reported, like every other cap here.
 */
const statusTransitions = (raw) => {
  const out = [];
  for (const h of (raw.changelog || {}).histories || []) {
    const at = String(h.created || '').slice(0, 10);
    if (!at) continue;
    for (const item of h.items || []) {
      if (String(item.field || '').toLowerCase() !== 'status') continue;
      // The name the site uses, not a category. Deciding what it means is the
      // page's job and the config's.
      out.push({ to: item.toString ?? null, at });
    }
  }
  return out;
};

/**
 * Was this issue put into the sprint after it started?
 *
 * Compared as YYYY-MM-DD strings, which is what the Python fetcher does — so
 * an item added later on the day the sprint opened reads as committed in both.
 * Matching the existing behaviour matters more than being right about the edge
 * case: two producers disagreeing about one issue is worse than both being
 * generous about the same one.
 */
const addedMidSprint = (raw, sprintStart) => {
  const start = String(sprintStart || '').slice(0, 10);
  if (!start) return false;
  const histories = (raw.changelog || {}).histories || [];
  for (const h of histories) {
    const when = String(h.created || '').slice(0, 10);
    if (!when || when <= start) continue;
    for (const item of h.items || []) {
      if (String(item.field || '').toLowerCase() === 'sprint') return true;
    }
  }
  return false;
};

/**
 * Which finished epics a period may credit its value to, and how many it may not.
 *
 * The rule is unchanged and is ADR 0026's: an epic's value belongs to the
 * period it completed in, and a sprint's period is the window it declared —
 * `startDate` to `endDate`. What changes here is that the epics that rule
 * excludes are counted instead of dropped in silence.
 *
 * A board whose finished epics all sit outside the selected sprint's window is
 * an ordinary state, not an error. But from the value tile's seat it is
 * indistinguishable from a board where nobody has priced anything, and those
 * have entirely different fixes — so the tile was left to guess and printed a
 * third explanation for both: that the only priced thing it could see was a
 * story, which was true and was not the reason. `CLAUDE.md`: code that bounds
 * its own output has to say what it dropped.
 *
 * Takes issues that have been through `issueFrom`, not raw Jira bodies, so that
 * "carries a value" is read off the same `businessValue` the page reads and not
 * off a second extraction of the same custom field.
 *
 * An epic with no resolution date is not counted on either side. It has not
 * finished, so no period is being denied it.
 */
export const creditableEpics = (epics, entry) => {
  const start = entry?.startDate;
  const end = entry?.endDate;
  const credited = [];
  let excluded = 0;
  let excludedWithValue = 0;
  // No window, nothing withheld. An entry without both dates never reaches the
  // epic pass at all, so this is unreachable in the resolver — but a count of
  // "every epic on the board" would read to a caller as value this period kept
  // out, and a number that means one thing to its producer and another to its
  // reader is the shape of most of what this repository has had to fix.
  if (!start || !end) return { credited, excluded, excludedWithValue };
  for (const e of epics || []) {
    const done = e?.resolved;
    if (!done) continue;
    if (done >= start && done <= end) {
      credited.push(e);
      continue;
    }
    excluded += 1;
    if (typeof e?.businessValue === 'number' && e.businessValue > 0) excludedWithValue += 1;
  }
  return { credited, excluded, excludedWithValue };
};

/**
 * The envelope `GET api/context?id=…` returns.
 *
 * Three of the four series are empty because this app computes nothing and no
 * route serves them yet. The burndown is no longer one of them: the calculator
 * is provisioned, `metrics.burndown` is served at `/v1/burndown`, and the
 * caller passes the rows in. When they are empty `burndownNote` says which of
 * the four reasons it was — a window has no committed scope to burn down, a
 * sprint can be missing its dates, the calculator can refuse or be
 * unreachable, and a file can simply carry no series. They had one sentence
 * between them and it was the wrong one on every Forge install.
 */
export const contextBody = (entry, issues, orgConfig, setup, valueWindow, burndown) => ({
  // Which of this app's fields a person can actually type into, when that is
  // the difference between "nobody has priced anything" and "nobody *can*".
  // Absent on a transport with no Jira behind it — a file's value came from a
  // file, and there is no screen to be told about. ADR 0025.
  ...(setup ? { setup } : {}),
  // What the window in `creditableEpics` left out, when a producer knows. Absent
  // for the same reason `setup` is: a file's epics were selected when it was
  // baked and there is no board left to ask, so the page keeps the sentences it
  // already had rather than being handed a zero that means "not measured".
  ...(valueWindow ? { valueWindow } : {}),
  context: {
    ...entry,
    // The entry's own as-of, with the planned end as a last resort. This
    // comment used to say the fallback *was* the rule and that matching the
    // live server required it — which was wrong in both directions: a bundle
    // carries a real as-of (today for a running sprint, the completion date for
    // a finished one) and `contextEntry` supplied none, so the two transports
    // were already reporting different elapsed-percentages for the same sprint.
    // Now the entry resolves it the same way and this is only a fallback.
    asOfDate: entry.asOfDate || entry.endDate || null,
    issueCount: issues.length,
  },
  orgConfig: orgConfig || {},
  issues,
  // Was hardcoded `[]` with a comment saying Forge cannot run Python. It still
  // cannot — `metrics.burndown` is served by the hosted calculator now, and the
  // caller does the asking. `burndownNote` says why the series is empty when it
  // is, because "no burndown series in this dataset" blamed a tenant's data for
  // a chart this transport had simply never built.
  burndown: (burndown && burndown.rows) || [],
  // Always sent, `null` when there is nothing to explain — unlike `setup` and
  // `valueWindow`, which are omitted because a producer may genuinely not know.
  // Here it always does: it either built a series or knows why it did not, and
  // an always-present key is one both transports can be held to.
  burndownNote: (burndown && burndown.note) || null,
  history: [],
  releases: [],
  dora: null,
});

/**
 * Not found, in the shape the loopback transport gives a 404 — and saying
 * which of the four reasons it was.
 *
 * The first version said only "unknown context", which is what the page then
 * put in front of a user as *"server returned 404"*. Four quite different
 * situations produce that answer and they have four different fixes; a reader
 * with the bare status has no way to tell a stale bookmark from a board that
 * has moved project.
 */
export const notFound = (id, why) => ({
  // "sprint or window", not "sprint": a flow board's context is neither a
  // sprint nor a mistake, and a message that only knows about sprints reads to
  // its owner as the product not knowing their board exists.
  error: `No sprint or window on this site matches ${JSON.stringify(String(id))}`
    + (why ? ` — ${why}.` : '.'),
});
