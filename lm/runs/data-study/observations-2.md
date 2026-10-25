# Observations 2: marks new against observations.md

From three more gold solvers: [44f52bb0](case-44f52bb0.md) (classify a 3x3 input by its mirror symmetry, output 1 or 7), [5ad8a7c0](case-5ad8a7c0.md) (fill the span of the closest pair of marks) and [6d1d5c90](case-6d1d5c90.md) (drop a band, rotate the rows by the marker's row). This file lists only what [observations.md](observations.md) does not have, or what contradicts it, with one example each.

## Marks that a table adds no signal

- **A complement inside a product.** 44f52bb0 &r16, the pairs of examples whose outputs differ, is &r10 x &r10 minus &r13.
- **A class written as pairs.** 44f52bb0 &r12 gives the two output classes as 18 pairs, where a class label per example takes 6 rows.
- **A lib fact restated.** 44f52bb0 &r22 is `sym_member`, 31 rows, the same for every task.
- **DET assignments equal in pairs.** In 6d1d5c90, from &r3 to &r18, &r0 = DIR_T gives the same tables as DIR_B, and DIR_L gives the same tables as DIR_R. The tables read only the axis of the direction, so four values give two distinct tables.
- **A closure bounded by a per-example value.** 6d1d5c90 &r24 walks every step up to the shift amount, 6 x (amount + 1) rows. The next clause reads only the rows at the amount.
- **A gold case that is empty from an INIT on.** In 3eda0437 `$Area` (no case file), the BoundingBox INIT's cell input is SKIP. So &r3 and every table after it are empty at every example, and the final table is the input with no cell painted.

## Marks that a table adds signal

- **The empty entry holds the most information.** 44f52bb0 &r0 has 0 rows in e0, because every D4 transform leaves e0 unchanged.
- **The entries split the examples as the outputs do.** In 44f52bb0 &r0, the 4-row examples (e2, e3) and the empty e0 are the "1" class, and the 7-row examples are the "7" class. This shows before any table is read from the outputs.
- **"Empty in some examples" is the rule.** 44f52bb0 &r25 is empty in exactly the examples that give 1. 5ad8a7c0 &r27 is empty in exactly e1 and e3, the examples whose output equals the input. This contradicts the README, where such a table is of questionable viability.
- **One row in every example picks the DET's value.** 6d1d5c90 &r12 has one marker in each example only at &r9 = DIR_L. At DIR_T it has a row in e0 only, and at DIR_B and DIR_R it is empty. This contradicts "which DET assignment is the case's" in observations.md: here, the table alone tells.
- **A row count that matches an earlier table's only at one assignment.** 5ad8a7c0 &r13 (pairs) has 4, 8, 6, 8, 8 rows at AXIS_H, equal to &r2 (marks): every mark has one partner. At AXIS_V it has 4, 4, 4, 4, 8.
- **A task-wide entry that holds the test inputs.** 44f52bb0 &r5 includes e6 and e7, and &r18 puts e7 in the "7" class. The answer for test 1 is in a DET's rows.
- **A row count that encodes a value.** 6d1d5c90 &r24 has 6, 18 and 24 rows, which gives the shift amounts 0, 2 and 3 with no Number read.

## What could not be told from a table alone

- **A move in a later column, hidden by the drawing.** 6d1d5c90 &r27 is drawn by c0, the input cell, so at all four live assignments it shows the input without the band. The rotation is in c10, the output cell.
- **The sign of a direction.** 6d1d5c90 &r23 gives the amounts 0, 2, 3 at &r0 = DIR_B and 5, 3, 2 at DIR_T. Each has one row per example, and only the outputs tell which is right.
- **What a lib DET's value means.** 6d1d5c90 &r10 is 1 and &r11 is 2. The table holds only the value. Only the clause's DET name (DimDiff, RarestColor) tells that these are the band's width and the marker's color.

## Existing marks seen again

- Rows equal to an earlier table's, or a projection: 44f52bb0 &r1, &r13, &r24; 5ad8a7c0 &r14, &r15.
- Rows as many as the grid's cells: 6d1d5c90 &r2.
- Rows that follow from a smaller table and the grid size: 5ad8a7c0 &r3, &r8.
- Constant columns, or the same rows in every example: 5ad8a7c0 &r7, &r12; 6d1d5c90 &r1, &r13 to &r18.
- An assignment empty at every example: 6d1d5c90 &r23, 8 of 16.
- A selection much smaller than its parent: 5ad8a7c0 &r2.
- A first table read from the outputs: 44f52bb0 &r11.
- A functional dependency in every row: 44f52bb0 &r26 and &r27 (class to color); 5ad8a7c0 &r19 (Example to least gap).
- Many rows reduced to one: 44f52bb0 &r21 (SYM_BOX).
- What a table lacks: 44f52bb0 &r17 lacks HT, LR and TB.
- A match between a table from the inputs and the outputs: 5ad8a7c0 &r27 at AXIS_H.
- Which DET assignment is the case's: 5ad8a7c0 &r28 and 6d1d5c90 &r27, a whole grid at a wrong assignment.
- Which column is which: 6d1d5c90 &r27, columns c0 to c13.
- Rows repeated: 5ad8a7c0 &r16 and &r27, each cell once from each end of its pair.
- Tables that nothing reads: 5ad8a7c0 &r17, &r18, &r20 to &r22.
