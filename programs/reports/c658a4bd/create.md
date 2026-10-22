# c658a4bd

## Departures
- The models of `$SideOnAxis` ([RankRings, BySide, SideOnAxis]), `$RankByBboxArea` ([RankRings, RankByBboxArea, LargerExtent]) and `bg=DominantColor` (the concept base with derived `bg`) are no case of the solver, so `witness --file work/task/c658a4bd/witnesses.json` reports those three names as denoting no case on every witness: each fails Subsumption under `$InnermostFills` at the same other branches. Where RankRings is defined, every ring has a square of its rank, so the InnermostFills fill never fires and the output is the same. `impl_choice` gives RankRings with the concept branch at every other point alone, and the `@derive` line has `@ignore: derive $RankRings`. The witnessed cases that stand for those branches are now InnermostFills and SideFromCount cases. Their `@witness` verdicts stay `concept`.
- The cases [OutlineAtSide | SolidAtSide, RankByBboxArea, *] are left out of `impl_choice`, as they fail Subsumption under the same cases with BySide. Under those two nestings the rank key picks only the frame. A square whose side is larger than the frame's side is on no ring, so those cases are undefined. So RankByBboxArea is defined only where the first square by area has the largest side, and then it has the same frame as BySide. A side tie leaves both undefined.
- Witness `one-column-left` added to the witness file. It separates `$OutlineAtSide & $SideOnAxis` and `$SolidAtSide & $SideOnAxis` from their LargerExtent cases, where no other input shows them defined and differing.
- `Determine.bg` added: the input color that a train output does not hold. The determination plan asked for a relation for `bg`, because `DominantColor` derives it from a fact the concept does not use.

## Judgments
- The concept rule has a relational form. Ring depth comes from `Rim` over the output frame, and a square's rank is the count of squares with a larger side (`Order`). Nothing is approximated.
- `$SideFromCount`: the frame is the smallest square's side as a `Frame2D`, with `uniform_outset` added by its rank (the count of larger squares) and measured with `box_extent`. That gives 2(n-1) + s without arithmetic.
- `$OutlineAtSide` and `$SolidAtSide` read a ring's side as the frame inset by the cell's depth. They are undefined where some square's side is the side of no ring (`unplaced`).
- A score tie under either rank key empties `order.elem`, so every case that reads the order is undefined there. This makes `$RankByBboxArea` undefined on an area tie, as the Analyze report gives. Under BySide it also makes the concept undefined on a side tie, which only an input that breaks `distinct-sizes` shows.
- `one-column-left`: plausibility `borderline`, verdict `$OutlineAtSide`. It breaks `sizes-step`, because the smallest square has side 3. The generator's nest 9, 7, 5, 3 leaves the center cell at background, and that is `$OutlineAtSide`'s output. The side-7 square shows all 7 of its rows, so `partly-hidden` holds. The solver has no `@witness` line for it, because it is a divergence witness between cases and stands for no branch.
- `store` lists `frame.extent[a]` and `core.extent[a]` with no witness and no line to add. Those columns are the two axes on every input, so no `@store` branch is held.
- `derive` gives `bg: DominantColor` alone, and the `@derive DominantColor: borderline concept` line records it. `side_axis` is determined by its enumerable domain (pairs-exact AXIS_H), so it has no determination relation.
- `$Components`, `$RankByCellCount`, `$BboxPerAxis`, `bg=SharedColor`, `bg=VanishedColor` and `bg=RarestColor` fail Fit, as the Analyze report gives, and are not formed. No item under Not formed states a model that fits.
- Deletions: `tie`, `unplaced`, the OutlineAtSide bg disjunct and the InnermostFills fill stay. They give each model's undefinedness or its behavior off the pairs. `area.domain` and the `impl_choice` atoms in the `frame.extent` clauses were removed: every square has cells in its own box, and the runner reads the cases from `impl_choice`.
- Lint gave no hints. No performance issue: each run finishes in a few seconds.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
