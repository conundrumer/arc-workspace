# ea32f347

## Concept
- Three straight gray bars of different lengths are recolored by their length rank: the longest bar takes one color, the middle bar another, and the shortest bar a third.

## Scene
- `background`: every cell that is not a bar cell has the color `background`.
- `straight-bars`: the input holds `bar_count` bars of the color `bar_color`, each a 4-connected straight run of cells, one cell wide, horizontal or vertical, and no two bars touch.
- `distinct-lengths`: no two bars have the same length.

## Rules
- `rank-by-length`: a bar's length is its cell count, and its rank is the number of distinct lengths longer than its own, so bars of one length share a rank.
- `recolor-by-rank`: each cell of a bar takes the color `rank_color` gives to that bar's rank, and every other cell keeps its input color; undefined where a rank has no entry in `rank_color`.

## Parameters
- `bar_color`: `5`
- `rank_color`: rank 0 (longest) → `1`, rank 1 → `4`, rank 2 (shortest) → `2`

## Scene parameters
- `background`: `0`
- `bar_count`: `3`
