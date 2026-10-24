# ef135b50

## Concept
- Solid rectangles stand scattered on a field; two rectangles that face each other along `bridge-axis` with nothing in between are bridged: the gap between them, on the lines they share, is painted in `bridge-color`.

## Scene
- `solid-rectangles`: the cells of `object-color` form solid axis-aligned rectangles on a field of `background`, and no two rectangles touch, by side or by corner.

## Rules
- `bridge-facing-pairs`: two rectangles face each other when they share a line along `bridge-axis`; their strip is the cells strictly between them on the lines they share. A pair whose strip holds no cell of `object-color` is bridged, and every cell of its strip takes `bridge-color`; a pair whose strip holds a rectangle cell is not bridged on any of its lines.
- `keep-rest`: every other cell keeps its input color; no bridge is painted across `bridge-axis`.

## Parameters
- `bridge-color`: 9
- `object-color`: 2
- `background`: 0
- `bridge-axis`: horizontal (the bridges run along rows)

## Scene parameters
- none
