# e40b9e2f

## Departures
- The concept case drops a tied square about which `consistent-images` fails, and the core is the one square left. `quarter-turn-completion` takes the core-center text, with no `@approximated:` line. `tied-cores` (variant, concept) gives the output analyze.md judged, and stands under `$MirrorCore`, where `tied-core-off-grid` (variant, concept) stands too. The other core branches stay undefined at a tie.
- `$AnySolidCore` alone is no case. `impl_choice` holds `$AnySolidCore` only with `$InputWins`: analyze.md finds that `$AnySolidCore` fails Subsumption. Under `$NoConflict`, it is defined only where its core is the concept's core. The `witness` run had nothing that separated it from `$SymmetricCore`. The `$AnySolidCore` & `$InputWins` case stays, as analyze.md gives it. Because of this, `witness --file witnesses.json` reports that the `$AnySolidCore` model is no case on every witness.
- In the witness file, `record --all` rewrote the groups. The name `$AnySolidCore` now denotes the `$AnySolidCore` & `$InputWins` case. On `unsymmetric-square`, that case gives a defined grid (the input, with no painted cell), so it stands in its own group. witnesses.json gives that branch's model as undefined there.

## Judgments
- `$MostAgreement` scores a center by the number of figure cells whose every `group` image holds the same color. analyze.md's phrase "have a group image of the same color" leaves this open. This reading reproduces the `arm-agreement` output of witnesses.json (5 cells about (5,6) against 4 about the core). The run shows that it fits every pair.
- The candidate squares are the bounding boxes of two grid cells on one diagonal line, through `Bbox` keyed by the cell pair. The `$MostAgreement` centers are the 1x1 and 2x2 squares among them. The turn about a center is `relative`, then `apply`, then `compose` in the center square's frame.
- A tie for the core that stays (or for the most-agreeing center) is made undefined by an explicit `core_tie` / `left_tie` / `most_tie` test. Without it, two tied centers could give one output and be defined.
- Determination: sweep gives `bg` = 0 and `group` = `SYM_C4` as unique. The plan lists `bg` (DominantColor exact) and `group` (pairs-exact enumeration). Both values come from the same facts the concept reads (the field is the commonest color, and the group is fixed by the pairs), so there is no Determine comp.
- Hints: `off_grid` (single consumer) is inlined into the `$InGrid` `broken` clause, and the two `out` clauses are merged into one disjunction (common-subexpr).
- `deletions` lists 20 removals that change no pair. All of them are tie, conflict, off-grid, and symmetry tests, which the pairs never trigger, together with the diagonal test that makes the boxes square. The witnesses exercise each of them, so they all stay. After `deletions`, only two comment lines changed.
- `store` printed no line to add, and step 3 forms no branch: the items under Not formed state no model with a relational form.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
