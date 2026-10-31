# e41c6fd3

## Concept
- Several copies of one shape, each in its own color, sit at different heights; the copy in the anchor color stays put, and every other copy slides up or down into the same rows as it.

## Scene
- `copies-of-one-shape`: on a field of the `background` color, the cells of each other color form one copy, and all copies are translates of one shape.
- `one-anchor`: one copy has the `anchor` color.
- `disjoint-columns`: no two copies share a column.

## Rules
- `align-to-anchor`: each copy slides along `align_axis`, with its place across that axis kept, until its line on an edge of `align_axis` meets the anchor copy's line on that edge; the anchor copy stays where it is. The rule runs both edges of `align_axis` and is undefined on an input where the two edges give different outputs.
- `clear-rest`: every cell that no moved copy covers is the `background` color.

## Parameters
- `background`: `0`
- `anchor`: `8`
    - the color of the copy that keeps its place
- `align_axis`: `AXIS_V`
    - the axis of the slide

## Scene parameters
none
