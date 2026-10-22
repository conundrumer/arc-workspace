# b7fb29bc

## Concept
- A box outline holds one dot. Concentric square rings grow out from the dot and fill the inside of the box, and they alternate between two colors.

## Scene
- `box-outline`: a one-cell-wide rectangle outline of `frame_color` on a field of `background`, closed on all four sides.
- `one-dot`: exactly one cell of `frame_color` inside the box, apart from the outline; it can touch the outline.
- `empty-inside`: every other cell inside the box is `background`.

## Rules
- `square-rings`: each background cell inside the box takes a color from its Chebyshev distance to the dot: `ring_colors` at odd distance first, then at even distance, so the rings alternate outward from the dot.
- `clip-to-box`: rings cover only the cells inside the outline, and they stop at the outline.
- `keep-rest`: the outline, the dot, and every cell outside the box keep their input colors.

## Parameters
- `ring_colors`: 4 at odd distance, 2 at even distance
    - the ring color by the parity of the distance to the dot

## Scene parameters
- `frame_color`: 3
    - the color of the outline and of the dot
- `background`: 0
