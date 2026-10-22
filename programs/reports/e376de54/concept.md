# e376de54

## Concept
- Several parallel lines start from one common edge; every line is cut or extended from its free end so that it has the length of the middle line.

## Scene
- `field`: the grid is a field of color `bg`.
- `parallel-lines`: the field holds an odd number of straight segments, each one cell wide and of one color, all on one line axis (row, column, or one of the two diagonals); no two segments touch, and two segments can share a color.
- `common-start`: one end of each segment lies on one common line perpendicular to the segments' axis; that end is the segment's start, and the other end is its free end.
- `middle-line`: ordered along the common line, one segment has as many segments on one side as on the other; that segment is the middle line.

## Rules
- `match-middle`: each segment keeps its color, its axis and its start, and runs from its start toward its free end for the length of the middle line: a longer segment loses the cells past that length, and a shorter one gains cells of its color up to that length.
- `keep-field`: every other cell is `bg`.

## Parameters
- `bg`: 7

## Scene parameters
none
