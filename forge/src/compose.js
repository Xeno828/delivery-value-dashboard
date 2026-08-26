/**
 * From figures to a sent brief. No Forge, no network, no model.
 *
 * The model and the send arrive as parameters. `index.js` supplies `chat` from
 * `@forge/llm` and its own `sendBrief`; the tests supply stubs. Nothing here
 * imports the SDK, which is what makes the interesting half of item 3 testable
 * — `index.js` cannot be loaded outside Forge, so anything left in it is
 * provable only by deploying and watching.
 *
 * It computes nothing. Figures arrive decided, prose arrives written, and this
 * chooses neither.
 */

import { composeBrief } from './brief.js';
import { MODEL, briefMessages, proseFrom } from './brief.js';
import { sendsFor } from './recipients.js';
import { emailBody } from './mailbody.js';

/**
 * One audience's section, written by the model and assembled in code.
 *
 * Exported for the tests, which run it with a stub `chat` — the composition and
 * the guard are what can be wrong here, and neither needs Atlassian to be
 * reachable to be checked.
 */
export const composeSection = async ({ audience, heading, template, figures,
                                      refusal, ask }) => {
  if (refusal) return { heading, template, values: figures, prose: '', refusal };

  const response = await ask({
    model: MODEL,
    messages: briefMessages({ audience, figures, refused: [] }),
  });
  const got = proseFrom(response);
  // A model that returned nothing usable is not softened into a section with
  // an empty paragraph; it is handed to composeBrief as prose that will fail
  // its guard, and the brief does not go.
  return { heading, template, values: figures, prose: got.prose ?? '' };
};

/**
 * Everything after the board is read: compose, render, send.
 *
 * `ask` and `send` are parameters with no defaults, which is the whole reason
 * this file exists rather than living in `index.js`. That file imports the
 * Forge SDK and cannot be loaded outside Atlassian's runtime, so anything in it
 * is provable only by deploying. Here the model and the send are injected, so
 * `tests/test_service.py` runs the entire path over fixture figures with a stub
 * of each — and the code that decides what reaches an inbox is exercised
 * without a tenant.
 */
export const briefsForBoard = async ({
  config, boardId, boardName, periodName, asOf, calendar, boardUrl,
  figuresFor, ask, send,
}) => {
  const resolved = sendsFor(config, boardId);
  if (resolved.problems) return { sent: false, reasons: resolved.problems };

  const results = [];
  for (const { audience, anchorIssue, to } of resolved.sends) {
    const built = await Promise.all(
      figuresFor(audience).map((f) => composeSection({ ...f, audience, ask })));

    const brief = composeBrief({ audience, sections: built });
    if (!brief.sent) {
      results.push({ audience, sent: false, reasons: brief.problems });
      continue;
    }

    const { subject, textBody, htmlBody } = emailBody({
      audience, boardName, periodName, asOf, calendar, boardUrl,
      sections: brief.sections,
    });

    const outcome = await send({ anchorIssue, to, subject, textBody, htmlBody });
    results.push({
      audience,
      sent: outcome.sent === true,
      ...(outcome.reason ? { reasons: [outcome.reason] } : {}),
      refusedSections: brief.refusedSections,
    });
  }
  return { results };
};

