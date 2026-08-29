#!/usr/bin/env python3
"""
orgconfig.py — the assumptions that differ per organisation.

Four things were baked into the code and are true of exactly one company:
which statuses mean done, which days of the week are worked, which of those
days are holidays, and how long a sprint is. This module is the one place
they are decided, and the resolved config travels **inside the dataset** as
`orgConfig` so that every consumer reads the same answer.

Why it travels in the data rather than sitting in a file each tool reads
----------------------------------------------------------------------
Because the tools and the page must never disagree. `metrics.py` and the
browser's `derive()` already compute the same figures twice, and the suite
asserts they match; a config read separately by each of them would be a third
opinion, arriving by a different route, and the first sign of trouble would be
a facts pack and a dashboard reporting different flow efficiency for the same
sprint. That exact bug shipped once — 25% against 22% — and it was a units
disagreement of precisely this kind.

So: the producer (`fetch_delivery_data.py`, the bundle builders, the import
wizard) resolves the config once and writes it into the file. Everything
downstream reads it from there. A dataset with no `orgConfig` gets DEFAULTS,
which reproduce the behaviour that was hard-coded before this module existed —
adopting it changes no number until someone edits the config.

Units are unchanged and remain the rule
---------------------------------------
Holidays and the working week affect **working days only**: the Monte Carlo
horizon, sprint elapsed-percentage, the burndown's ideal line. Reported
elapsed time stays in **calendar days** — an item raised 21 days ago is 21
days old whether or not the office was shut. Making a holiday shorten an
item's age would be the same lie of convenience as skipping weekends.

    python3 agent/tools/orgconfig.py config/organisation.json     # validate
    python3 agent/tools/orgconfig.py data/sample-bundle.json      # what a file uses
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta

SCHEMA_VERSION = 1

#: The behaviour that was hard-coded before this file existed. A dataset
#: carrying no `orgConfig` resolves to exactly this, so nothing moves.
DEFAULTS = {
    "version": SCHEMA_VERSION,
    "statuses": {
        # Matched case-insensitively against the raw tracker status name.
        "done": ["Done", "Closed", "Resolved", "Complete", "Completed", "Shipped"],
        "inProgress": ["In Progress", "In Review", "Review", "Testing", "Test",
                       "QA", "Doing"],
    },
    "workingWeek": ["mon", "tue", "wed", "thu", "fri"],
    "holidays": [],
    "sprintLengthDays": 14,
    # How many sprints a trend shows — roadmap item 4b. Six was hardcoded in
    # three producers and truncated silently in all of them, which is the
    # thing CLAUDE.md forbids: a chart of the last six sprints of a
    # twenty-sprint board reads as the whole record. It travels inside the
    # dataset like every other assumption here, so the page, the tools and both
    # transports read one resolved answer rather than each keeping a constant.
    "trendSprints": 6,
    # Which issues count as items — roadmap item 7, ADR 0024.
    #
    # **Subtasks are excluded by default**, because a parent and its three
    # subtasks are one piece of work and four rows. Counted, a team that breaks
    # work down finely appears to deliver several times more than one that does
    # not, and every figure denominated in items moves with a habit rather than
    # with delivery. Whether they even arrive depends on the board type and on
    # whether raw JQL was used, so before this the product could not say
    # whether its own counts included them.
    "countSubtasks": False,
    # An allow-list of issue type names, matched case-insensitively. Empty means
    # every type that is not excluded above — which is the right default,
    # because naming the types means naming them per site and a site that adds
    # one would silently stop counting it.
    "countedTypes": [],
}

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_INDEX = {n: i for i, n in enumerate(DAY_NAMES)}
MAX_SPRINT_DAYS = 90
#: The most sprints a trend may ask for. Every one is a sprint's worth of
#: issues fetched, so this is a latency bound rather than a statistical one.
MAX_TREND_SPRINTS = 40

# Used only when a status matches no configured rule and the tracker offered no
# category of its own. Kept because a brand-new status appearing mid-sprint
# should not silently become "To Do" and quietly finish the sprint early — but
# every status that lands here is recorded and named by the caller.
_DONE_RE = re.compile(r"done|closed|resolved|complete|shipped", re.I)
_WIP_RE = re.compile(r"progress|review|test|doing|qa", re.I)


# ----------------------------------------------------------------- resolving
def _norm(s):
    return " ".join(str(s or "").split()).lower()


def merge(base, override):
    """Shallow-merge one level down, which is as deep as this schema goes.

    `statuses` merges key by key, so a config naming only `done` keeps the
    default `inProgress` list rather than emptying it — an empty list would
    mean "no status is in progress", which is a claim nobody intended to make
    by omission.
    """
    out = json.loads(json.dumps(base))
    for k, v in (override or {}).items():
        if k == "statuses" and isinstance(v, dict):
            out["statuses"] = dict(out.get("statuses", {}))
            out["statuses"].update({sk: sv for sk, sv in v.items() if sv is not None})
        elif v is not None:
            out[k] = v
    return out


def from_dataset(ds):
    """The config a dataset was built with, or the defaults if it predates this."""
    return merge(DEFAULTS, (ds or {}).get("orgConfig") or {})


def load(path):
    """Read and validate a config file. Exits with the problems if it is wrong.

    Refusing a bad config is the point. A typo in `workingWeek` that silently
    fell back to a five-day week would move every forecast in the product
    without anything on screen saying so.
    """
    with open(path) as fh:
        raw = json.load(fh)
    cfg = merge(DEFAULTS, raw)
    problems = validate(cfg)
    if problems:
        sys.exit("%s is not a usable organisation config:\n  - %s"
                 % (path, "\n  - ".join(problems)))
    return cfg


def validate(cfg):
    """Every problem with a config, as sentences. Empty list means usable."""
    p = []
    week = cfg.get("workingWeek")
    if not isinstance(week, list) or not week:
        p.append("workingWeek must be a non-empty list of day names")
    else:
        bad = [d for d in week if _norm(d) not in DAY_INDEX]
        if bad:
            p.append("workingWeek contains %s — use %s"
                     % (", ".join(repr(b) for b in bad), "/".join(DAY_NAMES)))

    for key in ("done", "inProgress"):
        v = (cfg.get("statuses") or {}).get(key)
        if not isinstance(v, list):
            p.append("statuses.%s must be a list of status names" % key)
        elif any(not str(x).strip() for x in v):
            p.append("statuses.%s contains an empty name" % key)

    done = {_norm(x) for x in (cfg.get("statuses") or {}).get("done", []) if isinstance(x, str)}
    wip = {_norm(x) for x in (cfg.get("statuses") or {}).get("inProgress", []) if isinstance(x, str)}
    both = sorted(done & wip)
    if both:
        # Silently preferring one list would make "done" mean different things
        # in the burndown and the ageing chart.
        p.append("%s appears in both statuses.done and statuses.inProgress"
                 % ", ".join(repr(b) for b in both))

    hol = cfg.get("holidays")
    if not isinstance(hol, list):
        p.append("holidays must be a list of YYYY-MM-DD dates")
    else:
        for h in hol:
            try:
                date.fromisoformat(str(h))
            except ValueError:
                p.append("holidays contains %r, which is not a YYYY-MM-DD date" % h)

    n = cfg.get("sprintLengthDays")
    if not isinstance(n, int) or isinstance(n, bool) or not (1 <= n <= MAX_SPRINT_DAYS):
        p.append("sprintLengthDays must be a whole number of calendar days "
                 "between 1 and %d" % MAX_SPRINT_DAYS)

    # Two is the floor because a trend needs two points to be a trend, and the
    # ceiling exists because every sprint in the window is a sprint's worth of
    # issues fetched — an unbounded window is a tenant waiting on a page load.
    if not isinstance(cfg.get("countSubtasks"), bool):
        p.append("countSubtasks must be true or false")
    ct = cfg.get("countedTypes")
    if not isinstance(ct, list) or not all(isinstance(x, str) for x in ct):
        p.append("countedTypes must be a list of issue type names, or empty for "
                 "every type")

    t = cfg.get("trendSprints")
    if not isinstance(t, int) or isinstance(t, bool) or not (2 <= t <= MAX_TREND_SPRINTS):
        p.append("trendSprints must be a whole number of sprints between 2 "
                 "and %d" % MAX_TREND_SPRINTS)
    return p


# -------------------------------------------------------------- working days
def weekday_mask(cfg):
    return {DAY_INDEX[_norm(d)] for d in cfg["workingWeek"] if _norm(d) in DAY_INDEX}


def holiday_set(cfg):
    return {str(h)[:10] for h in (cfg.get("holidays") or [])}


def is_working_day(d, cfg):
    """`d` is a date or an ISO string."""
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return d.weekday() in weekday_mask(cfg) and d.isoformat() not in holiday_set(cfg)


def working_days(start, end, cfg):
    """Working dates between two ISO dates or dates, inclusive.

    Returns `date` objects. Callers that write this into a dataset store the
    ISO strings — see `working_days_iso`.
    """
    if isinstance(start, str):
        start = date.fromisoformat(start[:10]) if start else None
    if isinstance(end, str):
        end = date.fromisoformat(end[:10]) if end else None
    if not start or not end or end < start:
        return []
    mask, hol, out, cur = weekday_mask(cfg), holiday_set(cfg), [], start
    while cur <= end:
        if cur.weekday() in mask and cur.isoformat() not in hol:
            out.append(cur)
        cur += timedelta(days=1)
    return out


def working_days_iso(start, end, cfg):
    return [d.isoformat() for d in working_days(start, end, cfg)]


def add_working_days(start, n, cfg):
    """The date `n` working days after `start`, skipping holidays too."""
    if isinstance(start, str):
        start = date.fromisoformat(start[:10])
    mask, hol, cur, left = weekday_mask(cfg), holiday_set(cfg), start, n
    # A config with no working days at all cannot advance; validate() rejects
    # it, but a dataset could still carry one, and looping forever is worse
    # than returning the day it started on.
    if not mask:
        return start
    while left > 0:
        cur += timedelta(days=1)
        if cur.weekday() in mask and cur.isoformat() not in hol:
            left -= 1
    return cur


# ------------------------------------------------------------------ statuses
class Statuses:
    """Maps tracker status names onto To Do / In Progress / Done.

    Records every name that matched no configured rule. A status the config has
    never heard of is the most likely way a customer's numbers go quietly
    wrong — a new "Awaiting sign-off" column reads as To Do, the burndown stops
    moving, and nothing says why. Callers print `unmatched` rather than
    discovering it in a support ticket.
    """

    def __init__(self, cfg):
        st = cfg.get("statuses") or {}
        self.done = {_norm(x) for x in st.get("done", [])}
        self.wip = {_norm(x) for x in st.get("inProgress", [])}
        self._unmatched = {}

    def category(self, name, hint=None):
        n = _norm(name)
        if n and n in self.done:
            return "Done"
        if n and n in self.wip:
            return "In Progress"

        # The tracker's own category is trusted next: Jira sites define one per
        # status, and it is a statement by the site rather than a guess here.
        if hint:
            h = _norm(hint)
            if "done" in h or "complete" in h:
                return "Done"
            if "progress" in h:
                return "In Progress"
            if name:
                self._unmatched[n] = name
            return "To Do"

        if name:
            self._unmatched[n] = name
        if _DONE_RE.search(n):
            return "Done"
        if _WIP_RE.search(n):
            return "In Progress"
        return "To Do"

    @property
    def unmatched(self):
        """Status names no rule covered, in the spelling the tracker used."""
        return sorted(self._unmatched.values())


def is_done(issue, cfg=None):
    """Completion, from the field the producer already resolved.

    Downstream tools read `statusCategory` rather than re-deriving it, because
    the producer applied the config once and re-deriving invites two answers.
    `cfg` is accepted so a caller holding only a raw status can pass one.
    """
    c = issue.get("statusCategory")
    if c:
        return c == "Done"
    return Statuses(cfg or DEFAULTS).category(issue.get("status")) == "Done"


# ------------------------------------------------------------------ printing
def summary(cfg):
    """One line for a basis note, so a figure can name the rules behind it."""
    week = [_norm(d) for d in cfg["workingWeek"] if _norm(d) in DAY_INDEX]
    hol = len(cfg.get("holidays") or [])
    return ("%d-day working week (%s), %d holiday%s, %d-day sprints; done = %s"
            % (len(week), ", ".join(week), hol, "" if hol == 1 else "s",
               cfg.get("sprintLengthDays"),
               ", ".join((cfg.get("statuses") or {}).get("done", [])) or "nothing"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("path", help="an organisation config, or a dataset that carries one")
    a = ap.parse_args()
    with open(a.path) as fh:
        raw = json.load(fh)
    cfg = from_dataset(raw) if "orgConfig" in raw or "issues" in raw else merge(DEFAULTS, raw)
    problems = validate(cfg)
    print(json.dumps(cfg, indent=2))
    print()
    print(summary(cfg))
    if problems:
        print()
        print("Not usable:")
        for p in problems:
            print("  - " + p)
        sys.exit(1)
    if "orgConfig" not in raw and "issues" in raw:
        print("\nThis dataset carries no orgConfig — the defaults above are what it used.")


if __name__ == "__main__":
    main()


# ------------------------------------------------------------- what counts
def counted_issues(issues, cfg=None):
    """The issues that count as items, and what was left out.

    Returns `(kept, excluded)`, where `excluded` is `{reason: count}` — never a
    bare list. Every figure this product reports in items is a count of the
    first, and a count that quietly dropped rows is the silent cap `CLAUDE.md`
    forbids: the reader sees a smaller number and no reason for it.

    Two rules, in this order, and both are the organisation's rather than ours.

    **Subtasks.** A parent and its three subtasks are one piece of work and four
    rows. Counting them makes a team that breaks work down finely look several
    times faster than one that does not, and moves every item-denominated figure
    with a habit rather than with delivery. Excluded unless the config says
    otherwise. ADR 0024.

    **Named types.** An allow-list, empty by default. Naming types means naming
    them per site, and a site that adds one would silently stop counting it —
    so the default counts everything the first rule left.

    `isSubtask` absent is treated as *not* a subtask. Every dataset written
    before this existed carries none, and reading absence as "subtask" would
    empty them.
    """
    cfg = cfg or DEFAULTS
    keep_sub = bool(cfg.get("countSubtasks"))
    named = [str(t).strip().lower() for t in (cfg.get("countedTypes") or [])
             if str(t).strip()]

    kept, excluded = [], {}
    def drop(reason):
        excluded[reason] = excluded.get(reason, 0) + 1

    for i in issues or []:
        if not keep_sub and i.get("isSubtask") is True:
            drop("subtask")
            continue
        if named and str(i.get("type") or "").strip().lower() not in named:
            drop("type not counted")
            continue
        kept.append(i)
    return kept, excluded


def counted_note(excluded, total):
    """What a reader is told about issues that were not counted.

    Silent when nothing was. When something was, it says how many and why —
    because a figure over 40 issues where the board holds 52 is a figure whose
    denominator the reader cannot see.
    """
    gone = sum((excluded or {}).values())
    if not gone:
        return ""
    parts = ", ".join("%d %s" % (n, r) for r, n in sorted((excluded or {}).items()))
    return ("%d of %d issues are not counted as items (%s). A parent and its "
            "subtasks are one piece of work; counting both would report a team "
            "that breaks work down finely as delivering several times more."
            % (gone, total, parts))
