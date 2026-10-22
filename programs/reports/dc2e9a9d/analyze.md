# dc2e9a9d

## Concept
- Fits every pair (`probe.py pairs`). Every claim has a relational form, and no witness has verdict `other`.
- An object that is not one box outline with one nub gets no copy. The concept is undefined where two copies of different colors cover one cell.

## Choice points
- `copy-transform`
    - `concept`: the copy is the mirror image across the axis parallel to the box's side opposite the nub.
    - `$Rotate`: replaces `mirror-away-from-nub` with a copy that is the half turn of the object, placed at the same box; no new parameters; undefined nowhere. Fits every pair. Witness `off-center-nub`: breaks `nubbed-boxes`; stands at the stored assignment; `borderline`; verdict `concept`. It breaks the invariant that every nub sits at the middle cell of an odd-length side.
    - `$Translate`: replaces `mirror-away-from-nub` with a copy that is the object translated by the box's extent plus `gap` away from the nub, so the copy's nub keeps its side; no new parameters; undefined nowhere. Fails Fit at train0: the copy's nub lands at (5,9) and (13,9), where the output has (5,15) and (9,9).
- `copy-side`
    - `concept`: the copy goes to the side opposite the nub.
    - `$TowardNub`: replaces `mirror-away-from-nub` with a mirror copy on the nub's side, `gap` lines past the nub; no new parameters; undefined nowhere. Fails Fit at train0: the copy of the box at rows 3–7, cols 4–8 falls left of col 3, where the output has it at cols 10–15.
- `copy-color-key`
    - `concept`: `copy_color` is keyed by the axis the copy moves along.
    - `$ColorByDir`: replaces `color-by-axis` with `copy_color_dir`, keyed by the direction the copy moves: left → 1, right → 1, up → 8, down → 8; undefined nowhere. Fits every pair. Witness `dir-keyed-color`: breaks no scene claim; stands at `copy_color_dir` with right → 2; `ordinary`; verdict `$ColorByDir`.
- `frame-edge`
    - `concept`: copy cells past the frame edge are dropped.
    - `$FitInFrame`: replaces `clip-at-frame`; no new parameters; undefined on an input where a copy cell falls past the frame edge. Fails Fit at train1: the copy's nub of the box at rows 2–4, cols 12–14 falls at (3,19), past the frame.
- `background`
    - `concept`: `background` is stored.
    - `background=DominantColor`: derives `background` as the commonest color of the input, each tied color where colors tie; undefined nowhere. Fits every pair. Witness `background=DominantColor`: breaks `background-field`; stands at the stored assignment; `variant`; verdict `background=DominantColor`. It breaks the invariant that every input's field is 0.
    - `background=SharedColor`: derives `background` as each color present in every input, which gives 0 and 3. Fails Fit at train0: at 3 the model makes no copy, so the output holds the input beside the expected grid.
    - `background=RarestColor`: derives `background` as the rarest color of the input, which gives 3. Fails Fit at train0: the model makes no copy and gives the input.
- `copy-over-input`
    - `concept`: a copy paints only `background` cells, and every input cell keeps its color.
    - `$CopyOver`: replaces `keep-input` with copy cells that paint over input cells; no new parameters; undefined nowhere. Fits every pair. Witness `copy-lands-on-shape`: breaks `room-for-copy`; stands at the stored assignment; `borderline`; verdict `any`. It breaks the invariant that every copy covers only background cells, apart from any other shape.
- `copy-collision`
    - `concept`: undefined where two copies of different colors cover one cell.
    - `$HorizontalCopyOnTop`: adds that a cell covered by a horizontal and a vertical copy takes the horizontal copy's color; no new parameters; undefined where two copies of different colors on one axis cover one cell. Fits every pair. Witness `crossing-copies`: breaks `room-for-copy`; stands at the stored assignment; `borderline`; verdict `any`. It breaks the invariant that no two copies share a cell.
    - `$VerticalCopyOnTop`: adds that such a cell takes the vertical copy's color; no new parameters; undefined as `$HorizontalCopyOnTop` is. Fits every pair. Witness `crossing-copies`, as for `$HorizontalCopyOnTop`.
- `adjacency`
    - `concept`: objects are the 4-connected components of non-background cells.
    - `$Adjacency8`: replaces the object parse with 8-connected components; no new parameters; undefined nowhere. Fits every pair. Witness `corner-touching-boxes`: breaks no scene claim; stands at the stored assignment; `borderline`; verdict `concept`. It breaks the invariant that no two objects touch, at a side or at a corner.
- `object-cells`
    - `concept`: objects are made of every non-background cell.
    - `$ShapeColorObjects`: replaces the object parse with components of `shape_color` cells, and moves `shape_color` (3) from the scene parameters to the parameters; undefined nowhere. Fits every pair. Witness `other-color-box`: breaks `nubbed-boxes`; stands at the stored assignment; `borderline`; verdict `concept`. It breaks the invariant that every object is drawn in 3.
- `copy-transform` & `copy-side`, `copy-transform` & `copy-color-key`, `copy-transform` & `frame-edge`, `copy-transform` & `background`, `copy-transform` & `copy-over-input`, `copy-transform` & `copy-collision`, `copy-transform` & `adjacency`, `copy-transform` & `object-cells`, `copy-side` & `copy-color-key`, `copy-side` & `frame-edge`, `copy-side` & `background`, `copy-side` & `copy-over-input`, `copy-side` & `copy-collision`, `copy-side` & `adjacency`, `copy-side` & `object-cells`, `copy-color-key` & `frame-edge`, `copy-color-key` & `background`, `copy-color-key` & `copy-over-input`, `copy-color-key` & `copy-collision`, `copy-color-key` & `adjacency`, `copy-color-key` & `object-cells`, `frame-edge` & `background`, `frame-edge` & `copy-over-input`, `frame-edge` & `copy-collision`, `frame-edge` & `adjacency`, `frame-edge` & `object-cells`, `background` & `copy-over-input`, `background` & `copy-collision`, `background` & `adjacency`, `background` & `object-cells`, `copy-over-input` & `copy-collision`, `copy-over-input` & `adjacency`, `copy-over-input` & `object-cells`, `copy-collision` & `adjacency`, `copy-collision` & `object-cells`, `adjacency` & `object-cells`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- The copy's color follows the box's size or shape: two 3×3 boxes (train0 rows 14–16, cols 8–10; train1 rows 2–4, cols 12–14) take 8 and 1.
- `copy_color` derived by `OutNewColor`: the proposer gives the set {1, 8}, and not which axis takes which color.
- The copy goes to the side with more free room: in train1 the box at rows 2–4, cols 12–14 has more room on its left, and its copy goes right, where its nub falls past the frame. The nub fixes the side in every pair.
- `gap` read from the nub's length: the nub is one cell in every input, and no reading of the concept ties the copy's distance to the nub.
- A copy of the whole box, interior included: it parts from the copy of the shape cells only where the copy's box covers non-background input cells, which breaks `room-for-copy`, and every box interior is background.

## Tickets filed
- none
