# cfb2ce5a

## Departures
- `border=TileDim` is a `@derive` branch, written `// @derive TileDim: borderline $SquareFromFullTile` with `@relaxed square-in-border`. `analyze.md` (Not formed) says no proposer gives an edge margin. `derive` reports that TileDim fits every pair, and Develop step 4 holds every built-in derivation that fits. On the 12 × 12 input of `off-center-square`, the square inset by 2 recolors (8,9) and (9,8) to 5 and leaves the rest of the grid as the input, so the case is not subsumed.
- The combination `$SquareFromFullTile & $SourceFromFullQuadrant`, which `analyze.md` defines, is no case: `impl_choice` leaves it out. It fails Fit. Under the definition in `analyze.md`, a marker on a corner of the ink box is a full 1 × 1 tile, so several corners qualify and the first run left it undefined on train0, train2 and test0. Because of that, the `$SourceFromFullQuadrant` clauses implement only the inset-square reading: the square's one quadrant with no background cell. I took `other_full` out under Simplify.
- The concept constructors carry my own names: `$Mirror`, `$Inset` and `$StoredCorner`. `record --all` rewrote the groups in the witness file in terms of the solver's names.
- The witness file has a fifth witness, `border=TileDim`, written by `derive`. I rewrote its `separates` text.

## Judgments
- `sweep` says `copy_group` also admits `SYM_D4`. I did not store it. Overlaying every D4 element that carries the source quadrant onto a quadrant is not a per-quadrant table, so no reader of the table interpretation takes it.
- I wrote `@ignore cell: store` and `@ignore quadrant: store` above `quad`. `store` printed these instead of a `@store` line, and says no witnessed case would take the stored 8 × 8 frame.
- Determination of `background`: `square-in-border` says the border is background, so it is the one color of every edge cell of the trained inputs (`Unanimous`). Determination of `border`: the margin of the ink box from both edges of `source_corner`, which must agree across the trained examples. The ink box moved into `Parse`, which the program and `Determine` share.
- The first lint run gave case-section hints, because `sq_cell`, `quad`, `source` and `copy` ran across cases without a case key. I resolved them by keying `sq_cell` and `quad` by `Square`, `source` by `Square` and `Source`, and `copy` and `recolor` by `Choice` and `OpenValue`. No hint remains and lint is ok.
- Judgments on the `deletions` report:
    - These stay, because the pairs never instantiate what they guard: `inside(B, ZERO)` (where the square leaves the grid), `c4_elem` and `sym_member`/`copy_group` (which keep reflections out of the copies), `recolor.ov` (which keeps open values apart), `impl_choice` in `out`, `source` in the rest-kept clause (needed for undefinedness), and the `ex_out` guards (the test-input rule).
    - `quad.quadrant` in the `$Mirror` copy stays: the distance match implies it, but it states that the target cell is in quadrant Q.
- Keywords: `tile-arrangement d4 markers mapping`.
- Witness verdicts are as in `analyze.md`. `$StoredGroup` takes `asymmetric-tile` at borderline, verdict `concept`, the same as the first branch with that witness.
- Final runs: every train pair and the test pair pass with 7 witnessed cases, lint ok, determination ok (background, border), `witness` ok with and without `--file`, and audit ok. I ran the audit before the Simplify change to the full-quadrant pick, and `witness` after it.

## Unsettled
- Which border values TileDim gives on the 12 × 12 witness. I reasoned it from the proposer's definition: border 2, possibly also 5, which changes nothing there. I did not print it. A run that prints the derived `border` values on that input would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
