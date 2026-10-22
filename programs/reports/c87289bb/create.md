# c87289bb

## Departures
- `tie_dir` is not a parameter. The solver stores `tie_sense` (`SENSE_CC`), and the tie side is `turn(tie_sense, fall)`. The header's `tie-side` rule says this: [Style, Params](docs/handbook/style.md#params), "Relative orientation". The family fixes the tie side to the axis across `fall_dir`, and varies only its sense, since a mirrored variant changes the side and keeps `fall_dir`.
- Witness `streams-from-bottom`, case `$FallFromEdge`: the stream in col 5 now runs left around the bar, to col 3. The Analyze file has it run right, to col 7. This follows from the departure above: with the derived fall direction up, `turn(SENSE_CC, DIR_T)` is left. The right-going grid of the Analyze file is now the output of `$TieNearerEdge & $FallFromEdge`, which is a witnessed case on this witness.
- `bar` leaves out stream cells (`!stream(P)`). Without this, the `bar_color=RarestColor` case on its witness (where the rarest color is 8, the stream color) marked every stream cell as a bar and painted columns the Analyze file does not give. With the change, the solver gives the Analyze file's grid for that case: the 8 columns are streams and fall straight through the 2 cells.
- `$FallFromEdge` derives the fall direction from all four edges: the edge that every stream touches, which must be unique. The Analyze report reads it from the top and bottom edges only. This form needs no stored axis. It is also undefined where every stream touches a side edge as well as the top or bottom edge, for example a lone stream in col 0. No pair or witness has that.

## Judgments
- The concept's iterated detours are a `Propagation` over grid cells. A fall edge joins a cell to the next cell in the fall direction when that cell is not a bar. A detour edge joins the cell before a bar to the exit cell. The side is chosen once at the cell before the bar, so `$EdgeOtherSide` cannot loop back.
- `$OneDetour` uses the same `Propagation` without detour edges, then a `Ray` from each exit cell over every non-bar cell.
- Where the model is undefined, the case gives no `out` facts: no fall direction (`$FallFromEdge` with zero or two shared edges), or a stream meeting a bar's middle cell with no side (`$TieNearerEdge` on the grid's center line). This follows the Analyze report's undefinedness.
- Branches dropped under Fit (no witness, no constructor): `$StoredSide`, `$NearerEdgeSide`, `$TieSplit`, `$TieAwayFromStreams`, `$RunAtStreamEnd` and `$ReturnBelow`. The Analyze report gives the pair at which each one fails.
- `store` listed `misses` and `source_edge` under `$FallFromEdge`. Each has `@ignore: store`, because the stored form fixes the fall direction, and that case is equivalent to `$FallStored`. Of two equivalent cases, the case with more non-concept branches leaves.
- `@derive RarestColor` on `bar_color` has the Analyze report's plausibility and verdict, `variant concept`.
- Not formed items: none of them gives a separate model, so none became a branch.
- Determination: `Determine` gives `stream_color` (the color the output paints), `fall_dir` (the direction in which a stream cell's neighbor takes the stream color) and `bar_color` (the output color of the cell that stops a stream). The plan still lists `tie_sense` as enumerable with one fitting value, `SENSE_CC`. No proposer derives it, so it has no determination relation.
- My first `bar_color` determination tested input facts and output facts together, and the hint flagged it. I changed it to read the value from the outputs.
- Deletions: 13 deletions changed nothing on the pairs. The solver keeps all of them except the `impl_choice` atom in the `$EveryDetour` edge, which `flow_exit` already grounds. Each of the others serves a witness or an undefined case that no pair has: the `undefined` clauses, `two_source_edges`, the `in(X, _)` tests for exits, the off-grid disjunct, `!bar(P)` in `after.cell`, and `!stream(P)`. `stream_color` in the `fall_dir` determination states the concept.
- Keywords: `cast walk objects`. The streams extend along a line (`cast`), the detours make a stepwise propagation (`walk`), and the bars are discrete pieces (`objects`).
- Scenes `detour-lines-free` and `background-rest` are left out of the header: no `@claim` or `@relaxed` denotes them, no rule text depends on them, and no branch replaces them.
- I ran the inline Python edit scripts without `timeout 60` and `python -u`. They were short file edits, and each one finished at once.

## Open
- Whether the tie side under `$FallFromEdge` is relative to the fall direction (the solver) or a fixed screen side (the Analyze file): review of the "Relative orientation" reading for a stored sense against a derived direction would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-826_task_c87289bb_create.md
