# e9b4f6fc

## Concept
- Cut out the big picture and repaint it with the color key: each two-cell key says "this color becomes that color".

## Scene
- `background`: every cell outside the objects is `background`.
- `one-picture`: one connected object of more than two cells, the picture, a filled rectangle of a field color with a drawing of other colors on it.
- `domino-keys`: the other objects are keys, each two cells of two colors side by side on the axis of `new-side`, with background at every other cell that touches it at a side or a corner.
- `key-names-picture-color`: the old cell of each key holds a color of the picture's drawing, and the new cell holds a color the picture does not hold.
- `keys-cover-drawing`: each color of the drawing is the old color of exactly one key, and the field color is the old color of no key.

## Rules
- `crop-picture`: the output is the picture's bounding box, cut out of the input.
- `recolor-by-key`: each cell of the picture whose color is the old color of a key takes that key's new color; each other cell keeps its color.

## Parameters
- `background`: `0`
- `new-side`: `DIR_L`
    - the direction from a key's old cell to its new cell

## Scene parameters
- none
