# Marks of signal in a table

The marks the readers used over fifteen gold solvers ([observations.md](observations.md) and observations-1 to -4), gathered as candidate detectors: each is a function of a table, or of a table with the tables before it, that a program can compute at decode time. Each line names one case and table that shows it.

## Filters: the table adds no signal

- Empty in every train example, and not read under `NOT` later (1fad071e &r17).
- Faulted, or stopped at the engine's work cap.
- Rows equal to an earlier table's, or a projection of one onto fewer columns (0ca9ddb6 &r25, &r27, &r41, &r43; 1fad071e &r4 = &r2; 3979b1a8 &r13 = &r3).
- A rank or order equal to its score, with no gap (bda2d7a6 &r21 = &r13).
- A lib fact restated, the same in every task (44f52bb0 &r22, `sym_member`).
- A product of column groups that share no variable: the same count at every cell of the drawing (0ca9ddb6 &r25; 3979b1a8 &r30), or a witness column that multiplies the rows (22425bda &r4, 91 rows for 14 line cells; 3979b1a8 &r28, 1800 rows for 9 pairs).
- A complement inside a product (44f52bb0 &r16 = &r10 × &r10 − &r13).
- A class or an order written as pairs (44f52bb0 &r12, 18 pairs for 6 labels).
- Each row twice, once per order of a symmetric pair (e633a9e5 &r15, &r20, &r21; 5ad8a7c0 &r16).
- One row per grid cell, restating the input (3ac3eb23 &r6; 0ca9ddb6 &r34; b5bb5719 &r32).
- Rows that follow from a smaller table and the grid size (0ca9ddb6 &r22, each dot's row and column to the edges; 2c608aff &r19, &r20).
- Rows that name cells off the grid, which nothing joins (b5bb5719 &r16, &r21).
- A closure walked to a bound, where the reader takes the last step only (6d1d5c90 &r24).
- A table equal to its whole domain after a `NOT` of an empty table (8e5a5113 &r21).
- Assignments of a DET equal in pairs, where the table reads only the axis of a direction (22425bda &r24; 6d1d5c90 &r3 to &r18; b5bb5719 &r9).
- A second chain that finds a fact already found, in other terms (3979b1a8 &r24 to &r26 after &r20 to &r22).

## Graded signals of one table against its parents

- A selection much smaller than its parent (0ca9ddb6 &r14, 15 dots of 324 cells; 7c008303 &r1, 2 of 18 lines).
- Many rows reduced to one or two: a direction, a period, a color pair, a count (3ac3eb23 &r4, &r14; 0ca9ddb6 &r29; 44f52bb0 &r21).
- A functional dependency that holds in every row (0ca9ddb6 &r28, mark color to paint color; 1fad071e &r28, example to bar length; e633a9e5 &r8).
- A one-to-one map between the values of two columns (bda2d7a6 &r26, the recolor).
- A regularity across the examples: the same shape around each seed, the same parity pattern in every row (0ca9ddb6 &r16; 3ac3eb23 &r8; b5bb5719 &r24).
- The same values under other keys in each example, which tells where a thing sits (7c008303 &r8).
- A count that varies over a shape: interior, edge, corner (2c608aff &r14), or a count of distinct values per region that tells roles apart (7c008303 &r23).
- A Number column that varies where the count drawing is flat (e633a9e5 &r5, extents 2 and 1).
- One row of difference from an earlier table (9565186b &r7 against &r0).
- An intersection over the examples of a table that was mostly chance (e633a9e5 &r3 keeps 25 of &r1's 154 pairs).
- A row count that varies over the examples, where a tie shows (9565186b &r13: 1, 1, 1, 3).
- A row count that encodes a value (6d1d5c90 &r24: 6, 18, 24 rows for shifts 0, 2, 3).
- A number equal to a size of the output (22425bda &r20: 2, 3, 4, 5, the output widths).
- What a product lacks: a direction, a transform, a distance missing from a near-complete product (3ac3eb23 &r3 lacks DIR_T; 1fad071e &r31 lacks DIR_L; 8e5a5113 &r15 lacks D4_CW; 3979b1a8 &r32, no row at distance 3).
- Empty in some examples, where those examples are the ones whose output differs from the rest (44f52bb0 &r25; 5ad8a7c0 &r27; bda2d7a6 &r15), or where the empty entry is the fact (44f52bb0 &r0, no transform changes e0).
- Empty in every example, read under `NOT`: the fact is that nothing fired (3979b1a8 &r21, &r25).

## Relations between tables, and across a DET's assignments

- A table built from the inputs that matches a table built from the outputs, in rows or in cells (1fad071e &r21 at assignment 4 = &r28; 0ca9ddb6 &r51 and &r15; 3ac3eb23 &r31 and &r7; 9565186b &r21 and &r33; e633a9e5 &r22; bda2d7a6 &r68).
- The inputs alone kill assignments: a table empty at most assignments before any output is read (8e5a5113 &r6, 3 of 4; &r14, 14 of 16; b5bb5719 &r22, 6 of 8).
- One assignment at which a table differs from its source, or has one row in every example (b5bb5719 &r18 at DIR_B; 6d1d5c90 &r12 at DIR_L).
- A row count equal to an earlier table's at one assignment only (5ad8a7c0 &r13 = &r2 at AXIS_H: every mark has one partner).
- An assignment whose Boxes fit the output grid (22425bda &r24 at DIR_L and DIR_R).
- Assignments that all agree though their source differs between them (bda2d7a6 &r44 to &r52).
- The entries split the examples as the outputs do, before any output is read (44f52bb0 &r0).
- A row count that tracks a grid quantity: the input's cells, the output's size, cells times offsets (88e364bc &r8; 45a5af55 &r11, &r17, &r22; 332f06d7 &r25). A row count equal to the output's cell count is not a match (8e5a5113 &r33, the input unchanged).

## Not told by the table, with the earlier tables in view

- Which of two surviving assignments is the case's, where both hold on the train pairs (8e5a5113 &r21, D4_CC at DIR_L and D4_CW at DIR_R; 22425bda &r27; 6d1d5c90 &r23, the sign of a direction).
- Which of two hypotheses the train pairs support, where both agree on every train example (9565186b &r14 and &r25; bda2d7a6 &r31 and &r13).
- Whether a table is read whole, in part, under `NOT`, or never (1fad071e &r31; 0ca9ddb6 &r22; 2c608aff &r14; 5ad8a7c0 &r17 to &r22).
- What a lib DET's value means without the clause (1fad071e &r1; 6d1d5c90 &r10, &r11).
- Whether rows equal in every example are a step or a restatement, where every input has one size (e633a9e5 &r14 to &r21, the rule's tile offsets).
- Whether a table that states the scene belongs to this case (b5bb5719 &r4, read by no clause).
- Signal that no clause reads but that a human would (2c608aff &r5, the least-counted color is the marker color).
