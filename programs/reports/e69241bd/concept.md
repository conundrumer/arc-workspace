# e69241bd

## Concept
- Walls split the floor into rooms, and each colored seed paints the whole room it stands in with its own color.

## Scene
- `floor-and-walls`: every cell is a floor cell of color `background` or a wall cell of color `wall`, apart from a few seed cells.
- `seeds`: each seed is a single cell of a color other than `background` and `wall`, and no two seeds share a room.
- `rooms`: a room is a 4-connected component of the floor cells and seeds.

## Rules
- `seed-fills-room`: each floor cell of a room that holds a seed takes that seed's color.
- `rest-unchanged`: every other cell keeps its input color.

## Parameters
- `background`: 0
- `wall`: 5

## Scene parameters
- none
