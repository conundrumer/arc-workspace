# d0f5fe59

## Departures
- `diagonal` is stored as a `DiagAxis` (`DAXIS_DG`), not as the corner `DIAG_TL` that the concept file's wording ("from the top-left corner") suggests: the audit's relabelings check found that a half turn or an anti-diagonal mirror of a stored `DiagDir` changes no output, because in a square the diagonal from TL is the same as the one from BR. The diagonal axis is the entity the rule reads, and `Diagonal` gets both of its corners through `diag_axis_of`.
- `mark_color=stored` from `analyze.md` is the `@store value` line on the `mark_color` instance (`Unanimous`, the one ink color). In the witness file it is renamed `mark_color.value=stored`, as Develop step 5 requires. `analyze.md` had no constructor for it, so its outputs are the same as `witnesses.json` gives. The `witness --file programs/reports/d0f5fe59/witnesses.json` run prints only that the old name denotes no case.
- New branch `shape_color=RarestColor` (`@derive RarestColor` on `$ShapesOfOneColor`'s `shape_color`): `derive` reported it as fitting, and Develop step 4 holds it. It is not in `analyze.md`.

## Judgments
- Choice shape: `Choice = [adj: Adjacency, cells: ShapeCells, counted: Counted]`, with `MarkColor` as the field of `AllInk`. `analyze.md` says the `mark color` property exists only under the concept branch of `shape cells`. The concept constructors are named `CornerAdjacency`, `AllInk`, `ShapeColor` and `EveryShape`.
- `$CongruenceClasses` and `$CountTable` have no constructor: they fail Fit at test0, and `analyze.md` gives them no witness.
- No item under Not formed was formed. The cell-count, color-count and fixed-size readings are each refuted by the pairs, and the anti-diagonal is the stored `diagonal`, not a branch.
- `@derive DominantColor` on `background`: plausibility `variant`, verdict `derived`, `@relaxed shapes-on-background`, as `analyze.md` gives for `background=DominantColor`.
- `@derive RarestColor` on `shape_color`, `variant derived`: I built this judgment. The witness is train0 with its shapes in 1. A color swap is a variant task and breaks no scene claim, but every shape in the evidence is 8, so it is `variant`, not `ordinary`. The generator would mark the diagonal in 1. The concept and the derived branch give that, and stored `shape_color` 8 is undefined.
- `@store value` on `mark_color`: `variant concept`, as `analyze.md` gives.
- `store` hints were dismissed with `@ignore`:
    - `ink[col]`: a stored ink color is the `$ShapesOfOneColor` branch.
    - `mark_color.item`: stored items give the value that `value=stored` stores.
    - `mark`: storing it is `mark_color.value=stored`, or under `$CommonestShapeColor` a model equivalent to that one.
    - `commonest.item` and `commonest.mode`: storing either under `$CommonestShapeColor` gives a model equivalent to `mark_color.value=stored`, and that case takes more non-concept branches, so it fails Equivalence.
- The `store` hint "make it a parameter" for `mark_color.value` was not followed for the concept: the concept file and `analyze.md` take the mark color as derived from the input, and the stored reading is the `mark_color.value=stored` branch.
- Case-section lint hints after I removed a marker over shared code: the `shape_cell` and `shape` clauses were regrouped under `$AllInk`, `$ShapesOfOneColor`, `$CornerAdjacency` and `$SideAdjacency` markers, and the hints cleared.
- Determination: I wrote `background` (commonest color of every train input) and `shape_color` (rarest color of every train input), as the plan listed. `diagonal` is left to the built-in enumeration. The plan lists it with no proposer, and the pairs fix it to `DAXIS_DG`. The sweep found each parameter's value unique.
- `deletions`: removing `uneven` / `not_rarest` and their negations changes nothing on this task's pairs. The pairs never exercise these universals (every input shares its commonest and rarest color), so they stay.
- The solver uses `Components8` / `Components` for the adjacency branches, `Unanimous` and `Mode` for the mark color, `Tally` for the count, and `Bbox` + `crop` + `KeyedSetCompare` + `Canon` for forms up to translation, following 00dbd492's Determine. The output uses `Frame2D` and `Diagonal`, following 3b4c2228.
- The final run passes all train pairs and test0 with 8 witnessed cases. Lint, `witness`, and the audit (witness, dropped cases, derive, store, open values, relabelings) are all ok. The audit skipped no check. No performance issue was seen: every run finished in 10 s or less.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
