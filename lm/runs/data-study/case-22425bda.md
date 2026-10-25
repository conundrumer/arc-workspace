# 22425bda, case `concept`

- concept case: True; tokens: 306; tables: 20 relations, 35 per assignment
- cells: a Position is `(row,col)` of the example's input grid (`(row,col)out` where it fits only the output grid), an Offset `+(drow,dcol)`, another Box `rR0-R1 cC0-C1` over the input grid or `[t b l r]` margins; an Ident is `id<n>`, equal only within one case; see README.md

## Grids

### Train example 0: input 7x7, output 1x2

```
input            output
7 7 7 2 7 7 7    2 5
7 7 7 2 7 7 7
7 7 7 2 7 7 7
5 5 5 5 5 5 5
7 7 7 2 7 7 7
7 7 7 2 7 7 7
7 7 7 2 7 7 7
```

### Train example 1: input 10x10, output 1x3

```
input                  output
9 7 7 7 7 7 8 7 7 7    0 8 9
7 9 7 7 7 7 8 7 7 7
7 7 9 7 7 7 8 7 7 7
7 7 7 9 7 7 8 7 7 7
0 0 0 0 9 0 8 0 0 0
7 7 7 7 7 9 8 7 7 7
7 7 7 7 7 7 9 7 7 7
7 7 7 7 7 7 8 9 7 7
7 7 7 7 7 7 8 7 9 7
7 7 7 7 7 7 8 7 7 9
```

### Train example 2: input 12x12, output 1x4

```
input                      output
7 1 7 7 3 7 7 7 5 7 7 7    3 2 1 5
7 7 1 7 3 7 7 7 5 7 7 7
7 7 7 1 3 7 7 7 5 7 7 7
7 7 7 7 1 7 7 7 5 7 7 7
7 7 7 7 3 1 7 7 5 7 7 7
2 2 2 2 2 2 1 2 5 2 2 2
7 7 7 7 3 7 7 1 5 7 7 7
7 7 7 7 3 7 7 7 5 7 7 7
7 7 7 7 3 7 7 7 5 1 7 7
7 7 7 7 3 7 7 7 5 7 1 7
7 7 7 7 3 7 7 7 5 7 7 1
7 7 7 7 3 7 7 7 5 7 7 7
```

### Train example 3: input 16x16, output 1x5

```
input                              output
7 7 7 7 7 7 7 7 7 7 5 7 9 7 4 7    4 1 9 3 5
7 7 7 7 7 7 7 7 7 7 5 7 9 7 4 7
7 7 7 7 7 7 7 7 7 7 5 7 9 7 4 7
7 7 7 7 7 7 7 7 7 7 5 7 9 7 4 7
7 7 7 7 7 7 7 7 7 7 5 7 9 7 4 7
7 7 7 7 7 7 7 7 7 7 5 7 9 7 4 7
7 7 7 7 7 7 7 7 7 7 5 7 9 7 4 7
7 7 7 7 7 7 7 7 7 7 5 7 9 7 4 7
7 7 7 7 7 7 7 7 7 7 5 7 9 7 4 7
7 7 7 7 7 7 7 7 7 7 5 7 9 7 4 7
7 7 7 7 7 7 7 7 7 7 5 7 9 7 4 7
7 7 7 7 7 7 7 7 7 7 5 7 9 7 4 7
3 3 3 3 3 3 3 3 3 3 5 3 3 3 3 3
7 7 7 7 7 7 7 7 7 7 5 7 9 7 4 7
1 1 1 1 1 1 1 1 1 1 5 1 9 1 1 1
7 7 7 7 7 7 7 7 7 7 5 7 9 7 4 7
```

### Test example 0: input 16x16

```
7 7 7 7 7 7 4 1 7 5 7 7 7 7 7 7
7 7 7 7 7 7 4 7 5 7 7 7 7 7 7 7
7 7 7 7 7 7 4 5 7 1 7 7 7 7 7 7
7 7 7 7 7 7 4 7 7 7 1 7 7 7 7 7
7 7 7 7 7 5 4 7 7 7 7 1 7 7 7 7
0 7 7 7 5 7 4 7 7 7 7 7 1 7 7 7
7 0 7 5 7 7 4 7 7 7 7 7 7 1 7 3
9 9 9 9 9 9 9 9 9 9 9 9 9 9 3 9
7 5 7 0 7 7 4 7 7 7 7 7 7 3 7 1
5 7 7 7 0 7 4 7 7 7 7 7 3 7 7 7
7 7 7 7 7 0 4 7 7 7 7 3 7 7 7 7
7 7 7 7 7 7 0 7 7 7 3 7 7 7 7 7
7 7 7 7 7 7 4 0 7 3 7 7 7 7 7 7
7 7 7 7 7 7 4 7 3 7 7 7 7 7 7 7
7 7 7 7 7 7 4 3 7 0 7 7 7 7 7 7
7 7 7 7 7 7 3 7 7 7 0 7 7 7 7 7
```

## Program and tables

Model-written tokens plain, engine-written ones in [brackets]. Each clause is followed by the tables of the relations it declares. A table whose entries hold several DET assignments is given once per assignment, each marked with the values, at that assignment, of the DETs whose value differs between them; a DET's value is the rows of its own table at that assignment.

```
DET DominantColor END [&r0]
```

### &r0 (export table 2)

- columns: C: Color
- depth 1, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [0, 0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
C
7
```

```
RULE input :0 * [L0] :1 * [L1] NOT &r0 :0 L1 END [&r1]
```

### &r1 (export table 3)

- columns: c0: Box, c1: Color
- depth 2, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [13, 27, 42, 74]; test: 62

Train example 0: 13 rows
Drawn on a 7x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . 2 . . .
. . . 2 . . .
. . . 2 . . .
5 5 5 5 5 5 5
. . . 2 . . .
. . . 2 . . .
. . . 2 . . .
```
```
c0 | c1
(0,3) | 2
(1,3) | 2
(2,3) | 2
(3,0) | 5
(3,1) | 5
(3,2) | 5
(3,3) | 5
(3,4) | 5
(3,5) | 5
(3,6) | 5
(4,3) | 2
(5,3) | 2
(6,3) | 2
```

Train example 1: 27 rows
Drawn on a 10x10 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
9 . . . . . 8 . . .
. 9 . . . . 8 . . .
. . 9 . . . 8 . . .
. . . 9 . . 8 . . .
0 0 0 0 9 0 8 0 0 0
. . . . . 9 8 . . .
. . . . . . 9 . . .
. . . . . . 8 9 . .
. . . . . . 8 . 9 .
. . . . . . 8 . . 9
```
```
c0 | c1
(0,0) | 9
(0,6) | 8
(1,1) | 9
(1,6) | 8
(2,2) | 9
(2,6) | 8
(3,3) | 9
(3,6) | 8
(4,0) | 0
(4,1) | 0
(4,2) | 0
(4,3) | 0
(4,4) | 9
(4,5) | 0
(4,6) | 8
(4,7) | 0
(4,8) | 0
(4,9) | 0
(5,5) | 9
(5,6) | 8
(6,6) | 9
(7,6) | 8
(7,7) | 9
(8,6) | 8
(8,8) | 9
(9,6) | 8
(9,9) | 9
```

Train example 2: 42 rows, the first 30 shown
Drawn on a 12x12 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 1 . . 3 . . . 5 . . .
. . 1 . 3 . . . 5 . . .
. . . 1 3 . . . 5 . . .
. . . . 1 . . . 5 . . .
. . . . 3 1 . . 5 . . .
2 2 2 2 2 2 1 2 5 2 2 2
. . . . 3 . . 1 5 . . .
. . . . 3 . . . 5 . . .
. . . . 3 . . . 5 1 . .
. . . . 3 . . . 5 . 1 .
. . . . 3 . . . 5 . . 1
. . . . 3 . . . 5 . . .
```
```
c0 | c1
(0,1) | 1
(0,4) | 3
(0,8) | 5
(1,2) | 1
(1,4) | 3
(1,8) | 5
(2,3) | 1
(2,4) | 3
(2,8) | 5
(3,4) | 1
(3,8) | 5
(4,4) | 3
(4,5) | 1
(4,8) | 5
(5,0) | 2
(5,1) | 2
(5,2) | 2
(5,3) | 2
(5,4) | 2
(5,5) | 2
(5,6) | 1
(5,7) | 2
(5,8) | 5
(5,9) | 2
(5,10) | 2
(5,11) | 2
(6,4) | 3
(6,7) | 1
(6,8) | 5
(7,4) | 3
```

Train example 3: 74 rows, the first 30 shown
Drawn on a 16x16 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . . . 5 . 9 . 4 .
. . . . . . . . . . 5 . 9 . 4 .
. . . . . . . . . . 5 . 9 . 4 .
. . . . . . . . . . 5 . 9 . 4 .
. . . . . . . . . . 5 . 9 . 4 .
. . . . . . . . . . 5 . 9 . 4 .
. . . . . . . . . . 5 . 9 . 4 .
. . . . . . . . . . 5 . 9 . 4 .
. . . . . . . . . . 5 . 9 . 4 .
. . . . . . . . . . 5 . 9 . 4 .
. . . . . . . . . . 5 . 9 . 4 .
. . . . . . . . . . 5 . 9 . 4 .
3 3 3 3 3 3 3 3 3 3 5 3 3 3 3 3
. . . . . . . . . . 5 . 9 . 4 .
1 1 1 1 1 1 1 1 1 1 5 1 9 1 1 1
. . . . . . . . . . 5 . 9 . 4 .
```
```
c0 | c1
(0,10) | 5
(0,12) | 9
(0,14) | 4
(1,10) | 5
(1,12) | 9
(1,14) | 4
(2,10) | 5
(2,12) | 9
(2,14) | 4
(3,10) | 5
(3,12) | 9
(3,14) | 4
(4,10) | 5
(4,12) | 9
(4,14) | 4
(5,10) | 5
(5,12) | 9
(5,14) | 4
(6,10) | 5
(6,12) | 9
(6,14) | 4
(7,10) | 5
(7,12) | 9
(7,14) | 4
(8,10) | 5
(8,12) | 9
(8,14) | 4
(9,10) | 5
(9,12) | 9
(9,14) | 4
```

```
RULE &r1 :0 * [L0] &r1 :0 * [L1] axis4_elem :0 * [L2] same_line :0 L2 :1 L0 :2 L1 END [&r2]
```

### &r2 (export table 4)

- columns: c0: Axis4, c1: Box, c2: Box
- depth 3, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [160, 448, 850, 1998]; test: 1466

Train example 0: 160 rows, the first 30 shown
Drawn on a 7x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . + . . .
. . . + . . .
. . . + . . .
+ + + + + + +
. . . + . . .
. . . + . . .
. . . + . . .
```
```
c0 | c1 | c2
AXIS_V | (0,3) | (0,3)
AXIS_V | (0,3) | (1,3)
AXIS_V | (0,3) | (2,3)
AXIS_V | (0,3) | (3,3)
AXIS_V | (0,3) | (4,3)
AXIS_V | (0,3) | (5,3)
AXIS_V | (0,3) | (6,3)
AXIS_V | (1,3) | (0,3)
AXIS_V | (1,3) | (1,3)
AXIS_V | (1,3) | (2,3)
AXIS_V | (1,3) | (3,3)
AXIS_V | (1,3) | (4,3)
AXIS_V | (1,3) | (5,3)
AXIS_V | (1,3) | (6,3)
AXIS_V | (2,3) | (0,3)
AXIS_V | (2,3) | (1,3)
AXIS_V | (2,3) | (2,3)
AXIS_V | (2,3) | (3,3)
AXIS_V | (2,3) | (4,3)
AXIS_V | (2,3) | (5,3)
AXIS_V | (2,3) | (6,3)
AXIS_V | (3,0) | (3,0)
AXIS_V | (3,1) | (3,1)
AXIS_V | (3,2) | (3,2)
AXIS_V | (3,3) | (0,3)
AXIS_V | (3,3) | (1,3)
AXIS_V | (3,3) | (2,3)
AXIS_V | (3,3) | (3,3)
AXIS_V | (3,3) | (4,3)
AXIS_V | (3,3) | (5,3)
```

Train example 1: 448 rows, the first 30 shown
Drawn on a 10x10 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
+ . . . . . + . . .
. + . . . . + . . .
. . + . . . + . . .
. . . + . . + . . .
+ + + + + + + + + +
. . . . . + + . . .
. . . . . . + . . .
. . . . . . + + . .
. . . . . . + . + .
. . . . . . + . . +
```
```
c0 | c1 | c2
AXIS_V | (0,0) | (0,0)
AXIS_V | (0,0) | (4,0)
AXIS_V | (0,6) | (0,6)
AXIS_V | (0,6) | (1,6)
AXIS_V | (0,6) | (2,6)
AXIS_V | (0,6) | (3,6)
AXIS_V | (0,6) | (4,6)
AXIS_V | (0,6) | (5,6)
AXIS_V | (0,6) | (6,6)
AXIS_V | (0,6) | (7,6)
AXIS_V | (0,6) | (8,6)
AXIS_V | (0,6) | (9,6)
AXIS_V | (1,1) | (1,1)
AXIS_V | (1,1) | (4,1)
AXIS_V | (1,6) | (0,6)
AXIS_V | (1,6) | (1,6)
AXIS_V | (1,6) | (2,6)
AXIS_V | (1,6) | (3,6)
AXIS_V | (1,6) | (4,6)
AXIS_V | (1,6) | (5,6)
AXIS_V | (1,6) | (6,6)
AXIS_V | (1,6) | (7,6)
AXIS_V | (1,6) | (8,6)
AXIS_V | (1,6) | (9,6)
AXIS_V | (2,2) | (2,2)
AXIS_V | (2,2) | (4,2)
AXIS_V | (2,6) | (0,6)
AXIS_V | (2,6) | (1,6)
AXIS_V | (2,6) | (2,6)
AXIS_V | (2,6) | (3,6)
```

Train example 2: 850 rows, the first 30 shown
Drawn on a 12x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. + . . + . . . + . . .
. . + . + . . . + . . .
. . . + + . . . + . . .
. . . . + . . . + . . .
. . . . + + . . + . . .
+ + + + + + + + + + + +
. . . . + . . + + . . .
. . . . + . . . + . . .
. . . . + . . . + + . .
. . . . + . . . + . + .
. . . . + . . . + . . +
. . . . + . . . + . . .
```
```
c0 | c1 | c2
AXIS_V | (0,1) | (0,1)
AXIS_V | (0,1) | (5,1)
AXIS_V | (0,4) | (0,4)
AXIS_V | (0,4) | (1,4)
AXIS_V | (0,4) | (2,4)
AXIS_V | (0,4) | (3,4)
AXIS_V | (0,4) | (4,4)
AXIS_V | (0,4) | (5,4)
AXIS_V | (0,4) | (6,4)
AXIS_V | (0,4) | (7,4)
AXIS_V | (0,4) | (8,4)
AXIS_V | (0,4) | (9,4)
AXIS_V | (0,4) | (10,4)
AXIS_V | (0,4) | (11,4)
AXIS_V | (0,8) | (0,8)
AXIS_V | (0,8) | (1,8)
AXIS_V | (0,8) | (2,8)
AXIS_V | (0,8) | (3,8)
AXIS_V | (0,8) | (4,8)
AXIS_V | (0,8) | (5,8)
AXIS_V | (0,8) | (6,8)
AXIS_V | (0,8) | (7,8)
AXIS_V | (0,8) | (8,8)
AXIS_V | (0,8) | (9,8)
AXIS_V | (0,8) | (10,8)
AXIS_V | (0,8) | (11,8)
AXIS_V | (1,2) | (1,2)
AXIS_V | (1,2) | (5,2)
AXIS_V | (1,4) | (0,4)
AXIS_V | (1,4) | (1,4)
```

Train example 3: 1998 rows, the first 30 shown
Drawn on a 16x16 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
+ + + + + + + + + + + + + + + +
. . . . . . . . . . + . + . + .
+ + + + + + + + + + + + + + + +
. . . . . . . . . . + . + . + .
```
```
c0 | c1 | c2
AXIS_V | (0,10) | (0,10)
AXIS_V | (0,10) | (1,10)
AXIS_V | (0,10) | (2,10)
AXIS_V | (0,10) | (3,10)
AXIS_V | (0,10) | (4,10)
AXIS_V | (0,10) | (5,10)
AXIS_V | (0,10) | (6,10)
AXIS_V | (0,10) | (7,10)
AXIS_V | (0,10) | (8,10)
AXIS_V | (0,10) | (9,10)
AXIS_V | (0,10) | (10,10)
AXIS_V | (0,10) | (11,10)
AXIS_V | (0,10) | (12,10)
AXIS_V | (0,10) | (13,10)
AXIS_V | (0,10) | (14,10)
AXIS_V | (0,10) | (15,10)
AXIS_V | (0,12) | (0,12)
AXIS_V | (0,12) | (1,12)
AXIS_V | (0,12) | (2,12)
AXIS_V | (0,12) | (3,12)
AXIS_V | (0,12) | (4,12)
AXIS_V | (0,12) | (5,12)
AXIS_V | (0,12) | (6,12)
AXIS_V | (0,12) | (7,12)
AXIS_V | (0,12) | (8,12)
AXIS_V | (0,12) | (9,12)
AXIS_V | (0,12) | (10,12)
AXIS_V | (0,12) | (11,12)
AXIS_V | (0,12) | (12,12)
AXIS_V | (0,12) | (13,12)
```

```
RULE &r1 :1 * [L0] axis4_elem :0 * [L1] ALL &r1 :1 L0 :0 * [L2] &r1 :1 L0 :0 * [L3] END &r2 :2 L1 :0 L2 :1 L3 END END [&r3]
```

### &r3 (export table 5)

- columns: c0: Axis4, c1: Color
- depth 4, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [2, 3, 4, 5]; test: 6

Train example 0: 2 rows
```
c0 | c1
AXIS_V | 2
AXIS_H | 5
```

Train example 1: 3 rows
```
c0 | c1
AXIS_V | 8
AXIS_H | 0
DAXIS_DG | 9
```

Train example 2: 4 rows
```
c0 | c1
AXIS_V | 3
AXIS_V | 5
AXIS_H | 2
DAXIS_DG | 1
```

Train example 3: 5 rows
```
c0 | c1
AXIS_V | 4
AXIS_V | 5
AXIS_V | 9
AXIS_H | 1
AXIS_H | 3
```

```
RULE &r3 :0 * [L0] :1 * [L1] &r1 :1 L0 :0 * [L2] input :0 * [L3] same_line :0 L1 :1 L3 :2 L2 END [&r4]
```

### &r4 (export table 6)

- columns: c0: Box, c1: Box, c2: Axis4, c3: Color
- depth 5, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [91, 270, 494, 1184]; test: 790

Train example 0: 91 rows, the first 30 shown
Drawn on a 7x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . 6 . . .
. . . 6 . . .
. . . 6 . . .
7 7 7 + 7 7 7
. . . 6 . . .
. . . 6 . . .
. . . 6 . . .
```
```
c0 | c1 | c2 | c3
(0,3) | (0,3) | AXIS_V | 2
(0,3) | (1,3) | AXIS_V | 2
(0,3) | (2,3) | AXIS_V | 2
(0,3) | (4,3) | AXIS_V | 2
(0,3) | (5,3) | AXIS_V | 2
(0,3) | (6,3) | AXIS_V | 2
(1,3) | (0,3) | AXIS_V | 2
(1,3) | (1,3) | AXIS_V | 2
(1,3) | (2,3) | AXIS_V | 2
(1,3) | (4,3) | AXIS_V | 2
(1,3) | (5,3) | AXIS_V | 2
(1,3) | (6,3) | AXIS_V | 2
(2,3) | (0,3) | AXIS_V | 2
(2,3) | (1,3) | AXIS_V | 2
(2,3) | (2,3) | AXIS_V | 2
(2,3) | (4,3) | AXIS_V | 2
(2,3) | (5,3) | AXIS_V | 2
(2,3) | (6,3) | AXIS_V | 2
(3,0) | (3,0) | AXIS_H | 5
(3,0) | (3,1) | AXIS_H | 5
(3,0) | (3,2) | AXIS_H | 5
(3,0) | (3,3) | AXIS_H | 5
(3,0) | (3,4) | AXIS_H | 5
(3,0) | (3,5) | AXIS_H | 5
(3,0) | (3,6) | AXIS_H | 5
(3,1) | (3,0) | AXIS_H | 5
(3,1) | (3,1) | AXIS_H | 5
(3,1) | (3,2) | AXIS_H | 5
(3,1) | (3,3) | AXIS_H | 5
(3,1) | (3,4) | AXIS_H | 5
```

Train example 1: 270 rows, the first 30 shown
Drawn on a 10x10 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
+ . . . . . 9 . . .
. + . . . . 9 . . .
. . + . . . 9 . . .
. . . + . . 9 . . .
8 8 8 8 + 8 + 8 8 8
. . . . . + 9 . . .
. . . . . . + . . .
. . . . . . 9 + . .
. . . . . . 9 . + .
. . . . . . 9 . . +
```
```
c0 | c1 | c2 | c3
(0,0) | (0,0) | DAXIS_DG | 9
(0,0) | (1,1) | DAXIS_DG | 9
(0,0) | (2,2) | DAXIS_DG | 9
(0,0) | (3,3) | DAXIS_DG | 9
(0,0) | (4,4) | DAXIS_DG | 9
(0,0) | (5,5) | DAXIS_DG | 9
(0,0) | (6,6) | DAXIS_DG | 9
(0,0) | (7,7) | DAXIS_DG | 9
(0,0) | (8,8) | DAXIS_DG | 9
(0,0) | (9,9) | DAXIS_DG | 9
(0,6) | (0,6) | AXIS_V | 8
(0,6) | (1,6) | AXIS_V | 8
(0,6) | (2,6) | AXIS_V | 8
(0,6) | (3,6) | AXIS_V | 8
(0,6) | (4,6) | AXIS_V | 8
(0,6) | (5,6) | AXIS_V | 8
(0,6) | (7,6) | AXIS_V | 8
(0,6) | (8,6) | AXIS_V | 8
(0,6) | (9,6) | AXIS_V | 8
(1,1) | (0,0) | DAXIS_DG | 9
(1,1) | (1,1) | DAXIS_DG | 9
(1,1) | (2,2) | DAXIS_DG | 9
(1,1) | (3,3) | DAXIS_DG | 9
(1,1) | (4,4) | DAXIS_DG | 9
(1,1) | (5,5) | DAXIS_DG | 9
(1,1) | (6,6) | DAXIS_DG | 9
(1,1) | (7,7) | DAXIS_DG | 9
(1,1) | (8,8) | DAXIS_DG | 9
(1,1) | (9,9) | DAXIS_DG | 9
(1,6) | (0,6) | AXIS_V | 8
```

Train example 2: 494 rows, the first 30 shown
Drawn on a 12x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. + . . + . . . + . . .
. . + . + . . . + . . .
. . . + + . . . + . . .
. . . . + . . . + . . .
. . . . + + . . + . . .
+ + + + + + + + + + + +
. . . . + . . + + . . .
. . . . + . . . + . . .
. . . . + . . . + + . .
. . . . + . . . + . + .
. . . . + . . . + . . +
. . . . + . . . + . . .
```
```
c0 | c1 | c2 | c3
(0,1) | (0,1) | DAXIS_DG | 1
(0,1) | (1,2) | DAXIS_DG | 1
(0,1) | (2,3) | DAXIS_DG | 1
(0,1) | (3,4) | DAXIS_DG | 1
(0,1) | (4,5) | DAXIS_DG | 1
(0,1) | (5,6) | DAXIS_DG | 1
(0,1) | (6,7) | DAXIS_DG | 1
(0,1) | (8,9) | DAXIS_DG | 1
(0,1) | (9,10) | DAXIS_DG | 1
(0,1) | (10,11) | DAXIS_DG | 1
(0,4) | (0,4) | AXIS_V | 3
(0,4) | (1,4) | AXIS_V | 3
(0,4) | (2,4) | AXIS_V | 3
(0,4) | (4,4) | AXIS_V | 3
(0,4) | (6,4) | AXIS_V | 3
(0,4) | (7,4) | AXIS_V | 3
(0,4) | (8,4) | AXIS_V | 3
(0,4) | (9,4) | AXIS_V | 3
(0,4) | (10,4) | AXIS_V | 3
(0,4) | (11,4) | AXIS_V | 3
(0,8) | (0,8) | AXIS_V | 5
(0,8) | (1,8) | AXIS_V | 5
(0,8) | (2,8) | AXIS_V | 5
(0,8) | (3,8) | AXIS_V | 5
(0,8) | (4,8) | AXIS_V | 5
(0,8) | (5,8) | AXIS_V | 5
(0,8) | (6,8) | AXIS_V | 5
(0,8) | (7,8) | AXIS_V | 5
(0,8) | (8,8) | AXIS_V | 5
(0,8) | (9,8) | AXIS_V | 5
```

Train example 3: 1184 rows, the first 30 shown
Drawn on a 16x16 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
. . . . . . . . . . + . + . + .
+ + + + + + + + + + + + + + + +
. . . . . . . . . . + . + . + .
+ + + + + + + + + + + + + + + +
. . . . . . . . . . + . + . + .
```
```
c0 | c1 | c2 | c3
(0,10) | (0,10) | AXIS_V | 5
(0,10) | (1,10) | AXIS_V | 5
(0,10) | (2,10) | AXIS_V | 5
(0,10) | (3,10) | AXIS_V | 5
(0,10) | (4,10) | AXIS_V | 5
(0,10) | (5,10) | AXIS_V | 5
(0,10) | (6,10) | AXIS_V | 5
(0,10) | (7,10) | AXIS_V | 5
(0,10) | (8,10) | AXIS_V | 5
(0,10) | (9,10) | AXIS_V | 5
(0,10) | (10,10) | AXIS_V | 5
(0,10) | (11,10) | AXIS_V | 5
(0,10) | (12,10) | AXIS_V | 5
(0,10) | (13,10) | AXIS_V | 5
(0,10) | (14,10) | AXIS_V | 5
(0,10) | (15,10) | AXIS_V | 5
(0,12) | (0,12) | AXIS_V | 9
(0,12) | (1,12) | AXIS_V | 9
(0,12) | (2,12) | AXIS_V | 9
(0,12) | (3,12) | AXIS_V | 9
(0,12) | (4,12) | AXIS_V | 9
(0,12) | (5,12) | AXIS_V | 9
(0,12) | (6,12) | AXIS_V | 9
(0,12) | (7,12) | AXIS_V | 9
(0,12) | (8,12) | AXIS_V | 9
(0,12) | (9,12) | AXIS_V | 9
(0,12) | (10,12) | AXIS_V | 9
(0,12) | (11,12) | AXIS_V | 9
(0,12) | (13,12) | AXIS_V | 9
(0,12) | (14,12) | AXIS_V | 9
```

```
RULE &r4 :0 * [L0] :3 * [L1] &r4 :0 * [L2] :3 L1 != L0 L2 input :0 L1 :1 L0 END [&r5]
```

### &r5 (export table 7)

- columns: c0: Box, c1: Color, c2: Color
- depth 6, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [1, 3, 5, 6]; test: 10

Train example 0: 1 row
Drawn on a 7x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . .
. . . . . . .
. . . . . . .
. . . 1 . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(3,3) | 5 | 2
```

Train example 1: 3 rows
Drawn on a 10x10 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . 1 . 1 . . .
. . . . . . . . . .
. . . . . . 1 . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
```
```
c0 | c1 | c2
(4,4) | 9 | 0
(4,6) | 8 | 0
(6,6) | 9 | 8
```

Train example 2: 5 rows
Drawn on a 12x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . 1 . . . . . . .
. . . . . . . . . . . .
. . . . 1 . 1 . 1 . . .
. . . . . . . . . . . .
. . . . . . . . 1 . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1 | c2
(3,4) | 1 | 3
(5,4) | 2 | 3
(5,6) | 1 | 2
(5,8) | 5 | 2
(7,8) | 5 | 1
```

Train example 3: 6 rows
Drawn on a 16x16 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . .
. . . . . . . . . . 1 . 1 . 1 .
. . . . . . . . . . . . . . . .
. . . . . . . . . . 1 . 1 . 1 .
. . . . . . . . . . . . . . . .
```
```
c0 | c1 | c2
(12,10) | 5 | 3
(12,12) | 3 | 9
(12,14) | 3 | 4
(14,10) | 5 | 1
(14,12) | 9 | 1
(14,14) | 1 | 4
```

```
INIT Propagation [:0] &r1 :2 ^ [L0] END [:1] SKIP [:2] SKIP [:3] SKIP [:1] SKIP [:2] &r5 :1 * [L1] :3 * [L2] END [:0] END [:1] L2 END [:2] L1 END [:3] SKIP [&r6] [&r7] [&r8] [&r9]
```

### &r6 (export table 8)

- columns: c0: Color, c1: Color
- depth 8, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [3, 6, 10, 15]; test: 21

Train example 0: 3 rows
```
c0 | c1
2 | 2
2 | 5
5 | 5
```

Train example 1: 6 rows
```
c0 | c1
0 | 0
0 | 8
0 | 9
8 | 8
8 | 9
9 | 9
```

Train example 2: 10 rows
```
c0 | c1
1 | 1
1 | 5
2 | 1
2 | 2
2 | 5
3 | 1
3 | 2
3 | 3
3 | 5
5 | 5
```

Train example 3: 15 rows
```
c0 | c1
1 | 1
1 | 3
1 | 5
1 | 9
3 | 3
3 | 5
4 | 1
4 | 3
4 | 4
4 | 5
4 | 9
5 | 5
9 | 3
9 | 5
9 | 9
```

```
INIT Order [:0] SKIP [:1] &r1 :2 * [L0] END [:0] END [:1] L0 END [:2] &r6 :1 :0 * [L1] END :2 * [L2] != L1 L2 END [:0] END [:1] L1 END [:2] L2 END [:3] SKIP [:4] SKIP [&r10] [&r11] [&r12] [&r13] [&r14] [&r15] [&r16] [&r17] [&r18] [&r19]
```

### &r10 (export table 9)

- columns: c0: Color, c1: Number
- depth 10, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [2, 3, 4, 5]; test: 6

Train example 0: 2 rows
```
c0 | c1
2 | 0
5 | 1
```

Train example 1: 3 rows
```
c0 | c1
0 | 0
8 | 1
9 | 2
```

Train example 2: 4 rows
```
c0 | c1
1 | 2
2 | 1
3 | 0
5 | 3
```

Train example 3: 5 rows
```
c0 | c1
1 | 1
3 | 3
4 | 0
5 | 4
9 | 2
```

### &r11 (export table 10)

- columns: c0: Color, c1: Number
- depth 10, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [2, 3, 4, 5]; test: 6

Train example 0: 2 rows
```
c0 | c1
2 | 1
5 | 0
```

Train example 1: 3 rows
```
c0 | c1
0 | 2
8 | 1
9 | 0
```

Train example 2: 4 rows
```
c0 | c1
1 | 1
2 | 2
3 | 3
5 | 0
```

Train example 3: 5 rows
```
c0 | c1
1 | 3
3 | 1
4 | 4
5 | 0
9 | 2
```

### &r12 (export table 11)

- columns: c0: Color
- depth 10, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
2
```

Train example 1: 1 row
```
c0
0
```

Train example 2: 1 row
```
c0
3
```

Train example 3: 1 row
```
c0
4
```

### &r13 (export table 12)

- columns: c0: Color
- depth 10, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
5
```

Train example 1: 1 row
```
c0
9
```

Train example 2: 1 row
```
c0
5
```

Train example 3: 1 row
```
c0
5
```

### &r14 (export table 13)

- columns: c0: Color, c1: Color
- depth 10, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [1, 2, 3, 4]; test: 5

Train example 0: 1 row
```
c0 | c1
2 | 5
```

Train example 1: 2 rows
```
c0 | c1
0 | 8
8 | 9
```

Train example 2: 3 rows
```
c0 | c1
1 | 5
2 | 1
3 | 2
```

Train example 3: 4 rows
```
c0 | c1
1 | 9
3 | 5
4 | 1
9 | 3
```

### &r15 (export table 14)

- columns: c0: Color, c1: Color
- depth 10, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [2, 3, 4, 5]; test: 6

Train example 0: 2 rows
```
c0 | c1
2 | 5
5 | 2
```

Train example 1: 3 rows
```
c0 | c1
0 | 8
8 | 9
9 | 0
```

Train example 2: 4 rows
```
c0 | c1
1 | 5
2 | 1
3 | 2
5 | 3
```

Train example 3: 5 rows
```
c0 | c1
1 | 9
3 | 5
4 | 1
5 | 4
9 | 3
```

### &r17 (export table 15)

- columns: c0: Color, c1: Color
- depth 9, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [1, 3, 6, 10]; test: 15

Train example 0: 1 row
```
c0 | c1
2 | 5
```

Train example 1: 3 rows
```
c0 | c1
0 | 8
0 | 9
8 | 9
```

Train example 2: 6 rows
```
c0 | c1
1 | 5
2 | 1
2 | 5
3 | 1
3 | 2
3 | 5
```

Train example 3: 10 rows
```
c0 | c1
1 | 3
1 | 5
1 | 9
3 | 5
4 | 1
4 | 3
4 | 5
4 | 9
9 | 3
9 | 5
```

```
INIT Cardinality [:0] SKIP [:1] &r10 :3 * [L0] END [:0] END [:1] L0 END [:2] SKIP [&r20] [&r21] [&r22]
```

### &r20 (export table 16)

- columns: c0: Number
- depth 12, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
2
```

Train example 1: 1 row
```
c0
3
```

Train example 2: 1 row
```
c0
4
```

Train example 3: 1 row
```
c0
5
```

```
DET DirDomain END [&r23]
```

### &r23 (export table 17)

- columns: D: Dir
- depth 1, candidate keys none
- DETs its entries are assigned: &r23; assignments: 4

#### &r23, assignment 1 of 4

- DET values that differ between the assignments: &r23 = {(DIR_T)}
- rows per train example: [0, 0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
DIR_T
```


#### &r23, assignment 2 of 4

- DET values that differ between the assignments: &r23 = {(DIR_B)}
- rows per train example: [0, 0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
DIR_B
```


#### &r23, assignment 3 of 4

- DET values that differ between the assignments: &r23 = {(DIR_L)}
- rows per train example: [0, 0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
DIR_L
```


#### &r23, assignment 4 of 4

- DET values that differ between the assignments: &r23 = {(DIR_R)}
- rows per train example: [0, 0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
DIR_R
```

```
INIT Frame [:0] SKIP [:1] &r23 :0 * [L0] axis_of :0 L0 :1 * [L1] &r20 :2 * [L2] END [:0] END [:1] L1 END [:2] L2 END [&r24] [&r25]
```

### &r24 (export table 18)

- columns: c0: Box
- depth 14, candidate keys none
- DETs its entries are assigned: &r0, &r23; assignments: 4

#### &r24, assignment 1 of 4

- DET values that differ between the assignments: &r23 = {(DIR_T)}
- rows per train example: [2, 3, 4, 5]; test: 6

Train example 0: 2 rows
```
c0
r0-5 c0-6
r1-6 c0-6
```

Train example 1: 3 rows
```
c0
r0-7 c0-9
r1-8 c0-9
r2-9 c0-9
```

Train example 2: 4 rows
```
c0
r0-8 c0-11
r1-9 c0-11
r2-10 c0-11
r3-11 c0-11
```

Train example 3: 5 rows
```
c0
r0-11 c0-15
r1-12 c0-15
r2-13 c0-15
r3-14 c0-15
r4-15 c0-15
```


#### &r24, assignment 2 of 4

- DET values that differ between the assignments: &r23 = {(DIR_B)}
- rows equal to those of assignment 1 at every example

#### &r24, assignment 3 of 4

- DET values that differ between the assignments: &r23 = {(DIR_L)}
- rows per train example: [2, 3, 4, 5]; test: 6

Train example 0: 2 rows
Drawn on a 1x2 grid, the size of the output grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1
```
```
c0
(0,0)out
(0,1)out
```

Train example 1: 3 rows
Drawn on a 1x3 grid, the size of the output grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1
```
```
c0
(0,0)out
(0,1)out
(0,2)out
```

Train example 2: 4 rows
Drawn on a 1x4 grid, the size of the output grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1
```
```
c0
(0,0)out
(0,1)out
(0,2)out
(0,3)out
```

Train example 3: 5 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
```
```
c0
(0,0)out
(0,1)out
(0,2)out
(0,3)out
(0,4)out
```


#### &r24, assignment 4 of 4

- DET values that differ between the assignments: &r23 = {(DIR_R)}
- rows equal to those of assignment 3 at every example
### &r25 (export table 19)

- columns: c0: Axis, c1: Number
- depth 13, candidate keys none
- DETs its entries are assigned: &r0, &r23; assignments: 4

#### &r25, assignment 1 of 4

- DET values that differ between the assignments: &r23 = {(DIR_T)}
- rows per train example: [1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1
AXIS_V | 2
```

Train example 1: 1 row
```
c0 | c1
AXIS_V | 3
```

Train example 2: 1 row
```
c0 | c1
AXIS_V | 4
```

Train example 3: 1 row
```
c0 | c1
AXIS_V | 5
```


#### &r25, assignment 2 of 4

- DET values that differ between the assignments: &r23 = {(DIR_B)}
- rows equal to those of assignment 1 at every example

#### &r25, assignment 3 of 4

- DET values that differ between the assignments: &r23 = {(DIR_L)}
- rows per train example: [1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1
AXIS_H | 2
```

Train example 1: 1 row
```
c0 | c1
AXIS_H | 3
```

Train example 2: 1 row
```
c0 | c1
AXIS_H | 4
```

Train example 3: 1 row
```
c0 | c1
AXIS_H | 5
```


#### &r25, assignment 4 of 4

- DET values that differ between the assignments: &r23 = {(DIR_R)}
- rows equal to those of assignment 3 at every example
```
RULE &r24 :1 * [L0] &r23 :0 * [L1] margin :0 L0 :1 L1 :2 * [L2] &r10 :2 L2 END [&r26]
```

### &r26 (export table 20)

- columns: c0: Box, c1: Dir, c2: Number
- depth 15, candidate keys none
- DETs its entries are assigned: &r0, &r23; assignments: 4

#### &r26, assignment 1 of 4

- DET values that differ between the assignments: &r23 = {(DIR_T)}
- rows per train example: [2, 3, 4, 5]; test: 6

Train example 0: 2 rows
```
c0 | c1 | c2
r0-5 c0-6 | DIR_T | 0
r1-6 c0-6 | DIR_T | 1
```

Train example 1: 3 rows
```
c0 | c1 | c2
r0-7 c0-9 | DIR_T | 0
r1-8 c0-9 | DIR_T | 1
r2-9 c0-9 | DIR_T | 2
```

Train example 2: 4 rows
```
c0 | c1 | c2
r0-8 c0-11 | DIR_T | 0
r1-9 c0-11 | DIR_T | 1
r2-10 c0-11 | DIR_T | 2
r3-11 c0-11 | DIR_T | 3
```

Train example 3: 5 rows
```
c0 | c1 | c2
r0-11 c0-15 | DIR_T | 0
r1-12 c0-15 | DIR_T | 1
r2-13 c0-15 | DIR_T | 2
r3-14 c0-15 | DIR_T | 3
r4-15 c0-15 | DIR_T | 4
```


#### &r26, assignment 2 of 4

- DET values that differ between the assignments: &r23 = {(DIR_B)}
- rows per train example: [2, 3, 4, 5]; test: 6

Train example 0: 2 rows
```
c0 | c1 | c2
r0-5 c0-6 | DIR_B | 1
r1-6 c0-6 | DIR_B | 0
```

Train example 1: 3 rows
```
c0 | c1 | c2
r0-7 c0-9 | DIR_B | 2
r1-8 c0-9 | DIR_B | 1
r2-9 c0-9 | DIR_B | 0
```

Train example 2: 4 rows
```
c0 | c1 | c2
r0-8 c0-11 | DIR_B | 3
r1-9 c0-11 | DIR_B | 2
r2-10 c0-11 | DIR_B | 1
r3-11 c0-11 | DIR_B | 0
```

Train example 3: 5 rows
```
c0 | c1 | c2
r0-11 c0-15 | DIR_B | 4
r1-12 c0-15 | DIR_B | 3
r2-13 c0-15 | DIR_B | 2
r3-14 c0-15 | DIR_B | 1
r4-15 c0-15 | DIR_B | 0
```


#### &r26, assignment 3 of 4

- DET values that differ between the assignments: &r23 = {(DIR_L)}
- rows per train example: [2, 3, 4, 5]; test: 6

Train example 0: 2 rows
Drawn on a 1x2 grid, the size of the output grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 1
```
```
c0 | c1 | c2
(0,0)out | DIR_L | 0
(0,1)out | DIR_L | 1
```

Train example 1: 3 rows
Drawn on a 1x3 grid, the size of the output grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 1 2
```
```
c0 | c1 | c2
(0,0)out | DIR_L | 0
(0,1)out | DIR_L | 1
(0,2)out | DIR_L | 2
```

Train example 2: 4 rows
Drawn on a 1x4 grid, the size of the output grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 1 2 3
```
```
c0 | c1 | c2
(0,0)out | DIR_L | 0
(0,1)out | DIR_L | 1
(0,2)out | DIR_L | 2
(0,3)out | DIR_L | 3
```

Train example 3: 5 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 1 2 3 4
```
```
c0 | c1 | c2
(0,0)out | DIR_L | 0
(0,1)out | DIR_L | 1
(0,2)out | DIR_L | 2
(0,3)out | DIR_L | 3
(0,4)out | DIR_L | 4
```


#### &r26, assignment 4 of 4

- DET values that differ between the assignments: &r23 = {(DIR_R)}
- rows per train example: [2, 3, 4, 5]; test: 6

Train example 0: 2 rows
Drawn on a 1x2 grid, the size of the output grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
1 0
```
```
c0 | c1 | c2
(0,0)out | DIR_R | 1
(0,1)out | DIR_R | 0
```

Train example 1: 3 rows
Drawn on a 1x3 grid, the size of the output grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
2 1 0
```
```
c0 | c1 | c2
(0,0)out | DIR_R | 2
(0,1)out | DIR_R | 1
(0,2)out | DIR_R | 0
```

Train example 2: 4 rows
Drawn on a 1x4 grid, the size of the output grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
3 2 1 0
```
```
c0 | c1 | c2
(0,0)out | DIR_R | 3
(0,1)out | DIR_R | 2
(0,2)out | DIR_R | 1
(0,3)out | DIR_R | 0
```

Train example 3: 5 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
4 3 2 1 0
```
```
c0 | c1 | c2
(0,0)out | DIR_R | 4
(0,1)out | DIR_R | 3
(0,2)out | DIR_R | 2
(0,3)out | DIR_R | 1
(0,4)out | DIR_R | 0
```

```
RULE &r10 :1 * [L0] :2 * [L1] &r26 :2 L1 :0 * [L2] END [&r27]
```

### &r27 (export table 21)

- columns: c0: Color, c1: Box, c2: Number
- depth 16, candidate keys none
- DETs its entries are assigned: &r0, &r23; assignments: 4

#### &r27, assignment 1 of 4

- DET values that differ between the assignments: &r23 = {(DIR_T)}
- rows per train example: [2, 3, 4, 5]; test: 6

Train example 0: 2 rows
```
c0 | c1 | c2
2 | r0-5 c0-6 | 0
5 | r1-6 c0-6 | 1
```

Train example 1: 3 rows
```
c0 | c1 | c2
0 | r0-7 c0-9 | 0
8 | r1-8 c0-9 | 1
9 | r2-9 c0-9 | 2
```

Train example 2: 4 rows
```
c0 | c1 | c2
1 | r2-10 c0-11 | 2
2 | r1-9 c0-11 | 1
3 | r0-8 c0-11 | 0
5 | r3-11 c0-11 | 3
```

Train example 3: 5 rows
```
c0 | c1 | c2
1 | r1-12 c0-15 | 1
3 | r3-14 c0-15 | 3
4 | r0-11 c0-15 | 0
5 | r4-15 c0-15 | 4
9 | r2-13 c0-15 | 2
```


#### &r27, assignment 2 of 4

- DET values that differ between the assignments: &r23 = {(DIR_B)}
- rows per train example: [2, 3, 4, 5]; test: 6

Train example 0: 2 rows
```
c0 | c1 | c2
2 | r1-6 c0-6 | 0
5 | r0-5 c0-6 | 1
```

Train example 1: 3 rows
```
c0 | c1 | c2
0 | r2-9 c0-9 | 0
8 | r1-8 c0-9 | 1
9 | r0-7 c0-9 | 2
```

Train example 2: 4 rows
```
c0 | c1 | c2
1 | r1-9 c0-11 | 2
2 | r2-10 c0-11 | 1
3 | r3-11 c0-11 | 0
5 | r0-8 c0-11 | 3
```

Train example 3: 5 rows
```
c0 | c1 | c2
1 | r3-14 c0-15 | 1
3 | r1-12 c0-15 | 3
4 | r4-15 c0-15 | 0
5 | r0-11 c0-15 | 4
9 | r2-13 c0-15 | 2
```


#### &r27, assignment 3 of 4

- DET values that differ between the assignments: &r23 = {(DIR_L)}
- rows per train example: [2, 3, 4, 5]; test: 6

Train example 0: 2 rows
Drawn on a 1x2 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 5
```
```
c0 | c1 | c2
2 | (0,0)out | 0
5 | (0,1)out | 1
```

Train example 1: 3 rows
Drawn on a 1x3 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
0 8 9
```
```
c0 | c1 | c2
0 | (0,0)out | 0
8 | (0,1)out | 1
9 | (0,2)out | 2
```

Train example 2: 4 rows
Drawn on a 1x4 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
3 2 1 5
```
```
c0 | c1 | c2
1 | (0,2)out | 2
2 | (0,1)out | 1
3 | (0,0)out | 0
5 | (0,3)out | 3
```

Train example 3: 5 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
4 1 9 3 5
```
```
c0 | c1 | c2
1 | (0,1)out | 1
3 | (0,3)out | 3
4 | (0,0)out | 0
5 | (0,4)out | 4
9 | (0,2)out | 2
```


#### &r27, assignment 4 of 4

- DET values that differ between the assignments: &r23 = {(DIR_R)}
- rows per train example: [2, 3, 4, 5]; test: 6

Train example 0: 2 rows
Drawn on a 1x2 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 2
```
```
c0 | c1 | c2
2 | (0,1)out | 0
5 | (0,0)out | 1
```

Train example 1: 3 rows
Drawn on a 1x3 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
9 8 0
```
```
c0 | c1 | c2
0 | (0,2)out | 0
8 | (0,1)out | 1
9 | (0,0)out | 2
```

Train example 2: 4 rows
Drawn on a 1x4 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 1 2 3
```
```
c0 | c1 | c2
1 | (0,1)out | 2
2 | (0,2)out | 1
3 | (0,3)out | 0
5 | (0,0)out | 3
```

Train example 3: 5 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 3 9 1 4
```
```
c0 | c1 | c2
1 | (0,3)out | 1
3 | (0,1)out | 3
4 | (0,4)out | 0
5 | (0,0)out | 4
9 | (0,2)out | 2
```

## What I see

The task: full-length lines of one color each lie on the background 7, along a row, a column or a diagonal. Where two lines cross, the upper one shows. The output is one row of the line colors, bottom of the stack at the left. The case reads no table from the outputs. Only the DET DirDomain (&r23) has more than one assignment, and the engine keeps the assignment whose output matches.

- **&r0** (DominantColor): 7.
- **&r1** (input cells not of color 7): the line cells, 13/27/42/74 rows. A selection, and the drawings are the lines with the gaps at each crossing: in e1, (4,4) is 9 and (4,6) is 8 on the 0 row.
- **&r2** (pairs of ink cells on one line of each of the four axis families): 160 to 1998 rows, `same_line` restricted to &r1's cells. A lib relation per pair; it holds nothing beyond &r1 and the grid. The drawing shows `+` (more than 9 rows) at every cell, so it tells nothing by eye either.
- **&r3** (the axis family that holds all of a color's cells): 2/3/4/5 rows, one per color. Color to Axis4 is a functional dependency in every row: in e2, 3 and 5 are AXIS_V, 2 is AXIS_H and 1 is DAXIS_DG. This is the first table with signal about the task: one line per color, and its direction.
- **&r4** (each line cell P with each ink cell Q of its color): 91/270/494/1184 rows. The columns are (P, Q, axis, color): the drawing by c0 shows 6 on the 2 column and 7 on the 5 row of e0, the counts of Q per P, and `+` (13) at the crossing (3,3). Q is only a witness; the projection onto (P, color) is the whole line, 14 rows in e0. So most rows are noise, made by a column no later clause needs.
- **&r5** (crossings: the cell, the color that shows, the color it hides): 1/3/5/6 rows, drawn at the crossing cells. `(3,3) | 5 | 2` in e0, and in e1 `(4,4) | 9 | 0`, `(4,6) | 8 | 0`, `(6,6) | 9 | 8`. A selection of a few rows out of &r4, and it is the pairwise order of the stack. The signal about the rule jumps here.
- **&r6** (Propagation: the colors at or above each color): 3/6/10/15 rows, the reflexive closure of &r5's pairs. In e3 it is a total order, with n(n+1)/2 rows. A closure; it adds that the pairs chain into one order, which &r5 does not show by eye.
- **&r10** (Order rank, ascending): `2 | 0`, `5 | 1` in e0; `3 | 0`, `2 | 1`, `1 | 2`, `5 | 3` in e2. Read by rank, it is the output row of each train example: 2 5, 0 8 9, 3 2 1 5, 4 1 9 3 5. Each column is a key of every example's rows. Here the rule is visible, from the inputs only, before any DET.
- **&r11 to &r17** (other Order outputs): &r11 is the descending rank, &r12 the bottom color and &r13 the top, &r14 the successor pairs, &r15 the same with the wrap pair (`5 | 2` in e0), &r17 the strict order, which is &r6 without its reflexive rows. Each is a function of &r10. No later clause reads them. &r16, &r18 and &r19 have no table in the export.
- **&r20** (Cardinality of &r10): 2/3/4/5, the output width of each example. One row per example. It matches the output size, which only the grids show.
- **&r23** (DET DirDomain): DIR_T, DIR_B, DIR_L or DIR_R, one row at each of four assignments. It reads nothing; it lists a domain, and the engine tries each value.
- **&r24, &r25** (Frame along the axis of &r23, of length &r20): at DIR_T and DIR_B the cells are of an n x 1 column, and they print as boxes over the input grid (`r0-5 c0-6` is (0,0) of a 2x1 grid). At DIR_L and DIR_R they are the cells `(0,0)out` to `(0,4)out` of the output grid, drawn as 1 1 1 1 1. Assignment 2 equals 1, and 4 equals 3: the frame depends only on the axis. The drawing tells that the axis is AXIS_H, because only those assignments fit the output grid.
- **&r26** (the frame cells with their distance from the &r23 edge): at DIR_L the distances run 0 1 2 3 4, at DIR_R 4 3 2 1 0. The four assignments now differ.
- **&r27** (rank joined with the frame cell): at DIR_L (assignment 3) the drawings are 2 5, 0 8 9, 3 2 1 5 and 4 1 9 3 5, the output grids. At DIR_R they are the reverse. Only a comparison with the outputs picks DIR_L, as the clause adds nothing to tell them apart.

Rows that look like noise: &r2 and &r4 (pairs of cells, nearly all of the case's rows); &r11 to &r17 (Order outputs that nothing reads); &r23's four assignments, two of which (DIR_T, DIR_B) give frames that fit no grid of the task.
