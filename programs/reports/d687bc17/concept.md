# d687bc17

## Concept
- Each dot flies to the wall of its own color and sticks to it; a dot whose color no wall has disappears.

## Scene
- `four-walls`: the grid's border is four walls, one per edge, each a solid line of one color across that edge, with the four corner cells `background`.
- `distinct-wall-colors`: the four walls have four different colors.
- `scattered-dots`: the interior is `background` with single-cell dots scattered in it, no two dots touching.
- `no-landing-clash`: no two dots of one wall's color share a line perpendicular to that wall.

## Rules
- `dot-to-wall`: a dot whose color is a wall's color moves, along its row or column perpendicular to that wall, to the interior cell next to that wall; other dots do not block it.
- `unmatched-dot-erased`: a dot whose color is no wall's color becomes `background`.
- `walls-kept`: the walls and the corner cells stay as they are.

## Parameters
- `background`: 0

## Scene parameters
- none
