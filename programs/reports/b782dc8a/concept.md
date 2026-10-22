# b782dc8a

## Concept
- A maze has a short two-color checkerboard painted in one of its corridors; flood the corridor system that the paint touches, continuing the alternation of the two colors cell by cell.

## Scene
- `maze`: every cell is `wall` or `background`, apart from the seed cells.
- `seed`: the seed is a few cells of two colors, neither of them `wall` or `background`: one cell of the first color, and each of its 4-neighbors that is not `wall`, in the second color.
- `seed-checkerboard`: two seed cells have the same color exactly when their row+column sums have the same parity.

## Rules
- `flood-seed-region`: each `background` cell that a 4-adjacent walk through `background` cells joins to a seed cell takes the color of the seed cells whose row+column parity is its own.
- `rest-unchanged`: every other cell keeps its input color.

## Parameters
- `background`: 0
    - the color the flood passes through and paints

## Scene parameters
- `wall`: 8
    - the color the flood does not pass through
