# d89b689b

## Concept
- Fits every pair (train0–2, test0). No witness with verdict `other` was found. The rule `marker-to-corner` is the rule as the generator applies it: it sends a marker to the block cell on the corner the marker lies diagonally off, and it is undefined on a marker in line with the block's rows or columns.

## Choice points
- `marker-target` (which block cell a marker moves into)
    - `concept`: the block cell at the block corner the marker lies strictly diagonally off
    - `$GridQuadrant`: replaces `marker-to-corner`; the marker goes to the block cell at the corner of the grid quadrant the marker sits in, split at the grid's middle; parameters unchanged; undefined where a marker is on the middle row or column of an odd-sized grid, or two markers share a grid quadrant. It fits every pair. Witness `marker-past-grid-midline`: train2's input with the marker 3 moved from (7,2) to (4,2), below and left of the block and above the grid's middle. It breaks no scene claim. Plausibility `ordinary`, verdict `concept`. Where both models are defined, they give one output, so the branch differs from the concept only where it is defined.
    - `$NearestBlockCell`: replaces `marker-to-corner` and drops the corner condition of `one-marker-per-corner`; the marker goes to the block cell at the least 4-step distance from it; parameters unchanged; undefined where that cell is tied, or two markers reach one cell. It fits every pair. Witness `marker-in-block-column`: train2's input with the marker 1 moved from (0,3) to (0,5), directly above the block's left column. It breaks `one-marker-per-corner`. Plausibility `borderline`, verdict `$NearestBlockCell`. It breaks the invariant that every marker lies outside the block's rows and columns.
    - `$ReadingOrder`: replaces `marker-to-corner`; the markers in row-major order fill the block cells in row-major order; fails Fit at train0, where it gives 7 at (4,4) in place of 6.
- `block-locate` (how the block is found)
    - `concept`: the cells of the stored `block_color` (8)
    - `$BlockByShape`: replaces `one-block`'s color with shape; the block is the one 4-connected component of non-`background` cells with more than one cell, and `block_color` is dropped; undefined where no such component, or more than one, exists. It fits every pair. Witness `block-other-color`: train0's input with the block recolored to 3. It breaks `one-block`. Plausibility `variant`, verdict `$BlockByShape`. It breaks the invariant that the block is 8 in every input.
    - `block_color=SharedColor`: derives every color of the input; fails Fit at train0, where the cells of those colors form no 2×2 block.
    - `block_color=RarestColor`: derives the four marker colors; fails Fit at train0, where no block is found.
    - `block_color=DominantColor`: derives 0; fails Fit at train0, where the 0 cells form no 2×2 block.
- `background`
    - `concept`: the stored `background` (0)
    - `background=DominantColor`: derives the commonest color of the input; undefined where that color is tied. It fits every pair. Witness `background=DominantColor`: train0's input with the field recolored to 1. It breaks `one-block` at the stored `background`. Plausibility `variant`, verdict `background=DominantColor`. It breaks the invariant that the field is 0 in every input.
- `marker-fate`
    - `concept`: the markers leave their places (`clear-rest`)
    - `$KeepMarkers`: replaces `clear-rest`; each marker also stays where it was; fails Fit at train0, where it keeps 7 at (0,8).
- `marker-target` & `block-locate`, `marker-target` & `background`, `marker-target` & `marker-fate`, `block-locate` & `background`, `block-locate` & `marker-fate`, `background` & `marker-fate`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Output cropped to the block: every output has the input's 10×10 size.
- Markers matched to block cells by color: the four marker colors differ in each pair, and no color holds a fixed corner across pairs (9 is bottom-right in train0 and top-right in train1).
- Euclidean or king-move nearest block cell: off a corner, each gives the same cell as the 4-step distance. In line with the block, the Euclidean distance gives the same cell, and the king-move distance ties and is undefined. Either one adds no model beyond `$NearestBlockCell` that the pairs or the generator separate.
- Block size other than 2×2: every input has a 2×2 block, and the corner rule reads only the block's corner cells.

## Tickets filed
- none
