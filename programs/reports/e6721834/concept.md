# e6721834

## Concept
- The grid is two halves: one has rectangles with a few marked cells, the other has loose dots. Each rectangle moves to the dot half so its marked cells land on dots of the same colors; a rectangle whose marks match no dots is left out.

## Scene
- `two-halves`: the grid is cut along one axis into two halves of equal size, each filled with its own background color.
- `dot-half`: one half holds single dots on its background, no two of them 4-adjacent.
- `object-half`: the other half holds solid rectangles apart from one another, each of one body color with some cells of another color, its marks.
- `exact-cover`: in one way only, the dots split into groups, each group a translated copy of the marks, with their colors, of a different rectangle.
- `placed-fit`: each rectangle, moved by its group's translation, lies inside the dot half and overlaps no other moved rectangle.

## Rules
- `output-is-dot-half`: the output is the dot half, with its background kept and its dots erased.
- `move-rectangle`: each rectangle that has a group is drawn, body and marks, at the translation that puts its marks on that group.
- `drop-unmatched`: a rectangle that has no group is not drawn.

## Parameters
- none

## Scene parameters
- none
