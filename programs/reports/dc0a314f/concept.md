# dc0a314f

## Concept
- A symmetric pattern has a patch painted over; fill the patch in from the pattern's mirror images and give back what was under it.

## Scene
- `symmetric-pattern`: the grid is square, and once the covered cells are filled in, it is unchanged under each symmetry of the `symmetry` group about the grid's center.
- `cover-block`: one solid rectangle of `cover_color` covers part of the pattern, and `cover_color` occurs nowhere else.
- `cover-recoverable`: each covered cell has an image under the `symmetry` group that is not covered.

## Rules
- `fill-from-image`: each covered cell takes the color of an uncovered image of it under the `symmetry` group.
- `crop-cover`: the output is the cover's rectangle of the filled grid.

## Parameters
- `cover_color`: 3
- `symmetry`: the eight symmetries of the square (D4)

## Scene parameters
- none
