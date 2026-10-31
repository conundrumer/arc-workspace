# e8686506

## Departures
- The solver adds the choice point `Background` with the branch `$CornerColor`. In that branch, the background is the color that all four grid corners hold, and the branch is undefined where the corners differ. The witness file adds the witness `corner-field` for it: this rests on Develop step 3, because the Not formed item "Background as the color at a grid corner" states one model when the four corners agree. That model fits every pair, because the corners are 8, 3 and 4 in the three pairs, the same as the commonest color.
- The witness file adds `accent-frame`, from `work/task/e8686506/witness_grids.json`: `analyze.md` gives it as a further witness of `$FrameMostCells` (`ordinary concept`), and `witnesses.json` does not hold it. The concept gives train0's output with a bottom row of 2 2 6 2 2, and `$FrameMostCells` is undefined, as `analyze.md` states.
- The witness groups name the concept branches by their constructors `$Search`, `$Parts4` and `$Commonest`, where `witnesses.json` writes `concept`. `record --all` wrote those names.

## Judgments
- The exact cover is enumerated. `Occurrences` gives each piece's placements on the gaps. `PlacementPruning` drops the placements that no exact cover holds. `TiebreakResolutions` takes one live placement per piece, and a choice with no overlap is an exact cover, since the pieces hold as many cells as the gaps (the `Tally` gate). This gives the concept's three grids on `diagonal-piece` and both boxes on `dotted-rows`, as `witnesses.json` gives them. With pruning alone, as in 184a9768, the concept would be undefined on `diagonal-piece`.
- Frame candidates are the sets of one or two non-background colors, written as a color pair, with a single color written twice. The `frame` scene claim allows at most two frame colors. The pair is not ordered, because colors have no order, so each two-color set is computed twice. The two copies give the same grid.
- `TiebreakResolution` holds the cover, and the frame candidate is not in the term. Two candidates with different frame sets have different piece sets, so their terms differ. This does not hold where both piece sets are empty, and then no resolution exists.
- `corner-field` (built): a frame of 3 fills most of an 8×9 grid, so 3 outnumbers the field of 8 at the corners. Plausibility `borderline`: it breaks the scene claim `background`, and a generator that keeps the frame small among loose pieces makes such a grid only rarely. Verdict `$CornerColor`: a person sees the 8 field, the 3 frame and the two 4 pieces, and fills the two gaps.
- Hints: `head-repeat` on `piece` and `single-consumer` on `cover` and `sized` were right, and the solver was changed for them. The `case section` hints on `piece_cell`, `parts4` and `parts8` went away after the change to `piece`, without an `@ignore`.
- Deletions: the `domain` rules of the two `Tally` instances, `sized(K)` in `stranded` and `in(P, _)` in `out` changed nothing on any input, and the solver no longer has them. `corners_differ`, `most_outside` and the `most.mode` atoms stay: no pair has corners that differ or more than one tie, but the readings need them.
- `derive` found no built-in derivation that fits. `store` gave no line to add.
- Determination: `piece_turns` is SYM_1 at every run that finished. The plan lists no proposer that derives it, so the solver has no `Determine` comp.

## Unsettled
- `piece_turns` at values other than SYM_1: the sweep and the plan time out at train0 or train1 for all nine other subgroups. With turns, the pieces have many more live placements, and the enumeration of covers grows. A faster cover enumeration would settle it. `analyze.md` judges SYM_C4, SYM_D4 and SYM_TB to fail Fit and SYM_LR not to be an open value.
- The cases that take two or more non-concept branches are not witnessed, and no run checks them. A witness on which such a case's output differs from the output of every case that takes only part of its branches would settle it.
- `deletions` ran before the last edits, which removed the four deletions it reported and inlined `sized`. The pairs run and the witness run after those edits pass.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
