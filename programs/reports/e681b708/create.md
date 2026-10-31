# e681b708

## Departures
- The concept branches take names of their own: `Rooms4` for the 4-connected rooms and `RunDots` for the run-based dot set. No witness name refers to them. Run with `--file programs/reports/e681b708/witnesses.json`, the witness check reports no difference.

## Judgments
- The `background=DominantColor` branch is a `@derive DominantColor` line on `background`, not a constructor. Its plausibility and verdict are `borderline concept` with `@relaxed loose-dots`, as `analyze.md` gives them. Its witness is the one `analyze.md` built.
- The `$SideMarkers`, `$CornerMarkers`, `$StrictMajority`, `$NearestMarker` and `line_color=DominantColor` branches fail Fit at train0, as `analyze.md` states. They have no witness, so they are not formed. `derive` lists no derivation for `line_color`.
- The `Not formed` items in `analyze.md` state no model that fits: they are a tie rule no evidence gives, proposers that fail Fit or are undefined at every pair, derived data, and rectangle rooms that equal the concept's or `$Rooms8`'s rooms. Develop step 3 adds no branch.
- `store` prints no line to add. Only `runs.clear` and `runs.stop` vary, and they vary by position.
- The pairs run reports 5 witnessed cases: concept, `$Rooms8`, `$IsolatedDots`, `$MarkerFreeParts` and `background=DominantColor`. Every witness verdict is `concept`, so every non-concept branch is rejected. A combination of two rejected branches is not witnessed.
- Determination: `line_color` is the input color of each cell an output recolors. `background` is a color 4-adjacent to such a cell, other than that cell's own color. The first version of that relation also took the dot's own color at `domino-dot` and `dot-touching-wall`. The plan flagged this, and I added the exclusion. The plan then listed no actions.
- Deletions:
    - I removed the `impl_choice` atom in the dot `out` clause. `dot` and `room` already bind both fields, and every combination is a case.
    - I removed `!line(P)` from `$IsolatedDots`. A cell with no 4-adjacent cell other than `params.background` is on no run.
    - I removed the `in`/`params.line_color` atoms from `$MarkerFreeParts`. A non-background cell in a part with no marker has `line_color`.
    - Some atoms stay because the pairs never instantiate them:
        - `line(P) :- marker(P, _)`: markers are line cells, so they are not room cells.
        - `runs.stop` and `marker` in the run clause: a run must end on a marker.
        - `dir_elem` in the `background` determination: 4-adjacency.
- Keywords: `decompose markers rank`. The lines cut the grid into rooms, and the markers supply the colors. The commonest marker color is an extremum over counts.
- Hints: lint reported one `long-clause` at the `$MarkerFreeParts` dot clause. I wrapped it, and later simplified it to one short line.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
