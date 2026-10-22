# c61be7dc

## Departures
- none

## Judgments
- The centered line has a relational form with no arithmetic. An `AxisFrame` of as many cells as the shape has holds the line in a frame of its own. Its center cell (`centered`), or in an even frame its middle pair (`middle`), is carried onto the center or the middle pair of a host box by the frame change `relative` gives, and `compose` places every line cell. An odd count against an odd host, or an even count against an even host, gives one placement. A count against a host of the other parity gives a placement only under `$EvenCountBothSides`, one per resolution. Overflow is a placed cell with a negative margin (`!inside(L, ZERO)`): rests on the pairs passing and on `witness --file` agreeing with every Analyze group.
- One host relation per choice point (`along_host`, `across_host`) carries the cross line's box, the shape's box, the corridor's box, or the grid's frame `ZERO`. So the three branches at each centering point differ only in one fact or clause: rests on the Analyze statements of `$AlongShapeCenter`, `$AlongGridMiddle`, `$AcrossShapeCenter` and `$AcrossGridMiddle`, which change only the box the middle is taken in.
- `TiebreakResolution` is `[side: Dir]`, over the two directions along the walls. Every case emits both resolutions, so a case with one placement gives one distinct grid, and `$EvenCountBothSides` gives two where the count and the host differ in parity: rests on the Types line that admits `TiebreakResolution` for the grids a case gives at a tie its model leaves unbroken.
- `$EvenCountBothSides` on an input with no shape cells: at first the solver was undefined there, because a frame of no cells has no middle, while the Analyze file gives a grid with no pressed line (witness `shape_color=RarestColor`). I added one clause under `$EvenCountBothSides` that counts a line of no cells as placed. The Analyze reading is consistent (zero is an even count, and two empty placements give one grid), so the solver now gives the Analyze file's grid: rests on `witness --file` reporting no difference.
- `head-zero` hints on `along_host` and `across_host`: kept with `@ignore`. `ZERO` is the grid's own frame, the host of the `GridMiddle` branches, and no relation measures it.
- `store` on `full_line.value` and `outside.value` (one color, 0, on every input): kept with `@ignore`, because `full` and `cross` keep exactly the value that equals `params.line_color`. `store` on `along_host` and `across_host`: kept with `@ignore`, because `ZERO` is the host at one branch alone.
- I moved the walls, the corridor and the cross line into `Parse<Key>`, because Determine repeats them to determine `background` and `shape_color`. The determination relations read facts of the train inputs alone: `line_color` fills a full line in every train input; `background` is the one color off the corridor, the walls and the cross line; `shape_color` lies in the corridor in every train input and never outside it. Rests on `determination-plan` listing each of the three for a determination relation, and on `determination: ok`.
- Deletion report: I removed the `wall_axis` atom in `wall` and the axis atoms in `new_wall`, because another atom already implies them (a line's across component cannot equal a component on the other axis). I kept `!wall` in `corridor`, the `line_color` atoms in `full` and `cross`, the `middle`, `overflow` and even-placement clauses, and the Determine atoms that restrict to train examples. They state the concept or a branch on inputs that the pairs never instantiate.
- Not built: the wall-axis point's `$AxisStored`. The Analyze report gives it no witness, and it fails Fit at train1 and test0 with `axis` vertical, and at train0 and train2 with `axis` horizontal. The Not formed items (a derived `line_color`, other line lengths, the cross line's color on top, the corridor keeping input content, a fixed wall step) give no proposer or fail Fit at a train pair, so none is a branch.
- Every branch, both `@derive` branches, and the concept fit every pair. `run_dl` counts 9 witnessed cases: the concept, one for each of the six constructor branches, and the two derived colors. `witness` reports no unseparated pair and no undemonstrated case: rests on `witness: ok` and `audit` clean.
- Keywords `lines span cross count color-class`: the walls and cross line are full lines, the corridor is an extent the walls delimit, the line centers where the cross line crosses the center line, the shape's count sets the line's length, and the shape is the cells of one color.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
