# b5bb5719

## Concept
- The concept case fits every pair, and every claim has a relational form. No witness has the verdict `other`.
- On the two colors of `swap`, the concept's color rule is the same function as "two of one color give the other color, and two different colors give the right one". Those two readings part only on a seed color outside `swap` (`$MixedTakesOtherSide`).
- The color rule is chiral: train0 (5 then 2 gives 2) and train3 (2 then 5 gives 5) fix `read_side` to left, so no rule symmetric in the two neighbors fits.

## Choice points
- `fill-condition`
    - `concept`: a `background` cell fills when both of its diagonal neighbors in the row before it are filled (`fill-under-pair`).
    - `$SpanTriangle`: replaces `fill-under-pair`: the `background` cells of the triangle under the span from the seed row's first to its last filled cell fill, row by row in `grow_dir`. Same parameters. Undefined where a triangle cell's `read_side` diagonal neighbor is `background`. Fits every pair. Witness `interior-gap`, at the stored assignment: breaks no scene claim, `ordinary`, verdict `concept`.
    - `$UnderThree`: replaces `fill-under-pair`: a cell fills when all three cells above it in the row before it are filled. Same parameters. Fails Fit at train0.
    - `$OneRow`: replaces `fill-under-pair`: only the row after the seed row fills. Same parameters. Fails Fit at train2.
- `fill-color`
    - `concept`: a filled cell takes the color that `swap` pairs with its `read_side` diagonal neighbor's color (`swap-side-neighbor`).
    - `$MixedTakesOtherSide`: replaces `swap-side-neighbor`: under two cells of one color, a filled cell takes that color's `swap` partner, and under two cells of different colors, it takes the color of the neighbor opposite `read_side`. Same parameters. Undefined where both neighbors have one color outside `swap`. Fits every pair. Witness `third-seed-color`, at the stored assignment: breaks `seed-row`, `foreign`, verdict `any`. Breaks the input invariant "every seed cell is 2, 5 or 7".
- `background`
    - `concept`: stored, 7.
    - `background=DominantColor`: derives `background` as the input's commonest color, in place of the stored value that `seed-row`, `fill-under-pair` and `keep-rest` read. Undefined where two or more colors tie for commonest. Fits every pair. Witness `background=DominantColor`, at the stored assignment: breaks `seed-row`, `variant`, verdict `background=DominantColor`. Breaks the input invariant "the field color is 7".
- `swap`
    - `concept`: stored, 2 ↔ 5.
    - `$SwapFromSeedColors`: derives `swap` as the pairing of the input's two non-`background` colors, in place of the stored value that `seed-row` and `swap-side-neighbor` read. Undefined where the input does not hold exactly two non-`background` colors. Fails Fit at train1, where the seed holds only 2.
- `grow-direction`
    - `concept`: stored, down.
    - `$GrowFromSeedEdge`: derives `grow_dir` as the direction away from the one edge whose line holds every non-`background` cell, in place of the stored value that `seed-row` and `fill-under-pair` read. Undefined where no edge line or more than one holds every such cell, and where the direction lies on `read_side`'s axis. Fits every pair. Witness `seed-at-bottom`, at the stored assignment: breaks `seed-row`, `variant`, verdict `$GrowFromSeedEdge`. Breaks the input invariant "the seed lies on the top row".
- `fill-condition` & `fill-color`, `fill-condition` & `background`, `fill-condition` & `swap`, `fill-condition` & `grow-direction`, `fill-color` & `background`, `fill-color` & `swap`, `fill-color` & `grow-direction`, `background` & `swap`, `background` & `grow-direction`, `swap` & `grow-direction`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A derived `read_side`: a single input holds no sign of the side, so no derivation from the input gives it.
- `swap` from `ChangedPairs` or `VanishedNewPairs`: both read `ex_out`, which is empty in a run on one input. Because of this, they give no value on any input and fail Fit at train0.
- `background` from `SharedColor` or `RarestColor`: on one input, `SharedColor` gives every color of the input. Then every cell is background, nothing fills, and it fails Fit at train0. `RarestColor` gives the seed colors 5 and 2 at train0, in place of 7, and it fails Fit at train0.
- A color rule that reads the two neighbors as an unordered pair: train0 and train3 have the same pair {2, 5} and give 2 and 5. It fails Fit at train0 or train3.
- Coloring a cell by the seed color at the head of its `read_side` diagonal, swapped once per row: this is equivalent to the concept, because a filled cell's whole diagonal back to the seed row is filled.
- A fill condition that reads the neighbor above on the `read_side` side and the neighbor directly above: it fails Fit at train0, where (1,2) fills under (0,2) = 7.
- Growth from filled pairs outside the seed row: the concept's rule already reads every row, so this gives the same model.

## Tickets filed
- none
