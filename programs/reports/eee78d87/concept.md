# eee78d87

## Concept
- The small shape is a stencil: repeat it edge to edge over a 16×16 canvas, its cells as holes of 0 in the background color, with the copies laid symmetric about the canvas center, which at 16 puts a copy's center on every third row and column starting at the edge, and paint the holes inside the canvas's middle 6×6 window 9.

## Scene
- `field`: every input is an `in_size`×`in_size` grid of one background color.
- `one-shape`: the cells off the background all share one other color and together fit a box of `shape_extent`×`shape_extent` cells, touching all four sides of it; the cells need not be connected.

## Rules
- `canvas`: the output is a `canvas_size`×`canvas_size` grid.
- `stencil-tiling`: the shape's box, whose own extent e is the period, repeats across the output edge to edge, a copy's center on each row r and each column with 2r ≡ `canvas_size` − 1 (mod e), so the copies sit symmetric about the canvas center (at 16 and e = 3, every multiple of 3); a box cell the shape holds gives `hole_color`, and any other box cell gives the input's background color.
- `center-window`: within the centered `window_size`×`window_size` window of the output (rows 5–10, cols 5–10), each `hole_color` cell becomes `window_color`; every other cell there keeps its stencil color.
- `shape-color-dropped`: neither the shape's color nor its place in the input reaches the output.

## Parameters
- `canvas_size`: 16
- `hole_color`: 0
- `window_color`: 9
- `window_size`: 6
    - the extent of the centered window whose holes recolor

## Scene parameters
- `in_size`: 6
- `shape_extent`: 3
