# db3e9e38

## Concept
- A line hangs from the top edge, and a staircase grows out from it on both sides: each column one step farther out is one cell shorter, and the columns alternate between the line's color and a second color.

## Scene
- `hanging-line`: the only non-background cells form one straight line of the line color `line_color`, perpendicular to the edge `anchor_edge` and touching that edge, on a field of `background`.

## Rules
- `staircase-length`: a column at distance d from the line, on either side, is filled along the line's rows, from the line's end nearest `anchor_edge`, for L - d cells, with L the line's length; a column with L - d <= 0 stays background, and the grid edge clips the staircase.
- `alternating-color`: a filled column at even distance d takes the line's color, and one at odd d takes `stripe_color`.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `anchor_edge`: top
    - the edge the line touches and the staircase hangs from
- `stripe_color`: 8
    - the color of the columns at odd distance from the line
- `background`: 0

## Scene parameters
- `line_color`: 7
