# b9630600

## Concept
- Hollow boxes are rooms, and the rooms get joined by straight corridors into one network: each corridor runs between two rooms that face each other, and the network uses the shortest corridors and makes no loop.

## Scene
- `hollow-rooms`: every input holds several hollow rectangles on a `background` field, each with a wall 1 cell thick in `room_color` and an interior of at least 1×1 cells, and no two rectangles touch.
- `facing-network-connected`: the rooms are linked into one group through facing pairs, as `facing-pair` defines them.

## Rules
- `facing-pair`: two rooms face each other when, on one axis, their interiors share a span of lines, and the band between their facing walls across that span holds only `background`; the gap of the pair is the count of cells between the two facing walls.
- `shortest-joins`: a facing pair gets a corridor unless the two rooms are linked by a chain of facing pairs whose gaps are each strictly smaller than its gap, so the corridors are those of a minimum spanning tree of the facing pairs weighted by gap.
- `corridor-shape`: a corridor covers the span the two interiors share; across the gap, the two outermost lines of that span become `room_color`, and on the two facing walls, the lines strictly between those two become `background`. A span of 1 or 2 lines gives a solid bar with no opening.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `background`: 0
- `room_color`: 3
    - the color of the room walls and of the corridor walls

## Scene parameters
none
