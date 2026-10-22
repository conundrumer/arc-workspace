# b4a43f3b

## Concept
- A small picture is drawn at each marked cell of a mask: the output is the mask blown up so that each marked cell becomes one copy of the picture, and each unmarked cell becomes a blank block of the picture's size.

## Scene
- `two-halves`: the input is two equal halves stacked on one axis, with a full line of `separator_color` between them.
- `scaled-picture`: the half on `pattern_side` is a picture scaled up by `pattern_scale`, so each picture cell is a `pattern_scale`×`pattern_scale` block of one color, `background` included.
- `mask`: the other half is a mask: cells of `mask_color` on `background`, at mask resolution (one input cell per mask cell, no scaling).
- `half-extent`: each half is `half_extent`×`half_extent`, so the picture is (`half_extent` / `pattern_scale`) on a side.

## Rules
- `picture-down`: the picture is the half on `pattern_side`, read at one cell per `pattern_scale`×`pattern_scale` block.
- `output-size`: the output is the mask's extent times the picture's extent on each axis.
- `stamp-at-marks`: the output is cut into a tile per mask cell, each the size of the picture; the tile of a marked mask cell holds the picture, and the tile of an unmarked mask cell is `background`.

## Parameters
- `pattern_side`: top
    - the side of the separator that holds the picture; the mask is on the opposite side
- `pattern_scale`: 2
- `background`: 0

## Scene parameters
- `separator_color`: 5
- `mask_color`: 2
- `half_extent`: 6
