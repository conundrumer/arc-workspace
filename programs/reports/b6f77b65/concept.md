# b6f77b65

## Concept
- A stack of arches is built from colored sticks; the marker colors in the corner name the sticks to pull out, and what they held up drops until it rests again.

## Scene
- `marker`: the line on the edge opposite `fall_dir` holds a run of marker cells from the `marker_corner` corner, and nothing else; the line next to it is empty.
- `arches`: the rest of the grid is a stack of arches, each a bar across the tops of two legs that run along the axis of `fall_dir`.
- `sticks`: each leg is one color for its whole length, its top corner cell included; each bar is one color over the cells strictly between its two legs.
- `stacked`: each leg stands on the edge toward `fall_dir` or on a stick of a lower arch; the two legs of one arch may differ in length.

## Rules
- `pull-marked`: every stick whose color is a marker color becomes `background`.
- `legs-fall`: each leg left moves toward `fall_dir` until the cell past its end is the frame edge or a stick.
- `bar-hangs`: a bar whose arch keeps both legs moves toward `fall_dir` until it lies on the line of the lower of its legs' tops, or a cell past it is the frame edge or a stick.
- `bar-drops`: a bar whose arch lost a leg moves toward `fall_dir` until a cell past it is the frame edge or a stick.
- `marker-kept`: the marker cells stay as they are.

## Parameters
- `fall_dir`: `DIR_B`
    - the direction in which sticks fall; the legs run along its axis, and the marker sits on the edge opposite it
- `background`: `0`

## Scene parameters
- `marker_corner`: `DIAG_TL`
    - the corner from which the marker run starts, on the edge opposite `fall_dir`
