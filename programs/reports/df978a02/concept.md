# df978a02

## Concept
- Four shapes point at one center from its four sides; the biggest one bites off the tip of each of the others and grows by that many cells at its back.

## Scene
- `four-pointers`: on a field of `background`, four shapes of one color each, one on each side of a center cell; each shape's line nearest the center, across the row or column through the center, holds a single cell, its tip, which lies on that row or column.
- `one-largest`: one shape has more cells than each of the others.

## Rules
- `others-lose-tip`: each shape other than the one with the most cells loses its tip cell, which becomes `background`.
- `largest-grows-back`: the shape with the most cells gains one cell per tip taken, laid as a line across its axis, centered on the line through the center, one step beyond its far edge.
- `rest-unchanged`: every other cell keeps its input color.

## Parameters
- `background`: 8

## Scene parameters
- none
