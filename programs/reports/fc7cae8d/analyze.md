# fc7cae8d

## Concept
- Fits every pair (`work/task/fc7cae8d/check_concept.py`): the picture is the box between its two strips, and the D4 element that takes each strip's side to the grid edge of its color is `ad` on train 0, `cc` on train 1 and train 2, and `dg` on test 0. No witness has verdict `other`. The concept as written is the rule the generator applies, not an approximation of it.
- A solid frame edge can carry a stray cell of the other frame color next to the corner: on test 0, (1,28) holds 2 on the right edge, which is 3. The check therefore reads each edge without its two cells at each end. The parameterization is empty. `background` 0 and `noise_color` 5 are scene parameters that the program does not read.

## Choice points
- `orientation`: which D4 element turns the picture
    - `concept`: the element that takes the side each strip borders to the grid edge of that strip's color (`orient-by-color`)
    - `$CornerSwap`: replaces `orient-by-color`. Of the two elements that take the strips' corner of the picture to the corner where the solid frame edges meet, it uses the one that swaps the axes, and it reads no strip color. No parameters. Defined wherever the concept is. Fits every pair, since every pair's element (`ad`, `cc`, `cc`, `dg`) swaps the axes. Witness `same-axis-colors`: train 2 input with the two strip colors swapped (top strip 4, left strip 2). It breaks no scene claim. Plausibility `ordinary`, verdict `concept`. The concept gives the top-bottom flip and `$CornerSwap` gives the counterclockwise quarter turn.
    - `$StoredD4`: replaces `orient-by-color` with a stored D4 parameter `transform` applied to the cropped picture (the 7468f01a form). Fails Fit at train 1: train 0 needs `ad` and train 1 needs `cc`.
    - `$RotationOnly`: replaces `orient-by-color` with the C4 element that takes each strip to the edge of its color. Undefined where only a reflection does this. Fails Fit at train 0, which needs the reflection `ad`, so this model is undefined there.
    - `$MirrorOnly`: replaces `orient-by-color` with the reflection that takes each strip to the edge of its color (the 846bdb03 form). Undefined where only a rotation does this. Fails Fit at train 1, which needs the rotation `cc`.
- `extent`: which cells of the input form the picture
    - `concept`: the box whose rows the vertical strip spans and whose columns the horizontal strip spans, strips excluded (`crop-picture`)
    - `$ContentBox`: replaces `crop-picture`. The box is the bounding box of the largest 8-connected set of cells that are neither `background` nor `noise_color` nor a frame color. No parameters. Defined on every input that has such a cell. Fits every pair, because every edge line of each picture holds a non-background cell. Witness `blank-far-edge`: train 2 input with the picture's right column (rows 5–9, col 8) set to `background`. It breaks no scene claim. Plausibility `variant`, verdict `concept`. It breaks the invariant of the inputs that every edge line of the picture holds a cell other than `background`. The concept keeps the 5×5 box, whose top output row is `0 0 0 0 0`. `$ContentBox` gives a 4×5 box without that row.
    - `$KeepStrips`: replaces `crop-picture` with the box that includes the two strips and the cell at their corner. Fails Fit at train 0: the 16×12 box, turned by `ad`, gives 12×16, and the pair's output is 11×15.
- `orientation` & `extent`: the two branches' changes applied together

## Open parameters
none

## Not formed
- `0` cells of the picture recolored to the picture's main color: the train 0 output keeps its `0` cells (rows 9–10, cols 10–13), and so does the train 2 output (row 0, cols 3–4). No reader of the pairs could take this claim.
- Other ways to find the frame edges (the edge holding the most cells of a color, or the edge next to the stray cells of its color) and the strips (a full-length line along a picture side, or the longest interior run of a frame color): these are parses of one claim. On every input the generator produces they give the same edges and strips, so they are implementations of `color-frame` and `picture`, not different claims.
- Pairing each strip with the frame edge of the other color: the D4 element would be the half turn on train 0, giving a 15×11 output where the pair's is 11×15. Pairing by color is the only color reading the pairs allow, and `$CornerSwap` covers the reading that ignores color.
- No lib component or proposer gives a parameter that the program reads (the parameterization is empty), so there is no `@derive` or `@store` branch.

## Tickets filed
- none
