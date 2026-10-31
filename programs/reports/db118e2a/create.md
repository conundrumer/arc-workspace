# db118e2a

## Departures
- `$ChainFromCorner` reads a stored `chain_corner` (DIAG_TL) in place of `copy_axis`: "the first corner of `copy_axis`" names one member of the two corners of a diagonal axis. Under [Orientation](docs/handbook/principles.md#orientation), "One member", a parameter stores the chosen member.
- `$FixedAnchors` stores `copy_anchor(d, p)` with the copy corner `d` beside each anchor cell: "top-left cells" is an orientation, and an equivariant model stores it.
- `canvas_size` is stored as `canvas_size(a: Axis, n)`, one fact per axis. A `Frame2D` instance builds the canvas from it, so that `Determine` reads each axis's extent with no literal axis.
- Every placement case is undefined where a copy cell falls off its canvas (`spills`), and every case is undefined where no copy is painted (`drawn`). `analyze.md` gives the off-canvas condition for `$CenterGap`, `$FixedAnchors` and `$ChainFromCorner`. The concept and `$FitCanvas` share the clause, and on the inputs the generator produces it never fires for them.
- The frame color is read from the edge cells other than the four grid corners, so it does not depend on the background branch.
- Added `@store` branches `copy_extent=stored` (under `$FitCanvas`) and `copy_span=stored` (under `$ChainFromCorner`), because `store` printed lines to add for them. Their witness, train 2 with 7 and 0 swapped, is `variant $BgFromCorner` with `@relaxed framed-panel`.
- Added witness `chain-gap` (train 0's input, `--assign copy_gap=[[2]]`). Without it, no witness separated `$ChainFromCorner & copy_span=stored` from `$FixedAnchors`. At the stored assignment the two give the same anchors on every input, and their clauses differ.

## Judgments
- `chain-gap`: plausibility `ordinary`, verdict `concept`. Its input is a train input, and the generator pairs it with the train output. It stands at a reassigned `copy_gap`, so it has no `@witness` line: the line would be a further witness of a `@store` branch.
- Hint `case section` on `params.bg` and `bg`: dismissed with `@ignore`. `bg` is keyed by its `Background` column, so each case reads only the row of its own branch. The linter cannot see this statically.
- Hint `common-subexpr` on the two `$ChainFromCorner` anchor clauses: merged into one clause with a disjunction.
- `deletions`: every entry that changes nothing stays. `spills`/`drawn` give undefinedness that the witnesses show. `copy_extent.a` and `perp` matter for non-square pictures. `corner_rule` keeps the corner anchors to `$Corners` and `$FitCanvas`. The `diag_dir_elem`/`axis_elem` enumerators are bound enumerators, which stay.
- `fit_cell` ranges over every corner, not the corners of `copy_axis`: every corner gives the same canvas extent, and placement then follows the concept's corner rule.
- `anchor` has `@ignore: store`: a stored anchor set is the model of `$FixedAnchors`, and `store` found no witness for it.
- Develop step 3: no item under Not formed gives one model that fits, so no branch was formed from them.
- Keywords: `crop`, `bbox`, `border`, `tile-arrangement`, plus `rings` for `$ReadFrameWidth`.
- Every case passes every pair (9 witnessed cases of 28). `witness --file programs/reports/db118e2a/witnesses.json` reports ok.

## Unsettled
- The audit's relabelings check fails: "line 274: `copy_span` is not one value on every input at the case values the cases that take its `@store` branch hold; it differs on train 1". `relation` on train 1 gives the same `copy_span` at every case as `store` reports for the other inputs. Narrowing `copy_span` to the `chain_corner` corner did not clear it. A report from the check that names the relabeling it ran would settle this.
- `sweep` stopped at its 120 s timeout and was not rerun. A sweep run within the timeout would settle which values it reports.
- `chain_corner`: the train pairs admit DIAG_TL and DIAG_BR. A reader could start the chain at either end, so it is likely an open parameter that needs both values stored under an `OpenValue` column. This was left undone at the Determine budget.
- The determination plan's remaining entries: `copy_anchor` is undecided, and `chain_corner`, `copy_axis`, `copy_gap`, `corner_inset` and `frame_width` are covered by proposers but have no determination relation. Writing those relations would settle them. `frame_width`'s relation would repeat `$ReadFrameWidth`'s ring count, which would then move into `Parse`.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
