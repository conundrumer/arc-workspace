# e95e3d8e

## Departures
- The `fill-from-period` rule line takes the rule as `analyze.md` restates it (the hole cell takes the generator's tile color), and the concept file's text stands under it as `@approximated:`, with `hidden-tile-color` under it: the generator's tile is hidden wherever the holes cover every cell that shows its true period, so no set of clauses reads it from the input, and the restated rule has no relational form.
- The `$DerivedHoleColor` case gives a cell a color only where every tied least-sum hole color gives it that color. A union of the tied colors' outputs would fill each cell one tied color leaves empty from another tied color, and on `single-copy-cell` that union returned the input unchanged where `witnesses.json` gives undefined: `analyze.md` states that the branch is undefined where two colors tie and give different outputs.

## Judgments
- The 16 combinations of the four choice points are all in `impl_choice`, and the runner witnesses 5 of them: the concept and one case for each non-concept branch. No combination is witnessed past its single branches.
- The concept's per-axis period is `OffsetInvariance.min_period` on the uncovered cells. `$SquarePeriod` takes the least shift that some uncovered pair witnesses on either axis and that no pair contradicts on either axis. On `unequal-periods` this gives 5, as `analyze.md` gives.
- The sum of the two periods for `$DerivedHoleColor` is counted as the residue classes the grid holds on both axes (`Tally`), so no arithmetic is needed. The derivation is limited to colors present in the input.
- The `case section` hints on `hole_cand`, `hole`, `residues` and `fewest` are kept with `@ignore`: those relations are keyed by hole color, hole source or period shape, and each case reads only its own key.
- The `deletions` findings are kept. The reflexive `cls.equiv`, the stored `hole_cand` clause, the `wp.*` inputs and the tie check (`fill.c`, `lacks`) carry the witnesses, and the pairs do not exercise them. The `hole(_, K)` atoms limit the classes and the wallpaper to the selected keys. `axis_of`, `in(Q, _)`, `in(P, C)`, the `residues.domain` atoms and `in(_, C)` state the claim's domain.
- `Determine` derives `hole_color` as the color of cells the output changes, as the plan asked (ChangedColor).
- No branch was added in Develop: `derive` found no built-in derivation that fits, and `store` printed no line to add.

## Unsettled
- `deletions` timed out on removing `residues.item` at train 2, so no finding covers that removal: a run of the cases without that rule within the time limit would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
