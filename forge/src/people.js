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
