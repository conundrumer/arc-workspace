# ce602527

## Departures
- The `background` scene line reads "one color, the commonest, fills the grid around the shapes", where the concept file has "one color fills the grid around the shapes": the program finds the background with a `Mode` over the input's colors, as the corpus does (for example the `bg_mode` instances of non-draft solvers). On every input the generator produces, the background has the most cells.
- `out` has a `TiebreakResolution` column, `[shown: Color]`: where the concept matches two small shapes, it gives both grids (analyze.md, Concept and Not formed). Without the column the two shapes landed in one grid of mixed size, which the runner rejected as "inconsistent grid bounds" on `copy-chain`.
- The witness file adds five witnesses beyond witnesses.json: `scale=TileCount`, which `derive` wrote; `scale=TileDim`, `tile-dim-four` and `corner-block`, which separate the derived-scale branches from each other; and `copy-chain`, which shows `$LargeByCount` and `$LargeByEdge` defined and differing from `$AnyShape` (Subsumption). `record --all` rewrote the group names of the three Analyze witnesses into the forms the solver's cases take. `witness --file programs/reports/ce602527/witnesses.json` reports no difference.
- `$ScalePerAxis` is not formed: its encoding needs a workaround, and a non-concept branch takes none.

## Judgments
- The concept branches' constructors are `$Stored` and `$AnyShape`. `Choice` is the record `[s: ScaleSource, c: CopyIdentity]`, and all 6 combinations are cases. All of them fit. The witnessed cases are the concept case, `$ScaleDerived`, `$LargeByCount`, `$LargeByEdge`, `scale=TileCount` and `scale=TileDim`.
- The match: for each small shape s, copy l and scale, the solver takes every placement that lands a cell of s's enlarged form on a cell of l (`relative`). It keeps a placement when no cell of l is left uncovered and no cell of the placed form that lies inside the grid falls outside l (defect negation). This is the rule `pick-shown-shape` stated directly. It has a relational form, so no rule is approximated.
- The enlarged form is `concat_2d` of the shape's box cell and a cell of a `Frame2D<Scale>` block. `Scale = [a, k, k2]` keys the block by its extent on each axis. A uniform scale enters twice, once per axis; the two give the same block.
- "k ≥ 2" in `$ScaleDerived` is written without a literal: a length enlarges when its block line holds a cell at a positive distance from its first edge (`enlarging`).
- `$ScaleDerived` ranges k only up to the copy's own extent on each axis, under `@workaround`. The principled form runs k up to the grid's extent. With that form the derive runs at large factors ran out of memory: a run at a factor of 17 was killed with -9 before I changed `stray` to range over grid cells.
- `stray` is tested only on placements that `uncovered` leaves standing. `deletions` reports that the filter changes nothing, but I kept it: without it every placement at a large scale is checked against the whole grid.
- Hints: two `case section` hints, on `params.scale` and `factor`, are dismissed with `@ignore`. The match is keyed by `Scale` and shared, as [Components](docs/handbook/solver-file.md#components) "Keys" asks, and each case reads it only at the scales its own `factor` rows give. The lint's static reading cannot see that. The `single-consumer` hint on `shown` was resolved by folding `shown` into `out`.
- `derive` held two derivations that fit. `scale=TileCount` and `scale=TileDim` are `@derive` branches with verdict `variant derived`, `@relaxed enlarged-copy`. Their witnesses enlarge the copy by 3 or 4, which breaks the factor of 2 without breaking the rest of the scene, and the generator would pair the copied shape, which is the derived output.
- `store` found no relation that holds one value on every input, so there is no `@store` line.
- Judgments on the witnesses I built:
    - `scale=TileDim`, a 3× copy in a 15 × 15 grid: `variant`, verdict `derived`.
    - `tile-dim-four`, a 4× copy in a 9 × 9 grid: `variant`. The generator would pair the 2 shape, the output of `$ScaleDerived` and `scale=TileDim`.
    - `copy-chain`, where one small shape is itself the other enlarged: `borderline`, since it breaks `enlarged-copy`'s single copy. Verdict `$LargeByCount`, because the generator pairs the shape the large copy shows.
    - `corner-block` has a fourth shape: `foreign`, since it breaks `three-shapes`. Verdict `any`. It exists only to separate cases.
- Analyze's branches that fail Fit (`$MatchUpToD4` at train1, `$BlockAligned`, `$Components8` and `$CopyColor` at train0, and the four `$Pick*` branches) have no witness, so they have no constructor here. The three Not formed items give no model that fits: the reduced visible part and a stored background color fail Fit, and the two-match output gives no other reading.
- Determine: the plan asked for a determination relation for `scale`, because `TileDim` derives 2 from the grid's extents, a fact the concept does not use. `Determine.scale` keeps each factor at which, in every train input, some shape's enlarged form shows as another shape. To share it, the shape parse and the match moved into `Parse<Key>`. The determination gives 2, and the plan then reports no actions.
- Simplify: `deletions` led me to remove `size.domain`, since every shape has cells, and the `pairing` atom in `enlarged`. The other atoms it lists stand for structure that the pairs do not exercise, such as the full extent in `span`, the edge test of `$LargeByEdge`, `perp` and the `missed` rule.
- Keywords: `color-class scale crop select match`.

## Unsettled
- The audit's store report skipped `parse.enlarged`, `parse.placement` and `parse.uncovered`, each over 20000 rows on one input: it is open whether any of them holds one value on every input. That is unlikely, since all three vary with the shapes. A store check that handles large relations would settle it.
- The `@workaround` bound on `$ScaleDerived`'s factor changes that model only where the copy shows less than one block along an axis. A faster match, or a principled bound at the grid's extent, would settle it.

## Concept faults
- none

## Fixes elsewhere
- `scripts/run_dl.py` lint, "case section" hint: it treats a relation keyed by a non-`Choice` key, here `Scale`, as read by every case once the `Choice` column is dropped. It should follow the case through the join that gives the key (`factor(Ch, L, Sc)`).
- `scripts/run_dl.py derive`: it judged `scale_axis=ConstInDimAxis` as fitting through cases that do not read `scale_axis`. It should judge a derivation only on cases that read the parameter. This is the same static reading, and it also inflates the case count from 12 to 36.

## Tickets filed
- none
