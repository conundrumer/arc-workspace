# b0039139

## Departures
- `$ColorMap` has no constructor and no clauses, and the witness `stray-color-in-shape` is gone from `programs/witnesses/b0039139.wit.json`: the case fails Subsumption, as the Analyze report gives. Wherever it is defined it gives the concept's output, and no input shows it defined and differing. Once it was removed, `stray-color-in-shape` separated nothing. The Analyze file still names `$ColorMap` in the groups of every witness.
- `$GapFromShapeMargin` is a new Gap branch, formed from the Analyze report's Not formed item "a gap read from the shape's margin in its panel". In it, the gap is the shape box's distance from the sides of its panel, and it is undefined where the four distances differ. Every pair has distance 1 on all four sides, so it fits every pair. It has a relational form (`relative` of the two boxes, `dist` per side, `Unanimous`). Its witness is `shape-margin-two`.
- `background` has a `@derive DominantColor` branch, which `derive` found to fit. Its witness `background=DominantColor` repaints the background 5. With the stored 0, `$GapFromMarkSpacing` finds no run and is undefined, and the derived color gives the concept's output.
- New witnesses: `shape-margin-two` for `$GapFromShapeMargin`, and `shape-panel-right` and `field-panel-dominant` for pairs of cases that no run separated. Judgments gives the reason for each.

## Judgments
- Panels: `DividerTiles` over the full lines of `divider_color`. The panels are ordered toward each end of the panel axis by an `Order` over tile positions, using `nearer`. The roles come from `first`, `next` and `last` rather than from tile indices. `part_idx` counts divider lines, so with thick dividers the indices are not dense, and with `Order` the concept still gives its output on `thick-dividers`, as the Analyze file gives.
- `$MarkCells`: the mark cells set the extent of an `AxisFrame`, and `divide_by_size` by `mark_size` with gap 0 cuts that frame. The outer frame's extent is the copy count. On a cell count that is not a multiple of `mark_size`, nothing decomposes, and the case is undefined.
- `$GapFromMarkSpacing`: a `Ray` is cast from each mark cell along the four cardinals, and every cell off `background` blocks it. A cast counts when its `stop` cell is a mark of another component under the case's mark reading (4-connected for `$Marks4` and `$MarkCells`, 8-connected for `$Marks8`). The gap is the least background count of such a cast.
- `$GapFromDivider`: each divider band (`Components` over divider-line cells) is counted in lines, and the counts must agree (`Unanimous`).
- The output: `concat_slab` places each copy index and each box-relative cell, with the case's gap. A `Frame2D` over that extent gives the frame, and every frame cell that is not a shape copy takes the field color.
- `shape-margin-two`, `variant concept`: the shape sits two cells in from every side, and that breaks no scene claim. Panel sizes vary across the pairs, and a variant task could routinely give a larger margin. The verdict follows the Analyze report's reading that the gap is a fixed one line.
- `shape-panel-right`, `variant concept`: the left-right mirror of train3. Without it, no run showed `$RolesByContent` defined and differing from `$PanelOrder` under `$PanelInset` and under `$GapFromShapeMargin`. On it, `$PanelOrder` reads from the top-left, takes the solid left panel as the shape panel, finds no mark in the next panel, and is undefined. It stands at the stored assignment, because no `start_corner` makes `$PanelOrder` defined and different there.
- `background=DominantColor`, `variant derived`, `@relaxed shape-panel` and `count-panel`: a recolored background is a color-permutation variant. It breaks the scene claims' "background 0".
- `field-panel-dominant`, `ordinary concept`, a second witness of the `background` point, with no `@witness` line: a 10-wide field panel makes 8 the commonest color, and the derived background then finds no background run between the marks. Panel widths vary across the pairs, as in test1, and this breaks no scene claim. Without it, no run showed `background=stored` defined and differing.
- Hints: the `single-consumer` hint on `count_panel` was cleared by inlining. The `common-subexpr` hint in Determine was cleared by `line_cell`. The `case section` hint on `copies` is kept with `@ignore`: the clause under `// --- $Marks4, $Marks8 ---` feeds `copies` only `$Marks4` and `$Marks8` keys (ticket 10-139). The `choice-tag` finding on `mark` was cleared with one clause that excludes `$Marks8()`.
- Markers: `marks4` stands under `$Marks4, $MarkCells & $GapFromMarkSpacing`, because `$MarkCells` reads 4-connected marks only for the mark-spacing gap.
- Deletions: `mark($Marks8(), ...)` and the `facing.stop` atom change nothing on the pairs, because the pairs never instantiate them: no marks touch at a corner, and every counted run ends on a mark. Both are kept. The `ex_out` atoms in `lacks` and `margin` restrict the determination to train examples, as [Determination](docs/handbook/solver-file.md#determination) gives, and are kept.
- Determination: the plan was over the enumeration limit. The Determine comp derives `divider_color`, the color whose every cell lies on a one-colored line of that color in every train input. Color 0 also forms full lines, so "a one-colored line" alone did not determine it. It also derives `gap_width`, from the runs of output lines all in the field color, and `margin`, from the shape's distance from its panel's sides under `$RolesByContent`. The runner covers the rest.
- Keywords: `decompose tile-arrangement crop bbox objects count mapping`. `mapping` is for the panel colors that the shape color and the field take.
- `src/` was grepped once, for the category string to write in `@ignore`. The hint text already prints it, so the grep was not needed.

## Open
- none

## Lib
- Full lines of a color, by defect negation: `broken(Ky, A, L) :- grid(Ky, P, Col), !params.divider_color(Col), axis_elem(A), split(P, A, L, _).` and `divider(Ky, A, L) :- grid(Ky, P, _), axis_elem(A), split(P, A, L, _), !broken(Ky, A, L).` The same shape is at `programs/solvers/5daaa586.dl:40`, `7e576d6e.dl:37`, `97239e3d.dl:41`, `9ddd00f0.dl:106` and `a32d8b75.dl:171`, each a line all of whose cells pass a test. An operation could take a cell set and a per-cell test set, and give the lines on each axis whose cells all pass.

## Fixes elsewhere
- none

## Tickets filed
- 10-139_task_b0039139_create.md
- 10-140_task_b0039139_create.md
