# Observations 4: marks new against observations.md

From three more gold solvers: [e633a9e5](case-e633a9e5.md) (scale each cell to a tile, 2 wide on a grid edge), [b5bb5719](case-b5bb5719.md) (grow a pyramid under the seed pairs, swapping 2 and 5) and [bda2d7a6](case-bda2d7a6.md) (cycle the colors of nested rings). Each mark is one that [observations.md](observations.md) does not state, or one that goes against it, with one example.

## Marks that a table adds no signal

- **Rows that name cells off the grid.** b5bb5719 &r16 and &r21 give each cell its neighbors, and at an edge these print as margins with a negative entry: `[-1 3 0 4]` is row -1. No input cell joins them.
- **Each row twice, once per order of a symmetric pair.** e633a9e5 &r15 and &r21 hold each tile once for (AXIS_V, AXIS_H) and once for (AXIS_H, AXIS_V); &r20 does the same for the opposite sides.
- **An assignment whose rows equal another assignment's, or the table's own source.** b5bb5719 &r9 is equal at DIR_T and DIR_B, as it reads only the axis. &r18 equals its seeds, &r17, at 6 of its 8 assignments.
- **A rank equal to its score.** bda2d7a6 &r21 ranks the colors by first depth and equals &r13, since the depths are 0, 1 and 2 with no gap.
- **A row for each value of a pair relation, where the cell holds one.** b5bb5719 &r29 has `(0,1) | 2 | (1,2) | 5` and `(0,1) | 5 | (1,2) | 2`, though (0,1) holds only 5.
- **A first table read from the outputs that is mostly chance.** This goes against observations.md. In e633a9e5 &r1, the 5 at (0,1) of e0 pairs with all ten 5s of the output. The signal comes only at &r3.

## Marks that a table adds signal

- **An intersection over the examples whose count drawing has a shape.** e633a9e5 &r1 has 154 same-color pairs, mostly chance. &r3 keeps the 25 pairs that hold in every example, and its count drawing, `4 2 4` / `2 1 2` / `4 2 4`, is each cell's tile area.
- **One DET assignment at which a table differs from its source.** b5bb5719 &r18 grows past the seeds only at DIR_B, and &r22 is empty at the other 6 assignments. Here the case's assignment is visible without the outputs.
- **Assignments that all agree though the source differs between them.** bda2d7a6 &r34 ranks the cells differently at each of 8 scans, but &r44 to &r52, which drop the cell, are equal at all 8: the rings are symmetric under the scans.
- **A table empty in some examples that marks the exception.** bda2d7a6 &r15 is one row, `8 | 0 | 3`, in e2 only: the one color found in two rings.
- **A one-to-one map between colors.** bda2d7a6 &r26 maps the three colors of each example to each other, and read from c1 to c0 it is the output's recolor.
- **A Number column that varies where the count drawing is the same at every cell.** This goes against observations.md, which reads the same count at every cell as no signal. e633a9e5 &r5 draws 2 at every cell, one row per axis, and c2 holds the extents 2 and 1.

## What I could not tell from a table alone

- **Whether a table that states the scene belongs to this case.** b5bb5719 &r4 gives DIR_T, the edge that every seed is on, but this case takes its direction from DirDomain, and no clause reads &r4.
- **Which of two orders the rule uses, where the train pairs agree on both.** bda2d7a6 &r31 (cell counts) orders the colors as &r13 (first depths) does in all three examples.
- **What changes in a table with two Color columns.** b5bb5719 &r32 and bda2d7a6 &r68 draw 1 at every cell, and the change of color shows only in the rows.
- **Whether rows that are the same in every example are a step or a restatement, where all inputs have one size.** This goes against observations.md. e633a9e5 &r14 to &r21 are equal in the three 3x3 examples, and they are the rule's tile offsets.

## Seen again

- Rows equal to an earlier table's: bda2d7a6 &r21 and &r13; b5bb5719 &r11 and &r2.
- The same count at every cell: b5bb5719 &r16.
- Rows as many as the grid's cells: b5bb5719 &r32, bda2d7a6 &r40.
- Rows that follow from a smaller table and the grid size: bda2d7a6 &r0 and &r4, e633a9e5 &r10.
- Constant columns, or the same rows in every example: bda2d7a6 &r55 to &r60.
- An assignment empty at every example: b5bb5719 &r22, &r23 and &r29.
- A selection much smaller than its parent: b5bb5719 &r2.
- A functional dependency that holds in every row: e633a9e5 &r8, bda2d7a6 &r10.
- Many rows reduced to one or two: bda2d7a6 &r23 and &r24.
- A regularity across the examples: b5bb5719 &r24.
- A match between a table from the inputs and one from the outputs: e633a9e5 &r22, bda2d7a6 &r68.
- Which DET assignment is the case's: b5bb5719 &r27 (the sense).
- What a lib DET's values are: e633a9e5 &r0.
- Which column is which: bda2d7a6 &r68.
- What kind of value a Box is: e633a9e5 &r10 and &r12.
- Whether a table is read whole, under NOT, or not at all: e633a9e5 &r2, bda2d7a6 &r34 to &r53.
