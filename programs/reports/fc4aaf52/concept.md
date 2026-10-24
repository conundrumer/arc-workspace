# fc4aaf52

## Concept
- A two-colored shape is snapped in half across its middle; the two colors trade places, and the `moved_half` slides toward `slide_dir` just far enough that its cut edge clears the other half's cut edge, so the two halves meet only at a corner.

## Scene
- `one-shape`: every input holds one 4-connected shape of non-`bg` cells on a field of `bg`.
- `two-colors`: the shape holds exactly two colors, and each half holds both.
- `mirror-halves`: the shape has an even extent across the cut, and the reflection that swaps the `moved_half` side with its opposite maps the shape onto itself, so the cut lies on its mirror line and the two cut rows are equal.
- `contiguous-cut-row`: each cut row is one unbroken run of shape cells.

## Rules
- `swap-colors`: every shape cell takes the shape's other color; `bg` cells away from the shape stay `bg`.
- `cut-at-middle`: the shape splits on the line between its two middle rows across the `moved_half` axis, into the half on the `moved_half` side and the half on the opposite side.
- `other-half-stays`: the half opposite `moved_half` keeps its place.
- `slide-to-clear`: the `moved_half` moves toward `slide_dir` by the least amount after which every cell of its cut row lies beyond every cell of the other half's cut row toward `slide_dir`; with equal unbroken cut rows that is the cut row's length.
- `vacated-to-bg`: cells the moved half leaves become `bg`, and a moved cell that lands past the frame is dropped.

## Parameters
- `bg`: 8
    - the background color
- `moved_half`: DIR_T
    - the side of the cut whose half moves
- `slide_dir`: DIR_R
    - the direction the moved half slides, perpendicular to the axis of `moved_half`

## Scene parameters
- none
