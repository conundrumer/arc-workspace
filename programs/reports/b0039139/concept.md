# b0039139

## Concept
- Four panels in a row give a stamp, a count and two colors: stamp the shape as many times as there are marks, in a line with a gap between copies, with the shape in the first color on a field of the second.

## Scene
- `panels`: full lines of `divider_color`, one cell wide, cut the input into four panels in a row along one axis, and each panel spans the whole input across that axis.
- `shape-panel`: one end panel holds one connected shape of `shape_color` on `background`, with background between the shape and the panel's sides.
- `count-panel`: the panel next to the shape panel holds marks of `mark_color` on `background`, each mark a domino of two cells, with background between any two marks.
- `solid-panels`: each of the other two panels is solid in one color, and the two colors differ from each other, from `divider_color` and from `background`.

## Rules
- `count`: N is the number of marks in the count panel.
- `tile-shape`: the output is the shape's bounding box, copied N times in a line along the panel axis, with `gap_width` lines between neighbor copies.
- `recolor`: a shape cell takes the color of the solid panel next to the count panel, and every other cell of the output, in a box or in a gap, takes the color of the solid panel at the far end.

## Parameters
- `divider_color`: 1
- `shape_color`: 4
- `mark_color`: 3
- `gap_width`: 1
    - the number of lines between neighbor copies

## Scene parameters
- `background`: 0
    - the field color of the shape panel and the count panel
