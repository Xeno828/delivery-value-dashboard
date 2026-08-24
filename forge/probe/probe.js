/**
 * Connection check. Not the product.
 *
 * A successful `forge deploy` proves the manifest is valid and the bundle
 * builds. It proves nothing about permissions, because nothing has called Jira
 * yet. This page makes the three calls that would otherwise stay untested until
 * the first customer install:
 *
 *   1. can a static resource reach a resolver at all
 *   2. can the resolver read boards with the scopes in the manifest
 *   3. can it read issues, and does the projection strip issue text
 *
 * Every value from Jira is written with textContent, never innerHTML. An issue
 * summary is free text that anyone who can raise a ticket controls, and this
 * page renders board names and issue keys straight from a tenant.
 */

import { invoke } from '@forge/bridge';

const $ = (id) => document.getElementById(id);

function verdict(el, state, text) {
  el.className = 'verdict v-' + state;
  el.textContent = text;
}

function show(el, value) {
  const pre = document.createElement('pre');
  pre.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  el.replaceChildren(pre);
}

function note(el, text) {
  const p = document.createElement('div');
  p.className = 'note';
  p.textContent = text;
  el.appendChild(p);
}

/** Outside a Forge iframe there is nothing on the other end of the bridge, and
 *  `invoke` neither resolves nor rejects — it waits. The first version of this
 *  page sat on "checking" indefinitely with no explanation, which is the least
 *  useful thing a diagnostic can do. Fifteen seconds is generous enough for a
 *  cold start and short enough to be an answer. */
const TIMEOUT_MS = 15000;

function withTimeout(promise, name) {
  return Promise.race([
    promise,
    new Promise((_, reject) =>
      setTimeout(
        () => reject(new Error(
          `invoke("${name}") did not answer within ${TIMEOUT_MS / 1000}s. ` +
          'Outside a Forge iframe there is nothing on the other end of the ' +
          'bridge and the call simply waits; inside one, this means the ' +
          'resolver did not respond.')),
        TIMEOUT_MS,
      )),
  ]);
}

/** The resolver's own answer plus the failure, kept apart. A resolver that
 *  threw and a resolver that answered "no" look identical if you only print
 *  one of them, and they need different fixes. */
async function call(name, payload) {
  try {
    return { ok: true, value: await withTimeout(invoke(name, payload), name) };
  } catch (err) {
    return { ok: false, error: String((err && err.message) || err) };
  }
}

async function main() {
  // ---- 1. the bridge -----------------------------------------------------
  const ping = await call('ping', {});
  if (!ping.ok) {
    verdict($('v-bridge'), 'bad', 'no resolver');
    show($('d-bridge'), ping.error);
    note($('d-bridge'),
      'The page could not reach a resolver. Check that manifest.yml points this ' +
      'resource at a module with a resolver function, and that forge deploy succeeded.');
    return;
  }
  verdict($('v-bridge'), 'ok', 'reachable');
  show($('d-bridge'), ping.value);

  // ---- 2. boards ---------------------------------------------------------
  const boards = await call('boards', {});
  if (!boards.ok || boards.value?.available === false) {
    verdict($('v-boards'), 'bad', 'refused');
    show($('d-boards'), boards.error || boards.value);
    note($('d-boards'),
      'A 403 here means read:board-scope:jira-software is missing or was not ' +
      'granted at install. Re-run forge install after a scope change — Jira does ' +
      'not widen an existing consent on its own.');
    return;
  }

  const list = boards.value.boards || [];
  verdict($('v-boards'), list.length ? 'ok' : 'bad',
    list.length + ' board' + (list.length === 1 ? '' : 's'));
  if (!list.length) {
    note($('d-boards'), 'The call succeeded and returned nothing. The scope is fine; ' +
      'this Jira site has no boards the app can see.');
    return;
  }

  const buttons = document.createElement('div');
  list.slice(0, 25).forEach((b) => {
    const button = document.createElement('button');
    button.textContent = b.name + '  #' + b.id;   // textContent: board names are free text
    button.onclick = () => loadBoard(b.id);
    buttons.appendChild(button);
  });
  $('d-boards').replaceChildren(buttons);
  if (list.length > 25) {
    note($('d-boards'), 'Showing 25 of ' + list.length + '. The rest are not hidden by ' +
      'a permission problem, only by this page.');
  }
}

// ---- 3 and 4. issues, and what the projection would send ------------------
async function loadBoard(boardId) {
  verdict($('v-issues'), 'wait', 'loading board ' + boardId);
  $('d-issues').replaceChildren();
  verdict($('v-proj'), 'wait', 'waiting');
  $('d-proj').replaceChildren();

  const got = await call('probeBoardIssues', { boardId });
  if (!got.ok || got.value?.available === false) {
    verdict($('v-issues'), 'bad', 'refused');
    show($('d-issues'), got.error || got.value);
    note($('d-issues'),
      'A 403 here means read:issue-details:jira is missing or was not granted. ' +
      'If boards worked and issues did not, that is the scope pair being wrong ' +
      'rather than the install.');
    return;
  }

  const { total, sample, projected, freeTextFields } = got.value;
  verdict($('v-issues'), 'ok', total + ' issues readable');
  show($('d-issues'), sample);
  note($('d-issues'), 'Keys and dates only — this is what the resolver holds locally, ' +
    'before projection.');

  // The claim the whole architecture rests on, shown rather than asserted.
  const clean = !freeTextFields.length;
  verdict($('v-proj'), clean ? 'ok' : 'bad',
    clean ? 'no issue text in the payload' : 'LEAK: ' + freeTextFields.join(', '));
  show($('d-proj'), projected);
  note($('d-proj'), clean
    ? 'This is the whole payload the calculator would receive for one issue. No ' +
      'summary, no assignee — the resolver re-attaches those by key after the call, ' +
      'from the copy that never left.'
    : 'The projection let a free-text field through. Nothing should be deployed ' +
      'in this state; see CALC_FIELDS in forge/src/index.js.');
}

main().catch((err) => {
  verdict($('v-bridge'), 'bad', 'failed');
  show($('d-bridge'), String((err && err.message) || err));
});
