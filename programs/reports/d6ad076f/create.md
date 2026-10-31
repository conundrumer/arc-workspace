# d6ad076f

## Departures
- none

## Judgments
- Solver and witness file: `programs/solvers/d6ad076f.dl` and `programs/witnesses/d6ad076f.wit.json`. All three train pairs and the test pair pass at 5 witnessed cases out of 12. Lint, determination (`bg`, `fill`, `inset`), `witness` (on both files) and `audit` all pass, and the audit skips no check.
- Blocks are parsed as 4-connected components of non-`bg` cells, each with its bounding box (`Components` + `Bbox`, the parse 1da012fc uses), not as color classes. Both parses are faithful to `two-blocks`. With components, the `bg=DominantColor` witness of analyze.md stays undefined in the way analyze.md describes: the 0 cells and the 9 block merge into one block.
- The concept is undefined where the two blocks do not face each other across a gap of `bg` (`defined` needs a `pair`). Without this, the concept and `$EveryFacingPair` would not agree on every two-block input, and analyze.md states that they do.
- `facing` asks that the cells between the two blocks hold only `bg`. `$EveryFacingPair` reads "face each other across a gap of `bg`" this way. Under `$Two` the test never fires, because any other non-`bg` cell would be a third block. In the `three-blocks` witness this test is what keeps the 2 and 6 blocks from being bridged.
- Encoding the span branches: each branch gives the blocks whose span, less `inset` lines at each end, bounds the bridge (`bound`). `$Overlap` uses both blocks of the pair; `$NarrowerFace` and `$NarrowerFaceClipped` use the narrower block. `$NarrowerFaceClipped` also trims the gap cells that lie past the wider block's span. Where a pair has no `bound` (equal widths under the narrower branches), the branch is undefined.
- Hints:
    - `single-consumer` on `block`: inlined.
    - `common-subexpr` between `past` and `trimmed`: `past` became an inline relation, which also covers an off-frame cell `inset` lines out.
    - `head-repeat` on `bound`: the two blocks of the `$Overlap` pair are now stated by a disjunction, `Id = A ; Id = B`.
    - `head-zero` on `bound`: the wider block's 0-line bound under `$NarrowerFaceClipped` became its own `trimmed` clause.
    - `single-consumer` on the `clip` relation that clause replaced: the relation was removed.
    - `negated-use` finding on `!bounded`: replaced by `!bound(S, A, B, _)`.
- `derive` lists `bg` DominantColor alone. It is held as `// @derive DominantColor: variant concept`, the plausibility and verdict analyze.md gives. `store` reports nothing.
- `witness` reported that no run showed `bg=DominantColor` defined and differing from `bg=stored`. I built the witness `dominant-block`: a full-width 3 block, the commonest color, cuts the field of 0 in two. The concept bridges row 7, cols 3–6. Under derived `bg` 3, the row of 0 above and the 0 and 9 cells below are the two blocks, so that case fills rows 1–6, cols 1–8. It breaks no header scene claim at the stored assignment, only the invariant that 0 is the commonest color. I judge it `variant`, verdict `concept`.
- `record --all` rewrote the witness file's names: `concept` became `$Overlap`, `$Two` and `bg=stored`.
- Branches analyze.md gives no witness are not formed, since each fails Fit: `bg=SharedColor`, `fill=OutNewColor`, `fill=AnyOutNewColor` and `$StoredAxis`.
- Not formed items:
    - The interior-overlap span and the bg-only painting each state one model, but analyze.md shows each is equivalent to a case already present, so they fail Equivalence.
    - `inset` derived from the input has no proposer or fact that gives it, so it is no model.
    - The diagonal bridge states no single model, since `inset` has no diagonal reading.
- Determination: `bg` and `fill` are read from the repainted cells, as their input and output colors. `inset` is the bridge's margin inside the region between the facing pair, taken from the two boxes on each end across the gap. This needed the parse moved into `Parse<Key>`, shared by the program and `Determine`. The plan's DivisorRatio match for `inset` is a coincidence, because the input and output have the same size, and is not used.
- Deletions:
    - 24 of 77 deletions change nothing. Each removes a structure the pairs never instantiate: a third block, an obstructed gap, a width tie, a staggered span, or the facing test inside `narrower`. The cases and witnesses rest on these structures, so they stay.
    - The `pair.d` column is redundant on every input, since facing blocks have one separating direction. I kept it so the bridge clause names the gap along the separating axis.
    - The `a`/`b` columns of `bound`, `trimmed` and `third` are needed where a block is in two pairs, as in `three-blocks`.
- Combinations of two non-concept branches, such as `$NarrowerFace` & `$EveryFacingPair`, are cases of the solver, but the run does not witness them: no task or witness input shows any of them giving an output that a case with fewer of its non-concept branches does not give. `witness` reports no unresolved pair.
- Performance: each run finishes in about 1 s, with no issue.
- No keyword proposal. `objects`, `bbox` and `span` cover the concept.

## Unsettled
- Whether `$NarrowerFace` & `$EveryFacingPair` and the other two-branch combinations stand as separate witnessed cases: a three-block input with a staggered pair would show it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
