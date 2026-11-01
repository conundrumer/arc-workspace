# f9d67f8b

## Departures
- The concept's `mirror_sum_v` and `mirror_sum_h` (31) are stored as one parameter, `canvas_margin` = [0, 2, 0, 2]. That parameter holds the grid's margins within a 32×32 canvas, and each mirror is the canvas flip on one axis: [Grounding](docs/handbook/principles.md) needs every number to count something the task has. A sum of two coordinates counts nothing, and a margin counts canvas lines. The precedent 0934a4d8 stores the same structure as `mosaic_margin`. The `mirror-picture` scene line gives the value in this form.
- `restore` reads a stored 4 × 4 table of tile groups, the form 0934a4d8 and de493100 use. `Determine` gives the table from the train outputs, and `$DiagonalFallback` keeps the rule with no tiles. `full-orbit-cover` stands under that branch with `@relaxed mask-recoverable`.

## Judgments
- The concept's diagonal coset is the four D4 elements outside the group that the two axis flips generate, applied in the canvas frame. `mirror` is derived from `flip_of` and `d4_compose`, so no D4 constant is a literal.
- `$DerivedCenter` is a clause derivation and not a built-in derivation, so it is a constructor. Its candidates per axis are the margins of k lines past one edge, with k taken from `dist`. That choice gives one canvas per mirror center and covers k = 0 without a `ZERO` head, which fixes the `head-zero` hint. The `Unanimous` instance states that one candidate qualifies, and the model is undefined otherwise.
- Hint `common-subexpr` (between the mirror and diagonal image clauses): fixed by one relation, `image`, keyed by the D4 element.
- Hint `negated-use` on `has_mirror`: fixed when `image` replaced `mirror_color`. `has_mirror` now joins `image` with `mirror`.
- Hint `single-consumer` on `covered`: inlined into `image`.
- Hint `determine prediction` on `canvas_margin`: fixed. The determination now reads the train outputs alone, whose pictures are whole, through `Parse<Example>`. The `$DerivedCenter` symmetry test moved into `Parse`, which the program and `Determine` share.
- `mask_color` is determined as the color that the outputs change (the plan's ChangedColor).
- `store` printed no line to add. `margin` already equals the stored `canvas_margin` on every input, and that is the `$DerivedCenter` branch.
- Deletions: `impl_choice` was dropped from the restore clauses of `out`, where `image` binds the case. `!mirror(D)` was dropped from the diagonal clause, because `!has_mirror` implies it. The `ext_cand` atom was dropped from the first `broken` clause, because `mismatch` implies it. These were kept, though no pair exercises them: the visible-cell atoms of `paired`, the half-turn and identity clause of `mirror`, the covered-cell atoms of `image`, and the second `broken` clause, which is for outputs of different sizes. The concept states each of them.

## Unsettled
- `deletions` timed out on the deletion of column `canvas.p_grid` (train 0, 2 s). No finding rests on it. A rerun with a longer bound would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
