# baf41dbf

## Concept
- A rectangular frame stretches toward the marker dots outside it: each side moves out until it stands right next to the farthest marker beyond that side, and the frame's divider lines stretch with it.

## Scene
- `frame`: one rectangle outline of the color `frame_color`, on a field of the color `background`, with zero or more full-span divider lines of `frame_color` across its inside; every other inside cell is `background`.
- `markers`: single cells of the color `marker_color`, each outside the frame's box and beyond at least one of its sides.

## Rules
- `side-moves-to-marker`: each side of the frame that has a marker beyond it moves out to stand `marker_gap` cells short of the farthest such marker; a side with no marker beyond it stays.
- `outline-redrawn`: the output draws the outline of the new box in `frame_color`, and the old outline's cells that are not on the new outline or on a divider become `background`.
- `dividers-stretch`: each divider keeps its row or column and runs across the whole new box.
- `markers-stay`: the markers and the rest of the grid are unchanged.

## Parameters
- `frame_color`: 3
- `marker_color`: 6
- `background`: 0
- `marker_gap`: 0
    - the count of background cells between a marker and the side it pulls

## Scene parameters
- none
