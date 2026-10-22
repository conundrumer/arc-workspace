# c87289bb

## Concept
- Streams fall from the top edge to the bottom edge, and a stream that lands on a bar flows around it by the bar's nearer end, going right when both ends are equally near.

## Scene
- `streams-from-edge`: vertical streams of `stream_color`, each one column wide, run from the edge opposite `fall_dir` toward `fall_dir` and stop short of the far edge.
- `bars-in-one-line`: bars of `bar_color`, each one cell deep along `fall_dir` and one or more cells wide, lie in one line across `fall_dir`, past the end of every stream.
- `exits-in-grid`: the cell past each end of a bar lies in the grid.
- `detour-lines-free`: past each end of a bar, the line along `fall_dir` holds no bar cell.
- `background-rest`: every other cell is `background`.

## Rules
- `straight-fall`: a stream whose line holds no bar past its end extends in `fall_dir` to the far edge.
- `detour-nearer-end`: a stream whose line meets a bar extends to the cell before the bar, runs across along that line of cells toward the bar's nearer end to the first cell past that end, and from there falls on in `fall_dir` by these rules.
- `tie-side`: a stream that meets a bar at a cell equally far from its two ends runs toward `tie_dir`.
- `keep-input`: a cell the streams do not cover keeps its color, and the streams cover no bar cell.

## Parameters
- `stream_color`: 8
- `bar_color`: 2
- `fall_dir`: down
    - the direction in which the streams extend
- `tie_dir`: right
    - the side a stream takes around a bar it meets at the bar's middle cell

## Scene parameters
- `background`: 0
