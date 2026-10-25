# bda2d7a6, case `$Recolor $ListCycle $FirstSeen`

- concept case: True; tokens: 525; tables: 45 relations, 164 per assignment
- cells: a Position is `(row,col)` of the example's input grid (`(row,col)out` where it fits only the output grid), an Offset `+(drow,dcol)`, another Box `rR0-R1 cC0-C1` over the input grid or `[t b l r]` margins; an Ident is `id<n>`, equal only within one case; see README.md

## Grids

### Train example 0: input 6x6, output 6x6

```
input          output
3 3 3 3 3 3    0 0 0 0 0 0
3 2 2 2 2 3    0 3 3 3 3 0
3 2 0 0 2 3    0 3 2 2 3 0
3 2 0 0 2 3    0 3 2 2 3 0
3 2 2 2 2 3    0 3 3 3 3 0
3 3 3 3 3 3    0 0 0 0 0 0
```

### Train example 1: input 6x6, output 6x6

```
input          output
0 0 0 0 0 0    6 6 6 6 6 6
0 7 7 7 7 0    6 0 0 0 0 6
0 7 6 6 7 0    6 0 7 7 0 6
0 7 6 6 7 0    6 0 7 7 0 6
0 7 7 7 7 0    6 0 0 0 0 6
0 0 0 0 0 0    6 6 6 6 6 6
```

### Train example 2: input 8x8, output 8x8

```
input              output
8 8 8 8 8 8 8 8    5 5 5 5 5 5 5 5
8 0 0 0 0 0 0 8    5 8 8 8 8 8 8 5
8 0 5 5 5 5 0 8    5 8 0 0 0 0 8 5
8 0 5 8 8 5 0 8    5 8 0 5 5 0 8 5
8 0 5 8 8 5 0 8    5 8 0 5 5 0 8 5
8 0 5 5 5 5 0 8    5 8 0 0 0 0 8 5
8 0 0 0 0 0 0 8    5 8 8 8 8 8 8 5
8 8 8 8 8 8 8 8    5 5 5 5 5 5 5 5
```

### Test example 0: input 6x6

```
9 9 9 9 9 9
9 0 0 0 0 9
9 0 1 1 0 9
9 0 1 1 0 9
9 0 0 0 0 9
9 9 9 9 9 9
```

### Test example 1: input 8x8

```
3 3 3 3 3 3 3 3
3 7 7 7 7 7 7 3
3 7 6 6 6 6 7 3
3 7 6 3 3 6 7 3
3 7 6 3 3 6 7 3
3 7 6 6 6 6 7 3
3 7 7 7 7 7 7 3
3 3 3 3 3 3 3 3
```

## Program and tables

Model-written tokens plain, engine-written ones in [brackets]. Each clause is followed by the tables of the relations it declares. A table whose entries hold several DET assignments is given once per assignment, each marked with the values, at that assignment, of the DETs whose value differs between them; a DET's value is the rows of its own table at that assignment.

```
INIT Boundary [:0] SKIP [:1] input :0 * [L0] END [:0] END [:1] L0 END [:2] SKIP [&r0] [&r1] [&r2] [&r3]
```

### &r0 (export table 2)

- columns: c0: Box
- depth 2, candidate keys none
- rows per train example: [20, 20, 28]; test: 48

Train example 0: 20 rows
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 . . . . 1
1 . . . . 1
1 . . . . 1
1 . . . . 1
1 1 1 1 1 1
```
```
c0
(0,0)
(0,1)
(0,2)
(0,3)
(0,4)
(0,5)
(1,0)
(1,5)
(2,0)
(2,5)
(3,0)
(3,5)
(4,0)
(4,5)
(5,0)
(5,1)
(5,2)
(5,3)
(5,4)
(5,5)
```

Train example 1: 20 rows
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 . . . . 1
1 . . . . 1
1 . . . . 1
1 . . . . 1
1 1 1 1 1 1
```
```
c0
(0,0)
(0,1)
(0,2)
(0,3)
(0,4)
(0,5)
(1,0)
(1,5)
(2,0)
(2,5)
(3,0)
(3,5)
(4,0)
(4,5)
(5,0)
(5,1)
(5,2)
(5,3)
(5,4)
(5,5)
```

Train example 2: 28 rows
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1
1 . . . . . . 1
1 . . . . . . 1
1 . . . . . . 1
1 . . . . . . 1
1 . . . . . . 1
1 . . . . . . 1
1 1 1 1 1 1 1 1
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
(1,0)
(1,7)
(2,0)
(2,7)
(3,0)
(3,7)
(4,0)
(4,7)
(5,0)
(5,7)
(6,0)
(6,7)
(7,0)
(7,1)
(7,2)
(7,3)
(7,4)
(7,5)
(7,6)
(7,7)
```

### &r1 (export table 3)

- columns: c0: Box, c1: Dir8
- depth 2, candidate keys none
- rows per train example: [24, 24, 32]; test: 56

Train example 0: 24 rows
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 1 1 1 1 2
1 . . . . 1
1 . . . . 1
1 . . . . 1
1 . . . . 1
2 1 1 1 1 2
```
```
c0 | c1
(0,0) | DIR_T
(0,0) | DIR_L
(0,1) | DIR_T
(0,2) | DIR_T
(0,3) | DIR_T
(0,4) | DIR_T
(0,5) | DIR_T
(0,5) | DIR_R
(1,0) | DIR_L
(1,5) | DIR_R
(2,0) | DIR_L
(2,5) | DIR_R
(3,0) | DIR_L
(3,5) | DIR_R
(4,0) | DIR_L
(4,5) | DIR_R
(5,0) | DIR_B
(5,0) | DIR_L
(5,1) | DIR_B
(5,2) | DIR_B
(5,3) | DIR_B
(5,4) | DIR_B
(5,5) | DIR_B
(5,5) | DIR_R
```

Train example 1: 24 rows
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 1 1 1 1 2
1 . . . . 1
1 . . . . 1
1 . . . . 1
1 . . . . 1
2 1 1 1 1 2
```
```
c0 | c1
(0,0) | DIR_T
(0,0) | DIR_L
(0,1) | DIR_T
(0,2) | DIR_T
(0,3) | DIR_T
(0,4) | DIR_T
(0,5) | DIR_T
(0,5) | DIR_R
(1,0) | DIR_L
(1,5) | DIR_R
(2,0) | DIR_L
(2,5) | DIR_R
(3,0) | DIR_L
(3,5) | DIR_R
(4,0) | DIR_L
(4,5) | DIR_R
(5,0) | DIR_B
(5,0) | DIR_L
(5,1) | DIR_B
(5,2) | DIR_B
(5,3) | DIR_B
(5,4) | DIR_B
(5,5) | DIR_B
(5,5) | DIR_R
```

Train example 2: 32 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 1 1 1 1 1 1 2
1 . . . . . . 1
1 . . . . . . 1
1 . . . . . . 1
1 . . . . . . 1
1 . . . . . . 1
1 . . . . . . 1
2 1 1 1 1 1 1 2
```
```
c0 | c1
(0,0) | DIR_T
(0,0) | DIR_L
(0,1) | DIR_T
(0,2) | DIR_T
(0,3) | DIR_T
(0,4) | DIR_T
(0,5) | DIR_T
(0,6) | DIR_T
(0,7) | DIR_T
(0,7) | DIR_R
(1,0) | DIR_L
(1,7) | DIR_R
(2,0) | DIR_L
(2,7) | DIR_R
(3,0) | DIR_L
(3,7) | DIR_R
(4,0) | DIR_L
(4,7) | DIR_R
(5,0) | DIR_L
(5,7) | DIR_R
(6,0) | DIR_L
(6,7) | DIR_R
(7,0) | DIR_B
(7,0) | DIR_L
(7,1) | DIR_B
(7,2) | DIR_B
(7,3) | DIR_B
(7,4) | DIR_B
(7,5) | DIR_B
(7,6) | DIR_B
```

```
INIT CellDistance [:0] SKIP [:1] input :0 * [L0] END [:0] END [:1] L0 END [:2] &r0 :2 * [L1] END [:0] END [:1] L1 END [:3] SKIP [&r4] [&r5] [&r6] [&r7] [&r8]
```

### &r4 (export table 4)

- columns: c0: Box, c1: Number
- depth 4, candidate keys none
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 0 0 0 0 0
0 1 1 1 1 0
0 1 2 2 1 0
0 1 2 2 1 0
0 1 1 1 1 0
0 0 0 0 0 0
```
```
c0 | c1
(0,0) | 0
(0,1) | 0
(0,2) | 0
(0,3) | 0
(0,4) | 0
(0,5) | 0
(1,0) | 0
(1,1) | 1
(1,2) | 1
(1,3) | 1
(1,4) | 1
(1,5) | 0
(2,0) | 0
(2,1) | 1
(2,2) | 2
(2,3) | 2
(2,4) | 1
(2,5) | 0
(3,0) | 0
(3,1) | 1
(3,2) | 2
(3,3) | 2
(3,4) | 1
(3,5) | 0
(4,0) | 0
(4,1) | 1
(4,2) | 1
(4,3) | 1
(4,4) | 1
(4,5) | 0
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 0 0 0 0 0
0 1 1 1 1 0
0 1 2 2 1 0
0 1 2 2 1 0
0 1 1 1 1 0
0 0 0 0 0 0
```
```
c0 | c1
(0,0) | 0
(0,1) | 0
(0,2) | 0
(0,3) | 0
(0,4) | 0
(0,5) | 0
(1,0) | 0
(1,1) | 1
(1,2) | 1
(1,3) | 1
(1,4) | 1
(1,5) | 0
(2,0) | 0
(2,1) | 1
(2,2) | 2
(2,3) | 2
(2,4) | 1
(2,5) | 0
(3,0) | 0
(3,1) | 1
(3,2) | 2
(3,3) | 2
(3,4) | 1
(3,5) | 0
(4,0) | 0
(4,1) | 1
(4,2) | 1
(4,3) | 1
(4,4) | 1
(4,5) | 0
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 0 0 0 0 0 0 0
0 1 1 1 1 1 1 0
0 1 2 2 2 2 1 0
0 1 2 3 3 2 1 0
0 1 2 3 3 2 1 0
0 1 2 2 2 2 1 0
0 1 1 1 1 1 1 0
0 0 0 0 0 0 0 0
```
```
c0 | c1
(0,0) | 0
(0,1) | 0
(0,2) | 0
(0,3) | 0
(0,4) | 0
(0,5) | 0
(0,6) | 0
(0,7) | 0
(1,0) | 0
(1,1) | 1
(1,2) | 1
(1,3) | 1
(1,4) | 1
(1,5) | 1
(1,6) | 1
(1,7) | 0
(2,0) | 0
(2,1) | 1
(2,2) | 2
(2,3) | 2
(2,4) | 2
(2,5) | 2
(2,6) | 1
(2,7) | 0
(3,0) | 0
(3,1) | 1
(3,2) | 2
(3,3) | 3
(3,4) | 3
(3,5) | 2
```

```
DET DiagDirAxisDomain ONE END END [&r9]
```

### &r9 (export table 5)

- columns: D: DiagDir, A: Axis
- depth 1, candidate keys [[]]
- DETs its entries are assigned: &r9; assignments: 8

#### &r9, assignment 1 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_V)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D | A
DIAG_TL | AXIS_V
```


#### &r9, assignment 2 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_H)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D | A
DIAG_TL | AXIS_H
```


#### &r9, assignment 3 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_V)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D | A
DIAG_TR | AXIS_V
```


#### &r9, assignment 4 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_H)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D | A
DIAG_TR | AXIS_H
```


#### &r9, assignment 5 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_V)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D | A
DIAG_BL | AXIS_V
```


#### &r9, assignment 6 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_H)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D | A
DIAG_BL | AXIS_H
```


#### &r9, assignment 7 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_V)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D | A
DIAG_BR | AXIS_V
```


#### &r9, assignment 8 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_H)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D | A
DIAG_BR | AXIS_H
```

```
RULE &r4 :1 * [L0] :2 * [L1] input :0 L0 :1 * [L2] END [&r10]
```

### &r10 (export table 6)

- columns: c0: Box, c1: Color, c2: Number
- depth 5, candidate keys none
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
3 3 3 3 3 3
3 2 2 2 2 3
3 2 0 0 2 3
3 2 0 0 2 3
3 2 2 2 2 3
3 3 3 3 3 3
```
```
c0 | c1 | c2
(0,0) | 3 | 0
(0,1) | 3 | 0
(0,2) | 3 | 0
(0,3) | 3 | 0
(0,4) | 3 | 0
(0,5) | 3 | 0
(1,0) | 3 | 0
(1,1) | 2 | 1
(1,2) | 2 | 1
(1,3) | 2 | 1
(1,4) | 2 | 1
(1,5) | 3 | 0
(2,0) | 3 | 0
(2,1) | 2 | 1
(2,2) | 0 | 2
(2,3) | 0 | 2
(2,4) | 2 | 1
(2,5) | 3 | 0
(3,0) | 3 | 0
(3,1) | 2 | 1
(3,2) | 0 | 2
(3,3) | 0 | 2
(3,4) | 2 | 1
(3,5) | 3 | 0
(4,0) | 3 | 0
(4,1) | 2 | 1
(4,2) | 2 | 1
(4,3) | 2 | 1
(4,4) | 2 | 1
(4,5) | 3 | 0
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
0 0 0 0 0 0
0 7 7 7 7 0
0 7 6 6 7 0
0 7 6 6 7 0
0 7 7 7 7 0
0 0 0 0 0 0
```
```
c0 | c1 | c2
(0,0) | 0 | 0
(0,1) | 0 | 0
(0,2) | 0 | 0
(0,3) | 0 | 0
(0,4) | 0 | 0
(0,5) | 0 | 0
(1,0) | 0 | 0
(1,1) | 7 | 1
(1,2) | 7 | 1
(1,3) | 7 | 1
(1,4) | 7 | 1
(1,5) | 0 | 0
(2,0) | 0 | 0
(2,1) | 7 | 1
(2,2) | 6 | 2
(2,3) | 6 | 2
(2,4) | 7 | 1
(2,5) | 0 | 0
(3,0) | 0 | 0
(3,1) | 7 | 1
(3,2) | 6 | 2
(3,3) | 6 | 2
(3,4) | 7 | 1
(3,5) | 0 | 0
(4,0) | 0 | 0
(4,1) | 7 | 1
(4,2) | 7 | 1
(4,3) | 7 | 1
(4,4) | 7 | 1
(4,5) | 0 | 0
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
8 8 8 8 8 8 8 8
8 0 0 0 0 0 0 8
8 0 5 5 5 5 0 8
8 0 5 8 8 5 0 8
8 0 5 8 8 5 0 8
8 0 5 5 5 5 0 8
8 0 0 0 0 0 0 8
8 8 8 8 8 8 8 8
```
```
c0 | c1 | c2
(0,0) | 8 | 0
(0,1) | 8 | 0
(0,2) | 8 | 0
(0,3) | 8 | 0
(0,4) | 8 | 0
(0,5) | 8 | 0
(0,6) | 8 | 0
(0,7) | 8 | 0
(1,0) | 8 | 0
(1,1) | 0 | 1
(1,2) | 0 | 1
(1,3) | 0 | 1
(1,4) | 0 | 1
(1,5) | 0 | 1
(1,6) | 0 | 1
(1,7) | 8 | 0
(2,0) | 8 | 0
(2,1) | 0 | 1
(2,2) | 5 | 2
(2,3) | 5 | 2
(2,4) | 5 | 2
(2,5) | 5 | 2
(2,6) | 0 | 1
(2,7) | 8 | 0
(3,0) | 8 | 0
(3,1) | 0 | 1
(3,2) | 5 | 2
(3,3) | 8 | 3
(3,4) | 8 | 3
(3,5) | 5 | 2
```

```
INIT Order [:0] &r10 :2 * [L0] :3 ^ [L1] END [:1] &r10 :2 * [L2] :3 L1 END [:0] END [:1] L2 END [:2] SKIP [:3] &r10 :2 * [L3] :3 L1 END [:0] END [:1] L3 END [:2] L3 END [:4] SKIP [:2] SKIP [:4] SKIP [&r11] [&r12] [&r13] [&r14] [&r15] [&r16] [&r17] [&r18] [&r19] [&r20]
```

### &r11 (export table 7)

- columns: c0: Color, c1: Number, c2: Number
- depth 7, candidate keys none
- rows per train example: [3, 3, 4]; test: 7

Train example 0: 3 rows
```
c0 | c1 | c2
0 | 2 | 0
2 | 1 | 0
3 | 0 | 0
```

Train example 1: 3 rows
```
c0 | c1 | c2
0 | 0 | 0
6 | 2 | 0
7 | 1 | 0
```

Train example 2: 4 rows
```
c0 | c1 | c2
0 | 1 | 0
5 | 2 | 0
8 | 0 | 0
8 | 3 | 1
```

### &r12 (export table 8)

- columns: c0: Color, c1: Number, c2: Number
- depth 7, candidate keys none
- rows per train example: [3, 3, 4]; test: 7

Train example 0: 3 rows
```
c0 | c1 | c2
0 | 2 | 0
2 | 1 | 0
3 | 0 | 0
```

Train example 1: 3 rows
```
c0 | c1 | c2
0 | 0 | 0
6 | 2 | 0
7 | 1 | 0
```

Train example 2: 4 rows
```
c0 | c1 | c2
0 | 1 | 0
5 | 2 | 0
8 | 0 | 1
8 | 3 | 0
```

### &r13 (export table 9)

- columns: c0: Color, c1: Number
- depth 7, candidate keys none
- rows per train example: [3, 3, 3]; test: 6

Train example 0: 3 rows
```
c0 | c1
0 | 2
2 | 1
3 | 0
```

Train example 1: 3 rows
```
c0 | c1
0 | 0
6 | 2
7 | 1
```

Train example 2: 3 rows
```
c0 | c1
0 | 1
5 | 2
8 | 0
```

### &r14 (export table 10)

- columns: c0: Color, c1: Number
- depth 7, candidate keys none
- rows per train example: [3, 3, 3]; test: 6

Train example 0: 3 rows
```
c0 | c1
0 | 2
2 | 1
3 | 0
```

Train example 1: 3 rows
```
c0 | c1
0 | 0
6 | 2
7 | 1
```

Train example 2: 3 rows
```
c0 | c1
0 | 1
5 | 2
8 | 3
```

### &r15 (export table 11)

- columns: c0: Color, c1: Number, c2: Number
- depth 7, candidate keys none
- rows per train example: [0, 0, 1]; test: 1

Train example 0: 0 rows

Train example 1: 0 rows

Train example 2: 1 row
```
c0 | c1 | c2
8 | 0 | 3
```

### &r16 (export table 12)

- columns: c0: Color, c1: Number, c2: Number
- depth 7, candidate keys none
- rows per train example: [3, 3, 4]; test: 7

Train example 0: 3 rows
```
c0 | c1 | c2
0 | 2 | 2
2 | 1 | 1
3 | 0 | 0
```

Train example 1: 3 rows
```
c0 | c1 | c2
0 | 0 | 0
6 | 2 | 2
7 | 1 | 1
```

Train example 2: 4 rows
```
c0 | c1 | c2
0 | 1 | 1
5 | 2 | 2
8 | 0 | 3
8 | 3 | 0
```

```
INIT Order [:0] SKIP [:1] input :1 * [L0] END [:0] END [:1] L0 END [:2] &r13 :1 :0 * [L1] END :2 * [L2] &r13 :1 :0 * [L3] END :2 * [L4] < L2 L4 END [:0] END [:1] L1 END [:2] L3 END [:3] SKIP [:4] SKIP [&r21] [&r22] [&r23] [&r24] [&r25] [&r26] [&r27] [&r28] [&r29] [&r30]
```

### &r21 (export table 13)

- columns: c0: Color, c1: Number
- depth 9, candidate keys none
- rows per train example: [3, 3, 3]; test: 6

Train example 0: 3 rows
```
c0 | c1
0 | 2
2 | 1
3 | 0
```

Train example 1: 3 rows
```
c0 | c1
0 | 0
6 | 2
7 | 1
```

Train example 2: 3 rows
```
c0 | c1
0 | 1
5 | 2
8 | 0
```

### &r22 (export table 14)

- columns: c0: Color, c1: Number
- depth 9, candidate keys none
- rows per train example: [3, 3, 3]; test: 6

Train example 0: 3 rows
```
c0 | c1
0 | 0
2 | 1
3 | 2
```

Train example 1: 3 rows
```
c0 | c1
0 | 2
6 | 0
7 | 1
```

Train example 2: 3 rows
```
c0 | c1
0 | 1
5 | 0
8 | 2
```

### &r23 (export table 15)

- columns: c0: Color
- depth 9, candidate keys none
- rows per train example: [1, 1, 1]; test: 2

Train example 0: 1 row
```
c0
3
```

Train example 1: 1 row
```
c0
0
```

Train example 2: 1 row
```
c0
8
```

### &r24 (export table 16)

- columns: c0: Color
- depth 9, candidate keys none
- rows per train example: [1, 1, 1]; test: 2

Train example 0: 1 row
```
c0
0
```

Train example 1: 1 row
```
c0
6
```

Train example 2: 1 row
```
c0
5
```

### &r25 (export table 17)

- columns: c0: Color, c1: Color
- depth 9, candidate keys none
- rows per train example: [2, 2, 2]; test: 4

Train example 0: 2 rows
```
c0 | c1
2 | 0
3 | 2
```

Train example 1: 2 rows
```
c0 | c1
0 | 7
7 | 6
```

Train example 2: 2 rows
```
c0 | c1
0 | 5
8 | 0
```

### &r26 (export table 18)

- columns: c0: Color, c1: Color
- depth 9, candidate keys none
- rows per train example: [3, 3, 3]; test: 6

Train example 0: 3 rows
```
c0 | c1
0 | 3
2 | 0
3 | 2
```

Train example 1: 3 rows
```
c0 | c1
0 | 7
6 | 0
7 | 6
```

Train example 2: 3 rows
```
c0 | c1
0 | 5
5 | 8
8 | 0
```

### &r28 (export table 19)

- columns: c0: Color, c1: Color
- depth 8, candidate keys none
- rows per train example: [3, 3, 3]; test: 6

Train example 0: 3 rows
```
c0 | c1
2 | 0
3 | 0
3 | 2
```

Train example 1: 3 rows
```
c0 | c1
0 | 6
0 | 7
7 | 6
```

Train example 2: 3 rows
```
c0 | c1
0 | 5
8 | 0
8 | 5
```

```
INIT Cardinality [:0] input :0 * [L0] :1 ^ [L1] END [:1] input :0 * [L2] :1 L1 END [:0] END [:1] L2 END [:2] SKIP [:2] SKIP [&r31] [&r32] [&r33]
```

### &r31 (export table 20)

- columns: c0: Color, c1: Number
- depth 2, candidate keys none
- rows per train example: [3, 3, 3]; test: 6

Train example 0: 3 rows
```
c0 | c1
0 | 4
2 | 12
3 | 20
```

Train example 1: 3 rows
```
c0 | c1
0 | 20
6 | 4
7 | 12
```

Train example 2: 3 rows
```
c0 | c1
0 | 20
5 | 12
8 | 32
```

```
INIT Order [:0] SKIP [:1] &r9 :0 * [L0] :1 * [L1] input :0 * [L2] END [:0] END [:1] L2 END [:2] &r9 :0 * [L3] :1 * [L4] input :0 * [L5] input :0 * [L6] OR corner_dir :0 L3 :1 L4 :2 * [L7] nearer :0 L7 :1 L5 :2 L6 ALSO diag_dirs :0 L3 :1 L4 :2 L7 :3 * [L8] same_dist :0 L7 :1 L5 :2 L6 nearer :0 L8 :1 L5 :2 L6 END END [:0] END [:1] L5 END [:2] L6 END [:3] SKIP [:4] SKIP [&r34] [&r35] [&r36] [&r37] [&r38] [&r39] [&r40] [&r41] [&r42] [&r43]
```

### &r34 (export table 21)

- columns: c0: Box, c1: Number
- depth 3, candidate keys none
- DETs its entries are assigned: &r9; assignments: 8

#### &r34, assignment 1 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 1 2 3 4 5
6 7 8 9 + +
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
```
```
c0 | c1
(0,0) | 0
(0,1) | 1
(0,2) | 2
(0,3) | 3
(0,4) | 4
(0,5) | 5
(1,0) | 6
(1,1) | 7
(1,2) | 8
(1,3) | 9
(1,4) | 10
(1,5) | 11
(2,0) | 12
(2,1) | 13
(2,2) | 14
(2,3) | 15
(2,4) | 16
(2,5) | 17
(3,0) | 18
(3,1) | 19
(3,2) | 20
(3,3) | 21
(3,4) | 22
(3,5) | 23
(4,0) | 24
(4,1) | 25
(4,2) | 26
(4,3) | 27
(4,4) | 28
(4,5) | 29
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 1 2 3 4 5
6 7 8 9 + +
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
```
```
c0 | c1
(0,0) | 0
(0,1) | 1
(0,2) | 2
(0,3) | 3
(0,4) | 4
(0,5) | 5
(1,0) | 6
(1,1) | 7
(1,2) | 8
(1,3) | 9
(1,4) | 10
(1,5) | 11
(2,0) | 12
(2,1) | 13
(2,2) | 14
(2,3) | 15
(2,4) | 16
(2,5) | 17
(3,0) | 18
(3,1) | 19
(3,2) | 20
(3,3) | 21
(3,4) | 22
(3,5) | 23
(4,0) | 24
(4,1) | 25
(4,2) | 26
(4,3) | 27
(4,4) | 28
(4,5) | 29
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 1 2 3 4 5 6 7
8 9 + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
```
```
c0 | c1
(0,0) | 0
(0,1) | 1
(0,2) | 2
(0,3) | 3
(0,4) | 4
(0,5) | 5
(0,6) | 6
(0,7) | 7
(1,0) | 8
(1,1) | 9
(1,2) | 10
(1,3) | 11
(1,4) | 12
(1,5) | 13
(1,6) | 14
(1,7) | 15
(2,0) | 16
(2,1) | 17
(2,2) | 18
(2,3) | 19
(2,4) | 20
(2,5) | 21
(2,6) | 22
(2,7) | 23
(3,0) | 24
(3,1) | 25
(3,2) | 26
(3,3) | 27
(3,4) | 28
(3,5) | 29
```


#### &r34, assignment 2 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_H)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 6 + + + +
1 7 + + + +
2 8 + + + +
3 9 + + + +
4 + + + + +
5 + + + + +
```
```
c0 | c1
(0,0) | 0
(0,1) | 6
(0,2) | 12
(0,3) | 18
(0,4) | 24
(0,5) | 30
(1,0) | 1
(1,1) | 7
(1,2) | 13
(1,3) | 19
(1,4) | 25
(1,5) | 31
(2,0) | 2
(2,1) | 8
(2,2) | 14
(2,3) | 20
(2,4) | 26
(2,5) | 32
(3,0) | 3
(3,1) | 9
(3,2) | 15
(3,3) | 21
(3,4) | 27
(3,5) | 33
(4,0) | 4
(4,1) | 10
(4,2) | 16
(4,3) | 22
(4,4) | 28
(4,5) | 34
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 6 + + + +
1 7 + + + +
2 8 + + + +
3 9 + + + +
4 + + + + +
5 + + + + +
```
```
c0 | c1
(0,0) | 0
(0,1) | 6
(0,2) | 12
(0,3) | 18
(0,4) | 24
(0,5) | 30
(1,0) | 1
(1,1) | 7
(1,2) | 13
(1,3) | 19
(1,4) | 25
(1,5) | 31
(2,0) | 2
(2,1) | 8
(2,2) | 14
(2,3) | 20
(2,4) | 26
(2,5) | 32
(3,0) | 3
(3,1) | 9
(3,2) | 15
(3,3) | 21
(3,4) | 27
(3,5) | 33
(4,0) | 4
(4,1) | 10
(4,2) | 16
(4,3) | 22
(4,4) | 28
(4,5) | 34
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 8 + + + + + +
1 9 + + + + + +
2 + + + + + + +
3 + + + + + + +
4 + + + + + + +
5 + + + + + + +
6 + + + + + + +
7 + + + + + + +
```
```
c0 | c1
(0,0) | 0
(0,1) | 8
(0,2) | 16
(0,3) | 24
(0,4) | 32
(0,5) | 40
(0,6) | 48
(0,7) | 56
(1,0) | 1
(1,1) | 9
(1,2) | 17
(1,3) | 25
(1,4) | 33
(1,5) | 41
(1,6) | 49
(1,7) | 57
(2,0) | 2
(2,1) | 10
(2,2) | 18
(2,3) | 26
(2,4) | 34
(2,5) | 42
(2,6) | 50
(2,7) | 58
(3,0) | 3
(3,1) | 11
(3,2) | 19
(3,3) | 27
(3,4) | 35
(3,5) | 43
```


#### &r34, assignment 3 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 4 3 2 1 0
+ + 9 8 7 6
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
```
```
c0 | c1
(0,0) | 5
(0,1) | 4
(0,2) | 3
(0,3) | 2
(0,4) | 1
(0,5) | 0
(1,0) | 11
(1,1) | 10
(1,2) | 9
(1,3) | 8
(1,4) | 7
(1,5) | 6
(2,0) | 17
(2,1) | 16
(2,2) | 15
(2,3) | 14
(2,4) | 13
(2,5) | 12
(3,0) | 23
(3,1) | 22
(3,2) | 21
(3,3) | 20
(3,4) | 19
(3,5) | 18
(4,0) | 29
(4,1) | 28
(4,2) | 27
(4,3) | 26
(4,4) | 25
(4,5) | 24
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 4 3 2 1 0
+ + 9 8 7 6
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
```
```
c0 | c1
(0,0) | 5
(0,1) | 4
(0,2) | 3
(0,3) | 2
(0,4) | 1
(0,5) | 0
(1,0) | 11
(1,1) | 10
(1,2) | 9
(1,3) | 8
(1,4) | 7
(1,5) | 6
(2,0) | 17
(2,1) | 16
(2,2) | 15
(2,3) | 14
(2,4) | 13
(2,5) | 12
(3,0) | 23
(3,1) | 22
(3,2) | 21
(3,3) | 20
(3,4) | 19
(3,5) | 18
(4,0) | 29
(4,1) | 28
(4,2) | 27
(4,3) | 26
(4,4) | 25
(4,5) | 24
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
7 6 5 4 3 2 1 0
+ + + + + + 9 8
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
```
```
c0 | c1
(0,0) | 7
(0,1) | 6
(0,2) | 5
(0,3) | 4
(0,4) | 3
(0,5) | 2
(0,6) | 1
(0,7) | 0
(1,0) | 15
(1,1) | 14
(1,2) | 13
(1,3) | 12
(1,4) | 11
(1,5) | 10
(1,6) | 9
(1,7) | 8
(2,0) | 23
(2,1) | 22
(2,2) | 21
(2,3) | 20
(2,4) | 19
(2,5) | 18
(2,6) | 17
(2,7) | 16
(3,0) | 31
(3,1) | 30
(3,2) | 29
(3,3) | 28
(3,4) | 27
(3,5) | 26
```


#### &r34, assignment 4 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_H)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + 6 0
+ + + + 7 1
+ + + + 8 2
+ + + + 9 3
+ + + + + 4
+ + + + + 5
```
```
c0 | c1
(0,0) | 30
(0,1) | 24
(0,2) | 18
(0,3) | 12
(0,4) | 6
(0,5) | 0
(1,0) | 31
(1,1) | 25
(1,2) | 19
(1,3) | 13
(1,4) | 7
(1,5) | 1
(2,0) | 32
(2,1) | 26
(2,2) | 20
(2,3) | 14
(2,4) | 8
(2,5) | 2
(3,0) | 33
(3,1) | 27
(3,2) | 21
(3,3) | 15
(3,4) | 9
(3,5) | 3
(4,0) | 34
(4,1) | 28
(4,2) | 22
(4,3) | 16
(4,4) | 10
(4,5) | 4
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + 6 0
+ + + + 7 1
+ + + + 8 2
+ + + + 9 3
+ + + + + 4
+ + + + + 5
```
```
c0 | c1
(0,0) | 30
(0,1) | 24
(0,2) | 18
(0,3) | 12
(0,4) | 6
(0,5) | 0
(1,0) | 31
(1,1) | 25
(1,2) | 19
(1,3) | 13
(1,4) | 7
(1,5) | 1
(2,0) | 32
(2,1) | 26
(2,2) | 20
(2,3) | 14
(2,4) | 8
(2,5) | 2
(3,0) | 33
(3,1) | 27
(3,2) | 21
(3,3) | 15
(3,4) | 9
(3,5) | 3
(4,0) | 34
(4,1) | 28
(4,2) | 22
(4,3) | 16
(4,4) | 10
(4,5) | 4
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + + 8 0
+ + + + + + 9 1
+ + + + + + + 2
+ + + + + + + 3
+ + + + + + + 4
+ + + + + + + 5
+ + + + + + + 6
+ + + + + + + 7
```
```
c0 | c1
(0,0) | 56
(0,1) | 48
(0,2) | 40
(0,3) | 32
(0,4) | 24
(0,5) | 16
(0,6) | 8
(0,7) | 0
(1,0) | 57
(1,1) | 49
(1,2) | 41
(1,3) | 33
(1,4) | 25
(1,5) | 17
(1,6) | 9
(1,7) | 1
(2,0) | 58
(2,1) | 50
(2,2) | 42
(2,3) | 34
(2,4) | 26
(2,5) | 18
(2,6) | 10
(2,7) | 2
(3,0) | 59
(3,1) | 51
(3,2) | 43
(3,3) | 35
(3,4) | 27
(3,5) | 19
```


#### &r34, assignment 5 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
6 7 8 9 + +
0 1 2 3 4 5
```
```
c0 | c1
(0,0) | 30
(0,1) | 31
(0,2) | 32
(0,3) | 33
(0,4) | 34
(0,5) | 35
(1,0) | 24
(1,1) | 25
(1,2) | 26
(1,3) | 27
(1,4) | 28
(1,5) | 29
(2,0) | 18
(2,1) | 19
(2,2) | 20
(2,3) | 21
(2,4) | 22
(2,5) | 23
(3,0) | 12
(3,1) | 13
(3,2) | 14
(3,3) | 15
(3,4) | 16
(3,5) | 17
(4,0) | 6
(4,1) | 7
(4,2) | 8
(4,3) | 9
(4,4) | 10
(4,5) | 11
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
6 7 8 9 + +
0 1 2 3 4 5
```
```
c0 | c1
(0,0) | 30
(0,1) | 31
(0,2) | 32
(0,3) | 33
(0,4) | 34
(0,5) | 35
(1,0) | 24
(1,1) | 25
(1,2) | 26
(1,3) | 27
(1,4) | 28
(1,5) | 29
(2,0) | 18
(2,1) | 19
(2,2) | 20
(2,3) | 21
(2,4) | 22
(2,5) | 23
(3,0) | 12
(3,1) | 13
(3,2) | 14
(3,3) | 15
(3,4) | 16
(3,5) | 17
(4,0) | 6
(4,1) | 7
(4,2) | 8
(4,3) | 9
(4,4) | 10
(4,5) | 11
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
8 9 + + + + + +
0 1 2 3 4 5 6 7
```
```
c0 | c1
(0,0) | 56
(0,1) | 57
(0,2) | 58
(0,3) | 59
(0,4) | 60
(0,5) | 61
(0,6) | 62
(0,7) | 63
(1,0) | 48
(1,1) | 49
(1,2) | 50
(1,3) | 51
(1,4) | 52
(1,5) | 53
(1,6) | 54
(1,7) | 55
(2,0) | 40
(2,1) | 41
(2,2) | 42
(2,3) | 43
(2,4) | 44
(2,5) | 45
(2,6) | 46
(2,7) | 47
(3,0) | 32
(3,1) | 33
(3,2) | 34
(3,3) | 35
(3,4) | 36
(3,5) | 37
```


#### &r34, assignment 6 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_H)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 + + + + +
4 + + + + +
3 9 + + + +
2 8 + + + +
1 7 + + + +
0 6 + + + +
```
```
c0 | c1
(0,0) | 5
(0,1) | 11
(0,2) | 17
(0,3) | 23
(0,4) | 29
(0,5) | 35
(1,0) | 4
(1,1) | 10
(1,2) | 16
(1,3) | 22
(1,4) | 28
(1,5) | 34
(2,0) | 3
(2,1) | 9
(2,2) | 15
(2,3) | 21
(2,4) | 27
(2,5) | 33
(3,0) | 2
(3,1) | 8
(3,2) | 14
(3,3) | 20
(3,4) | 26
(3,5) | 32
(4,0) | 1
(4,1) | 7
(4,2) | 13
(4,3) | 19
(4,4) | 25
(4,5) | 31
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 + + + + +
4 + + + + +
3 9 + + + +
2 8 + + + +
1 7 + + + +
0 6 + + + +
```
```
c0 | c1
(0,0) | 5
(0,1) | 11
(0,2) | 17
(0,3) | 23
(0,4) | 29
(0,5) | 35
(1,0) | 4
(1,1) | 10
(1,2) | 16
(1,3) | 22
(1,4) | 28
(1,5) | 34
(2,0) | 3
(2,1) | 9
(2,2) | 15
(2,3) | 21
(2,4) | 27
(2,5) | 33
(3,0) | 2
(3,1) | 8
(3,2) | 14
(3,3) | 20
(3,4) | 26
(3,5) | 32
(4,0) | 1
(4,1) | 7
(4,2) | 13
(4,3) | 19
(4,4) | 25
(4,5) | 31
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
7 + + + + + + +
6 + + + + + + +
5 + + + + + + +
4 + + + + + + +
3 + + + + + + +
2 + + + + + + +
1 9 + + + + + +
0 8 + + + + + +
```
```
c0 | c1
(0,0) | 7
(0,1) | 15
(0,2) | 23
(0,3) | 31
(0,4) | 39
(0,5) | 47
(0,6) | 55
(0,7) | 63
(1,0) | 6
(1,1) | 14
(1,2) | 22
(1,3) | 30
(1,4) | 38
(1,5) | 46
(1,6) | 54
(1,7) | 62
(2,0) | 5
(2,1) | 13
(2,2) | 21
(2,3) | 29
(2,4) | 37
(2,5) | 45
(2,6) | 53
(2,7) | 61
(3,0) | 4
(3,1) | 12
(3,2) | 20
(3,3) | 28
(3,4) | 36
(3,5) | 44
```


#### &r34, assignment 7 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
+ + 9 8 7 6
5 4 3 2 1 0
```
```
c0 | c1
(0,0) | 35
(0,1) | 34
(0,2) | 33
(0,3) | 32
(0,4) | 31
(0,5) | 30
(1,0) | 29
(1,1) | 28
(1,2) | 27
(1,3) | 26
(1,4) | 25
(1,5) | 24
(2,0) | 23
(2,1) | 22
(2,2) | 21
(2,3) | 20
(2,4) | 19
(2,5) | 18
(3,0) | 17
(3,1) | 16
(3,2) | 15
(3,3) | 14
(3,4) | 13
(3,5) | 12
(4,0) | 11
(4,1) | 10
(4,2) | 9
(4,3) | 8
(4,4) | 7
(4,5) | 6
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
+ + 9 8 7 6
5 4 3 2 1 0
```
```
c0 | c1
(0,0) | 35
(0,1) | 34
(0,2) | 33
(0,3) | 32
(0,4) | 31
(0,5) | 30
(1,0) | 29
(1,1) | 28
(1,2) | 27
(1,3) | 26
(1,4) | 25
(1,5) | 24
(2,0) | 23
(2,1) | 22
(2,2) | 21
(2,3) | 20
(2,4) | 19
(2,5) | 18
(3,0) | 17
(3,1) | 16
(3,2) | 15
(3,3) | 14
(3,4) | 13
(3,5) | 12
(4,0) | 11
(4,1) | 10
(4,2) | 9
(4,3) | 8
(4,4) | 7
(4,5) | 6
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + 9 8
7 6 5 4 3 2 1 0
```
```
c0 | c1
(0,0) | 63
(0,1) | 62
(0,2) | 61
(0,3) | 60
(0,4) | 59
(0,5) | 58
(0,6) | 57
(0,7) | 56
(1,0) | 55
(1,1) | 54
(1,2) | 53
(1,3) | 52
(1,4) | 51
(1,5) | 50
(1,6) | 49
(1,7) | 48
(2,0) | 47
(2,1) | 46
(2,2) | 45
(2,3) | 44
(2,4) | 43
(2,5) | 42
(2,6) | 41
(2,7) | 40
(3,0) | 39
(3,1) | 38
(3,2) | 37
(3,3) | 36
(3,4) | 35
(3,5) | 34
```


#### &r34, assignment 8 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_H)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + 5
+ + + + + 4
+ + + + 9 3
+ + + + 8 2
+ + + + 7 1
+ + + + 6 0
```
```
c0 | c1
(0,0) | 35
(0,1) | 29
(0,2) | 23
(0,3) | 17
(0,4) | 11
(0,5) | 5
(1,0) | 34
(1,1) | 28
(1,2) | 22
(1,3) | 16
(1,4) | 10
(1,5) | 4
(2,0) | 33
(2,1) | 27
(2,2) | 21
(2,3) | 15
(2,4) | 9
(2,5) | 3
(3,0) | 32
(3,1) | 26
(3,2) | 20
(3,3) | 14
(3,4) | 8
(3,5) | 2
(4,0) | 31
(4,1) | 25
(4,2) | 19
(4,3) | 13
(4,4) | 7
(4,5) | 1
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + 5
+ + + + + 4
+ + + + 9 3
+ + + + 8 2
+ + + + 7 1
+ + + + 6 0
```
```
c0 | c1
(0,0) | 35
(0,1) | 29
(0,2) | 23
(0,3) | 17
(0,4) | 11
(0,5) | 5
(1,0) | 34
(1,1) | 28
(1,2) | 22
(1,3) | 16
(1,4) | 10
(1,5) | 4
(2,0) | 33
(2,1) | 27
(2,2) | 21
(2,3) | 15
(2,4) | 9
(2,5) | 3
(3,0) | 32
(3,1) | 26
(3,2) | 20
(3,3) | 14
(3,4) | 8
(3,5) | 2
(4,0) | 31
(4,1) | 25
(4,2) | 19
(4,3) | 13
(4,4) | 7
(4,5) | 1
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + + + 7
+ + + + + + + 6
+ + + + + + + 5
+ + + + + + + 4
+ + + + + + + 3
+ + + + + + + 2
+ + + + + + 9 1
+ + + + + + 8 0
```
```
c0 | c1
(0,0) | 63
(0,1) | 55
(0,2) | 47
(0,3) | 39
(0,4) | 31
(0,5) | 23
(0,6) | 15
(0,7) | 7
(1,0) | 62
(1,1) | 54
(1,2) | 46
(1,3) | 38
(1,4) | 30
(1,5) | 22
(1,6) | 14
(1,7) | 6
(2,0) | 61
(2,1) | 53
(2,2) | 45
(2,3) | 37
(2,4) | 29
(2,5) | 21
(2,6) | 13
(2,7) | 5
(3,0) | 60
(3,1) | 52
(3,2) | 44
(3,3) | 36
(3,4) | 28
(3,5) | 20
```

### &r35 (export table 22)

- columns: c0: Box, c1: Number
- depth 3, candidate keys none
- DETs its entries are assigned: &r9; assignments: 8

#### &r35, assignment 1 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
+ + 9 8 7 6
5 4 3 2 1 0
```
```
c0 | c1
(0,0) | 35
(0,1) | 34
(0,2) | 33
(0,3) | 32
(0,4) | 31
(0,5) | 30
(1,0) | 29
(1,1) | 28
(1,2) | 27
(1,3) | 26
(1,4) | 25
(1,5) | 24
(2,0) | 23
(2,1) | 22
(2,2) | 21
(2,3) | 20
(2,4) | 19
(2,5) | 18
(3,0) | 17
(3,1) | 16
(3,2) | 15
(3,3) | 14
(3,4) | 13
(3,5) | 12
(4,0) | 11
(4,1) | 10
(4,2) | 9
(4,3) | 8
(4,4) | 7
(4,5) | 6
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
+ + 9 8 7 6
5 4 3 2 1 0
```
```
c0 | c1
(0,0) | 35
(0,1) | 34
(0,2) | 33
(0,3) | 32
(0,4) | 31
(0,5) | 30
(1,0) | 29
(1,1) | 28
(1,2) | 27
(1,3) | 26
(1,4) | 25
(1,5) | 24
(2,0) | 23
(2,1) | 22
(2,2) | 21
(2,3) | 20
(2,4) | 19
(2,5) | 18
(3,0) | 17
(3,1) | 16
(3,2) | 15
(3,3) | 14
(3,4) | 13
(3,5) | 12
(4,0) | 11
(4,1) | 10
(4,2) | 9
(4,3) | 8
(4,4) | 7
(4,5) | 6
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + 9 8
7 6 5 4 3 2 1 0
```
```
c0 | c1
(0,0) | 63
(0,1) | 62
(0,2) | 61
(0,3) | 60
(0,4) | 59
(0,5) | 58
(0,6) | 57
(0,7) | 56
(1,0) | 55
(1,1) | 54
(1,2) | 53
(1,3) | 52
(1,4) | 51
(1,5) | 50
(1,6) | 49
(1,7) | 48
(2,0) | 47
(2,1) | 46
(2,2) | 45
(2,3) | 44
(2,4) | 43
(2,5) | 42
(2,6) | 41
(2,7) | 40
(3,0) | 39
(3,1) | 38
(3,2) | 37
(3,3) | 36
(3,4) | 35
(3,5) | 34
```


#### &r35, assignment 2 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_H)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + 5
+ + + + + 4
+ + + + 9 3
+ + + + 8 2
+ + + + 7 1
+ + + + 6 0
```
```
c0 | c1
(0,0) | 35
(0,1) | 29
(0,2) | 23
(0,3) | 17
(0,4) | 11
(0,5) | 5
(1,0) | 34
(1,1) | 28
(1,2) | 22
(1,3) | 16
(1,4) | 10
(1,5) | 4
(2,0) | 33
(2,1) | 27
(2,2) | 21
(2,3) | 15
(2,4) | 9
(2,5) | 3
(3,0) | 32
(3,1) | 26
(3,2) | 20
(3,3) | 14
(3,4) | 8
(3,5) | 2
(4,0) | 31
(4,1) | 25
(4,2) | 19
(4,3) | 13
(4,4) | 7
(4,5) | 1
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + 5
+ + + + + 4
+ + + + 9 3
+ + + + 8 2
+ + + + 7 1
+ + + + 6 0
```
```
c0 | c1
(0,0) | 35
(0,1) | 29
(0,2) | 23
(0,3) | 17
(0,4) | 11
(0,5) | 5
(1,0) | 34
(1,1) | 28
(1,2) | 22
(1,3) | 16
(1,4) | 10
(1,5) | 4
(2,0) | 33
(2,1) | 27
(2,2) | 21
(2,3) | 15
(2,4) | 9
(2,5) | 3
(3,0) | 32
(3,1) | 26
(3,2) | 20
(3,3) | 14
(3,4) | 8
(3,5) | 2
(4,0) | 31
(4,1) | 25
(4,2) | 19
(4,3) | 13
(4,4) | 7
(4,5) | 1
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + + + 7
+ + + + + + + 6
+ + + + + + + 5
+ + + + + + + 4
+ + + + + + + 3
+ + + + + + + 2
+ + + + + + 9 1
+ + + + + + 8 0
```
```
c0 | c1
(0,0) | 63
(0,1) | 55
(0,2) | 47
(0,3) | 39
(0,4) | 31
(0,5) | 23
(0,6) | 15
(0,7) | 7
(1,0) | 62
(1,1) | 54
(1,2) | 46
(1,3) | 38
(1,4) | 30
(1,5) | 22
(1,6) | 14
(1,7) | 6
(2,0) | 61
(2,1) | 53
(2,2) | 45
(2,3) | 37
(2,4) | 29
(2,5) | 21
(2,6) | 13
(2,7) | 5
(3,0) | 60
(3,1) | 52
(3,2) | 44
(3,3) | 36
(3,4) | 28
(3,5) | 20
```


#### &r35, assignment 3 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
6 7 8 9 + +
0 1 2 3 4 5
```
```
c0 | c1
(0,0) | 30
(0,1) | 31
(0,2) | 32
(0,3) | 33
(0,4) | 34
(0,5) | 35
(1,0) | 24
(1,1) | 25
(1,2) | 26
(1,3) | 27
(1,4) | 28
(1,5) | 29
(2,0) | 18
(2,1) | 19
(2,2) | 20
(2,3) | 21
(2,4) | 22
(2,5) | 23
(3,0) | 12
(3,1) | 13
(3,2) | 14
(3,3) | 15
(3,4) | 16
(3,5) | 17
(4,0) | 6
(4,1) | 7
(4,2) | 8
(4,3) | 9
(4,4) | 10
(4,5) | 11
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
6 7 8 9 + +
0 1 2 3 4 5
```
```
c0 | c1
(0,0) | 30
(0,1) | 31
(0,2) | 32
(0,3) | 33
(0,4) | 34
(0,5) | 35
(1,0) | 24
(1,1) | 25
(1,2) | 26
(1,3) | 27
(1,4) | 28
(1,5) | 29
(2,0) | 18
(2,1) | 19
(2,2) | 20
(2,3) | 21
(2,4) | 22
(2,5) | 23
(3,0) | 12
(3,1) | 13
(3,2) | 14
(3,3) | 15
(3,4) | 16
(3,5) | 17
(4,0) | 6
(4,1) | 7
(4,2) | 8
(4,3) | 9
(4,4) | 10
(4,5) | 11
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
8 9 + + + + + +
0 1 2 3 4 5 6 7
```
```
c0 | c1
(0,0) | 56
(0,1) | 57
(0,2) | 58
(0,3) | 59
(0,4) | 60
(0,5) | 61
(0,6) | 62
(0,7) | 63
(1,0) | 48
(1,1) | 49
(1,2) | 50
(1,3) | 51
(1,4) | 52
(1,5) | 53
(1,6) | 54
(1,7) | 55
(2,0) | 40
(2,1) | 41
(2,2) | 42
(2,3) | 43
(2,4) | 44
(2,5) | 45
(2,6) | 46
(2,7) | 47
(3,0) | 32
(3,1) | 33
(3,2) | 34
(3,3) | 35
(3,4) | 36
(3,5) | 37
```


#### &r35, assignment 4 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_H)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 + + + + +
4 + + + + +
3 9 + + + +
2 8 + + + +
1 7 + + + +
0 6 + + + +
```
```
c0 | c1
(0,0) | 5
(0,1) | 11
(0,2) | 17
(0,3) | 23
(0,4) | 29
(0,5) | 35
(1,0) | 4
(1,1) | 10
(1,2) | 16
(1,3) | 22
(1,4) | 28
(1,5) | 34
(2,0) | 3
(2,1) | 9
(2,2) | 15
(2,3) | 21
(2,4) | 27
(2,5) | 33
(3,0) | 2
(3,1) | 8
(3,2) | 14
(3,3) | 20
(3,4) | 26
(3,5) | 32
(4,0) | 1
(4,1) | 7
(4,2) | 13
(4,3) | 19
(4,4) | 25
(4,5) | 31
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 + + + + +
4 + + + + +
3 9 + + + +
2 8 + + + +
1 7 + + + +
0 6 + + + +
```
```
c0 | c1
(0,0) | 5
(0,1) | 11
(0,2) | 17
(0,3) | 23
(0,4) | 29
(0,5) | 35
(1,0) | 4
(1,1) | 10
(1,2) | 16
(1,3) | 22
(1,4) | 28
(1,5) | 34
(2,0) | 3
(2,1) | 9
(2,2) | 15
(2,3) | 21
(2,4) | 27
(2,5) | 33
(3,0) | 2
(3,1) | 8
(3,2) | 14
(3,3) | 20
(3,4) | 26
(3,5) | 32
(4,0) | 1
(4,1) | 7
(4,2) | 13
(4,3) | 19
(4,4) | 25
(4,5) | 31
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
7 + + + + + + +
6 + + + + + + +
5 + + + + + + +
4 + + + + + + +
3 + + + + + + +
2 + + + + + + +
1 9 + + + + + +
0 8 + + + + + +
```
```
c0 | c1
(0,0) | 7
(0,1) | 15
(0,2) | 23
(0,3) | 31
(0,4) | 39
(0,5) | 47
(0,6) | 55
(0,7) | 63
(1,0) | 6
(1,1) | 14
(1,2) | 22
(1,3) | 30
(1,4) | 38
(1,5) | 46
(1,6) | 54
(1,7) | 62
(2,0) | 5
(2,1) | 13
(2,2) | 21
(2,3) | 29
(2,4) | 37
(2,5) | 45
(2,6) | 53
(2,7) | 61
(3,0) | 4
(3,1) | 12
(3,2) | 20
(3,3) | 28
(3,4) | 36
(3,5) | 44
```


#### &r35, assignment 5 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 4 3 2 1 0
+ + 9 8 7 6
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
```
```
c0 | c1
(0,0) | 5
(0,1) | 4
(0,2) | 3
(0,3) | 2
(0,4) | 1
(0,5) | 0
(1,0) | 11
(1,1) | 10
(1,2) | 9
(1,3) | 8
(1,4) | 7
(1,5) | 6
(2,0) | 17
(2,1) | 16
(2,2) | 15
(2,3) | 14
(2,4) | 13
(2,5) | 12
(3,0) | 23
(3,1) | 22
(3,2) | 21
(3,3) | 20
(3,4) | 19
(3,5) | 18
(4,0) | 29
(4,1) | 28
(4,2) | 27
(4,3) | 26
(4,4) | 25
(4,5) | 24
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 4 3 2 1 0
+ + 9 8 7 6
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
```
```
c0 | c1
(0,0) | 5
(0,1) | 4
(0,2) | 3
(0,3) | 2
(0,4) | 1
(0,5) | 0
(1,0) | 11
(1,1) | 10
(1,2) | 9
(1,3) | 8
(1,4) | 7
(1,5) | 6
(2,0) | 17
(2,1) | 16
(2,2) | 15
(2,3) | 14
(2,4) | 13
(2,5) | 12
(3,0) | 23
(3,1) | 22
(3,2) | 21
(3,3) | 20
(3,4) | 19
(3,5) | 18
(4,0) | 29
(4,1) | 28
(4,2) | 27
(4,3) | 26
(4,4) | 25
(4,5) | 24
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
7 6 5 4 3 2 1 0
+ + + + + + 9 8
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
```
```
c0 | c1
(0,0) | 7
(0,1) | 6
(0,2) | 5
(0,3) | 4
(0,4) | 3
(0,5) | 2
(0,6) | 1
(0,7) | 0
(1,0) | 15
(1,1) | 14
(1,2) | 13
(1,3) | 12
(1,4) | 11
(1,5) | 10
(1,6) | 9
(1,7) | 8
(2,0) | 23
(2,1) | 22
(2,2) | 21
(2,3) | 20
(2,4) | 19
(2,5) | 18
(2,6) | 17
(2,7) | 16
(3,0) | 31
(3,1) | 30
(3,2) | 29
(3,3) | 28
(3,4) | 27
(3,5) | 26
```


#### &r35, assignment 6 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_H)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + 6 0
+ + + + 7 1
+ + + + 8 2
+ + + + 9 3
+ + + + + 4
+ + + + + 5
```
```
c0 | c1
(0,0) | 30
(0,1) | 24
(0,2) | 18
(0,3) | 12
(0,4) | 6
(0,5) | 0
(1,0) | 31
(1,1) | 25
(1,2) | 19
(1,3) | 13
(1,4) | 7
(1,5) | 1
(2,0) | 32
(2,1) | 26
(2,2) | 20
(2,3) | 14
(2,4) | 8
(2,5) | 2
(3,0) | 33
(3,1) | 27
(3,2) | 21
(3,3) | 15
(3,4) | 9
(3,5) | 3
(4,0) | 34
(4,1) | 28
(4,2) | 22
(4,3) | 16
(4,4) | 10
(4,5) | 4
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + 6 0
+ + + + 7 1
+ + + + 8 2
+ + + + 9 3
+ + + + + 4
+ + + + + 5
```
```
c0 | c1
(0,0) | 30
(0,1) | 24
(0,2) | 18
(0,3) | 12
(0,4) | 6
(0,5) | 0
(1,0) | 31
(1,1) | 25
(1,2) | 19
(1,3) | 13
(1,4) | 7
(1,5) | 1
(2,0) | 32
(2,1) | 26
(2,2) | 20
(2,3) | 14
(2,4) | 8
(2,5) | 2
(3,0) | 33
(3,1) | 27
(3,2) | 21
(3,3) | 15
(3,4) | 9
(3,5) | 3
(4,0) | 34
(4,1) | 28
(4,2) | 22
(4,3) | 16
(4,4) | 10
(4,5) | 4
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
+ + + + + + 8 0
+ + + + + + 9 1
+ + + + + + + 2
+ + + + + + + 3
+ + + + + + + 4
+ + + + + + + 5
+ + + + + + + 6
+ + + + + + + 7
```
```
c0 | c1
(0,0) | 56
(0,1) | 48
(0,2) | 40
(0,3) | 32
(0,4) | 24
(0,5) | 16
(0,6) | 8
(0,7) | 0
(1,0) | 57
(1,1) | 49
(1,2) | 41
(1,3) | 33
(1,4) | 25
(1,5) | 17
(1,6) | 9
(1,7) | 1
(2,0) | 58
(2,1) | 50
(2,2) | 42
(2,3) | 34
(2,4) | 26
(2,5) | 18
(2,6) | 10
(2,7) | 2
(3,0) | 59
(3,1) | 51
(3,2) | 43
(3,3) | 35
(3,4) | 27
(3,5) | 19
```


#### &r35, assignment 7 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 1 2 3 4 5
6 7 8 9 + +
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
```
```
c0 | c1
(0,0) | 0
(0,1) | 1
(0,2) | 2
(0,3) | 3
(0,4) | 4
(0,5) | 5
(1,0) | 6
(1,1) | 7
(1,2) | 8
(1,3) | 9
(1,4) | 10
(1,5) | 11
(2,0) | 12
(2,1) | 13
(2,2) | 14
(2,3) | 15
(2,4) | 16
(2,5) | 17
(3,0) | 18
(3,1) | 19
(3,2) | 20
(3,3) | 21
(3,4) | 22
(3,5) | 23
(4,0) | 24
(4,1) | 25
(4,2) | 26
(4,3) | 27
(4,4) | 28
(4,5) | 29
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 1 2 3 4 5
6 7 8 9 + +
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
```
```
c0 | c1
(0,0) | 0
(0,1) | 1
(0,2) | 2
(0,3) | 3
(0,4) | 4
(0,5) | 5
(1,0) | 6
(1,1) | 7
(1,2) | 8
(1,3) | 9
(1,4) | 10
(1,5) | 11
(2,0) | 12
(2,1) | 13
(2,2) | 14
(2,3) | 15
(2,4) | 16
(2,5) | 17
(3,0) | 18
(3,1) | 19
(3,2) | 20
(3,3) | 21
(3,4) | 22
(3,5) | 23
(4,0) | 24
(4,1) | 25
(4,2) | 26
(4,3) | 27
(4,4) | 28
(4,5) | 29
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 1 2 3 4 5 6 7
8 9 + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
```
```
c0 | c1
(0,0) | 0
(0,1) | 1
(0,2) | 2
(0,3) | 3
(0,4) | 4
(0,5) | 5
(0,6) | 6
(0,7) | 7
(1,0) | 8
(1,1) | 9
(1,2) | 10
(1,3) | 11
(1,4) | 12
(1,5) | 13
(1,6) | 14
(1,7) | 15
(2,0) | 16
(2,1) | 17
(2,2) | 18
(2,3) | 19
(2,4) | 20
(2,5) | 21
(2,6) | 22
(2,7) | 23
(3,0) | 24
(3,1) | 25
(3,2) | 26
(3,3) | 27
(3,4) | 28
(3,5) | 29
```


#### &r35, assignment 8 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_H)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 6 + + + +
1 7 + + + +
2 8 + + + +
3 9 + + + +
4 + + + + +
5 + + + + +
```
```
c0 | c1
(0,0) | 0
(0,1) | 6
(0,2) | 12
(0,3) | 18
(0,4) | 24
(0,5) | 30
(1,0) | 1
(1,1) | 7
(1,2) | 13
(1,3) | 19
(1,4) | 25
(1,5) | 31
(2,0) | 2
(2,1) | 8
(2,2) | 14
(2,3) | 20
(2,4) | 26
(2,5) | 32
(3,0) | 3
(3,1) | 9
(3,2) | 15
(3,3) | 21
(3,4) | 27
(3,5) | 33
(4,0) | 4
(4,1) | 10
(4,2) | 16
(4,3) | 22
(4,4) | 28
(4,5) | 34
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 6 + + + +
1 7 + + + +
2 8 + + + +
3 9 + + + +
4 + + + + +
5 + + + + +
```
```
c0 | c1
(0,0) | 0
(0,1) | 6
(0,2) | 12
(0,3) | 18
(0,4) | 24
(0,5) | 30
(1,0) | 1
(1,1) | 7
(1,2) | 13
(1,3) | 19
(1,4) | 25
(1,5) | 31
(2,0) | 2
(2,1) | 8
(2,2) | 14
(2,3) | 20
(2,4) | 26
(2,5) | 32
(3,0) | 3
(3,1) | 9
(3,2) | 15
(3,3) | 21
(3,4) | 27
(3,5) | 33
(4,0) | 4
(4,1) | 10
(4,2) | 16
(4,3) | 22
(4,4) | 28
(4,5) | 34
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 8 + + + + + +
1 9 + + + + + +
2 + + + + + + +
3 + + + + + + +
4 + + + + + + +
5 + + + + + + +
6 + + + + + + +
7 + + + + + + +
```
```
c0 | c1
(0,0) | 0
(0,1) | 8
(0,2) | 16
(0,3) | 24
(0,4) | 32
(0,5) | 40
(0,6) | 48
(0,7) | 56
(1,0) | 1
(1,1) | 9
(1,2) | 17
(1,3) | 25
(1,4) | 33
(1,5) | 41
(1,6) | 49
(1,7) | 57
(2,0) | 2
(2,1) | 10
(2,2) | 18
(2,3) | 26
(2,4) | 34
(2,5) | 42
(2,6) | 50
(2,7) | 58
(3,0) | 3
(3,1) | 11
(3,2) | 19
(3,3) | 27
(3,4) | 35
(3,5) | 43
```

### &r36 (export table 23)

- columns: c0: Box
- depth 3, candidate keys none
- DETs its entries are assigned: &r9; assignments: 8

#### &r36, assignment 1 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_V)}
- rows per train example: [1, 1, 1]; test: 2

Train example 0: 1 row
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
```
```
c0
(0,0)
```

Train example 1: 1 row
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
```
```
c0
(0,0)
```

Train example 2: 1 row
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
```
```
c0
(0,0)
```


#### &r36, assignment 2 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r36, assignment 3 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_V)}
- rows per train example: [1, 1, 1]; test: 2

Train example 0: 1 row
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . 1
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
```
```
c0
(0,5)
```

Train example 1: 1 row
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . 1
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
```
```
c0
(0,5)
```

Train example 2: 1 row
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . 1
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
```
```
c0
(0,7)
```


#### &r36, assignment 4 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_H)}
- rows equal to those of assignment 3 at every example

#### &r36, assignment 5 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_V)}
- rows per train example: [1, 1, 1]; test: 2

Train example 0: 1 row
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
1 . . . . .
```
```
c0
(5,0)
```

Train example 1: 1 row
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
1 . . . . .
```
```
c0
(5,0)
```

Train example 2: 1 row
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
1 . . . . . . .
```
```
c0
(7,0)
```


#### &r36, assignment 6 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_H)}
- rows equal to those of assignment 5 at every example

#### &r36, assignment 7 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_V)}
- rows per train example: [1, 1, 1]; test: 2

Train example 0: 1 row
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . 1
```
```
c0
(5,5)
```

Train example 1: 1 row
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . 1
```
```
c0
(5,5)
```

Train example 2: 1 row
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . 1
```
```
c0
(7,7)
```


#### &r36, assignment 8 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_H)}
- rows equal to those of assignment 7 at every example
### &r37 (export table 24)

- columns: c0: Box
- depth 3, candidate keys none
- DETs its entries are assigned: &r9; assignments: 8

#### &r37, assignment 1 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_V)}
- rows per train example: [1, 1, 1]; test: 2

Train example 0: 1 row
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . 1
```
```
c0
(5,5)
```

Train example 1: 1 row
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . 1
```
```
c0
(5,5)
```

Train example 2: 1 row
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . 1
```
```
c0
(7,7)
```


#### &r37, assignment 2 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r37, assignment 3 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_V)}
- rows per train example: [1, 1, 1]; test: 2

Train example 0: 1 row
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
1 . . . . .
```
```
c0
(5,0)
```

Train example 1: 1 row
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
1 . . . . .
```
```
c0
(5,0)
```

Train example 2: 1 row
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
1 . . . . . . .
```
```
c0
(7,0)
```


#### &r37, assignment 4 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_H)}
- rows equal to those of assignment 3 at every example

#### &r37, assignment 5 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_V)}
- rows per train example: [1, 1, 1]; test: 2

Train example 0: 1 row
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . 1
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
```
```
c0
(0,5)
```

Train example 1: 1 row
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . 1
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
```
```
c0
(0,5)
```

Train example 2: 1 row
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . 1
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
```
```
c0
(0,7)
```


#### &r37, assignment 6 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_H)}
- rows equal to those of assignment 5 at every example

#### &r37, assignment 7 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_V)}
- rows per train example: [1, 1, 1]; test: 2

Train example 0: 1 row
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
```
```
c0
(0,0)
```

Train example 1: 1 row
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
. . . . . .
```
```
c0
(0,0)
```

Train example 2: 1 row
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
```
```
c0
(0,0)
```


#### &r37, assignment 8 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_H)}
- rows equal to those of assignment 7 at every example
### &r38 (export table 25)

- columns: c0: Box, c1: Box
- depth 3, candidate keys none
- DETs its entries are assigned: &r9; assignments: 8

#### &r38, assignment 1 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_V)}
- rows per train example: [35, 35, 63]; test: 98

Train example 0: 35 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 .
```
```
c0 | c1
(0,0) | (0,1)
(0,1) | (0,2)
(0,2) | (0,3)
(0,3) | (0,4)
(0,4) | (0,5)
(0,5) | (1,0)
(1,0) | (1,1)
(1,1) | (1,2)
(1,2) | (1,3)
(1,3) | (1,4)
(1,4) | (1,5)
(1,5) | (2,0)
(2,0) | (2,1)
(2,1) | (2,2)
(2,2) | (2,3)
(2,3) | (2,4)
(2,4) | (2,5)
(2,5) | (3,0)
(3,0) | (3,1)
(3,1) | (3,2)
(3,2) | (3,3)
(3,3) | (3,4)
(3,4) | (3,5)
(3,5) | (4,0)
(4,0) | (4,1)
(4,1) | (4,2)
(4,2) | (4,3)
(4,3) | (4,4)
(4,4) | (4,5)
(4,5) | (5,0)
```

Train example 1: 35 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 .
```
```
c0 | c1
(0,0) | (0,1)
(0,1) | (0,2)
(0,2) | (0,3)
(0,3) | (0,4)
(0,4) | (0,5)
(0,5) | (1,0)
(1,0) | (1,1)
(1,1) | (1,2)
(1,2) | (1,3)
(1,3) | (1,4)
(1,4) | (1,5)
(1,5) | (2,0)
(2,0) | (2,1)
(2,1) | (2,2)
(2,2) | (2,3)
(2,3) | (2,4)
(2,4) | (2,5)
(2,5) | (3,0)
(3,0) | (3,1)
(3,1) | (3,2)
(3,2) | (3,3)
(3,3) | (3,4)
(3,4) | (3,5)
(3,5) | (4,0)
(4,0) | (4,1)
(4,1) | (4,2)
(4,2) | (4,3)
(4,3) | (4,4)
(4,4) | (4,5)
(4,5) | (5,0)
```

Train example 2: 63 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 .
```
```
c0 | c1
(0,0) | (0,1)
(0,1) | (0,2)
(0,2) | (0,3)
(0,3) | (0,4)
(0,4) | (0,5)
(0,5) | (0,6)
(0,6) | (0,7)
(0,7) | (1,0)
(1,0) | (1,1)
(1,1) | (1,2)
(1,2) | (1,3)
(1,3) | (1,4)
(1,4) | (1,5)
(1,5) | (1,6)
(1,6) | (1,7)
(1,7) | (2,0)
(2,0) | (2,1)
(2,1) | (2,2)
(2,2) | (2,3)
(2,3) | (2,4)
(2,4) | (2,5)
(2,5) | (2,6)
(2,6) | (2,7)
(2,7) | (3,0)
(3,0) | (3,1)
(3,1) | (3,2)
(3,2) | (3,3)
(3,3) | (3,4)
(3,4) | (3,5)
(3,5) | (3,6)
```


#### &r38, assignment 2 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_H)}
- rows per train example: [35, 35, 63]; test: 98

Train example 0: 35 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 .
```
```
c0 | c1
(0,0) | (1,0)
(0,1) | (1,1)
(0,2) | (1,2)
(0,3) | (1,3)
(0,4) | (1,4)
(0,5) | (1,5)
(1,0) | (2,0)
(1,1) | (2,1)
(1,2) | (2,2)
(1,3) | (2,3)
(1,4) | (2,4)
(1,5) | (2,5)
(2,0) | (3,0)
(2,1) | (3,1)
(2,2) | (3,2)
(2,3) | (3,3)
(2,4) | (3,4)
(2,5) | (3,5)
(3,0) | (4,0)
(3,1) | (4,1)
(3,2) | (4,2)
(3,3) | (4,3)
(3,4) | (4,4)
(3,5) | (4,5)
(4,0) | (5,0)
(4,1) | (5,1)
(4,2) | (5,2)
(4,3) | (5,3)
(4,4) | (5,4)
(4,5) | (5,5)
```

Train example 1: 35 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 .
```
```
c0 | c1
(0,0) | (1,0)
(0,1) | (1,1)
(0,2) | (1,2)
(0,3) | (1,3)
(0,4) | (1,4)
(0,5) | (1,5)
(1,0) | (2,0)
(1,1) | (2,1)
(1,2) | (2,2)
(1,3) | (2,3)
(1,4) | (2,4)
(1,5) | (2,5)
(2,0) | (3,0)
(2,1) | (3,1)
(2,2) | (3,2)
(2,3) | (3,3)
(2,4) | (3,4)
(2,5) | (3,5)
(3,0) | (4,0)
(3,1) | (4,1)
(3,2) | (4,2)
(3,3) | (4,3)
(3,4) | (4,4)
(3,5) | (4,5)
(4,0) | (5,0)
(4,1) | (5,1)
(4,2) | (5,2)
(4,3) | (5,3)
(4,4) | (5,4)
(4,5) | (5,5)
```

Train example 2: 63 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 .
```
```
c0 | c1
(0,0) | (1,0)
(0,1) | (1,1)
(0,2) | (1,2)
(0,3) | (1,3)
(0,4) | (1,4)
(0,5) | (1,5)
(0,6) | (1,6)
(0,7) | (1,7)
(1,0) | (2,0)
(1,1) | (2,1)
(1,2) | (2,2)
(1,3) | (2,3)
(1,4) | (2,4)
(1,5) | (2,5)
(1,6) | (2,6)
(1,7) | (2,7)
(2,0) | (3,0)
(2,1) | (3,1)
(2,2) | (3,2)
(2,3) | (3,3)
(2,4) | (3,4)
(2,5) | (3,5)
(2,6) | (3,6)
(2,7) | (3,7)
(3,0) | (4,0)
(3,1) | (4,1)
(3,2) | (4,2)
(3,3) | (4,3)
(3,4) | (4,4)
(3,5) | (4,5)
```


#### &r38, assignment 3 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_V)}
- rows per train example: [35, 35, 63]; test: 98

Train example 0: 35 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
. 1 1 1 1 1
```
```
c0 | c1
(0,0) | (1,5)
(0,1) | (0,0)
(0,2) | (0,1)
(0,3) | (0,2)
(0,4) | (0,3)
(0,5) | (0,4)
(1,0) | (2,5)
(1,1) | (1,0)
(1,2) | (1,1)
(1,3) | (1,2)
(1,4) | (1,3)
(1,5) | (1,4)
(2,0) | (3,5)
(2,1) | (2,0)
(2,2) | (2,1)
(2,3) | (2,2)
(2,4) | (2,3)
(2,5) | (2,4)
(3,0) | (4,5)
(3,1) | (3,0)
(3,2) | (3,1)
(3,3) | (3,2)
(3,4) | (3,3)
(3,5) | (3,4)
(4,0) | (5,5)
(4,1) | (4,0)
(4,2) | (4,1)
(4,3) | (4,2)
(4,4) | (4,3)
(4,5) | (4,4)
```

Train example 1: 35 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
. 1 1 1 1 1
```
```
c0 | c1
(0,0) | (1,5)
(0,1) | (0,0)
(0,2) | (0,1)
(0,3) | (0,2)
(0,4) | (0,3)
(0,5) | (0,4)
(1,0) | (2,5)
(1,1) | (1,0)
(1,2) | (1,1)
(1,3) | (1,2)
(1,4) | (1,3)
(1,5) | (1,4)
(2,0) | (3,5)
(2,1) | (2,0)
(2,2) | (2,1)
(2,3) | (2,2)
(2,4) | (2,3)
(2,5) | (2,4)
(3,0) | (4,5)
(3,1) | (3,0)
(3,2) | (3,1)
(3,3) | (3,2)
(3,4) | (3,3)
(3,5) | (3,4)
(4,0) | (5,5)
(4,1) | (4,0)
(4,2) | (4,1)
(4,3) | (4,2)
(4,4) | (4,3)
(4,5) | (4,4)
```

Train example 2: 63 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
. 1 1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (1,7)
(0,1) | (0,0)
(0,2) | (0,1)
(0,3) | (0,2)
(0,4) | (0,3)
(0,5) | (0,4)
(0,6) | (0,5)
(0,7) | (0,6)
(1,0) | (2,7)
(1,1) | (1,0)
(1,2) | (1,1)
(1,3) | (1,2)
(1,4) | (1,3)
(1,5) | (1,4)
(1,6) | (1,5)
(1,7) | (1,6)
(2,0) | (3,7)
(2,1) | (2,0)
(2,2) | (2,1)
(2,3) | (2,2)
(2,4) | (2,3)
(2,5) | (2,4)
(2,6) | (2,5)
(2,7) | (2,6)
(3,0) | (4,7)
(3,1) | (3,0)
(3,2) | (3,1)
(3,3) | (3,2)
(3,4) | (3,3)
(3,5) | (3,4)
```


#### &r38, assignment 4 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_H)}
- rows per train example: [35, 35, 63]; test: 98

Train example 0: 35 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
. 1 1 1 1 1
```
```
c0 | c1
(0,0) | (1,0)
(0,1) | (1,1)
(0,2) | (1,2)
(0,3) | (1,3)
(0,4) | (1,4)
(0,5) | (1,5)
(1,0) | (2,0)
(1,1) | (2,1)
(1,2) | (2,2)
(1,3) | (2,3)
(1,4) | (2,4)
(1,5) | (2,5)
(2,0) | (3,0)
(2,1) | (3,1)
(2,2) | (3,2)
(2,3) | (3,3)
(2,4) | (3,4)
(2,5) | (3,5)
(3,0) | (4,0)
(3,1) | (4,1)
(3,2) | (4,2)
(3,3) | (4,3)
(3,4) | (4,4)
(3,5) | (4,5)
(4,0) | (5,0)
(4,1) | (5,1)
(4,2) | (5,2)
(4,3) | (5,3)
(4,4) | (5,4)
(4,5) | (5,5)
```

Train example 1: 35 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
. 1 1 1 1 1
```
```
c0 | c1
(0,0) | (1,0)
(0,1) | (1,1)
(0,2) | (1,2)
(0,3) | (1,3)
(0,4) | (1,4)
(0,5) | (1,5)
(1,0) | (2,0)
(1,1) | (2,1)
(1,2) | (2,2)
(1,3) | (2,3)
(1,4) | (2,4)
(1,5) | (2,5)
(2,0) | (3,0)
(2,1) | (3,1)
(2,2) | (3,2)
(2,3) | (3,3)
(2,4) | (3,4)
(2,5) | (3,5)
(3,0) | (4,0)
(3,1) | (4,1)
(3,2) | (4,2)
(3,3) | (4,3)
(3,4) | (4,4)
(3,5) | (4,5)
(4,0) | (5,0)
(4,1) | (5,1)
(4,2) | (5,2)
(4,3) | (5,3)
(4,4) | (5,4)
(4,5) | (5,5)
```

Train example 2: 63 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
. 1 1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (1,0)
(0,1) | (1,1)
(0,2) | (1,2)
(0,3) | (1,3)
(0,4) | (1,4)
(0,5) | (1,5)
(0,6) | (1,6)
(0,7) | (1,7)
(1,0) | (2,0)
(1,1) | (2,1)
(1,2) | (2,2)
(1,3) | (2,3)
(1,4) | (2,4)
(1,5) | (2,5)
(1,6) | (2,6)
(1,7) | (2,7)
(2,0) | (3,0)
(2,1) | (3,1)
(2,2) | (3,2)
(2,3) | (3,3)
(2,4) | (3,4)
(2,5) | (3,5)
(2,6) | (3,6)
(2,7) | (3,7)
(3,0) | (4,0)
(3,1) | (4,1)
(3,2) | (4,2)
(3,3) | (4,3)
(3,4) | (4,4)
(3,5) | (4,5)
```


#### &r38, assignment 5 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_V)}
- rows per train example: [35, 35, 63]; test: 98

Train example 0: 35 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 .
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (0,1)
(0,1) | (0,2)
(0,2) | (0,3)
(0,3) | (0,4)
(0,4) | (0,5)
(1,0) | (1,1)
(1,1) | (1,2)
(1,2) | (1,3)
(1,3) | (1,4)
(1,4) | (1,5)
(1,5) | (0,0)
(2,0) | (2,1)
(2,1) | (2,2)
(2,2) | (2,3)
(2,3) | (2,4)
(2,4) | (2,5)
(2,5) | (1,0)
(3,0) | (3,1)
(3,1) | (3,2)
(3,2) | (3,3)
(3,3) | (3,4)
(3,4) | (3,5)
(3,5) | (2,0)
(4,0) | (4,1)
(4,1) | (4,2)
(4,2) | (4,3)
(4,3) | (4,4)
(4,4) | (4,5)
(4,5) | (3,0)
(5,0) | (5,1)
```

Train example 1: 35 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 .
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (0,1)
(0,1) | (0,2)
(0,2) | (0,3)
(0,3) | (0,4)
(0,4) | (0,5)
(1,0) | (1,1)
(1,1) | (1,2)
(1,2) | (1,3)
(1,3) | (1,4)
(1,4) | (1,5)
(1,5) | (0,0)
(2,0) | (2,1)
(2,1) | (2,2)
(2,2) | (2,3)
(2,3) | (2,4)
(2,4) | (2,5)
(2,5) | (1,0)
(3,0) | (3,1)
(3,1) | (3,2)
(3,2) | (3,3)
(3,3) | (3,4)
(3,4) | (3,5)
(3,5) | (2,0)
(4,0) | (4,1)
(4,1) | (4,2)
(4,2) | (4,3)
(4,3) | (4,4)
(4,4) | (4,5)
(4,5) | (3,0)
(5,0) | (5,1)
```

Train example 2: 63 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 .
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (0,1)
(0,1) | (0,2)
(0,2) | (0,3)
(0,3) | (0,4)
(0,4) | (0,5)
(0,5) | (0,6)
(0,6) | (0,7)
(1,0) | (1,1)
(1,1) | (1,2)
(1,2) | (1,3)
(1,3) | (1,4)
(1,4) | (1,5)
(1,5) | (1,6)
(1,6) | (1,7)
(1,7) | (0,0)
(2,0) | (2,1)
(2,1) | (2,2)
(2,2) | (2,3)
(2,3) | (2,4)
(2,4) | (2,5)
(2,5) | (2,6)
(2,6) | (2,7)
(2,7) | (1,0)
(3,0) | (3,1)
(3,1) | (3,2)
(3,2) | (3,3)
(3,3) | (3,4)
(3,4) | (3,5)
(3,5) | (3,6)
(3,6) | (3,7)
```


#### &r38, assignment 6 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_H)}
- rows per train example: [35, 35, 63]; test: 98

Train example 0: 35 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 .
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (5,1)
(0,1) | (5,2)
(0,2) | (5,3)
(0,3) | (5,4)
(0,4) | (5,5)
(1,0) | (0,0)
(1,1) | (0,1)
(1,2) | (0,2)
(1,3) | (0,3)
(1,4) | (0,4)
(1,5) | (0,5)
(2,0) | (1,0)
(2,1) | (1,1)
(2,2) | (1,2)
(2,3) | (1,3)
(2,4) | (1,4)
(2,5) | (1,5)
(3,0) | (2,0)
(3,1) | (2,1)
(3,2) | (2,2)
(3,3) | (2,3)
(3,4) | (2,4)
(3,5) | (2,5)
(4,0) | (3,0)
(4,1) | (3,1)
(4,2) | (3,2)
(4,3) | (3,3)
(4,4) | (3,4)
(4,5) | (3,5)
(5,0) | (4,0)
```

Train example 1: 35 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 .
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (5,1)
(0,1) | (5,2)
(0,2) | (5,3)
(0,3) | (5,4)
(0,4) | (5,5)
(1,0) | (0,0)
(1,1) | (0,1)
(1,2) | (0,2)
(1,3) | (0,3)
(1,4) | (0,4)
(1,5) | (0,5)
(2,0) | (1,0)
(2,1) | (1,1)
(2,2) | (1,2)
(2,3) | (1,3)
(2,4) | (1,4)
(2,5) | (1,5)
(3,0) | (2,0)
(3,1) | (2,1)
(3,2) | (2,2)
(3,3) | (2,3)
(3,4) | (2,4)
(3,5) | (2,5)
(4,0) | (3,0)
(4,1) | (3,1)
(4,2) | (3,2)
(4,3) | (3,3)
(4,4) | (3,4)
(4,5) | (3,5)
(5,0) | (4,0)
```

Train example 2: 63 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 .
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (7,1)
(0,1) | (7,2)
(0,2) | (7,3)
(0,3) | (7,4)
(0,4) | (7,5)
(0,5) | (7,6)
(0,6) | (7,7)
(1,0) | (0,0)
(1,1) | (0,1)
(1,2) | (0,2)
(1,3) | (0,3)
(1,4) | (0,4)
(1,5) | (0,5)
(1,6) | (0,6)
(1,7) | (0,7)
(2,0) | (1,0)
(2,1) | (1,1)
(2,2) | (1,2)
(2,3) | (1,3)
(2,4) | (1,4)
(2,5) | (1,5)
(2,6) | (1,6)
(2,7) | (1,7)
(3,0) | (2,0)
(3,1) | (2,1)
(3,2) | (2,2)
(3,3) | (2,3)
(3,4) | (2,4)
(3,5) | (2,5)
(3,6) | (2,6)
```


#### &r38, assignment 7 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_V)}
- rows per train example: [35, 35, 63]; test: 98

Train example 0: 35 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,1) | (0,0)
(0,2) | (0,1)
(0,3) | (0,2)
(0,4) | (0,3)
(0,5) | (0,4)
(1,0) | (0,5)
(1,1) | (1,0)
(1,2) | (1,1)
(1,3) | (1,2)
(1,4) | (1,3)
(1,5) | (1,4)
(2,0) | (1,5)
(2,1) | (2,0)
(2,2) | (2,1)
(2,3) | (2,2)
(2,4) | (2,3)
(2,5) | (2,4)
(3,0) | (2,5)
(3,1) | (3,0)
(3,2) | (3,1)
(3,3) | (3,2)
(3,4) | (3,3)
(3,5) | (3,4)
(4,0) | (3,5)
(4,1) | (4,0)
(4,2) | (4,1)
(4,3) | (4,2)
(4,4) | (4,3)
(4,5) | (4,4)
(5,0) | (4,5)
```

Train example 1: 35 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,1) | (0,0)
(0,2) | (0,1)
(0,3) | (0,2)
(0,4) | (0,3)
(0,5) | (0,4)
(1,0) | (0,5)
(1,1) | (1,0)
(1,2) | (1,1)
(1,3) | (1,2)
(1,4) | (1,3)
(1,5) | (1,4)
(2,0) | (1,5)
(2,1) | (2,0)
(2,2) | (2,1)
(2,3) | (2,2)
(2,4) | (2,3)
(2,5) | (2,4)
(3,0) | (2,5)
(3,1) | (3,0)
(3,2) | (3,1)
(3,3) | (3,2)
(3,4) | (3,3)
(3,5) | (3,4)
(4,0) | (3,5)
(4,1) | (4,0)
(4,2) | (4,1)
(4,3) | (4,2)
(4,4) | (4,3)
(4,5) | (4,4)
(5,0) | (4,5)
```

Train example 2: 63 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
```
```
c0 | c1
(0,1) | (0,0)
(0,2) | (0,1)
(0,3) | (0,2)
(0,4) | (0,3)
(0,5) | (0,4)
(0,6) | (0,5)
(0,7) | (0,6)
(1,0) | (0,7)
(1,1) | (1,0)
(1,2) | (1,1)
(1,3) | (1,2)
(1,4) | (1,3)
(1,5) | (1,4)
(1,6) | (1,5)
(1,7) | (1,6)
(2,0) | (1,7)
(2,1) | (2,0)
(2,2) | (2,1)
(2,3) | (2,2)
(2,4) | (2,3)
(2,5) | (2,4)
(2,6) | (2,5)
(2,7) | (2,6)
(3,0) | (2,7)
(3,1) | (3,0)
(3,2) | (3,1)
(3,3) | (3,2)
(3,4) | (3,3)
(3,5) | (3,4)
(3,6) | (3,5)
```


#### &r38, assignment 8 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_H)}
- rows per train example: [35, 35, 63]; test: 98

Train example 0: 35 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,1) | (5,0)
(0,2) | (5,1)
(0,3) | (5,2)
(0,4) | (5,3)
(0,5) | (5,4)
(1,0) | (0,0)
(1,1) | (0,1)
(1,2) | (0,2)
(1,3) | (0,3)
(1,4) | (0,4)
(1,5) | (0,5)
(2,0) | (1,0)
(2,1) | (1,1)
(2,2) | (1,2)
(2,3) | (1,3)
(2,4) | (1,4)
(2,5) | (1,5)
(3,0) | (2,0)
(3,1) | (2,1)
(3,2) | (2,2)
(3,3) | (2,3)
(3,4) | (2,4)
(3,5) | (2,5)
(4,0) | (3,0)
(4,1) | (3,1)
(4,2) | (3,2)
(4,3) | (3,3)
(4,4) | (3,4)
(4,5) | (3,5)
(5,0) | (4,0)
```

Train example 1: 35 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,1) | (5,0)
(0,2) | (5,1)
(0,3) | (5,2)
(0,4) | (5,3)
(0,5) | (5,4)
(1,0) | (0,0)
(1,1) | (0,1)
(1,2) | (0,2)
(1,3) | (0,3)
(1,4) | (0,4)
(1,5) | (0,5)
(2,0) | (1,0)
(2,1) | (1,1)
(2,2) | (1,2)
(2,3) | (1,3)
(2,4) | (1,4)
(2,5) | (1,5)
(3,0) | (2,0)
(3,1) | (2,1)
(3,2) | (2,2)
(3,3) | (2,3)
(3,4) | (2,4)
(3,5) | (2,5)
(4,0) | (3,0)
(4,1) | (3,1)
(4,2) | (3,2)
(4,3) | (3,3)
(4,4) | (3,4)
(4,5) | (3,5)
(5,0) | (4,0)
```

Train example 2: 63 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
```
```
c0 | c1
(0,1) | (7,0)
(0,2) | (7,1)
(0,3) | (7,2)
(0,4) | (7,3)
(0,5) | (7,4)
(0,6) | (7,5)
(0,7) | (7,6)
(1,0) | (0,0)
(1,1) | (0,1)
(1,2) | (0,2)
(1,3) | (0,3)
(1,4) | (0,4)
(1,5) | (0,5)
(1,6) | (0,6)
(1,7) | (0,7)
(2,0) | (1,0)
(2,1) | (1,1)
(2,2) | (1,2)
(2,3) | (1,3)
(2,4) | (1,4)
(2,5) | (1,5)
(2,6) | (1,6)
(2,7) | (1,7)
(3,0) | (2,0)
(3,1) | (2,1)
(3,2) | (2,2)
(3,3) | (2,3)
(3,4) | (2,4)
(3,5) | (2,5)
(3,6) | (2,6)
```

### &r39 (export table 26)

- columns: c0: Box, c1: Box
- depth 3, candidate keys none
- DETs its entries are assigned: &r9; assignments: 8

#### &r39, assignment 1 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (0,1)
(0,1) | (0,2)
(0,2) | (0,3)
(0,3) | (0,4)
(0,4) | (0,5)
(0,5) | (1,0)
(1,0) | (1,1)
(1,1) | (1,2)
(1,2) | (1,3)
(1,3) | (1,4)
(1,4) | (1,5)
(1,5) | (2,0)
(2,0) | (2,1)
(2,1) | (2,2)
(2,2) | (2,3)
(2,3) | (2,4)
(2,4) | (2,5)
(2,5) | (3,0)
(3,0) | (3,1)
(3,1) | (3,2)
(3,2) | (3,3)
(3,3) | (3,4)
(3,4) | (3,5)
(3,5) | (4,0)
(4,0) | (4,1)
(4,1) | (4,2)
(4,2) | (4,3)
(4,3) | (4,4)
(4,4) | (4,5)
(4,5) | (5,0)
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (0,1)
(0,1) | (0,2)
(0,2) | (0,3)
(0,3) | (0,4)
(0,4) | (0,5)
(0,5) | (1,0)
(1,0) | (1,1)
(1,1) | (1,2)
(1,2) | (1,3)
(1,3) | (1,4)
(1,4) | (1,5)
(1,5) | (2,0)
(2,0) | (2,1)
(2,1) | (2,2)
(2,2) | (2,3)
(2,3) | (2,4)
(2,4) | (2,5)
(2,5) | (3,0)
(3,0) | (3,1)
(3,1) | (3,2)
(3,2) | (3,3)
(3,3) | (3,4)
(3,4) | (3,5)
(3,5) | (4,0)
(4,0) | (4,1)
(4,1) | (4,2)
(4,2) | (4,3)
(4,3) | (4,4)
(4,4) | (4,5)
(4,5) | (5,0)
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (0,1)
(0,1) | (0,2)
(0,2) | (0,3)
(0,3) | (0,4)
(0,4) | (0,5)
(0,5) | (0,6)
(0,6) | (0,7)
(0,7) | (1,0)
(1,0) | (1,1)
(1,1) | (1,2)
(1,2) | (1,3)
(1,3) | (1,4)
(1,4) | (1,5)
(1,5) | (1,6)
(1,6) | (1,7)
(1,7) | (2,0)
(2,0) | (2,1)
(2,1) | (2,2)
(2,2) | (2,3)
(2,3) | (2,4)
(2,4) | (2,5)
(2,5) | (2,6)
(2,6) | (2,7)
(2,7) | (3,0)
(3,0) | (3,1)
(3,1) | (3,2)
(3,2) | (3,3)
(3,3) | (3,4)
(3,4) | (3,5)
(3,5) | (3,6)
```


#### &r39, assignment 2 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_H)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (1,0)
(0,1) | (1,1)
(0,2) | (1,2)
(0,3) | (1,3)
(0,4) | (1,4)
(0,5) | (1,5)
(1,0) | (2,0)
(1,1) | (2,1)
(1,2) | (2,2)
(1,3) | (2,3)
(1,4) | (2,4)
(1,5) | (2,5)
(2,0) | (3,0)
(2,1) | (3,1)
(2,2) | (3,2)
(2,3) | (3,3)
(2,4) | (3,4)
(2,5) | (3,5)
(3,0) | (4,0)
(3,1) | (4,1)
(3,2) | (4,2)
(3,3) | (4,3)
(3,4) | (4,4)
(3,5) | (4,5)
(4,0) | (5,0)
(4,1) | (5,1)
(4,2) | (5,2)
(4,3) | (5,3)
(4,4) | (5,4)
(4,5) | (5,5)
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (1,0)
(0,1) | (1,1)
(0,2) | (1,2)
(0,3) | (1,3)
(0,4) | (1,4)
(0,5) | (1,5)
(1,0) | (2,0)
(1,1) | (2,1)
(1,2) | (2,2)
(1,3) | (2,3)
(1,4) | (2,4)
(1,5) | (2,5)
(2,0) | (3,0)
(2,1) | (3,1)
(2,2) | (3,2)
(2,3) | (3,3)
(2,4) | (3,4)
(2,5) | (3,5)
(3,0) | (4,0)
(3,1) | (4,1)
(3,2) | (4,2)
(3,3) | (4,3)
(3,4) | (4,4)
(3,5) | (4,5)
(4,0) | (5,0)
(4,1) | (5,1)
(4,2) | (5,2)
(4,3) | (5,3)
(4,4) | (5,4)
(4,5) | (5,5)
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (1,0)
(0,1) | (1,1)
(0,2) | (1,2)
(0,3) | (1,3)
(0,4) | (1,4)
(0,5) | (1,5)
(0,6) | (1,6)
(0,7) | (1,7)
(1,0) | (2,0)
(1,1) | (2,1)
(1,2) | (2,2)
(1,3) | (2,3)
(1,4) | (2,4)
(1,5) | (2,5)
(1,6) | (2,6)
(1,7) | (2,7)
(2,0) | (3,0)
(2,1) | (3,1)
(2,2) | (3,2)
(2,3) | (3,3)
(2,4) | (3,4)
(2,5) | (3,5)
(2,6) | (3,6)
(2,7) | (3,7)
(3,0) | (4,0)
(3,1) | (4,1)
(3,2) | (4,2)
(3,3) | (4,3)
(3,4) | (4,4)
(3,5) | (4,5)
```


#### &r39, assignment 3 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (1,5)
(0,1) | (0,0)
(0,2) | (0,1)
(0,3) | (0,2)
(0,4) | (0,3)
(0,5) | (0,4)
(1,0) | (2,5)
(1,1) | (1,0)
(1,2) | (1,1)
(1,3) | (1,2)
(1,4) | (1,3)
(1,5) | (1,4)
(2,0) | (3,5)
(2,1) | (2,0)
(2,2) | (2,1)
(2,3) | (2,2)
(2,4) | (2,3)
(2,5) | (2,4)
(3,0) | (4,5)
(3,1) | (3,0)
(3,2) | (3,1)
(3,3) | (3,2)
(3,4) | (3,3)
(3,5) | (3,4)
(4,0) | (5,5)
(4,1) | (4,0)
(4,2) | (4,1)
(4,3) | (4,2)
(4,4) | (4,3)
(4,5) | (4,4)
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (1,5)
(0,1) | (0,0)
(0,2) | (0,1)
(0,3) | (0,2)
(0,4) | (0,3)
(0,5) | (0,4)
(1,0) | (2,5)
(1,1) | (1,0)
(1,2) | (1,1)
(1,3) | (1,2)
(1,4) | (1,3)
(1,5) | (1,4)
(2,0) | (3,5)
(2,1) | (2,0)
(2,2) | (2,1)
(2,3) | (2,2)
(2,4) | (2,3)
(2,5) | (2,4)
(3,0) | (4,5)
(3,1) | (3,0)
(3,2) | (3,1)
(3,3) | (3,2)
(3,4) | (3,3)
(3,5) | (3,4)
(4,0) | (5,5)
(4,1) | (4,0)
(4,2) | (4,1)
(4,3) | (4,2)
(4,4) | (4,3)
(4,5) | (4,4)
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (1,7)
(0,1) | (0,0)
(0,2) | (0,1)
(0,3) | (0,2)
(0,4) | (0,3)
(0,5) | (0,4)
(0,6) | (0,5)
(0,7) | (0,6)
(1,0) | (2,7)
(1,1) | (1,0)
(1,2) | (1,1)
(1,3) | (1,2)
(1,4) | (1,3)
(1,5) | (1,4)
(1,6) | (1,5)
(1,7) | (1,6)
(2,0) | (3,7)
(2,1) | (2,0)
(2,2) | (2,1)
(2,3) | (2,2)
(2,4) | (2,3)
(2,5) | (2,4)
(2,6) | (2,5)
(2,7) | (2,6)
(3,0) | (4,7)
(3,1) | (3,0)
(3,2) | (3,1)
(3,3) | (3,2)
(3,4) | (3,3)
(3,5) | (3,4)
```


#### &r39, assignment 4 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_H)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (1,0)
(0,1) | (1,1)
(0,2) | (1,2)
(0,3) | (1,3)
(0,4) | (1,4)
(0,5) | (1,5)
(1,0) | (2,0)
(1,1) | (2,1)
(1,2) | (2,2)
(1,3) | (2,3)
(1,4) | (2,4)
(1,5) | (2,5)
(2,0) | (3,0)
(2,1) | (3,1)
(2,2) | (3,2)
(2,3) | (3,3)
(2,4) | (3,4)
(2,5) | (3,5)
(3,0) | (4,0)
(3,1) | (4,1)
(3,2) | (4,2)
(3,3) | (4,3)
(3,4) | (4,4)
(3,5) | (4,5)
(4,0) | (5,0)
(4,1) | (5,1)
(4,2) | (5,2)
(4,3) | (5,3)
(4,4) | (5,4)
(4,5) | (5,5)
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (1,0)
(0,1) | (1,1)
(0,2) | (1,2)
(0,3) | (1,3)
(0,4) | (1,4)
(0,5) | (1,5)
(1,0) | (2,0)
(1,1) | (2,1)
(1,2) | (2,2)
(1,3) | (2,3)
(1,4) | (2,4)
(1,5) | (2,5)
(2,0) | (3,0)
(2,1) | (3,1)
(2,2) | (3,2)
(2,3) | (3,3)
(2,4) | (3,4)
(2,5) | (3,5)
(3,0) | (4,0)
(3,1) | (4,1)
(3,2) | (4,2)
(3,3) | (4,3)
(3,4) | (4,4)
(3,5) | (4,5)
(4,0) | (5,0)
(4,1) | (5,1)
(4,2) | (5,2)
(4,3) | (5,3)
(4,4) | (5,4)
(4,5) | (5,5)
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (1,0)
(0,1) | (1,1)
(0,2) | (1,2)
(0,3) | (1,3)
(0,4) | (1,4)
(0,5) | (1,5)
(0,6) | (1,6)
(0,7) | (1,7)
(1,0) | (2,0)
(1,1) | (2,1)
(1,2) | (2,2)
(1,3) | (2,3)
(1,4) | (2,4)
(1,5) | (2,5)
(1,6) | (2,6)
(1,7) | (2,7)
(2,0) | (3,0)
(2,1) | (3,1)
(2,2) | (3,2)
(2,3) | (3,3)
(2,4) | (3,4)
(2,5) | (3,5)
(2,6) | (3,6)
(2,7) | (3,7)
(3,0) | (4,0)
(3,1) | (4,1)
(3,2) | (4,2)
(3,3) | (4,3)
(3,4) | (4,4)
(3,5) | (4,5)
```


#### &r39, assignment 5 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (0,1)
(0,1) | (0,2)
(0,2) | (0,3)
(0,3) | (0,4)
(0,4) | (0,5)
(0,5) | (5,0)
(1,0) | (1,1)
(1,1) | (1,2)
(1,2) | (1,3)
(1,3) | (1,4)
(1,4) | (1,5)
(1,5) | (0,0)
(2,0) | (2,1)
(2,1) | (2,2)
(2,2) | (2,3)
(2,3) | (2,4)
(2,4) | (2,5)
(2,5) | (1,0)
(3,0) | (3,1)
(3,1) | (3,2)
(3,2) | (3,3)
(3,3) | (3,4)
(3,4) | (3,5)
(3,5) | (2,0)
(4,0) | (4,1)
(4,1) | (4,2)
(4,2) | (4,3)
(4,3) | (4,4)
(4,4) | (4,5)
(4,5) | (3,0)
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (0,1)
(0,1) | (0,2)
(0,2) | (0,3)
(0,3) | (0,4)
(0,4) | (0,5)
(0,5) | (5,0)
(1,0) | (1,1)
(1,1) | (1,2)
(1,2) | (1,3)
(1,3) | (1,4)
(1,4) | (1,5)
(1,5) | (0,0)
(2,0) | (2,1)
(2,1) | (2,2)
(2,2) | (2,3)
(2,3) | (2,4)
(2,4) | (2,5)
(2,5) | (1,0)
(3,0) | (3,1)
(3,1) | (3,2)
(3,2) | (3,3)
(3,3) | (3,4)
(3,4) | (3,5)
(3,5) | (2,0)
(4,0) | (4,1)
(4,1) | (4,2)
(4,2) | (4,3)
(4,3) | (4,4)
(4,4) | (4,5)
(4,5) | (3,0)
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (0,1)
(0,1) | (0,2)
(0,2) | (0,3)
(0,3) | (0,4)
(0,4) | (0,5)
(0,5) | (0,6)
(0,6) | (0,7)
(0,7) | (7,0)
(1,0) | (1,1)
(1,1) | (1,2)
(1,2) | (1,3)
(1,3) | (1,4)
(1,4) | (1,5)
(1,5) | (1,6)
(1,6) | (1,7)
(1,7) | (0,0)
(2,0) | (2,1)
(2,1) | (2,2)
(2,2) | (2,3)
(2,3) | (2,4)
(2,4) | (2,5)
(2,5) | (2,6)
(2,6) | (2,7)
(2,7) | (1,0)
(3,0) | (3,1)
(3,1) | (3,2)
(3,2) | (3,3)
(3,3) | (3,4)
(3,4) | (3,5)
(3,5) | (3,6)
```


#### &r39, assignment 6 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_H)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (5,1)
(0,1) | (5,2)
(0,2) | (5,3)
(0,3) | (5,4)
(0,4) | (5,5)
(0,5) | (5,0)
(1,0) | (0,0)
(1,1) | (0,1)
(1,2) | (0,2)
(1,3) | (0,3)
(1,4) | (0,4)
(1,5) | (0,5)
(2,0) | (1,0)
(2,1) | (1,1)
(2,2) | (1,2)
(2,3) | (1,3)
(2,4) | (1,4)
(2,5) | (1,5)
(3,0) | (2,0)
(3,1) | (2,1)
(3,2) | (2,2)
(3,3) | (2,3)
(3,4) | (2,4)
(3,5) | (2,5)
(4,0) | (3,0)
(4,1) | (3,1)
(4,2) | (3,2)
(4,3) | (3,3)
(4,4) | (3,4)
(4,5) | (3,5)
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (5,1)
(0,1) | (5,2)
(0,2) | (5,3)
(0,3) | (5,4)
(0,4) | (5,5)
(0,5) | (5,0)
(1,0) | (0,0)
(1,1) | (0,1)
(1,2) | (0,2)
(1,3) | (0,3)
(1,4) | (0,4)
(1,5) | (0,5)
(2,0) | (1,0)
(2,1) | (1,1)
(2,2) | (1,2)
(2,3) | (1,3)
(2,4) | (1,4)
(2,5) | (1,5)
(3,0) | (2,0)
(3,1) | (2,1)
(3,2) | (2,2)
(3,3) | (2,3)
(3,4) | (2,4)
(3,5) | (2,5)
(4,0) | (3,0)
(4,1) | (3,1)
(4,2) | (3,2)
(4,3) | (3,3)
(4,4) | (3,4)
(4,5) | (3,5)
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (7,1)
(0,1) | (7,2)
(0,2) | (7,3)
(0,3) | (7,4)
(0,4) | (7,5)
(0,5) | (7,6)
(0,6) | (7,7)
(0,7) | (7,0)
(1,0) | (0,0)
(1,1) | (0,1)
(1,2) | (0,2)
(1,3) | (0,3)
(1,4) | (0,4)
(1,5) | (0,5)
(1,6) | (0,6)
(1,7) | (0,7)
(2,0) | (1,0)
(2,1) | (1,1)
(2,2) | (1,2)
(2,3) | (1,3)
(2,4) | (1,4)
(2,5) | (1,5)
(2,6) | (1,6)
(2,7) | (1,7)
(3,0) | (2,0)
(3,1) | (2,1)
(3,2) | (2,2)
(3,3) | (2,3)
(3,4) | (2,4)
(3,5) | (2,5)
```


#### &r39, assignment 7 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (5,5)
(0,1) | (0,0)
(0,2) | (0,1)
(0,3) | (0,2)
(0,4) | (0,3)
(0,5) | (0,4)
(1,0) | (0,5)
(1,1) | (1,0)
(1,2) | (1,1)
(1,3) | (1,2)
(1,4) | (1,3)
(1,5) | (1,4)
(2,0) | (1,5)
(2,1) | (2,0)
(2,2) | (2,1)
(2,3) | (2,2)
(2,4) | (2,3)
(2,5) | (2,4)
(3,0) | (2,5)
(3,1) | (3,0)
(3,2) | (3,1)
(3,3) | (3,2)
(3,4) | (3,3)
(3,5) | (3,4)
(4,0) | (3,5)
(4,1) | (4,0)
(4,2) | (4,1)
(4,3) | (4,2)
(4,4) | (4,3)
(4,5) | (4,4)
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (5,5)
(0,1) | (0,0)
(0,2) | (0,1)
(0,3) | (0,2)
(0,4) | (0,3)
(0,5) | (0,4)
(1,0) | (0,5)
(1,1) | (1,0)
(1,2) | (1,1)
(1,3) | (1,2)
(1,4) | (1,3)
(1,5) | (1,4)
(2,0) | (1,5)
(2,1) | (2,0)
(2,2) | (2,1)
(2,3) | (2,2)
(2,4) | (2,3)
(2,5) | (2,4)
(3,0) | (2,5)
(3,1) | (3,0)
(3,2) | (3,1)
(3,3) | (3,2)
(3,4) | (3,3)
(3,5) | (3,4)
(4,0) | (3,5)
(4,1) | (4,0)
(4,2) | (4,1)
(4,3) | (4,2)
(4,4) | (4,3)
(4,5) | (4,4)
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (7,7)
(0,1) | (0,0)
(0,2) | (0,1)
(0,3) | (0,2)
(0,4) | (0,3)
(0,5) | (0,4)
(0,6) | (0,5)
(0,7) | (0,6)
(1,0) | (0,7)
(1,1) | (1,0)
(1,2) | (1,1)
(1,3) | (1,2)
(1,4) | (1,3)
(1,5) | (1,4)
(1,6) | (1,5)
(1,7) | (1,6)
(2,0) | (1,7)
(2,1) | (2,0)
(2,2) | (2,1)
(2,3) | (2,2)
(2,4) | (2,3)
(2,5) | (2,4)
(2,6) | (2,5)
(2,7) | (2,6)
(3,0) | (2,7)
(3,1) | (3,0)
(3,2) | (3,1)
(3,3) | (3,2)
(3,4) | (3,3)
(3,5) | (3,4)
```


#### &r39, assignment 8 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_H)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (5,5)
(0,1) | (5,0)
(0,2) | (5,1)
(0,3) | (5,2)
(0,4) | (5,3)
(0,5) | (5,4)
(1,0) | (0,0)
(1,1) | (0,1)
(1,2) | (0,2)
(1,3) | (0,3)
(1,4) | (0,4)
(1,5) | (0,5)
(2,0) | (1,0)
(2,1) | (1,1)
(2,2) | (1,2)
(2,3) | (1,3)
(2,4) | (1,4)
(2,5) | (1,5)
(3,0) | (2,0)
(3,1) | (2,1)
(3,2) | (2,2)
(3,3) | (2,3)
(3,4) | (2,4)
(3,5) | (2,5)
(4,0) | (3,0)
(4,1) | (3,1)
(4,2) | (3,2)
(4,3) | (3,3)
(4,4) | (3,4)
(4,5) | (3,5)
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (5,5)
(0,1) | (5,0)
(0,2) | (5,1)
(0,3) | (5,2)
(0,4) | (5,3)
(0,5) | (5,4)
(1,0) | (0,0)
(1,1) | (0,1)
(1,2) | (0,2)
(1,3) | (0,3)
(1,4) | (0,4)
(1,5) | (0,5)
(2,0) | (1,0)
(2,1) | (1,1)
(2,2) | (1,2)
(2,3) | (1,3)
(2,4) | (1,4)
(2,5) | (1,5)
(3,0) | (2,0)
(3,1) | (2,1)
(3,2) | (2,2)
(3,3) | (2,3)
(3,4) | (2,4)
(3,5) | (2,5)
(4,0) | (3,0)
(4,1) | (3,1)
(4,2) | (3,2)
(4,3) | (3,3)
(4,4) | (3,4)
(4,5) | (3,5)
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
```
```
c0 | c1
(0,0) | (7,7)
(0,1) | (7,0)
(0,2) | (7,1)
(0,3) | (7,2)
(0,4) | (7,3)
(0,5) | (7,4)
(0,6) | (7,5)
(0,7) | (7,6)
(1,0) | (0,0)
(1,1) | (0,1)
(1,2) | (0,2)
(1,3) | (0,3)
(1,4) | (0,4)
(1,5) | (0,5)
(1,6) | (0,6)
(1,7) | (0,7)
(2,0) | (1,0)
(2,1) | (1,1)
(2,2) | (1,2)
(2,3) | (1,3)
(2,4) | (1,4)
(2,5) | (1,5)
(2,6) | (1,6)
(2,7) | (1,7)
(3,0) | (2,0)
(3,1) | (2,1)
(3,2) | (2,2)
(3,3) | (2,3)
(3,4) | (2,4)
(3,5) | (2,5)
```

### &r40 (export table 27)

- columns: c0: Box
- depth 2, candidate keys none
- DETs its entries are assigned: &r9; assignments: 8

#### &r40, assignment 1 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0
(0,0)
(0,1)
(0,2)
(0,3)
(0,4)
(0,5)
(1,0)
(1,1)
(1,2)
(1,3)
(1,4)
(1,5)
(2,0)
(2,1)
(2,2)
(2,3)
(2,4)
(2,5)
(3,0)
(3,1)
(3,2)
(3,3)
(3,4)
(3,5)
(4,0)
(4,1)
(4,2)
(4,3)
(4,4)
(4,5)
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0
(0,0)
(0,1)
(0,2)
(0,3)
(0,4)
(0,5)
(1,0)
(1,1)
(1,2)
(1,3)
(1,4)
(1,5)
(2,0)
(2,1)
(2,2)
(2,3)
(2,4)
(2,5)
(3,0)
(3,1)
(3,2)
(3,3)
(3,4)
(3,5)
(4,0)
(4,1)
(4,2)
(4,3)
(4,4)
(4,5)
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
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
(1,0)
(1,1)
(1,2)
(1,3)
(1,4)
(1,5)
(1,6)
(1,7)
(2,0)
(2,1)
(2,2)
(2,3)
(2,4)
(2,5)
(2,6)
(2,7)
(3,0)
(3,1)
(3,2)
(3,3)
(3,4)
(3,5)
```


#### &r40, assignment 2 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r40, assignment 3 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r40, assignment 4 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r40, assignment 5 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r40, assignment 6 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r40, assignment 7 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r40, assignment 8 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_H)}
- rows equal to those of assignment 1 at every example
### &r41 (export table 28)

- columns: c0: Box, c1: Box
- depth 2, candidate keys none
- DETs its entries are assigned: &r9; assignments: 8

#### &r41, assignment 1 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_V)}
- rows per train example: [630, 630, 2016]; test: 2646

Train example 0: 630 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
+ + 9 8 7 6
5 4 3 2 1 .
```
```
c0 | c1
(0,0) | (0,1)
(0,0) | (0,2)
(0,0) | (0,3)
(0,0) | (0,4)
(0,0) | (0,5)
(0,0) | (1,0)
(0,0) | (1,1)
(0,0) | (1,2)
(0,0) | (1,3)
(0,0) | (1,4)
(0,0) | (1,5)
(0,0) | (2,0)
(0,0) | (2,1)
(0,0) | (2,2)
(0,0) | (2,3)
(0,0) | (2,4)
(0,0) | (2,5)
(0,0) | (3,0)
(0,0) | (3,1)
(0,0) | (3,2)
(0,0) | (3,3)
(0,0) | (3,4)
(0,0) | (3,5)
(0,0) | (4,0)
(0,0) | (4,1)
(0,0) | (4,2)
(0,0) | (4,3)
(0,0) | (4,4)
(0,0) | (4,5)
(0,0) | (5,0)
```

Train example 1: 630 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
+ + 9 8 7 6
5 4 3 2 1 .
```
```
c0 | c1
(0,0) | (0,1)
(0,0) | (0,2)
(0,0) | (0,3)
(0,0) | (0,4)
(0,0) | (0,5)
(0,0) | (1,0)
(0,0) | (1,1)
(0,0) | (1,2)
(0,0) | (1,3)
(0,0) | (1,4)
(0,0) | (1,5)
(0,0) | (2,0)
(0,0) | (2,1)
(0,0) | (2,2)
(0,0) | (2,3)
(0,0) | (2,4)
(0,0) | (2,5)
(0,0) | (3,0)
(0,0) | (3,1)
(0,0) | (3,2)
(0,0) | (3,3)
(0,0) | (3,4)
(0,0) | (3,5)
(0,0) | (4,0)
(0,0) | (4,1)
(0,0) | (4,2)
(0,0) | (4,3)
(0,0) | (4,4)
(0,0) | (4,5)
(0,0) | (5,0)
```

Train example 2: 2016 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + 9 8
7 6 5 4 3 2 1 .
```
```
c0 | c1
(0,0) | (0,1)
(0,0) | (0,2)
(0,0) | (0,3)
(0,0) | (0,4)
(0,0) | (0,5)
(0,0) | (0,6)
(0,0) | (0,7)
(0,0) | (1,0)
(0,0) | (1,1)
(0,0) | (1,2)
(0,0) | (1,3)
(0,0) | (1,4)
(0,0) | (1,5)
(0,0) | (1,6)
(0,0) | (1,7)
(0,0) | (2,0)
(0,0) | (2,1)
(0,0) | (2,2)
(0,0) | (2,3)
(0,0) | (2,4)
(0,0) | (2,5)
(0,0) | (2,6)
(0,0) | (2,7)
(0,0) | (3,0)
(0,0) | (3,1)
(0,0) | (3,2)
(0,0) | (3,3)
(0,0) | (3,4)
(0,0) | (3,5)
(0,0) | (3,6)
```


#### &r41, assignment 2 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_H)}
- rows per train example: [630, 630, 2016]; test: 2646

Train example 0: 630 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
+ + + + + 5
+ + + + + 4
+ + + + 9 3
+ + + + 8 2
+ + + + 7 1
+ + + + 6 .
```
```
c0 | c1
(0,0) | (0,1)
(0,0) | (0,2)
(0,0) | (0,3)
(0,0) | (0,4)
(0,0) | (0,5)
(0,0) | (1,0)
(0,0) | (1,1)
(0,0) | (1,2)
(0,0) | (1,3)
(0,0) | (1,4)
(0,0) | (1,5)
(0,0) | (2,0)
(0,0) | (2,1)
(0,0) | (2,2)
(0,0) | (2,3)
(0,0) | (2,4)
(0,0) | (2,5)
(0,0) | (3,0)
(0,0) | (3,1)
(0,0) | (3,2)
(0,0) | (3,3)
(0,0) | (3,4)
(0,0) | (3,5)
(0,0) | (4,0)
(0,0) | (4,1)
(0,0) | (4,2)
(0,0) | (4,3)
(0,0) | (4,4)
(0,0) | (4,5)
(0,0) | (5,0)
```

Train example 1: 630 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
+ + + + + 5
+ + + + + 4
+ + + + 9 3
+ + + + 8 2
+ + + + 7 1
+ + + + 6 .
```
```
c0 | c1
(0,0) | (0,1)
(0,0) | (0,2)
(0,0) | (0,3)
(0,0) | (0,4)
(0,0) | (0,5)
(0,0) | (1,0)
(0,0) | (1,1)
(0,0) | (1,2)
(0,0) | (1,3)
(0,0) | (1,4)
(0,0) | (1,5)
(0,0) | (2,0)
(0,0) | (2,1)
(0,0) | (2,2)
(0,0) | (2,3)
(0,0) | (2,4)
(0,0) | (2,5)
(0,0) | (3,0)
(0,0) | (3,1)
(0,0) | (3,2)
(0,0) | (3,3)
(0,0) | (3,4)
(0,0) | (3,5)
(0,0) | (4,0)
(0,0) | (4,1)
(0,0) | (4,2)
(0,0) | (4,3)
(0,0) | (4,4)
(0,0) | (4,5)
(0,0) | (5,0)
```

Train example 2: 2016 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
+ + + + + + + 7
+ + + + + + + 6
+ + + + + + + 5
+ + + + + + + 4
+ + + + + + + 3
+ + + + + + + 2
+ + + + + + 9 1
+ + + + + + 8 .
```
```
c0 | c1
(0,0) | (0,1)
(0,0) | (0,2)
(0,0) | (0,3)
(0,0) | (0,4)
(0,0) | (0,5)
(0,0) | (0,6)
(0,0) | (0,7)
(0,0) | (1,0)
(0,0) | (1,1)
(0,0) | (1,2)
(0,0) | (1,3)
(0,0) | (1,4)
(0,0) | (1,5)
(0,0) | (1,6)
(0,0) | (1,7)
(0,0) | (2,0)
(0,0) | (2,1)
(0,0) | (2,2)
(0,0) | (2,3)
(0,0) | (2,4)
(0,0) | (2,5)
(0,0) | (2,6)
(0,0) | (2,7)
(0,0) | (3,0)
(0,0) | (3,1)
(0,0) | (3,2)
(0,0) | (3,3)
(0,0) | (3,4)
(0,0) | (3,5)
(0,0) | (3,6)
```


#### &r41, assignment 3 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_V)}
- rows per train example: [630, 630, 2016]; test: 2646

Train example 0: 630 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
6 7 8 9 + +
. 1 2 3 4 5
```
```
c0 | c1
(0,0) | (1,0)
(0,0) | (1,1)
(0,0) | (1,2)
(0,0) | (1,3)
(0,0) | (1,4)
(0,0) | (1,5)
(0,0) | (2,0)
(0,0) | (2,1)
(0,0) | (2,2)
(0,0) | (2,3)
(0,0) | (2,4)
(0,0) | (2,5)
(0,0) | (3,0)
(0,0) | (3,1)
(0,0) | (3,2)
(0,0) | (3,3)
(0,0) | (3,4)
(0,0) | (3,5)
(0,0) | (4,0)
(0,0) | (4,1)
(0,0) | (4,2)
(0,0) | (4,3)
(0,0) | (4,4)
(0,0) | (4,5)
(0,0) | (5,0)
(0,0) | (5,1)
(0,0) | (5,2)
(0,0) | (5,3)
(0,0) | (5,4)
(0,0) | (5,5)
```

Train example 1: 630 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
6 7 8 9 + +
. 1 2 3 4 5
```
```
c0 | c1
(0,0) | (1,0)
(0,0) | (1,1)
(0,0) | (1,2)
(0,0) | (1,3)
(0,0) | (1,4)
(0,0) | (1,5)
(0,0) | (2,0)
(0,0) | (2,1)
(0,0) | (2,2)
(0,0) | (2,3)
(0,0) | (2,4)
(0,0) | (2,5)
(0,0) | (3,0)
(0,0) | (3,1)
(0,0) | (3,2)
(0,0) | (3,3)
(0,0) | (3,4)
(0,0) | (3,5)
(0,0) | (4,0)
(0,0) | (4,1)
(0,0) | (4,2)
(0,0) | (4,3)
(0,0) | (4,4)
(0,0) | (4,5)
(0,0) | (5,0)
(0,0) | (5,1)
(0,0) | (5,2)
(0,0) | (5,3)
(0,0) | (5,4)
(0,0) | (5,5)
```

Train example 2: 2016 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
8 9 + + + + + +
. 1 2 3 4 5 6 7
```
```
c0 | c1
(0,0) | (1,0)
(0,0) | (1,1)
(0,0) | (1,2)
(0,0) | (1,3)
(0,0) | (1,4)
(0,0) | (1,5)
(0,0) | (1,6)
(0,0) | (1,7)
(0,0) | (2,0)
(0,0) | (2,1)
(0,0) | (2,2)
(0,0) | (2,3)
(0,0) | (2,4)
(0,0) | (2,5)
(0,0) | (2,6)
(0,0) | (2,7)
(0,0) | (3,0)
(0,0) | (3,1)
(0,0) | (3,2)
(0,0) | (3,3)
(0,0) | (3,4)
(0,0) | (3,5)
(0,0) | (3,6)
(0,0) | (3,7)
(0,0) | (4,0)
(0,0) | (4,1)
(0,0) | (4,2)
(0,0) | (4,3)
(0,0) | (4,4)
(0,0) | (4,5)
```


#### &r41, assignment 4 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_H)}
- rows per train example: [630, 630, 2016]; test: 2646

Train example 0: 630 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
5 + + + + +
4 + + + + +
3 9 + + + +
2 8 + + + +
1 7 + + + +
. 6 + + + +
```
```
c0 | c1
(0,0) | (1,0)
(0,0) | (2,0)
(0,0) | (3,0)
(0,0) | (4,0)
(0,0) | (5,0)
(0,1) | (0,0)
(0,1) | (1,0)
(0,1) | (1,1)
(0,1) | (2,0)
(0,1) | (2,1)
(0,1) | (3,0)
(0,1) | (3,1)
(0,1) | (4,0)
(0,1) | (4,1)
(0,1) | (5,0)
(0,1) | (5,1)
(0,2) | (0,0)
(0,2) | (0,1)
(0,2) | (1,0)
(0,2) | (1,1)
(0,2) | (1,2)
(0,2) | (2,0)
(0,2) | (2,1)
(0,2) | (2,2)
(0,2) | (3,0)
(0,2) | (3,1)
(0,2) | (3,2)
(0,2) | (4,0)
(0,2) | (4,1)
(0,2) | (4,2)
```

Train example 1: 630 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
5 + + + + +
4 + + + + +
3 9 + + + +
2 8 + + + +
1 7 + + + +
. 6 + + + +
```
```
c0 | c1
(0,0) | (1,0)
(0,0) | (2,0)
(0,0) | (3,0)
(0,0) | (4,0)
(0,0) | (5,0)
(0,1) | (0,0)
(0,1) | (1,0)
(0,1) | (1,1)
(0,1) | (2,0)
(0,1) | (2,1)
(0,1) | (3,0)
(0,1) | (3,1)
(0,1) | (4,0)
(0,1) | (4,1)
(0,1) | (5,0)
(0,1) | (5,1)
(0,2) | (0,0)
(0,2) | (0,1)
(0,2) | (1,0)
(0,2) | (1,1)
(0,2) | (1,2)
(0,2) | (2,0)
(0,2) | (2,1)
(0,2) | (2,2)
(0,2) | (3,0)
(0,2) | (3,1)
(0,2) | (3,2)
(0,2) | (4,0)
(0,2) | (4,1)
(0,2) | (4,2)
```

Train example 2: 2016 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
7 + + + + + + +
6 + + + + + + +
5 + + + + + + +
4 + + + + + + +
3 + + + + + + +
2 + + + + + + +
1 9 + + + + + +
. 8 + + + + + +
```
```
c0 | c1
(0,0) | (1,0)
(0,0) | (2,0)
(0,0) | (3,0)
(0,0) | (4,0)
(0,0) | (5,0)
(0,0) | (6,0)
(0,0) | (7,0)
(0,1) | (0,0)
(0,1) | (1,0)
(0,1) | (1,1)
(0,1) | (2,0)
(0,1) | (2,1)
(0,1) | (3,0)
(0,1) | (3,1)
(0,1) | (4,0)
(0,1) | (4,1)
(0,1) | (5,0)
(0,1) | (5,1)
(0,1) | (6,0)
(0,1) | (6,1)
(0,1) | (7,0)
(0,1) | (7,1)
(0,2) | (0,0)
(0,2) | (0,1)
(0,2) | (1,0)
(0,2) | (1,1)
(0,2) | (1,2)
(0,2) | (2,0)
(0,2) | (2,1)
(0,2) | (2,2)
```


#### &r41, assignment 5 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_V)}
- rows per train example: [630, 630, 2016]; test: 2646

Train example 0: 630 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
5 4 3 2 1 .
+ + 9 8 7 6
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
```
```
c0 | c1
(0,0) | (0,1)
(0,0) | (0,2)
(0,0) | (0,3)
(0,0) | (0,4)
(0,0) | (0,5)
(0,1) | (0,2)
(0,1) | (0,3)
(0,1) | (0,4)
(0,1) | (0,5)
(0,2) | (0,3)
(0,2) | (0,4)
(0,2) | (0,5)
(0,3) | (0,4)
(0,3) | (0,5)
(0,4) | (0,5)
(1,0) | (0,0)
(1,0) | (0,1)
(1,0) | (0,2)
(1,0) | (0,3)
(1,0) | (0,4)
(1,0) | (0,5)
(1,0) | (1,1)
(1,0) | (1,2)
(1,0) | (1,3)
(1,0) | (1,4)
(1,0) | (1,5)
(1,1) | (0,0)
(1,1) | (0,1)
(1,1) | (0,2)
(1,1) | (0,3)
```

Train example 1: 630 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
5 4 3 2 1 .
+ + 9 8 7 6
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
```
```
c0 | c1
(0,0) | (0,1)
(0,0) | (0,2)
(0,0) | (0,3)
(0,0) | (0,4)
(0,0) | (0,5)
(0,1) | (0,2)
(0,1) | (0,3)
(0,1) | (0,4)
(0,1) | (0,5)
(0,2) | (0,3)
(0,2) | (0,4)
(0,2) | (0,5)
(0,3) | (0,4)
(0,3) | (0,5)
(0,4) | (0,5)
(1,0) | (0,0)
(1,0) | (0,1)
(1,0) | (0,2)
(1,0) | (0,3)
(1,0) | (0,4)
(1,0) | (0,5)
(1,0) | (1,1)
(1,0) | (1,2)
(1,0) | (1,3)
(1,0) | (1,4)
(1,0) | (1,5)
(1,1) | (0,0)
(1,1) | (0,1)
(1,1) | (0,2)
(1,1) | (0,3)
```

Train example 2: 2016 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
7 6 5 4 3 2 1 .
+ + + + + + 9 8
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
```
```
c0 | c1
(0,0) | (0,1)
(0,0) | (0,2)
(0,0) | (0,3)
(0,0) | (0,4)
(0,0) | (0,5)
(0,0) | (0,6)
(0,0) | (0,7)
(0,1) | (0,2)
(0,1) | (0,3)
(0,1) | (0,4)
(0,1) | (0,5)
(0,1) | (0,6)
(0,1) | (0,7)
(0,2) | (0,3)
(0,2) | (0,4)
(0,2) | (0,5)
(0,2) | (0,6)
(0,2) | (0,7)
(0,3) | (0,4)
(0,3) | (0,5)
(0,3) | (0,6)
(0,3) | (0,7)
(0,4) | (0,5)
(0,4) | (0,6)
(0,4) | (0,7)
(0,5) | (0,6)
(0,5) | (0,7)
(0,6) | (0,7)
(1,0) | (0,0)
(1,0) | (0,1)
```


#### &r41, assignment 6 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_H)}
- rows per train example: [630, 630, 2016]; test: 2646

Train example 0: 630 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
+ + + + 6 .
+ + + + 7 1
+ + + + 8 2
+ + + + 9 3
+ + + + + 4
+ + + + + 5
```
```
c0 | c1
(0,0) | (0,1)
(0,0) | (0,2)
(0,0) | (0,3)
(0,0) | (0,4)
(0,0) | (0,5)
(0,0) | (1,1)
(0,0) | (1,2)
(0,0) | (1,3)
(0,0) | (1,4)
(0,0) | (1,5)
(0,0) | (2,1)
(0,0) | (2,2)
(0,0) | (2,3)
(0,0) | (2,4)
(0,0) | (2,5)
(0,0) | (3,1)
(0,0) | (3,2)
(0,0) | (3,3)
(0,0) | (3,4)
(0,0) | (3,5)
(0,0) | (4,1)
(0,0) | (4,2)
(0,0) | (4,3)
(0,0) | (4,4)
(0,0) | (4,5)
(0,0) | (5,1)
(0,0) | (5,2)
(0,0) | (5,3)
(0,0) | (5,4)
(0,0) | (5,5)
```

Train example 1: 630 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
+ + + + 6 .
+ + + + 7 1
+ + + + 8 2
+ + + + 9 3
+ + + + + 4
+ + + + + 5
```
```
c0 | c1
(0,0) | (0,1)
(0,0) | (0,2)
(0,0) | (0,3)
(0,0) | (0,4)
(0,0) | (0,5)
(0,0) | (1,1)
(0,0) | (1,2)
(0,0) | (1,3)
(0,0) | (1,4)
(0,0) | (1,5)
(0,0) | (2,1)
(0,0) | (2,2)
(0,0) | (2,3)
(0,0) | (2,4)
(0,0) | (2,5)
(0,0) | (3,1)
(0,0) | (3,2)
(0,0) | (3,3)
(0,0) | (3,4)
(0,0) | (3,5)
(0,0) | (4,1)
(0,0) | (4,2)
(0,0) | (4,3)
(0,0) | (4,4)
(0,0) | (4,5)
(0,0) | (5,1)
(0,0) | (5,2)
(0,0) | (5,3)
(0,0) | (5,4)
(0,0) | (5,5)
```

Train example 2: 2016 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
+ + + + + + 8 .
+ + + + + + 9 1
+ + + + + + + 2
+ + + + + + + 3
+ + + + + + + 4
+ + + + + + + 5
+ + + + + + + 6
+ + + + + + + 7
```
```
c0 | c1
(0,0) | (0,1)
(0,0) | (0,2)
(0,0) | (0,3)
(0,0) | (0,4)
(0,0) | (0,5)
(0,0) | (0,6)
(0,0) | (0,7)
(0,0) | (1,1)
(0,0) | (1,2)
(0,0) | (1,3)
(0,0) | (1,4)
(0,0) | (1,5)
(0,0) | (1,6)
(0,0) | (1,7)
(0,0) | (2,1)
(0,0) | (2,2)
(0,0) | (2,3)
(0,0) | (2,4)
(0,0) | (2,5)
(0,0) | (2,6)
(0,0) | (2,7)
(0,0) | (3,1)
(0,0) | (3,2)
(0,0) | (3,3)
(0,0) | (3,4)
(0,0) | (3,5)
(0,0) | (3,6)
(0,0) | (3,7)
(0,0) | (4,1)
(0,0) | (4,2)
```


#### &r41, assignment 7 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_V)}
- rows per train example: [630, 630, 2016]; test: 2646

Train example 0: 630 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 2 3 4 5
6 7 8 9 + +
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
```
```
c0 | c1
(0,1) | (0,0)
(0,2) | (0,0)
(0,2) | (0,1)
(0,3) | (0,0)
(0,3) | (0,1)
(0,3) | (0,2)
(0,4) | (0,0)
(0,4) | (0,1)
(0,4) | (0,2)
(0,4) | (0,3)
(0,5) | (0,0)
(0,5) | (0,1)
(0,5) | (0,2)
(0,5) | (0,3)
(0,5) | (0,4)
(1,0) | (0,0)
(1,0) | (0,1)
(1,0) | (0,2)
(1,0) | (0,3)
(1,0) | (0,4)
(1,0) | (0,5)
(1,1) | (0,0)
(1,1) | (0,1)
(1,1) | (0,2)
(1,1) | (0,3)
(1,1) | (0,4)
(1,1) | (0,5)
(1,1) | (1,0)
(1,2) | (0,0)
(1,2) | (0,1)
```

Train example 1: 630 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 2 3 4 5
6 7 8 9 + +
+ + + + + +
+ + + + + +
+ + + + + +
+ + + + + +
```
```
c0 | c1
(0,1) | (0,0)
(0,2) | (0,0)
(0,2) | (0,1)
(0,3) | (0,0)
(0,3) | (0,1)
(0,3) | (0,2)
(0,4) | (0,0)
(0,4) | (0,1)
(0,4) | (0,2)
(0,4) | (0,3)
(0,5) | (0,0)
(0,5) | (0,1)
(0,5) | (0,2)
(0,5) | (0,3)
(0,5) | (0,4)
(1,0) | (0,0)
(1,0) | (0,1)
(1,0) | (0,2)
(1,0) | (0,3)
(1,0) | (0,4)
(1,0) | (0,5)
(1,1) | (0,0)
(1,1) | (0,1)
(1,1) | (0,2)
(1,1) | (0,3)
(1,1) | (0,4)
(1,1) | (0,5)
(1,1) | (1,0)
(1,2) | (0,0)
(1,2) | (0,1)
```

Train example 2: 2016 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 2 3 4 5 6 7
8 9 + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
+ + + + + + + +
```
```
c0 | c1
(0,1) | (0,0)
(0,2) | (0,0)
(0,2) | (0,1)
(0,3) | (0,0)
(0,3) | (0,1)
(0,3) | (0,2)
(0,4) | (0,0)
(0,4) | (0,1)
(0,4) | (0,2)
(0,4) | (0,3)
(0,5) | (0,0)
(0,5) | (0,1)
(0,5) | (0,2)
(0,5) | (0,3)
(0,5) | (0,4)
(0,6) | (0,0)
(0,6) | (0,1)
(0,6) | (0,2)
(0,6) | (0,3)
(0,6) | (0,4)
(0,6) | (0,5)
(0,7) | (0,0)
(0,7) | (0,1)
(0,7) | (0,2)
(0,7) | (0,3)
(0,7) | (0,4)
(0,7) | (0,5)
(0,7) | (0,6)
(1,0) | (0,0)
(1,0) | (0,1)
```


#### &r41, assignment 8 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_H)}
- rows per train example: [630, 630, 2016]; test: 2646

Train example 0: 630 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 6 + + + +
1 7 + + + +
2 8 + + + +
3 9 + + + +
4 + + + + +
5 + + + + +
```
```
c0 | c1
(0,1) | (0,0)
(0,1) | (1,0)
(0,1) | (2,0)
(0,1) | (3,0)
(0,1) | (4,0)
(0,1) | (5,0)
(0,2) | (0,0)
(0,2) | (0,1)
(0,2) | (1,0)
(0,2) | (1,1)
(0,2) | (2,0)
(0,2) | (2,1)
(0,2) | (3,0)
(0,2) | (3,1)
(0,2) | (4,0)
(0,2) | (4,1)
(0,2) | (5,0)
(0,2) | (5,1)
(0,3) | (0,0)
(0,3) | (0,1)
(0,3) | (0,2)
(0,3) | (1,0)
(0,3) | (1,1)
(0,3) | (1,2)
(0,3) | (2,0)
(0,3) | (2,1)
(0,3) | (2,2)
(0,3) | (3,0)
(0,3) | (3,1)
(0,3) | (3,2)
```

Train example 1: 630 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 6 + + + +
1 7 + + + +
2 8 + + + +
3 9 + + + +
4 + + + + +
5 + + + + +
```
```
c0 | c1
(0,1) | (0,0)
(0,1) | (1,0)
(0,1) | (2,0)
(0,1) | (3,0)
(0,1) | (4,0)
(0,1) | (5,0)
(0,2) | (0,0)
(0,2) | (0,1)
(0,2) | (1,0)
(0,2) | (1,1)
(0,2) | (2,0)
(0,2) | (2,1)
(0,2) | (3,0)
(0,2) | (3,1)
(0,2) | (4,0)
(0,2) | (4,1)
(0,2) | (5,0)
(0,2) | (5,1)
(0,3) | (0,0)
(0,3) | (0,1)
(0,3) | (0,2)
(0,3) | (1,0)
(0,3) | (1,1)
(0,3) | (1,2)
(0,3) | (2,0)
(0,3) | (2,1)
(0,3) | (2,2)
(0,3) | (3,0)
(0,3) | (3,1)
(0,3) | (3,2)
```

Train example 2: 2016 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 8 + + + + + +
1 9 + + + + + +
2 + + + + + + +
3 + + + + + + +
4 + + + + + + +
5 + + + + + + +
6 + + + + + + +
7 + + + + + + +
```
```
c0 | c1
(0,1) | (0,0)
(0,1) | (1,0)
(0,1) | (2,0)
(0,1) | (3,0)
(0,1) | (4,0)
(0,1) | (5,0)
(0,1) | (6,0)
(0,1) | (7,0)
(0,2) | (0,0)
(0,2) | (0,1)
(0,2) | (1,0)
(0,2) | (1,1)
(0,2) | (2,0)
(0,2) | (2,1)
(0,2) | (3,0)
(0,2) | (3,1)
(0,2) | (4,0)
(0,2) | (4,1)
(0,2) | (5,0)
(0,2) | (5,1)
(0,2) | (6,0)
(0,2) | (6,1)
(0,2) | (7,0)
(0,2) | (7,1)
(0,3) | (0,0)
(0,3) | (0,1)
(0,3) | (0,2)
(0,3) | (1,0)
(0,3) | (1,1)
(0,3) | (1,2)
```

```
INIT Order [:0] input :0 * [L0] :1 ^ [L1] &r34 :2 L0 :3 * [L2] END [:1] input :0 * [L3] :1 L1 &r34 :2 L3 :3 * [L4] END [:0] END [:1] L4 END [:2] SKIP [:3] input :0 * [L5] :1 L1 &r34 :2 L5 :3 * [L6] END [:0] END [:1] L6 END [:2] L6 END [:4] SKIP [:2] SKIP [:4] SKIP [&r44] [&r45] [&r46] [&r47] [&r48] [&r49] [&r50] [&r51] [&r52] [&r53]
```

### &r44 (export table 29)

- columns: c0: Color, c1: Number, c2: Number
- depth 5, candidate keys none
- DETs its entries are assigned: &r9; assignments: 8

#### &r44, assignment 1 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
```
c0 | c1 | c2
0 | 14 | 0
0 | 15 | 1
0 | 20 | 2
0 | 21 | 3
2 | 7 | 0
2 | 8 | 1
2 | 9 | 2
2 | 10 | 3
2 | 13 | 4
2 | 16 | 5
2 | 19 | 6
2 | 22 | 7
2 | 25 | 8
2 | 26 | 9
2 | 27 | 10
2 | 28 | 11
3 | 0 | 0
3 | 1 | 1
3 | 2 | 2
3 | 3 | 3
3 | 4 | 4
3 | 5 | 5
3 | 6 | 6
3 | 11 | 7
3 | 12 | 8
3 | 17 | 9
3 | 18 | 10
3 | 23 | 11
3 | 24 | 12
3 | 29 | 13
```

Train example 1: 36 rows, the first 30 shown
```
c0 | c1 | c2
0 | 0 | 0
0 | 1 | 1
0 | 2 | 2
0 | 3 | 3
0 | 4 | 4
0 | 5 | 5
0 | 6 | 6
0 | 11 | 7
0 | 12 | 8
0 | 17 | 9
0 | 18 | 10
0 | 23 | 11
0 | 24 | 12
0 | 29 | 13
0 | 30 | 14
0 | 31 | 15
0 | 32 | 16
0 | 33 | 17
0 | 34 | 18
0 | 35 | 19
6 | 14 | 0
6 | 15 | 1
6 | 20 | 2
6 | 21 | 3
7 | 7 | 0
7 | 8 | 1
7 | 9 | 2
7 | 10 | 3
7 | 13 | 4
7 | 16 | 5
```

Train example 2: 64 rows, the first 30 shown
```
c0 | c1 | c2
0 | 9 | 0
0 | 10 | 1
0 | 11 | 2
0 | 12 | 3
0 | 13 | 4
0 | 14 | 5
0 | 17 | 6
0 | 22 | 7
0 | 25 | 8
0 | 30 | 9
0 | 33 | 10
0 | 38 | 11
0 | 41 | 12
0 | 46 | 13
0 | 49 | 14
0 | 50 | 15
0 | 51 | 16
0 | 52 | 17
0 | 53 | 18
0 | 54 | 19
5 | 18 | 0
5 | 19 | 1
5 | 20 | 2
5 | 21 | 3
5 | 26 | 4
5 | 29 | 5
5 | 34 | 6
5 | 37 | 7
5 | 42 | 8
5 | 43 | 9
```


#### &r44, assignment 2 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r44, assignment 3 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r44, assignment 4 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r44, assignment 5 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r44, assignment 6 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r44, assignment 7 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r44, assignment 8 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_H)}
- rows equal to those of assignment 1 at every example
### &r45 (export table 30)

- columns: c0: Color, c1: Number, c2: Number
- depth 5, candidate keys none
- DETs its entries are assigned: &r9; assignments: 8

#### &r45, assignment 1 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
```
c0 | c1 | c2
0 | 14 | 3
0 | 15 | 2
0 | 20 | 1
0 | 21 | 0
2 | 7 | 11
2 | 8 | 10
2 | 9 | 9
2 | 10 | 8
2 | 13 | 7
2 | 16 | 6
2 | 19 | 5
2 | 22 | 4
2 | 25 | 3
2 | 26 | 2
2 | 27 | 1
2 | 28 | 0
3 | 0 | 19
3 | 1 | 18
3 | 2 | 17
3 | 3 | 16
3 | 4 | 15
3 | 5 | 14
3 | 6 | 13
3 | 11 | 12
3 | 12 | 11
3 | 17 | 10
3 | 18 | 9
3 | 23 | 8
3 | 24 | 7
3 | 29 | 6
```

Train example 1: 36 rows, the first 30 shown
```
c0 | c1 | c2
0 | 0 | 19
0 | 1 | 18
0 | 2 | 17
0 | 3 | 16
0 | 4 | 15
0 | 5 | 14
0 | 6 | 13
0 | 11 | 12
0 | 12 | 11
0 | 17 | 10
0 | 18 | 9
0 | 23 | 8
0 | 24 | 7
0 | 29 | 6
0 | 30 | 5
0 | 31 | 4
0 | 32 | 3
0 | 33 | 2
0 | 34 | 1
0 | 35 | 0
6 | 14 | 3
6 | 15 | 2
6 | 20 | 1
6 | 21 | 0
7 | 7 | 11
7 | 8 | 10
7 | 9 | 9
7 | 10 | 8
7 | 13 | 7
7 | 16 | 6
```

Train example 2: 64 rows, the first 30 shown
```
c0 | c1 | c2
0 | 9 | 19
0 | 10 | 18
0 | 11 | 17
0 | 12 | 16
0 | 13 | 15
0 | 14 | 14
0 | 17 | 13
0 | 22 | 12
0 | 25 | 11
0 | 30 | 10
0 | 33 | 9
0 | 38 | 8
0 | 41 | 7
0 | 46 | 6
0 | 49 | 5
0 | 50 | 4
0 | 51 | 3
0 | 52 | 2
0 | 53 | 1
0 | 54 | 0
5 | 18 | 11
5 | 19 | 10
5 | 20 | 9
5 | 21 | 8
5 | 26 | 7
5 | 29 | 6
5 | 34 | 5
5 | 37 | 4
5 | 42 | 3
5 | 43 | 2
```


#### &r45, assignment 2 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r45, assignment 3 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r45, assignment 4 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r45, assignment 5 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r45, assignment 6 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r45, assignment 7 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r45, assignment 8 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_H)}
- rows equal to those of assignment 1 at every example
### &r46 (export table 31)

- columns: c0: Color, c1: Number
- depth 5, candidate keys none
- DETs its entries are assigned: &r9; assignments: 8

#### &r46, assignment 1 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_V)}
- rows per train example: [3, 3, 3]; test: 6

Train example 0: 3 rows
```
c0 | c1
0 | 14
2 | 7
3 | 0
```

Train example 1: 3 rows
```
c0 | c1
0 | 0
6 | 14
7 | 7
```

Train example 2: 3 rows
```
c0 | c1
0 | 9
5 | 18
8 | 0
```


#### &r46, assignment 2 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r46, assignment 3 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r46, assignment 4 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r46, assignment 5 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r46, assignment 6 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r46, assignment 7 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r46, assignment 8 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_H)}
- rows equal to those of assignment 1 at every example
### &r47 (export table 32)

- columns: c0: Color, c1: Number
- depth 5, candidate keys none
- DETs its entries are assigned: &r9; assignments: 8

#### &r47, assignment 1 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_V)}
- rows per train example: [3, 3, 3]; test: 6

Train example 0: 3 rows
```
c0 | c1
0 | 21
2 | 28
3 | 35
```

Train example 1: 3 rows
```
c0 | c1
0 | 35
6 | 21
7 | 28
```

Train example 2: 3 rows
```
c0 | c1
0 | 54
5 | 45
8 | 63
```


#### &r47, assignment 2 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r47, assignment 3 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r47, assignment 4 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r47, assignment 5 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r47, assignment 6 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r47, assignment 7 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r47, assignment 8 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_H)}
- rows equal to those of assignment 1 at every example
### &r48 (export table 33)

- columns: c0: Color, c1: Number, c2: Number
- depth 5, candidate keys none
- DETs its entries are assigned: &r9; assignments: 8

#### &r48, assignment 1 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_V)}
- rows per train example: [33, 33, 61]; test: 94

Train example 0: 33 rows, the first 30 shown
```
c0 | c1 | c2
0 | 14 | 15
0 | 15 | 20
0 | 20 | 21
2 | 7 | 8
2 | 8 | 9
2 | 9 | 10
2 | 10 | 13
2 | 13 | 16
2 | 16 | 19
2 | 19 | 22
2 | 22 | 25
2 | 25 | 26
2 | 26 | 27
2 | 27 | 28
3 | 0 | 1
3 | 1 | 2
3 | 2 | 3
3 | 3 | 4
3 | 4 | 5
3 | 5 | 6
3 | 6 | 11
3 | 11 | 12
3 | 12 | 17
3 | 17 | 18
3 | 18 | 23
3 | 23 | 24
3 | 24 | 29
3 | 29 | 30
3 | 30 | 31
3 | 31 | 32
```

Train example 1: 33 rows, the first 30 shown
```
c0 | c1 | c2
0 | 0 | 1
0 | 1 | 2
0 | 2 | 3
0 | 3 | 4
0 | 4 | 5
0 | 5 | 6
0 | 6 | 11
0 | 11 | 12
0 | 12 | 17
0 | 17 | 18
0 | 18 | 23
0 | 23 | 24
0 | 24 | 29
0 | 29 | 30
0 | 30 | 31
0 | 31 | 32
0 | 32 | 33
0 | 33 | 34
0 | 34 | 35
6 | 14 | 15
6 | 15 | 20
6 | 20 | 21
7 | 7 | 8
7 | 8 | 9
7 | 9 | 10
7 | 10 | 13
7 | 13 | 16
7 | 16 | 19
7 | 19 | 22
7 | 22 | 25
```

Train example 2: 61 rows, the first 30 shown
```
c0 | c1 | c2
0 | 9 | 10
0 | 10 | 11
0 | 11 | 12
0 | 12 | 13
0 | 13 | 14
0 | 14 | 17
0 | 17 | 22
0 | 22 | 25
0 | 25 | 30
0 | 30 | 33
0 | 33 | 38
0 | 38 | 41
0 | 41 | 46
0 | 46 | 49
0 | 49 | 50
0 | 50 | 51
0 | 51 | 52
0 | 52 | 53
0 | 53 | 54
5 | 18 | 19
5 | 19 | 20
5 | 20 | 21
5 | 21 | 26
5 | 26 | 29
5 | 29 | 34
5 | 34 | 37
5 | 37 | 42
5 | 42 | 43
5 | 43 | 44
5 | 44 | 45
```


#### &r48, assignment 2 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r48, assignment 3 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r48, assignment 4 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r48, assignment 5 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r48, assignment 6 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r48, assignment 7 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r48, assignment 8 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_H)}
- rows equal to those of assignment 1 at every example
### &r49 (export table 34)

- columns: c0: Color, c1: Number, c2: Number
- depth 5, candidate keys none
- DETs its entries are assigned: &r9; assignments: 8

#### &r49, assignment 1 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
```
c0 | c1 | c2
0 | 14 | 15
0 | 15 | 20
0 | 20 | 21
0 | 21 | 14
2 | 7 | 8
2 | 8 | 9
2 | 9 | 10
2 | 10 | 13
2 | 13 | 16
2 | 16 | 19
2 | 19 | 22
2 | 22 | 25
2 | 25 | 26
2 | 26 | 27
2 | 27 | 28
2 | 28 | 7
3 | 0 | 1
3 | 1 | 2
3 | 2 | 3
3 | 3 | 4
3 | 4 | 5
3 | 5 | 6
3 | 6 | 11
3 | 11 | 12
3 | 12 | 17
3 | 17 | 18
3 | 18 | 23
3 | 23 | 24
3 | 24 | 29
3 | 29 | 30
```

Train example 1: 36 rows, the first 30 shown
```
c0 | c1 | c2
0 | 0 | 1
0 | 1 | 2
0 | 2 | 3
0 | 3 | 4
0 | 4 | 5
0 | 5 | 6
0 | 6 | 11
0 | 11 | 12
0 | 12 | 17
0 | 17 | 18
0 | 18 | 23
0 | 23 | 24
0 | 24 | 29
0 | 29 | 30
0 | 30 | 31
0 | 31 | 32
0 | 32 | 33
0 | 33 | 34
0 | 34 | 35
0 | 35 | 0
6 | 14 | 15
6 | 15 | 20
6 | 20 | 21
6 | 21 | 14
7 | 7 | 8
7 | 8 | 9
7 | 9 | 10
7 | 10 | 13
7 | 13 | 16
7 | 16 | 19
```

Train example 2: 64 rows, the first 30 shown
```
c0 | c1 | c2
0 | 9 | 10
0 | 10 | 11
0 | 11 | 12
0 | 12 | 13
0 | 13 | 14
0 | 14 | 17
0 | 17 | 22
0 | 22 | 25
0 | 25 | 30
0 | 30 | 33
0 | 33 | 38
0 | 38 | 41
0 | 41 | 46
0 | 46 | 49
0 | 49 | 50
0 | 50 | 51
0 | 51 | 52
0 | 52 | 53
0 | 53 | 54
0 | 54 | 9
5 | 18 | 19
5 | 19 | 20
5 | 20 | 21
5 | 21 | 26
5 | 26 | 29
5 | 29 | 34
5 | 34 | 37
5 | 37 | 42
5 | 42 | 43
5 | 43 | 44
```


#### &r49, assignment 2 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r49, assignment 3 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r49, assignment 4 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r49, assignment 5 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r49, assignment 6 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r49, assignment 7 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r49, assignment 8 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_H)}
- rows equal to those of assignment 1 at every example
### &r50 (export table 35)

- columns: c0: Color, c1: Number
- depth 4, candidate keys none
- DETs its entries are assigned: &r9; assignments: 8

#### &r50, assignment 1 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
```
c0 | c1
0 | 14
0 | 15
0 | 20
0 | 21
2 | 7
2 | 8
2 | 9
2 | 10
2 | 13
2 | 16
2 | 19
2 | 22
2 | 25
2 | 26
2 | 27
2 | 28
3 | 0
3 | 1
3 | 2
3 | 3
3 | 4
3 | 5
3 | 6
3 | 11
3 | 12
3 | 17
3 | 18
3 | 23
3 | 24
3 | 29
```

Train example 1: 36 rows, the first 30 shown
```
c0 | c1
0 | 0
0 | 1
0 | 2
0 | 3
0 | 4
0 | 5
0 | 6
0 | 11
0 | 12
0 | 17
0 | 18
0 | 23
0 | 24
0 | 29
0 | 30
0 | 31
0 | 32
0 | 33
0 | 34
0 | 35
6 | 14
6 | 15
6 | 20
6 | 21
7 | 7
7 | 8
7 | 9
7 | 10
7 | 13
7 | 16
```

Train example 2: 64 rows, the first 30 shown
```
c0 | c1
0 | 9
0 | 10
0 | 11
0 | 12
0 | 13
0 | 14
0 | 17
0 | 22
0 | 25
0 | 30
0 | 33
0 | 38
0 | 41
0 | 46
0 | 49
0 | 50
0 | 51
0 | 52
0 | 53
0 | 54
5 | 18
5 | 19
5 | 20
5 | 21
5 | 26
5 | 29
5 | 34
5 | 37
5 | 42
5 | 43
```


#### &r50, assignment 2 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r50, assignment 3 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r50, assignment 4 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r50, assignment 5 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r50, assignment 6 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r50, assignment 7 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r50, assignment 8 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_H)}
- rows equal to those of assignment 1 at every example
### &r52 (export table 36)

- columns: c0: Color, c1: Number, c2: Number
- depth 4, candidate keys none
- DETs its entries are assigned: &r9; assignments: 8

#### &r52, assignment 1 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_V)}
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
```
c0 | c1 | c2
0 | 14 | 14
0 | 15 | 15
0 | 20 | 20
0 | 21 | 21
2 | 7 | 7
2 | 8 | 8
2 | 9 | 9
2 | 10 | 10
2 | 13 | 13
2 | 16 | 16
2 | 19 | 19
2 | 22 | 22
2 | 25 | 25
2 | 26 | 26
2 | 27 | 27
2 | 28 | 28
3 | 0 | 0
3 | 1 | 1
3 | 2 | 2
3 | 3 | 3
3 | 4 | 4
3 | 5 | 5
3 | 6 | 6
3 | 11 | 11
3 | 12 | 12
3 | 17 | 17
3 | 18 | 18
3 | 23 | 23
3 | 24 | 24
3 | 29 | 29
```

Train example 1: 36 rows, the first 30 shown
```
c0 | c1 | c2
0 | 0 | 0
0 | 1 | 1
0 | 2 | 2
0 | 3 | 3
0 | 4 | 4
0 | 5 | 5
0 | 6 | 6
0 | 11 | 11
0 | 12 | 12
0 | 17 | 17
0 | 18 | 18
0 | 23 | 23
0 | 24 | 24
0 | 29 | 29
0 | 30 | 30
0 | 31 | 31
0 | 32 | 32
0 | 33 | 33
0 | 34 | 34
0 | 35 | 35
6 | 14 | 14
6 | 15 | 15
6 | 20 | 20
6 | 21 | 21
7 | 7 | 7
7 | 8 | 8
7 | 9 | 9
7 | 10 | 10
7 | 13 | 13
7 | 16 | 16
```

Train example 2: 64 rows, the first 30 shown
```
c0 | c1 | c2
0 | 9 | 9
0 | 10 | 10
0 | 11 | 11
0 | 12 | 12
0 | 13 | 13
0 | 14 | 14
0 | 17 | 17
0 | 22 | 22
0 | 25 | 25
0 | 30 | 30
0 | 33 | 33
0 | 38 | 38
0 | 41 | 41
0 | 46 | 46
0 | 49 | 49
0 | 50 | 50
0 | 51 | 51
0 | 52 | 52
0 | 53 | 53
0 | 54 | 54
5 | 18 | 18
5 | 19 | 19
5 | 20 | 20
5 | 21 | 21
5 | 26 | 26
5 | 29 | 29
5 | 34 | 34
5 | 37 | 37
5 | 42 | 42
5 | 43 | 43
```


#### &r52, assignment 2 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r52, assignment 3 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r52, assignment 4 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_TR, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r52, assignment 5 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r52, assignment 6 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BL, AXIS_H)}
- rows equal to those of assignment 1 at every example

#### &r52, assignment 7 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_V)}
- rows equal to those of assignment 1 at every example

#### &r52, assignment 8 of 8

- DET values that differ between the assignments: &r9 = {(DIAG_BR, AXIS_H)}
- rows equal to those of assignment 1 at every example
```
RULE &r4 :1 * [L0] :2 * [L1] neighbor :0 L0 :2 * [L2] &r4 :1 L2 :2 * [L3] < L3 L1 END [&r54]
```

### &r54 (export table 37)

- columns: c0: Box, c1: Number, c2: Number, c3: Box
- depth 5, candidate keys none
- rows per train example: [64, 64, 132]; test: 196

Train example 0: 64 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. 5 3 3 5 .
. 3 5 5 3 .
. 3 5 5 3 .
. 5 3 3 5 .
. . . . . .
```
```
c0 | c1 | c2 | c3
(1,1) | 0 | 1 | (0,0)
(1,1) | 0 | 1 | (0,1)
(1,1) | 0 | 1 | (0,2)
(1,1) | 0 | 1 | (1,0)
(1,1) | 0 | 1 | (2,0)
(1,2) | 0 | 1 | (0,1)
(1,2) | 0 | 1 | (0,2)
(1,2) | 0 | 1 | (0,3)
(1,3) | 0 | 1 | (0,2)
(1,3) | 0 | 1 | (0,3)
(1,3) | 0 | 1 | (0,4)
(1,4) | 0 | 1 | (0,3)
(1,4) | 0 | 1 | (0,4)
(1,4) | 0 | 1 | (0,5)
(1,4) | 0 | 1 | (1,5)
(1,4) | 0 | 1 | (2,5)
(2,1) | 0 | 1 | (1,0)
(2,1) | 0 | 1 | (2,0)
(2,1) | 0 | 1 | (3,0)
(2,2) | 1 | 2 | (1,1)
(2,2) | 1 | 2 | (1,2)
(2,2) | 1 | 2 | (1,3)
(2,2) | 1 | 2 | (2,1)
(2,2) | 1 | 2 | (3,1)
(2,3) | 1 | 2 | (1,2)
(2,3) | 1 | 2 | (1,3)
(2,3) | 1 | 2 | (1,4)
(2,3) | 1 | 2 | (2,4)
(2,3) | 1 | 2 | (3,4)
(2,4) | 0 | 1 | (1,5)
```

Train example 1: 64 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. 5 3 3 5 .
. 3 5 5 3 .
. 3 5 5 3 .
. 5 3 3 5 .
. . . . . .
```
```
c0 | c1 | c2 | c3
(1,1) | 0 | 1 | (0,0)
(1,1) | 0 | 1 | (0,1)
(1,1) | 0 | 1 | (0,2)
(1,1) | 0 | 1 | (1,0)
(1,1) | 0 | 1 | (2,0)
(1,2) | 0 | 1 | (0,1)
(1,2) | 0 | 1 | (0,2)
(1,2) | 0 | 1 | (0,3)
(1,3) | 0 | 1 | (0,2)
(1,3) | 0 | 1 | (0,3)
(1,3) | 0 | 1 | (0,4)
(1,4) | 0 | 1 | (0,3)
(1,4) | 0 | 1 | (0,4)
(1,4) | 0 | 1 | (0,5)
(1,4) | 0 | 1 | (1,5)
(1,4) | 0 | 1 | (2,5)
(2,1) | 0 | 1 | (1,0)
(2,1) | 0 | 1 | (2,0)
(2,1) | 0 | 1 | (3,0)
(2,2) | 1 | 2 | (1,1)
(2,2) | 1 | 2 | (1,2)
(2,2) | 1 | 2 | (1,3)
(2,2) | 1 | 2 | (2,1)
(2,2) | 1 | 2 | (3,1)
(2,3) | 1 | 2 | (1,2)
(2,3) | 1 | 2 | (1,3)
(2,3) | 1 | 2 | (1,4)
(2,3) | 1 | 2 | (2,4)
(2,3) | 1 | 2 | (3,4)
(2,4) | 0 | 1 | (1,5)
```

Train example 2: 132 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . .
. 5 3 3 3 3 5 .
. 3 5 3 3 5 3 .
. 3 3 5 5 3 3 .
. 3 3 5 5 3 3 .
. 3 5 3 3 5 3 .
. 5 3 3 3 3 5 .
. . . . . . . .
```
```
c0 | c1 | c2 | c3
(1,1) | 0 | 1 | (0,0)
(1,1) | 0 | 1 | (0,1)
(1,1) | 0 | 1 | (0,2)
(1,1) | 0 | 1 | (1,0)
(1,1) | 0 | 1 | (2,0)
(1,2) | 0 | 1 | (0,1)
(1,2) | 0 | 1 | (0,2)
(1,2) | 0 | 1 | (0,3)
(1,3) | 0 | 1 | (0,2)
(1,3) | 0 | 1 | (0,3)
(1,3) | 0 | 1 | (0,4)
(1,4) | 0 | 1 | (0,3)
(1,4) | 0 | 1 | (0,4)
(1,4) | 0 | 1 | (0,5)
(1,5) | 0 | 1 | (0,4)
(1,5) | 0 | 1 | (0,5)
(1,5) | 0 | 1 | (0,6)
(1,6) | 0 | 1 | (0,5)
(1,6) | 0 | 1 | (0,6)
(1,6) | 0 | 1 | (0,7)
(1,6) | 0 | 1 | (1,7)
(1,6) | 0 | 1 | (2,7)
(2,1) | 0 | 1 | (1,0)
(2,1) | 0 | 1 | (2,0)
(2,1) | 0 | 1 | (3,0)
(2,2) | 1 | 2 | (1,1)
(2,2) | 1 | 2 | (1,2)
(2,2) | 1 | 2 | (1,3)
(2,2) | 1 | 2 | (2,1)
(2,2) | 1 | 2 | (3,1)
```

```
INIT Order [:0] SKIP [:1] &r13 :2 * [L0] END [:0] END [:1] L0 END [:2] SKIP [:3] &r13 :2 * [L1] END [:0] END [:1] L1 END [:2] L1 END [:4] SKIP [&r55] [&r56] [&r57] [&r58] [&r59] [&r60] [&r61] [&r62] [&r63] [&r64]
```

### &r55 (export table 38)

- columns: c0: Number, c1: Number
- depth 9, candidate keys none
- rows per train example: [3, 3, 3]; test: 6

Train example 0: 3 rows
```
c0 | c1
0 | 0
1 | 1
2 | 2
```

Train example 1: 3 rows
```
c0 | c1
0 | 0
1 | 1
2 | 2
```

Train example 2: 3 rows
```
c0 | c1
0 | 0
1 | 1
2 | 2
```

### &r56 (export table 39)

- columns: c0: Number, c1: Number
- depth 9, candidate keys none
- rows per train example: [3, 3, 3]; test: 6

Train example 0: 3 rows
```
c0 | c1
0 | 2
1 | 1
2 | 0
```

Train example 1: 3 rows
```
c0 | c1
0 | 2
1 | 1
2 | 0
```

Train example 2: 3 rows
```
c0 | c1
0 | 2
1 | 1
2 | 0
```

### &r57 (export table 40)

- columns: c0: Number
- depth 9, candidate keys none
- rows per train example: [1, 1, 1]; test: 2

Train example 0: 1 row
```
c0
0
```

Train example 1: 1 row
```
c0
0
```

Train example 2: 1 row
```
c0
0
```

### &r58 (export table 41)

- columns: c0: Number
- depth 9, candidate keys none
- rows per train example: [1, 1, 1]; test: 2

Train example 0: 1 row
```
c0
2
```

Train example 1: 1 row
```
c0
2
```

Train example 2: 1 row
```
c0
2
```

### &r59 (export table 42)

- columns: c0: Number, c1: Number
- depth 9, candidate keys none
- rows per train example: [2, 2, 2]; test: 4

Train example 0: 2 rows
```
c0 | c1
0 | 1
1 | 2
```

Train example 1: 2 rows
```
c0 | c1
0 | 1
1 | 2
```

Train example 2: 2 rows
```
c0 | c1
0 | 1
1 | 2
```

### &r60 (export table 43)

- columns: c0: Number, c1: Number
- depth 9, candidate keys none
- rows per train example: [3, 3, 3]; test: 6

Train example 0: 3 rows
```
c0 | c1
0 | 1
1 | 2
2 | 0
```

Train example 1: 3 rows
```
c0 | c1
0 | 1
1 | 2
2 | 0
```

Train example 2: 3 rows
```
c0 | c1
0 | 1
1 | 2
2 | 0
```

```
INIT Cardinality [:0] SKIP [:1] input :1 * [L0] NOT &r10 :2 0 :3 L0 END [:0] END [:1] L0 END [:2] END [:0] END [&r65] [&r66] [&r67]
```

### &r65 (export table 44)

- columns: c0: Number
- depth 7, candidate keys none
- rows per train example: [1, 1, 1]; test: 2

Train example 0: 1 row
```
c0
2
```

Train example 1: 1 row
```
c0
2
```

Train example 2: 1 row
```
c0
2
```

### &r67 (export table 45)

- columns: none
- depth 1, candidate keys none
- rows per train example: [1, 1, 1]; test: 2

Train example 0: 1 row
The relation has no columns: its one row says the relation holds.

Train example 1: 1 row
The relation has no columns: its one row says the relation holds.

Train example 2: 1 row
The relation has no columns: its one row says the relation holds.

```
RULE input :0 * [L0] :1 * [L1] OR &r25 :1 * [L2] :2 L1 ALSO &r23 :1 L1 &r24 :1 L2 END END [&r68]
```

### &r68 (export table 46)

- columns: c0: Box, c1: Color, c2: Color
- depth 10, candidate keys none
- rows per train example: [36, 36, 64]; test: 100

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 0 | 3
(0,1) | 0 | 3
(0,2) | 0 | 3
(0,3) | 0 | 3
(0,4) | 0 | 3
(0,5) | 0 | 3
(1,0) | 0 | 3
(1,1) | 3 | 2
(1,2) | 3 | 2
(1,3) | 3 | 2
(1,4) | 3 | 2
(1,5) | 0 | 3
(2,0) | 0 | 3
(2,1) | 3 | 2
(2,2) | 2 | 0
(2,3) | 2 | 0
(2,4) | 3 | 2
(2,5) | 0 | 3
(3,0) | 0 | 3
(3,1) | 3 | 2
(3,2) | 2 | 0
(3,3) | 2 | 0
(3,4) | 3 | 2
(3,5) | 0 | 3
(4,0) | 0 | 3
(4,1) | 3 | 2
(4,2) | 3 | 2
(4,3) | 3 | 2
(4,4) | 3 | 2
(4,5) | 0 | 3
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
1 1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 6 | 0
(0,1) | 6 | 0
(0,2) | 6 | 0
(0,3) | 6 | 0
(0,4) | 6 | 0
(0,5) | 6 | 0
(1,0) | 6 | 0
(1,1) | 0 | 7
(1,2) | 0 | 7
(1,3) | 0 | 7
(1,4) | 0 | 7
(1,5) | 6 | 0
(2,0) | 6 | 0
(2,1) | 0 | 7
(2,2) | 7 | 6
(2,3) | 7 | 6
(2,4) | 0 | 7
(2,5) | 6 | 0
(3,0) | 6 | 0
(3,1) | 0 | 7
(3,2) | 7 | 6
(3,3) | 7 | 6
(3,4) | 0 | 7
(3,5) | 6 | 0
(4,0) | 6 | 0
(4,1) | 0 | 7
(4,2) | 0 | 7
(4,3) | 0 | 7
(4,4) | 0 | 7
(4,5) | 6 | 0
```

Train example 2: 64 rows, the first 30 shown
Drawn on a 8x8 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 5 | 8
(0,1) | 5 | 8
(0,2) | 5 | 8
(0,3) | 5 | 8
(0,4) | 5 | 8
(0,5) | 5 | 8
(0,6) | 5 | 8
(0,7) | 5 | 8
(1,0) | 5 | 8
(1,1) | 8 | 0
(1,2) | 8 | 0
(1,3) | 8 | 0
(1,4) | 8 | 0
(1,5) | 8 | 0
(1,6) | 8 | 0
(1,7) | 5 | 8
(2,0) | 5 | 8
(2,1) | 8 | 0
(2,2) | 0 | 5
(2,3) | 0 | 5
(2,4) | 0 | 5
(2,5) | 0 | 5
(2,6) | 8 | 0
(2,7) | 5 | 8
(3,0) | 5 | 8
(3,1) | 8 | 0
(3,2) | 0 | 5
(3,3) | 5 | 8
(3,4) | 5 | 8
(3,5) | 0 | 5
```

## What I see

The task: the grid is a set of nested rings, each 1 cell wide. List the colors in the order they first appear from the outer ring inward. Each color takes the color just before it in that list, and the first color takes the last. The DET &r9 (a scan's corner and axis, 8 values) is read only by the clauses of the $ScanOrder case, so every table that this case reads has one assignment.

- **&r0, &r1** (Boundary: the cells of the outer ring, with the edge each is on): a function of the grid size. No signal.
- **&r4** (CellDistance from the outer ring): each cell's depth. The drawing shows the rings 0, 1, 2 (to 3 in e2), but the table is also a function of the grid size only.
- **&r10** (each cell's depth and input color): the functional dependency depth → color holds in every example, and this is the nested-rings scene. In e2, color 8 is at depths 0 and 3, so color → depth does not hold.
- **&r11 to &r16** (Order of the depths of each color): &r13 is each color's first depth (e0: 3 at 0, 2 at 1, 0 at 2), the column the rule needs. &r14 is the last depth. &r15 is one row, `8 | 0 | 3`, in e2 only: the one color that is in two rings. This table is empty in two examples, and it marks the example in which a color comes again. &r11, &r12 and &r16 are ranks of the same rows.
- **&r21 to &r28** (Order of the colors by first depth): &r21 equals &r13 in every example, since the first depths are 0, 1 and 2 with no gap. &r23 is the first color (the outer ring), and &r24 the last. &r25 is the pairs of neighbors in the list, and &r26 adds the pair of the last and the first color. &r26 is a one-to-one map of the three colors in each example; read from c1 to c0, it is the output's recolor (e0: 3 to 0, 2 to 3, 0 to 2). The signal about the rule jumps at &r13, and again at &r26. &r28 is the order as pairs.
- **&r31** (Cardinality: the cells of each color): no clause of this case reads it. Its order (e0: 3 has 20, 2 has 12, 0 has 4) is the order of &r13 in all three examples, so the train pairs cannot tell which of the two orders the rule uses.
- **&r34 to &r53** (ScanOrder at each of the 8 scans): most of the case's rows (&r41 holds 630, 630 and 2016 pairs at each assignment), and no clause of this case reads them. &r34's ranks differ at each scan, but &r44 to &r52 are equal at all 8 assignments. These tables keep a color and a rank and drop the cell, and the rings are symmetric under the 8 scans, so each color gets the same set of ranks at each scan. The equality states the symmetry of the inputs.
- **&r54** (cells with a neighbor of lower depth): for the $EnclosingColor and $RingShift cases; this case does not read it.
- **&r55 to &r60** (Order over the depths 0, 1, 2): the same in all examples, ranks equal to the values. **&r65** (2 colors off the outer ring) and **&r67** are for $RingShift and are not read.
- **&r68** (out): c1 is the output color and c2 the input color, which is not the order of the clause's variables. The drawing shows 1 at every cell, since the table has two Color columns. The rows equal the outputs.

Rows that look like noise: &r0, &r1 and &r4 (the grid size); &r11, &r12, &r16, &r21, &r28 and &r55 to &r60 (ranks and order pairs of tables already shown); and every table of the other cases' clauses, which hold most of the rows.
