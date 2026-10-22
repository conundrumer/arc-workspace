# d6ad076f

## Concept
- Two blocks face each other across an empty gap, and a bridge of `fill` spans that gap, one cell narrower than the blocks' shared side at each end.

## Scene
- `two-blocks`: every input holds exactly two solid rectangles, each of one color other than `bg` and of distinct colors, on a field of `bg`.
- `facing-across-gap`: the two rectangles are separated along one axis by a gap of `bg` cells at least one cell wide, and their spans on the other axis overlap by at least three cells.

## Rules
- `bridge`: each cell that lies in the gap between the two rectangles along the axis that separates them, and whose line on the other axis lies within the overlap of the two rectangles' spans on that axis, at least `inset` cells from each end of that overlap, takes `fill`.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `bg`: 0
    - the field color
- `fill`: 8
    - the bridge color
- `inset`: 1
    - the number of lines of the overlap left unfilled at each end

## Scene parameters
- none
