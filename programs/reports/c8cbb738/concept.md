# c8cbb738

## Concept
- Several four-dot figures lie apart on a plain background. Stack them all on one common center, and crop to the largest figure, which is a square.

## Scene
- `plain-background`: one color fills every cell that is not a mark.
- `one-figure-per-color`: each mark color other than the background marks exactly `marks-per-figure` cells, and those cells form one figure.
- `figure-has-both-mirror-symmetries`: each figure is unchanged by a flip across its vertical center line and by a flip across its horizontal center line, so it is the four corners of a rectangle or the four edge midpoints of a box (a diamond).
- `odd-extents`: each figure's bounding box has an odd height and an odd width, so each figure has a center cell.
- `largest-figure-is-square`: one figure's bounding box is a square whose side is at least the height and the width of each other figure's bounding box.

## Rules
- `output-is-largest-box`: the output is a square whose side is the side of the largest figure's bounding box, filled with the background color.
- `figures-share-center`: each figure is copied into the output, translated so that the center of its bounding box is at the center of the output, with each mark keeping its color.

## Parameters
- none

## Scene parameters
- `marks-per-figure`: 4
