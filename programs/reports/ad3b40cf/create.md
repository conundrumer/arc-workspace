# ad3b40cf

## Departures
- `$OffGridUndefined` and its choice point `off-grid` are not in the solver: the branch fails Subsumption. It is defined only where no image of a mirrored cell leaves the grid, and there it gives the output of the case that drops off-grid images. No run can show it defined and differing. The witness `image-off-grid` stays, because it still separates `$FrameFlip` from the concept, and its `separates` text no longer names `$OffGridUndefined`.
- `$BackgroundCompetes` is a new branch at `competitors`, formed from the Analyze report's Not formed item "the background counted among the competing colors". It fits every pair and has a relational form. Its witnesses are `background-rarest` (foreign, concept, relaxes `one-side`) and `no-shapes` (foreign, `$BackgroundCompetes`, relaxes `two-colors`).
- `impl_choice` leaves out `$ColorBoxArea & $LineCompetes`, because that combination fails Fit at train2. The line is a 1x15 row with a box of 15 cells. The boxes of 2 and 6 hold 30 and 48 cells. So the line is the least, and the output is the input. The Analyze report gave this pair only as "the two branches' changes applied together".
- `@ignore: derive $ShapeColors & $CellCount & $PaintOver` stands under the `@derive DominantColor` line on `background`. Those derived-background cases fail Subsumption: `$BackgroundCompetes` subsumes them. A derived background is the unique most common color, so it is never the least by cell count. Leaving it out of the count therefore changes no defined output, and under `$PaintOver` nothing else reads the background.
- `witness --file` against the Analyze file prints differences on `object-box-order`, `scattered-color` and `corner-touch` for `$ColorBoxArea & background=DominantColor`. That case is a combination. The Analyze group names the model of the `background=DominantColor` branch alone, and the combination gives the `$ColorBoxArea` output, as it should. This is not an error in the solver or in the Analyze file.
- The witness file has two new witnesses, `object-box-line` and `corner-touch-line`. Without them, no run showed `$ObjectBoxArea & $Adjacency4` defined and differing from `$CellCount` under `$LineCompetes`, or `$Adjacency8` from `$Adjacency4` under `$LineCompetes`. In each Analyze witness the line ties a shape color under the box-area measures, which leaves those cases undefined.

## Judgments
- How the mirror is encoded: the line orientation is the line family (row, column or diagonal, `Axis4`) that every pair of line cells shares. This is stated through defect negation (`aligned`, `off_line`, `straight`). The reflection `F` comes from that family through `perp`/`flip_of` or `diag_flip_of`. Under `$DrawnLine`, the image of `P` is `L + F(P - L)` for a line cell `L` (`relative`, `apply`, `compose`). Every line cell gives the same image. `$FrameFlip` applies `F` to `P` in the grid frame.
- `$LineByShape` reads the line color as the one non-background color whose cells all lie on one line of some family and fill every grid cell of that line (`line_gap`, then `Unanimous`). On this reading, a single cell of a color in a grid corner counts as a full diagonal line.
- The box-area measures count the cells of the boxes with `Tally`: one item for each pair of object and box cell. So the sum of box areas has a relational form and needs no arithmetic.
- Line detection is keyed by `LineColor`. Under `$StoredLine` it reads only `params.line`, so `$BackgroundCompetes & $PaintOver & $StoredLine` never reads `background`. Without this keying, `background=stored` and `background=DominantColor` would differ under `$BackgroundCompetes` only on a grid whose most common color is the line. The lint finding `shared-read` then put `background` under the marker `$ShapeColors, $LineCompetes, $PaintBackgroundOnly, $LineByShape`.
- Witnesses built in this pass:
    - `background-rarest`: foreign. It breaks `one-side`, and under the scene the background always outnumbers both shape colors. Verdict concept.
    - `no-shapes`: foreign. It breaks `two-colors`. Verdict `$BackgroundCompetes`, because a grid with nothing to mirror would be paired with itself. `$LineCompetes` gives the same output.
    - `object-box-line` and `corner-touch-line`: ordinary. Each keeps every scene claim, and the verdict is concept. They have no `@witness` line, because they only separate cases under `$LineCompetes`.
- Analyze Not formed:
    - The per-object choice of what is mirrored (by shape or by distance) is formed as no case. No reading fits: train1 mirrors an L and a square of 6 and keeps a rectangle, a T and an L of 7, and in train0 both colors are at the same distance from the line.
    - "Originals moved" fails Fit, because every output keeps the originals.
- Hints:
    - `case section` on the `copied_color_choice` enumerator is kept with `@ignore`, because the enumerator lists every value of its field.
    - `single-consumer` on `line_cell`: the relation was inlined into its one use.
    - `long-clause`: the clause was wrapped.
- `deletions`: I removed the `impl_choice` atoms of `painted`, because `defined` already gates `out`. I kept the other "changes nothing" deletions:
    - `in(_, Col)` in `straight`, `line_flip` and `defined` keep the model undefined where no line or no single least color exists (`line-recolored`, `tie`).
    - `in(Q, _)` in `painted` drops off-grid images (`image-off-grid`).
    - The `params.background` tests carry the claims of their branches.
- Determine: `sweep` and `determination-plan` list no actions. Both parameters are covered on the examples (background by `DominantColor`, line by `SharedColor`), so the solver has no Determine comp.
- Keywords: `d4 markers color-class rank objects bbox`.
    - `d4`: the mirror is a D4 reflection applied to content.
    - `markers`: the drawn line fixes where the mirror stands.
    - `rank`: the least measure picks the color.
    - `objects` and `bbox`: these serve the box-area cases.
- Performance: the solver runs in 2 to 8 s, and `audit` runs in about 10 s.

## Open
none

## Lib
- The image of a cell under a D4 element about an anchor cell: `relative(L, P, V), apply(F, V, V2), compose(L, V2, Q)`. In this solver it is the `$DrawnLine` clause of `image`. The same shape stands in 538b439f.dl:63, 2b01abd0.dl:33, 5545f144.dl:61 and 5545f144.dl:143, 2bcee788.dl:112 (the offset part), 3e980e27.dl:54 and 3e980e27.dl:68, and 4c416de3.dl:76. Proposed as an inline box relation `apply_about(d: D4, anchor: Position, p: Position, q: Position)`: q is p's image under d, with the anchor fixed.

## Fixes elsewhere
none

## Tickets filed
- 10-94_task_ad3b40cf_create.md
