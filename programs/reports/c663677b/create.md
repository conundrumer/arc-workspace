# c663677b

## Departures
- `$WitnessedMirror` excludes the identity from the `Wallpaper` transforms (`d4_compose(T, U, V), U != V`): with every `d4_elem` as in 0dfd9992, `Wallpaper` also takes the identity with each shift of a coset as a candidate. These candidates are the oblique translations, so the branch filled `oblique-stripes`, where the Analyze file gives it undefined. The branch's claim names reflections and rotations only.
- The lib's `Wallpaper` counts a candidate as witnessed where it takes some grid cell onto another grid cell of the same color, even where it fixes the tile class. The Analyze model asks that the class itself move. On every Analyze witness the two readings agree. They differ only where a reflection takes every unblanked off-diagonal class onto a blank class, and there the lib reading merges the classes and the Analyze reading does not.
- `$ClassMode` is undefined where two tiles tie for least area. The Analyze model takes the tile with fewer rows. That tiebreak picks an axis, so it is a hidden orientation. No pair or witness has a tie.
- `$ClassMode` finds its candidate tiles at all four corners (`tile_place`, keyed by `DiagDir`), as 29ec7d0e's `phase` does. A class is a cell's distances to the corner's two edges, each taken modulo the tile's extent on its axis. Every corner gives the same partition, so the corner is not observable.
- `$StoredMirror` merges each cell with its image under `params.mirror` (D4_DG) in the grid frame. It is undefined where that image is off the grid or where the two periods differ. On a square grid, D4_DG in the grid frame is the tile's reflection through cell (0,0) on its torus, which is the Analyze model.
- Under `period=stored`, `$HoleFromPeriod` still picks its hole color by the least-area tile of `shifts.min_period`, and only the fill reads the stored periods. The Analyze text gives that combination as the color that leaves the unblanked cells consistent under the stored periods. The `@store` line replaces `period` alone, so no other relation changes.
- The `@scene periodic-pattern` line adds the period derivation that the Analyze report's `period` concept branch gives ("the shortest shift under which the unblanked cells agree"), because `period=stored` replaces that derivation.
- Two witnesses are added that the Analyze file does not hold, `blank-majority` and `contradicted-mirror` (see Judgments).

## Judgments
- Choice structure: `Choice = [d: Damage, p: Periods, i: Isometry]`. The `repeat` point has no formed branch besides its concept branch, since `$MirrorOnly` fails Fit, so `period` (`Periods`) and `isometries` (`Isometry`) are fields at the top level. There are 18 bases, and each base reads `period`, so with the `@store` branch there are 36 cases, of which 7 are witnessed.
- Concept branch names: `StoredHole`, `AxisShifts`, `Translations`.
- The period classes come from a `Wallpaper` instance with no transform rows. Its `action` then gives the translation classes alone. The mirror branch reuses the same component with transforms, as 0dfd9992 does.
- `shifts` (`OffsetInvariance`) is keyed by `[Damage, Color]`. With a key of `Color` alone, the linter found the `$StoredHole` key feeding `$HoleFromPeriod`.
- The `hole_color` derivations: `derive` reports that none fit, which matches the Analyze report (all fail Fit).
- `store` printed two values: `period`, held as `period=stored` with `// @store: variant concept` from the Analyze witness, and `shifts.min_period`, dismissed with `@ignore min_period: store`. When stored, `shifts.min_period` gives `$StoredHole` the periods that `period=stored` gives, which is an equivalent model. It gives `$HoleFromPeriod` the same tile for every color, so the hole color ties and the model is undefined on every input (fails Fit).
- Determination: `hole_color` is the color the outputs change (`ChangedColor exact`, per the plan). `mirror` is the diagonal reflection under which the most train outputs are symmetric (a `Mode` over examples). Under "every output", the plan refused `asymmetric-tile`, and under "some output" it refused `sparse-dots`, which is symmetric under both diagonals.
- Sweep: `mirror` also admits D4_ID, which merges nothing and is the concept. No reader of `$StoredMirror`'s claim takes it, so it is not an open value and is not stored.
- Not formed, separator panels: the panels the uniform lines cut do not repeat one another, so that model fails Fit at train0. It is not formed.
- Not formed, every cell takes its class color: I tried it during Simplify (the deletion report found that `in(P, C)` changed no pair). It is equivalent to the concept under the axis periods, as the Analyze report says, so it fails Equivalence against the concept case. Under `$StoredMirror` it is not equivalent: there, a merged class that holds two colors and no blank cell becomes undefined (`contradicted-mirror`). The keep-unblanked fill stays.
- Witness `blank-majority`: a 3x3 tile on a 9x9 grid, where five 2x2 holes blank five of the nine copies of four tile cells. `$HoleFromPeriod` and the concept restore the tile. `$ClassMode` keeps the holes 0. Plausibility `variant`: the holes cover 20 of 81 cells, which breaks the invariant of at most 12%, and the witness breaks no scene claim. Verdict `concept`. It answers the report that no run showed `$HoleFromPeriod` defined and differing from `$ClassMode`.
- Witness `contradicted-mirror`: a 3x3 tile that is symmetric about its main diagonal except for the pair 3/7, with every copy of tile cell (0,1) blank. `$StoredMirror` fills that cell with 2. `$WitnessedMirror` finds the reflection contradicted and is undefined, as the concept is. Plausibility `borderline` with `@relaxed each-class-seen`. Verdict `$StoredMirror`: the nearly symmetric tile makes the mirror cell the best reading of the hidden cell. It answers the report that no run showed `$StoredMirror` defined and differing from `$WitnessedMirror`. A symmetric tile cannot separate the two, because the lib takes any uncontradicted reflection as witnessed.
- Hints: `blank` and `oblique_shift` (single-consumer) were inlined. `common-subexpr` on the two Excess feeds was resolved with `tile_vote` and `orbit_vote`. `head-zero` on `short_step` was resolved by taking each component's length from `dist`, so the zero shift is measured. The case-section hints were resolved by rekeying `shifts`.
- Deletions: these were judged to stay because the pairs do not instantiate them: the branch clauses and guards (`broken`, `aperiodic`, the oblique and mirror clauses), the self edges of `orbit` (a cell with no partner under the period translations on a grid less than twice the period), and `tile_cand.a`, which keeps the two axes of a tile apart. Removed: `periodic.cell` (the translation action does not read cells), the two `Tally` domains (every key has a member), and `impl_choice` in two `$ClassMode` clauses (`orbit.id` binds the case).
- Performance: a solver run takes about 27 s. On its first run after a change, the store part of `audit` takes about 180 s, so `audit` passes 240 s and was run in the background. Four `deletions` runs on `tile_place` and `tile_vote` timed out at 40 s, and no finding rests on them.

## Open
- The lib's `Wallpaper` witness test (a cell moves) and the Analyze model's (a class moves) differ, as Departures gives. A witness where a reflection takes each unblanked off-diagonal class onto a blank class would show the difference: settle whether `$WitnessedMirror` follows the lib or the Analyze reading.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
