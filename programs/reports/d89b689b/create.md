# d89b689b

## Departures
- The witness file has a witness that `witnesses.json` lacks, `marker-in-right-half-column`. It is train2's input with marker 4 moved from (0,9) to (0,5), directly above the block's left column and in the grid's right half. `$GridQuadrant` gives train2's output there. `$NearestBlockCell` sends 1 and 4 to one cell, and the concept leaves (2,6) empty, so both are undefined. This rests on the audit: no run showed `$GridQuadrant` defined and differing from the concept, and then from `$NearestBlockCell`. Without the witness, `$GridQuadrant` would leave under Subsumption. With it, the case meets Subsumption and stays. I added it to the branch as `@witness marker-in-right-half-column: borderline $GridQuadrant`, `@relaxed one-marker-per-corner`.
- The scene lines name `block_color` and `background` rather than giving 8 and 0. The concept file's Scene parameters section is empty, and that section is what fixes which values a `@scene` line gives.

## Judgments
- Choice shape: `Choice = [t: Target, l: Locate]`, built from `analyze.md`'s choice points. `Target` holds `BlockCorner` (concept), `$GridQuadrant` and `$NearestBlockCell`. `Locate` holds `ByColor` (concept) and `$BlockByShape`. `background=DominantColor` is a `@derive` line, not a constructor. That gives 12 cases, and 5 are witnessed. `$ReadingOrder` and `$KeepMarkers` fail Fit and have no witness, so they get no constructor.
- Concept defined only when a block is found: the clear-rest clause reads `block.box(L, _)`. Without it, the concept gave an all-background grid on `block-other-color`, not the undefined result `witnesses.json` gives. The deletions report flags this atom because the pairs never need it. I keep it because that witness does need it.
- `$NearestBlockCell` encoding: 4-step distance comes from `GraphDistance` over grid adjacency, keyed by marker. The least distance comes from `ArgExtremes` keyed by a `MarkerOf = [l: Locate, m: Position]` record, which is the allowed kind of record used as a generic comp's type argument. The record is needed because the block cells, and so the markers, depend on `Locate`. The first draft used a defect-negation self-join and drew the `argmax` hint. I replaced it with `ArgExtremes`, the lib form of that step.
- `$BlockByShape` encoding: "the one component with more than one cell" is a `Unanimous<Unit, Ident>` over the ids of multi-cell components, so two such components leave the case undefined, as `analyze.md` states.
- Deletions report: I dropped `marker(M, _, L)` from the `$GridQuadrant` target clause, because `out` already joins `marker`. I kept `marker` in `nearest.cand`, because it keys the comparison by a marker under that reading. I kept `in(Q, _)` in `steps.edge`, because it states grid adjacency. I kept the `ex_out(E, _, _)` filters in Determine, because they hold the test inputs out. I kept `outvoted`, because it is the universal that the background determination states.
- Determine: the plan listed `background` (DominantColor) and `block_color` (VanishedColor) under the "fact other than any the concept derives it from" condition. The concept derives neither value, so I took the condition as holding and wrote both relations. `background` is the commonest color of every solved input. `block_color` is an input color that no output holds. My first `block_color` test read inputs and outputs together and drew the "determine prediction" hint, so I rewrote it to test outputs alone.
- Witness judgments for `marker-in-right-half-column`: plausibility `borderline`, because it breaks `one-marker-per-corner`. Verdict `$GridQuadrant`: with one marker off the top-left corner and one above the left column, giving each top marker its own top cell, left to right, is the natural reading.
- Not formed in `analyze.md`, each judged at Develop step 3:
    - Output cropped to the block: fails Fit, because the outputs are 10×10.
    - Markers matched to block cells by color: fails Fit, because 9 sits at different corners in train0 and train1.
    - King-move nearest block cell: fails Fit at train0. Marker 7 at (0,8) is at Chebyshev distance 4 from both (4,4) and (4,5), a tie.
    - Euclidean nearest block cell: fails Relational form, because a Euclidean distance counts nothing the task has.
    - Other block sizes: add no model, because the bounding-box encoding already reads any block.
- `store` printed no line to add. `halves.*` and `steps.edge` have no witness, and `block_cell` has no anchor. So no `@store` branch was added.
- Hints: `argmax` and "determine prediction" were each resolved as described above. The lint now has no hints and no findings.
- No performance issues: every run finished in under 10 s.

## Unsettled
- The 7 cases that are not witnessed: for example, `$GridQuadrant & $BlockByShape`, and every `Target` branch combined with `background=DominantColor`. No input in the task or the witness file shows any of them giving an output that their partial cases do not, so every check skips them. A witness showing such an output would settle each one.
- How to read the determination-plan's "other than any the concept derives it from" when the concept derives the value from nothing. A doc line or tool text that states the vacuous case would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
