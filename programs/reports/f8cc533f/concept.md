# f8cc533f

## Concept
- Every colored figure is a damaged copy of one common pattern; repair each copy to the full pattern, which you get by overlaying all the copies.

## Scene
- `background`: one color fills every cell no figure holds.
- `one-color-per-copy`: each non-background color holds the cells of exactly one copy, and no two copies share a color.
- `copies-of-one-pattern`: each copy is the common pattern, placed somewhere in the grid, with some of its cells missing and no cell added.
- `pattern-is-union`: overlaying the copies, each aligned so that it lies inside the pattern, gives every cell of the pattern.
- `copies-apart`: the boxes of the full copies do not overlap one another, and each lies inside the grid.

## Rules
- `restore-copy`: each copy's color fills every cell of the pattern at that copy's placement.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- none

## Scene parameters
- none
