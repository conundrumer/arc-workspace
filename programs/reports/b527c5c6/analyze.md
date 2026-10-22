# b527c5c6

## Concept
- The concept case fits every pair (`probe.py`). Each rule has a relational form, and no witness of the concept case has verdict `other`.
- The concept is undefined where a mark sits on more than one side of its bar, where a piece is not a solid rectangle of `bar_color` with one `mark_color` cell, and where two beams overlap with different colors. No input in the evidence shows any of these.

## Choice points
- `beam-side`: which side of the bar the beam leaves
    - `concept`: the side of the bar that holds the mark; undefined where the mark sits on more than one side
    - `$LongSide`: replaces `beam-direction`: the beam leaves the long side of the bar that holds the mark, and the flank width is the bar's thickness less one; no new parameter; undefined on a square bar, on a mark on a short side away from the corners, and on a bar one cell thick. Fits every pair. Witness `corner-mark`: the mark sits at a corner of a 3-thick bar; breaks `one-mark-per-bar`; stored assignment; `borderline`, verdict `$LongSide`; it breaks the invariant that each mark sits at least the bar's thickness less one from each end of its side
- `beam-width`: how wide each flank is
    - `concept`: the bar's extent across the marked side less one
    - `$StoredWidth`: replaces `beam-flanks`: a stored flank width, the same for every bar; fails Fit at train1, where the flanks are 2 wide on the vertical bar and 1 wide on the horizontal bar
- `beam-span`: how far the flanks reach along the marked side
    - `concept`: the full flank width, past the bar's end where the mark is near it
    - `$ClipToBar`: replaces `beam-flanks`: a flank line outside the bar's span along the marked side is dropped; no new parameter; undefined where the concept is. Fits every pair. Witness `mark-near-end`: the mark sits one cell from the end of a 3-thick bar; breaks `one-mark-per-bar`; stored assignment; `borderline`, verdict `concept`; it breaks the invariant that each mark sits at least the bar's thickness less one from each end of its side
- `beam-blocking`: what a beam does at a non-background cell on its path
    - `concept`: it paints over the cell and runs on to the grid edge
    - `$Underlay`: replaces `beam-core` and `beam-flanks`: a beam cell takes its color only where the input is `background`, and the beam runs on past the cell; no new parameter; undefined where the concept is. Fits every pair. Witness `beam-meets-bar`: one bar stands in the other bar's beam path; breaks `clear-paths`; stored assignment; `borderline`, verdict `$Blocked`; it breaks the invariant that each beam path holds only `background`
    - `$Blocked`: replaces `beam-direction`: each line of the beam ends at the cell before its first non-background cell; no new parameter; undefined where the concept is. Fits every pair. Witness `beam-meets-bar`, as under `$Underlay`
- `beam-overlap`: the color of a cell where two beams give different colors
    - `concept`: none; the model is undefined there
    - `$CoreOnTop`: adds a claim: where beams overlap, a core cell covers a flank cell; no new parameter; undefined where two flanks or two cores of different colors overlap. Fits every pair. Witness `beams-cross`: a vertical beam and a horizontal beam cross; breaks `clear-paths`; stored assignment; `borderline`, verdict `$CoreOnTop`; it breaks the invariant that each beam path holds only `background`
- `bar-colors`: where the beam's colors come from
    - `concept`: stored `bar_color` and `mark_color`
    - `$OwnColors`: replaces `bars`, `one-mark-per-bar`, `beam-core` and `beam-flanks`: each non-background piece is a solid rectangle of one color with one cell of another color, the core takes that cell's color, and the flanks take the rectangle's color; reads `background` alone; undefined where a piece is not such a rectangle. Fits every pair. Witness `other-color-bar`: one bar is of color 4; breaks `bars`; stored assignment; `borderline`, verdict `$OwnColors`; it breaks the invariant that every bar is of one color, 3
- `beam-side` & `beam-span`, `beam-side` & `beam-blocking`, `beam-side` & `beam-overlap`, `beam-side` & `bar-colors`, `beam-span` & `beam-blocking`, `beam-span` & `beam-overlap`, `beam-span` & `bar-colors`, `beam-blocking` & `beam-overlap`, `beam-blocking` & `bar-colors`, `beam-overlap` & `bar-colors`: the two branches' changes applied together
- `beam-width` & each other point: `$StoredWidth` fails Fit, so no case takes it

## Open parameters
none

## Not formed
- Flank width as the distance from the mark to the bar's far side: wherever the mark sits on one side, that distance is the bar's extent across the side less one, so the model is equivalent to the concept's.
- Built-in derivations of `background`, `bar_color` and `mark_color`: Develop step 4 holds each that `run_dl.py derive` lists.

## Tickets filed
none
