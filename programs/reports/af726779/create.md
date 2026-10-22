# af726779

## Departures
- The solver adds the branch `$EvenColorRarest` (the even levels take the input's rarest color) and the choice point `Scope` with the branch `$Pooled`, and the witness file adds the witnesses `mixed-base` and `two-lines` for them: Develop step 3 forms each Not formed item that meets Fit and Relational form. The RarestColor item and the pooled-marks item both fit every pair, and each has a set of clauses.
- The witness file drops the Analyze witness `background=DominantColor` (a background of 1). `derive` recorded its own witness for that branch under the same id (train 0 with 3 and 0 swapped), and the Witness step removes a `@derive` branch witness that duplicates the one `derive` records.
- The groups of `base-color-2` name the concept case `$Parity` and add `$EvenColorRarest` beside `$EvenColorOfBase`. These come from `record --all` over the solver's cases. `witness --file work/task/af726779/witnesses.json` reports no difference.

## Judgments
- Parameter names follow the concept file: `background`, `growth_dir`, `level_step`, `level_colors`. `level_colors` is keyed by parity (0 → 7, 1 → 6). A level's parity is its index walked around the cycle that `IndexCycle` builds over the stored parities, with `CycleWalk` doing the walk. `$ColorBySuccession` stores its own `level_succ` {7→6, 6→7} and walks it from the color of the base marks.
- Levels are iterated by `Propagation`, with one join per gap: the marks on the two cells beside G make the mark `level_step` lines past G. The test "no mark on G" reads only the input marks of the stack. A level that gap-mark makes never has two adjacent marks, so on every input this is the concept's test. The solver comment states this. A level index is the fewest join steps from an input mark (`GraphDistance` over the marks).
- Stacks are keyed by their box (`Stack = [s: Box, sc: Scope]`). `$PerLine` keys one stack per line across `growth_dir`, so marks of different base lines never pool, as the concept reads `gap-mark` per level. `$Pooled` keys one stack on `ZERO`, the whole frame. At first the Scope clauses fed a shared relation that both scopes read, and lint flagged that as a case-section problem. Putting the scope into the key fixed it.
- The stack derivation is in `Parse<Key>`, because the Determine comp repeats it to find each train mark's level.
- `$Pooled` rule text gives what the program runs: one pool of every input mark and every new mark, with the gap test against input marks only. On every input the generator produces (one marked line), this agrees with a pooled reading. So the text is the program's rule, and no `@approximated:` line is needed.
- Witness `two-lines` (a second marked line four rows below the first): `borderline $Pooled`, relaxing `background` and `base-line`. A person, or a generator that applies the gap rule row by row, would read row 5 as one alternating run and continue the pyramid. The generator never draws a second marked line.
- Witness `mixed-base` (one mark of 2 among marks of 7 on the base line): `borderline concept`, relaxing `base-line`. Every input has one mark color, and the stored colors give the concept's output.
- `store` reported `base_color.item` and `base_color.value` (7 on every input) with no witness, on several lines. I gave each an `@ignore … : store` line. With 7 stored, `$EvenColorOfBase` and `$ColorBySuccession` give `$Parity`'s output on every input, so they fail Equivalence. `rarest.low` and `color_count.domain` were reported on one line each with no witness, so they get no `@store` line.
- `derive` lists only `background=DominantColor` (`variant derived`), and it is held as a `@derive` line.
- Not formed items that are not cases of the solver:
    - OutNewColor and AnyOutNewColor for the odd-level color fail Fit, because on an input alone they give no value.
    - SharedColor for `background` fails Fit, as the Analyze report states. `derive` does not list it.
    - The `ex_out` proposers for `background` fail Fit.
    - The triangle-over-runs reading marks the cells gap-mark marks, so its model is equivalent to the concept's and fails Equivalence.
    - A derived `level_step` has no derivation to form, because no proposer or input feature gives 2.
    - `$GrowFarSide`, `$GrowBothSides`, `$BetweenTwoMarks`, `$GapCenter` and `$EdgeAsMark` get no constructor, because the report gives them no witness (each fails Fit).
- Hints: `single-consumer` on `base_line`: I inlined it. `case section` on the `scope` clauses: I resolved it by the Stack key, as above.
- Deletions:
    - I removed `color_count.domain` (Tally counts each present color from `item`).
    - I removed the background test in the `$PerLine` stack clause (a line with no mark has an empty stack).
    - I kept `params.growth_dir` in the stack clause, `inside(P, S)`, `perp_dir(D, D1)` and `grid(Ky, Q, _)` in the join. Each states structure that the pairs do not exercise: the line axis, stack membership, the along-line gap, and the `stop` rule at the grid edge.
- Determination: `level_colors` is the shortest period of the level colors in the train outputs that no level breaks, read at each phase. This follows the approved Determine of 97999447. `level_succ` is the pair of colors on each level edge, from a mark to a mark it makes. `determination: ok`.
- Sweep: `level_colors` (66) and `level_succ` (3) have single-row changes that still give every train output. The concept fixes both, and the Analyze report gives no open parameter, so no value is stored beyond the stored set.
- Keywords: `lines walk parity`.
- Performance: each run takes 1–3 s, and the audit takes 7 s.

## Open
- Whether a second marked line pools with a stack (`two-lines`): a sibling task with two marked lines would settle it.

## Lib
- Shortest period of an indexed sequence: in the Determine comp, `cand(W)` from the indices, `Unanimous<[w, r], Color>` over `stride(K, W, 0, _, R)`, the clash gives `mismatch(W)`, and `Extremes` gives the least unbroken W. In this solver: `phase_color`, `mismatch`, `unbroken` in `Determine`. The grep finds the same shape in the Determine comps of 97999447, 3ac3eb23, 8403a5d5 (draft) and 212895b5.
- Walk around a stored dense index cycle: `IndexCycle` over a stored slot domain feeding `CycleWalk.succ`, read as `walk(0, K, R)`. In this solver: `parities` and `parity`. The grep finds the same shape in 3ac3eb23, 8403a5d5 (draft) and 97999447 (`slots`/`slot_walk`).

## Fixes elsewhere
- none

## Tickets filed
- 10-130_task_af726779_create.md
