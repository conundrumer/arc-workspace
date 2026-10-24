# f21745ec

## Concept
- One rectangle carries a pattern inside its border; every empty rectangle outline of exactly the same height and width gets that pattern copied in, in its own color, and every outline of another size is erased.

## Scene
- `rectangles-on-background`: on a field of `bg`, a few single-color rectangles stand apart, each of its own color, none touching another.
- `one-patterned-rectangle`: exactly one rectangle has cells of its color inside its border, the pattern; each other rectangle is an empty one-cell-wide outline.

## Rules
- `same-size-gets-pattern`: an empty outline whose height and width both equal the patterned rectangle's takes, at each cell of its box, the patterned rectangle's cell at the same place in its box, recolored to the outline's color.
- `other-size-erased`: an empty outline whose height or width differs from the patterned rectangle's becomes `bg`.
- `pattern-kept`: the patterned rectangle stays as it is.

## Parameters
- `bg`: 0

## Scene parameters
none
