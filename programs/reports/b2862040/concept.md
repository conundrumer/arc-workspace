# b2862040

## Concept
- Every shape that has a hole in it is recolored; shapes with no hole stay as they are.

## Scene
- `background-field`: the grid is a field of `background`.
- `shapes`: on that field stand shapes, each a 4-connected set of `shape_color` cells.
- `some-shapes-closed`: some shapes close off a region of the field from the frame edge (a hole), and the other shapes close off none.

## Rules
- `recolor-closed-shapes`: each shape that by itself closes off a region from the frame edge takes `closed_color` on every one of its cells.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `shape_color`: 1
- `closed_color`: 8

## Scene parameters
- `background`: 9
