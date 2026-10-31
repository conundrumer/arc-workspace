# b9630600

## Departures
- The `join-selection` point is not in the solver. `measured-rule` and `join-weight` are the `Select` and `Weight` fields of `Choice` at top level: the other branches of `join-selection` (`$AllFacing`, `$NearestPerSide`) fail Fit and have no witness, so they get no constructor, and a type with the concept branch alone would encode no choice.

## Judgments
- `shortest-joins` states the relation the pairs show: a facing pair gets a corridor unless its two rooms are linked by a chain of facing pairs whose gaps are each strictly smaller than its gap. The program runs that relation, so the rule has no `@approximated:` line and no `tied-loop` witness. The scene claim `unique-largest-gap` (in every loop of facing pairs, the largest gap belongs to one pair only) limits the inputs to those where this relation gives one spanning tree of least total gap.
- `impl_choice` leaves out `$GapLimit & $AreaWeight`, which fails Fit per the Analyze report, and `$GapLimit & $IgnoreBlocking`. The run showed the second one failing: on train0 it gives conflicting colors at (16,14), (16,16), (17,14), (17,16), and on train2 the stored output is not among its grids. 10 cases remain: `$SpanningTree` with every `Weight`, `Span` and `Facing`, and `$GapLimit & $GapWeight & $ClearBand` with each `Span`.
- `$NearestJoin`, `$AllFacing` and `$NearestPerSide` fail Fit (Analyze report). They have no witness, so they get no constructor.
- Not formed:
    - Corridor wall lines placed inside the shared span, or on the boxes' outer lines, fail Fit. The span-2 bar at train0 rows 20–21 is solid, and the train1 corridor at row 9 has its walls at cols 3 and 6 (the shared interior lines), not at the box lines, cols 2 and 7.
    - The choice among tied corridors is a tiebreak, and the generator leaves it free. `tied-loop` records it.
    - The gap measured wall to wall orders the pairs the same way as the cell count, so it gives one model.
    - `SharedColor`, `ChangedColor`, `UnchangedColor`, `VanishedColor` and `OutNewColor` give no single value.
- The `@derive` lines `background` DominantColor and `room_color` RarestColor are `variant derived`, `@relaxed hollow-rooms`, as the Analyze report gives them. `store` printed no line to add.
- The gap is the `k` of the `Ray` cast from the first cell past a room's wall to the facing wall cell, so it counts the band cells. `facing-pair` under `$ClearBand` is the universal "every shared line's cast stops first at the facing wall, and its first cell is `background`", written as the defect relation `blocked_band`.
- `Ray` is keyed by `Dir`: the marks beyond the walls on side d cast only toward d.
- `$NarrowerSpan` uses the corridor's orientation from the room whose box is no wider (`box_extent`). The corridor runs out to the line of the other room's wall (`same_dist`). The case is undefined (`live` withholds it) where two facing rooms have one width and a line that is not shared.
- `$AreaWeight` measures a pair by a `Tally` of the corridor's band cells. That band is the gap times the lines of the corridor's span, so the key includes `Span`: under `$NarrowerSpan` the span is the narrower interior, as the Analyze report's `join-weight` & `corridor-span` line gives.
- The program compares distances and counts (`K_x < K`, `N <= N2`, `N2 < N`, `K <= M`) as bound comparisons. Lint did not flag them.
- Hints:
    - `pass-through` on `weight`: merged into `measure`.
    - `common-subexpr` on the two `paint` clauses: merged into one disjunction.
    - `reserved name` `band`: renamed to `corridor_cell`.
    - `keyword`: see the proposal below.
- Keyword proposal: `spanning-tree`, with the gloss "pieces are joined by links into one connected network with no loop, and an order of the links' measures chooses the links". No listed keyword denotes that concept: `match` pairs pieces off, `rank` covers the order, and `route` is a path between designated ends. The solver's `@keywords:` line carries it.
- Deletions:
    - `impl_choice` in `paint`: removed, because `live` in `out` already restricts the cases.
    - `clear_line` columns: `d` removed from `blocked_band` and `clear_line`. A version keyed by (d, q) alone failed train2 under `$GapLimit`, because a line's cast reaches rooms behind the facing room, so the pair key stays.
    - `outer_line.a`: kept for reading.
    - `!sight.blocked`, `no_narrower`, `live` and both `area.tally` disjuncts: kept. The pairs do not exercise them, and the witnesses or the undefined inputs of `$NarrowerSpan` need them.
- Determine: the sweep found each stored value unique, and `determination-plan` lists no actions (DominantColor and RarestColor are exact, and `max_gap` is pairs-exact at 7). So the solver has no `Determine` comp.
- `witness` with no `--file` reports no unseparated case and no unshown case. `--file` on the Analyze file differs only at `tied-loop`, where the concept case gives the loop, as its `other` verdict expects.
- Performance: the run is about 1 s. With `room_color` equal to the background (the 0 field), `Outlines` finds every rectangle of the field, `face_cell` pairs each such box with every cell, and the run passes 20 s.

## Open
- The audit's relabeling check timed out after 20 s, so it judged nothing. A run limit that fits this solver, or a faster room parse under a relabeled room color, would settle it.
- `derive` did not judge `room_color` by DominantColor, SharedColor or VanishedColor, because each run timed out after 20 s (see Performance). A run that finishes would settle it. The DominantColor value, 0, is the field color, so it almost certainly fails Fit.

## Concept faults
none

## Fixes elsewhere
none

## Tickets filed
- 10-493_task_b9630600_create.md
