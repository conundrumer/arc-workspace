# e5790162

## Concept
- A line grows from the start cell into the grid. When the line meets a marker, it turns in front of the marker: one marker color turns it right and the other turns it left. The line stops at the frame edge.

## Scene
- `start-cell`: one cell of `path_color` sits on the frame edge opposite `start_dir`, and every other non-background cell is a marker.
- `marker-colors`: each marker has a color that `turn_sense` has a row for.
- `every-marker-met`: each marker is the cell directly ahead of the line at one of its turns.
- `line-exits`: the line reaches the frame edge without a crossing of itself and without a marker directly ahead of a cell where it turns.

## Rules
- `walk`: the line starts at the start cell with heading `start_dir`, and steps one cell along the heading at a time.
- `turn-at-marker`: when the next cell ahead is a marker, the line turns a quarter turn in the sense `turn_sense` gives for that marker's color, and continues from the cell it is at.
- `stop-at-edge`: the line stops when the next cell ahead is outside the frame.
- `paint-line`: each cell the line visits takes `path_color`, and every other cell keeps its input color.

## Parameters
- `start_dir`: right
    - the heading of the line's first step
- `turn_sense`: 6 → clockwise, 8 → counterclockwise
    - the turn sense for each marker color
- `path_color`: 3
    - the color of the start cell and of the line

## Scene parameters
- `background`: 0
