# a934301b

## Concept
- Each rectangle of `body` color is speckled with `mark` cells; a rectangle with more than one mark is erased, and the rest stay as they are.

## Scene
- `rectangles`: the input is a `background` field holding solid rectangles, each made of `body` cells and `mark` cells, and no two rectangles touch, so each rectangle is one connected component of non-`background` cells.
- `marks`: each rectangle holds zero or more `mark` cells, scattered inside it.

## Rules
- `count-marks`: an object is a connected component of non-`background` cells, and its mark count is the number of its `mark` cells.
- `erase-crowded`: an object whose mark count exceeds `max_marks` becomes `background` in the output.
- `keep-rest`: every other cell of the output is the input cell.

## Parameters
- `background`: 0
- `mark`: 8
- `max_marks`: 1
    - the largest mark count an object keeps

## Scene parameters
- `body`: 1
