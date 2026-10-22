# aee291af

## Departures
- `$OffMode` is not in the solver, and the Analyze witnesses' `$OffMode` names are gone from the witness file: it fails Subsumption, as the Analyze report states. `witness` found no input on which `$OffMode` is defined and differs from `$RarestPattern`, because where `$OffMode` is defined, the one other pattern is the unique rarest pattern. The witness `two-two-one`, which I built to separate the two, was removed with it.
- New box-finding branch `$MarkGroupBbox`, from the Not formed item "Marks grouped by their own 8-connected components": a box is the bounding box of one 8-connected group of marks, grown by one cell on each side. All of its cases fit every pair, test0 included. In test0 the common pattern splits into a 4x4 piece and a 3x3 piece, and the odd box stays whole, so the odd box is still the one unique pattern. Its witness is `split-marks` (see Judgments).
- `$MarkGroupBbox & $OffMode` failed Fit on test0, because the two pieces of a common box tie as the commonest pattern. This stopped mattering once `$OffMode` left.
- `@derive` branches beyond the Analyze report's `mark_color=RarestColor`: `derive` also found `mark_color=SharedColor` and `background=DominantColor`. I hold both. `mark_color=VanishedColor` has an `@ignore: derive`, because it fails Equivalence: on one input with no train output it gives every color of the input, as SharedColor does. Its witness was removed from the witness file. `$MarkBbox` and `$MarkGroupBbox` with SharedColor fail Fit on every pair, and each has an `@ignore: derive` line.
- The concept branches are named `$FramedSquare` (box-finding) and `$UniquePattern` (odd-selection). `record --all` rewrote the witness groups under these names.
- The run against the Analyze file shows only that the `$OffMode` name has no case. No grid differs.

## Judgments
- `@derive SharedColor: variant derived`, `@relaxed boxes`: `derive` built the witness from train0 with 2 and 0 swapped. A color-permuted variant task gives that input routinely. The generator pairs it with the box marked in 0, which is SharedColor's output. The stored `mark_color` finds no box there.
- `@derive DominantColor: variant derived`, `@relaxed field`: the witness is train0 with 1 and 0 swapped. `$MarkBbox` with the stored `background` takes the whole field as one group. DominantColor gives the odd box.
- `split-marks: ordinary concept`: train2 with the odd box's center mark (11,7) set to 8. The odd box's marks still reach every side of its interior, and test0 already shows a box with a mark that touches no other mark, so no scene claim breaks. `$MarkGroupBbox` outputs a 3x4 piece, and the concept and `$MarkBbox` output the whole odd box.
- `big-marks` (a further witness of `mark_color=SharedColor`, with no `@witness` line): three 9x9 boxes with dense marks, a few stray 8 cells, and one stray 8 cell touching a box. I judge it `variant concept`, because box size and mark density are routine changes in a variant task. The stored value and SharedColor output the odd box. RarestColor takes 8 as the mark color and is undefined. This witness resolves the `witness` finding that no run showed SharedColor defined and different from RarestColor.
- `split-marks` also separates `$MarkBbox & background=DominantColor` from `$MarkGroupBbox`, which resolves that `witness` finding.
- Analyze's `$ComponentBbox` and `$CongruentPattern` fail Fit and have no witness, so they have no constructor.
- Not formed items other than the mark-group reading are not branches. A stored box size, selection by mark count, and output of the interior alone each fail Fit on the pairs. `derive` already covers a derived `frame_color`, and it lists none that fits.
- Deletions: the clauses that `deletions` reports as changing nothing (`foreign_cell`, the mark atom and the square test in `candidate`, `nested`, `spill`, `many_unique`, `rare_tie`) state the concept's box conditions and the undefinedness the Analyze report gives. The pairs never exercise them, so they stay. `copies.domain` was removed, because each box shows its own pattern, so every key already has an item.
- Simplify: I replaced a local defect-negation comparison of two box patterns with the lib's `KeyedSetCompare.equals`, which is the precedent in 39a8645d.
- `background` sweep: the train pairs also admit 8, and test0 refutes it. No reader of the concept takes the frame color as background, so it is not an open parameter. The determination plan lists no actions, so the solver has no Determine comp.
- `store`: `extremes.low` has no witness, and `box_cell` is no case, so neither is a branch.

## Open
- none

## Lib
- none

## Fixes elsewhere
- none

## Tickets filed
- none
