# 1fad071e, case `$Object $Fixed`

- concept case: True; tokens: 403; tables: 25 relations, 91 per assignment
- cells: a Position is `(row,col)` of the example's input grid (`(row,col)out` where it fits only the output grid), an Offset `+(drow,dcol)`, another Box `rR0-R1 cC0-C1` over the input grid or `[t b l r]` margins; an Ident is `id<n>`, equal only within one case; see README.md

## Grids

### Train example 0: input 9x9, output 1x5

```
input                output
0 0 0 0 2 2 0 0 1    1 1 0 0 0
0 1 1 0 2 2 0 0 0
0 1 1 0 0 0 0 2 2
0 0 0 0 0 0 0 2 2
1 0 2 2 0 0 0 0 0
0 0 2 2 0 1 1 0 0
0 0 0 0 0 1 1 0 0
0 0 0 0 0 0 0 0 0
0 1 0 0 0 0 0 0 1
```

### Train example 1: input 9x9, output 1x5

```
input                output
1 1 0 2 0 0 0 0 2    1 1 1 1 0
1 1 0 0 0 1 1 0 0
0 0 0 2 0 1 1 0 0
0 0 0 0 0 0 0 0 1
0 1 1 0 2 2 0 0 0
0 1 1 0 2 2 0 0 2
0 0 0 0 0 0 0 0 0
0 0 0 2 2 0 1 1 0
0 1 0 2 2 0 1 1 0
```

### Train example 2: input 9x9, output 1x5

```
input                output
2 2 0 1 1 0 0 0 0    1 1 1 1 0
2 2 0 1 1 0 0 1 1
1 0 0 0 0 0 0 1 1
0 2 2 0 0 0 0 0 0
0 2 2 0 1 1 0 1 0
0 0 0 0 1 1 0 0 0
0 0 0 0 2 0 0 0 0
0 1 1 0 0 0 0 2 2
0 1 1 0 0 1 0 2 2
```

### Test example 0: input 9x9

```
0 0 0 0 0 2 2 0 1
1 1 0 1 0 2 2 0 0
1 1 0 0 0 0 0 0 0
0 0 0 0 0 1 1 0 0
0 2 2 0 0 1 1 0 0
0 2 2 0 0 0 0 0 0
1 0 0 0 0 0 2 2 0
2 2 0 1 1 0 2 2 0
2 2 0 1 1 0 0 0 0
```

## Program and tables

Model-written tokens plain, engine-written ones in [brackets]. Each clause is followed by the tables of the relations it declares. A table whose entries hold several DET assignments is given once per assignment, each marked with the values, at that assignment, of the DETs whose value differs between them; a DET's value is the rows of its own table at that assignment.

```
DET ColorDomain END [&r0]
```

### &r0 (export table 2)

- columns: C: Color
- depth 1, candidate keys none
- DETs its entries are assigned: &r0; assignments: 3

#### &r0, assignment 1 of 3

- DET values that differ between the assignments: &r0 = {(0)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
C
0
```


#### &r0, assignment 2 of 3

- DET values that differ between the assignments: &r0 = {(1)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
C
1
```


#### &r0, assignment 3 of 3

- DET values that differ between the assignments: &r0 = {(2)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
C
2
```

```
DET TileCount END [&r1]
```

### &r1 (export table 3)

- columns: N: Number
- depth 1, candidate keys none
- DETs its entries are assigned: &r1; assignments: 3

#### &r1, assignment 1 of 3

- DET values that differ between the assignments: &r1 = {(2)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
N
2
```


#### &r1, assignment 2 of 3

- DET values that differ between the assignments: &r1 = {(3)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
N
3
```


#### &r1, assignment 3 of 3

- DET values that differ between the assignments: &r1 = {(5)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
N
5
```

```
INIT Frame [:0] SKIP [:1] axis_elem :0 * [L0] &r1 :0 * [L1] END [:0] END [:1] L0 END [:2] L1 END [&r2] [&r3]
```

### &r2 (export table 4)

- columns: c0: Box
- depth 3, candidate keys none
- DETs its entries are assigned: &r1; assignments: 3

#### &r2, assignment 1 of 3

- DET values that differ between the assignments: &r1 = {(2)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 4
- every row is of a task-wide entry

Task-wide: 4 rows
Drawn on a 2x2 grid, a task-wide frame, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1
1 1
```
```
c0
[0 1 0 1]
[0 1 1 0]
[1 0 0 1]
[1 0 1 0]
```


#### &r2, assignment 2 of 3

- DET values that differ between the assignments: &r1 = {(3)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 9
- every row is of a task-wide entry

Task-wide: 9 rows
Drawn on a 3x3 grid, a task-wide frame, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1
1 1 1
1 1 1
```
```
c0
[0 2 0 2]
[0 2 1 1]
[0 2 2 0]
[1 1 0 2]
[1 1 1 1]
[1 1 2 0]
[2 0 0 2]
[2 0 1 1]
[2 0 2 0]
```


#### &r2, assignment 3 of 3

- DET values that differ between the assignments: &r1 = {(5)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 25
- every row is of a task-wide entry

Task-wide: 25 rows
Drawn on a 5x5 grid, a task-wide frame, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0
[0 4 0 4]
[0 4 1 3]
[0 4 2 2]
[0 4 3 1]
[0 4 4 0]
[1 3 0 4]
[1 3 1 3]
[1 3 2 2]
[1 3 3 1]
[1 3 4 0]
[2 2 0 4]
[2 2 1 3]
[2 2 2 2]
[2 2 3 1]
[2 2 4 0]
[3 1 0 4]
[3 1 1 3]
[3 1 2 2]
[3 1 3 1]
[3 1 4 0]
[4 0 0 4]
[4 0 1 3]
[4 0 2 2]
[4 0 3 1]
[4 0 4 0]
```

### &r3 (export table 5)

- columns: c0: Axis, c1: Number
- depth 2, candidate keys none
- DETs its entries are assigned: &r1; assignments: 3

#### &r3, assignment 1 of 3

- DET values that differ between the assignments: &r1 = {(2)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 2
- every row is of a task-wide entry

Task-wide: 2 rows
```
c0 | c1
AXIS_V | 2
AXIS_H | 2
```


#### &r3, assignment 2 of 3

- DET values that differ between the assignments: &r1 = {(3)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 2
- every row is of a task-wide entry

Task-wide: 2 rows
```
c0 | c1
AXIS_V | 3
AXIS_H | 3
```


#### &r3, assignment 3 of 3

- DET values that differ between the assignments: &r1 = {(5)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 2
- every row is of a task-wide entry

Task-wide: 2 rows
```
c0 | c1
AXIS_V | 5
AXIS_H | 5
```

```
DET &r2 :1 * [L0] END [&r4]
```

### &r4 (export table 6)

- columns: c0: Box
- depth 4, candidate keys none
- DETs its entries are assigned: &r1, &r4; assignments: 3

#### &r4, assignment 1 of 3

- DET values that differ between the assignments: &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 4
- every row is of a task-wide entry

Task-wide: 4 rows
Drawn on a 2x2 grid, a task-wide frame, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1
1 1
```
```
c0
[0 1 0 1]
[0 1 1 0]
[1 0 0 1]
[1 0 1 0]
```


#### &r4, assignment 2 of 3

- DET values that differ between the assignments: &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 9
- every row is of a task-wide entry

Task-wide: 9 rows
Drawn on a 3x3 grid, a task-wide frame, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1
1 1 1
1 1 1
```
```
c0
[0 2 0 2]
[0 2 1 1]
[0 2 2 0]
[1 1 0 2]
[1 1 1 1]
[1 1 2 0]
[2 0 0 2]
[2 0 1 1]
[2 0 2 0]
```


#### &r4, assignment 3 of 3

- DET values that differ between the assignments: &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 25
- every row is of a task-wide entry

Task-wide: 25 rows
Drawn on a 5x5 grid, a task-wide frame, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0
[0 4 0 4]
[0 4 1 3]
[0 4 2 2]
[0 4 3 1]
[0 4 4 0]
[1 3 0 4]
[1 3 1 3]
[1 3 2 2]
[1 3 3 1]
[1 3 4 0]
[2 2 0 4]
[2 2 1 3]
[2 2 2 2]
[2 2 3 1]
[2 2 4 0]
[3 1 0 4]
[3 1 1 3]
[3 1 2 2]
[3 1 3 1]
[3 1 4 0]
[4 0 0 4]
[4 0 1 3]
[4 0 2 2]
[4 0 3 1]
[4 0 4 0]
```

```
DET DominantColor END [&r5]
```

### &r5 (export table 7)

- columns: C: Color
- depth 1, candidate keys none
- DETs its entries are assigned: &r5; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
C
0
```

```
DET ex_output :1 * [L0] axis_elem :0 * [L1] frame_extent :0 L0 :1 L1 :2 * [L2] END [&r6]
```

### &r6 (export table 8)

- columns: c0: Axis, c1: Box, c2: Number
- depth 1, candidate keys none
- DETs its entries are assigned: &r6; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 10
- every row is of a task-wide entry

Task-wide: 10 rows
Drawn on a 1x5 grid, a task-wide frame, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2 2 2
```
```
c0 | c1 | c2
AXIS_V | [0 0 0 4] | 1
AXIS_V | [0 0 1 3] | 1
AXIS_V | [0 0 2 2] | 1
AXIS_V | [0 0 3 1] | 1
AXIS_V | [0 0 4 0] | 1
AXIS_H | [0 0 0 4] | 5
AXIS_H | [0 0 1 3] | 5
AXIS_H | [0 0 2 2] | 5
AXIS_H | [0 0 3 1] | 5
AXIS_H | [0 0 4 0] | 5
```

```
INIT Frame [:0] SKIP [:1] &r6 :1 * [L0] :2 * [L1] END [:0] END [:1] L0 END [:2] L1 END [&r7] [&r8]
```

### &r7 (export table 9)

- columns: c0: Box
- depth 3, candidate keys none
- DETs its entries are assigned: &r6; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 5
- every row is of a task-wide entry

Task-wide: 5 rows
Drawn on a 1x5 grid, a task-wide frame, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
```
```
c0
[0 0 0 4]
[0 0 1 3]
[0 0 2 2]
[0 0 3 1]
[0 0 4 0]
```

```
DET &r7 :1 * [L0] END [&r9]
```

### &r9 (export table 10)

- columns: c0: Box
- depth 4, candidate keys none
- DETs its entries are assigned: &r6, &r9; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 5
- every row is of a task-wide entry

Task-wide: 5 rows
Drawn on a 1x5 grid, a task-wide frame, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
```
```
c0
[0 0 0 4]
[0 0 1 3]
[0 0 2 2]
[0 0 3 1]
[0 0 4 0]
```

```
RULE input :0 * [L0] :1 * [L1] &r0 :0 L1 END [&r10]
```

### &r10 (export table 11)

- columns: c0: Box, c1: Color
- depth 2, candidate keys none
- DETs its entries are assigned: &r0; assignments: 3

#### &r10, assignment 1 of 3

- DET values that differ between the assignments: &r0 = {(0)}
- rows per train example: [57, 51, 49]; test: 50

Train example 0: 57 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
0 0 0 0 . . 0 0 .
0 . . 0 . . 0 0 0
0 . . 0 0 0 0 . .
0 0 0 0 0 0 0 . .
. 0 . . 0 0 0 0 0
0 0 . . 0 . . 0 0
0 0 0 0 0 . . 0 0
0 0 0 0 0 0 0 0 0
0 . 0 0 0 0 0 0 .
```
```
c0 | c1
(0,0) | 0
(0,1) | 0
(0,2) | 0
(0,3) | 0
(0,6) | 0
(0,7) | 0
(1,0) | 0
(1,3) | 0
(1,6) | 0
(1,7) | 0
(1,8) | 0
(2,0) | 0
(2,3) | 0
(2,4) | 0
(2,5) | 0
(2,6) | 0
(3,0) | 0
(3,1) | 0
(3,2) | 0
(3,3) | 0
(3,4) | 0
(3,5) | 0
(3,6) | 0
(4,1) | 0
(4,4) | 0
(4,5) | 0
(4,6) | 0
(4,7) | 0
(4,8) | 0
(5,0) | 0
```

Train example 1: 51 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . 0 . 0 0 0 0 .
. . 0 0 0 . . 0 0
0 0 0 . 0 . . 0 0
0 0 0 0 0 0 0 0 .
0 . . 0 . . 0 0 0
0 . . 0 . . 0 0 .
0 0 0 0 0 0 0 0 0
0 0 0 . . 0 . . 0
0 . 0 . . 0 . . 0
```
```
c0 | c1
(0,2) | 0
(0,4) | 0
(0,5) | 0
(0,6) | 0
(0,7) | 0
(1,2) | 0
(1,3) | 0
(1,4) | 0
(1,7) | 0
(1,8) | 0
(2,0) | 0
(2,1) | 0
(2,2) | 0
(2,4) | 0
(2,7) | 0
(2,8) | 0
(3,0) | 0
(3,1) | 0
(3,2) | 0
(3,3) | 0
(3,4) | 0
(3,5) | 0
(3,6) | 0
(3,7) | 0
(4,0) | 0
(4,3) | 0
(4,6) | 0
(4,7) | 0
(4,8) | 0
(5,0) | 0
```

Train example 2: 49 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . 0 . . 0 0 0 0
. . 0 . . 0 0 . .
. 0 0 0 0 0 0 . .
0 . . 0 0 0 0 0 0
0 . . 0 . . 0 . 0
0 0 0 0 . . 0 0 0
0 0 0 0 . 0 0 0 0
0 . . 0 0 0 0 . .
0 . . 0 0 . 0 . .
```
```
c0 | c1
(0,2) | 0
(0,5) | 0
(0,6) | 0
(0,7) | 0
(0,8) | 0
(1,2) | 0
(1,5) | 0
(1,6) | 0
(2,1) | 0
(2,2) | 0
(2,3) | 0
(2,4) | 0
(2,5) | 0
(2,6) | 0
(3,0) | 0
(3,3) | 0
(3,4) | 0
(3,5) | 0
(3,6) | 0
(3,7) | 0
(3,8) | 0
(4,0) | 0
(4,3) | 0
(4,6) | 0
(4,8) | 0
(5,0) | 0
(5,1) | 0
(5,2) | 0
(5,3) | 0
(5,6) | 0
```


#### &r10, assignment 2 of 3

- DET values that differ between the assignments: &r0 = {(1)}
- rows per train example: [12, 18, 19]; test: 15

Train example 0: 12 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . 1
. 1 1 . . . . . .
. 1 1 . . . . . .
. . . . . . . . .
1 . . . . . . . .
. . . . . 1 1 . .
. . . . . 1 1 . .
. . . . . . . . .
. 1 . . . . . . 1
```
```
c0 | c1
(0,8) | 1
(1,1) | 1
(1,2) | 1
(2,1) | 1
(2,2) | 1
(4,0) | 1
(5,5) | 1
(5,6) | 1
(6,5) | 1
(6,6) | 1
(8,1) | 1
(8,8) | 1
```

Train example 1: 18 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1 1 . . . . . . .
1 1 . . . 1 1 . .
. . . . . 1 1 . .
. . . . . . . . 1
. 1 1 . . . . . .
. 1 1 . . . . . .
. . . . . . . . .
. . . . . . 1 1 .
. 1 . . . . 1 1 .
```
```
c0 | c1
(0,0) | 1
(0,1) | 1
(1,0) | 1
(1,1) | 1
(1,5) | 1
(1,6) | 1
(2,5) | 1
(2,6) | 1
(3,8) | 1
(4,1) | 1
(4,2) | 1
(5,1) | 1
(5,2) | 1
(7,6) | 1
(7,7) | 1
(8,1) | 1
(8,6) | 1
(8,7) | 1
```

Train example 2: 19 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . 1 1 . . . .
. . . 1 1 . . 1 1
1 . . . . . . 1 1
. . . . . . . . .
. . . . 1 1 . 1 .
. . . . 1 1 . . .
. . . . . . . . .
. 1 1 . . . . . .
. 1 1 . . 1 . . .
```
```
c0 | c1
(0,3) | 1
(0,4) | 1
(1,3) | 1
(1,4) | 1
(1,7) | 1
(1,8) | 1
(2,0) | 1
(2,7) | 1
(2,8) | 1
(4,4) | 1
(4,5) | 1
(4,7) | 1
(5,4) | 1
(5,5) | 1
(7,1) | 1
(7,2) | 1
(8,1) | 1
(8,2) | 1
(8,5) | 1
```


#### &r10, assignment 3 of 3

- DET values that differ between the assignments: &r0 = {(2)}
- rows per train example: [12, 12, 13]; test: 16

Train example 0: 12 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . 2 2 . . .
. . . . 2 2 . . .
. . . . . . . 2 2
. . . . . . . 2 2
. . 2 2 . . . . .
. . 2 2 . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1
(0,4) | 2
(0,5) | 2
(1,4) | 2
(1,5) | 2
(2,7) | 2
(2,8) | 2
(3,7) | 2
(3,8) | 2
(4,2) | 2
(4,3) | 2
(5,2) | 2
(5,3) | 2
```

Train example 1: 12 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . 2 . . . . 2
. . . . . . . . .
. . . 2 . . . . .
. . . . . . . . .
. . . . 2 2 . . .
. . . . 2 2 . . 2
. . . . . . . . .
. . . 2 2 . . . .
. . . 2 2 . . . .
```
```
c0 | c1
(0,3) | 2
(0,8) | 2
(2,3) | 2
(4,4) | 2
(4,5) | 2
(5,4) | 2
(5,5) | 2
(5,8) | 2
(7,3) | 2
(7,4) | 2
(8,3) | 2
(8,4) | 2
```

Train example 2: 13 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 2 . . . . . . .
2 2 . . . . . . .
. . . . . . . . .
. 2 2 . . . . . .
. 2 2 . . . . . .
. . . . . . . . .
. . . . 2 . . . .
. . . . . . . 2 2
. . . . . . . 2 2
```
```
c0 | c1
(0,0) | 2
(0,1) | 2
(1,0) | 2
(1,1) | 2
(3,1) | 2
(3,2) | 2
(4,1) | 2
(4,2) | 2
(6,4) | 2
(7,7) | 2
(7,8) | 2
(8,7) | 2
(8,8) | 2
```

```
INIT Connectivity [:0] SKIP [:1] &r10 :1 * [L0] END [:0] END [:1] L0 END [:2] SKIP [&r11] [&r12] [&r13] [&r14]
```

### &r11 (export table 12)

- columns: c0: Box, c1: Ident
- depth 4, candidate keys none
- DETs its entries are assigned: &r0; assignments: 3

#### &r11, assignment 1 of 3

- DET values that differ between the assignments: &r0 = {(0)}
- rows per train example: [57, 51, 49]; test: 50

Train example 0: 57 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
a a a a . . a a .
a . . a . . a a a
a . . a a a a . .
a a a a a a a . .
. a . . a a a a a
a a . . a . . a a
a a a a a . . a a
a a a a a a a a a
a . a a a a a a .
```
```
c0 | c1
(0,0) | id0
(0,1) | id0
(0,2) | id0
(0,3) | id0
(0,6) | id0
(0,7) | id0
(1,0) | id0
(1,3) | id0
(1,6) | id0
(1,7) | id0
(1,8) | id0
(2,0) | id0
(2,3) | id0
(2,4) | id0
(2,5) | id0
(2,6) | id0
(3,0) | id0
(3,1) | id0
(3,2) | id0
(3,3) | id0
(3,4) | id0
(3,5) | id0
(3,6) | id0
(4,1) | id0
(4,4) | id0
(4,5) | id0
(4,6) | id0
(4,7) | id0
(4,8) | id0
(5,0) | id0
```

Train example 1: 51 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . a . a a a a .
. . a a a . . a a
a a a . a . . a a
a a a a a a a a .
a . . a . . a a a
a . . a . . a a .
a a a a a a a a a
a a a . . a . . a
a . a . . a . . a
```
```
c0 | c1
(0,2) | id10
(0,4) | id10
(0,5) | id10
(0,6) | id10
(0,7) | id10
(1,2) | id10
(1,3) | id10
(1,4) | id10
(1,7) | id10
(1,8) | id10
(2,0) | id10
(2,1) | id10
(2,2) | id10
(2,4) | id10
(2,7) | id10
(2,8) | id10
(3,0) | id10
(3,1) | id10
(3,2) | id10
(3,3) | id10
(3,4) | id10
(3,5) | id10
(3,6) | id10
(3,7) | id10
(4,0) | id10
(4,3) | id10
(4,6) | id10
(4,7) | id10
(4,8) | id10
(5,0) | id10
```

Train example 2: 49 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . a . . a a a a
. . a . . a a . .
. a a a a a a . .
a . . a a a a a a
a . . a . . a . a
a a a a . . a a a
a a a a . a a a a
a . . a a a a . .
a . . a a . a . .
```
```
c0 | c1
(0,2) | id21
(0,5) | id21
(0,6) | id21
(0,7) | id21
(0,8) | id21
(1,2) | id21
(1,5) | id21
(1,6) | id21
(2,1) | id21
(2,2) | id21
(2,3) | id21
(2,4) | id21
(2,5) | id21
(2,6) | id21
(3,0) | id21
(3,3) | id21
(3,4) | id21
(3,5) | id21
(3,6) | id21
(3,7) | id21
(3,8) | id21
(4,0) | id21
(4,3) | id21
(4,6) | id21
(4,8) | id21
(5,0) | id21
(5,1) | id21
(5,2) | id21
(5,3) | id21
(5,6) | id21
```


#### &r11, assignment 2 of 3

- DET values that differ between the assignments: &r0 = {(1)}
- rows per train example: [12, 18, 19]; test: 15

Train example 0: 12 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . a
. b b . . . . . .
. b b . . . . . .
. . . . . . . . .
c . . . . . . . .
. . . . . d d . .
. . . . . d d . .
. . . . . . . . .
. e . . . . . . f
```
```
c0 | c1
(0,8) | id1
(1,1) | id6
(1,2) | id6
(2,1) | id6
(2,2) | id6
(4,0) | id2
(5,5) | id4
(5,6) | id4
(6,5) | id4
(6,6) | id4
(8,1) | id3
(8,8) | id5
```

Train example 1: 18 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
a a . . . . . . .
a a . . . b b . .
. . . . . b b . .
. . . . . . . . c
. d d . . . . . .
. d d . . . . . .
. . . . . . . . .
. . . . . . e e .
. f . . . . e e .
```
```
c0 | c1
(0,0) | id13
(0,1) | id13
(1,0) | id13
(1,1) | id13
(1,5) | id14
(1,6) | id14
(2,5) | id14
(2,6) | id14
(3,8) | id11
(4,1) | id15
(4,2) | id15
(5,1) | id15
(5,2) | id15
(7,6) | id12
(7,7) | id12
(8,1) | id3
(8,6) | id12
(8,7) | id12
```

Train example 2: 19 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . a a . . . .
. . . a a . . b b
c . . . . . . b b
. . . . . . . . .
. . . . d d . e .
. . . . d d . . .
. . . . . . . . .
. f f . . . . . .
. f f . . g . . .
```
```
c0 | c1
(0,3) | id22
(0,4) | id22
(1,3) | id22
(1,4) | id22
(1,7) | id25
(1,8) | id25
(2,0) | id27
(2,7) | id25
(2,8) | id25
(4,4) | id16
(4,5) | id16
(4,7) | id23
(5,4) | id16
(5,5) | id16
(7,1) | id24
(7,2) | id24
(8,1) | id24
(8,2) | id24
(8,5) | id26
```


#### &r11, assignment 3 of 3

- DET values that differ between the assignments: &r0 = {(2)}
- rows per train example: [12, 12, 13]; test: 16

Train example 0: 12 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . a a . . .
. . . . a a . . .
. . . . . . . b b
. . . . . . . b b
. . c c . . . . .
. . c c . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1
(0,4) | id7
(0,5) | id7
(1,4) | id7
(1,5) | id7
(2,7) | id8
(2,8) | id8
(3,7) | id8
(3,8) | id8
(4,2) | id9
(4,3) | id9
(5,2) | id9
(5,3) | id9
```

Train example 1: 12 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . a . . . . b
. . . . . . . . .
. . . c . . . . .
. . . . . . . . .
. . . . d d . . .
. . . . d d . . e
. . . . . . . . .
. . . f f . . . .
. . . f f . . . .
```
```
c0 | c1
(0,3) | id17
(0,8) | id1
(2,3) | id19
(4,4) | id16
(4,5) | id16
(5,4) | id16
(5,5) | id16
(5,8) | id20
(7,3) | id18
(7,4) | id18
(8,3) | id18
(8,4) | id18
```

Train example 2: 13 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
a a . . . . . . .
a a . . . . . . .
. . . . . . . . .
. b b . . . . . .
. b b . . . . . .
. . . . . . . . .
. . . . c . . . .
. . . . . . . d d
. . . . . . . d d
```
```
c0 | c1
(0,0) | id13
(0,1) | id13
(1,0) | id13
(1,1) | id13
(3,1) | id30
(3,2) | id30
(4,1) | id30
(4,2) | id30
(6,4) | id28
(7,7) | id29
(7,8) | id29
(8,7) | id29
(8,8) | id29
```

```
INIT BoundingBox [:0] &r11 :2 * [L0] :3 ^ [L1] END [:1] &r11 :2 * [L2] :3 L1 END [:0] END [:1] L2 END [&r15] [&r16]
```

### &r15 (export table 13)

- columns: c0: Ident, c1: Box
- depth 6, candidate keys none
- DETs its entries are assigned: &r0; assignments: 3

#### &r15, assignment 1 of 3

- DET values that differ between the assignments: &r0 = {(0)}
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1
id0 | +(0,0)
```

Train example 1: 1 row
```
c0 | c1
id10 | +(0,0)
```

Train example 2: 1 row
```
c0 | c1
id21 | +(0,0)
```


#### &r15, assignment 2 of 3

- DET values that differ between the assignments: &r0 = {(1)}
- rows per train example: [6, 6, 7]; test: 6

Train example 0: 6 rows
```
c0 | c1
id1 | (0,8)
id2 | (4,0)
id3 | (8,1)
id4 | r5-6 c5-6
id5 | (8,8)
id6 | r1-2 c1-2
```

Train example 1: 6 rows
```
c0 | c1
id3 | (8,1)
id11 | (3,8)
id12 | r7-8 c6-7
id13 | r0-1 c0-1
id14 | r1-2 c5-6
id15 | r4-5 c1-2
```

Train example 2: 7 rows
```
c0 | c1
id16 | r4-5 c4-5
id22 | r0-1 c3-4
id23 | (4,7)
id24 | r7-8 c1-2
id25 | r1-2 c7-8
id26 | (8,5)
id27 | (2,0)
```


#### &r15, assignment 3 of 3

- DET values that differ between the assignments: &r0 = {(2)}
- rows per train example: [3, 6, 4]; test: 4

Train example 0: 3 rows
```
c0 | c1
id7 | r0-1 c4-5
id8 | r2-3 c7-8
id9 | r4-5 c2-3
```

Train example 1: 6 rows
```
c0 | c1
id1 | (0,8)
id16 | r4-5 c4-5
id17 | (0,3)
id18 | r7-8 c3-4
id19 | (2,3)
id20 | (5,8)
```

Train example 2: 4 rows
```
c0 | c1
id13 | r0-1 c0-1
id28 | (6,4)
id29 | r7-8 c7-8
id30 | r3-4 c1-2
```

```
INIT Inclusion [:0] SKIP [:1] &r4 :0 * [L0] END [:0] END [:1] L0 END [:2] &r16 :1 :0 * [L1] END :2 * [L2] &r15 :1 :0 L1 END :2 * [L3] inside :0 L2 :1 L3 relative :0 L3 :1 L2 :2 * [L4] END [:0] L1 END [:1] L4 END [&r17] [&r18] [&r19] [&r20]
```

### &r17 (export table 14)

- columns: c0: Ident
- depth 8, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r4; assignments: 9

#### &r17, assignment 1 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [0, 0, 0]; test: 0


#### &r17, assignment 2 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- empty at every example

#### &r17, assignment 3 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- empty at every example

#### &r17, assignment 4 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [2, 4, 4]; test: 3

Train example 0: 2 rows
```
c0
id4
id6
```

Train example 1: 4 rows
```
c0
id12
id13
id14
id15
```

Train example 2: 4 rows
```
c0
id16
id22
id24
id25
```


#### &r17, assignment 5 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- empty at every example

#### &r17, assignment 6 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- empty at every example

#### &r17, assignment 7 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [3, 2, 3]; test: 4

Train example 0: 3 rows
```
c0
id7
id8
id9
```

Train example 1: 2 rows
```
c0
id16
id18
```

Train example 2: 3 rows
```
c0
id13
id29
id30
```


#### &r17, assignment 8 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- empty at every example

#### &r17, assignment 9 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- empty at every example
### &r18 (export table 15)

- columns: c0: Ident
- depth 8, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r4; assignments: 9

#### &r18, assignment 1 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [0, 0, 0]; test: 0


#### &r18, assignment 2 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- empty at every example

#### &r18, assignment 3 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- empty at every example

#### &r18, assignment 4 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [2, 4, 4]; test: 3

Train example 0: 2 rows
```
c0
id4
id6
```

Train example 1: 4 rows
```
c0
id12
id13
id14
id15
```

Train example 2: 4 rows
```
c0
id16
id22
id24
id25
```


#### &r18, assignment 5 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- empty at every example

#### &r18, assignment 6 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- empty at every example

#### &r18, assignment 7 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [3, 2, 3]; test: 4

Train example 0: 3 rows
```
c0
id7
id8
id9
```

Train example 1: 2 rows
```
c0
id16
id18
```

Train example 2: 3 rows
```
c0
id13
id29
id30
```


#### &r18, assignment 8 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- empty at every example

#### &r18, assignment 9 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- empty at every example
### &r20 (export table 16)

- columns: c0: Ident, c1: Box
- depth 7, candidate keys none
- DETs its entries are assigned: &r0; assignments: 3

#### &r20, assignment 1 of 3

- DET values that differ between the assignments: &r0 = {(0)}
- rows per train example: [57, 51, 49]; test: 50

Train example 0: 57 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
a a a a . . a a .
a . . a . . a a a
a . . a a a a . .
a a a a a a a . .
. a . . a a a a a
a a . . a . . a a
a a a a a . . a a
a a a a a a a a a
a . a a a a a a .
```
```
c0 | c1
id0 | (0,0)
id0 | (0,1)
id0 | (0,2)
id0 | (0,3)
id0 | (0,6)
id0 | (0,7)
id0 | (1,0)
id0 | (1,3)
id0 | (1,6)
id0 | (1,7)
id0 | (1,8)
id0 | (2,0)
id0 | (2,3)
id0 | (2,4)
id0 | (2,5)
id0 | (2,6)
id0 | (3,0)
id0 | (3,1)
id0 | (3,2)
id0 | (3,3)
id0 | (3,4)
id0 | (3,5)
id0 | (3,6)
id0 | (4,1)
id0 | (4,4)
id0 | (4,5)
id0 | (4,6)
id0 | (4,7)
id0 | (4,8)
id0 | (5,0)
```

Train example 1: 51 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . a . a a a a .
. . a a a . . a a
a a a . a . . a a
a a a a a a a a .
a . . a . . a a a
a . . a . . a a .
a a a a a a a a a
a a a . . a . . a
a . a . . a . . a
```
```
c0 | c1
id10 | (0,2)
id10 | (0,4)
id10 | (0,5)
id10 | (0,6)
id10 | (0,7)
id10 | (1,2)
id10 | (1,3)
id10 | (1,4)
id10 | (1,7)
id10 | (1,8)
id10 | (2,0)
id10 | (2,1)
id10 | (2,2)
id10 | (2,4)
id10 | (2,7)
id10 | (2,8)
id10 | (3,0)
id10 | (3,1)
id10 | (3,2)
id10 | (3,3)
id10 | (3,4)
id10 | (3,5)
id10 | (3,6)
id10 | (3,7)
id10 | (4,0)
id10 | (4,3)
id10 | (4,6)
id10 | (4,7)
id10 | (4,8)
id10 | (5,0)
```

Train example 2: 49 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . a . . a a a a
. . a . . a a . .
. a a a a a a . .
a . . a a a a a a
a . . a . . a . a
a a a a . . a a a
a a a a . a a a a
a . . a a a a . .
a . . a a . a . .
```
```
c0 | c1
id21 | (0,2)
id21 | (0,5)
id21 | (0,6)
id21 | (0,7)
id21 | (0,8)
id21 | (1,2)
id21 | (1,5)
id21 | (1,6)
id21 | (2,1)
id21 | (2,2)
id21 | (2,3)
id21 | (2,4)
id21 | (2,5)
id21 | (2,6)
id21 | (3,0)
id21 | (3,3)
id21 | (3,4)
id21 | (3,5)
id21 | (3,6)
id21 | (3,7)
id21 | (3,8)
id21 | (4,0)
id21 | (4,3)
id21 | (4,6)
id21 | (4,8)
id21 | (5,0)
id21 | (5,1)
id21 | (5,2)
id21 | (5,3)
id21 | (5,6)
```


#### &r20, assignment 2 of 3

- DET values that differ between the assignments: &r0 = {(1)}
- rows per train example: [12, 18, 19]; test: 15

Train example 0: 12 rows
```
c0 | c1
id1 | +(0,0)
id2 | +(0,0)
id3 | +(0,0)
id4 | r0-7 c0-7
id4 | r0-7 c1-8
id4 | r1-8 c0-7
id4 | r1-8 c1-8
id5 | +(0,0)
id6 | r0-7 c0-7
id6 | r0-7 c1-8
id6 | r1-8 c0-7
id6 | r1-8 c1-8
```

Train example 1: 18 rows
```
c0 | c1
id3 | +(0,0)
id11 | +(0,0)
id12 | r0-7 c0-7
id12 | r0-7 c1-8
id12 | r1-8 c0-7
id12 | r1-8 c1-8
id13 | r0-7 c0-7
id13 | r0-7 c1-8
id13 | r1-8 c0-7
id13 | r1-8 c1-8
id14 | r0-7 c0-7
id14 | r0-7 c1-8
id14 | r1-8 c0-7
id14 | r1-8 c1-8
id15 | r0-7 c0-7
id15 | r0-7 c1-8
id15 | r1-8 c0-7
id15 | r1-8 c1-8
```

Train example 2: 19 rows
```
c0 | c1
id16 | r0-7 c0-7
id16 | r0-7 c1-8
id16 | r1-8 c0-7
id16 | r1-8 c1-8
id22 | r0-7 c0-7
id22 | r0-7 c1-8
id22 | r1-8 c0-7
id22 | r1-8 c1-8
id23 | +(0,0)
id24 | r0-7 c0-7
id24 | r0-7 c1-8
id24 | r1-8 c0-7
id24 | r1-8 c1-8
id25 | r0-7 c0-7
id25 | r0-7 c1-8
id25 | r1-8 c0-7
id25 | r1-8 c1-8
id26 | +(0,0)
id27 | +(0,0)
```


#### &r20, assignment 3 of 3

- DET values that differ between the assignments: &r0 = {(2)}
- rows per train example: [12, 12, 13]; test: 16

Train example 0: 12 rows
```
c0 | c1
id7 | r0-7 c0-7
id7 | r0-7 c1-8
id7 | r1-8 c0-7
id7 | r1-8 c1-8
id8 | r0-7 c0-7
id8 | r0-7 c1-8
id8 | r1-8 c0-7
id8 | r1-8 c1-8
id9 | r0-7 c0-7
id9 | r0-7 c1-8
id9 | r1-8 c0-7
id9 | r1-8 c1-8
```

Train example 1: 12 rows
```
c0 | c1
id1 | +(0,0)
id16 | r0-7 c0-7
id16 | r0-7 c1-8
id16 | r1-8 c0-7
id16 | r1-8 c1-8
id17 | +(0,0)
id18 | r0-7 c0-7
id18 | r0-7 c1-8
id18 | r1-8 c0-7
id18 | r1-8 c1-8
id19 | +(0,0)
id20 | +(0,0)
```

Train example 2: 13 rows
```
c0 | c1
id13 | r0-7 c0-7
id13 | r0-7 c1-8
id13 | r1-8 c0-7
id13 | r1-8 c1-8
id28 | +(0,0)
id29 | r0-7 c0-7
id29 | r0-7 c1-8
id29 | r1-8 c0-7
id29 | r1-8 c1-8
id30 | r0-7 c0-7
id30 | r0-7 c1-8
id30 | r1-8 c0-7
id30 | r1-8 c1-8
```

```
INIT Cardinality [:0] SKIP [:1] &r18 :1 * [L0] END [:0] END [:1] L0 END [:2] input END [:0] END [&r21] [&r22] [&r23]
```

### &r21 (export table 17)

- columns: c0: Number
- depth 10, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r4; assignments: 9

#### &r21, assignment 1 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [1, 1, 1]; test: 1

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


#### &r21, assignment 2 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- rows equal to those of assignment 1 at every example

#### &r21, assignment 3 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- rows equal to those of assignment 1 at every example

#### &r21, assignment 4 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
2
```

Train example 1: 1 row
```
c0
4
```

Train example 2: 1 row
```
c0
4
```


#### &r21, assignment 5 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- rows equal to those of assignment 1 at every example

#### &r21, assignment 6 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- rows equal to those of assignment 1 at every example

#### &r21, assignment 7 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [1, 1, 1]; test: 1

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
3
```


#### &r21, assignment 8 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- rows equal to those of assignment 1 at every example

#### &r21, assignment 9 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- rows equal to those of assignment 1 at every example
```
RULE &r21 :1 * [L0] END [&r24]
```

### &r24 (export table 18)

- columns: c0: Number
- depth 11, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r4; assignments: 9

#### &r24, assignment 1 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [1, 1, 1]; test: 1

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


#### &r24, assignment 2 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- rows equal to those of assignment 1 at every example

#### &r24, assignment 3 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- rows equal to those of assignment 1 at every example

#### &r24, assignment 4 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
2
```

Train example 1: 1 row
```
c0
4
```

Train example 2: 1 row
```
c0
4
```


#### &r24, assignment 5 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- rows equal to those of assignment 1 at every example

#### &r24, assignment 6 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- rows equal to those of assignment 1 at every example

#### &r24, assignment 7 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [1, 1, 1]; test: 1

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
3
```


#### &r24, assignment 8 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- rows equal to those of assignment 1 at every example

#### &r24, assignment 9 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- rows equal to those of assignment 1 at every example
```
DET ex_output :0 * [L0] :1 * [L1] :2 * [L2] NOT &r5 :0 L2 END [&r25]
```

### &r25 (export table 19)

- columns: c0: Example, c1: Box, c2: Color
- depth 2, candidate keys none
- DETs its entries are assigned: &r5, &r25; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 10
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 2 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1 1 . . .
```
```
c0 | c1 | c2
e0 | (0,0)out | 1
e0 | (0,1)out | 1
```

Task-wide, rows whose Example column is e1: 4 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1 1 1 1 .
```
```
c0 | c1 | c2
e1 | (0,0)out | 1
e1 | (0,1)out | 1
e1 | (0,2)out | 1
e1 | (0,3)out | 1
```

Task-wide, rows whose Example column is e2: 4 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1 1 1 1 .
```
```
c0 | c1 | c2
e2 | (0,0)out | 1
e2 | (0,1)out | 1
e2 | (0,2)out | 1
e2 | (0,3)out | 1
```

```
DET &r25 :2 * [L0] END [&r26]
```

### &r26 (export table 20)

- columns: c0: Color
- depth 3, candidate keys none
- DETs its entries are assigned: &r5, &r25, &r26; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
c0
1
```

```
RULE &r26 :0 * [L0] END [&r27]
```

### &r27 (export table 21)

- columns: c0: Color
- depth 4, candidate keys none
- DETs its entries are assigned: &r5, &r25, &r26; assignments: 1
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
1
```

Train example 1: 1 row
```
c0
1
```

Train example 2: 1 row
```
c0
1
```

```
INIT Cardinality [:0] &r25 :0 ^ [L0] :1 * [L1] END [:1] &r25 :0 L0 :1 * [L2] END [:0] END [:1] L2 END [:2] SKIP [:2] SKIP [&r28] [&r29] [&r30]
```

### &r28 (export table 22)

- columns: c0: Example, c1: Number
- depth 4, candidate keys none
- DETs its entries are assigned: &r5, &r25; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 3
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 1 row
```
c0 | c1
e0 | 2
```

Task-wide, rows whose Example column is e1: 1 row
```
c0 | c1
e1 | 4
```

Task-wide, rows whose Example column is e2: 1 row
```
c0 | c1
e2 | 4
```

```
DET dir_elem :0 * [L0] &r28 :0 :0 * [L1] END :1 * [L2] ex_output :0 L1 :1 * [L3] margin :0 L3 :1 L0 :2 * [L4] < L4 L2 NOT &r25 :0 L1 :1 L3 END [&r31]
```

### &r31 (export table 23)

- columns: c0: Dir, c1: Example, c2: Box, c3: Number, c4: Number
- depth 5, candidate keys none
- DETs its entries are assigned: &r5, &r25, &r31; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 14
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 8 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . 2 3 3
```
```
c0 | c1 | c2 | c3 | c4
DIR_T | e0 | (0,2)out | 2 | 0
DIR_T | e0 | (0,3)out | 2 | 0
DIR_T | e0 | (0,4)out | 2 | 0
DIR_B | e0 | (0,2)out | 2 | 0
DIR_B | e0 | (0,3)out | 2 | 0
DIR_B | e0 | (0,4)out | 2 | 0
DIR_R | e0 | (0,3)out | 2 | 1
DIR_R | e0 | (0,4)out | 2 | 0
```

Task-wide, rows whose Example column is e1: 3 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . 3
```
```
c0 | c1 | c2 | c3 | c4
DIR_T | e1 | (0,4)out | 4 | 0
DIR_B | e1 | (0,4)out | 4 | 0
DIR_R | e1 | (0,4)out | 4 | 0
```

Task-wide, rows whose Example column is e2: 3 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . 3
```
```
c0 | c1 | c2 | c3 | c4
DIR_T | e2 | (0,4)out | 4 | 0
DIR_B | e2 | (0,4)out | 4 | 0
DIR_R | e2 | (0,4)out | 4 | 0
```

```
DET dir_elem :0 * [L0] NOT &r31 :0 L0 END [&r32]
```

### &r32 (export table 24)

- columns: c0: Dir
- depth 6, candidate keys none
- DETs its entries are assigned: &r5, &r25, &r31, &r32; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
c0
DIR_L
```

```
RULE &r9 :0 * [L0] &r32 :0 * [L1] margin :0 L0 :1 L1 :2 * [L2] &r24 :0 * [L3] < L2 L3 END [&r33]
```

### &r33 (export table 25)

- columns: c0: Box, c1: Number, c2: Dir, c3: Number
- depth 12, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r4, &r5, &r6, &r9, &r25, &r31, &r32; assignments: 9

#### &r33, assignment 1 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [0, 0, 0]; test: 0


#### &r33, assignment 2 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- empty at every example

#### &r33, assignment 3 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- empty at every example

#### &r33, assignment 4 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [2, 4, 4]; test: 3

Train example 0: 2 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 . . .
```
```
c0 | c1 | c2 | c3
(0,0)out | 2 | DIR_L | 0
(0,1)out | 2 | DIR_L | 1
```

Train example 1: 4 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 .
```
```
c0 | c1 | c2 | c3
(0,0)out | 4 | DIR_L | 0
(0,1)out | 4 | DIR_L | 1
(0,2)out | 4 | DIR_L | 2
(0,3)out | 4 | DIR_L | 3
```

Train example 2: 4 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 .
```
```
c0 | c1 | c2 | c3
(0,0)out | 4 | DIR_L | 0
(0,1)out | 4 | DIR_L | 1
(0,2)out | 4 | DIR_L | 2
(0,3)out | 4 | DIR_L | 3
```


#### &r33, assignment 5 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- empty at every example

#### &r33, assignment 6 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- empty at every example

#### &r33, assignment 7 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [3, 2, 3]; test: 4

Train example 0: 3 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 . .
```
```
c0 | c1 | c2 | c3
(0,0)out | 3 | DIR_L | 0
(0,1)out | 3 | DIR_L | 1
(0,2)out | 3 | DIR_L | 2
```

Train example 1: 2 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 . . .
```
```
c0 | c1 | c2 | c3
(0,0)out | 2 | DIR_L | 0
(0,1)out | 2 | DIR_L | 1
```

Train example 2: 3 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 . .
```
```
c0 | c1 | c2 | c3
(0,0)out | 3 | DIR_L | 0
(0,1)out | 3 | DIR_L | 1
(0,2)out | 3 | DIR_L | 2
```


#### &r33, assignment 8 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- empty at every example

#### &r33, assignment 9 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- empty at every example
```
RULE OR &r33 :0 * [L0] &r27 :0 * [L1] ALSO &r9 :0 L0 &r24 NOT &r33 :0 L0 &r27 &r5 :0 L1 END END [&r34]
```

### &r34 (export table 26)

- columns: c0: Box, c1: Color
- depth 13, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r4, &r5, &r6, &r9, &r25, &r26, &r31, &r32; assignments: 9

#### &r34, assignment 1 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [5, 5, 5]; test: 5

Train example 0: 5 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
0 0 0 0 0
```
```
c0 | c1
(0,0)out | 0
(0,1)out | 0
(0,2)out | 0
(0,3)out | 0
(0,4)out | 0
```

Train example 1: 5 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
0 0 0 0 0
```
```
c0 | c1
(0,0)out | 0
(0,1)out | 0
(0,2)out | 0
(0,3)out | 0
(0,4)out | 0
```

Train example 2: 5 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
0 0 0 0 0
```
```
c0 | c1
(0,0)out | 0
(0,1)out | 0
(0,2)out | 0
(0,3)out | 0
(0,4)out | 0
```


#### &r34, assignment 2 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- rows equal to those of assignment 1 at every example

#### &r34, assignment 3 of 9

- DET values that differ between the assignments: &r0 = {(0)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- rows equal to those of assignment 1 at every example

#### &r34, assignment 4 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [5, 5, 5]; test: 5

Train example 0: 5 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1 1 0 0 0
```
```
c0 | c1
(0,0)out | 1
(0,1)out | 1
(0,2)out | 0
(0,3)out | 0
(0,4)out | 0
```

Train example 1: 5 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1 1 1 1 0
```
```
c0 | c1
(0,0)out | 1
(0,1)out | 1
(0,2)out | 1
(0,3)out | 1
(0,4)out | 0
```

Train example 2: 5 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1 1 1 1 0
```
```
c0 | c1
(0,0)out | 1
(0,1)out | 1
(0,2)out | 1
(0,3)out | 1
(0,4)out | 0
```


#### &r34, assignment 5 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- rows equal to those of assignment 1 at every example

#### &r34, assignment 6 of 9

- DET values that differ between the assignments: &r0 = {(1)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- rows equal to those of assignment 1 at every example

#### &r34, assignment 7 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(2)}; &r4 = {([0 1 0 1]) ([0 1 1 0]) ([1 0 0 1]) ([1 0 1 0])}
- rows per train example: [5, 5, 5]; test: 5

Train example 0: 5 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1 1 1 0 0
```
```
c0 | c1
(0,0)out | 1
(0,1)out | 1
(0,2)out | 1
(0,3)out | 0
(0,4)out | 0
```

Train example 1: 5 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1 1 0 0 0
```
```
c0 | c1
(0,0)out | 1
(0,1)out | 1
(0,2)out | 0
(0,3)out | 0
(0,4)out | 0
```

Train example 2: 5 rows
Drawn on a 1x5 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1 1 1 0 0
```
```
c0 | c1
(0,0)out | 1
(0,1)out | 1
(0,2)out | 1
(0,3)out | 0
(0,4)out | 0
```


#### &r34, assignment 8 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(3)}; &r4 = {([0 2 0 2]) ([0 2 1 1]) ([0 2 2 0]) ([1 1 0 2]) ([1 1 1 1]) ([1 1 2 0]) ([2 0 0 2]) ([2 0 1 1]) ([2 0 2 0])}
- rows equal to those of assignment 1 at every example

#### &r34, assignment 9 of 9

- DET values that differ between the assignments: &r0 = {(2)}; &r1 = {(5)}; &r4 = {([0 4 0 4]) ([0 4 1 3]) ([0 4 2 2]) ([0 4 3 1]) ([0 4 4 0]) ([1 3 0 4]) ([1 3 1 3]) ([1 3 2 2]) ([1 3 3 1]) ([1 3 4 0]) ([2 2 0 4]) ([2 2 1 3]) ... 25 rows}
- rows equal to those of assignment 1 at every example
## What I see

The task: count the blue (1) 2x2 blocks of the input, and draw that count as a bar of 1s from the left of a 1x5 output. The outputs' bar lengths are 2, 4, 4.

Three DETs give the case nine assignments: &r0 (a color: 0, 1 or 2) crossed with &r1 (a size: 2, 3 or 5). A table that reads both has nine assignments, and most of the rows below are read per assignment.

- **&r0, &r1** (ColorDomain, TileCount): one task-wide row per assignment, colors 0, 1, 2 and sizes 2, 3, 5. The colors are the grids' colors. Where 2, 3, 5 come from I can't tell from the table or the grids: the clause names a lib DET and nothing else. No row says which assignment is right.
- **&r2, &r3** (Frame of N x N): every cell of an N x N frame (4, 9, 25 rows, drawn as full squares) and its two extents. Each is a product of N's range with itself, and holds nothing beyond &r1's N. **&r4** (DET of &r2) restates &r2 row for row at every assignment.
- **&r5** (DominantColor): one row, 0.
- **&r6** (DET on ex_output): 10 task-wide rows, 5 output cells x 2 axes, with extent 1 for AXIS_V and 5 for AXIS_H. The extent is a function of the axis, and the cell column is a factor of a product. The new fact is one fact: every output is 1x5. **&r7, &r9** restate it as the 5 cells of a 1x5 frame.
- **&r10**: the input cells of &r0's color, a selection of the input: 57/51/49 background cells at assignment 1, 12/18/19 blue cells at assignment 2, 12/12/13 red cells at assignment 3.
- **&r11** (Connectivity labels): &r10's cells with a component Ident. At assignment 1 the drawing is all `a`: one component per example, so the table is &r10 plus a constant. At assignments 2 and 3 the letters split the cells into 2x2 blocks and single cells. An Ident is equal across examples for the same cell set: id3 is the single cell (8,1) in train 0 and in train 1 (&r15, assignment 2).
- **&r15** (BoundingBox): one row per component, so the Ident is a key. At assignment 1 the box is the whole grid, printed `+(0,0)` because its margins [0 0 0 0] decode as the zero offset. At assignment 2 (blue): 6/6/7 boxes, single cells such as `id1 | (0,8)` beside 2x2 boxes such as `id4 | r5-6 c5-6`. This is the first table in which a 2x2 block is one row.
- **&r20** (Inclusion's relative positions): each component cell as a cell of its own box. The renderer prints these as boxes over the input: `r0-7 c0-7` is the margins [0 1 0 1], cell (0,0) of a 2x2 box, and `+(0,0)` is the one cell of a 1x1 box. At assignment 1 the box is the whole grid, so the 57/51/49 rows are &r11's rows with the columns swapped: a restatement. At assignments 2 and 3: four rows per 2x2 block, one per single cell.
- **&r17, &r18** (Inclusion against &r4's shape): the Idents whose cells equal the N x N shape. Seven of the nine assignments are empty at every example (color 0, or N 3 or 5). Assignment 4 (color 1, N 2) gives 2/4/4 Idents, `id4`, `id6` in train 0, the two 2x2 boxes of &r15. Assignment 7 (color 2, N 2) gives 3/2/3. &r17 and &r18 hold equal rows at every assignment, so from rows alone each restates the other.
- **&r21** (Cardinality of &r18), **&r24** (a RULE copy of it): one Number per example. It is 2, 4, 4 at assignment 4, 3, 2, 3 at assignment 7 and 0 at the others. &r21 is an aggregate, and &r24 restates &r21.
- **&r25** (DET: output cells that are not &r5's color): the bar, (0,0)-(0,1) in e0 and (0,0)-(0,3) in e1 and e2, color 1. A selection of ex_output.
- **&r26, &r27**: the bar color 1, task-wide, then one copy per train example. &r27 is a product of &r26 with the examples.
- **&r28** (Cardinality of &r25): the bar length per example, `e0 | 2`, `e1 | 4`, `e2 | 4`. Example to Number is a function. This sequence is &r21's at assignment 4 and at no other assignment. With &r21 in view, here the rule shows: the count of blue 2x2 blocks is the bar's length. The information about the rule jumps at &r15 (blocks as rows), then &r18 at assignment 4, then the match of &r21 and &r28.
- **&r31** (DET: the edges the bar does not run from): 14 rows of (direction, example, cell, length, distance), the cells within the bar's length from an edge that the bar misses. They hold DIR_T, DIR_B and DIR_R and no DIR_L. **&r32** is DIR_L, the one direction &r31 lacks. &r31 is a guard read under NOT, and its information is the direction it lacks.
- **&r33** (marked): the cells within the count of the left edge. At assignment 4 the drawings `1 1 . . .`, `1 1 1 1 .`, `1 1 1 1 .` equal &r25's cells. At assignment 7 they are 3, 2, 3 cells, which do not.
- **&r34** (out): five rows per example at every assignment. Assignment 4 equals the outputs, assignment 7 does not, and the seven others are all 0 (a count of 0). The table alone does not say which assignment is the case's. A comparison with the output grids does.

Rows that look like noise: the frame products &r2, &r3, &r4, &r7, &r9; &r11 and &r20 at assignment 1, where the background is one component and its box is the grid; the restatements &r24, &r27, and &r17 beside &r18; and the assignments that are empty at every example, seven of nine in &r17, &r18 and &r33.
