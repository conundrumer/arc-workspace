# b2862040

## Departures
- `other-color-ring`: the Analyze file says `shape_color=RarestColor` is undefined on this witness because the rarest color is tied. The solver's case recolors both rings, the same output as `$AnyInk`. This rests on the `RarestColor` proposer, which `derive` describes as "ties included". On a tie it gives both colors, so the case is defined. The Analyze file erred here. Its statement that `background=DominantColor` is undefined on a tie is wrong for the same reason, but no witness exercises that.
- `$HoleCountTable` stays as a case. The Analyze report says it fails Subsumption. The witness `two-hole-table` reassigns `count_color` to {0: 1, 1: 8, 2: 3}. On a shape with two holes, `$HoleCountTable` is then defined and gives 3, the concept gives 8, and `$OneHole` keeps 1. That witness has a `@witness` line under `$HoleCountTable` with `@reassigned count_color`.
- `$MinHoleSize` was added as a branch at the hole-condition point. It forms the Analyze report's Not formed item about a least hole size, as Develop step 3 requires. Its witness `one-cell-hole` reassigns `min_hole_size` to 2.
- `@derive TileDim` on `hole_count` was added as a branch. `derive` reports that it fits. Its witness `hole_count=TileDim` was written by `derive`.
- `@ignore: derive TileDim` stands on `min_hole_size`. On any grid with a hole, the derived values include 1 (d = 1, g = 0, n = the extent). Under `N >= K` the case then recolors the shapes the concept recolors, so its model is equivalent to the concept case's. It takes more non-concept branches, so it fails Equivalence.
- The concept branches have constructor names of my own: `$Shapes4`, `$Escape4`, `$OwnWalls`, `$ShapeInk` and `$AnyHole`. `record --all` rewrote the Analyze names in the witness file into case names.

## Judgments
- `@derive RarestColor` on `shape_color`: variant, derived, `@relaxed shapes`. The witness `derive` built swaps colors 1 and 0 in train 0. That is a color-permuted variant task, and the generator would recolor the closed ring of 0. At the stored `shape_color` of 1, the claim `shapes` is false of that input.
- `@derive DominantColor` on `background`: variant, derived, `@relaxed background-field`. The witness swaps colors 9 and 0, which is a color-permuted variant. Its field is 0, so `background-field` at 9 is false.
- `@derive TileDim` on `hole_count`: ordinary, concept. The witness is the two-hole-shape input. The derived set holds 2 on a 5x7 grid, so the derived case recolors the shape as the concept does, and `$OneHole` at the stored 1 keeps it.
- `one-cell-hole`: ordinary, concept. Train 1 already has a ring around a one-cell hole, and the concept recolors it.
- `two-hole-table`: ordinary, concept. A shape with two holes breaks no scene claim. The generator recolors every shape with a hole using `closed_color`.
- `rarer-ring` (built to separate `$AnyInk & background=DominantColor` from `$ShapeInk & shape_color=RarestColor`): borderline, concept. A second ink color breaks the invariant that inputs hold only `background` and `shape_color`. The concept recolors the ring of 1 alone.
- `two-hole-square-grid` (built to separate `$OneHole & hole_count=TileDim` from the concept): ordinary, concept. On a 9x9 grid, `TileDim` does not derive 2, so the derived case keeps the two-hole shape.
- Sweep: `min_hole_size` also admits 0. Nothing was added, because 0 and 1 never give different outputs: every hole has at least one cell. The sweep also lists 45 one-row additions to `count_color`, which are rows for counts no pair shows. Nothing was added: the concept does not leave the table's unseen keys open. Under `$HoleCountTable` they are unseen keys.
- Parse: the shape and hole machinery for every reading is in `Parse<Key>`, so `Determine` reads it over the examples. `count_color` is determined as the union over every reading, as the run's `determination: ok` confirms. Every `$HoleCountTable` case stores the same table, so the relation has no case column.
- Deletions: four `impl_choice` atoms were removed from `closing` and from the table's `out` clause, because every combination of fields is a case and the other atoms ground the fields. Some deletions change no pair output, and these were kept: the two 8-step `step` rules, which the `$DiagEscape` reading needs, and `dir_elem(D)` in `ink_holed`, which keeps the `$AllInk` adjacency 4-way as the Analyze report states it. The pairs never instantiate a hole that meets the outside only at a corner, or one that meets a shape only diagonally.
- The scene claim `some-shapes-closed` is left out of the header. No `@claim` or `@relaxed` line denotes it, no rule text depends on it, and no branch replaces it.
- Keywords: `count` and `lookup` are added for `$OneHole`, `$MinHoleSize` and `$HoleCountTable`.
- Not formed items:
    - The proposers that read `ex_out`, and `CountRankAsc`/`CountRankDesc`, are not listed by `derive`, so no branch holds them.
    - Filling the holes in place of the shapes fails Fit, because every hole cell keeps `background` in every output. No case takes it.
- `$HoleWallOnly` fails Fit and has no witness, so it has no constructor. `closed_color=OutNewColor` fails Fit, and `derive` does not list it.

## Open
- none

## Lib
- Closed with 8-step escape, as an extension of `Closed`. The cells that no 8-step walk from the frame edge reaches, grouped into 8-connected regions. The solver-local form is in `Parse`, as `own_open8` and `own8`, and as `ink_open8` and `ink8`: a `Reach` with `step(V) :- step_offset(_, V)`, seeded at the frame edge, and then `Components8` over the unreached cells. Other sites with the same flood: `programs/solvers/aa4ec2a5.dl` (`open8`, `own_open8`), `programs/solvers/a5313dff.dl` (`leak`) and `programs/solvers/ac2e8ecf.dl` (`own8`).

## Fixes elsewhere
- none

## Tickets filed
- none
