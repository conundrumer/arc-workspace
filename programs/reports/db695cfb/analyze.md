# db695cfb

## Concept
- The concept case fits every pair, the test included (`work/task/db695cfb/probe.py`, interpretation `concept`: 0 cells differ on each pair).
- Each concept rule has a relational form, so no rule is approximated, and no witness has the verdict `other`.
- The inputs show an invariant that the concept file states as the scene claim `clear-cross-lines`: none of the eight square lines in the evidence (train0 from (5,3) and (8,6), train1 from (3,4), train3 from (9,9), test0 from (4,4), (6,6), (14,11) and (18,8)) meets another mark or a cell of another joining line. So `cross-over-link` acts in the evidence only on the emitting cells themselves.
- The marks are not kept apart: train0 (8,6) and (9,7), and test0 (17,9) and (18,8), touch at a corner.
- No `link_color` cell in the evidence has more than one diagonal partner. Test0 holds four joined pairs, and two unpaired `link_color` cells, (1,9) and (23,11). Train3 also has two unpaired ones, (3,12) and (14,3).

## Choice points
- `join-axes`: the line families along which two `link_color` cells join
    - `concept`: the two diagonals
    - `$JoinCardinal`: replaces `join-diagonal-pairs`. Two `link_color` cells on one row or one column also join, and a `cross_color` cell between a row or column pair sends its line along the other cardinal axis. Parameters `link_color`, `cross_color`. It is undefined on no input. It fails Fit at test0, where the row 1 pair (1,9), (1,17) stays unjoined (26 cells differ, from (1,10)).
- `join-source`: which `link_color` cells join
    - `concept`: the input's `link_color` cells
    - `$IterateJoin`: adds a rule that the cells a join draws join again with every `link_color` cell on one of their diagonals, until nothing changes. Parameters `link_color`, `cross_color`. It is undefined on no input. It fails Fit at test0 (18 cells differ, from (2,8)).
- `join-blocking`: whether a `cross_color` cell between two `link_color` cells stops the join
    - `concept`: the join runs through it
    - `$SixBlocksJoin`: replaces `join-diagonal-pairs`. A pair with a `cross_color` cell between them is not joined, and so that cell sends no line. Parameters `link_color`, `cross_color`. It is undefined on no input. It fails Fit at train0, where (4,2), (6,4) and (7,5) stay `5`, and the lines through (5,3) and (8,6) are missing.
- `emitters`: which `cross_color` cells send a square line
    - `concept`: each one strictly between two joined `link_color` cells
    - `$ExtensionEmits`: adds a rule that a `cross_color` cell on the diagonal of a joined pair, beyond either end, also sends the square line. Parameters `link_color`, `cross_color`. It is undefined on no input. It fits every pair.
        - witness `cross-color-on-extension`: it stands at the stored assignment. Plausibility `ordinary`, verdict `concept`.
    - `$LoneRayEmits`: replaces the trigger of `perpendicular-cross`. A `cross_color` cell that is the first mark on a diagonal ray from any `link_color` cell sends the line square to that ray, whether or not a partner lies beyond it. Parameters `link_color`, `cross_color`. It is undefined on no input. It fails Fit at test0: (20,12), on the ray from (17,9), sends a line that the output lacks (11 cells differ, from (12,20)).
- `cross-axes`: which diagonals through an emitting cell are painted
    - `concept`: the diagonal square to the joining line
    - `$CrossBothAxes`: replaces `perpendicular-cross`. Both diagonals through the emitting cell take `cross_color`, so the joining line and its extension do too. Parameters `link_color`, `cross_color`. It is undefined on no input. It fails Fit at train0, where (3,1) and the other cells of the joining line take `6` (10 cells differ).
- `cross-extent`: where a square line ends
    - `concept`: at the grid edges, in both directions
    - `$CrossStopsAtMark`: replaces `perpendicular-cross`. In each direction the line stops before the first input mark of either color. Parameters `link_color`, `cross_color`. It is undefined on no input. It fits every pair.
        - witness `stray-mark-on-cross-line`: it stands at the stored assignment. It breaks `clear-cross-lines`. Plausibility `variant`, verdict `concept`. It breaks the invariant of the inputs that no square line meets another mark.
- `crossing-precedence`: the color of a cell where a square line meets `link_color`
    - `concept`: `cross_color`, on the emitting cell and on every other meeting
    - `$LinkOverCross`: replaces `cross-over-link`. A cell of another joining line, or a `link_color` mark, that a square line passes keeps `link_color`, and the emitting cell keeps `cross_color`. Parameters `link_color`, `cross_color`. It is undefined on no input. It fits every pair.
        - witness `cross-line-meets-other-link`: it stands at the stored assignment. It breaks `clear-cross-lines`. Plausibility `variant`, verdict `concept`. It breaks the invariant of the inputs that no square line meets a cell of another joining line.
    - `$LinkOverSix`: replaces `cross-over-link`. Every meeting keeps `link_color`, the emitting cell included, and that cell still sends its line. Parameters `link_color`, `cross_color`. It is undefined on no input. It fails Fit at train0, where (5,3) and (8,6) take `1`.
- `link_color` derivation
    - `concept`: stored
    - `link_color=SharedColor`: on one input it gives every color of that input, so on train0 alone it gives `1`, `5` and `6`. Every `cross_color` cell then lies between two `link_color` cells on a diagonal, and the stray `6` at (2,9) sends a line. It fails Fit at train0 (37 cells differ, from (0,7)). It is undefined on no input.
    - `link_color=RarestColor`: on train1 alone it gives `6` (one cell, against three `1` cells), so nothing joins. It fails Fit at train1 (10 cells differ). It is undefined on no input.
- `cross_color` derivation
    - `concept`: stored
    - `cross_color=SharedColor`: on train0 alone it gives `1`, `5` and `6`. Every background cell between the joined pair then sends a line. It fails Fit at train0 (49 cells differ, from (0,6)). It is undefined on no input.
    - `cross_color=RarestColor`: on train0 alone it gives `1` (two cells, against four `6` cells), so no `6` sends a line. It fails Fit at train0 (21 cells differ, from (0,8)). It is undefined on no input.
- `join-axes` & `join-source`, `join-axes` & `join-blocking`, `join-axes` & `emitters`, `join-axes` & `cross-axes`, `join-axes` & `cross-extent`, `join-axes` & `crossing-precedence`, `join-axes` & `link_color` derivation, `join-axes` & `cross_color` derivation, `join-source` & `join-blocking`, `join-source` & `emitters`, `join-source` & `cross-axes`, `join-source` & `cross-extent`, `join-source` & `crossing-precedence`, `join-source` & `link_color` derivation, `join-source` & `cross_color` derivation, `join-blocking` & `emitters`, `join-blocking` & `link_color` derivation, `join-blocking` & `cross_color` derivation, `emitters` & `cross-axes`, `emitters` & `cross-extent`, `emitters` & `crossing-precedence`, `emitters` & `link_color` derivation, `emitters` & `cross_color` derivation, `cross-axes` & `cross-extent`, `cross-axes` & `crossing-precedence`, `cross-axes` & `link_color` derivation, `cross-axes` & `cross_color` derivation, `cross-extent` & `crossing-precedence`, `cross-extent` & `link_color` derivation, `cross-extent` & `cross_color` derivation, `crossing-precedence` & `link_color` derivation, `crossing-precedence` & `cross_color` derivation, `link_color` derivation & `cross_color` derivation: the two branches' changes applied together
- `join-blocking` & `cross-axes`, `join-blocking` & `cross-extent`, `join-blocking` & `crossing-precedence`: the `$SixBlocksJoin` model, because no cell sends a line under it while `emitters` takes its concept branch. These three points stand at the concept, because under `$SixBlocksJoin` with `$LoneRayEmits` square lines are still drawn, and the points' branches differ there.

## Open parameters
- none

## Not formed
- Each `link_color` cell joins only the next `link_color` cell along a diagonal: the joined cells are the same set as under the concept, and so is the set of cells that send a line. The two models are equivalent.
- A `cross_color` cell under a joining line is hidden and sends no line: this is `$LinkOverSix` with `perpendicular-cross` removed, and with it train0, train1 and train3 lose every square line their outputs show.
- `link_color` or `cross_color` from `DominantColor`: on each input it gives the background color.
- `link_color` or `cross_color` from `OutNewColor`, `AnyOutNewColor`, `VanishedColor`, `ChangedColor`, `UnchangedColor`, `ChangedPairs`, `VanishedNewPairs`: each one reads `ex_out`, which is empty in a run on one input, so it gives no value on any input.
- `link_color` or `cross_color` from `CountRankAsc` or `CountRankDesc`: each gives a rank per color, which is not a value of a `Color` parameter.
- A derived background color: the concept reads no background, because `rest-unchanged` keeps every cell that no rule paints.

## Tickets filed
- none
