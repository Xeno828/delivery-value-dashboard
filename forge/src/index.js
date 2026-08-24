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
import api, { route, fetch } from '@forge/api';

import {
  contextEntry, contextsBody, contextBody, contextId, parseContextId,
  issueFrom, notFound, recentSprints,
} from './jira.js';

const resolver = new Resolver();

/**
 * The only issue fields a calculation reads. Verified empirically, not guessed:
 * forecast.build() over a dataset stripped to these produces byte-identical
 * figures to one with everything. The fields left behind — summary, assignee,
 * epic, labels, url, valueBasis — are the sensitive half, and the calculator
 * refuses the payload outright if any of them arrive.
 */
const CALC_FIELDS = [
  'key', 'created', 'started', 'resolved', 'statusCategory', 'status',
  'storyPoints', 'priority', 'dueDate', 'flagged', 'addedMidSprint',
  'contextId', 'epicKey',
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
 * One call to the calculator. `fetch` here is @forge/api's, which routes
 * through the remote declared in manifest.yml and attaches an Atlassian-issued
 * invocation token — that is what lets the service know the call came from this
 * app and which tenant it is for, without this app holding a secret of its own.
 */
const callCalculator = async (path, body) => {
  const res = await fetch(`${process.env.CALCULATOR_URL ?? ''}${path}`, {
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

/** Pull one board's issues. The only place this app talks to Jira. */
const fetchBoardIssues = async (boardId) => {
  const id = String(boardId ?? '').replace(/[^0-9]/g, '');
  if (!id) throw new Error('no board id');

  const issues = [];
  let startAt = 0;
  for (;;) {
    const res = await api
      .asUser()
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
        // OPEN, and it returns a plausible wrong number rather than failing:
        // the story-point custom field id differs per Jira site. The Python
        // fetcher discovers it by display name via /rest/api/3/field; this
        // hardcodes the common one. On a site that uses a different id every
        // issue reads as zero points, the burndown flattens in points mode, and
        // nothing says why. The connection check will show it — storyPoints
        // absent from the projected payload means this id is wrong here.
        // Fixing it needs a field-read scope, so it is a decision, not a patch.
        storyPoints: i.fields?.customfield_10016 ?? 0,
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

const compute = async (path, { boardId, orgConfig, meta, extra }) => {
  const local = await fetchBoardIssues(boardId);
  const byKey = new Map(local.map((i) => [i.key, i]));

  const projected = local.map(projectIssue);
  assertNoFreeText(projected);

  const answer = await callCalculator(path, {
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

/** Sprints per board offered in the picker. The live server's default, for the
 *  same reason: a forecast samples a team's recent history, not its whole life. */
const SPRINTS_PER_BOARD = 6;

/** A page count no real project reaches, so a Jira that stopped sending
 *  `isLast` stops this rather than looping. It throws rather than returning
 *  what it has — a truncated list of a customer's boards reads as a complete
 *  one, and this repository has shipped that bug twice. */
const MAX_PAGES = 20;

/** Every page of an Agile list endpoint (`{values, isLast, total}`). */
const pagedValues = async (routeAt, what) => {
  const out = [];
  let startAt = 0;
  for (let page = 0; ; page += 1) {
    if (page >= MAX_PAGES) {
      throw new Error(
        `${what}: more than ${MAX_PAGES} pages. ${out.length} were read and none are ` +
        'reported, because a list cut short here would read as a complete one.',
      );
    }
    const res = await api.asUser().requestJira(routeAt(startAt));
    if (!res.ok) throw new Error(`${what}: Jira returned ${res.status}`);
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
const fetchSprintIssues = async (boardId, sprintId) => {
  const fields = [
    'summary', 'issuetype', 'status', 'assignee', 'priority', 'parent',
    'created', 'resolutiondate', 'duedate', 'labels', 'flagged',
    'customfield_10016',
  ].join(',');

  const out = [];
  let startAt = 0;
  for (let page = 0; ; page += 1) {
    if (page >= MAX_PAGES) {
      throw new Error(
        `issues in sprint ${sprintId}: more than ${MAX_PAGES} pages. ${out.length} were ` +
        'read and none are reported — a sprint shown short is a burndown that is wrong.',
      );
    }
    const res = await api.asUser().requestJira(
      route`/rest/agile/1.0/board/${boardId}/sprint/${sprintId}/issue?startAt=${startAt}&maxResults=100&fields=${fields}&expand=changelog`,
    );
    if (!res.ok) throw new Error(`issues in sprint ${sprintId}: Jira returned ${res.status}`);
    const body = await res.json();
    const page_ = body.issues ?? [];
    out.push(...page_);
    startAt += page_.length;
    if (!page_.length || startAt >= (body.total ?? startAt)) break;
  }
  return out;
};

/** Board metadata plus its recent sprints. A board with no sprints at all —
 *  a kanban board — makes Jira refuse the sprint endpoint; that is a fact
 *  about the board, not a failure, so it is reported and skipped rather than
 *  taking the whole picker down with it. */
const sprintsFor = async (board) => {
  try {
    return await pagedValues(
      (startAt) => route`/rest/agile/1.0/board/${board.id}/sprint?state=active,closed&startAt=${startAt}&maxResults=50`,
      `sprints on board ${board.id}`,
    );
  } catch {
    return null;
  }
};

/**
 * Every sprint on every board of the project this page is open in.
 *
 * The project comes from Forge's own context rather than from the page, so the
 * page sends nothing and cannot ask about a project it is not displayed in.
 */
resolver.define('contexts', async ({ context }) => {
  const projectKey = context?.extension?.project?.key;
  if (!projectKey) {
    return {
      status: 400,
      body: {
        error: 'This module was not opened on a Jira project, so there is no project '
             + 'to read boards from. Nothing was queried.',
      },
    };
  }

  const boards = await pagedValues(
    (startAt) => route`/rest/agile/1.0/board?projectKeyOrId=${projectKey}&startAt=${startAt}&maxResults=50`,
    `boards in project ${projectKey}`,
  );

  const contexts = [];
  let withoutSprints = 0;
  for (const board of boards) {
    const sprints = await sprintsFor(board);
    if (sprints === null) { withoutSprints += 1; continue; }
    for (const sprint of recentSprints(sprints, SPRINTS_PER_BOARD)) {
      contexts.push(contextEntry(board, sprint));
    }
  }

  // What was left out is said out loud, in the line the page prints in its
  // footer. A picker quietly missing a board is indistinguishable from a
  // project that does not have one.
  const label = `Jira, project ${projectKey} — ${boards.length - withoutSprints} board`
    + (boards.length - withoutSprints === 1 ? '' : 's')
    + (withoutSprints ? `, ${withoutSprints} without sprints and not offered` : '');

  return { status: 200, body: contextsBody(label, contexts) };
});

/**
 * One sprint's issues.
 *
 * The id carries project, board and sprint, so nothing is held between calls.
 * It is checked rather than trusted: the entry is rebuilt from what Jira says
 * the board and sprint are, and if that does not reproduce the id the caller
 * asked for, the answer is 404. A project key supplied by the page would
 * otherwise label another project's board.
 */
resolver.define('context', async ({ payload, context }) => {
  const asked = payload?.id;
  const parsed = parseContextId(asked);
  if (!parsed) return { status: 404, body: notFound(asked) };

  const boardRes = await api.asUser().requestJira(
    route`/rest/agile/1.0/board/${parsed.boardId}`,
  );
  if (boardRes.status === 404) return { status: 404, body: notFound(asked) };
  if (!boardRes.ok) throw new Error(`board ${parsed.boardId}: Jira returned ${boardRes.status}`);
  const board = await boardRes.json();

  // Found through the board rather than by /sprint/{id} directly, so this
  // needs no scope the contexts call does not already need — and so a sprint
  // id from another board cannot be read through this one.
  const sprints = await sprintsFor(board);
  const sprint = (sprints ?? []).find((sp) => String(sp.id) === parsed.sprintId);
  if (!sprint) return { status: 404, body: notFound(asked) };

  const entry = contextEntry(board, sprint);
  if (entry.id !== asked) return { status: 404, body: notFound(asked) };

  const raw = await fetchSprintIssues(parsed.boardId, parsed.sprintId);
  const issues = raw.map((r) => issueFrom(r, {
    sprintStart: entry.startDate,
    // Only so an issue key is a link. Absent, the page leaves it as text
    // rather than guessing a host.
    siteUrl: context?.siteUrl,
  }));

  return { status: 200, body: contextBody(entry, issues) };
});

/**
 * The forecast and the sequencing, over the bridge.
 *
 * Both are computed by the hosted calculator, and no calculator is hosted —
 * `remotes[0].baseUrl` in the manifest still points at `.invalid` and no
 * environment has been provisioned. The honest answer is the tool's own
 * refusal shape saying exactly that, not a number and not an error: the rest
 * of the page is the tenant's real data and works.
 *
 * Delete these two the moment `CALCULATOR_URL` names a real deployment, and
 * route them through `compute()` — the projection and re-attachment are
 * already written and tested.
 */
const NO_CALCULATOR =
  'The forecast is computed by a hosted calculator, and this installation has not '
  + 'been pointed at one. Nothing was simulated. Everything else on this page is '
  + "this site's own data.";

resolver.define('forecast', () => ({
  status: 200,
  body: {
    sprint_completion: { available: false, reason: NO_CALCULATOR },
    capacity_to_target: { available: false, reason: NO_CALCULATOR },
    next_commitment: { available: false, reason: NO_CALCULATOR },
    asked: {}, sampled_from: {}, inputs: {},
  },
}));

resolver.define('sequence', () => ({
  status: 200,
  body: {
    available: false,
    sentence: 'Ask sequencing is computed by a hosted calculator, and this installation '
            + 'has not been pointed at one. Nothing was sequenced.',
  },
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
    storyPoints: i.fields?.customfield_10016 ?? 0,
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
    // Keys and dates only. Summaries stay on this side even in the sample.
    sample: raw.map((i) => ({ key: i.key, status: i.status, created: i.created })),
    projected: projected[0] ?? null,
    freeTextFields: leaked,
  };
});

/* `facts` is the one resolver still wired to compute(). The projection, the
   free-text assertion, the call and the re-attachment are real and tested
   (tests/test_service.py); what is missing is a calculator to call and the
   mapping from a context id to the board a calculation reads. When
   CALCULATOR_URL names a real deployment, the two refusals above become
   compute('/v1/forecast', …) and compute('/v1/sequence', …) with that
   mapping, and nothing else here changes. */
resolver.define('facts', ({ payload }) => compute('/v1/facts', payload ?? {}));

export const handler = resolver.getDefinitions();
