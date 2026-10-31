# f35d900a

## Concept
- Four dots mark the corners of a rectangle, the two diagonals in two colors; each dot gets a ring of the other color, and each side of the rectangle is dotted gray from both ends toward its middle.

## Scene
- `four-corner-markers`: on a field of `background`, exactly four single cells, at the corners of an axis-aligned rectangle.
- `diagonal-colors`: the markers have two colors, and the two markers on each diagonal share one.
- `rings-in-frame`: no marker lies on the frame edge, so its 3×3 box fits the grid.
- `rings-apart`: the two markers of each side are at least 5 apart, so their 3×3 boxes leave a gap of at least 2 cells.

## Rules
- `swap-ring`: the 8 neighbors of each marker take the other marker color; the marker keeps its color.
- `dotted-sides`: on each side of the rectangle, a cell between the two rings takes `dot_color` where its distance to the nearer ring is odd (the cell next to a ring is at distance 1).
- `rest-unchanged`: every other cell keeps its input color.

## Parameters
- `background`: `0`
- `dot_color`: `5`

## Scene parameters
none
