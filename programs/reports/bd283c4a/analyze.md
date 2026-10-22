# bd283c4a

## Concept
- The concept case fits every pair at `start_corner` bottom-left and `fill_axis` vertical (`probe_orders.py`); no other corner and axis fits a pair.
- Each claim has a relational form: the cell count of each color, the rank of each color by count, the first index of each color as the sum of the counts ranked before it, and each output cell's index in the raster order from `start_corner` with `fill_axis` primary. No claim is approximated, and no witness has the verdict `other`.

## Choice points
- `fill-path`
    - `concept`: a raster order, in which every line runs from the `start_corner` side
    - `$SnakeFill`: replaces `raster-fill` with a boustrophedon order, in which each line runs opposite to the line before it; parameters `start_corner` and `fill_axis`; undefined on no input. Fails Fit at test0: the only assignment that fits train0 and train1 is top-left and vertical, and there the snake runs col 4 downward, so it gives `3` at test0 output (0,4)–(3,4), where the output has `8`.
- `color-rank`
    - `concept`: the colors are ranked by their cell count in the input
        - `tie`
            - `concept`: colors of equal count take either order, one output for each order
            - `$TieUndefined`: replaces the tie clause of `count-order`; undefined on an input where two colors have the same count. Fits every pair. Witness `tied-counts`: breaks `distinct-counts`, at the stored assignment, `borderline`, verdict `concept`, invariant broken: no two colors of an input have the same count. The concept is defined wherever `$TieUndefined` is, with the same output, so `$TieUndefined` fails Subsumption.
    - `color_rank=stored`: replaces `count-order` with a stored order over colors; undefined on an input with a color the order lacks. Fails Fit at test0: color `3` is not a key of the order (an unseen key), and train0 puts `9` before `8` where test0 puts `8` before `9`.
- `out-size`
    - `concept`: the output has the input's size
    - `out_dim=stored`: replaces `same-size` with a stored output extent, 10×10; undefined on an input whose cell count differs from the stored area. Fits every pair. Witness `out_dim=stored`: a 5×20 input of train0's 100 cells, breaks no scene claim, at the stored assignment, `variant`, verdict `concept`, invariant broken: every input is 10×10.
- `fill-path` & `color-rank`, `fill-path` & `out-size`, `color-rank` & `out-size`, `fill-path` & `tie`, `out-size` & `tie`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Ranking from the lowest count first: that model at a corner is the concept's model at the opposite corner, because the order of cells is reversed and the order of colors is reversed too, so the two are equivalent.
- A tie-break by position, such as the order in which each color's first cell comes: no pair has a tie, and no solver header, proposer or variant task gives a position by which tied colors are ordered.
- A `start_corner` or `fill_axis` derived from the input: no input has a mark or a feature that points to a corner or an axis, and no proposer derives one.
- Counting objects in place of cells: in every pair each color fills as many output cells as it has input cells, and the counts fill the frame exactly; any other count does not fill a total grid on train0.

## Tickets filed
- none
