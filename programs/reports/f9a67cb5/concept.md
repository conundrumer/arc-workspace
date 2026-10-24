# f9a67cb5

## Concept
- Water poured from a spout on one edge falls away from that edge; at each wall it spreads sideways along the wall until it finds a hole or the grid edge, drains through every hole it finds, and keeps going until it leaves the far edge.

## Scene
- `one-source`: exactly one cell of `source_color` lies on an edge of the grid, off its corners; that edge is the source edge.
- `parallel-walls`: full-length lines of `wall_color` run parallel to the source edge, each broken by one or more one-cell gaps.
- `walls-apart`: at least one line free of wall lies between the source edge and the first wall, between each two walls, and between the last wall and the far edge.
- `background`: every other cell is `background`.

## Rules
- `fall-straight`: water leaves the source moving away from the source edge and moves straight on while the cell ahead is not wall, until it leaves the grid.
- `spread-along-wall`: where the cell ahead of the water is wall, the water spreads both ways along its line, each way up to and including the first cell whose cell ahead is not wall, or up to the grid edge.
- `drain-through-gap`: from each cell the water reaches whose cell ahead is not wall, the water falls straight on through the gap; water that arrives straight in front of a gap passes through without spreading.
- `paint-water`: every cell the water reaches takes `source_color`; every other cell keeps its input color.

## Parameters
- `source_color`: 2
    - the color of the spout, which the water takes
- `wall_color`: 8

## Scene parameters
- `background`: 0
