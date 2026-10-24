# f25fbde4

## Concept
- Fits every pair (train0–2, test0): crop to the bounding box of the non-background cells, then turn each cell into a `factor` × `factor` block, with `bg` 0 and `factor` 2. Every rule has a relational form, and the generator applies the rule as the concept file states it, with no approximation.
- No witness has the verdict `other`.
- `one-drawing` is now stated as the invariant of the inputs: one ink drawing whose cells all join at an edge or a corner. In test0 they join only at corners, so the drawing is 8-connected and not 4-connected.

## Choice points
- `crop-cells`: which cells the cropped box bounds
    - `concept`: every non-background cell
        - `bg-source`: where the background color comes from
            - `concept`: stored `bg`
            - `bg=DominantColor`: derives `bg` as the input's commonest color, replacing the stored `bg` read by `crop-to-drawing`; undefined where two colors tie for commonest. Fits every pair. Witness `bg=DominantColor`: a 4 slab covers rows 0–5, and only 0 is left below it. Breaks `one-drawing` (a small drawing) and `blank-field`. Stands at the stored assignment, plausibility `borderline`, verdict `concept`. Invariant broken: in every input the drawing has at most 8 cells, so the background far outnumbers it.
            - `bg=SharedColor`, `bg=RarestColor`: derive `bg` from one input. Both fail Fit at train0. SharedColor gives both 0 and 4, so the output holds two grids. RarestColor gives 4, so the whole 9×9 grid is cropped.
    - `$CropInkColor`: replaces `crop-to-drawing` with the bounding box of the cells of the stored color `ink`, which moves `ink` from Scene parameters to Parameters. The program reads no `bg`. Undefined where no cell has the color `ink`. Fits every pair. Witness `second-color-joined`: train1's input with a 3 at (4,6), joined to the drawing at a corner. Breaks `one-drawing` (one color). Stands at the stored assignment, plausibility `variant`, verdict `concept`. Invariant broken: every input holds one color besides the background.
- `crop-extent`: how much of the selected cells the box bounds
    - `concept`: all of them
    - `$CropObject8`: replaces `crop-to-drawing` with the bounding box of the largest 8-connected component of the selected cells. Undefined where two components tie for largest, or no cell is selected. Fits every pair. Witness `second-drawing-apart`: train0's input with a second drawing of two 4 cells at (6,6) and (6,7), joined to the first at no edge or corner. Breaks `one-drawing` (all cells join). Stands at the stored assignment, plausibility `variant`, verdict `concept`. Invariant broken: in every input the non-background cells form a single 8-connected piece.
    - `$CropObject4`: the same with 4-connected components. Fails Fit at train1, where the largest component is the 3 cells at (1,4), (2,3), (2,4), giving a 4×4 output. It also fails at test0, where all 7 components are single cells and tie.
- `factor-source`: where the scale factor comes from
    - `concept`: one stored `factor` for both axes
    - `$FactorColorCount`: derives the factor as the number of distinct colors in the input, background included (as in solver d4b1c2b1), replacing the stored `factor` read by `scale-up`. Defined on every non-empty input. Fits every pair, because each input has 2 colors. Witness `two-color-drawing`: train1's input with (3,5) recolored to 3. Breaks `one-drawing` (one color). Stands at the stored assignment, plausibility `variant`, verdict `concept`. Invariant broken: every input holds exactly the background and one ink color.
    - `$FactorPerAxis`: stores one factor per axis, `axis_factor` (V 2, H 2), in place of the shared `factor` in `scale-up`. This is a different parameterization: an uneven assignment agrees with no assignment of the concept. Fits every pair. Witness `uneven-scale`: train0's input at the assignment `axis_factor` V 2, H 3 (one value changed). It gives a 6×12 output where the concept gives 6×8. Breaks no scene claim, plausibility `ordinary`, verdict `$FactorPerAxis`, because at that assignment the generator stretches unevenly and the pairs do not say whether the factor is shared.
    - `factor=ScaleRatio`: derives `factor` from one input's dims with no output. It gives no value, so it is undefined on every input and fails Fit at train0. In determination mode too it proposes nothing: 6/9 and 8/9 are not whole.
- `crop-cells` & `crop-extent`, `crop-cells` & `factor-source`, `crop-extent` & `factor-source`, `crop-extent` & `bg-source`, `factor-source` & `bg-source`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Scale-up as a k×k copy of the whole drawing per cell (a fractal), in place of a k×k block: the output sizes rule it out. Train0 would be 18×24 and not 6×8.
- `factor` from the cell count or the non-background color count (ac0a08a4, b91ae062): these give 8, 4, 5 and 1 at train0–2, which fails Fit at train0.
- `factor` from the number of 8-connected components plus one: it fits only because every input has one component, and no solver header, proposer or lib component supplies the "+1". It is a coincidence of the pairs and not a reading of the concept.

## Tickets filed
- none
