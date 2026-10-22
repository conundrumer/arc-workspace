# b7999b51

## Concept
- Fits every pair (probe `work/task/b7999b51/probe.py`). No witness has the verdict `other`.
- The generator draws each bar as tall as its rectangle. The concept reads the extent of the color's visible cells on `axis`. Under `rectangles-may-overlap` both edges of a covered rectangle show, so the two are the same on every input of the scene.
- The test pair is the one that separates the measure: the 3 rectangle is cut by the 8 bar at row 6 (test0 input rows 3–7, cols 4–9). It spans 5 rows but shows cells in only 4 rows, and its longest run is 3.

## Choice points
- `extent-measure`
    - `concept`: the bounding-box extent of each color's cells on `axis` (`extent-per-color`)
    - `$ComponentExtent`: replaces `extent-per-color` and `bar-per-color`: one bar per connected component of a color, as long as that component's extent on `axis`. Fails Fit at test0: the 3 rectangle splits into two components, extents 3 and 1.
    - `$LineCount`: replaces `extent-per-color`: the count of lines on `axis` that hold a cell of the color. Fails Fit at test0: 3 has cells in 4 rows, and the bar is 5 long.
    - `$LongestRun`: replaces `extent-per-color`: the longest unbroken run of the color's cells along `axis`. Fails Fit at test0: 3's longest run is 3.
- `order-key`
    - `concept`: bars in order of extent, longest at `order-edge` (`bars-ordered-by-extent`)
    - `$OrderByArea`: replaces `bars-ordered-by-extent`: bars in order of the color's cell count, the largest at `order-edge`. Fails Fit at train0: 7 has 32 cells and 8 has 20, so 7 comes first, and the output has 8 first.
    - `$OrderByPlace`: replaces `bars-ordered-by-extent`: bars in order of the place of the color's cells from `order-edge` (the nearest line across `axis`, then the nearest to `anchor`). Fails Fit at train0: the order would be 1 2 8 7, and the output is 8 7 1 2.
- `tie-order`
    - `concept`: no two colors share an extent (`distinct-extents`), and the model is undefined on a tie
    - `$TieByPlace`: adds a rule: bars with the same extent stand in order of their colors' places from `order-edge` (nearest line across `axis` first, then nearest to `anchor`). Reads no new parameter. Defined on every input of the concept's scene. Fits every pair. Witness `tied-extents`: breaks `distinct-extents`. Plausibility `borderline`, verdict `any`. It breaks the invariant that no two colors in an input share an extent.
    - `$TieBothOrders`: adds a rule: the output holds each order of the bars that share an extent. Fits every pair. Witness `tied-extents`: breaks `distinct-extents`. Plausibility `borderline`, verdict `any`. It breaks the invariant that no two colors in an input share an extent.
- `background`
    - `concept`: stored, 0
    - `background=DominantColor`: `background` derived as the color that holds the most cells of the input. It is undefined where two colors tie for the most cells. Fits every pair. Witness `background=DominantColor`: a 6 rectangle covers more cells than 0. It breaks no scene claim. Plausibility `borderline`, verdict `concept`. It breaks the invariant that `background` holds most cells of each input.
    - `background=SharedColor`: `background` derived as a color present in the input. On one input alone it gives every color of that input, so every color is background and no bar is drawn. Fails Fit at train0.
- `extent-measure` & `order-key`, `extent-measure` & `tie-order`, `extent-measure` & `background`, `order-key` & `tie-order`, `order-key` & `background`, `tie-order` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- The axis that measures the extent differs from the axis the bars run along: the pairs separate it. On that axis train1's widths 7, 6 and 5 would give bars of those lengths in the order 2 3 1, and the output is 2 1 3 with bars of 3, 1 and 2.
- The full height of a rectangle whose whole edge across `axis` another rectangle covers: there is no relational form, because the input does not give the hidden extent. Inside the scene (`rectangles-may-overlap`) it is the concept's extent.
- Ties ordered by color value: colors have identity and no order.
- A stored output size: the train outputs have different sizes (5×4, 3×3, 4×3).

## Tickets filed
- none
