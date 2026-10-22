# b10624e5

## Departures
- (create.md) The Analyze branch `template_corner=stored` is the `@store value` line above `.init template`, named `template.value=stored` in the witness file. The Analyze witness `template_corner=stored` (train0 turned a half turn) is removed: it duplicates the witness `store` recorded for that branch (train0 turned a quarter turn), which separates the same two models in the same way. Holds: Witness step, "remove each witness of a `@derive` or `@store` branch that duplicates the one `derive` or `store` records for that branch".
- (create.md) The Analyze branch `background=DominantColor` is the `@derive DominantColor` line on `bg`, named `bg=DominantColor`. Its line takes the plausibility and verdict of the witness `derive` recorded, train0 with 4 and 0 swapped: `variant derived`, `@relaxed cross`. The Analyze report gives `borderline concept` for its own witness. That witness (each lone core 11 by 11) stays as a further witness of the branch, renamed `cores-outnumber-background`, because the id `background=DominantColor` names no branch of the solver. Holds.
- (create.md) `$SquareScale` is not in the solver: it fails Subsumption. It is undefined where a core is not a square, and gives the concept's output everywhere else. Its witness `rectangular-core` is removed because it then separates nothing. This pass checked the drop as Departures asks: a scratch copy of the solver with a `ScaleAxes` point (`PerAxis` | `SquareScale`, undefined where a core box has unequal extents) restored the case, and `witness <copy> --every-case --dropped-from programs/solvers/b10624e5.dl` printed "dropped case `$SquareScale` fails Subsumption against `concept`".
- (create.md) On `cores-outnumber-background`, `$GridClip` is undefined, and the Analyze file gives a grid. With 11-by-11 cores, the bottom-left and bottom-right figures each paint the other's quadrant, and they give some cells different colors. The Analyze grid takes the bottom-right figure's color at every such cell, in both bottom quadrants: green over the bottom-left core, and the bottom-right core's red over the bottom-left figure's green. So the Analyze grid paints one lone figure after the other. The Analyze branch text gives no such order, and an order over quadrants is an orientation the concept does not distinguish. The solver's `GridClip` is undefined where two figures disagree, and its `@rule paint` line says so. This pass confirmed this is the only difference that a run against a renamed copy of the Analyze file prints.
- (create.md) Branch names in the witness file take the forms the Witness file section gives: `$GridClip`, `$CoreByQuadrants`, `$FigureOnly`, `$Adjacency4` (for `FigureOnly & Adjacency4`), `bg=DominantColor`, `template.value=stored`.

## Judgments
- The header's `@scene scalable` is removed. The Style rule for `@scene` keeps a scene line only where `@claim` or `@relaxed` uses it, where a `@rule` or `@approximated:` line depends on its text, or where a branch replaces it. None of these is true for `scalable`: the `scale` rule states its own undefined condition.
- The gloss above `.init template` is removed. It repeated the `template` rule, which the instance's `@claim template` already points to.
- Reconcile checks: the run passes every pair for the 15 witnessed cases, lint is ok, and each audit section (witness, dropped cases, derive, store, open values) is ok. `sweep` gives one value for each parameter, and `determination-plan` lists no actions.
- `deletions`: 16 deletions change no pair. They are the same 16 that create.md judged, and the judgment stands: each removes structure that the general model needs, but the pairs do not use it. Examples are the axis columns of `mixed` and `lone_side`, the `unscaled` gate, the quadrant clip atom, `params.divider_color` in `quad.divider`, and the `FigureOnly` atoms.
- Simplify: no change. The two `figure` clauses of `$FigureOnly` read different lib comps (`Components8`, `Components`). The `step` input of `Components` takes no key, so one instance cannot hold both adjacencies.
- (create.md) Develop step 4 holds these branches beyond the Analyze report, each from a line that `store` printed:
    - `@store: variant concept`, `@relaxed template-quadrant` on `mirror`. Witness: train0 turned a quarter turn. The stored direction map is for the old lone quadrants.
    - `@store divider: variant stored` and `@store tile_of: variant stored` on `quad`, both `@relaxed cross`. Witness: train0 with 1 and 0 swapped. The concept and the stored divider color find no cross and give the input. The stored cut grows the figure, as a variant task with a black cross would.
- (create.md) `@ignore item: store` on `template`: storing `template.item` stores the top-left quadrant as the template, the same as storing `template.value`. So it fails Equivalence.
- (create.md) `@ignore: derive VanishedColor` on `divider_color`: a run gives no train output, so the derivation gives every color of the input, as `SharedColor` does. It fails Equivalence.
- (create.md) Witness `off-center-cross`, a 29-by-29 grid with the cross on row 13 and column 13. It separates `quad.tile_of=stored` from `quad.divider=stored` and from `divider_color=SharedColor`. `borderline`, verdict `concept`: it breaks `cross`.
- (create.md) Witness `moved-divider-row`: train0 with the horizontal divider on row 11. It separates `quad.divider=stored` from `divider_color=SharedColor`. `borderline`, verdict `concept`: it breaks `cross`.
- (create.md) Not formed, resampling a fractional block side (from the near edge, the far edge, or at cell centers): each reading fails Relational form. Each reading places a lone cell by a fraction of a template block, s / k or a cell center scaled by t / s. That number counts nothing the task has, and no lib relation scales a count by a ratio.
- (create.md) Not formed, a different scale per axis from a non-square template core, and the cross away from the grid center: the program already reads each axis's extents, and finds the cross by its full lines wherever they lie. No reading differs from the concept, so no branch is formed.
- (create.md) The template's block side is read per axis. It is the largest side that divides the template core's extent and on whose lattice, aligned to the core, no line along the axis holds two colors in one block.
- (create.md) The lone figure is gated on the template's block count: the model is undefined only where a template block count exists and does not divide a lone core's extent. Where no template core is found, nothing is painted and the output is the input.
- (create.md) Cross parse: the solver follows the precedent of the approved solver 0bb8deee, a `Unanimous<Line, Color>` over grid lines that feeds `DividerTiles`.
- (create.md) Hint `common-subexpr` on `lone_idx` (shared with `tmpl_idx`): kept with `@ignore`. One relation for both would close a recursion cycle.
- (create.md) Keywords: `decompose markers scale d4 stamp` for the concept, and `objects` for the connected piece that `$FigureOnly` reads.
- (create.md) Performance: on a cold cache, a run of the cases takes 30–50 s. On a warm cache it takes 2–7 s.

## Open
- none

## Lib
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-259_task_b10624e5_refine.md
