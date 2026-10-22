# c35c1b4c

## Concept
- A big blob of one color sits on a field of random noise, and the blob is made mirror-symmetric left to right: every blob cell is copied to its mirror cell across the grid's vertical midline.

## Scene
- `noise-field`: the grid is filled with scattered cells of a few colors, `0` among them, with no structure.
- `one-blob`: one color, the blob color, forms a large connected region near the middle of the grid, and that region is the largest single-color region in the grid.
- `blob-crosses-midline`: the blob covers cells on both sides of the vertical midline.

## Rules
- `mirror-union`: each cell of the blob color is copied, in the blob color, to the cell that mirrors it across the grid's vertical midline, on axis `axis`.
- `rest-kept`: every other cell keeps its input color.

## Parameters
- `axis`: H (the mirror swaps left and right; the midline runs vertically)

## Scene parameters
- none
