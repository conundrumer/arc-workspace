# f28a3cbb

## Departures
- The concept's `stray-in-band-attaches` now piles strays on one line outward from the side cell, the nearest first. The concept-branch constructor is `$Pile`, and the old concept collision ("strays that land on one cell make one cell") is now the branch `$Merge`: `same-line-strays` and `domino-along-motion` are witnesses of a branch with no `@reassigned` line, and each has a verdict that names that branch at `ordinary`. The Witness rule says to fix the concept case to give the judged output. Both verdicts are now `concept`, and the witness file's `$Stack` names are rewritten to `concept`.
- `$MinorAxisFirst` is not in the solver. It fails Subsumption: the audit found no run where it is defined and differs from `$DiagonalApproach`, and `analyze.md` states the same.
- `square_corners=stored` and `square_size=stored` are not in the solver, and their witnesses are removed from the witness file. `store` printed no line to add for either value, so `square_of` has a `@workaround` line for them.
- The witness `background=DominantColor` is removed. The witness `bg=DominantColor` that `derive` wrote has the same input and stands in its place. The groups use the name `bg=DominantColor`.
- `domino-along-motion` no longer separates `$RigidPieces` from the concept, because after the concept fix both give (3,1),(4,1). The new witness `piece-across-band-edge` separates them.
- `witness --file programs/reports/f28a3cbb/witnesses.json` shows differences only at the names listed above, and at the concept's grid on `same-line-strays` and `domino-along-motion`, which follows from the concept fix.

## Judgments
- `piece-across-band-edge` (a 9 piece at (5,2)-(5,3) that crosses the column band's edge), plausibility `ordinary`, verdict `concept`. Strays may touch one another, and train0 has a two-cell stray piece. Nothing in the evidence moves a piece as one body.
- `@derive DominantColor: variant derived`, `@relaxed background`. I took the plausibility and verdict from `analyze.md`'s `background=DominantColor` witness.
- `Determine.bg` keeps each color that, in every example with an output, one cell changes into and another changes out of. That matches the stray rules: a stray's cell vacates to the background, and a background cell takes a landed stray. The plan then gave "no actions".
- Off-band motion and the straight landing use one body mechanism. A body is a single stray (`$PerCell`) or a 4-connected piece (`$RigidPieces`). The diagonal phase is the least `Ray.stop` distance out of the quadrant. The straight phase uses `Gravity` against the square cells. For `$Merge`, each body falls alone. For `$Pile`, the bodies of one color and heading fall together.
- `$NearestSide` has a relational form. For a stray off both bands, the Euclidean-nearest edge-adjacent cell is the one the diagonal approach reaches, except on the corner diagonal, where the two cells beside the corner cell tie. The program states only that tie.
- Lint hints: the keyword hints came from commas on the `@keywords` line, which I fixed. I fixed the case-section hints by moving clauses under the right markers. The `negated-use` finding is fixed (`!square_of(Q, Col, _)`).
- `deletions`: 43 removals change nothing. Each of them removes structure that the pairs never use: square ties, corner arrivals, squareless colors, the both-bands undefinedness, the diagonal-pair restriction on spans (the solidity test already rejects the non-square spans), and the `$LargestPiece` square tests. Each one states part of a claim, so all stay.
- Performance: the audit took 21 s (most of it in `store`), and a pairs run took 0-4 s. No workaround was needed for speed.

## Unsettled
- `square_corners=stored` and `square_size=stored`: the program has no derived relation that has one value on every input for the squares' side or corners. A parse that derives the side and the corner set as their own relations, and then builds the squares from them, would give each a `@store` point.

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/f28a3cbb/analyze.md`, the `stray-collision` and `stray-unit` entries: each verdict names a branch at `ordinary` with no reassignment, so the concept should pile strays on one line.

## Tickets filed
- none
