# Observations, second set

From three more gold solvers: [22425bda](case-22425bda.md) (stack the crossing lines, list the colors bottom first), [3979b1a8](case-3979b1a8.md) (grow the input to 2x, continue its diagonal with period 3) and [2c608aff](case-2c608aff.md) (join each marker on the block's row or column to the block). Each mark below is new against [observations.md](observations.md) or contradicts it.

## Marks that a table adds no signal

- **A witness column that multiplies the rows.** 22425bda &r4 keeps the ink cell Q beside each line cell P: 91 rows in e0, where the projection onto (P, color) is the 14 line cells. 3979b1a8 &r28 is 1800 rows, every output cell x 2 axes x 9 distances, for the 9 (distance, offset) pairs that are its content.
- **A second chain that finds a fact again in other terms.** 3979b1a8 &r24 to &r26 find corner DIAG_TL after &r20 to &r22 found tile (0,0) of the same 2x2 frame.
- **A DET that reads nothing.** 22425bda &r23 (DirDomain) is one of the four directions at each assignment. The engine's choice of assignment is signal, and the table is not.
- **Assignments equal in pairs.** 22425bda &r24 and &r25 at DIR_B equal those at DIR_T, and at DIR_R those at DIR_L: the table depends only on the axis.

## Marks that a table adds signal

- **An empty table read under NOT** (contradicts "an assignment empty at every example"). 3979b1a8 &r21 and &r25 are empty at every example, and the empty table is the fact: no train example puts the input in another tile or corner.
- **A count that varies over a shape.** 2c608aff &r14 draws 4 inside the block, 3 on its edges, 2 at its corners and nothing at the markers. The opposite of "the same count at every cell".
- **The rule visible with no table from the outputs** (contradicts the match of an input table with an output table as the clearest mark). In 22425bda and 2c608aff no table reads the outputs. 22425bda &r10's ranks, read in order, are the output rows; 2c608aff &r22's drawing is the cells the outputs add. Only the grids show the match.
- **A number equal to a size of the output.** 22425bda &r20 is 2, 3, 4, 5, the output widths.
- **An assignment whose Boxes fit the output grid.** 22425bda &r24 at DIR_L and DIR_R draws on the 1xN output grid; at DIR_T and DIR_B its cells print as boxes over the input. The drawing tells the axis. Telling DIR_L from DIR_R still takes the output colors (&r27).
- **Signal that no clause reads.** 2c608aff &r5, the least-counted color, is the marker color in all four train examples. The program finds the markers by shape (&r15).

## What could not be told from the table alone

- **What a drawing by the first Box column shows when that column is a seed.** 2c608aff &r18 to &r20 draw `+` at each marker and nothing of the ray cells in their second Box column.
- **What a `-` cell is.** Every row shown of 2c608aff &r17 has `-` in its Number and Box columns.
- **That a column is a key.** 22425bda &r10's header says "candidate keys none", and each of its columns is a key of every example's rows.
- **That a Box is a cell of a third grid.** 22425bda &r24's `r0-5 c0-6` is (0,0) of a 2x1 grid, and 3979b1a8 &r3's `r0-3 c0-3` is (0,0) of the 2x2 tile frame, each printed as margins over the input.

## Existing marks seen again

- Rows equal to an earlier table's: 3979b1a8 &r13 (= &r3), &r34 (= &r29).
- The same count at every cell: 3979b1a8 &r30 (4); 2c608aff &r16 (2), &r21 (4).
- Rows as many as the grid's cells: 3979b1a8 &r14; 2c608aff &r20 (per marker).
- Rows that follow from a smaller table and the grid size: 3979b1a8 &r3; 2c608aff &r19, &r20.
- Constant columns, or the same rows in every example: 3979b1a8 &r2, &r29.
- A selection much smaller than its parent: 22425bda &r5; 2c608aff &r15; 3979b1a8 &r16.
- A first table read from the outputs: 3979b1a8 &r16.
- A functional dependency that holds in every row: 22425bda &r3 (color to axis family).
- Many rows reduced to one or two: 3979b1a8 &r22, &r33.
- The direction a product lacks: 3979b1a8 &r32 (no row at distance 3).
- A match between a table from the inputs and one from the outputs: 3979b1a8 &r31 and &r23.
- Which DET assignment is the case's: 22425bda &r27 (DIR_L or DIR_R).
- What a lib DET's values are: 3979b1a8 &r0.
- Which column is which: 22425bda &r4 (c0 is the line cell, told by the drawing's counts).
- Whether a table is read whole, under NOT, or not at all: 2c608aff &r14 (under NOT); 22425bda &r11 to &r17 (not read).
