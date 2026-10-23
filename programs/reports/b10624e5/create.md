# b10624e5

## Departures
- The Analyze branch `template_corner=stored` is the `@store value` line above `.init template`, named `template.value=stored` in the witness file. The Analyze witness `template_corner=stored` (train0 turned a half turn) is removed: it duplicates the witness `store` recorded for that branch (train0 turned a quarter turn), which separates the same two models in the same way.
- The Analyze branch `background=DominantColor` is the `@derive DominantColor` line on `bg`, named `bg=DominantColor`. Its line takes the plausibility and verdict of the witness `derive` recorded, train0 with 4 and 0 swapped: `variant derived`, `@relaxed cross`. The Analyze report gives `borderline concept` for its own witness. That witness (each lone core 11 by 11) stays as a further witness of the branch, with its id renamed to `cores-outnumber-background`, because the id `background=DominantColor` names no branch of the solver.
- `$SquareScale` is not in the solver. No input, at any assignment, shows it defined and differing from the per-axis scale: it is undefined where a core is not a square, and it gives the concept's output everywhere else. So it fails Subsumption. Its witness `rectangular-core` is removed because it then separates nothing. The Analyze report already judged the branch subsumed.
- On `cores-outnumber-background`, `$GridClip` is undefined, and the Analyze file gives a grid. With 11-by-11 cores, the bottom-left core's mirrored green block runs over the bottom-right core, so two lone figures give cells different colors. The solver's reading of `GridClip` leaves such a cell without one color, and its `@rule` line states this. The Analyze grid keeps the bottom-right core's red there, which implies a painting order that the Analyze branch text does not give.
- Branch names in the witness file take the forms the Witness file section gives: `$GridClip`, `$CoreByQuadrants`, `$FigureOnly`, `$Adjacency4` (for `FigureOnly & Adjacency4`), `bg=DominantColor`, `template.value=stored`.

## Judgments
- Develop step 4 holds these branches beyond the Analyze report, each from a line that `store` printed:
    - `@store: variant concept`, `@relaxed template-quadrant` on `mirror`. Witness: train0 turned a quarter turn. The stored direction map is for the old lone quadrants.
    - `@store divider: variant stored` and `@store tile_of: variant stored` on `quad`, both `@relaxed cross`. Witness: train0 with 1 and 0 swapped. Concept and the stored divider color find no cross and give the input. The stored cut grows the figure, as a variant task with a black cross would.
- `@ignore item: store` on `template`: storing `template.item` stores the top-left quadrant as the template, the same as storing `template.value`. So it fails Equivalence. A separate relation `figured` that `store` also printed was folded into `template.item`.
- `@ignore: derive VanishedColor` on `divider_color`: a run gives no train output, so the derivation gives every color of the input, as `SharedColor` does. It fails Equivalence. Its witness was removed because the name denotes no case.
- New witness `off-center-cross`, a 29-by-29 grid with the cross on row 13 and column 13. It separates `quad.tile_of=stored` from `quad.divider=stored` and from `divider_color=SharedColor`. Judged `borderline`, verdict `concept`: it breaks `cross`, because the cross is off center and the quadrants are unequal. No other input separates the two stored cuts: on a 27-by-27 grid they give one tile map, and on a 25-by-25 grid each finds no single template.
- New witness `moved-divider-row`: train0 with the horizontal divider on row 11. It separates `quad.divider=stored` from `divider_color=SharedColor`. Judged `borderline`, verdict `concept`: it breaks `cross` (center, equal quadrants).
- Not formed, resampling a fractional block side (from the near edge, the far edge, or at cell centers): each reading fails Relational form. Each reading places a lone cell by a fraction of a template block, s / k or a cell center scaled by t / s. That number counts nothing the task has, and no lib relation scales a count by a ratio.
- Not formed, a different scale per axis from a non-square template core: the concept already reads each axis's extents, so no reading differs from it, and no branch is formed.
- Not formed, the cross away from the grid center: the program finds the cross by its full lines wherever they lie, so no reading differs, and no branch is formed.
- The template's block side is read per axis. It is the largest side that divides the template core's extent and whose tiling, aligned to the core, has no line along the axis that holds two colors in one block. A cell's block is counted from whichever core edge it lies on or past, and a tiling aligned to the core makes both counts agree.
- The lone figure is gated on the template's block count: the model is undefined only where a template block count exists and does not divide a lone core's extent. Where no template core is found, nothing is painted and the output is the input, as the Analyze file gives on `divider_color=SharedColor` for `template.value=stored`.
- Cross parse: the solver follows the precedent of the approved solver 0bb8deee. That precedent is a `Unanimous<Line, Color>` over grid lines feeding `DividerTiles`, which keeps the full lines of a divider color. With this parse, `divider_color=SharedColor` fits.
- Hint `common-subexpr` on `lone_idx` (shared with `tmpl_idx`): kept with `@ignore`. The template's cells take a block index at every candidate side before the side is chosen, and a lone core's side follows from that choice. One relation for both would close a recursion cycle.
- `deletions`: 16 deletions change no pair. Each was judged as structure the pairs never use. Examples are the per-axis columns of `mixed` and `lone_side`, the `unscaled` gate, the quadrant clip atom, and the `FigureOnly` atoms. The column `broken.a` went away when `line_color` replaced `broken`.
- Determine: `sweep` gives one value for each parameter, and `determination-plan` lists no actions, so the solver has no `Determine` comp.
- Keywords: `decompose markers scale d4 stamp` for the concept, and `objects` for the connected piece that `$FigureOnly` reads.
- Performance: on a cold cache, a run of the 768 cases takes 30–50 s. On a warm cache it takes 2–7 s.

## Open
- none

## Lib
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-256_task_b10624e5_create.md
