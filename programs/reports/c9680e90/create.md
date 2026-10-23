# c9680e90

## Departures
- `divider-color=CountRankDesc` and `background=CountRankDesc` are not branches of the solver: `CountRankDesc` proposes `(color, rank)` rows, so it gives no value of a one-column color parameter. `derive` lists only `background=DominantColor`. With a `@derive CountRankDesc` line on `divider_color`, the run aborted with an arity mismatch. The witness `divider-color=CountRankDesc` separated only that branch and was removed. The witness `background=CountRankDesc` had the same input as `background=DominantColor` and was removed. Both names were dropped from the other witnesses' groups.
- The `divider-location` point stands under the divider branch of `mirror-line` (`Mirror = DividerMirror {locate: Locate} | CenterMirror {}`): `$CenterMirror` reads no divider, as `analyze.md` states for `mirror-line` & `divider-location`. `divider_color` is read only under `$StoredDivider`, so the `@derive` branch of `divider-color` never combines with `$CenterMirror` or `$DividerDerived`.
- Added witness `tail-dominant` for `background=DominantColor` & `$DividerDerived`: no Analyze witness shows that case defined.

## Judgments
- Keywords `symmetry move markers`: the twins mirror across the divider, the heads translate, and each tail fixes its head's direction and extent and is consumed.
- The mirror across the divider is encoded as `relative` to a divider cell, the `flip_of` of the axis perpendicular to the divider, and `compose` back. In a divider cell's 1×1 frame, the flip reflects across that cell's line, so any divider cell gives the same image.
- The concept case is undefined where the input has no full line of `divider_color` along `divider_axis`, or more than one: `Unanimous<Locate, Line>` gives no value there, and `ready` holds no case that reads the divider. A mark whose mirror image falls off the grid paints an `out` fact outside the frame, so the model is undefined there. Two moves that paint different colors on one cell are undefined too. This matches `analyze.md`.
- `tail_color` has no determination relation: the plan covers it by `VanishedColor`, and the tail color leaving the output follows from `crawl-to-tail-end`, so the proposer reads the concept's own fact.
- The other determination relations read the concept's facts in an acyclic order. `head_color` is the changed non-tail color beside a tail. `background` is what a train output gives a tail cell that no head lands on. `divider_color` and `divider_axis` come from a full non-background line in every trained example. `mark_color` is the remaining input color. A first version, in which `background` and `mark_color` excluded each other's stored colors, was reported as circular. It also drew a `common-subexpr` hint, which the rewrite removed.
- Deletions:
    - Removed `same_line(A2, P, D)` from the divider mirror, because any divider cell gives the same image.
    - Removed the `ready` atom from the twin `paint` clause, the twin `cleared` clause and the `$MirrorRedraw` `paint` clause: `twin` and `mirror` already bind and gate those cases.
    - Kept the other reported atoms. Each states the concept, or a non-concept branch's rule, on inputs the pairs do not hold: the `mirror_axis` gate, `move` before a mark is cleared, `head`/`mark` in `twin`, the `$ColumnTwin` line test, the stored axis, `dir_elem` for 4-neighbors, and the train-pair `ex_out` atom and defect relation in the determination.
- `tail-dominant` (`foreign`, verdict `concept`, breaks `mirror-twins`): for the tail color to outnumber the background while the divider is the only full line, the top half needs a mark that mirrors no head. With heads and marks equal in number, the background count is never less than the tail count. The generator keeps the background at 7, so the concept's output is the verdict.
- 27 bases and the `background=DominantColor` branch give 54 cases. The run witnesses 9 of them. No performance issue arose.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 17-7_task_c9680e90_create.md
