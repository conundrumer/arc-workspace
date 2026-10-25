# e633a9e5, case `$Edge`

- concept case: True; tokens: 485; tables: 19 relations, 19 per assignment
- cells: a Position is `(row,col)` of the example's input grid (`(row,col)out` where it fits only the output grid), an Offset `+(drow,dcol)`, another Box `rR0-R1 cC0-C1` over the input grid or `[t b l r]` margins; an Ident is `id<n>`, equal only within one case; see README.md

## Grids

### Train example 0: input 3x3, output 5x5

```
input    output
6 5 5    6 6 5 5 5
5 1 7    6 6 5 5 5
4 5 2    5 5 1 7 7
         4 4 5 2 2
         4 4 5 2 2
```

### Train example 1: input 3x3, output 5x5

```
input    output
1 3 5    1 1 3 5 5
1 2 8    1 1 3 5 5
8 3 8    1 1 2 8 8
         8 8 3 8 8
         8 8 3 8 8
```

### Train example 2: input 3x3, output 5x5

```
input    output
2 3 7    2 2 3 7 7
2 1 6    2 2 3 7 7
1 5 7    2 2 1 6 6
         1 1 5 7 7
         1 1 5 7 7
```

### Test example 0: input 3x3

```
1 2 5
7 3 6
7 6 5
```

## Program and tables

Model-written tokens plain, engine-written ones in [brackets]. Each clause is followed by the tables of the relations it declares. A table whose entries hold several DET assignments is given once per assignment, each marked with the values, at that assignment, of the DETs whose value differs between them; a DET's value is the rows of its own table at that assignment.

```
DET DimDiff END [&r0]
```

### &r0 (export table 2)

- columns: D: Number
- depth 1, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
2
```

```
DET ex_input :0 * [L0] :1 * [L1] :2 * [L2] ex_output :0 L0 :1 * [L3] :2 L2 END [&r1]
```

### &r1 (export table 3)

- columns: c0: Example, c1: Box, c2: Box, c3: Color
- depth 1, candidate keys none
- DETs its entries are assigned: &r1; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 154
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 55 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
4 + +
+ 1 2
4 + 4
```
```
c0 | c1 | c2 | c3
e0 | (0,0) | (0,0)out | 6
e0 | (0,0) | (0,1)out | 6
e0 | (0,0) | (1,0)out | 6
e0 | (0,0) | (1,1)out | 6
e0 | (0,1) | (0,2)out | 5
e0 | (0,1) | (0,3)out | 5
e0 | (0,1) | (0,4)out | 5
e0 | (0,1) | (1,2)out | 5
e0 | (0,1) | (1,3)out | 5
e0 | (0,1) | (1,4)out | 5
e0 | (0,1) | (2,0)out | 5
e0 | (0,1) | (2,1)out | 5
e0 | (0,1) | (3,2)out | 5
e0 | (0,1) | (4,2)out | 5
e0 | (0,2) | (0,2)out | 5
e0 | (0,2) | (0,3)out | 5
e0 | (0,2) | (0,4)out | 5
e0 | (0,2) | (1,2)out | 5
e0 | (0,2) | (1,3)out | 5
e0 | (0,2) | (1,4)out | 5
e0 | (0,2) | (2,0)out | 5
e0 | (0,2) | (2,1)out | 5
e0 | (0,2) | (3,2)out | 5
e0 | (0,2) | (4,2)out | 5
e0 | (1,0) | (0,2)out | 5
e0 | (1,0) | (0,3)out | 5
e0 | (1,0) | (0,4)out | 5
e0 | (1,0) | (1,2)out | 5
e0 | (1,0) | (1,3)out | 5
e0 | (1,0) | (1,4)out | 5
```

Task-wide, rows whose Example column is e1: 55 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
6 4 4
6 1 +
+ 4 +
```
```
c0 | c1 | c2 | c3
e1 | (0,0) | (0,0)out | 1
e1 | (0,0) | (0,1)out | 1
e1 | (0,0) | (1,0)out | 1
e1 | (0,0) | (1,1)out | 1
e1 | (0,0) | (2,0)out | 1
e1 | (0,0) | (2,1)out | 1
e1 | (0,1) | (0,2)out | 3
e1 | (0,1) | (1,2)out | 3
e1 | (0,1) | (3,2)out | 3
e1 | (0,1) | (4,2)out | 3
e1 | (0,2) | (0,3)out | 5
e1 | (0,2) | (0,4)out | 5
e1 | (0,2) | (1,3)out | 5
e1 | (0,2) | (1,4)out | 5
e1 | (1,0) | (0,0)out | 1
e1 | (1,0) | (0,1)out | 1
e1 | (1,0) | (1,0)out | 1
e1 | (1,0) | (1,1)out | 1
e1 | (1,0) | (2,0)out | 1
e1 | (1,0) | (2,1)out | 1
e1 | (1,1) | (2,2)out | 2
e1 | (1,2) | (2,3)out | 8
e1 | (1,2) | (2,4)out | 8
e1 | (1,2) | (3,0)out | 8
e1 | (1,2) | (3,1)out | 8
e1 | (1,2) | (3,3)out | 8
e1 | (1,2) | (3,4)out | 8
e1 | (1,2) | (4,0)out | 8
e1 | (1,2) | (4,1)out | 8
e1 | (1,2) | (4,3)out | 8
```

Task-wide, rows whose Example column is e2: 44 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
6 2 8
6 5 2
5 2 8
```
```
c0 | c1 | c2 | c3
e2 | (0,0) | (0,0)out | 2
e2 | (0,0) | (0,1)out | 2
e2 | (0,0) | (1,0)out | 2
e2 | (0,0) | (1,1)out | 2
e2 | (0,0) | (2,0)out | 2
e2 | (0,0) | (2,1)out | 2
e2 | (0,1) | (0,2)out | 3
e2 | (0,1) | (1,2)out | 3
e2 | (0,2) | (0,3)out | 7
e2 | (0,2) | (0,4)out | 7
e2 | (0,2) | (1,3)out | 7
e2 | (0,2) | (1,4)out | 7
e2 | (0,2) | (3,3)out | 7
e2 | (0,2) | (3,4)out | 7
e2 | (0,2) | (4,3)out | 7
e2 | (0,2) | (4,4)out | 7
e2 | (1,0) | (0,0)out | 2
e2 | (1,0) | (0,1)out | 2
e2 | (1,0) | (1,0)out | 2
e2 | (1,0) | (1,1)out | 2
e2 | (1,0) | (2,0)out | 2
e2 | (1,0) | (2,1)out | 2
e2 | (1,1) | (2,2)out | 1
e2 | (1,1) | (3,0)out | 1
e2 | (1,1) | (3,1)out | 1
e2 | (1,1) | (4,0)out | 1
e2 | (1,1) | (4,1)out | 1
e2 | (1,2) | (2,3)out | 6
e2 | (1,2) | (2,4)out | 6
e2 | (2,0) | (2,2)out | 1
```

```
DET &r1 :1 * [L0] :3 * [L1] ex_output :0 * [L2] NOT &r1 :0 L2 :1 L0 :3 L1 END [&r2]
```

### &r2 (export table 4)

- columns: c0: Example, c1: Box, c2: Box
- depth 2, candidate keys none
- DETs its entries are assigned: &r1, &r2; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 128
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 39 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 . 4
4 4 8
7 . +
```
```
c0 | c1 | c2
e0 | (0,0) | (2,0)out
e0 | (0,0) | (2,1)out
e0 | (0,2) | (3,3)out
e0 | (0,2) | (3,4)out
e0 | (0,2) | (4,3)out
e0 | (0,2) | (4,4)out
e0 | (1,0) | (0,0)out
e0 | (1,0) | (0,1)out
e0 | (1,0) | (1,0)out
e0 | (1,0) | (1,1)out
e0 | (1,1) | (3,0)out
e0 | (1,1) | (3,1)out
e0 | (1,1) | (4,0)out
e0 | (1,1) | (4,1)out
e0 | (1,2) | (3,0)out
e0 | (1,2) | (3,1)out
e0 | (1,2) | (3,3)out
e0 | (1,2) | (3,4)out
e0 | (1,2) | (4,0)out
e0 | (1,2) | (4,1)out
e0 | (1,2) | (4,3)out
e0 | (1,2) | (4,4)out
e0 | (2,0) | (2,2)out
e0 | (2,0) | (2,3)out
e0 | (2,0) | (2,4)out
e0 | (2,0) | (3,3)out
e0 | (2,0) | (3,4)out
e0 | (2,0) | (4,3)out
e0 | (2,0) | (4,4)out
e0 | (2,2) | (0,3)out
```

Task-wide, rows whose Example column is e1: 39 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 6 +
8 4 .
1 6 4
```
```
c0 | c1 | c2
e1 | (0,1) | (0,3)out
e1 | (0,1) | (0,4)out
e1 | (0,1) | (1,3)out
e1 | (0,1) | (1,4)out
e1 | (0,1) | (2,0)out
e1 | (0,1) | (2,1)out
e1 | (0,2) | (0,2)out
e1 | (0,2) | (1,2)out
e1 | (0,2) | (2,0)out
e1 | (0,2) | (2,1)out
e1 | (0,2) | (3,2)out
e1 | (0,2) | (3,3)out
e1 | (0,2) | (3,4)out
e1 | (0,2) | (4,2)out
e1 | (0,2) | (4,3)out
e1 | (0,2) | (4,4)out
e1 | (1,0) | (0,2)out
e1 | (1,0) | (0,3)out
e1 | (1,0) | (0,4)out
e1 | (1,0) | (1,2)out
e1 | (1,0) | (1,3)out
e1 | (1,0) | (1,4)out
e1 | (1,0) | (3,2)out
e1 | (1,0) | (4,2)out
e1 | (1,1) | (3,0)out
e1 | (1,1) | (3,1)out
e1 | (1,1) | (4,0)out
e1 | (1,1) | (4,1)out
e1 | (2,0) | (2,2)out
e1 | (2,1) | (0,3)out
```

Task-wide, rows whose Example column is e2: 50 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 8 6
8 . 8
6 8 6
```
```
c0 | c1 | c2
e2 | (0,1) | (0,3)out
e2 | (0,1) | (0,4)out
e2 | (0,1) | (1,3)out
e2 | (0,1) | (1,4)out
e2 | (0,1) | (2,0)out
e2 | (0,1) | (2,1)out
e2 | (0,1) | (3,2)out
e2 | (0,1) | (4,2)out
e2 | (0,2) | (0,2)out
e2 | (0,2) | (1,2)out
e2 | (0,2) | (2,0)out
e2 | (0,2) | (2,1)out
e2 | (0,2) | (3,2)out
e2 | (0,2) | (4,2)out
e2 | (1,0) | (0,2)out
e2 | (1,0) | (0,3)out
e2 | (1,0) | (0,4)out
e2 | (1,0) | (1,2)out
e2 | (1,0) | (1,3)out
e2 | (1,0) | (1,4)out
e2 | (1,0) | (3,2)out
e2 | (1,0) | (4,2)out
e2 | (1,2) | (3,0)out
e2 | (1,2) | (3,1)out
e2 | (1,2) | (3,3)out
e2 | (1,2) | (3,4)out
e2 | (1,2) | (4,0)out
e2 | (1,2) | (4,1)out
e2 | (1,2) | (4,3)out
e2 | (1,2) | (4,4)out
```

```
DET &r1 :1 * [L0] :3 * [L1] NOT &r2 :0 L0 :1 L1 END [&r3]
```

### &r3 (export table 5)

- columns: c0: Box, c1: Box
- depth 3, candidate keys none
- DETs its entries are assigned: &r1, &r2, &r3; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 25
- every row is of a task-wide entry

Task-wide: 25 rows
Drawn on a 3x3 grid, a task-wide frame, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
4 2 4
2 1 2
4 2 4
```
```
c0 | c1
[0 2 0 2] | [0 4 0 4]
[0 2 0 2] | [0 4 1 3]
[0 2 0 2] | [1 3 0 4]
[0 2 0 2] | [1 3 1 3]
[0 2 1 1] | [0 4 2 2]
[0 2 1 1] | [1 3 2 2]
[0 2 2 0] | [0 4 3 1]
[0 2 2 0] | [0 4 4 0]
[0 2 2 0] | [1 3 3 1]
[0 2 2 0] | [1 3 4 0]
[1 1 0 2] | [2 2 0 4]
[1 1 0 2] | [2 2 1 3]
[1 1 1 1] | [2 2 2 2]
[1 1 2 0] | [2 2 3 1]
[1 1 2 0] | [2 2 4 0]
[2 0 0 2] | [3 1 0 4]
[2 0 0 2] | [3 1 1 3]
[2 0 0 2] | [4 0 0 4]
[2 0 0 2] | [4 0 1 3]
[2 0 1 1] | [3 1 2 2]
[2 0 1 1] | [4 0 2 2]
[2 0 2 0] | [3 1 3 1]
[2 0 2 0] | [3 1 4 0]
[2 0 2 0] | [4 0 3 1]
[2 0 2 0] | [4 0 4 0]
```

```
DET &r3 :0 * [L0] :1 * [L1] axis_elem :0 * [L2] split :0 L1 :1 L2 :2 * [L3] END [&r4]
```

### &r4 (export table 6)

- columns: c0: Axis, c1: Box, c2: Box, c3: Box
- depth 4, candidate keys none
- DETs its entries are assigned: &r1, &r2, &r3, &r4; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 50
- every row is of a task-wide entry

Task-wide: 50 rows, the first 30 shown
Drawn on a 3x3 grid, a task-wide frame, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
8 4 8
4 2 4
8 4 8
```
```
c0 | c1 | c2 | c3
AXIS_V | [0 2 0 2] | [0 4 0 4] | [0 4 0 0]
AXIS_V | [0 2 0 2] | [0 4 1 3] | [0 4 0 0]
AXIS_V | [0 2 0 2] | [1 3 0 4] | [1 3 0 0]
AXIS_V | [0 2 0 2] | [1 3 1 3] | [1 3 0 0]
AXIS_V | [0 2 1 1] | [0 4 2 2] | [0 4 0 0]
AXIS_V | [0 2 1 1] | [1 3 2 2] | [1 3 0 0]
AXIS_V | [0 2 2 0] | [0 4 3 1] | [0 4 0 0]
AXIS_V | [0 2 2 0] | [0 4 4 0] | [0 4 0 0]
AXIS_V | [0 2 2 0] | [1 3 3 1] | [1 3 0 0]
AXIS_V | [0 2 2 0] | [1 3 4 0] | [1 3 0 0]
AXIS_V | [1 1 0 2] | [2 2 0 4] | [2 2 0 0]
AXIS_V | [1 1 0 2] | [2 2 1 3] | [2 2 0 0]
AXIS_V | [1 1 1 1] | [2 2 2 2] | [2 2 0 0]
AXIS_V | [1 1 2 0] | [2 2 3 1] | [2 2 0 0]
AXIS_V | [1 1 2 0] | [2 2 4 0] | [2 2 0 0]
AXIS_V | [2 0 0 2] | [3 1 0 4] | [3 1 0 0]
AXIS_V | [2 0 0 2] | [3 1 1 3] | [3 1 0 0]
AXIS_V | [2 0 0 2] | [4 0 0 4] | [4 0 0 0]
AXIS_V | [2 0 0 2] | [4 0 1 3] | [4 0 0 0]
AXIS_V | [2 0 1 1] | [3 1 2 2] | [3 1 0 0]
AXIS_V | [2 0 1 1] | [4 0 2 2] | [4 0 0 0]
AXIS_V | [2 0 2 0] | [3 1 3 1] | [3 1 0 0]
AXIS_V | [2 0 2 0] | [3 1 4 0] | [3 1 0 0]
AXIS_V | [2 0 2 0] | [4 0 3 1] | [4 0 0 0]
AXIS_V | [2 0 2 0] | [4 0 4 0] | [4 0 0 0]
AXIS_H | [0 2 0 2] | [0 4 0 4] | [0 0 0 4]
AXIS_H | [0 2 0 2] | [0 4 1 3] | [0 0 1 3]
AXIS_H | [0 2 0 2] | [1 3 0 4] | [0 0 0 4]
AXIS_H | [0 2 0 2] | [1 3 1 3] | [0 0 1 3]
AXIS_H | [0 2 1 1] | [0 4 2 2] | [0 0 2 2]
```

```
INIT Cardinality [:0] &r4 :0 ^ [L0] :2 ^ [L1] :3 * [L2] END [:1] &r4 :0 L0 :2 L1 :3 * [L3] END [:0] END [:1] L3 END [:2] SKIP [:2] SKIP [&r5] [&r6] [&r7]
```

### &r5 (export table 7)

- columns: c0: Box, c1: Axis, c2: Number
- depth 6, candidate keys none
- DETs its entries are assigned: &r1, &r2, &r3, &r4; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 18
- every row is of a task-wide entry

Task-wide: 18 rows
Drawn on a 3x3 grid, a task-wide frame, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2
2 2 2
2 2 2
```
```
c0 | c1 | c2
[0 2 0 2] | AXIS_V | 2
[0 2 0 2] | AXIS_H | 2
[0 2 1 1] | AXIS_V | 2
[0 2 1 1] | AXIS_H | 1
[0 2 2 0] | AXIS_V | 2
[0 2 2 0] | AXIS_H | 2
[1 1 0 2] | AXIS_V | 1
[1 1 0 2] | AXIS_H | 2
[1 1 1 1] | AXIS_V | 1
[1 1 1 1] | AXIS_H | 1
[1 1 2 0] | AXIS_V | 1
[1 1 2 0] | AXIS_H | 2
[2 0 0 2] | AXIS_V | 2
[2 0 0 2] | AXIS_H | 2
[2 0 1 1] | AXIS_V | 2
[2 0 1 1] | AXIS_H | 1
[2 0 2 0] | AXIS_V | 2
[2 0 2 0] | AXIS_H | 2
```

```
DET &r5 :0 :0 * [L0] :1 * [L1] END :1 * [L2] split :0 L0 :1 L1 :2 * [L3] END [&r8]
```

### &r8 (export table 8)

- columns: c0: Box, c1: Axis, c2: Box, c3: Number
- depth 7, candidate keys none
- DETs its entries are assigned: &r1, &r2, &r3, &r4, &r8; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 18
- every row is of a task-wide entry

Task-wide: 18 rows
Drawn on a 3x3 grid, a task-wide frame, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2
2 2 2
2 2 2
```
```
c0 | c1 | c2 | c3
[0 2 0 2] | AXIS_V | [0 2 0 0] | 2
[0 2 0 2] | AXIS_H | [0 0 0 2] | 2
[0 2 1 1] | AXIS_V | [0 2 0 0] | 2
[0 2 1 1] | AXIS_H | [0 0 1 1] | 1
[0 2 2 0] | AXIS_V | [0 2 0 0] | 2
[0 2 2 0] | AXIS_H | [0 0 2 0] | 2
[1 1 0 2] | AXIS_V | [1 1 0 0] | 1
[1 1 0 2] | AXIS_H | [0 0 0 2] | 2
[1 1 1 1] | AXIS_V | [1 1 0 0] | 1
[1 1 1 1] | AXIS_H | [0 0 1 1] | 1
[1 1 2 0] | AXIS_V | [1 1 0 0] | 1
[1 1 2 0] | AXIS_H | [0 0 2 0] | 2
[2 0 0 2] | AXIS_V | [2 0 0 0] | 2
[2 0 0 2] | AXIS_H | [0 0 0 2] | 2
[2 0 1 1] | AXIS_V | [2 0 0 0] | 2
[2 0 1 1] | AXIS_H | [0 0 1 1] | 1
[2 0 2 0] | AXIS_V | [2 0 0 0] | 2
[2 0 2 0] | AXIS_H | [0 0 2 0] | 2
```

```
RULE OR &r0 :0 * [L0] ALSO &r8 :2 L0 END END [&r9]
```

### &r9 (export table 9)

- columns: c0: Number
- depth 8, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r2, &r3, &r4, &r8; assignments: 1
- rows per train example: [2, 2, 2]; test: 2

Train example 0: 2 rows
```
c0
1
2
```

Train example 1: 2 rows
```
c0
1
2
```

Train example 2: 2 rows
```
c0
1
2
```

```
INIT Frame [:0] &r9 :1 ^ [L0] axis_elem :0 ^ [L1] END [:1] SKIP [:1] SKIP [&r10] [&r11]
```

### &r10 (export table 10)

- columns: c0: Number, c1: Axis, c2: Box
- depth 9, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r2, &r3, &r4, &r8; assignments: 1
- rows per train example: [6, 6, 6]; test: 6

Train example 0: 6 rows
```
c0 | c1 | c2
1 | AXIS_V | +(0,0)
1 | AXIS_H | +(0,0)
2 | AXIS_V | r0-1 c0-2
2 | AXIS_V | r1-2 c0-2
2 | AXIS_H | r0-2 c0-1
2 | AXIS_H | r0-2 c1-2
```

Train example 1: 6 rows
```
c0 | c1 | c2
1 | AXIS_V | +(0,0)
1 | AXIS_H | +(0,0)
2 | AXIS_V | r0-1 c0-2
2 | AXIS_V | r1-2 c0-2
2 | AXIS_H | r0-2 c0-1
2 | AXIS_H | r0-2 c1-2
```

Train example 2: 6 rows
```
c0 | c1 | c2
1 | AXIS_V | +(0,0)
1 | AXIS_H | +(0,0)
2 | AXIS_V | r0-1 c0-2
2 | AXIS_V | r1-2 c0-2
2 | AXIS_H | r0-2 c0-1
2 | AXIS_H | r0-2 c1-2
```

```
DET &r10 :1 :0 * [L0] :1 * [L1] END :2 * [L2] END [&r12]
```

### &r12 (export table 11)

- columns: c0: Number, c1: Axis, c2: Box
- depth 10, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r2, &r3, &r4, &r8, &r12; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 6
- every row is of a task-wide entry

Task-wide: 6 rows
```
c0 | c1 | c2
1 | AXIS_V | +(0,0)
1 | AXIS_H | +(0,0)
2 | AXIS_V | [0 1 0 0]
2 | AXIS_V | [1 0 0 0]
2 | AXIS_H | [0 0 0 1]
2 | AXIS_H | [0 0 1 0]
```

```
RULE &r0 :0 * [L0] &r12 :1 * [L1] :0 L0 :2 * [L2] END [&r13]
```

### &r13 (export table 12)

- columns: c0: Number, c1: Axis, c2: Box
- depth 11, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r2, &r3, &r4, &r8, &r12; assignments: 1
- rows per train example: [4, 4, 4]; test: 4

Train example 0: 4 rows
```
c0 | c1 | c2
2 | AXIS_V | r0-1 c0-2
2 | AXIS_V | r1-2 c0-2
2 | AXIS_H | r0-2 c0-1
2 | AXIS_H | r0-2 c1-2
```

Train example 1: 4 rows
```
c0 | c1 | c2
2 | AXIS_V | r0-1 c0-2
2 | AXIS_V | r1-2 c0-2
2 | AXIS_H | r0-2 c0-1
2 | AXIS_H | r0-2 c1-2
```

Train example 2: 4 rows
```
c0 | c1 | c2
2 | AXIS_V | r0-1 c0-2
2 | AXIS_V | r1-2 c0-2
2 | AXIS_H | r0-2 c0-1
2 | AXIS_H | r0-2 c1-2
```

```
RULE input :0 * [L0] axis_of :0 * [L1] :1 * [L2] OR margin :0 L0 :1 L1 :2 0 &r13 :1 L2 :2 * [L3] ALSO dist_pair :0 L0 :1 L1 :2 * [L4] :3 * [L5] != L4 0 != L5 0 = L3 0 END END [&r14]
```

### &r14 (export table 13)

- columns: c0: Box, c1: Dir, c2: Axis, c3: Box
- depth 12, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r2, &r3, &r4, &r8, &r12; assignments: 1
- rows per train example: [36, 36, 36]; test: 36

Train example 0: 36 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
4 4 4
4 4 4
4 4 4
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | AXIS_V | r0-1 c0-2
(0,0) | DIR_T | AXIS_V | r1-2 c0-2
(0,0) | DIR_L | AXIS_H | r0-2 c0-1
(0,0) | DIR_L | AXIS_H | r0-2 c1-2
(0,1) | DIR_T | AXIS_V | r0-1 c0-2
(0,1) | DIR_T | AXIS_V | r1-2 c0-2
(0,1) | DIR_L | AXIS_H | +(0,0)
(0,1) | DIR_R | AXIS_H | +(0,0)
(0,2) | DIR_T | AXIS_V | r0-1 c0-2
(0,2) | DIR_T | AXIS_V | r1-2 c0-2
(0,2) | DIR_R | AXIS_H | r0-2 c0-1
(0,2) | DIR_R | AXIS_H | r0-2 c1-2
(1,0) | DIR_T | AXIS_V | +(0,0)
(1,0) | DIR_B | AXIS_V | +(0,0)
(1,0) | DIR_L | AXIS_H | r0-2 c0-1
(1,0) | DIR_L | AXIS_H | r0-2 c1-2
(1,1) | DIR_T | AXIS_V | +(0,0)
(1,1) | DIR_B | AXIS_V | +(0,0)
(1,1) | DIR_L | AXIS_H | +(0,0)
(1,1) | DIR_R | AXIS_H | +(0,0)
(1,2) | DIR_T | AXIS_V | +(0,0)
(1,2) | DIR_B | AXIS_V | +(0,0)
(1,2) | DIR_R | AXIS_H | r0-2 c0-1
(1,2) | DIR_R | AXIS_H | r0-2 c1-2
(2,0) | DIR_B | AXIS_V | r0-1 c0-2
(2,0) | DIR_B | AXIS_V | r1-2 c0-2
(2,0) | DIR_L | AXIS_H | r0-2 c0-1
(2,0) | DIR_L | AXIS_H | r0-2 c1-2
(2,1) | DIR_B | AXIS_V | r0-1 c0-2
(2,1) | DIR_B | AXIS_V | r1-2 c0-2
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
4 4 4
4 4 4
4 4 4
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | AXIS_V | r0-1 c0-2
(0,0) | DIR_T | AXIS_V | r1-2 c0-2
(0,0) | DIR_L | AXIS_H | r0-2 c0-1
(0,0) | DIR_L | AXIS_H | r0-2 c1-2
(0,1) | DIR_T | AXIS_V | r0-1 c0-2
(0,1) | DIR_T | AXIS_V | r1-2 c0-2
(0,1) | DIR_L | AXIS_H | +(0,0)
(0,1) | DIR_R | AXIS_H | +(0,0)
(0,2) | DIR_T | AXIS_V | r0-1 c0-2
(0,2) | DIR_T | AXIS_V | r1-2 c0-2
(0,2) | DIR_R | AXIS_H | r0-2 c0-1
(0,2) | DIR_R | AXIS_H | r0-2 c1-2
(1,0) | DIR_T | AXIS_V | +(0,0)
(1,0) | DIR_B | AXIS_V | +(0,0)
(1,0) | DIR_L | AXIS_H | r0-2 c0-1
(1,0) | DIR_L | AXIS_H | r0-2 c1-2
(1,1) | DIR_T | AXIS_V | +(0,0)
(1,1) | DIR_B | AXIS_V | +(0,0)
(1,1) | DIR_L | AXIS_H | +(0,0)
(1,1) | DIR_R | AXIS_H | +(0,0)
(1,2) | DIR_T | AXIS_V | +(0,0)
(1,2) | DIR_B | AXIS_V | +(0,0)
(1,2) | DIR_R | AXIS_H | r0-2 c0-1
(1,2) | DIR_R | AXIS_H | r0-2 c1-2
(2,0) | DIR_B | AXIS_V | r0-1 c0-2
(2,0) | DIR_B | AXIS_V | r1-2 c0-2
(2,0) | DIR_L | AXIS_H | r0-2 c0-1
(2,0) | DIR_L | AXIS_H | r0-2 c1-2
(2,1) | DIR_B | AXIS_V | r0-1 c0-2
(2,1) | DIR_B | AXIS_V | r1-2 c0-2
```

Train example 2: 36 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
4 4 4
4 4 4
4 4 4
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | AXIS_V | r0-1 c0-2
(0,0) | DIR_T | AXIS_V | r1-2 c0-2
(0,0) | DIR_L | AXIS_H | r0-2 c0-1
(0,0) | DIR_L | AXIS_H | r0-2 c1-2
(0,1) | DIR_T | AXIS_V | r0-1 c0-2
(0,1) | DIR_T | AXIS_V | r1-2 c0-2
(0,1) | DIR_L | AXIS_H | +(0,0)
(0,1) | DIR_R | AXIS_H | +(0,0)
(0,2) | DIR_T | AXIS_V | r0-1 c0-2
(0,2) | DIR_T | AXIS_V | r1-2 c0-2
(0,2) | DIR_R | AXIS_H | r0-2 c0-1
(0,2) | DIR_R | AXIS_H | r0-2 c1-2
(1,0) | DIR_T | AXIS_V | +(0,0)
(1,0) | DIR_B | AXIS_V | +(0,0)
(1,0) | DIR_L | AXIS_H | r0-2 c0-1
(1,0) | DIR_L | AXIS_H | r0-2 c1-2
(1,1) | DIR_T | AXIS_V | +(0,0)
(1,1) | DIR_B | AXIS_V | +(0,0)
(1,1) | DIR_L | AXIS_H | +(0,0)
(1,1) | DIR_R | AXIS_H | +(0,0)
(1,2) | DIR_T | AXIS_V | +(0,0)
(1,2) | DIR_B | AXIS_V | +(0,0)
(1,2) | DIR_R | AXIS_H | r0-2 c0-1
(1,2) | DIR_R | AXIS_H | r0-2 c1-2
(2,0) | DIR_B | AXIS_V | r0-1 c0-2
(2,0) | DIR_B | AXIS_V | r1-2 c0-2
(2,0) | DIR_L | AXIS_H | r0-2 c0-1
(2,0) | DIR_L | AXIS_H | r0-2 c1-2
(2,1) | DIR_B | AXIS_V | r0-1 c0-2
(2,1) | DIR_B | AXIS_V | r1-2 c0-2
```

```
RULE input :0 * [L0] :1 * [L1] perp :0 * [L2] :1 * [L3] &r14 :0 L0 :2 L2 :3 * [L4] &r14 :0 L0 :2 L3 :3 * [L5] compose :0 L4 :1 L5 :2 * [L6] END [&r15]
```

### &r15 (export table 14)

- columns: c0: Box, c1: Axis, c2: Color, c3: Axis, c4: Box, c5: Box, c6: Box
- depth 13, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r2, &r3, &r4, &r8, &r12; assignments: 1
- rows per train example: [50, 50, 50]; test: 50

Train example 0: 50 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
8 4 8
4 2 4
8 4 8
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | AXIS_V | 6 | AXIS_H | r0-1 c0-1 | r0-1 c0-2 | r0-2 c0-1
(0,0) | AXIS_V | 6 | AXIS_H | r0-1 c1-2 | r0-1 c0-2 | r0-2 c1-2
(0,0) | AXIS_V | 6 | AXIS_H | r1-2 c0-1 | r1-2 c0-2 | r0-2 c0-1
(0,0) | AXIS_V | 6 | AXIS_H | r1-2 c1-2 | r1-2 c0-2 | r0-2 c1-2
(0,0) | AXIS_H | 6 | AXIS_V | r0-1 c0-1 | r0-2 c0-1 | r0-1 c0-2
(0,0) | AXIS_H | 6 | AXIS_V | r0-1 c1-2 | r0-2 c1-2 | r0-1 c0-2
(0,0) | AXIS_H | 6 | AXIS_V | r1-2 c0-1 | r0-2 c0-1 | r1-2 c0-2
(0,0) | AXIS_H | 6 | AXIS_V | r1-2 c1-2 | r0-2 c1-2 | r1-2 c0-2
(0,1) | AXIS_V | 5 | AXIS_H | r0-1 c0-2 | r0-1 c0-2 | +(0,0)
(0,1) | AXIS_V | 5 | AXIS_H | r1-2 c0-2 | r1-2 c0-2 | +(0,0)
(0,1) | AXIS_H | 5 | AXIS_V | r0-1 c0-2 | +(0,0) | r0-1 c0-2
(0,1) | AXIS_H | 5 | AXIS_V | r1-2 c0-2 | +(0,0) | r1-2 c0-2
(0,2) | AXIS_V | 5 | AXIS_H | r0-1 c0-1 | r0-1 c0-2 | r0-2 c0-1
(0,2) | AXIS_V | 5 | AXIS_H | r0-1 c1-2 | r0-1 c0-2 | r0-2 c1-2
(0,2) | AXIS_V | 5 | AXIS_H | r1-2 c0-1 | r1-2 c0-2 | r0-2 c0-1
(0,2) | AXIS_V | 5 | AXIS_H | r1-2 c1-2 | r1-2 c0-2 | r0-2 c1-2
(0,2) | AXIS_H | 5 | AXIS_V | r0-1 c0-1 | r0-2 c0-1 | r0-1 c0-2
(0,2) | AXIS_H | 5 | AXIS_V | r0-1 c1-2 | r0-2 c1-2 | r0-1 c0-2
(0,2) | AXIS_H | 5 | AXIS_V | r1-2 c0-1 | r0-2 c0-1 | r1-2 c0-2
(0,2) | AXIS_H | 5 | AXIS_V | r1-2 c1-2 | r0-2 c1-2 | r1-2 c0-2
(1,0) | AXIS_V | 5 | AXIS_H | r0-2 c0-1 | +(0,0) | r0-2 c0-1
(1,0) | AXIS_V | 5 | AXIS_H | r0-2 c1-2 | +(0,0) | r0-2 c1-2
(1,0) | AXIS_H | 5 | AXIS_V | r0-2 c0-1 | r0-2 c0-1 | +(0,0)
(1,0) | AXIS_H | 5 | AXIS_V | r0-2 c1-2 | r0-2 c1-2 | +(0,0)
(1,1) | AXIS_V | 1 | AXIS_H | +(0,0) | +(0,0) | +(0,0)
(1,1) | AXIS_H | 1 | AXIS_V | +(0,0) | +(0,0) | +(0,0)
(1,2) | AXIS_V | 7 | AXIS_H | r0-2 c0-1 | +(0,0) | r0-2 c0-1
(1,2) | AXIS_V | 7 | AXIS_H | r0-2 c1-2 | +(0,0) | r0-2 c1-2
(1,2) | AXIS_H | 7 | AXIS_V | r0-2 c0-1 | r0-2 c0-1 | +(0,0)
(1,2) | AXIS_H | 7 | AXIS_V | r0-2 c1-2 | r0-2 c1-2 | +(0,0)
```

Train example 1: 50 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
8 4 8
4 2 4
8 4 8
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | AXIS_V | 1 | AXIS_H | r0-1 c0-1 | r0-1 c0-2 | r0-2 c0-1
(0,0) | AXIS_V | 1 | AXIS_H | r0-1 c1-2 | r0-1 c0-2 | r0-2 c1-2
(0,0) | AXIS_V | 1 | AXIS_H | r1-2 c0-1 | r1-2 c0-2 | r0-2 c0-1
(0,0) | AXIS_V | 1 | AXIS_H | r1-2 c1-2 | r1-2 c0-2 | r0-2 c1-2
(0,0) | AXIS_H | 1 | AXIS_V | r0-1 c0-1 | r0-2 c0-1 | r0-1 c0-2
(0,0) | AXIS_H | 1 | AXIS_V | r0-1 c1-2 | r0-2 c1-2 | r0-1 c0-2
(0,0) | AXIS_H | 1 | AXIS_V | r1-2 c0-1 | r0-2 c0-1 | r1-2 c0-2
(0,0) | AXIS_H | 1 | AXIS_V | r1-2 c1-2 | r0-2 c1-2 | r1-2 c0-2
(0,1) | AXIS_V | 3 | AXIS_H | r0-1 c0-2 | r0-1 c0-2 | +(0,0)
(0,1) | AXIS_V | 3 | AXIS_H | r1-2 c0-2 | r1-2 c0-2 | +(0,0)
(0,1) | AXIS_H | 3 | AXIS_V | r0-1 c0-2 | +(0,0) | r0-1 c0-2
(0,1) | AXIS_H | 3 | AXIS_V | r1-2 c0-2 | +(0,0) | r1-2 c0-2
(0,2) | AXIS_V | 5 | AXIS_H | r0-1 c0-1 | r0-1 c0-2 | r0-2 c0-1
(0,2) | AXIS_V | 5 | AXIS_H | r0-1 c1-2 | r0-1 c0-2 | r0-2 c1-2
(0,2) | AXIS_V | 5 | AXIS_H | r1-2 c0-1 | r1-2 c0-2 | r0-2 c0-1
(0,2) | AXIS_V | 5 | AXIS_H | r1-2 c1-2 | r1-2 c0-2 | r0-2 c1-2
(0,2) | AXIS_H | 5 | AXIS_V | r0-1 c0-1 | r0-2 c0-1 | r0-1 c0-2
(0,2) | AXIS_H | 5 | AXIS_V | r0-1 c1-2 | r0-2 c1-2 | r0-1 c0-2
(0,2) | AXIS_H | 5 | AXIS_V | r1-2 c0-1 | r0-2 c0-1 | r1-2 c0-2
(0,2) | AXIS_H | 5 | AXIS_V | r1-2 c1-2 | r0-2 c1-2 | r1-2 c0-2
(1,0) | AXIS_V | 1 | AXIS_H | r0-2 c0-1 | +(0,0) | r0-2 c0-1
(1,0) | AXIS_V | 1 | AXIS_H | r0-2 c1-2 | +(0,0) | r0-2 c1-2
(1,0) | AXIS_H | 1 | AXIS_V | r0-2 c0-1 | r0-2 c0-1 | +(0,0)
(1,0) | AXIS_H | 1 | AXIS_V | r0-2 c1-2 | r0-2 c1-2 | +(0,0)
(1,1) | AXIS_V | 2 | AXIS_H | +(0,0) | +(0,0) | +(0,0)
(1,1) | AXIS_H | 2 | AXIS_V | +(0,0) | +(0,0) | +(0,0)
(1,2) | AXIS_V | 8 | AXIS_H | r0-2 c0-1 | +(0,0) | r0-2 c0-1
(1,2) | AXIS_V | 8 | AXIS_H | r0-2 c1-2 | +(0,0) | r0-2 c1-2
(1,2) | AXIS_H | 8 | AXIS_V | r0-2 c0-1 | r0-2 c0-1 | +(0,0)
(1,2) | AXIS_H | 8 | AXIS_V | r0-2 c1-2 | r0-2 c1-2 | +(0,0)
```

Train example 2: 50 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
8 4 8
4 2 4
8 4 8
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | AXIS_V | 2 | AXIS_H | r0-1 c0-1 | r0-1 c0-2 | r0-2 c0-1
(0,0) | AXIS_V | 2 | AXIS_H | r0-1 c1-2 | r0-1 c0-2 | r0-2 c1-2
(0,0) | AXIS_V | 2 | AXIS_H | r1-2 c0-1 | r1-2 c0-2 | r0-2 c0-1
(0,0) | AXIS_V | 2 | AXIS_H | r1-2 c1-2 | r1-2 c0-2 | r0-2 c1-2
(0,0) | AXIS_H | 2 | AXIS_V | r0-1 c0-1 | r0-2 c0-1 | r0-1 c0-2
(0,0) | AXIS_H | 2 | AXIS_V | r0-1 c1-2 | r0-2 c1-2 | r0-1 c0-2
(0,0) | AXIS_H | 2 | AXIS_V | r1-2 c0-1 | r0-2 c0-1 | r1-2 c0-2
(0,0) | AXIS_H | 2 | AXIS_V | r1-2 c1-2 | r0-2 c1-2 | r1-2 c0-2
(0,1) | AXIS_V | 3 | AXIS_H | r0-1 c0-2 | r0-1 c0-2 | +(0,0)
(0,1) | AXIS_V | 3 | AXIS_H | r1-2 c0-2 | r1-2 c0-2 | +(0,0)
(0,1) | AXIS_H | 3 | AXIS_V | r0-1 c0-2 | +(0,0) | r0-1 c0-2
(0,1) | AXIS_H | 3 | AXIS_V | r1-2 c0-2 | +(0,0) | r1-2 c0-2
(0,2) | AXIS_V | 7 | AXIS_H | r0-1 c0-1 | r0-1 c0-2 | r0-2 c0-1
(0,2) | AXIS_V | 7 | AXIS_H | r0-1 c1-2 | r0-1 c0-2 | r0-2 c1-2
(0,2) | AXIS_V | 7 | AXIS_H | r1-2 c0-1 | r1-2 c0-2 | r0-2 c0-1
(0,2) | AXIS_V | 7 | AXIS_H | r1-2 c1-2 | r1-2 c0-2 | r0-2 c1-2
(0,2) | AXIS_H | 7 | AXIS_V | r0-1 c0-1 | r0-2 c0-1 | r0-1 c0-2
(0,2) | AXIS_H | 7 | AXIS_V | r0-1 c1-2 | r0-2 c1-2 | r0-1 c0-2
(0,2) | AXIS_H | 7 | AXIS_V | r1-2 c0-1 | r0-2 c0-1 | r1-2 c0-2
(0,2) | AXIS_H | 7 | AXIS_V | r1-2 c1-2 | r0-2 c1-2 | r1-2 c0-2
(1,0) | AXIS_V | 2 | AXIS_H | r0-2 c0-1 | +(0,0) | r0-2 c0-1
(1,0) | AXIS_V | 2 | AXIS_H | r0-2 c1-2 | +(0,0) | r0-2 c1-2
(1,0) | AXIS_H | 2 | AXIS_V | r0-2 c0-1 | r0-2 c0-1 | +(0,0)
(1,0) | AXIS_H | 2 | AXIS_V | r0-2 c1-2 | r0-2 c1-2 | +(0,0)
(1,1) | AXIS_V | 1 | AXIS_H | +(0,0) | +(0,0) | +(0,0)
(1,1) | AXIS_H | 1 | AXIS_V | +(0,0) | +(0,0) | +(0,0)
(1,2) | AXIS_V | 6 | AXIS_H | r0-2 c0-1 | +(0,0) | r0-2 c0-1
(1,2) | AXIS_V | 6 | AXIS_H | r0-2 c1-2 | +(0,0) | r0-2 c1-2
(1,2) | AXIS_H | 6 | AXIS_V | r0-2 c0-1 | r0-2 c0-1 | +(0,0)
(1,2) | AXIS_H | 6 | AXIS_V | r0-2 c1-2 | r0-2 c1-2 | +(0,0)
```

```
INIT Cardinality [:0] &r15 :1 ^ [L0] dir_elem :0 ^ [L1] END [:1] axis_of :0 L1 :1 * [L2] input :0 * [L3] same_line :0 L2 :1 L0 :2 L3 nearer :0 L1 :1 L3 :2 L0 &r14 :1 L3 :3 L2 :4 * [L4] END [:0] END [:1] :0 L3 :1 L4 END END [:2] SKIP [:2] SKIP [&r16] [&r17] [&r18]
```

### &r16 (export table 15)

- columns: c0: Box, c1: Dir, c2: Number
- depth 15, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r2, &r3, &r4, &r8, &r12; assignments: 1
- rows per train example: [36, 36, 36]; test: 36

Train example 0: 36 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
4 4 4
4 4 4
4 4 4
```
```
c0 | c1 | c2
(0,0) | DIR_T | 0
(0,0) | DIR_B | 3
(0,0) | DIR_L | 0
(0,0) | DIR_R | 3
(0,1) | DIR_T | 0
(0,1) | DIR_B | 3
(0,1) | DIR_L | 2
(0,1) | DIR_R | 2
(0,2) | DIR_T | 0
(0,2) | DIR_B | 3
(0,2) | DIR_L | 3
(0,2) | DIR_R | 0
(1,0) | DIR_T | 2
(1,0) | DIR_B | 2
(1,0) | DIR_L | 0
(1,0) | DIR_R | 3
(1,1) | DIR_T | 2
(1,1) | DIR_B | 2
(1,1) | DIR_L | 2
(1,1) | DIR_R | 2
(1,2) | DIR_T | 2
(1,2) | DIR_B | 2
(1,2) | DIR_L | 3
(1,2) | DIR_R | 0
(2,0) | DIR_T | 3
(2,0) | DIR_B | 0
(2,0) | DIR_L | 0
(2,0) | DIR_R | 3
(2,1) | DIR_T | 3
(2,1) | DIR_B | 0
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
4 4 4
4 4 4
4 4 4
```
```
c0 | c1 | c2
(0,0) | DIR_T | 0
(0,0) | DIR_B | 3
(0,0) | DIR_L | 0
(0,0) | DIR_R | 3
(0,1) | DIR_T | 0
(0,1) | DIR_B | 3
(0,1) | DIR_L | 2
(0,1) | DIR_R | 2
(0,2) | DIR_T | 0
(0,2) | DIR_B | 3
(0,2) | DIR_L | 3
(0,2) | DIR_R | 0
(1,0) | DIR_T | 2
(1,0) | DIR_B | 2
(1,0) | DIR_L | 0
(1,0) | DIR_R | 3
(1,1) | DIR_T | 2
(1,1) | DIR_B | 2
(1,1) | DIR_L | 2
(1,1) | DIR_R | 2
(1,2) | DIR_T | 2
(1,2) | DIR_B | 2
(1,2) | DIR_L | 3
(1,2) | DIR_R | 0
(2,0) | DIR_T | 3
(2,0) | DIR_B | 0
(2,0) | DIR_L | 0
(2,0) | DIR_R | 3
(2,1) | DIR_T | 3
(2,1) | DIR_B | 0
```

Train example 2: 36 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
4 4 4
4 4 4
4 4 4
```
```
c0 | c1 | c2
(0,0) | DIR_T | 0
(0,0) | DIR_B | 3
(0,0) | DIR_L | 0
(0,0) | DIR_R | 3
(0,1) | DIR_T | 0
(0,1) | DIR_B | 3
(0,1) | DIR_L | 2
(0,1) | DIR_R | 2
(0,2) | DIR_T | 0
(0,2) | DIR_B | 3
(0,2) | DIR_L | 3
(0,2) | DIR_R | 0
(1,0) | DIR_T | 2
(1,0) | DIR_B | 2
(1,0) | DIR_L | 0
(1,0) | DIR_R | 3
(1,1) | DIR_T | 2
(1,1) | DIR_B | 2
(1,1) | DIR_L | 2
(1,1) | DIR_R | 2
(1,2) | DIR_T | 2
(1,2) | DIR_B | 2
(1,2) | DIR_L | 3
(1,2) | DIR_R | 0
(2,0) | DIR_T | 3
(2,0) | DIR_B | 0
(2,0) | DIR_L | 0
(2,0) | DIR_R | 3
(2,1) | DIR_T | 3
(2,1) | DIR_B | 0
```

### &r17 (export table 16)

- columns: c0: Box, c1: Dir, c2: Box, c3: Box
- depth 14, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r2, &r3, &r4, &r8, &r12; assignments: 1
- rows per train example: [60, 60, 60]; test: 60

Train example 0: 60 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
6 7 6
7 8 7
6 7 6
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_B | (1,0) | +(0,0)
(0,0) | DIR_B | (2,0) | r0-1 c0-2
(0,0) | DIR_B | (2,0) | r1-2 c0-2
(0,0) | DIR_R | (0,1) | +(0,0)
(0,0) | DIR_R | (0,2) | r0-2 c0-1
(0,0) | DIR_R | (0,2) | r0-2 c1-2
(0,1) | DIR_B | (1,1) | +(0,0)
(0,1) | DIR_B | (2,1) | r0-1 c0-2
(0,1) | DIR_B | (2,1) | r1-2 c0-2
(0,1) | DIR_L | (0,0) | r0-2 c0-1
(0,1) | DIR_L | (0,0) | r0-2 c1-2
(0,1) | DIR_R | (0,2) | r0-2 c0-1
(0,1) | DIR_R | (0,2) | r0-2 c1-2
(0,2) | DIR_B | (1,2) | +(0,0)
(0,2) | DIR_B | (2,2) | r0-1 c0-2
(0,2) | DIR_B | (2,2) | r1-2 c0-2
(0,2) | DIR_L | (0,0) | r0-2 c0-1
(0,2) | DIR_L | (0,0) | r0-2 c1-2
(0,2) | DIR_L | (0,1) | +(0,0)
(1,0) | DIR_T | (0,0) | r0-1 c0-2
(1,0) | DIR_T | (0,0) | r1-2 c0-2
(1,0) | DIR_B | (2,0) | r0-1 c0-2
(1,0) | DIR_B | (2,0) | r1-2 c0-2
(1,0) | DIR_R | (1,1) | +(0,0)
(1,0) | DIR_R | (1,2) | r0-2 c0-1
(1,0) | DIR_R | (1,2) | r0-2 c1-2
(1,1) | DIR_T | (0,1) | r0-1 c0-2
(1,1) | DIR_T | (0,1) | r1-2 c0-2
(1,1) | DIR_B | (2,1) | r0-1 c0-2
(1,1) | DIR_B | (2,1) | r1-2 c0-2
```

Train example 1: 60 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
6 7 6
7 8 7
6 7 6
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_B | (1,0) | +(0,0)
(0,0) | DIR_B | (2,0) | r0-1 c0-2
(0,0) | DIR_B | (2,0) | r1-2 c0-2
(0,0) | DIR_R | (0,1) | +(0,0)
(0,0) | DIR_R | (0,2) | r0-2 c0-1
(0,0) | DIR_R | (0,2) | r0-2 c1-2
(0,1) | DIR_B | (1,1) | +(0,0)
(0,1) | DIR_B | (2,1) | r0-1 c0-2
(0,1) | DIR_B | (2,1) | r1-2 c0-2
(0,1) | DIR_L | (0,0) | r0-2 c0-1
(0,1) | DIR_L | (0,0) | r0-2 c1-2
(0,1) | DIR_R | (0,2) | r0-2 c0-1
(0,1) | DIR_R | (0,2) | r0-2 c1-2
(0,2) | DIR_B | (1,2) | +(0,0)
(0,2) | DIR_B | (2,2) | r0-1 c0-2
(0,2) | DIR_B | (2,2) | r1-2 c0-2
(0,2) | DIR_L | (0,0) | r0-2 c0-1
(0,2) | DIR_L | (0,0) | r0-2 c1-2
(0,2) | DIR_L | (0,1) | +(0,0)
(1,0) | DIR_T | (0,0) | r0-1 c0-2
(1,0) | DIR_T | (0,0) | r1-2 c0-2
(1,0) | DIR_B | (2,0) | r0-1 c0-2
(1,0) | DIR_B | (2,0) | r1-2 c0-2
(1,0) | DIR_R | (1,1) | +(0,0)
(1,0) | DIR_R | (1,2) | r0-2 c0-1
(1,0) | DIR_R | (1,2) | r0-2 c1-2
(1,1) | DIR_T | (0,1) | r0-1 c0-2
(1,1) | DIR_T | (0,1) | r1-2 c0-2
(1,1) | DIR_B | (2,1) | r0-1 c0-2
(1,1) | DIR_B | (2,1) | r1-2 c0-2
```

Train example 2: 60 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
6 7 6
7 8 7
6 7 6
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_B | (1,0) | +(0,0)
(0,0) | DIR_B | (2,0) | r0-1 c0-2
(0,0) | DIR_B | (2,0) | r1-2 c0-2
(0,0) | DIR_R | (0,1) | +(0,0)
(0,0) | DIR_R | (0,2) | r0-2 c0-1
(0,0) | DIR_R | (0,2) | r0-2 c1-2
(0,1) | DIR_B | (1,1) | +(0,0)
(0,1) | DIR_B | (2,1) | r0-1 c0-2
(0,1) | DIR_B | (2,1) | r1-2 c0-2
(0,1) | DIR_L | (0,0) | r0-2 c0-1
(0,1) | DIR_L | (0,0) | r0-2 c1-2
(0,1) | DIR_R | (0,2) | r0-2 c0-1
(0,1) | DIR_R | (0,2) | r0-2 c1-2
(0,2) | DIR_B | (1,2) | +(0,0)
(0,2) | DIR_B | (2,2) | r0-1 c0-2
(0,2) | DIR_B | (2,2) | r1-2 c0-2
(0,2) | DIR_L | (0,0) | r0-2 c0-1
(0,2) | DIR_L | (0,0) | r0-2 c1-2
(0,2) | DIR_L | (0,1) | +(0,0)
(1,0) | DIR_T | (0,0) | r0-1 c0-2
(1,0) | DIR_T | (0,0) | r1-2 c0-2
(1,0) | DIR_B | (2,0) | r0-1 c0-2
(1,0) | DIR_B | (2,0) | r1-2 c0-2
(1,0) | DIR_R | (1,1) | +(0,0)
(1,0) | DIR_R | (1,2) | r0-2 c0-1
(1,0) | DIR_R | (1,2) | r0-2 c1-2
(1,1) | DIR_T | (0,1) | r0-1 c0-2
(1,1) | DIR_T | (0,1) | r1-2 c0-2
(1,1) | DIR_B | (2,1) | r0-1 c0-2
(1,1) | DIR_B | (2,1) | r1-2 c0-2
```

```
RULE &r16 :0 :1 * [L0] :0 * [L1] END :1 * [L2] edge_inset :0 L0 :1 L2 :2 * [L3] END [&r19]
```

### &r19 (export table 17)

- columns: c0: Box, c1: Dir, c2: Box, c3: Number
- depth 16, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r2, &r3, &r4, &r8, &r12; assignments: 1
- rows per train example: [36, 36, 36]; test: 36

Train example 0: 36 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
4 4 4
4 4 4
4 4 4
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | +(0,0) | 0
(0,0) | DIR_B | [0 3 0 0] | 3
(0,0) | DIR_L | +(0,0) | 0
(0,0) | DIR_R | [0 0 0 3] | 3
(0,1) | DIR_T | +(0,0) | 0
(0,1) | DIR_B | [0 3 0 0] | 3
(0,1) | DIR_L | r0-2 c2-2 | 2
(0,1) | DIR_R | r0-2 c0-0 | 2
(0,2) | DIR_T | +(0,0) | 0
(0,2) | DIR_B | [0 3 0 0] | 3
(0,2) | DIR_L | [0 0 3 0] | 3
(0,2) | DIR_R | +(0,0) | 0
(1,0) | DIR_T | r2-2 c0-2 | 2
(1,0) | DIR_B | r0-0 c0-2 | 2
(1,0) | DIR_L | +(0,0) | 0
(1,0) | DIR_R | [0 0 0 3] | 3
(1,1) | DIR_T | r2-2 c0-2 | 2
(1,1) | DIR_B | r0-0 c0-2 | 2
(1,1) | DIR_L | r0-2 c2-2 | 2
(1,1) | DIR_R | r0-2 c0-0 | 2
(1,2) | DIR_T | r2-2 c0-2 | 2
(1,2) | DIR_B | r0-0 c0-2 | 2
(1,2) | DIR_L | [0 0 3 0] | 3
(1,2) | DIR_R | +(0,0) | 0
(2,0) | DIR_T | [3 0 0 0] | 3
(2,0) | DIR_B | +(0,0) | 0
(2,0) | DIR_L | +(0,0) | 0
(2,0) | DIR_R | [0 0 0 3] | 3
(2,1) | DIR_T | [3 0 0 0] | 3
(2,1) | DIR_B | +(0,0) | 0
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
4 4 4
4 4 4
4 4 4
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | +(0,0) | 0
(0,0) | DIR_B | [0 3 0 0] | 3
(0,0) | DIR_L | +(0,0) | 0
(0,0) | DIR_R | [0 0 0 3] | 3
(0,1) | DIR_T | +(0,0) | 0
(0,1) | DIR_B | [0 3 0 0] | 3
(0,1) | DIR_L | r0-2 c2-2 | 2
(0,1) | DIR_R | r0-2 c0-0 | 2
(0,2) | DIR_T | +(0,0) | 0
(0,2) | DIR_B | [0 3 0 0] | 3
(0,2) | DIR_L | [0 0 3 0] | 3
(0,2) | DIR_R | +(0,0) | 0
(1,0) | DIR_T | r2-2 c0-2 | 2
(1,0) | DIR_B | r0-0 c0-2 | 2
(1,0) | DIR_L | +(0,0) | 0
(1,0) | DIR_R | [0 0 0 3] | 3
(1,1) | DIR_T | r2-2 c0-2 | 2
(1,1) | DIR_B | r0-0 c0-2 | 2
(1,1) | DIR_L | r0-2 c2-2 | 2
(1,1) | DIR_R | r0-2 c0-0 | 2
(1,2) | DIR_T | r2-2 c0-2 | 2
(1,2) | DIR_B | r0-0 c0-2 | 2
(1,2) | DIR_L | [0 0 3 0] | 3
(1,2) | DIR_R | +(0,0) | 0
(2,0) | DIR_T | [3 0 0 0] | 3
(2,0) | DIR_B | +(0,0) | 0
(2,0) | DIR_L | +(0,0) | 0
(2,0) | DIR_R | [0 0 0 3] | 3
(2,1) | DIR_T | [3 0 0 0] | 3
(2,1) | DIR_B | +(0,0) | 0
```

Train example 2: 36 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
4 4 4
4 4 4
4 4 4
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | +(0,0) | 0
(0,0) | DIR_B | [0 3 0 0] | 3
(0,0) | DIR_L | +(0,0) | 0
(0,0) | DIR_R | [0 0 0 3] | 3
(0,1) | DIR_T | +(0,0) | 0
(0,1) | DIR_B | [0 3 0 0] | 3
(0,1) | DIR_L | r0-2 c2-2 | 2
(0,1) | DIR_R | r0-2 c0-0 | 2
(0,2) | DIR_T | +(0,0) | 0
(0,2) | DIR_B | [0 3 0 0] | 3
(0,2) | DIR_L | [0 0 3 0] | 3
(0,2) | DIR_R | +(0,0) | 0
(1,0) | DIR_T | r2-2 c0-2 | 2
(1,0) | DIR_B | r0-0 c0-2 | 2
(1,0) | DIR_L | +(0,0) | 0
(1,0) | DIR_R | [0 0 0 3] | 3
(1,1) | DIR_T | r2-2 c0-2 | 2
(1,1) | DIR_B | r0-0 c0-2 | 2
(1,1) | DIR_L | r0-2 c2-2 | 2
(1,1) | DIR_R | r0-2 c0-0 | 2
(1,2) | DIR_T | r2-2 c0-2 | 2
(1,2) | DIR_B | r0-0 c0-2 | 2
(1,2) | DIR_L | [0 0 3 0] | 3
(1,2) | DIR_R | +(0,0) | 0
(2,0) | DIR_T | [3 0 0 0] | 3
(2,0) | DIR_B | +(0,0) | 0
(2,0) | DIR_L | +(0,0) | 0
(2,0) | DIR_R | [0 0 0 3] | 3
(2,1) | DIR_T | [3 0 0 0] | 3
(2,1) | DIR_B | +(0,0) | 0
```

```
RULE axis_of :0 * [L0] :1 * [L1] opposite :0 L0 :1 * [L2] &r19 :0 L0 :1 * [L3] :3 * [L4] &r19 :0 L2 :1 L3 :3 * [L5] compose :0 L4 :1 L5 :2 * [L6] END [&r20]
```

### &r20 (export table 18)

- columns: c0: Dir, c1: Box, c2: Axis, c3: Dir, c4: Box, c5: Box, c6: Box
- depth 17, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r2, &r3, &r4, &r8, &r12; assignments: 1
- rows per train example: [36, 36, 36]; test: 36

Train example 0: 36 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
4 4 4
4 4 4
4 4 4
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
DIR_T | (0,0) | AXIS_V | DIR_B | [0 3 0 0] | +(0,0) | [0 3 0 0]
DIR_T | (0,1) | AXIS_V | DIR_B | [0 3 0 0] | +(0,0) | [0 3 0 0]
DIR_T | (0,2) | AXIS_V | DIR_B | [0 3 0 0] | +(0,0) | [0 3 0 0]
DIR_T | (1,0) | AXIS_V | DIR_B | [2 2 0 0] | r2-2 c0-2 | r0-0 c0-2
DIR_T | (1,1) | AXIS_V | DIR_B | [2 2 0 0] | r2-2 c0-2 | r0-0 c0-2
DIR_T | (1,2) | AXIS_V | DIR_B | [2 2 0 0] | r2-2 c0-2 | r0-0 c0-2
DIR_T | (2,0) | AXIS_V | DIR_B | [3 0 0 0] | [3 0 0 0] | +(0,0)
DIR_T | (2,1) | AXIS_V | DIR_B | [3 0 0 0] | [3 0 0 0] | +(0,0)
DIR_T | (2,2) | AXIS_V | DIR_B | [3 0 0 0] | [3 0 0 0] | +(0,0)
DIR_B | (0,0) | AXIS_V | DIR_T | [0 3 0 0] | [0 3 0 0] | +(0,0)
DIR_B | (0,1) | AXIS_V | DIR_T | [0 3 0 0] | [0 3 0 0] | +(0,0)
DIR_B | (0,2) | AXIS_V | DIR_T | [0 3 0 0] | [0 3 0 0] | +(0,0)
DIR_B | (1,0) | AXIS_V | DIR_T | [2 2 0 0] | r0-0 c0-2 | r2-2 c0-2
DIR_B | (1,1) | AXIS_V | DIR_T | [2 2 0 0] | r0-0 c0-2 | r2-2 c0-2
DIR_B | (1,2) | AXIS_V | DIR_T | [2 2 0 0] | r0-0 c0-2 | r2-2 c0-2
DIR_B | (2,0) | AXIS_V | DIR_T | [3 0 0 0] | +(0,0) | [3 0 0 0]
DIR_B | (2,1) | AXIS_V | DIR_T | [3 0 0 0] | +(0,0) | [3 0 0 0]
DIR_B | (2,2) | AXIS_V | DIR_T | [3 0 0 0] | +(0,0) | [3 0 0 0]
DIR_L | (0,0) | AXIS_H | DIR_R | [0 0 0 3] | +(0,0) | [0 0 0 3]
DIR_L | (0,1) | AXIS_H | DIR_R | [0 0 2 2] | r0-2 c2-2 | r0-2 c0-0
DIR_L | (0,2) | AXIS_H | DIR_R | [0 0 3 0] | [0 0 3 0] | +(0,0)
DIR_L | (1,0) | AXIS_H | DIR_R | [0 0 0 3] | +(0,0) | [0 0 0 3]
DIR_L | (1,1) | AXIS_H | DIR_R | [0 0 2 2] | r0-2 c2-2 | r0-2 c0-0
DIR_L | (1,2) | AXIS_H | DIR_R | [0 0 3 0] | [0 0 3 0] | +(0,0)
DIR_L | (2,0) | AXIS_H | DIR_R | [0 0 0 3] | +(0,0) | [0 0 0 3]
DIR_L | (2,1) | AXIS_H | DIR_R | [0 0 2 2] | r0-2 c2-2 | r0-2 c0-0
DIR_L | (2,2) | AXIS_H | DIR_R | [0 0 3 0] | [0 0 3 0] | +(0,0)
DIR_R | (0,0) | AXIS_H | DIR_L | [0 0 0 3] | [0 0 0 3] | +(0,0)
DIR_R | (0,1) | AXIS_H | DIR_L | [0 0 2 2] | r0-2 c0-0 | r0-2 c2-2
DIR_R | (0,2) | AXIS_H | DIR_L | [0 0 3 0] | +(0,0) | [0 0 3 0]
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
4 4 4
4 4 4
4 4 4
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
DIR_T | (0,0) | AXIS_V | DIR_B | [0 3 0 0] | +(0,0) | [0 3 0 0]
DIR_T | (0,1) | AXIS_V | DIR_B | [0 3 0 0] | +(0,0) | [0 3 0 0]
DIR_T | (0,2) | AXIS_V | DIR_B | [0 3 0 0] | +(0,0) | [0 3 0 0]
DIR_T | (1,0) | AXIS_V | DIR_B | [2 2 0 0] | r2-2 c0-2 | r0-0 c0-2
DIR_T | (1,1) | AXIS_V | DIR_B | [2 2 0 0] | r2-2 c0-2 | r0-0 c0-2
DIR_T | (1,2) | AXIS_V | DIR_B | [2 2 0 0] | r2-2 c0-2 | r0-0 c0-2
DIR_T | (2,0) | AXIS_V | DIR_B | [3 0 0 0] | [3 0 0 0] | +(0,0)
DIR_T | (2,1) | AXIS_V | DIR_B | [3 0 0 0] | [3 0 0 0] | +(0,0)
DIR_T | (2,2) | AXIS_V | DIR_B | [3 0 0 0] | [3 0 0 0] | +(0,0)
DIR_B | (0,0) | AXIS_V | DIR_T | [0 3 0 0] | [0 3 0 0] | +(0,0)
DIR_B | (0,1) | AXIS_V | DIR_T | [0 3 0 0] | [0 3 0 0] | +(0,0)
DIR_B | (0,2) | AXIS_V | DIR_T | [0 3 0 0] | [0 3 0 0] | +(0,0)
DIR_B | (1,0) | AXIS_V | DIR_T | [2 2 0 0] | r0-0 c0-2 | r2-2 c0-2
DIR_B | (1,1) | AXIS_V | DIR_T | [2 2 0 0] | r0-0 c0-2 | r2-2 c0-2
DIR_B | (1,2) | AXIS_V | DIR_T | [2 2 0 0] | r0-0 c0-2 | r2-2 c0-2
DIR_B | (2,0) | AXIS_V | DIR_T | [3 0 0 0] | +(0,0) | [3 0 0 0]
DIR_B | (2,1) | AXIS_V | DIR_T | [3 0 0 0] | +(0,0) | [3 0 0 0]
DIR_B | (2,2) | AXIS_V | DIR_T | [3 0 0 0] | +(0,0) | [3 0 0 0]
DIR_L | (0,0) | AXIS_H | DIR_R | [0 0 0 3] | +(0,0) | [0 0 0 3]
DIR_L | (0,1) | AXIS_H | DIR_R | [0 0 2 2] | r0-2 c2-2 | r0-2 c0-0
DIR_L | (0,2) | AXIS_H | DIR_R | [0 0 3 0] | [0 0 3 0] | +(0,0)
DIR_L | (1,0) | AXIS_H | DIR_R | [0 0 0 3] | +(0,0) | [0 0 0 3]
DIR_L | (1,1) | AXIS_H | DIR_R | [0 0 2 2] | r0-2 c2-2 | r0-2 c0-0
DIR_L | (1,2) | AXIS_H | DIR_R | [0 0 3 0] | [0 0 3 0] | +(0,0)
DIR_L | (2,0) | AXIS_H | DIR_R | [0 0 0 3] | +(0,0) | [0 0 0 3]
DIR_L | (2,1) | AXIS_H | DIR_R | [0 0 2 2] | r0-2 c2-2 | r0-2 c0-0
DIR_L | (2,2) | AXIS_H | DIR_R | [0 0 3 0] | [0 0 3 0] | +(0,0)
DIR_R | (0,0) | AXIS_H | DIR_L | [0 0 0 3] | [0 0 0 3] | +(0,0)
DIR_R | (0,1) | AXIS_H | DIR_L | [0 0 2 2] | r0-2 c0-0 | r0-2 c2-2
DIR_R | (0,2) | AXIS_H | DIR_L | [0 0 3 0] | +(0,0) | [0 0 3 0]
```

Train example 2: 36 rows, the first 30 shown
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
4 4 4
4 4 4
4 4 4
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
DIR_T | (0,0) | AXIS_V | DIR_B | [0 3 0 0] | +(0,0) | [0 3 0 0]
DIR_T | (0,1) | AXIS_V | DIR_B | [0 3 0 0] | +(0,0) | [0 3 0 0]
DIR_T | (0,2) | AXIS_V | DIR_B | [0 3 0 0] | +(0,0) | [0 3 0 0]
DIR_T | (1,0) | AXIS_V | DIR_B | [2 2 0 0] | r2-2 c0-2 | r0-0 c0-2
DIR_T | (1,1) | AXIS_V | DIR_B | [2 2 0 0] | r2-2 c0-2 | r0-0 c0-2
DIR_T | (1,2) | AXIS_V | DIR_B | [2 2 0 0] | r2-2 c0-2 | r0-0 c0-2
DIR_T | (2,0) | AXIS_V | DIR_B | [3 0 0 0] | [3 0 0 0] | +(0,0)
DIR_T | (2,1) | AXIS_V | DIR_B | [3 0 0 0] | [3 0 0 0] | +(0,0)
DIR_T | (2,2) | AXIS_V | DIR_B | [3 0 0 0] | [3 0 0 0] | +(0,0)
DIR_B | (0,0) | AXIS_V | DIR_T | [0 3 0 0] | [0 3 0 0] | +(0,0)
DIR_B | (0,1) | AXIS_V | DIR_T | [0 3 0 0] | [0 3 0 0] | +(0,0)
DIR_B | (0,2) | AXIS_V | DIR_T | [0 3 0 0] | [0 3 0 0] | +(0,0)
DIR_B | (1,0) | AXIS_V | DIR_T | [2 2 0 0] | r0-0 c0-2 | r2-2 c0-2
DIR_B | (1,1) | AXIS_V | DIR_T | [2 2 0 0] | r0-0 c0-2 | r2-2 c0-2
DIR_B | (1,2) | AXIS_V | DIR_T | [2 2 0 0] | r0-0 c0-2 | r2-2 c0-2
DIR_B | (2,0) | AXIS_V | DIR_T | [3 0 0 0] | +(0,0) | [3 0 0 0]
DIR_B | (2,1) | AXIS_V | DIR_T | [3 0 0 0] | +(0,0) | [3 0 0 0]
DIR_B | (2,2) | AXIS_V | DIR_T | [3 0 0 0] | +(0,0) | [3 0 0 0]
DIR_L | (0,0) | AXIS_H | DIR_R | [0 0 0 3] | +(0,0) | [0 0 0 3]
DIR_L | (0,1) | AXIS_H | DIR_R | [0 0 2 2] | r0-2 c2-2 | r0-2 c0-0
DIR_L | (0,2) | AXIS_H | DIR_R | [0 0 3 0] | [0 0 3 0] | +(0,0)
DIR_L | (1,0) | AXIS_H | DIR_R | [0 0 0 3] | +(0,0) | [0 0 0 3]
DIR_L | (1,1) | AXIS_H | DIR_R | [0 0 2 2] | r0-2 c2-2 | r0-2 c0-0
DIR_L | (1,2) | AXIS_H | DIR_R | [0 0 3 0] | [0 0 3 0] | +(0,0)
DIR_L | (2,0) | AXIS_H | DIR_R | [0 0 0 3] | +(0,0) | [0 0 0 3]
DIR_L | (2,1) | AXIS_H | DIR_R | [0 0 2 2] | r0-2 c2-2 | r0-2 c0-0
DIR_L | (2,2) | AXIS_H | DIR_R | [0 0 3 0] | [0 0 3 0] | +(0,0)
DIR_R | (0,0) | AXIS_H | DIR_L | [0 0 0 3] | [0 0 0 3] | +(0,0)
DIR_R | (0,1) | AXIS_H | DIR_L | [0 0 2 2] | r0-2 c0-0 | r0-2 c2-2
DIR_R | (0,2) | AXIS_H | DIR_L | [0 0 3 0] | +(0,0) | [0 0 3 0]
```

```
RULE perp :0 * [L0] :1 * [L1] &r20 :1 L0 :3 * [L2] :6 * [L3] &r20 :1 L1 :3 L2 :6 * [L4] compose :0 L3 :1 L4 :2 * [L5] END [&r21]
```

### &r21 (export table 19)

- columns: c0: Axis, c1: Axis, c2: Box, c3: Box, c4: Box, c5: Box
- depth 18, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r2, &r3, &r4, &r8, &r12; assignments: 1
- rows per train example: [18, 18, 18]; test: 18

Train example 0: 18 rows
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2
2 2 2
2 2 2
```
```
c0 | c1 | c2 | c3 | c4 | c5
AXIS_V | AXIS_H | (0,0) | [0 3 0 3] | [0 3 0 0] | [0 0 0 3]
AXIS_V | AXIS_H | (0,1) | [0 3 2 2] | [0 3 0 0] | [0 0 2 2]
AXIS_V | AXIS_H | (0,2) | [0 3 3 0] | [0 3 0 0] | [0 0 3 0]
AXIS_V | AXIS_H | (1,0) | [2 2 0 3] | [2 2 0 0] | [0 0 0 3]
AXIS_V | AXIS_H | (1,1) | (2,2)out | [2 2 0 0] | [0 0 2 2]
AXIS_V | AXIS_H | (1,2) | [2 2 3 0] | [2 2 0 0] | [0 0 3 0]
AXIS_V | AXIS_H | (2,0) | [3 0 0 3] | [3 0 0 0] | [0 0 0 3]
AXIS_V | AXIS_H | (2,1) | [3 0 2 2] | [3 0 0 0] | [0 0 2 2]
AXIS_V | AXIS_H | (2,2) | [3 0 3 0] | [3 0 0 0] | [0 0 3 0]
AXIS_H | AXIS_V | (0,0) | [0 3 0 3] | [0 0 0 3] | [0 3 0 0]
AXIS_H | AXIS_V | (0,1) | [0 3 2 2] | [0 0 2 2] | [0 3 0 0]
AXIS_H | AXIS_V | (0,2) | [0 3 3 0] | [0 0 3 0] | [0 3 0 0]
AXIS_H | AXIS_V | (1,0) | [2 2 0 3] | [0 0 0 3] | [2 2 0 0]
AXIS_H | AXIS_V | (1,1) | (2,2)out | [0 0 2 2] | [2 2 0 0]
AXIS_H | AXIS_V | (1,2) | [2 2 3 0] | [0 0 3 0] | [2 2 0 0]
AXIS_H | AXIS_V | (2,0) | [3 0 0 3] | [0 0 0 3] | [3 0 0 0]
AXIS_H | AXIS_V | (2,1) | [3 0 2 2] | [0 0 2 2] | [3 0 0 0]
AXIS_H | AXIS_V | (2,2) | [3 0 3 0] | [0 0 3 0] | [3 0 0 0]
```

Train example 1: 18 rows
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2
2 2 2
2 2 2
```
```
c0 | c1 | c2 | c3 | c4 | c5
AXIS_V | AXIS_H | (0,0) | [0 3 0 3] | [0 3 0 0] | [0 0 0 3]
AXIS_V | AXIS_H | (0,1) | [0 3 2 2] | [0 3 0 0] | [0 0 2 2]
AXIS_V | AXIS_H | (0,2) | [0 3 3 0] | [0 3 0 0] | [0 0 3 0]
AXIS_V | AXIS_H | (1,0) | [2 2 0 3] | [2 2 0 0] | [0 0 0 3]
AXIS_V | AXIS_H | (1,1) | (2,2)out | [2 2 0 0] | [0 0 2 2]
AXIS_V | AXIS_H | (1,2) | [2 2 3 0] | [2 2 0 0] | [0 0 3 0]
AXIS_V | AXIS_H | (2,0) | [3 0 0 3] | [3 0 0 0] | [0 0 0 3]
AXIS_V | AXIS_H | (2,1) | [3 0 2 2] | [3 0 0 0] | [0 0 2 2]
AXIS_V | AXIS_H | (2,2) | [3 0 3 0] | [3 0 0 0] | [0 0 3 0]
AXIS_H | AXIS_V | (0,0) | [0 3 0 3] | [0 0 0 3] | [0 3 0 0]
AXIS_H | AXIS_V | (0,1) | [0 3 2 2] | [0 0 2 2] | [0 3 0 0]
AXIS_H | AXIS_V | (0,2) | [0 3 3 0] | [0 0 3 0] | [0 3 0 0]
AXIS_H | AXIS_V | (1,0) | [2 2 0 3] | [0 0 0 3] | [2 2 0 0]
AXIS_H | AXIS_V | (1,1) | (2,2)out | [0 0 2 2] | [2 2 0 0]
AXIS_H | AXIS_V | (1,2) | [2 2 3 0] | [0 0 3 0] | [2 2 0 0]
AXIS_H | AXIS_V | (2,0) | [3 0 0 3] | [0 0 0 3] | [3 0 0 0]
AXIS_H | AXIS_V | (2,1) | [3 0 2 2] | [0 0 2 2] | [3 0 0 0]
AXIS_H | AXIS_V | (2,2) | [3 0 3 0] | [0 0 3 0] | [3 0 0 0]
```

Train example 2: 18 rows
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2
2 2 2
2 2 2
```
```
c0 | c1 | c2 | c3 | c4 | c5
AXIS_V | AXIS_H | (0,0) | [0 3 0 3] | [0 3 0 0] | [0 0 0 3]
AXIS_V | AXIS_H | (0,1) | [0 3 2 2] | [0 3 0 0] | [0 0 2 2]
AXIS_V | AXIS_H | (0,2) | [0 3 3 0] | [0 3 0 0] | [0 0 3 0]
AXIS_V | AXIS_H | (1,0) | [2 2 0 3] | [2 2 0 0] | [0 0 0 3]
AXIS_V | AXIS_H | (1,1) | (2,2)out | [2 2 0 0] | [0 0 2 2]
AXIS_V | AXIS_H | (1,2) | [2 2 3 0] | [2 2 0 0] | [0 0 3 0]
AXIS_V | AXIS_H | (2,0) | [3 0 0 3] | [3 0 0 0] | [0 0 0 3]
AXIS_V | AXIS_H | (2,1) | [3 0 2 2] | [3 0 0 0] | [0 0 2 2]
AXIS_V | AXIS_H | (2,2) | [3 0 3 0] | [3 0 0 0] | [0 0 3 0]
AXIS_H | AXIS_V | (0,0) | [0 3 0 3] | [0 0 0 3] | [0 3 0 0]
AXIS_H | AXIS_V | (0,1) | [0 3 2 2] | [0 0 2 2] | [0 3 0 0]
AXIS_H | AXIS_V | (0,2) | [0 3 3 0] | [0 0 3 0] | [0 3 0 0]
AXIS_H | AXIS_V | (1,0) | [2 2 0 3] | [0 0 0 3] | [2 2 0 0]
AXIS_H | AXIS_V | (1,1) | (2,2)out | [0 0 2 2] | [2 2 0 0]
AXIS_H | AXIS_V | (1,2) | [2 2 3 0] | [0 0 3 0] | [2 2 0 0]
AXIS_H | AXIS_V | (2,0) | [3 0 0 3] | [0 0 0 3] | [3 0 0 0]
AXIS_H | AXIS_V | (2,1) | [3 0 2 2] | [0 0 2 2] | [3 0 0 0]
AXIS_H | AXIS_V | (2,2) | [3 0 3 0] | [0 0 3 0] | [3 0 0 0]
```

```
RULE &r15 :0 * [L0] :6 * [L1] :1 * [L2] &r21 :2 L0 :5 * [L3] compose :0 L3 :1 L1 :2 * [L4] END [&r22]
```

### &r22 (export table 20)

- columns: c0: Box, c1: Box, c2: Color, c3: Box, c4: Box
- depth 19, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r2, &r3, &r4, &r8, &r12; assignments: 1
- rows per train example: [25, 25, 25]; test: 25

Train example 0: 25 rows
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
4 2 4
2 1 2
4 2 4
```
```
c0 | c1 | c2 | c3 | c4
(0,0) | (0,0)out | 6 | [0 3 0 3] | r0-1 c0-1
(0,0) | (0,1)out | 6 | [0 3 0 3] | r0-1 c1-2
(0,0) | (1,0)out | 6 | [0 3 0 3] | r1-2 c0-1
(0,0) | (1,1)out | 6 | [0 3 0 3] | r1-2 c1-2
(0,1) | (0,2)out | 5 | [0 3 2 2] | r0-1 c0-2
(0,1) | (1,2)out | 5 | [0 3 2 2] | r1-2 c0-2
(0,2) | (0,3)out | 5 | [0 3 3 0] | r0-1 c0-1
(0,2) | (0,4)out | 5 | [0 3 3 0] | r0-1 c1-2
(0,2) | (1,3)out | 5 | [0 3 3 0] | r1-2 c0-1
(0,2) | (1,4)out | 5 | [0 3 3 0] | r1-2 c1-2
(1,0) | (2,0)out | 5 | [2 2 0 3] | r0-2 c0-1
(1,0) | (2,1)out | 5 | [2 2 0 3] | r0-2 c1-2
(1,1) | (2,2)out | 1 | (2,2)out | +(0,0)
(1,2) | (2,3)out | 7 | [2 2 3 0] | r0-2 c0-1
(1,2) | (2,4)out | 7 | [2 2 3 0] | r0-2 c1-2
(2,0) | (3,0)out | 4 | [3 0 0 3] | r0-1 c0-1
(2,0) | (3,1)out | 4 | [3 0 0 3] | r0-1 c1-2
(2,0) | (4,0)out | 4 | [3 0 0 3] | r1-2 c0-1
(2,0) | (4,1)out | 4 | [3 0 0 3] | r1-2 c1-2
(2,1) | (3,2)out | 5 | [3 0 2 2] | r0-1 c0-2
(2,1) | (4,2)out | 5 | [3 0 2 2] | r1-2 c0-2
(2,2) | (3,3)out | 2 | [3 0 3 0] | r0-1 c0-1
(2,2) | (3,4)out | 2 | [3 0 3 0] | r0-1 c1-2
(2,2) | (4,3)out | 2 | [3 0 3 0] | r1-2 c0-1
(2,2) | (4,4)out | 2 | [3 0 3 0] | r1-2 c1-2
```

Train example 1: 25 rows
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
4 2 4
2 1 2
4 2 4
```
```
c0 | c1 | c2 | c3 | c4
(0,0) | (0,0)out | 1 | [0 3 0 3] | r0-1 c0-1
(0,0) | (0,1)out | 1 | [0 3 0 3] | r0-1 c1-2
(0,0) | (1,0)out | 1 | [0 3 0 3] | r1-2 c0-1
(0,0) | (1,1)out | 1 | [0 3 0 3] | r1-2 c1-2
(0,1) | (0,2)out | 3 | [0 3 2 2] | r0-1 c0-2
(0,1) | (1,2)out | 3 | [0 3 2 2] | r1-2 c0-2
(0,2) | (0,3)out | 5 | [0 3 3 0] | r0-1 c0-1
(0,2) | (0,4)out | 5 | [0 3 3 0] | r0-1 c1-2
(0,2) | (1,3)out | 5 | [0 3 3 0] | r1-2 c0-1
(0,2) | (1,4)out | 5 | [0 3 3 0] | r1-2 c1-2
(1,0) | (2,0)out | 1 | [2 2 0 3] | r0-2 c0-1
(1,0) | (2,1)out | 1 | [2 2 0 3] | r0-2 c1-2
(1,1) | (2,2)out | 2 | (2,2)out | +(0,0)
(1,2) | (2,3)out | 8 | [2 2 3 0] | r0-2 c0-1
(1,2) | (2,4)out | 8 | [2 2 3 0] | r0-2 c1-2
(2,0) | (3,0)out | 8 | [3 0 0 3] | r0-1 c0-1
(2,0) | (3,1)out | 8 | [3 0 0 3] | r0-1 c1-2
(2,0) | (4,0)out | 8 | [3 0 0 3] | r1-2 c0-1
(2,0) | (4,1)out | 8 | [3 0 0 3] | r1-2 c1-2
(2,1) | (3,2)out | 3 | [3 0 2 2] | r0-1 c0-2
(2,1) | (4,2)out | 3 | [3 0 2 2] | r1-2 c0-2
(2,2) | (3,3)out | 8 | [3 0 3 0] | r0-1 c0-1
(2,2) | (3,4)out | 8 | [3 0 3 0] | r0-1 c1-2
(2,2) | (4,3)out | 8 | [3 0 3 0] | r1-2 c0-1
(2,2) | (4,4)out | 8 | [3 0 3 0] | r1-2 c1-2
```

Train example 2: 25 rows
Drawn on a 3x3 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
4 2 4
2 1 2
4 2 4
```
```
c0 | c1 | c2 | c3 | c4
(0,0) | (0,0)out | 2 | [0 3 0 3] | r0-1 c0-1
(0,0) | (0,1)out | 2 | [0 3 0 3] | r0-1 c1-2
(0,0) | (1,0)out | 2 | [0 3 0 3] | r1-2 c0-1
(0,0) | (1,1)out | 2 | [0 3 0 3] | r1-2 c1-2
(0,1) | (0,2)out | 3 | [0 3 2 2] | r0-1 c0-2
(0,1) | (1,2)out | 3 | [0 3 2 2] | r1-2 c0-2
(0,2) | (0,3)out | 7 | [0 3 3 0] | r0-1 c0-1
(0,2) | (0,4)out | 7 | [0 3 3 0] | r0-1 c1-2
(0,2) | (1,3)out | 7 | [0 3 3 0] | r1-2 c0-1
(0,2) | (1,4)out | 7 | [0 3 3 0] | r1-2 c1-2
(1,0) | (2,0)out | 2 | [2 2 0 3] | r0-2 c0-1
(1,0) | (2,1)out | 2 | [2 2 0 3] | r0-2 c1-2
(1,1) | (2,2)out | 1 | (2,2)out | +(0,0)
(1,2) | (2,3)out | 6 | [2 2 3 0] | r0-2 c0-1
(1,2) | (2,4)out | 6 | [2 2 3 0] | r0-2 c1-2
(2,0) | (3,0)out | 1 | [3 0 0 3] | r0-1 c0-1
(2,0) | (3,1)out | 1 | [3 0 0 3] | r0-1 c1-2
(2,0) | (4,0)out | 1 | [3 0 0 3] | r1-2 c0-1
(2,0) | (4,1)out | 1 | [3 0 0 3] | r1-2 c1-2
(2,1) | (3,2)out | 5 | [3 0 2 2] | r0-1 c0-2
(2,1) | (4,2)out | 5 | [3 0 2 2] | r1-2 c0-2
(2,2) | (3,3)out | 7 | [3 0 3 0] | r0-1 c0-1
(2,2) | (3,4)out | 7 | [3 0 3 0] | r0-1 c1-2
(2,2) | (4,3)out | 7 | [3 0 3 0] | r1-2 c0-1
(2,2) | (4,4)out | 7 | [3 0 3 0] | r1-2 c1-2
```

## What I see

The task: each input cell becomes a tile, and the tiles keep the input's arrangement. A cell on a grid edge is 2 wide along the axis of that edge, and a cell off both edges of an axis is 1 wide. All three inputs are 3x3 and all outputs 5x5. Each table has one assignment.

- **&r0** (DimDiff): 2, the rows and columns the output adds. A lib DET's value, which only the clause names.
- **&r1** (DET: an input cell and an output cell of one color, per example): 55, 55 and 44 rows. This is the first table read from the outputs, and most of its rows are chance: in e0 the 5 at (0,1) pairs with all ten 5s of the output, and the count drawing (`4 + +` / `+ 1 2` / `4 + 4`) shows no shape. Alone, only a cell of a color used once is a true pair, such as `e0 | (1,1) | (2,2)out | 1`.
- **&r2** (DET: the pairs that break in some example): 39, 39 and 50 rows. &r3 reads it only under NOT, so its rows are the chance pairs to drop.
- **&r3** (DET: the pairs that hold in every example): 25 rows with no Example column, so its Boxes print as margins: `[0 2 0 2]` is (0,0) of a 3x3 input and `[0 4 0 4]` is (0,0) of a 5x5 output. The count drawing on the 3x3 frame is `4 2 4` / `2 1 2` / `4 2 4`, the area of each cell's tile. The signal about the rule jumps here: an intersection over the examples turns 154 chance pairs into the cell correspondence.
- **&r4** (DET: each pair, split per axis into its output line): 50 rows, two per pair. c3 is a function of c0 and c2 through `split`, so it adds no signal beyond &r3.
- **&r5** (Cardinality: the output lines of each input cell, per axis): 18 rows. The drawing shows 2 at every cell, the one row per axis, and the signal is in c2: 2 along an axis where the cell is on an edge, else 1. `[0 2 1 1] | AXIS_H | 1` is (0,1): 1 column wide, and `[0 2 1 1] | AXIS_V | 2`: 2 rows tall.
- **&r8** (DET: &r5 with the cell's line on that axis): c2 is the line, and the functional dependency (c1, c2) → c3 holds in all 18 rows. The extent depends only on the line: `[0 2 0 0]` → 2, `[1 1 0 0]` → 1, `[2 0 0 0]` → 2. These are the rows of the solver's stored `ext`.
- **&r9** (the extents in use, DimDiff or &r8's): 1 and 2 in every example.
- **&r10, &r12** (Frame: the in-tile positions of a strip of each extent; the DET lifts them task-wide): the same 6 rows in each. One offset prints as `r0-1 c0-2` in &r10, where the rows are per example, and as `[0 1 0 0]` in &r12, where they are task-wide. Both restate the extents 1 and 2.
- **&r13** (the strips of the extent equal to DimDiff): 4 rows, &r10 at n = 2.
- **&r14** (each cell's in-tile positions on the axis of each side): 36 rows, equal in the three examples. A cell on an edge gets the two positions of &r13, and a cell off both edges gets `+(0,0)`. The rule is applied here, but the rows follow from &r13 and the grid size. The off-edge rows are there once per side: `(0,1) | DIR_L | AXIS_H | +(0,0)` and `(0,1) | DIR_R | AXIS_H | +(0,0)`.
- **&r15** (the cells of each tile, with the tile's color): 50 rows. Each in-tile cell is there once for each order of the two perpendicular axes (c1, c3), so half the rows mirror the other half. c2 is the first column on the applied side that differs between the examples.
- **&r16, &r17** (Cardinality: the output lines of the tiles before each tile, toward each side): &r16 is the count, 0, 2 or 3 (`(0,1) | DIR_L | 2`, `(0,0) | DIR_R | 3`). &r17 is the items it counts, 60 rows, which only &r16 reads.
- **&r19** (each count as an inset offset): c2 is a function of c1 and c3 through `edge_inset`, a restatement of &r16.
- **&r20, &r21** (the offsets composed over the two opposite sides, then over the two axes): 36 and 18 rows, each pair twice by its order. &r21's c3 places each tile: (1,1) at `(2,2)out`, (0,0) at `[0 3 0 3]`, the 2x2 block at the top left.
- **&r22** (out): 25 rows per example, the output's cells with their colors, equal to the outputs.

Rows that look like noise: &r1 and &r2 (chance pairs); &r4, &r12 and &r19 (functions of earlier columns); &r17; the mirrored halves of &r15, &r20 and &r21; the repeated off-edge rows of &r14. The signal jumps at &r3, then at &r5 and &r8. From &r14 on, every table is equal in the three examples except in its Color column, since all inputs are 3x3.
