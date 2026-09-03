# An empty selection is a refusal, not a zero

When the selected context contains no issues, the tiles that would state a figure about them print a refusal instead. They do not print zero, they do not print a dash in place of one figure while the tile around it keeps its others, and they do not fall through to whatever their divide-by-zero guard returns.

This is [ADR 0007](0007-refuse-rather-than-widen.md) applied to the page rather than the tools. The forecaster already refuses below its thresholds because a wide interval still carries a number a reader can quote. A share of nothing is the same failure with none of the ceremony: the denominator is empty, the guard supplies a plausible value, and the result is indistinguishable on screen from a measurement.

## What it was

`derive()` scored sprint health from four weighted components, each a share of the selected issues. Over an empty selection every one of them collapsed to a fallback that reads as good news — no blockers among nothing, no ageing work among nothing, no scope growth on nothing — because `Math.max(items.length, 1)` and `? … : 0` exist to keep the arithmetic finite, not to say what happened. Delivery pace contributed its neutral zero, the four weights summed, and the header printed **Sprint health: Needs attention (66/100)** in an amber chip for a page with nothing on it.

Sixty-six is the worst possible number to have landed on. Zero would have looked broken and a hundred would have looked absurd; 66 out of 100 looks like the output of a calculation, in a band with a verdict attached, sitting in the most prominent chip on the page.

It was not the only one. The executive card opened *"0 of 0 items are done (0%)"*. The KPI strip printed eight tiles of zeros, four of them shares with an empty denominator. The ageing chart printed *"Nothing open has outlived a sprint. That is the healthy state."* The value card printed a `$0` hero. The risk register reported *"No risks triggered against the current filters"* — a finding, over nothing examined.

## Why it is not a corner case

The Forge build opens in exactly this state and may never leave it. `forge/seed.json` carries no issues on purpose ([ADR 0009](0009-one-contract-two-transports.md)), the page renders before the bridge answers, and it renders the same way for good if the bridge fails. So the empty selection is not the state a developer sees for half a second with a broken fixture — for a customer opening the app for the first time inside their own Jira, it may be the only state they ever see, and it was telling them their sprint needed attention.

The same arithmetic is reachable without Forge. The score is computed over the *filtered* items, so a search box matching nothing produces it too.

## Where the line is

Counts of an empty set that are honestly nil keep their nil. What refuses is the figure with no denominator behind it, and the claim that depends on having looked.

That distinction is why the ageing chart's sentence is not simply deleted. With issues present and none of them open, *"Nothing open has outlived a sprint. That is the healthy state"* is true and worth saying. It is only false when there was never anything to age. The same holds for the risk register: no risks triggered against thirty issues is a finding; against none it is silence.

## The same rule one level down: inside the score

A composite figure has the same problem in miniature, and the health score had it twice.

**A component that could not be measured is dropped from the composition, not scored zero.** Delivery pace carries 0.34 of the four weights — the largest, and the only forward-looking one. Over a sprint whose dates were unknown it scored 0/100, which took the sample sprint from 52 and *Needs attention* to 22 and *Off track*. A zero is a finding. "We do not know when this sprint runs" is not a finding about delivery, and it should not be able to change the colour of the chip.

The measured components are re-weighted to sum to one, so what is reported is the honest score of what could be taken rather than that score capped by the weight of what could not. That makes it a different quantity from a four-component score, so the chip says `3 of 4 measures` and the disclosure prints the weights that actually multiplied — 33%, not the nominal 22%. This is the *no silent caps* rule: a composition that bounds itself must say what it dropped.

**Below half the weight, the score refuses.** Two of the four components read work volume, so in points over a dataset nobody estimated both are undefined — and they failed in opposite directions, pace scoring 0 and scope stability scoring 100/100 for "no mid-sprint additions" out of nothing. What survives is blockers and ageing work, which describe hygiene rather than whether the sprint will land. Calling that "sprint health" is a claim the remainder cannot carry.

**And the disclosure has to name the right cause.** All three of those situations printed *"no sprint calendar"*, including a rollup that has dates and a points view whose calendar was present and complete. The disclosure exists so a reader can argue with the method; one that names the wrong cause sends them to fix the wrong thing. There are three causes and there are now three sentences.

### Where the calendar actually went

Most of those missing calendars were not missing. `forge/src/jira.js` sends no `workingDays`, deliberately — which days are worked is organisation config, and resolving it in a resolver would be a fourth opinion arriving by a fourth route. But the page holds that config and already derives `statusCategory` from it for exactly the same reason, so it derives the day list too. Until it did, every sprint in a Forge tenant lost the largest component of its score, *Pace vs clock* read `—` across the whole install, and the two transports rendered different figures from the same sprint — the thing [ADR 0009](0009-one-contract-two-transports.md) exists to prevent, invisible to its parity test because that test feeds the bridge the loopback's own bodies.

A rollup keeps its empty list. Its dates span every sprint in it, so a derived list would be perfectly real and would describe nothing: *how far through nineteen sprints are we* is not a pace, and it would compute to a confident number.

## What it rules out

**A single "no data" banner over the grid.** It would have been fewer lines and it would have passed any test written against the score alone. It also throws away the two things the page still knows — that it has zero issues, and which tiles were already refusing for their own reasons (no burndown series, no assignees, no live connection). A tile that says why it in particular has nothing to show is the product; a banner is a loading state.

**Dimming instead of saying.** The grid used to be faded to 0.45 opacity over an empty context, which was the honest instinct reached through the only channel that could not carry the reason. Once the tiles state their condition in words, fading them puts the only text on the page below the AA contrast floor. The fade is gone. The same channel reopened once through typography rather than opacity: the KPI band's refusal was printed as an 11.5px muted note, the smallest text on the page, while the forecast tile's was set in the callout with the rule and the wash. A refusal is a statement, and every one of them is now set in the one callout (1.79.0), so a reader cannot tell a tile that refused from a tile that is loading by how quietly it was printed.

**Scoring the gap instead of dropping it.** Zero was one option and a neutral 0.5 was the other. Zero is a penalty for missing data; 0.5 is a figure nobody measured, placed in the middle of a scale so it moves the answer while looking like it does not. Neither is available to a reader who wants to know what was measured.

**A softened sentence.** The refusals end in *the evidence is absent, not noisy*, the same clause the tools use, and for the same reason: it is the part that says waiting or widening will not fill this in. `tests/e2e.py` asserts the clause survives, and separately sweeps those tiles for digits — so a later change that reinstates a figure fails whether or not it kept the words.
