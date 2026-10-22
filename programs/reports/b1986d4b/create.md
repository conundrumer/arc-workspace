# b1986d4b

## Departures
- The solver has the concept case alone, and its run fails train0 and train1. That case draws five 2x2 stacks in each, where the expected outputs draw four (train0: 5x19 against 5x16; train1: 5x21 against 5x18). Train2 and test0 pass, and lint and determination pass: the Analyze report finds that no case of the task as given meets every case condition, and reads those two outputs as errors in the task data.
- `programs/witnesses/b1986d4b.wit.json` is not written. The only witness, `one-largest-square`, separates the concept from `$CapSmallestTwiceLargest` and `$CapSmallestLargestPlusTwo`. Those two branches have no case, and `witness` lists no case for them, so the names leave and the witness then separates nothing. The concept's output on that input matches the Analyze file's `concept` group.
- `$CapSmallestTwiceLargest` and `$CapSmallestLargestPlusTwo` have no constructor. They fail Relational form: each caps the smallest size's count by a factor of two or an offset of two, and neither number counts anything the task has, so no set of clauses states the cap.

## Judgments
- The concept case is written even though it fails Fit at train0 and train1: the Analyze report gives it as the generator's rule (train2 and test0 show it), and the only branches that fit every pair fail Relational form.
- Every other branch of the Analyze report fails Fit, as that report gives, and has no witness, so none has a constructor.
- Not formed, the start of the line apart from `corner`, and the stack order other than fullest first, which is the same model: as a branch, the case at its stored start gives the concept's output on every pair, so it fails Fit at train0 and train1 like the concept, and is not added.
- Not formed, a rule that drops one 2x2 square by position or neighbors: the item gives no reading to form, since `probe_features.py` found no such feature.
- Layout of stacks of unequal width: the slot of a stack is its largest square's box extended by `gap` past the corner opposite `corner` (`edge_outset` and `compose`, then `box_extent`). The output's lines along `axis` are the slots' lines in lexicographic order (stack, then line within its slot) through `Order`, laid out by `DirFrame` from their ranks. The lines across `axis` are the largest slot's. This keeps the cumulative offsets out of the program.
- Stacks are the cells of an `AxisFrame` as long as the largest count. Stack i holds a color when i is less than the color's count, which is a bound comparison.
- Squares are drawn per axis: a cell is covered by a color when its distance to each of the corner's edges is less than the color's extent on that axis. A smaller square is on top, with the sizes compared along `axis`.
- Background is in `Parse`, because the determination reads it too.
- Determination: `corner` is each corner whose cell is background in no train output. `axis` is each axis along which no train output is shorter than across. `gap` is the least distance from the far edge across `axis` of a non-background output cell, kept where every train output agrees (`Unanimous`).
- `derive`: no built-in derivation fits. `store`: no case that takes a stored value fits the pairs, since the concept case fails train0 and train1.
- Keywords `objects noise count rank overlay`: the squares are pieces, the noise is told apart, counts set the stacks, size orders the drawing, and the squares stack on one frame.

## Open
- The task data: train0 and train1 expected outputs. A patch that gives each of them five 2x2 stacks, or a ruling that the task stays as given, would settle whether the concept case is the solver.
- `deletions` did not run ("baseline fails: stored source does not pass train+test"), so Simplify had no deletion report. It runs once train0 and train1 pass.
- `sweep` skipped every parameter ("stored value fails train"). It runs once train0 and train1 pass.

## Lib
- Laying an order out as a line of positions (an `Order` rank fed to `DirFrame.dist_set`): solver-local form `lines.dist_set($U(), R) :- columns.rank($U(), _, R).` with `lines.dir` from the start edge. Sites: 22425bda, 291dc1e1, 68bc2e87, f8b3ba0a, f8ff0b80.
- Concatenating slots of unequal width along an axis: solver-local form is `Order<Unit, Column>` over `[stack, line]` with `before` taking an earlier stack, or an earlier line of one slot, then the rank-to-`DirFrame` step above. The grep found no other site.

## Fixes elsewhere
none

## Tickets filed
- 10-265_task_b1986d4b_create.md
