# e78887d1

## Concept
- Fits every pair (concept.md): the patterns of the last band move `shift-step` (1) slots toward `shift-dir` (left) cyclically, and each pattern is drawn in the color of the slot it lands in. Train 2 has one band, so the move is a stored parameter: no input with one band shows it.
- The generator applies the rule as concept.md states it: it picks a slot color and a pattern for each slot, each band moves the patterns of the band before it one slot to the left, and the output is the band that would come after the last band. No witness has the verdict `other`.

## Choice points
- `step-source`: where the move from one band to the next comes from
    - `concept`: the stored `shift-dir` and `shift-step`
    - `$StepFromBands`: replaces `next-band`: the move is the cyclic move of slots that takes each band's patterns onto the next band's patterns, read off the input, and `shift-dir` and `shift-step` are not read; undefined on an input with one band, and where no cyclic move takes each band onto the next. Fails Fit at train 2: that input has one band.
    - `$StepFromBandsOrStored`: replaces `next-band`: the move is read off the bands as `$StepFromBands` reads it, and on an input with one band it is the stored `shift-dir` and `shift-step`; undefined where an input has more than one band and no cyclic move takes each band onto the next. Fits every pair. Witness `bands-move-right`: each band moves the patterns of the band before it one slot to the right. It breaks `band-shift`. Plausibility `variant`, verdict `$StepFromBandsOrStored`. The invariant of the inputs it breaks: in every input, each band moves the patterns of the band before it one slot to the left.
    - `$PermutationFromBandsOrStored`: replaces `next-band`: the move is each permutation of slots that takes each band's patterns onto the next band's patterns, read off the input and applied to the last band, and on an input with one band it is the stored `shift-dir` and `shift-step`; undefined where an input has more than one band and no permutation takes each band onto the next. Fits every pair. Witness `bands-swap-two`: the second band is the first with the patterns of its first two slots swapped. It breaks `band-shift`, and `$StepFromBandsOrStored` is undefined there. Plausibility `borderline`, verdict `$PermutationFromBandsOrStored`. The invariant of the inputs it breaks: consecutive bands differ by a cyclic move of the slots.
- `output-band`: which band the output continues from
    - `concept`: the last band, moved once
    - `$FromFirstBand`: replaces `next-band`: the first band's patterns moved `shift-step` × (the number of bands) slots toward `shift-dir`, drawn in the last band's slot colors; undefined nowhere the concept is defined. Fits every pair. Witness `bands-unrelated`: the second band holds none of the first band's patterns. It breaks `band-shift`. Plausibility `foreign`, verdict `concept`. The invariant of the inputs it breaks: each band holds the patterns of the band before it.
- `glyph-color`: the color a moved pattern is drawn in
    - `concept`: the color of the slot it lands in, in the last band
    - `$SlotColorFromFirstBand`: replaces the color in `next-band` with the color of the slot it lands in, in the first band; undefined nowhere the concept is defined. Fits every pair. Witness `slot-colors-change`: the second band draws its slots in colors 5, 6, 7, and the first band in 2, 3, 1. It breaks `slot-colors`. Plausibility `foreign`, verdict `concept`. The invariant of the inputs it breaks: each slot position holds one color in every band.
    - `$GlyphKeepsColor`: replaces the color in `next-band` with the color the pattern has in the last band, so that colors move with the patterns; undefined nowhere the concept is defined. Fails Fit at train 0: train0 output rows 0–2, cols 0–2 are drawn in 2, and the pattern there is drawn in 1 in the last band (train0 input rows 9–11, cols 4–6).
- `tiling`: how the input is cut into slots
    - `concept`: cells of the stored `glyph-size` with blank lines `gap` wide between them, and on the band axis a border `gap` wide
        - `glyph-size`
            - `concept`: stored, 3
            - `glyph-size=SepTileDim`: replaces the stored `glyph-size` in `glyph-tiling` with the segment dims of a witnessed separator tiling of the input; undefined where it gives none. Fails Fit at train 1: the derivation gives 3 and 4 on that input, so the model gives more than one output.
            - `glyph-size=TileDim`: replaces the stored `glyph-size` with the tile dims that fit an input axis; undefined where it gives none. Fails Fit at train 0: the derivation gives 1 to 6 on that input.
        - `gap`
            - `concept`: stored, 1
            - `gap=SepThickness`: replaces the stored `gap` in `glyph-tiling` with the separator thicknesses of a witnessed tiling of the input; undefined where it gives none. It gives 1 on every input of the evidence, so it fits every pair. Witness `gap=SepThickness`: four slots two columns apart, with two blank rows above and below the band. It breaks `glyph-tiling`. The concept is undefined there, because a tiling of 3-wide cells with 1-wide lines does not fit an 18-wide grid. Plausibility `variant`, verdict `gap=SepThickness`. The invariant of the inputs it breaks: the blank lines are one cell wide.
    - `$CutAtBlankLines`: replaces `glyph-tiling`: the slots are the tiles that the input's lines of background cut, and `glyph-size` and `gap` are not read; undefined nowhere the concept is defined. Fails Fit at train 2: train2 input col 13 is background in every row and lies inside the glyph at cols 12–14, so the cut splits that glyph into two tiles and the band has five slots.
- `background`
    - `concept`: stored, 0
    - `background=DominantColor`: replaces the stored `background` in `glyph-tiling` and `bands` with each color whose cell count is the highest of the input; undefined where it gives none. It gives 0 on every input of the evidence, so it fits every pair. Witness `background=DominantColor`: the field is 8 in place of 0. It breaks `glyph-tiling` and `bands`. The concept is undefined there, because the blank lines hold 8 and not the stored 0. Plausibility `variant`, verdict `background=DominantColor`. The invariant of the inputs it breaks: the field is 0.
    - `background=SharedColor`: replaces the stored `background` with each color of the input. Fails Fit at train 0: the derivation gives 0, 1, 2 and 3 on that input.
    - `background=RarestColor`: replaces the stored `background` with each color whose cell count is the lowest of the input. Fails Fit at train 0: the derivation gives 1, 2 and 3 on that input.
- `step-source` & `output-band`, `step-source` & `glyph-color`, `step-source` & `tiling`, `step-source` & `glyph-size`, `step-source` & `gap`, `step-source` & `background`, `output-band` & `glyph-color`, `output-band` & `tiling`, `output-band` & `glyph-size`, `output-band` & `gap`, `output-band` & `background`, `glyph-color` & `tiling`, `glyph-color` & `glyph-size`, `glyph-color` & `gap`, `glyph-color` & `background`, `tiling` & `background`, `glyph-size` & `gap`, `glyph-size` & `background`, `gap` & `background`: the two branches' changes applied together

## Open parameters
none

## Not formed
- The output is the first band again: train 0's output equals its first band, because three moves of one slot over three slots bring the patterns back to where they started. Train 1's output is not its first band, and the concept gives train 0's output by the move it gives the other pairs. The concept states the same output there, so this claim adds no model that a reading of the pairs gives.

## Tickets filed
none
