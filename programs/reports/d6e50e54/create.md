# d6e50e54

## Departures
- `$CollideUndefined` is no longer in the solver. Its constructor and clauses are gone, its name is gone from every group of the witness file, and the `separates` text of `same-line-pair` no longer mentions it: `witness` reported that no run shows it defined and differing from `$Merge`. Wherever it is defined, it gives the concept's output, so it fails Subsumption, as `analyze.md` also says.
- The case that takes the concept base and `mark_color=RarestColor` is no case of the solver: it is recorded by `@ignore: derive concept` under the `@derive RarestColor` line. `witness` reported that no run shows `$OffLineUndefined & mark_color=RarestColor` defined and differing from `$OffLineErase & mark_color=RarestColor`, and no input can show it: where the first is defined, no mark is off-line, and the two give the same output. So it fails Subsumption. The run against `witnesses.json` therefore says that `mark_color=RarestColor` denotes no case. Its cases that take `$OffLineStay` or `$OffLineErase` remain.
- I added a point `Touch` (`$TouchLands` concept, `$TouchStays`) with witness `touching-mark`: Develop step 3 forms the Not formed item "a mark that touches the block staying outside it". It states one model, fits every pair (no pair has a touching mark) and has a relational form (the mark is the neighbor of the block cell its line meets).
- Concept constructors take names of my own: `Within`, `Along`, `TouchLands`, `Always`, `Merge`, `OffLineUndefined`, `RestKept`, `MarkStored`, `BlockStored`. The type for the `reach` point is named `ReachBy`, because `Reach` clashes with the lib component of that name. No name in the witness file needed rewriting for these.
- The witness file holds `touching-mark` beyond `witnesses.json`, and its groups have been rewritten by `record --all`.

## Judgments
- `touching-mark`: plausibility `variant`, verdict `concept`. The concept's rule names d = 1 explicitly and treats every distance alike, so a touching mark lands on the block's edge. No input has a touching mark: the least distance over all 16 marks is 2. That suggests the generator may avoid touching marks, so the witness is `variant` rather than `ordinary`.
- Not formed, "a mark off the block's rows and columns pulled diagonally to a corner": this does not state one model. An off-line mark lies on a corner's diagonal only by chance, and the item gives neither a landing cell nor a reach for such a pull. No branch was formed.
- Not formed, "reach of the side plus a stored offset": fails Relational form, because the offset counts nothing the task has, as `analyze.md` says. No branch was formed.
- `$Stack` is encoded as follows: a lane's marks rest in a row outward from where the lane's nearest mark lands, one cell per nearer mark (an `Ordinal` rank over distance, keyed by the first block cell the line meets and the side). This equals `analyze.md`'s step-by-step rule, because every landing cell is either the block's edge cell or the cell just outside, and landing cells grow outward as distance grows.
- The reach branches use comparisons with bounds only. `$ReachMin` requires the distance to be below both extents; `$ReachMax` requires it to be below one of them. No aggregate is needed.
- A mark found inside the block (mark color equal to block color) makes the model undefined, through `overlap`. This is where `analyze.md` makes `mark_color=RarestColor` undefined.
- `$MarkColorByShape` and `$BlockColorByShape` read objects as same-color, 4-connected pieces: a cell with no same-color neighbor is a single-cell object, and the block is the one same-color `Components<Color>` piece of more than one cell.
- `derive`: both lines it printed were already written from `analyze.md`. `store`: no line to add. `placed[col]` is already stored as `mark_color`, and every other value has no witness.
- `deletions`: 32 removals change nothing. I judged each to remove structure the pairs never instantiate: the undefined and off-line clauses, the two-color and two-object guards of the ByShape branches, the axis column of `side` (every block is square), the nearest-mark anchor of `$Stack` (no lane holds two marks), `touching` (no touching mark), and the `uneven` and train-scope guards of `Determine`. All stay. The two bound enumerators, `dir_elem(D_in)` and `axis_elem(A)`, stay as the report says.
- Simplify: the `ruled`, `named` and `tint` relations, keyed by the whole `Choice`, were replaced by `out` clauses over `placed`, `block` and `mark`. The model and the cases are unchanged; the run passes and `witness` is ok after the change.
- Determine: the plan's first list asked for a relation for every parameter. `bg` is the commonest color of every train input, `fill_color` a color of the outputs that no input holds, and `block_color` a color of a train input that no output keeps. For `mark_color`, the first relation ("neither bg nor block") gave 3 with `stray-cell` added, so it is now a color whose cells clear to the field. The plan then reported no actions.
- Performance: one run takes 80–90 s and the audit 521 s (1052 s before the restructure), from 1920 bases times the derive copies. There is no `@workaround`; the principled form stands.
- Keywords: `objects move count`. The count is the block's side length, which decides where a mark lands.

## Unsettled
- The case that takes the concept base and `bg=DominantColor` is subsumed by `$OffLineErase & bg=DominantColor` in the same way as the RarestColor case. More generally, every case that takes `$OffLineUndefined` is subsumed by its `$OffLineErase` copy. `witness` reports only the pair whose `$OffLineErase` copy is a witnessed case, so those cases stay. What would settle it: a statement of whether Subsumption is checked against unwitnessed cases.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
