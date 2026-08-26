/**
 * Reading Jira's answer about what this user may do. No Forge, no network.
 *
 * One question is asked: may the person looking at this panel administer this
 * project? It decides whether they can change who receives a board's brief,
 * which is a disclosure control rather than a display preference. ADR 0014.
 *
 * The parsing is here, alone, for one reason: **it has to fail closed**, and a
 * fail-closed check written inline beside the call that uses it is one nobody
 * ever runs the malformed cases through. Every shape Jira might return that is
 * not an unambiguous yes has to end as `false`, and the only way to know that
 * is to try them — `tests/test_service.py` does.
 */

/** The one permission this app asks about. Jira's own key, not a synonym. */
export const ADMIN_PERMISSION = 'ADMINISTER_PROJECTS';

/**
 * Whether the response to
 * `GET /rest/api/3/mypermissions?projectKey=…&permissions=ADMINISTER_PROJECTS`
 * is a yes.
 *
 * `havePermission === true` and nothing else. Not truthy — **exactly** true.
 * Jira returns a boolean, and a string `"false"` is truthy in JavaScript, so a
 * shape change or a proxy that stringifies the body would silently turn every
 * viewer into an administrator. That is the whole reason this is a function
 * with tests rather than a `?.` chain at a call site.
 */
export const canAdminister = (body) => {
  const entry = body?.permissions?.[ADMIN_PERMISSION];
  return entry?.havePermission === true;
};

/**
 * What the panel is told about its own rights, and why.
 *
 * The sentence matters as much as the flag. A viewer who cannot edit is shown
 * the active configuration and told who can change it — hiding it entirely
 * would make a misconfigured board indistinguishable from an unconfigured one,
 * and the person best placed to notice a wrong recipient list is whoever is
 * reading the panel, not the administrator who set it and moved on.
 */
export const editability = (body) => (
  canAdminister(body)
    ? { canEdit: true }
    : {
      canEdit: false,
      why: 'Only a project administrator can change who receives this board’s '
         + 'brief. You can see what is configured; ask an administrator of this '
         + 'project to change it.',
    });
