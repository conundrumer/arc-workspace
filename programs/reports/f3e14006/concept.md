# f3e14006

## Concept
- Two marked lines cross; the marks on the bar line give a width, the bar line and the marks on the other line give a height, and that rectangle is woven as a period-2 lattice: threads of each line's color, crossing as the lines cross in the input, with the holes between them taking the marks' colors.

## Scene
- `two-crossing-lines`: on a field of `background`, one straight line runs along `bar_axis` (the bar line) and one runs across it (the cross line), and the two meet at one cell.
- `line-colors`: each line has a base color and exactly two cells of a mark color of its own; the four colors are distinct, and the crossing cell holds one line's base color.
- `cross-marks-one-side`: both marks of the cross line lie on one side of the bar line.

## Rules
- `rectangle`: the output keeps only a rectangle on a field of `background`; its extent along `bar_axis` is the span between the bar line's two marks, and its extent across is the span from the bar line to the farther mark of the cross line.
- `lattice`: from the rectangle's `anchor_corner`, cells at an even offset on both axes are holes, lines at an odd offset across `bar_axis` are bar threads, and lines at an odd offset along `bar_axis` are cross threads.
- `thread-colors`: a bar thread takes the bar line's base color and a cross thread the cross line's base color; where two threads cross, the cell takes the base color the input's crossing cell shows.
- `hole-colors`: a hole whose line across `bar_axis` lies within the span of the cross line's two marks takes the cross line's mark color, and every other hole takes the bar line's mark color.

## Parameters
- `background`: 0
- `bar_axis`: horizontal
    - the direction the bar line runs, whose marks give the rectangle's width
- `anchor_corner`: top-left
    - the corner of the rectangle that holds a hole

## Scene parameters
- none
