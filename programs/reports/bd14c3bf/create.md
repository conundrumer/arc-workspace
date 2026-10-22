# bd14c3bf

## Departures
- `paint_color` is the color of the reference shape's cells, and not a rename of `ref_color`: a rename is an `alias-inline` lint finding, and the `@store` line on `paint_color=stored` needs a relation of its own. Both forms give the same color on every input where a reference shape exists.
- Witness file: `mark_color=VanishedColor` is removed, since that branch has no case (see Judgments). `derive` added `mark_color=SharedColor` and `background=RarestColor`, and `corner-ring` is new (see Judgments). `record --all` rewrote every group to the solver's case names.

## Judgments
- Branch structure: `Choice = [shape, adj, cand, ref]` with `$Stretch`/`$Topology`, `$Adjacency4`/`$Adjacency8`, `$MarkColor`/`$AnyColor`, `$StoredRef`/`$CornerReference`. `ref_color=RarestColor` is a `@derive` line on `params.ref_color` (under `$StoredRef`), `background=DominantColor` is a `@derive` line on `params.background`, and `paint_color=stored` is a `@store` line on `paint_color`. All of them fit every pair. The run checks 15 witnessed cases.
- `$Adjacency8` joins only candidate shapes with 8-adjacency. The reference stays 4-connected, as the Analyze report gives the branch.
- `$CornerReference` reads `params.background` and is undefined where the corner cell is background, as the Analyze report states.
- `derive` also listed `mark_color=SharedColor`. On one input it gives every color of that input, so every shape becomes a candidate, the background's shapes included. It is held as `@derive SharedColor: variant derived`, `@relaxed mark-shapes`: its witness is train0 with 1 and 3 swapped, a color-permuted variant task, and the generator would paint the green matches red there.
- `mark_color=VanishedColor` is equivalent to `SharedColor`: on one input with no output, each gives every color of the input. It gets `@ignore: derive VanishedColor`.
- `derive` listed `background=RarestColor`. Its witness has the same input as `ref_color=RarestColor`, which the Analyze report judged `borderline`, and the concept's output there is the stored-background output: `borderline concept`. Its cases that take `$CornerReference` fail Fit, because the rarest color in every train input is the reference's red, so the corner cell counts as background and every pair is undefined. They get `@ignore: derive $CornerReference`.
- The `witness` run reported that no run showed `$StoredRef` defined and differing from `$CornerReference` in the pairs that take `paint_color=stored`. The new witness `corner-ring` shows it: a green ring holds the top-left corner and a red C stands apart, beside a blue stretched ring and a blue stretched C. Judged `borderline concept` and `@relaxed reference-shape`: the generator puts its red reference at the corner, and across the pairs red is the reference color.
- Lint hints:
    - The case-section hints came from shared clauses that read `ref_color(_, C)` and `cand_color(_, _, C)` as wildcards. The setup now takes the components of every color under both adjacencies, and each case selects its own.
    - The `head-repeat` hint on `matched` is fixed by keying it by the component id.
    - `single-consumer` on `paint_color` is kept with `@ignore`, because the `@store` branch stores that relation (the same reason as in a09f6c25).
- Deletions:
    - Applied: the enumerators in `out` that other atoms already bound, `box_cell` in `differ` (implied by `line_of`), `axis_of` in the run edge (a perpendicular step gives a self-edge), and `match_group` in the pattern (now every D4 element, filtered in `matched`).
    - Kept, because each states a claim that the pairs do not exercise: the `match_group` test, the negations in `$AnyColor` and `$CornerReference`, `perp`, `ref_fig` in `out` (undefined with no reference), `!open_part`, and the columns.
- Determine: it reads `ref_color` and `mark_color` from the recolored cells, `background` from the kept cells beside a recolored cell, and `ref_corner` from the corner whose input cell has the paint color. Each read is positive, which clears the `determine prediction` hints that a negated test over inputs and outputs gave. `match_group` stays with the values at which the model fits.
- Not formed: no item gives one model. The proposers other than `RarestColor` for `ref_color` give no single color. No proposer gives `mark_color` alone. "The smallest shape as reference" ties in train1, so it does not give one reference or one paint color.
- `stretch-match` has a relational form: the runs of identical adjacent lines come from `Canon`, the reduced frame from `OrderFrame`, and the D4 comparison from `KeyedSetCompare`. There is no approximation.
- Keywords: `objects congruent scale`. `scale` covers the stretched shapes, which correspond to the reference across a size change.
- The sweep reports 8 single-row changes of `match_group` that fit every train pair. The open values stay the Analyze report's `SYM_C4` and `SYM_D4`.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-593_task_bd14c3bf_create.md
