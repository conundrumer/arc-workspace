# e9614598

## Departures
- `$MarkColor`, `$BoxCenter` and `$MarksOnTop` are not cases, and neither is any other combination of `$OnePair` with a non-concept branch at `marks`, `center` or `overlap`. `impl_choice` keeps `$OnePair` only beside the concept branch at those points: `witness` found no run where such a case is defined and differs from the same case with `$EveryPair`, and no input can show that. Where exactly two marks give a center, `$EveryPair` draws the same one plus. Those cases fail Subsumption. Each branch is now represented by its case with `$EveryPair`, which gives the branch's output on its witness. `witness --file witnesses.json` therefore does not check the groups that name `$MarkColor`, `$BoxCenter`, `$MarksOnTop` and `background=DominantColor`.
- `background=DominantColor` at the concept base is no case: `// @ignore: derive concept`. Where it is defined, the input holds exactly two cells off its commonest color. On such an input, `$MarkColor & $EveryPair & mark_color=RarestColor` takes the same two cells as marks and gives the same output, so the concept base with the derived background fails Subsumption. The `@derive DominantColor` line stays for the cases that take `$EveryPair`.
- `$StoredFootprint` is not formed: its encoding needs a workaround, and a non-concept branch takes none.
- Added `@derive RarestColor: variant derived` (`@relaxed two-marks`) on `mark_color`. `derive` reported it, and Analyze lists it under Not formed. Its witness `mark_color=RarestColor` is train0 with the marks recolored to 2.
- Added the witness `background-majority`, the 1 × 3 grid `1 0 1`. It separates the stored background from `background=DominantColor`: the stored background 0 draws `3 3 3`, and the derived background 1 finds one mark.
- The `mark-color` witness line stands under `$MarkColor` alone. Analyze's witness also separates `$EveryPair`, but `$EveryPair` has its own witness.

## Judgments
- `background-majority`: plausibility `foreign`, verdict `concept`. No input from the generator has marks that outnumber the background; the witness exists only to separate the two cases.
- `@derive RarestColor`: plausibility `variant`, verdict `derived`. A color permutation of the marks is a variant task. Both the concept and the derived branch draw the plus there, and stored `$MarkColor` is undefined.
- Center: `relative(M1, P, V), relative(P, M2, V)` states "P is as far from M1 as M2 is from P". `$Midpoint` adds `same_line` on an `Axis`, and `$BoxCenter` omits it. No arithmetic is needed, so `midpoint` has a relational form.
- Plus: a `Ray<Choice>` from each drawn center, limited to `K <= arm_length`. The grid edge clips it, as Not formed gives.
- Determine: `plus_color` is the color of output cells that differ from the input. `background` is the color that leaves exactly two other cells in every input, stated by defect negation. `mark_color` is the input color other than the background. `arm_length` is the farthest drawn cell along a cardinal ray from that center, read through `Extremes`. The plan's first run asked for relations because each value was covered only by proposers (`DivisorRatio`, `DominantColor`, `RarestColor`, `AnyOutNewColor`) that read facts other than the concept's. The second run gave no actions.
- Hints: the case-section hints fired on clauses that fed relations every case read. I fixed them by keying `Ray` on `Choice` and by moving the shared clauses above the markers. The argmax hint on a self-join was fixed with `Extremes`. The single-consumer hint on `arm_cell` was fixed by inlining.
- Deletions: these deletions changed no pair. `axis_elem`/`same_line`, `crowded` and `!crowded`, `drawn_center` in `defined`, `!parse.mark` and `!two_others` are tested by witnesses or by inputs that the pairs do not contain, and they stay. `ex_out(E, _, _)` in `arms.mark` in Determine only restricts to train examples. It is redundant, but I did not remove it, because `deletions` took 66 s and runs once after the last edit.

## Unsettled
- The joint cases that `impl_choice` keeps but no witness shows: these are subsumed in the same way as the cases that left. Only witnessed cases are checked, so they stay unrun.
- The redundant atom `ex_out(E, _, _)` in Determine's `arms.mark`: removing it and running `deletions` again would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
