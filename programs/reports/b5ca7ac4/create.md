# b5ca7ac4

## Departures
- `box_size=stored` is not held, so it has no case. Its name is removed from every group in the witness file, and the `box_size=stored` witness is removed because it then separates nothing: `store` prints no `@store` line for a square side. The program tests each outline for squareness and derives no side value that has one value per input. The Analyze report also found that this branch gives the concept's output wherever it is defined.
- `$HeadingOpposite` reads its own parameters, `lead_heading` and `trail_color`, and does not read a one-row `heading`: its form differs from the concept's two-row `heading` table ([Shared form](docs/handbook/principles.md)). If the case read `heading` through a case column, an `assign` of `heading` would reach both cases, and the `perpendicular-headings` witness would not separate them.
- The stored `$HeadingOpposite` values are lead 2 → `DIR_R` and trail 8. The Analyze report has lead 8 → left. The determination makes the lead the frame color with more cells in the train outputs, because `Color` has no order (`typed-order` lint). Both assignments give the same model.
- In the witness file, the `assign` of `perpendicular-headings` adds `lead_heading` = (2, `DIR_B`). With it, `$HeadingOpposite` gives the Analyze file's grid for that witness (8 up, 2 down). Against the Analyze file, `$HeadingOpposite` gives 8 left and 2 right on that witness. The reason is that the Analyze file's `assign` sets only `heading`, which that case does not read.

## Judgments
- Constructor names chosen for concept branches: `Squares` (body-parse), `Adjacent4` (adjacency), `StoredHeading` (heading-source), `OutsideBodies` (background).
- Square parse: `Outlines` per frame color, then a square test on the box's two extents, then one interior color (`Unanimous` over `interior` cells). The parse keeps only framed squares that lie inside no other framed square of any color. That test across colors is needed: in train2, the 8-framed square at rows 1–5, cols 3–7 has a solid 2 interior, and `Outlines` on 2 finds a 3×3 framed square at rows 2–4, cols 4–6.
- Every parse relation is keyed by the heading reading. Before that change, the `case section` hints showed that the `$Squares & $HeadingOpposite` cases read `params.heading` through a union over the heading readings.
- Not formed, the bounding-box contact: I formed it as a branch under `$FrameComponents`. It fails Fit at train0. The 2-framed squares at rows 13–17, cols 0–4 and rows 16–20, cols 5–9 share an edge at rows 16–17. The box of the body they form (rows 13–20, cols 0–9) differs from its cells. `$Adjacent4 & $BoxContact` gave a wrong grid there, and `$Adjacent8 & $BoxContact` gave conflicting colors at (7,8) and (7,9). The Analyze report says no pair shows such a body, and train0 shows one. Under `$Squares`, the branch is equivalent to the concept.
- Not formed, a stored background color: it fails Fit. The background is 0, 4 and 1 across the train pairs.
- Not formed, squares that push squares of the other frame color: it fails Fit at train2. The 8-framed square at rows 5–9, cols 12–16 and the 2-framed square at rows 8–12, cols 2–6 head toward each other on rows 8–9. A push would move one of them away from its place in the output.
- `derive` reports no built-in derivation that fits.
- The sweep shows 20 single-row changes of `heading` that give every train output. Each one adds a row for a color that no reader would take as a frame color, so none is an open value, and `heading` keeps its stored set.
- Determination of `heading`: a frame color slides toward an edge that its color reaches in every train output.
- Deletions: I removed the atoms that are redundant (`box_corner` in `square_box`, `square` in `square_fall.dir` and in `moved`, `impl_choice` in `background`, `color_cells.domain`). I kept the square test, `fill.value` and `opposite` in `lead_trail`, because they state concept claims that the pairs do not exercise.
- Single-consumer hints on `component_id` and `outer_component`: I inlined both relations.
- Keywords: `objects move lookup enclose`. `lookup` is for the stored `heading` table, which fixes where each square goes. `enclose` is for the closed-off cells that `$FrameComponents` adds to a body.
- I built no new witness. The plausibility and verdict of each witness are the Analyze report's.

## Open
- The `$HeadingOpposite` determination breaks the lead/trail tie by cell count, and it fails when the two frame colors have equal counts. A handbook rule for picking one of two assignments that a relabeling makes equal would settle it (ticket 10-380).

## Lib
- A component together with the cells it closes off from the grid edge (a filled component), where a component inside another component's closed-off cells belongs to that one. Solver-local form: `enclosed = Closed<ComponentKey>` fed with the cells outside each component, then `nested` and `frame_body`. The grep found the same `Closed`-per-component shape at `programs/solvers/a680ac02.dl:185`, `programs/solvers/b2862040.dl:173` and `programs/solvers/a5313dff.dl:117`.

## Fixes elsewhere
- none

## Tickets filed
- 10-379_task_b5ca7ac4_create.md
- 10-380_task_b5ca7ac4_create.md
