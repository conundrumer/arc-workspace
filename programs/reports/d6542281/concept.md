# d6542281

## Concept
- A few whole shapes are drawn, and loose dots elsewhere repeat a few cells of one of them; each group of dots is completed into a copy of the shape it comes from, placed so the dots sit where those cells sit in the shape.

## Scene
- `background`: the commonest color of the input fills the field.
- `shapes`: some 8-connected objects of non-background cells hold more than one color; these are the whole shapes.
- `dots`: every other 8-connected object holds one color, and none touches a shape.
- `dots-from-one-shape`: the dots fall in groups, and each group is a translated copy of a subset of one shape's cells, color for color, at one placement of that shape alone.
- `copies-fit`: at that placement the shape's cells land on the group's dots or on background, and inside the grid.

## Rules
- `placement`: a placement of a shape is a translation that takes some shape cell onto a dot of its color, where every shape cell lands inside the grid on background or on a dot of its color.
- `largest-match`: a placement is kept when the set of dots it covers is not a proper subset of the set another placement covers.
- `stamp`: each kept placement draws the whole shape, cell for cell, over the input; every other cell keeps its input color.

## Parameters
- none

## Scene parameters
- none
