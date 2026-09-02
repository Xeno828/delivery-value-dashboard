#!/usr/bin/env python3
"""
routes.py — the calculator's answers, with nothing to serve them.

Everything `service/app.py` did that was not HTTP or authentication lives here:
the projection that keeps a customer's words out of a calculation, the caps,
the refusal sentences, and one function per route that validates, delegates to
`agent/tools/` and hands the figures back. Two callers import it and neither
adds anything:

  * `service/app.py`, the hosted calculator, puts a socket and two auth
    verifiers in front of `answer()` and is otherwise a pass-through.
  * The Forge function runs this file unchanged under Pyodide — CPython
    compiled to WebAssembly — inside Atlassian's runtime, and calls `answer()`
    with the same bodies. ADR 0031. Nothing is rewritten for that; the
    generated module the function ships is built from this file and from
    `agent/tools/` at deploy, so there is no second copy of any of it.

**It does no arithmetic of its own.** Every figure comes from metrics.py,
forecast.py, intake.py or selection.py, exactly as the dashboard and the CLI
get theirs. The moment this file computes a percentage there are two answers
to one question and no way to tell which the customer is reading;
`tests/test_service.py` asserts every route's answer equals the tool called
directly, and `tests/test_wasm.py` asserts the same answer under WebAssembly.

Nothing here opens a socket, reads an environment variable, or imports a
module the WebAssembly runtime lacks. That is a constraint, not a description:
this file is what travels into the Forge function, and an `import` that works
only on the hosted service is a deploy that fails inside a tenant.

The layout is fixed by `ROOT` below. Wherever this file is, the tools are two
directories up and under `agent/tools/`; the Forge function writes the sources
to `/work/service/routes.py` and `/work/agent/tools/*.py` for exactly that
reason.
"""

from __future__ import annotations

import pathlib
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent" / "tools"))

import forecast as FC      # noqa: E402
import intake as IN        # noqa: E402
import metrics as MT       # noqa: E402
import orgconfig as OC     # noqa: E402
import selection as SEL    # noqa: E402

#: The version every envelope carries. One string for both transports, so a
#: figure computed by the hosted service and one computed inside the Forge
#: function are labelled the same when they are the same.
VERSION = "1.0"

#: Bounds, and each one is reported rather than applied quietly. A truncated
#: issue list reads as a complete one, and a forecast over half a team's
#: history looks exactly like a forecast over all of it.
MAX_ISSUES = 50_000
# An asked-for item count is bounded so a typo cannot start a simulation that
# runs for minutes. Stated in the refusal rather than clamped quietly, which is
# the same rule every other limit here follows. Matches scripts/serve_live.py,
# because the two answer the same question over different transports.
MAX_ITEMS = 5000
# The cap on asks is not here. It is `intake.MAX_ASKS`, because it is a fact
# about the tool — how many orderings one sequencing can simulate while a
# reader waits — and the file transport has to refuse at the same number in
# the same sentence. `check_sequence` below consults it; ADR 0031.

#: Fields a calculation reads. Anything else in an incoming issue is dropped
#: before the tools see it — not for size, but because free text has no
#: business being here at all. Forge holds the summaries and re-attaches them
#: by key after the call, so nothing is lost from the rendered tile.
CALC_FIELDS = frozenset((
    "key", "created", "started", "resolved", "statusCategory", "status",
    "storyPoints", "priority", "dueDate", "flagged", "addedMidSprint",
    "contextId", "epicKey",
    # Which issues count as items is the organisation's answer and is applied
    # by the tools, so the tools have to be able to see it. `type` is a Jira
    # configuration label like `status`, which is already here; `isSubtask` is
    # Jira's own flag. Neither is free text and neither identifies a person.
    # ADR 0024.
    "type", "isSubtask",
    # Business value and the level it sits at — ADR 0025. The tools sum value
    # and apply the hierarchy rule, so the tools have to see both.
    #
    # This is the most commercially sensitive figure in the product and sending
    # it is a deliberate decision, not a field addition. It is a *number* with
    # no label attached: `valueBasis`, the sentence explaining what the number
    # means, stays in FREE_TEXT_FIELDS and is refused at the door. A currency
    # amount with no issue key beside it and no basis is not something a reader
    # of this service could act on, and the calculator stores nothing.
    "businessValue", "hierarchyLevel",
))

#: Fields refused outright if they arrive. A caller sending issue summaries to
#: a calculator is a caller with a bug, and accepting them quietly would make
#: this service a place customer text lives — which is the whole thing the
#: projection exists to avoid.
FREE_TEXT_FIELDS = ("summary", "assignee", "epic", "labels", "url", "valueBasis")


class Refused(Exception):
    """A bad request, with the sentence to send back."""

    def __init__(self, sentence, status=400):
        super().__init__(sentence)
        self.sentence = sentence
        self.status = status


# ------------------------------------------------------------- validation
def _clean_issue(raw, offenders):
    if not isinstance(raw, dict):
        raise Refused("every issue must be an object")
    for f in FREE_TEXT_FIELDS:
        if f in raw:
            offenders.add(f)
    return {k: v for k, v in raw.items() if k in CALC_FIELDS}


def clean_dataset(body):
    """The dataset the tools will see, or a refusal saying what was wrong."""
    ds = body.get("dataset")
    if not isinstance(ds, dict):
        raise Refused("send {\"dataset\": {...}} — nothing was calculated")
    issues = ds.get("issues")
    if not isinstance(issues, list):
        raise Refused("dataset.issues must be a list — nothing was calculated")
    if len(issues) > MAX_ISSUES:
        raise Refused("%d issues is over this service's limit of %d. Nothing was "
                      "calculated: a forecast over a truncated history looks "
                      "exactly like a forecast over all of it."
                      % (len(issues), MAX_ISSUES), 413)

    offenders = set()
    clean = {
        "issues": [_clean_issue(i, offenders) for i in issues],
        "meta": ds.get("meta") if isinstance(ds.get("meta"), dict) else {},
        "orgConfig": ds.get("orgConfig") if isinstance(ds.get("orgConfig"), dict) else {},
    }
    for optional in ("releases", "contexts", "byContext", "history"):
        if isinstance(ds.get(optional), (list, dict)):
            clean[optional] = ds[optional]

    if offenders:
        raise Refused(
            "the payload carried %s. This service calculates from dates and "
            "status categories; issue text does not belong here and was not "
            "stored. Project the issues before sending them."
            % ", ".join(sorted(offenders)))

    problems = OC.validate(OC.from_dataset(clean))
    if problems:
        raise Refused("the organisation config in this payload is not usable: "
                      + "; ".join(problems))
    return clean


def _iso_or_none(body, key):
    v = body.get(key)
    if v is None:
        return None
    from datetime import date
    try:
        date.fromisoformat(str(v)[:10])
    except ValueError:
        raise Refused("%s must be YYYY-MM-DD, not %r — nothing was calculated"
                      % (key, v))
    return str(v)[:10]


# ------------------------------------------------------------------ routes
def route_facts(body):
    ds = clean_dataset(body)
    scope = body.get("scope") or "sprint"
    if scope not in ("sprint", "all"):
        raise Refused("scope must be 'sprint' or 'all'")
    prev = body.get("previous") if isinstance(body.get("previous"), dict) else None
    return MT.facts(ds, previous=prev, scope=scope)


def route_forecast(body):
    ds = clean_dataset(body)
    remaining = body.get("remaining")
    if remaining is not None:
        if not isinstance(remaining, int) or isinstance(remaining, bool) or remaining < 0:
            raise Refused("remaining must be a whole number of items, or absent "
                          "to use the dataset's own outstanding count")
    window = body.get("windowDays")
    if window is not None and (not isinstance(window, int) or window <= 0):
        raise Refused("windowDays must be a positive whole number of days")
    return FC.build(ds,
                    as_of=_iso_or_none(body, "asOf"),
                    remaining=remaining,
                    target=_iso_or_none(body, "target"),
                    snapshots=body.get("snapshots"),
                    window_days=window)


def route_slice(body):
    """Which contexts a forecast for this one would sample.

    The caller that needs this is a Forge resolver. It has to fetch the issues
    of every context in the slice before it can ask for a forecast over them,
    and it must not decide the slice itself — that decision is `team_slice`,
    which is the logic whose every failure is a plausible date rather than an
    error, and which exists in exactly one place for that reason.

    So the resolver asks. It sends the contexts it knows about, with no issues
    at all — this route needs none — and gets back the ids to fetch. One round
    trip against a service that answers in well under a second, in exchange for
    there being no second copy of the rule and no way to forecast from a
    narrower sample than the answer claims.
    """
    ds = body.get("dataset")
    contexts = ds.get("contexts") if isinstance(ds, dict) else None
    if not isinstance(contexts, list) or not contexts:
        raise Refused('send {"dataset": {"contexts": [...]}} — this route chooses '
                      'the slice and needs the contexts to choose from. No issues '
                      'are needed and none should be sent.')
    cid = body.get("contextId")
    if not isinstance(cid, str) or not cid.strip():
        raise Refused('send "contextId" — which context the slice is for')
    members, label = SEL.slice_for(contexts, cid.strip())
    if members is None:
        raise Refused("unknown context %r — no slice was chosen" % cid.strip(), 404)
    return {"contextIds": [c["id"] for c in members if c.get("id")], "slice": label}


def route_forecast_context(body):
    """A forecast for one context, with this service choosing the slice.

    `/v1/forecast` takes a flat list of issues and simulates them. That leaves
    the *slice* — which issues make up this team's history, how much work is
    outstanding, and whether the date on offer is a deadline or an artefact — to
    whoever calls it. Over loopback that caller is `scripts/serve_live.py`,
    which is Python and can use the same rules the tools use. Over Forge the
    caller is a Node resolver, which cannot; and the slice is the last thing in
    this repository that should be written twice, because every one of its
    failures is a plausible date rather than an error.

    So the caller sends what it has — the contexts, the issues, and which
    context the reader is looking at — and `selection.forecast_for` does the
    rest. This service still computes nothing: it validates, delegates, and
    passes the figures back. `tests/test_service.py` holds this route's answer
    against the same function called directly.
    """
    ds = clean_dataset(body)
    contexts = ds.get("contexts")
    if not isinstance(contexts, list) or not contexts:
        raise Refused('send "dataset.contexts" — the slice is chosen from them. '
                      'A forecast built from a single sprint refuses for want of '
                      'observations, so the sample is the team and only the '
                      'outstanding work is the selected context\'s.')
    cid = body.get("contextId")
    if not isinstance(cid, str) or not cid.strip():
        raise Refused('send "contextId" — which context this forecast is for')
    items = body.get("items")
    if items is not None:
        if (not isinstance(items, int) or isinstance(items, bool)
                or items <= 0 or items > MAX_ITEMS):
            raise Refused("items must be a whole number between 1 and %d — "
                          "nothing was simulated" % MAX_ITEMS)
    # The reader's issue-type selection, which narrows the organisation's rule
    # and never widens it. A list of type names; absent means no narrowing.
    types = body.get("types")
    if types is not None and (not isinstance(types, list)
                              or not all(isinstance(t, str) for t in types)):
        raise Refused('"types" must be a list of issue type names, or absent — '
                      "nothing was simulated")
    out = SEL.forecast_for(contexts, ds["issues"], ds.get("byContext") or {},
                           cid.strip(), items=items,
                           target=_iso_or_none(body, "target"),
                           org_cfg=ds.get("orgConfig") or {},
                           types=types)
    if out is None:
        # A context this dataset does not describe is a 404 and not a 400: the
        # request was well formed and named something that is not here.
        raise Refused("unknown context %r — nothing was simulated" % cid.strip(), 404)

    # The forecast log — roadmap item 4c, ADR 0017. The caller sends the log it
    # holds; `update_log` adds this forecast's claims, resolves the ones whose
    # horizon has passed, trims and scores. This service still computes nothing
    # of its own: one tool function does all of it and both transports call it.
    #
    # Optional, and absent means the caller keeps no log — the forecast comes
    # back exactly as it did before, which is what `/v1/forecast` and every
    # existing caller rely on.
    log = body.get("log")
    if log is not None:
        if not isinstance(log, list):
            raise Refused('"log" must be the caller\'s forecast log, or absent')
        # **The latest date this caller's data can speak to**, which is one
        # rule with two answers. Over Forge the issues are read live, so it is
        # today. Over loopback the dataset is a file that stops where it stops,
        # and resolving a claim whose window runs past the last day the file
        # describes would count zero completions and call the forecast wrong —
        # a false verdict from missing data rather than a missed prediction.
        # Absent, it falls back to the forecast's own as-of, which is the
        # conservative end of the same rule.
        today = _iso_or_none(body, "today") or _iso_or_none(body, "asOf")
        out["calibration"] = FC.update_log(
            log, out.get("claims") or [], ds["issues"],
            today or (out.get("asked") or {}).get("as_of"),
            # How wide this caller's view is, from the slice the forecast
            # actually sampled. It gates two things: publishing a claim the log
            # would mistake for the board's, and resolving one against work this
            # reader cannot see — which is the irreversible half, because a
            # claim is scored once and never rescored.
            seen=out.get("issuesSeen"))
    return out


def route_ask(body):
    ds = clean_dataset(body)
    ask = body.get("ask")
    if not isinstance(ask, dict):
        raise Refused("send an \"ask\" object — see docs/product-intake.md")
    _refuse_ask_text(ask, "the ask")
    return IN.forecast_ask(ds, dict(ask), board=body.get("board"),
                           as_of=_iso_or_none(body, "asOf"))


#: Free text on an *ask*, refused for the reason FREE_TEXT_FIELDS above are.
#:
#: The projection protects the issues in `dataset`. Nothing looked at `asks`,
#: which are built by the caller rather than projected from anything — so a
#: title, a problem statement or a value basis would have travelled straight
#: through, and `title` is the obvious one to send because it is what a reader
#: wants beside an ordering. The Forge resolver holds those words back and joins
#: them on afterwards; this makes that a rule rather than a habit.
ASK_TEXT_FIELDS = ("title", "team", "requestedBy", "problemStatement",
                   "successMeasure", "assumptions", "dependencies", "basis",
                   "summary")


def _refuse_ask_text(ask, where):
    present = [f for f in ASK_TEXT_FIELDS if f in (ask or {})]
    nested = [n for n in ("valueEstimate", "sizing")
              if isinstance((ask or {}).get(n), dict) and "basis" in ask[n]]
    if present or nested:
        raise Refused(
            "%s carries %s. This service sequences and forecasts; it is not a "
            "place a customer's words live, and an ask's title and basis belong "
            "beside the answer in whatever is showing it. Nothing was computed."
            % (where, ", ".join(sorted(present + ["%s.basis" % n for n in nested]))))


def check_sequence(body):
    """Everything `route_sequence` refuses, without the minutes of computing.

    Split from the route on purpose. Sequencing is the one calculation that no
    longer fits a synchronous call on Forge — twelve asks is three and a half
    minutes there — so the resolver validates here, hands the projection to a
    consumer function, and the consumer computes. A refusal has to come from
    the resolver, in under a second, and it has to be the same refusal the
    route would have given: the same sentence, the same status. Two validators
    would be two opinions about the same body. ADR 0031.

    Returns the cleaned dataset and the asks, which is exactly what the route
    then hands to the tool.
    """
    ds = clean_dataset(body)
    asks = body.get("asks")
    if not isinstance(asks, list) or not asks:
        raise Refused("send a non-empty \"asks\" list. Sequencing compares the "
                      "outstanding asks against each other, so it needs at least two.")
    # The tool's own cap and the tool's own sentence. It lives in intake.py
    # because every transport sequences through `intake.sequence` and has to
    # refuse at the same number in the same words; this only refuses early,
    # with a 413, before a dataset is cleaned for nothing.
    over = IN.too_many_asks(len(asks))
    if over:
        raise Refused(over, 413)
    for a in asks:
        _refuse_ask_text(a, "ask %r" % ((a or {}).get("id") or "?"))
    return ds, asks


def route_sequence(body):
    ds, asks = check_sequence(body)
    return IN.sequence(ds, [dict(a) for a in asks], board=body.get("board"),
                       as_of=_iso_or_none(body, "asOf"))


def route_history(body):
    """One row per sprint, for a caller that cannot compute one.

    The caller that needs this is a Forge resolver. It holds the tenant's own
    contexts and issues and must not derive a history row itself — `CLAUDE.md`
    is explicit that nothing between a tool and a reader does arithmetic, and a
    resolver that counted completions would be the second implementation this
    repository spends most of its tests preventing.

    So it sends what it has and `metrics.history_series` does the rest. This
    service still computes nothing: it validates, delegates and passes the rows
    back. A row here is nine numbers and a sprint name; the issue text that
    produced them is refused at the door by `clean_dataset`, like every other
    route.

    The rows come back with their context id and the sprint's state attached,
    because the caller has to decide whether it may *record* each one — a sprint
    that closed before the app saw the board is shown and never stored. That
    decision is the caller's and is made in `forge/src/series.js`; this route
    supplies the two facts it needs and takes no view.
    """
    ds = clean_dataset(body)
    contexts = (body.get("dataset") or {}).get("contexts")
    if not isinstance(contexts, list) or not contexts:
        raise Refused('send {"dataset": {"contexts": [...], "issues": [...]}} — '
                      "a row is per sprint, and the sprints come from the contexts. "
                      "Nothing was calculated.")
    got = MT.history_series(contexts, ds.get("issues") or [])
    rows, skipped = got["rows"], got["skipped"]

    # Every row is returned to the caller, because what may be *recorded* is
    # every sprint this look could see. What is *shown* stops at the selected
    # context — a sprint does not get to be compared against its own future.
    cid = body.get("contextId")
    shown = MT.series_upto(rows, cid) if isinstance(cid, str) and cid else rows

    # The caller's store, if it has one, so the merged answer comes back in the
    # same round trip. Nothing is stored here — this service holds no state and
    # is not becoming a place a tenant's series lives. It is handed the rows the
    # caller already has, and it returns what a reader should see.
    stored = body.get("stored")
    if stored is not None and not isinstance(stored, dict):
        raise Refused('"stored" must be the caller\'s series object, or absent')
    merged = MT.merge_series(stored or {},
                             [{"sprintId": r["contextId"], "row": r["row"],
                               "asOf": r.get("asOf"),
                               "issuesSeen": r.get("issuesSeen")}
                              for r in shown],
                             body.get("statuses"))
    # What the board has, against the window that was kept — roadmap item 4b.
    # The caller knows both; the sentence is the tool's, because it states a
    # count a reader reads.
    board_sprints = body.get("boardSprints")
    window = body.get("window")

    return {
        "rows": rows,
        # Read off the lists they describe, never computed beside them. `offered`
        # is what the caller sent; `sprints` is what produced a row. The two
        # differing is the fact a reader needs and the one that was invisible.
        "offered": len(rows) + len(skipped),
        "sprints": len(rows),
        "skipped": skipped,
        "merged": merged["rows"],
        "orphaned": merged["orphaned"],
        "outsideWindow": merged.get("outsideWindow") or [],
        "note": " ".join(x for x in (
            MT.series_note(merged),
            MT.skipped_note(skipped),
            MT.window_note(board_sprints, len(rows) + len(skipped), window)) if x),
    }


def route_burndown(body):
    """One sprint's daily burndown, for a caller that cannot compute one.

    The same case as `/v1/history` and the same rule. A Forge resolver holds the
    tenant's issues and their dates, and Forge cannot run Python — so before
    this route existed `contextBody` sent an empty series and the page drew
    nothing. Two of this product's eighteen tiles are a burndown and a reader
    who wants one is not served by a chart that is permanently blank.

    A resolver that built the series itself would be the fourth implementation
    of an algorithm that already has three, held together by a test. This
    service still computes nothing: it validates, delegates to
    `metrics.burndown`, and passes the rows back.

    `meta.workingDays` is the caller's to supply and is not derived here when it
    is absent — a window has no working-day list on purpose (ADR 0011), and a
    calendar invented at this end is the third opinion `CLAUDE.md` warns about.
    Absent both that and a start/end pair, the answer is an empty series, which
    is what a period with no clock honestly has.
    """
    ds = clean_dataset(body)
    meta = ds.get("meta") or {}
    if not (meta.get("workingDays") or (meta.get("startDate") and meta.get("endDate"))):
        raise Refused('send dataset.meta with either "workingDays" or a '
                      '"startDate" and "endDate" — a burndown needs days to plot '
                      "against. Nothing was calculated.")
    # The config the *dataset* carries, resolved the one way every other tool
    # resolves it. `CLAUDE.md`: it travels inside the data and is never read
    # from a file beside it.
    return {"burndown": MT.burndown(ds.get("issues") or [], meta, OC.from_dataset(ds))}


ROUTES = {
    "/v1/facts": route_facts,
    "/v1/forecast": route_forecast,
    "/v1/forecast-context": route_forecast_context,
    "/v1/slice": route_slice,
    "/v1/ask": route_ask,
    "/v1/sequence": route_sequence,
    "/v1/history": route_history,
    "/v1/burndown": route_burndown,
}


# ------------------------------------------------------------------ answer
def answer(path, body):
    """One route's envelope: `(status, payload)`, no socket and no auth.

    This is the seam both transports share. `service/app.py` calls it after
    authenticating and reading the body off the wire; the Forge function calls
    it with the body it assembled. What comes back is the same dict either way
    — `{"ok": true, "calendar": …, "version": …, "result": …}` or
    `{"ok": false, "error": …}` — and `tests/test_wasm.py` holds the two
    byte for byte, which is only possible because neither caller adds a key.

    `calendar` is on every answer on purpose: two forecasts of one board under
    different working weeks are different forecasts, and the difference is
    otherwise invisible to whoever reads the number.
    """
    fn = ROUTES.get(path)
    if fn is None:
        return 404, {"ok": False, "error": "no such route: %s" % path}
    if not isinstance(body, dict):
        return 400, {"ok": False, "error": "body must be a JSON object"}
    try:
        result = fn(body)
    except Refused as r:
        return r.status, {"ok": False, "error": r.sentence}
    except Exception:
        # The traceback goes to the operator, never to the caller: it would
        # carry field values, and those are the customer's.
        traceback.print_exc(file=sys.stderr)
        return 500, {"ok": False, "error": "the calculation failed. Nothing partial "
                                           "was returned."}

    cfg = OC.from_dataset(body.get("dataset") or {})
    return 200, {"ok": True, "calendar": OC.summary(cfg), "version": VERSION,
                 "result": result}
