# b7999b51

## Concept
- Each colored rectangle becomes a bar as tall as the rectangle is tall; the bars stand side by side, tallest first, hanging from the top.

## Scene
- `background-field`: the input is a field of `background`.
- `colored-rectangles`: the field holds several solid rectangles, each of its own color, and no two colors share a rectangle.
- `rectangles-may-overlap`: a rectangle may cover part of another; the covered rectangle still shows cells on both of its edges across `axis`, so its extent on `axis` is the extent of its color's cells.
- `distinct-extents`: no two rectangles have the same extent on `axis`.

## Rules
- `extent-per-color`: each non-`background` color has an extent, the count of lines on `axis` that its cells span (its bounding box's extent on `axis`).
- `bar-per-color`: the output has one line across `axis` per color, and that line holds the color's bar: the color fills its first extent cells from the `anchor` edge, and `background` fills the rest.
- `bars-ordered-by-extent`: the bars stand in order of extent, the longest at the `order-edge` edge and each next one shorter.
- `output-size`: the output's extent on `axis` is the longest bar's extent, and its extent across `axis` is the count of colors.

## Parameters
- `axis`: V
    - the axis on which each rectangle's extent is measured and along which each bar runs
- `anchor`: T
    - the edge every bar starts from
- `order-edge`: L
    - the edge the longest bar stands at
- `background`: 0

## Scene parameters
- none
