# d5d6de2d

## Departures
- Combinations dropped from `impl_choice` under Equivalence: `$PerObject` (with `$OwnHole`) together with `$Objects8`, and `$PerObject` (with `$OwnHole`, either adjacency) together with `$Enclose8`, in both `WallCells` branches. analyze.md gives these pairs as "the two branches' changes applied together". The models exist, but each one gives the output of the matching `$Whole` case on every input, at every assignment. The reason: the cells that block a walk around a closed-off region form one shape under the other adjacency. With a 4-step walk, the outer border of the region is 8-connected. With an 8-step walk, it is 4-connected, and so lies within one 4-component. A random search of 20000 grids up to 8x8 (scratch `eqcheck.py`) found no input that separates them, and found inputs that separate `$OwnHole & $Objects4` from `$Whole`. The case that takes more non-concept branches fails Equivalence. So the only per-object case that walks is `[$PerObject($OwnHole(), $Objects4()), $Walk4(), W]`. `$BboxInterior` and `$InsetBox` take `$Walk4` alone, as analyze.md states.
- The concept branch constructors take names of my own: `Whole` (hole-scope), `OwnHole` (object-region), `Objects4` (object-adjacency), `Walk4` (walk-adjacency) and `AnyInk` (wall-cells). The witness file keeps `concept` and the analyze.md branch names. `record --all` rewrote its groups into names of witnessed cases.
- The header leaves out the concept file's scene claim `shapes-apart`. No `@claim` or `@relaxed` denotes it, no rule text depends on it, and no branch replaces it, so Style#Header excludes it.
- The `$Objects8` branch keeps `@witness four-corners-missing: borderline concept`. On that witness the branch's model (per-object holes, 8-connected shapes) fills the hole, and the concept branch's model `$PerObject` fills nothing. But that model is no case of the solver (first departure), and `witness` reports "`$PerObject & $Objects8` and `$PerObject` give the same output or neither is defined". The finding is left in place: the witness and the audit both **fail** on this one finding. See Unsettled.
- `witness --file programs/reports/d5d6de2d/witnesses.json` says the names `$Objects8` and `outline_color=RarestColor` denote no case, so it compares nothing for them. `$Objects8` follows from the first departure. For `outline_color=RarestColor`, `record` resolves the name to `$WallOutlineOnly & outline_color=RarestColor`, which matches the analyze.md nesting. Every other group matches witnesses.json.

## Judgments
- Hint "enumerator name: `walked_scope` enumerates the `Choice` field type `HoleScope`": I removed that relation and the `hole_scope_choice` enumerator. `impl_choice` now lists the scope combinations directly in four clauses.
- Determination: the plan asked for determination relations for `background` (DominantColor), `fill_color` (a new output color) and `outline_color`. My first `outline_color` relation kept colors that no cell keeps, which reads inputs and outputs together. It drew the hint and gave {1, 2} with the `box-of-other-color` pair added. Now it keeps the color that every input holds and that is commonest in none, which is a fact of the inputs alone. After that the plan lists no actions. `background` and `outline_color` range over examples that have `ex_out` rows.
- Sweep: each parameter has a unique fitting value (0, 3, 2). There are no open parameters.
- `derive`: DominantColor fits `background` and RarestColor fits `outline_color`. Both are held as `@derive` lines (borderline concept, from witnesses.json), with `@relaxed background-field` and `@relaxed outline-shapes`. No derivation fits `fill_color`, and `store` reports nothing.
- Not formed (Develop step 3): no branch formed. Keeping the outline fails Fit at train0. A hole-size-dependent fill color would be a lookup table, and test0's 24-cell hole is a key no train pair holds (Unseen key). An input-only derivation of `fill_color` gives 0 or 2 and fails Fit at train0.
- `deletions`: 8 deletions change nothing, and I kept all of them. `leak.step` makes the 8-step walk of `$Enclose8`. `open(W, P)` in the `$OwnHole` fill clause keeps out cells of other shapes that one shape closes off. `train(E)`, `not_commonest`, `missing` and their negations make the determinations general beyond these pairs.
- Encoding: the concept uses `Closed` over the open cells, the relational form analyze.md gives. `$Enclose8` uses `Reach` with the eight step offsets, as a5313dff does. `$PerObject` uses `Closed<Shape>`, where each shape alone blocks the walk. `$BboxInterior` and `$InsetBox` use `Bbox<Shape>` with `inside` and `interior`.
- Witnessed cases: 9. Each run passes every train and test pair, and lint is ok. There are no performance issues: each run takes about 5 s. I built no witnesses. Every verdict is `concept` at `borderline`, with no `@reassigned`.

## Unsettled
- The audit's `$Objects8` finding (line 46). The docs allow a branch model that is not a case (the stand-in rule in Solver file#Cases), but the check seems to need that model held. Holding `$PerObject & $Objects8` brings back the Equivalence finding against `$Whole`. Two things could settle it: a tool fix that judges a branch witness against an unheld branch model, or a decision to reshape. The reshape would move `object-adjacency` under one branch that joins `$BboxInterior` and `$InsetBox`. There `$Objects8`'s model `$BboxInterior & $Objects8` is a case, and `four-corners-missing` separates it from `$BboxInterior`.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
