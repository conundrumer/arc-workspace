# e3fe1151

## Concept
- A cross splits the grid into four small quadrants that all hold the same colors; one cell of each quadrant is blanked out, and you fill each blank with the color its quadrant is missing compared to the others.

## Scene
- `cross`: one full row and one full column of `divider_color` split the grid into four quadrants of `quadrant_size` × `quadrant_size` cells.
- `blanks`: each quadrant holds `blanks_per_quadrant` cells of `divider_color`, and its other cells hold no `divider_color`.
- `shared-multiset`: each quadrant, with its blanks filled, holds the same multiset of colors, and the quadrants' blanks sit so that each color of that multiset shows its full count in some quadrant.

## Rules
- `keep`: every cell that is not a blank keeps its color.
- `fill-missing`: each blank takes the color its quadrant lacks against the multiset union of the four quadrants' non-blank colors (each color at the highest count it has in one quadrant).

## Parameters
- `divider_color`: 7
    - the color of the cross, which is also the color of a blank cell

## Scene parameters
- `quadrant_size`: 2
- `blanks_per_quadrant`: 1
