# bae5c565

## Concept
- The colors along one edge drop into their columns and stack into a stepped mountain around a stalk: the mountain's top is the stalk's top, and each column away from the stalk is one cell shorter than the column next to it.

## Scene
- `square-grid`: the grid is square, with an odd side.
- `palette-row`: the row on edge `palette_side` holds a color in every cell, and that color is `background` only in the stalk's column.
- `stalk`: one straight line of color `stalk_color` runs along the center column, from the edge opposite `palette_side` toward `palette_side`, and stops at least one row short of the palette row.
- `stalk-reach`: the stalk reaches at least to the middle row, so every column of the mountain gets one cell or more.
- `background-field`: every cell that is not in the palette row or the stalk is `background`.

## Rules
- `clear-palette`: the palette row becomes `background`.
- `keep-stalk`: the stalk stays as it is.
- `stepped-fill`: in each column other than the stalk's, at distance d from the stalk's column, the cells from d rows past the stalk's end nearest the palette row to the edge opposite `palette_side` take that column's palette color.
- `rest-background`: every other cell is `background`.

## Parameters
- `background`: 5
- `palette_side`: top
    - the edge that holds the palette row; the stalk and the mountain stand on the opposite edge

## Scene parameters
- `stalk_color`: 8
