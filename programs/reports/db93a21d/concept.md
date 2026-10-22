# db93a21d

## Concept
- Each square gets a halo half its side thick, and drops a stream of its own width straight down to the bottom edge, which runs under the halos.

## Scene
- `background`: a field of `background`.
- `squares`: solid squares of `square_color`, each of even side, apart from each other; a square can be cut off by the grid edge, and its side is then its longer extent.
- `own-columns`: no two squares share a column.
- `clear-halo`: no square has a cell in the ring of another square's halo.

## Rules
- `keep-squares`: each square stays as it is.
- `halo`: around each square, the ring of cells out to a distance of half its side takes `frame_color`: its outer box is the square scaled by `frame_scale` about its center, cut at the grid edge.
- `trail`: the cells in each square's columns, from the square toward `trail_dir` to the grid edge, take `trail_color`.
- `layers`: a square cell is drawn over a halo cell, and a halo cell over a trail cell; every other cell keeps its input color.

## Parameters
- `square_color`: 9
- `frame_color`: 3
- `trail_color`: 1
- `trail_dir`: bottom
- `frame_scale`: 2
    - the side of a halo's outer box over the side of its square

## Scene parameters
- `background`: 0
