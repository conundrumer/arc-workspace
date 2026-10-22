# b7999b51

## Departures
- The concept file's `axis` parameter is not stored. `Params.axis` derives it from `anchor` through `axis_of`: the bars start from `anchor`, so `anchor` lies on `axis` in every variant task, and Redundant value makes `axis` derived data. The Analyze report's Not formed item, which measures extents on another axis, fails Fit at train1.
- The header carries only the `distinct-extents` scene claim. `background-field`, `colored-rectangles` and `rectangles-may-overlap` are left out because no `@claim`, `@relaxed`, rule text or branch denotes them (Style, Header).
- `witness --file work/task/b7999b51/witnesses.json` prints a difference under `tied-extents` for `$TieBothOrders`. That case gives the same two grids as the Analyze group, in the other order. No grid differs.
- The `tied-extents` witness's undefined group lists `concept` alone. The Analyze file listed `concept, background=DominantColor`. `record --all` wrote the groups.

## Judgments
- `$TieBothOrders` gives several grids, so `out` takes a trailing `TiebreakResolution` column, filled by a `TiebreakResolutions<Choice, Position, Color>` instance. The task has no alt. [Types](docs/handbook/solver-file.md#types) gives no other type for the several grids of one case. Every case reads that column:
    - In `$TieUndefined` and `$TieByPlace`, each bar line has as candidate the color whose rank equals its distance from `order_edge`, and that gives one resolution.
    - In `$TieBothOrders`, a line takes each color with rank ≤ its distance from `order_edge` and descending rank ≤ its distance from the opposite edge.
- The concept case is undefined on a tie. When two colors share a rank, one bar line has no candidate. Then the chart is not total.
- `$TieByPlace` orders bars of one extent by the bounding-box margin toward `order_edge` and then toward `anchor`, which is the Analyze reading. That reading puts the 2 bar before the 3 bar on `tied-extents`, as the Analyze file gives.
- `order_edge` is stored as a `Dir` beside `anchor`. The family varies its side on the perpendicular axis independently of `anchor`, so it is not relative to `anchor`.
- The Not formed items:
    - Extent measured on another axis than the bars: fails Fit at train1. On H the widths 7, 6, 5 give the order 2 3 1, and the output has 2 1 3.
    - The full height of a rectangle with a hidden edge: fails Relational form. The input does not give the hidden extent.
    - Ties ordered by color value: fails Relational form. Colors have identity and no order.
    - A stored output size: fails Fit. The train outputs are 5×4, 3×3 and 4×3.
- `derive` lists `background=DominantColor`, which is the `@derive DominantColor: borderline concept` line on `background`. `store` lists nothing.
- The sweep gives one value for each stored parameter. The determination plan lists no actions, so the solver has no `Determine` comp.
- The `deletions` run reports two kinds of deletion that change no pair's output. The `$TieByPlace` `before` clause and its two disjuncts stay, because the pairs have no tie and `tied-extents` exercises them. The redundant `impl_choice(Ch)` atom in the rank `cand` clause is removed.
- Keywords: `color-class` (each color's cells form one unit, its bounding box), `bbox` (the extent is the bounding box's extent), `rank` (the bars stand in order of extent).

## Open
- Using `TiebreakResolution` on a task with no alt to give `$TieBothOrders`'s several grids: a handbook line that names the type for a case whose rule gives several grids would settle it (ticket 10-461).

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-460_task_b7999b51_create.md
- 10-461_task_b7999b51_create.md
