# 33067df9

## Concept
- The input is a small lattice of colored dots, a thumbnail of a picture made of rectangles; the output redraws that lattice on a fixed square canvas, with wider lines and each dot grown into a tile as large as the canvas allows, and same-colored dots that make up one rectangle drawn as one block: dots join first into runs along `run_axis`, and runs then join across it when they have the same color and the same extent.

## Scene
- `dot-lattice`: every input is a lattice of `in_tile`-cell tiles ruled off by `in_line`-cell lines of `bg`, with a line on every side; each tile is `bg` (an empty slot) or one color.
- `counts-fit`: each lattice count, n tiles on an axis, divides `out_extent` − `out_line`, so the output tiles come out equal and whole (counts 1 to 4 occur).

## Rules
- `canvas`: the output is an `out_extent` × `out_extent` grid of `bg`, ruled on each axis by `out_line`-cell lines, a line on every side, into as many equal tiles as the input has on that axis.
- `paint`: each output tile takes the color of its input tile; a `bg` tile leaves it `bg`.
- `join-runs`: a maximal run of same-colored tiles that are neighbors along `run_axis` draws as one rectangle, the lines between its tiles painted in its color.
- `stack-runs`: runs that are neighbors across `run_axis`, with the same color and the same extent along `run_axis`, draw as one rectangle, the lines between them painted; runs whose extents differ stay apart, with the line between them `bg`.

## Parameters
- `bg`: 0
- `in_line`: 1
- `in_tile`: 1
- `out_line`: 2
- `out_extent`: 26
- `run_axis`: H
    - the axis along which same-colored tiles join first

## Scene parameters
none
