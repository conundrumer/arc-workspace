# 3ac3eb23, case `$Parity $Dir`

- concept case: True; tokens: 467; tables: 26 relations, 26 per assignment
- cells: a Position is `(row,col)` of the example's input grid (`(row,col)out` where it fits only the output grid), an Offset `+(drow,dcol)`, another Box `rR0-R1 cC0-C1` over the input grid or `[t b l r]` margins; an Ident is `id<n>`, equal only within one case; see README.md

## Grids

### Train example 0: input 6x10, output 6x10

```
input                  output
0 2 0 0 0 8 0 0 0 0    0 2 0 0 0 8 0 0 0 0
0 0 0 0 0 0 0 0 0 0    2 0 2 0 8 0 8 0 0 0
0 0 0 0 0 0 0 0 0 0    0 2 0 0 0 8 0 0 0 0
0 0 0 0 0 0 0 0 0 0    2 0 2 0 8 0 8 0 0 0
0 0 0 0 0 0 0 0 0 0    0 2 0 0 0 8 0 0 0 0
0 0 0 0 0 0 0 0 0 0    2 0 2 0 8 0 8 0 0 0
```

### Train example 1: input 6x7, output 6x7

```
input            output
0 4 0 0 0 0 0    0 4 0 0 0 0 0
0 0 0 0 0 0 0    4 0 4 0 0 0 0
0 0 0 0 0 0 0    0 4 0 0 0 0 0
0 0 0 0 0 0 0    4 0 4 0 0 0 0
0 0 0 0 0 0 0    0 4 0 0 0 0 0
0 0 0 0 0 0 0    4 0 4 0 0 0 0
```

### Test example 0: input 6x12

```
0 0 3 0 0 0 6 0 0 7 0 0
0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0
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
- rows per train example: [0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
C
0
```

```
RULE input :0 * [L0] :1 * [L1] NOT &r0 :0 L1 END [&r1]
```

### &r1 (export table 3)

- columns: c0: Box, c1: Color
- depth 2, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [2, 1]; test: 3

Train example 0: 2 rows
Drawn on a 6x10 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . . . 8 . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
```
```
c0 | c1
(0,1) | 2
(0,5) | 8
```

Train example 1: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 4 . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1
(0,1) | 4
```

```
DET ex_input :0 * [L0] :1 * [L1] :2 * [L2] NOT &r0 :0 L2 ex_output :0 L0 END [&r2]
```

### &r2 (export table 4)

- columns: c0: Example, c1: Box, c2: Color
- depth 2, candidate keys none
- DETs its entries are assigned: &r0, &r2; assignments: 1
- rows per train example: [0, 0]; test: 0; task-wide: 3
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 2 rows
Drawn on a 6x10 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . . . 8 . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
```
```
c0 | c1 | c2
e0 | (0,1) | 2
e0 | (0,5) | 8
```

Task-wide, rows whose Example column is e1: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 4 . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
e1 | (0,1) | 4
```

```
DET &r2 :1 * [L0] dir_elem :0 * [L1] NOT margin :0 L0 :1 L1 :2 0 END [&r3]
```

### &r3 (export table 5)

- columns: c0: Dir, c1: Box
- depth 3, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3; assignments: 1
- rows per train example: [0, 0]; test: 0; task-wide: 9
- every row is of a task-wide entry

Task-wide: 9 rows
```
c0 | c1
DIR_B | [0 5 1 5]
DIR_B | [0 5 1 8]
DIR_B | [0 5 5 4]
DIR_L | [0 5 1 5]
DIR_L | [0 5 1 8]
DIR_L | [0 5 5 4]
DIR_R | [0 5 1 5]
DIR_R | [0 5 1 8]
DIR_R | [0 5 5 4]
```

```
DET dir_elem :0 * [L0] NOT &r3 :1 L0 END [&r4]
```

### &r4 (export table 6)

- columns: c0: Dir
- depth 4, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4; assignments: 1
- rows per train example: [0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
c0
DIR_T
```

```
RULE &r1 :0 * [L0] :1 * [L1] &r4 :0 * [L2] opposite :0 L2 :1 * [L3] END [&r5]
```

### &r5 (export table 7)

- columns: c0: Box, c1: Dir, c2: Dir, c3: Color
- depth 5, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4; assignments: 1
- rows per train example: [2, 1]; test: 3

Train example 0: 2 rows
Drawn on a 6x10 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . . . 8 . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
```
```
c0 | c1 | c2 | c3
(0,1) | DIR_T | DIR_B | 2
(0,5) | DIR_T | DIR_B | 8
```

Train example 1: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 4 . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2 | c3
(0,1) | DIR_T | DIR_B | 4
```

```
RULE input :0 * [L0] END [&r6]
```

### &r6 (export table 8)

- columns: c0: Box
- depth 1, candidate keys none
- rows per train example: [60, 42]; test: 72

Train example 0: 60 rows, the first 30 shown
Drawn on a 6x10 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1
```
```
c0
(0,0)
(0,1)
(0,2)
(0,3)
(0,4)
(0,5)
(0,6)
(0,7)
(0,8)
(0,9)
(1,0)
(1,1)
(1,2)
(1,3)
(1,4)
(1,5)
(1,6)
(1,7)
(1,8)
(1,9)
(2,0)
(2,1)
(2,2)
(2,3)
(2,4)
(2,5)
(2,6)
(2,7)
(2,8)
(2,9)
```

Train example 1: 42 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
```
```
c0
(0,0)
(0,1)
(0,2)
(0,3)
(0,4)
(0,5)
(0,6)
(1,0)
(1,1)
(1,2)
(1,3)
(1,4)
(1,5)
(1,6)
(2,0)
(2,1)
(2,2)
(2,3)
(2,4)
(2,5)
(2,6)
(3,0)
(3,1)
(3,2)
(3,3)
(3,4)
(3,5)
(3,6)
(4,0)
(4,1)
```

```
DET &r2 :0 * [L0] :1 * [L1] :2 * [L2] ex_output :0 L0 :1 * [L3] :2 L2 relative :0 L1 :1 L3 :2 * [L4] END [&r7]
```

### &r7 (export table 9)

- columns: c0: Example, c1: Box, c2: Box, c3: Box, c4: Color
- depth 3, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r7; assignments: 1
- rows per train example: [0, 0]; test: 0; task-wide: 27
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 18 rows
Drawn on a 6x10 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . . . 8 . . . .
2 . 2 . 8 . 8 . . .
. 2 . . . 8 . . . .
2 . 2 . 8 . 8 . . .
. 2 . . . 8 . . . .
2 . 2 . 8 . 8 . . .
```
```
c0 | c1 | c2 | c3 | c4
e0 | (0,1) | (0,1) | +(0,0) | 2
e0 | (0,5) | (0,5) | +(0,0) | 8
e0 | (1,0) | (0,1) | +(1,-1) | 2
e0 | (1,2) | (0,1) | +(1,1) | 2
e0 | (1,4) | (0,5) | +(1,-1) | 8
e0 | (1,6) | (0,5) | +(1,1) | 8
e0 | (2,1) | (0,1) | +(2,0) | 2
e0 | (2,5) | (0,5) | +(2,0) | 8
e0 | (3,0) | (0,1) | +(3,-1) | 2
e0 | (3,2) | (0,1) | +(3,1) | 2
e0 | (3,4) | (0,5) | +(3,-1) | 8
e0 | (3,6) | (0,5) | +(3,1) | 8
e0 | (4,1) | (0,1) | +(4,0) | 2
e0 | (4,5) | (0,5) | +(4,0) | 8
e0 | (5,0) | (0,1) | +(5,-1) | 2
e0 | (5,2) | (0,1) | +(5,1) | 2
e0 | (5,4) | (0,5) | +(5,-1) | 8
e0 | (5,6) | (0,5) | +(5,1) | 8
```

Task-wide, rows whose Example column is e1: 9 rows
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 4 . . . . .
4 . 4 . . . .
. 4 . . . . .
4 . 4 . . . .
. 4 . . . . .
4 . 4 . . . .
```
```
c0 | c1 | c2 | c3 | c4
e1 | (0,1) | (0,1) | +(0,0) | 4
e1 | (1,0) | (0,1) | +(1,-1) | 4
e1 | (1,2) | (0,1) | +(1,1) | 4
e1 | (2,1) | (0,1) | +(2,0) | 4
e1 | (3,0) | (0,1) | +(3,-1) | 4
e1 | (3,2) | (0,1) | +(3,1) | 4
e1 | (4,1) | (0,1) | +(4,0) | 4
e1 | (5,0) | (0,1) | +(5,-1) | 4
e1 | (5,2) | (0,1) | +(5,1) | 4
```

```
DET &r7 :0 * [L0] :1 * [L1] :4 * [L2] &r4 :0 * [L3] margin :0 L2 :1 L3 :2 * [L4] perp_dir :0 L3 :1 * [L5] margin :0 L2 :1 L5 :2 * [L6] >= L6 0 END [&r8]
```

### &r8 (export table 10)

- columns: c0: Example, c1: Dir, c2: Dir, c3: Box, c4: Number, c5: Number, c6: Box
- depth 5, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4, &r7, &r8; assignments: 1
- rows per train example: [0, 0]; test: 0; task-wide: 36
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 24 rows
Drawn on a 6x10 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. + . . . + . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
e0 | DIR_T | DIR_L | (0,1) | 0 | 0 | +(0,0)
e0 | DIR_T | DIR_L | (0,1) | 0 | 2 | +(2,0)
e0 | DIR_T | DIR_L | (0,1) | 0 | 4 | +(4,0)
e0 | DIR_T | DIR_L | (0,1) | 1 | 1 | +(1,1)
e0 | DIR_T | DIR_L | (0,1) | 1 | 3 | +(3,1)
e0 | DIR_T | DIR_L | (0,1) | 1 | 5 | +(5,1)
e0 | DIR_T | DIR_L | (0,5) | 0 | 0 | +(0,0)
e0 | DIR_T | DIR_L | (0,5) | 0 | 2 | +(2,0)
e0 | DIR_T | DIR_L | (0,5) | 0 | 4 | +(4,0)
e0 | DIR_T | DIR_L | (0,5) | 1 | 1 | +(1,1)
e0 | DIR_T | DIR_L | (0,5) | 1 | 3 | +(3,1)
e0 | DIR_T | DIR_L | (0,5) | 1 | 5 | +(5,1)
e0 | DIR_T | DIR_R | (0,1) | 0 | 0 | +(0,0)
e0 | DIR_T | DIR_R | (0,1) | 0 | 2 | +(2,0)
e0 | DIR_T | DIR_R | (0,1) | 0 | 4 | +(4,0)
e0 | DIR_T | DIR_R | (0,1) | 1 | 1 | +(1,-1)
e0 | DIR_T | DIR_R | (0,1) | 1 | 3 | +(3,-1)
e0 | DIR_T | DIR_R | (0,1) | 1 | 5 | +(5,-1)
e0 | DIR_T | DIR_R | (0,5) | 0 | 0 | +(0,0)
e0 | DIR_T | DIR_R | (0,5) | 0 | 2 | +(2,0)
e0 | DIR_T | DIR_R | (0,5) | 0 | 4 | +(4,0)
e0 | DIR_T | DIR_R | (0,5) | 1 | 1 | +(1,-1)
e0 | DIR_T | DIR_R | (0,5) | 1 | 3 | +(3,-1)
e0 | DIR_T | DIR_R | (0,5) | 1 | 5 | +(5,-1)
```

Task-wide, rows whose Example column is e1: 12 rows
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. + . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
e1 | DIR_T | DIR_L | (0,1) | 0 | 0 | +(0,0)
e1 | DIR_T | DIR_L | (0,1) | 0 | 2 | +(2,0)
e1 | DIR_T | DIR_L | (0,1) | 0 | 4 | +(4,0)
e1 | DIR_T | DIR_L | (0,1) | 1 | 1 | +(1,1)
e1 | DIR_T | DIR_L | (0,1) | 1 | 3 | +(3,1)
e1 | DIR_T | DIR_L | (0,1) | 1 | 5 | +(5,1)
e1 | DIR_T | DIR_R | (0,1) | 0 | 0 | +(0,0)
e1 | DIR_T | DIR_R | (0,1) | 0 | 2 | +(2,0)
e1 | DIR_T | DIR_R | (0,1) | 0 | 4 | +(4,0)
e1 | DIR_T | DIR_R | (0,1) | 1 | 1 | +(1,-1)
e1 | DIR_T | DIR_R | (0,1) | 1 | 3 | +(3,-1)
e1 | DIR_T | DIR_R | (0,1) | 1 | 5 | +(5,-1)
```

```
DET &r8 :4 * [L0] != L0 0 END [&r9]
```

### &r9 (export table 11)

- columns: c0: Number
- depth 6, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4, &r7, &r8, &r9; assignments: 1
- rows per train example: [0, 0]; test: 0; task-wide: 5
- every row is of a task-wide entry

Task-wide: 5 rows
```
c0
1
2
3
4
5
```

```
DET &r8 :0 * [L0] :1 * [L1] :4 * [L2] :6 * [L3] &r8 :0 L0 :1 L1 :4 * [L4] NOT &r8 :0 L0 :1 L1 :4 L4 :6 L3 END [&r10]
```

### &r10 (export table 12)

- columns: c0: Example, c1: Box, c2: Number, c3: Number, c4: Number
- depth 6, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4, &r7, &r8, &r10; assignments: 1
- rows per train example: [0, 0]; test: 0; task-wide: 54
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 36 rows, the first 30 shown
Drawn on a 6x10 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. + . . . + . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4
e0 | (0,1) | 0 | 1 | 1
e0 | (0,1) | 0 | 3 | 1
e0 | (0,1) | 0 | 5 | 1
e0 | (0,1) | 1 | 0 | 0
e0 | (0,1) | 1 | 2 | 0
e0 | (0,1) | 1 | 4 | 0
e0 | (0,1) | 2 | 1 | 1
e0 | (0,1) | 2 | 3 | 1
e0 | (0,1) | 2 | 5 | 1
e0 | (0,1) | 3 | 0 | 0
e0 | (0,1) | 3 | 2 | 0
e0 | (0,1) | 3 | 4 | 0
e0 | (0,1) | 4 | 1 | 1
e0 | (0,1) | 4 | 3 | 1
e0 | (0,1) | 4 | 5 | 1
e0 | (0,1) | 5 | 0 | 0
e0 | (0,1) | 5 | 2 | 0
e0 | (0,1) | 5 | 4 | 0
e0 | (0,5) | 0 | 1 | 1
e0 | (0,5) | 0 | 3 | 1
e0 | (0,5) | 0 | 5 | 1
e0 | (0,5) | 1 | 0 | 0
e0 | (0,5) | 1 | 2 | 0
e0 | (0,5) | 1 | 4 | 0
e0 | (0,5) | 2 | 1 | 1
e0 | (0,5) | 2 | 3 | 1
e0 | (0,5) | 2 | 5 | 1
e0 | (0,5) | 3 | 0 | 0
e0 | (0,5) | 3 | 2 | 0
e0 | (0,5) | 3 | 4 | 0
```

Task-wide, rows whose Example column is e1: 18 rows
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. + . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2 | c3 | c4
e1 | (0,1) | 0 | 1 | 1
e1 | (0,1) | 0 | 3 | 1
e1 | (0,1) | 0 | 5 | 1
e1 | (0,1) | 1 | 0 | 0
e1 | (0,1) | 1 | 2 | 0
e1 | (0,1) | 1 | 4 | 0
e1 | (0,1) | 2 | 1 | 1
e1 | (0,1) | 2 | 3 | 1
e1 | (0,1) | 2 | 5 | 1
e1 | (0,1) | 3 | 0 | 0
e1 | (0,1) | 3 | 2 | 0
e1 | (0,1) | 3 | 4 | 0
e1 | (0,1) | 4 | 1 | 1
e1 | (0,1) | 4 | 3 | 1
e1 | (0,1) | 4 | 5 | 1
e1 | (0,1) | 5 | 0 | 0
e1 | (0,1) | 5 | 2 | 0
e1 | (0,1) | 5 | 4 | 0
```

```
DET &r9 :0 * [L0] &r10 :2 * [L1] :4 * [L2] divide :0 L1 :1 L0 :2 0 :4 * [L3] divide :0 L2 :1 L0 :2 0 :4 L3 END [&r11]
```

### &r11 (export table 13)

- columns: c0: Number, c1: Number, c2: Number, c3: Number
- depth 7, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4, &r7, &r8, &r9, &r10, &r11; assignments: 1
- rows per train example: [0, 0]; test: 0; task-wide: 26
- every row is of a task-wide entry

Task-wide: 26 rows
```
c0 | c1 | c2 | c3
0 | 1 | 1 | 0
0 | 1 | 3 | 0
0 | 1 | 5 | 0
0 | 3 | 3 | 0
0 | 5 | 5 | 0
1 | 1 | 0 | 0
1 | 1 | 2 | 0
1 | 1 | 4 | 0
1 | 3 | 4 | 1
2 | 1 | 1 | 0
2 | 1 | 3 | 0
2 | 1 | 5 | 0
2 | 3 | 5 | 2
3 | 1 | 0 | 0
3 | 1 | 2 | 0
3 | 1 | 4 | 0
3 | 3 | 0 | 0
4 | 1 | 1 | 0
4 | 1 | 3 | 0
4 | 1 | 5 | 0
4 | 3 | 1 | 1
5 | 1 | 0 | 0
5 | 1 | 2 | 0
5 | 1 | 4 | 0
5 | 3 | 2 | 2
5 | 5 | 0 | 0
```

```
INIT Order [:0] SKIP [:1] &r9 :0 * [L0] NOT &r11 :0 L0 END [:0] END [:1] L0 END [:2] SKIP [:3] &r9 :0 * [L1] NOT &r11 :0 L1 END [:0] END [:1] L1 END [:2] L1 END [:4] SKIP [&r12] [&r13] [&r14] [&r15] [&r16] [&r17] [&r18] [&r19] [&r20] [&r21]
```

### &r12 (export table 14)

- columns: c0: Number, c1: Number
- depth 9, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4, &r7, &r8, &r9, &r10, &r11; assignments: 1
- rows per train example: [0, 0]; test: 0; task-wide: 2
- every row is of a task-wide entry

Task-wide: 2 rows
```
c0 | c1
2 | 0
4 | 1
```

### &r13 (export table 15)

- columns: c0: Number, c1: Number
- depth 9, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4, &r7, &r8, &r9, &r10, &r11; assignments: 1
- rows per train example: [0, 0]; test: 0; task-wide: 2
- every row is of a task-wide entry

Task-wide: 2 rows
```
c0 | c1
2 | 1
4 | 0
```

### &r14 (export table 16)

- columns: c0: Number
- depth 9, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4, &r7, &r8, &r9, &r10, &r11; assignments: 1
- rows per train example: [0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
c0
2
```

### &r15 (export table 17)

- columns: c0: Number
- depth 9, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4, &r7, &r8, &r9, &r10, &r11; assignments: 1
- rows per train example: [0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
c0
4
```

### &r16 (export table 18)

- columns: c0: Number, c1: Number
- depth 9, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4, &r7, &r8, &r9, &r10, &r11; assignments: 1
- rows per train example: [0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
c0 | c1
2 | 4
```

### &r17 (export table 19)

- columns: c0: Number, c1: Number
- depth 9, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4, &r7, &r8, &r9, &r10, &r11; assignments: 1
- rows per train example: [0, 0]; test: 0; task-wide: 2
- every row is of a task-wide entry

Task-wide: 2 rows
```
c0 | c1
2 | 4
4 | 2
```

```
DET &r14 :1 * [L0] END [&r22]
```

### &r22 (export table 20)

- columns: c0: Number
- depth 10, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4, &r7, &r8, &r9, &r10, &r11, &r22; assignments: 1
- rows per train example: [0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
c0
2
```

```
DET &r22 :0 * [L0] END [&r23]
```

### &r23 (export table 21)

- columns: c0: Number
- depth 11, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4, &r7, &r8, &r9, &r10, &r11, &r22, &r23; assignments: 1
- rows per train example: [0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
c0
2
```

```
INIT Ray [:0] SKIP [:1] &r5 :1 * [L0] END [:0] END [:1] L0 END [:2] input :0 * [L1] END [:0] END [:1] L1 END [:3] &r5 :4 * [L2] END [:0] END [:1] L2 END [&r24] [&r25] [&r26] [&r27] [&r28]
```

### &r24 (export table 22)

- columns: c0: Box, c1: Dir8, c2: Number, c3: Box
- depth 7, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4; assignments: 1
- rows per train example: [12, 6]; test: 18

Train example 0: 12 rows
Drawn on a 6x10 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. 0 . . . 0 . . . .
. 1 . . . 1 . . . .
. 2 . . . 2 . . . .
. 3 . . . 3 . . . .
. 4 . . . 4 . . . .
. 5 . . . 5 . . . .
```
```
c0 | c1 | c2 | c3
(0,1) | DIR_B | 0 | (0,1)
(0,5) | DIR_B | 0 | (0,5)
(1,1) | DIR_B | 1 | (0,1)
(1,5) | DIR_B | 1 | (0,5)
(2,1) | DIR_B | 2 | (0,1)
(2,5) | DIR_B | 2 | (0,5)
(3,1) | DIR_B | 3 | (0,1)
(3,5) | DIR_B | 3 | (0,5)
(4,1) | DIR_B | 4 | (0,1)
(4,5) | DIR_B | 4 | (0,5)
(5,1) | DIR_B | 5 | (0,1)
(5,5) | DIR_B | 5 | (0,5)
```

Train example 1: 6 rows
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. 0 . . . . .
. 1 . . . . .
. 2 . . . . .
. 3 . . . . .
. 4 . . . . .
. 5 . . . . .
```
```
c0 | c1 | c2 | c3
(0,1) | DIR_B | 0 | (0,1)
(1,1) | DIR_B | 1 | (0,1)
(2,1) | DIR_B | 2 | (0,1)
(3,1) | DIR_B | 3 | (0,1)
(4,1) | DIR_B | 4 | (0,1)
(5,1) | DIR_B | 5 | (0,1)
```

### &r25 (export table 23)

- columns: c0: Box, c1: Dir8, c2: Number, c3: Box
- depth 7, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4; assignments: 1
- rows per train example: [2, 1]; test: 3

Train example 0: 2 rows
Drawn on a 6x10 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
. . . . . . . . . .
. 5 . . . 5 . . . .
```
```
c0 | c1 | c2 | c3
(5,1) | DIR_B | 5 | (0,1)
(5,5) | DIR_B | 5 | (0,5)
```

Train example 1: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. 5 . . . . .
```
```
c0 | c1 | c2 | c3
(5,1) | DIR_B | 5 | (0,1)
```

```
RULE &r24 :1 * [L0] :2 * [L1] :3 * [L2] :4 * [L3] &r6 :0 L0 &r5 :1 * [L4] :3 L1 :0 L3 END [&r29]
```

### &r29 (export table 24)

- columns: c0: Box, c1: Dir, c2: Number, c3: Color, c4: Box
- depth 8, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4; assignments: 1
- rows per train example: [12, 6]; test: 18

Train example 0: 12 rows
Drawn on a 6x10 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . . . 8 . . . .
. 2 . . . 8 . . . .
. 2 . . . 8 . . . .
. 2 . . . 8 . . . .
. 2 . . . 8 . . . .
. 2 . . . 8 . . . .
```
```
c0 | c1 | c2 | c3 | c4
(0,1) | DIR_B | 0 | 2 | (0,1)
(0,5) | DIR_B | 0 | 8 | (0,5)
(1,1) | DIR_B | 1 | 2 | (0,1)
(1,5) | DIR_B | 1 | 8 | (0,5)
(2,1) | DIR_B | 2 | 2 | (0,1)
(2,5) | DIR_B | 2 | 8 | (0,5)
(3,1) | DIR_B | 3 | 2 | (0,1)
(3,5) | DIR_B | 3 | 8 | (0,5)
(4,1) | DIR_B | 4 | 2 | (0,1)
(4,5) | DIR_B | 4 | 8 | (0,5)
(5,1) | DIR_B | 5 | 2 | (0,1)
(5,5) | DIR_B | 5 | 8 | (0,5)
```

Train example 1: 6 rows
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 4 . . . . .
. 4 . . . . .
. 4 . . . . .
. 4 . . . . .
. 4 . . . . .
. 4 . . . . .
```
```
c0 | c1 | c2 | c3 | c4
(0,1) | DIR_B | 0 | 4 | (0,1)
(1,1) | DIR_B | 1 | 4 | (0,1)
(2,1) | DIR_B | 2 | 4 | (0,1)
(3,1) | DIR_B | 3 | 4 | (0,1)
(4,1) | DIR_B | 4 | 4 | (0,1)
(5,1) | DIR_B | 5 | 4 | (0,1)
```

```
RULE &r29 :4 * [L0] :1 * [L1] :0 * [L2] :2 * [L3] &r23 :0 * [L4] divide :0 L3 :1 L4 :2 0 :4 0 END [&r30]
```

### &r30 (export table 25)

- columns: c0: Number, c1: Box, c2: Dir, c3: Number, c4: Color
- depth 12, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4, &r7, &r8, &r9, &r10, &r11, &r22, &r23; assignments: 1
- rows per train example: [6, 3]; test: 9

Train example 0: 6 rows
Drawn on a 6x10 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . . . 8 . . . .
. . . . . . . . . .
. 2 . . . 8 . . . .
. . . . . . . . . .
. 2 . . . 8 . . . .
. . . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4
2 | (0,1) | DIR_B | 0 | 2
2 | (0,5) | DIR_B | 0 | 8
2 | (2,1) | DIR_B | 2 | 2
2 | (2,5) | DIR_B | 2 | 8
2 | (4,1) | DIR_B | 4 | 2
2 | (4,5) | DIR_B | 4 | 8
```

Train example 1: 3 rows
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 4 . . . . .
. . . . . . .
. 4 . . . . .
. . . . . . .
. 4 . . . . .
. . . . . . .
```
```
c0 | c1 | c2 | c3 | c4
2 | (0,1) | DIR_B | 0 | 4
2 | (2,1) | DIR_B | 2 | 4
2 | (4,1) | DIR_B | 4 | 4
```

```
RULE OR &r30 :0 * [L0] :2 * [L1] ALSO &r30 :0 L0 :1 * [L2] :2 * [L3] corner_dir :0 * [L4] :2 L2 neighbor :0 L3 :1 L4 :2 L1 input :0 L1 END END [&r31]
```

### &r31 (export table 26)

- columns: c0: Box, c1: Color
- depth 13, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4, &r7, &r8, &r9, &r10, &r11, &r22, &r23; assignments: 1
- rows per train example: [18, 9]; test: 27

Train example 0: 18 rows
Drawn on a 6x10 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . . . 8 . . . .
2 . 2 . 8 . 8 . . .
. 2 . . . 8 . . . .
2 . 2 . 8 . 8 . . .
. 2 . . . 8 . . . .
2 . 2 . 8 . 8 . . .
```
```
c0 | c1
(0,1) | 2
(0,5) | 8
(1,0) | 2
(1,2) | 2
(1,4) | 8
(1,6) | 8
(2,1) | 2
(2,5) | 8
(3,0) | 2
(3,2) | 2
(3,4) | 8
(3,6) | 8
(4,1) | 2
(4,5) | 8
(5,0) | 2
(5,2) | 2
(5,4) | 8
(5,6) | 8
```

Train example 1: 9 rows
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 4 . . . . .
4 . 4 . . . .
. 4 . . . . .
4 . 4 . . . .
. 4 . . . . .
4 . 4 . . . .
```
```
c0 | c1
(0,1) | 4
(1,0) | 4
(1,2) | 4
(2,1) | 4
(3,0) | 4
(3,2) | 4
(4,1) | 4
(5,0) | 4
(5,2) | 4
```

```
RULE OR &r31 :1 * [L0] :0 * [L1] ALSO input :0 L0 NOT &r31 :1 L0 &r0 :0 L1 END END [&r32]
```

### &r32 (export table 27)

- columns: c0: Box, c1: Color
- depth 14, candidate keys none
- DETs its entries are assigned: &r0, &r2, &r3, &r4, &r7, &r8, &r9, &r10, &r11, &r22, &r23; assignments: 1
- rows per train example: [60, 42]; test: 72

Train example 0: 60 rows, the first 30 shown
Drawn on a 6x10 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
0 2 0 0 0 8 0 0 0 0
2 0 2 0 8 0 8 0 0 0
0 2 0 0 0 8 0 0 0 0
2 0 2 0 8 0 8 0 0 0
0 2 0 0 0 8 0 0 0 0
2 0 2 0 8 0 8 0 0 0
```
```
c0 | c1
(0,0) | 0
(0,1) | 2
(0,2) | 0
(0,3) | 0
(0,4) | 0
(0,5) | 8
(0,6) | 0
(0,7) | 0
(0,8) | 0
(0,9) | 0
(1,0) | 2
(1,1) | 0
(1,2) | 2
(1,3) | 0
(1,4) | 8
(1,5) | 0
(1,6) | 8
(1,7) | 0
(1,8) | 0
(1,9) | 0
(2,0) | 0
(2,1) | 2
(2,2) | 0
(2,3) | 0
(2,4) | 0
(2,5) | 8
(2,6) | 0
(2,7) | 0
(2,8) | 0
(2,9) | 0
```

Train example 1: 42 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
0 4 0 0 0 0 0
4 0 4 0 0 0 0
0 4 0 0 0 0 0
4 0 4 0 0 0 0
0 4 0 0 0 0 0
4 0 4 0 0 0 0
```
```
c0 | c1
(0,0) | 0
(0,1) | 4
(0,2) | 0
(0,3) | 0
(0,4) | 0
(0,5) | 0
(0,6) | 0
(1,0) | 4
(1,1) | 0
(1,2) | 4
(1,3) | 0
(1,4) | 0
(1,5) | 0
(1,6) | 0
(2,0) | 0
(2,1) | 4
(2,2) | 0
(2,3) | 0
(2,4) | 0
(2,5) | 0
(2,6) | 0
(3,0) | 4
(3,1) | 0
(3,2) | 4
(3,3) | 0
(3,4) | 0
(3,5) | 0
(3,6) | 0
(4,0) | 0
(4,1) | 4
```

## What I see

The task: each marker on the top row casts a period-2 trail down, the marker's own column at even steps and its two side neighbors at odd steps. Each table has one assignment.

- **&r0** (DominantColor): 0.
- **&r1** (input cells not of color 0): the markers, `(0,1) | 2` and `(0,5) | 8` in e0, `(0,1) | 4` in e1. A selection: 2 of 60 cells.
- **&r2** (DET: the same cells, train examples only): &r1's rows with an Example column and without the test. A restatement.
- **&r3** (DET: each marker with each edge it is not on): 9 rows, 3 markers x {DIR_B, DIR_L, DIR_R}. The table has no Example column, so its Boxes print as margins: `[0 5 1 8]` is (0,1) of a 6x10 grid, `[0 5 1 5]` is (0,1) of a 6x7 grid. This is a product of the markers with three directions. Its information is the direction it lacks, DIR_T. **&r4** (DET: directions not in &r3) is DIR_T in one row: every marker is on the top edge. As &r31 and &r32 do in 1fad071e, a guard read under NOT gives the fact.
- **&r5** (seeds): &r1's rows with two constant columns, DIR_T and its opposite DIR_B. A restatement.
- **&r6** (input cells): every cell, 60/42 rows, a restatement of the input's cells (Ray.cell).
- **&r7** (DET: output cells of a marker's color, with their offset from the marker): 18/9 rows, drawn as the zigzag. This is the first table with information from the outputs.
- **&r8** (DET: each offset's steps down (c5) and to the side (c4), per side direction): 24/12 rows. Which Number column is which I took from the rows and the clause: the next clause reads the steps as position `:4`, which is the table's c5. In e1, `+(2,0)` has side 0 at step 2, and `+(3,1)` has side 1 at step 3. The three offsets on the column appear under both DIR_L and DIR_R, so the table repeats them. The rule is visible in these rows: side 0 at even steps, side 1 at odd steps.
- **&r9** (candidate periods): the steps 1 to 5.
- **&r10** (DET: pairs of steps of one trail whose sides differ): 36/18 rows. Each step (c2) is paired with every step of the other parity (c3), and c4 is the side at c3. The parity is plain in the rows, though no single row states it.
- **&r11** (mismatch): 26 rows in which c1 holds only 1, 3 and 5, the candidates that some differing pair breaks. 2 and 4 are absent.
- **&r12 to &r17** (Order over the unbroken candidates 2, 4): ranks, low 2 (&r14), high 4 (&r15), and the pairs (2, 4). Each is a function of the two values. **&r22** (period) and **&r23** (step_cells) restate &r14: 2. The information about the rule on this side jumps at &r4 (one direction) and at &r11, which leaves 2 and 4.
- **&r24** (Ray down from each marker): the column below each marker with its step count 0 to 5 (drawn as the numbers). A closure of the grid's step, implied by &r5 and the grid height. **&r25** is the ray ends at step 5.
- **&r29** (trail cells): &r24's rows with the marker's color. A restatement of &r24 joined with &r5.
- **&r30** (centers: steps divisible by &r23): 6/3 rows, at steps 0, 2 and 4. On the applied side, the period enters here, as a selection of &r29.
- **&r31** (lit: the centers and the two diagonal neighbors ahead of each): 18/9 rows, the same cells and colors as &r7's at each train example. The drawings are equal.
- **&r32** (out): equal to the outputs.

Rows that look like noise: &r2, &r5, &r6, &r29 (restatements); &r3 (a product read only for what it lacks); &r8's repeated center offsets; &r12, &r13, &r15 to &r17 (Order outputs that nothing reads).
