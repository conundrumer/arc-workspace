# e39e9282

## Concept
- Pins stuck to the sides of square boxes: a box of one color takes each of its pins inside, to the box's middle line; a box of the other color is taken away, and each of its pins grows one cell into the place where the box was.

## Scene
- `background`: a field of `background_color` fills the grid.
- `boxes`: solid `box_size`×`box_size` squares of `keep_color` or of `erase_color` stand on the field, apart from each other.
- `pins`: single cells of `pin_color` stand on the field, each next to one side cell of one box, across that side.

## Rules
- `pin-cleared`: each pin of a `keep_color` box becomes `background_color`.
- `pin-to-middle`: each pin of a `keep_color` box paints `pin_color` on the box cell where the pin's line, through the box, crosses the box's middle line across that line.
- `box-erased`: each `erase_color` box becomes `background_color`.
- `pin-grows`: each pin of an `erase_color` box stays, and paints `pin_color` on the box cell next to it.
- `rest-kept`: every other cell keeps its input color.

## Parameters
- `background_color`: 8
- `pin_color`: 9
- `keep_color`: 6
    - the color of the boxes that take their pins inside
- `erase_color`: 5
    - the color of the boxes that are taken away

## Scene parameters
- `box_size`: 3
