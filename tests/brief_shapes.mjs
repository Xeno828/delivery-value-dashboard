/**
 * Runs `forge/src/brief.js` over the cases `tests/test_service.py` asserts on.
 *
 * Reads one JSON object on stdin and writes one on stdout. The reason it takes
 * input at all is the refusal round-trip: the sentence has to be the one
 * `agent/tools/forecast.py` really produces, not a copy of it pasted here, or
 * the test proves that two copies of a string are equal and nothing else.
 * Python builds a real `Refusal`, pipes its sentence in, and asserts what comes
 * back is identical byte for byte.
 *
 *     echo '{"refusal":"..."}' | node tests/brief_shapes.mjs
 */

import {
  MODEL, NUMBER_WORDS, PROSE_RULE, UNCHECKED,
  briefMessages, composeBrief, deliveryBlockers, fillSlots, proseFrom,
  proseProblems, section, slotsIn,
} from '../forge/src/brief.js';

const stdin = await new Promise((resolve) => {
  let buf = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (d) => { buf += d; });
  process.stdin.on('end', () => resolve(buf));
});
const input = JSON.parse(stdin || '{}');

/* Prose a model could plausibly return. The first group is usable; the second
   carries a figure and must not be. The usable group is not decoration — every
   entry in it contains a word that *contains* a number word, which is the way
   a substring check for "one", "ten" or "half" turns the guard into something
   that refuses every brief. */
const USABLE = {
  plain: 'Throughput fell against the previous sprint, and the drop sits in '
       + 'items that were started and not finished.',
  substringBait: 'Work is often blocked upstream, and someone raised it on '
       + 'behalf of the team. The vendor did not phone back; chasing it is '
       + 'onerous and the whole thread reads as atonal.',
  punctuation: 'Delivery slowed — the queue, not the team, is where it went.',
};

const CARRIES_A_FIGURE = {
  digit: 'Throughput fell to 4 items.',
  percent: 'Flow efficiency was 22%.',
  decimal: 'The median cycle time was 3.5 days.',
  thousands: 'The simulation ran 20,000 trials.',
  word: 'Throughput fell to four items.',
  wordCapitalised: 'Six sprints were sampled.',
  fraction: 'Roughly half the sprint was unplanned work.',
  slot: 'Throughput was {{throughput}} this sprint.',
  empty: '   ',
};

const TEMPLATE = 'Throughput was {{throughput}} items against {{committed}} committed.';

/* The refusal Python really produced, carried through untouched. */
const refusal = input.refusal || '';

const refusedSection = section({
  heading: 'Forecast',
  template: 'The 85th percentile lands on {{p85}}.',
  values: { p85: '2026-09-14' },
  /* Deliberately a *usable* piece of prose that contradicts the refusal. If
     anything in section() prefers the model's sentences when they are
     well-formed, this is where it shows: the output must be the refusal and
     must not contain a syllable of this. */
  prose: 'Delivery is comfortably on track and the team should expect to finish early.',
  refusal,
});

console.log(JSON.stringify({
  numberWords: NUMBER_WORDS,
  proseRule: PROSE_RULE,
  unchecked: UNCHECKED,
  model: MODEL,

  /* What the model is asked. The figures must arrive named rather than in a
     sentence: prose the model is shown is prose it will copy, and copied prose
     carries the figure, which its own guard would then refuse. A prompt that
     cannot produce a passing answer fails weekly for a reason invisible from
     the prompt. */
  messages: briefMessages({
    audience: 'exec',
    figures: { throughput: 9, committed: 12 },
    refused: ['forecast'],
  }),

  /* The model's answer, in the four states it comes back in. Truncation is the
     one worth having: half a paragraph reads as a whole one. */
  responses: {
    ok: proseFrom({ choices: [{ finish_reason: 'stop',
      message: { content: '  Throughput fell against the previous sprint.  ' } }] }),
    truncated: proseFrom({ choices: [{ finish_reason: 'length',
      message: { content: 'Throughput fell against the previ' } }] }),
    empty: proseFrom({ choices: [{ finish_reason: 'stop', message: { content: '   ' } }] }),
    noChoices: proseFrom({ choices: [] }),
    rubbish: proseFrom(null),
  },

  /* Why a scheduled run is not sending. All three are real today. */
  blockers: {
    nothingConfigured: deliveryBlockers({}),
    scopeOnly: deliveryBlockers({ scope: [{ boardId: 2 }] }),
    scopeAndRecipients: deliveryBlockers({
      scope: [{ boardId: 2 }], recipients: ['a@example.com'] }),
    allThree: deliveryBlockers({
      scope: [{ boardId: 2 }], recipients: ['a@example.com'], transport: 'mail' }),
  },

  usable: Object.fromEntries(
    Object.entries(USABLE).map(([k, v]) => [k, proseProblems(v)])),
  carriesAFigure: Object.fromEntries(
    Object.entries(CARRIES_A_FIGURE).map(([k, v]) => [k, proseProblems(v)])),

  slots: slotsIn(TEMPLATE),

  /* A slot the tools did not fill. The assertion is not only that it refuses,
     but that no partly filled text comes back beside the refusal — a caller
     that reads `text` first and `problems` second would send it. */
  missingSlot: fillSlots(TEMPLATE, { throughput: 9 }),
  filled: fillSlots(TEMPLATE, { throughput: 9, committed: 12 }),
  /* Zero is a value, not an absence. A guard written as `!have[k]` would treat
     a real measured zero as a missing figure and refuse a brief that was
     correct — the same confusion ADR 0010 is about, pointing the other way. */
  filledWithZero: fillSlots('Unplanned work was {{unplanned}} items.', { unplanned: 0 }),

  refusedSection,

  /* One broken section stops the whole brief. */
  brokenBrief: composeBrief({
    audience: 'exec',
    sections: [
      { heading: 'Delivery', template: 'Throughput was {{throughput}}.',
        values: { throughput: 9 }, prose: USABLE.plain },
      { heading: 'Forecast', template: 'Lands on {{p85}}.',
        values: { p85: '2026-09-14' }, prose: CARRIES_A_FIGURE.digit },
    ],
  }),

  /* A refused section is the product working, and is carried. */
  briefWithARefusal: composeBrief({
    audience: 'exec',
    sections: [
      { heading: 'Delivery', template: 'Throughput was {{throughput}}.',
        values: { throughput: 9 }, prose: USABLE.plain },
      { heading: 'Forecast', template: 'Lands on {{p85}}.',
        values: {}, prose: USABLE.plain, refusal },
    ],
  }),
}, null, 2));
