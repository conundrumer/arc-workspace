# e66aafb8

## Departures
- The solver has the concept case only. It has no constructor for `$AsymmetricMask`, `$MaskComponent`, `$DerivedSym`, `$DerivedCenter`, `$ModalImage` or `$AnyImage`, and no `@store` line for `$StoredCenter`: the Develop pace rule says that if no run has passed every pair at the end of the budget, the solver is cut to the concept case. No multi-case run passed every pair in time (see Unsettled).
- The witness file holds no witnesses: with one case, each witness of `witnesses.json` separates nothing once the names that denote no case are removed. Against `programs/reports/e66aafb8/witnesses.json`, the concept case gives the output the file gives it on every witness.

## Judgments
- `symmetry` stays stored at SYM_D4, and it is not an open parameter: the sweep finds that the train pairs also admit SYM_TB, SYM_HT, SYM_BOX, SYM_X and SYM_C4. `analyze.md` gives no open parameters, and its Not formed section says that these are values of `symmetry` that the determination, the largest subgroup every input keeps off the mask, rules out.
- Determine: `mask_color` is the color that every input holds and no output holds, since the plan lists VanishedColor. `symmetry` is the named subgroup equal to the D4 elements that `D4Map.conflict` does not break on any input's unmasked cells. The hint "determine prediction" on `symmetry` stays: the test reads the inputs and the determined `mask_color` only, and it reads no output cell directly.
- Lint hint `comp-idiom` (the hand-written conflict test is `D4Map.conflict`): taken. The finding `negated-use` on `output_color` and on `broken`: taken, so both relations are inlined.
- Deletions: removing `params.mask_color(C)` from `shared.item` changes nothing, because the crop to the mask box already keeps only masked cells. The atom stays because it states which cells the rule restores. `params.symmetry(S)` stays because it is the parameter the rule reads. With `sym_member` left free, it ranges over every subgroup, and that gives D4. `lacks`, the `inv` inputs and `!inv.conflict` stay because they state the determination. The pairs never hold a color that is absent from every output by chance, and they never hold an input that breaks an element.

## Unsettled
- Every branch of `analyze.md`: `$AsymmetricMask`, `$MaskComponent`, `$DerivedSym`, `$StoredCenter`, `$DerivedCenter`, `$ModalImage`, `$AnyImage`, and their combinations. To settle them, a pass with more Develop time writes them as cases. The design tried in this pass has these parts.
    1. It keeps one hypothesis per candidate mask color.
    2. For each hypothesis, it computes the broken elements on the visible cells.
    3. For `$DerivedSym`, it derives the group from the elements left unbroken.
    4. For `$AsymmetricMask`, it keeps the one color whose group breaks no visible pair and gives every masked cell a visible image.
    5. For each combining branch, it reads the images through `Unanimous`, `Mode`, or one copy per clear element. The copies sit in a `TiebreakResolution` column.
- `$DerivedCenter`: in the first design, it timed out at the runner's 20 s limit on every pair. That design generated candidate centers per axis from the axis reflections, which is a workaround for testing every center under every element, and it checked each square frame for every candidate mask color. To settle it, a cheaper enumeration of the centers is needed, or a lib relation that finds the center of a symmetry.
- `$StoredCenter`: the grid center is implicit in `apply`, so the program has no derived relation that a `@store` line could stand on. To settle it, `run_dl.py store` must be run on a solver whose center is an explicit relation.
- `[$AsymmetricMask, $MaskComponent, $DerivedSym]` emitted no output on any pair in the first design, so it fails Fit there. It is unsettled whether that is the model or a fault of that encoding.
- The derive and store survey for the concept case: the audit reports `derive: ok` and `store: ok`, so it holds no `@derive` or `@store` branch.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
