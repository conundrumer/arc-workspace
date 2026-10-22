# c6e1b8da

## Departures
- The Analyze witness `background=DominantColor` has the id `big-still-rectangle` in the witness file: `derive` wrote the branch's own witness (train0 with 0 and 1 swapped) under the id `background=DominantColor`, and a branch's witness takes the branch's name as its id. The groups of `big-still-rectangle` now read `background=stored` and `background=DominantColor`, from `record --all`; the grids are unchanged.
- The `@derive DominantColor` line gives `variant derived`, with `@relaxed solid-rectangles`, where the Analyze report gives `borderline concept`: the line records the witness `derive` built, and the Analyze judgment belongs to the further witness `big-still-rectangle`, which takes no `@witness` line.

## Judgments
- Only `$RestoreVacatedOnly` is a constructor, with `$RestoreWhole` as the concept branch of the `hidden-cells` point: the Analyze report gives no other non-derive branch a witness.
- Branches dropped under Fit, as the Analyze report gives: `$SlideUntilBlocked` (train0, the 5 rectangle), `$StillOnTop` (train0 rows 11–12, cols 11–12), `$HiddenToBackground` (train0 rows 4–6, cols 4–6), `$TailAtSideEnd` (train0, the 3 rectangle), and the derivations `SharedColor`, `RarestColor`, `OutNewColor`, `AnyOutNewColor`, `VanishedColor`, `ChangedColor`, `UnchangedColor`.
- Not formed: "tail kept or dropped" states one model, and it fails Equivalence, because the slid rectangle covers every tail cell. The other items state no model.
- The parameter is named `background`, as in the concept file's Parameters section.
- Rectangles are keyed by color (`color-class`): `solid-rectangles` gives each rectangle its own color, and a tail can cut a hidden rectangle's visible cells into pieces.
- Tail parse: a foot is a cell whose neighbor toward D has its color and has no neighbor of that color across D's axis, and whose two neighbors along the side have its color (the middle part of the side). The tail is the `Slide` run of the foot's color from the foot toward D. Its size (`Tally`) is the slide distance. This rejects train0's 3 rectangle, whose visible cell at row 12 col 1 is at the end of a side.
- Keywords: `objects color-class markers move occlude bbox`. The tail is a mark that fixes a direction and an extent. The hidden cells are recovered. A still rectangle is drawn over its bounding box.
- `tailed-apart` has no `@scene` line: no `@claim` or `@relaxed` denotes it, no rule text depends on it, and no branch replaces it.
- Hints: two `common-subexpr` hints (`foot` against `mate`, and `tail.node` against `foot`). I resolved both: `mate` now has the neighbor as a column, and `tail.node` now reads the foot's color alone.
- Deletions: I removed the redundant `!params.background` in `mate` and `side_end`, `tail.node(Q, Q)`, `foot` in `tail_cell`, `tail_size.domain`, and `in(Q, _)` in `slid`. I kept these: `tail_cand.a`, `side_end.d` and `axis_of` in `foot`, which state that the tail is one cell wide across its own axis and leaves the side perpendicular to it; `!params.background` in `tail_cand`, because the field is not a rectangle; `foot` in `tail.node`, which keys the instance by feet; `in(P, _)` in `out`; and the `slide` atoms of the `$RestoreVacatedOnly` clause, which define that branch.
- Determination: the plan asked for a relation for `background` from a fact other than dominance. `Determine.background` keeps the color that reaches every edge of each train input, which follows from `solid-rectangles`: the field lies around the rectangles. After that, the plan printed no actions.
- Witnessed cases: 3 of 4. `$RestoreVacatedOnly & background=DominantColor` is not witnessed: no input shows it giving an output that neither of its parts gives.
- I built no witness beyond the one `derive` wrote. `witness`, `witness --file work/task/c6e1b8da/witnesses.json`, and the final `audit` report no difference.

## Open
- Whether the edge fact is the one the determination-plan line means: the reply to ticket 10-772 would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-772_task_c6e1b8da_create.md
