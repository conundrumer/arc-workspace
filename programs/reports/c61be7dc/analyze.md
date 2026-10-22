# c61be7dc

## Concept
- Fits every pair (`work/task/c61be7dc/probe.py pairs`). No witness has the verdict `other`.
- The concept is undefined where the shape's count is even and where the line is longer than the corridor. `$EvenCountBothSides` and `$ClipAtEdge` give an output there.
- In every input, the whole cross is centered in the grid, and the shape spans the full width of the corridor and is symmetric about the cross line. So the cross line, the shape's middle and the grid's middle give the same center along the corridor. Also, the corridor's center line, the shape's center line and the grid's middle line give the same line across it. The `along-center` and `across-center` points come from these coincidences.

## Choice points
- `along-center`: the point along the corridor that the pressed line centers on
    - `concept`: the cross line
    - `$AlongShapeCenter`: replaces `press-shape`. The line centers on the middle of the shape's extent along the corridor. Undefined where that extent and the count do not let the line center on that middle. Fits every pair. Witness `shape-off-cross-line`: breaks `shape` (the shape is not symmetric about the cross line). Plausibility `borderline`, verdict `concept`. Invariant broken: every shape is symmetric about the cross line.
    - `$AlongGridMiddle`: replaces `press-shape`. The line centers on the grid's middle line across the corridor. Undefined where the grid's extent along the corridor and the count do not let the line center there. Fits every pair. Witness `cross-line-off-middle`: breaks no scene claim. Plausibility `variant`, verdict `concept`. Invariant broken: the cross line is the grid's middle line in every input.
- `across-center`: the line that the closed corridor centers on
    - `concept`: the center line of the corridor between the two walls
    - `$AcrossShapeCenter`: replaces `close-walls` and `press-shape`. The new walls flank the center line of the shape's extent across the corridor, and the line sits on that center line. Undefined where that extent is even. Fits every pair. Witness `shape-narrower-than-corridor`: breaks no scene claim. Plausibility `variant`, verdict `concept`. Invariant broken: every shape spans the full width of the corridor.
    - `$AcrossGridMiddle`: replaces `close-walls` and `press-shape`. The new walls flank the grid's middle line parallel to the walls. Undefined where the grid's extent across the walls is even. Fits every pair. Witness `corridor-off-middle`: breaks no scene claim. Plausibility `variant`, verdict `concept`. Invariant broken: the two walls are symmetric about the grid's middle in every input.
- `uncentered-count`: a count that cannot center on the center point (an even count on a cell)
    - `concept`: undefined
    - `$EvenCountBothSides`: replaces the odd count of `shape` and adds to `press-shape`. Where the line cannot center exactly, the output holds two grids: the two placements half a cell off the center, one on each side. Undefined nowhere the concept is defined. Fits every pair. Witness `even-count`: breaks `shape` (the count is even). Plausibility `borderline`, verdict `$EvenCountBothSides`. Invariant broken: every shape has an odd count.
- `overflow`: a line longer than the corridor
    - `concept`: undefined
    - `$ClipAtEdge`: adds to `press-shape`. The part of the line past a grid edge is dropped. Fits every pair. Witness `line-longer-than-corridor`: breaks no scene claim. Plausibility `borderline`, verdict `$ClipAtEdge`. Invariant broken: every shape's count is at most the corridor's length. In train2 the count equals the corridor's length.
- `wall-axis`: the axis of the walls
    - `concept`: read per input, as the axis with two full lines of `line_color`
    - `$AxisStored`: replaces `walls`. A stored parameter `axis` gives the walls' axis, and the model is undefined on an input whose walls lie on the other axis. Fails Fit at train1 (and test0) with `axis` vertical, and at train0 and train2 with `axis` horizontal.
- `background`: the background color
    - `concept`: stored, 7
    - `background=DominantColor`: replaces `field`. The background is the input's commonest color, and the model is undefined where that color is tied. Fits every pair. Witness `background=DominantColor`: train1's input with the field recolored 3. It breaks `field`. Plausibility `variant`, verdict `background=DominantColor`. Invariant broken: the field is 7 in every input.
- `shape_color`: the shape's color
    - `concept`: stored, 5
    - `shape_color=RarestColor`: replaces `shape`. The shape's color is the input's rarest color, and the model is undefined where that color is tied. Fits every pair. Witness `shape_color=RarestColor`: train1's input with the shape recolored 3. It breaks `shape` (no cell has `shape_color`, so the count is zero, which is even). Plausibility `variant`, verdict `shape_color=RarestColor`. Invariant broken: the shape is 5 in every input.
- `along-center` & `across-center`, `along-center` & `uncentered-count`, `along-center` & `overflow`, `along-center` & `wall-axis`, `along-center` & `background`, `along-center` & `shape_color`, `across-center` & `uncentered-count`, `across-center` & `overflow`, `across-center` & `wall-axis`, `across-center` & `background`, `across-center` & `shape_color`, `uncentered-count` & `overflow`, `uncentered-count` & `wall-axis`, `uncentered-count` & `background`, `uncentered-count` & `shape_color`, `overflow` & `wall-axis`, `overflow` & `background`, `overflow` & `shape_color`, `wall-axis` & `background`, `wall-axis` & `shape_color`, `background` & `shape_color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A derived `line_color`: no proposer gives one color on a single input. `SharedColor` gives every color of the input, and the other color proposers read `ex_out`, which is empty in a run on one input.
- A line length other than the shape's count, such as the shape's bounding-box area or the corridor's full length: train1 (count 5, box 9) and train0 (count 9, corridor 11) rule them out.
- The cross line's color on top where the line crosses it: train0 output (5,5) is 5.
- The old corridor's cells on the cross line keeping the input's content: train2 output (6,4) is 0 where the input has 5.
- Walls that move inward by a fixed step: train0 moves them by 1, and train2 moves them by 2.

## Tickets filed
- none
