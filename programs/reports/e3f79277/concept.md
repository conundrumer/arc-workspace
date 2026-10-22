# e3f79277

## Concept
- A small right angle sits in one corner of the grid. The output is a bigger canvas with the same corner, where the angle's legs grow to twice their length and a diagonal closes them into a triangle outline.

## Scene
- `corner-angle`: the input is a `in_size` by `in_size` field of the `background` color, and one corner holds a right angle of one other color: two legs of equal length k, one along each edge of that corner, that meet in the corner cell.
- `no-other-marks`: every cell off the angle is the `background` color.

## Rules
- `canvas`: the output is a `out_size` by `out_size` grid of the `background` color.
- `same-corner`: the triangle sits in the output corner that matches the input corner of the angle.
- `scaled-legs`: each leg of the triangle runs `leg_scale` times k cells from that corner along the matching edge, in the angle's color.
- `hypotenuse`: the diagonal from the far end of one leg to the far end of the other is drawn in the angle's color.

## Parameters
- `background`: 7
- `out_size`: 16
    - the side length of the square output grid
- `leg_scale`: 2
    - the factor from the input leg length to the output leg length

## Scene parameters
- `in_size`: 6
    - the side length of the square input grid
