# f21745ec

## Departures
- `$SizeOnOneAxis` is not a case of the solver, and the witness file lists it in no group: it fails Subsumption. Where it is defined, every outline that matches on `match_axis` also matches on the other axis, so its output is the concept's at every value of `match_axis`. Where an outline matches on one axis alone, it is undefined. `witness` showed no run where it is defined and differs. analyze.md gives the same reading.
- The witness `same-height-other-width` stays in the witness file with new `separates` text. With `$SizeOnOneAxis` gone, it separates the concept from `$SourceMostCells`: the 2 outline has more cells than the 8 rectangle, so `$SourceMostCells` takes the 2 outline as the source.
- `witness --file programs/reports/f21745ec/witnesses.json` reports only that `$SizeOnOneAxis` denotes no case. Every other output agrees with witnesses.json.

## Judgments
- The constructors are `$SourceMostCells` (`Source`) and `$CopyTransformed` (`Copy`). The concept branches are `PatternedSource` and `CopyInPlace`. `bg=DominantColor` is a `@derive DominantColor: variant derived` line on `bg`, as `derive` printed. Branches that fail Fit (`$SizeUpToTurn`, `$SizeByArea`, `$KeepUnmatched`, `$SourceLargestBox`, `$SourceColorStored`, `$PatternColorKept`, `$PatternErased`) have no witness in analyze.md and get no constructor.
- The cases are all four combinations of `Source` × `Copy`. Every pair passes at all four.
- The Not formed items add no branch. Copying the interior alone is equivalent to the concept. The component parse is a parse, not a claim.
- Rectangles are found by color (`Bbox<Color>` over the non-`bg` cells), as `rectangles-on-background` gives each rectangle its own color.
- An outline matches when its box extents equal the copy's frame extents on both axes. The copy's frame comes from `axis_dim` on the copied cells, so under `$CopyTransformed` a transposing `copy_d4` compares against the transposed extents.
- `store` printed nothing to add. The single line it printed, for `copy_dim`, has no case.
- `determination-plan` listed `bg` (DominantColor exact), `copy_d4` and `match_axis` (pairs-exact) as covered by the proposers and the enumeration. No determination relation derives any of them from another fact, so the solver has no `Determine` comp. `match_axis` then left with `$SizeOnOneAxis`.
- Kept after `deletions`: `extra_source` and its negation make a case undefined where two sources exist, and the pairs have none. `!source` in `outline` keeps the source from being matched to itself, which `$CopyTransformed` would transform at a non-identity `copy_d4`. The `matched` atom in the copy clause states the size match, which the frame equality in `crop`/`copy_cell` also implies. The disjunct that copies `bg` pattern cells states the rule, where the outline's interior is already `bg`. Removed: `rect_size.domain` (every rectangle has cells) and the axis column of `differs`.
- A `case section` hint fired on the shared clauses below the `$CopyTransformed` marker. The fix was a `// --- $CopyInPlace, $CopyTransformed ---` marker above them.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
