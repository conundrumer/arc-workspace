# df8cc377

## Concept
- Each hollow box is filled with a checkerboard in the color of the scattered dots whose count equals the number of checkerboard cells that fit in the box, and the dots are wiped away.

## Scene
- `hollow-frames`: a few one-cell-thick rectangle outlines, each in its own color, each around an interior of `background` cells at least one cell on each side.
- `scattered-dots`: single cells in colors that no frame has, scattered on the `background` outside the frames, with one dot color per frame.
- `counts-match`: for each frame, exactly one dot color has as many dots as the frame's checkerboard has cells, and no two frames share that color.

## Rules
- `erase-dots`: every dot becomes `background`.
- `keep-frames`: every frame cell keeps its color.
- `checker-fill`: in each frame's interior, the cells whose row and column offsets from the `anchor` corner of the interior have an even sum take the dot color whose dot count equals the number of those cells, and the other interior cells stay `background`.

## Parameters
- `background`: 0
- `anchor`: `DIAG_TL`
    - the interior corner whose cell the checkerboard fills

## Scene parameters
- none
