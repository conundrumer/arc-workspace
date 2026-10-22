# e12f9a14

## Concept
- Walled boxes leak their color: each gap in a box's wall shoots a ray of the box's color straight out to the edge, and when two rays would cross, both bend just short of the crossing into the direction between them and run on side by side.

## Scene
- `background`: the commonest color fills the field.
- `boxes`: each box is a `core-side` × `core-side` core of one color, inside a ring one cell wide of the wall color; every box in a grid has the same wall color, and no core has it.
- `gaps`: some cells of a box's ring, on a side or at a corner, are background, and a box may run past the grid edge.
- `clear-paths`: no ray's path enters another box.
- `single-meetings`: each ray meets at most one other ray, and a pair that a meeting makes meets no other ray.

## Rules
- `rays`: each gap paints a ray of its box's core color, from the gap cell out to the grid edge: a gap on a side goes straight out, at a right angle to that side, and a gap at a corner goes out diagonally from that corner.
- `meeting`: where the straight paths of two rays would cross, at a cell or between two diagonal steps, and neither ray has bent before that crossing, each ray stops at its last cell before the crossing, and from there both go on in the sum of their two directions, side by side, so the crossing cell stays background.
    - Two cardinal directions sum to a diagonal, two diagonals sum to a cardinal, and a cardinal and a diagonal sum to a line of two cardinal steps for each step across, drawn as cardinal and diagonal steps in turn, the cardinal step first.
- `keep`: every other cell keeps its input color.

## Parameters
- `core-side`: 2
    - the side length of a box's core

## Scene parameters
- none
