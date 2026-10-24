# ff2825db

## Concept
- Fits every pair (train0–2, test0–1; `work/task/ff2825db/check_concept.py`). Every claim is relational: a count per color (Mode), the bounding box of a color class, and the edge cells of that box. On a tie, Mode keeps both colors, so `out` conflicts and the concept is undefined there. The scene claim `distinct-counts` states that no tie occurs. No witness has verdict `other`. The rule as the generator applies it is the rule the concept file states, with no approximation.

## Choice points
- `strip-side`: how the program locates the palette strip, and so the frame and the box
    - `concept`: `strip_side` is stored (top)
    - `$StripSideDerived`: replaces the stored `strip_side` with a derivation: the strip lies on the edge line that holds the most colors. Undefined where two edge lines tie for the most colors. Fits every pair. Witness `strip-left` (the test1 input transposed, so the strip lies in col 0). It breaks `palette-strip` and stands at the stored assignment. Plausibility `variant`, verdict `$StripSideDerived`. It breaks the invariant of the inputs that the strip lies on the top row.
- `background`
    - `concept`: `background` is stored (0)
    - `background=DominantColor`: derives `background` as the commonest color of the one input. Fails Fit at train1: it derives 2 (the frame color, 36 cells, against 24 cells of 0). Then 0 and 3 tie at 24 cells among the non-background box cells, and the model is undefined.
- `winner-measure`: what makes a scattered color the winner
    - `concept`: plurality, the color with the most cells (`winner`)
    - `$Majority`: replaces `winner`: the color that holds more than half of the scattered cells. Undefined where no color does. Fits every pair. Fails Subsumption: wherever it is defined, the concept gives the same output. Witness `three-colors-plurality` (test1 input plus two cells of 3, at (2,2) and (8,7); counts 3, 2, 2). `$Majority` is undefined on it, and no witness exists on which it is defined and differs. It breaks `scattered-cells` (`scatter_color_count` 2). Plausibility `variant`, verdict `concept`. It breaks the invariant of the inputs that exactly two colors are scattered.
        - `tie`: what the plurality gives when two colors tie for the most cells
            - `concept`: undefined (`distinct-counts`)
            - `$TieBoth`: replaces `distinct-counts` and extends `winner`: each tied color gives one output, and the output holds both grids. Undefined where more than two colors tie. Fits every pair. Witness `tied-counts` (test1 input with the 2 at (3,7) cleared; 2 cells each of 1 and 2). It breaks `distinct-counts`. Plausibility `borderline`, verdict `any`. It breaks the invariant of the inputs that one scattered color outnumbers the other.
- `count-region`: which cells the winner count reads
    - `concept`: the box inside the frame alone
    - `$CountWithStrip`: replaces `winner`: the count reads the strip's cells as well as the box's. Fits every pair, because the strip adds two cells to each of its colors. Witness `color-off-strip` (test1 input with its scattered 2 recolored 6). The concept picks 6 (3 cells against 2), and `$CountWithStrip` picks 1 (2 + 2 strip cells = 4). It breaks no scene claim of the concept. Plausibility `borderline`, verdict `concept`. It breaks the invariant of the inputs that every color of the input is one of the strip's colors.
- `strip-side` & `background`, `strip-side` & `winner-measure`, `strip-side` & `count-region`, `strip-side` & `tie`, `background` & `winner-measure`, `background` & `count-region`, `background` & `tie`, `winner-measure` & `count-region`, `count-region` & `tie`: the two branches' changes applied together
    - `$Majority` & `$CountWithStrip` takes a majority over the strip's and the box's cells together. It fails Fit at train0: 5 holds 8 of 19 cells.
- `winner-measure` & `tie`: `tie` stands under the concept branch of `winner-measure`, because a majority is never tied
    - `$Majority` & `$TieBoth`: `$Majority`'s model alone

## Open parameters
- none

## Not formed
- winner = the color whose cells have the larger bounding box: train1 ties (both boxes are 42 cells), and at train2 the box of 2 is larger. The smaller box: train0 picks 1. Fails Fit.
- winner = the color with the largest connected component (4- or 8-adjacency): at train2 every component is one cell, so it ties. Fails Fit.
- winner = the color with the most components: at train1, 4 has 8 one-cell components against fewer for 3. Fails Fit.
- outline of the bounding box of all scattered cells: train0 (the 1 at (7,2) extends the box to row 7). Fails Fit.
- outline of the rectangle that the most winner cells lie on (a repaired noisy outline): at train0 rows 4–6, cols 4–5 hold 4 of the 5s on their outline, against 3 for the output's box. Fails Fit.
- filled box in place of its outline, kept inner winner cells, kept minority cells, or a frame that keeps its color: each fails Fit at train0.
- `background` from SharedColor or RarestColor: on one input they give several values (every color present; the tied strip colors). The proposers that read outputs (OutNewColor, AnyOutNewColor, VanishedColor, ChangedColor, UnchangedColor, ChangedPairs, VanishedNewPairs) give nothing under `@derive`, which reads no output. The dimension, tiling and panel proposers have no parameter to derive.
- the winner as a stored color (DominantColor, CountRankDesc): the winner changes from input to input, so no stored value fits every pair.
- `strip_colors`, `scatter_color_count` and `grid_size`: scene parameters that the program does not read, so no branch reassigns them.

## Tickets filed
- none
