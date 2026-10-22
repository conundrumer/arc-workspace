# c8b7cc0f

## Concept
- The concept fits every pair: the counts inside the outline are 3, 5, 4 and 4 (train0, train1, train2, test0), and the reading-order fill of those counts reproduces each output.
- The concept case has no witness with verdict `other`. The concept rule is the generator's rule as the pairs show it, with no approximation.
- The concept case is undefined on `two-dot-colors`, where `$DotColorInside` is defined. On every input where the concept is defined, `$DotColorInside` gives the concept's output.
- The pairs fix `fill_corner` (top-left) and `fill_primary_axis` (V): the counts 4 and 5 put the fourth and fifth cells at the start of row 1, and a column-major fill would put them in column 1.

## Choice points
- `frame-color`
    - `concept`: `frame_color` stored as 1
    - `$FrameCommonest`: replaces the stored value in `box-outline`; the frame color is derived per input as the commonest color other than `background`; undefined where two such colors tie. Fits every pair. Witness `frame-color-swapped`: breaks `box-outline` (the outline is color 2); stands at the stored assignment; plausibility `variant`; verdict `$FrameCommonest` (its output is `$FrameOutline`'s as well); breaks the invariant that the outline is color 1 in every input.
    - `$FrameOutline`: replaces the stored value in `box-outline`; the frame color is derived per input as the one color whose cells are exactly the border of their bounding box, at least 3×3; undefined where no color or more than one color does so. Fits every pair. Witness `frame-color-swapped`: breaks `box-outline`; stands at the stored assignment; plausibility `variant`; verdict `$FrameOutline`; breaks the invariant that the outline is color 1 in every input.
    - `frame_color=DominantColor`: the derivation gives the background 0 on each input. Fails Fit at train0.
    - `frame_color=RarestColor`: the derivation gives the dot color on each input. Fails Fit at train0.
    - `frame_color=SharedColor`: on one input the derivation gives every color of that input (0, 1 and the dot color), so the output holds the grids of three frame colors. Fails Fit at train0.
- `background`
    - `concept`: `background` stored as 0
    - `background=DominantColor`: replaces the stored value in `box-outline` and `fill-in-order`; the background is the commonest color of the input. Fits every pair. Witness `background=DominantColor`: breaks `scattered-dots` (dots share sides); stands at the stored assignment; plausibility `borderline`; verdict `concept`; breaks the invariants that 0 is the commonest color of each input and that no two dots share a side.
- `dot-color`
    - `concept`: the dot color is derived as the one color of the input other than `background` and `frame_color`; undefined where there are two or more.
    - `$DotColorStored`: replaces the derivation in `scattered-dots` with a stored dot color. Fails Fit at train1 (train0 needs 4 and train1 needs 6).
    - `$DotColorInside`: replaces `scattered-dots`; the dot color is the one color other than `background` and `frame_color` among the cells strictly inside the outline, and the output is all `background` where those cells hold no such color; undefined where they hold two or more. Fits every pair. Witness `two-dot-colors`: breaks `scattered-dots` (two dot colors); stands at the stored assignment; plausibility `variant`; verdict `$DotColorInside`; breaks the invariant that each input has one color besides 0 and 1.
- `interior`
    - `concept`: the cells strictly inside the bounding box of the `frame_color` cells
    - `$Enclosed`: replaces `count-inside`; the count runs over the parts of the non-frame cells that no 4-adjacent walk through non-frame cells reaches from the grid edge (lib `Closed`). Fits every pair. Witness `broken-outline`: breaks `box-outline` (the outline has a gap); stands at the stored assignment; plausibility `foreign`; verdict `concept`; breaks the invariant that the outline is a closed rectangle.
- `count-unit`
    - `concept`: the count is the number of dot cells
    - `$CountObjects`: replaces `count-inside`; the count is the number of connected components of the dot cells inside the outline. Fits every pair. Witness `adjacent-dots`: breaks `scattered-dots` (two dots share a side); stands at the stored assignment; plausibility `borderline`; verdict `concept`; breaks the invariant that no two dots share a side.
        - `adjacency`
            - `concept`: 4-adjacency (lib `Components`)
            - `$Adjacency8`: 8-adjacency (lib `Components8`). Fails Fit at train0 (the dots at (4,4) and (5,3) join, so the count is 2).
- `fill-order`
    - `concept`: lexicographic order from `fill_corner` with `fill_primary_axis` first (lib `LexOrder`)
    - `$Snake`: replaces `fill-in-order`; each row runs opposite to the row before it. Fails Fit at train1 (the fourth cell lands at (1,2)).
    - `$Spiral`: replaces `fill-in-order`; the fill runs clockwise around the border and then to the center. Fails Fit at train1 (the fourth cell lands at (1,2)).
- `overflow`
    - `concept`: a count past the output's cell count fills every cell
    - `$OverflowUndefined`: replaces `fill-in-order`; undefined where the count exceeds the output's cell count. Fits every pair. Witness `ten-dots`: breaks `count-fits` (10 dots inside); stands at the stored assignment; plausibility `foreign`; verdict `concept`; breaks the invariant that the count inside is at most 5. The model gives the concept's output wherever it is defined, so it is subsumed by the concept case's model and fails Subsumption.
- `out-size`
    - `concept`: `out_size` stored as 3×3
    - `out_size=ConstOutDim`: the derivation reads train outputs, so on an input alone it gives no value and the branch is undefined. Fails Fit at train0.
- `frame-color` & `background`, `frame-color` & `dot-color`, `frame-color` & `interior`, `frame-color` & `count-unit`, `frame-color` & `fill-order`, `frame-color` & `overflow`, `frame-color` & `out-size`, `background` & `dot-color`, `background` & `interior`, `background` & `count-unit`, `background` & `fill-order`, `background` & `overflow`, `background` & `out-size`, `dot-color` & `interior`, `dot-color` & `count-unit`, `dot-color` & `fill-order`, `dot-color` & `overflow`, `dot-color` & `out-size`, `interior` & `count-unit`, `interior` & `fill-order`, `interior` & `overflow`, `interior` & `out-size`, `count-unit` & `fill-order`, `count-unit` & `overflow`, `count-unit` & `out-size`, `fill-order` & `overflow`, `fill-order` & `out-size`, `overflow` & `out-size`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A count of the dots outside the outline: train0 has 4 dots outside and an output of 3, so no reader of the pairs takes it.
- A derivation of the output size from the input: no cell, extent or count of any input is 3 in both axes in a way the pairs share, and the pairs keep 3×3 for interiors of 2×4, 4×4, 6×3 and 4×5.
- A fill of the output from another corner or along the other axis: these are values of `fill_corner` and `fill_primary_axis`, which the pairs fix.

## Tickets filed
- 10-555_task_c8b7cc0f_analyze.md
