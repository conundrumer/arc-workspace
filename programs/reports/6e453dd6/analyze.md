# 6e453dd6

## Concept
- Fits every train and test pair (`.scratch/6e453dd6/check.py`, `.scratch/6e453dd6/probe.py`). Each rule has a relational form (Components, Gravity or a per-shape slide, Closed, a row cast), and no witness has verdict `other`.
- The concept's `mark` condition (the row holds a hole cell of the shape and a cell of that shape beside the divider) and `$CastThroughShape` (a run of shape cells joins the hole to the divider) are the nearest pair: no input in the evidence separates them. Only an input with an open notch between the hole and the wall at the divider separates them, and the verdict on that input (`notch-beside-hole`) is a judgment call. The existing solver `programs/solvers/6e453dd6.dl` implements `$CastThroughShape`, with `$Between` and `concept` hole readings as its two cases.

## Choice points
- `hole`: which background cells count as a shape's hole
    - `concept`: a background cell that no 4-adjacent walk from beyond the frame reaches without crossing the slid shape's own cells (divider and far side are open)
    - `$Between`: replaces `holes`/`mark`'s hole reading with a background cell that has cells of the same shape on both sides of it in its row; no parameters; defined wherever the concept is. Fits every pair. Witness `cup-open-up`: breaks no scene claim; plausibility `ordinary`; verdict `concept`.
    - `$Closed8`: replaces the hole reading with closure under 8-adjacent walks; no parameters; defined wherever the concept is. Fits every pair. Witness `ring-corner-gap`: breaks no scene claim; plausibility `ordinary`; verdict `concept`.
    - `$DividerWall`: replaces the hole reading with closure by the shape together with the divider column; no parameters; defined wherever the concept is. Fits every pair (train1 row 10's cavity, which only the divider closes, has no shape cell at the divider in that row). Witness `cavity-open-to-divider`: breaks no scene claim; plausibility `ordinary`; verdict `concept`.
- `marked-rows`: which rows a shape's holes mark
    - `concept`: a row that holds a hole cell of the shape and that shape's cell beside the divider
    - `$CastThroughShape`: replaces `mark` with: a hole cell whose run toward the divider consists of the shape's cells all the way to the divider marks its row; no parameters; defined wherever the concept is. Fits every pair. Witness `notch-beside-hole`: breaks no scene claim; plausibility `ordinary`; verdict `concept`.
    - `$WallAdjacent`: replaces `mark` with: a hole cell whose next cell toward the divider is the shape's cell beside the divider marks its row; no parameters; defined wherever the concept is. Fits every pair. Witness `thick-right-wall`: breaks no scene claim; plausibility `ordinary`; verdict `concept`; it breaks the invariant that every hole's wall toward the divider is one cell thick, though that invariant is no scene claim.
    - `$AnyHoleRow`: replaces `mark` with: every row holding a hole cell marks; fails Fit at train0 (row 1, hole at (1,7) after the slide, is unmarked in the output), and at train1 and test0 likewise.
    - `$TouchRow`: replaces `mark` with: every row in which a shape has a cell beside the divider marks; fails Fit at train0 (row 3 and row 7 hold shape cells at col 10 and are unmarked).
- `shape-unit`: what slides as one rigid body
    - `concept`: `components`, each 4-connected component of `shape` cells
        - `connectivity`
            - `concept`: 4-adjacency
            - `$Components8`: replaces `shapes` and `slide`'s unit with 8-connected components; no parameters; defined wherever the concept is. Fits every pair. Witness `diagonal-touch`: breaks the scene claim `shapes` (no background row separates the two pieces); plausibility `borderline`; verdict `concept`; it breaks the invariant that at least one background row lies between any two shapes.
        - `collision`
            - `concept`: each shape slides on its own, and shapes that land on one cell overlap
            - `$Stack`: replaces `slide` with gravity among the shapes: a shape stops at the divider or against a shape already at rest ahead of it; no parameters; defined wherever the concept is. Fits every pair. Witness `shared-row`: breaks the scene claim `shapes` (two shapes share a row); plausibility `borderline`; verdict `$Stack`; it breaks the invariant that no two shapes share a row.
    - `$Band`: replaces `shapes` and `slide`'s unit with each maximal run of rows holding `shape` cells; no parameters; defined wherever the concept is. Fits every pair. Witness `band-no-blank-row`: breaks the scene claim `shapes`; plausibility `borderline`; verdict `concept`; it breaks the invariant that at least one background row lies between any two shapes.
    - `$WholeColor`: replaces `slide`'s unit with every `shape` cell at once; fails Fit at train0 (the upper shape moves 5 columns while the lower one stays).
- `toward`
    - `concept`: stored, `R`
    - `$DeriveToward`: replaces the stored `toward` with the direction from the side of the divider that holds `shape` cells toward the divider; undefined when both sides hold them. Fits every pair. Witness `mirrored`: breaks the scene claims `divider` and `far-side-empty` at the stored `toward`, where the concept is undefined; plausibility `variant`; verdict `$DeriveToward`; it breaks the invariant that the shapes stand left of the divider.
- `background`
    - `concept`: stored, 6
    - `$DeriveBg`: replaces the stored `background` with the commonest color of the input; no new parameters. Fits every pair. Witness `recolored-background`: breaks the scene claim `background` at the stored value; plausibility `variant`; verdict `$DeriveBg`; it breaks the invariant that the background is 6.
- `shape`
    - `concept`: stored, 0
    - `$DeriveShape`: replaces the stored `shape` with the one color other than `background` and `divider`; undefined when the input holds no such color or more than one. Fits every pair. Witness `recolored-shape`: breaks the scene claim `shapes` at the stored value; plausibility `variant`; verdict `$DeriveShape`; it breaks the invariant that the shapes are 0.
- `divider`
    - `concept`: stored, 5
    - `$DeriveDivider`: replaces the stored `divider` with the color of the one full column of a single color other than `background`; undefined when there is no such column or more than one. Fits every pair. Witness `recolored-divider`: breaks the scene claim `divider` at the stored value, where the concept is undefined; plausibility `variant`; verdict `$DeriveDivider`; it breaks the invariant that the divider is 5.
- `hole` & `marked-rows`: the holes the `hole` branch reads, and the rows the `marked-rows` branch picks from those holes (`$Between` & `$CastThroughShape` is the existing solver's `$Between` case).
- `shape-unit`, `connectivity`, `collision` with `hole` or `marked-rows`: the shapes the unit branch finds slide by the collision branch, and each slid shape's holes and marked rows follow the other point's branch.
- `connectivity` & `collision`: 8-connected components slide under gravity among themselves.
- `toward`, `background`, `shape`, `divider` with any other point: the derived value takes the place of the stored one, and the other point's branch applies unchanged; `background` & `shape` derives the shape color against the derived background.
    - none

## Open parameters
none

## Not formed
- Marking only far-side background cells, in place of every far-side cell of the row: the two differ only where the far side holds a non-background cell. That is foreign to the scene (`far-side-empty`), and the pairs give no reading of such a cell.
- A horizontal divider: it is the `toward` parameter's value under another orientation, reached by reassigning `toward`, not by another program.
- Mark extents other than the whole far-side row (only the cell beside the divider, or only the hole's width): each fails Fit at train0, whose marked rows fill all four far-side columns.

## Issues filed
- 1791155172-6e453dd6-analyze-1.md
