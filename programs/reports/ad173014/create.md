# ad173014

## Departures
- The report's `empty-box` point, with three branches, is two nested points in the solver. `Membership` is `EveryBoxMember {hand: EmptyHand} | SkipEmptyBoxes {}`, and `EmptyHand` is `HandsNothing {} | EmptyBoxErases {}` under `EveryBoxMember`. The models and witness outputs are unchanged, and `witness --file work/task/ad173014/witnesses.json` is ok. This rests on two things. First, the flat type gave the lint finding `choice-tag`, because the `member` clause of `$EveryBoxMember` and `$EmptyBoxErases` was the same. Second, by Principles, a choice point stands under a branch when its property exists only with that branch: what an empty box hands on exists only when empty boxes are members.
- The witness file has one witness that the Analyze file does not: `big-box-dominant`. The audit found no witness that separates `background=stored` from `background=DominantColor` among the `$BboxRingOrder` cases. On the Analyze witness `background=DominantColor`, both of those cases are undefined, because the large box has no cell on the ring. The new input has the loop's corner inside a large box of 3 that outnumbers 0, so every box has a cell on the ring. There, the stored background recolors the 3 shape to 4, and the derived background (3) recolors the large box's one 0 cell to 4 and gives the bottom box 0.

## Judgments
- How the program reads `sense`: at each end of a loop segment, the program steps from the end cell into the box frame. If the enclosed side lies a quarter turn in `sense` from that step, the box is ahead. If it lies a quarter turn against `sense`, the box is behind. `next(A, B)` joins the box behind a segment to the box ahead of it. This rests on the fact that a clockwise walk has the inside of the loop on its right.
- The enclosed side of the loop is the cells that the line cells and the box cells close off from the grid edge (`Closed` over the cells that are neither line nor box). It does not read `background`. A first version closed off `background` cells instead, and its `background=DominantColor` case was undefined on that Analyze witness. With this reading, the case gives the Analyze file's grid.
- `$BboxRingOrder` uses the same segment clauses. Its track is the ring of the line cells' bounding box, less the cells of member boxes, and its enclosed side is that box's interior. It is undefined where a box has no cell on the ring, as the report states.
- `$SkipEmptyBoxes` adds the frame of a box with no shape to the loop's track, so the cycle runs through that box. `$EmptyBoxErases` has an empty member box hand on `background`.
- Boxes are found with `Outlines` over `frame_color` cells (`@claim boxes-on-loop`). Shape colors come from `Unanimous` (`@claim one-shape-per-box`), so a box whose shape has two colors leaves its predecessor undefined.
- `$ShapesMove`, `$LexCycle` and `$StoredColorMap` have no constructor. The report gives each as failing Fit.
- Keywords: `objects` (the boxes), `chain` (the loop links the boxes into one cycle, and the rule reads their order along it), `permutation` (the colors shift one step around that cycle).
- `big-box-dominant` (a further witness of the `@derive DominantColor` branch, with no `@witness` line): plausibility `foreign`, verdict `concept`. Its box is larger than the rest of the grid, with the loop's corner inside it. The field stays 0 as the concept reads it.
- Sweep: it reports that the train pairs also admit `step` values 13 and 25. `step` is not open: the concept reads the next box, so it stays 1. Under `$BboxRingOrder`, `line_color` also admits 2. One value serves every case, so `line_color` has no case column.
- Determination plan: no actions, so the solver has no `Determine` comp.
- Deletions: three removals change no pair's output. These are `member(M, B)` in `touch`, the `track` rule for the frames of boxes that are not members, and the `$EmptyBoxErases` `handed` rule. The pairs have no empty box, so they never use these structures. The `empty-box` witness uses each of them, so all three stay.
- No lint hint fired. Every run took a few seconds or less, so there is no performance issue.

## Open
- `deletions` timed out (2 s) on the removal of `params.frame_color(Col)` from `outlines.node`, so that removal was not judged. A run with a longer timeout would settle it.
- A box placed where a loop corner meets it gives the segment's end cell no cardinal neighbor on the enclosed side, so that box has no `next`, and every case is undefined. The pairs never place a box at a corner. A witness with a box at a loop corner, and a verdict on it, would settle whether the concept should be defined there.

## Lib
- The cells of a rectangle outline: `frame(B, P) :- outlines.box($U(), B), in(P, _), box_edge(P, B, _).` The grep found the same shape at 1c786137:56, 810b9b61:45 and 64, 890034e9:36, 8a6d367c:121, 917bccba:95, and a6f40cea:221.

## Fixes elsewhere
- none

## Tickets filed
- 10-85_task_ad173014_create.md
