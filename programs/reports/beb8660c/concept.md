# beb8660c

## Concept
- Horizontal bars fall to the floor and stack in order of length, the longest at the bottom, each pushed against the right wall, so they form a staircase.

## Scene
- `bars`: every non-background cell belongs to a horizontal bar, a run of one color on one row, and each row holds at most one bar.
- `distinct-colors`: no two bars share a color.
- `lengths-one-to-width`: the bar lengths are exactly 1 to the grid width, one bar of each length.
- `base-bar`: the bottom row is a full-width bar of color `base_color`.

## Rules
- `sort-by-length`: the output places the bars on consecutive rows, ordered by length, the longest on the row nearest the `fall_dir` edge.
- `stack-at-edge`: the stack of bars touches the `fall_dir` edge, with one bar per row and no gap rows.
- `align-to-side`: each bar touches the `align_side` edge.
- `keep-bar`: each bar keeps its color and length.
- `clear-rest`: every other cell is `bg`.

## Parameters
- `fall_dir`: bottom
    - the edge the bars stack against
- `align_side`: right
    - the edge each bar touches in the output
- `bg`: 0

## Scene parameters
- `base_color`: 8
