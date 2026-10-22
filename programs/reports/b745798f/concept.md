# b745798f

## Concept
- Four small L-shaped pieces each point a bend toward one corner; each piece moves to the grid corner it points at and grows its two arms along the grid edges up to the middle line.

## Scene
- `square-odd-grid`: the grid is square, with an odd side, so one middle row and one middle column split it into four equal quadrants.
- `background-field`: every cell outside the pieces is `background`.
- `four-l-pieces`: the input holds four pieces, each a one-color connected set (4-adjacency within its color) of three cells that fill a 2×2 box less one cell; pieces may touch pieces of other colors.
- `one-piece-per-corner`: the bend cell of each piece (the cell of the 2×2 box opposite the missing cell) sits at a different corner of its box, so each of the four corner directions has exactly one piece.

## Rules
- `piece-to-corner`: each piece goes to the grid corner in the direction its bend cell takes in its 2×2 box, and its color is kept.
- `arms-to-middle`: at that corner, the piece's color fills the cells of both grid edges through that corner that lie nearer that corner than the edge's other end, (side - 1) / 2 cells on each edge of an odd side, so each arm stops one cell before the middle line.
- `rest-background`: every other output cell, the middle row and column included, is `background`; the output has the input's size.

## Parameters
- `background`: 8

## Scene parameters
- none
