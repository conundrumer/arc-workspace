# ac605cbb

## Departures
- (create) The parameter `stamp` is stored as two relations, `stamp_line` and `stamp_end`, each a `GRID_STAMP` picture per seed color with the `@` on the seed, in place of a list of unit steps: a step list needs an accumulated offset per step, which needs recursion, and 0ca9ddb6 `template` is the precedent for a per-color stamp stored as offsets. The rules read line cells and the end cell apart (`cross-cell` reads line cells, `stamp-path` paints the two in different colors), so each part has its own relation. Holds: every stamp a task gives is a path, and each path has one offset picture that gives the same output.
- (create) `$RayAlongHorizontalLine` reads the step direction of a stamp at a line cell from the offsets: the stamp runs toward D through P when the cell behind P toward the seed's side is the seed or a line cell of that stamp (`runs`). On every path whose cells touch only their neighbors along the path, this is the step that reaches P, as `probe.py` reads it. Holds.
- (create) The Analyze report's `ray_vertical` is `ray_fixed_dir` (`DIR_B`): under a quarter turn the axis it fixes is no longer vertical. The axis the ray follows a stamp along is derived through `perp`. Holds.
- (create) The concept branches take the constructors `RayPaintsInk`, `RayStoredDir`, `EndLineClash`, `StampOverSeed` and `ClipStampToGrid`. The witness file's groups use these names after `record --all`. Holds: the Analyze report names each concept branch `concept`, and a constructor needs a name of its own.
- (create) The witness file holds two witnesses beside the Analyze file's five. `end-on-horizontal-line` separates `$RayAlongHorizontalLine & $CrossAtEndCell` from `$RayAlongHorizontalLine`, which `end-on-line` leaves both undefined. `end-on-line-same-color` (`assign` `line_color` = 3) shows `$RayAlongHorizontalLine` defined and differing from `$RayAlongHorizontalLine & $CrossAtEndCell`. Holds: `witness` and the audit pass with both.
- (create) On `end-on-line`, `$RayAlongHorizontalLine & $CrossAtEndCell` is undefined: the crossing at (4,2) lies on the 3 line, and no stamp line runs horizontally through it. The Analyze file names no combination there. Holds: the run against the Analyze file passes.

## Judgments
- (refine-1) Reconcile: no overrides, no open items, and no `## Fixes elsewhere` item on this task in another task's report. Each departure of create.md holds. The solver passes every pair with 10 witnessed cases, lint is clean, the audit passes, and the run against `work/task/ac605cbb/witnesses.json` passes. The audit reports no parameter fact whose removal changes no output.
- (refine-1) Determine: the sweep finds `line_color`, `cross_color`, `cross_dir` and `ray_fixed_dir` unique. The extra `stamp_line` and `stamp_end` rows it reports were judged in create.md. The plan lists no actions.
- (refine-1) Simplify: `deletions` gives no new removal. The 33 removals that change nothing are the structure create.md judged, and the determination's `ground` test, which states that a seed is a cell off the ground color. The bound enumerator `dir_elem(D)` in `runs` stays, as the tool says. No code changed.
- (refine-1) Prune: the header and comments serve a reader of the solver. No text changed.
- (create) The cases are all 96 combinations of the five choice points: each branch fits every pair, and no two branches' changes conflict on a pair. The run holds 10 witnessed cases.
- (create) Not formed: no item forms a branch. A `stamp` derivation fails Fit (no relation of color to path holds across the keys). `derive` finds no built-in derivation of `line_color` or `cross_color`. `background` is read by no rule. An overlap of two stamps along one line falls under `end-meets-line` and `stamp-meets-seed`. A seed color with no key separates no two models.
- (create) `derive` reports no derivation that fits, and `store` reports no value that is the same on every input, so the solver has no `@derive` or `@store` line.
- (create) `end-on-horizontal-line`: plausibility `borderline`, verdict `$EndOverLine`. It breaks `stamps-meet-at-lines` as `end-on-line` does, with the end of the 3 stamp on the line of the 2 stamp, and the Analyze report's verdict on `end-on-line` applies to it.
- (create) `end-on-line-same-color`: plausibility `borderline`, verdict `concept`. It breaks `stamps-meet-at-lines` and reassigns `line_color` to a seed color. There, the end color and the line color are one color, and the concept case, `$EndOverLine` and `$LineOverEnd` all give it.
- (create) `witness` reported that no run showed `$RayAlongHorizontalLine` defined and differing from `$RayAlongHorizontalLine & $CrossAtEndCell`. With `line_color` 3, an end cell of the 3 stamp on a line cell of another stamp paints one color under `$EndLineClash`. `$CrossAtEndCell` makes that cell a crossing. `end-on-line-same-color` shows this, and the case meets Subsumption.
- (create) Lint findings: the enumerators were renamed to the names lint gives. `runs` moved under the `$RayAlongHorizontalLine` marker. The `live` and `out` clauses moved above the case markers, which cleared the case-section hints.
- (create) Sweep: the extra `stamp_line` and `stamp_end` rows that give every train output belong to colors that no input holds, or are rows that no pair reads. No concept reader takes them, so no open values are stored.
- (create) Determine finds the seeds as the cells off the inputs' commonest color. It reads a stamp's end as the changed cell in the seed's color. It reads a line offset as one that every seed of that color, in every example with an output, marks with a changed cell in another color.
- (create) Deletions: `axis_of(D, A)` in the `$RayAlongHorizontalLine` `ray_dir` clause was redundant with `diag_dirs`, and was removed. Every other deletion that changes nothing removes structure that the pairs never instantiate: clipping, a ray over ink, end and line overlaps, seed cover, and an undefined ray direction. The witnesses instantiate each of them. Two others are the `neighbor` test and the `Q = S` disjunct in `runs`, which a stamp with a turn after a straight run needs.

## Open
- none

## Lib
- (create) At least two distinct members of a cell: `two_lines(P, G) :- line_cell(P, S1, G), line_cell(P, S2, G), S1 != S2.` The grep found the same shape in 71e489b6 `continued`, 7f4411dc `support_kept` and 8cb8642d (`nearest.low(P, D1, _), nearest.low(P, D2, _), D1 != D2`).

## Fixes elsewhere
- none

## Tickets filed
- none
