# f3e14006

## Departures
- The concept case starts the hole lines along `bar_axis` at the bar line (constructor `$AnchorAcrossBarLine`, now the concept branch). Its `lattice` rule says so. The stored-edge reading is the non-concept branch `$AnchorAcrossSide`, and it reads `across_start` (DIR_T). The `anchor-across-bar-line` witness is a witness of a branch, stands at the stored assignment, and has no reassignment and no approximation, yet `analyze.md` gives it verdict `$AnchorAcrossBarLine` at `ordinary`. The Witness operation says to fix the concept case in that case. The verdict is now `concept`. Against `witnesses.json`, the run prints one difference on that witness: the group that names `concept` gives the top-anchored grid, and the solver's concept gives the bar-line grid. That difference comes from this fix.
- `anchor_corner` (DIAG_TL) is now two `Dir` parameters, `along_start` (DIR_L) under `$AnchorAlongSide` and `across_start` (DIR_T) under `$AnchorAcrossSide`: after the fix, each case reads at most one side of the corner, and a DiagDir that one case reads on one axis alone leaves its other side unread.
- The concept branch along `bar_axis` is the constructor `$AnchorAlongSide`. The witness file names it `concept` and `$AnchorAlongSide` (from `record --all`).
- The background derivation branch is `background=DominantColor`, with `@derive DominantColor: variant derived` and `@relaxed two-crossing-lines`, as `analyze.md` gives it. Its other branch is named `background=stored` in the witness file.
- When the input has no rectangle, the solver gives no output, so the concept case is undefined on the `background=DominantColor` witness. This matches `witnesses.json`. The background clause of `out` reads `rect.box`, and without it the concept gave an all-0 grid there.

## Judgments
- Line parse: a line cell is an ink cell that shares a line of family `a` with another ink cell. The crossing is the cell on both lines. A line's base color is the `Mode` of its cells off the crossing, and its marks are its other cells off the crossing. This holds on test0, where the bar row ends in a 0 cell.
- Rectangle: the `Bbox` of the bar marks and of the cells where a bar mark's column meets a cross mark's row. This gives "from the bar line to the farther cross mark" with no comparison of distances. The clause is symmetric in the two axes, so it reads no `bar_axis` (`deletions` showed that atom changed nothing).
- Parity: `stride(K, period, 0, _, 0)` on the distance to the anchor edge in the rectangle's own frame, with `period(2)` in Params, as in the corpus precedent (d492a647, 834ec97d).
- `$AnchorAlongNearCross`: the crossing is placed in the rectangle's frame with `relative`, and an edge is an anchor where the crossing's distance to it is `<=` its distance to the opposite edge. This comparison of two distances is the nearer-mark test, and lint accepts it.
- Hint `common-subexpr` (even_across and even_along shared their parity body): resolved by factoring the body into `even(p, d)`.
- `deletions`: I removed `ink.col` and `params.bar_axis` in `rect.cell`. I kept the other atoms for these reasons:
    - `params.bar_axis` in `anchor_across($AnchorAcrossBarLine)`: without it, the cross marks can test the rectangle's side edges.
    - `params.bar_axis` and `perp` in `in_cross_span`: these state the claim, and they are redundant only under `cross-marks-one-side`.
    - `rect.box` in the background clause of `out`: the `background=DominantColor` witness needs it.
    - The determination atoms: they are the universal over the train examples.
- Determine: `background` is determined as the commonest color of every train input, through `Mode<Example, …>` and a defect relation. The plan lists `bar_axis`, `across_start` and `along_start` as pairs-exact over their enumerable domains, and `period` as narrowed by TileCount. No proposer derives these exactly, so they have no determination relation.
- Keywords: lines, markers, span, wallpaper, parity, cross.
- Witnessed cases: 4 of 4. The case that takes both `$AnchorAcrossSide` and `$AnchorAlongNearCross` takes two rejected branches, so it is not witnessed.

## Unsettled
- I ran `deletions` before the last edits: the removals above and a reworded header comment. I did not run it again, so the final file has no `deletions` run. Running it once on the final file would settle this.

## Concept faults
- none

## Fixes elsewhere
- programs/reports/f3e14006/concept.md, rule `lattice`: across `bar_axis`, the hole lines start at the bar line, not at the side of `anchor_corner`. The analyze.md line "Against the concept" already reports this.

## Tickets filed
- none
