# b5bb5719

## Concept
- An upside-down pyramid grows from the seed row: a cell fills when both of its diagonal neighbors in the row before it are filled, and it takes the other color from its upper-left neighbor.

## Scene
- `seed-row`: the line at the edge opposite `grow_dir` holds cells of the two colors of `swap`, with `background` cells among them, and every other cell is `background`.

## Rules
- `fill-under-pair`: row by row in `grow_dir`, a `background` cell whose two diagonal neighbors in the row before it are both filled becomes filled.
- `swap-side-neighbor`: a filled cell takes the color that `swap` pairs with the color of its diagonal neighbor on the `read_side` side in the row before it.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `background`: 7
- `swap`: 2 ↔ 5
    - the color each seed color turns into
- `grow_dir`: down
    - the direction the pyramid grows in, away from the seed row
- `read_side`: left
    - the side of the diagonal neighbor whose color is swapped

## Scene parameters
- none
