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
 * Status: the projection, re-attachment and call plumbing below are real and
 * tested against the calculator (tests/test_service.py asserts the projection
 * loses nothing). What has never run is Forge itself — no app has been
 * registered and nothing has been deployed. Treat the manifest's Forge-specific
 * syntax as needing a check against current Atlassian docs.
 */

import Resolver from '@forge/resolver';
import api, { route, fetch } from '@forge/api';

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
  const raw = (body.issues ?? []).map((i) => ({
    key: i.key,
    summary: i.fields?.summary ?? '',
    assignee: i.fields?.assignee?.displayName ?? null,
    status: i.fields?.status?.name ?? null,
    created: (i.fields?.created ?? '').slice(0, 10) || null,
    resolved: (i.fields?.resolutiondate ?? '').slice(0, 10) || null,
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

resolver.define('forecast', ({ payload }) => compute('/v1/forecast', payload ?? {}));
resolver.define('facts', ({ payload }) => compute('/v1/facts', payload ?? {}));
resolver.define('sequence', ({ payload }) => compute('/v1/sequence', payload ?? {}));

export const handler = resolver.getDefinitions();
