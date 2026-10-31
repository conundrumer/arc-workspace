# f15e1fac

## Concept
- Seed marks on one edge each shoot a line straight across the grid; every marker on a perpendicular edge kinks all the lines one step away from the marker's edge, starting on the marker's line, and a line that steps off the grid is gone.

## Scene
- `seeds-on-one-edge`: cells of `seed_color` lie on one edge of the grid, the seed edge, and on no other edge line.
- `markers-on-adjacent-edge`: cells of `marker_color` lie on one edge perpendicular to the seed edge, the marker edge, and not on the seed edge.
- `rest-background`: every other cell is `background`.

## Rules
- `ray-across`: each seed starts a line of `seed_color` that runs from the seed edge across the grid, perpendicular to the seed edge.
- `kink-at-marker`: at each marker's line across the rays (the row or column it sits on, parallel to the seed edge), every ray, from that line on, steps `step` cells away from that marker's own edge; the steps add up marker by marker.
- `clip-off-grid`: the part of a ray that steps past the grid's edge is dropped, with no wrap.
- `markers-kept`: markers stay as they are, and every other cell is `background`.

## Parameters
- `seed_color`: 8
- `marker_color`: 2
- `step`: 1
    - the cells each ray steps sideways at each marker

## Scene parameters
- `background`: 0
