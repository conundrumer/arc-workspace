# f1cefba8

## Concept
- Fits every pair, train0–2 and test0 (probe `work/task/f1cefba8/probe.py`). Every rule has a relational form: nubs are inner-color cells 4-adjacent to the inner rectangle's side, and lines are the nub's row or column, split by the inner rectangle's span and the background. So no rule is approximated.
- No witness has verdict `other`.
- Frame color and inner color are derived per input. They are 8/2, 1/4, 2/3 and 1/8 across the pairs, so no stored value fits. Only `background` (0) is stored.
- The concept model is undefined wherever the non-background cells do not form one solid rectangle with one solid inner rectangle. Painting background cells and painting every cell outside the frame therefore never part on an input where the model is defined.

## Choice points
- `background-source`
    - `concept`: `background` stored as 0
    - `background=DominantColor`: derives `background` from the input alone as its commonest color, in place of the stored value. It is undefined where the commonest color is tied, and where the non-background cells on that color form no framed rectangle. It fits every pair, since 0 is the commonest color in each input. Witness `background=DominantColor`: a 20×20 grid with a 16×16 frame at margin 2, whose inner color 4 (146 cells) outnumbers the background 0 (144 cells). It breaks no scene claim, plausibility `ordinary`, verdict `concept`. The concept draws the lines; the branch takes 4 as the background and is undefined.
    - `background=SharedColor`: derives `background` as each color of the one input. Every input holds three colors, so the background takes three values and the branch is undefined on every input. It fails Fit at train0.
    - `background=RarestColor`: derives `background` as the input's rarest color, which is the inner or frame color in every input and never 0. It fails Fit at train0.
- `nub-cells`
    - `concept`: a nub is an inner-color cell 4-adjacent to a side of the inner rectangle (`nubs`).
    - `$AnyRingCell`: replaces `nubs`. Every inner-color cell outside the inner rectangle that lies in its row span or its column span marks a line. It has no parameters and is undefined where the concept is. It fits every pair. Witness `stray-ring-cell`: test0's input with an extra 8 at (3,8), on the outer row of the top ring. It breaks the scene claim `nubs` and the input invariant "every inner-color cell outside the inner rectangle touches it". Plausibility `borderline`, verdict `$AnyRingCell`. The concept keeps the cell and draws no line; the branch erases it and draws column 8 through the inner rectangle in 1 and out to both edges in 8.
- `line-outside-extent`
    - `concept`: the line takes the inner color on the background on both sides of the frame, out to the grid edges (`line-outside`).
    - `$NubSideOnly`: replaces `line-outside`, painting only on the nub's side of the frame. It fails Fit at train0: the top nub's column 7 is also painted at rows 15–18, the bottom nub's column 4 at rows 0–1, and the right nub's row 6 at col 0.
- `line-in-ring`
    - `concept`: the frame ring keeps the frame color along the line, except that the nub is erased (`rest-kept`, `nub-erased`).
    - `$RingLineInner`: replaces `rest-kept`. On the nub's side, the ring cells of the line between the nub and the background take the inner color. It fails Fit at train0: (2,7) is 8 in the output, not 2.
- `nub-line-axis`
    - `concept`: a nub on the top or bottom side marks its column, and a nub on the left or right side marks its row (`line-through-inner`).
    - `$NubBothLines`: adds to `line-through-inner` a line on the nub's other axis as well. It fails Fit at train0: the top nub's row 3 is 0 outside the frame at cols 0 and 12.
- `background-source` & `nub-cells`, `background-source` & `line-outside-extent`, `background-source` & `line-in-ring`, `background-source` & `nub-line-axis`, `nub-cells` & `line-outside-extent`, `nub-cells` & `line-in-ring`, `nub-cells` & `nub-line-axis`, `line-outside-extent` & `line-in-ring`, `line-outside-extent` & `nub-line-axis`, `line-in-ring` & `nub-line-axis`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Stored frame color and inner color: they differ in every pair (8/2, 1/4, 2/3, 1/8), so no stored value fits any two pairs.
- Painting every cell outside the frame instead of only the background cells: the concept model is undefined on any input with a non-background cell outside the framed rectangle, because the non-background cells form no solid rectangle. The two readings therefore have no divergence witness.
- Resolving where lines cross: a row line and a column line meet only inside the inner rectangle, where both give the frame color. Outside the frame, row lines lie beside it and column lines above and below it, so the two never meet.
- Background derivations that read outputs (UnchangedColor, ChangedColor, VanishedColor, OutNewColor, AnyOutNewColor, ChangedPairs, VanishedNewPairs): a `@derive` run reads one input and no output, so these give no value and their branches are undefined on every input.
- `frame-width` (2): a scene parameter that the program does not read. Nubs are found by adjacency to the inner rectangle, not by their distance from the frame edge.

## Tickets filed
- none
