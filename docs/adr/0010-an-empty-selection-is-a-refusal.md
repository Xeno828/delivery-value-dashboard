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

## What it rules out

**A single "no data" banner over the grid.** It would have been fewer lines and it would have passed any test written against the score alone. It also throws away the two things the page still knows — that it has zero issues, and which tiles were already refusing for their own reasons (no burndown series, no assignees, no live connection). A tile that says why it in particular has nothing to show is the product; a banner is a loading state.

**Dimming instead of saying.** The grid used to be faded to 0.45 opacity over an empty context, which was the honest instinct reached through the only channel that could not carry the reason. Once the tiles state their condition in words, fading them puts the only text on the page below the AA contrast floor. The fade is gone.

**A softened sentence.** The refusals end in *the evidence is absent, not noisy*, the same clause the tools use, and for the same reason: it is the part that says waiting or widening will not fill this in. `tests/e2e.py` asserts the clause survives, and separately sweeps those tiles for digits — so a later change that reinstates a figure fails whether or not it kept the words.
