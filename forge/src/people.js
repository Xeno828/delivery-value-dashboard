/**
 * Finding a person by name. No Forge, no network.
 *
 * The recipient config holds Jira account ids, because that is all the notify
 * endpoint accepts and because an id is not a contact detail (ADR 0014). That
 * is right and it is unusable: nobody knows their colleagues' account ids, and
 * asking an administrator to paste `712020:5ad8ac88-…` is asking them to get it
 * wrong.
 *
 * So the picker searches by name and stores the id. The distinction from the
 * thing ADR 0014 refuses is worth being precise about, because they look alike:
 *
 *   **Refused:** the app takes an email address and decides which Jira user it
 *   belongs to. That is an identity claim the app has no standing to make.
 *
 *   **This:** a person types a name, Jira returns the accounts it matches, and
 *   *the person* picks one. The identity claim is made by an administrator
 *   looking at a list, which is exactly who should be making it.
 *
 * What this file is for is the projection. `GET /rest/api/3/user/search`
 * returns **`emailAddress`** among other things, and the config must never hold
 * one — the same rule, and the same reason, as the calculator's `clean_dataset`.
 */

/** Shown at once. A picker that silently shows the first ten of forty matches
 *  invites picking the wrong Mitch, so the count that was dropped is returned
 *  beside the list and the caller says so. No silent caps. */
export const MAX_MATCHES = 10;

/**
 * Only what the picker needs. Deliberately an allow-list of two fields.
 *
 * `emailAddress` is in the raw response and is the reason this is a projection
 * rather than a `map`. A deny-list here would be one edit away from leaking
 * whatever Atlassian adds next; an allow-list cannot.
 */
const person = (u) => ({ accountId: u.accountId, displayName: u.displayName });

/**
 * The people a search matched, or the reason there are none.
 *
 * Filters to real, active humans:
 *
 * - **inactive accounts** — a deactivated colleague is a recipient who will
 *   never read it, and a brief that silently goes nowhere is the failure
 *   `recipients.js` already refuses an empty audience for.
 * - **`accountType` other than `atlassian`** — app users and customer accounts
 *   are not people who read a delivery brief. App users especially: this app's
 *   own account would otherwise be offered as a recipient of its own brief.
 */
export const peopleFrom = (raw) => {
  if (!Array.isArray(raw)) {
    return { problems: ['Jira did not return a list of people.'] };
  }

  const usable = raw.filter(
    (u) => u && typeof u.accountId === 'string'
      && typeof u.displayName === 'string' && u.displayName.trim()
      && u.active === true
      && (u.accountType === undefined || u.accountType === 'atlassian'));

  const people = usable.slice(0, MAX_MATCHES).map(person);

  return {
    people,
    // What was left out, so the caller can say it rather than imply a complete
    // list. `raw.length` and not `usable.length`: a search that matched thirty
    // accounts of which twenty are deactivated has still been narrowed, and the
    // person typing deserves to know their search was too broad.
    matched: raw.length,
    // Counted from the list itself, never computed alongside it. Written as
    // `Math.min(usable.length, MAX_MATCHES)` this agreed with the list only as
    // long as the slice above matched the arithmetic here — two expressions of
    // one fact, and removing the cap left the count still claiming ten while
    // sixteen were returned. A figure that describes a list is read off the
    // list.
    shown: people.length,
  };
};

/**
 * What the picker says above the list.
 *
 * A sentence rather than a count, because "10 of 34" reads as a page of results
 * and this is not paginated — the answer to too many matches is a better
 * search, and saying so is more useful than offering a next page that does not
 * exist.
 */
export const matchNote = ({ people, matched, shown }) => {
  if (!people.length) {
    return matched
      ? 'No active people matched. Deactivated accounts and app users are not '
        + 'offered — a brief sent to one goes nowhere.'
      : 'Nobody matched that name.';
  }
  if (shown < matched) {
    return `Showing ${shown} of ${matched} matches. Type more of the name to `
         + 'narrow it — there is no second page.';
  }
  return shown === 1 ? 'One match.' : `${shown} matches.`;
};

/* ---------------------------------------------------------------------------
   Reading back the ids that are already stored.
   ---------------------------------------------------------------------------

   The search above solves half the problem: nobody has to *know* an account id
   to add one. The other half is that the field then shows
   `712020:5ad8ac88-…, 60ad2eb506bf0c006a432a17` to the next administrator who
   opens the tile, which is a recipient list nobody can check. A disclosure
   control that cannot be read is a disclosure control that does not work.

   So the stored ids are resolved back to names. `GET /rest/api/3/user/bulk`
   answers the whole list in one request under `read:jira-user`, which is
   already granted for the search — no new scope, no reinstall.

   Two things make this projection different from the one above, and both are
   deliberate.

   **`active` is kept, and an inactive account is not filtered out.** The search
   drops deactivated people because adding one is a mistake being made now. Here
   the mistake was made months ago and is sitting in the config sending nothing.
   Hiding the row would leave the reader looking at a list of names that appears
   complete and correct; the deactivated recipient is the single most useful
   thing this route can tell them.

   **An id that resolves to nothing is reported, not dropped.** `user/bulk`
   simply omits ids it cannot match — a deleted account, or an id copied from a
   different site. Silently returning four names for five ids is the shape of
   bug this repository is most afraid of: a plausible answer that is wrong. The
   ids that came back with nothing are returned by id, so the tile can show
   which one it was.
   --------------------------------------------------------------------------- */

/** Resolved in one call. Beyond this the answer is a group, not a longer list;
 *  `idsToAsk` reports the remainder rather than trimming it out of sight. */
export const MAX_NAMES = 50;

/**
 * The ids one request will ask about, and how many were left over.
 *
 * Deduplicated first, because the field is free text and a list typed by hand
 * repeats an id sooner or later; asking twice would render the same person
 * twice and read as two recipients.
 */
export const idsToAsk = (ids) => {
  const unique = [...new Set((Array.isArray(ids) ? ids : [])
    .filter((x) => typeof x === 'string' && x.trim()))];
  const ask = unique.slice(0, MAX_NAMES);
  // Read off the two lists rather than computed from MAX_NAMES. The count and
  // the slice are then one fact, not two expressions that agree until somebody
  // changes the cap — which is exactly how `shown` went wrong above.
  return { ask, over: unique.length - ask.length };
};

/**
 * Only what the tile needs to render one row. An allow-list of three fields,
 * for the same reason as `person` above: `emailAddress`, `avatarUrls`,
 * `timeZone` and `locale` are all in the raw response and none of them belongs
 * here.
 *
 * `state` rather than `active`, because there are three answers and not two. An
 * id that resolved to a deactivated account and an id that resolved to nothing
 * are different facts with different fixes — reactivate the person, or delete
 * the line — and collapsing them into one falsy flag is how this repository
 * came to print "no sprint calendar" for three unrelated causes.
 */
const namedPerson = (id, u) => {
  if (!u) return { accountId: id, displayName: '', state: 'unknown' };
  return {
    accountId: id,
    displayName: typeof u.displayName === 'string' ? u.displayName.trim() : '',
    state: u.active === true ? 'active' : 'deactivated',
  };
};

/**
 * One row per id asked about, in the order they were asked about.
 *
 * Asked-for order, and *every* id gets a row: the tile renders this beside a
 * field holding the same ids in the same sequence, so a reader checking one
 * against the other reads straight down. Returning only the ids that resolved
 * would leave four names against five ids and no way to tell which one was
 * missing — a list that looks complete and is not, which is the failure mode
 * this codebase pays for most often.
 *
 * `user/bulk` omits the ids it cannot match rather than reporting them, so the
 * unmatched ones are recovered here by asking what came back for each id
 * instead of reading the response as the answer.
 */
export const namesFrom = (raw, asked) => {
  if (!Array.isArray(raw)) {
    return { problems: ['Jira did not return a list of people.'] };
  }
  const want = Array.isArray(asked) ? asked : [];
  const byId = new Map(raw
    .filter((u) => u && typeof u.accountId === 'string')
    .map((u) => [u.accountId, u]));

  return { people: want.map((id) => namedPerson(id, byId.get(id))) };
};

/**
 * What the tile says above the names.
 *
 * Silent when there is nothing wrong. The names are listed directly below, so
 * "3 recipients, named" over three visible names is noise; this speaks only for
 * the states a reader cannot see by looking — an account that will never
 * receive anything, an id that names nobody, and ids that were not looked up.
 *
 * Every count is read off the list it describes, never computed beside it.
 */
export const nameNote = ({ people }, over = 0) => {
  const out = [];
  const gone = people.filter((p) => p.state === 'deactivated').length;
  const unknown = people.filter((p) => p.state === 'unknown').length;

  if (gone) {
    out.push(gone === 1
      ? 'One of these accounts is deactivated, so the brief reaches nobody there.'
      : `${gone} of these accounts are deactivated, so the brief reaches nobody `
        + 'at them.');
  }
  if (unknown) {
    out.push(unknown === 1
      ? 'One id matches no account on this site — deleted, or copied from a '
        + 'different site. Nothing will be delivered to it.'
      : `${unknown} ids match no account on this site — deleted, or copied from `
        + 'a different site. Nothing will be delivered to them.');
  }
  if (over) {
    out.push(over === 1
      ? `One further id was not looked up; only the first ${MAX_NAMES} are named.`
      : `${over} further ids were not looked up; only the first ${MAX_NAMES} are `
        + 'named.');
  }
  return out.join(' ');
};
