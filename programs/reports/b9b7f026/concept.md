# b9b7f026

## Concept
- Several filled rectangles lie on a field, and one of them has a hole in it; the answer is that rectangle's color, as a single cell.

## Scene
- `rectangles`: each input holds several axis-aligned rectangles on a field of `bg`, each of its own color; two rectangles may touch.
- `one-holed`: exactly one rectangle has a hole: a region of `bg` cells inside it that no walk through `bg` cells reaches from the frame edge.

## Rules
- `holed-color`: the output is a 1×1 grid whose cell is the color of the rectangle that encloses the hole.

## Parameters
- `bg`: 0

## Scene parameters
none
