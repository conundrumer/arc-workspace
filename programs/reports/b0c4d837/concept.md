# b0c4d837

## Concept
- A cup is partly full of liquid: count how many rows of the cup are still empty above the liquid, and show that count as liquid-colored marks laid one by one into a small fixed grid, starting at the top-left corner.

## Scene
- `cup`: one cup drawn in `wall_color`: two vertical walls of equal height joined at their bottom ends by a horizontal floor, open at the top, with `background` outside it.
- `liquid`: a solid block of `fluid_color` fills the cup's inside from the floor up, across the full width between the walls, to some level below the top of the walls.
- `empty-rows`: at least one row inside the cup, between the walls and above the liquid, is all `background`.

## Rules
- `count-empty-rows`: the count is the number of rows inside the cup that hold no liquid: the rows from the topmost row that holds `wall_color` down to the topmost row that holds `fluid_color`, that row left out.
- `output-frame`: the output is the frame that the cells of `fill_order` cover, all `background`.
- `lay-marks`: the first count cells of the output, in `fill_order`, take `fluid_color`; every other cell stays `background`.

## Parameters
- `wall_color`: 5
- `fluid_color`: 8
- `background`: 0
- `fill_order`: open values
    - the order in which the marks fill the output, as a rank for each cell of a 3×3 frame; the pairs fix only the first four ranks: (0,0), (0,1), (0,2), (1,2)
    - snake: (0,0), (0,1), (0,2), (1,2), (1,1), (1,0), (2,0), (2,1), (2,2)
    - clockwise spiral: (0,0), (0,1), (0,2), (1,2), (2,2), (2,1), (2,0), (1,0), (1,1)

## Scene parameters
- none
