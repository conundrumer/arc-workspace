# f341894c

## Concept
- Each little two-cell arrow, a `tail_color` tail and a `head_color` head, sits in line with a `marker_color` marker on the grid edge; turn every arrow so its head points at its marker.

## Scene
- `background`: every cell outside the markers and arrows is `background`.
- `edge-markers`: `marker_color` cells stand on the outer border of the grid; a marker in a corner stands on two edges.
- `arrows`: an arrow is two orthogonally adjacent cells, one `head_color` and one `tail_color`; arrows may touch other arrows, so their cells can form larger clumps of the two colors.
- `one-marker-per-arrow`: each arrow lies along the row or column of exactly one marker, on the arrow's own axis, the marker standing at that line's end on the edge; that line holds no other arrow, and every marker has one arrow on one of its lines (a corner marker's other line holds none).

## Rules
- `head-toward-marker`: each arrow is rewritten so that its cell nearer its marker is `head_color` and its other cell is `tail_color`.
- `rest-unchanged`: every other cell keeps its input color.

## Parameters
- `head_color`: 6
    - the arrow cell that ends up nearer the marker
- `tail_color`: 1
    - the arrow cell that ends up farther from the marker
- `marker_color`: 7

## Scene parameters
- `background`: 8
