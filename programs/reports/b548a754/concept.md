# b548a754

## Concept
- A framed box is stretched toward a marker dot until its far side reaches the dot.

## Scene
- `framed-box`: one solid rectangle on `background`, with a 1-wide border of one color around an interior of another color.
- `marker`: one cell of `marker_color`, outside the box, within the box's span on one axis, so that it lies straight out from one side of the box.
- `background`: every other cell is `background`.

## Rules
- `stretch-to-marker`: the side of the box that faces the marker moves out to the marker's row or column, and the opposite side stays; the stretched box is drawn with the same 1-wide border color and the interior color fills its inside, so the marker cell becomes border.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `marker_color`: 8
- `background`: 0

## Scene parameters
- none
