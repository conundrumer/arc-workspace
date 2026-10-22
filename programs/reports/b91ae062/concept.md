# b91ae062

## Concept
- Blow the grid up: each cell becomes a k×k block, where k is the number of different colors in the picture.

## Scene
- `small-grid`: every input is a `size`×`size` grid.
- `colored-cells-on-background`: every input holds a few cells of non-`background` colors on a field of `background`, with at least one non-`background` color.

## Rules
- `scale-factor-is-color-count`: k is the number of distinct non-`background` colors in the input.
- `scale-up`: the output is the input scaled by k on both axes: input cell (r, c) fills output rows k·r to k·r+k−1, cols k·c to k·c+k−1 with its color.

## Parameters
- `background`: 0
    - the field color, which the color count leaves out

## Scene parameters
- `size`: 3
