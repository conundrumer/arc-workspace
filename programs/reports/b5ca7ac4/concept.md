# b5ca7ac4

## Concept
- Framed squares slide sideways to the grid edge by their frame color, squares of one frame color one way and the other the opposite way, and each square stops against the edge or against a square of its own frame color that is already stopped there.

## Scene
- `background`: one background color fills every cell outside the squares.
- `framed-squares`: the other cells form squares of side `box-size`, each a one-cell outline in one of the colors of `heading` around a solid interior of one color, and the interior color may equal a frame color.
- `disjoint-squares`: no two squares share a cell, and two squares may touch along an edge or at a corner.

## Rules
- `slide-by-frame`: each square keeps its rows and moves along the row axis toward the direction `heading` gives its frame color.
- `stack-per-color`: the squares of one frame color fall together as rigid bodies: each square stops at the first place where it meets the grid edge or a stopped square of the same frame color, and squares of the other frame color do not block it.
- `background-rest`: every cell that no moved square covers takes the background color.

## Parameters
- `heading`: 8 → left, 2 → right
    - the direction each frame color slides

## Scene parameters
- `box-size`: 5
