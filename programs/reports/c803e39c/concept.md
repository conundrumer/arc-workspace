# c803e39c

## Concept
- The first shape is a tile and the second shape is a map of where tiles go: each set cell of the map becomes a copy of the tile, and the colors come from the two solid squares.

## Scene
- `four-panels`: the input is a row of four panels on `background`, counted from the `panel_from` edge and split by full-height lines of `divider_color`; each panel holds its content in an n×n square one cell in from the panel's top and its near side, where n is the side of the solid squares, and the grid is n+2 high.
- `tile-shape`: panel 0 holds a shape of `tile_color` in its n×n square.
- `map-shape`: panel 1 holds a shape of `map_color` in its n×n square.
- `shapes-span-square`: each of the two shapes touches all four sides of its n×n square.
- `solid-squares`: panels 2 and 3 each hold a solid n×n square, and the two squares differ in color.

## Rules
- `tile-by-map`: the output is n²×n², cut into n×n blocks of n×n cells; block (i, j) is the tile shape where map cell (i, j) is set, and ground color everywhere where it is not.
- `tile-colors`: in a block that holds the tile, the tile's cells take the color of panel 2's square (the fill color) and its other cells take the color of panel 3's square (the ground color).

## Parameters
- `divider_color`: 5
- `background`: 0
- `panel_from`: `DIR_L`
    - the edge from which the panels are counted
- `panel_role`: 0 → tile, 1 → map, 2 → fill color, 3 → ground color
    - the role of each panel by its rank from `panel_from`

## Scene parameters
- `tile_color`: 1
- `map_color`: 2
