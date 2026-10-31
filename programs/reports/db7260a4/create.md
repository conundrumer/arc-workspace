# db7260a4

## Departures
- `fill-height` stands under the concept branch of `fill-region` (`.type Fill = WallSpan {height: Height} | FillBasinFlood {}`), so the solver has no `$FillToTallerRim & $FillBasinFlood` case. `analyze.md` lists `fill-height` & `fill-region` as a pair: the property "end of the shorter or taller wall" exists only where the fill is bounded by the two walls the spread meets. `$FillBasinFlood` reads no wall end, because it finds its own level. [Choice points and open parameters](docs/handbook/principles.md#choice-points-and-open-parameters) puts a point under the branch its property exists with.
- The concept branch constructors have names of my own: `$WallSpan` (fill-region), `$ShorterWall` (fill-height), `$EdgeLines` (pool), `$StoredFall` (fall). The witness file uses `concept` for them, so no names needed a rewrite.
- `@scene no-landing-on-rim` is left out of the header. No `@claim` or `@relaxed` line denotes it, and no rule text depends on it ([Header](docs/handbook/style.md#header)).
- The concept's `fill` writes water only on cells that are not `wall`. This keeps `out` a function where a filled column crosses a wall cell. It changes no output on scene inputs, because the inside of a cup holds only background there.

## Judgments
- Water flow is a `Propagation` (construction) over cells. Its edges are "falls to the next cell toward `fall`" and "spreads from a landing cell to the cells of a `Ray` cast along its line up to the first wall". Recursion is banned, so this is how the fall and spread rules are written without it.
- A cup is held when the water reaches its landing cell, the spread meets a wall on each side (`spread.stop` in both perpendicular directions), and every spread cell has a wall under it. "Up to the end of the shorter wall" is written as "not above either wall's end", and "taller" as "not above some wall's end". The wall ends come from `Slide.rest` over wall cells, opposite `fall`. This avoids a min over the two ends.
- `$FillBasinFlood` is a `Reach` keyed by (fall, landing cell, level line). It keeps the highest level at which the reached set touches neither side edge nor the edge toward `fall`.
- `$FallFromDropEdge` is undefined on a corner drop and where no drop exists, because `fall_dir` then has no row and every `out` clause reads `fall_dir`.
- `store` printed `drop_edge` under `$FallFromDropEdge`, with the value DIR_T. Its stored branch gives back the stored fall of `$StoredFall`, so I recorded it with `// @ignore: store` and gave it no branch.
- Lint hint `common-subexpr` (`floored` and the fall edge): accepted. Both now read a `next_cell` relation.
- Lint hints `determine prediction` on `wall` and `pool_depth`: kept with `@ignore`. `wall` reads the input color left after the determined `water` and `background`. `pool_depth` counts the lines at the fall edge that the output covers fully. In each case, the other side of the evidence enters only through a parameter that is already determined.
- Determine: `water` is the one color with a single cell in every input (the drop). `background` is the color the drop cell takes in the output. `fall` is the direction whose opposite edge holds every drop. The determination plan lists no actions.
- `deletions`: the 27 deletions that change nothing remove structure that the pairs never instantiate. Examples are corner drops, an unbounded spread, a level that floods out, walls on the edge row, and more than one cup at a time. Each of those is a claim of its case, so all of them stay.
- Witness rewrite: `record --all` rewrote the names in the groups. No witness needed to be built, `witness` without `--file` reports no unseparated or unwitnessed case, and the run against `witnesses.json` is clean.
- Keywords: `walk` (stepwise flow), `cast` (falls along a line), `enclose` (a cup holds water only when it is closed).

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
