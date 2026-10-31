# dd2401ed

## Departures
- `$NearEdgeOfNearMarks` is not in the solver: it fails Subsumption by `$NearEdgeNearer`, as `analyze.md` states, and `witness` showed no run on which it is defined and differs.
- `$FarColorOfFarSide` is not in the solver: it fails Subsumption by `$RecolorAnySwept`, as `analyze.md` states, and `witness` showed no run on which it is defined and differs.
- The case `$StoredNearEdge & $NearColorOfNearSide` is excluded from `impl_choice` (`subsumed_pair`): where the stored left edge has a destination inside the grid, the divider is nearer that edge, so `$NearEdgeNearer & $NearColorOfNearSide` gives the same output, and no input separates them at any assignment. `$NearColorOfNearSide` stands through `$NearEdgeNearer & $NearColorOfNearSide`.
- Witness `background=DominantColor`: `witnesses.json` gives `$NearEdgeNearer` and `$NearEdgeOfNearMarks` as undefined, and the solver's `$NearEdgeNearer` gives the concept's grid (old line 0, swept 2s become 1). The input still has one full line of 5 in the left half, so the edge the divider is nearer to is left, and the branch is defined there. I take `witnesses.json` to be wrong on this group.
- The destination rule is stated without arithmetic: the count of lines from `near_edge` up to and including the destination is `factor` times the count up to and including the divider, through `tile_size(K_dest, factor, 0, K)`. This is the concept's index 2(k+1)−1.
- A divider whose cells stand at different distances from the near edge (`skewed`) gives no destination, so the concept is undefined on a divider that is not a line across `near_edge`. Without this, a quarter-turned input gave a total grid with many destination columns.
- `$NearColorOfNearSide` reads a side that holds two non-background colors as no color (`mixed_side`), so the branch is undefined there, as `analyze.md` states.
- Witnesses added: `near-edge-right-assigned` (mirrored train0, `near_edge` reassigned to right) and `near-color-assigned` (train0, `near_color` reassigned to 3). They separate cases that take `side_color=stored` from the cases with derived side colors, as `witness` asked.
- `@store` on `side_color`: the store witness `side_color=stored` (train0 with 0 and 3 swapped) gets `variant background=DominantColor`, `@relaxed background`. The generator would give that input's background, 3, to the old line, which only `background=DominantColor` gives.
- `off_half` has `@ignore: store`: `store` found no input on which the stored value gives an output other than `$NearEdgeNearer`'s.

## Judgments
- `determination-plan` lists every parameter as covered by a proposer or by enumeration, and `sweep` finds each value unique. So the solver has no Determine comp.
- Lint hint single-consumer on `has_dest`: accepted, and the relation was inlined.
- Deletions: the 28 removals that change no pair are guards for inputs the pairs do not hold: two side colors, a skewed divider, marks on the destination, and the `d`/`c_near` reading key. The witnesses use them, so they stay.
- Keywords: `lines move span count`.

## Unsettled
- The `store` points `dest`, `skewed`, `near_color_at` (case `$NearColorOfNearSide`) and `recolored` (case `$RecolorAnySwept`) have no `@store` or `@ignore: store` line. The pace stopped new branches, and `store` ran 67 s, so a third run was not allowed. To settle them, run `store` once and write each line it prints.
- `$StoredNearEdge & $StoredNearColor & $RecolorAnySwept` and `$NearEdgeNearer & $NearColorOfNearSide & $RecolorAnySwept & side_color=stored`: `near-edge-right-assigned` separates them. To settle whether `side_color=stored` belongs in the solver at all, judge whether its cases meet Equivalence.

## Concept faults
- none

## Fixes elsewhere
- programs/reports/dd2401ed/witnesses.json, witness `background=DominantColor`: the groups list `$NearEdgeNearer` and `$NearEdgeOfNearMarks` as undefined, and both are defined with the concept's grid.

## Tickets filed
- none
