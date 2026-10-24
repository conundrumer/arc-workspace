# f0100645

## Concept
- Two opposite edges of the grid are walls of two different colors. Each shape slides straight toward the wall of its own color, like gravity, and stops when it touches that wall or a shape that has already stopped.

## Scene
- `two-walls`: two opposite edge lines of the grid are each one solid color, and the two colors differ.
- `background`: every other cell that is not part of a shape is `background`.
- `shapes`: the shapes are 8-connected groups of one color, and each shape's color is one of the two wall colors.
- `shapes-clear-of-walls`: no shape touches a wall in the input.

## Rules
- `fall-to-own-wall`: each shape moves as a rigid body along the wall axis toward the wall of its color.
- `stack`: a shape stops at the smallest shift that puts one of its cells next to its wall, or next to a cell of a stopped same-direction shape. Shapes nearer the wall stop first.
- `keep-rest`: the walls stay in place, and every cell no shape covers after moving is `background`.

## Parameters
- `background`: 7

## Scene parameters
none
