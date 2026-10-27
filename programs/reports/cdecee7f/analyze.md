# cdecee7f

## Concept
- Fits every pair (`work/task/cdecee7f/probe.py`). No witness has the verdict `other`, and the concept file's rules are the rule as the generator applies it, with no approximation.
- The inputs hold 6, 7, 9 and 9 dots, 31 in all. No two of them share a column and no two touch, even at a corner. Random rows would make some of them touch, so `scattered-dots` states both as generator constraints.

## Choice points
- `dot-unit`
    - `concept`: each cell that is not `bg` is a dot
    - `$Objects`: each 4-connected component of one color is a dot, which takes its color and is ranked by its column nearest the `scan-dir` edge; undefined where two components share that column. Fits every pair. Witness `touching-same-color-row` breaks `scattered-dots` (no two touching), plausibility `foreign`, verdict `concept`; the invariant it breaks: no two dots of any input touch, even at a corner.
        - `adjacency`
            - `concept`: 4-adjacency
            - `$Diag8`: 8-adjacency, so two dots of one color that meet at a corner are one dot. Fits every pair. Witness `touching-same-color-corner` breaks `scattered-dots` (no two touching), plausibility `foreign`, verdict `concept`; the invariant it breaks: no two dots of any input touch, even at a corner.
        - `object-color`
            - `concept`: a component holds one color
            - `$MixedObjects`: a component joins touching cells of any color that is not `bg`; undefined where a component holds two colors. Fits every pair. Fails Subsumption: where it is defined, each component holds one color, so its output is the output of `$Objects`.
- `bg`
    - `concept`: `bg` stored, `0`
    - `bg=DominantColor`: `bg` is the commonest color of the input; it is defined on every input. Fits every pair. Witness `bg=DominantColor` breaks `scattered-dots` (a field of `0`), plausibility `variant`, verdict `bg=DominantColor`; the invariant it breaks: the field of every input is `0`.
    - `bg=SharedColor`: `bg` takes each color of the input. Fails Fit at train0: at each value other than `0`, the `0` cells are dots, several in a column, and the model is undefined.
- `fill-path`
    - `concept`: the snake path from `fill-corner` along `fill-axis`
        - `out-size`
            - `concept`: `out-size` stored, 3×3
            - `$FitSquare`: the output's side is the least k with k×k at least the dot count. Fits every pair. Witness `four-dots`, plausibility `ordinary`, verdict `concept`.
            - `$FillRows`: the output is 3 wide, with as many rows as the dots fill. Fails Fit at train0: 6 dots give 2 rows, and the output has 3.
            - `out-size=ConstOutDim`: on an input alone the proposer gives no value, so the model is undefined everywhere. Fails Fit at train0.
    - `$StoredPath`: a stored table `fill_order` maps each rank to an output cell, and the output's frame is the frame of those cells; the train pairs determine it, and train2 shows all 9 ranks. Fits every pair. Witness `raster-path`, at the assignment that sets `fill_order` to raster order, plausibility `ordinary`, verdict `$StoredPath`.
    - `$RowMajor`: each row runs from the left. Fails Fit at train0: row 1 reads `6 7 9`.
    - `$Spiral`: a clockwise spiral from the top-left. Fails Fit at train0: the fifth dot goes to (2,2).
    - `$ColumnIndex`: a dot takes the path cell at its column index, with no ranking. Fails Fit at train0: no dot sits in col 3, so (1,2) stays empty, and the output holds 6 there.
- `overflow`
    - `concept`: the dots past the last path cell are dropped
    - `$Overflow`: the model is undefined where the dots outnumber the path's cells. Fits every pair. Fails Subsumption: where it is defined, its output is the concept's. Witness `ten-dots` breaks `scattered-dots` (no more dots than the cells of an `out-size` grid), plausibility `borderline`, verdict `$FitSquare`; the invariant it breaks: no input holds more than 9 dots.
- `dot-unit` & `bg`, `dot-unit` & `fill-path`, `dot-unit` & `out-size`, `dot-unit` & `overflow`, `adjacency` & `bg`, `adjacency` & `fill-path`, `adjacency` & `out-size`, `adjacency` & `overflow`, `object-color` & `bg`, `object-color` & `fill-path`, `object-color` & `out-size`, `object-color` & `overflow`, `bg` & `fill-path`, `bg` & `out-size`, `bg` & `overflow`, `fill-path` & `overflow`: the two branches' changes applied together
- `out-size` & `overflow`: the two branches' changes applied together
    - `$FitSquare` & `$Overflow`: the model of `$FitSquare` alone, because its square holds every dot and no dot overflows

## Not formed
- A separate color for the empty output cells: in every variant task it follows from `bg`, so it is derived data and not a second parameter.
- Ranking by row, or from another edge: these are values of `scan-dir`, and the pairs fix `left`.
- Another start corner or axis for the snake: these are values of `fill-corner` and `fill-axis`, and the pairs fix top-left and horizontal.

## Tickets filed
- 10-608_task_cdecee7f_analyze.md
