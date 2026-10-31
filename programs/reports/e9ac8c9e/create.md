# e9ac8c9e

## Departures
- The branch `background=DominantColor` is the `@derive DominantColor` line on `bg`, named `bg=DominantColor` in the witness file. `witness --file programs/reports/e9ac8c9e/witnesses.json` reports only that `background=DominantColor` denotes no case. No grid differs. The renaming rests on Write ("other than one that derives a parameter's value by a built-in derivation") and Develop step 5.
- The Analyze witness `background=DominantColor` is kept under the id `dominant-block`: `derive` recorded its own witness under the id `bg=DominantColor`, and ids must be unique. `dominant-block` does not duplicate it. The `derive` witness swaps 0 and 3, and `dominant-block` is an 8×8 square that outnumbers the background.
- The scene claims `field` and `apart` are not in the header: no `@claim` or `@relaxed` line denotes them, no rule text depends on them, and no branch replaces them (Style, Header).
- `$BlockByShape` takes one-color 4-connected components (`Components<Color>`) of non-background cells that have a same-colored cardinal neighbor. "More than one cell" is stated as "has a cardinal neighbor of its color", which gives the same set with no count. One-color components follow the analyze text "takes its own color as its block color".

## Judgments
- `@derive DominantColor: variant derived`: the line records the `derive` witness, which is train0 with 0 and 3 swapped. That is a color-permuted variant task, and its generator erases the dots to 3, as the derived branch does. The further witness `dominant-block` keeps the Analyze judgment `ordinary concept`, with no `@witness` line, per [Params](docs/handbook/solver-file.md#params).
- Cases: 8 `Choice` combinations × 2 `bg` branches. Of these, 6 are witnessed: `concept`, `$BlockByShape`, `$RayDot`, `$KeepBlock`, `bg=DominantColor`, and `$BlockByShape & bg=DominantColor`. `witness` reports no unseparated pair and no unshown case.
- `$OneBlock`, `background=RarestColor`, `background=SharedColor`, `block_color=DominantColor`, `block_color=RarestColor` and `block_color=SharedColor` get no branch. They fail Fit per `analyze.md`, which gives them no witness. `derive` lists only `bg=DominantColor`.
- `store` gives no line to add. `block[col]` is already stored as `block_color`. The other values vary by an id. `shapes.node` has no witness.
- Not formed: no item states a new model that needs a branch. The Euclidean-nearest reading is equivalent to the quarter cut. No odd-side rule is given. The `ex_out` proposers cannot run in `@derive`. Rectangles give the same output as squares.
- Determination: the sweep finds `bg` (0) and `block_color` (5) unique. The plan says these values are covered by proposers (`bg` DominantColor exact, `block_color` VanishedColor exact), and asks for a determination relation only where a proposer derives the value from a fact other than the concept's. The concept reads no further fact for either value, so no `Determine` comp is written.
- Hints: the case-section hints came from `// --- concept ---` over clauses that every case shares. They were fixed by markers that list `$StoredColor, $BlockByShape`. The common-subexpr hint on `quarter_cell` was fixed by the relation `block_inner`. The enumerator-name findings were fixed by the `_choice` names.
- Deletions: `diag_ray.cell` was removed, because `Ray.stop` does not read the domain. These are kept, because the pairs do not instantiate them: `dir_elem(D)` (the cardinal adjacency of a block), `!params.bg(Col)` in `diag_ray.blocked`, `!params.bg(Col)` and `!block(Pc, _, Col)` in `dot` (the dot's color claim), and the `$KeepBlock` rule.
- Performance: every run took under 15 s.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
