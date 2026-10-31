# f3b10344

## Concept
- Solid rectangles stand on a blank field; two rectangles of one color that face each other across an empty gap, with nothing between them, get a `bridge_color` bridge across that gap, `inset` cells narrower on each side than the span the two faces share.

## Scene
- `solid-rectangles`: every input holds axis-aligned solid single-colored rectangles on a `background` field, each a 4-connected component of its color.
- `rectangles-apart`: no two rectangles touch, even at a corner; each gap between two rectangles is at least one cell.
- `bridge-color-absent`: no input cell holds `bridge_color`.

## Rules
- `facing-pair`: two rectangles face each other along an axis when their spans on the other axis overlap and the band between them over that overlap holds only `background`.
- `same-color-bridge`: a facing pair of one color is joined; a facing pair of two colors is not.
- `bridge-band`: the bridge fills the gap between the pair, over the shared span less `inset` cells at each end; where that leaves no cell, no bridge is drawn.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `bridge_color`: 8
- `inset`: 1
    - the cells the bridge leaves at each end of the shared span
- `background`: 0

## Scene parameters
none
