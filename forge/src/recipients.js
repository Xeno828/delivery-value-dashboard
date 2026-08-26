/**
 * Who a board's brief goes to. No Forge, no network, no storage.
 *
 * The config this validates lives in the app's own key-value store and is
 * edited by project administrators. ADR 0014 has why it is not a Jira project
 * property, why the recipients are Jira identities rather than addresses, and
 * why project admin is the authority.
 *
 * Everything here is a function of a parsed object, so `tests/test_service.py`
 * can run it over the shapes an admin will actually produce — including the
 * wrong ones, which are the point. A recipient list is a disclosure control:
 * the failure that matters is not a crash but a brief quietly reaching someone
 * it should not, or quietly reaching nobody while appearing configured.
 */

/** The two audiences item 3 describes. A board may configure either, or both,
 *  and configuring neither is not a silent no-op — see `problemsFor`. */
export const AUDIENCES = ['exec', 'team'];

/**
 * An Atlassian account id, loosely.
 *
 * Deliberately not a tight pattern. Atlassian has shipped at least three
 * shapes — 24 hex characters, `557058:` with a UUID after it, `712020:` with
 * another — and a regex tuned to the ones that exist today would reject the
 * next one, in a tenant, with a valid config. Loose enough to admit an id and
 * tight enough to catch the two things people actually paste: an email address
 * and a display name.
 */
const ACCOUNT_ID = /^[A-Za-z0-9](?:[A-Za-z0-9:._-]{6,126})[A-Za-z0-9]$/;

/** Anything with an @ in it is an address, whatever else it might be. */
const LOOKS_LIKE_EMAIL = /@/;

/** A Jira issue key: project key, hyphen, number. The anchor, see below. */
const ISSUE_KEY = /^[A-Z][A-Z0-9]{1,9}-[1-9][0-9]{0,9}$/;

/**
 * What is wrong with one board's entry, as sentences. Empty means usable.
 *
 * The rules, and the reason for each:
 *
 * **An audience with no recipients is a refusal, not a send to nobody.** A
 * board that names `exec` and lists no one is a board somebody meant to
 * configure and did not finish. Sending to nobody looks identical to sending
 * successfully, and at a weekly cadence nobody notices for a month.
 *
 * **An email address is refused rather than translated.** `/issue/{key}/notify`
 * has no field for one — `to` takes `users` by accountId, `groups` and
 * `groupIds` and nothing else. An address here cannot work, and the useful
 * thing is to say so rather than to look it up: resolving an address to an
 * account would mean this app deciding that the person at that address is that
 * Jira user, which is an identity claim it has no business making.
 *
 * **An anchor issue is required.** Jira's notify endpoint sends *about* an
 * issue; there is no site-wide send. The anchor is named by the administrator
 * rather than picked from the board, because it does two jobs beyond existing:
 * it is what recipients see the mail threaded against, and its BROWSE
 * permission is what `restrict` filters the recipient list by. Choosing it is
 * a decision about who may receive the brief, so it is not a detail to guess.
 */
export const problemsFor = (boardId, entry) => {
  const at = `board ${boardId}`;
  const out = [];

  if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
    return [`${at}: the entry is not an object, so nothing is configured for it.`];
  }

  const anchor = entry.anchorIssue;
  if (typeof anchor !== 'string' || !ISSUE_KEY.test(anchor)) {
    out.push(
      `${at}: anchorIssue is ${JSON.stringify(anchor ?? null)}, which is not an `
      + 'issue key like ABC-123. Jira sends a notification about an issue and '
      + "has no site-wide send; the anchor is also the issue whose BROWSE "
      + 'permission decides who is allowed to receive this.');
  }

  const named = AUDIENCES.filter((a) => a in entry);
  if (!named.length) {
    out.push(
      `${at}: neither ${AUDIENCES.join(' nor ')} is configured, so this board `
      + 'has an entry that sends nothing. Remove the entry or give it an '
      + 'audience — a board that is listed and silent reads as a board that is '
      + 'covered.');
  }

  for (const audience of named) {
    const who = entry[audience];
    const where = `${at}, ${audience}`;
    if (!who || typeof who !== 'object' || Array.isArray(who)) {
      out.push(`${where}: expected an object with users and/or groups.`);
      continue;
    }

    const users = Array.isArray(who.users) ? who.users : [];
    const groups = Array.isArray(who.groups) ? who.groups : [];

    for (const u of users) {
      if (typeof u !== 'string') {
        out.push(`${where}: ${JSON.stringify(u)} is not an account id.`);
      } else if (LOOKS_LIKE_EMAIL.test(u)) {
        out.push(
          `${where}: "${u}" is an email address. Jira's notify endpoint takes `
          + 'account ids and groups and has no field for an address, so this '
          + 'would never be delivered. Use the account id — this app does not '
          + 'look an address up, because deciding that the person at an address '
          + 'is a given Jira user is not a claim it can make.');
      } else if (!ACCOUNT_ID.test(u)) {
        out.push(
          `${where}: "${u}" is not an account id. A display name is not one `
          + 'either — two people can share it.');
      }
    }

    for (const g of groups) {
      if (typeof g !== 'string' || !g.trim()) {
        out.push(`${where}: ${JSON.stringify(g)} is not a group name.`);
      }
    }

    if (!users.length && !groups.length) {
      out.push(
        `${where}: no users and no groups, so this audience sends to nobody. `
        + 'That is indistinguishable from a send that worked, which is why it '
        + 'is refused rather than skipped.');
    }
  }

  return out;
};

/**
 * What is wrong with the whole config, as sentences. Empty means usable.
 *
 * Every board is reported, not just the first: an admin fixing one line at a
 * time, a week apart, is the cost of stopping at the first problem.
 */
export const problemsIn = (config) => {
  if (!config || typeof config !== 'object' || Array.isArray(config)) {
    return ['the recipient config is not an object, so no board is configured.'];
  }
  const boards = config.boards;
  if (!boards || typeof boards !== 'object' || Array.isArray(boards)) {
    return ['the recipient config has no boards object, so no board is configured.'];
  }
  const ids = Object.keys(boards);
  if (!ids.length) {
    return ['no board has recipients configured, so there is nobody to send to.'];
  }
  return ids.flatMap((id) => problemsFor(id, boards[id]));
};

/**
 * The audiences configured for one board, ready to send, or the reasons there
 * are none.
 *
 * Returns `{ sends: [{ audience, anchorIssue, to }] }` or `{ problems }` —
 * never a partial list. A config with one good audience and one broken one
 * refuses both: the whole entry was written by one person in one sitting, and
 * sending half of what they asked for while saying nothing is the failure this
 * file exists to prevent.
 *
 * `to` is the notify endpoint's own shape, built here so the caller does not
 * assemble it from parts and get `users` wrong in a way only a tenant sees.
 */
export const sendsFor = (config, boardId) => {
  const key = String(boardId);
  const entry = config?.boards?.[key];
  if (entry === undefined) {
    return { problems: [`board ${key} has no recipients configured.`] };
  }

  const problems = problemsFor(key, entry);
  if (problems.length) return { problems };

  return {
    sends: AUDIENCES.filter((a) => a in entry).map((audience) => ({
      audience,
      anchorIssue: entry.anchorIssue,
      to: {
        ...(entry[audience].users?.length
          ? { users: entry[audience].users.map((accountId) => ({ accountId })) }
          : {}),
        ...(entry[audience].groups?.length
          ? { groups: entry[audience].groups.map((name) => ({ name })) }
          : {}),
      },
    })),
  };
};

/**
 * The `restrict` block that goes with every send.
 *
 * Constant rather than configurable, and that is the decision. `BROWSE` on the
 * anchor issue is Jira dropping recipients who may not see it, enforced by the
 * platform instead of asserted by us — the only permission filtering in this
 * product that is not a promise. Making it optional would make it the first
 * thing switched off by someone whose brief did not arrive.
 *
 * It is **partial** and ADR 0014 says so out loud: it filters against the
 * anchor issue, not against every issue the brief names. A reader who may
 * browse the anchor and not some other issue is still told about the other.
 * That gap is roadmap item 5 and it is not closed here.
 */
export const RESTRICT = Object.freeze({ permissions: [{ key: 'BROWSE' }] });

/** The boards a scheduled run should walk: the ones with a usable entry. */
export const boardsIn = (config) => {
  if (problemsIn(config).length) return [];
  return Object.keys(config.boards);
};

/**
 * The body `POST /rest/api/3/issue/{key}/notify` takes.
 *
 * Assembled here rather than at the call site so there is one place that knows
 * the endpoint's shape, and so the `restrict` block cannot be forgotten: a send
 * built by hand that happens to omit it still succeeds, still delivers, and has
 * quietly dropped the only permission filtering in the product. Making it part
 * of the payload rather than an argument means there is no call that can leave
 * it out.
 */
export const notifyPayload = ({ subject, textBody, htmlBody, to }) => ({
  subject,
  textBody,
  htmlBody,
  to,
  restrict: RESTRICT,
});
