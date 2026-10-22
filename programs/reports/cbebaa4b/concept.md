# cbebaa4b

## Concept
- Put the jigsaw together: each piece carries `2` dots that mark where it joins another piece, and every piece slides, without turning, until its dots sit on the matching dots of its neighbours, building out from the `4` piece, which stays where it is.

## Scene
- `pieces`: on a field of `background`, the input holds several pieces, each a 4-connected shape of one color other than `background` and `connector`, with single `connector` cells beside it, each 4-adjacent to that piece and to no other.
- `one-anchor`: exactly one piece has the color `anchor`.
- `pieces-fit`: there is exactly one way to translate each piece other than the anchor piece, the anchor piece fixed, such that each `connector` cell lands on a `connector` cell of exactly one other piece, no other cells of two pieces share a place, and the whole assembly lies inside the grid.

## Rules
- `anchor-stays`: the anchor piece and its `connector` cells keep their places.
- `assemble`: every other piece, with its `connector` cells, moves by its translation in that fit.
- `rest-background`: every other output cell is `background`.

## Parameters
- `background`: `0`
- `connector`: `2`
    - the color of the dots that mark the joins
- `anchor`: `4`
    - the color of the piece that does not move

## Scene parameters
- none
