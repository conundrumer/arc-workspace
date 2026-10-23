# e681b708

## Concept
- Straight lines cut the grid into rooms, and each line end and each crossing carries a colored marker. Every loose dot in a room takes the color that occurs most often among the markers on that room's walls.

## Scene
- `wall-lines`: horizontal and vertical lines of `line_color` on a `background` field, each running from a grid edge or another line to a grid edge or another line.
- `markers`: each end of a line and each cell where lines meet holds a marker, a color other than `line_color` and `background`, and no other line cell does.
- `rooms`: the lines cut the grid into rectangular rooms, each a 4-connected part of the cells that are not line cells.
- `loose-dots`: each room holds single cells of `line_color`, no two 4-adjacent, none 4-adjacent to a line cell.
- `clear-majority`: among the markers on the walls of each room that holds a dot, one color occurs more often than every other.

## Rules
- `dot-recolor`: a line cell is a marker, or a `line_color` cell on a straight run of `line_color` cells between two markers in its row or column; every other `line_color` cell is a dot, and takes the color that occurs most often among the markers 8-adjacent to its room.
- `rest-kept`: every other cell keeps its input color.

## Parameters
- `line_color`: 1
    - the color of the lines and of the dots
- `background`: 0

## Scene parameters
none
