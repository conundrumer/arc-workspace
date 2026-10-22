# c35c1b4c

## Departures
- The solver has no `$Replace` constructor (and so no `Target` type), and the witness file has no `$Replace` group. The `damaged-left-half` separates text no longer names `$Replace`: `witness` found no input where `$OneWay & $Replace` is defined and differs from `$OneWay`, so that case fails Subsumption, as the Analyze report predicted. The run against `work/task/c35c1b4c/witnesses.json` reports `$Replace` as a name that denotes no case of the solver, on each witness, and it reports no other difference.

## Judgments
- The `Choice` is the record `[color: BlobColor, adj: Adjacency, source: Source, dir: Direction, axis: MirrorAxis]`, one field per choice point of the Analyze report that has a branch with a witness. `impl_choice` leaves out these combinations, which fail Equivalence:
    - `$CommonestColor & $Adj8` without `$BlobOnly` reads no region, so it is the model of `$CommonestColor` alone.
    - `$OneWay & $IntactHalf` is the model of `$IntactHalf` alone.
- There is no constructor for `$StoredBlobColor`, `$NearestAxis`, `$BothAxes`, `$BboxMidline` or `$HalfCopy`. The Analyze report gives none of them a witness, because each one fails Fit. `store` lists no `@store` point for the blob color, because its value differs between inputs.
- Not formed: neither item gives a case. The center-color reading gives no single color in train1. The enclosed-fill reading adds none of the cells that train1's output adds. Both fail Fit.
- Concept blob color: the color of the largest 4-connected region, from `Mode` and then `Unanimous` over the colors of the tied largest regions. So the concept is undefined only where largest regions of two different colors tie. `$BlobOnly` takes the largest region of the blob color, and it is undefined where two regions of that color tie.
- `$OneWay` reads its mirror axis from the axis of `params.source_side` (Relative orientation), and does not read `params.axis`.
- `derive`: no built-in derivation fits.
- `store` printed three lines: `intact.item`, `intact.value` and `unmatched` under `$IntactHalf`. Each one, when stored, fixes the axis to `params.axis`, so its case is the concept case and fails Equivalence. Each line carries an `@ignore ... store` line.
- Determine: `sweep` gives one value of `axis` (AXIS_H) and one of `source_side` (DIR_L). `determination-plan` lists both as `enumerable`, `pairs-exact`, and lists no relation to write. So the solver has no Determine comp.
- New witness `commonest-intact-half`, which `witness` needed so that a run shows `$CommonestColor & $IntactHalf` defined and differing from `$IntactHalf`. On a 6×8 grid, noise color 2 (15 cells) outnumbers a 14-cell blob of 1, and the cells of both colors are intact left of the vertical midline only. Plausibility `borderline`: the blob is small, and a noise color outnumbers it. Verdict `concept`.
- `deletions`: the atoms whose removal changes nothing are guards that the pairs do not test. These are the definedness guards in `out` and the `$BlobOnly` region tie, and `nearer` in the `$OneWay` paint, which `damaged-left-half` tests. `axis_of(D, Ax)` in `unmatched` stays, because it states which axis's mirror side D is on. The three bound enumerators stay.
- The header leaves out the `noise-field` and `blob-crosses-midline` scene claims. Per the Style section of the handbook, no `@claim`, `@relaxed`, rule text or branch depends on them.
- Keywords `symmetry repair objects noise rank color-class`: the blob is restored from its mirror (`symmetry`, `repair`). It is the largest region (`objects`, `rank`) on a noise field (`noise`). The concept mirrors every cell of the blob color, wherever the cell lies (`color-class`).
- Lint gave no hint. Every command finished in a few seconds.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
