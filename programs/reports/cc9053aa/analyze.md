# cc9053aa

## Concept
- The concept fits every pair. At each train pair it gives the expected output. At test0 it gives one grid, the expected one. Under the 8-neighborhood closure, the clear wall cells in each pair hold exactly one simple route between the two contacts, so there are no ties and no detours to choose from.
- No witness has the verdict `other`.
- In this report, a turn count includes the step from each marker into its contact cell.

## Choice points
- `hazard-reach`: the wall cells a hazard closes to the route
    - `concept`: each wall cell with a hazard in its 8-neighborhood, at a side or at a corner
    - `$HazardSide`: replaces `clear-walls`. A wall cell closes only when a hazard is 4-adjacent to it. No new parameters. It is defined wherever the concept is. It fails Fit at test0: the clear cells join (1,1) to (1,7) by four tied fewest-hop routes of 18 steps, so the model gives four grids.
    - `$HazardCellOnly`: replaces `clear-walls`. No wall cell closes, and the route avoids only the hazard cells themselves. No new parameters. It is defined wherever the concept is. It fails Fit at train0: the route runs down col 7, (1,7)–(5,7).
    - `$HazardRoom`: replaces `clear-walls`. A wall cell closes when its 8-neighborhood holds a cell of the background region that holds a hazard, or holds the hazard itself. No new parameters. It is undefined where a marker's contact cell closes. It fails Fit at train2: contact (1,4) borders the room at row 2, cols 2–6, which holds the hazard at (2,2).
- `route-choice`: the cells painted when the clear wall cells join the contacts in more than one way
    - `concept`: each fewest-hop 4-connected walk of clear wall cells from one contact to the other. Tied walks each give their own output grid.
    - `$RouteTieUnion`: replaces `route`. One output paints every cell of every fewest-hop walk. No new parameters. It fits every pair. Witness `tied-routes`: it breaks `one-clear-route`, plausibility `borderline`, verdict `concept`.
    - `$RouteAnyWalk`: replaces `route`. One output paints every clear wall cell on some simple walk between the contacts, of any length. No new parameters. It fits every pair. Witness `unequal-routes`: it breaks `one-clear-route`, plausibility `borderline`, verdict `concept`.
    - `$RouteFewestTurns`: replaces `route`. It takes the simple walks with the fewest turns, of any length, and each gives its own output grid. No new parameters. It fits every pair. Witness `unequal-routes`: the shorter route and the longer route both have four turns, so this model gives two grids and the concept gives one. It breaks `one-clear-route`, plausibility `borderline`, verdict `concept`.
    - `$RouteTieFewestTurns`: replaces `route`. Of the fewest-hop walks, it keeps those with the fewest turns, and each gives its own output grid. No new parameters. It fits every pair. Witness `tied-turns`: it breaks `one-clear-route`, plausibility `borderline`, verdict `concept`.
    - `$RouteReachable`: replaces `route`. It paints every clear wall cell that is 4-connected to a contact. No new parameters. It fails Fit at train0: it paints the spur at (3,2).
    - `$RouteOuterBoundary`: replaces `route`. The route runs along the structure's outer boundary, on the side that is clear of hazards. No new parameters. It is undefined where both sides close. It fails Fit at train2: (1,3) and (2,1) close the left side, and (6,7) closes the right side.
- `route-color`: the color the route is painted
    - `concept`: `marker_color`
    - `route_color=stored`: replaces `paint-route`, and adds the parameter `route_color` = 9. It is defined wherever the concept is. It fits every pair. Witness `route_color=stored`: the train0 input with `route_color` set to 3. It breaks no scene claim, plausibility `ordinary`, verdict `route_color=stored`.
- `wall-color`: the value of `wall_color`
    - `concept`: stored
    - `wall_color=DominantColor`: on train0 alone this derivation gives 0. It fails Fit at train0: marker (1,8) touches two cells of color 0, so the model is undefined.
    - `wall_color=SharedColor`: on train0 alone this derivation gives 0, 7, 8 and 9. It fails Fit at train0: the model is undefined there.
    - `$WallColorCommonest`: replaces the stored `wall_color` with the commonest color other than `background_color`, which becomes a parameter. It is undefined on a tie. It fits every pair. Witness `recolored-walls`: it breaks `wall-lattice`, plausibility `variant`, verdict `$WallColorCommonest`.
- `marker-color`: the value of `marker_color`
    - `concept`: stored
    - `marker_color=RarestColor`: on train0 alone this derivation gives 7 and 9. It fails Fit at train0: four marker cells, so the model is undefined.
    - `marker_color=SharedColor`: on train0 alone this derivation gives every input color. It fails Fit at train0: the model is undefined there.
    - `$MarkerColorEdge`: replaces the stored `marker_color` with the one color other than `background_color` on the grid edge, and `background_color` becomes a parameter. It is undefined where the edge holds no such color, or more than one. It fits every pair. Witness `recolored-markers`: it breaks `two-markers`, plausibility `variant`, verdict `$MarkerColorEdge`.
- `hazard-color`: the value of `hazard_color`
    - `concept`: stored
    - `hazard_color=RarestColor`: on train0 alone this derivation gives 7 and 9. It fails Fit at train0: the contact (1,7) touches the marker (1,8), so the contact closes and the model is undefined.
    - `hazard_color=SharedColor`: on train0 alone this derivation gives every input color. It fails Fit at train0: every wall cell closes.
    - `$HazardColorRest`: replaces the stored `hazard_color` with the one input color other than `background_color`, `wall_color` and `marker_color`, and `background_color` becomes a parameter. It is undefined where there is no such color, or more than one. It fits every pair. Witness `recolored-hazards`: it breaks `hazards`, plausibility `variant`, verdict `$HazardColorRest`.
- `hazard-reach` & `route-choice`, `hazard-reach` & `route-color`, `hazard-reach` & `wall-color`, `hazard-reach` & `marker-color`, `hazard-reach` & `hazard-color`, `route-choice` & `route-color`, `route-choice` & `wall-color`, `route-choice` & `marker-color`, `route-choice` & `hazard-color`, `route-color` & `wall-color`, `route-color` & `marker-color`, `route-color` & `hazard-color`, `wall-color` & `marker-color`, `wall-color` & `hazard-color`, `marker-color` & `hazard-color`: the two branches' changes applied together
    - `$HazardSide & $RouteFewestTurns` and `$HazardSide & $RouteTieFewestTurns` fit every pair. At test0, of the four tied 18-step routes, only the expected route (col 1, row 7, col 7) has the fewest turns, and it has fewer turns than any longer route. Every other combination with `$HazardSide` fails Fit: with `$RouteReachable` or `$RouteOuterBoundary` at the pair where that branch alone fails, and otherwise at test0. Every combination with `$HazardCellOnly` or `$HazardRoom` fails Fit at the pair where that branch alone fails.

## Open parameters
- none

## Not formed
- A hazard reach wider than the 8-neighborhood: at radius 2, the hazard at train2 (2,2) closes the contact (1,4). Radius 0 is `$HazardCellOnly`.
- The route keeps every hazard on one side: the train2 route has the hazard (2,2) on one side and (6,6) on the other, and no route between the contacts keeps both on one side.
- Role colors from the proposers that read `ex_out` (`OutNewColor`, `ChangedColor`, `UnchangedColor`, `VanishedColor` and the like): a run on an input alone has `ex_out` empty, so they give no value, and the branch is undefined at every pair.
- The count-rank proposers (`CountRankAsc`, `CountRankDesc`): at train0, 7 and 9 tie at the lowest count, and the commonest color is 0 at every train input. No rank gives one role color on every input alone.

## Tickets filed
- 10-598_task_cc9053aa_analyze.md
