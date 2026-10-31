# e5c44e8f

## Departures
- The witness name `paint_color=stored` is now `paint=stored`, in the witness file's ids, groups and `separates` texts: the branch is the `@store` line on the derived relation `paint`, and [Witness file](docs/handbook/solver-file.md#witness-file) names a `@store` branch `<rel>=stored`.
- The witness file holds the witness `background=DominantColor`, which `derive` built: it is train 0 with colors 0 and 1 swapped. On it, `$AnyColorBlocks` with the stored `background` 0 treats every 1 cell as an obstacle and paints nothing, and `$AnyColorBlocks & background=DominantColor` draws the concept's spiral.
- Every case is undefined on an input that has no seed cell or two seed cells. `analyze.md` gives that `seed_color=RarestColor` is undefined where two colors tie for rarest, and gives every stored-seed case as undefined on the input whose seed is color 4. Without this gate, both inputs gave an output.
- The painted path leaves out the seed cell, which keeps its input color. In the concept this changes nothing, because the seed already has the paint color. It matches `analyze.md`'s `paint_color=stored` witness, where the seed stays 4 under the stored paint 3.

## Judgments
- The spiral is encoded as rings, not as a walk of arms. A `Propagation` over translations from the seed gives the ring radii 0, gap + 1, 2(gap + 1), ...: each step is `jump` by `gap` and then `neighbor` by one cell, so no literal is needed. Each ring's square is the seed outset by its radius. One turn of the spiral runs from the previous ring's square to its own square: the arm along `first_dir` runs on the previous square's side and reaches one ring step past it, the next arm starts at the previous square, and the third and fourth arms are sides of the turn's own square. The 08573cc6 precedent walks arms with a `Propagation` over arm ends that are grid positions. That form cannot follow a path that runs outside the grid and comes back in, which `$EdgeContinue` needs. The ring form enumerates only grid cells and the cells next to them, so all three edge-exit branches share it.
- The order along the path is `precedes`: ring first, then the arm within the turn (`arm_before`), then the distance along the arm. A path cell is painted when no blocking cell comes before it or at it, and for `$EdgeStop` also when no exit comes before it. `$MeetsObstacle` is defined only where some blocking cell comes before every exit.
- The ring radii come from distances in the grid plus one ring step. This covers every ring that has a path cell in the grid. The arm along `first_dir` of a turn lies on the previous ring, so the turn's own ring can be one step past the grid's distances.
- Hint `single-consumer` on `paint`: kept, because `paint` carries the `@store` line.
- Hint `determine prediction` on `Determine.obstacle_color`: kept under `@ignore`. The obstacle color is the input color that the output neither paints with nor paints over, and only a pair shows those two colors.
- `determination-plan` listed `background`, `gap`, `obstacle_color` and `seed_color`. Their determination relations read the repainted cells of each pair. `gap` is the distance from the seed to the last empty cell of a `Ray` cast in the second arm's direction before that cast meets the painted third arm. `first_dir` and `turn_sense` are enumerable, and each has one value that fits the pairs.
- `@derive DominantColor` on `background`: plausibility `variant`, because a color swap is a variant task. The verdict is `derived`, because the generator would draw the spiral on a field of 1. The line has `@relaxed one-seed`, because the field is not 0.
- `deletions`: 24 deletions change nothing on the pairs. Most remove the exit and edge-exit structure (`exit`, `past_exit`, `second_seed`, `!seed(P)`), which only the witnesses use. The `precedes` and `exit` key columns are kept, because they are the order's keys. `params.turn_sense(S)` in `Determine.beside.dir` is kept, because without it the cast runs in both senses. The `in(P, _)` disjunct of `arm_cell` is removed, because the neighbor disjunct already covers the grid's cells.
- Performance: an input with many seed cells, such as seed color 0, makes the ring and path relations large. The derive and relabeling runs time out on such inputs.

## Unsettled
- Audit `derive`: the `seed_color=DominantColor`, `SharedColor` and `VanishedColor` runs time out at 20 s, so no finding rests on them. A run that stops before it builds rings at more than one seed would settle them.
- Audit `relabelings`: that run timed out after 20 s. The same speed-up would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
