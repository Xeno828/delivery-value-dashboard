/**
 * The brief as an email. No Forge, no network, no model.
 *
 * Jira's notify endpoint carries `subject`, `textBody` and `htmlBody` and no
 * attachment, so this is what item 3 actually delivers: the figures and the
 * written brief as static HTML in the message. ADR 0014 has why that trade was
 * taken and what it costs.
 *
 * Two things make this file worth reading rather than skimming.
 *
 * **It is a new output surface for issue text.** A Jira summary is writable by
 * anyone who can raise a ticket, and until now every one of them went to a page
 * this repository controls. These land in a mail client, in someone's inbox,
 * rendered by software nobody here chose. A stored XSS already shipped once in
 * this product, from two call sites interpolating `i.key` and `i.summary`
 * directly, and the rule that came out of it is the rule here: **escape at
 * output, once**, at the point of output, with no string reaching the template
 * un-escaped and none escaped twice.
 *
 * **It computes nothing.** Same rule as the agent, the service and the
 * resolver: every figure arrives already decided and this only places it.
 * There is no arithmetic below, not even a percentage.
 */

/**
 * The one escape, and every issue-derived string goes through it here.
 *
 * Character-for-character what `src/app.js` uses. A second escaper that handles
 * four of the five characters is the shape this class of bug arrives in, so the
 * set is identical and `tests/test_service.py` compares the two.
 */
export const esc = (s) => String(s == null ? '' : s).replace(
  /[&<>"']/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]),
);

/** Only http(s) survives, and only to be rendered as an attribute value that
 *  `esc` has already been through. `javascript:` in an issue's tracker URL is
 *  the same attack as a summary full of markup, wearing a different hat. */
export const safeUrl = (u) => {
  const t = String(u ?? '').trim();
  return /^https?:\/\//i.test(t) ? t : null;
};

/**
 * A subject line, flattened to one line and bounded.
 *
 * The subject is a mail *header*, and a header ends at a newline. A board name
 * is customer text — an issue summary is writable by anyone who can raise a
 * ticket, and a board name by anyone who can make a board — so a `\n` in one
 * would end the Subject header and begin whatever came next. That is header
 * injection, and it is a different bug from the HTML escaping below: escaping
 * would render `&#10;` harmless in a body and does nothing to a header.
 *
 * Jira very likely strips this too. That is not a reason to pass it on: the
 * repository's rule is that issue-derived text is made safe at the point it
 * leaves, by us, once.
 *
 * The cap is stated rather than silent, because a truncated subject reads as a
 * complete one — the same rule as everywhere else here.
 */
const SUBJECT_MAX = 200;
const oneLine = (s) => {
  const flat = String(s).replace(/[\r\n\u2028\u2029\t]+/g, ' ')
    // Other C0 controls have no business in a header either, and a bare CR is
    // not the only one a client will act on.
    .replace(/[\u0000-\u001f\u007f]/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
  return flat.length > SUBJECT_MAX ? `${flat.slice(0, SUBJECT_MAX - 1)}…` : flat;
};

/**
 * Plain text for `textBody`.
 *
 * Sent alongside the HTML rather than instead of it, because a client that
 * refuses HTML should get the brief rather than an empty message — and because
 * a reader forwarding one to somebody without the app is the case the whole
 * artifact argument is about. **Not escaped**: this is text, and `&amp;` in a
 * plain-text part is a bug, not a precaution. Nothing here reaches a parser.
 */
const asText = ({ title, subtitle, sections, footer }) => [
  title,
  subtitle,
  '',
  ...sections.flatMap((s) => [
    s.heading.toUpperCase(),
    s.text,
    '',
  ]),
  '—',
  footer,
].join('\n');

/* Inline styles only, and no <style> block: mail clients strip those, and the
   ones that do not disagree about which. Colours are stated rather than
   inherited for the same reason — a body with no background of its own is at
   the mercy of whatever the client paints behind it, which is the same reason
   the artifact pages set theirs explicitly. */
const S = {
  wrap: 'margin:0;padding:24px;background:#f6f8f7;'
      + "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;"
      + 'color:#101715;line-height:1.55;',
  card: 'max-width:640px;margin:0 auto;background:#ffffff;border:1px solid #dce4e0;'
      + 'border-radius:10px;padding:24px;',
  h1: 'margin:0 0 4px;font-size:20px;line-height:1.25;color:#101715;',
  sub: 'margin:0 0 20px;font-size:13px;color:#57635e;',
  h2: 'margin:22px 0 8px;font-size:15px;color:#0b4741;',
  p: 'margin:0 0 10px;font-size:14px;color:#33403b;',
  /* A refusal is a statement, not an error, and it must not read as one. Set
     apart so a reader can see it was answered rather than missed — the same
     reason the dashboard gives refusals their own treatment instead of an
     empty tile. */
  refusal: 'margin:0 0 10px;padding:10px 12px;background:#f7ebdc;'
         + 'border-left:3px solid #8a4b08;font-size:14px;color:#33403b;',
  foot: 'margin:20px 0 0;padding-top:14px;border-top:1px solid #e9eeeb;'
      + 'font-size:12px;color:#57635e;',
  link: 'color:#0f5d57;',
};

/**
 * One audience's brief, ready for `POST /issue/{key}/notify`.
 *
 * Takes what `composeBrief` produced and what the tools said about the context;
 * returns `{ subject, textBody, htmlBody }`. Every caller-supplied string is
 * escaped here and nowhere else.
 *
 * `boardUrl` is optional and dropped rather than rendered if it is not http(s).
 * A brief that quietly loses its link is better than one carrying a `javascript:`
 * href into an inbox.
 */
export const emailBody = ({
  audience, boardName, periodName, sections, calendar, boardUrl, asOf,
}) => {
  const who = audience === 'exec' ? 'Executive' : 'Team';
  const board = boardName || 'this board';
  const period = periodName || '';

  const title = `${who} delivery brief — ${board}`;
  const subtitle = [period, asOf ? `as at ${asOf}` : ''].filter(Boolean).join(' · ');
  const footer = calendar
    || 'the working calendar for these figures was not stated';

  const url = safeUrl(boardUrl);
  const rows = (sections || []).map((s) => ({
    heading: String(s.heading ?? ''),
    text: String(s.text ?? ''),
    refused: s.refused === true,
  }));

  const html = [
    `<div style="${S.wrap}">`,
    `<div style="${S.card}">`,
    `<h1 style="${S.h1}">${esc(title)}</h1>`,
    subtitle ? `<p style="${S.sub}">${esc(subtitle)}</p>` : '',
    ...rows.flatMap((s) => [
      `<h2 style="${S.h2}">${esc(s.heading)}</h2>`,
      /* Paragraph breaks are the only structure carried over from the composed
         text. The model writes prose and the slots hold figures; neither is
         markup, and treating either as markup is how issue text would get a
         second chance at being parsed. */
      ...s.text.split(/\n{2,}/).filter((para) => para.trim()).map(
        (para) => `<p style="${s.refused ? S.refusal : S.p}">${esc(para.trim())}</p>`),
    ]),
    `<p style="${S.foot}">`,
    esc(footer),
    url ? `<br><a href="${esc(url)}" style="${S.link}">Open the board in Jira</a>` : '',
    '</p>',
    '</div>',
    '</div>',
  ].filter(Boolean).join('');

  return {
    subject: oneLine(title + (period ? ` (${period})` : '')),
    textBody: asText({ title, subtitle, sections: rows, footer }),
    htmlBody: html,
  };
};
