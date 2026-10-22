# b230c067

## Concept
- Each input has a few shapes of one color. All but one are copies of one shape. Recolor the copies with one color and the odd shape with another.

## Scene
- `objects-of-one-color`: on a field of `background`, every other cell has `object_color`, and those cells form objects, each an 8-connected component of `object_color` cells.
- `copies-and-one-odd`: `copy_count` objects are translates of one shape, and one other object has a different shape.

## Rules
- `copies-take-copy-color`: each cell of an object whose shape, up to translation, another object has turns `copy_color`.
- `odd-takes-odd-color`: each cell of an object whose shape, up to translation, no other object has turns `odd_color`.
- `rest-kept`: each cell that is in no object keeps its color.

## Parameters
- `object_color`: 8
- `copy_color`: 1
- `odd_color`: 2

## Scene parameters
- `background`: 0
- `copy_count`: 2
