# bda2d7a6

## Concept
- The grid is a set of nested square rings, and the ring colors rotate one step inward: each color is replaced by the color that comes just before it, counted from the outside, and the first color is replaced by the last.

## Scene
- `nested-rings`: the grid is square, and every cell's color depends only on its ring, the cells at one distance from the nearest frame edge; each ring is `ring-width` cells wide.
- `color-cycle`: read from the outermost ring inward, the first `color-count` rings show `color-count` distinct colors, one new color each, and every ring after them repeats a color already seen.

## Rules
- `cycle-colors`: list the distinct colors in the order they first appear from the outermost ring inward; every cell of color at place i in that list takes the color at place i − `step`, wrapping around the list.

## Parameters
- `step`: 1
    - how many places back in the outside-in color list each color takes its replacement from

## Scene parameters
- `ring-width`: 1
- `color-count`: 3
