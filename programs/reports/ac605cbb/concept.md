# ac605cbb

## Concept
- Each colored dot grows a path whose shape its color sets: a line of `line_color` that ends in a copy of the dot. Where two lines cross, the crossing cell turns `cross_color` and a diagonal of `cross_color` runs from it toward `cross_dir` to the grid edge.

## Scene
- `background`: every cell that is not a seed is `background`.
- `single-cell-seeds`: the input holds a few seeds, each one cell, and no two seeds touch.
- `seed-colors-keyed`: each seed's color is a key of `stamp`, and no color occurs on more than one seed.
- `stamps-fit`: each seed's stamp lies inside the grid.
- `stamps-meet-at-lines`: two stamps share no cell other than a cell that is a line cell of both, and no line cell of a stamp lands on a seed.

## Rules
- `keep-input`: each input cell keeps its color unless a rule below paints it.
- `stamp-path`: at each seed, the stamp of the seed's color is drawn from the seed: its line cells in `line_color` and its end cell in the seed's color.
- `cross-cell`: a cell that is a line cell of two stamps is `cross_color`.
- `cross-ray`: from each crossing cell, the cells toward `cross_dir` up to the grid edge are `cross_color`.

## Parameters
- `stamp`: 1 → right, right, up; 2 → left, left, left, left; 3 → down, down, down; 6 → up, up, up, up, up, up
    - per seed color, the unit steps of the path from the seed; every cell the path reaches is a line cell, except the last, which is the end cell
- `line_color`: 5
- `cross_color`: 4
- `cross_dir`: down-left (`DIAG_BL`)

## Scene parameters
- `background`: 0
