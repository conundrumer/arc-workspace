# e78887d1

## Departures
- The solver has no `band-axis` parameter. The axis the bands run along is the axis of `shift_dir`, and the axis they stack along is the axis of `band_dir`: [Stored or derived](docs/handbook/principles.md#stored-or-derived), "Redundant value".
- The solver adds `band_sense` (SENSE_CC), and derives `band_dir` (DIR_B) from it in Params by `turn`. The concept's Parameters do not list it. The "last band" and "first band" need the direction from one band to the next, and that direction is task data under D4. It is always perpendicular to `shift_dir`, so it is stored as a Sense: [Params style](docs/handbook/style.md#params), "Relative orientation".
- The concept's `background` parameter is `bg` in the solver. In the witness file, `background=DominantColor` is now `bg=DominantColor`, both as a group name and as a witness id. `witness --file programs/reports/e78887d1/witnesses.json` reports only that name as a difference.
- `$StepFromBandsOrStored` is undefined where more than one cyclic move takes each band onto the next. In `analyze.md`, that model would give one grid per move. The `out` column that holds alternatives is the `TiebreakResolution` that `$PermutationFromBandsOrStored` uses, and that type cannot hold a cyclic-move count. So the moves merge into one `$End` key, and their facts conflict. The new `@rule` line for that branch says this.
- The new witness `patterns-repeat` (ordinary, verdict `concept`) separates `$StepFromBandsOrStored` from `$PermutationFromBandsOrStored`. Two slots hold one pattern, so two permutations fit and one cyclic move fits. The permutation case gives two grids, and one of those grids is the concept's. No scene claim breaks.
- `shift_step=SepThickness` is held as a `@derive` branch (variant, verdict `concept`). `derive` reports that it fits: the separator thickness and the step are both 1 on every input. The witness `shift_step=SepThickness` reassigns `gap` to 2. On that input, the concept moves the patterns 1 slot and the branch moves them 2 slots. The generator moves the patterns by its step, and the gap width does not set that step.
- The cases that take `gap=stored` and `shift_step=SepThickness` leave under Subsumption, by `@ignore: derive gap=stored` under the `shift_step` `@derive` line. `witness` reported no run that shows them defined and different from `gap=SepThickness & shift_step=SepThickness`. A probe grid that had a blank glyph edge column did not separate them either.

## Judgments
- The task is not a nested task, so `induce` is not in `@keywords:`, and the solver has no `DemonstratedChoice`. Train 2's input holds one band, so it holds no demonstrated pair. Also, the concept stores the move. Only `$StepFromBandsOrStored` and `$PermutationFromBandsOrStored` read the move off the bands, and both fall back to the stored move.
- The determination of `shift_step` keeps the step counts that take the last band's patterns onto the train output's patterns. It has `@ignore: determine prediction`, because that comparison is the fact `next-band` states. A first version read the step from consecutive input bands. With witness `bands-unrelated` added, that version lost the stored value, so the plan rejected it.
- `bg` is determined as the one color of the grid's edge line toward `band_dir`. `gap` is the distance from that edge to the nearest pattern cell. `glyph_size` is the output's extent across the bands. `shift_dir` and `band_sense` keep the runner's fit over the values of their types: 1 of 8 joint assignments reproduces every train pair.
- Sweep: `shift_step` 13 also fits, because 13 moves round the 3-slot and 4-slot cycles act the same as 1 move. No reader of the concept takes 13, so it is not an open value.
- Hint "parse unshared with determine": resolved. `Determine` now reads `Parse<Example>`, and the slot cycle and the step misfit test moved into `Parse`.
- Hint "circular determination" (Parse read `params.shift_step`): resolved. The stored step's `slot_cycle.step` fact is now added at program scope.
- Case-marker hints: resolved by moving the shared relations above the markers, and by marking the `landing` and `color_band` clauses with the `$LastBand` and `$LandingSlot` constructors.
- `deletions` listed 19 deletions that change nothing on the pairs. All are kept. They are clauses that only the non-concept step sources exercise distinctly (`next_band`, `stacked`, `unlike`, `step_misfit`), or atoms that fix the frame the program works in (`last_band`, `band_dir`, `color_band`'s band). On these pairs, the bands have equal frames and equal slot colors, so those atoms make no difference.
- Develop step 3: the one item under Not formed (the output is the first band again) states no model of its own, so no branch was formed for it.

## Unsettled
- The determination relations for `shift_dir` and `band_sense`: the plan's last run asks for a relation where a proposer derives the value from a fact the concept does not use. The pass kept the fit over the values of the types. A relation that reads the direction off the last band and the output would settle it.

## Concept faults
none

## Fixes elsewhere
none

## Tickets filed
- none
