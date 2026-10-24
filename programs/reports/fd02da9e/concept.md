# fd02da9e

## Concept
- A smiley face: each marked corner of the grid colors its own part of the face in the marker's color, an eye for each top corner and half of the smile for each bottom corner, and the corner marks themselves vanish.

## Scene
- `background-field`: every input is a grid of `grid_size` filled with `background`.
- `corner-markers`: one or more of the four corner cells each hold a single marker cell of a color other than `background`, and no other cell differs from `background`.

## Rules
- `markers-cleared`: each marker cell becomes `background`.
- `face-part`: each marked corner paints the cells of its `corner_stamp` entry in its marker's color, each cell placed by its distances from that corner's two edges.
- `rest-background`: every other cell is `background`.

## Parameters
- `background`: 7
- `corner_stamp`: TL and TR: (1,1), (1,2), (2,1), (2,2); BL and BR: (1,3), (2,2), (3,2)
    - per corner, the cells of its face part, each as (distance from the corner's top or bottom edge, distance from its left or right edge): a 2×2 eye at the top corners, a bent stroke of the smile at the bottom corners

## Scene parameters
- `grid_size`: 8×8
