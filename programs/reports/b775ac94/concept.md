# b775ac94

## Concept
- Each shape has a 2×2 color key at one corner: the shape's corner cell and up to three single marker cells around it. The shape is mirrored into each other quadrant of the key that holds a marker, and each copy takes the color of the marker in its quadrant.

## Scene
- `shapes`: the non-`background` cells form separate objects. Each object is one shape of one color (its cells 8-connected), plus one to three single marker cells.
- `key-block`: one cell of the shape, at a corner of the shape's bounding box, and the object's marker cells lie in one 2×2 block. That shape cell is the block's corner nearest the shape, and each marker fills one of the other three corners of the block.
- `marker-colors`: each marker's color differs from the color of its shape.
- `room`: each copy fits in the grid and covers no other object.

## Rules
- `keep`: each input cell that is not `background` stays in the output, and a copy cell that lands on one does not replace it.
- `mirror-copy`: for each marker, the shape is copied into the marker's quadrant of the key block, in the marker's color. The copy is the shape's image under the reflection that takes the shape's key cell to the marker's cell:
    - a marker beside the key cell along a row gives the reflection across the key block's vertical center line;
    - a marker beside it along a column gives the reflection across the key block's horizontal center line;
    - a diagonal marker gives both reflections together (a half turn about the key block's center).
- `no-marker-no-copy`: a corner of the key block with no marker gets no copy.

## Parameters
- `background`: 0

## Scene parameters
- none
