# dc2aa30b

## Concept
- The concept fits every train pair and the test pair (`work/task/dc2aa30b/probe.py pairs`). Each input gives its nine tiles nine distinct counts of 1, so the rank of each tile is the rank of its count, and the concept places tiles by rank, not by count: train1 counts 1 to 9 and train0 counts 0 to 8 both fill the slots in one order.
- No witness has the verdict `other`. The rules have a relational form, and the generator applies them as the concept file states them.

## Choice points
- `tie-order`: the output where two tiles hold one count of `counted_color`
    - `concept`: the model is undefined there (`distinct-counts`)
    - `$TieAnyOrder`: replaces `rank-by-count`: tiles that tie take their run of rank slots in every order, and the output holds the grid of each order; parameters as the concept's; undefined where the concept is, apart from ties. Fits every pair. Witness `tied-counts`: it breaks `distinct-counts`; it stands at the stored assignment; plausibility `borderline`, verdict `$TieAnyOrder`; it breaks the invariant that every input gives its nine tiles nine distinct counts, of the ten that a 3×3 tile can hold.
- `tile-layout`: where the tiles are cut
    - `concept`: at the full lines of `divider_color` (`divider-board`)
        - `divider-color-source`: the color of the divider lines
            - `concept`: the stored `divider_color`
            - `divider_color=SharedColor`: replaces the stored `divider_color` with the colors the input holds, so a full line uniform in any of them is a divider; undefined where the concept is, with the divider color left out. Fits every pair. Witness `divider_color=SharedColor`: it breaks `divider-board` at `divider_color` 0; it stands at the stored assignment; plausibility `variant`, verdict `divider_color=SharedColor`; it breaks the invariant that every divider line is 0.
            - `divider_color=DominantColor`: the input's commonest color is the divider color. Fails Fit at train0: it derives 2, which makes no full line, so the model is undefined.
            - `divider_color=RarestColor`: the input's rarest color is the divider color. Fails Fit at train0: it derives 1, which makes no full line, so the model is undefined.
    - `tile_layout=stored`: replaces the reading of `divider-board` with a stored layout, `tile_count` 3, `tile_size` 3 and a gap of 1, and keeps the cells between tiles as they are, of any color; it reads no `divider_color`; undefined where the grid's extent is not `tile_count`·`tile_size` + (`tile_count` − 1)·gap, and where counts tie. Fits every pair. Witness `tile_layout=stored`: it breaks `divider-board` at `divider_color` 0; it stands at the stored assignment; plausibility `variant`, verdict `tile_layout=stored`; it breaks the invariant that every divider line is 0.
- `counted-color-source`: the color whose cells a tile's rank counts
    - `concept`: the stored `counted_color`
    - `counted_color=DominantColor`: the input's commonest color is counted. Fails Fit at train0: it derives 2, and the tiles come out in the reverse order.
    - `counted_color=RarestColor`: the input's rarest color is counted. Fails Fit at train1: it derives 2, and the tiles come out in the reverse order.
    - `counted_color=SharedColor`: every color the input holds is counted. Fails Fit at train0: every tile counts 9, so all nine tie and the model is undefined.
- `tie-order` & `tile-layout`, `tie-order` & `divider-color-source`, `tie-order` & `counted-color-source`, `tile-layout` & `counted-color-source`, `divider-color-source` & `counted-color-source`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A slot order that fills columns first, or that turns back at each row: train0 separates them, and of the sixteen assignments of color, corner and `fill_axis`, only the two assignments (1, bottom-left) and (2, top-right) of `counted_color` with `order_corner` fit. The concept case runs both assignments and is undefined on an input where those values give different outputs.
- Placing a tile at the slot its count gives rather than its rank: train0 counts 0 to 8 and train1 counts 1 to 9, and both fill the slots in one order. Ten counts also cannot map onto nine slots.
- A tile changed as it is placed: every tile of every output is an unchanged copy of an input tile.
- Ranking by the count of cells that are not `other_color`: it is the assignment (2, top-right) of `counted_color` with `order_corner`, which the concept case runs with (1, bottom-left) and which ranks by the count of 2; the case is undefined on an input where those values give different outputs.
- A stored permutation of tile positions: each pair moves its tiles by a different permutation, so no one permutation fits the train pairs.
- A derived `order_corner` or `fill_axis`: no proposer gives an orientation value.
- A tile layout derived by `SepTileCount`, `SepTileDim` and `SepThickness`: it reads the tiling of uniform lines with no reading of their color, which is the model of `divider_color=SharedColor`.
- A derived `counted_color` or `divider_color` by `OutNewColor`, `AnyOutNewColor`, `VanishedColor`, `ChangedColor`, `UnchangedColor`, `ChangedPairs` or `VanishedNewPairs`: each reads `ex_out`, which is empty in a run on one input, so it gives no value. `CountRankAsc` and `CountRankDesc` give a rank per color, not one color.

## Tickets filed
- 10-825_task_dc2aa30b_analyze.md
