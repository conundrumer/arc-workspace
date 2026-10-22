# afe3afe9

## Departures
- The header has no `@scene pack-gap-empty` line: no `@claim` or `@relaxed` line names that claim, no rule's text depends on it, and no branch replaces it. [Style § Header](docs/handbook/style.md#header) admits a scene line only in those cases.
- Each `$PackTowardUniformHalf` / `$PackTowardColorHalf` case is undefined on an input whose squares' span has an even number of lattice lines on either axis. This applies to both axes, the pack axis included. The Analyze report states the same thing ("undefined where an axis spans an even number of lattice lines"). The witness `first-cross-line-empty` needs this reading, because in it only the V axis is even.
- Every case is undefined when some unit gets no output cell (`lost`). The Analyze report states this for `$StoredAlongExtent` (a line holds more squares than `along_count`) and for `$ComponentUnit` (pieces off one lattice). For the other branches the guard fires only where a unit lies off the lattice. That input breaks `ring-lattice`, and the Analyze report gives no output for it.

## Judgments
- Concept square: an `Outlines` box of one color whose two extents are `ring_side` and whose inside cells are all `bg_color`. This is the closest lib statement of "a hollow square of side `ring_side` with a background center".
- Lattice: the lines of each slot come from `stride` over each line's distance past an edge of the units' span. The slot's slab is the `Bbox` of those lines. A slab counts only when it holds `ring_side` lines, so it fits inside the frame. `$LatticeSpan` keeps the slabs inside the span, `$FrameLattice` keeps every slab, and `$RankedLines` keeps the slabs that hold a unit. These three sets differ only in which slabs they keep, so one `OrderFrame` places them across the pack axis.
- Middle line for the half branches: a span slab that has equal distances to the two edges of the span on its axis. "The only half that qualifies" is `Unanimous` over the qualifying sides.
- Cases: every combination of the four `Choice` fields fits every pair (3 × 2 × 3 × 3 bases), together with the two `@derive` branches. The runner reports 10 witnessed cases, and every pair passes.
- `derive` listed `bg_color=DominantColor` and `line_color=RarestColor`. Both are held as `@derive` lines (`variant derived`, `@relaxed edge-line`), as the Analyze report gives them. `derive` did not list `band_color` by `SharedColor`, so that parameter has no `@ignore: derive` line.
- `store` found nothing to hold. `line` was reported on a single line as having no witness. Each of the other single-value relations reads back a stored parameter.
- Not formed: packing toward or away from the line fails Fit at train0. In train0 the cells pack along rows and the line is a row, so neither reading fits. The other items are as the Analyze report gives them. None of them adds a case.
- Determination: the plan needed relations until the candidate product fell under its limit. `ring_gap` is the fewest lines strictly between two squares. `along_count` is a train output's extent along the edge line, which the pack axis is parallel to. The square and line-defect derivations moved into `Parse`, which `Determine` shares.
- Deletions: the `half` column `b` and the `impl_choice` atoms in `frame` and `placed` were removed, because nothing read them or another atom already bound the case. These stay, because the pairs never use what they state: `filled`, the side check, `even`, `lost`, `inside(S, B_a)` (the witness `first-cross-line-empty` uses it), `middle.a` with its `axis_of`, `axis_of(E, A)` in `lattice`, and the `nearer` and `opposite` atoms in `between.item`.
- Witness lines: `quadrants-one-color` (`ordinary concept`) and `band-recolored` (`variant concept`) were added under the two half branches, as the Analyze report gives them. `record --all` rewrote the group names into the listed forms. The grids are identical to the Analyze file, and `witness` with `--file` reports no difference.
- Keywords: `objects markers lines move rank scale`.
- No hint fired. The audit is clean, and each command runs in seconds.

## Open
- No witness shows `$StoredAlongExtent` undefined. A witness that would show it: train0 with a seventh square in a row.

## Lib
- Order of members by nearness to an edge: `Order` with `before(K, A, B) :- elem(K, A), elem(K, B), <dir D for K>, nearer(D, A, B)`. Here it is `along_order.before`. The grep finds the same shape in 3e6067c3, 72207abc, 7e576d6e, 9473c6fb, 97d7923e, 9968a131, 9f41bd9c, 99306f82, 9aaea919 and a1aa0c1e. The candidate operation is an `Order` whose input is a direction per key in place of `before`.

## Fixes elsewhere
- none

## Tickets filed
- none
