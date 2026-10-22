# dd2401ed

## Concept
- A divider line moves away from the near edge until the count of columns from that edge up to and including the line doubles; the far marks the line passes over turn the near color, and the far marks still beyond the line stay as they are.

## Scene
- `divider-line`: one full line of `line_color` crosses the grid perpendicular to `near_edge`, and no other cell has `line_color`.
- `near-marks`: cells of `near_color` stand only between `near_edge` and the divider.
- `far-marks`: cells of `far_color` stand only on the far side of the divider.
- `background`: every other cell is `background`.
- `room-to-move`: the destination line, at `factor` times the count of lines from `near_edge` up to and including the divider, lies inside the grid.
- `destination-clear`: no far mark stands on the destination line.

## Rules
- `move-divider`: the divider's old line becomes `background`, and the destination line becomes `line_color`; with the divider at index k from `near_edge`, the destination is at index `factor`·(k+1)−1.
- `recolor-swept`: a `far_color` cell between the old line and the destination line becomes `near_color`.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `near_edge`: left
    - the edge the divider's distance is measured from, the side of the near marks
- `factor`: 2
    - the multiple of the count of lines from `near_edge` up to and including the divider that gives the destination's count
- `line_color`: 5
- `far_color`: 2
- `near_color`: 1
    - the color the swept far marks take
- `background`: 0

## Scene parameters
- none
