/**
 * Forge resolver — SCAFFOLD, NOT WIRED UP.
 *
 * The point of this file is the boundary it draws, not the code in it.
 *
 * The dashboard's numbers come from three dependency-free Python modules in
 * agent/tools: metrics.py (facts), forecast.py (Monte Carlo) and intake.py
 * (sizing an ask). Forge runs Node in Atlassian's sandbox and cannot call
 * them. So a Forge build has exactly two honest options:
 *
 *   1. Forge fetches the issues and hands them to the same Python, running
 *      somewhere else. The app becomes a thin data path; the numbers stay in
 *      one implementation. This is the option the roadmap's risk section
 *      argues for — "keep the forecasting tools as dependency-free Python
 *      that the app calls, so the engine is portable even when the
 *      distribution is not".
 *
 *   2. Port the tools to JavaScript. That is a second implementation of a
 *      seeded Monte Carlo, and the moment it exists the tile and the written
 *      brief can disagree about the same sprint. The project already refused
 *      this once — it is why the forecast tile shows an offline notice in an
 *      emailed file rather than recomputing itself in the browser.
 *
 * Nothing here decides that. The resolvers return the shape the UI expects and
 * no data, so the decision stays visible instead of being made by whoever
 * writes the first working version.
 */

import Resolver from '@forge/resolver';
import api, { route } from '@forge/api';

const resolver = new Resolver();

const NOT_WIRED = {
  available: false,
  sentence:
    'This Forge app is a scaffold. The working connection is OAuth 2.0 (3LO) — ' +
    'see scripts/jira_auth.py. Nothing here has been deployed.',
};

/**
 * The one thing that is real: proof the scopes in manifest.yml are enough to
 * read a board's issues. Everything downstream depends on it and it is cheap
 * to check first.
 */
resolver.define('boardIssues', async ({ payload }) => {
  const boardId = String(payload?.boardId ?? '').replace(/[^0-9]/g, '');
  if (!boardId) return { ...NOT_WIRED, reason: 'no board id' };

  const res = await api
    .asUser()
    .requestJira(route`/rest/agile/1.0/board/${boardId}/issue?maxResults=50`);
  if (!res.ok) return { ...NOT_WIRED, reason: `Jira returned ${res.status}` };

  const body = await res.json();
  // Deliberately not categorised here. Which statuses mean done is organisation
  // config (config/organisation.json, mirrored in agent/tools/orgconfig.py), and
  // a third copy of that rule written in this file is exactly the divergence the
  // config exists to prevent.
  return {
    available: true,
    total: body.total ?? 0,
    issues: (body.issues ?? []).map((i) => ({
      key: i.key,
      summary: i.fields?.summary ?? '',
      status: i.fields?.status?.name ?? null,
      statusCategoryHint: i.fields?.status?.statusCategory?.name ?? null,
      created: (i.fields?.created ?? '').slice(0, 10) || null,
      resolved: (i.fields?.resolutiondate ?? '').slice(0, 10) || null,
    })),
  };
});

/** Would call forecast.py. Returns a refusal rather than a number. */
resolver.define('forecast', async () => NOT_WIRED);

/** Would call metrics.py. Same. */
resolver.define('facts', async () => NOT_WIRED);

export const handler = resolver.getDefinitions();
