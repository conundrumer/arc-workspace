# c920a713

## Departures
- I did not store the concept file's `center` parameter (top). The program states the nesting directly: ring k from the center holds the outline that has k outlines above it. The reasons: no lib type holds "an end of the stack", and [Types](docs/handbook/solver-file.md#types) bans defining one. Also, no D4 element or color permutation changes the value, so under [Invariance](docs/handbook/principles.md#invariance) it is a way of combining content rather than task data. A variant that reverses the nesting would need another program.
- The concept branches' constructors are names I chose: `Drop` (conflict-resolution) and `Total` (unordered-outlines). `record --all` rewrote the witness file's names to the listed forms: `concept` → `$Total` in `apart`, and `concept`/`$Majority`/`$EachExtension` → `background=stored` in `background=DominantColor`. The grids are unchanged.
- I added a Determine relation for `background` that `analyze.md` does not give: a color of the inputs that no train output shows. The determination plan asked for it, and its only other derivation is the `@derive DominantColor` branch.

## Judgments
- `$KeepConflicts` has no constructor. `analyze.md` gives it no witness, and it fails Fit at train2.
- Not formed, Develop step 3: no item yields a case.
    - Crossings-only fails Fit, checked with a scratch script. At train0, outlines 2 and 5 are left unordered. At train2, it closes the cycle 4 ↔ 9.
    - The chain reading takes both directions of train2's conflicted pair 4/9 as steps, so it closes a cycle and fails Fit there.
    - The remaining items fail Fit as `analyze.md` states.
- `derive` reported `background=DominantColor`, so it has a `@derive DominantColor: variant concept` line, following `analyze.md`. Its witness is the one `analyze.md` gives.
- `store` reported `strip.extent[a]` as constant. That set is every `Axis` value, `store` printed no directive, and no branch was held.
- Hints:
    - single-consumer on `extension` and `center`: both inlined into their one consumer.
    - negated-use on `Determine.shown`: inlined as `!ex_out(_, _, Col)`.
- Deletions:
    - Dropped: `loose`'s colour columns (it is now keyed by `Conflict` alone).
    - Removed: the `seat` bounds (two `Tally` counts of outlines above and below each outline). They only restated what injectivity plus `misplaced` already give, so `ties.cand` now offers every ring to every outline.
    - Kept: `loose` and `!loose`, which the train pairs never trigger but which `apart` needs, and the bound enumerator `dir_elem`.
- Performance: without the bounds, `TiebreakResolutions` enumerates n^n seatings. On a cold run, test0's 7 outlines took 18 s, against 1 s with the bounds. An input with 8 or more outlines would be very slow. I kept the principled form, since this task's inputs still run.
- Output frame: the side 2n-1 comes from rings, not arithmetic. An `AxisFrame` of extent n (the outline count) gives the ring numbers. The center cell is `uniform_inset` at the outermost ring number. Each ring is drawn by two `jump`s from the center. This follows 89565ca0's precedent of a `Frame2D` extent taken from a `Tally` and `R <= K` comparisons.
- An undefined case writes no `out` fact. Cycles kill every seating through `misplaced`. The concept gates on `!loose(X)` for `one-stack`.
- `layer-order` keeps the restated generator rule, with the concept file's text under `@approximated:`. Why it has no relational form:
    - The generator's order comes from whole rectangles, including a side hidden entirely under other outlines.
    - The visible cells do not fix where such a side lies.
    - Recovering it means searching over joint rectangle placements and drawing orders consistent with the image. Clauses over visible cells only approximate this by taking the colour's bounding-box border.
- `witness --file programs/reports/c920a713/witnesses.json` prints, under `hidden-side`, that the concept case is undefined where the judged output is a grid. That is the approximation's disagreement that `analyze.md` records (verdict `other`), not a departure.
- Keywords: `color-class bbox occlude rank rings`.

## Unsettled
- The audit skipped one check: its store check did not check `ties.assign` (over 20000 rows on an input). It stays open until a store check can handle a relation that large.
- Whether the restated `layer-order` has a relational form after all, as a Datalog search over candidate rectangles per colour and drawing orders: settled by building such clauses or showing that a needed form is banned.
- Performance above 7 outlines: settled by a lib construction that enumerates the linear extensions of a partial order directly.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
