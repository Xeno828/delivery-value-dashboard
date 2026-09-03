"""Which issues a forecast reads, and what it is told about them.

This is the *slice*, and it is separate from the Monte Carlo on purpose. The
forecaster in `forecast.py` takes a flat list of issues and simulates; deciding
which issues those are, how much work is outstanding, and which of the dates on
offer is a deadline rather than an artefact — that is this module, and it is
where the mistakes have been.

Every rule below exists because it was got wrong once, and every time the
symptom was a **credible number rather than an error**. Reading the wrong
context turned a 19-day forecast into 77 (CHANGELOG 1.8.0). Counting a flow
board's three overlapping windows as three separate contexts forecast a team
2.5 times too fast (1.16.13). Passing a window's end date through as a target
answered "0% by today" for a board that set no deadline (1.16.13 again). None
of those failed. They all returned a plausible date.

It lived in `scripts/serve_live.py` until the hosted calculator needed it too.
`forge/build-assets.mjs` packs `agent/tools/` and `service/routes.py` and nothing
else, so a slice defined in `scripts/` was a slice the Forge route could not
reach — and the only other way to give Forge a forecast was to write this
logic a second time in JavaScript, which is exactly what ADR 0005 and ADR 0008
exist to refuse. Of everything in this repository, this is the last code that
should have had two implementations.

So: one implementation, three callers. `scripts/serve_live.py` imports it,
`service/routes.py` imports it, and the agent's tools use it directly.
"""

import forecast as FC


#: A roll-up across every board in a project, rather than across one board's
#: sprints. Roadmap item 7, ADR 0023. Deliberately a different prefix from
#: `roll:` — the two answer different questions, and an id that could be read as
#: either is an id the wrong one will eventually answer.
CROSS_TEAM_PREFIX = "rollteams:"


def cross_team_members(contexts, project):
    """Every sprint context in a project, for a cross-team roll-up.

    **Sprints only.** A flow board is offered 14, 30 and 90 days of itself and
    those overlap completely, so a roll-up holding all three would count the
    same issue three times and report a programme delivering triple what it
    does. The per-board roll-up in `src/app.js` excludes them for the same
    reason and says so at length.
    """
    return [c for c in contexts or []
            if (c.get("kind") or "sprint") == "sprint"
            and str(c.get("projectKey") or c.get("projectName") or "") == str(project)]


def cross_team_boards(members):
    """The boards a cross-team roll-up spans, in a stable order, by name.

    Names and not a count, and that is the whole decision. This app cannot know
    which boards a reader is *not* seeing — the board list is read with their
    authority — so an omission cannot be detected and must instead be made
    unnecessary to detect. "3 boards" can be checked by nobody; three names can
    be checked by anybody who knows the programme. ADR 0023.
    """
    seen, out = set(), []
    for c in members or []:
        key = str(c.get("boardId") or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(c.get("boardName") or c.get("team") or "board %s" % (key or "?"))
    return sorted(out)


def cross_team_label(members):
    """What the page says a cross-team roll-up covers. The boards, listed."""
    names = cross_team_boards(members)
    if not names:
        return "no boards"
    return "%d board%s you can see — %s" % (
        len(names), "" if len(names) == 1 else "s", ", ".join(names))


def team_slice(contexts, ctx):
    """Every context belonging to the same team as `ctx`.

    A forecast built from one sprint refuses — on the demo board a single sprint
    offers 2 throughput observations against a threshold of 8. The team's whole
    history offers 55. So the sample is the team, and only the *remaining work*
    comes from the selected sprint.

    `team` is a free-text label, so fall back to project+board when it is absent.
    Slicing by team rather than board matters when a team runs two boards: the
    request is for everything known about that team, not a convenient subset.
    """
    team = (ctx.get("team") or "").strip()
    if team:
        return [c for c in contexts if (c.get("team") or "").strip() == team], "team %r" % team
    return ([c for c in contexts
             if c.get("projectKey") == ctx.get("projectKey")
             and c.get("boardId") == ctx.get("boardId")],
            "board %s/%s" % (ctx.get("projectKey"), ctx.get("boardId")))


def resolve_context(contexts, cid):
    """The context a forecast is *for*, and the sprints a rollup stands for.

    Returns `(ctx, roll_members)`, or `(None, None)` for an id this dataset does
    not describe. Split out so that asking "which contexts would this sample"
    and actually forecasting resolve the id the same way — a caller that has to
    fetch the slice's issues before it can ask for a forecast needs the first
    question answered on its own, and answering it twice is how the two would
    come to disagree about what a rollup means.
    """
    ctx = next((c for c in contexts if c["id"] == cid), None)
    roll_members = None
    if ctx is None and cid.startswith(CROSS_TEAM_PREFIX):
        # Cross-team — roadmap item 7, ADR 0023. Every sprint context in the
        # project, which on the panel path is every one *this reader can
        # browse*: the board list is read with the viewer's authority, so a
        # board they may not see never arrives here. That is mirroring holding
        # for free, and it is also why the members are named rather than
        # counted — this app cannot know what it is not seeing, so the honest
        # move is to say what it is.
        proj = cid[len(CROSS_TEAM_PREFIX):]
        roll_members = cross_team_members(contexts, proj)
        if not roll_members:
            return None
        latest = max(roll_members, key=lambda c: str(c.get("endDate") or ""))
        ctx = dict(latest)
        ctx["isRollup"] = True
        ctx["isCrossTeam"] = True
        # No team label. `team_slice` selects by one, and a cross-team context
        # carrying one would be sliced down to that single team and forecast
        # under a heading claiming the programme — the silent-narrowing fault
        # this module exists to prevent. Absent, `team_slice` falls back to
        # project+board, which `forecast_for` refuses for a cross-team rollup
        # rather than answering narrowly.
        ctx["team"] = ""
        ctx["sprintName"] = "All %d board%s" % (
            len(cross_team_boards(roll_members)),
            "" if len(cross_team_boards(roll_members)) == 1 else "s")
        return ctx, roll_members
    if ctx is None and cid.startswith("roll:"):
        # The dashboard synthesises one rollup per board client-side, so the
        # server has never seen this id. It is still a real question — "when
        # does everything open on this board land" — so answer it rather than
        # bouncing the caller. Key format: roll:<projectKey>|<boardId>.
        key = cid[len("roll:"):]
        proj, _, board = key.partition("|")
        roll_members = [c for c in contexts
                        if str(c.get("projectKey") or c.get("projectName") or "") == proj
                        and str(c.get("boardId") or c.get("boardName") or "") == board]
        if not roll_members:
            return None
        latest = max(roll_members, key=lambda c: str(c.get("endDate") or ""))
        ctx = dict(latest)
        ctx["sprintName"] = "All %d sprints" % len(roll_members)
    return ctx, roll_members


def slice_for(contexts, cid):
    """Which contexts a forecast for `cid` would sample, and how it chose them.

    `(members, label)`, or `(None, None)` for an unknown id. This exists for one
    caller: a Forge resolver, which must fetch the issues of every context in
    the slice *before* it can ask for a forecast over them, and which must not
    decide the slice itself. Asking here costs one round trip and keeps the rule
    in the one place it has ever been safe to have it.

    A caller that sends issues for fewer contexts than this names will get a
    forecast over a narrower sample than `sampled_from` reports — which is the
    silent-narrowing fault this repository keeps paying for, and the reason this
    route exists rather than the resolver guessing.
    """
    ctx, _ = resolve_context(contexts, cid)
    if ctx is None:
        return None, None
    return team_slice(contexts, ctx)


def forecast_for(contexts, issues, byContext, cid, items=None, target=None,
                 org_cfg=None, types=None):
    """Run the real forecaster for one context. Returns None for an unknown id.

    The slice is the thing to get right, and getting it wrong produces a
    credible wrong number rather than an error — see CHANGELOG 1.8.0, where
    reading the wrong context turned a 19-day forecast into 77.
    """
    ctx, roll_members = resolve_context(contexts, cid)
    if ctx is None:
        return None

    # A cross-team roll-up reports facts and does not forecast — ADR 0023, and
    # for two reasons that are worth keeping apart.
    #
    # The implementation one: `team_slice` selects by team label, so a
    # cross-team context would be sliced down to whichever team's label it
    # carried and forecast under a heading claiming the programme. That is a
    # forecast over a narrower sample than it reports, which is the fault this
    # module exists to prevent and which CHANGELOG 1.8.0 records turning a
    # 19-day answer into 77.
    #
    # The modelling one, which does not go away by fixing the first: pooling
    # several teams' throughput assumes an item finished by one team is
    # evidence about how fast another finishes items. Nothing here establishes
    # that, and a Monte Carlo will produce a confident date from the pooled
    # sample without complaint. The refusal names which reason it is rather
    # than reading as a gap somebody forgot to fill.
    if ctx.get("isCrossTeam"):
        sentence = ("This roll-up reports what is in flight and what completed "
                        "across %d board%s, and does not forecast. Pooling several "
                        "teams' throughput would assume an item finished by one team "
                        "says how fast another finishes items, which nothing here "
                        "establishes. Forecast one board at a time. Covering: %s."
                    % (len(cross_team_boards(roll_members)),
                       "" if len(cross_team_boards(roll_members)) == 1 else "s",
                       ", ".join(cross_team_boards(roll_members))))
        # The shape a whole-forecast refusal already has, rather than a new one.
        # `noCalculator` in forge/src/index.js answers this way and the page
        # renders it verbatim; a top-level `{available, sentence}` looked
        # reasonable and printed "No forecast. not available", because every
        # sub-answer the tile reads was simply absent. One refusal, one shape.
        refusal = {"available": False, "reason": sentence, "have": 0, "need": 1}
        return {
            "available": False,
            "sentence": sentence,
            "sprint_completion": dict(refusal),
            "capacity_to_target": dict(refusal),
            "next_commitment": dict(refusal),
            "item_risk": dict(refusal),
            "size_stability": dict(refusal),
            "asked": {}, "inputs": {},
            "sampled_from": {"slice": cross_team_label(roll_members),
                             "contexts": len(roll_members or [])},
            "crossTeam": True,
            "boards": cross_team_boards(roll_members),
        }
    members, slice_label = team_slice(contexts, ctx)
    member_ids = {c["id"] for c in members}
    # One issue is one item, however many contexts hold it. On a sprint board
    # that is free — a team's sprints do not overlap, and no key appears twice
    # in one slice. A flow board's windows overlap completely: 14, 30 and 90
    # days of the *same* board, so every issue in the short window is also in
    # the long ones, and the slice held each of them three times.
    #
    # Nothing failed. `throughput_samples` counted three completions on the day
    # one item finished, the forecaster read a team going three times as fast,
    # and the 85th-percentile date came back correspondingly early. `item_risk`
    # listed the same issue three times over. This is the class of fault this
    # repository keeps finding: a smaller number, arrived at by arithmetic,
    # with nothing on screen to suggest it.
    seen, team_issues = set(), []
    for i in issues:
        if i.get("contextId") not in member_ids:
            continue
        key = i.get("key")
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        team_issues.append(i)
    # Remaining work is the selected context's, never the team's — the sample is
    # wide, the outstanding count is narrow. A rollup's "selected context" is
    # every sprint it spans.
    remaining_ids = ({c["id"] for c in roll_members} if roll_members else {cid})
    actual_remaining = len([i for i in issues
                            if i.get("contextId") in remaining_ids
                            and (i.get("statusCategory") or "") != "Done"])
    # An asked-for item count or date replaces the sprint's own, so the same
    # history can answer "what if it were 30 items" or "what about by then".
    # The defaults are still reported, so the tile can show what was swapped.
    remaining = actual_remaining if items is None else items
    as_of = ctx.get("asOfDate") or ctx.get("endDate")
    # A window's end date is today, not a deadline. Passed through as one it
    # became the forecast's default target, so "will this land by the end of
    # the period" was asked against an end that is always now — and answered
    # **0%**, in a tile whose whole job is to say when work will land. A
    # probability of nought is a number a reader can quote, and it was quoting
    # a deadline nobody set. ADR 0011: a window bounds a selection and is not a
    # clock, and that has to hold in the forecaster as much as on the page.
    is_window = ctx.get("kind") == "window"
    meta = {"sprintName": ctx.get("sprintName"), "startDate": ctx.get("startDate"),
            "endDate": None if is_window else ctx.get("endDate"), "asOfDate": as_of,
            "workingDays": [] if is_window else ctx.get("workingDays")}
    # The bundle's own config, carried onto the slice. Building this dict
    # without it would forecast the customer's board against a calendar they do
    # not keep — a different answer, arrived at silently, from the same data.
    # A reader's issue-type selection narrows the organisation's rule; it never
    # widens it. Expressed as a config rather than as a filter here, so
    # `counted_issues` stays the one implementation and `inputs.counting`
    # reports what was actually counted rather than the site's default. A type
    # the site does not count is not made countable by somebody ticking it.
    eff_cfg = dict(org_cfg or {})
    if types:
        asked = [str(t).strip() for t in types if str(t).strip()]
        site = [str(t).strip() for t in (eff_cfg.get("countedTypes") or [])
                if str(t).strip()]
        if site:
            low = {t.lower() for t in site}
            asked = [t for t in asked if t.lower() in low]
        # An empty intersection is a selection of nothing, which is a refusal
        # rather than a silent fall back to everything — ADR 0010.
        eff_cfg["countedTypes"] = asked or ["\u0000none"]

    ds = {"issues": team_issues, "meta": meta,
          "orgConfig": eff_cfg,
          "releases": (byContext.get(cid) or {}).get("releases", [])}
    # A window has no end to fall back to, so a caller who names no date gets
    # no date — not today dressed up as a deadline. The `meta` above says the
    # same thing, and this line has to agree with it: it is the one the tool
    # actually reads, and setting only the other left the tile answering
    # "0% by 2026-08-10" for a board that set no deadline at all.
    eff_target = target if is_window else (target or ctx.get("endDate"))
    out = FC.build(ds, as_of=as_of, remaining=remaining, target=eff_target)
    out["asked"] = {
        "items": items, "date": target,
        "default_items": actual_remaining,
        "default_date": None if is_window else ctx.get("endDate"),
        "as_of": as_of,
    }
    resolved = sorted(x for x in (FC._d(i["resolved"]) for i in team_issues
                                  if i.get("resolved")) if x)
    out["sampled_from"] = {
        "slice": slice_label,
        "contexts": len(members),
        "first_resolved": resolved[0].isoformat() if resolved else None,
        "last_resolved": resolved[-1].isoformat() if resolved else None,
    }
    # The falsifiable claims this forecast makes, for the log — roadmap item 4c,
    # ADR 0017. Emitted here, from the same computation that produced the
    # figures, so a logged claim and the tile above it cannot disagree.
    #
    # **Only the default forecast.** The tile lets a reader ask "what if it were
    # twenty items, or the end of the month?", and a what-if is not a published
    # prediction — nobody said it. It is also not merely untidy to log one:
    # `claim_id` is keyed on context, day and percentile, so a what-if with a
    # different target would take the same id as the day's real forecast and
    # overwrite it, replacing a claim somebody made with one nobody did.
    #
    # The width the forecast sampled at travels with the claim. A reader who can
    # see ten of a board's forty issues forecasts a smaller board, and a claim
    # from that view stored as the board's would score the forecaster on a
    # prediction it never made about the whole of it. ADR 0019.
    out["claims"] = (
        FC.claims_from(out.get("capacity_to_target"), cid, ctx.get("boardId"),
                       as_of, ctx.get("boardName") or ctx.get("team"),
                       len(team_issues))
        if items is None and target is None else [])
    out["issuesSeen"] = len(team_issues)
    return out


