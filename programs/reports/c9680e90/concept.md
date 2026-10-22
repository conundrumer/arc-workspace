# c9680e90

## Concept
- A center line splits the grid into two mirror halves. On one side, each head sits at the start of a straight tail and crawls along it to the tail's far end, eating the tail. On the other side, each head has a mirror twin, and the twin makes the mirror move.

## Scene
- `background`: every cell that is not a divider, head, tail, or mark cell has the `background` color.
- `center-divider`: one full line of the `divider-color` runs on the `divider-axis` through the center of the grid, so the two halves have the same extent.
- `heads-on-one-side`: every `head-color` cell and every `tail-color` cell is in the half on the `head-side` of the divider.
- `straight-tail`: each head has one straight run of `tail-color` cells that starts at a 4-neighbor of the head and goes away from it in one direction, with length 1 or more.
- `mirror-twins`: the other half has a `mark-color` cell at the mirror image across the divider of each head cell, and no other mark cells.

## Rules
- `crawl-to-tail-end`: each head moves to the last cell of its tail; the tail cells and the head's old cell become `background`.
- `twin-follows`: each mark moves to the mirror image across the divider of its head's new cell; the mark's old cell becomes `background`.
- `divider-kept`: the divider line stays as it is.

## Parameters
- `background`: 7
- `divider-color`: 9
- `divider-axis`: horizontal
    - the axis the divider line runs along, which is also the axis of the mirror
- `head-color`: 2
- `tail-color`: 6
- `mark-color`: 5

## Scene parameters
- `head-side`: bottom
    - the half that holds the heads and tails
