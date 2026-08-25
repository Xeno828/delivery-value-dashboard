/**
 * Composing the scheduled brief. No Forge, no network, no model.
 *
 * Roadmap item 3 mails the two views out on a timer, and the brief that goes
 * with them is written by a model — Forge LLMs, inside Atlassian's runtime, so
 * the tenant's issue text never leaves the boundary it is already inside.
 * ADR 0013 has that decision and the alternative it rejected.
 *
 * This file is the half of it that has to be right rather than merely
 * plausible, which is why it is pure: everything below is a function of a
 * string and an object, and `tests/test_service.py` runs it over cases that a
 * deploy could not reach.
 *
 * The shape it enforces is the whole design, and it is easier to state than to
 * argue with:
 *
 *   The model never writes a number. It writes the sentences between them.
 *
 * A brief is a template with named slots. Tool output fills the slots, by
 * substitution, in code. The model is given the figures so it knows which way
 * things moved, and is told to refer to them by name — "throughput fell" — with
 * the value arriving from the slot beside it. Prose that comes back carrying a
 * numeral has restated a figure, and a restatement is a second copy of a number
 * that can disagree with the first. That is ADR 0005's rule reaching the one
 * place ADR 0005 did not anticipate: the tools compute, and something else
 * narrates.
 *
 * The alternative — let the model write the figures and check them afterwards
 * against the tool output — was rejected. Checking that a number in prose
 * matches a number in a dict requires knowing which figure a given numeral was
 * meant to be, and getting that wrong in the permissive direction passes a
 * wrong number. Forbidding the numeral outright needs no such judgement.
 */

/**
 * Numbers written as words, because a digit check alone is a hole a model
 * walks through without trying: *"throughput fell to four"* carries a figure
 * and contains no digit.
 *
 * This list is deliberately finite and therefore incomplete — see
 * `UNCHECKED` below, which says so out loud rather than letting the guard read
 * as total.
 */
export const NUMBER_WORDS = [
  'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
  'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen',
  'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty', 'thirty', 'forty',
  'fifty', 'sixty', 'seventy', 'eighty', 'ninety', 'hundred', 'thousand',
  'half', 'third', 'quarter', 'twice', 'double', 'triple',
];

/**
 * What this guard does not catch, stated because a bounded check that reads as
 * a total one is the failure this repository has been bitten by twice.
 *
 * It cannot catch a figure carried by a comparison rather than a numeral —
 * *"throughput more than halved"* survives `halved` not being in the list
 * above, and *"most of the sprint"* is a quantity with no number in it at all.
 * Nor can it catch prose that contradicts a refusal: a brief whose forecast was
 * refused and whose sentences say delivery is on track is well-formed by every
 * rule here. That one is answered structurally instead — the refusal is printed
 * verbatim beside the prose, so a reader sees both — and not by this function.
 */
export const UNCHECKED = 'quantities written without a numeral, and prose that '
  + 'contradicts a refusal rather than restating a figure';

/** A slot: `{{throughput}}`. Lower case and underscores, so a slot cannot be
 *  confused with the prose around it or with Handlebars in a template someone
 *  pastes in from elsewhere. */
export const SLOT = /\{\{\s*([a-z][a-z0-9_]*)\s*\}\}/g;

/** Every slot a template asks for, in order, without duplicates. */
export const slotsIn = (template) => {
  const seen = [];
  for (const m of String(template).matchAll(SLOT)) {
    if (!seen.includes(m[1])) seen.push(m[1]);
  }
  return seen;
};

/**
 * The instruction the model is given. Exported rather than inlined at the call
 * site because the guard below and this sentence have to describe the same
 * rule: a prompt that invites a figure and a check that forbids one produce a
 * brief that fails every week for a reason nobody can see from the prompt.
 */
export const PROSE_RULE = [
  'Write the connective prose only. Do not write any number, in digits or in',
  'words, and do not restate a figure you were given: refer to it by name and',
  'say which way it moved. The figures are inserted beside your sentences from',
  'the tools that produced them.',
].join(' ');

/**
 * What is wrong with a piece of model-written prose, as sentences.
 *
 * Empty array means usable. Every problem names the offending token, because a
 * guard that says "prose contained a number" and not which one cannot be acted
 * on by the thing that has to regenerate it.
 */
export const proseProblems = (prose) => {
  const text = String(prose ?? '');
  const problems = [];

  if (!text.trim()) {
    problems.push('the model returned no prose at all');
    return problems;
  }

  const digits = text.match(/\d+(?:[.,]\d+)*%?/g);
  if (digits) {
    problems.push(
      `the prose states ${unique(digits).map(q).join(', ')}. Figures are `
      + 'inserted from tool output, not written by the model — a restated '
      + 'figure is a second copy that can disagree with the first.');
  }

  /* Matched as whole words rather than as substrings, which is the difference
     between a guard and a nuisance: a substring test finds "ten" inside
     "often", "one" inside "someone" and "half" inside "behalf", and refuses
     every brief that uses any of them. The tests hold those three words
     specifically. */
  const words = unique(
    (text.toLowerCase().match(/[a-z]+/g) || []).filter(
      (w) => NUMBER_WORDS.includes(w)));
  if (words.length) {
    problems.push(
      `the prose states ${words.map(q).join(', ')} as a word. A figure spelled `
      + 'out is still a figure, and still a second copy of it.');
  }

  /* Slots left in what the model returned. The model is not given the
     template and has no business emitting one; a `{{...}}` coming back means
     it is trying to place a figure itself, which is the same failure arriving
     by a different route. */
  const slots = slotsIn(text);
  if (slots.length) {
    problems.push(
      `the prose contains the slot ${slots.map((s) => q(`{{${s}}}`)).join(', ')}. `
      + 'Slots are filled by the caller from tool output; prose that writes one '
      + 'is placing a figure of its own.');
  }

  return problems;
};

/**
 * Fill a template's slots from tool output.
 *
 * A slot with no value **refuses** rather than resolving to an empty string or
 * a dash. That is ADR 0010 in the place it matters most: a brief is read once,
 * quickly, by someone who will not check it, and a sentence that reads
 * "throughput was  items" is worse than no brief, because the reader supplies
 * the missing number themselves and is confident about it.
 *
 * Returns `{ text }` or `{ problems }` — never both, and never a partly filled
 * template.
 */
export const fillSlots = (template, values) => {
  const have = values && typeof values === 'object' ? values : {};
  const asked = slotsIn(template);
  const missing = asked.filter(
    (k) => have[k] === undefined || have[k] === null || have[k] === '');

  if (missing.length) {
    return {
      problems: [
        `the brief asks for ${missing.map(q).join(', ')} and the tools did not `
        + 'return it. Nothing was sent: a brief with a figure missing is read '
        + 'as a brief with a figure of zero.'],
    };
  }

  return {
    text: String(template).replace(SLOT, (_, k) => String(have[k])),
  };
};

/**
 * Assemble one section of a brief.
 *
 * The refusal is the reason this function exists rather than being two lines at
 * the call site. When a tool refused, **its sentence is printed and the model's
 * prose is not used at all** — not summarised, not placed underneath, not
 * softened. `CLAUDE.md` requires refusals verbatim and ADR 0007 is why; a model
 * asked to write readably around "too little completion history to sample from"
 * produces something that reads like a wide interval, which is the one thing
 * that sentence exists to deny.
 *
 * So a refused section never reaches the model's output path. The model is
 * still *told* the figure was refused — otherwise it writes "delivery improved"
 * about a section that has no figure — but what it says about it is discarded.
 */
export const section = ({ heading, template, values, prose, refusal }) => {
  if (refusal) {
    return { heading, text: String(refusal), refused: true };
  }

  const bad = proseProblems(prose);
  if (bad.length) return { heading, problems: bad };

  const filled = fillSlots(template, values);
  if (filled.problems) return { heading, problems: filled.problems };

  return { heading, text: `${String(prose).trim()}\n\n${filled.text}`, refused: false };
};

/**
 * The whole brief, or the reason there isn't one.
 *
 * **A brief with a broken section is not sent.** Dropping the section and
 * sending the rest was the obvious alternative and it is the worse one: the
 * reader cannot tell a brief that omitted a section from a brief that had
 * nothing to say about it, and the weekly cadence means nobody goes looking.
 * A brief that does not arrive is noticed; a brief that quietly shrank is not.
 *
 * A section that *refused* is not a broken one — it is the product working, and
 * it is carried.
 */
export const composeBrief = ({ audience, sections }) => {
  const built = (sections || []).map(section);
  const problems = built.flatMap(
    (s) => (s.problems || []).map((p) => `${s.heading}: ${p}`));

  if (problems.length) return { sent: false, problems };

  return {
    sent: true,
    audience,
    refusedSections: built.filter((s) => s.refused).map((s) => s.heading),
    text: built.map((s) => `## ${s.heading}\n\n${s.text}`).join('\n\n'),
  };
};

const unique = (xs) => xs.filter((x, i) => xs.indexOf(x) === i);
const q = (s) => `"${s}"`;

/* ------------------------------------------------------------------------
   Talking to the model, and the two shapes around that call.

   `chat()` itself lives in index.js because it is I/O. What is here is what
   goes in and what comes out — both pure, both wrong in ways a deploy would
   not show, and both therefore tested.
   --------------------------------------------------------------------- */

/**
 * The model the brief is written by.
 *
 * Named here rather than at the call site so `tests/test_service.py` can hold
 * it against the manifest's `llm` module: a model the app has not declared
 * fails inside a tenant, on a timer, with nobody watching.
 *
 * Neither `temperature` nor `top_p` is sent with it. That is not a tuning
 * choice — Atlassian rejects both parameters for this model family, and a
 * request carrying one fails validation rather than being ignored.
 */
export const MODEL = 'claude-opus-5';

/**
 * What the model is asked, as the `messages` array `chat()` takes.
 *
 * The figures go in so the model knows which way things moved. They go in
 * **named**, never as a sentence it could copy — `throughput: 9` rather than
 * "throughput was 9 items" — because a figure it is shown in prose is a figure
 * it will repeat in prose, and `proseProblems` would then refuse every brief
 * this function produced. The instruction and the guard have to want the same
 * thing.
 *
 * A refused figure is named as refused and its sentence is **not** included.
 * The model needs to know the forecast is absent, or it writes around a gap it
 * cannot see; it does not need the wording, and giving it the wording invites
 * the paraphrase ADR 0013 exists to prevent.
 */
export const briefMessages = ({ audience, figures, refused }) => {
  const named = Object.entries(figures || {})
    .map(([k, v]) => `- ${k}: ${JSON.stringify(v)}`)
    .join('\n');
  const absent = (refused || []).length
    ? `\n\nRefused, so say nothing about them and do not write around them as `
      + `though they were bad news — they are unmeasured, not poor:\n`
      + (refused || []).map((r) => `- ${r}`).join('\n')
    : '';

  return [
    {
      role: 'system',
      content:
        `You are writing the ${audience === 'exec' ? 'executive' : 'team'} `
        + 'section of a weekly delivery brief for a software team. '
        + PROSE_RULE
        + ' Be plain and short. Do not open with a greeting, do not close with '
        + 'a recommendation, and do not speculate about causes the figures do '
        + 'not show.',
    },
    {
      role: 'user',
      content: `Figures for this period:\n${named}${absent}`,
    },
  ];
};

/**
 * The prose out of an `LlmResponse`, or nothing.
 *
 * Written defensively on purpose. Every other caller in this app is talking to
 * a service whose shape `tests/test_service.py` pins; this one is talking to a
 * model, on a schedule, with no page to render an error into. A response that
 * arrives truncated — `finish_reason` anything but `stop` — is discarded rather
 * than used, because half a paragraph reads as a whole one and the reader has
 * no way to tell.
 */
export const proseFrom = (response) => {
  const choice = response?.choices?.[0];
  if (!choice) return { problems: ['the model returned no choices'] };
  if (choice.finish_reason && choice.finish_reason !== 'stop') {
    return {
      problems: [
        `the model stopped early (${choice.finish_reason}). A truncated brief `
        + 'reads as a complete one, so it was not used.'],
    };
  }
  const content = choice.message?.content;
  if (typeof content !== 'string' || !content.trim()) {
    return { problems: ['the model returned no text'] };
  }
  return { prose: content.trim() };
};

/**
 * Why a brief is not being sent, as sentences, or an empty array if it can be.
 *
 * Both blockers below are real and neither is a to-do. They are checked before
 * anything is fetched or generated, so a scheduled run that cannot deliver
 * costs one function invocation rather than a board's worth of Jira calls and
 * a model completion nobody receives.
 */
export const deliveryBlockers = ({ recipients, transport, scope }) => {
  const out = [];
  /* Ordered by how early each one stops the run, not by how hard it is to fix.
     Scope comes first because without it there is nothing to compute at all —
     the other two are about where the answer goes. */
  if (!Array.isArray(scope) || !scope.length) {
    out.push(
      'no board is configured for this installation to report on. A scheduled '
      + 'run has no user and no project context, so unlike the panel it cannot '
      + 'infer one from where it was opened.');
  }
  if (!Array.isArray(recipients) || !recipients.length) {
    out.push(
      'no recipients are configured for this installation. Which audience goes '
      + 'to which addresses is not recorded anywhere Jira can be asked for it.');
  }
  if (!transport) {
    out.push(
      'no mail transport is declared, so there is nowhere to send it. Forge has '
      + 'no SMTP and the remote that would carry it does not exist yet.');
  }
  return out;
};
