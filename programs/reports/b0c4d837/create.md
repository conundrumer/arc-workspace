# b0c4d837

## Departures
- The solver stores a parameter that the concept file does not have, `open_dir` (`DIR_T`), which is the side the cup opens toward. The rules "topmost row", "above the floor" and "walls" read it: the task picks out one direction, and [One member](docs/handbook/principles.md#orientation) has a parameter store the chosen member. The `@scene cup` and `@rule count-empty-rows` lines name it.
- The Analyze report's `order_d4` (`D4_ID`) for `$SnakeOrder` and `$SpiralOrder` is stored as `order_corner` (`DIAG_TL`) and `line_axis` (`AXIS_H`): the walk clauses read a start corner and the axis of the first line, and the eight pairs of values are the eight D4 values ([Indirection](docs/handbook/principles.md#indirection)). The sweep finds each value unique.
- `$SpiralOrder` stores no sense. At a blocked step the spiral takes the one perpendicular step that stays on its ring or goes to the next ring inward. On a square frame, the ring depths and the start corner fix that step, so the corner and the axis fix the sense.
- The concept case and the two walk cases are all undefined where the count is more than the frame's cells (`K <= N` against a tally of the ranked cells). The Analyze report gives this for the walk cases. For the concept case it is my reading of "the first count cells", because there are no such cells when the count is larger than the frame.
- `fill_order` stores its two open values under the `Ident` keys 0 (snake) and 1 (clockwise spiral). The `out` clause runs over the ranks of every value, so a cell that the values rank on the two sides of the count gets two colors and the grid is undefined. A defect relation `partial` makes the case undefined where one value leaves a cell unranked that the other ranks. Without it, the audit's open-values check found that no single stored fact changed any output.
- The header has no `@scene empty-rows`, because no `@claim`, `@relaxed` or rule text refers to it.
- The witness file has a new witness, `liquid-debris`: a cup with three empty rows whose bottom liquid row is `8 2 8`. It shows `$StoredLiquid` defined and different from `$LiquidAnyColor` in the cases that take `$MarkColor` or `$CountTable`, which `witness` reported as unshown. Under `$LiquidAnyColor` it carries the line `@witness liquid-debris: borderline concept` with `@relaxed liquid`.
- `derive` added the branch `mark_color=RarestColor` and its witness `mark_color=RarestColor`. The Analyze report does not have this branch.

## Judgments
- The `@derive` lines are `fluid_color` RarestColor `ordinary concept` and `background` DominantColor `ordinary concept`, both as the Analyze report gives them. For `mark_color` RarestColor I judged `ordinary concept`: its witness is the `mark-color` input at `mark_color` = 2, where the derived mark color (8) gives the concept's output.
- `liquid-debris` is `borderline concept`: it breaks `liquid` (one stray cell in the liquid), and a reader would still count the empty rows above the liquid's top.
- Not formed: no item becomes a case. Each one fails Fit, fails Relational form, or is a value of an existing parameter, as the Analyze report states. There is no other relational reading of the derived `wall_color`.
- `store` lists no `@store` line to add. Each derived value that is the same on every input is already a stored value (`fluid_color` or `mark_color`).
- The count is the distance between the rim box's edge toward `open_dir` and the same edge of the liquid's bounding box (`relative` and then `dist`). This counts the rows from the rim down to the liquid's top, that row left out. `$LowerRim` takes the bounding box of the wall cells on rows where both outer wall columns hold the wall color.
- `$LiquidAnyColor` reads the cells that sit directly above a cell of the cup box's edge and lie inside that box. Only the floor row has such cells.
- The snake and the spiral are walks. Each is a `GraphDistance` over (cell, heading) states, seeded at the start corner, and a cell's rank is its distance. The snake reverses at the frame's edge and steps one line on. The spiral goes straight while the next cell is on its ring (and is not that ring's start) or deeper, and otherwise turns. I checked them on 4×4, 5×5 and 6×6 frames and from other corners.
- Determine: `count_table` takes each train output under the concept's count. `fill_order` builds the snake and the spiral from the start corner and first axis that the outputs show. The outputs give the marked cells an order (`Order`); its first cell gives the corner and the next cell gives the axis. The determination check passes for both parameters. The plan found every other parameter covered.
- Deletions: I removed the floor's `opposite(U, D)`, the snake's line-axis restriction, the spiral's sense atoms and `ring.depth`, and `ex_out` in `shown.before`. Other atoms already imply each of them. I kept `uneven` and its `same_dist`, because they are the `$LowerRim` structure and no pair has uneven walls. I kept `partial`, because it is the open-value defect. I kept the bound enumerators, as the report states.
- Hints: the `sense` single-consumer hint was resolved first by inlining and then by removing it (see above). The case-section hint on `mark` was resolved by putting `$LiquidMark` and `$MarkColor` under their own markers. Lint passes.
- Keywords: `count rank walk lookup`.
- The run shows 12 witnessed cases of 114. Every pair passes. `witness`, `witness --file` against the Analyze file, and the audit all report ok.

## Open
- Whether the concept case is undefined above nine empty rows, or fills the whole frame: a sibling task with a count larger than its frame would settle it.

## Lib
- Rank along a walk over (cell, heading) states (the snake and spiral orders in `Parse`, through `GraphDistance<KeyOrder, Step>`). The grep finds spiral walks in 08573cc6 (`Propagation<Unit, Arm>`, an outward spiral whose arms grow) and in the draft 28e73c20 (`Propagation<Unit, Step>`, a spiral line drawn with a gap). Both draw a path. Neither ranks the cells of a frame that the walk fills, so I propose no lib operation.

## Fixes elsewhere
- none

## Tickets filed
- none
