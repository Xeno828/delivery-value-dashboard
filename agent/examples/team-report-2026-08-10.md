# Sprint 24 — team report
**as at 10 August 2026 · 12/22 items, 41/83 points `[measured]`**

## Where we actually are

- 49% of the points are complete against 60% of the sprint elapsed `[derived]` — 11 points of percentage behind the clock.
- 9 points added after kickoff: BLC-450, BLC-451, BLC-452, BLC-453 `[measured]`. That is 12% growth on the original 74.
- 42 points still open across 10 items `[measured]`.

## Forecast

Units below are **working days**; elapsed-time figures elsewhere in this report are **calendar days**.

**0.4% probability all ten open items close by 14 August** `[forecast]`. At the 85th percentile we finish **four of the ten** by the sprint end `[forecast p85]`, and all ten by 26 August.

Four items have never been started — **BLC-424, BLC-436, BLC-438, BLC-443** `[measured]`. These cannot be forecast, only scheduled: with no start date there is no cycle time to sample from. They are the realistic carry-over. Decide now whether they carry or get cut, rather than discovering it on the 14th.

## Unblock first

1. **BLC-429** — inventory sync race condition oversells limited stock. Open 21 days, overdue since 7 August, flagged, highest priority, and the blocker on v2.2.0 `[measured]`. Blocked on an external dependency. This needs a named person outside the team and a date, or it should leave the sprint.
2. **BLC-441** — saved cards not shown for returning customers. In review, flagged `[measured]`. Sitting in review is queue time, not work.
3. **BLC-421** — refund webhook fires twice. In review, flagged, external dependency `[measured]`.

Three flagged items is 14% of the sprint consuming stand-up attention while producing nothing.

## Ageing

Cycle time p50 6.0 / p85 14.0 working days · end-to-end p50 11.0 / p85 17.8 `[measured]`.

- **BLC-438** — 29 working days alive, never started. Past the 85th percentile end-to-end with zero active time. The delay is entirely upstream of the team.
- **BLC-436** — 15 days alive, never started. Same shape. It is also the accessibility compliance item.
- **BLC-429** — 4 active days, 15 alive. Active time is normal; the queue before it was not.

That pattern — normal active time, excessive end-to-end time — is the report. The team is not slow. The work waits.

## Flow

- Cycle time p50 2.0 / p85 3.0 calendar days on items closed this sprint `[measured]`
- **21.9% of elapsed time on closed items was active work** `[derived]` — the other 78% was queueing
- The largest single queue is the gap between an item being raised and being picked up `[judgement]` — four items have sat there for the whole sprint

## What to commit to next sprint

**11 items** `[forecast p85]` — the 85%-confidence figure from 20,000 simulated ten-day sprints. The median is 14, which is a coin flip by construction: commit there and you miss half the time on purpose.

Trailing three-sprint average completed: **9 items** `[measured]`. This sprint committed 18 items — 100% above it `[derived]`. In points the same story reads 77 committed against a 35.7 average, 116% over.

Commit 11, including the carry-over decided above. A team that reliably delivers 11 is more useful than one that swings between 8 and 13 while being told it missed 18.

**Size-stability check: safe** `[measured]`. Cycle time p85 is 2.33x the median, and the throughput rise across the window is not explained by items getting smaller. Item counting is a valid unit for this team — if that changes, the forecasts above become provisional and this line will say so.

## Everything open, by owner

| Owner | Open items | Open points | Oldest open |
|---|---|---|---|
| Sam Okafor | 3 | 11 | BLC-438 (41d) |
| Jordan Lee | 3 | 13 | BLC-436 (23d) |
| Priya Nair | 3 | 10 | BLC-433 (14d) |
| Alex Rivera | 2 | 13 | BLC-429 (21d) |

*Ownership counts only. No ranking, and no throughput attributed to an individual — throughput is a property of the system, not the person.*
