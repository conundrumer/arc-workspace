# ae58858e

## Concept
- The concept case fits every pair. It recolors to `new_color` (6) each 4-connected shape of `shape_color` (2) with at least `min_size` (4) cells, and keeps every other cell. The kept shapes in the pairs have 1 to 3 cells, and the recolored shapes have 4 to 8 cells, so the pairs fix `min_size` at 4.
- The rule has a relational form, and the generator applies it as written. No witness has the verdict `other`.

## Choice points
- `adjacency`
    - `concept`: shape cells join across a shared side (4-adjacency).
    - `$Diagonal`: replaces `scattered-shapes` and `recolor-large`: shape cells also join at a corner (8-adjacency); same parameters; defined on every input. It fits every pair. Witness `diagonal-contact`: two dominoes of color 2 meet at one corner, and `$Diagonal` recolors them as one 4-cell shape. It breaks no scene claim; plausibility `ordinary` (the inputs place pieces in corner contact, in train1 at (8,7)/(9,6) and in train3 at (5,3)/(6,2)); verdict `concept`.
- `shape-cells`
    - `concept`: the shape cells are the cells of the stored `shape_color`.
    - `shape_color=RarestColor`: replaces the stored `shape_color` by the rarest color of the input; undefined where colors tie for the fewest cells. It fits every pair. Witness `shape_color=RarestColor`: cells of color 2 outnumber the 0 cells, so the derived color is 0 and the large 0 regions turn 6. It breaks no scene claim; plausibility `borderline`; verdict `concept`. Invariant broken: in every input, color 2 has fewer cells than 0.
    - `shape_color=DominantColor`: replaces the stored `shape_color` by the commonest color of the input (0). It fails Fit at train0.
    - `shape_color=SharedColor`: replaces the stored `shape_color` by every color of the input (0 and 2). It fails Fit at train0.
    - `$Foreground`: replaces `scattered-shapes` and the parameter `shape_color` by a parameter `bg` (0): the shapes are the same-color 4-connected groups of every color other than `bg`; defined on every input. It fits every pair. Witness `other-color-shape`: a 4-cell shape of color 3 beside shapes of color 2, which `$Foreground` turns 6. It breaks `scattered-shapes` (shapes of one color); plausibility `variant`; verdict `$Foreground`. Invariant broken: every input holds only the colors 0 and 2.
        - `color-mixing`
            - `concept`: a shape is a group of one color.
            - `$Multicolor`: replaces the per-color groups by the 4-connected groups of non-`bg` cells of any colors; defined on every input. It fits every pair. Witness `two-color-contact`: a domino of color 2 lies on a domino of color 3, and `$Multicolor` recolors both as one 4-cell shape. It breaks `scattered-shapes`; plausibility `borderline`; verdict `concept` (the output of `$Foreground` is the same there). Invariant broken: every input holds only the colors 0 and 2.
- `recolor-test`
    - `concept`: a shape recolors when its cell count is at least `min_size`.
    - `$SizeTable`: replaces `recolor-large` by a lookup table from a shape's cell count to recolor or keep: `size_recolor` {4, 5, 6, 7, 8} and `size_keep` {1, 2, 3}, read from the train pairs; undefined on an input with a shape whose count neither set holds. It fits every pair: the test counts 4 and 5 are in `size_recolor`. Witness `unseen-size`: a 9-cell block of color 2, at the assignment that adds 9 to `size_keep`, where the table keeps the block. It breaks no scene claim; plausibility `ordinary` (train1 has an 8-cell shape); verdict `concept`.
- `new-color`
    - `concept`: the stored `new_color`.
    - `new_color=OutNewColor`: derives `new_color` from the train outputs, which a run on one input does not have, so it gives no value and the branch is undefined on every input. It fails Fit at train0.
    - `new_color=AnyOutNewColor`: as `new_color=OutNewColor`. It fails Fit at train0.
- `adjacency` & `shape-cells`, `adjacency` & `recolor-test`, `adjacency` & `new-color`, `shape-cells` & `recolor-test`, `shape-cells` & `new-color`, `recolor-test` & `new-color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A recolor table keyed by shape color in place of `shape_color` and `new_color`: every task of the generator has one shape color, so the table has one row, and it is equivalent to the concept case.
- A recolor test of "more than 3 cells" in place of "at least 4 cells": the same model with the threshold stored one lower, equivalent to the concept case.
- A recolor test by bounding box (at least 2×2, or area at least 4) or by shape (not a straight line): the 3-cell L of train3 at (1,1), (1,2), (2,2) has a 2×2 box and bends, and it stays 2, so each fails Fit at train3.
- A `@derive` branch on `min_size`: the number proposers in `programs/proposers.dl` read grid extents, periods, tile counts and separator tilings, and none counts a shape's cells. `ConstInDim` on train2 (6×6) gives 6, under which the 4-cell shapes of train2 stay 2, so it fails Fit there.

## Tickets filed
- 10-112_task_ae58858e_analyze.md
