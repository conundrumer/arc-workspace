# db93a21d

## Departures
- `$HaloTable` has no constructor, and `side-eight` is removed from the witness file: the case fails Subsumption. No run shows it defined and differing from the concept, and every table the generator's tasks give holds half the measure at each key, as `analyze.md` states. After the removal, `side-eight` separates nothing. With `$HaloTable` gone, the `halo-width` point has only its concept branch, so `OddSide` is a field of `Choice` and is no longer nested under a `Half` constructor.
- `$TrailStopsAtSquare` is removed from every group of the witness file: it fails Equivalence (`analyze.md`), so it has no constructor and no case.
- `frame_scale` is read as the count of equal parts that a square's measure is cut into, and the halo is one part wide (`tile_size(N, frame_scale, 0, K)`). The concept's gloss (the outer box's side over the square's side) gives the same value only at 2. The `halo` rule text says the same thing in this reading. Multiplying the side by `frame_scale` needs arithmetic, which the program bans.
- The `background` scene claim is left out of the header: no `@claim` or `@relaxed` line refers to it, and no rule text depends on it.
- The witness `side-five` was built for `frame_scale=TileCount` (see Judgments).

## Judgments
- `frame_scale=TileCount` (`@derive TileCount: borderline any`, `@relaxed squares`) is held as a branch, because `derive` reports that it fits. The derived tile counts of the grid's sides always include 2, and a square gets the union of the halos those counts give, so the widest halo wins on every pair. The witness `frame_scale=TileCount` (odd-side input) has verdict `any`, as `odd-side` has.
- Built witness `side-five`: a 10x10 grid with a 5x5 square. The model `$HaloFloor` gives a halo 2 wide, `$HaloCeil` gives 3, and `frame_scale=TileCount` gives 1 (5 parts). It breaks `squares` (odd side), so the plausibility is `borderline`. The verdict is `any`, the same as the analyze verdict on odd sides. The witness separates `$HaloFloor & frame_scale=stored` from `$OddUndefined & frame_scale=TileCount`, which no witness separated before.
- `square_color=RarestColor` is a `@derive` line (`variant derived`, `@relaxed squares`), as `analyze.md` gives it.
- `store` reported `cast.ray[d]` with no witness and printed no line to add. The ray's direction column always holds `params.trail_dir`, so the cast toward that one stored direction is the principled form of `trail`, and it carries no `@workaround` mark.
- Determine hints. The lint flagged `square_color`, which tested a negated input-and-output relation. It is rewritten as a positive read: a kept cell beside a cell of another input color that changes. `trail_color` keeps `@ignore: determine prediction`: the halo's color is read first, and the trail's color is the other new color.
- `frame_scale` determination: the halo run and the square's extent are observed from each square's edge cells, and only where both runs end inside the grid. A part count is kept where some observation gives exactly one part, and where no observation is shorter than one part. The plan now lists no actions.
- `deletions`: the 26 no-change deletions are kept. Each one removes structure that the pairs never use, such as odd sides, squares in another square's halo, or a trail across a square. Some of them, such as the `$HaloByWidth` axis atoms, only seem to change nothing because the halos are combined by union.
- Odd measure: `$HaloFloor` takes the middle line's distance to the square's edge, and `$HaloCeil` takes the distance from the line one step past the middle line. Both are counts of lines, so the rule needs no arithmetic.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
