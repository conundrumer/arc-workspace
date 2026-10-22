# b190f7f5

## Departures
- The concept case cuts the input into squares whose side is the input's extent across the cut axis (`divide_by_size_slab`), and not into two halves along the long axis as `probe.py` does: the concept file's `two-square-halves` claim states two n×n squares, and this reading needs no stored count. On generator inputs the two readings agree. On an input whose halves are equal rectangles, the concept case is undefined, so the Analyze report's Not formed item "one program serves both" does not hold for this solver.
- Branch `$EqualHalves` (point `split`, concept branch `$SquareHalves`) is added from that Not formed item: two equal halves along the long axis, read with `half_count` 2. Witness `rectangle-halves` (3x8 input, 3x4 halves): borderline, verdict `$EqualHalves`, `@relaxed two-square-halves`.
- The case of `$MonoTemplate` with `$WholeHalf` is excluded through `impl_choice` under Subsumption (its output is that of `$FewerColorsTemplate` with `$WholeHalf` wherever it is defined), as the Analyze report gives. `$MonoTemplate` with `$TemplateBbox` stays: on `empty-pattern` it gives a 6x6 background grid where `$FewerColorsTemplate & $TemplateBbox` takes the empty half as the shape and is undefined. The Analyze report drops `$MonoTemplate` as a whole.
- The concept branches take my own names: `$SquareHalves`, `$OnlyTemplateColor`, `$WholeHalf`. The witness file's `concept` groups are rewritten to these names by `record --all`.

## Judgments
- The concept case takes as the shape the half that holds `template_color` and no other non-`background` color, and as the pattern the other half; two such halves leave no pattern half, so the model is undefined there. The shape's cells are read as the half's non-`background` cells, which within that half are its `template_color` cells, so one `shape_ink` clause serves every `Template` branch.
- `two-color-shape` (built): separates `$MonoTemplate` from `$FewerColorsTemplate`. Plausibility borderline (the shape in two colors breaks `template-half`), verdict `$FewerColorsTemplate`.
- `one-color-pattern` (built): shows `$OnlyTemplateColor & $TemplateBbox` defined and differing from `$MonoTemplate & $TemplateBbox`. Plausibility ordinary, verdict `concept`.
- `empty-pattern` (built): shows `$MonoTemplate & $TemplateBbox` defined and differing from `$FewerColorsTemplate & $TemplateBbox`. Plausibility foreign (no input has an empty pattern half), verdict `any`.
- `derive` found no built-in derivation that fits, and `store` printed no `@store` line (it reported `shape_box.box` constant with no witness), so no `@derive` or `@store` branch is held.
- Not formed items left unformed: the shape found by colors absent from the output reads the output, which a test input does not have, so it has no relational form over the evidence a test gives; `PanelCombine` overlay fails Fit (the output is n²×n², not a half's frame); the other `template_color` and `bg` derivations are covered by `derive`, which found none that fits.
- Determine: `sweep` gives one value per parameter, and `determination-plan` lists no actions, so the solver has no `Determine` comp.
- `deletions`: the 9 deletions that change no pair are kept. `impl_choice` in `out` excludes the subsumed case. `off_template`, the negations in `shape_half` and `colors.item`, and `colors.domain` decide outputs on the witness inputs. `shape_half` in the `$TemplateBbox` `block` clause is implied by the box's frame, and is kept because it states that the box lies in the shape's half.
- `N < N2` over two `Tally` counts and `N1 > N2` over the two extents for the long axis are comparisons; lint accepts them.

## Open
- The verdict `$MonoTemplate` on `template-in-other-color` denotes the model `$SquareHalves & $MonoTemplate & $WholeHalf`, which is no case after the exclusion; the case that stands for the branch is `$MonoTemplate & $TemplateBbox`, which gives the same grid on that witness. `witness` accepts it. A reviewer could settle whether the verdict should name `$MonoTemplate & $TemplateBbox`.

## Lib
- The long axis of the frame: `axis_dims(P, A, N1, N2), N1 > N2` in `half($EqualHalves(), ...)`. The grep finds the same shape in 291dc1e1 (line 126, `axis_dims(P, A, N1, N2), N1 < N2`; line 71 over `box_extent`) and 689c358e (line 49, over `box_extent`).

## Fixes elsewhere
- none

## Tickets filed
- none
