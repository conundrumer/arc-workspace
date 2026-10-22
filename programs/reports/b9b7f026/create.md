# b9b7f026

## Departures
- Where a case picks more than one rectangle, the solver gives no grid, where the Analyze file gives one grid per color (`hole-neighbors` at `$HoleNeighbors`, `walk8` at the concept and `$NotSolid`, `color-class` at `$ColorClass`, `object8` at `$ColorClass` and `$Object8`): two `out` facts with different colors at the one output cell describe no total grid, and none of the column types that [Types](docs/handbook/solver-file.md#types) allows can tell those grids apart. The task gives no tiebreak alt and has no open parameter. Each of those witnesses still separates the same cases. Each `separates` text now says "is undefined" where it said that the case gives both colors.
- `Params` stores `out_dim` (1 on each axis) and derives `out_pos` through `helpers.frame_pos`, where the concept file gives `bg` alone: the `head-zero` hint fires on `out(ZERO, …)`, and approved 1×1-output solvers (1a2e2828, 27a28665) store the output size this way.

## Judgments
- The constructors for the concept branches are named `Closure` (pick), `BgWalk` (walk-set), `Walk4` (walk-adjacency) and `Component` (object). `bg=stored` is the concept branch of `bg`.
- `$CountRank` gets no constructor: the Analyze report says it fails Fit at train0, and gives it no witness.
- `bg=RarestColor`, `bg=SharedColor` and `bg=VanishedColor` get no `@derive` line: `derive` lists only `DominantColor` as fitting, and the Analyze report says each of the others fails Fit at train0.
- Not formed, "a rank among several holed rectangles": no branch. The item gives no order to rank by, so no reading of it states one model.
- Not formed, "an output sized by the hole or the rectangle": no branch. It fails Fit at train0, because that hole is 2×1 and the output is 1×1.
- `@derive DominantColor: borderline concept` takes the Analyze report's plausibility and verdict. The `bg=DominantColor` witness breaks no scene claim, so the line has no `@relaxed`.
- `$Walk8` uses a `Reach` instance with the diagonal steps added and edge seeds, because `Closed` has no 8-adjacent form. `$Walk4` keeps `Closed`, which is the lib's statement of the claim.
- `$ColorClass` gives each color an object id through `IdentOf<Color>`, with `@claim rectangles`, so that all three object readings share the `member` relation and the `Bbox<Obj>` instance.
- `$HoleNeighbors` keeps `dir_elem(D)` in its clause, although `deletions` reports that its removal changes no pair: the Analyze report gives that branch as 4-adjacency to a closed cell.
- `deletions` also reports that the `flood8` and `own8` clauses change no pair. That is expected, because `$Walk8` agrees with `$Walk4` on every pair. The `walk8` witness tests `flood8`.
- NotSolid reads the `outside` relation of `$OwnEnclosure` in place of a negated `member` atom (Simplify).
- Witnesses built for case pairs that no witness separated. The plausibility and verdict of each one is my judgment:
    - `split-color` (`$ColorClass` against `$Object8`): two apart bars of one color close off a bg cell together with two other bars. It breaks `rectangles` and `one-holed`. `foreign`, verdict `other` (no single rectangle has a hole).
    - `corner-join` (`$Object8` against `$Component`): two bars of one color that touch at a corner close off a bg cell. It breaks `rectangles` and `one-holed`. `foreign`, verdict `other`.
    - `hole-in-box` (`$HoleNeighbors` against `$BgWalk`): a holed rectangle inside the box of a C shape that opens to the edge. It breaks `rectangles`. `borderline`, verdict `$HoleNeighbors` (6).
    - `notch` (`$OwnEnclosure` against `$NotSolid`): a notched rectangle beside a holed one. It breaks `rectangles`. `borderline`, verdict `concept` (4).
    - `field-5` (`bg=DominantColor` against `bg=stored`, at `$OwnEnclosure` and at `$NotSolid`): the field is 5. This is a color permutation of a task input, so it is `variant`, and the verdict is `bg=DominantColor` (3).
    - `filled-ring` (`$HoleNeighbors` against `$OwnEnclosure`): a holed rectangle beside a hollow rectangle that another rectangle fills. It breaks `one-holed`. `borderline`, verdict `concept` (6).
- `sweep` reports `bg` and `out_dim` unique. `determination-plan` lists no actions, so the solver has no `Determine` comp.
- `store` has no findings, and the audit is clean.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
