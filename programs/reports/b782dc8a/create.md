# b782dc8a

## Departures
- `wall` is a `Params` parameter that every case reads, not a scene parameter: the program finds the seed as the cells of neither `wall` nor `background` color, so the seed reads `wall`. The Analyze report's Not formed item says the concept's rules never read `wall`, but its own `probe.py` reads `WALL` to find the seed.
- The seed is the cells of neither `wall` nor `background` color that touch another such cell. This matches the seed in `probe.py` (a 4-connected cluster of more than one such cell). The `flood-seed-region` rule text states it. With every such cell as a seed, the concept would be undefined on `stray-color`, where the Analyze file gives it a grid.
- `$PassNonWall` reads `background` to find the seed. The Analyze report says that branch reads no `background`. Its outputs on every pair and witness are the ones the Analyze file gives.
- `wall=DominantColor` is held as a `@derive` branch (`variant derived`), and only for the bases that take `$SeedParity` or `$PathParity` with `$PassBackground`. The Analyze report has it failing train1. In this program, that failure happens only under `$PassNonWall` (the train1 tie makes 0 a wall, so the walk passes through no cell) and under `$CenterParity` (the tie makes the arm at (9,5) a second center). Each failure has an `@ignore: derive` line. The other bases read `wall` only to keep it out of the seed, so the tie changes nothing there.
- `record --all` rewrote the witness file's groups to the fewest names, for example `$Flood4` in place of `concept` on `diagonal-corner`. The grids did not change.

## Judgments
- Row+column parity is encoded as a `Canon` class over two-step walks between grid cells. This needs no arithmetic and agrees with row+column parity on every grid larger than 1×1.
- `$PathParity` is encoded as a `GraphDistance` over (cell, seed color) nodes. Each step changes to another seed color in scope, and the colors at the least distance to a cell are the colors its nearest seed cells give it. Because no parity arithmetic is needed, the encoding also runs under `$Flood8`. The run shows that `$Flood8 & $PathParity` fails every pair, as the Analyze report says, so `impl_choice` leaves it out.
- "Undefined where the seed has other than two colors" (`$PathParity`, `$CenterParity`) comes from "the seed's other color": with three or more colors, a cell takes two colors and the grid is not total. With one color, the cell takes none. This is not exact: a three-color seed whose painted cells all take the nearest seed cell's own color would give a defined output. A seed's arms put cells at odd distance next to them, so no generator input reaches this.
- "More than one center" (`$CenterParity`) is stated by `two_centers`, a pair of distinct centers in one cell's scope.
- The cases are the 20 bases (`$Flood8 & $PathParity` left out) and the 6 bases that also take `wall=DominantColor`. Seven of them are witnessed. The combinations of two or more non-concept branches give no output on any task or witness input that some case with fewer of those branches does not also give. `witness` and the audit report nothing unseparated.
- `wall=DominantColor` witness (train0 with 8 and 1 swapped): a color permutation of a train input, so `variant`. The generator pairs it with the recolored output, which is the derived branch's output, so `derived`.
- Not formed: distance parity read from the center is `$CenterParity`'s model, so it would fail Equivalence and gets no branch. `derive` lists no `ex_out` derivation of `background`. The item on `wall` as a parameter is moot because `wall` is now a parameter. Wider corridors change no claim.
- `$FillAll` and `$StoredPaint` fail Fit (train0 and train1, as the Analyze report gives) and have no witness, so they get no constructor.
- From `deletions`: I dropped `in(Q, _)` from `parity.edge`, `reading(R)` from `class_paint.item`, and the `system` atom from `walk.seed`, and folded `reading` into `walk.seed`. The atoms the pairs do not need and that I kept state the model's structure off the pairs: the seed's ink-neighbor test, 4-neighbor restrictions, `two_centers`, the walk staying on flood cells, and seed cells left unpainted.
- Keywords: `flood` and `parity`.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
