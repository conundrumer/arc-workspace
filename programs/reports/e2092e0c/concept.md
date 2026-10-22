# e2092e0c

## Concept
- A small pattern sits in the corner, fenced off by a line. The same pattern hides somewhere else in the grid, and you draw a box in the fence's color around it.

## Scene
- `corner-key`: a `key-size` × `key-size` key sits at `key-corner`, and a line of `mark-color` cells runs along its two inner sides and meets at the corner cell diagonal to the key, which fences it off from the rest of the grid.
- `scattered-field`: every other cell is background `0` or a scattered color, in no shape.
- `one-copy`: outside the fenced region, the key's pattern occurs exactly once, cell for cell with background included, at a place where a ring one cell outside it stays in the grid.

## Rules
- `ring-copy`: a one-cell-wide square ring of `mark-color` is drawn just outside the copy, over whatever the ring's cells held.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `key-corner`: top-left
    - the corner of the grid that holds the key
- `key-size`: 3
    - the side of the square key
- `mark-color`: 5
    - the color of the key's fence and of the ring drawn around the copy

## Scene parameters
- `background`: 0
