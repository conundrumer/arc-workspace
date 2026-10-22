# bf699163

## Concept
- Fits every pair. The program reads the inside of the frame as the intersection of half-planes: each drawn line of `frame_color` (a row or column that holds at least two frame cells) bounds the region on the side toward which the perpendicular lines run, and the region reaches the grid edge where no line is drawn. The single ring of a non-`background`, non-frame color whose box lies in that region is cropped. The model is undefined where that region holds no ring or more than one. Its rule is relational, and no witness has verdict `other`.

## Choice points
- `selection`: which ring the frame marks
    - `concept`: the ring inside the rectangle the drawn lines bound, whose undrawn sides lie past the grid edge
    - `$FrameBbox`: replaces `dashed-frame` and `one-ring-inside` with the ring whose box lies inside the bounding box of the frame-colored cells; undefined where that box holds no ring or more than one. Fits every pair. Witness `second-ring-past-line-end`: train0 with (16,8) cleared and a ring of 4 at rows 14–16, cols 12–14, past the end of the left line; breaks `one-ring-inside`; `foreign`, verdict `concept` (undefined); breaks the invariants that one ring lies inside the frame and that each line reaches the grid edge with a frame cell.
    - `$MostFramedSides`: replaces `one-ring-inside` with the ring that has frame cells in line with it toward the most of the four directions; undefined where two rings tie. Fits every pair. Witness `sparse-dashes`: train0 with (8,10), (8,11), (11,8)–(14,8) cleared, so no frame cell lines up with ring 1 and ring 3 alone has one; breaks no scene claim; `borderline`, verdict `concept`; breaks the invariant that the gaps of a dashed line are at most 2 cells long.
    - `$NearestToFrame`: the ring nearest a frame cell; fails Fit at train0 (rings 1 and 3 tie at distance 2) and train1 (ring 3 is nearest).
    - `$BetweenLines`: the ring with frame cells on both sides of it along a row or a column; fails Fit at train0 (ring 1 has frame cells only to its left and above).
    - `$ClosedByFrame`: the ring that the frame closes off from the grid edge; fails Fit at train0 (every ring reaches the edge through background).
- `output-content`
    - `concept`: the selected ring's box cropped from the input, hole included
    - `shape=stored`: a stored 3×3 ring mask, drawn in the selected ring's color with the hole in `background`; parameter `shape`. Fits every pair. Witness `shape=stored`: the test input with ring 2 enlarged to a 4×4 hollow square at rows 0–3, cols 10–13; breaks `rings` at `ring_side` 3; `variant`, verdict `concept`; breaks the invariant that every ring is 3×3.
- `background`
    - `concept`: stored, 5
    - `background=DominantColor`: the commonest color of the input; undefined where two colors tie for it. Fits every pair. Witness `background=DominantColor`: the test input with 5 and 2 swapped; breaks `background` at 5; `variant`, verdict `background=DominantColor`; breaks the invariant that the field is 5.
    - `background=SharedColor`: fails Fit at train0 (it gives 5, 7, 1, 2 and 8).
    - `background=RarestColor`: fails Fit at train0 (it gives no value that is the field).
- `frame_color`
    - `concept`: stored, 7
    - `$FrameColorByShape`: the one non-`background` color whose cells do not form one hollow square; undefined where no such color or more than one exists. Fits every pair. Witness `frame-recolored`: the test input with 7 recolored to 9; breaks `dashed-frame` at `frame_color` 7; `variant`, verdict `$FrameColorByShape`; breaks the invariant that the frame is 7.
    - `frame_color=SharedColor`: fails Fit at train0 (it gives 5, 7, 1, 2 and 8).
    - `frame_color=RarestColor`: fails Fit at train0 (the ring colors, at 8 cells each, are rarer than the 12 frame cells).
    - `frame_color=DominantColor`: fails Fit at train0 (it gives 5).
- `selection` & `output-content`, `selection` & `background`, `selection` & `frame_color`, `output-content` & `background`, `output-content` & `frame_color`, `background` & `frame_color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A stored output grid or output color: the output color differs in every pair (1, 4, 2), and no key in the input selects a stored entry, so no lookup fits.

## Tickets filed
- none
