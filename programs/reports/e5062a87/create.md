# e5062a87

## Departures
- `field_color=DominantColor` in the witness file: `analyze.md` sets the `field_color` point under `$NonFieldSeat`. In the solver, the `$ThirdColorShape` cases also read `field_color`, so the name alone denotes no case (the concept base does not read the field color). `witness --file programs/reports/e5062a87/witnesses.json` reports this for every witness and shows no other difference. `record --all` rewrote the groups in `programs/witnesses/e5062a87.wit.json` to names that have cases.
- `$MirrorCopies & $ExclusiveFits` is no case, and `impl_choice` excludes it. This combination fails Fit at train1: the L template and its top-to-bottom mirror overlap at their fits, so the exclusive rule drops the true fit.
- The concept branches take constructor names that `analyze.md` does not give: `$OwnOrientation`, `$HoleSeat`, `$OffShape`, `$AllFits`, `$WholeShape`, `$Join4`, `$StoredShape`.
- Witness `red-field` was added to resolve the unseparated pair `field_color=DominantColor` / `field_color=stored` under `$HoleSeat & $ThirdColorShape`. The input has a red field, a gray domino and black holes. With the derived field color, the domino stamps on the black pair. With the stored field color, the template is the red field, which fits nowhere. I judge it `variant` (it is the color-permuted task), with the verdict `$ThirdColorShape & field_color=DominantColor`.
- Witness `rarest-tie` was added to resolve the pair `$ThirdColorShape & field_color=DominantColor` / `$StoredShape & shape_color=RarestColor`. In the input, red and black tie for the rarest color. The rarest-color derivation takes both colors as the shape and paints nothing. `$ThirdColorShape` takes red and paints the black domino, as the concept does. I judge it `borderline` (a small grid with a count tie), with the verdict `concept`.

## Judgments
- `third_color` has `@ignore: store`: a stored third color is a stored shape color. So `$ThirdColorShape & third_color=stored` is equivalent to the `$StoredShape` case, takes more non-concept branches, and fails Equivalence.
- `paint_color` is held as a `@store` branch (`paint_color=stored`). The `store` command reports the line, and `analyze.md` gives it a witness.
- `@derive` lines for `field_color` (DominantColor) and `shape_color` (RarestColor) come from the `derive` command, with the plausibility and verdict from `analyze.md`.
- Hint "case section" on `params.mirror_axis` and `transform`: the `Occurrences` key now carries the `Orient` branch. With that key, the own-orientation cases read no mirror transform, and the hint does not fire.
- Hint "head-repeat" on `fit_cell`: `fit_cell` now names a fit by footprint id, transform and offset, not by the whole `FitKey`.
- Hint "determine prediction" on `Determine.field_color`: kept with `@ignore`. The field color is read from the evidence as the input color that remains after the painted color and the painted-over color are removed.
- In `$ExclusiveFits`, two fits are distinct only when their cell sets differ. A symmetric template's mirrored copy at the same place is therefore not a second fit.
- The whole-template footprint takes its id from a `Canon` class that holds every template cell, so the whole footprint and the per-object footprints share one key form.
- `params.identity` (D4_ID) stores the template's own orientation as a transform. All cases read it, and the sweep and the plan find it unique.
- `deletions`: 13 deletions change nothing on the pairs. Each removes structure that the pairs never instantiate: the mirror transform, the exclusive-fit clauses, seats on the template, the third-color tie, the shape-color exclusion from non-field seats, and the gate that makes `$ThirdColorShape` undefined. The witnesses exercise each of them, so all stay.

## Unsettled
- `identity` and `mirror_axis` have no determination relation. The plan lists them as pairs-exact by enumeration and names no proposer for them. A plan run that asks for a relation would settle this.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
