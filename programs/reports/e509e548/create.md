# e509e548

## Departures
- The concept's `kind_color` parameter is three relations, `l_color`, `u_color` and `other_color`: the solver may define no kind type to key one relation by, and 25d8a9c8 stores one color relation per class the same way.
- `$SeenKindsOnly` has no constructor and no case, and the witness file no longer names it: it fails Subsumption. Where it is defined (an L, a U, or a drawing with one T junction), its output is the concept's output. `witness` reported that no run shows it defined and different from another case. `analyze.md` gives the same standing.
- `$RunCount` and `$ShapeTable` have no constructor: they fail Fit, as `analyze.md` gives, and have no witness.
- The witness file has a further witness, `bg=DominantColor`, that `derive` wrote. It is the `@derive DominantColor` branch of `bg`.

## Judgments
- `bg=DominantColor` is `variant` and `derived`: on train0 with colors 0 and 4 swapped, the field is 4. A color permutation of a task is a variant task, and the generator keeps the field color, which is the derived `bg`.
- The bend classifier is relational, so the rule needs no `@approximated:` line. A bend is a cell with exactly two neighbors at a right angle. A junction is a cell with neighbors on both sides of one axis and one more neighbor. An L is a drawing with one bend and no junction. A U is a drawing with exactly two bends, no junction, and two bends that share an arm direction. Two bends joined by a straight middle segment share an arm direction only when they turn the same way. "One", "two" and "three" bends are stated through distinct cells (`!=`), and no number is read.
- Under `$Corner8`, each `Class` branch classes the 8-connected drawing with the same bend and junction tests. A merged drawing is no path, so this reading of "path" over such a drawing is a choice. On `corner-contact` it gives the output `analyze.md` gives.
- The `$CornerCount` tally counts one corner per `DiagDir` that has both of its cardinal neighbors. This counts each vertical and horizontal neighbor pair once.
- `deletions`: the `!link` negations in `bend_dir`, `three_bends`, the `bend_dir` atoms and negations in `u_drawing`, and the negations in `two_bend_path` stay. The pairs hold no T-junction bend, no three-bend path and no Z, and the witnesses `t-no-bend`, `three-bend-path` and `z-path` need these atoms. `corners.domain` left: a drawing with no corner has no `corner_color` entry with or without a 0 tally. The `impl_choice` atoms in the per-branch `out` clauses left: the cases are every combination, and `parse.drawing` grounds `J`.
- Determine reads drawings at `$Edge4` only. With both joins, `corner-contact` added as a pair made `other_color` take 1 and 6 from the merged 8-connected drawing. `bg` is the color that each train output keeps from its input.
- The sweep found 52 single-row changes of `corner_color` that give every train output. These are rows at counts that no drawing has, and `corner_color` is not an open parameter. The stored rows stay.

## Unsettled
- `deletions` ran before the last solver edit. That edit removed the atoms it found and changed comments. The last pairs run passes with lint ok. A second `deletions` run after the edit would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
