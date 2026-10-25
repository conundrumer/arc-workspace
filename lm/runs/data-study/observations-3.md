# Observations, third set: marks not in observations.md

From the tables of three more gold solvers: [9565186b](case-9565186b.md) (keep the majority color, gray the rest), [7c008303](case-7c008303.md) (recolor a pattern quadrant by a key quadrant) and [8e5a5113](case-8e5a5113.md) (fill tiles with quarter turns of a pattern tile). Each mark below is new against [observations.md](observations.md) or contradicts it.

## Marks that a table adds no signal

- **A table equal to its whole domain after a NOT.** 8e5a5113 &r21 is all 8 transforms at assignments 3 and 7, because the mismatch table &r20 it negates is empty there. The check tested nothing.
- **The last table at the size of the output, with the wrong content.** 8e5a5113 &r33 has 33 rows at twelve assignments, the input unchanged. A row count equal to the output's cell count is not a match.
- **A sibling case's chain that the output does not read.** 9565186b &r3, &r7 and &r22 to &r32 compute the components for `$BlobColor` and `$Blob`, inside the case `$Count`.

## Marks that a table adds signal

- **The input alone kills DET assignments.** 8e5a5113 &r6 is empty at 3 of its 4 assignments, before any table reads the outputs, and &r14 is empty at 14 of 16. This contradicts observations.md's point that only a comparison with the outputs picks the assignment.
- **A row count that varies over the examples.** 9565186b &r13 has 1, 1, 1 and 3 rows: the 3 are a tie at count 2 in example 3.
- **One row of difference from an earlier table.** 9565186b &r7 equals &r0 except in example 3, where color 8 splits into two components.
- **The same values under other keys in each example.** 7c008303 &r8 holds 2 and 6 in every example, but under T, B, L, R as 2 6 2 6, 2 6 6 2 and 6 2 2 6: where the cross sits.
- **A count of distinct colors per region that tells the roles apart.** 7c008303 &r23 gives 4 colors to the key quadrant, 1 to the pattern and no row to the blank quadrants.

## What I could not tell from a table alone

- **Which of two hypotheses the train data supports.** 9565186b &r14 (the most cells per color) and &r25 (the color of the largest component) agree at every train example and at the test.
- **Which of two surviving assignments is the case's.** 8e5a5113 &r21 is D4_CC at DIR_L and D4_CW at DIR_R, and both hold for the train outputs.
- **What frame a Box is in**, which goes past what kind of value it is. In 7c008303 &r22, `r0-7 c0-3` is cell (0,0) of a 2x6 quadrant, and `(0,0)out` in &r25 is a cell of the 6x6 pattern, not of the output.
- **That the program fails.** 8e5a5113 &r33 holds 15 of the 33 output cells at the four assignments with the parse, and only &r23's one row at step 0 shows why.
- **That a table matches the output, where its first Box column is not the output cell.** 7c008303 &r30 equals the output, but the drawing goes by c0, the key's quadrant, so no drawing is made.
- **What an axis names.** 7c008303 &r1 puts AXIS_V on the row `r2-2 c0-8`.

## Marks seen again

- Rows equal to an earlier table's: 7c008303 &r4 = &r1; 8e5a5113 &r16 = &r15.
- Rows that follow from a smaller table and the grid size: 7c008303 &r16 and &r17 (288 rows each).
- Constant columns, or the same rows in every example: 7c008303 &r27; 8e5a5113 &r8.
- An assignment empty at every example: 8e5a5113 &r14 to &r33.
- A selection much smaller than its parent: 7c008303 &r1 (2 of 18 lines).
- A first table read from the outputs: 9565186b &r10; 8e5a5113 &r13.
- Many rows reduced to one or two: 9565186b &r14; 7c008303 &r24.
- What a product lacks: 8e5a5113 &r15 lacks D4_CW.
- A match between an input table and the outputs: 9565186b &r21 and &r33; 7c008303 &r30.
- An Ident equal across examples for the same cell set: 9565186b id5.
- A table not read at all: 9565186b &r11, &r12, &r15, &r16.
