# e9ac8c9e

## Concept
- Fits every train pair and the test pair (probe `work/task/e9ac8c9e/probe.py`). No witness has the verdict `other`. The rule `quadrant-color` cuts each square at half its side on each axis. This is the generator's rule as it applies it: each cell of a square takes the color of the corner dot nearest to it. On the even sides that the scene gives, the two agree. The concept is undefined where a square has no dot diagonally adjacent to one of its corners, and where a square has an odd side.

## Choice points
- `background`
    - `concept`: `background` stored, `0`
    - `background=DominantColor`: `background` derived as the commonest color of each input; replaces the `field` claim's stored value; undefined where two colors tie for the commonest. Fits every pair. Witness `background=DominantColor`: an 8×8 square of `5` in a 10×10 grid, so `5` outnumbers `0`. It breaks no scene claim. Plausibility `ordinary`, verdict `concept`.
    - `background=RarestColor`: `background` derived as each input's least common colors, the four dot colors and more; replaces the `field` claim's stored value. Fails Fit at train0.
    - `background=SharedColor`: on one input, every color of that input; replaces the `field` claim's stored value. Fails Fit at train0.
- `block-color`
    - `concept`: `block_color` stored, `5`
    - `$BlockByShape`: each 4-connected component of non-`background` cells that has more than one cell is a block, and takes its own color as its block color; replaces `squares`, with no `block_color` parameter; undefined on no input where the concept is defined. Fits every pair. Witness `non-gray-block`: train0's scene with the square in `3`. It breaks `squares` at the stored assignment, where the concept finds no square and returns the input. Plausibility `variant`, verdict `$BlockByShape`. The invariant of the inputs it breaks: every block is `5`.
    - `block_color=DominantColor`: on one input, `0`, the background; replaces the stored `block_color`. Fails Fit at train0.
    - `block_color=RarestColor`: on one input, the dot colors, each a single cell of odd side; replaces the stored `block_color`. Fails Fit at train0.
    - `block_color=SharedColor`: on one input, every color of that input; replaces the stored `block_color`. Fails Fit at train0.
- `block-count`
    - `concept`: each 4-connected component of `block_color` cells is one square
    - `$OneBlock`: one block, the bounding box of every `block_color` cell; replaces `squares`; undefined where a corner of that box has no dot, or where the box has an odd side. Fails Fit at test0.
- `dot-reach`
    - `concept`: the dot is the cell diagonally adjacent to the corner, outside the square
    - `$RayDot`: the dot is the first non-`background` cell on the diagonal ray outward from the corner; replaces `corner-dots`; undefined where that ray meets no such cell before the grid edge, or meets a `block_color` cell first. Fits every pair. Witness `gapped-dots`: a 4×4 square with each dot two diagonal steps from its corner. It breaks `corner-dots`. Plausibility `borderline`, verdict `$RayDot`. The invariant of the inputs it breaks: each dot touches its corner diagonally.
- `missing-dot`
    - `concept`: a square with no dot at a corner leaves the output undefined
    - `$KeepBlock`: a quarter whose corner has no dot keeps `block_color`; adds a rule beside `quadrant-color`; undefined on no input where the concept is defined. Fits every pair. Witness `missing-dot`: train0's scene with the bottom-right dot removed. It breaks `corner-dots`. Plausibility `borderline`, verdict `$KeepBlock`. The invariant of the inputs it breaks: every square has a dot at each of its four corners.
- `background` & `block-color`, `background` & `block-count`, `background` & `dot-reach`, `background` & `missing-dot`, `block-color` & `block-count`, `block-color` & `dot-reach`, `block-color` & `missing-dot`, `block-count` & `dot-reach`, `block-count` & `missing-dot`, `dot-reach` & `missing-dot`: the two branches' changes applied together

## Open parameters
none

## Not formed
- Each cell of a square takes the color of the dot nearest to it, by Euclidean distance: this is equivalent to the quarter cut. On an even side, the nearest dot is the dot of the cell's quarter. On an odd side, the cells of the middle row or column tie between two dots, and both models are undefined.
- A rule for the middle row or column of an odd-sided square: no pair, solver header, lib component or variant task gives a rule for it.
- `background` or `block_color` derived by `VanishedColor`, `ChangedColor`, `UnchangedColor`, `OutNewColor` or `AnyOutNewColor`: these read train outputs, and a `@derive` run leaves `ex_out` empty.
- A non-square rectangle as the block: the concept's program does not read squareness, so on an even-sided rectangle every model gives the same output as on a square.

## Tickets filed
none
