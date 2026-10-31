# fd02da9e

## Departures
- The `face-part` rule keeps the concept file's corner-relative text. analyze.md's restatement ("draw one fixed 8×8 smiley-face picture") is not used: the analysis keeps the corner-relative placement as the concept branch of `placement`, and the whole-face placements are its branches `$CenterPlacement` and `$AnchorPlacement`.
- The witness file renames `background=DominantColor` to `bg=DominantColor`, in the witness id and in the groups. The parameter's name is `bg`, and that is the `@derive` line's name.
- The `assign` of `corner_stamp` in `winking-eye` uses Offsets from the corner cell, such as TL (1,1) → `[1, -1, 1, -1]`. The `assign` of `face` in `nose-cell` uses Positions in the 8×8 frame. witnesses.json has `[k1, k2]` pairs, and the solver's columns take a Box. Run against `--file witnesses.json`, the solver reports only these name and assign forms. On the rewritten file every branch's output is the output witnesses.json gives it.
- New branch `$NearestCorner` (choice point `MarkerSite`), from the Not formed item "any non-background cell acting as the marker of its nearest corner". That item states one model, and the model fits every pair. Its witness is `stray-cell` (`borderline`, `$KeepStrayCells`). On that witness, `$NearestCorner` paints the bottom-right stroke in the stray color.
- Every placement is undefined when a marked corner's stamp cell lands outside the frame. The concept file says nothing about small grids, and analyze.md gives this condition only for `$CenterPlacement` and `$AnchorPlacement`. The concept case reaches it only on grids smaller than 4×4.

## Judgments
- `corner_stamp` stores Offsets from the corner cell with `GRID_STAMP`. A marker sits on its corner cell, so an offset from that cell is a cell's distances from the corner's two edges. The determination reads the stamp straight from the train pairs with `relative`.
- `$QuadrantPartition` places a face cell with `crop` and `corner_anchor`, at the same distances from corner D's edges of the face box. The `stamp` column therefore holds an Offset under `$CornerTable` and a Position of the face frame under `$QuadrantPartition`. `apply` mirrors both correctly for `$MirroredHalves`.
- `$CenterPlacement` and `$AnchorPlacement` need the face's extent. The solver stores it as `face_reach` (7), the diagonal steps between opposite face corners. analyze.md lists only `corner_stamp` and `background` for these branches, but the stamps alone do not fix the extent of the face.
- The face box is a `Bbox` keyed by placement. Under the concept, its cells are all the grid's cells, so the box is the whole grid. This form replaces a `ZERO` head, which the `head-zero` hint flagged.
- `store` printed the face box cells for `$CenterPlacement` and `$AnchorPlacement` and no witness for them. They take `// @ignore cell: store`.
- `derive` reported only `bg=DominantColor`. The `@derive` line takes analyze.md's `variant` and `derived`, with `@relaxed background-field`.
- `anchor_corner` (TL) and `mirror_source` (DIR_L) are not open parameters. The pairs admit every corner and DIR_R, but analyze.md's branches fix TL and the left corners, and analyze.md lists no open parameters.
- `bg` has no determination relation. The plan reports it covered by DominantColor, which reads the same fact that `background-field` reads.
- Deletions: every no-change deletion is structure that the 8×8 pairs never use: the undefinedness gate `unplaced`, the centering tests of `$CenterPlacement`, the off-frame test `in(Q, _)`, `marker.p` (read by `$KeepStrayCells`), and the `!params.bg` test on corner markers. All of them stay.
- Lint hints `case section` (shared clauses under an `$AnchorPlacement` marker) and `common-subexpr` (the two `$AnchorPlacement` face cells): the shared block was moved above the markers, and the two clauses were merged into one disjunction.

## Unsettled
- `$KeepStrayCells & $NearestCorner` is probably equivalent to `$NearestCorner`, because every cell of a color other than bg is a marker under `$NearestCorner`. It is not a witnessed case, so `witness` does not test it. A witness run that includes it would settle this.

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/fd02da9e/witnesses.json`, the `assign` values of `corner_stamp` and `face`: they give `[k1, k2]` pairs, which match no solver column type.

## Tickets filed
- none
