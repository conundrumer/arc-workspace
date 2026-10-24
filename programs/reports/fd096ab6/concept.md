# fd096ab6

## Concept
- One shape in `template_color` is whole; every other colored piece is a broken-off part of a copy of that shape, and each piece is completed into a full copy of the shape in its own color.

## Scene
- `background-field`: the grid is a field of `background`.
- `one-template`: exactly one shape is drawn in `template_color`, and it is the whole shape.
- `fragments`: every other non-`background` cell belongs to a fragment, a set of cells of one color that lie on one translated copy of the template and are a proper part of it; no other translated copy of the template holds every cell of the fragment.
- `copies-clear`: each fragment's completed copy lies inside the grid, on `background` cells apart from the fragment's own cells, and meets no other copy.

## Rules
- `keep-input`: every input cell keeps its color.
- `complete-fragment`: for each fragment, the translated copy of the template that holds all its cells is drawn in the fragment's color.

## Parameters
- `background`: 1
- `template_color`: 4
    - the color of the whole shape that every fragment is completed to

## Scene parameters
none
