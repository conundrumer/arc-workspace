# Observations: telling from a table that it adds signal

From reading the tables of three gold solvers along their programs: [1fad071e](case-1fad071e.md) (count the 2x2 blocks, draw the count as a bar), [0ca9ddb6](case-0ca9ddb6.md) (stamp a star around each marked dot) and [3ac3eb23](case-3ac3eb23.md) (a period-2 trail down from each marker). Each mark below is one I used, with one example.

## Marks that a table adds no signal

- **Rows equal to an earlier table's, or a projection of them.** 0ca9ddb6 &r25, &r27, &r41 and &r43 hold equal rows, 1215 each. 1fad071e &r4 equals &r2 at every assignment.
- **The same count at every cell of the drawing.** 0ca9ddb6 &r25 draws 2, 5, 3 and 5 at every cell, the count of dots of each example: a product of the dots with the grid.
- **Rows as many as the grid's cells, one per cell.** 3ac3eb23 &r6 (60 and 42 rows) and 0ca9ddb6 &r34 (81 rows of color 1) restate the input's cells.
- **Rows that follow from a smaller table and the grid size.** 0ca9ddb6 &r22's 300 rows are each dot's row and column out to the grid's edges. &r29 keeps the 16 of them that fall on a star cell, all at K = 1.
- **Constant columns, or the same rows in every example.** 3ac3eb23 &r5 is &r1 with DIR_T and DIR_B added. 0ca9ddb6 &r30 is the same 4 rows in each example. 1fad071e &r27 is one task-wide color, copied per example.
- **An assignment empty at every example.** Seven of the nine assignments of 1fad071e &r17, &r18 and &r33 are empty.

## Marks that a table adds signal

- **A selection much smaller than its parent, of cells that stand out in the drawing.** 0ca9ddb6 &r14 is 15 dots in place of 324 cells. 1fad071e &r15 is one box per component, with the 2x2 blocks as single rows.
- **A first table read from the outputs.** 0ca9ddb6 &r15, the cells where output and input differ, and 3ac3eb23 &r7, the output's cells as offsets from the markers.
- **A functional dependency that holds in every row.** In 0ca9ddb6 &r28, mark color 2 goes to paint color 4 and 1 goes to 7. In 1fad071e &r28, Example goes to bar length.
- **Many rows reduced to one or two.** 3ac3eb23 &r4 is DIR_T, 0ca9ddb6 &r29 is (1, 7), and 3ac3eb23 &r14 is the period 2.
- **The direction a product lacks.** 3ac3eb23 &r3 is 3 markers x {DIR_B, DIR_L, DIR_R}, and the information is the absent DIR_T. 1fad071e &r31 lacks only DIR_L.
- **A regularity across the examples.** The same star shape around each dot in 0ca9ddb6 &r16, and side 0 at even steps and 1 at odd steps in every row of 3ac3eb23 &r8.
- **A match between a table from the inputs and one from the outputs.** This was the clearest mark of the rule. 1fad071e &r21 at assignment 4 (2, 4, 4) equals &r28, the bar lengths. The cells of 0ca9ddb6 &r51 are those of &r15, and the cells of 3ac3eb23 &r31 are those of &r7.

## What I could not tell from a table alone

- **Which DET assignment is the case's.** 1fad071e &r34 gives a whole 1x5 grid at all nine assignments. Only a comparison with the output grids picks assignment 4, and until &r28, &r21's 3, 2, 3 at assignment 7 looks as good as 2, 4, 4.
- **What a lib DET's values are.** 1fad071e &r1 holds 2, 3, 5, and 0ca9ddb6 &r3 holds 1. It took the clause text and the later RULE (&r51 reads &r3 as the arms' reach) to tell.
- **Which column is which.** Most columns are named c0, c1, and so on. A DET table's column order is not the order of the clause's positions: 3ac3eb23 &r8's step count is position `:4` in the next clause and column c5 in the table.
- **What kind of value a Box is.** In 1fad071e &r15 the whole-grid box [0 0 0 0] prints as the offset `+(0,0)`. In &r20 a cell of a 2x2 box prints as `r0-7 c0-7`. In 3ac3eb23 &r3, Boxes with no Example column print as bare margins.
- **Whether a table is read whole, under NOT, or in part.** 1fad071e &r31 and 3ac3eb23 &r3 are guards whose meaning is what they lack. 0ca9ddb6 &r22 is read only where it meets &r28's star cells. 3ac3eb23 &r12, &r13 and &r15 to &r17 are not read at all. Each of these shows only in the later clauses.
- **That an Ident is equal across examples for the same cell set.** 1fad071e id3 is the cell (8,1) in train 0 and in train 1. I saw this by chance, and the table does not mark it.
