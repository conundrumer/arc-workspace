# dd6b8c4b

## Departures
- The witness file adds the `center=RarestColor`, `box=stored` and `capacity.tally=stored` witnesses that `derive` and `store` wrote, and `box-moved`, which separates `box=stored` from `center=RarestColor`: `witness` reported that no witness separated that pair of cases, and a box away from the grid's center shows the difference.
- The case `$WalkFromCenter` (with `$TieUndefined`) stays in the solver, though `analyze.md` says it fails Subsumption under `$WalkFromCenter & $TieReading`: it stands for the branch's model, so it is a witnessed case, and `witness` reports no case that no run shows defined and differing. On `center-breaks-tie` it is defined and differs from the concept case, which is undefined there.
- `$TieReading` breaks ties by `fill_corner` and `fill_axis`, the same parameters as the fill order: `analyze.md` gives the tie rule as reading order, which is the stored fill order, and the Analyze files give no separate parameter for it.

## Judgments
- The take rule is encoded without a tiebreak in the concept case: the marks are ranked by walk distance with ties sharing a rank (`Order` score form), a mark is taken when the marks no farther than it fit in the box, it is left when the strictly nearer marks already fill the box, and neither holds for a mark in a tie group that the cut splits. That cell then gets no `out` fact, so the concept case is undefined there, as `analyze.md` states. `$TieReading` adds the reading rank as `secondary_score`, which makes the order total, so no group is split.
- The box cells that fill are counted, not matched to marks: a box cell of fill rank k takes the mark when more than k marks are reached. This gives the concept's output whether or not ties fall inside the taken set.
- Comparisons of a rank or a count against another count (`E <= N`, `R >= N`, `K < N`) are bound comparisons, as in 28a6681f.
- `@derive RarestColor` on `center`: the witness swaps 2 and 0 in train 1. A color permutation of the center gives it, so plausibility is `variant`; the generator fills the 0 center as a box cell, so the verdict is `derived`. It breaks the `box` scene claim at the stored assignment (no `center` 2 cell), hence `@relaxed box`.
- `@store` on `box` (`variant stored`, `@relaxed box`): the same color-swap witness; the stored box fills all nine cells, as the generator does. `box-moved` is a further witness, `ordinary` (a box away from the center breaks no scene claim) with verdict `concept`.
- `@store tally` on `capacity` (`variant center=RarestColor`, `@relaxed box`): on the color-swap witness the stored count takes nine marks into eight box cells, while the generator fills nine cells, which `center=RarestColor` gives.
- `capacity.item` has `@ignore item: store`: the program reads only the box's cell count, so storing the cell set is equivalent to `capacity.tally=stored`, and that case fails Equivalence.
- `walk.seed` has `@ignore seed: store`: `store` reported that no witnessed case takes a stored seed.
- Determination: `mark` is the color that both leaves and enters cells, `bg` is what a mark becomes, the box colors are those that become the mark, and `center` is the box color with a cell that has no neighbor outside the box. A `wall` relation and a fit test for `fill_corner`/`fill_axis` drew the `determine prediction` hint (a test that reads inputs and outputs together), so they were removed and the runner's enumeration determines those three; the plan reports 1 of 8 joint assignments fitting every train pair.
- Deletions: `!params.wall(C1)` and `!params.wall(C2)` in `walk.edge` are each redundant alone, as a walk that can neither enter nor leave a wall needs only one of them, but together they state "through cells that are not wall", so both stay. The `reading` instance and `secondary_score` are `$TieReading`'s and no pair has a tie at the cut. `dist(P, D, 0)` in `box_rim` and `boxlike(C)` in `center` stay for the meaning. `reached.domain` and `!mark(C)` in `boxlike` were removed.
- Keywords: `flood` (the walk through gaps), `rank` (nearest first), `count` (as many as the box holds), `move` (marks move into the box).
- Not formed items of `analyze.md` each fail Fit at a train pair, so no branch was added for them.

## Unsettled
- The audit's relabelings check fails: "line 71: `box` is not one value on every input at the case values the cases that take its `@store` branch hold; it differs on train 1", while `store` reports `box` as one cell set on every input. Settling it needs the relabeling and case at which `box` differs, which the output does not give.
- The last `determination-plan` run lists `fill_axis`, `fill_corner` (pairs-exact) and `wall` (UnchangedColor) under "write a determination relation for each value here that a proposer derives from a fact other than any the concept derives it from". The concept derives none of them from such a fact, so no relation was written; the plan run cap was reached.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
