# ae58858e

## Concept
- Recolor every shape of four or more cells; leave the small shapes as they are.

## Scene
- `scattered-shapes`: the grid holds shapes of one color `shape_color` on a field of `0`, each shape a 4-connected group of cells, and some shapes have fewer than `min_size` cells while others have at least `min_size` cells.

## Rules
- `recolor-large`: each shape of at least `min_size` cells takes the color `new_color` in the output.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `shape_color`: 2
- `new_color`: 6
- `min_size`: 4
    - the fewest cells a shape has when it is recolored

## Scene parameters
- none
