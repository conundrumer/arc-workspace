# e3721c99

## Concept
- A legend of keys, each a solid colored block with some number of holes, tells what color each `shape_color` shape takes: a shape takes the color of the key with as many holes as the shape has, and a shape whose hole count no key has is erased.

## Scene
- `divider`: a line of `divider_color`, straight or bent once, the one object of that color that touches the grid edge, runs to the grid edge and cuts off a legend region at one side or corner of the grid.
- `legend-keys`: the legend region holds keys in a row or a column, each a block of one color other than `shape_color`, with single `background` cells as holes; no two keys have the same hole count.
- `shapes`: outside the legend, shapes of `shape_color` on `background`, each a 4-connected set of cells that encloses zero or more holes.
- `hole`: a hole of an object is a 4-connected region of the cells outside that object that no walk of cardinal steps through the cells outside that object reaches from the grid edge.

## Rules
- `recolor-by-holes`: each shape takes the color of the key whose hole count equals the shape's hole count.
- `erase-unmatched`: a shape whose hole count no key has becomes `background`.
- `rest-kept`: the divider, the keys and the background stay as they are.

## Parameters
- `shape_color`: 5
- `background`: 0
- `divider_color`: 1
    - the color of the line the program excludes from the keys

## Scene parameters
none
