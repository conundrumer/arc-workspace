# 6e453dd6

## Concept
- Each shape slides along its rows toward the divider until it touches it, and every row in which a shape that touches the divider holds a hole is marked across the far side of the divider.

## Scene
- `background`: every cell not otherwise named is `background`.
- `divider`: one full line of `divider` cells runs across the grid, perpendicular to `toward`, splitting it into a near side and a far side; the far side lies past the divider in direction `toward`.
- `far-side-empty`: every far-side cell is `background`.
- `shapes`: the near side holds one or more shapes, each a 4-connected set of `shape` cells; no two shapes share a line parallel to `toward` (each row, here), so background lines separate them.
- `holes`: some shapes close off background cells (a hole: a background region the shape alone cuts off from the frame edge and from the rest of the background).

## Rules
- `slide`: each shape moves rigidly in direction `toward` until its leading cells are adjacent to the divider; a shape already adjacent stays. The cells it leaves become `background`.
- `mark`: for each row in which a slid shape has a cell adjacent to the divider and has a hole cell, every far-side cell of that row becomes `mark`.
- `rest`: every other cell keeps its input color (the divider and the unmarked far-side cells unchanged).

## Parameters
- `toward`: R
    - the direction from the shapes to the divider, along which they slide
- `background`: 6
- `shape`: 0
- `divider`: 5
- `mark`: 2

## Scene parameters
none
