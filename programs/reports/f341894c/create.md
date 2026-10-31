# f341894c

## Departures
- `$ComponentArrow` has no constructor: `analyze.md` gives it no witness, and it fails Fit at train2 (rows 4–5, cols 8–9).
- The case `$MarkerInLine` (with the concept branch `$BothUndefined`) left the solver under Subsumption, and `witness --file programs/reports/f341894c/witnesses.json` now reports that `$MarkerInLine` names no case on `interior-marker` and `markers-both-ends`. The reason is that the case's model is undefined wherever it differs from `$MarkerInLine & $NearerMarker`, because two aims on one arrow give its cells two colors, and no input shows it defined and differing. The `$MarkerInLine` branch stands for `$MarkerInLine & $NearerMarker`, and `interior-marker` witnesses that case. This is no error in `analyze.md`.
- A new branch `$Alternate`, at a new choice point `ArrowParse` whose concept branch is `$Pair`, is formed from the Not formed item "recoloring a marker line's head/tail cells alternately from the marker". Develop step 3 requires it because the item states one model and that model fits every pair. Its witness `alternate-crossing` is new.
- `impl_choice` lists 4 cases: `concept`, `$NearerMarker`, `$MarkerInLine & $NearerMarker`, and `$Alternate`. `$Alternate & $MarkerInLine` fails Fit at train2, where the interior-looking marker (13,4) recolors (13,0). `$Alternate & $NearerMarker` has no statement in the Analyze files, so it is not formed.

## Judgments
- `alternate-crossing` (built): the row 2 marker at (2,6) crosses (2,4), a cell of the column-4 arrow, before it reaches its own arrow at (2,1)–(2,2). This breaks `one-marker-per-arrow`, because the line holds another arrow's cell, so the plausibility is `borderline`. The verdict is `concept`, because the generator turns arrows, not line cells.
- Alternation is encoded as a walk on the 2-cycle head→tail→head (`CycleWalk`), one step per rank of the line's `Order`. This keeps parity out of arithmetic, per "A wraparound shift is a walk around a cycle".
- The hint `argmax` on a self-join `overridden` relation was valid. The nearer-marker choice now reads `ArgExtremes` over both orders of each arrow's cells. A tie keeps both aims, so the model is undefined at equal distance, as the branch claims.
- The concept reads `sight.ray` (no blocking), and `$MarkerInLine` reads `sight.clear` (blocked at markers), from one shared `Ray` instance.
- `deletions`: these deletions change nothing on the pairs, and they stay because the pairs never instantiate the structure they serve: `sight.blocked` (`$MarkerInLine`), the already-aimed disjunct of `aim`, the second order of `nearest.cand` (two markers), the tail→head `succ` (rank ≥ 2), `arrow_color` in `along.score` (it states the scored set explicitly), and `ex_out` in `off_border` (test inputs). The bound enumerator `dir_elem(E)` stays.
- Determination: `marker_color` is the color whose every cell lies on the border. `head_color` and `tail_color` are the output colors of two adjacent changed cells on the line of an edge marker, nearer cell first. The plan reports no actions.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
