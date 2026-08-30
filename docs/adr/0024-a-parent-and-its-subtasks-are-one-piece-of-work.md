# 0024 — A parent and its subtasks are one piece of work

Roadmap item 7's second half is intake sequencing, and it has been refused on
Forge since it was built because nobody had decided **what an ask is inside
Jira**. The answer, given 2026-08-29: *an ask is an issue type* — sequencing is
valid at user-story level and at epic level — *and a selectable issue type
filter over the overall data is required, for example to remove subtasks,
because it is normally the parent that should be counted.*

The second half of that sentence turned out to be the larger finding, and it is
not about sequencing at all.

## What was wrong

**Nothing in this product excluded subtasks, and nothing recorded whether an
issue was one.** The fetcher's projection kept the issue type's *name* and no
more; the Forge projection did the same. No consumer filtered on it. So on any
board whose sprints contain subtasks, **every figure denominated in items
counted them**: throughput, commitment, completion percentage, the Monte Carlo's
sample, the durable series, the forecast log's claims.

A parent and its three subtasks are one piece of work and four rows. Counted, a
team that breaks work down finely reports several times the throughput of one
that does not, and every item-denominated figure moves with a *habit* rather
than with delivery. Item counting was chosen over story points precisely because
it *"cannot be inflated by estimating generously"* — and it could be inflated by
decomposing generously, which nobody had noticed.

**And the product could not say whether its own counts included them.** Whether
subtasks arrive at all depends on the board type and on the route: the Agile
sprint and board endpoints often omit them, team-managed projects omit them from
sprint-filtered JQL, and the fetcher's `--jira-jql` path is raw JQL against
`/rest/api/3/search`, which returns whatever the query asks for. So two
customers on two board types got two different definitions of throughput from
the same product, with nothing on either screen saying which.

That is worse than a consistent overcount. A wrong number that is wrong the same
way everywhere can be found; one that varies with a configuration nobody looks
at cannot.

## The decision

**Which issues count as items is the organisation's answer, it travels inside
the dataset like every other assumption, and subtasks do not count by default.**

`orgConfig` gains two keys, validated in Python and mirrored in
`forge/src/jira.js` as every other setting is:

- **`countSubtasks`**, default `false`. The user's own framing: normally it is
  the parent that should be counted.
- **`countedTypes`**, an allow-list of issue type names, default empty meaning
  *every type the first rule left*. Empty is the right default because naming
  the types means naming them per site, and a site that added one would silently
  stop counting it — a smaller number appearing for a reason nobody could see.

`orgconfig.counted_issues()` is the one implementation, and `countedIssues()` in
`src/app.js` mirrors it because the browser cannot call Python — the same
arrangement the working week already has, and `tests/test_agent.py` holds the
page's figures against the tools'. Change one, change both.

**Jira's own flag, not a guess from the name.** `issuetype.subtask` is recorded
on every issue by both producers. A site can call a subtask anything, and
matching on the word would count a type called "Subtask Review" and miss one
called "Step".

**Absent means not a subtask.** Every dataset written before this carries no
flag, and reading absence as "subtask" would empty them.

**`type` and `isSubtask` reach the calculator.** They had to: the *tools* apply
the rule, so the tools must see it. Neither is free text and neither identifies
a person — `type` is a Jira configuration label like `status`, which was already
in `CALC_FIELDS`.

**Nothing is dropped silently.** `facts.meta.counting` and
`forecast.inputs.counting` report what was seen, what was counted and what was
not, *whether or not anything was excluded* — a key that appears only sometimes
is read as meaning nothing when it is absent.

## What it costs

**Figures move on boards that carry subtasks**, and they move down. That is the
correction, not a regression: the earlier numbers counted one piece of work
several times. Anyone comparing a report from before this to one from after will
see a drop that no team caused, which is exactly why the counting basis is now
reported beside the figures rather than assumed.

**A second implementation of the rule**, in JavaScript, for the page. The
alternative — the producer filtering before writing the dataset — was rejected
because it discards the raw issues, so changing the config would need a refetch,
and a bundle could never be re-read under a different answer.

## The reader's own selection, added the same day

The organisation decides what is *countable*; a reader chooses among what is
left. The filter in the page's own row lists the types **this board actually
uses**, read off the loaded issues rather than from what Jira could return — a
board that has never raised a Bug should not offer Bug, and a site that invents
a type next week should offer it without anybody editing code.

Three things about it are decisions rather than styling.

**It changes what is counted, not only what is listed**, which makes it unlike
its neighbours in that row. And because the forecast is computed where the page
is not, **the selection travels with the forecast request** and is part of the
cache key on both sides. Without that the tiles would count one set of issues
and the forecast another — both correct, disagreeing, with nothing on screen
saying which was which.

**A reader's selection narrows the organisation's rule and never widens it.**
Expressed as an effective config rather than as a filter, so `counted_issues`
stays the one implementation and `inputs.counting` reports what was actually
counted rather than the site's default. Ticking a type the site excludes does
not make it countable, so types the site excludes are not offered — and the
reason is printed under the list rather than left as an absence.

**Selecting nothing is a refusal.** `null` means no restriction; an empty list
means the reader unticked everything, and the page says the evidence is absent
rather than quietly showing all of them or reporting zero. ADR 0010.

## What this does not do

**It does not answer what an ask is for sequencing.** That is the rest of the
decision above — an ask is an issue type, at story level or epic level — and it
needs a place to name those types and a Forge route that reads them. This record
is the filter that had to exist first, because sequencing over data that
double-counts is sequencing over the wrong numbers.

**It does not roll subtask work up to parents.** A parent with three subtasks
counts as one item, and the subtasks' story points, cycle times and completion
dates are not folded into it. That would be a different and much stronger claim
about what a parent's dates mean, and it needs its own record.

## What this rules out

**Guessing subtask-ness from the type's name.**

**Filtering in the producer.** The raw issues stay; the rule is applied where
the figures are made, so a config change re-derives without a refetch.

**A default that counts subtasks.** It would be the compatible choice and it
would mean the product's headline unit stays inflatable by a working habit.
