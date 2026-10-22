# df9fd884

## Concept
- Two cups work as a pair of portals: an object lined up with the mouth of one cup goes in there, comes out of the mouth of the other cup still moving the same way, and slides on until it reaches the grid edge.

## Scene
- `background`: every cell that is not a cup or the object has the color `background`.
- `two-cups`: the input holds two cups of the color `cup_color`. A cup is a solid line along one edge of the grid with a leg of `cup_depth` cells at each end, standing away from that edge, so the cup's mouth faces into the grid.
- `opposite-cups`: the two cups lie in opposite corners, their mouths face each other along one axis, and the two mouths have one width.
- `one-object`: the input holds one connected object of one color that is neither `background` nor `cup_color`. Its color changes from pair to pair.
- `object-at-mouth`: the object is as wide as the mouths, lies in line with the mouth of one cup, the entry cup, and sits between the two cups, apart from both.
- `clear-path`: no cell other than `background` lies in the object's way from the mouth of the exit cup to the grid edge that mouth faces.

## Rules
- `remove-object`: the object's cells take the color `background`.
- `exit-other-cup`: the object, unchanged in shape and color, moves across the axis of the mouths until it lies in line with the mouth of the other cup, the exit cup.
- `slide-to-edge`: along that axis, the object then moves in the direction the exit cup's mouth faces, until it touches the grid edge.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `background`: 7
- `cup_color`: 4

## Scene parameters
- `cup_depth`: 1
    - the length of each leg of a cup, which is also the depth of its mouth
