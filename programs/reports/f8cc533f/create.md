# f8cc533f

## Departures
- `$SymmetricClosure` on `asymmetric-pattern` gives two grids, one for each value of `pattern_sym`. `witnesses.json` gives it as undefined: [Open parameters](docs/handbook/principles.md#open-parameters) defines M_open as the union of the outputs at the open values, and SYM_D4 and SYM_BOX are open values of that branch's parameter, since no pair separates them. The solver stores them in one `@open` relation with a `pattern_sym` field on `OpenValue`.
- `$CornerAlign` stores `align_corner` (`DIAG_TL`, `DIAG_BL`, as an `@open` relation), where `analyze.md` stores `align_edge` = `DIR_L` and runs both ends of the other axis. The two corners are exactly the left edge with each vertical end, so the solver needs one relation instead of a stored edge plus ends derived from it. Where the ends disagree, the case gives two grids (M_open) instead of being undefined, as above.
- `restore-copy` states the analyze placement (the joint placement in the pattern box that gives the smallest overlay) and runs an approximation under `@approximated:`. A copy with one placement in the pattern box is fixed, and every copy goes to the placement that puts the fewest of its cells outside the overlay of the fixed copies.
- `copies-apart` is not in the header: no claim, branch or rule text depends on it.

## Judgments
- The joint smallest overlay has no relational form that the program allows: to choose among placement combinations, the program must enumerate them as values, and that needs recursion or a combination type that [Types](docs/handbook/solver-file.md#types) does not list. The approximation is the same as the rule wherever every copy but one has a single placement in the pattern box. That holds in every pair: only train2's 8 copy has two placements.
- Witness `no-fixed-copy` (built): the 1 copy has lost its left column and the 2 copy its top row, so no copy is fixed. The joint minimum is unique and restores both copies to the 6-cell pattern. The approximation ties every placement and stamps each copy at both of its placements. It breaks no scene claim. Its pattern is not D4-symmetric, and that breaks only the unclaimed invariant, so the plausibility is `variant`. The verdict is `other`: no case gives the joint-minimum output. The judged output is the input with both copies made whole.
- Candidate placements are the boxes of the pattern extent that contain the copy's box, found as `relative(Q, P, F)` over copy cells P and pattern-frame cells Q. This is the same form that `Occurrences.placement` uses.
- `min_copies` gets a determination: the fewest input copies that hold a cell of an output pattern, with each copy's full box taken from its color's box in the output. It gives 1 (train1). The sweep also admits 0, which `held` makes the same as 1.
- `pattern_sym` and `align_corner`: the plan lists them as undecided with no clauses that read them, so the fit set determines them. The sweep admits every Sym for `pattern_sym`. The stored values are the reader's open values that `analyze.md` gives.
- Lint hint `negated-use` (`!bg(Col)`): accepted. The single-use `bg` relation was inlined to `!bg_mode.mode($U(), C)`.
- The first audit reported that removing either `align_corner` fact changed no output. The `no-fixed-copy` witness resolves this: there `DIAG_TL` and `DIAG_BL` give different `$CornerAlign` grids.
- Deletions that change nothing and are kept: `off_frame` and its atoms (the non-square undefinedness of `$SymmetricClosure`, which no pair reaches); `params.align_corner(D)` (without it, `corner_anchor` grounds all four corners); Determine's `bg_mode` (it keeps the background's box out of the copies).
- Deletions applied: the `impl_choice` atoms and the `impl_choice` and enumerator relations, since the cases are every combination of the two fields; the Tally `domain` rows whose keys always have items; the `ex_out` guard on the Determine background, since `full_box` reads only train outputs.
- Branches with no witness in `analyze.md` (`$MajorityVote`, `$LargestCopy`, `$StoredPattern`, `$SelfSymmetry`, `$ComponentCopies`, `$StoredBackground`) fail Fit, and the solver has no constructor for them. `derive` found no fitting derivation. `store` printed no line to add.
- 4 of the 6 cases are witnessed. The audit and `witness` report no pair of cases that no witness separates, and no case left without a witness.

## Unsettled
- The joint-minimum placement rule: settling it needs a lib construction that enumerates one choice per key (a placement per copy) and ranks the combinations.

## Concept faults
- f8cc533f `restore-copy`: choosing the joint placement of the copies with the smallest overlay needs enumeration of placement combinations, which needs recursion or a type outside the allowed list.

## Fixes elsewhere
- none

## Tickets filed
- none
