# b527c5c6

## Concept
- Each bar has a mark on one side, and from that side it shoots a beam to the grid edge: a line of the mark color straight out from the mark, flanked on each side by the bar color, as wide on each side as the bar is thick behind the mark.

## Scene
- `bars`: the input holds solid rectangles of `bar_color` on `background`, apart from one another, each at least two cells thick and longer along one axis than across it.
- `one-mark-per-bar`: each bar holds exactly one cell of `mark_color`, on one of its long sides, with at least the bar's thickness less one cells of that side on each side of it; the bar holds no other color.
- `clear-paths`: the beam of each bar crosses only `background` cells, so no beam meets another bar or another beam.

## Rules
- `beam-direction`: a bar's beam leaves the side of the bar that holds its mark, toward the grid edge that side faces, and runs from the cell next to the bar up to that grid edge; where the mark sits on more than one side, the model is undefined.
- `beam-core`: the beam's center line is the mark's line across the bar; outside the bar, each of its cells takes `mark_color`.
- `beam-flanks`: on each side of the center line, the beam is as wide as the bar's extent across the marked side less one (the distance from the mark to the bar's far side), and each flank cell takes `bar_color`; a flank cell past the grid edge is dropped.
- `keep-rest`: every cell outside the beams keeps its input color.

## Parameters
- `background`: 0
- `bar_color`: 3
- `mark_color`: 2

## Scene parameters
none
