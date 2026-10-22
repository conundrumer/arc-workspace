# aee291af

## Departures
- `$OffMode` is not in the solver, and the Analyze witnesses' `$OffMode` names are gone from the witness file (create): it fails Subsumption, as the Analyze report states. Where `$OffMode` is defined, the one other pattern has a lower count than the unique commonest pattern, so it is the unique rarest pattern, and `$RarestPattern` gives it too. In this pass I restored `$OffMode` in a scratch copy and ran `witness --every-case`. No witness separates it from `$RarestPattern`, and `$MarkGroupBbox & $OffMode` is undefined on test0. The departure holds.
- New box-finding branch `$MarkGroupBbox`, from the Not formed item "Marks grouped by their own 8-connected components" (create): each of its cases fits every pair. In test0, each common box splits into a 4x4 piece and a 3x3 piece, the odd box stays whole, and so the odd box still shows the only unique pattern. Develop step 3 has the branch formed. Its witness is `split-marks`. The departure holds.
- `@derive` branches beyond the Analyze report's `mark_color=RarestColor` (create): `derive` still lists `mark_color=SharedColor` and `background=DominantColor` as fits, and Develop step 4 requires both as branches. `mark_color=VanishedColor` keeps its `@ignore: derive`. On a run over one input with no train output, it gives every color of that input, as SharedColor does, so it fails Equivalence. `$MarkBbox` and `$MarkGroupBbox` with SharedColor fail Fit on every pair and keep their `@ignore: derive` lines. The departure holds.
- The concept branches are named `$FramedSquare` (box-finding) and `$UniquePattern` (odd-selection) (create).
- The run against the Analyze file shows only that the name `$OffMode` denotes no case. No grid differs (create, confirmed in this pass).

## Judgments
- Checks: the solver passes every pair with 7 witnessed cases, lint is ok, and the audit reports witness, dropped cases, derive, store and open values all ok, both before and after Simplify.
- `store`: `extremes.low` is reported on a single line with no witness and has no `@store` line, so it is not a branch. `box_cell` varies by box and cell, so it is no case (create, rerun in this pass).
- Simplify: the square test in `candidate` read the box's extents through a scan of every input cell (`in(Q, _), crop(Q, B, Q_rel)`). It now reads them from the mark cell `P` that the clause already binds inside the box (`crop(P, B, P_rel)`). The outputs are unchanged.
- Deletions: the clauses that `deletions` reports as changing nothing (`foreign_cell`, the mark atom and the square test in `candidate`, `nested`, `spill`, `many_unique`, `rare_tie`) state the concept's box conditions and the undefinedness the Analyze report gives. The pairs never exercise them, so they stay (create, rerun in this pass). The one timed-out deletion run, of `params.frame_color(Col)` in `outline.node`, removes the frame test so that every cell is an outline node, and that is not a simplification.
- Prune: the header and comments state only the claims, branches and relations a reader needs, so no text was cut.
- `@derive SharedColor: variant derived`, `@relaxed boxes` (create): the witness is train0 with 2 and 0 swapped. A color-permuted variant task gives that input routinely. The generator pairs it with the box marked in 0, which is SharedColor's output. The stored `mark_color` finds no box there.
- `@derive DominantColor: variant derived`, `@relaxed field` (create): the witness is train0 with 1 and 0 swapped. `$MarkBbox` with the stored `background` takes the whole field as one group. DominantColor gives the odd box.
- `split-marks: ordinary concept` (create): train2 with the odd box's center mark (11,7) set to 8. The odd box's marks still reach every side of its interior, and test0 already shows a box with a mark that touches no other mark, so no scene claim breaks. `$MarkGroupBbox` outputs a 3x4 piece, and the concept and `$MarkBbox` output the whole odd box.
- `big-marks` (create): a further witness of `mark_color=SharedColor`, with no `@witness` line, judged `variant concept`, because box size and mark density are routine changes in a variant task. The stored value and SharedColor output the odd box, and RarestColor is undefined.
- `split-marks` also separates `$MarkBbox & background=DominantColor` from `$MarkGroupBbox` (create).
- Analyze's `$ComponentBbox` and `$CongruentPattern` fail Fit and have no witness, so they have no constructor (create).
- Not formed items other than the mark-group reading are not branches (create). A stored box size, selection by mark count, and output of the interior alone each fail Fit on the pairs. `derive` covers a derived `frame_color`, and it lists none that fits.
- `copies` has no `domain` row, because each box shows its own pattern, so every key already has an item (create).
- Simplify (create): a local defect-negation comparison of two box patterns is the lib's `KeyedSetCompare.equals`, the precedent in 39a8645d.
- `background` sweep (create): the train pairs also admit 8, and test0 refutes it. No reader of the concept takes the frame color as background, so it is not an open parameter. The determination plan lists no actions, so the solver has no Determine comp.

## Open
- none

## Lib
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-119_task_aee291af_refine.md
