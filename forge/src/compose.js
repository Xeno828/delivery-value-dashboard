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
import { MODEL, briefMessages, proseFrom, proseProblems } from './brief.js';

/** How many times the model is asked before a section gives up. Two, so one
 *  corrective round is possible and a stubborn model costs one extra call
 *  rather than an unbounded number on a schedule nobody is watching. */
const ATTEMPTS = 2;
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

  /* Ask again when the guard refuses, and tell it what it did.
     A tenant run had the model write "two" and "85" into every section despite
     the rule, so every section was refused and nothing was sent — for ever,
     because a weekly trigger would repeat the same prompt and get the same
     answer. A model that breaks the contract gets shown the complaint and one
     more try; a model that breaks it twice is reported, not softened. The
     figures never change between attempts, so a retry cannot produce a
     different number, only a different sentence. */
  const messages = briefMessages({ audience, figures, refused: [] });
  let got = null;
  for (let attempt = 0; attempt < ATTEMPTS; attempt += 1) {
    // eslint-disable-next-line no-await-in-loop
    const response = await ask({ model: MODEL, messages });
    got = proseFrom(response);
    if (got.problems) break;              // a failed call is not a rule breach
    const bad = proseProblems(got.prose);
    if (!bad.length) break;
    if (attempt === ATTEMPTS - 1) return { heading, template, values: figures, problems: bad };
    messages.push({ role: 'assistant', content: got.prose });
    messages.push({
      role: 'user',
      content: `That was rejected: ${bad.join(' ')} Write it again with no `
             + 'number in it at all — not in digits, not spelled out, not a '
             + 'percentile, a count, a date or a duration.',
    });
  }
  // A model that returned nothing usable is not softened into a section with
  // an empty paragraph — the brief does not go. But `proseFrom` knows *which*
  // way it was unusable (no choices, stopped early, no text) and that reason
  // used to be dropped here in favour of an empty string, which then tripped
  // the empty-prose guard and reported "the model returned no prose at all"
  // for every cause alike. The first live run said exactly that, three times,
  // and named nothing that could be acted on. Carried through now.
  if (got.problems) return { heading, template, values: figures, problems: got.problems };
  return { heading, template, values: figures, prose: got.prose };
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
    template: '85% of finished work took {{typical_days}} {{unit}} or less.',
    // Not `p85`. Slot names reach the model — the values are listed to it by
    // key — so a key with a digit in it hands the model a number to copy, and
    // it copied exactly that one. The template keeps the 85; the model never
    // sees a template.
    figures: { typical_days: fl.cycle_p85, unit: fl.unit },
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
     is the product working rather than a gap. ADR 0007, and `section()` will
     not let the model near the refusal.
     ------------------------------------------------------------------
     The figures live under `sprint_completion`, not at the top level. This
     read `forecast.remaining_items` and `forecast.percentiles` — the shape of
     the *flat* `/v1/forecast` route — while the context route returns
     `{ sprint_completion, item_risk, next_commitment, ... }`. In a tenant that
     produced "the brief asks for remaining, landing_date and the tools did not
     return it", which is `fillSlots` refusing exactly as designed over figures
     that were there all along under another key. Checkable in this repository
     at any point and checked only after it failed in production. */
  const completion = forecast?.sprint_completion ?? forecast ?? {};
  const outlook = completion.available === false || forecast?.sentence
    ? {
      heading: 'Forecast',
      template: 'unused',
      figures: {},
      /* The tool's own words, and only its own words. There is no `sentence`
         in the payload — `Refusal.sentence()` is a Python method and does not
         survive serialisation — so this quotes `reason` verbatim and puts
         have/need beside it as data, which is precisely what `fcRefusal` in
         `src/app.js` does. Composing the fuller sentence here would be a
         second implementation of it in a second language. */
      refusal: forecast?.sentence
        || `No forecast: ${completion.reason || 'not available'}.`
           + (completion.have != null && completion.need != null
             ? ` Has ${completion.have}, needs ${completion.need}.` : ''),
    }
    : {
      heading: 'Forecast',
      template: 'On the evidence so far, {{remaining}} items remain and the 85th '
              + 'percentile lands on {{landing_date}}.',
      figures: {
        remaining: completion.remaining_items,
        landing_date: completion.percentiles?.['85'] ?? completion.percentiles?.[85],
      },
    };

  return audience === 'exec'
    ? [delivery, outlook, blocked]
    : [delivery, scope, flow, outlook, blocked];
};
