# d968ffd4

## Departures
- `$AxisByShape` stays as a case, though `analyze.md` says the concept subsumes it and it fails Subsumption: the witness `three-blocks` shows it defined where the concept is undefined. In that input a third block shares columns with one block, and that block shares rows with the second. The concept then finds two facing axes, fills along both, and is undefined where the fills cross. `$AxisByShape` takes only the longer axis and gives a grid. Subsumption ranges over every input ([Equivalence and subsumption](docs/handbook/principles.md#equivalence-and-subsumption)), so the Witness rule keeps the case. The witness is `foreign`, so the case stays only on a nonsense input. A later pass may want the corpus's view on whether subsumption should be tested against inputs that break the scene claims this badly.
- With `$AxisByShape` kept, the case `$AxisByShape & $FrameMidline` is witnessed too: on `three-blocks` the frame is 7 wide, so its center column 3 keeps the background, while `$AxisByShape` fills it. The solver therefore runs 4 witnessed cases.
- Witness file: added `three-blocks` (above). `record --all` changed no groups of the two witnesses copied from `witnesses.json`. `witness --file programs/reports/d968ffd4/witnesses.json` reports no difference.

## Judgments
- Constructors: `analyze.md` gives a witness only for `$AxisByShape` and `$FrameMidline`. The concept branches take my own names, `AxisByEnds` and `GapMidpoint`. `$StoredAxis`, `$BlockSpan`, `$FillEndMargin` and `$MiddleTaken` fail Fit and have no witness, so they get no constructor.
- Empty parameterization (`.comp Params {}`): the background, the block colors and the facing axis vary from pair to pair, so the program derives all of them. The background is the color of the frame's corners. This rests on `facing-ends` and `side-margin`, which put every block at least 1 cell from each edge. `analyze.md` (Not formed) says every reading of the background gives the same color under the scene claims.
- Blocks are told apart by color (`two-blocks` gives them two different colors), so no Components instance is needed.
- Facing axis (`AxisByEnds`): the axis along which cells of the two blocks share a line. `toward` gives each block's direction toward the other. The gap is the set of lines, taken as axis-only positions, that lie more than 0 lines past both blocks' facing lines. `split-gap` compares the two line counts with `K1 < K2`, and `odd-middle` is the gap line where they are equal. This is the relational form `analyze.md` states, so no `@approximated:` line is needed.
- `three-blocks` witness: plausibility `foreign`, because three blocks break `two-blocks` and the generator never draws a third block. Verdict `any`: no reading of the concept fixes an output for this input, and only the `$AxisByShape` cases are defined on it.
- Develop step 3: no Not formed item adds a case. Nearest block over the whole frame, fixed growth and far-block color all fail Fit. The background reading and the "middle keeps its input color" reading do not change the model.
- `derive`: no built-in derivation fits. `store`: no findings. Determination: the sweep reports nothing, the plan lists no actions, and there is no Determine comp.
- Hints: `common-subexpr` on `toward`, `ahead` and on the `out` clauses. All three were resolved by restructuring: `toward` was made independent of FaceAxis, `face` now carries the direction, and the `out` clauses were merged into one disjunction. No `@ignore` was used.
- Deletions: removed the unused column `gap.c2`. Kept the rest:
    - The `axis_of` atoms in `toward` and `face` state that the direction is on the axis.
    - `!middle` and the `middle` rules encode `odd-middle`, which says the middle line keeps the background, not its input color. The two readings differ on an input with non-background cells in the gap.
    - The `toward`/`axis_of` atoms in the `$AxisByShape` facing clause give that branch's undefinedness, which the witness `short-axis-facing` shows.
- Keywords: `objects lines span`.

## Unsettled
- `$AxisByShape` and `$AxisByShape & $FrameMidline` meet Subsumption only through a `foreign` witness (see Departures). A ruling on whether a witness this far outside the scene claims should count for Subsumption would settle whether they stay.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
