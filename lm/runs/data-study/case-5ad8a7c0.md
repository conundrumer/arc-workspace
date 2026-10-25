# 5ad8a7c0, case `$Shortest`

- concept case: True; tokens: 295; tables: 21 relations, 40 per assignment
- cells: a Position is `(row,col)` of the example's input grid (`(row,col)out` where it fits only the output grid), an Offset `+(drow,dcol)`, another Box `rR0-R1 cC0-C1` over the input grid or `[t b l r]` margins; an Ident is `id<n>`, equal only within one case; see README.md

## Grids

### Train example 0: input 4x6, output 4x6

```
input          output
2 0 0 0 0 2    2 2 2 2 2 2
0 0 0 0 0 0    0 0 0 0 0 0
0 0 0 0 0 0    0 0 0 0 0 0
2 0 0 0 0 2    2 2 2 2 2 2
```

### Train example 1: input 4x6, output 4x6

```
input          output
2 0 0 0 0 2    2 0 0 0 0 2
0 2 0 0 2 0    0 2 0 0 2 0
0 0 2 2 0 0    0 0 2 2 0 0
0 2 0 0 2 0    0 2 0 0 2 0
```

### Train example 2: input 4x6, output 4x6

```
input          output
0 0 0 0 0 0    0 0 0 0 0 0
0 2 0 0 2 0    0 2 2 2 2 0
2 0 0 0 0 2    2 0 0 0 0 2
0 2 0 0 2 0    0 2 2 2 2 0
```

### Train example 3: input 4x6, output 4x6

```
input          output
0 0 2 2 0 0    0 0 2 2 0 0
0 2 0 0 2 0    0 2 0 0 2 0
2 0 0 0 0 2    2 0 0 0 0 2
0 2 0 0 2 0    0 2 0 0 2 0
```

### Train example 4: input 4x6, output 4x6

```
input          output
2 0 0 0 0 2    2 0 0 0 0 2
0 2 0 0 2 0    0 2 2 2 2 0
0 2 0 0 2 0    0 2 2 2 2 0
2 0 0 0 0 2    2 0 0 0 0 2
```

### Test example 0: input 4x6

```
2 0 0 0 0 2
0 2 0 0 2 0
0 0 0 0 0 0
2 0 0 0 0 2
```

## Program and tables

Model-written tokens plain, engine-written ones in [brackets]. Each clause is followed by the tables of the relations it declares. A table whose entries hold several DET assignments is given once per assignment, each marked with the values, at that assignment, of the DETs whose value differs between them; a DET's value is the rows of its own table at that assignment.

```
DET AxisDomain END [&r0]
```

### &r0 (export table 2)

- columns: A: Axis
- depth 1, candidate keys none
- DETs its entries are assigned: &r0; assignments: 2

#### &r0, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [0, 0, 0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
A
AXIS_V
```


#### &r0, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [0, 0, 0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
A
AXIS_H
```

```
DET RarestColor END [&r1]
```

### &r1 (export table 3)

- columns: C: Color
- depth 1, candidate keys none
- DETs its entries are assigned: &r1; assignments: 1
- rows per train example: [0, 0, 0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
C
2
```

```
RULE input :0 * [L0] :1 * [L1] &r1 :0 L1 END [&r2]
```

### &r2 (export table 4)

- columns: c0: Box, c1: Color
- depth 2, candidate keys none
- DETs its entries are assigned: &r1; assignments: 1
- rows per train example: [4, 8, 6, 8, 8]; test: 6

Train example 0: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 . . . . 2
. . . . . .
. . . . . .
2 . . . . 2
```
```
c0 | c1
(0,0) | 2
(0,5) | 2
(3,0) | 2
(3,5) | 2
```

Train example 1: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 . . . . 2
. 2 . . 2 .
. . 2 2 . .
. 2 . . 2 .
```
```
c0 | c1
(0,0) | 2
(0,5) | 2
(1,1) | 2
(1,4) | 2
(2,2) | 2
(2,3) | 2
(3,1) | 2
(3,4) | 2
```

Train example 2: 6 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . .
. 2 . . 2 .
2 . . . . 2
. 2 . . 2 .
```
```
c0 | c1
(1,1) | 2
(1,4) | 2
(2,0) | 2
(2,5) | 2
(3,1) | 2
(3,4) | 2
```

Train example 3: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . 2 2 . .
. 2 . . 2 .
2 . . . . 2
. 2 . . 2 .
```
```
c0 | c1
(0,2) | 2
(0,3) | 2
(1,1) | 2
(1,4) | 2
(2,0) | 2
(2,5) | 2
(3,1) | 2
(3,4) | 2
```

Train example 4: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 . . . . 2
. 2 . . 2 .
. 2 . . 2 .
2 . . . . 2
```
```
c0 | c1
(0,0) | 2
(0,5) | 2
(1,1) | 2
(1,4) | 2
(2,1) | 2
(2,4) | 2
(3,0) | 2
(3,5) | 2
```

```
INIT Ray [:0] SKIP [:1] &r2 :1 * [L0] END [:0] END [:1] L0 END [:2] input :0 * [L1] NOT &r2 :1 L1 END [:0] END [:1] L1 END [:3] &r0 :0 * [L2] axis_of :0 * [L3] :1 L2 END [:0] END [:1] L3 END [&r3] [&r4] [&r5] [&r6] [&r7]
```

### &r3 (export table 5)

- columns: c0: Box, c1: Dir8, c2: Number, c3: Box
- depth 4, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 2

#### &r3, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [16, 34, 24, 34, 28]; test: 26

Train example 0: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 . . . . 2
2 . . . . 2
2 . . . . 2
2 . . . . 2
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,0) | DIR_B | 0 | (0,0)
(0,5) | DIR_T | 0 | (0,5)
(0,5) | DIR_B | 0 | (0,5)
(1,0) | DIR_T | 2 | (3,0)
(1,0) | DIR_B | 1 | (0,0)
(1,5) | DIR_T | 2 | (3,5)
(1,5) | DIR_B | 1 | (0,5)
(2,0) | DIR_T | 1 | (3,0)
(2,0) | DIR_B | 2 | (0,0)
(2,5) | DIR_T | 1 | (3,5)
(2,5) | DIR_B | 2 | (0,5)
(3,0) | DIR_T | 0 | (3,0)
(3,0) | DIR_B | 0 | (3,0)
(3,5) | DIR_T | 0 | (3,5)
(3,5) | DIR_B | 0 | (3,5)
```

Train example 1: 34 rows, the first 30 shown
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 1 1 1 1 2
1 2 1 1 2 1
1 2 2 2 2 1
1 2 1 1 2 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,0) | DIR_B | 0 | (0,0)
(0,1) | DIR_T | 1 | (1,1)
(0,2) | DIR_T | 2 | (2,2)
(0,3) | DIR_T | 2 | (2,3)
(0,4) | DIR_T | 1 | (1,4)
(0,5) | DIR_T | 0 | (0,5)
(0,5) | DIR_B | 0 | (0,5)
(1,0) | DIR_B | 1 | (0,0)
(1,1) | DIR_T | 0 | (1,1)
(1,1) | DIR_B | 0 | (1,1)
(1,2) | DIR_T | 1 | (2,2)
(1,3) | DIR_T | 1 | (2,3)
(1,4) | DIR_T | 0 | (1,4)
(1,4) | DIR_B | 0 | (1,4)
(1,5) | DIR_B | 1 | (0,5)
(2,0) | DIR_B | 2 | (0,0)
(2,1) | DIR_T | 1 | (3,1)
(2,1) | DIR_B | 1 | (1,1)
(2,2) | DIR_T | 0 | (2,2)
(2,2) | DIR_B | 0 | (2,2)
(2,3) | DIR_T | 0 | (2,3)
(2,3) | DIR_B | 0 | (2,3)
(2,4) | DIR_T | 1 | (3,4)
(2,4) | DIR_B | 1 | (1,4)
(2,5) | DIR_B | 2 | (0,5)
(3,0) | DIR_B | 3 | (0,0)
(3,1) | DIR_T | 0 | (3,1)
(3,1) | DIR_B | 0 | (3,1)
(3,2) | DIR_B | 1 | (2,2)
```

Train example 2: 24 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 . . 1 1
1 2 . . 2 1
2 2 . . 2 2
1 2 . . 2 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 2 | (2,0)
(0,1) | DIR_T | 1 | (1,1)
(0,4) | DIR_T | 1 | (1,4)
(0,5) | DIR_T | 2 | (2,5)
(1,0) | DIR_T | 1 | (2,0)
(1,1) | DIR_T | 0 | (1,1)
(1,1) | DIR_B | 0 | (1,1)
(1,4) | DIR_T | 0 | (1,4)
(1,4) | DIR_B | 0 | (1,4)
(1,5) | DIR_T | 1 | (2,5)
(2,0) | DIR_T | 0 | (2,0)
(2,0) | DIR_B | 0 | (2,0)
(2,1) | DIR_T | 1 | (3,1)
(2,1) | DIR_B | 1 | (1,1)
(2,4) | DIR_T | 1 | (3,4)
(2,4) | DIR_B | 1 | (1,4)
(2,5) | DIR_T | 0 | (2,5)
(2,5) | DIR_B | 0 | (2,5)
(3,0) | DIR_B | 1 | (2,0)
(3,1) | DIR_T | 0 | (3,1)
(3,1) | DIR_B | 0 | (3,1)
(3,4) | DIR_T | 0 | (3,4)
(3,4) | DIR_B | 0 | (3,4)
(3,5) | DIR_B | 1 | (2,5)
```

Train example 3: 34 rows, the first 30 shown
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 2 2 1 1
1 2 1 1 2 1
2 2 1 1 2 2
1 2 1 1 2 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 2 | (2,0)
(0,1) | DIR_T | 1 | (1,1)
(0,2) | DIR_T | 0 | (0,2)
(0,2) | DIR_B | 0 | (0,2)
(0,3) | DIR_T | 0 | (0,3)
(0,3) | DIR_B | 0 | (0,3)
(0,4) | DIR_T | 1 | (1,4)
(0,5) | DIR_T | 2 | (2,5)
(1,0) | DIR_T | 1 | (2,0)
(1,1) | DIR_T | 0 | (1,1)
(1,1) | DIR_B | 0 | (1,1)
(1,2) | DIR_B | 1 | (0,2)
(1,3) | DIR_B | 1 | (0,3)
(1,4) | DIR_T | 0 | (1,4)
(1,4) | DIR_B | 0 | (1,4)
(1,5) | DIR_T | 1 | (2,5)
(2,0) | DIR_T | 0 | (2,0)
(2,0) | DIR_B | 0 | (2,0)
(2,1) | DIR_T | 1 | (3,1)
(2,1) | DIR_B | 1 | (1,1)
(2,2) | DIR_B | 2 | (0,2)
(2,3) | DIR_B | 2 | (0,3)
(2,4) | DIR_T | 1 | (3,4)
(2,4) | DIR_B | 1 | (1,4)
(2,5) | DIR_T | 0 | (2,5)
(2,5) | DIR_B | 0 | (2,5)
(3,0) | DIR_B | 1 | (2,0)
(3,1) | DIR_T | 0 | (3,1)
(3,1) | DIR_B | 0 | (3,1)
(3,2) | DIR_B | 3 | (0,2)
```

Train example 4: 28 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 1 . . 1 2
2 2 . . 2 2
2 2 . . 2 2
2 1 . . 1 2
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,0) | DIR_B | 0 | (0,0)
(0,1) | DIR_T | 1 | (1,1)
(0,4) | DIR_T | 1 | (1,4)
(0,5) | DIR_T | 0 | (0,5)
(0,5) | DIR_B | 0 | (0,5)
(1,0) | DIR_T | 2 | (3,0)
(1,0) | DIR_B | 1 | (0,0)
(1,1) | DIR_T | 0 | (1,1)
(1,1) | DIR_B | 0 | (1,1)
(1,4) | DIR_T | 0 | (1,4)
(1,4) | DIR_B | 0 | (1,4)
(1,5) | DIR_T | 2 | (3,5)
(1,5) | DIR_B | 1 | (0,5)
(2,0) | DIR_T | 1 | (3,0)
(2,0) | DIR_B | 2 | (0,0)
(2,1) | DIR_T | 0 | (2,1)
(2,1) | DIR_B | 0 | (2,1)
(2,4) | DIR_T | 0 | (2,4)
(2,4) | DIR_B | 0 | (2,4)
(2,5) | DIR_T | 1 | (3,5)
(2,5) | DIR_B | 2 | (0,5)
(3,0) | DIR_T | 0 | (3,0)
(3,0) | DIR_B | 0 | (3,0)
(3,1) | DIR_B | 1 | (2,1)
(3,4) | DIR_B | 1 | (2,4)
(3,5) | DIR_T | 0 | (3,5)
(3,5) | DIR_B | 0 | (3,5)
```


#### &r3, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [24, 40, 32, 40, 44]; test: 34

Train example 0: 24 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2 2 2 2
. . . . . .
. . . . . .
2 2 2 2 2 2
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,0) | DIR_R | 0 | (0,0)
(0,1) | DIR_L | 4 | (0,5)
(0,1) | DIR_R | 1 | (0,0)
(0,2) | DIR_L | 3 | (0,5)
(0,2) | DIR_R | 2 | (0,0)
(0,3) | DIR_L | 2 | (0,5)
(0,3) | DIR_R | 3 | (0,0)
(0,4) | DIR_L | 1 | (0,5)
(0,4) | DIR_R | 4 | (0,0)
(0,5) | DIR_L | 0 | (0,5)
(0,5) | DIR_R | 0 | (0,5)
(3,0) | DIR_L | 0 | (3,0)
(3,0) | DIR_R | 0 | (3,0)
(3,1) | DIR_L | 4 | (3,5)
(3,1) | DIR_R | 1 | (3,0)
(3,2) | DIR_L | 3 | (3,5)
(3,2) | DIR_R | 2 | (3,0)
(3,3) | DIR_L | 2 | (3,5)
(3,3) | DIR_R | 3 | (3,0)
(3,4) | DIR_L | 1 | (3,5)
(3,4) | DIR_R | 4 | (3,0)
(3,5) | DIR_L | 0 | (3,5)
(3,5) | DIR_R | 0 | (3,5)
```

Train example 1: 40 rows, the first 30 shown
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2 2 2 2
1 2 2 2 2 1
1 1 2 2 1 1
1 2 2 2 2 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,0) | DIR_R | 0 | (0,0)
(0,1) | DIR_L | 4 | (0,5)
(0,1) | DIR_R | 1 | (0,0)
(0,2) | DIR_L | 3 | (0,5)
(0,2) | DIR_R | 2 | (0,0)
(0,3) | DIR_L | 2 | (0,5)
(0,3) | DIR_R | 3 | (0,0)
(0,4) | DIR_L | 1 | (0,5)
(0,4) | DIR_R | 4 | (0,0)
(0,5) | DIR_L | 0 | (0,5)
(0,5) | DIR_R | 0 | (0,5)
(1,0) | DIR_L | 1 | (1,1)
(1,1) | DIR_L | 0 | (1,1)
(1,1) | DIR_R | 0 | (1,1)
(1,2) | DIR_L | 2 | (1,4)
(1,2) | DIR_R | 1 | (1,1)
(1,3) | DIR_L | 1 | (1,4)
(1,3) | DIR_R | 2 | (1,1)
(1,4) | DIR_L | 0 | (1,4)
(1,4) | DIR_R | 0 | (1,4)
(1,5) | DIR_R | 1 | (1,4)
(2,0) | DIR_L | 2 | (2,2)
(2,1) | DIR_L | 1 | (2,2)
(2,2) | DIR_L | 0 | (2,2)
(2,2) | DIR_R | 0 | (2,2)
(2,3) | DIR_L | 0 | (2,3)
(2,3) | DIR_R | 0 | (2,3)
(2,4) | DIR_R | 1 | (2,3)
(2,5) | DIR_R | 2 | (2,3)
```

Train example 2: 32 rows, the first 30 shown
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
1 2 2 2 2 1
2 2 2 2 2 2
1 2 2 2 2 1
```
```
c0 | c1 | c2 | c3
(1,0) | DIR_L | 1 | (1,1)
(1,1) | DIR_L | 0 | (1,1)
(1,1) | DIR_R | 0 | (1,1)
(1,2) | DIR_L | 2 | (1,4)
(1,2) | DIR_R | 1 | (1,1)
(1,3) | DIR_L | 1 | (1,4)
(1,3) | DIR_R | 2 | (1,1)
(1,4) | DIR_L | 0 | (1,4)
(1,4) | DIR_R | 0 | (1,4)
(1,5) | DIR_R | 1 | (1,4)
(2,0) | DIR_L | 0 | (2,0)
(2,0) | DIR_R | 0 | (2,0)
(2,1) | DIR_L | 4 | (2,5)
(2,1) | DIR_R | 1 | (2,0)
(2,2) | DIR_L | 3 | (2,5)
(2,2) | DIR_R | 2 | (2,0)
(2,3) | DIR_L | 2 | (2,5)
(2,3) | DIR_R | 3 | (2,0)
(2,4) | DIR_L | 1 | (2,5)
(2,4) | DIR_R | 4 | (2,0)
(2,5) | DIR_L | 0 | (2,5)
(2,5) | DIR_R | 0 | (2,5)
(3,0) | DIR_L | 1 | (3,1)
(3,1) | DIR_L | 0 | (3,1)
(3,1) | DIR_R | 0 | (3,1)
(3,2) | DIR_L | 2 | (3,4)
(3,2) | DIR_R | 1 | (3,1)
(3,3) | DIR_L | 1 | (3,4)
(3,3) | DIR_R | 2 | (3,1)
(3,4) | DIR_L | 0 | (3,4)
```

Train example 3: 40 rows, the first 30 shown
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 2 2 1 1
1 2 2 2 2 1
2 2 2 2 2 2
1 2 2 2 2 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 2 | (0,2)
(0,1) | DIR_L | 1 | (0,2)
(0,2) | DIR_L | 0 | (0,2)
(0,2) | DIR_R | 0 | (0,2)
(0,3) | DIR_L | 0 | (0,3)
(0,3) | DIR_R | 0 | (0,3)
(0,4) | DIR_R | 1 | (0,3)
(0,5) | DIR_R | 2 | (0,3)
(1,0) | DIR_L | 1 | (1,1)
(1,1) | DIR_L | 0 | (1,1)
(1,1) | DIR_R | 0 | (1,1)
(1,2) | DIR_L | 2 | (1,4)
(1,2) | DIR_R | 1 | (1,1)
(1,3) | DIR_L | 1 | (1,4)
(1,3) | DIR_R | 2 | (1,1)
(1,4) | DIR_L | 0 | (1,4)
(1,4) | DIR_R | 0 | (1,4)
(1,5) | DIR_R | 1 | (1,4)
(2,0) | DIR_L | 0 | (2,0)
(2,0) | DIR_R | 0 | (2,0)
(2,1) | DIR_L | 4 | (2,5)
(2,1) | DIR_R | 1 | (2,0)
(2,2) | DIR_L | 3 | (2,5)
(2,2) | DIR_R | 2 | (2,0)
(2,3) | DIR_L | 2 | (2,5)
(2,3) | DIR_R | 3 | (2,0)
(2,4) | DIR_L | 1 | (2,5)
(2,4) | DIR_R | 4 | (2,0)
(2,5) | DIR_L | 0 | (2,5)
(2,5) | DIR_R | 0 | (2,5)
```

Train example 4: 44 rows, the first 30 shown
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2 2 2 2
1 2 2 2 2 1
1 2 2 2 2 1
2 2 2 2 2 2
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,0) | DIR_R | 0 | (0,0)
(0,1) | DIR_L | 4 | (0,5)
(0,1) | DIR_R | 1 | (0,0)
(0,2) | DIR_L | 3 | (0,5)
(0,2) | DIR_R | 2 | (0,0)
(0,3) | DIR_L | 2 | (0,5)
(0,3) | DIR_R | 3 | (0,0)
(0,4) | DIR_L | 1 | (0,5)
(0,4) | DIR_R | 4 | (0,0)
(0,5) | DIR_L | 0 | (0,5)
(0,5) | DIR_R | 0 | (0,5)
(1,0) | DIR_L | 1 | (1,1)
(1,1) | DIR_L | 0 | (1,1)
(1,1) | DIR_R | 0 | (1,1)
(1,2) | DIR_L | 2 | (1,4)
(1,2) | DIR_R | 1 | (1,1)
(1,3) | DIR_L | 1 | (1,4)
(1,3) | DIR_R | 2 | (1,1)
(1,4) | DIR_L | 0 | (1,4)
(1,4) | DIR_R | 0 | (1,4)
(1,5) | DIR_R | 1 | (1,4)
(2,0) | DIR_L | 1 | (2,1)
(2,1) | DIR_L | 0 | (2,1)
(2,1) | DIR_R | 0 | (2,1)
(2,2) | DIR_L | 2 | (2,4)
(2,2) | DIR_R | 1 | (2,1)
(2,3) | DIR_L | 1 | (2,4)
(2,3) | DIR_R | 2 | (2,1)
(2,4) | DIR_L | 0 | (2,4)
```

### &r4 (export table 6)

- columns: c0: Box, c1: Dir8, c2: Number, c3: Box
- depth 4, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 2

#### &r4, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [8, 16, 12, 16, 16]; test: 12

Train example 0: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 . . . . 0
2 . . . . 2
2 . . . . 2
0 . . . . 0
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,5) | DIR_T | 0 | (0,5)
(1,0) | DIR_T | 2 | (3,0)
(1,5) | DIR_T | 2 | (3,5)
(2,0) | DIR_B | 2 | (0,0)
(2,5) | DIR_B | 2 | (0,5)
(3,0) | DIR_B | 0 | (3,0)
(3,5) | DIR_B | 0 | (3,5)
```

Train example 1: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
. . . . . .
. 2 . . 2 .
1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,1) | DIR_T | 1 | (1,1)
(0,2) | DIR_T | 2 | (2,2)
(0,3) | DIR_T | 2 | (2,3)
(0,4) | DIR_T | 1 | (1,4)
(0,5) | DIR_T | 0 | (0,5)
(2,1) | DIR_T | 1 | (3,1)
(2,1) | DIR_B | 1 | (1,1)
(2,4) | DIR_T | 1 | (3,4)
(2,4) | DIR_B | 1 | (1,4)
(3,0) | DIR_B | 3 | (0,0)
(3,1) | DIR_B | 0 | (3,1)
(3,2) | DIR_B | 1 | (2,2)
(3,3) | DIR_B | 1 | (2,3)
(3,4) | DIR_B | 0 | (3,4)
(3,5) | DIR_B | 3 | (0,5)
```

Train example 2: 12 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 . . 1 1
. . . . . .
. 2 . . 2 .
1 1 . . 1 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 2 | (2,0)
(0,1) | DIR_T | 1 | (1,1)
(0,4) | DIR_T | 1 | (1,4)
(0,5) | DIR_T | 2 | (2,5)
(2,1) | DIR_T | 1 | (3,1)
(2,1) | DIR_B | 1 | (1,1)
(2,4) | DIR_T | 1 | (3,4)
(2,4) | DIR_B | 1 | (1,4)
(3,0) | DIR_B | 1 | (2,0)
(3,1) | DIR_B | 0 | (3,1)
(3,4) | DIR_B | 0 | (3,4)
(3,5) | DIR_B | 1 | (2,5)
```

Train example 3: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1
. . . . . .
. 2 . . 2 .
1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 2 | (2,0)
(0,1) | DIR_T | 1 | (1,1)
(0,2) | DIR_T | 0 | (0,2)
(0,3) | DIR_T | 0 | (0,3)
(0,4) | DIR_T | 1 | (1,4)
(0,5) | DIR_T | 2 | (2,5)
(2,1) | DIR_T | 1 | (3,1)
(2,1) | DIR_B | 1 | (1,1)
(2,4) | DIR_T | 1 | (3,4)
(2,4) | DIR_B | 1 | (1,4)
(3,0) | DIR_B | 1 | (2,0)
(3,1) | DIR_B | 0 | (3,1)
(3,2) | DIR_B | 3 | (0,2)
(3,3) | DIR_B | 3 | (0,3)
(3,4) | DIR_B | 0 | (3,4)
(3,5) | DIR_B | 1 | (2,5)
```

Train example 4: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 1 . . 1 0
2 0 . . 0 2
2 0 . . 0 2
0 1 . . 1 0
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,1) | DIR_T | 1 | (1,1)
(0,4) | DIR_T | 1 | (1,4)
(0,5) | DIR_T | 0 | (0,5)
(1,0) | DIR_T | 2 | (3,0)
(1,1) | DIR_B | 0 | (1,1)
(1,4) | DIR_B | 0 | (1,4)
(1,5) | DIR_T | 2 | (3,5)
(2,0) | DIR_B | 2 | (0,0)
(2,1) | DIR_T | 0 | (2,1)
(2,4) | DIR_T | 0 | (2,4)
(2,5) | DIR_B | 2 | (0,5)
(3,0) | DIR_B | 0 | (3,0)
(3,1) | DIR_B | 1 | (2,1)
(3,4) | DIR_B | 1 | (2,4)
(3,5) | DIR_B | 0 | (3,5)
```


#### &r4, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [8, 16, 12, 16, 16]; test: 12

Train example 0: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 4 . . 4 0
. . . . . .
. . . . . .
0 4 . . 4 0
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,1) | DIR_L | 4 | (0,5)
(0,4) | DIR_R | 4 | (0,0)
(0,5) | DIR_R | 0 | (0,5)
(3,0) | DIR_L | 0 | (3,0)
(3,1) | DIR_L | 4 | (3,5)
(3,4) | DIR_R | 4 | (3,0)
(3,5) | DIR_R | 0 | (3,5)
```

Train example 1: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 4 . . 4 0
1 . 2 2 . 1
2 . 0 0 . 2
1 . 2 2 . 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,1) | DIR_L | 4 | (0,5)
(0,4) | DIR_R | 4 | (0,0)
(0,5) | DIR_R | 0 | (0,5)
(1,0) | DIR_L | 1 | (1,1)
(1,2) | DIR_L | 2 | (1,4)
(1,3) | DIR_R | 2 | (1,1)
(1,5) | DIR_R | 1 | (1,4)
(2,0) | DIR_L | 2 | (2,2)
(2,2) | DIR_R | 0 | (2,2)
(2,3) | DIR_L | 0 | (2,3)
(2,5) | DIR_R | 2 | (2,3)
(3,0) | DIR_L | 1 | (3,1)
(3,2) | DIR_L | 2 | (3,4)
(3,3) | DIR_R | 2 | (3,1)
(3,5) | DIR_R | 1 | (3,4)
```

Train example 2: 12 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . .
1 . 2 2 . 1
0 4 . . 4 0
1 . 2 2 . 1
```
```
c0 | c1 | c2 | c3
(1,0) | DIR_L | 1 | (1,1)
(1,2) | DIR_L | 2 | (1,4)
(1,3) | DIR_R | 2 | (1,1)
(1,5) | DIR_R | 1 | (1,4)
(2,0) | DIR_L | 0 | (2,0)
(2,1) | DIR_L | 4 | (2,5)
(2,4) | DIR_R | 4 | (2,0)
(2,5) | DIR_R | 0 | (2,5)
(3,0) | DIR_L | 1 | (3,1)
(3,2) | DIR_L | 2 | (3,4)
(3,3) | DIR_R | 2 | (3,1)
(3,5) | DIR_R | 1 | (3,4)
```

Train example 3: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
2 . 0 0 . 2
1 . 2 2 . 1
0 4 . . 4 0
1 . 2 2 . 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 2 | (0,2)
(0,2) | DIR_R | 0 | (0,2)
(0,3) | DIR_L | 0 | (0,3)
(0,5) | DIR_R | 2 | (0,3)
(1,0) | DIR_L | 1 | (1,1)
(1,2) | DIR_L | 2 | (1,4)
(1,3) | DIR_R | 2 | (1,1)
(1,5) | DIR_R | 1 | (1,4)
(2,0) | DIR_L | 0 | (2,0)
(2,1) | DIR_L | 4 | (2,5)
(2,4) | DIR_R | 4 | (2,0)
(2,5) | DIR_R | 0 | (2,5)
(3,0) | DIR_L | 1 | (3,1)
(3,2) | DIR_L | 2 | (3,4)
(3,3) | DIR_R | 2 | (3,1)
(3,5) | DIR_R | 1 | (3,4)
```

Train example 4: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 4 . . 4 0
1 . 2 2 . 1
1 . 2 2 . 1
0 4 . . 4 0
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,1) | DIR_L | 4 | (0,5)
(0,4) | DIR_R | 4 | (0,0)
(0,5) | DIR_R | 0 | (0,5)
(1,0) | DIR_L | 1 | (1,1)
(1,2) | DIR_L | 2 | (1,4)
(1,3) | DIR_R | 2 | (1,1)
(1,5) | DIR_R | 1 | (1,4)
(2,0) | DIR_L | 1 | (2,1)
(2,2) | DIR_L | 2 | (2,4)
(2,3) | DIR_R | 2 | (2,1)
(2,5) | DIR_R | 1 | (2,4)
(3,0) | DIR_L | 0 | (3,0)
(3,1) | DIR_L | 4 | (3,5)
(3,4) | DIR_R | 4 | (3,0)
(3,5) | DIR_R | 0 | (3,5)
```

### &r7 (export table 7)

- columns: c0: Dir8
- depth 2, candidate keys none
- DETs its entries are assigned: &r0; assignments: 2

#### &r7, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [2, 2, 2, 2, 2]; test: 2

Train example 0: 2 rows
```
c0
DIR_T
DIR_B
```

Train example 1: 2 rows
```
c0
DIR_T
DIR_B
```

Train example 2: 2 rows
```
c0
DIR_T
DIR_B
```

Train example 3: 2 rows
```
c0
DIR_T
DIR_B
```

Train example 4: 2 rows
```
c0
DIR_T
DIR_B
```


#### &r7, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [2, 2, 2, 2, 2]; test: 2

Train example 0: 2 rows
```
c0
DIR_L
DIR_R
```

Train example 1: 2 rows
```
c0
DIR_L
DIR_R
```

Train example 2: 2 rows
```
c0
DIR_L
DIR_R
```

Train example 3: 2 rows
```
c0
DIR_L
DIR_R
```

Train example 4: 2 rows
```
c0
DIR_L
DIR_R
```

```
INIT Ray [:0] SKIP [:1] &r2 :1 * [L0] END [:0] END [:1] L0 END [:2] input :0 * [L1] END [:0] END [:1] L1 END [:3] &r0 :0 * [L2] axis_of :0 * [L3] :1 L2 END [:0] END [:1] L3 END [&r8] [&r9] [&r10] [&r11] [&r12]
```

### &r8 (export table 8)

- columns: c0: Box, c1: Dir8, c2: Number, c3: Box
- depth 4, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 2

#### &r8, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [20, 40, 30, 40, 40]; test: 30

Train example 0: 20 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
3 . . . . 3
2 . . . . 2
2 . . . . 2
3 . . . . 3
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,0) | DIR_T | 3 | (3,0)
(0,0) | DIR_B | 0 | (0,0)
(0,5) | DIR_T | 0 | (0,5)
(0,5) | DIR_T | 3 | (3,5)
(0,5) | DIR_B | 0 | (0,5)
(1,0) | DIR_T | 2 | (3,0)
(1,0) | DIR_B | 1 | (0,0)
(1,5) | DIR_T | 2 | (3,5)
(1,5) | DIR_B | 1 | (0,5)
(2,0) | DIR_T | 1 | (3,0)
(2,0) | DIR_B | 2 | (0,0)
(2,5) | DIR_T | 1 | (3,5)
(2,5) | DIR_B | 2 | (0,5)
(3,0) | DIR_T | 0 | (3,0)
(3,0) | DIR_B | 0 | (3,0)
(3,0) | DIR_B | 3 | (0,0)
(3,5) | DIR_T | 0 | (3,5)
(3,5) | DIR_B | 0 | (3,5)
(3,5) | DIR_B | 3 | (0,5)
```

Train example 1: 40 rows, the first 30 shown
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 1 1 2 2
1 3 1 1 3 1
1 2 2 2 2 1
1 3 1 1 3 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,0) | DIR_B | 0 | (0,0)
(0,1) | DIR_T | 1 | (1,1)
(0,1) | DIR_T | 3 | (3,1)
(0,2) | DIR_T | 2 | (2,2)
(0,3) | DIR_T | 2 | (2,3)
(0,4) | DIR_T | 1 | (1,4)
(0,4) | DIR_T | 3 | (3,4)
(0,5) | DIR_T | 0 | (0,5)
(0,5) | DIR_B | 0 | (0,5)
(1,0) | DIR_B | 1 | (0,0)
(1,1) | DIR_T | 0 | (1,1)
(1,1) | DIR_T | 2 | (3,1)
(1,1) | DIR_B | 0 | (1,1)
(1,2) | DIR_T | 1 | (2,2)
(1,3) | DIR_T | 1 | (2,3)
(1,4) | DIR_T | 0 | (1,4)
(1,4) | DIR_T | 2 | (3,4)
(1,4) | DIR_B | 0 | (1,4)
(1,5) | DIR_B | 1 | (0,5)
(2,0) | DIR_B | 2 | (0,0)
(2,1) | DIR_T | 1 | (3,1)
(2,1) | DIR_B | 1 | (1,1)
(2,2) | DIR_T | 0 | (2,2)
(2,2) | DIR_B | 0 | (2,2)
(2,3) | DIR_T | 0 | (2,3)
(2,3) | DIR_B | 0 | (2,3)
(2,4) | DIR_T | 1 | (3,4)
(2,4) | DIR_B | 1 | (1,4)
(2,5) | DIR_B | 2 | (0,5)
```

Train example 2: 30 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 2 . . 2 1
1 3 . . 3 1
2 2 . . 2 2
1 3 . . 3 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 2 | (2,0)
(0,1) | DIR_T | 1 | (1,1)
(0,1) | DIR_T | 3 | (3,1)
(0,4) | DIR_T | 1 | (1,4)
(0,4) | DIR_T | 3 | (3,4)
(0,5) | DIR_T | 2 | (2,5)
(1,0) | DIR_T | 1 | (2,0)
(1,1) | DIR_T | 0 | (1,1)
(1,1) | DIR_T | 2 | (3,1)
(1,1) | DIR_B | 0 | (1,1)
(1,4) | DIR_T | 0 | (1,4)
(1,4) | DIR_T | 2 | (3,4)
(1,4) | DIR_B | 0 | (1,4)
(1,5) | DIR_T | 1 | (2,5)
(2,0) | DIR_T | 0 | (2,0)
(2,0) | DIR_B | 0 | (2,0)
(2,1) | DIR_T | 1 | (3,1)
(2,1) | DIR_B | 1 | (1,1)
(2,4) | DIR_T | 1 | (3,4)
(2,4) | DIR_B | 1 | (1,4)
(2,5) | DIR_T | 0 | (2,5)
(2,5) | DIR_B | 0 | (2,5)
(3,0) | DIR_B | 1 | (2,0)
(3,1) | DIR_T | 0 | (3,1)
(3,1) | DIR_B | 0 | (3,1)
(3,1) | DIR_B | 2 | (1,1)
(3,4) | DIR_T | 0 | (3,4)
(3,4) | DIR_B | 0 | (3,4)
(3,4) | DIR_B | 2 | (1,4)
(3,5) | DIR_B | 1 | (2,5)
```

Train example 3: 40 rows, the first 30 shown
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 2 2 2 2 1
1 3 1 1 3 1
2 2 1 1 2 2
1 3 1 1 3 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 2 | (2,0)
(0,1) | DIR_T | 1 | (1,1)
(0,1) | DIR_T | 3 | (3,1)
(0,2) | DIR_T | 0 | (0,2)
(0,2) | DIR_B | 0 | (0,2)
(0,3) | DIR_T | 0 | (0,3)
(0,3) | DIR_B | 0 | (0,3)
(0,4) | DIR_T | 1 | (1,4)
(0,4) | DIR_T | 3 | (3,4)
(0,5) | DIR_T | 2 | (2,5)
(1,0) | DIR_T | 1 | (2,0)
(1,1) | DIR_T | 0 | (1,1)
(1,1) | DIR_T | 2 | (3,1)
(1,1) | DIR_B | 0 | (1,1)
(1,2) | DIR_B | 1 | (0,2)
(1,3) | DIR_B | 1 | (0,3)
(1,4) | DIR_T | 0 | (1,4)
(1,4) | DIR_T | 2 | (3,4)
(1,4) | DIR_B | 0 | (1,4)
(1,5) | DIR_T | 1 | (2,5)
(2,0) | DIR_T | 0 | (2,0)
(2,0) | DIR_B | 0 | (2,0)
(2,1) | DIR_T | 1 | (3,1)
(2,1) | DIR_B | 1 | (1,1)
(2,2) | DIR_B | 2 | (0,2)
(2,3) | DIR_B | 2 | (0,3)
(2,4) | DIR_T | 1 | (3,4)
(2,4) | DIR_B | 1 | (1,4)
(2,5) | DIR_T | 0 | (2,5)
(2,5) | DIR_B | 0 | (2,5)
```

Train example 4: 40 rows, the first 30 shown
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
3 2 . . 2 3
2 3 . . 3 2
2 3 . . 3 2
3 2 . . 2 3
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,0) | DIR_T | 3 | (3,0)
(0,0) | DIR_B | 0 | (0,0)
(0,1) | DIR_T | 1 | (1,1)
(0,1) | DIR_T | 2 | (2,1)
(0,4) | DIR_T | 1 | (1,4)
(0,4) | DIR_T | 2 | (2,4)
(0,5) | DIR_T | 0 | (0,5)
(0,5) | DIR_T | 3 | (3,5)
(0,5) | DIR_B | 0 | (0,5)
(1,0) | DIR_T | 2 | (3,0)
(1,0) | DIR_B | 1 | (0,0)
(1,1) | DIR_T | 0 | (1,1)
(1,1) | DIR_T | 1 | (2,1)
(1,1) | DIR_B | 0 | (1,1)
(1,4) | DIR_T | 0 | (1,4)
(1,4) | DIR_T | 1 | (2,4)
(1,4) | DIR_B | 0 | (1,4)
(1,5) | DIR_T | 2 | (3,5)
(1,5) | DIR_B | 1 | (0,5)
(2,0) | DIR_T | 1 | (3,0)
(2,0) | DIR_B | 2 | (0,0)
(2,1) | DIR_T | 0 | (2,1)
(2,1) | DIR_B | 0 | (2,1)
(2,1) | DIR_B | 1 | (1,1)
(2,4) | DIR_T | 0 | (2,4)
(2,4) | DIR_B | 0 | (2,4)
(2,4) | DIR_B | 1 | (1,4)
(2,5) | DIR_T | 1 | (3,5)
(2,5) | DIR_B | 2 | (0,5)
```


#### &r8, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [28, 56, 42, 56, 56]; test: 42

Train example 0: 28 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
3 2 2 2 2 3
. . . . . .
. . . . . .
3 2 2 2 2 3
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,0) | DIR_L | 5 | (0,5)
(0,0) | DIR_R | 0 | (0,0)
(0,1) | DIR_L | 4 | (0,5)
(0,1) | DIR_R | 1 | (0,0)
(0,2) | DIR_L | 3 | (0,5)
(0,2) | DIR_R | 2 | (0,0)
(0,3) | DIR_L | 2 | (0,5)
(0,3) | DIR_R | 3 | (0,0)
(0,4) | DIR_L | 1 | (0,5)
(0,4) | DIR_R | 4 | (0,0)
(0,5) | DIR_L | 0 | (0,5)
(0,5) | DIR_R | 0 | (0,5)
(0,5) | DIR_R | 5 | (0,0)
(3,0) | DIR_L | 0 | (3,0)
(3,0) | DIR_L | 5 | (3,5)
(3,0) | DIR_R | 0 | (3,0)
(3,1) | DIR_L | 4 | (3,5)
(3,1) | DIR_R | 1 | (3,0)
(3,2) | DIR_L | 3 | (3,5)
(3,2) | DIR_R | 2 | (3,0)
(3,3) | DIR_L | 2 | (3,5)
(3,3) | DIR_R | 3 | (3,0)
(3,4) | DIR_L | 1 | (3,5)
(3,4) | DIR_R | 4 | (3,0)
(3,5) | DIR_L | 0 | (3,5)
(3,5) | DIR_R | 0 | (3,5)
(3,5) | DIR_R | 5 | (3,0)
```

Train example 1: 56 rows, the first 30 shown
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
3 2 2 2 2 3
2 3 2 2 3 2
2 2 3 3 2 2
2 3 2 2 3 2
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,0) | DIR_L | 5 | (0,5)
(0,0) | DIR_R | 0 | (0,0)
(0,1) | DIR_L | 4 | (0,5)
(0,1) | DIR_R | 1 | (0,0)
(0,2) | DIR_L | 3 | (0,5)
(0,2) | DIR_R | 2 | (0,0)
(0,3) | DIR_L | 2 | (0,5)
(0,3) | DIR_R | 3 | (0,0)
(0,4) | DIR_L | 1 | (0,5)
(0,4) | DIR_R | 4 | (0,0)
(0,5) | DIR_L | 0 | (0,5)
(0,5) | DIR_R | 0 | (0,5)
(0,5) | DIR_R | 5 | (0,0)
(1,0) | DIR_L | 1 | (1,1)
(1,0) | DIR_L | 4 | (1,4)
(1,1) | DIR_L | 0 | (1,1)
(1,1) | DIR_L | 3 | (1,4)
(1,1) | DIR_R | 0 | (1,1)
(1,2) | DIR_L | 2 | (1,4)
(1,2) | DIR_R | 1 | (1,1)
(1,3) | DIR_L | 1 | (1,4)
(1,3) | DIR_R | 2 | (1,1)
(1,4) | DIR_L | 0 | (1,4)
(1,4) | DIR_R | 0 | (1,4)
(1,4) | DIR_R | 3 | (1,1)
(1,5) | DIR_R | 1 | (1,4)
(1,5) | DIR_R | 4 | (1,1)
(2,0) | DIR_L | 2 | (2,2)
(2,0) | DIR_L | 3 | (2,3)
```

Train example 2: 42 rows, the first 30 shown
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
2 3 2 2 3 2
3 2 2 2 2 3
2 3 2 2 3 2
```
```
c0 | c1 | c2 | c3
(1,0) | DIR_L | 1 | (1,1)
(1,0) | DIR_L | 4 | (1,4)
(1,1) | DIR_L | 0 | (1,1)
(1,1) | DIR_L | 3 | (1,4)
(1,1) | DIR_R | 0 | (1,1)
(1,2) | DIR_L | 2 | (1,4)
(1,2) | DIR_R | 1 | (1,1)
(1,3) | DIR_L | 1 | (1,4)
(1,3) | DIR_R | 2 | (1,1)
(1,4) | DIR_L | 0 | (1,4)
(1,4) | DIR_R | 0 | (1,4)
(1,4) | DIR_R | 3 | (1,1)
(1,5) | DIR_R | 1 | (1,4)
(1,5) | DIR_R | 4 | (1,1)
(2,0) | DIR_L | 0 | (2,0)
(2,0) | DIR_L | 5 | (2,5)
(2,0) | DIR_R | 0 | (2,0)
(2,1) | DIR_L | 4 | (2,5)
(2,1) | DIR_R | 1 | (2,0)
(2,2) | DIR_L | 3 | (2,5)
(2,2) | DIR_R | 2 | (2,0)
(2,3) | DIR_L | 2 | (2,5)
(2,3) | DIR_R | 3 | (2,0)
(2,4) | DIR_L | 1 | (2,5)
(2,4) | DIR_R | 4 | (2,0)
(2,5) | DIR_L | 0 | (2,5)
(2,5) | DIR_R | 0 | (2,5)
(2,5) | DIR_R | 5 | (2,0)
(3,0) | DIR_L | 1 | (3,1)
(3,0) | DIR_L | 4 | (3,4)
```

Train example 3: 56 rows, the first 30 shown
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 3 3 2 2
2 3 2 2 3 2
3 2 2 2 2 3
2 3 2 2 3 2
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 2 | (0,2)
(0,0) | DIR_L | 3 | (0,3)
(0,1) | DIR_L | 1 | (0,2)
(0,1) | DIR_L | 2 | (0,3)
(0,2) | DIR_L | 0 | (0,2)
(0,2) | DIR_L | 1 | (0,3)
(0,2) | DIR_R | 0 | (0,2)
(0,3) | DIR_L | 0 | (0,3)
(0,3) | DIR_R | 0 | (0,3)
(0,3) | DIR_R | 1 | (0,2)
(0,4) | DIR_R | 1 | (0,3)
(0,4) | DIR_R | 2 | (0,2)
(0,5) | DIR_R | 2 | (0,3)
(0,5) | DIR_R | 3 | (0,2)
(1,0) | DIR_L | 1 | (1,1)
(1,0) | DIR_L | 4 | (1,4)
(1,1) | DIR_L | 0 | (1,1)
(1,1) | DIR_L | 3 | (1,4)
(1,1) | DIR_R | 0 | (1,1)
(1,2) | DIR_L | 2 | (1,4)
(1,2) | DIR_R | 1 | (1,1)
(1,3) | DIR_L | 1 | (1,4)
(1,3) | DIR_R | 2 | (1,1)
(1,4) | DIR_L | 0 | (1,4)
(1,4) | DIR_R | 0 | (1,4)
(1,4) | DIR_R | 3 | (1,1)
(1,5) | DIR_R | 1 | (1,4)
(1,5) | DIR_R | 4 | (1,1)
(2,0) | DIR_L | 0 | (2,0)
(2,0) | DIR_L | 5 | (2,5)
```

Train example 4: 56 rows, the first 30 shown
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
3 2 2 2 2 3
2 3 2 2 3 2
2 3 2 2 3 2
3 2 2 2 2 3
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,0) | DIR_L | 5 | (0,5)
(0,0) | DIR_R | 0 | (0,0)
(0,1) | DIR_L | 4 | (0,5)
(0,1) | DIR_R | 1 | (0,0)
(0,2) | DIR_L | 3 | (0,5)
(0,2) | DIR_R | 2 | (0,0)
(0,3) | DIR_L | 2 | (0,5)
(0,3) | DIR_R | 3 | (0,0)
(0,4) | DIR_L | 1 | (0,5)
(0,4) | DIR_R | 4 | (0,0)
(0,5) | DIR_L | 0 | (0,5)
(0,5) | DIR_R | 0 | (0,5)
(0,5) | DIR_R | 5 | (0,0)
(1,0) | DIR_L | 1 | (1,1)
(1,0) | DIR_L | 4 | (1,4)
(1,1) | DIR_L | 0 | (1,1)
(1,1) | DIR_L | 3 | (1,4)
(1,1) | DIR_R | 0 | (1,1)
(1,2) | DIR_L | 2 | (1,4)
(1,2) | DIR_R | 1 | (1,1)
(1,3) | DIR_L | 1 | (1,4)
(1,3) | DIR_R | 2 | (1,1)
(1,4) | DIR_L | 0 | (1,4)
(1,4) | DIR_R | 0 | (1,4)
(1,4) | DIR_R | 3 | (1,1)
(1,5) | DIR_R | 1 | (1,4)
(1,5) | DIR_R | 4 | (1,1)
(2,0) | DIR_L | 1 | (2,1)
(2,0) | DIR_L | 4 | (2,4)
```

### &r9 (export table 9)

- columns: c0: Box, c1: Dir8, c2: Number, c3: Box
- depth 4, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 2

#### &r9, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [8, 16, 12, 16, 16]; test: 12

Train example 0: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 . . . . 2
. . . . . .
. . . . . .
2 . . . . 2
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,0) | DIR_T | 3 | (3,0)
(0,5) | DIR_T | 0 | (0,5)
(0,5) | DIR_T | 3 | (3,5)
(3,0) | DIR_B | 0 | (3,0)
(3,0) | DIR_B | 3 | (0,0)
(3,5) | DIR_B | 0 | (3,5)
(3,5) | DIR_B | 3 | (0,5)
```

Train example 1: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 2 1 1 2 1
. . . . . .
. . . . . .
1 2 1 1 2 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,1) | DIR_T | 1 | (1,1)
(0,1) | DIR_T | 3 | (3,1)
(0,2) | DIR_T | 2 | (2,2)
(0,3) | DIR_T | 2 | (2,3)
(0,4) | DIR_T | 1 | (1,4)
(0,4) | DIR_T | 3 | (3,4)
(0,5) | DIR_T | 0 | (0,5)
(3,0) | DIR_B | 3 | (0,0)
(3,1) | DIR_B | 0 | (3,1)
(3,1) | DIR_B | 2 | (1,1)
(3,2) | DIR_B | 1 | (2,2)
(3,3) | DIR_B | 1 | (2,3)
(3,4) | DIR_B | 0 | (3,4)
(3,4) | DIR_B | 2 | (1,4)
(3,5) | DIR_B | 3 | (0,5)
```

Train example 2: 12 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 2 . . 2 1
. . . . . .
. . . . . .
1 2 . . 2 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 2 | (2,0)
(0,1) | DIR_T | 1 | (1,1)
(0,1) | DIR_T | 3 | (3,1)
(0,4) | DIR_T | 1 | (1,4)
(0,4) | DIR_T | 3 | (3,4)
(0,5) | DIR_T | 2 | (2,5)
(3,0) | DIR_B | 1 | (2,0)
(3,1) | DIR_B | 0 | (3,1)
(3,1) | DIR_B | 2 | (1,1)
(3,4) | DIR_B | 0 | (3,4)
(3,4) | DIR_B | 2 | (1,4)
(3,5) | DIR_B | 1 | (2,5)
```

Train example 3: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 2 1 1 2 1
. . . . . .
. . . . . .
1 2 1 1 2 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 2 | (2,0)
(0,1) | DIR_T | 1 | (1,1)
(0,1) | DIR_T | 3 | (3,1)
(0,2) | DIR_T | 0 | (0,2)
(0,3) | DIR_T | 0 | (0,3)
(0,4) | DIR_T | 1 | (1,4)
(0,4) | DIR_T | 3 | (3,4)
(0,5) | DIR_T | 2 | (2,5)
(3,0) | DIR_B | 1 | (2,0)
(3,1) | DIR_B | 0 | (3,1)
(3,1) | DIR_B | 2 | (1,1)
(3,2) | DIR_B | 3 | (0,2)
(3,3) | DIR_B | 3 | (0,3)
(3,4) | DIR_B | 0 | (3,4)
(3,4) | DIR_B | 2 | (1,4)
(3,5) | DIR_B | 1 | (2,5)
```

Train example 4: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 . . 2 2
. . . . . .
. . . . . .
2 2 . . 2 2
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,0) | DIR_T | 3 | (3,0)
(0,1) | DIR_T | 1 | (1,1)
(0,1) | DIR_T | 2 | (2,1)
(0,4) | DIR_T | 1 | (1,4)
(0,4) | DIR_T | 2 | (2,4)
(0,5) | DIR_T | 0 | (0,5)
(0,5) | DIR_T | 3 | (3,5)
(3,0) | DIR_B | 0 | (3,0)
(3,0) | DIR_B | 3 | (0,0)
(3,1) | DIR_B | 1 | (2,1)
(3,1) | DIR_B | 2 | (1,1)
(3,4) | DIR_B | 1 | (2,4)
(3,4) | DIR_B | 2 | (1,4)
(3,5) | DIR_B | 0 | (3,5)
(3,5) | DIR_B | 3 | (0,5)
```


#### &r9, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [8, 16, 12, 16, 16]; test: 12

Train example 0: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 . . . . 2
. . . . . .
. . . . . .
2 . . . . 2
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,0) | DIR_L | 5 | (0,5)
(0,5) | DIR_R | 0 | (0,5)
(0,5) | DIR_R | 5 | (0,0)
(3,0) | DIR_L | 0 | (3,0)
(3,0) | DIR_L | 5 | (3,5)
(3,5) | DIR_R | 0 | (3,5)
(3,5) | DIR_R | 5 | (3,0)
```

Train example 1: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 . . . . 2
2 . . . . 2
2 . . . . 2
2 . . . . 2
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,0) | DIR_L | 5 | (0,5)
(0,5) | DIR_R | 0 | (0,5)
(0,5) | DIR_R | 5 | (0,0)
(1,0) | DIR_L | 1 | (1,1)
(1,0) | DIR_L | 4 | (1,4)
(1,5) | DIR_R | 1 | (1,4)
(1,5) | DIR_R | 4 | (1,1)
(2,0) | DIR_L | 2 | (2,2)
(2,0) | DIR_L | 3 | (2,3)
(2,5) | DIR_R | 2 | (2,3)
(2,5) | DIR_R | 3 | (2,2)
(3,0) | DIR_L | 1 | (3,1)
(3,0) | DIR_L | 4 | (3,4)
(3,5) | DIR_R | 1 | (3,4)
(3,5) | DIR_R | 4 | (3,1)
```

Train example 2: 12 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
2 . . . . 2
2 . . . . 2
2 . . . . 2
```
```
c0 | c1 | c2 | c3
(1,0) | DIR_L | 1 | (1,1)
(1,0) | DIR_L | 4 | (1,4)
(1,5) | DIR_R | 1 | (1,4)
(1,5) | DIR_R | 4 | (1,1)
(2,0) | DIR_L | 0 | (2,0)
(2,0) | DIR_L | 5 | (2,5)
(2,5) | DIR_R | 0 | (2,5)
(2,5) | DIR_R | 5 | (2,0)
(3,0) | DIR_L | 1 | (3,1)
(3,0) | DIR_L | 4 | (3,4)
(3,5) | DIR_R | 1 | (3,4)
(3,5) | DIR_R | 4 | (3,1)
```

Train example 3: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 . . . . 2
2 . . . . 2
2 . . . . 2
2 . . . . 2
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 2 | (0,2)
(0,0) | DIR_L | 3 | (0,3)
(0,5) | DIR_R | 2 | (0,3)
(0,5) | DIR_R | 3 | (0,2)
(1,0) | DIR_L | 1 | (1,1)
(1,0) | DIR_L | 4 | (1,4)
(1,5) | DIR_R | 1 | (1,4)
(1,5) | DIR_R | 4 | (1,1)
(2,0) | DIR_L | 0 | (2,0)
(2,0) | DIR_L | 5 | (2,5)
(2,5) | DIR_R | 0 | (2,5)
(2,5) | DIR_R | 5 | (2,0)
(3,0) | DIR_L | 1 | (3,1)
(3,0) | DIR_L | 4 | (3,4)
(3,5) | DIR_R | 1 | (3,4)
(3,5) | DIR_R | 4 | (3,1)
```

Train example 4: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 . . . . 2
2 . . . . 2
2 . . . . 2
2 . . . . 2
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,0) | DIR_L | 5 | (0,5)
(0,5) | DIR_R | 0 | (0,5)
(0,5) | DIR_R | 5 | (0,0)
(1,0) | DIR_L | 1 | (1,1)
(1,0) | DIR_L | 4 | (1,4)
(1,5) | DIR_R | 1 | (1,4)
(1,5) | DIR_R | 4 | (1,1)
(2,0) | DIR_L | 1 | (2,1)
(2,0) | DIR_L | 4 | (2,4)
(2,5) | DIR_R | 1 | (2,4)
(2,5) | DIR_R | 4 | (2,1)
(3,0) | DIR_L | 0 | (3,0)
(3,0) | DIR_L | 5 | (3,5)
(3,5) | DIR_R | 0 | (3,5)
(3,5) | DIR_R | 5 | (3,0)
```

### &r12 (export table 10)

- columns: c0: Dir8
- depth 2, candidate keys none
- DETs its entries are assigned: &r0; assignments: 2

#### &r12, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [2, 2, 2, 2, 2]; test: 2

Train example 0: 2 rows
```
c0
DIR_T
DIR_B
```

Train example 1: 2 rows
```
c0
DIR_T
DIR_B
```

Train example 2: 2 rows
```
c0
DIR_T
DIR_B
```

Train example 3: 2 rows
```
c0
DIR_T
DIR_B
```

Train example 4: 2 rows
```
c0
DIR_T
DIR_B
```


#### &r12, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [2, 2, 2, 2, 2]; test: 2

Train example 0: 2 rows
```
c0
DIR_L
DIR_R
```

Train example 1: 2 rows
```
c0
DIR_L
DIR_R
```

Train example 2: 2 rows
```
c0
DIR_L
DIR_R
```

Train example 3: 2 rows
```
c0
DIR_L
DIR_R
```

Train example 4: 2 rows
```
c0
DIR_L
DIR_R
```

```
RULE &r4 :1 * [L0] :2 * [L1] :4 * [L2] neighbor :0 L0 :1 L1 :2 * [L3] &r8 :1 L3 :2 L1 :3 * [L4] :4 L2 END [&r13]
```

### &r13 (export table 11)

- columns: c0: Box, c1: Dir8, c2: Box, c3: Number, c4: Box
- depth 5, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 2

#### &r13, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [4, 4, 4, 4, 8]; test: 4

Train example 0: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . .
3 . . . . 3
3 . . . . 3
. . . . . .
```
```
c0 | c1 | c2 | c3 | c4
(1,0) | DIR_T | (0,0) | 3 | (3,0)
(1,5) | DIR_T | (0,5) | 3 | (3,5)
(2,0) | DIR_B | (3,0) | 3 | (0,0)
(2,5) | DIR_B | (3,5) | 3 | (0,5)
```

Train example 1: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . . . . .
. 2 . . 2 .
. . . . . .
```
```
c0 | c1 | c2 | c3 | c4
(2,1) | DIR_T | (1,1) | 2 | (3,1)
(2,1) | DIR_B | (3,1) | 2 | (1,1)
(2,4) | DIR_T | (1,4) | 2 | (3,4)
(2,4) | DIR_B | (3,4) | 2 | (1,4)
```

Train example 2: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . . . . .
. 2 . . 2 .
. . . . . .
```
```
c0 | c1 | c2 | c3 | c4
(2,1) | DIR_T | (1,1) | 2 | (3,1)
(2,1) | DIR_B | (3,1) | 2 | (1,1)
(2,4) | DIR_T | (1,4) | 2 | (3,4)
(2,4) | DIR_B | (3,4) | 2 | (1,4)
```

Train example 3: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . . . . .
. 2 . . 2 .
. . . . . .
```
```
c0 | c1 | c2 | c3 | c4
(2,1) | DIR_T | (1,1) | 2 | (3,1)
(2,1) | DIR_B | (3,1) | 2 | (1,1)
(2,4) | DIR_T | (1,4) | 2 | (3,4)
(2,4) | DIR_B | (3,4) | 2 | (1,4)
```

Train example 4: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . .
3 1 . . 1 3
3 1 . . 1 3
. . . . . .
```
```
c0 | c1 | c2 | c3 | c4
(1,0) | DIR_T | (0,0) | 3 | (3,0)
(1,1) | DIR_B | (2,1) | 1 | (1,1)
(1,4) | DIR_B | (2,4) | 1 | (1,4)
(1,5) | DIR_T | (0,5) | 3 | (3,5)
(2,0) | DIR_B | (3,0) | 3 | (0,0)
(2,1) | DIR_T | (1,1) | 1 | (2,1)
(2,4) | DIR_T | (1,4) | 1 | (2,4)
(2,5) | DIR_B | (3,5) | 3 | (0,5)
```


#### &r13, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [4, 8, 6, 8, 8]; test: 6

Train example 0: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. 5 . . 5 .
. . . . . .
. . . . . .
. 5 . . 5 .
```
```
c0 | c1 | c2 | c3 | c4
(0,1) | DIR_L | (0,0) | 5 | (0,5)
(0,4) | DIR_R | (0,5) | 5 | (0,0)
(3,1) | DIR_L | (3,0) | 5 | (3,5)
(3,4) | DIR_R | (3,5) | 5 | (3,0)
```

Train example 1: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. 5 . . 5 .
. . 3 3 . .
. . 1 1 . .
. . 3 3 . .
```
```
c0 | c1 | c2 | c3 | c4
(0,1) | DIR_L | (0,0) | 5 | (0,5)
(0,4) | DIR_R | (0,5) | 5 | (0,0)
(1,2) | DIR_L | (1,1) | 3 | (1,4)
(1,3) | DIR_R | (1,4) | 3 | (1,1)
(2,2) | DIR_R | (2,3) | 1 | (2,2)
(2,3) | DIR_L | (2,2) | 1 | (2,3)
(3,2) | DIR_L | (3,1) | 3 | (3,4)
(3,3) | DIR_R | (3,4) | 3 | (3,1)
```

Train example 2: 6 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . .
. . 3 3 . .
. 5 . . 5 .
. . 3 3 . .
```
```
c0 | c1 | c2 | c3 | c4
(1,2) | DIR_L | (1,1) | 3 | (1,4)
(1,3) | DIR_R | (1,4) | 3 | (1,1)
(2,1) | DIR_L | (2,0) | 5 | (2,5)
(2,4) | DIR_R | (2,5) | 5 | (2,0)
(3,2) | DIR_L | (3,1) | 3 | (3,4)
(3,3) | DIR_R | (3,4) | 3 | (3,1)
```

Train example 3: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . 1 1 . .
. . 3 3 . .
. 5 . . 5 .
. . 3 3 . .
```
```
c0 | c1 | c2 | c3 | c4
(0,2) | DIR_R | (0,3) | 1 | (0,2)
(0,3) | DIR_L | (0,2) | 1 | (0,3)
(1,2) | DIR_L | (1,1) | 3 | (1,4)
(1,3) | DIR_R | (1,4) | 3 | (1,1)
(2,1) | DIR_L | (2,0) | 5 | (2,5)
(2,4) | DIR_R | (2,5) | 5 | (2,0)
(3,2) | DIR_L | (3,1) | 3 | (3,4)
(3,3) | DIR_R | (3,4) | 3 | (3,1)
```

Train example 4: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. 5 . . 5 .
. . 3 3 . .
. . 3 3 . .
. 5 . . 5 .
```
```
c0 | c1 | c2 | c3 | c4
(0,1) | DIR_L | (0,0) | 5 | (0,5)
(0,4) | DIR_R | (0,5) | 5 | (0,0)
(1,2) | DIR_L | (1,1) | 3 | (1,4)
(1,3) | DIR_R | (1,4) | 3 | (1,1)
(2,2) | DIR_L | (2,1) | 3 | (2,4)
(2,3) | DIR_R | (2,4) | 3 | (2,1)
(3,1) | DIR_L | (3,0) | 5 | (3,5)
(3,4) | DIR_R | (3,5) | 5 | (3,0)
```

```
RULE &r13 :1 * [L0] :2 * [L1] :3 * [L2] :4 * [L3] END [&r14]
```

### &r14 (export table 12)

- columns: c0: Dir8, c1: Box, c2: Number, c3: Box
- depth 6, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 2

#### &r14, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [4, 4, 4, 4, 8]; test: 4

Train example 0: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
3 . . . . 3
. . . . . .
. . . . . .
3 . . . . 3
```
```
c0 | c1 | c2 | c3
DIR_T | (0,0) | 3 | (3,0)
DIR_T | (0,5) | 3 | (3,5)
DIR_B | (3,0) | 3 | (0,0)
DIR_B | (3,5) | 3 | (0,5)
```

Train example 1: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . .
. 2 . . 2 .
. . . . . .
. 2 . . 2 .
```
```
c0 | c1 | c2 | c3
DIR_T | (1,1) | 2 | (3,1)
DIR_T | (1,4) | 2 | (3,4)
DIR_B | (3,1) | 2 | (1,1)
DIR_B | (3,4) | 2 | (1,4)
```

Train example 2: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . .
. 2 . . 2 .
. . . . . .
. 2 . . 2 .
```
```
c0 | c1 | c2 | c3
DIR_T | (1,1) | 2 | (3,1)
DIR_T | (1,4) | 2 | (3,4)
DIR_B | (3,1) | 2 | (1,1)
DIR_B | (3,4) | 2 | (1,4)
```

Train example 3: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . .
. 2 . . 2 .
. . . . . .
. 2 . . 2 .
```
```
c0 | c1 | c2 | c3
DIR_T | (1,1) | 2 | (3,1)
DIR_T | (1,4) | 2 | (3,4)
DIR_B | (3,1) | 2 | (1,1)
DIR_B | (3,4) | 2 | (1,4)
```

Train example 4: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
3 . . . . 3
. 1 . . 1 .
. 1 . . 1 .
3 . . . . 3
```
```
c0 | c1 | c2 | c3
DIR_T | (0,0) | 3 | (3,0)
DIR_T | (0,5) | 3 | (3,5)
DIR_T | (1,1) | 1 | (2,1)
DIR_T | (1,4) | 1 | (2,4)
DIR_B | (2,1) | 1 | (1,1)
DIR_B | (2,4) | 1 | (1,4)
DIR_B | (3,0) | 3 | (0,0)
DIR_B | (3,5) | 3 | (0,5)
```


#### &r14, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [4, 8, 6, 8, 8]; test: 6

Train example 0: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 . . . . 5
. . . . . .
. . . . . .
5 . . . . 5
```
```
c0 | c1 | c2 | c3
DIR_L | (0,0) | 5 | (0,5)
DIR_L | (3,0) | 5 | (3,5)
DIR_R | (0,5) | 5 | (0,0)
DIR_R | (3,5) | 5 | (3,0)
```

Train example 1: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 . . . . 5
. 3 . . 3 .
. . 1 1 . .
. 3 . . 3 .
```
```
c0 | c1 | c2 | c3
DIR_L | (0,0) | 5 | (0,5)
DIR_L | (1,1) | 3 | (1,4)
DIR_L | (2,2) | 1 | (2,3)
DIR_L | (3,1) | 3 | (3,4)
DIR_R | (0,5) | 5 | (0,0)
DIR_R | (1,4) | 3 | (1,1)
DIR_R | (2,3) | 1 | (2,2)
DIR_R | (3,4) | 3 | (3,1)
```

Train example 2: 6 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . .
. 3 . . 3 .
5 . . . . 5
. 3 . . 3 .
```
```
c0 | c1 | c2 | c3
DIR_L | (1,1) | 3 | (1,4)
DIR_L | (2,0) | 5 | (2,5)
DIR_L | (3,1) | 3 | (3,4)
DIR_R | (1,4) | 3 | (1,1)
DIR_R | (2,5) | 5 | (2,0)
DIR_R | (3,4) | 3 | (3,1)
```

Train example 3: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . 1 1 . .
. 3 . . 3 .
5 . . . . 5
. 3 . . 3 .
```
```
c0 | c1 | c2 | c3
DIR_L | (0,2) | 1 | (0,3)
DIR_L | (1,1) | 3 | (1,4)
DIR_L | (2,0) | 5 | (2,5)
DIR_L | (3,1) | 3 | (3,4)
DIR_R | (0,3) | 1 | (0,2)
DIR_R | (1,4) | 3 | (1,1)
DIR_R | (2,5) | 5 | (2,0)
DIR_R | (3,4) | 3 | (3,1)
```

Train example 4: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 . . . . 5
. 3 . . 3 .
. 3 . . 3 .
5 . . . . 5
```
```
c0 | c1 | c2 | c3
DIR_L | (0,0) | 5 | (0,5)
DIR_L | (1,1) | 3 | (1,4)
DIR_L | (2,1) | 3 | (2,4)
DIR_L | (3,0) | 5 | (3,5)
DIR_R | (0,5) | 5 | (0,0)
DIR_R | (1,4) | 3 | (1,1)
DIR_R | (2,4) | 3 | (2,1)
DIR_R | (3,5) | 5 | (3,0)
```

```
RULE &r14 :0 * [L0] :3 * [L1] :1 * [L2] END [&r15]
```

### &r15 (export table 13)

- columns: c0: Dir8, c1: Number, c2: Box
- depth 7, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 2

#### &r15, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [4, 4, 4, 4, 8]; test: 4

Train example 0: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
3 . . . . 3
. . . . . .
. . . . . .
3 . . . . 3
```
```
c0 | c1 | c2
DIR_T | 3 | (3,0)
DIR_T | 3 | (3,5)
DIR_B | 3 | (0,0)
DIR_B | 3 | (0,5)
```

Train example 1: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . .
. 2 . . 2 .
. . . . . .
. 2 . . 2 .
```
```
c0 | c1 | c2
DIR_T | 2 | (3,1)
DIR_T | 2 | (3,4)
DIR_B | 2 | (1,1)
DIR_B | 2 | (1,4)
```

Train example 2: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . .
. 2 . . 2 .
. . . . . .
. 2 . . 2 .
```
```
c0 | c1 | c2
DIR_T | 2 | (3,1)
DIR_T | 2 | (3,4)
DIR_B | 2 | (1,1)
DIR_B | 2 | (1,4)
```

Train example 3: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . .
. 2 . . 2 .
. . . . . .
. 2 . . 2 .
```
```
c0 | c1 | c2
DIR_T | 2 | (3,1)
DIR_T | 2 | (3,4)
DIR_B | 2 | (1,1)
DIR_B | 2 | (1,4)
```

Train example 4: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
3 . . . . 3
. 1 . . 1 .
. 1 . . 1 .
3 . . . . 3
```
```
c0 | c1 | c2
DIR_T | 1 | (2,1)
DIR_T | 1 | (2,4)
DIR_T | 3 | (3,0)
DIR_T | 3 | (3,5)
DIR_B | 1 | (1,1)
DIR_B | 1 | (1,4)
DIR_B | 3 | (0,0)
DIR_B | 3 | (0,5)
```


#### &r15, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [4, 8, 6, 8, 8]; test: 6

Train example 0: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 . . . . 5
. . . . . .
. . . . . .
5 . . . . 5
```
```
c0 | c1 | c2
DIR_L | 5 | (0,5)
DIR_L | 5 | (3,5)
DIR_R | 5 | (0,0)
DIR_R | 5 | (3,0)
```

Train example 1: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 . . . . 5
. 3 . . 3 .
. . 1 1 . .
. 3 . . 3 .
```
```
c0 | c1 | c2
DIR_L | 1 | (2,3)
DIR_L | 3 | (1,4)
DIR_L | 3 | (3,4)
DIR_L | 5 | (0,5)
DIR_R | 1 | (2,2)
DIR_R | 3 | (1,1)
DIR_R | 3 | (3,1)
DIR_R | 5 | (0,0)
```

Train example 2: 6 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . .
. 3 . . 3 .
5 . . . . 5
. 3 . . 3 .
```
```
c0 | c1 | c2
DIR_L | 3 | (1,4)
DIR_L | 3 | (3,4)
DIR_L | 5 | (2,5)
DIR_R | 3 | (1,1)
DIR_R | 3 | (3,1)
DIR_R | 5 | (2,0)
```

Train example 3: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . 1 1 . .
. 3 . . 3 .
5 . . . . 5
. 3 . . 3 .
```
```
c0 | c1 | c2
DIR_L | 1 | (0,3)
DIR_L | 3 | (1,4)
DIR_L | 3 | (3,4)
DIR_L | 5 | (2,5)
DIR_R | 1 | (0,2)
DIR_R | 3 | (1,1)
DIR_R | 3 | (3,1)
DIR_R | 5 | (2,0)
```

Train example 4: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 . . . . 5
. 3 . . 3 .
. 3 . . 3 .
5 . . . . 5
```
```
c0 | c1 | c2
DIR_L | 3 | (1,4)
DIR_L | 3 | (2,4)
DIR_L | 5 | (0,5)
DIR_L | 5 | (3,5)
DIR_R | 3 | (1,1)
DIR_R | 3 | (2,1)
DIR_R | 5 | (0,0)
DIR_R | 5 | (3,0)
```

```
RULE &r15 :2 * [L0] :0 * [L1] &r3 :1 * [L2] :2 L1 :3 * [L3] :4 L0 != L3 0 END [&r16]
```

### &r16 (export table 14)

- columns: c0: Box, c1: Dir8, c2: Number, c3: Box
- depth 8, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 2

#### &r16, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [8, 4, 4, 4, 8]; test: 8

Train example 0: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
2 . . . . 2
2 . . . . 2
. . . . . .
```
```
c0 | c1 | c2 | c3
(1,0) | DIR_T | 2 | (3,0)
(1,0) | DIR_B | 1 | (0,0)
(1,5) | DIR_T | 2 | (3,5)
(1,5) | DIR_B | 1 | (0,5)
(2,0) | DIR_T | 1 | (3,0)
(2,0) | DIR_B | 2 | (0,0)
(2,5) | DIR_T | 1 | (3,5)
(2,5) | DIR_B | 2 | (0,5)
```

Train example 1: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . . . . .
. 2 . . 2 .
. . . . . .
```
```
c0 | c1 | c2 | c3
(2,1) | DIR_T | 1 | (3,1)
(2,1) | DIR_B | 1 | (1,1)
(2,4) | DIR_T | 1 | (3,4)
(2,4) | DIR_B | 1 | (1,4)
```

Train example 2: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . . . . .
. 2 . . 2 .
. . . . . .
```
```
c0 | c1 | c2 | c3
(2,1) | DIR_T | 1 | (3,1)
(2,1) | DIR_B | 1 | (1,1)
(2,4) | DIR_T | 1 | (3,4)
(2,4) | DIR_B | 1 | (1,4)
```

Train example 3: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . . . . .
. 2 . . 2 .
. . . . . .
```
```
c0 | c1 | c2 | c3
(2,1) | DIR_T | 1 | (3,1)
(2,1) | DIR_B | 1 | (1,1)
(2,4) | DIR_T | 1 | (3,4)
(2,4) | DIR_B | 1 | (1,4)
```

Train example 4: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
2 . . . . 2
2 . . . . 2
. . . . . .
```
```
c0 | c1 | c2 | c3
(1,0) | DIR_T | 2 | (3,0)
(1,0) | DIR_B | 1 | (0,0)
(1,5) | DIR_T | 2 | (3,5)
(1,5) | DIR_B | 1 | (0,5)
(2,0) | DIR_T | 1 | (3,0)
(2,0) | DIR_B | 2 | (0,0)
(2,5) | DIR_T | 1 | (3,5)
(2,5) | DIR_B | 2 | (0,5)
```


#### &r16, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [16, 16, 16, 16, 24]; test: 20

Train example 0: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 2 2 2 2 .
. . . . . .
. . . . . .
. 2 2 2 2 .
```
```
c0 | c1 | c2 | c3
(0,1) | DIR_L | 4 | (0,5)
(0,1) | DIR_R | 1 | (0,0)
(0,2) | DIR_L | 3 | (0,5)
(0,2) | DIR_R | 2 | (0,0)
(0,3) | DIR_L | 2 | (0,5)
(0,3) | DIR_R | 3 | (0,0)
(0,4) | DIR_L | 1 | (0,5)
(0,4) | DIR_R | 4 | (0,0)
(3,1) | DIR_L | 4 | (3,5)
(3,1) | DIR_R | 1 | (3,0)
(3,2) | DIR_L | 3 | (3,5)
(3,2) | DIR_R | 2 | (3,0)
(3,3) | DIR_L | 2 | (3,5)
(3,3) | DIR_R | 3 | (3,0)
(3,4) | DIR_L | 1 | (3,5)
(3,4) | DIR_R | 4 | (3,0)
```

Train example 1: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 2 2 2 2 .
. . 2 2 . .
. . . . . .
. . 2 2 . .
```
```
c0 | c1 | c2 | c3
(0,1) | DIR_L | 4 | (0,5)
(0,1) | DIR_R | 1 | (0,0)
(0,2) | DIR_L | 3 | (0,5)
(0,2) | DIR_R | 2 | (0,0)
(0,3) | DIR_L | 2 | (0,5)
(0,3) | DIR_R | 3 | (0,0)
(0,4) | DIR_L | 1 | (0,5)
(0,4) | DIR_R | 4 | (0,0)
(1,2) | DIR_L | 2 | (1,4)
(1,2) | DIR_R | 1 | (1,1)
(1,3) | DIR_L | 1 | (1,4)
(1,3) | DIR_R | 2 | (1,1)
(3,2) | DIR_L | 2 | (3,4)
(3,2) | DIR_R | 1 | (3,1)
(3,3) | DIR_L | 1 | (3,4)
(3,3) | DIR_R | 2 | (3,1)
```

Train example 2: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . 2 2 . .
. 2 2 2 2 .
. . 2 2 . .
```
```
c0 | c1 | c2 | c3
(1,2) | DIR_L | 2 | (1,4)
(1,2) | DIR_R | 1 | (1,1)
(1,3) | DIR_L | 1 | (1,4)
(1,3) | DIR_R | 2 | (1,1)
(2,1) | DIR_L | 4 | (2,5)
(2,1) | DIR_R | 1 | (2,0)
(2,2) | DIR_L | 3 | (2,5)
(2,2) | DIR_R | 2 | (2,0)
(2,3) | DIR_L | 2 | (2,5)
(2,3) | DIR_R | 3 | (2,0)
(2,4) | DIR_L | 1 | (2,5)
(2,4) | DIR_R | 4 | (2,0)
(3,2) | DIR_L | 2 | (3,4)
(3,2) | DIR_R | 1 | (3,1)
(3,3) | DIR_L | 1 | (3,4)
(3,3) | DIR_R | 2 | (3,1)
```

Train example 3: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . 2 2 . .
. 2 2 2 2 .
. . 2 2 . .
```
```
c0 | c1 | c2 | c3
(1,2) | DIR_L | 2 | (1,4)
(1,2) | DIR_R | 1 | (1,1)
(1,3) | DIR_L | 1 | (1,4)
(1,3) | DIR_R | 2 | (1,1)
(2,1) | DIR_L | 4 | (2,5)
(2,1) | DIR_R | 1 | (2,0)
(2,2) | DIR_L | 3 | (2,5)
(2,2) | DIR_R | 2 | (2,0)
(2,3) | DIR_L | 2 | (2,5)
(2,3) | DIR_R | 3 | (2,0)
(2,4) | DIR_L | 1 | (2,5)
(2,4) | DIR_R | 4 | (2,0)
(3,2) | DIR_L | 2 | (3,4)
(3,2) | DIR_R | 1 | (3,1)
(3,3) | DIR_L | 1 | (3,4)
(3,3) | DIR_R | 2 | (3,1)
```

Train example 4: 24 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 2 2 2 2 .
. . 2 2 . .
. . 2 2 . .
. 2 2 2 2 .
```
```
c0 | c1 | c2 | c3
(0,1) | DIR_L | 4 | (0,5)
(0,1) | DIR_R | 1 | (0,0)
(0,2) | DIR_L | 3 | (0,5)
(0,2) | DIR_R | 2 | (0,0)
(0,3) | DIR_L | 2 | (0,5)
(0,3) | DIR_R | 3 | (0,0)
(0,4) | DIR_L | 1 | (0,5)
(0,4) | DIR_R | 4 | (0,0)
(1,2) | DIR_L | 2 | (1,4)
(1,2) | DIR_R | 1 | (1,1)
(1,3) | DIR_L | 1 | (1,4)
(1,3) | DIR_R | 2 | (1,1)
(2,2) | DIR_L | 2 | (2,4)
(2,2) | DIR_R | 1 | (2,1)
(2,3) | DIR_L | 1 | (2,4)
(2,3) | DIR_R | 2 | (2,1)
(3,1) | DIR_L | 4 | (3,5)
(3,1) | DIR_R | 1 | (3,0)
(3,2) | DIR_L | 3 | (3,5)
(3,2) | DIR_R | 2 | (3,0)
(3,3) | DIR_L | 2 | (3,5)
(3,3) | DIR_R | 3 | (3,0)
(3,4) | DIR_L | 1 | (3,5)
(3,4) | DIR_R | 4 | (3,0)
```

```
INIT Order [:0] SKIP [:1] &r15 :2 * [L0] END [:0] END [:1] L0 END [:2] SKIP [:3] &r15 :2 * [L1] END [:0] END [:1] L1 END [:2] L1 END [:4] SKIP [&r17] [&r18] [&r19] [&r20] [&r21] [&r22] [&r23] [&r24] [&r25] [&r26]
```

### &r17 (export table 15)

- columns: c0: Number, c1: Number
- depth 9, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 2

#### &r17, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [1, 1, 1, 1, 2]; test: 1

Train example 0: 1 row
```
c0 | c1
3 | 0
```

Train example 1: 1 row
```
c0 | c1
2 | 0
```

Train example 2: 1 row
```
c0 | c1
2 | 0
```

Train example 3: 1 row
```
c0 | c1
2 | 0
```

Train example 4: 2 rows
```
c0 | c1
1 | 0
3 | 1
```


#### &r17, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [1, 3, 2, 3, 2]; test: 2

Train example 0: 1 row
```
c0 | c1
5 | 0
```

Train example 1: 3 rows
```
c0 | c1
1 | 0
3 | 1
5 | 2
```

Train example 2: 2 rows
```
c0 | c1
3 | 0
5 | 1
```

Train example 3: 3 rows
```
c0 | c1
1 | 0
3 | 1
5 | 2
```

Train example 4: 2 rows
```
c0 | c1
3 | 0
5 | 1
```

### &r18 (export table 16)

- columns: c0: Number, c1: Number
- depth 9, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 2

#### &r18, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [1, 1, 1, 1, 2]; test: 1

Train example 0: 1 row
```
c0 | c1
3 | 0
```

Train example 1: 1 row
```
c0 | c1
2 | 0
```

Train example 2: 1 row
```
c0 | c1
2 | 0
```

Train example 3: 1 row
```
c0 | c1
2 | 0
```

Train example 4: 2 rows
```
c0 | c1
1 | 1
3 | 0
```


#### &r18, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [1, 3, 2, 3, 2]; test: 2

Train example 0: 1 row
```
c0 | c1
5 | 0
```

Train example 1: 3 rows
```
c0 | c1
1 | 2
3 | 1
5 | 0
```

Train example 2: 2 rows
```
c0 | c1
3 | 1
5 | 0
```

Train example 3: 3 rows
```
c0 | c1
1 | 2
3 | 1
5 | 0
```

Train example 4: 2 rows
```
c0 | c1
3 | 1
5 | 0
```

### &r19 (export table 17)

- columns: c0: Number
- depth 9, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 2

#### &r19, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
3
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

Train example 3: 1 row
```
c0
2
```

Train example 4: 1 row
```
c0
1
```


#### &r19, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
5
```

Train example 1: 1 row
```
c0
1
```

Train example 2: 1 row
```
c0
3
```

Train example 3: 1 row
```
c0
1
```

Train example 4: 1 row
```
c0
3
```

### &r20 (export table 18)

- columns: c0: Number
- depth 9, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 2

#### &r20, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
3
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

Train example 3: 1 row
```
c0
2
```

Train example 4: 1 row
```
c0
3
```


#### &r20, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
5
```

Train example 1: 1 row
```
c0
5
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

Train example 4: 1 row
```
c0
5
```

### &r21 (export table 19)

- columns: c0: Number, c1: Number
- depth 9, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 2

#### &r21, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [0, 0, 0, 0, 1]; test: 0

Train example 0: 0 rows

Train example 1: 0 rows

Train example 2: 0 rows

Train example 3: 0 rows

Train example 4: 1 row
```
c0 | c1
1 | 3
```


#### &r21, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [0, 2, 1, 2, 1]; test: 1

Train example 0: 0 rows

Train example 1: 2 rows
```
c0 | c1
1 | 3
3 | 5
```

Train example 2: 1 row
```
c0 | c1
3 | 5
```

Train example 3: 2 rows
```
c0 | c1
1 | 3
3 | 5
```

Train example 4: 1 row
```
c0 | c1
3 | 5
```

### &r22 (export table 20)

- columns: c0: Number, c1: Number
- depth 9, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 2

#### &r22, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [1, 1, 1, 1, 2]; test: 1

Train example 0: 1 row
```
c0 | c1
3 | 3
```

Train example 1: 1 row
```
c0 | c1
2 | 2
```

Train example 2: 1 row
```
c0 | c1
2 | 2
```

Train example 3: 1 row
```
c0 | c1
2 | 2
```

Train example 4: 2 rows
```
c0 | c1
1 | 3
3 | 1
```


#### &r22, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [1, 3, 2, 3, 2]; test: 2

Train example 0: 1 row
```
c0 | c1
5 | 5
```

Train example 1: 3 rows
```
c0 | c1
1 | 3
3 | 5
5 | 1
```

Train example 2: 2 rows
```
c0 | c1
3 | 5
5 | 3
```

Train example 3: 3 rows
```
c0 | c1
1 | 3
3 | 5
5 | 1
```

Train example 4: 2 rows
```
c0 | c1
3 | 5
5 | 3
```

```
RULE &r15 :2 * [L0] :0 * [L1] :1 * [L2] &r19 :1 L2 &r16 :0 L0 :1 L1 :2 * [L3] END [&r27]
```

### &r27 (export table 21)

- columns: c0: Box, c1: Dir8, c2: Number, c3: Box
- depth 10, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 2

#### &r27, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [8, 4, 4, 4, 0]; test: 8

Train example 0: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
2 . . . . 2
2 . . . . 2
. . . . . .
```
```
c0 | c1 | c2 | c3
(1,0) | DIR_T | 3 | (3,0)
(1,0) | DIR_B | 3 | (0,0)
(1,5) | DIR_T | 3 | (3,5)
(1,5) | DIR_B | 3 | (0,5)
(2,0) | DIR_T | 3 | (3,0)
(2,0) | DIR_B | 3 | (0,0)
(2,5) | DIR_T | 3 | (3,5)
(2,5) | DIR_B | 3 | (0,5)
```

Train example 1: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . . . . .
. 2 . . 2 .
. . . . . .
```
```
c0 | c1 | c2 | c3
(2,1) | DIR_T | 2 | (3,1)
(2,1) | DIR_B | 2 | (1,1)
(2,4) | DIR_T | 2 | (3,4)
(2,4) | DIR_B | 2 | (1,4)
```

Train example 2: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . . . . .
. 2 . . 2 .
. . . . . .
```
```
c0 | c1 | c2 | c3
(2,1) | DIR_T | 2 | (3,1)
(2,1) | DIR_B | 2 | (1,1)
(2,4) | DIR_T | 2 | (3,4)
(2,4) | DIR_B | 2 | (1,4)
```

Train example 3: 4 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . . . . .
. 2 . . 2 .
. . . . . .
```
```
c0 | c1 | c2 | c3
(2,1) | DIR_T | 2 | (3,1)
(2,1) | DIR_B | 2 | (1,1)
(2,4) | DIR_T | 2 | (3,4)
(2,4) | DIR_B | 2 | (1,4)
```

Train example 4: 0 rows


#### &r27, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [16, 0, 8, 0, 8]; test: 4

Train example 0: 16 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 2 2 2 2 .
. . . . . .
. . . . . .
. 2 2 2 2 .
```
```
c0 | c1 | c2 | c3
(0,1) | DIR_L | 5 | (0,5)
(0,1) | DIR_R | 5 | (0,0)
(0,2) | DIR_L | 5 | (0,5)
(0,2) | DIR_R | 5 | (0,0)
(0,3) | DIR_L | 5 | (0,5)
(0,3) | DIR_R | 5 | (0,0)
(0,4) | DIR_L | 5 | (0,5)
(0,4) | DIR_R | 5 | (0,0)
(3,1) | DIR_L | 5 | (3,5)
(3,1) | DIR_R | 5 | (3,0)
(3,2) | DIR_L | 5 | (3,5)
(3,2) | DIR_R | 5 | (3,0)
(3,3) | DIR_L | 5 | (3,5)
(3,3) | DIR_R | 5 | (3,0)
(3,4) | DIR_L | 5 | (3,5)
(3,4) | DIR_R | 5 | (3,0)
```

Train example 1: 0 rows

Train example 2: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . 2 2 . .
. . . . . .
. . 2 2 . .
```
```
c0 | c1 | c2 | c3
(1,2) | DIR_L | 3 | (1,4)
(1,2) | DIR_R | 3 | (1,1)
(1,3) | DIR_L | 3 | (1,4)
(1,3) | DIR_R | 3 | (1,1)
(3,2) | DIR_L | 3 | (3,4)
(3,2) | DIR_R | 3 | (3,1)
(3,3) | DIR_L | 3 | (3,4)
(3,3) | DIR_R | 3 | (3,1)
```

Train example 3: 0 rows

Train example 4: 8 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . .
. . 2 2 . .
. . 2 2 . .
. . . . . .
```
```
c0 | c1 | c2 | c3
(1,2) | DIR_L | 3 | (1,4)
(1,2) | DIR_R | 3 | (1,1)
(1,3) | DIR_L | 3 | (1,4)
(1,3) | DIR_R | 3 | (1,1)
(2,2) | DIR_L | 3 | (2,4)
(2,2) | DIR_R | 3 | (2,1)
(2,3) | DIR_L | 3 | (2,4)
(2,3) | DIR_R | 3 | (2,1)
```

```
RULE OR &r27 :3 * [L0] &r1 :0 * [L1] ALSO input :0 L0 :1 L1 NOT &r27 :3 L0 END END [&r28]
```

### &r28 (export table 22)

- columns: c0: Color, c1: Box
- depth 11, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 2

#### &r28, assignment 1 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_V)}
- rows per train example: [24, 24, 24, 24, 24]; test: 24

Train example 0: 24 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 0 0 0 0 2
2 0 0 0 0 2
2 0 0 0 0 2
2 0 0 0 0 2
```
```
c0 | c1
0 | (0,1)
0 | (0,2)
0 | (0,3)
0 | (0,4)
0 | (1,1)
0 | (1,2)
0 | (1,3)
0 | (1,4)
0 | (2,1)
0 | (2,2)
0 | (2,3)
0 | (2,4)
0 | (3,1)
0 | (3,2)
0 | (3,3)
0 | (3,4)
2 | (0,0)
2 | (0,5)
2 | (1,0)
2 | (1,5)
2 | (2,0)
2 | (2,5)
2 | (3,0)
2 | (3,5)
```

Train example 1: 24 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 0 0 0 0 2
0 2 0 0 2 0
0 2 2 2 2 0
0 2 0 0 2 0
```
```
c0 | c1
0 | (0,1)
0 | (0,2)
0 | (0,3)
0 | (0,4)
0 | (1,0)
0 | (1,2)
0 | (1,3)
0 | (1,5)
0 | (2,0)
0 | (2,5)
0 | (3,0)
0 | (3,2)
0 | (3,3)
0 | (3,5)
2 | (0,0)
2 | (0,5)
2 | (1,1)
2 | (1,4)
2 | (2,1)
2 | (2,2)
2 | (2,3)
2 | (2,4)
2 | (3,1)
2 | (3,4)
```

Train example 2: 24 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
0 0 0 0 0 0
0 2 0 0 2 0
2 2 0 0 2 2
0 2 0 0 2 0
```
```
c0 | c1
0 | (0,0)
0 | (0,1)
0 | (0,2)
0 | (0,3)
0 | (0,4)
0 | (0,5)
0 | (1,0)
0 | (1,2)
0 | (1,3)
0 | (1,5)
0 | (2,2)
0 | (2,3)
0 | (3,0)
0 | (3,2)
0 | (3,3)
0 | (3,5)
2 | (1,1)
2 | (1,4)
2 | (2,0)
2 | (2,1)
2 | (2,4)
2 | (2,5)
2 | (3,1)
2 | (3,4)
```

Train example 3: 24 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
0 0 2 2 0 0
0 2 0 0 2 0
2 2 0 0 2 2
0 2 0 0 2 0
```
```
c0 | c1
0 | (0,0)
0 | (0,1)
0 | (0,4)
0 | (0,5)
0 | (1,0)
0 | (1,2)
0 | (1,3)
0 | (1,5)
0 | (2,2)
0 | (2,3)
0 | (3,0)
0 | (3,2)
0 | (3,3)
0 | (3,5)
2 | (0,2)
2 | (0,3)
2 | (1,1)
2 | (1,4)
2 | (2,0)
2 | (2,1)
2 | (2,4)
2 | (2,5)
2 | (3,1)
2 | (3,4)
```

Train example 4: 24 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 0 0 0 0 2
0 2 0 0 2 0
0 2 0 0 2 0
2 0 0 0 0 2
```
```
c0 | c1
0 | (0,1)
0 | (0,2)
0 | (0,3)
0 | (0,4)
0 | (1,0)
0 | (1,2)
0 | (1,3)
0 | (1,5)
0 | (2,0)
0 | (2,2)
0 | (2,3)
0 | (2,5)
0 | (3,1)
0 | (3,2)
0 | (3,3)
0 | (3,4)
2 | (0,0)
2 | (0,5)
2 | (1,1)
2 | (1,4)
2 | (2,1)
2 | (2,4)
2 | (3,0)
2 | (3,5)
```


#### &r28, assignment 2 of 2

- DET values that differ between the assignments: &r0 = {(AXIS_H)}
- rows per train example: [24, 24, 24, 24, 24]; test: 24

Train example 0: 24 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 2 2 2 2 2
0 0 0 0 0 0
0 0 0 0 0 0
2 2 2 2 2 2
```
```
c0 | c1
0 | (1,0)
0 | (1,1)
0 | (1,2)
0 | (1,3)
0 | (1,4)
0 | (1,5)
0 | (2,0)
0 | (2,1)
0 | (2,2)
0 | (2,3)
0 | (2,4)
0 | (2,5)
2 | (0,0)
2 | (0,1)
2 | (0,2)
2 | (0,3)
2 | (0,4)
2 | (0,5)
2 | (3,0)
2 | (3,1)
2 | (3,2)
2 | (3,3)
2 | (3,4)
2 | (3,5)
```

Train example 1: 24 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 0 0 0 0 2
0 2 0 0 2 0
0 0 2 2 0 0
0 2 0 0 2 0
```
```
c0 | c1
0 | (0,1)
0 | (0,2)
0 | (0,3)
0 | (0,4)
0 | (1,0)
0 | (1,2)
0 | (1,3)
0 | (1,5)
0 | (2,0)
0 | (2,1)
0 | (2,4)
0 | (2,5)
0 | (3,0)
0 | (3,2)
0 | (3,3)
0 | (3,5)
2 | (0,0)
2 | (0,5)
2 | (1,1)
2 | (1,4)
2 | (2,2)
2 | (2,3)
2 | (3,1)
2 | (3,4)
```

Train example 2: 24 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
0 0 0 0 0 0
0 2 2 2 2 0
2 0 0 0 0 2
0 2 2 2 2 0
```
```
c0 | c1
0 | (0,0)
0 | (0,1)
0 | (0,2)
0 | (0,3)
0 | (0,4)
0 | (0,5)
0 | (1,0)
0 | (1,5)
0 | (2,1)
0 | (2,2)
0 | (2,3)
0 | (2,4)
0 | (3,0)
0 | (3,5)
2 | (1,1)
2 | (1,2)
2 | (1,3)
2 | (1,4)
2 | (2,0)
2 | (2,5)
2 | (3,1)
2 | (3,2)
2 | (3,3)
2 | (3,4)
```

Train example 3: 24 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
0 0 2 2 0 0
0 2 0 0 2 0
2 0 0 0 0 2
0 2 0 0 2 0
```
```
c0 | c1
0 | (0,0)
0 | (0,1)
0 | (0,4)
0 | (0,5)
0 | (1,0)
0 | (1,2)
0 | (1,3)
0 | (1,5)
0 | (2,1)
0 | (2,2)
0 | (2,3)
0 | (2,4)
0 | (3,0)
0 | (3,2)
0 | (3,3)
0 | (3,5)
2 | (0,2)
2 | (0,3)
2 | (1,1)
2 | (1,4)
2 | (2,0)
2 | (2,5)
2 | (3,1)
2 | (3,4)
```

Train example 4: 24 rows
Drawn on a 4x6 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 0 0 0 0 2
0 2 2 2 2 0
0 2 2 2 2 0
2 0 0 0 0 2
```
```
c0 | c1
0 | (0,1)
0 | (0,2)
0 | (0,3)
0 | (0,4)
0 | (1,0)
0 | (1,5)
0 | (2,0)
0 | (2,5)
0 | (3,1)
0 | (3,2)
0 | (3,3)
0 | (3,4)
2 | (0,0)
2 | (0,5)
2 | (1,1)
2 | (1,2)
2 | (1,3)
2 | (1,4)
2 | (2,1)
2 | (2,2)
2 | (2,3)
2 | (2,4)
2 | (3,0)
2 | (3,5)
```

## What I see

The task: marks of color 2 lie in pairs, one pair to a row. The pair with the least gap fills the cells between its marks with 2. Where the least gap is 1, as in e1 and e3, the closest pair is adjacent, nothing fills, and the output equals the input. The DET &r0 has two assignments: assignment 2 (AXIS_H) is the case's, and assignment 1 (AXIS_V) is the other.

- **&r0** (DET: the pair axis): AXIS_V or AXIS_H. **&r1** (DET RarestColor): 2. **&r2** (input cells of color 2): the marks, 4 to 8 per example. A selection that stands out in the drawing, as 0ca9ddb6 &r14 does.
- **&r3, &r4, &r7** (Ray along the axis from each mark, through non-mark cells: the cells it clears, the cell where it stops, and its directions): &r3 is the closure of the grid's step along the axis from each mark, so it is derived from &r2 and the grid. &r7 is DIR_T, DIR_B or DIR_L, DIR_R, the same in every example (a constant table). &r4 is one stop cell per ray, the last cell before a mark or the grid's edge. Half of its rows are rays that run out to the edge, such as `(1,0) | DIR_L | 1 | (1,1)` in e1 at AXIS_H. Those rows do not take part in a pair, and they are noise.
- **&r8, &r9, &r12** (the same Ray with the marks as cells too): &r9 holds the mark that each ray reaches, for example (0,0) DIR_T 3 (3,0) in e0 at AXIS_V. &r12 is equal to &r7.
- **&r13** (pairs: a stop cell whose next step is a mark, with the gap): **at AXIS_H, the signal jumps here.** Its row count is 4, 8, 6, 8, 8, which equals &r2's at every example: every mark has exactly one partner. The gaps in e1 are 5, 3, 1, 3, one pair to each row (`(2,2) | DIR_R | (2,3) | 1 | (2,2)` is the adjacent pair). At AXIS_V, the row count is 4, 4, 4, 4, 8, so some marks have no partner. The table alone tells the assignments apart: at the right axis, the pairs' count matches the marks' count.
- **&r14, &r15** (&r13 with columns dropped): projections, no signal.
- **&r16** (span cells: the cells a ray clears, toward its partner): at AXIS_H, every cell between the two marks of each pair, twice (once from each end, DIR_L and DIR_R). The drawing is all the cells that could fill: a superset of the output's changed cells. Each cell is held twice because the pair relation is symmetric. The second copy adds no signal.
- **&r17 to &r26** (Order over the gaps): &r19 is the least gap per example: 5, 1, 3, 1, 3 at AXIS_H, and 3, 2, 2, 2, 1 at AXIS_V. "Many rows reduced to one": it is a functional dependency of Example to gap. &r17 (rank), &r18, &r20 (high) to &r22 and the others are functions of the same few values, and only &r19 is read later.
- **&r27** (the span cells of the pairs at the least gap): at AXIS_H, the row counts are 16, 0, 8, 0, 8. The table is empty in exactly the two examples whose output equals the input, and its cells in e0, e2 and e4 are the output's changed cells, each cell twice. At AXIS_V, the row counts are 8, 4, 4, 4, 0, and none of its cells (`(1,0)` in e0, `(2,1)` in e1 to e3) is a changed cell of an output. The match with the outputs, and the pattern of empty examples, point to AXIS_H.
- **&r28** (out): 24 rows at both assignments, the whole grid. Only a comparison with the outputs tells that assignment 2 is correct and assignment 1 is not.

Rows that look like noise: &r3 and &r8 (closures of the grid step), &r7 and &r12 (constants), &r14 and &r15 (projections), the second copy of each cell in &r16 and &r27, and the Order outputs other than &r19. The signal about the rule jumps at &r13 (pairs, with a count that matches the marks only at AXIS_H) and at &r19 (one gap per example).
