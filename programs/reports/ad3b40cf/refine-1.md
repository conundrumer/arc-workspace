# ad3b40cf

## Departures
- `$OffGridUndefined` and its choice point `off-grid` are not in the solver (create): the branch fails Subsumption. It is defined only where no image of a mirrored cell leaves the grid, and there it gives the output of the case that drops off-grid images. This pass restored it in a scratch copy as a `MirrorPlace` constructor. The `witness --every-case` run then printed "no run shows `$OffGridUndefined` defined and differing from `$DrawnLine`". The witness `image-off-grid` stays, because it separates `$FrameFlip` from the concept. `witness --file` against the Analyze file prints only "the name `$OffGridUndefined` denotes no case of the solver" for each witness. With that name taken out of a copy of the Analyze file, the run prints `witness: ok`.
- `$BackgroundCompetes` is a branch at `competitors` (create), formed from the Analyze report's Not formed item "the background counted among the competing colors": Develop has each Not formed claim formed as a branch. It fits every pair, has a relational form, and has the witnesses `background-rarest` (foreign, concept, relaxes `one-side`) and `no-shapes` (foreign, `$BackgroundCompetes`, relaxes `two-colors`).
- `impl_choice` leaves out `$ColorBoxArea & $LineCompetes` (create): the combination fails Fit at train2. The line is a 1x15 row with a box of 15 cells, and the boxes of 2 and 6 hold 30 and 48 cells. So the line is the least and the output is the input. This pass confirmed it with `relation copied_color` on train2 in a scratch copy without the exclusion: that case copies color 1.
- `@ignore: derive $ShapeColors & $CellCount & $PaintOver` under the `@derive DominantColor` line on `background` (create): those derived-background cases fail Subsumption under `$BackgroundCompetes`. A derived background is the unique most common color, so it is never the least by cell count, and under `$PaintOver` nothing else reads it. With the `@ignore` line taken out of a scratch copy, `witness --every-case` printed "no run shows `$ShapeColors & background=DominantColor` defined and differing from `$BackgroundCompetes & background=stored`" for the `$PaintOver` pair.

## Judgments
- Create's departure on the witnesses `object-box-line` and `corner-touch-line` does not hold, so this pass removed them from the witness file. Create built them so that some run showed `$ObjectBoxArea & $Adjacency4` and `$Adjacency8` defined and differing under `$LineCompetes`. Those combinations are not witnessed cases: `$LineCompetes` and the box-area branches have only `concept` verdicts. The checks now run the witnessed cases alone, and `witness` and `audit` print `ok` without the two witnesses.
- Create's departure on the `witness --file` differences for `$ColorBoxArea & background=DominantColor` no longer applies. The run against the Analyze file prints no such difference, so the item is dropped.
- How the mirror is encoded (create): the line orientation is the line family (row, column or diagonal, `Axis4`) that every pair of line cells shares. This is stated through defect negation (`aligned`, `off_line`, `straight`). The reflection `F` comes from that family through `perp`/`flip_of` or `diag_flip_of`. Under `$DrawnLine`, the image of `P` is `L + F(P - L)` for a line cell `L` (`relative`, `apply`, `compose`). `$FrameFlip` applies `F` to `P` in the grid frame.
- `$LineByShape` reads the line color as the one non-background color whose cells all lie on one line of some family and fill every grid cell of that line (create). On this reading, a single cell of a color in a grid corner counts as a full diagonal line.
- The box-area measures count the cells of the boxes with `Tally`, one item for each pair of object and box cell, so the sum of box areas needs no arithmetic (create).
- Line detection is keyed by `LineColor` (create). Under `$StoredLine` it reads only `params.line`, so `$BackgroundCompetes & $PaintOver & $StoredLine` never reads `background`, and `background` stands under the marker `$ShapeColors, $LineCompetes, $PaintBackgroundOnly, $LineByShape`.
- Witness plausibilities (create): `background-rarest` foreign, concept; `no-shapes` foreign, `$BackgroundCompetes`, because a grid with nothing to mirror would be paired with itself.
- Analyze Not formed (create): the per-object choice of what is mirrored, by shape or by distance, fails Fit, because train1 mirrors an L and a square of 6 and keeps a rectangle, a T and an L of 7, and in train0 both colors are at the same distance from the line. "Originals moved" fails Fit, because every output keeps the originals.
- Hints (create): `case section` on the `copied_color_choice` enumerator is kept with `@ignore`, because the enumerator lists every value of its field. Lint prints no hint in this pass.
- `deletions` (this pass, as in create): every "changes nothing" deletion is kept. The column removals on `line_candidate`, `aligned` and `line_gap` would merge colors that the line detection keeps apart. `in(_, Col)` in `straight`, `line_color` in `line_flip`, and the `defined` atoms keep the model undefined where no line or no single least color exists, and keep the excluded combination out of `out`. `line_gap` and the `params.background` tests carry the claims of their branches. `in(Q, _)` in `painted` drops off-grid images.
- Simplify and Prune: no code reimplements the lib, and the header and comments need no cut.
- Determine (create): `sweep` and `determination-plan` list no actions, and the solver has no Determine comp.
- Keywords (create): `d4 markers color-class rank objects bbox`.
- Performance: the run takes 1 to 7 s, and `audit` 3 to 22 s.

## Open
none

## Lib
- The image of a cell under a D4 element about an anchor cell (create): `relative(L, P, V), apply(F, V, V2), compose(L, V2, Q)`, the `$DrawnLine` clause of `image`. The same shape stands in 538b439f.dl:63, 2b01abd0.dl:33, 5545f144.dl:61 and 5545f144.dl:143, 2bcee788.dl:112 (the offset part), 3e980e27.dl:54 and 3e980e27.dl:68, and 4c416de3.dl:76. Proposed as an inline box relation `apply_about(d: D4, anchor: Position, p: Position, q: Position)`: q is p's image under d, with the anchor fixed.

## Fixes elsewhere
none

## Tickets filed
- 10-98_task_ad3b40cf_refine.md
