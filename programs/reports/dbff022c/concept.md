# dbff022c

## Concept
- A two-line legend on the grid edge pairs colors: each color on the line along the edge names an outline color, and the color beside it on the inner line is the paint for that outline's holes. Each outline whose color the legend names gets its holes filled with that paint, and every other outline stays as it is.

## Scene
- `legend`: one block of cells of several colors, two lines thick, with one of its long sides on the grid edge; each cross line of the block is one pair of colors.
- `key-line`: the line of the legend that lies on the grid edge holds the keys, and the other line holds the paints.
- `outlines`: apart from the legend, each object is drawn in one color on a field of `bg`, and encloses one or more holes of `bg` cells that no 4-adjacent walk through `bg` cells reaches from the grid edge.
- `hole-wall`: each hole meets the cells of one outline color only.

## Rules
- `fill-keyed-holes`: each hole whose wall color is a key of the legend takes the paint paired with that key.
- `keep-rest`: every other cell, the legend and the holes of outlines whose color is no key included, keeps its input color.

## Parameters
- `bg`: 0

## Scene parameters
none
