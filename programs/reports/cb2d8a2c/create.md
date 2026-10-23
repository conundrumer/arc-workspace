# cb2d8a2c

## Departures
- `clearance_of=stored` is the constructor `$StoredClearance`, with `clearance_of` as a Params table, in place of a `@store` line. In the witness file, its name is `$StoredClearance`, and its witness id is `stored-clearance`: a `@store` line needs a relation that has one value on every input. `clearance_of(n, k)`, derived from the input's mark counts, differs between inputs, so that `@store` case stored no rows and failed every pair but train0. The run against `witnesses.json` differs only in that name.
- The witness file holds two witnesses that `witnesses.json` does not hold. `mark_period=SepTileCount` is the witness `derive` built for that branch. `recolored-source` shows `path_color=RarestColor` defined and differing from the stored path color, which the witness check asked for.

## Judgments
- The path is a walk over its corners: a `Propagation` over cells, with one edge per corner, keyed by `Choice`. The three `Meet` branches differ only in `lane_out`, the lane in which the path leaves a wall's turn row. Each leg is the bounding box of its two corners. The concept's lane past a wall does not depend on the lane it arrives in, but the shared walk lets the branches whose lane does depend on it use the same clauses.
- Each lane is the across component of `split` on the travel axis, and each turn row is the along component. `compose` joins them into a cell. The program has no arithmetic: the turn row and the lane past a wall are `jump` by the clearance and then one `neighbor` step.
- `$MarkedRunClearance` counts the cells of the run in pairs: the distinct period indices that `stride` gives at period `mark_period` (2) over the run's distances from the edge. This is half the run's length, rounded up, with no arithmetic. So the claim has a relational form.
- `mark_period=SepTileCount` is held as a `@derive` branch. It fits, and it differs on the input of `short-wall-near`. I judged that witness `borderline` (it breaks `walls-in-order`, as `analyze.md` judges that input) with verdict `concept`, because the generator pairs the concept's output with it.
- `mark_period=TileCount` gets `@ignore: derive`. It fits the train pairs at the derived set of tile counts, so that set holds 2 and not 1. At any set like that, the pair indices it counts are those that 2 alone counts, so wherever it is defined the output is the stored value's output, and the branch is subsumed.
- `recolored-source` (train0 with the source recolored 4): plausibility `variant`, because a color permutation of the task gives it. Verdict `path_color=RarestColor`, because the generator draws the path in the source's color. The solver has no `@witness` line for it, so `record` wrote its groups.
- Not formed items: none states one model that fits. Separate clearances and walls found by structure give no single model. The return to the original line and clearance from length fail Fit.
- Lint hints: `common-subexpr` on `turn_row`/`lane_past` was resolved by merging them into `detour`. The hints on `walk.edge` were resolved by one disjunctive clause and the helper `turn_cell`. `head-repeat` on `clearance_of` went away with the `@store` relation.
- Deletions: I removed the `impl_choice` atoms in the `lane_out` clauses and `gap.cell` and the `ex_out` atoms in the `Ray` inputs of `Determine`. I kept these, because they state structure that the pairs do not instantiate: the edge test in `source`, `back` in `wall_edge`, the straight-on disjuncts and `crosses`, and the `domain` rules (a wall with no mark has clearance 0).
- Determination: `mark_color` is the input color that no train output holds. `wall_color` is the color the marks take. `path_color` is the color that the output paints over a cell that is not a mark. `mark_period` is the `Ray` step from a mark along its wall to the next mark. `clearance_of` needs no determination relation: the train pairs do not pin rows for counts that they do not have.
- Performance: no issue. Each run took a few seconds, and the sweep took 65 s.
- I piped one `audit` run to `grep`. An unpiped `audit` on the same solver had already reported every check ok.

## Unsettled
- The 17 cases that are not witnessed, such as `$KeepClearance & $MarkedRunClearance`, are cases that no input shows giving an output that the cases with only some of their branches do not give: a witness of each combination would settle them.

## Concept faults
none

## Fixes elsewhere
none

## Tickets filed
- tickets/new/17-80_task_cb2d8a2c_create.md
