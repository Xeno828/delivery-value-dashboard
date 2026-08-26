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
import {
  AUDIENCES, RESTRICT, boardsIn, notifyPayload, problemsIn, sendsFor,
} from '../forge/src/recipients.js';
import { emailBody, esc, safeUrl } from '../forge/src/mailbody.js';
import { briefsForBoard } from '../forge/src/compose.js';

/* One set of recipient cases, judged here and by scripts/serve_live.py. Two
   implementations of a rule is what this repository most reliably regrets; the
   mirror is tolerated only because this file and that one are held together by
   `test_the_two_recipient_validators_agree`. */
import { readFileSync } from 'node:fs';
const RECIPIENT_CASES = JSON.parse(
  readFileSync(new URL('./fixtures/recipient-configs.json', import.meta.url)));

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

/* A board name an attacker controls. Issue text is writable by anyone who can
   raise a ticket, and this is the first surface in the product that renders it
   somewhere this repository does not control. */
const HOSTILE = '</p><script>alert(1)</script><p onmouseover="x">';
/* A heading is issue-derived too — a section can be named after a context. */
const HOSTILE_HEADING = 'Delivery <img src=x onerror="alert(1)">';

const MAIL_CONFIG = { boards: { 2: {
  anchorIssue: 'SFT-1',
  exec: { users: ['5b10a2844c20165700ede21g'] },
  team: { groups: ['storefront'] },
} } };

const answers = (content) => async () => ({
  choices: [{ finish_reason: 'stop', message: { content } }],
});

const REFUSAL_SENTENCE = 'No forecast: too little completion history to sample '
  + 'from (2 observations, 6 needed). A wider confidence interval would not fix '
  + 'this — the data is absent, not noisy.';

const figures = () => [
  { heading: 'Delivery', template: 'Throughput was {{t}} of {{c}} committed.',
    figures: { t: 9, c: 12 } },
  { heading: 'Forecast', template: 'unused', figures: {}, refusal: REFUSAL_SENTENCE },
];

const runBoard = async (opts) => {
  const captured = [];
  const out = await briefsForBoard({
    config: MAIL_CONFIG, boardId: 2, boardName: HOSTILE, periodName: 'Sprint 24',
    asOf: '2026-08-26', calendar: '5-day working week, 14-day sprints',
    boardUrl: 'https://example.atlassian.net/jira/software/boards/2',
    figuresFor: figures,
    send: async (p) => { captured.push(p); return { sent: true }; },
    ...opts,
  });
  return { out, captured };
};

const usable = await runBoard({ ask: answers('Delivery slowed against the previous sprint.') });
/* Prose carrying a figure fails brief.js's guard. The assertion that matters is
   not that composeBrief refuses — that is already covered — but that nothing
   reaches the send when it does. */
const guarded = await runBoard({ ask: answers('Throughput fell to 4 items.') });
const badConfig = await (async () => {
  const captured = [];
  const out = await briefsForBoard({
    config: { boards: { 2: { anchorIssue: 'SFT-1', exec: { users: ['a@b.com'] } } } },
    boardId: 2, figuresFor: figures, ask: answers('Fine.'),
    send: async (p) => { captured.push(p); return { sent: true }; },
  });
  return { out, captured };
})();
/* Jira refusing one audience must not take the other with it. */
const jiraRefuses = await (async () => {
  const seen = [];
  const out = await briefsForBoard({
    config: MAIL_CONFIG, boardId: 2, boardName: 'B', figuresFor: figures,
    ask: answers('Delivery slowed.'),
    send: async (p) => {
      seen.push(p.subject);
      return seen.length === 1
        ? { sent: false, reason: 'Jira refused the notification for SFT-1 with 403.' }
        : { sent: true };
    },
  });
  return { out, attempts: seen.length };
})();

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

  /* The brief as an email, which is a new output surface for issue text. */
  mail: {
    /* Character for character what src/app.js uses. A second escaper handling
       four of the five characters is the shape this bug arrives in. */
    escSample: esc(HOSTILE),
    escAll: esc(`&<>"'`),
    safeUrl: {
      https: safeUrl('https://example.atlassian.net/x'),
      javascript: safeUrl('javascript:alert(1)'),
      data: safeUrl('data:text/html,<script>alert(1)</script>'),
      empty: safeUrl(''),
    },
    /* A refusal must not be styled as prose: it is a statement that was
       answered, not a paragraph that happened to be short. */
    body: emailBody({
      audience: 'exec', boardName: HOSTILE, periodName: 'Sprint 24',
      asOf: '2026-08-26', calendar: '5-day week',
      boardUrl: 'javascript:alert(1)',
      sections: [
        /* Hostile text in the *body*, not only the board name. A section's text
           is prose plus substituted figures, and a figure can carry issue text:
           `reattach` puts summaries back on item_risk rows before anything is
           rendered. This is the path that matters and it is the one a fixture
           full of polite sentences never exercises. */
        { heading: HOSTILE_HEADING,
          text: `Delivery slowed.\n\nBlocked: ${HOSTILE}`, refused: false },
        { heading: 'Forecast', text: REFUSAL_SENTENCE, refused: true },
      ],
    }),
    payload: notifyPayload({ subject: 's', textBody: 't', htmlBody: 'h',
                            to: { users: [{ accountId: 'x' }] } }),
    /* A subject is a mail header and a header ends at a newline. Escaping does
       nothing about that — it is a different bug from the HTML below. */
    headerInjection: emailBody({
      audience: 'exec', boardName: 'Storefront\r\nBcc: attacker@evil.example',
      periodName: 'Sprint 24', sections: [],
    }).subject,
    longSubject: emailBody({
      audience: 'team', boardName: 'B'.repeat(400), sections: [],
    }).subject,
  },

  /* Compose, render and send, with the model and the send stubbed. */
  pipeline: {
    usable: { out: usable.out, subjects: usable.captured.map((p) => p.subject),
              anchors: usable.captured.map((p) => p.anchorIssue),
              html: usable.captured[0]?.htmlBody ?? '',
              text: usable.captured[0]?.textBody ?? '' },
    guarded: { out: guarded.out, sends: guarded.captured.length },
    badConfig: { out: badConfig.out, sends: badConfig.captured.length },
    jiraRefuses: { out: jiraRefuses.out, attempts: jiraRefuses.attempts },
  },

  /* Who a board's brief goes to. The good config exercises both audiences,
     both recipient kinds and two of Atlassian's account id shapes; the bad one
     is every way an administrator gets this wrong, and each has to be caught
     separately because they will arrive one at a time, a week apart. */
  recipients: (() => {
    const good = { boards: {
      2: { anchorIssue: 'SFT-1',
           exec: { users: ['5b10a2844c20165700ede21g'], groups: ['leadership'] },
           team: { users: ['712020:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'] } },
      7: { anchorIssue: 'OPS-42', team: { groups: ['ops-team'] } },
    } };
    const bad = {
      /* An address cannot be delivered by this endpoint at all, and looking it
         up would mean claiming the person at that address is that Jira user. */
      email:        { anchorIssue: 'SFT-1', exec: { users: ['josh@example.com'] } },
      displayName:  { anchorIssue: 'SFT-1', exec: { users: ['Josh Bruen'] } },
      /* Sends to nobody, which looks exactly like a send that worked. */
      emptyAudience:{ anchorIssue: 'SFT-1', exec: { users: [], groups: [] } },
      /* Listed, therefore looks covered, and silent. */
      noAudience:   { anchorIssue: 'SFT-1' },
      noAnchor:     { exec: { users: ['5b10a2844c20165700ede21g'] } },
      badAnchor:    { anchorIssue: 'not-a-key', exec: { users: ['5b10a2844c20165700ede21g'] } },
      notAnObject:  'leadership@example.com',
    };
    return {
      audiences: AUDIENCES,
      restrict: RESTRICT,
      goodProblems: problemsIn(good),
      boards: boardsIn(good),
      sends: sendsFor(good, 2),
      groupsOnly: sendsFor(good, 7),
      unconfigured: sendsFor(good, 99),
      /* One broken audience refuses the whole board, including the audience
         that was fine — the entry was written by one person in one sitting. */
      partiallyBroken: sendsFor({ boards: { 2: {
        anchorIssue: 'SFT-1',
        exec: { users: ['5b10a2844c20165700ede21g'] },
        team: { users: ['josh@example.com'] },
      } } }, 2),
      each: Object.fromEntries(Object.entries(bad).map(
        ([name, entry]) => [name, problemsIn({ boards: { 9: entry } })])),
      empty: problemsIn({ boards: {} }),
      notAnObject: problemsIn(null),
      noBoardsKey: problemsIn({}),
      /* A config that does not validate offers no boards to walk, rather than
         offering the ones that happened to parse. */
      boardsFromBroken: boardsIn({ boards: { 9: bad.email } }),
      /* The shared set. Python runs the identical list and the two verdicts
         have to match, case for case. */
      verdicts: RECIPIENT_CASES.map(
        (c) => [c.name, problemsIn(c.config).length === 0]),
    };
  })(),

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
