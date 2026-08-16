# {{sprint}} — team report
**as at {{as_of}} · {{items_done}}/{{items_total}} items, {{points_done}}/{{points_total}} points `[measured]`**

## Where we actually are

{{Pace against the clock, with the unit. Scope change, in points and percent. Both from the facts pack.}}

- {{x}}% of the work is complete against {{y}}% of the sprint elapsed `[derived]`
- {{n}} points added after kickoff ({{keys}}) `[measured]`

## Forecast

{{Probability against the sprint end date, then the percentile table.}} `[forecast]`
Units are **working days**; elapsed-time figures elsewhere in this report are **calendar days**.

At the 85th percentile we finish {{n}} of the {{m}} outstanding items by {{end date}} `[forecast p85]`.
The realistic carry-over is therefore {{list of keys least likely to land}} — decide now whether they carry or get cut.

## Unblock first

Ordered by what is costing the most. Each line: key, what it is waiting on, who can clear it, how long it has been waiting.

1. **{{KEY}}** — {{summary}}. Blocked {{n}} days `[measured]`. Waiting on {{named person or team}}.

## Ageing

{{Items past the 85th percentile on active time, and separately on end-to-end time.}} `[forecast]`

An item whose *active* time is normal but whose *end-to-end* time is past the 85th percentile is not a team problem — the delay is upstream, in the queue before the work started. Say which kind each one is.

## Flow

- Cycle time p50 {{a}} / p85 {{b}} calendar days `[measured]`
- {{x}}% of elapsed time on closed items was active work `[derived]` — the rest was queueing
- {{The single biggest queue, named}} `[judgement]`

## What to commit to next sprint

**{{n}} items** `[forecast p85]` — the 85%-confidence figure from `recommend_commitment`, not the median ({{m}} items, which is a coin flip by construction).

Trailing three-sprint average completed: {{a}} items `[measured]`. This sprint committed {{b}} items, {{c}}% above it `[derived]`.

Points are shown elsewhere for continuity but are not the commitment unit: six sprints supplies six point-observations, which cannot support a distribution, while the same period supplies sixty-odd item-observations.

**Size-stability check:** {{safe / suspect}} `[measured]`. {{If suspect, quote the warning verbatim and mark every forecast above as provisional.}}

## Everything open, by owner

| Owner | Open items | Open points | Oldest |
|---|---|---|---|

*Ownership counts only. No comparison between people, no ranking, no throughput attributed to an individual — throughput is a property of the system, not the person.*
