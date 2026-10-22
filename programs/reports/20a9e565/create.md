# 20a9e565

## Judgments
- The solver is the Create draft of `work/task/20a9e565/2/` brought under the current handbook. The concept case reads the `catalog` instance of `DemonstrationConsistency`. Its `DemonstratedChoice` holds one growth rule per input: `Stretch {side: Dir}` (train 0), `FlippedEnds` (train 1), `PeriodEnd {side: Dir}` (train 2), `MirrorEnds` (test 0) and `SplitStep` (test 1). Each rule has its own clauses.
- The rules that apply are the ones `catalog.confirmed` gives. `out` takes a `DemonstratedChoice` column after the `Choice` column.
- No relation of the solver recurses. Each closure of the draft has a closed form or is a lib construction:
    - The count of periods, moves or steps that a growth adds after n steps is a whole multiple, which `stride(S, K, 0, N, 0)` states (`period_block`, `repeat`, `tent`).
    - The mirror end that the term reaches after n steps is the end of rank n in an `Order` over the ends (`ends`).
    - The end pieces of `FlippedEnds` are a `Propagation` over (index, cell), with grid cells as the domain of its edges (`end_piece`). The flip keeps a cell inside the term's band along the sequence, and a cell that moves off the grid across the sequence is not shown.
    - The front lines of the new terms are a `Propagation` over (index, line) (`front`). A front line that is off the grid places no term that is on the grid.
    - A new term's color is the color of the shown terms at its place in the cycle, by `stride` on the index (`term_color_at`).
- The cases are the same as the draft's: `Drawn` (`$EveryTerm`, `$NewTermsOnly`) × `Extent` (`$MarkBox`, `$ElbowBox`), with `@derive` on `background` and `marker_color`, and `@store` on `term_gap`. `record --all` left every group of the witness file unchanged.
- Hints:
    - `fill` keeps `@ignore: head-repeat`, because a cell that a rule grows in the grown term's own color names that term in two columns. `shape` is folded into `fill`.
    - `stretch` keeps `@ignore: head-zero`.
    - `half_out` keeps `@ignore: common-subexpr`, because it measures a different part than `piece_shift`.
    - `tent_seed` keeps `@ignore: head-repeat`.
    - `grid_line` takes the atoms that `gap.item` and `advance` shared, and `steps` reads `moves`.
- Simplify, from `deletions` (777 s):
    - These atoms are removed, because another atom implies them: `term_at` in `step`, `span(N)` in `period_block`, and `new_index(D, I2)` in `advance`.
    - The clause of `term_color_at` for shown terms is removed, because only new terms read it.
    - The other deletions that change nothing stay. They are keys, or guards that state a rule's condition, or generality that the pairs do not use: `uncolored`, the `W = 0` disjunct, the `elbow` atoms, and the `$EveryTerm` clause that `new-terms-only` needs.

## Open
- `store` does not check `fill` and `grown_box.cell`, because each has over 20000 rows on an input.

## Departures
- The Analyze file's `distinct-color-cycle` and `stored-mark-corners`, and its names `$DistinctColorCycle` and `$StoredMarkCorners`, have no case. Both branches fail Subsumption, as the Create report in `work/task/20a9e565/2/create.md` gives.
