# b7249182

## Concept
- Two dots on one line grow toward each other and meet at the middle: each draws a stem, then a crossbar, whose ends bend toward the other dot, so the two halves close a hollow box between them.

## Scene
- `two-dots`: two single cells on a field of `background`, and nothing else.
- `shared-line`: the two dots are on one row or on one column.
- `even-span`: the run of cells from one dot to the other, both dots included, has an even length, so the run splits into two equal halves.
- `long-span`: each half holds at least `box-depth` cells.

## Rules
- `halves`: the run from one dot to the other splits into two equal halves, and each half takes the color of the dot at its end.
- `stem`: a half's cells, from the dot toward the middle, are painted in its color, except for the last `box-depth` cells.
- `crossbar`: the next cell of the half after the stem is the center of a crossbar across the line, which reaches `bar-reach` cells to each side, in the half's color, where those cells are in the frame.
- `arms`: the two ends of the crossbar extend toward the middle along the line, up to the half's last cell, in the half's color, where those cells are in the frame.
- `keep`: every other cell keeps its input color.

## Parameters
- `background`: 0
- `bar-reach`: 2
    - the number of cells the crossbar reaches to each side of the line
- `box-depth`: 2
    - the number of cells of each half, at its middle end, that the box takes: the crossbar's cell and the arm cells after it

## Scene parameters
- none
