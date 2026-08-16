# Review of the Sprint 24 dashboard — what's wrong and what changed

A read of the screenshot you sent, then what the replacement does differently. Ordered by how much damage each problem does.

---

## 1. Three different "done" numbers on one screen

The screenshot says **Done 13**, **Tasks Done 15/22**, and **Work Complete 9/22**, all visible at once. An executive who notices this stops trusting every other number on the page, and they are right to.

**Changed:** one completion figure, stated in both items and story points, computed from a single field. If two numbers on the page disagree, it is now a data problem, not a definition problem.

## 2. The burndown hides the thing it exists to reveal

The chart shows a line falling behind the guideline. It does not show that four issues were added mid-sprint. So the chart says "this team is slow" when the data says "this team was given more work". Those are opposite conversations and the original merges them.

**Changed:** a second orange line for total scope, a marker on the day scope changed, and a labelled callout showing how many points arrived. The delivery line and the scope line are now separable at a glance.

## 3. "Scope Added 4 — impact under review" is a placeholder pretending to be a metric

Four *what*? A one-line copy tweak and an 8-point hotfix are both "1". Counting items instead of points is the most common way scope change gets understated.

**Changed:** scope shown in story points with the percentage growth, and every added item listed one click away.

## 4. Nothing on the page can be inspected

Every tile is a dead end. The only way to answer "which three are blocked?" is to leave the dashboard and search Jira — which is what people actually do, which is why dashboards like this quietly stop being opened.

**Changed:** every tile, bar, band and risk opens a side panel listing the underlying issues with owner, points, age, elapsed-time breakdown and a deep link back to Jira. Any panel exports to CSV.

## 5. The assignee donut is the wrong chart

Four slices at 27%, 23%, 23%, 27%. A donut exists to show part-to-whole *at a glance*; when the parts are within four points of each other it communicates nothing that four numbers wouldn't. It also colours a person red, which reads as a judgement about that person.

**Changed:** a horizontal stacked bar per person, split done / in progress / not started, using one blue ramp so no colour implies blame. The useful signal — someone with a tall in-progress block — is now visible, and it wasn't before.

## 6. The lead-time chart and the lead-time table say the same thing twice

Roughly a fifth of the screen shows one dataset in two forms, and neither answers the question the metric exists for.

**Changed:** one chart, restructured. Each closed item is a single bar of total elapsed time, split into *waiting in a queue* and *actively being worked*. On your demo numbers, **22% of elapsed time was active work** — meaning the other 78% is queueing. That is the single largest and cheapest improvement available to the team, and the original dashboard renders it invisible by charting lead and cycle as two separate bars nobody subtracts.

## 7. Age bands of 0–30 / 31–60 / 61–90 days on a two-week sprint

Everything lands in the first bucket, so the chart is decorative.

**Changed:** bands of 0–7 / 8–14 / 15–30 / over 30 days, so "has this survived a full sprint?" becomes readable. Ageing is a better predictor of work never finishing than priority is, and this is where you see it.

## 8. "Overall Health: Amber" with no method

Nobody can challenge it, so nobody believes it, so it gets ignored. Same for the unlabelled 43/39/22% bar — three numbers with no stated units summing to 100 of something.

**Changed:** a single score with the full working exposed on hover — four weighted components, each with its weight, its sub-score and the sentence explaining it. Argue with the method, not the colour.

## 9. "$86,000 delivered this sprint" with no methodology

The first question any CFO asks is "says who, and does that appear in the accounts?" The original has no answer.

**Changed:** the figure is labelled an estimate, each contributing item shows its basis line ("1,340 abandoned checkouts/mo × $39 AOV recovered"), and the card states how many completed items carry *no* estimate — so the number reads as a floor rather than a total. Unattributed value claims are how a reporting pack loses its credibility in one meeting.

## 10. Output per person and overtime share a card

Two series with different units in one visual frame invites the reader to infer a relationship the data doesn't establish. Any chart with two y-scales is doing this on purpose.

**Changed, then changed again.** The first replacement split them into two charts on their own scales. Both series have since been removed entirely: this organisation does not operate overtime, so charting hours implied a time-tracking regime that does not exist — and output-per-person, with its counterweight gone, is a productivity-per-head number that has no place on a dashboard which does not measure people.

The card is now **Team load**: work in progress, and work that arrived after planning. Both come from issue status alone, and together they answer what the original card was reaching for by proxy — is this team being overloaded or interrupted?

## 11. The "Executive AI Advice" panel is static prose

It reads well and links to nothing. It will also be wrong the moment the data moves, because nothing regenerates it.

**Changed:** the risk register is computed from the current dataset — including the current *filtered* dataset — with a severity, a "do this" action, and a link to the issues. Filter to one person and the risks recompute for that person.

## 12. Missing entirely: is the commitment realistic?

Your history shows six sprints averaging ~37 completed points, and Sprint 24 committing 77. That team will "fail" a sprint it is delivering normally in. Nothing on the original dashboard surfaces this, so the conversation never happens.

**Changed:** a predictability card showing committed vs completed with a hit-rate percentage per sprint, plus the trailing three-sprint average as the recommended next commitment. It also appears as a risk and in the executive summary.

---

## Smaller things also fixed

- **No accessibility path.** Status was colour-only. Now every status chip carries an icon and a word, every chart has a table view, and the palette was validated for colour-vision deficiency in both light and dark modes (adjacent-pair ΔE ≥ 8, contrast checked against both surfaces).
- **No filtering.** One filter row now scopes every chart at once — never per-chart filters, which produce charts that disagree.
- **No provenance.** A source badge states where the data came from and when it was pulled, and shows amber when the connection is not live. A dashboard that can't say how fresh it is gets treated as always-stale.
- **No dark mode, no print layout, no export.** All three now present; the palette has selected dark steps rather than an automatic inversion.
- **Metrics without direction.** A number with no comparison isn't actionable. Tiles carry a delta against the previous sprint; DORA measures carry a trend word and a sparkline.

## One thing the original did better

The eight-tile KPI strip across the top is the right instinct, and the replacement keeps it. Executives scan left to right across a single band; burying the headline inside a chart card is worse. The tiles were re-picked, not removed.
