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
 *   3. can it read issues, which field this site calls story points, and does
 *      the projection strip issue text
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

  // ---- 2. the board read is wired to the form, not run on load --------
  $('f-board').addEventListener('submit', (e) => {
    e.preventDefault();
    const id = $('board').value.trim();
    if (id) loadBoard(id);
  });
  $('board').focus();
}

// ---- 2 and 3. the board read, and what the projection would send ----------
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
      'A 403 means read:issue-details:jira or read:board-scope:jira-software was ' +
      'not granted. After changing scopes, re-run forge install — Jira does not ' +
      'widen an existing consent on its own. A 404 means the board id is wrong.');
    return;
  }

  const { total, sample, projected, freeTextFields,
          storyPointField, storyPointFieldNote } = got.value;
  verdict($('v-issues'), 'ok', total + ' issues readable');
  show($('d-issues'), sample);
  note($('d-issues'), 'Keys and dates only — this is what the resolver holds locally, ' +
    'before projection.');

  // Which field this site calls story points, resolved by display name rather
  // than assumed. Shown because the failure it prevents is invisible: an id
  // that is wrong for this site reads every issue as zero points, flattens the
  // burndown in points mode, and says nothing.
  note($('d-issues'), storyPointFieldNote);
  if (!storyPointField) {
    note($('d-issues'), 'Items are unaffected — that is the default unit on the page ' +
      'and the only one the forecaster reads. Rename the field to Story Points, ' +
      'Story point estimate or Points, or add the name to STORY_POINT_FIELD_NAMES ' +
      'in forge/src/jira.js and scripts/fetch_delivery_data.py together.');
  }

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
