# c803e39c

## Departures
- The concept's square frame ("an n×n square one cell in from the panel's top and its near side, where n is the side of the solid squares") runs in `Parse.square_cell` as the place the solid squares hold in their panels: on their lines along the panel axis, at their distances from the near side. The header keeps the concept's text: this is a relational form of the claim, and it agrees with the claim on every input the generator produces, since the solid squares are themselves such squares. The literal reading needs a parameter for the "top" edge, and that parameter is task data that the evidence cannot fix: every grid is n+2 high, so `DIR_T` and `DIR_B` fit every pair (the sweep showed this on a draft that had a `top_side` parameter). The solver's outputs on all five Analyze witnesses equal the Analyze file's outputs (`witness --file` ok).
- `$HeightSide` takes n as the count of lines along the panel axis on neither cross edge (a `Tally`), and its square as those lines and the n cells after the first one from the near side. This is the Analyze "grid height less 2, at the same place" without arithmetic.
- `panel_role` is one Params relation with one column per role, `panel_role(k_tile, k_map, k_fill, k_ground)`, with the one fact `panel_role(0, 1, 2, 3)`. The reason: a role ADT is not among the types a solver may define.

## Judgments
- Choice points: `Role` (`PanelRank`, `TileByColor`), `ShapeFrame` (`Square`, `ShapeBbox`, `HeightSide`) and `Divider` (`StoredDivider`, `DividerByLines`) as a record `Choice`, plus `@derive DominantColor` on `background`. The branch names and the plausibilities and verdicts are the Analyze report's. All 6 witnessed cases pass every pair.
- `divider_color=SharedColor` and `background=SharedColor`: `derive` does not list them, so they fail Fit, which matches the Analyze report. No line was written for them.
- `store` printed no line to add, so no `@store` branch.
- Not formed: no item was formed. Telling fill from ground by color value goes against "Colors have identity and no other properties". Swapping tile/map or fill/ground is another value of `panel_role` and fails Fit. Drawing an unset block as the tile's complement fails Fit at every pair.
- Hints: `single-consumer` on `fill`: inlined into `out`. `pass-through` on the program's `divider_color`: removed, and the clauses now write `parse.divider_color`. `common-subexpr` in Determine: the shared rank quadruple became `roles`. `determine prediction` on `Determine.panel_role`: kept under `@workaround`, with its `@ignore`, as a workaround for the enumeration limit, and not as a judgment. The four roles are fixed jointly by the product the output draws. No fact of the inputs alone or the outputs alone tells tile from map or fill from ground. The runner's fit over the parameter's domain (923521 values) is past its enumeration limit.
- Determination: `divider_color` is the color that fills lines and lies on nothing else. `background` is the color of the panel cells on the edges across the panel axis. `tile_color` and `map_color` are the color the tile (map) panel's shape holds in the most inputs (`Mode`). With that reading, the swapped-shape-colors witness added to the train pairs still gives the stored value, as the plan requires. `panel_from` is left to the runner's domain enumeration, which keeps only `DIR_L` (1 of 4).
- Deletions that change nothing were kept, because each one carries the claim on inputs the pairs do not cover: `solid` and `panel_axis` in `square_cell`, the `k` column of `frame_cell`, `shape_panel` in the `$TileByColor` ranks, both disjuncts of `parse.solid`, `panel_from` in `cross_edge`, `hole` and `!hole` in Determine, and both `contradicted` clauses. The `shape_panel` atoms in the three `frame_box` clauses were removed: `out` reads frames only at the tile and map ranks.
- Keywords `decompose tile-arrangement scale stamp crop`. Dividers cut the panels. The output arranges copies of the tile. Each map cell scales to a block. The tile stamps at set map cells. Each square is the frame the model works in.
- Performance: one run takes about 19 s. Nearly all of that time is the `Determine` fit test over 256 role assignments.

## Open
- The combination cases (for example `$TileByColor & $DividerByLines`, or `$ShapeBbox` with `background=DominantColor`) are not witnessed, so no check runs them. A witness that breaks two claims at once would settle each combination that takes `$DividerByLines` or the derived background: for example, train0 with 1 and 2 swapped and the dividers recolored. Combinations of branches whose verdicts are all `concept` cannot be witnessed.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-790_task_c803e39c_create.md
- 10-791_task_c803e39c_create.md
