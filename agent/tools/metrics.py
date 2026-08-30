#!/usr/bin/env python3
"""
metrics.py — the deterministic facts pack.

Everything the reporting agent is allowed to state as fact comes from here.
The agent does not add, subtract, average or estimate. It reads this JSON and
writes prose. That division is the entire trust model: if a number in a report
is wrong, it is wrong in this file and can be fixed here, once, for everyone.

It intentionally duplicates the dashboard's browser-side `derive()`. Two
implementations of the same arithmetic is a liability, so `tests/test_agent.py`
asserts they agree on the sample dataset. If they ever diverge, that test fails
before a report does.

Adds one thing the dashboard cannot: a **diff against the previous snapshot**,
which is what a report is actually about. A dashboard shows a state; a report
has to say what changed since the last one and whether that is good.

    python3 agent/tools/metrics.py data/sample-sprint.json
    python3 agent/tools/metrics.py data/x.json --previous snapshots/2026-08-07.json
"""

from __future__ import annotations

import argparse
import datetime
import json
from collections import defaultdict
from datetime import date, timedelta

import orgconfig as OC


# ------------------------------------------------------------------- helpers
def _d(s):
    return date.fromisoformat(s[:10]) if s else None


def working_days(a, b, cfg=None):
    """Working dates, per the organisation config the dataset carries.

    `cfg=None` is a five-day week with no holidays, which is what was written
    here before the config existed — a file predating it computes as before.
    """
    return OC.working_days(a, b, cfg or OC.DEFAULTS)


def elapsed_days(a, b):
    """CALENDAR days between two dates.

    Deliberately calendar, not working, days — and the rule is worth stating
    because the two tools here use different units on purpose:

      * Anything reported to a human as "how long has this been sitting" is in
        calendar days. An item raised 21 days ago is 21 days old; telling a
        stakeholder it is 15 days old because of weekends is a lie of
        convenience, and it is what the dashboard shows.
      * Anything *simulated* — the Monte Carlo in forecast.py — runs on working
        days, because no work completes on a Saturday. Those outputs are always
        labelled "working days".

    Mixing them silently is how two tools built from one dataset end up
    disagreeing in a meeting. Every figure the agent emits must carry its unit.
    """
    return max((_d(b) - _d(a)).days, 0) if a and b else None


def pct(n, d):
    return round(n / d, 4) if d else 0.0


def _pctile(vals, p):
    if not vals:
        return None
    v = sorted(vals)
    k = (len(v) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (k - lo), 2)


def is_done(i):
    return (i.get("statusCategory") or "") == "Done"


def in_sprint(i, start):
    """Is this issue part of the period being reported on?

    Reporting scope and forecasting scope are NOT the same set, and conflating
    them is a real error rather than a rounding one. The facts pack must count
    only the current period, or "89% complete" appears on a report about a
    sprint that is 55% complete. The forecaster must see everything, because a
    throughput distribution needs months of history to exist at all.

    Rule: an issue belongs to the period unless it was already finished before
    the period began. Anything still open, or closed during it, is in scope.
    """
    if not start:
        return True
    r = i.get("resolved")
    return not (r and _d(r) < _d(start))


# --------------------------------------------------------------------- facts
def history_row(issues, sprint_name, as_of, cfg=None):
    """One sprint's row of the trend series, as it stood at `as_of`.

    **Every count here is a statement about a moment, and the moment is
    `as_of` — not the moment this ran.** That distinction is the whole reason
    this function exists, and getting it wrong produced numbers that looked
    right and flattered the team more the older the sprint was.

    The bundle path used to read each closed sprint's row off *current* issue
    status: `statusCategory == "Done"` for completion and `== "In Progress"`
    for work in progress. Both are true of the fetch, not of the sprint. Three
    months after Sprint 23 closed, nothing in it is in progress and everything
    anyone ever finished is done — so it reported **zero WIP and a commitment
    met in full**, and the further back you looked the better the team got.
    A predictability chart is a claim about what was true when the sprint
    ended; answering it with today's status is the plausible-wrong-number
    failure this repository is most afraid of, because nothing about the output
    looks wrong.

    Every field below is therefore derived from a *date* rather than a status:

    - **completed** — resolved on or before `as_of`. An issue carried into the
      next sprint and finished there belongs to the sprint that finished it.
    - **work in progress** — started on or before `as_of` and not resolved by
      then. This is the one figure that cannot be recovered later from Jira at
      all once the issue moves on, which is what makes a stored series worth
      having rather than a re-derivation.
    - **committed** and **unplanned** — from `addedMidSprint`, which the puller
      reads out of the changelog. Those two are properties of the record and do
      not move, so they re-derive correctly at any distance.

    `started` is absent on an issue that never entered an In Progress status,
    and absent is not zero: it was never work in progress, so it is not counted
    as such.

    **It lives here, in a tool, and not in the fetcher, because the fetcher is
    not the only producer any more.** A Forge tenant has no Python; its rows
    have to come from the hosted calculator, and the calculator ships
    `agent/tools/` and nothing else. Putting this in `scripts/` would have
    meant the resolver computing a row itself, which is the one thing
    `CLAUDE.md` says nothing between a tool and a reader may do. The fetcher and
    both bundle generators import it from here.

    One caveat this cannot fix and a caller should know: `started` is not a
    field Jira keeps. Whatever produced these issues recovered it by replaying a
    changelog through *its* idea of which statuses mean In Progress. Change that
    idea and every row this function has ever produced moves. ADR 0015.
    """
    # ISO dates compare correctly as strings, which is the comparison used
    # throughout the tools; `d()` has already normalised every one of these.
    def resolved_by(i):
        r = i.get("resolved")
        return bool(r and r <= as_of)

    def started_by(i):
        st = i.get("started")
        return bool(st and st <= as_of)

    done = [i for i in issues if resolved_by(i)]
    planned = [i for i in issues if not i.get("addedMidSprint")]
    wip = [i for i in issues if started_by(i) and not resolved_by(i)]

    lead = [(date.fromisoformat(i["resolved"]) - date.fromisoformat(i["created"])).days
            for i in done if i.get("resolved") and i.get("created")]
    cyc = [(date.fromisoformat(i["resolved"]) - date.fromisoformat(i["started"])).days
           for i in done if i.get("resolved") and i.get("started")]
    tot_lead, tot_cyc = sum(lead), sum(cyc)

    return {
        "sprint": sprint_name,
        "committedSP": round(sum(i["storyPoints"] for i in planned), 1),
        "completedSP": round(sum(i["storyPoints"] for i in done), 1),
        "committedItems": len(planned),
        "completedItems": len(done),
        "throughput": len(done),
        # Work in progress and interruption, both from issue status and dates.
        # No hours field: the organisation does not operate overtime, and
        # carrying one would imply a time-tracking regime that does not exist.
        "wipItems": len(wip),
        "unplannedItems": len([i for i in issues if i.get("addedMidSprint")]),
        # Calendar days on both sides of the ratio, so the unit cancels. Stated
        # because a working-day cycle over a calendar-day lead is the shape of
        # the 25%-versus-22% disagreement that shipped once.
        "flowEfficiency": round(tot_cyc / tot_lead, 2) if tot_lead else None,
        # Absent, not nil. Jira has no native value field, so a payload that
        # never carried one — every Forge tenant's — would otherwise report
        # every sprint as having delivered nothing of value, which is a much
        # stronger claim than "nobody told us". A set where the field is
        # present and sums to zero keeps its zero.
        # Through `value_of`, which applies the hierarchy rule — a parent epic
        # and its stories are one piece of value and several rows. ADR 0025.
        "valueDelivered": (round(sum(OC.value_of(i, cfg) for i in done), 0)
                           if any("businessValue" in i for i in issues) else None),
    }


def history_series(contexts, issues):
    """One row per sprint context, in the order the board runs them.

    The loop lives here rather than in whatever calls it, for the same reason
    `slice_for` does: a caller that grouped issues by context itself would be a
    second opinion about which issues belong to which sprint, and every failure
    of that opinion is a plausible row rather than an error.

    Only sprint contexts. A flow board's windows overlap completely — 14, 30 and
    90 days of the same board — so a "history" over them would count the same
    issue three times and draw a trend out of one. ADR 0011: a window is not a
    clock, and it is not a sprint either.

    Returns the context id beside each row rather than a bare list, because the
    caller has to line these up against a store keyed by sprint and a positional
    match would silently slip the day a board gains a sprint.

    **Ordered oldest first, here, rather than trusting the caller's order.** A
    series is a chart's x-axis and `series_upto` truncates by position, so the
    order is load-bearing twice over — and the two callers disagreed about it.
    A bundle lists a board's sprints oldest first; the Forge resolver gets them
    from `recentSprints`, which sorts newest first so the picker offers the
    current sprint at the top. Under the caller's order, selecting the newest
    sprint on Forge truncated the series to one row and the tile said *"needs at
    least two sprints of history"* on a board with plenty, while the same board
    over loopback drew six. That is a page behaving differently depending on how
    it was reached, which is the thing ADR 0009 exists to prevent.

    Sorted by start date, falling back to the as-of — a context that carries
    neither sorts last rather than first, because an undated row at the head of
    a trend silently shifts every point after it.
    """
    def when(c):
        return (c.get("startDate") or c.get("endDate") or c.get("asOfDate") or "9999-12-31")

    out, skipped = [], []
    for c in sorted(contexts or [], key=when):
        cid = c.get("id")
        if (c.get("kind") or "sprint") != "sprint":
            skipped.append({"contextId": cid, "sprintName": c.get("sprintName"),
                            "why": "it is a window rather than a sprint, and a "
                                   "window is not a point on a trend"})
            continue
        if not cid:
            skipped.append({"contextId": None, "sprintName": c.get("sprintName"),
                            "why": "it has no id, so nothing could be lined up "
                                   "against it"})
            continue
        mine = [i for i in issues or [] if i.get("contextId") == cid]
        as_of = c.get("asOfDate") or c.get("endDate")
        if not as_of:
            # No moment to be a statement about, so no row — and **named**, not
            # dropped. This said "countable by the caller" and nothing counted
            # it, which is the silent cap CLAUDE.md forbids: a sprint with no
            # end date vanished from the series and the tile reported thin data
            # on a board that had plenty. Dating it to today instead would
            # report a closed sprint's figures as of now, which is the 1.36.0
            # bug re-entered by a different door.
            skipped.append({
                "contextId": cid, "sprintName": c.get("sprintName"),
                "why": "it has no end date and no as-of date, so there is no "
                       "moment its figures would be about"})
            continue
        out.append({
            "contextId": cid,
            # Carried so `series_upto` can narrow to one board without parsing
            # an id. `selection.py` identifies a board the same way, off the
            # context rather than out of the string.
            "boardId": c.get("boardId"),
            "sprintState": c.get("sprintState"),
            # The moment the row is a statement about, returned rather than left
            # for the caller to recover from the contexts it sent. A caller that
            # re-derived it would be free to derive a different one, and "this
            # row is that Wednesday" is the whole claim a mid-flight row makes.
            "asOf": as_of,
            # How wide the view that produced this row was. A row is a fact
            # about the *board* (ADR 0019), so a row computed by somebody who
            # could see ten of a sprint's forty issues is not one — and nothing
            # else in the row says which it is, because every figure in it is
            # smaller in exactly the same way. A count, like everything else
            # here; it names no issue.
            "issuesSeen": len(mine),
            "row": history_row(mine, c.get("sprintName") or cid, as_of),
        })
    return {"rows": out, "skipped": skipped}



# --------------------------------------------------------- the durable series
#
# ADR 0015. A history row re-derives from Jira at any distance, so this is not a
# cache; rows are recorded because four things can make a later re-derivation
# disagree with what was true and none of them announces itself.
#
# The merge, the disagreements and the note live here rather than in the caller
# for the reason every figure in this repository lives in a tool: the note
# states counts a reader reads — *"2 of these 3 sprints were rebuilt"* — and a
# count computed between a tool and a reader is a second implementation waiting
# to disagree with the first. `forge/src/series.js` decides what is *kept*;
# this decides what is *shown*.

#: Fields a stored row carries. An allow-list, not a filter for size: this row
#: is derived from issues, and a deny-list is one upstream change away from
#: putting an issue summary into an app's store. Mirrored in series.js, and
#: `tests/test_service.py` holds the two lists together.
ROW_FIELDS = ("sprint", "committedSP", "completedSP", "committedItems",
              "completedItems", "throughput", "wipItems", "unplannedItems",
              "flowEfficiency", "valueDelivered")

#: Compared when a recorded row meets a re-derived one. Every one of these is
#: supposed to re-derive identically, so a difference is never noise.
_COMPARED = tuple(f for f in ROW_FIELDS if f != "sprint")

#: The two the derivation is entitled to leave absent. `flowEfficiency` when
#: there is no lead time to divide by; `valueDelivered` when nothing carried a
#: business value at all, which is every Forge tenant — Jira has no such field.
#: Zero there would claim the sprint delivered nothing worth anything.
_NULLABLE = ("flowEfficiency", "valueDelivered")


def series_disagreements(recorded, reconstructed):
    """Fields on which a recorded row and a re-derivation differ.

    Which field moved says a great deal about why. Commitment falling is a
    stripped sprint membership or a deleted issue; work in progress moving with
    commitment unchanged is a status recategorised underneath it.

    `flowEfficiency` carries a tolerance because it is a rounded ratio and two
    roundings of one quantity differ in the last place. Nothing else does:
    these are counts, and a count off by one is off by one.
    """
    out = []
    if not recorded or not reconstructed:
        return out
    for f in _COMPARED:
        a, b = recorded.get(f, "\0"), reconstructed.get(f, "\0")
        if a == "\0" or b == "\0":
            continue
        if f in _NULLABLE:
            if (a is None) != (b is None):
                out.append({"field": f, "recorded": a, "reconstructed": b})
            elif a is None:
                continue            # two refusals to state one figure agree
            elif f == "flowEfficiency":
                if abs(a - b) > 0.011:
                    out.append({"field": f, "recorded": a, "reconstructed": b})
            elif a != b:
                out.append({"field": f, "recorded": a, "reconstructed": b})
            continue
        if a != b:
            out.append({"field": f, "recorded": a, "reconstructed": b})
    return out


def merge_series(stored, computed, today_statuses=None):
    """One series, with each row saying which kind of evidence it is.

    `computed` arrives in the order the board runs its sprints and that order is
    kept, because it is a chart's x-axis. A recorded row *substitutes* at the
    same position; it never appends and never reorders, so a series with one
    recorded sprint in the middle is still one series.

    A recorded sprint that the board no longer offers is dropped and counted,
    not spliced back in at a guessed position — a point on a chart at a date
    nothing else agrees with is worse than a point that is missing and named.
    """
    sprints = (stored or {}).get("sprints") or {}
    rows, seen = [], set()
    # The oldest moment the caller actually looked at. Anything recorded before
    # it was not asked for, which is a different fact from a sprint the board no
    # longer offers — see the split below.
    asked_from = min((str(i.get("asOf")) for i in (computed or [])
                      if i.get("asOf")), default=None)
    for item in computed or []:
        sid = str(item.get("sprintId") if item.get("sprintId") is not None
                  else item.get("contextId"))
        raw = item.get("row") or {}
        seen.add(sid)
        kept = sprints.get(sid)
        if not kept or not kept.get("row"):
            rows.append(dict(raw, source="reconstructed"))
            continue
        row = dict(kept["row"])
        row["source"] = "recorded"
        row["observedOn"] = kept.get("observedOn")
        # On the row and not only in the note, because a chart may show one
        # sprint at a time and the note sits above all of them.
        row["atSprintEnd"] = kept.get("final") is True
        row["differs"] = [d["field"] for d in series_disagreements(kept["row"], raw)]
        # Computed under a different idea of "in progress" than today's. Not an
        # error and not a disagreement — it is what makes a difference in
        # wipItems explicable rather than alarming.
        row["statusesMoved"] = bool(
            isinstance(today_statuses, str) and isinstance(kept.get("statuses"), str)
            and kept["statuses"] != today_statuses)
        # This reader can see fewer of the sprint's issues than the row counts.
        # Under the common Jira setup — board access implying issue access —
        # this never fires. When it does, it is issue-level security, and it is
        # the one cause of a recorded/re-derived disagreement that is about the
        # *reader* rather than about the board. ADR 0019.
        seen_now, seen_then = item.get("issuesSeen"), kept.get("issuesSeen")
        row["narrowerThanRecord"] = bool(
            isinstance(seen_now, int) and isinstance(seen_then, int)
            and seen_now < seen_then)
        rows.append(row)
    # A recorded sprint that is not on screen, split by *why* — because the two
    # reasons have different answers and printing one for both is the failure
    # this file has now made twice.
    #
    #   **outside the window**  older than anything asked for. Widen
    #                           `trendSprints` and it comes back.
    #   **missing**             inside the range that was asked for, and the
    #                           board did not offer it. Deleted, or moved.
    #
    # Before this split, a board with ten recorded sprints and a six-sprint
    # window reported four of them as "no longer offered by this board", which
    # was not true of any of them.
    outside, missing = [], []
    for k in sorted(x for x in sprints if x not in seen):
        when = (sprints[k] or {}).get("observedOn")
        if asked_from and when and str(when) < asked_from:
            outside.append(k)
        else:
            missing.append(k)
    return {"rows": rows, "orphaned": missing, "outsideWindow": outside}


def series_upto(rows, context_id):
    """A context sees the series up to and including itself, never the future.

    The fetcher has always done this — `history` in a bundle is sliced per
    context — and the rule survived into the served route only because this
    function exists. Without it, selecting a sprint that closed in June draws a
    trend running through September and compares that sprint's delivery against
    a row from three months after it, which is not a comparison anybody asked
    for and reads as a perfectly ordinary chart.

    Matched on the context id rather than on a date, because the ids are what
    the caller selected by and a date comparison would need a tie-break the
    moment two sprints share an end. An id that is not in the list leaves the
    rows alone: the caller is looking at something this series is not about, and
    silently returning an empty trend would read as a team with no history.

    **Narrowed to the selected context's board first.** A trend is per board;
    both real callers pass one board's contexts, and this truncates by position,
    so a caller that passed two boards would get a series interleaved by date
    and cut in the middle of the wrong one. That is not a call anybody should
    make, and it is also not a call that should quietly return something
    plausible — so rather than documenting the trap, the function closes it.
    """
    all_rows = list(rows or [])
    here = next((r for r in all_rows if r.get("contextId") == context_id), None)
    if here is None:
        return all_rows
    board = here.get("boardId")
    mine = [r for r in all_rows
            if r.get("boardId") == board] if board is not None else all_rows
    ids = [r.get("contextId") for r in mine]
    return mine[:ids.index(context_id) + 1]


def skipped_note(skipped):
    """What the page says about sprints that produced no row at all.

    Separate from `series_note`, which is about the rows that exist. This is
    about the ones that do not, and it is the sentence whose absence turned a
    datable-sprint problem into "needs at least two sprints of history" on a
    board with two.
    """
    items = [x for x in (skipped or []) if x]
    if not items:
        return ""
    named = ", ".join(str(x.get("sprintName") or x.get("contextId") or "one sprint")
                      for x in items)
    whys = sorted({str(x.get("why") or "") for x in items if x.get("why")})
    return ("%d sprint%s on this board produced no row and %s left out of the "
            "trend — %s. %s"
            % (len(items), "" if len(items) == 1 else "s",
               "was" if len(items) == 1 else "were", named,
               " ".join(w[0].upper() + w[1:] + "." for w in whys)))


def window_note(offered, shown, window):
    """What the page says when a board has more sprints than the trend shows.

    The other half of item 4b. `outsideWindow` in `series_note` covers sprints
    this installation *recorded* and is not showing; this covers the ones the
    board has and was never asked for. Both are truncations and neither may be
    silent — a chart of six sprints from a board with twenty is a chart that
    reads as a complete record.

    Silent when nothing was cut, which is every board younger than its window.
    """
    if not isinstance(offered, int) or not isinstance(shown, int):
        return ""
    dropped = offered - shown
    if dropped <= 0:
        return ""
    return ("This board has %d sprints and the trend shows the most recent %d. "
            "The %d older %s not on it; trendSprints is %s."
            % (offered, shown, dropped,
               "one is" if dropped == 1 else "ones are",
               window if isinstance(window, int) else "the window setting"))


def series_note(merged):
    """What the page says above the chart. Silent when there is nothing to say.

    Every sentence is about something a reader cannot see by looking. Six
    visible points do not need a sentence saying there are six; a recorded
    sprint whose figures no longer match Jira's answer does.

    Counts are read off the rows they describe, never computed beside them.
    """
    rows = (merged or {}).get("rows") or []
    orphaned = (merged or {}).get("orphaned") or []
    recorded = [r for r in rows if r.get("source") == "recorded"]
    rebuilt = [r for r in rows if r.get("source") == "reconstructed"]
    out = []

    if recorded and rebuilt:
        out.append(
            "%d of these %d sprint%s closed before this app saw the board, so %s "
            "rebuilt from Jira rather than recorded at the time. They agree unless "
            "something below says otherwise."
            % (len(rebuilt), len(rows), "" if len(rows) == 1 else "s",
               "its row was" if len(rebuilt) == 1 else "their rows were"))

    mid = [r for r in recorded if r.get("atSprintEnd") is False]
    if mid:
        out.append(
            "One recorded sprint was last seen while it was still running, so its "
            "row is that day rather than the sprint's end." if len(mid) == 1 else
            "%d recorded sprints were last seen while still running, so their rows "
            "are those days rather than the sprints' ends." % len(mid))

    moved = [r for r in recorded if r.get("statusesMoved") is True]
    if moved:
        out.append(
            "%s recorded under a different set of \u201cin progress\u201d statuses than "
            "this site uses now. Work in progress and flow efficiency are measured "
            "against that word, so those points and the recent ones are not quite "
            "the same measurement."
            % ("One sprint was" if len(moved) == 1 else "%d sprints were" % len(moved)))

    narrowed = [r for r in recorded if r.get("narrowerThanRecord")]
    if narrowed:
        out.append(
            "%s about the whole board, and you can see fewer of the issues %s "
            "counts than it does. The figures shown are the board's; yours "
            "would be lower. That is issue-level security, not a delivery "
            "problem, and not a disagreement about what happened."
            % ("One row here is" if len(narrowed) == 1
               else "%d rows here are" % len(narrowed),
               "it" if len(narrowed) == 1 else "each"))

    # Rows whose disagreement is *explained* by the sentence above are not also
    # reported as an unexplained one. Offering "a sprint reopened, or an issue
    # deleted" for a difference this already knows the cause of is the failure
    # this file has now made three times: one sentence standing for several
    # causes. A narrowed row differs on every count, and for one reason.
    differing = [r for r in recorded
                 if r.get("differs") and not r.get("narrowerThanRecord")]
    if differing:
        fields = sorted({f for r in differing for f in r["differs"]})
        out.append(
            "%s what Jira answers for %s today \u2014 %s. The recorded figures are "
            "shown. A sprint reopened and closed again, or an issue deleted, changes "
            "what can be re-derived; the record of what was true does not change."
            % ("One recorded sprint no longer matches" if len(differing) == 1
               else "%d recorded sprints no longer match" % len(differing),
               "it" if len(differing) == 1 else "them", ", ".join(fields)))

    if orphaned:
        out.append(
            "%s no longer offered by this board and %s left out rather than placed "
            "at a guessed position."
            % ("One recorded sprint is" if len(orphaned) == 1
               else "%d recorded sprints are" % len(orphaned),
               "was" if len(orphaned) == 1 else "were"))

    # Not a fault, and said anyway. A trend showing six of a board's twenty
    # sprints reads as the whole record unless it says which it is, and the
    # window is a setting — so the sentence names the thing to change.
    outside = (merged or {}).get("outsideWindow") or []
    if outside:
        out.append(
            "%s recorded before the window this trend shows, so %s not on it. "
            "Widen trendSprints to bring %s back."
            % ("One further sprint was" if len(outside) == 1
               else "%d further sprints were" % len(outside),
               "it is" if len(outside) == 1 else "they are",
               "it" if len(outside) == 1 else "them"))

    return " ".join(out)


def facts(ds, previous=None, scope="sprint"):
    meta = ds.get("meta", {})
    # One resolution, from the file, shared by everything below. The dashboard
    # reads the same block out of the same file, which is what keeps this pack
    # and the page from disagreeing about which days were worked.
    cfg = OC.from_dataset(ds)
    as_of = meta.get("asOfDate") or meta.get("endDate") or date.today().isoformat()
    end = meta.get("endDate")
    start = meta.get("startDate")

    # Which issues count as items, per the config the dataset carries — ADR
    # 0024. A parent and its subtasks are one piece of work and several rows,
    # and every figure below is a count of items. What was left out is reported
    # in `counting` rather than dropped, because a smaller number with no reason
    # beside it is the silent cap this repository forbids.
    all_issues, not_counted = OC.counted_issues(ds["issues"], cfg)
    issues = ([i for i in all_issues if in_sprint(i, start)]
              if scope == "sprint" else list(all_issues))

    done = [i for i in issues if is_done(i)]
    openi = [i for i in issues if not is_done(i)]
    sp = lambda xs: round(sum(x.get("storyPoints") or 0 for x in xs), 1)

    added = [i for i in issues if i.get("addedMidSprint")]
    flagged = [i for i in issues if i.get("flagged")]
    critical = [i for i in openi if str(i.get("priority") or "").lower() in ("highest", "critical", "p1")]
    overdue = [i for i in openi if i.get("dueDate") and _d(i["dueDate"]) < _d(as_of)]
    unstarted = [i for i in openi if not i.get("started")]

    cyc = [elapsed_days(i["started"], i["resolved"]) for i in done if i.get("started") and i.get("resolved")]
    lead = [elapsed_days(i["created"], i["resolved"]) for i in done if i.get("created") and i.get("resolved")]
    cyc = [c for c in cyc if c is not None]
    lead = [l for l in lead if l is not None]

    # --- the flow figures a board without a sprint boundary is read on -------
    #
    # These are computed here rather than in the page for the reason every
    # figure is: the agent quotes, it does not calculate, and a chart whose
    # numbers no tool produced is a chart nobody can check. The page draws the
    # same series from the same issues and `tests/test_agent.py` holds the two
    # to the same answers.
    #
    # None of them needs a sprint. That is not a coincidence — it is why the
    # forecaster worked on a flow board from the start, and why these were
    # available all along rather than something the schema had to grow.

    # Cycle time per closed item, dated, so the scatterplot can be checked
    # against the pack a line at a time and an outlier can be named.
    cycle_items = sorted(
        ({"key": i["key"], "resolved": i["resolved"],
          "days": elapsed_days(i["started"], i["resolved"])}
         for i in done if i.get("started") and i.get("resolved")),
        key=lambda r: (r["resolved"], r["key"]))
    cycle_items = [r for r in cycle_items if r["days"] is not None]

    # Items finished per calendar week, keyed by the Monday. Weeks, not days:
    # a per-day series over a flow board is mostly zeroes and reads as a team
    # that keeps stopping. Zero weeks stay in — the same rule the forecaster's
    # throughput sampling follows, and for the same reason.
    per_week = {}
    finished = sorted(_d(i["resolved"]) for i in done if i.get("resolved"))
    if finished:
        first = finished[0] - datetime.timedelta(days=finished[0].weekday())
        last = finished[-1] - datetime.timedelta(days=finished[-1].weekday())
        w = first
        while w <= last:
            per_week[w.isoformat()] = 0
            w += datetime.timedelta(days=7)
        for r in finished:
            per_week[(r - datetime.timedelta(days=r.weekday())).isoformat()] += 1
    weeks = [{"week_starting": k, "items": v} for k, v in sorted(per_week.items())]

    # Work in progress at the as-of date: started, not yet finished. Derived
    # from dates rather than from status, so it means the same thing on a board
    # whose columns this tool has never seen.
    wip_now = len([i for i in openi if i.get("started")])

    # How the open work is ageing against what finished work actually took.
    # An item past the 85th percentile is late *now*, before it is late.
    cyc_p85 = _pctile(cyc, 85)
    ageing_wip = sorted(
        ({"key": i["key"], "status": i.get("status"),
          "age_days": elapsed_days(i["created"], as_of)}
         for i in openi if i.get("created")),
        key=lambda r: -(r["age_days"] or 0))
    past_p85 = ([r for r in ageing_wip if cyc_p85 is not None and (r["age_days"] or 0) > cyc_p85]
                if cyc_p85 is not None else [])

    # Cumulative flow, at the only granularity this schema can honestly carry.
    # A real CFD has one band per column; the bands below are the three status
    # *categories*, because nothing in a dataset records which column an issue
    # sat in on a given day. Said out loud in `bands`, so a reader who expects
    # seven columns learns why they got three rather than assuming the board
    # has three. The Forge resolver's `statusTransitions` would support the
    # finer version; the Python fetcher does not emit them yet.
    cfd = []
    if all_dates := sorted({d for i in issues for d in
                            (i.get("created"), i.get("started"), i.get("resolved")) if d}):
        span_start, span_end = _d(all_dates[0]), _d(as_of)
        day = span_start
        while day <= span_end:
            iso = day.isoformat()
            todo = ip = dn = 0
            for i in issues:
                c, st, r = i.get("created"), i.get("started"), i.get("resolved")
                if not c or c > iso:
                    continue
                if r and r <= iso:
                    dn += 1
                elif st and st <= iso:
                    ip += 1
                else:
                    todo += 1
            cfd.append({"date": iso, "to_do": todo, "in_progress": ip, "done": dn})
            day += datetime.timedelta(days=1)

    # Little's Law as a reconciliation, not as a prediction and not as a
    # verdict. Work in progress divided by throughput is how long the average
    # item must be spending in progress; measured cycle time is how long the
    # items that *finished* actually took. On a healthy board they land near
    # each other.
    #
    # When they do not, there are two honest readings and this tool does not
    # choose between them: the open work is genuinely sitting far longer than
    # anything that has finished — the case the ageing chart shows by name — or
    # the start dates are not recording when work really began. Both are worth
    # knowing and they are not the same problem, so the two figures are
    # returned side by side and `agrees` says only whether they line up.
    thr_per_day = (sum(w["items"] for w in weeks) / (len(weeks) * 7.0)) if weeks else None
    implied = (wip_now / thr_per_day) if thr_per_day else None
    cyc_p50 = _pctile(cyc, 50)
    littles = {
        "wip_now": wip_now,
        "throughput_items_per_day": round(thr_per_day, 2) if thr_per_day else None,
        "implied_cycle_days": round(implied, 1) if implied else None,
        "measured_cycle_p50": cyc_p50,
        # A factor of two either way. Tighter would fire on ordinary variation;
        # looser would never fire at all.
        "agrees": (None if implied is None or cyc_p50 in (None, 0)
                   else 0.5 <= implied / cyc_p50 <= 2.0),
    }

    wdays = meta.get("workingDays") or [d.isoformat() for d in working_days(_d(start), _d(end), cfg)]
    elapsed = pct(wdays.index(as_of) + 1, len(wdays)) if as_of in wdays else (1.0 if wdays else None)

    ages = {}
    for band, lo, hi in (("0-7", 0, 7), ("8-14", 7, 14), ("15-30", 14, 30), ("30+", 30, 10 ** 6)):
        ages[band] = [i["key"] for i in openi
                      if i.get("created") and lo < (elapsed_days(i["created"], as_of) or 0) <= hi]

    by_person = defaultdict(lambda: {"done": 0, "open": 0, "donePts": 0.0, "openPts": 0.0})
    for i in issues:
        b = by_person[i.get("assignee") or "Unassigned"]
        k = "done" if is_done(i) else "open"
        b[k] += 1
        b[k + "Pts"] = round(b[k + "Pts"] + (i.get("storyPoints") or 0), 1)

    hist = ds.get("history") or []
    last3 = [h.get("completedSP") for h in hist[-4:-1] if h.get("completedSP") is not None]
    last3_items = [h.get("throughput") for h in hist[-4:-1] if h.get("throughput") is not None]
    committed = hist[-1].get("committedSP") if hist else sp([i for i in issues if not i.get("addedMidSprint")])
    committed_items = len([i for i in issues if not i.get("addedMidSprint")])

    valued = [i for i in done if OC.value_of(i, cfg) > 0]

    f = {
        "meta": {
            "sprint": meta.get("sprintName"),
            "team": meta.get("team"),
            "organisation": meta.get("organisation"),
            "goal": meta.get("sprintGoal"),
            "start": start, "end": end, "as_of": as_of,
            "source": meta.get("sourceLabel"),
            "currency": meta.get("currency", "USD"),
            "scope": scope,
            # What the figures below are a count *of* — ADR 0024. Reported
            # whether or not anything was left out, because "nothing was
            # excluded" is a fact a reader needs as much as the other one, and
            # a key that appears only sometimes is read as a key that means
            # nothing when it is absent.
            "counting": {
                "issues_seen": len(ds["issues"]),
                "items_counted": len(all_issues),
                "not_counted": dict(not_counted),
                "sentence": OC.counted_note(not_counted, len(ds["issues"])),
            },
            "issues_in_scope": len(issues),
            "issues_in_file": len(all_issues),
            # Stated, not assumed. Sprint elapsed-percentage below is a share of
            # working days, so the calendar behind it belongs in the pack.
            "calendar": OC.summary(cfg),
        },
        "delivery": {
            "items_total": len(issues), "items_done": len(done),
            "items_done_pct": pct(len(done), len(issues)),
            "points_total": sp(issues), "points_done": sp(done), "points_open": sp(openi),
            "points_done_pct": pct(sp(done), sp(issues)),
            "time_elapsed_pct": elapsed,
            "pace_gap_pts": round(pct(sp(done), sp(issues)) - elapsed, 4) if elapsed is not None else None,
        },
        "scope": {
            "added_items": len(added), "added_points": sp(added),
            "growth_pct": pct(sp(added), sp(issues) - sp(added)),
            "added_keys": [i["key"] for i in added],
        },
        "risk": {
            "unit": "calendar days",
            "blocked": [i["key"] for i in flagged],
            "top_priority_open": [i["key"] for i in critical],
            "overdue": [i["key"] for i in overdue],
            "never_started": [i["key"] for i in unstarted],
            "age_bands": ages,
            "oldest_open": max(
                ({"key": i["key"], "days": elapsed_days(i["created"], as_of)} for i in openi if i.get("created")),
                key=lambda r: r["days"] or 0, default=None),
        },
        "flow": {
            "unit": "calendar days",
            "cycle_p50": _pctile(cyc, 50), "cycle_p85": _pctile(cyc, 85),
            "cycle_p95": _pctile(cyc, 95),
            "lead_p50": _pctile(lead, 50), "lead_p85": _pctile(lead, 85),
            "flow_efficiency": pct(sum(cyc), sum(lead)) if lead and sum(lead) else None,
            "samples": len(cyc),
            "cycle_items": cycle_items,
            "throughput_per_week": weeks,
            "throughput_mean_per_week": (
                round(sum(w["items"] for w in weeks) / len(weeks), 1) if weeks else None),
            "wip_now": wip_now,
            "ageing_wip": ageing_wip,
            "ageing_past_cycle_p85": [r["key"] for r in past_p85],
            "cumulative_flow": {
                "bands": ["to_do", "in_progress", "done"],
                "granularity": "status category",
                "why": ("one band per status category, not per column — no dataset records "
                        "which column an issue sat in on a given day"),
                "series": cfd,
            },
            "littles_law": littles,
        },
        "predictability": {
            # ITEMS is the primary unit. Every forecast and every commitment
            # recommendation is in items, because a throughput distribution needs
            # tens of observations and six sprints only ever supplies six point
            # figures. Points are retained below for continuity with existing
            # reporting — they are not a forecasting input and must never be
            # quoted as one.
            "primary_unit": "items",
            "items": {
                "committed_items": committed_items,
                "completed_items": len(done),
                "trailing_3_sprint_avg_completed_items": (
                    round(sum(last3_items) / len(last3_items), 1) if last3_items else None),
                "commitment_vs_trailing_avg": (
                    round(committed_items / (sum(last3_items) / len(last3_items)) - 1, 3)
                    if last3_items and committed_items else None),
                "hit_rates": [
                    {"sprint": h["sprint"], "completed_items": h.get("throughput")}
                    for h in hist if h.get("throughput") is not None],
                "note": ("For the commitment figure to recommend, use forecast.py's "
                         "recommend_commitment() — a distribution over simulated sprints "
                         "beats a mean of three numbers."),
            },
            "points": {
                "committed_points": committed,
                "trailing_3_sprint_avg_completed": round(sum(last3) / len(last3), 1) if last3 else None,
                "commitment_vs_trailing_avg": (
                    round(committed / (sum(last3) / len(last3)) - 1, 3) if last3 and committed else None),
                "hit_rates": [
                    {"sprint": h["sprint"], "rate": pct(h.get("completedSP") or 0, h.get("committedSP") or 0)}
                    for h in hist],
                "status": "reported for continuity; not a forecasting input",
            },
        },
        "value": {
            "closed_estimate": round(sum(OC.value_of(i, cfg) for i in valued)),
            "items_with_estimate": len(valued),
            "items_without_estimate": len(done) - len(valued),
            "bases": [{"key": i["key"], "amount": OC.value_of(i, cfg), "basis": i.get("valueBasis") or ""}
                      for i in valued],
        },
        "people": dict(by_person),
        "dora": ds.get("dora"),
        "releases": ds.get("releases") or [],
    }
    f["changes"] = diff(f, previous) if previous else None
    return f


# ---------------------------------------------------------------------- diff
WATCH = [
    ("delivery.items_done", "items completed", 1, "up"),
    ("delivery.points_done", "points completed", 1, "up"),
    ("delivery.pace_gap_pts", "pace against the clock", 0.03, "up"),
    ("scope.added_points", "points added mid-sprint", 1, "down"),
    ("value.closed_estimate", "estimated value closed", 1, "up"),
    ("flow.flow_efficiency", "flow efficiency", 0.03, "up"),
]


def _get(d, path):
    cur = d
    for k in path.split("."):
        cur = (cur or {}).get(k)
    return cur


def diff(now, before):
    """What changed since the previous snapshot, and which direction is good.

    A report that restates the same state every week gets skimmed then ignored.
    Movement, and only movement, is the news.
    """
    out = {"since": (before.get("meta") or {}).get("as_of"), "moved": [], "list_changes": {}}
    for path, label, threshold, good in WATCH:
        a, b = _get(before, path), _get(now, path)
        if a is None or b is None:
            continue
        delta = round(b - a, 4)
        if abs(delta) < threshold:
            continue
        direction = "up" if delta > 0 else "down"
        out["moved"].append({
            "metric": label, "from": a, "to": b, "delta": delta,
            "direction": direction,
            "reading": "better" if direction == good else "worse",
        })
    for key in ("blocked", "top_priority_open", "overdue", "never_started"):
        was = set((before.get("risk") or {}).get(key) or [])
        now_set = set((now.get("risk") or {}).get(key) or [])
        if was != now_set:
            out["list_changes"][key] = {
                "new": sorted(now_set - was),
                "cleared": sorted(was - now_set),
                "still_there": sorted(now_set & was),
            }
    return out


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--previous", help="a previous facts pack, for the change section")
    ap.add_argument("--out", help="write the facts pack here as well as printing it")
    ap.add_argument("--scope", choices=("sprint", "all"), default="sprint",
                    help="'sprint' counts only work not already finished before the sprint "
                         "started (the default, and what a sprint report means); "
                         "'all' counts every row in the file")
    a = ap.parse_args()

    ds = json.load(open(a.dataset))
    prev = json.load(open(a.previous)) if a.previous else None
    f = facts(ds, prev, a.scope)
    text = json.dumps(f, indent=2, default=str)
    if a.out:
        open(a.out, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
