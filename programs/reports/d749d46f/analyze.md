# d749d46f

## Concept
- The concept fits every train and test pair (`check_concept.py`). On each witness the probe runs, it is defined and gives the output a person expects, apart from the gap witnesses, where the verdict goes to `$GapPerNeighbor`. No witness has verdict `other`. The concept file's rules state the rule as the generator applies it: each bar lies along its longer side in the flat row and stands on its longer side in the standing row, and nothing there is an approximation.

## Choice points
- `output-gap`: the spacing between neighboring bars in the output
    - `concept`: the stored `gap`, one column, in both rows of the output, whatever spacing the input has
    - `$GapPerNeighbor`: replaces the spacing part of `top-lies-flat` and `bottom-stands-up`. Each output gap between bar k and bar k+1 is the input gap between those two bars. The program reads no `gap` parameter, and the model is defined on every input where the concept is defined. Fits every pair. Witness `gap-two`: it breaks `bars-in-a-row` at the stored `gap` = 1, plausibility `variant`, verdict `$GapPerNeighbor`, and it breaks the invariant that the bars of every input stand one column apart.
    - `$GapFromInput`: replaces the same part of `top-lies-flat` and `bottom-stands-up`. Every output gap is the one gap that all neighbors in the input share, and the model is undefined on an input whose gaps differ. Fits every pair. Witness `gap-two`, where it is defined and gives `$GapPerNeighbor`'s output: it breaks `bars-in-a-row` at the stored `gap` = 1, plausibility `variant`, verdict `$GapPerNeighbor`, and it breaks the invariant that the bars of every input stand one column apart. `$GapPerNeighbor` subsumes it: where it is defined, every input gap is one value, and `$GapPerNeighbor` gives the same grid. Witness `gaps-unequal` shows that the two are not equivalent: `$GapFromInput` is undefined there, and `$GapPerNeighbor` is defined. That witness breaks `bars-in-a-row`, plausibility `borderline`, verdict `$GapPerNeighbor`, and it breaks the invariant that every input has one gap width. The branch fails Subsumption.
- `bar-color`: which of the two input colors is the bar color
    - `concept`: the color of the top-left cell (`bar-color`)
    - `$BarColorMinority`: replaces `bar-color`. The bar color is the color with fewer cells, and the model is undefined on an input where the two colors have equal counts. Fits every pair. Witness `bars-outweigh-background`: it breaks no scene claim, plausibility `variant`, verdict `concept`, and it breaks the invariant that the bar color has fewer cells than the background in every input.
    - `$BackgroundAtBottomLeft`: replaces `bar-color`. The background is the color of the bottom-left cell, and the bar color is the other color. Fails Fit at train2, where the bottom-left cell is on the full-height bar at col 0.
- `output-height`: where the output's row count comes from
    - `concept`: the stored `output-height`, 10
    - `output-height=ConstOutDim`: derives `output-height` by `ConstOutDim`. That derivation reads only `ex_out`, so on an input alone it gives no value, and the model is undefined on every input. Fails Fit at train0.
- `output-gap` & `bar-color`, `output-gap` & `output-height`, `bar-color` & `output-height`: the two branches' changes applied together

## Open parameters
none

## Not formed
- The bars in an order sorted by size: train0's output keeps the input order, with longer sides 2, 2, 1, 3, 1, 4, and no sort gives that order.
- Each bar unturned, or each bar transposed, in the flat row: in train0 the 2x1 bar stays 2x1 in the flat row and the 1x2 bar turns to 2x1, so only the longer-side reading fits.
- The standing row packed from the far edge: train0's standing row starts at col 0 and leaves cols 12–17 empty. The edge is the `pack-edge` parameter, which a reassignment changes, so it is not a branch.
- An output height derived from the input: the input heights are 4, 5, 6 and 3, and the longest bar sides are 4, 5, 6 and 3, while every output is 10 rows tall. No count of the input gives 10 on all four.
- A canvas that grows when a standing bar is taller than `output-height`: no pair shows a height other than 10, and no reading of the pairs gives the height such a canvas would take.

## Tickets filed
none
