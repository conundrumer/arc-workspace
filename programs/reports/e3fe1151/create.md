# e3fe1151

## Departures
- The concept branch constructors are `DividerBlank` (point `blank-color`) and `CenterCross` (point `cross-location`). The witness file still uses `concept` for the concept case, which is a name the Witness file section allows. No name needed a rewrite.
- New witness `cross-at-top` for `$LineCross` (`borderline $LineCross`, `@relaxed cross`): `witness` reported that no run showed `$LineCross` defined and differing from `$CenterCross`. In this 3×5 input, the full row of 7 is row 0 and the full column is col 2. `$LineCross` fills the blank at (1,4) with 2. The center reading takes row 1 as the cross, finds the top quadrants all blank, and is undefined. So `$LineCross` meets Subsumption. The verdict is `$LineCross` because the annotator judges that the generator would fill the missing color. The plausibility is `borderline` because a cross at the edge breaks `cross`.
- Branches added in Develop: `@derive DominantColor` on `divider_color` (`variant derived`, `@relaxed cross`, `@relaxed blanks`) and on `blank_color` (`borderline derived`, same `@relaxed`). The `divider_color` witness is the one `derive` wrote: train0 with 7 and 2 swapped. The verdict is the derived output because a generator that draws the cross in 2 fills the blanks the same way. The plausibility is `variant` because that input is a color permutation.
- The witness `blank_color=DominantColor` was rebuilt. The witness that `derive` wrote no longer separated anything once the `$CenterCross` cases of that branch left (see Judgments). The new input is 7×7 with 3×3 quadrants and 0 blanks, 4 or 5 per quadrant. 0 is the commonest color, and each quadrant lacks one color at a count equal to its blanks. The derived blank color fills them, and the stored 7 gives no blanks and is undefined. The plausibility is `borderline` because the input breaks `cross` (quadrant size) and `blanks` (count and color).
- New witness `dominant-content` (no `@witness` line, kept in the witness file). It is a 7×7 grid where 1 outnumbers the 7s. The stored blank color fills the four 7 blanks, and every `DominantColor` case is undefined there. It was built for the `witness` report that no witness separated `$OwnBlankColor & blank_color=DominantColor` from `$DividerBlank & blank_color=stored`.
- The program is undefined where a filled quadrant's count of some color differs from the union count (`mismatch`), or where a cross has no line, or two lines, along an axis (`bad_cross`). The concept states that it is undefined where blanks and missing colors do not match one for one. `mismatch` encodes that with a second `Tally` over the filled quadrant. A blank that lacks two colors gets two colors, so it describes no total grid.

## Judgments
- `@ignore: derive $CenterCross` on `blank_color`: under `$CenterCross`, `divider_color` is read only as the blank color. So `$OwnBlankColor & $CenterCross & blank_color=DominantColor` is equivalent to `$DividerBlank & $CenterCross & divider_color=DominantColor`. It takes more non-concept branches, so it fails Equivalence.
- Not formed items: the "other three quadrants" reference states one model. It is equivalent to the concept by analyze.md's argument (a color's max over all four is the max of the other three's and the quadrant's own), so it fails Equivalence, and I formed no branch for it. The positional counterpart reading fails Fit (no map gives all 16 fills). The other items do not state one model.
- `store` gave no line to add. `broken_line` has no witness, and `content` has no case.
- Hints: `shared-read` on `divider_color` was resolved by moving it under `// --- $DividerBlank, $LineCross ---`. `common-subexpr` on `out` was resolved by merging the keep and fill clauses into one disjunction.
- `deletions`: 8 deletions change nothing on the pairs.
    - `bad_cross`, `mismatch`, `!bad_cross` and `!mismatch` set definedness on inputs the pairs do not have. The witnesses `blank-row-across-top`, `cross-at-top` and `blank_color=DominantColor` exercise them.
    - `!blank` in `content`, and `filled.domain`, matter on the witnesses where blanks are not 7 or a quadrant lacks a color.
    - The column `broken_line.a` keeps rows apart from columns.
    - All 8 were kept.
- Determine: `divider_color` is the unanimous color of the center lines over every input. `blank_color` is the unanimous input color of the cells that the outputs change. The plan listed no actions after these relations.
- Keywords: `decompose` (the cross cuts quadrants), `count` (per-quadrant color counts), `repair` (blanks restored from the shared multiset).

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
