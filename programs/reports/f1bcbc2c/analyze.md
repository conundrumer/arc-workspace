# f1bcbc2c

## Concept
- Fits every pair: `work/task/f1bcbc2c/probe.py` reproduces train0–3 and test0. Every claim has a relational form: the walls and the corridor are components, the openings are corridor cells on the grid border, a plug is at a bend or on a straight run depending on which of its 4-neighbors are wall cells, and the fill is a walk through the corridor. No approximation is needed.
- No witness with verdict `other` was found. The rule as the generator applies it is the concept file's rule.
- The plug test is written by wall sides (walls on two opposite sides means a straight run) rather than by corridor neighbors, so that a plug in an outlet cell, where the grid edge borders it, reads as being on a straight run (see `$PlugTestByOpenSides`).
- `background_color` is a scene parameter. The program reads only the wall, plug and fill colors and the source edge, and every other cell keeps its input color.

## Choice points
- `plug-test`: what decides whether a plug stops the fill
    - `concept`: a plug with wall cells on two adjacent sides (a bend) blocks, and one with walls on two opposite sides (a straight run) passes
    - `$PlugTestByOpenSides`: replaces `plug-at-bend-blocks` and `plug-on-straight-passes`. A plug passes when it has exactly two corridor neighbors and they are collinear, and blocks otherwise. No parameters. Defined wherever the concept is. Fits every pair. Witness `plug-at-outlet`: breaks the scene claim `at-most-one-plug` (away from both openings). At the stored assignment. Plausibility `borderline`, verdict `concept`. Invariant broken: every plug lies inside the corridor, at least two cells from either opening.
    - `$PlugAlwaysBlocks`: replaces `plug-on-straight-passes`. Every plug stops the fill. No parameters. Defined wherever the concept is. Fails Fit at train0: output (7,4) and col 4 rows 8–9 are 8, and the branch keeps (7,4) at 9 and leaves the cells below it 0.
    - `$PlugNeverBlocks`: replaces `plug-at-bend-blocks`. Every plug is washed through and painted. No parameters. Defined wherever the concept is. Fails Fit at train1: output (6,4) is 9 and row 6 cols 5–7 and col 7 rows 7–9 stay 0, and the branch paints them all 8.
    - `$PlugJamsAtNextBend`: replaces `plug-on-straight-passes`. The flow carries a plug downstream along a straight run until it reaches a bend, where it jams, or the outlet, where it leaves the pipe. No parameters. Defined wherever the concept is. Fails Fit at train2: the branch jams the plug at (7,5) and leaves row 7 cols 6–7 and col 7 rows 8–9 at 0, where the output fills them and paints (4,5).
- `plug-paint`: the color a plug takes
    - `concept`: a plug that the fill passes through is painted `fill_color`, and a blocking plug keeps `plug_color`
    - `$PassedPlugKeepsColor`: replaces the painting in `plug-on-straight-passes`. A plug the fill passes through keeps `plug_color`. No parameters. Defined wherever the concept is. Fails Fit at train0: (7,4) stays 9, and the output has 8.
    - `$BlockingPlugFilled`: replaces the kept color in `plug-at-bend-blocks`. A blocking plug is painted `fill_color`. No parameters. Defined wherever the concept is. Fails Fit at train1: (6,4) becomes 8, and the output keeps 9.
- `source`: where the fill enters the corridor
    - `concept`: the opening on the `source_edge` edge, stored as top
    - `$SourceUpperEnd`: replaces `fill-from-source`. The fill enters at the opening nearest the `source_edge` edge. Reads `source_edge`. Undefined where two openings tie for nearest. Fits every pair. Witness `side-openings`: breaks the scene claim `pipe` (opens on the `source_edge` edge). At the stored assignment. Plausibility `borderline`, verdict `$SourceUpperEnd`. Invariant broken: every input's corridor opens on the top edge.
    - `$FillLongerPart`: replaces `fill-from-source`. Where a blocking plug splits the corridor, the larger of the two parts fills, and otherwise the whole corridor fills. Does not read `source_edge`. Undefined where the two parts are equal in size. Fits every pair (the filled part is the larger in train1, 9 cells against 6, and in test0, 9 against 7). Witness `longer-part`: breaks no scene claim. At the stored assignment. Plausibility `ordinary`, verdict `concept`.
- `plug_color`: how the plug color is determined
    - `concept`: stored, 9
    - `plug_color=RarestColor`: derives the plug color as the rarest color of the input. Undefined where colors tie for rarest. Fits every pair (in train3, which has no plug, the rarest color is 7, which marks no corridor cell). Witness `plug_color=RarestColor`: breaks no scene claim. At the stored assignment. Plausibility `variant`, verdict `concept`. Invariant broken: every input is 10×10 and its commonest color is `background_color`.
- `fill_color`: how the fill color is determined
    - `concept`: stored, 8
    - `fill_color=OutNewColor`: derives the fill color as the color in every train output and in no input. On a run over one input `ex_out` is empty, so it gives no value and the branch is undefined on every input. Fails Fit at train0, as does `AnyOutNewColor` for the same reason.
- `plug-test` & `plug-paint`, `plug-test` & `source`, `plug-test` & `plug_color`, `plug-paint` & `source`, `plug-paint` & `plug_color`, `source` & `plug_color`: the two branches' changes applied together. For `$PlugJamsAtNextBend` with `$FillLongerPart`, the plug is carried away from the end of the larger part.
- `fill_color` & `plug-test`, `fill_color` & `plug-paint`, `fill_color` & `source`, `fill_color` & `plug_color`: the model of `fill_color=OutNewColor` alone, undefined on every input. The other points' properties therefore exist only under `fill_color`'s concept branch, and those points stand under it.

## Open parameters
none

## Not formed
- Another parse of the corridor (the non-wall component that holds the plug, or the one whose cells all touch both walls): the plug component is undefined in train3, which has no plug. The others agree with "the non-wall component touching both walls" on every input where two walls bound one corridor, and they differ only where the walls do not bound a single one-cell-wide corridor. There the concept's openings and plug test lose their meaning too.
- A derived `wall_color`: run on one input alone, no proposer gives 7. DominantColor gives 0, RarestColor gives 9 (7 only in train3), and SharedColor gives every color of the input.
- A derived `source_edge`: no proposer gives a direction. The geometric alternatives to the stored edge are `$SourceUpperEnd` and `$FillLongerPart`.
- A derived `background_color`: the program reads no background color.
- Filling from both openings: the same output as `$PlugNeverBlocks` wherever no plug blocks. Where one blocks, it fills both parts, which fails Fit at train1, where row 6 cols 5–7 and col 7 rows 7–9 stay 0.

## Tickets filed
- none
