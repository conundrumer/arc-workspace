# ed98d772

## Concept
- Make a pinwheel of the input: a 2×2 block of copies of it, each copy turned its own way — as is top left, a quarter turn counterclockwise top right, a half turn bottom left, a quarter turn clockwise bottom right.

## Scene
- `square-input`: every input is a square grid of side `n`, so each turn of it fits the same square.
- `one-mark-color`: every input holds background `background` cells and marks of one other color.

## Rules
- `quadrant-copies`: the output is twice the input's side on each axis, cut into 2 by 2 quadrants, and each quadrant holds the input under the transform `quadrant_transform` gives that quadrant, cell colors copied unchanged.

## Parameters
- `quadrant_transform`: TL → `D4_ID`, TR → `D4_CC`, BL → `D4_HT`, BR → `D4_CW`
    - the D4 transform of the input that each quadrant of the output, keyed by its corner, holds

## Scene parameters
- `n`: 3
- `background`: 0
