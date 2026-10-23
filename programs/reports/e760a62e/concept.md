# e760a62e

## Concept
- Divider lines cut the grid into a tiling of rooms, and some rooms hold a colored dot. Each two rooms whose dots have one color and that share a row or a column of rooms are joined by a bar of that color, which fills every room from one to the other. Where a bar of one color crosses a bar of the other color, the room takes a third color.

## Scene
- `divider-tiling`: full rows and full columns of `divider_color` cut the grid into rooms of one size, with a gap of one line between each two; the last row of rooms and the last column of rooms can be cut short by the bottom and right edges.
- `background-rooms`: every room cell that holds no dot is `background`.
- `one-dot-per-room`: a marked room holds exactly one dot cell, and the rest of that room is `background`.
- `dot-offset`: every dot sits at one place within its room, the same place for every dot of the input.
- `two-dot-colors`: each dot has one of the two colors of `cross_color`'s key.
- `dots-pair-up`: each dot shares a row or a column of rooms with at least one other dot of its color.

## Rules
- `join-aligned-dots`: for each two dots of one color in one row of rooms, or in one column of rooms, every room from the room of one dot to the room of the other, both included, fills whole with that color.
- `cross-mix`: a room that bars of both dot colors fill takes `cross_color`.
- `keep-rest`: the dividers and every room that no bar fills stay as in the input.

## Parameters
- `divider_color`: 8
- `background`: 0
- `cross_color`: {2, 3} → 6
    - the color of a room that bars of the two key colors both fill

## Scene parameters
- none
