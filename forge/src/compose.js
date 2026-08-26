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


/**
 * Which figures each audience's brief carries, as sections.
 *
 * Values are passed through exactly as the tools reported them. **No
 * arithmetic** — not a percentage, not a rounding, not a total. `facts` already
 * holds `items_done_pct`, and this deliberately does not use it: turning 0.6942
 * into "69%" is a calculation, and the moment this file does one, a figure in a
 * brief is a figure no tool produced. Counts say the same thing and need none.
 *
 * The executive brief is shorter and that is the difference between the two,
 * not a different set of numbers. Two audiences reading different figures about
 * one sprint is how a meeting becomes an argument about arithmetic.
 */
export const sectionsFor = (audience, { facts, forecast }) => {
  const d = facts?.delivery ?? {};
  const sc = facts?.scope ?? {};
  const fl = facts?.flow ?? {};
  const rk = facts?.risk ?? {};

  const delivery = {
    heading: 'Delivery',
    template: '{{done}} of {{total}} items finished.',
    figures: { done: d.items_done, total: d.items_total },
  };

  const scope = {
    heading: 'Scope',
    template: '{{added}} items were added after planning.',
    figures: { added: sc.added_items },
  };

  const flow = {
    heading: 'How long work takes',
    template: '85% of finished work took {{p85}} {{unit}} or less.',
    figures: { p85: fl.cycle_p85, unit: fl.unit },
  };

  const blocked = {
    heading: 'Blocked',
    template: '{{n}} items are flagged as blocked, and the oldest open item has '
            + 'been open {{oldest}} {{unit}}.',
    figures: {
      n: (rk.blocked ?? []).length,
      oldest: rk.oldest_open?.days,
      unit: rk.unit,
    },
  };

  /* The forecast is the one section that is routinely absent, and its absence
     is the product working rather than a gap. `forecast.sentence` is the tool's
     own words and is carried untouched — ADR 0007, and `section()` will not let
     the model near it. */
  const outlook = forecast?.available === false || forecast?.sentence
    ? { heading: 'Forecast', template: 'unused', figures: {},
        refusal: forecast.sentence }
    : {
      heading: 'Forecast',
      template: 'On the evidence so far, {{remaining}} items remain and the 85th '
              + 'percentile lands on {{p85}}.',
      figures: {
        remaining: forecast?.remaining_items,
        p85: forecast?.percentiles?.['85'] ?? forecast?.percentiles?.[85],
      },
    };

  return audience === 'exec'
    ? [delivery, outlook, blocked]
    : [delivery, scope, flow, outlook, blocked];
};
