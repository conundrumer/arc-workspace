# f1bcbc2c

## Concept
- A winding one-cell-wide pipe runs between two walls from the top edge to another edge; liquid poured in at the top fills the pipe, and a plug lodged at a bend stops it there, while a plug on a straight run is washed through.

## Scene
- `two-walls`: two separate `wall_color` walls, each a 4-connected staircase path of straight runs and right-angle bends, run side by side from one grid edge to another.
- `pipe`: between the two walls lies a one-cell-wide corridor of non-wall cells, the one non-wall component that touches both walls; it opens on the `source_edge` edge at one end and on another edge at the other.
- `outside`: every other cell is `background_color`.
- `at-most-one-plug`: the corridor holds at most one `plug_color` cell, which lies inside the corridor, away from both openings; all its other cells are `background_color`.

## Rules
- `fill-from-source`: each corridor cell that a walk through the corridor from its opening on the `source_edge` edge reaches is painted `fill_color`.
- `plug-at-bend-blocks`: a plug with wall cells on two adjacent sides (it sits at a bend) stops the walk: it keeps `plug_color`, and the corridor beyond it keeps its input color.
- `plug-on-straight-passes`: a plug with wall cells on two opposite sides (it sits on a straight run) lets the walk pass through it, and is painted `fill_color` with the rest.
- `rest-unchanged`: every other cell keeps its input color.

## Parameters
- `wall_color`: 7
- `plug_color`: 9
- `fill_color`: 8
- `source_edge`: top (`DIR_T`)
    - the grid edge the pouring end of the corridor opens on

## Scene parameters
- `background_color`: 0
