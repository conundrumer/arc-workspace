# c87289bb

## Concept
- The concept fits every train and test pair (`probe.py`, `check_concept.py`). Each rule has a relational form, and no witness has the verdict `other`.
- Two witnesses have a verdict for a non-concept branch, and each breaks a scene claim of the concept:
    - `bar-at-side-edge` breaks `exits-in-grid`. There, a person expects the stream to go around the bar's other end, and the concept runs the stream off the grid.
    - `streams-from-bottom` breaks `streams-from-edge`. There, a person expects the streams to flow upward, and the concept, at a stored `fall_dir` of down, finds no stream and returns the input.

## Choice points
- `side`: which way a stream goes around a bar it meets
    - `concept`: toward the bar's nearer end (`detour-nearer-end`)
    - `$StoredSide`: replaces `detour-nearer-end` and `tie-side`: the stream always runs toward `tie_dir`. It is undefined on no input. It fails Fit at train1: the stream in col 5 goes left, to col 4.
    - `$NearerEdgeSide`: replaces `detour-nearer-end` and `tie-side`: the stream runs toward the grid edge nearer to its line, and toward `tie_dir` when the two edges are equally near. It is undefined on no input. It fails Fit at test0: the stream in col 10 goes left to col 9, and the branch sends it right to col 14.
- `tie`: the side taken when a stream meets a bar at its middle cell
    - `concept`: the stored `tie_dir` (right) (`tie-side`)
    - `$TieNearerEdge`: replaces `tie-side`: the stream runs toward the grid edge nearer to its line. It is undefined where that stream's line is the grid's center column. It fits every pair. Witness `tie-left-of-center`: it breaks no scene claim, stands at the stored assignment, and is `ordinary` with the verdict `concept`.
    - `$TieSplit`: replaces `tie-side`: the stream runs around both ends. It is undefined on no input. It fails Fit at train0: the stream in col 5 goes right only.
    - `$TieAwayFromStreams`: replaces `tie-side`: the stream runs toward the end whose exit cell is farther from the nearest other stream. It is undefined where the two distances are equal. It fails Fit at train0, where the two distances are equal.
- `edge-exit`: what a stream does when the cell past the nearer end of its bar lies outside the grid
    - `concept`: the run leaves the grid there (`detour-nearer-end`)
    - `$EdgeOtherSide`: adds to `detour-nearer-end`: the stream runs toward the other end. It is undefined on no input. It fits every pair. Witness `bar-at-side-edge`: it breaks `exits-in-grid`, stands at the stored assignment, and is `borderline` with the verdict `$EdgeOtherSide`. It breaks the invariant that every bar has a free cell inside the grid past each of its ends.
- `later-bars`: what a stream does after a detour when its new line meets another bar
    - `concept`: it detours again by the same rules (`detour-nearer-end`)
    - `$OneDetour`: replaces `detour-nearer-end`: after its first detour, the stream falls straight to the far edge and passes over bar cells, which keep their color. It is undefined on no input. It fits every pair. Witness `bars-at-two-depths`: it breaks `bars-in-one-line`, stands at the stored assignment, and is `variant` with the verdict `concept`. It breaks the invariant that all bars lie in one row.
- `run-line`: the line of cells the detour runs across
    - `concept`: the line just before the bar (`detour-nearer-end`)
    - `$RunAtStreamEnd`: replaces `detour-nearer-end`: the run is on the stream's last input cell's line, and the stream falls from the exit cell to the bar's line. It is undefined on no input. It fails Fit at train0: the stream in col 5 ends on row 2, and the run is on row 3.
- `after-detour`: where the stream goes after it passes the bar's end
    - `concept`: it falls on in the exit cell's line (`detour-nearer-end`)
    - `$ReturnBelow`: replaces `detour-nearer-end`: past the bar, the stream steps back across to its own line and falls on in it. It is undefined on no input. It fails Fit at train0: the stream stays in col 7 below the bar.
- `fall-dir`: the direction in which the streams fall
    - `concept`: the stored `fall_dir` (down)
    - `$FallFromEdge`: replaces `streams-from-edge` and the stored `fall_dir`: the program derives `fall_dir` from the input as the direction away from the edge that the streams touch. It is undefined where streams touch both the top and the bottom edge, or neither. It fits every pair. Witness `streams-from-bottom` (train0's input flipped top to bottom): it breaks `streams-from-edge`, stands at the stored assignment, and is `variant` with the verdict `$FallFromEdge`. It breaks the invariant that every stream touches the top edge.
- `bar-color`: the color of the bars
    - `concept`: the stored `bar_color` (2)
    - `bar_color=RarestColor`: replaces the stored `bar_color` with the color that has the fewest cells in the input. It is undefined where two colors tie for the fewest cells. It fits every pair. Witness `bar_color=RarestColor`: the bar there has more cells than the streams together. It breaks no scene claim, stands at the stored assignment, and is `variant` with the verdict `concept`. It breaks the invariant that the bar color has fewer cells than the stream color in every input.
- `side` & `edge-exit`, `side` & `later-bars`, `side` & `run-line`, `side` & `after-detour`, `side` & `fall-dir`, `side` & `bar-color`, `tie` & `edge-exit`, `tie` & `later-bars`, `tie` & `run-line`, `tie` & `after-detour`, `tie` & `fall-dir`, `tie` & `bar-color`, `edge-exit` & `later-bars`, `edge-exit` & `run-line`, `edge-exit` & `after-detour`, `edge-exit` & `fall-dir`, `edge-exit` & `bar-color`, `later-bars` & `run-line`, `later-bars` & `after-detour`, `later-bars` & `fall-dir`, `later-bars` & `bar-color`, `run-line` & `after-detour`, `run-line` & `fall-dir`, `run-line` & `bar-color`, `after-detour` & `fall-dir`, `after-detour` & `bar-color`, `fall-dir` & `bar-color`: the two branches' changes applied together
- `side` & `tie`: the `side` branch's model alone. A side rule that does not compare the bar's two ends has no tie at a bar's middle cell. So the `tie` point exists only with the concept branch of `side`, and it stands at the concept.

## Open parameters
- none

## Not formed
- The side with the shorter run, counted in cells: the run toward an end is one cell longer than the distance to that end, so this gives the concept's model.
- `stream_color` by a proposer: no proposer in `programs/proposers.dl` gives 8 alone on each input. `SharedColor` gives 0, 2 and 8, `DominantColor` gives 0, `RarestColor` gives 2, and the proposers that read `ex_out` give nothing when `ex_out` is empty.
- `tie_dir` and `fall_dir` by a proposer: no proposer gives a direction.
- `background` derived: the program does not read `background`, because `keep-input` protects bar cells only.

## Tickets filed
- 10-554_task_c87289bb_analyze.md
