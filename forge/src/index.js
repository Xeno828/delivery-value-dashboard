/**
 * Forge resolver.
 *
 * Forge runs Node in Atlassian's sandbox and cannot execute agent/tools/. This
 * does not reimplement them. It pulls the issues, strips them to the fields a
 * calculation reads, posts that to the hosted calculator (service/app.py), and
 * puts the summaries back on the way out.
 *
 * The rule the whole product rests on — one implementation of every figure —
 * survives that. Nothing in this file computes a number.
 * See docs/adr/0008-forge-calls-a-hosted-calculator.md.
 *
 * Status: the app is registered, deployed to development and installed on a
 * dev site; `forge lint` is clean and the declared scopes have been proven
 * against real Jira. The context path below — `contexts` and `context` — is
 * what the dashboard reaches over the bridge, and it is the live one. The
 * `forecast`, `facts` and `sequence` resolvers still point at a calculator
 * that is not hosted anywhere, so they answer with the offline notice until
 * `remotes[0].baseUrl` names a real deployment.
 */

import Resolver from '@forge/resolver';
import api, { route, invokeRemote } from '@forge/api';
import { chat } from '@forge/llm';
import { kvs } from '@forge/kvs';
import { Queue } from '@forge/events';
import { randomUUID } from 'node:crypto';
import os from 'node:os';

// The Python runtime inside this function — `agent/tools/` and
// `service/routes.py` under WebAssembly, loaded from a generated module.
// CommonJS, hence the default import. ADR 0031.
import runtime from './runtime.js';
import {
  CONSUMER_ROUTES, JOB_ID, JOB_LIFETIME_MS, JOB_TTL, KIND_OF, QUEUE_KEY,
  chunkPayload, collect, failedSentence, forecastRefusal, inflightKey, jobKey, jobRow,
  joinPayload, payloadKey, resultKey, resultRow, retryRefusal, riskKeys, tooLarge,
  wrongRoute,
} from './jobs.js';

import {
  CONFIG_PROPERTY_KEY, contextEntry, contextsBody, contextBody, contextId,
  creditableEpics,
  noDaysYetNote,
  findStoryPointField, mergeOrgConfig, parseContextId, issueFrom, notFound,
  recentSprints, statusesFromJira, validateOrgConfig, findBusinessValueField,
  findValueBasisField, findAskField, findSizeField, asksFromIssues,
  WINDOW_DAYS, windowEntry, windowMembershipJql, contextsLabel,
  MAX_TREND_SPRINTS,
} from './jira.js';
import { deliveryBlockers } from './brief.js';
import { boardsIn, notifyPayload, problemsIn } from './recipients.js';
import { AUDIT_KEY, appendAudit, auditEntry } from './audit.js';
import { briefsForBoard, sectionsFor } from './compose.js';
import { ADMIN_PERMISSION, editability } from './permissions.js';
import {
  entryFrom, problemsInRow, readSeries, recordable, seriesKey,
  statusFingerprint, writeSeries,
} from './series.js';
import { MAX_MATCHES, MAX_NAMES, idsToAsk, matchNote, nameNote, namesFrom,
  peopleFrom } from './people.js';

const resolver = new Resolver();

/**
 * The only issue fields a calculation reads. Verified empirically, not guessed:
 * forecast.build() over a dataset stripped to these produces byte-identical
 * figures to one with everything. The fields left behind — summary, assignee,
 * epic, labels, url, valueBasis — are the sensitive half, and the calculator
 * refuses the payload outright if any of them arrive.
 */
// `type` and `isSubtask` are here because which issues count as items is the
// organisation's answer and the *tools* apply it, so the tools have to be able
// to see both. Neither is free text and neither identifies a person; `type` is
// a Jira configuration label like `status`, which was already here. ADR 0024.
//
// The reason sits above the array rather than inside it: `tests/test_service.py`
// compares this list against the service's by pulling quoted strings out of the
// source, and a comment between the entries put its own words into the set.
const CALC_FIELDS = [
  'key', 'created', 'started', 'resolved', 'statusCategory', 'status',
  'storyPoints', 'priority', 'dueDate', 'flagged', 'addedMidSprint',
  'contextId', 'epicKey', 'type', 'isSubtask',
  'businessValue', 'hierarchyLevel',
];

/** Everything the calculator must never see. Kept here so the two lists can be
 *  compared by eye against service/app.py's FREE_TEXT_FIELDS. */
const NEVER_SEND = ['summary', 'assignee', 'epic', 'labels', 'url', 'valueBasis'];

const projectIssue = (issue) => {
  const out = {};
  for (const f of CALC_FIELDS) {
    if (issue[f] !== undefined && issue[f] !== null) out[f] = issue[f];
  }
  return out;
};

/**
 * Belt and braces. The projection above is an allow-list, so a stray field
 * cannot pass — but a future edit that turns it into a deny-list would, and
 * this is the assertion that would catch it before a customer's issue titles
 * left their tenant. Cheap, and it fails closed.
 */
const assertNoFreeText = (projected) => {
  for (const issue of projected) {
    for (const f of NEVER_SEND) {
      if (f in issue) {
        throw new Error(
          `refusing to send: projection leaked "${f}". Nothing was calculated.`,
        );
      }
    }
  }
};

/**
 * Put the human-readable fields back, by key, from the copy Forge already
 * holds. The calculator echoes issue keys inside item_risk; the summaries and
 * assignees that belong beside them never left the tenant.
 */
const reattach = (result, byKey) => {
  const items = result?.item_risk?.items;
  if (!Array.isArray(items)) return result;
  for (const item of items) {
    const local = byKey.get(item.key);
    if (!local) continue;
    item.summary = local.summary ?? '';
    item.assignee = local.assignee ?? null;
  }
  return result;
};

/**
 * The same refusal as `assertNoFreeText`, for the other thing that goes out.
 *
 * An ask is built here rather than projected from an issue, so the allow-list
 * that protects the issue payload never looks at it. A field added to an ask in
 * a later change would reach the calculator by a door nobody was watching, and
 * `title` is the obvious one to add — it is what a reader wants beside an
 * ordering, and it is a customer's words for a customer's work.
 */
const ASK_TEXT_FIELDS = ['title', 'basis', 'team', 'summary', 'problemStatement',
  'successMeasure', 'assumptions', 'dependencies'];
const assertAsksCarryNoText = (asks) => {
  for (const a of asks || []) {
    for (const f of ASK_TEXT_FIELDS) {
      if (f in a) {
        throw new Error(`refusing to send: ask "${a.id}" carries "${f}". Nothing was sequenced.`);
      }
    }
    if (a.valueEstimate && 'basis' in a.valueEstimate) {
      throw new Error(`refusing to send: ask "${a.id}" carries a value basis. Nothing was sequenced.`);
    }
  }
};

/* `reattachAsks` — the title and the basis put back beside each ordering by
   id — lives in jobs.js now, because the join happens when a sequencing
   result is *collected* rather than when it is called for. */

/**
 * One call to the calculator.
 *
 * `invokeRemote` rather than `fetch`, and the difference is the whole point:
 * only `invokeRemote` attaches the Forge Invocation Token, which is what lets
 * the service know the call came from this app and which installation it is
 * for, without this app holding a secret of its own. Declaring the `remotes`
 * entry is what makes the egress *permitted*; it is not what authenticates it.
 * This code used to say otherwise and used to call `fetch` against a URL out of
 * `process.env.CALCULATOR_URL`, which sends no Authorization header at all — so
 * pointing the manifest at a real host would have returned 401 on every call,
 * in either of the service's auth modes. The remote also needs
 * `operations: [compute]`, which is what Forge requires before `invokeRemote`
 * will resolve this key.
 *
 * The URL is gone with it, and that is a gain rather than a loss. A URL built
 * here is one URL for every installation in the world; a `baseUrl` resolved
 * from the manifest is chosen per install from the customer's own Atlassian
 * data residency setting, so this app never decides which region a tenant's
 * numbers are computed in. docs/adr/0012.
 *
 * The remote key is a literal so `tests/test_service.py` can hold it against
 * the manifest: a mistyped key fails at runtime, inside a tenant, which is the
 * same failure the egress rule used to be checked for.
 */
/**
 * One call to the Python inside this function. ADR 0031.
 *
 * The drop-in for `callCalculator` as routes move: the same route names, the
 * same bodies, and the same two answers — the envelope on success, or
 * `{available: false, sentence}` with the route's own sentence on a refusal —
 * so a caller changes one identifier and nothing downstream of it. The
 * runtime loads from the memory snapshot on this function, 1.3 s cold
 * against 11 s, because it answers under the adapter's clock.
 *
 * Routes move here one per commit, and a route is answered here or by the
 * calculator, never both: `tests/test_service.py` holds that the set of
 * routes this is called with and the set `callCalculator` is called with do
 * not overlap. Git is the switch.
 */
const answerHere = async (path, body) => {
  const { status, payload } = await runtime.answer(path, body, { snapshot: true });
  if (status !== 200 || !payload || payload.ok === false) {
    return {
      available: false,
      sentence: payload?.error ?? `The calculation returned ${status}.`,
    };
  }
  return payload;
};

const callCalculator = async (path, body) => {
  const res = await invokeRemote('calculator', {
    path,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    // Never surface the body: a proxy error page is not something to render
    // into a Jira panel.
    return { available: false, sentence: `The calculator returned ${res.status}.` };
  }
  if (!res.ok || parsed.ok === false) {
    return {
      available: false,
      sentence: parsed.error ?? `The calculator returned ${res.status}.`,
    };
  }
  return parsed;
};

/**
 * Which authority a Jira read is made with.
 *
 * `'user'` everywhere the panel is involved, and that is not a default chosen
 * for tidiness: reading as the person looking at the page is **why** a viewer
 * can only ever see issues they could already see in Jira. Jira enforces it on
 * every request made on somebody's behalf, so permission mirroring — roadmap
 * item 5 — holds for free on that path and would have to be built if it did
 * not.
 *
 * `'app'` exists for the scheduled brief alone, which has no user to be. What
 * it costs, what checks it, and why it was declined for two versions before
 * being taken deliberately are in ADR 0013. In short: `restrict` means Jira
 * decides who may *receive* a brief, and nothing checks what the brief *says*
 * about issues a recipient cannot see.
 *
 * A parameter rather than ambient state, and defaulted to `'user'`, so a new
 * read added without thinking about it is added on the safe side.
 */
const jira = (as) => (as === 'app' ? api.asApp() : api.asUser());

/** Pull one board's issues, for the calculator path. */
const fetchBoardIssues = async (boardId, as) => {
  const spField = await storyPointFieldFor(as);
  const id = String(boardId ?? '').replace(/[^0-9]/g, '');
  if (!id) throw new Error('no board id');

  const issues = [];
  let startAt = 0;
  for (;;) {
    const res = await jira(as)
      .requestJira(
        route`/rest/agile/1.0/board/${id}/issue?startAt=${startAt}&maxResults=100`,
      );
    if (!res.ok) throw new Error(`Jira returned ${res.status}`);
    const body = await res.json();
    const page = body.issues ?? [];
    for (const i of page) {
      issues.push({
        key: i.key,
        summary: i.fields?.summary ?? '',
        assignee: i.fields?.assignee?.displayName ?? null,
        status: i.fields?.status?.name ?? null,
        // Left uncategorised on purpose. Which statuses mean done is
        // organisation config (config/organisation.json, resolved by
        // agent/tools/orgconfig.py) and a third copy of that rule written here
        // is exactly the divergence the config exists to prevent. The raw name
        // goes in the payload; the calculator applies the config.
        storyPoints: spField ? (i.fields?.[spField] ?? 0) : null,
        priority: i.fields?.priority?.name ?? null,
        created: (i.fields?.created ?? '').slice(0, 10) || null,
        resolved: (i.fields?.resolutiondate ?? '').slice(0, 10) || null,
        dueDate: i.fields?.duedate ?? null,
      });
    }
    startAt += page.length;
    if (!page.length || startAt >= (body.total ?? 0)) break;
  }
  return issues;
};

const compute = async (path, { boardId, orgConfig, meta, extra }, as) => {
  const local = await fetchBoardIssues(boardId, as);
  const byKey = new Map(local.map((i) => [i.key, i]));

  const projected = local.map(projectIssue);
  assertNoFreeText(projected);

  // In-function since the facts route moved (ADR 0031). Only `facts` reaches
  // this helper, so the whole of it is answered by the Python in this function.
  const answer = await answerHere(path, {
    dataset: { issues: projected, meta: meta ?? {}, orgConfig: orgConfig ?? {} },
    ...(extra ?? {}),
  });
  if (answer.available === false) return answer;

  return {
    available: true,
    // Passed through so the panel can say which calendar produced the numbers,
    // exactly as the dashboard footer and the facts pack do.
    calendar: answer.calendar,
    result: reattach(answer.result, byKey),
  };
};

/* ------------------------------------------------------------------------
   The context path — what the dashboard itself asks for over the bridge.

   These answer the same two questions `scripts/serve_live.py` answers over
   `api/contexts` and `api/context?id=`, and they return the same body shapes.
   One contract, two transports: a page that behaved differently depending on
   how it was reached would be the divergence ADR 0005 exists to prevent, and
   `tests/test_service.py` compares the two envelopes on every push.

   The reply is wrapped as {status, body} because the page's transport wants
   the thing an HTTP status carries — 404 for a sprint this site does not have
   is a different answer from a failure, and the page says different words for
   each. The *body* is the contract; the status is transport-level and each
   transport supplies its own.
   --------------------------------------------------------------------- */

/** Sprints per board offered in the picker, when the site's config states no
 *  window of its own. The live server's default, for the same reason: a
 *  forecast samples a team's recent history, not its whole life.
 *
 *  A default and no longer a constant — roadmap item 4b. It was hardcoded here
 *  and in two generators, and every one of them cut the older sprints without
 *  saying so. `trendSprints` travels inside the resolved config like every
 *  other assumption, and what it cut is reported rather than implied. */
const SPRINTS_PER_BOARD = 6;

/** The window this project states, or the default. Bounded by the validator on
 *  the way in, so a config that got past `validate` cannot ask for a thousand
 *  sprints' worth of issue fetches here. */
const trendWindow = (orgConfig) => {
  const n = orgConfig?.trendSprints;
  return Number.isInteger(n) && n >= 2 && n <= MAX_TREND_SPRINTS
    ? n : SPRINTS_PER_BOARD;
};

/** A page count no real project reaches, so a Jira that stopped sending
 *  `isLast` stops this rather than looping. It throws rather than returning
 *  what it has — a truncated list of a customer's boards reads as a complete
 *  one, and this repository has shipped that bug twice. */
const MAX_PAGES = 20;

/**
 * A Jira failure that remembers what Jira said.
 *
 * Without the status, every caller has to treat every failure alike — and the
 * one that mattered was `sprintsFor`, which swallowed all of them as "this
 * board has no sprints". A 403 then presented as a project with no boards, on
 * a page with nothing on it and nothing to say why.
 */
const jiraError = (what, status, body) => {
  const first = (body && body.errorMessages && body.errorMessages[0]) || '';
  const err = new Error(`${what}: Jira returned ${status}${first ? ` — ${first}` : ''}`);
  err.status = status;
  return err;
};

const bodyOf = async (res) => {
  try {
    return await res.json();
  } catch {
    return null;
  }
};

/** Every page of an Agile list endpoint (`{values, isLast, total}`). */
const pagedValues = async (routeAt, what, as) => {
  const out = [];
  let startAt = 0;
  for (let page = 0; ; page += 1) {
    if (page >= MAX_PAGES) {
      throw new Error(
        `${what}: more than ${MAX_PAGES} pages. ${out.length} were read and none are ` +
        'reported, because a list cut short here would read as a complete one.',
      );
    }
    const res = await jira(as).requestJira(routeAt(startAt));
    if (!res.ok) throw jiraError(what, res.status, await bodyOf(res));
    const body = await res.json();
    const values = body.values ?? [];
    out.push(...values);
    startAt += values.length;
    if (!values.length || body.isLast === true) break;
    if (typeof body.total === 'number' && startAt >= body.total) break;
  }
  return out;
};

/** Every issue in one sprint. `expand=changelog` is what makes addedMidSprint
 *  real rather than false-by-default — see the note in jira.js about why that
 *  particular default is a wrong answer rather than a missing one. */
// Named explicitly, so a field this app does not read is a field Jira does not
// send. That is the right default and it has one consequence worth stating: a
// field added to the *projection* and not to this list is a field that is never
// returned, so it reads as absent on every issue forever — no error, no empty
// response, just a figure that is quietly never there. `businessValue` was
// exactly that for the length of one deploy. ADR 0025.
//
// The app's own two fields travel as a named pair rather than as two more
// positional arguments. They are both custom field ids — two strings, adjacent
// in every signature — and transposing them would read the basis sentence as a
// number and the number as the basis. `valueOf` would return null and `basisOf`
// would return '', so the page would say "nobody has recorded a value" and
// "no basis recorded" on a board where somebody had recorded both. Nothing
// would throw and nothing would look wrong.
const issueFields = (storyPointField, appFields) => [
  'summary', 'issuetype', 'status', 'assignee', 'priority', 'parent',
  'created', 'resolutiondate', 'duedate', 'labels', 'flagged',
  ...(storyPointField ? [storyPointField] : []),
  ...(appFields?.value ? [appFields.value] : []),
  ...(appFields?.basis ? [appFields.basis] : []),
  ...(appFields?.candidate ? [appFields.candidate] : []),
  ...(appFields?.tshirt ? [appFields.tshirt] : []),
].join(',');

const fetchSprintIssues = async (boardId, sprintId, storyPointField, as, appFields) => {
  // Named explicitly, and the story-point field is named by the id this site
  // actually uses rather than one guessed at. `*navigable` would also work and
  // would be worse: it pulls every custom field on every issue, including free
  // text this app has no business holding.
  const fields = issueFields(storyPointField, appFields);

  const out = [];
  let startAt = 0;
  for (let page = 0; ; page += 1) {
    if (page >= MAX_PAGES) {
      throw new Error(
        `issues in sprint ${sprintId}: more than ${MAX_PAGES} pages. ${out.length} were ` +
        'read and none are reported — a sprint shown short is a burndown that is wrong.',
      );
    }
    const res = await jira(as).requestJira(
      route`/rest/agile/1.0/board/${boardId}/sprint/${sprintId}/issue?startAt=${startAt}&maxResults=100&fields=${fields}&expand=changelog`,
    );
    if (!res.ok) {
      throw jiraError(`issues in sprint ${sprintId}`, res.status, await bodyOf(res));
    }
    const body = await res.json();
    const page_ = body.issues ?? [];
    out.push(...page_);
    startAt += page_.length;
    if (!page_.length || startAt >= (body.total ?? startAt)) break;
  }
  return out;
};

/**
 * Every issue in one window, over the board's own issue endpoint.
 *
 * `/board/{id}/issue` returns what is on the board *now*, which is the wrong
 * question for a closed sprint and exactly the right one for a flow board:
 * there is no historical membership to recover, only the board and the dates.
 * The JQL narrows it to the window's membership and nothing else — the board
 * scoping is the endpoint's own, so no filter id is read and no scope beyond
 * the ones already granted is needed.
 *
 * `expand=changelog` for the same reason the sprint fetch has it. It buys
 * nothing today — `addedMidSprint` is meaningless without a sprint and is
 * false here — and it is what `started` will be read from when the transitions
 * go on the wire, which is the field a flow board most needs. Kept so the two
 * fetches differ in their query and not in their shape.
 */
const fetchWindowIssues = async (boardId, entry, storyPointField, as, appFields) => {
  const fields = issueFields(storyPointField, appFields);
  const jql = `${windowMembershipJql(entry.startDate, entry.endDate)} ORDER BY created ASC`;

  const out = [];
  let startAt = 0;
  for (let page = 0; ; page += 1) {
    if (page >= MAX_PAGES) {
      throw new Error(
        `issues in window ${entry.id}: more than ${MAX_PAGES} pages. ${out.length} were `
        + 'read and none are reported — a window shown short is a throughput series that '
        + 'is wrong, and it would read as a complete one.',
      );
    }
    const res = await jira(as).requestJira(
      route`/rest/agile/1.0/board/${boardId}/issue?startAt=${startAt}&maxResults=100&fields=${fields}&expand=changelog&jql=${jql}`,
    );
    if (!res.ok) {
      throw jiraError(`issues in window ${entry.id}`, res.status, await bodyOf(res));
    }
    const body = await res.json();
    const page_ = body.issues ?? [];
    out.push(...page_);
    startAt += page_.length;
    if (!page_.length || startAt >= (body.total ?? startAt)) break;
  }
  return out;
};

/** Today, as the resolver's own clock reads it. A window's dates come from
 *  here rather than from the page: an as-of a caller could set is a caller
 *  choosing which slice of a board to be shown, through an id the picker
 *  never offered. */
const todayISO = () => new Date().toISOString().slice(0, 10);

/**
 * Which field this site calls story points.
 *
 * Memoised because it is the same answer for every issue on every board of a
 * site, and a field list is not something to re-fetch per sprint. A Forge
 * function may be a cold start, in which case this costs one call; when it is
 * warm it costs nothing. The value is deliberately cached including `null` —
 * "this site has no story-point field" is an answer, and re-asking on every
 * request would not change it.
 */
let storyPointField;
/**
 * This app's own Business Value field id on this site — ADR 0025.
 *
 * Looked up the same way and cached the same way as the story-point field, but
 * for a different reason: that one is a guess among three known spellings,
 * because it is a field this app did not create. This one is a *fact* — the
 * key carries the module key that declared it — so a site with its own field
 * called "Business Value" is not mistaken for this one.
 *
 * `null` means the module has not produced a field on this site yet, which is
 * the state every installation is in until the app version declaring it is
 * installed. That is reported rather than treated as "nobody has entered a
 * value", because the two have entirely different fixes.
 */
let _fieldList;
/** The site's field list, read once. Three fields come out of it, and two round
 *  trips to answer one question are two chances to disagree about what is
 *  installed. */
const fieldListFor = async (as) => {
  if (_fieldList !== undefined) return _fieldList;
  try {
    const res = await jira(as).requestJira(route`/rest/api/3/field`);
    _fieldList = res.ok ? await res.json() : [];
  } catch {
    _fieldList = [];
  }
  return _fieldList;
};

/** The three fields this app reads off an issue.
 *
 *  Two are its own, found by module key. The third is whichever field the
 *  organisation says marks an ask — ours by default, theirs if they name one —
 *  which is why this takes the resolved config rather than memoising one
 *  answer. Candidacy is the thing every organisation defines differently, and
 *  the app declares a default rather than insisting on it. ADR 0028. */
const appFieldsFor = async (as, askField, sizeField) => {
  const fields = await fieldListFor(as);
  return {
    value: findBusinessValueField(fields),
    basis: findValueBasisField(fields),
    candidate: findAskField(fields, askField),
    tshirt: findSizeField(fields, sizeField),
  };
};

const storyPointFieldFor = async (as) => {
  if (storyPointField !== undefined) return storyPointField;
  const res = await jira(as).requestJira(route`/rest/api/3/field`);
  if (!res.ok) throw jiraError('the field list', res.status, await bodyOf(res));
  storyPointField = findStoryPointField(await res.json());
  return storyPointField;
};

/**
 * The organisation config for one project, resolved once.
 *
 * Which statuses mean done comes from the site's own status definitions; the
 * working week, the holiday calendar and the sprint length come from a project
 * property, because Jira has no notion of any of them. Absent, the page's
 * documented defaults apply — and the footer names the calendar it used, so
 * defaults are visible rather than assumed.
 *
 * A stated config that is not usable stops the request rather than being
 * partially applied. `orgconfig.py` refuses a bad file for the same reason: a
 * typo in `workingWeek` that quietly reverted to a five-day week would move
 * every forecast in the product with nothing saying so.
 */
const orgConfigs = new Map();
const orgConfigFor = async (projectKey, as) => {
  if (orgConfigs.has(projectKey)) return orgConfigs.get(projectKey);

  const statusRes = await jira(as).requestJira(route`/rest/api/3/status`);
  if (!statusRes.ok) throw jiraError('the status list', statusRes.status, await bodyOf(statusRes));
  const fromJira = { statuses: statusesFromJira(await statusRes.json()) };

  const propRes = await jira(as).requestJira(
    route`/rest/api/3/project/${projectKey}/properties/${CONFIG_PROPERTY_KEY}`,
  );
  let stated = {};
  if (propRes.status !== 404) {
    if (!propRes.ok) {
      throw jiraError(`the ${CONFIG_PROPERTY_KEY} project property`,
        propRes.status, await bodyOf(propRes));
    }
    const body = await propRes.json();
    stated = body?.value ?? {};
    if (stated === null || typeof stated !== 'object' || Array.isArray(stated)) {
      throw new Error(
        `The ${CONFIG_PROPERTY_KEY} property on project ${projectKey} is not an object, `
        + 'so no calendar was read from it and nothing was reported under it.',
      );
    }
    const problems = validateOrgConfig(stated);
    if (problems.length) {
      throw new Error(
        `The ${CONFIG_PROPERTY_KEY} property on project ${projectKey} is not usable, so `
        + `nothing was measured under it: ${problems.join('; ')}.`,
      );
    }
  }

  const resolved = {
    config: mergeOrgConfig(fromJira, stated),
    // Whether the calendar half was stated or defaulted. Reported, because a
    // five-day week nobody chose looks exactly like a five-day week somebody
    // did, and every working-day figure on the page rests on it.
    statedCalendar: ['workingWeek', 'holidays', 'sprintLengthDays']
      .some((k) => k in stated),
  };
  orgConfigs.set(projectKey, resolved);
  return resolved;
};

/**
 * One board's sprints, or the reason there are none to have.
 *
 * A kanban board has no sprints and Jira answers 400 for it. That is a fact
 * about the board, and skipping it is right. **Everything else is a failure**,
 * and the first version of this caught all of them the same way — so a 403
 * from a scope that had not been consented to came back as "this board has no
 * sprints", the picker came up empty, and the page had nothing on it and no
 * explanation on it either. That is the shape this repository keeps paying
 * for, and it cost a deploy cycle here too.
 */
const sprintsFor = async (board, as) => {
  try {
    return {
      sprints: await pagedValues(
        (startAt) => route`/rest/agile/1.0/board/${board.id}/sprint?state=active,closed&startAt=${startAt}&maxResults=50`,
        `sprints on board ${board.id}`, as,
      ),
    };
  } catch (err) {
    if (err.status === 400) return { skipped: 'does not use sprints' };
    throw err;
  }
};

/**
 * Turn a thrown failure into an answer the page can put on screen.
 *
 * A resolver that throws rejects `invoke()`, and the page treats a rejection
 * the way it treats a dead loopback server — silently, because over loopback
 * nothing running is the normal case. Over the bridge it is not: something
 * answered, and it said no. Swallowing that is a blank dashboard with no
 * reason on it, which is what this app shipped for one deploy cycle.
 */
const answering = (fn) => async (req) => {
  try {
    return await fn(req);
  } catch (err) {
    return {
      // Jira's own status where there is one, so a 403 reads as a permission
      // problem rather than as a bug in this app.
      status: err.status ?? 502,
      body: { error: String((err && err.message) || err) },
    };
  }
};

/**
 * Every sprint on every board of the project this page is open in.
 *
 * The project comes from Forge's own context rather than from the page, so the
 * page sends nothing and cannot ask about a project it is not displayed in.
 */
/**
 * Every context this project offers, and what had to be left out.
 *
 * Extracted from the `contexts` resolver because the forecast needs the same
 * list: a forecast samples a team's whole history, so it has to know every
 * context that history is spread across before it can ask for one. Building it
 * twice would be two answers to "what boards does this project have", and the
 * picker and the forecast disagreeing about that is the kind of difference
 * nothing on the page would show.
 */
const projectContexts = async (projectKey, as, window) => {
  const boards = await pagedValues(
    (startAt) => route`/rest/agile/1.0/board?projectKeyOrId=${projectKey}&startAt=${startAt}&maxResults=50`,
    `boards in project ${projectKey}`, as,
  );

  const contexts = [];
  const asOf = todayISO();
  // Two different things used to be one count. A board with no sprint support
  // is a flow board and is now offered a window each (ADR 0011); a board that
  // *has* sprints and has never run one has nothing to offer and is a
  // different sentence. Reporting them together would have described the
  // second as the first the moment windows existed.
  let flowBoards = 0;
  let sprintBoardsWithNoSprints = 0;
  const offered = new Map();
  for (const board of boards) {
    const got = await sprintsFor(board, as);
    if (got.skipped) {
      flowBoards += 1;
      for (const days of WINDOW_DAYS) {
        contexts.push(windowEntry(board, days, asOf, projectKey));
      }
      continue;
    }
    const keep = Number.isInteger(window) ? window : SPRINTS_PER_BOARD;
    const recent = recentSprints(got.sprints, keep);
    if (!recent.length) { sprintBoardsWithNoSprints += 1; continue; }
    // What the board has against what the window kept, per board, so a trend
    // can say what it is not showing. No silent caps: six sprints of a board
    // with twenty reads as the whole record unless something says otherwise.
    offered.set(String(board.id), got.sprints.length);
    for (const sprint of recent) {
      contexts.push(contextEntry(board, sprint, projectKey, todayISO()));
    }
  }
  return { boards, contexts, flowBoards, sprintBoardsWithNoSprints,
           offered: Object.fromEntries(offered) };
};

/**
 * The project a board belongs to, for a caller that has a board id and no page.
 *
 * The panel never needs this — it is opened *in* a project and reads the key
 * off the module context. A scheduled run has neither, and the recipient config
 * is keyed by board, so this is the one hop between them.
 */
const boardProject = async (boardId, as) => {
  const id = String(boardId ?? '').replace(/[^0-9]/g, '');
  if (!id) return null;
  const res = await jira(as).requestJira(route`/rest/agile/1.0/board/${id}`);
  if (!res.ok) return null;
  const body = await res.json();
  return body?.location?.projectKey ?? null;
};

/** The project this module is open on, or a body saying why there is none. */
const moduleProjectKey = (context) => context?.extension?.project?.key ?? null;

const NO_PROJECT = (context) => ({
  status: 400,
  body: {
    error: 'This module was not opened on a Jira project, so there is no project '
         + `to read boards from (module ${context?.moduleKey ?? 'unknown'}). `
         + 'Nothing was queried.',
  },
});

resolver.define('contexts', answering(async ({ context }) => {
  const projectKey = moduleProjectKey(context);
  if (!projectKey) return NO_PROJECT(context);

  const { boards, contexts, flowBoards, sprintBoardsWithNoSprints } =
    await projectContexts(projectKey);

  // A project with boards but no sprints on any of them is a real state and an
  // invisible one: the picker comes up empty and reads as a broken app. Say it
  // instead, in a sentence the page can put on screen.
  // A board with no sprints is no longer a reason to have nothing to show —
  // it gets windows. What is left is a project with no visible boards, or one
  // whose boards all run sprints and have never run one, and those are
  // different problems with different answers.
  if (!contexts.length) {
    return {
      status: 404,
      body: {
        error: boards.length
          ? `Project ${projectKey} has ${boards.length} board`
            + `${boards.length === 1 ? '' : 's'}, and ${boards.length === 1 ? 'it runs' : 'they all run'} `
            + 'sprints but have never started one. There is nothing to report on yet.'
          : `No boards are visible in project ${projectKey}. Either it has none, or `
            + 'this Jira account cannot see them.',
      },
    };
  }

  // What was left out is said out loud, in the line the page prints in its
  // footer. A picker quietly missing a board is indistinguishable from a
  // project that does not have one.
  const org = await orgConfigFor(projectKey);
  const label = contextsLabel({
    projectKey,
    boards: boards.length,
    flowBoards,
    sprintBoardsWithNoSprints,
    hasStoryPointField: Boolean(await storyPointFieldFor()),
    statedCalendar: org.statedCalendar,
  });

  return {
    status: 200,
    body: contextsBody(label, contexts, org.config),
  };
}));

/**
 * One context's issues, in the shape the page and the calculator both read.
 *
 * Extracted so the forecast can gather several contexts' worth. It stamps
 * `contextId`, which `issueFrom` deliberately does not: over the bridge the
 * page re-tags these itself in `loadContext()` and a value from Jira would only
 * invite the two to disagree. The calculator has no page to re-tag anything,
 * and `selection.forecast_for` filters the team's history by exactly this
 * field — an issue reaching it untagged is an issue silently dropped from the
 * sample, which is the narrowing this whole route is arranged to prevent.
 */
/**
 * Which of this app's fields a person can actually type into, on this board.
 *
 * **The app has been guessing.** The value tile says *"If this site has just
 * installed the app, its Business Value field exists but a Jira administrator
 * has to add it to a screen"* — one hedge covering two states with entirely
 * different fixes, in a product whose whole claim is telling a reader which of
 * several reasons applies.
 *
 * `/rest/api/3/issue/{key}/editmeta` answers it, with the ordinary issue read
 * this app already has and no new scope: it returns exactly the fields editable
 * on that issue's screens. Sampling one epic answers it for that epic's screen
 * scheme, which is the honest scope — the reply is about *this board's epics*
 * and not about the site, and screen schemes differ per project and issue type.
 *
 * Three states per field, three fixes:
 *
 *   absent from the site   the app is not installed, or not upgraded to the
 *                          version declaring it
 *   present, not on screen an administrator must add it, and no scope lets this
 *                          app do it for them
 *   on screen              it is answerable, and anything missing is unanswered
 *
 * `null` when there is no epic to sample or the call fails — unknown, said as
 * unknown, rather than reported as either of the three.
 */
const fieldsOnScreen = async (epicKey, as) => {
  if (!epicKey) return null;
  try {
    const res = await jira(as).requestJira(
      route`/rest/api/3/issue/${epicKey}/editmeta`,
    );
    if (!res.ok) return null;
    const body = await res.json();
    const fields = body?.fields;
    return fields && typeof fields === 'object' ? new Set(Object.keys(fields)) : null;
  } catch {
    return null;
  }
};

/** One field's state, as a word the page can act on rather than a sentence it
 *  has to parse. `unknown` is a fourth answer and not a fourth failure. */
const fieldState = (fieldId, onScreen) => {
  if (!fieldId) return 'absent';
  if (onScreen === null) return 'unknown';
  return onScreen.has(fieldId) ? 'ready' : 'off-screen';
};

/**
 * The board's epics, as issues, with their fields — ADR 0026.
 *
 * **Epics are not on a scrum board and never come back from a sprint fetch.**
 * *"Epic issues do not belong to the scrum boards"* is Jira's own description
 * of the design, and it is why declaring a Business Value field (ADR 0025) was
 * not enough on its own: the field existed, an administrator put it on a
 * screen, somebody typed a number into an epic, and the dashboard fetched every
 * issue in the sprint — none of which was that epic.
 *
 * So they are fetched separately: the board's epic list, then each one as an
 * issue for its fields. `1 + E` calls, once per invocation rather than once per
 * context, because a board has tens of epics and a history route reads a dozen
 * contexts.
 *
 * Capped, and the cap is reported rather than applied quietly — a board whose
 * epics were truncated would report less value than it delivered, with nothing
 * saying so.
 */
const MAX_EPICS = 200;
let _epics = {};
const boardEpicsFor = async (boardId, as, appFields, spField) => {
  const cacheKey = String(boardId);
  if (_epics[cacheKey]) return _epics[cacheKey];

  const listed = [];
  let startAt = 0;
  try {
    for (let page = 0; page < 20; page += 1) {
      const res = await jira(as).requestJira(
        route`/rest/agile/1.0/board/${boardId}/epic?startAt=${startAt}&maxResults=50`,
      );
      if (!res.ok) break;
      const body = await res.json();
      const values = body.values ?? [];
      listed.push(...values);
      startAt += values.length;
      if (!values.length || body.isLast || listed.length >= MAX_EPICS) break;
    }
  } catch {
    // A board with no epic support answers 4xx here, which is not an error —
    // it is a board without epics, and it has no value to report.
  }

  const fields = issueFields(spField, appFields);
  const out = [];
  for (const e of listed.slice(0, MAX_EPICS)) {
    try {
      const res = await jira(as).requestJira(
        route`/rest/api/3/issue/${e.key}?fields=${fields}`,
      );
      if (res.ok) out.push(await res.json());
    } catch { /* one unreadable epic is not a reason to report no value */ }
  }
  _epics[cacheKey] = { epics: out, dropped: Math.max(listed.length - MAX_EPICS, 0) };
  return _epics[cacheKey];
};

const issuesForEntry = async (entry, spField, siteUrl, as) => {
  const parsed = parseContextId(entry.id);
  // Which field marks an ask is config, so it is resolved before the fields
  // are, not after. ADR 0028.
  const entryCfg = (await orgConfigFor(entry.projectKey, as)).config;
  const appFields = await appFieldsFor(as, entryCfg?.askField, entryCfg?.sizeField);
  const raw = entry.kind === 'window'
    ? await fetchWindowIssues(parsed.boardId, entry, spField, as, appFields)
    : await fetchSprintIssues(parsed.boardId, parsed.sprintId, spField, as, appFields);
  const mapped = raw.map((r) => ({
    ...issueFrom(r, {
      // Undefined for a window, which is the honest value: `addedMidSprint` is
      // "the sprint field changed after the sprint began", and a board with no
      // sprints has no such moment. It goes out false — and unlike the false the
      // resolver used to send for a *sprint*, this one is not a claim that
      // nothing was added. The tile that reads it refuses on a flow board rather
      // than scoring it, which is where that has to be honoured.
      sprintStart: entry.kind === 'window' ? null : entry.startDate,
      storyPointField: spField,
      // This app's own field, so a value somebody typed in Jira reaches the
      // page. Null until the version declaring the module is installed, and
      // `issueFrom` reads that as "nobody has said" rather than as zero.
      // ADR 0025.
      businessValueField: appFields.value,
      // And the sentence beside it — ADR 0027. Absent until an admin puts this
      // field on a screen too, which is a separate act from putting the value
      // field on one; the tile says "no basis recorded" for both, because from
      // a reader's seat they are the same missing sentence.
      valueBasisField: appFields.basis,
      // ADR 0028. Absent until the site has the field on a screen and somebody
      // has answered it, which is the state every board starts in.
      askFieldId: appFields.candidate,
      sizeFieldId: appFields.tshirt,
      // Only so an issue key is a link. Absent, the page leaves it as text
      // rather than guessing a host.
      siteUrl,
    }),
    contextId: entry.id,
  }));

  // The epics that *finished* inside this period — ADR 0026. Value is credited
  // to the period an epic completed in, because that is the only moment about
  // it this product can date: an epic spans sprints, and spreading its value
  // across them by counting its children would be the double count the level
  // rule exists to prevent.
  //
  // A window has dates too, so this is not sprint-only. An entry with no dates
  // gets none, rather than every epic the board has ever finished.
  let valueWindow = null;
  if (entry.startDate && entry.endDate && appFields.value) {
    const { epics } = await boardEpicsFor(parsed.boardId, as, appFields, spField);
    // Mapped before they are partitioned, so "finished" and "carries a value"
    // are read off the same fields the page reads. Mapping an epic the window
    // then excludes costs nothing — it is pure — and reading its value a second
    // way to count it would be the second implementation this repository keeps
    // finding at the bottom of a disagreement.
    const all = epics.map((raw) => issueFrom(raw, {
      sprintStart: entry.kind === 'window' ? null : entry.startDate,
      storyPointField: spField,
      businessValueField: appFields.value,
      valueBasisField: appFields.basis,
      askFieldId: appFields.candidate,
      sizeFieldId: appFields.tshirt,
      siteUrl,
    }));
    const { credited, excluded, excludedWithValue } = creditableEpics(all, entry);
    for (const e of credited) mapped.push({ ...e, contextId: entry.id });
    // The window this reader is looking through, and what it did not let past.
    // Sent even when nothing was excluded: zero here is a measured zero, and
    // the tile distinguishes it from the absence a file reports.
    valueWindow = {
      start: entry.startDate,
      end: entry.endDate,
      excluded,
      excludedWithValue,
    };
  }
  return { issues: mapped, valueWindow };
};

/**
 * One sprint's issues.
 *
 * The id carries project, board and sprint, so nothing is held between calls.
 * It is checked rather than trusted: the entry is rebuilt from what Jira says
 * the board and sprint are, and if that does not reproduce the id the caller
 * asked for, the answer is 404. A project key supplied by the page would
 * otherwise label another project's board.
 */
/**
 * One sprint's burndown, from the calculator.
 *
 * This is why the tile was blank on every Forge install: Forge cannot run
 * Python, `build_burndown` was a step inside the fetcher, and `contextBody`
 * therefore sent `burndown: []` with the page printing "no burndown series in
 * this dataset" — which blamed the tenant's data for something this transport
 * had never computed. The algorithm now lives in `metrics.burndown` and
 * `/v1/burndown` serves it, so a Forge reader gets the same chart a file
 * reader gets. Nothing is derived here: the issues go out projected and the
 * rows come back.
 *
 * **A window is not a clock.** A flow board's period bounds a selection and
 * nobody committed to finishing by the end of it, so there is no scope to burn
 * down to and no call is made. ADR 0011, and `serve_live.py` refuses it in the
 * same words on the same test.
 *
 * Returns `{ rows, note }` — and the note is the point of the pair. An empty
 * series has four causes with four different fixes, and until now they all
 * printed the same sentence.
 */
const burndownFor = async (entry, issues, cfg) => {
  if (entry.kind === 'window') {
    return { rows: [], note: 'A burndown plots a committed scope down to the date it '
      + 'was committed for. This period is a rolling window rather than a sprint, so '
      + 'nobody committed to finishing by the end of it and there is no line to draw. '
      + 'Everything else on this page is valid for it.' };
  }
  if (!entry.startDate || !entry.endDate) {
    return { rows: [], note: 'This sprint has no start or end date recorded in Jira, '
      + 'so there are no days to plot a burndown against. Setting both on the sprint '
      + 'is the fix; nothing else on this page depends on it.' };
  }
  // Asked before the calculator is, because the answer is a property of the
  // entry's own dates and a round trip to be told every row is null is a round
  // trip to learn what was already on hand.
  const noDays = noDaysYetNote(entry);
  if (noDays) return { rows: [], note: noDays };
  const projected = issues.map(projectIssue);
  assertNoFreeText(projected);
  const answer = await callCalculator('/v1/burndown', {
    dataset: {
      issues: projected,
      meta: {
        startDate: entry.startDate,
        endDate: entry.endDate,
        asOfDate: entry.asOfDate || entry.endDate || null,
      },
      orgConfig: cfg || {},
    },
  });
  if (answer.available === false) {
    // The calculator's own sentence, verbatim. "Unavailable" names none of the
    // several things this is, and the reader who can act on it is the one told
    // which.
    return { rows: [], note: `No burndown could be calculated for this sprint — ${answer.sentence}` };
  }
  return { rows: (answer.result ?? {}).burndown ?? [], note: null };
};

resolver.define('context', answering(async ({ payload, context }) => {
  const asked = payload?.id;
  const parsed = parseContextId(asked);
  if (!parsed) {
    return {
      status: 404,
      body: notFound(asked,
        'that is not a project/board/period id. A sprint that came with the file '
        + 'rather than from this site reads like this, and so does a window '
        + 'length this site does not offer'),
    };
  }

  const boardRes = await api.asUser().requestJira(
    route`/rest/agile/1.0/board/${parsed.boardId}`,
  );
  if (boardRes.status === 404) {
    return { status: 404, body: notFound(asked, `board ${parsed.boardId} is not on this site`) };
  }
  if (!boardRes.ok) {
    throw jiraError(`board ${parsed.boardId}`, boardRes.status, await bodyOf(boardRes));
  }
  const board = await boardRes.json();

  // Found through the board rather than by /sprint/{id} directly, so this
  // needs no scope the contexts call does not already need — and so a sprint
  // id from another board cannot be read through this one.
  //
  // It is also what decides which kind of board this is, and that answer comes
  // from Jira rather than from the id. `kind` in the id says what the caller
  // *asked* for; whether the board runs sprints is a fact about the board, and
  // the two disagreeing is the case to refuse rather than to resolve. A window
  // honoured on a sprint board would report a different membership from the
  // one the picker offers for it, and nothing on the page would say so.
  const got = await sprintsFor(board);
  const moduleProject = context?.extension?.project?.key;
  let entry;

  if (parsed.kind === 'window') {
    if (!got.skipped) {
      return {
        status: 404,
        body: notFound(asked,
          `board ${parsed.boardId} runs sprints, so it is reported a sprint at a time `
          + 'and has no windows to offer'),
      };
    }
    entry = windowEntry(board, parsed.windowDays, todayISO(), moduleProject);
  } else {
    if (got.skipped) {
      return { status: 404, body: notFound(asked, `board ${parsed.boardId} ${got.skipped}`) };
    }
    const sprint = got.sprints.find((sp) => String(sp.id) === parsed.sprintId);
    if (!sprint) {
      return {
        status: 404,
        body: notFound(asked,
          `board ${parsed.boardId} has no open or closed sprint ${parsed.sprintId}`),
      };
    }
    entry = contextEntry(board, sprint, moduleProject, todayISO());
  }

  // The check that matters, and it is against Forge's own module context
  // rather than against a second Jira response: this page may read only the
  // boards of the project it is displayed in, so a project key supplied by the
  // page cannot be used to label — or reach — somebody else's board.
  if (moduleProject && entry.projectKey && entry.projectKey !== moduleProject) {
    return {
      status: 404,
      body: notFound(asked,
        `board ${parsed.boardId} belongs to project ${entry.projectKey}, and this `
        + `page is open on ${moduleProject}`),
    };
  }
  if (entry.id !== asked) {
    return {
      status: 404,
      body: notFound(asked, `this site now calls that ${JSON.stringify(entry.id)}`),
    };
  }

  const spField = await storyPointFieldFor();
  const { issues, valueWindow } = await issuesForEntry(entry, spField, context?.siteUrl);
  const cfg = (await orgConfigFor(entry.projectKey)).config;

  // **Only when it would change what a reader is told.** This is a call per
  // panel load, and a board where somebody has already priced something needs
  // no diagnosis — the tile is going to show a figure either way. Asking only
  // when the value tile is about to refuse is what keeps an honest sentence
  // from costing every load a round trip.
  let setup;
  if (!issues.some((i) => i.businessValue != null)) {
    const appFields = await appFieldsFor(undefined, cfg?.askField, cfg?.sizeField);
    const boardId = parsed.boardId;
    const sample = appFields.value && boardId
      ? (await boardEpicsFor(boardId, undefined, appFields, spField)).epics[0]?.key
      : null;
    const onScreen = await fieldsOnScreen(sample, undefined);
    setup = {
      businessValue: fieldState(appFields.value, onScreen),
      valueBasis: fieldState(appFields.basis, onScreen),
    };
  }

  return {
    status: 200,
    body: contextBody(entry, issues, cfg, setup, valueWindow,
                      await burndownFor(entry, issues, cfg)),
  };
}));

/**
 * The forecast, over the bridge.
 *
 * Three calls, in this order, and the order is the point.
 *
 * A forecast samples a *team's* history and takes only its outstanding work
 * from the sprint the reader selected. Which contexts make up that team is
 * `team_slice`, in `agent/tools/selection.py`, and it is the last logic in this
 * repository that should exist twice: every one of its failures is a plausible
 * date rather than an error. Reading the wrong context turned a 19-day forecast
 * into 77; counting a flow board's overlapping windows three times forecast a
 * team 2.5x too fast. Neither failed. Both returned a number.
 *
 * So this resolver does not decide the slice. It asks `/v1/slice` which
 * contexts to gather, fetches exactly those, and sends them to
 * `/v1/forecast-context`, which slices them with the same function the live
 * server uses. The extra round trip buys the guarantee that the issues sent are
 * the issues the answer claims to have sampled — send fewer and the forecast
 * runs over a narrower history than `sampled_from` reports, with nothing on
 * screen to say so.
 */
// The forecast body for a refusal: the shape is `forecastRefusal` in jobs.js
// now, because a refusal can arrive at collection as well as here.
const noCalculator = forecastRefusal;

resolver.define('forecast', answering(async ({ payload, context }) => {
  // Phase timings, to the log. Milliseconds and phase names only — no key,
  // no title, no figure — so a forecast that misses the adapter's clock says
  // which phase spent it. ADR 0031 priced the in-function forecast at about
  // 6 s cold; this is how that price is checked against a real tenant.
  const t0 = Date.now();
  const cold = !runtime.state().loaded;
  const mark = (label) => console.log(`forecast ${label} +${Date.now() - t0}ms`);
  const asked = payload?.id;
  const projectKey = moduleProjectKey(context);
  if (!projectKey) return NO_PROJECT(context);
  if (!parseContextId(asked)) {
    return { status: 404, body: notFound(asked, 'that is not a project/board/period id') };
  }

  const { contexts } = await projectContexts(projectKey);
  mark(`contexts ${contexts.length}`);
  if (!contexts.length) {
    return { status: 404, body: notFound(asked, `project ${projectKey} has nothing to report on`) };
  }

  // Which contexts this forecast samples. Metadata only — this route needs no
  // issues and none are sent, so asking costs one small round trip rather than
  // a board's worth of data going out twice.
  const slice = await answerHere('/v1/slice', { dataset: { contexts }, contextId: asked });
  mark(`slice ${cold ? 'cold' : 'warm'} ${runtime.state().loadedWith} ${os.cpus().length}cpu ${Math.round(os.totalmem() / 1048576)}MB node${process.version}`);
  if (slice.available === false) return { status: 200, body: noCalculator(slice.sentence) };
  const wanted = new Set(slice.result?.contextIds ?? []);
  if (!wanted.size) {
    return { status: 404, body: notFound(asked, 'this site does not offer that context') };
  }

  const spField = await storyPointFieldFor();
  const byKey = new Map();
  const issues = [];
  for (const entry of contexts.filter((c) => wanted.has(c.id))) {
    for (const issue of (await issuesForEntry(entry, spField, context?.siteUrl)).issues) {
      byKey.set(issue.key, issue);
      issues.push(issue);
    }
  }

  const projected = issues.map(projectIssue);
  assertNoFreeText(projected);
  mark(`issues ${projected.length} over ${wanted.size} contexts`);

  // The board's forecast log — roadmap item 4c, ADR 0017. Read here and
  // handed over with the request, so the job both publishes this forecast's
  // claims and scores everything already resolved; `jobResult` writes the
  // log back if it moved. A what-if carries no claims (`forecast_for` emits
  // them for the default forecast alone), so dragging the tile's sliders
  // reads the log and writes nothing back.
  const board = parseContextId(asked)?.boardId;
  const logKey = forecastLogKey(board);
  const heldLog = board ? ((await kvs.get(logKey)) ?? []) : [];

  const request = {
    dataset: {
      issues: projected,
      // Every context, not just the sampled ones. The tool resolves the id
      // against this list and a rollup id names sprints by their board, so
      // handing it only the slice would make it re-derive a slice from a list
      // that had already been narrowed by one.
      contexts,
      orgConfig: (await orgConfigFor(projectKey)).config,
    },
    contextId: asked,
    // The log, and the latest date this app's data can speak to. Forge reads
    // Jira live, so that is today; a bundle over loopback stops where the file
    // stops and sends its own as-of instead. One rule, two answers.
    ...(board ? { log: Array.isArray(heldLog) ? heldLog : [], today: todayISO() } : {}),
    ...(payload?.items == null ? {} : { items: payload.items }),
    ...(payload?.date == null ? {} : { target: payload.date }),
    // The reader's issue-type selection, passed through untouched. This
    // resolver decides nothing about it — which types count is the tools'
    // answer, narrowed by the reader and applied by `counted_issues`.
    ...(Array.isArray(payload?.types) && payload.types.length
      ? { types: payload.types } : {}),
  };

  // **The forecast is a job.** ADR 0031, corrected 2026-09-03: on a board
  // with a long, sparse history the completion simulation walks hundreds of
  // days per trial and took twelve seconds here, measured, against the
  // adapter's fifteen with Jira reads around it. The consumer computes it on
  // the plain runtime and `jobResult` finishes it — titles back on the
  // at-risk items, the calibration log written — when the page collects.
  const started = await startJob({
    route: '/v1/forecast-context', request, contextId: asked,
    accountId: context?.accountId ?? null, board: board == null ? null : String(board),
    text: {}, envelope: {},
  });
  mark(`pushed ${started.status}`);
  return started;
}));

/**
 * The board's trend series — roadmap item 4, ADR 0015.
 *
 * A route of its own rather than a field on `context`, and for the reason the
 * context route states about itself: it is a *sprint* read, deliberately
 * holding nothing between calls. A trend is a question about a board, it costs
 * one issue fetch per sprint to answer, and making every panel load of one
 * sprint pay for all of them would be a different trade taken by accident.
 *
 * Three things happen here, in this order.
 *
 * **The rows are computed by the calculator, never here.** `CLAUDE.md` is
 * explicit that nothing between a tool and a reader does arithmetic, and a
 * resolver that counted completions would be the second implementation of
 * `history_row` — the one whose failure mode is a plausible row rather than an
 * error, as 1.36.0 demonstrated at some length.
 *
 * **What we may record is decided before anything is written.** `recordable`
 * is the rule, and the one it enforces is that a sprint which closed before
 * this installation ever saw the board is *shown and not stored*. The rows are
 * usually identical; the warrant is not, and writing one in as the other would
 * make the series look complete from the day of install.
 *
 * **The store is read whole and written per sprint.** One key per board, so two
 * boards closing sprints in the same hour are two writers rather than one lost
 * row. A write happens only when the entry actually changes, because this route
 * runs on every panel load and a store rewritten each time is a quota spent on
 * nothing.
 */
resolver.define('history', answering(async ({ payload, context }) => {
  const asked = payload?.id;
  const projectKey = moduleProjectKey(context);
  if (!projectKey) return NO_PROJECT(context);
  const parsed = parseContextId(asked);
  if (!parsed) {
    return { status: 404, body: notFound(asked, 'that is not a project/board/period id') };
  }

  // Asked with the window this project states rather than a constant, so a
  // twelve-month trend is a setting rather than a code change — roadmap 4b.
  const cfgForWindow = (await orgConfigFor(projectKey)).config;
  const window = trendWindow(cfgForWindow);
  const { contexts, offered } = await projectContexts(projectKey, undefined, window);
  // This board's sprints only. A flow board's windows overlap completely, so a
  // trend across them would count one issue three times and draw a line out of
  // it — ADR 0011, and the calculator refuses them for the same reason.
  const mine = contexts.filter((c) => String(c.boardId) === String(parsed.boardId)
    && (c.kind || 'sprint') === 'sprint');
  if (!mine.length) {
    return {
      status: 200,
      body: {
        available: false,
        rows: [],
        note: '',
        why: 'this board reports a window at a time rather than a sprint, so it has no '
          + 'sprint-by-sprint trend. A window is not a clock and it is not a sprint either.',
      },
    };
  }

  const spField = await storyPointFieldFor();
  const issues = [];
  for (const entry of mine) {
    issues.push(...(await issuesForEntry(entry, spField, context?.siteUrl)).issues);
  }
  const projected = issues.map(projectIssue);
  assertNoFreeText(projected);

  const orgConfig = cfgForWindow;
  const fingerprint = statusFingerprint(orgConfig);
  const key = seriesKey(parsed.boardId);
  const stored = readSeries((await kvs.get(key)) ?? null);

  // One call. The calculator is sent the rows' raw material *and* the series
  // this installation has kept, and answers with both: the per-sprint rows, so
  // this resolver can decide what it is entitled to record, and the merged
  // view with its note, so nothing here counts anything a reader will read.
  const answer = await answerHere('/v1/history', {
    dataset: { issues: projected, contexts: mine, orgConfig },
    stored,
    statuses: fingerprint,
    // Recorded from every sprint this look could see; shown only up to the one
    // the reader selected. A sprint does not get to be compared against its own
    // future, and the rule lives in the tool so both transports obey one copy.
    contextId: asked,
    // What the board actually has, against the window that was kept. The tool
    // turns the pair into a sentence; nothing here counts anything.
    boardSprints: offered?.[String(parsed.boardId)] ?? null,
    window,
  });
  if (answer.available === false) {
    return { status: 200, body: { available: false, rows: [], note: '', problems: [], why: answer.sentence } };
  }
  const result = answer.result ?? {};

  // ---- what may be kept ----
  //
  // Decided here and not in the calculator, because it is the only part of this
  // that is a decision about *storage* rather than about a figure. `recordable`
  // is the rule: a sprint that closed before this installation ever saw the
  // board is shown and never stored, however identical its row.
  let next = stored;
  let wrote = false;
  const refused = [];
  for (const { contextId, sprintState, asOf, issuesSeen, row } of result.rows ?? []) {
    const prior = (next.sprints || {})[String(contextId)];
    if (!recordable({ sprintState }, prior, issuesSeen).record) continue;
    // Validated before writing, never after reading: a bad row in the store is
    // read by every panel load from then on, and a panel is not where anybody
    // wants to discover it.
    const problems = problemsInRow(row);
    if (problems.length) {
      refused.push(`${row?.sprint ?? contextId}: ${problems[0]}`);
      continue;
    }
    // `asOf` and not today. The row is a statement about a moment, and for a
    // closed sprint that moment is its completion date rather than the day
    // somebody happened to open the panel. For an active sprint the two are the
    // same date, which is why getting this wrong would never have shown.
    const entry = entryFrom({ sprintState }, row, asOf ?? todayISO(), orgConfig,
                            issuesSeen);
    // Only when it actually moved. This route runs on every panel load, and a
    // store rewritten each time is a write quota spent on nothing.
    if (prior && JSON.stringify(prior) === JSON.stringify(entry)) continue;
    next = writeSeries(next, contextId, entry);
    wrote = true;
  }

  if (!wrote) {
    return {
      status: 200,
      body: {
        available: true,
        rows: result.merged ?? [],
        note: result.note ?? '',
        // What the board offered against what produced a row. The two differing
        // is the fact that was invisible when a sprint with no end date left
        // the series and the tile reported thin data on a board with two.
        offered: result.offered ?? null,
        sprints: result.sprints ?? null,
        problems: [...stored.problems, ...refused],
      },
    };
  }

  // Something was recorded, so the merged answer just received described the
  // store as it was a moment ago. Asked again rather than patched here: patching
  // it would mean this resolver deciding which rows became recorded and what the
  // note should now say, which is the arithmetic it does not do. Two calls
  // happen only on the panel load after a sprint moves, not on every one.
  await kvs.set(key, next);
  const again = await answerHere('/v1/history', {
    dataset: { issues: projected, contexts: mine, orgConfig },
    stored: next,
    statuses: fingerprint,
    contextId: asked,
    boardSprints: offered?.[String(parsed.boardId)] ?? null,
    window,
  });
  if (again.available === false) {
    return { status: 200, body: { available: false, rows: [], note: '', problems: [], why: again.sentence } };
  }
  return {
    status: 200,
    body: {
      available: true,
      rows: again.result?.merged ?? [],
      note: again.result?.note ?? '',
      offered: again.result?.offered ?? null,
      sprints: again.result?.sprints ?? null,
      // The store's own complaints, verbatim and separate from the note: a row
      // this app declined to keep is a fact about this app, not about the team,
      // and collapsing the two would put an internal problem into a sentence
      // about delivery.
      problems: [...stored.problems, ...refused],
    },
  };
}));

/**
 * Sequencing — roadmap item 7, and the refusal below it is gone.
 *
 * It stood since this resolver was written and it was accurate every day of it:
 * `intake.sequence` compares orderings of *asks*, and nothing in a Jira site
 * said which issues were being weighed against each other. It does now
 * ([ADR 0028](docs/adr/0028-candidacy-is-a-state-somebody-declares.md)), so
 * this assembles them and delegates.
 *
 * **Nothing is computed here.** The orderings, the dates and the delay each ask
 * costs the others all come back from `/v1/sequence`. What this does is decide
 * which issues are candidates, build a payload with no free text in it, and put
 * the titles and bases back afterwards — a lookup by key, which is the same
 * move `reattach` already makes for item risk.
 *
 * **Candidacy is decided here rather than in the calculator, deliberately.**
 * Handing over one more field would have let the tools assemble the asks with
 * no mirror to keep in step. It cannot: an answer nobody can read is reported
 * back with the issue key *and the words somebody wrote*, and those words are
 * free text about a customer's business. `jira.js` carries the mirror and
 * `tests/test_service.py` runs it against the Python over shared cases.
 */
resolver.define('sequence', answering(async ({ payload, context }) => {
  const asked = payload?.id;
  const projectKey = moduleProjectKey(context);
  if (!projectKey) return NO_PROJECT(context);
  if (!parseContextId(asked)) {
    return { status: 404, body: notFound(asked, 'that is not a project/board/period id') };
  }

  const { contexts } = await projectContexts(projectKey);
  const entry = contexts.find((c) => c.id === asked);
  if (!entry) {
    return { status: 404, body: notFound(asked, 'this site does not offer that context') };
  }

  const spField = await storyPointFieldFor();
  const { issues } = await issuesForEntry(entry, spField, context?.siteUrl);
  const cfg = (await orgConfigFor(projectKey)).config;

  // **Candidates come from the board's epics, not from this period's issues.**
  //
  // `issuesForEntry` returns the sprint's issues plus the epics that *finished
  // inside the window* — which is right for value, because value is credited
  // to the period an epic completed in (ADR 0026), and exactly wrong here. A
  // candidate is by definition unfinished: it is being weighed against other
  // things precisely because nobody has done it. Assembling asks from that set
  // found nothing on a board with two epics marked, and said so as if it were a
  // fact about the board rather than about where this looked.
  // Read as the viewer, like every other panel read, and stated rather than
  // left to a default: `jira(undefined)` is `asUser()`, and item 5's permission
  // mirroring holds only because this app never reads a board its reader
  // cannot. `issuesForEntry` above takes the same authority the same way.
  const readAs = undefined;
  const appFields = await appFieldsFor(readAs, cfg?.askField, cfg?.sizeField);
  const boardId = parseContextId(asked)?.boardId;
  const { epics } = appFields.candidate && boardId
    ? await boardEpicsFor(boardId, readAs, appFields, spField)
    : { epics: [] };
  // What a person can actually type into, on this board's epics. Sampled from
  // one epic because that is what `editmeta` answers about; the page says "this
  // board's epics" rather than "this site" for the same reason.
  const onScreen = await fieldsOnScreen(epics[0]?.key, readAs);
  const setup = {
    businessValue: fieldState(appFields.value, onScreen),
    valueBasis: fieldState(appFields.basis, onScreen),
    candidate: fieldState(appFields.candidate, onScreen),
    tshirt: fieldState(appFields.tshirt, onScreen),
  };
  const candidates = epics.map((raw) => issueFrom(raw, {
    storyPointField: spField,
    businessValueField: appFields.value,
    valueBasisField: appFields.basis,
    askFieldId: appFields.candidate,
    sizeFieldId: appFields.tshirt,
    siteUrl: context?.siteUrl,
  }));
  const { asks, text, notes } = asksFromIssues(candidates, cfg);

  // Two refusals, and they are different facts about the board. One says
  // nobody has put anything forward; the other says one person has, and an
  // ordering of one thing is not a comparison. Saying "not enough" for both
  // would leave a reader who marked a single epic wondering what else to do.
  if (!asks.length) {
    return {
      status: 200,
      body: {
        available: false,
        board: boardId == null ? null : String(boardId),
        boardName: entry.boardName ?? null,
        setup,
        notes,
        sentence: 'Nothing on this board is marked as a candidate, so there is nothing '
                + 'to sequence. Answer the Candidate field on the epics being weighed '
                + 'against each other — or point orgConfig.askField at the field you '
                + 'already use for it. Nothing was sequenced, and nothing else on this '
                + 'page depends on it.',
      },
    };
  }
  if (asks.length < 2) {
    return {
      status: 200,
      body: {
        available: false,
        board: boardId == null ? null : String(boardId),
        boardName: entry.boardName ?? null,
        asks_considered: asks.length,
        setup,
        notes,
        sentence: 'One candidate is marked on this board, and sequencing compares '
                + 'orderings of two or more against each other. Nothing was sequenced, '
                + 'and nothing else on this page depends on it.',
      },
    };
  }

  const projected = issues.map(projectIssue);
  assertNoFreeText(projected);
  // The same guard, applied to the other thing going out. The ask payload is
  // built here rather than projected from an issue, so `assertNoFreeText` would
  // not have looked at it — and a field added to an ask in a later change is
  // exactly how customer text reaches a calculator by a door nobody was
  // watching.
  assertAsksCarryNoText(asks);

  // The same keys `scripts/serve_live.py` adds around the tool's answer, held
  // in the job row so the collector can put them back. ADR 0009 is one set of
  // body shapes over two transports, and the page reads `asks_considered` for
  // its own heading — without it the panel says "Sequencing 0 asks" over a
  // table of two.
  const envelope = {
    board: boardId == null ? null : String(boardId),
    boardName: entry.boardName ?? null,
    asks_considered: asks.length,
    setup,
    notes,
  };
  const refuse = (sentence) => ({ status: 200, body: { available: false, ...envelope, sentence } });
  const request = {
    dataset: { issues: projected, contexts, orgConfig: cfg },
    asks,
    board: parseContextId(asked)?.boardId,
  };

  // **Sequencing is a job.** ADR 0031. It is cubic in the ask count and runs
  // for minutes on this CPU, so this resolver does not compute it. It
  // validates the request through the same Python the consumer will run —
  // one validator, the tool's own cap and sentences, in this function under
  // the snapshot load — pushes the projection to a consumer function with a
  // 900-second budget, and answers with a job id for the adapter to poll.
  const checked = await runtime.answer('/v1/sequence-check', request, { snapshot: true });
  if (checked.status !== 200) {
    return refuse(checked.payload?.error
      ?? 'The sequencing request was refused before it started. Nothing was sequenced.');
  }
  const over = tooLarge(request);
  if (over) return refuse(over);

  return startJob({
    route: '/v1/sequence', request, contextId: asked, accountId: context?.accountId ?? null,
    board: boardId == null ? null : String(boardId), text, envelope,
  });
}));

/**
 * A simulation as a job — the resolver's half. ADR 0031.
 *
 * The projection goes to storage in chunks, the event names it, the job row
 * records who asked and what the page's body gets around the answer, and the
 * in-flight key lets a reload join the running job rather than start another.
 * One path for both kinds: a forecast carries a team's whole history, which
 * is past the event's 100 KB limit on any real board, and a second path for
 * the small case is a second path nobody tests.
 */
const startJob = async ({ route, request, contextId, accountId, board, text, envelope }) => {
  const kind = KIND_OF[route];
  const refuse = (sentence) => ({
    status: 200,
    body: kind === 'forecast'
      ? forecastRefusal(sentence)
      : { available: false, ...(envelope ?? {}), sentence },
  });
  const over = tooLarge(request, kind);
  if (over) return refuse(over);

  // A reload mid-job joins the running job rather than starting another:
  // the same context, the same projection, the same account is one
  // computation with two collectors, not two computations.
  const inflight = inflightKey(contextId, request, accountId);
  const running = await kvs.get(inflight);
  if (running?.jobId) {
    const job = await kvs.get(jobKey(running.jobId));
    const fresh = job && Date.now() - Date.parse(job.createdAt) < JOB_LIFETIME_MS;
    if (fresh) return { status: 202, body: { jobId: running.jobId, pending: true, joined: true } };
  }

  // The payload first, under its own id, so it is there before the event
  // that names it is — the consumer can start within a second of the push.
  const payloadId = randomUUID();
  const chunks = chunkPayload(request);
  for (let n = 0; n < chunks.length; n += 1) {
    await kvs.set(payloadKey(payloadId, n), { s: chunks[n] }, { ttl: JOB_TTL });
  }

  let jobId;
  try {
    ({ jobId } = await new Queue({ key: QUEUE_KEY }).push({
      body: { route, payloadId, chunks: chunks.length },
    }));
  } catch (err) {
    // The platform's own class name, never its message — a message can carry
    // the payload it refused, and the payload is a board.
    await Promise.all(chunks.map((_, n) => kvs.delete(payloadKey(payloadId, n))));
    return refuse(`The platform did not accept the job (${err?.name ?? 'error'}). `
                + 'Nothing was computed; try again in a minute.');
  }
  await kvs.set(jobKey(jobId), jobRow({
    jobId, kind, route, accountId, contextId, board, key: inflight, text, envelope, now: Date.now(),
  }), { ttl: JOB_TTL });
  await kvs.set(inflight, { jobId }, { ttl: JOB_TTL });
  return { status: 202, body: { jobId, pending: true } };
};

/**
 * The titles and assignees of a forecast's at-risk items, by key, read from
 * Jira as the person collecting. `reattach` needs them and they were never
 * in the job: a team's history is too many titles to hold in a row, and the
 * risk list names only a few. The keys are the tool's own echo of keys this
 * app fetched, validated to Jira's key shape before they go into a query.
 */
const issuesByKey = async (keys, boardId) => {
  const byKey = new Map();
  if (!keys.length || boardId == null) return byKey;
  for (let i = 0; i < keys.length; i += 100) {
    const jql = `key in (${keys.slice(i, i + 100).join(',')})`;
    const res = await api.asUser().requestJira(
      route`/rest/agile/1.0/board/${boardId}/issue?maxResults=100&fields=summary,assignee&jql=${jql}`,
    );
    if (!res.ok) continue; // shown without titles rather than not shown
    const body = await res.json();
    for (const raw of body.issues ?? []) {
      byKey.set(raw.key, {
        summary: raw.fields?.summary ?? '',
        assignee: (raw.fields?.assignee || {}).displayName || 'Unassigned',
      });
    }
  }
  return byKey;
};

/**
 * One poll of a job. ADR 0031.
 *
 * The adapter asks every few seconds with the job id the `sequence` or
 * `forecast` resolver handed it, and gets back exactly what `collect` in
 * jobs.js says: 202 while the consumer is running, the tool's answer when it
 * is done, a refusal when it was refused, and a 404, 403 or 410 for a job that
 * is gone, another account's, or older than an hour. A finished forecast has
 * its at-risk items' titles put back here, from a Jira read as the collector,
 * and its calibration log written if the log moved — the two things the
 * forecast resolver did after the call when the call was synchronous. The
 * rows are deleted the moment a final answer is handed over, so a result is
 * never served twice from storage.
 */
resolver.define('jobResult', answering(async ({ payload, context }) => {
  const jobId = payload?.jobId;
  if (typeof jobId !== 'string' || !JOB_ID.test(jobId)) {
    return { status: 400, body: { error: 'A job is collected by its id, and that is not one.' } };
  }
  const job = await kvs.get(jobKey(jobId));
  const result = job ? await kvs.get(resultKey(jobId)) : null;
  const out = collect({ job, result, accountId: context?.accountId ?? null, now: Date.now() });
  if (out.finished && job?.kind === 'forecast' && out.status === 200 && out.body?.item_risk) {
    reattach(out.body, await issuesByKey(riskKeys(out.body), job.board));
    // Written only when it moved. This route runs whenever the tile is
    // opened, and a store rewritten on every read is a write quota spent on
    // nothing.
    const cal = out.body.calibration;
    if (job.board != null && cal && (cal.added || cal.dropped)) {
      await kvs.set(forecastLogKey(job.board), cal.log);
    }
  }
  if (out.finished) {
    await Promise.all([
      kvs.delete(jobKey(jobId)),
      kvs.delete(resultKey(jobId)),
      job?.key ? kvs.delete(job.key) : Promise.resolve(),
    ]);
  }
  return { status: out.status, body: out.body };
}));

/* ------------------------------------------------------------------------
   Connection-check resolvers. Used only by forge/probe/, and deletable with
   it once the real bridge exists.

   They are here rather than in a separate function because a deploy proves
   the manifest and the bundle and nothing about permissions — and a scope
   that turns out to be wrong is far cheaper to find now than during a
   customer's install.
   --------------------------------------------------------------------- */

/** Proves the static resource can reach a resolver. Touches no Jira API, so a
 *  failure here is the bridge or the manifest, never a scope. */
resolver.define('ping', () => ({
  reached: 'resolver',
  at: new Date().toISOString(),
}));

/* There was a `boards` resolver here that listed every board, so the probe
   could offer them as buttons. `forge lint` refused it: GET /rest/agile/1.0/board
   needs read:project:jira, which nothing else in this app requires.
   
   Removed rather than granted. The product reads one named board and never
   enumerates them, so the scope would have existed purely to make a diagnostic
   more convenient — and it would have appeared on the consent screen of every
   install, in an app whose pitch is that it asks for almost nothing. The probe
   takes a board id instead.
   
   If the real context picker ever needs to enumerate boards, read:project:jira
   is the price, and that is a decision to take on its own merits. */

/** Tests read:issue-details:jira, and shows what the projection would send.
 *  One page, not the whole board — this is a check, not a pull. */
resolver.define('probeBoardIssues', async ({ payload }) => {
  const id = String(payload?.boardId ?? '').replace(/[^0-9]/g, '');
  if (!id) return { available: false, sentence: 'no board id' };

  // Named in the output, because this is the page you come to when the
  // burndown has flattened in points mode and nothing has said why.
  const spField = await storyPointFieldFor();

  const res = await api
    .asUser()
    .requestJira(route`/rest/agile/1.0/board/${id}/issue?maxResults=5`);
  if (!res.ok) {
    return { available: false, status: res.status, sentence: `Jira returned ${res.status}.` };
  }
  const body = await res.json();
  // The same shape fetchBoardIssues builds, so what section 3 displays is the
  // payload the product would really send rather than a thinner stand-in.
  const raw = (body.issues ?? []).map((i) => ({
    key: i.key,
    summary: i.fields?.summary ?? '',
    assignee: i.fields?.assignee?.displayName ?? null,
    status: i.fields?.status?.name ?? null,
    storyPoints: spField ? (i.fields?.[spField] ?? 0) : null,
    priority: i.fields?.priority?.name ?? null,
    created: (i.fields?.created ?? '').slice(0, 10) || null,
    resolved: (i.fields?.resolutiondate ?? '').slice(0, 10) || null,
    dueDate: i.fields?.duedate ?? null,
  }));

  const projected = raw.map(projectIssue);
  // Run the real guard, not a copy of it. If assertNoFreeText ever stops
  // throwing, this reports the leak instead of the page claiming it is clean.
  let leaked = [];
  try {
    assertNoFreeText(projected);
  } catch {
    leaked = NEVER_SEND.filter((f) => projected.some((i) => f in i));
  }

  return {
    available: true,
    total: body.total ?? raw.length,
    // Which field this site calls story points, resolved by display name. The
    // whole point of showing it: a null here is the difference between a team
    // that estimated nothing and a site this app cannot read estimates from.
    storyPointField: spField,
    storyPointFieldNote: spField
      ? `story points read from ${spField}`
      : 'this site has no field named Story Points, Story point estimate or '
        + 'Points, so points are not reported',
    // Keys and dates only. Summaries stay on this side even in the sample.
    sample: raw.map((i) => ({ key: i.key, status: i.status, created: i.created })),
    projected: projected[0] ?? null,
    freeTextFields: leaked,
  };
});

/* `facts` over a whole board, by board id — the shape the connection check
   was built around, kept because it is the one resolver that exercises
   `compute()` end to end: the projection, the free-text assertion, the call
   and the re-attachment. The page itself never asks it; the dashboard's KPI
   strip is the page's own mirror of `metrics.facts`, and the scheduled brief
   reads the same route through `boardFigures`. Since ADR 0031 the route is
   answered by the Python inside this function, not by the calculator. */
resolver.define('facts', ({ payload }) => compute('/v1/facts', payload ?? {}));

/* ------------------------------------------------------------------------
   Who receives this board's brief — the config the panel edits.

   Two routes, and the asymmetry between them is the design. Reading is open to
   anyone who can open the panel; writing is a project administrator only,
   because a recipient list decides who is told what is on a board.

   The gate is Jira's own answer, asked as the person looking at the page —
   `asUser()`, so a viewer who is not an administrator is refused by Jira rather
   than by a group membership this app guessed at. It is asked again on the
   write and not carried over from the read: the read happened when the page
   loaded, and permissions change.
   --------------------------------------------------------------------- */

/** May this user administer this project? Jira's answer, not ours. */
const editabilityFor = async (projectKey) => {
  // `api.asUser()` literally, never `jira(...)`. The question is whether *this
  // reader* may administer this project, so asking it as the app would answer
  // a different question and answer it yes. A test asserts this line.
  const res = await api.asUser().requestJira(
    route`/rest/api/3/mypermissions?projectKey=${projectKey}&permissions=${ADMIN_PERMISSION}`);
  if (!res.ok) {
    // Fail closed and say so. A permission check that cannot be made is not a
    // permission granted, and "Jira did not answer" is a different sentence
    // from "you are not an administrator" — the reader can act on one of them.
    return {
      canEdit: false,
      why: `Jira did not answer whether you may administer this project (${res.status}), `
         + 'so the recipient list is shown but cannot be changed here.',
    };
  }
  return editability(await res.json());
};

resolver.define('recipients', answering(async ({ context }) => {
  const projectKey = moduleProjectKey(context);
  if (!projectKey) return NO_PROJECT(context);

  const config = await recipientConfig();
  const rights = await editabilityFor(projectKey);

  return {
    status: 200,
    body: {
      available: true,
      // The stored config, whatever state it is in. A config with problems is
      // still shown — an administrator fixing it needs to see what is there,
      // and a reader needs to be able to tell "wrong" from "unset".
      config: config ?? { boards: {} },
      problems: config ? problemsIn(config) : [],
      // The operational log, for administrators only — ADR 0021. It carries who
      // changed a recipient list and when, and a reader who may not change one
      // has no business with the account id of whoever did. `rights.canEdit` is
      // Jira's answer to that question and is already asked here.
      //
      // Newest first, and only the recent tail: the store holds a thousand
      // entries and a panel needs the last few. `auditDropped` is the store's
      // own cumulative count, not the length of what was trimmed for this
      // response, so a log that has forgotten things says so however it is read.
      ...(rights.canEdit ? await auditFor() : {}),
      ...rights,
    },
  };
}));

/** The tail of the operational log, newest first, with what the store has
 *  forgotten. Never throws: a log that cannot be read must not take the
 *  recipients tile down with it. */
const AUDIT_SHOWN = 20;
const auditFor = async () => {
  try {
    const held = (await kvs.get(AUDIT_KEY)) ?? {};
    const entries = Array.isArray(held.entries) ? held.entries : [];
    return {
      audit: entries.slice(-AUDIT_SHOWN).reverse(),
      auditTotal: entries.length,
      auditDropped: held.droppedTotal || 0,
    };
  } catch {
    return {};
  }
};

/**
 * Find a person by name, so nobody has to know an account id.
 *
 * `asUser()`, and that is the point rather than a detail: the search returns
 * the people *this reader* is allowed to see. Jira's own "Browse users and
 * groups" permission decides that, and an app that searched as itself would
 * offer an administrator a directory their own account cannot browse.
 *
 * No permission gate of ours in front of it. Searching is not changing, the
 * result is what Jira already shows this person in any user-picker on the site,
 * and gating it would mean a viewer cannot see who a misconfigured board is
 * sending to — which is the thing they are best placed to notice.
 */
resolver.define('searchUsers', answering(async ({ payload }) => {
  const query = String(payload?.query ?? '').trim();
  if (query.length < 2) {
    return { status: 200, body: { available: true, people: [],
      note: 'Type at least two characters.' } };
  }

  const res = await api.asUser().requestJira(
    // One more than shown, so "more matches than fit" is a fact rather than a
    // guess. `peopleFrom` caps at MAX_MATCHES and reports what it dropped.
    route`/rest/api/3/user/search?query=${query}&maxResults=${MAX_MATCHES + 1}`);

  if (!res.ok) {
    return {
      status: 200,
      body: {
        available: false,
        people: [],
        // 403 here is almost always the reader lacking "Browse users and
        // groups", which is a site permission and not something this app can
        // ask for. Saying which is the difference between a fixable message
        // and a broken search box.
        note: res.status === 403
          ? 'You do not have permission to browse users on this site, so names '
            + 'cannot be looked up. A site administrator grants "Browse users '
            + 'and groups". Account ids can still be pasted under Account IDs.'
          : `Jira returned ${res.status} looking up names.`,
      },
    };
  }

  const found = peopleFrom(await res.json());
  if (found.problems) {
    return { status: 200, body: { available: false, people: [],
      note: found.problems.join(' ') } };
  }
  return { status: 200, body: { available: true, people: found.people,
    note: matchNote(found) } };
}));

/**
 * The names behind the ids a board already has stored.
 *
 * The search resolver above stops anyone having to know an account id to add
 * one; this stops the field being unreadable to whoever opens the tile next.
 * `people.js` has why an inactive account is shown rather than filtered, and
 * why an id that matches nothing is named rather than dropped.
 *
 * No new scope: `read:jira-user` is the one the search already uses.
 */
resolver.define('namesFor', answering(async ({ payload }) => {
  const { ask, over } = idsToAsk(payload?.ids);
  // An empty field is not a failure to look anything up. Answering `available`
  // with nothing in it lets the tile render no rows and say nothing, rather
  // than showing a refusal to somebody who has simply not typed yet.
  if (!ask.length) {
    return { status: 200, body: { available: true, people: [], note: '' } };
  }

  // A URLSearchParams in query position is handed through by `route` without a
  // second round of encoding, and it is the only way to send `accountId` more
  // than once — the bulk endpoint has no comma-separated form. Assembling the
  // query as a string and reaching for `assumeTrustedRoute` would also work,
  // and would throw away the single guard `route` exists to provide.
  const params = new URLSearchParams();
  params.set('maxResults', String(MAX_NAMES));
  for (const id of ask) params.append('accountId', id);

  // As the reader, exactly like the search. Resolved as the app, this would
  // show names out of a directory the reader may not browse — a disclosure the
  // tile has no standing to make on their behalf.
  const res = await api.asUser().requestJira(route`/rest/api/3/user/bulk?${params}`);

  if (!res.ok) {
    return {
      status: 200,
      body: {
        available: false,
        people: [],
        // The same site permission the search runs into, and the same reason to
        // name it: the ids are still correct and still send, so this is a
        // display that is missing rather than a config that is broken.
        note: res.status === 403
          ? 'You do not have permission to browse users on this site, so these '
            + 'ids cannot be shown as names. A site administrator grants "Browse '
            + 'users and groups". What is stored is unaffected.'
          : `Jira returned ${res.status} looking these ids up.`,
      },
    };
  }

  // `user/bulk` paginates, so the list is under `values`. Anything else is not
  // an answer, and `namesFrom` refuses it rather than reading an empty list off
  // it — no names and "all five ids are dead" are very different statements.
  const found = namesFrom((await res.json())?.values, ask);
  if (found.problems) {
    return { status: 200, body: { available: false, people: [],
      note: found.problems.join(' ') } };
  }
  return { status: 200, body: { available: true, people: found.people,
    note: nameNote(found, over) } };
}));

/**
 * Append one entry to the operational log — roadmap item 6, ADR 0021.
 *
 * Never throws and never blocks what it is recording. A save that succeeded and
 * an audit write that failed must not report the save as failed; the act is the
 * thing the administrator cares about, and a log that can veto it is a log that
 * takes the product down when storage hiccups.
 *
 * That is also the honest limit of it, and ADR 0021 says so: a log the app
 * writes into its own storage, best-effort, is operational and not a compliance
 * record. Jira's audit API is read-only, so there is no log this app could write
 * to that it cannot also alter.
 */
const audit = async (event, { actor, boardId, detail }) => {
  try {
    const entry = auditEntry({ at: new Date().toISOString(), event, actor, boardId, detail });
    if (!entry) return;
    const next = appendAudit((await kvs.get(AUDIT_KEY)) ?? null, entry);
    if (next.wrote) {
      await kvs.set(AUDIT_KEY, { entries: next.entries, droppedTotal: next.droppedTotal });
    }
  } catch {
    /* Recorded nowhere, and deliberately silent: see above. */
  }
};

/** How many recipients an audience holds, for the log. A count — what the list
 *  *is* stays on the tile, which anybody who can open it can read; this answers
 *  when it changed and who changed it. ADR 0021. */
const audienceCounts = (entry) => ({
  exec: ((entry?.exec?.users) || []).length + ((entry?.exec?.groups) || []).length,
  team: ((entry?.team?.users) || []).length + ((entry?.team?.groups) || []).length,
});

resolver.define('saveRecipients', answering(async ({ payload, context }) => {
  const projectKey = moduleProjectKey(context);
  if (!projectKey) return NO_PROJECT(context);

  // Asked again rather than trusted from the read. The page cannot be the
  // authority on whether the page may do this, and the read that said it could
  // happened whenever the tab was opened.
  const rights = await editabilityFor(projectKey);
  if (!rights.canEdit) {
    return { status: 403, body: { available: false, saved: false, ...rights } };
  }

  const config = payload?.config;
  const problems = problemsIn(config);
  if (problems.length) {
    // Refused whole. Storing a config with a broken board and reporting the
    // problem separately would leave the store holding something no run can
    // use, which is worse than the previous contents.
    return { status: 400, body: { available: true, saved: false, problems, ...rights } };
  }

  const before = (await recipientConfig()) || {};
  await kvs.set(RECIPIENTS_KEY, config);

  // One entry per board whose entry actually moved, rather than one per save:
  // a save writes the whole configuration, so recording the act would put a row
  // against boards nobody touched.
  const boards = new Set([...Object.keys(before.boards || {}),
                          ...Object.keys(config.boards || {})]);
  for (const id of boards) {
    const was = (before.boards || {})[id];
    const now = (config.boards || {})[id];
    if (JSON.stringify(was ?? null) === JSON.stringify(now ?? null)) continue;
    await audit(now ? 'recipients.saved' : 'recipients.cleared', {
      actor: context?.accountId,
      boardId: id,
      detail: now
        ? { ...audienceCounts(now), anchorSet: Boolean(now.anchorIssue) }
        : {},
    });
  }
  return { status: 200, body: { available: true, saved: true, config, problems: [], ...rights } };
}));

/* ------------------------------------------------------------------------
   The weekly brief — roadmap item 3.

   A separate export rather than another `resolver.define`, because a scheduled
   trigger is not a resolver call. Forge invokes the function directly with an
   event; `resolver.getDefinitions()` returns a dispatcher expecting
   `{ call: { functionKey } }` and does not recognise one. The manifest pointed
   its trigger at `resolver` from the day it was declared, and it threw on both
   of the two fires it has ever had — `TypeError: ... reading 'functionKey'`,
   2026-08-24. A scheduled trigger is not retried and its failure appears
   nowhere a person looks, which is what hid it for three versions.

   Two things about the runtime shape it in ways that are not obvious:

   **There is no user.** Scheduled triggers run without a user principal, so
   every `api.asUser()` call in this file — which is all of them — throws here.
   That is not an inconvenience to route around with `asApp()`. Reading as the
   user is *why* a viewer of the panel can only ever see issues they could see
   in Jira, which is roadmap item 5 holding for free. Reading as the app on a
   timer and mailing the result asserts that every recipient may see every issue
   the app can, and nothing in this product establishes that. See below.

   **It fires with nobody watching**, so it must not be expensive when it cannot
   do anything. The blockers are checked first, before a single Jira call.
   --------------------------------------------------------------------- */

/**
 * Where a board's recipients live: the app's own key-value store.
 *
 * Not a Jira project property, which is where `orgConfig` lives and would have
 * been the obvious home — saving to one needs write access into the customer's
 * project, and `storage:app` grants no access to Jira data at all. ADR 0014.
 *
 * A read that fails returns null rather than throwing, because a store that is
 * briefly unavailable and a store with nothing in it should both end in the
 * run saying what is missing, not in an unretried trigger failure whose reason
 * is only in a stack trace.
 */
/** One key per board, like the series. A forecast log is per board because a
 *  claim is about a board's delivery, and two boards sharing a key would make
 *  one board's calibration a statement about both. ADR 0017. */
export const forecastLogKey = (boardId) => `forecastlog:${String(boardId)}`;

export const RECIPIENTS_KEY = 'recipients';

const recipientConfig = async () => {
  try {
    return (await kvs.get(RECIPIENTS_KEY)) ?? null;
  } catch {
    return null;
  }
};

/**
 * Send one audience's brief, through the same machinery Jira uses to tell
 * somebody their issue was commented on.
 *
 * `asApp()` and not `asUser()`, and here that is correct rather than a
 * compromise: a scheduled run has no user to be, and the authority being
 * exercised is this app's own `send:notification:jira`. What stops it being a
 * way to tell anyone anything is `restrict` inside `notifyPayload` — Jira drops
 * recipients who may not browse the anchor issue, which is the app's claim
 * being checked by the platform rather than trusted.
 *
 * A 204 is success and carries no body. Anything else is returned rather than
 * thrown: one audience failing should not take the other with it, and a
 * scheduled trigger is not retried, so a thrown error is a reason nobody reads.
 *
 * Nothing about the message is logged — not the subject, not the recipients,
 * not a count of them. The subject carries a board name and the recipients are
 * account ids, and an app log holding either is a copy of something the
 * customer did not put there.
 */
const sendBrief = async ({ anchorIssue, to, subject, textBody, htmlBody }) => {
  const res = await api.asApp().requestJira(
    route`/rest/api/3/issue/${anchorIssue}/notify`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(notifyPayload({ subject, textBody, htmlBody, to })),
    },
  );
  if (res.status === 204) return { sent: true };

  /* Jira's own words, not just its status.
     A 403 alone says "refused" and nothing about by what — a missing scope, an
     app user without Browse on the project, outgoing mail disabled on the
     site. All three look identical from here and have different fixes, and the
     body says which. Discarding it was the third time in one session a reason
     existed and reached nobody.
     Capped and stripped of newlines: this goes in a log line, and Jira's error
     bodies are its own generic sentences — no issue text — but a cap is
     cheaper than trusting that forever. */
  let said = '';
  try {
    const body = await res.json();
    said = []
      .concat(body?.errorMessages || [], Object.values(body?.errors || {}))
      .join(' ')
      .replace(/\s+/g, ' ')
      .slice(0, 300);
  } catch {
    // A body that is not JSON is a proxy page, not an answer worth quoting.
  }

  return {
    sent: false,
    // Jira's own status, so a 403 reads as the app lacking permission on that
    // issue rather than as a bug here, and a 404 as an anchor that has been
    // deleted since somebody configured it.
    // Jira's own status, so a 403 reads as the app lacking permission on the
    // anchor rather than as a bug here, and a 404 as an anchor deleted since
    // somebody configured it.
    //
    // The anchor's key is deliberately *not* in this sentence. Reasons are
    // logged, and `CLAUDE.md` forbids an issue key reaching a log — an access
    // log holding one is a copy of part of the customer's backlog. The board
    // id in the log line is enough to find the anchor in the config.
    reason: `Jira refused the notification with ${res.status}.`
          + (said ? ` It said: ${said}` : ' It gave no reason.'),
  };
};

/**
 * The scheduled trigger's function.
 *
 * Returns rather than throws when it cannot send. A thrown error in a scheduled
 * trigger is not retried and shows up only as a failed invocation; a returned
 * reason is the same information in a form the next reader of this code can
 * see without opening a log.
 *
 * It logs the reasons and nothing else. No issue key, no title, no recipient —
 * the same rule the calculator's access log follows, and for the same reason.
 */
/**
 * Everything one board's brief needs from Jira and the calculator.
 *
 * Reads as the **app**, because a scheduled run has no user to be. That is the
 * decision ADR 0013 declined twice and records as taken; the addendum there has
 * what it costs and what `restrict` does and does not check. It is passed
 * explicitly at every hop rather than defaulted, so the authority a read is
 * made with is visible at the call site and not inherited from context.
 */
const boardFigures = async (boardId) => {
  const projectKey = await boardProject(boardId, 'app');
  if (!projectKey) return { problems: [`board ${boardId} is not on this site.`] };

  const { contexts } = await projectContexts(projectKey, 'app');
  const mine = contexts.filter((c) => String(c.boardId) === String(boardId));
  if (!mine.length) {
    return { problems: [`board ${boardId} has no sprint or window to report on.`] };
  }
  // The first is the most recent — `recentSprints` sorts, and windows are
  // offered newest first. A brief is about now, not about the whole record.
  const entry = mine[0];

  const spField = await storyPointFieldFor('app');
  const org = (await orgConfigFor(projectKey, 'app')).config;
  const { issues } = await issuesForEntry(entry, spField, null, 'app');

  const projected = issues.map(projectIssue);
  assertNoFreeText(projected);
  const dataset = { issues: projected, contexts, orgConfig: org, meta: {} };

  // In-function since the facts route moved (ADR 0031); the forecast follows
  // in its own commit. This function loads the runtime too, which is why the
  // manifest gives it the same memory as the resolver's.
  const facts = await answerHere('/v1/facts', { dataset });
  if (facts.available === false) return { problems: [facts.sentence] };

  // A refusal here is an answer, not a failure: `sectionsFor` carries the
  // tool's sentence into the brief verbatim.
  const forecast = await answerHere('/v1/forecast-context', {
    dataset, contextId: entry.id,
  });

  return {
    entry,
    facts: facts.result ?? facts,
    forecast: forecast.available === false
      ? { available: false, sentence: forecast.sentence }
      : (forecast.result ?? forecast),
  };
};

/**
 * The scheduled trigger's function.
 *
 * Returns rather than throws: a scheduled trigger is not retried, and a thrown
 * error is a reason only a stack trace carries.
 *
 * Logs board ids and outcomes and nothing else. No subject, no recipient, no
 * issue key — the subject carries a board name and the recipients are account
 * ids, and an app log holding either is a copy of something the customer did
 * not put there.
 */
export const weeklyBrief = async () => {
  const config = await recipientConfig();

  const problems = problemsIn(config);
  if (problems.length) {
    console.log(`weekly brief not sent: ${problems.join(' ')}`);
    return { sent: false, reasons: problems };
  }

  const out = [];
  for (const boardId of boardsIn(config)) {
    let got;
    try {
      got = await boardFigures(boardId);
    } catch (err) {
      // One board failing must not take the rest with it. They are separate
      // messages to separate people, and at a weekly cadence the others would
      // wait a week for somebody else's problem.
      out.push({ boardId, sent: false, reasons: [String(err?.message || err)] });
      continue;
    }
    if (got.problems) {
      out.push({ boardId, sent: false, reasons: got.problems });
      continue;
    }

    const result = await briefsForBoard({
      config,
      boardId,
      boardName: got.entry.boardName,
      periodName: got.entry.sprintName || got.entry.label || '',
      asOf: got.entry.asOfDate || todayISO(),
      calendar: got.facts?.meta?.calendar,
      figuresFor: (audience) => sectionsFor(audience, {
        facts: got.facts, forecast: got.forecast,
      }),
      ask: chat,
      send: sendBrief,
    });
    out.push({ boardId, ...result });
  }

  const sent = out.reduce(
    (n, b) => n + (b.results || []).filter((r) => r.sent).length, 0);
  console.log(`weekly brief: ${out.length} board(s), ${sent} message(s) sent`);

  /* And why, for the ones that did not go.
     The first real run reported "1 board(s), 0 message(s) sent" and nothing
     else, which is a summary nobody can act on: the reasons existed in the
     returned object and reached no one. A scheduled trigger has no page to
     render an error into, so the log is the only place a reason can live.
     These sentences are this app's own — blockers, tool refusals, guard
     complaints — and carry no issue key, no recipient and no issue text. */
  for (const board of out) {
    const why = (board.reasons || []).concat(
      (board.results || []).filter((r) => !r.sent).flatMap((r) => r.reasons || []));
    if (why.length) console.log(`weekly brief, board ${board.boardId}: ${why.join(' ')}`);
  }

  // The operational log — roadmap item 6, ADR 0021. A `console.log` lives for
  // days in the developer console and is visible to whoever deployed the app;
  // an administrator asking "did last Monday's brief go out?" can read neither.
  // Counts and audience names, no subject, no recipient, no issue key — the
  // same rule the log above already follows.
  for (const board of out) {
    const results = board.results || [];
    const went = results.filter((r) => r.sent);
    await audit(went.length ? 'brief.sent' : 'brief.refused', {
      actor: 'schedule',
      boardId: board.boardId,
      detail: {
        sent: went.length,
        refused: results.length - went.length,
        audiences: went.map((r) => r.audience).filter((a) => typeof a === 'string'),
      },
    });
  }
  return { sent: sent > 0, boards: out };
};

/**
 * The consumer: one simulation, computed under a 900-second budget in its
 * own container. ADR 0031.
 *
 * It reads the retry context before anything else. A consumer killed at its
 * timeout is re-invoked forty seconds later, and again forty seconds after
 * the next kill, for a day; without this guard the same doomed job runs every
 * six minutes for something nobody sees. On any retry it writes a refusal to
 * the row and returns without loading the runtime.
 *
 * Plain load, not the snapshot: on Forge everything computed after a snapshot
 * load runs 1.65× slower, and this function computes for seconds to minutes.
 * The cold load it pays instead is eleven seconds.
 *
 * Every outcome is a row. A consumer that threw would be retried, which is
 * the doomed-job loop above by another door, so nothing escapes: the cause
 * goes to the log and the row says it failed. The payload rows are deleted
 * as soon as they are read, whatever happens afterwards.
 */
export const simulationConsumer = async (event) => {
  const jobId = event?.jobId;
  const key = resultKey(jobId);
  const { route: askedRoute, payloadId, chunks } = event?.body ?? {};
  const kind = KIND_OF[askedRoute] ?? 'sequence';
  if (event?.retryContext) {
    await kvs.set(key, resultRow('refused', {
      sentence: retryRefusal(event.retryContext, kind),
      retryCount: event.retryContext.retryCount ?? null,
      retryReason: event.retryContext.retryReason ?? null,
    }, Date.now()), { ttl: JOB_TTL });
    return;
  }
  await kvs.set(key, resultRow('started', {}, Date.now()), { ttl: JOB_TTL });
  const t0 = Date.now();
  if (!CONSUMER_ROUTES.includes(askedRoute)) {
    await kvs.set(key, resultRow('refused', { sentence: wrongRoute(askedRoute) }, Date.now()),
      { ttl: JOB_TTL });
    return;
  }
  try {
    const n = Number(chunks) || 0;
    const rows = [];
    for (let i = 0; i < n; i += 1) rows.push(await kvs.get(payloadKey(payloadId, i)));
    await Promise.all(Array.from({ length: n }, (_, i) => kvs.delete(payloadKey(payloadId, i))));
    const body = joinPayload(rows, n);
    const { status, payload } = await runtime.answer(askedRoute, body, { snapshot: false });
    await kvs.set(key, resultRow('done', {
      http: status, envelope: payload, ms: Date.now() - t0, load: runtime.state().loadedWith,
    }, Date.now()), { ttl: JOB_TTL });
  } catch (err) {
    console.error('simulation consumer failed', jobId, String((err && err.stack) || err));
    await kvs.set(key, resultRow('failed', { sentence: failedSentence(kind), ms: Date.now() - t0 },
      Date.now()), { ttl: JOB_TTL });
  }
};

export const handler = resolver.getDefinitions();
