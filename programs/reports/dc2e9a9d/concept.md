# dc2e9a9d

## Concept
- Each box with a nub gets a mirror copy on the side away from its nub, one cell off, colored by the axis the copy moves along.

## Scene
- `background-field`: a field of `background`.
- `nubbed-boxes`: each object is a hollow rectangle outline, one cell thick, of `shape_color`, with one single-cell nub outside the middle cell of one side; that side has odd length.
- `room-for-copy`: the cells the copy of each box covers inside the frame are `background` and are covered by no other copy, and the copy's rectangle lies inside the frame; only the copy's nub may fall past the frame edge.

## Rules
- `keep-input`: every input cell keeps its color in the output.
- `mirror-away-from-nub`: each object is mirrored across the axis parallel to the side of its box opposite the nub, placed so that `gap` lines of cells part the copy's box from that side; the copy's nub points away from the original.
- `color-by-axis`: the copy takes the color `copy_color` gives the axis it moves along.
- `clip-at-frame`: copy cells past the frame edge are dropped.

## Parameters
- `background`: 0
- `gap`: 1
    - the number of background lines between the original box and its copy's box
- `copy_color`: horizontal → 1, vertical → 8
    - the copy's color, keyed by the axis along which the copy lies from the original

## Scene parameters
- `shape_color`: 3
