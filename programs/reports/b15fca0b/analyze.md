# b15fca0b

## Concept
- Fits every pair: in each input the fewest-step route between the two endpoints through background is unique, and painting its inner cells gives the output (checked with `GraphDistance`).
- No witness has verdict `other`: every reading found here that the pairs leave open is a branch below.

## Choice points
- `route`: how the route is chosen
    - `concept`: the least-cost route between the endpoints, by a search over all routes
    - `$WallFollow`: replaces `shortest-path`; a hand-on-wall walker goes from one endpoint, left or right hand, until it reaches the other. No parameters. Undefined where the walker never reaches the other endpoint. Fails Fit at train1: none of the four walkers, from either endpoint with either hand, gives the output.
- `cost`: what the route minimizes
    - `concept`: steps
    - `$FewestTurns`: replaces `shortest-path` and `unique-shortest`; the route with the fewest straight runs, ties broken by fewest steps. No parameters. Undefined where two routes tie on both. Fits every pair. Witness `turns-vs-steps`: breaks no scene claim; stored assignment; plausibility `variant`; verdict `concept`. Invariant broken: each wall is a solid straight bar.
- `adjacency`: which cells are next to each other on the route
    - `concept`: 4-adjacency
    - `$Adjacency8`: replaces `shortest-path` with an 8-adjacent route. No parameters. Fails Fit at train0: a diagonal step past (4,0) gives a 10-step route, which leaves (4,0) and (4,4) unpainted.
- `passable`: the cells the route can cross
    - `concept`: `background` cells
    - `$PassNonWall`: replaces `shortest-path` and `walls`; the route crosses any cell not of `wall_color`, and paints it. `wall_color` becomes a parameter the rules read. Fits every pair. Witness `foreign-color-on-route`: breaks `walls`; stored assignment; plausibility `variant`; verdict `concept`. Invariant broken: inputs hold only the background, wall and endpoint colors.
- `tie`: what is painted when fewest-step routes tie
    - `concept`: undefined (`unique-shortest`)
    - `$TieAny`: replaces `unique-shortest`; each tied route is a tiebreak output. No parameters. Fits every pair. Witness `tied-routes`: breaks `unique-shortest`; stored assignment; plausibility `variant`; verdict `$TieAny`. Invariant broken: the fewest-step route is unique.
    - `$TieUnion`: replaces `unique-shortest`; every cell of every tied route is painted. No parameters. Fits every pair. Witness `tied-routes`, as for `$TieAny`.
- `no-route`: what is given when no route joins the endpoints
    - `concept`: undefined (`connected`)
    - `$NoRouteKeep`: replaces `connected`; the input is given unchanged. No parameters. Fits every pair. Witness `no-route`: breaks `connected`; stored assignment; plausibility `foreign`; verdict `$NoRouteKeep`. Invariant broken: a route joins the endpoints.
- `endpoints`: how many endpoints the scene holds
    - `concept`: exactly two (`two-endpoints`)
    - `$AllPairs`: replaces `two-endpoints`; two or more endpoints, and the fewest-step route between each two of them is painted. Undefined where some two have no route or tie. Fits every pair. Witness `three-endpoints`: breaks `two-endpoints`; stored assignment; plausibility `variant`; verdict `$AllPairs`. Invariant broken: each input holds two endpoint cells.
- `background`: the background color
    - `concept`: stored, 0
    - `background=DominantColor`: replaces the stored `background` with the most common color of the input. Fits every pair. Witness `background=DominantColor`: breaks no scene claim; stored assignment; plausibility `variant`; verdict `concept`. Invariant broken: background is the most common color.
- `endpoint_color`: the endpoint color
    - `concept`: stored, 2
    - `endpoint_color=RarestColor`: replaces the stored `endpoint_color` with the least common color of the input. Undefined where the rarest color does not have exactly two cells, so wherever it and the concept are both defined they agree. Fits every pair. Witness `endpoint_color=RarestColor`: breaks `two-endpoints`; stored assignment; plausibility `variant`; verdict `endpoint_color=RarestColor`. Invariant broken: the endpoints are of color 2.
- `path_color`: the path color
    - `concept`: stored, 4
    - `path_color=OutNewColor`: replaces the stored `path_color` with a color in the output and not in the input. Fails Fit at train0: on a lone input, with `ex_out` empty, it gives no value, so the branch is undefined.
- `route` & `cost`, `route` & `tie`: a case that takes `$WallFollow` and `$FewestTurns`, `$TieAny` or `$TieUnion` has `$WallFollow`'s model alone. The walker minimizes nothing and gives one walk, so `cost` and `tie` exist only with the concept branch of `route`.
- Every other pair of points: the two branches' changes applied together.

## Open parameters
- none

## Not formed
- `background` or `endpoint_color` by `SharedColor`: on a lone input it gives every color present, so it does not pick out one color.
- `background` or `endpoint_color` by `ChangedColor`, `UnchangedColor` or `VanishedColor`: these read train outputs. On a lone input they give no value, so they fail Fit at train0, as `path_color=OutNewColor` does.
- `wall_color` by any derivation: no rule of the concept reads it, so a derived value changes no output.
- Painting the endpoints too: every pair keeps both endpoints in `endpoint_color`.

## Tickets filed
- none
