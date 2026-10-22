# ad173014

## Departures
- The report's `empty-box` point, with three branches, is two nested points in the solver (create.md). `Membership` is `EveryBoxMember {hand: EmptyHand} | SkipEmptyBoxes {}`, and `EmptyHand` is `HandsNothing {} | EmptyBoxErases {}` under `EveryBoxMember`. The models and witness outputs are unchanged, and `witness --file work/task/ad173014/witnesses.json` is ok. By Principles, a choice point stands under a branch when its property exists only with that branch. What an empty box hands on exists only when empty boxes are members. This pass judges that the departure holds.
- The witness file has one witness that the Analyze file does not: `big-box-dominant` (create.md). Without it, `witness --witness-file` reports that no witness separates `background=stored` from `background=DominantColor` among the `$BboxRingOrder` cases. On the Analyze witness `background=DominantColor`, both of those cases are undefined. In the new input, the loop's corner lies inside a large box of 3 that outnumbers 0. The stored background recolors the 3 shape to 4. The derived background (3) recolors the large box's one 0 cell to 4 and gives the bottom box 0. This pass judges that the departure holds.

## Judgments
- How the program reads `sense` (create.md, changed in this pass): at each end cell of a loop segment, the program steps into the box frame. If the enclosed side lies a quarter turn in `sense` from that step, the box is ahead. If it lies a quarter turn against `sense`, the box is behind. `next(A, B)` joins the box behind a segment to the box ahead of it. A clockwise walk has the inside of the loop on its right.
- Box at a loop corner (the open item of create.md, settled): `inward` finds the enclosed side of an end cell in one of two ways. An enclosed cell is next to the end cell on that side, or an outside cell is next to it on the opposite side. Before this pass, only the first way was in the program. A segment that ends at a loop corner, where the line turns at a box's edge, then had no `next`, and every case was undefined. With the second way, every case gives the turned colors on such an input: a top row that turns down into the top edge of the right-hand box, with three boxes. On that input, no two cases differ, and every case gives what the concept gives, so it is no witness. The output of every witness of the witness file and of the Analyze file is unchanged (`record --all`: groups unchanged).
- `outside` is the cells that `Closed` holds and that no closed region holds, under `$LoopWalk`. Under `$BboxRingOrder`, it is the cells outside the bounding box of the line cells.
- The enclosed side of the loop is the cells that the line cells and the box cells close off from the grid edge (`Closed` over the cells that are neither line nor box). It does not read `background`, so the `background=DominantColor` case gives the Analyze file's grid (create.md).
- `$BboxRingOrder` uses the same segment clauses. Its track is the ring of the line cells' bounding box, less the cells of member boxes, and its enclosed side is that box's interior. It is undefined where a box has no cell on the ring, as the report states (create.md).
- `$SkipEmptyBoxes` adds the frame of a box with no shape to the loop's track, so the cycle runs through that box. `$EmptyBoxErases` has an empty member box hand on `background` (create.md).
- Boxes are found with `Outlines` over `frame_color` cells (`@claim boxes-on-loop`). Shape colors come from `Unanimous` (`@claim one-shape-per-box`), so a box whose shape has two colors leaves its predecessor undefined (create.md).
- `$ShapesMove`, `$LexCycle` and `$StoredColorMap` have no constructor. The report gives each as failing Fit (create.md).
- Keywords: `objects` (the boxes), `chain` (the loop links the boxes into one cycle, and the rule reads their order along it), `permutation` (the colors shift one step around that cycle) (create.md).
- `big-box-dominant` (a further witness of the `@derive DominantColor` branch, with no `@witness` line): plausibility `foreign`, verdict `concept`. Its box is larger than the rest of the grid, with the loop's corner inside it. The field stays 0 as the concept reads it (create.md).
- The witnessed cases are 7 of 24. The seventh, beside the concept case and the six branch models, is `$BboxRingOrder & background=DominantColor`. On the `background=DominantColor` witness, its partial grid differs from that of `$BboxRingOrder`.
- Sweep: the train pairs also admit `step` values 13 and 25. `step` is not open: the concept reads the next box, so it stays 1. Under `$BboxRingOrder`, `line_color` also admits 2. One value serves every case, so `line_color` has no case column (create.md).
- Determination plan: no actions, so the solver has no `Determine` comp (create.md).
- Deletions: these removals change no pair's output, and each stays.
    - `member(M, B)` in `touch`, the `track` rule for the frames of boxes that are not members, and the `$EmptyBoxErases` `handed` rule: the `empty-box` witness uses each of them (create.md).
    - Each disjunct of `inward`, and each `enclosed` and `outside` rule: at an end cell on a straight run, either disjunct alone finds the enclosed side. The `outside` disjunct is needed at a loop corner. The `enclosed` disjunct is needed where the outer neighbor of an end cell is a line or box cell.
    - `params.frame_color(Col)` in `outlines.node`: `deletions` timed out at 2 s on it. A scratch copy without the atom ran in 36 s and failed every pair, because the loop is itself a rectangle outline. The atom stays. This settles the other open item of create.md.
- Audit, `witness`, and `witness --file work/task/ad173014/witnesses.json`: ok. No lint hint fired.

## Open
- none

## Lib
- The cells of a rectangle outline: `frame(B, P) :- outlines.box($U(), B), in(P, _), box_edge(P, B, _).` The grep found the same shape at 1c786137:56, 810b9b61:45 and 64, 890034e9:36, 8a6d367c:121, 917bccba:95, and a6f40cea:221 (create.md).

## Fixes elsewhere
- none

## Tickets filed
- 10-196_task_ad173014_refine.md
- 10-197_task_ad173014_refine.md
