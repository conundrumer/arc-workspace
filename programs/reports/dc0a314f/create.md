# dc0a314f

## Departures
- The witness file has two more witnesses than `witnesses.json`, `pinwheel` and `overhang-stray`: without a `--file` argument, `witness` reported that no run showed `$GroupPerInput & $CellRestore` defined and differing from `$SymStored & $WholeBlockImage`, and that no run showed `$CenterStored` defined and differing from `$CenterFound`. Each new witness shows the first case defined and differing, so each case meets Subsumption and stays.
- `impl_choice` leaves out `$GroupPerInput & $ImageMajority` and `$CenterFound & $ImageMajority`: `analyze.md` gives each of these combinations as the model of `$GroupPerInput` alone or `$CenterFound` alone. Each one takes more non-concept branches than its equivalent, so it fails Equivalence. The solver has 16 cases, and 6 of them are witnessed.

## Judgments
- `pinwheel`, `variant $GroupPerInput`, `@relaxed symmetric-pattern`: the pattern has the four rotations and no mirror. It breaks `symmetric-pattern`. A variant task whose symmetry is the four rotations would restore from rotation images. That is the output of `$GroupPerInput`. The stored D4 and the whole-cover image are undefined on it.
- `overhang-stray`, `borderline $CenterStored`, `@relaxed symmetric-pattern`: this is `pattern-overhangs` with uncovered cell (1,2) recolored. The orbit of that cell holds no covered cell. A stray cell that breaks the symmetry is unusual for the generator. About the stored center, the cover restores.
- The stored center is `center_frame(ZERO)`: the square as a box in the grid frame, here the whole 16x16 grid, whose center is the corner shared by cells (7,7) and (8,8). The parameter holds no corner, because the pairs' grids are the whole square and every corner gives one center. `pattern-overhangs` and `overhang-stray` reassign `center_frame` to `[0, -2, 0, -2]`, the 16-cell square at the corner of the 14x14 grid, so `$CenterStored` keeps the witness that `analyze.md` gives it.
- The centers that `$CenterFound` tries are each cell and each 2x2 block of the grid. The 2x2 blocks come from a `Bbox` keyed by a cell and a diagonal neighbor. This range is equivariant and needs no literal. A center off the grid can't restore a cover, so it is left out.
- Every center branch acts through one `image` relation, which is keyed by the center choice and the square frame. The group acts in the frame's own coordinates, through `relative`, `apply` and `compose`.
- The `head-zero` hint on `frame_at($GridCenter(), ZERO)` has an `@ignore`: `ZERO` is the grid's own frame as a box, and no relation measures it.
- `store` printed `@ignore: store` for `frame_at` at `$CenterFound`, and the solver has that line: the candidate squares are each input's own cells.
- `cover_color` has `@ignore: derive`: `derive` found no built-in derivation that fits, and `analyze.md` gives each derivation as failing Fit at train0.
- The `determine prediction` hint on `symmetry` has an `@ignore`: its test reads the outputs only through the determined `cover_color`, which picks the uncovered cells.
- The `comp-idiom` hint in Determine is resolved: the clash test now uses `D4Map.conflict`.
- The `deletions` findings are structures that the pairs never instantiate. Examples are the integer-center squares, the defects of the whole-block and found-center tests, and the `in(P2, _)` filter. The solver keeps them. The `sym_size.domain` clause added nothing to `Tally`, so I removed it.
- Performance: the pairs run takes 1 s, and `audit` takes 44 s, most of it in `store`.

## Unsettled
- `center_frame`: its determination relation gives `ZERO`, the grid's frame, from the inputs' one extent, and reads no `params` relation. It holds no corner.
- `deletions` ran before the last Determine edits, which the pairs run's lint required. Those edits are in Determine only. A `deletions` run on the final file would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
