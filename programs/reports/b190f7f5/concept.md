# b190f7f5

## Concept
- The input is two squares side by side: one draws a shape in the template color, the other is a small color pattern. Each colored cell of the pattern becomes a copy of the shape in that cell's color, and the empty cells stay empty, so the output is the pattern blown up with the shape as the stamp.

## Scene
- `two-square-halves`: the input is two n×n squares joined along its long side, with no divider between them; the axis of the join and the order of the two squares vary.
- `template-half`: one square holds only `template_color` and `background` cells; this is the shape.
- `pattern-half`: the other square holds no `template_color` cell; its non-`background` cells are the pattern.

## Rules
- `output-size`: the output is n²×n², an n×n grid of n×n blocks, one block per pattern cell.
- `stamp-shape`: the block at pattern cell (I,J) takes, at each cell (i,j), the color of pattern cell (I,J) where the shape has `template_color` at (i,j) and pattern cell (I,J) is not `background`; every other cell is `background`.

## Parameters
- `template_color`: 8
    - the color the shape is drawn in, which marks which half is the shape
- `background`: 0

## Scene parameters
- `half_count`: 2
    - the number of equal squares the input divides into
