# e39e9282

## Concept
- The concept fits every train and test pair (`check_concept.py`), and every input meets each scene claim (`check_scene.py`).
- No witness has the verdict `other`.
- The concept is undefined on a `keep_color` box of even size that has a pin, since such a box has no middle line.

## Choice points
- `keep-pin-landing`: the cell where a pin of a `keep_color` box lands along its line
    - `concept`: `pin-to-middle`, the box's middle line across the pin's line
    - `$PinJumpsEdge`: replaces `pin-to-middle` with `pin-jumps-edge`: each pin of a `keep_color` box paints `pin_color` two cells along its line from the pin, on the cell past the box's edge cell; no parameter; undefined on no input. Fits every pair. Witness `keep-box-wide`: breaks `boxes` at `box_size` 3; stands at the stored assignment; plausibility `variant`; verdict `concept`; breaks the invariant that every box is 3×3.
    - `pin_depth=stored`: replaces the middle line that `pin-to-middle` derives from the box with a stored `pin_depth` of 1, the depth from the box's edge cell, counted from 0, at which a pin lands; undefined on no input. Fits every pair. Witness `pin_depth=stored`: breaks `boxes` at `box_size` 3; stands at the stored assignment; plausibility `variant`; verdict `concept`; breaks the invariant that every box is 3×3.
- `pin-reach`: which `pin_color` cells are pins of a box
    - `concept`: `pins`, a `pin_color` cell next to a box's side cell, across that side
    - `$StrayPinCasts`: adds `pin-cast`: a `pin_color` cell that is next to no box, and that has only `background_color` between it and a box's side cell along a row or a column, is also a pin of that box; no parameter; undefined on no input. Fits every pair. Witness `distant-pin`: breaks `pins`; stands at the stored assignment; plausibility `borderline`; verdict `concept`; breaks the invariant that every `pin_color` cell is next to a side cell of a box.
    - `$InLinePin`: replaces `pins` with `pin-in-line`: every `pin_color` cell that has only `background_color` between it and a box's side cell along a row or a column is a pin of that box; no parameter; undefined on no input. Fails Fit at train0: the cell (6,3) is also a pin of the box at rows 1–3, cols 1–3, so the branch paints `9` at train0 output (2,3), where the output has `6`.
- `stray-pin`: what a `pin_color` cell that is no pin becomes
    - `concept`: `rest-kept`, it keeps its color
    - `$StrayPinErased`: adds `stray-erased`: each `pin_color` cell that is no pin becomes `background_color`; no parameter; undefined on no input. Fits every pair. Witness `stray-pin`: breaks `pins`; stands at the stored assignment; plausibility `borderline`; verdict `concept`; breaks the invariant that every `pin_color` cell is next to a side cell of a box.
- `unpinned-erase-box`: what an `erase_color` box with no pin becomes
    - `concept`: `box-erased`, it becomes `background_color`
    - `$UnpinnedBoxKept`: replaces `box-erased` with `pinned-box-erased`: an `erase_color` box with at least one pin becomes `background_color`, and one with no pin keeps its color; no parameter; undefined on no input. Fits every pair. Witness `unpinned-erase-box`: breaks no scene claim; stands at the stored assignment; plausibility `variant`; verdict `concept`; breaks the invariant that every box has a pin.
- `keep-pin-landing` & `pin-reach`, `keep-pin-landing` & `stray-pin`, `keep-pin-landing` & `unpinned-erase-box`, `pin-reach` & `stray-pin`, `pin-reach` & `unpinned-erase-box`, `stray-pin` & `unpinned-erase-box`: the two branches' changes applied together, with the pins that the `pin-reach` branch gives

## Open parameters
- none

## Not formed
- A pin of a `keep_color` box lands on the box cell next to the far edge: no reading of the pairs gives it over the middle line or the cell past the edge cell, and on a 3×3 box it is the middle line.
- A pin of an `erase_color` box grows by a stored length: at this task's length of one cell, its model gives the concept's output on every input, and no source gives another length.
- A pin of an `erase_color` box grows up to its middle line: on a 3×3 box it grows two cells, and train0 output (3,7) holds `8`, so it fails Fit at train0.
- The roles of `keep_color` and `erase_color` derived from the input: no fact of the inputs alone separates `6` from `5` (train2 holds two boxes of each color, each with pins, and train1 holds no `erase_color` box).
- A `pin_color` cell at a box's corner, diagonal to it, as a pin: no row or column through the box carries such a cell inward, and no input has one.
- A pin next to the sides of two boxes: it breaks `pins`, and the pairs give no order between the two boxes' rules, so the pairs ground no reading of it.
- A `keep_color` box with no pin: every reading keeps it unchanged.

## Tickets filed
- none
