# fd4b2b02

## Concept
- A bar sends a chain of bars off each of its four corners to the grid edge: each next bar is the last one turned a quarter turn and in the other color, touching it corner to corner.

## Scene
- `one-bar`: one solid rectangle of one color of the `partner` pair on the `background`, longer on one axis than on the other.

## Rules
- `keep-bar`: the input bar stays where it is, and the output has the input's size.
- `diagonal-chains`: toward each of the four diagonal directions, a chain of bars runs from the input bar: each next bar has the extents of the last one swapped, takes the `partner` of its color, and sits so its corner cell nearest the last bar is diagonally adjacent, in that direction, to the last bar's corner cell.
- `clip-at-edge`: a chain runs until a bar lies wholly outside the grid, and the part of a bar outside the grid is dropped.
- `rest-background`: every other cell is `background`.

## Parameters
- `partner`: 6 -> 3, 3 -> 6
    - the color a bar of each color passes to the next bar of a chain
- `background`: 0

## Scene parameters
- none
