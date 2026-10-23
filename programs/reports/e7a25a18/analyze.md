# e7a25a18

## Concept
- The concept fits every pair: the frame of `frame_color` 2 is cropped with its border, and the inside is the pattern scaled per axis by the inside's side over the pattern's side, 2 in every pair. The rule has a relational form, and no witness of the concept case has the verdict `other`.
- The concept is undefined where the inside's side is not a multiple of the pattern's side on an axis (`quadrants-off-scale`), and where no cell of `frame_color` stands (`recolored-frame`).
- `$BlockGrid` subsumes the concept's model: wherever the concept is defined, `$BlockGrid` gives the same output, and `$BlockGrid` is also defined at `quadrants-off-scale`, where the concept is not. The concept case is exempt from Subsumption.

## Choice points
- `fill`: what fills the frame's inside
    - `concept`: `scale-pattern`, the pattern scaled up by the inside-to-pattern ratio
        - `scale`: the scale factor
            - `concept`: derived on each axis as the inside's side over the pattern's side
            - `$UniformScale`: replaces `scale-pattern` with one ratio for both axes; undefined where the two axes' ratios differ. Fits every pair. Witness `oblong-frame` (inside 8×4 around a 4×4 pattern): it breaks `one-frame` (the frame is square) and the invariant that every frame is square; plausibility `variant`, verdict `concept`. `$UniformScale` is undefined there, and no witness exists where it is defined and differs from the concept, since its model gives the concept's output wherever it is defined; it fails Subsumption under the concept.
            - `scale=stored`: replaces `pattern-fits-inside` and `scale-pattern`; the stored `scale` = 2 scales the pattern, and the output is that scaled pattern inside a one-cell border of `frame_color`, whatever the frame's size; undefined where there is no pattern. Fits every pair. Witness `scale=stored` (inside 6 across around a 2×2 pattern): it breaks `pattern-fits-inside` at `interior_ratio` 2, and the invariant that the inside's side is twice the pattern's; plausibility `variant`, verdict `concept`.
    - `$QuadrantFill`: replaces `scale-pattern`; the inside is cut into 2×2 equal quadrants by a stored part count `parts` = 2, and each quadrant takes the one color of the matching quadrant of the pattern; undefined where the inside's side is odd or a pattern quadrant holds more than one color. Fits every pair. Witness `quadrants-off-scale` (inside 6 across around a 4×4 pattern of 2×2 blocks): it breaks `pattern-fits-inside` and the invariant that the inside's side is twice the pattern's; plausibility `variant`, verdict `$QuadrantFill`. `$BlockGrid` gives `$QuadrantFill`'s output wherever `$QuadrantFill` is defined, and is also defined at `nine-cell-pattern`, so `$QuadrantFill` fails Subsumption under `$BlockGrid`.
        - `part count`: the number of parts per side
            - `concept`: the stored `parts` = 2
            - `$BlockGrid`: derives the part count on each axis as the number of single-color blocks per side of the pattern, the blocks taken as large as the pattern allows; undefined where the inside's side is not a multiple of that count. Fits every pair. Witness `nine-cell-pattern` (a 3×3 pattern of single cells in a 6×6 inside): it breaks `quad-pattern` and the invariant that the pattern is four blocks in a 2×2 arrangement; plausibility `variant`, verdict `concept`, which `$BlockGrid` gives and `$QuadrantFill` does not, being undefined there.
- `frame`: how the frame is found
    - `concept`: the bounding box of the cells of the stored `frame_color`
    - `$FrameByOutline`: replaces the stored color in `one-frame`; the frame is the one rectangle outline, of any color, whose inside holds a cell of another non-background color, and `frame_color` is derived as that outline's color; undefined where no such outline or more than one stands. Fits every pair. Witness `recolored-frame` (train1's input with the frame in 5): it breaks `one-frame` (the frame's color is `frame_color`) and the invariant that every frame is 2; plausibility `variant`, verdict `$FrameByOutline`. The concept is undefined there at the stored `frame_color`.
- `background`: the background color
    - `concept`: the stored `background` = 0
    - `background=DominantColor`: derives `background` as the commonest color of the input; undefined where colors tie for commonest. Fits every pair. Witness `background=DominantColor` (train1's frame cropped to a 6×6 grid, so the frame is the grid's border): it breaks no scene claim. It breaks the invariant that every input is 14×14 with the frame off the grid edge; in a 14×14 grid 0 is always the commonest color. Plausibility `borderline`, verdict `concept`.
- `pattern`: where the pattern is read
    - `concept`: the cells inside the frame that are not `background`
    - `$PatternAnywhere`: replaces the pattern source in `quad-pattern`; the pattern is the bounding box of every cell, anywhere in the grid, that is neither `background` nor `frame_color`; undefined where that box's side does not divide the inside's side. Fits every pair. Witness `stray-cell-outside` (train1's pattern moved against the frame's right side, and one cell of 4 just outside the frame on the pattern's top row): it breaks `one-frame` (the frame lies on a field of background) and the invariant that every cell outside the frame is 0; plausibility `borderline`, verdict `concept`.
- `fill` & `frame`, `fill` & `background`, `fill` & `pattern`, `frame` & `background`, `frame` & `pattern`, `background` & `pattern`, `scale` & `frame`, `scale` & `background`, `scale` & `pattern`, `part count` & `frame`, `part count` & `background`, `part count` & `pattern`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Output without the frame's border: every train output keeps the border in `frame_color`, so it fails Fit on every pair.
- A scale factor or an output size from a proposer: ScaleRatio, DivisorRatio and DimDiff compare input and output sizes, and the input is 14×14 in every pair while the outputs are 10×10 and 6×6, so no whole-number ratio or single difference holds. ConstOutDim gives no size, since the output sizes differ.
- `frame_color` from a proposer: SharedColor on one input gives every color of that input, DominantColor gives 0, RarestColor gives a pattern color, and UnchangedColor and ChangedColor read outputs, which a run on an input leaves empty. The derivation of the frame color by the frame's shape is formed as `$FrameByOutline`.

## Tickets filed
- none
