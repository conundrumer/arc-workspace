# f5c89df1

## Concept
- A shape is drawn around one center cell; it is stamped once at each marker, placed so its center lands on the marker, and the original shape, its center and the markers are wiped.

## Scene
- `one-anchor`: exactly one cell has `anchor_color`; it is the shape's center.
- `markers`: one or more cells have `marker_color`.
- `pattern`: every other non-background cell has `pattern_color`; together these cells are the shape.
- `copies-in-frame`: the shape, moved so its center lands on any marker, lies wholly inside the grid.

## Rules
- `stamp-at-markers`: for each marker, each shape cell is painted at the marker plus that cell's offset from the center, in the shape cell's color; overlapping stamps paint the same color.
- `erase-source`: every cell no stamp paints is background, so the original shape, the center and the markers do not survive unless a stamp covers them.

## Parameters
- `anchor_color`: 3
- `marker_color`: 2
- `background`: 0

## Scene parameters
- `pattern_color`: 8
