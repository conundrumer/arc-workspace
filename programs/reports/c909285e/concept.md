# c909285e

## Concept
- A busy patterned grid has one square drawn on it in a color used nowhere else; cut that square out, its outline included.

## Scene
- `patterned-field`: a pattern of several colors covers the whole grid.
- `one-outline`: one rectangle outline, one cell wide, sits on the pattern; it is a square in every input.
- `outline-color-unique`: the outline's color appears nowhere else in the input.

## Rules
- `crop-outline`: the output is the input cropped to the outline's box, the outline included, with every cell copied as it is.

## Parameters
- none

## Scene parameters
- none
