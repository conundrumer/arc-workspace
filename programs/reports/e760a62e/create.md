# e760a62e

## Departures
- `$DerivedDivider` is not a case, and the witness `other-divider-color` is removed: the case fails Subsumption against `divider_color=SharedColor`. When `$DerivedDivider` is defined, one color fills a full row and a full column. Each full row then crosses each full column, so no full line of another color can exist. Both models then cut the same rooms and give the same output. `rows-only` shows `divider_color=SharedColor` defined where `$DerivedDivider` is undefined. `other-divider-color` (dividers in 5) duplicates the witness `derive` recorded for `divider_color=SharedColor` (dividers in 1).
- New derive branch `divider_color=SharedColor` (`@derive SharedColor: variant derived`, `@relaxed divider-tiling`): `derive` reports that it fits. In a run on one input, it gives every color of the input as a divider color. The program counts as a divider only a full line that holds one color alone, so the extra colors divide nothing that is not a uniform line.
- `$OneCrossColor` fills a room that bars of two or more colors fill: `analyze.md` says "two bar colors", and a room with three colors is also a room that bars of two colors fill.
- `$CellAligned & $DiagonalJoin` needs the dot cells on one grid diagonal and their rooms on one room diagonal, and the bar fills the rooms on that room diagonal: `analyze.md` gives only "the two branches' changes applied together".

## Judgments
- Witness `rows-only` (row dividers of 8, no column divider, 2 dots in the first and last room): plausibility `borderline`, verdict `concept`. It breaks `divider-tiling`, because it has no full column of `divider_color`. The generator would fill all three rooms, as the concept does. `$DerivedDivider` is undefined there. `divider_color=SharedColor` also takes the all-0 rows as dividers, so it fills only rows 1 and 9.
- Witness `divider_color=SharedColor` (train0 with 8 and 1 swapped): `variant derived`, because a color swap gives a variant task.
- `@ignore: derive VanishedColor`: with no train output, it gives every color of the input, as SharedColor does, so its model is equivalent to SharedColor's and fails Equivalence.
- `@ignore value: store` on `line_color`: storing the color of a full line duplicates `divider_color`, which already stores 8.
- The determination plan lists `background`, `divider_color` and `one_cross_color` as covered by proposers. No determination relation was added for them. The concept stores them and derives them from no fact. `one_cross_color`'s proposer, AnyOutNewColor, reads the same fact that the `cross_color` determination reads.
- The hints for case sections on `aligned` and `out` were right. `span` and `past` were keyed on `aligned` with the alignment field left out, so they now range over every pair of rooms on a line. Shared code stands under markers that list every branch of a point.
- The hint for one consumer on `bar` and on `new_color`: both relations were inlined.
- `deletions`: 32 deletions change nothing on the pairs. Each one removes structure for a branch (cut rooms, crowded rooms, a third dot, a dot passed through, the dot cell kept) that the pairs never instantiate, and the witnesses separate those branches. The atom `params.divider_color(Col)` in `rooms.divider` stays, because without it the concept becomes the SharedColor model. All of these deletions stay unapplied.
- The concept case is undefined on the inputs that `analyze.md` lists. A room with two cells that are not background gives no cell. A bar-filled room with no keyed color, or with three colors, gives no cell. The derived background gives no output on a tie.

## Unsettled
- `deletions` ran before the last solver edit, which inlined `new_color` in `Determine`: run `deletions` again to settle it.

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/e760a62e/analyze.md`, the `divider-color` choice point: `$DerivedDivider` is subsumed by the SharedColor derivation. Also, the line "No proposer gives 8 or 0 on every pair" under Not formed is wrong for `divider_color`, because SharedColor fits there in this program.

## Tickets filed
- none
