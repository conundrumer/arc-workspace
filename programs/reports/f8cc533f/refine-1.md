# f8cc533f

## Departures
- `restore-copy` places the copies by a pairwise relation, where `analyze.md` places them at the joint placement that gives the smallest overlay: each copy sits where its cells lie inside the pattern box, and each two copies sit at a relative placement at which they share the most cells. The case is undefined where this leaves a copy no placement or more than one. This applies the override, "State `restore-copy` as the relation the task shows, encode it with lib relations, and remove the `@approximated:` line where the encoding runs the claim itself." The encoding runs the claim itself, so the solver has no `@approximated:` line. With two copies, the most shared cells is the same as the smallest overlay, because each copy's cell count does not change with its placement. In every pair, every copy but train2's 8 copy has one placement, and both other copies share the most cells with the 8 copy at its left placement (7 and 8 cells, against 3 and 2).
- `$SymmetricClosure` and `$CornerAlign` are not formed: their open parameters `pattern_sym` and `align_corner` break ties no alt of the task accepts.
- `copies-apart` is not in the header: no claim, branch or rule text depends on it. (create.md)
- `$CopyCountThreshold` is not formed: it reads a numeric threshold, an approximation no claim of the concept declares.

## Judgments
- The encoding of `restore-copy`: `shared` (Tally) counts the cells that two copies at two candidate placements both hold, with a domain row for every candidate pair so that a pair that shares no cell counts 0. `most_shared` (ArgExtremes) gives each two copies' placement pairs that share the most cells. Two candidates conflict when their pair is not among those. `joint` (PlacementPruning) gives the candidates that a joint placement can still hold. A copy takes its candidate where it keeps exactly one. Where every copy keeps one, no two of them conflict (PlacementPruning kills a candidate that conflicts with every surviving candidate of another copy), so those placements satisfy the claim. They are also the only placements that satisfy it, because `alive` keeps every candidate of every joint placement that satisfies it.
- The joint smallest overlay is not formed as a branch: by the override, the Create concept fault that rested on it (an enumeration of placement combinations) shows a claim that states an implementation.
- Keyword `rank` added: an extremum over counts (the most shared cells) determines each copy's placement.
- Deletions that change nothing and are kept: `shared.domain` (without it, a candidate pair that shares no cell gets no tally and so no conflict); the `unplaced` rules and `!unplaced(_)` (the claim's undefinedness, which no pair reaches); Determine's `bg_mode` (it keeps the background's box out of the copies). (in part create.md)
- `deletions` timed out at 2 s on three removals (`bg_mode.item`, `!bg_mode.mode` in `copy_cell`, `inside(B, F)` in `cand_box`). Each one removes structure the parse needs, and each is kept.
- Lint hint `negated-use` (`!bg(Col)`): accepted. The single-use `bg` relation was inlined to `!bg_mode.mode($U(), C)`. (create.md)
- Candidate placements are the boxes of the pattern extent that contain the copy's box, found as `relative(Q, P, F)` over copy cells P and pattern-frame cells Q. This is the same form that `Occurrences.placement` uses. (create.md)
- Branches with no witness in `analyze.md` (`$MajorityVote`, `$LargestCopy`, `$StoredPattern`, `$SelfSymmetry`, `$ComponentCopies`, `$StoredBackground`) fail Fit, and the solver has no constructor for them. `derive` finds no fitting derivation. `store` prints no line to add. (create.md)

## Unsettled
- Whether PlacementPruning can leave a copy two placements on an input where exactly one joint placement satisfies `restore-copy`, which makes the case undefined where the claim gives an output. With at least one copy that has one placement, its conflicts leave each other copy only the placements that share the most cells with it. Only an input with several copies that each have more than one placement can show it. An input that shows it, or a proof that pruning is complete for these conflicts, would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
