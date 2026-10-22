# b190f7f5

## Departures
- The concept case cuts the input into squares whose side is the input's extent across the cut axis (`divide_by_size_slab`). It does not cut the input into two halves along the long axis as `probe.py` does. The concept file's `two-square-halves` claim states two n×n squares, and this reading needs no stored count. On generator inputs the two readings agree. On an input whose halves are equal rectangles, the concept case is undefined, so the Analyze report's Not formed item "one program serves both" does not hold for this solver (create.md). Judged in this pass: the departure holds. What it rests on is true, and the `rectangle-halves` witness separates the two readings.
- Branch `$EqualHalves` (point `split`, concept branch `$SquareHalves`) is added from that Not formed item: two equal halves along the long axis, read with `half_count` 2. Witness `rectangle-halves` (3x8 input, 3x4 halves): borderline, verdict `$EqualHalves`, `@relaxed two-square-halves` (create.md). Judged in this pass: the departure holds. The case fits every pair, has a relational form, and `rectangle-halves` shows it defined where `$SquareHalves` is undefined, so it meets Equivalence and Subsumption.
- The case of `$MonoTemplate` with `$WholeHalf` is excluded through `impl_choice` under Subsumption, as the Analyze report gives: its output is that of `$FewerColorsTemplate` with `$WholeHalf` wherever it is defined. `$MonoTemplate` with `$TemplateBbox` stays: on `empty-pattern` it gives a 6x6 background grid, and `$FewerColorsTemplate & $TemplateBbox` takes the empty half as the shape and is undefined. The Analyze report drops `$MonoTemplate` as a whole (create.md). Judged in this pass: the departure holds. `witness --every-case` reports the dropped case failing Subsumption against `$FewerColorsTemplate`.
- The concept branches take their own names: `$SquareHalves`, `$OnlyTemplateColor`, `$WholeHalf`. The witness file's `concept` groups are rewritten to these names by `record --all` (create.md). Judged in this pass: the departure holds, because the Analyze report gives the concept branches no constructor name.

## Judgments
- The concept case takes as the shape the half that holds `template_color` and no other non-`background` color, and as the pattern the other half. Two such halves leave no pattern half, so the model is undefined there. The shape's cells are read as the half's non-`background` cells, which within that half are its `template_color` cells, so one `shape_ink` clause serves every `Template` branch (create.md).
- `two-color-shape` (built): separates `$MonoTemplate` from `$FewerColorsTemplate`. Plausibility borderline (the shape in two colors breaks `template-half`), verdict `$FewerColorsTemplate` (create.md).
- `one-color-pattern` (built): shows `$OnlyTemplateColor & $TemplateBbox` defined and differing from `$MonoTemplate & $TemplateBbox`. Plausibility ordinary, verdict `concept` (create.md).
- `empty-pattern` (built): shows `$MonoTemplate & $TemplateBbox` defined and differing from `$FewerColorsTemplate & $TemplateBbox`. Plausibility foreign (no input has an empty pattern half), verdict `any` (create.md).
- `empty-pattern`'s `separates` text is rewritten. The old text said the fewer-colors reading is undefined, but its group `$FewerColorsTemplate` (the case with `$WholeHalf`) gives a 9x9 background grid. Only the case with `$TemplateBbox` is undefined.
- The verdict `$MonoTemplate` on `template-in-other-color` stays, which settles create.md's open item. A `@witness` verdict denotes the branch's model whether or not `impl_choice` holds it. The case that stands for the branch is `$MonoTemplate & $TemplateBbox`, which differs from the concept case at the fewest points.
- `derive` finds no built-in derivation that fits. `store` prints no `@store` line: it reports `shape_box.box` constant with no witness. So no `@derive` or `@store` branch is held (create.md; rerun in this pass with the same result).
- Not formed items left unformed (create.md):
    - The shape found by the colors absent from the output reads the output, which a test input does not have.
    - The `PanelCombine` overlay fails Fit, because the output is n²×n² and not a half's frame.
    - The other `template_color` and `bg` derivations are covered by `derive`, which finds none that fits.
- Determine: `sweep` gives one value per parameter, and `determination-plan` lists no actions, so the solver has no `Determine` comp (create.md; rerun in this pass with the same result).
- Simplify: `$MonoTemplate` reads its one-color half from the lib's `Unanimous` (`sole_color`), in place of the local `mixed` clause. A shared `half_color` relation now feeds `off_template`, `sole_color` and `colors`. `$OnlyTemplateColor` keeps `off_template`. A tried reading of it as `sole_color.value` equal to `template_color` gives the same output at a single stored color. But at a set of colors it changes the model: `derive` then reports `template_color=SharedColor` and `template_color=VanishedColor` as fitting, so the change was taken back.
- `deletions`: 7 deletions change no pair, and all are kept. `impl_choice` in `out` excludes the subsumed case. `off_template`, the atoms of the `$OnlyTemplateColor` `shape_half` clause, and `colors.domain` decide outputs on the witness inputs. `shape_half` in the `$TemplateBbox` `block` clause follows from the box's frame, and is kept because it states that the box lies in the shape's half (create.md).
- `N < N2` over two `Tally` counts and `N1 > N2` over the two extents for the long axis are comparisons, and lint accepts them (create.md).
- Prune: the `$EqualHalves` `@scene` line now also says that the case is undefined on a square input.

## Open
- none

## Lib
- The long axis of the frame: `axis_dims(P, A, N1, N2), N1 > N2` in `half($EqualHalves(), ...)`. The grep finds the same shape in 291dc1e1 (line 126, `axis_dims(P, A, N1, N2), N1 < N2`; line 71 over `box_extent`) and 689c358e (line 49, over `box_extent`) (create.md).

## Fixes elsewhere
- none

## Tickets filed
- none
