# b5bb5719, case `&background=$Stored $UnderPair $SwapSide $StoredGrow`

- concept case: True; tokens: 476; tables: 27 relations, 132 per assignment
- cells: a Position is `(row,col)` of the example's input grid (`(row,col)out` where it fits only the output grid), an Offset `+(drow,dcol)`, another Box `rR0-R1 cC0-C1` over the input grid or `[t b l r]` margins; an Ident is `id<n>`, equal only within one case; see README.md

## Grids

### Train example 0: input 3x5, output 3x5

```
input        output
7 5 7 2 7    7 5 7 2 7
7 7 7 7 7    7 7 2 7 7
7 7 7 7 7    7 7 7 7 7
```

### Train example 1: input 3x5, output 3x5

```
input        output
7 2 7 2 7    7 2 7 2 7
7 7 7 7 7    7 7 5 7 7
7 7 7 7 7    7 7 7 7 7
```

### Train example 2: input 3x5, output 3x5

```
input        output
2 5 2 5 2    2 5 2 5 2
7 7 7 7 7    7 5 2 5 7
7 7 7 7 7    7 7 2 7 7
```

### Train example 3: input 3x5, output 3x5

```
input        output
7 2 7 5 7    7 2 7 5 7
7 7 7 7 7    7 7 5 7 7
7 7 7 7 7    7 7 7 7 7
```

### Train example 4: input 5x9, output 5x9

```
input                output
5 5 2 2 5 5 5 2 2    5 5 2 2 5 5 5 2 2
7 7 7 7 7 7 7 7 7    7 2 2 5 5 2 2 2 7
7 7 7 7 7 7 7 7 7    7 7 5 5 2 2 5 7 7
7 7 7 7 7 7 7 7 7    7 7 7 2 2 5 7 7 7
7 7 7 7 7 7 7 7 7    7 7 7 7 5 7 7 7 7
```

### Train example 5: input 3x5, output 3x5

```
input        output
7 5 7 5 7    7 5 7 5 7
7 7 7 7 7    7 7 2 7 7
7 7 7 7 7    7 7 7 7 7
```

### Train example 6: input 4x7, output 4x7

```
input            output
5 2 5 5 5 5 2    5 2 5 5 5 5 2
7 7 7 7 7 7 7    7 2 5 2 2 2 7
7 7 7 7 7 7 7    7 7 5 2 5 7 7
7 7 7 7 7 7 7    7 7 7 2 7 7 7
```

### Test example 0: input 6x12

```
5 5 5 5 5 5 5 5 5 5 5 7
7 7 7 7 7 7 7 7 7 7 7 7
7 7 7 7 7 7 7 7 7 7 7 7
7 7 7 7 7 7 7 7 7 7 7 7
7 7 7 7 7 7 7 7 7 7 7 7
7 7 7 7 7 7 7 7 7 7 7 7
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
- rows per train example: [0, 0, 0, 0, 0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
C
7
```

```
DET DirDomain END [&r1]
```

### &r1 (export table 3)

- columns: D: Dir
- depth 1, candidate keys none
- DETs its entries are assigned: &r1; assignments: 4

#### &r1, assignment 1 of 4

- DET values that differ between the assignments: &r1 = {(DIR_T)}
- rows per train example: [0, 0, 0, 0, 0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
DIR_T
```


#### &r1, assignment 2 of 4

- DET values that differ between the assignments: &r1 = {(DIR_B)}
- rows per train example: [0, 0, 0, 0, 0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
DIR_B
```


#### &r1, assignment 3 of 4

- DET values that differ between the assignments: &r1 = {(DIR_L)}
- rows per train example: [0, 0, 0, 0, 0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
DIR_L
```


#### &r1, assignment 4 of 4

- DET values that differ between the assignments: &r1 = {(DIR_R)}
- rows per train example: [0, 0, 0, 0, 0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
DIR_R
```

```
RULE input :0 * [L0] :1 * [L1] NOT &r0 :0 L1 END [&r2]
```

### &r2 (export table 4)

- columns: c0: Box, c1: Color
- depth 2, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [2, 2, 5, 2, 9, 2, 7]; test: 11

Train example 0: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 5 . 2 .
. . . . .
. . . . .
```
```
c0 | c1
(0,1) | 5
(0,3) | 2
```

Train example 1: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . 2 .
. . . . .
. . . . .
```
```
c0 | c1
(0,1) | 2
(0,3) | 2
```

Train example 2: 5 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 5 2 5 2
. . . . .
. . . . .
```
```
c0 | c1
(0,0) | 2
(0,1) | 5
(0,2) | 2
(0,3) | 5
(0,4) | 2
```

Train example 3: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . 5 .
. . . . .
. . . . .
```
```
c0 | c1
(0,1) | 2
(0,3) | 5
```

Train example 4: 9 rows
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 5 2 2 5 5 5 2 2
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1
(0,0) | 5
(0,1) | 5
(0,2) | 2
(0,3) | 2
(0,4) | 5
(0,5) | 5
(0,6) | 5
(0,7) | 2
(0,8) | 2
```

Train example 5: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 5 . 5 .
. . . . .
. . . . .
```
```
c0 | c1
(0,1) | 5
(0,3) | 5
```

Train example 6: 7 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 2 5 5 5 5 2
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1
(0,0) | 5
(0,1) | 2
(0,2) | 5
(0,3) | 5
(0,4) | 5
(0,5) | 5
(0,6) | 2
```

```
DET ex_input :2 * [L0] NOT &r0 :0 L0 ex_input :2 * [L1] NOT &r0 :0 L1 != L0 L1 END [&r3]
```

### &r3 (export table 5)

- columns: c0: Color, c1: Color
- depth 2, candidate keys none
- DETs its entries are assigned: &r0, &r3; assignments: 1
- rows per train example: [0, 0, 0, 0, 0, 0, 0]; test: 0; task-wide: 2
- every row is of a task-wide entry

Task-wide: 2 rows
```
c0 | c1
2 | 5
5 | 2
```

```
INIT Singleton [:0] SKIP [:1] dir_elem :0 * [L0] ALL &r2 :1 * [L1] END margin :0 L1 :1 L0 :2 0 END END [:0] END [:1] L0 END [&r4] [&r5] [&r6]
```

### &r4 (export table 6)

- columns: c0: Dir
- depth 4, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
DIR_T
```

Train example 1: 1 row
```
c0
DIR_T
```

Train example 2: 1 row
```
c0
DIR_T
```

Train example 3: 1 row
```
c0
DIR_T
```

Train example 4: 1 row
```
c0
DIR_T
```

Train example 5: 1 row
```
c0
DIR_T
```

Train example 6: 1 row
```
c0
DIR_T
```

### &r5 (export table 7)

- columns: none
- depth 4, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [0, 0, 0, 0, 0, 0, 0]; test: 0

### &r6 (export table 8)

- columns: c0: Dir
- depth 3, candidate keys none
- DETs its entries are assigned: &r0; assignments: 1
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
DIR_T
```

Train example 1: 1 row
```
c0
DIR_T
```

Train example 2: 1 row
```
c0
DIR_T
```

Train example 3: 1 row
```
c0
DIR_T
```

Train example 4: 1 row
```
c0
DIR_T
```

Train example 5: 1 row
```
c0
DIR_T
```

Train example 6: 1 row
```
c0
DIR_T
```

```
RULE &r1 :0 * [L0] END [&r7]
```

### &r7 (export table 9)

- columns: c0: Dir
- depth 2, candidate keys none
- DETs its entries are assigned: &r1; assignments: 4

#### &r7, assignment 1 of 4

- DET values that differ between the assignments: &r1 = {(DIR_T)}
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
DIR_T
```

Train example 1: 1 row
```
c0
DIR_T
```

Train example 2: 1 row
```
c0
DIR_T
```

Train example 3: 1 row
```
c0
DIR_T
```

Train example 4: 1 row
```
c0
DIR_T
```

Train example 5: 1 row
```
c0
DIR_T
```

Train example 6: 1 row
```
c0
DIR_T
```


#### &r7, assignment 2 of 4

- DET values that differ between the assignments: &r1 = {(DIR_B)}
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
DIR_B
```

Train example 1: 1 row
```
c0
DIR_B
```

Train example 2: 1 row
```
c0
DIR_B
```

Train example 3: 1 row
```
c0
DIR_B
```

Train example 4: 1 row
```
c0
DIR_B
```

Train example 5: 1 row
```
c0
DIR_B
```

Train example 6: 1 row
```
c0
DIR_B
```


#### &r7, assignment 3 of 4

- DET values that differ between the assignments: &r1 = {(DIR_L)}
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
DIR_L
```

Train example 1: 1 row
```
c0
DIR_L
```

Train example 2: 1 row
```
c0
DIR_L
```

Train example 3: 1 row
```
c0
DIR_L
```

Train example 4: 1 row
```
c0
DIR_L
```

Train example 5: 1 row
```
c0
DIR_L
```

Train example 6: 1 row
```
c0
DIR_L
```


#### &r7, assignment 4 of 4

- DET values that differ between the assignments: &r1 = {(DIR_R)}
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
DIR_R
```

Train example 1: 1 row
```
c0
DIR_R
```

Train example 2: 1 row
```
c0
DIR_R
```

Train example 3: 1 row
```
c0
DIR_R
```

Train example 4: 1 row
```
c0
DIR_R
```

Train example 5: 1 row
```
c0
DIR_R
```

Train example 6: 1 row
```
c0
DIR_R
```

```
RULE &r7 :0 * [L0] axis_of :0 L0 :1 * [L1] perp :0 L1 :1 * [L2] END [&r8]
```

### &r8 (export table 10)

- columns: c0: Dir, c1: Axis, c2: Axis
- depth 3, candidate keys none
- DETs its entries are assigned: &r1; assignments: 4

#### &r8, assignment 1 of 4

- DET values that differ between the assignments: &r1 = {(DIR_T)}
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1 | c2
DIR_T | AXIS_H | AXIS_V
```

Train example 1: 1 row
```
c0 | c1 | c2
DIR_T | AXIS_H | AXIS_V
```

Train example 2: 1 row
```
c0 | c1 | c2
DIR_T | AXIS_H | AXIS_V
```

Train example 3: 1 row
```
c0 | c1 | c2
DIR_T | AXIS_H | AXIS_V
```

Train example 4: 1 row
```
c0 | c1 | c2
DIR_T | AXIS_H | AXIS_V
```

Train example 5: 1 row
```
c0 | c1 | c2
DIR_T | AXIS_H | AXIS_V
```

Train example 6: 1 row
```
c0 | c1 | c2
DIR_T | AXIS_H | AXIS_V
```


#### &r8, assignment 2 of 4

- DET values that differ between the assignments: &r1 = {(DIR_B)}
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1 | c2
DIR_B | AXIS_H | AXIS_V
```

Train example 1: 1 row
```
c0 | c1 | c2
DIR_B | AXIS_H | AXIS_V
```

Train example 2: 1 row
```
c0 | c1 | c2
DIR_B | AXIS_H | AXIS_V
```

Train example 3: 1 row
```
c0 | c1 | c2
DIR_B | AXIS_H | AXIS_V
```

Train example 4: 1 row
```
c0 | c1 | c2
DIR_B | AXIS_H | AXIS_V
```

Train example 5: 1 row
```
c0 | c1 | c2
DIR_B | AXIS_H | AXIS_V
```

Train example 6: 1 row
```
c0 | c1 | c2
DIR_B | AXIS_H | AXIS_V
```


#### &r8, assignment 3 of 4

- DET values that differ between the assignments: &r1 = {(DIR_L)}
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1 | c2
DIR_L | AXIS_V | AXIS_H
```

Train example 1: 1 row
```
c0 | c1 | c2
DIR_L | AXIS_V | AXIS_H
```

Train example 2: 1 row
```
c0 | c1 | c2
DIR_L | AXIS_V | AXIS_H
```

Train example 3: 1 row
```
c0 | c1 | c2
DIR_L | AXIS_V | AXIS_H
```

Train example 4: 1 row
```
c0 | c1 | c2
DIR_L | AXIS_V | AXIS_H
```

Train example 5: 1 row
```
c0 | c1 | c2
DIR_L | AXIS_V | AXIS_H
```

Train example 6: 1 row
```
c0 | c1 | c2
DIR_L | AXIS_V | AXIS_H
```


#### &r8, assignment 4 of 4

- DET values that differ between the assignments: &r1 = {(DIR_R)}
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1 | c2
DIR_R | AXIS_V | AXIS_H
```

Train example 1: 1 row
```
c0 | c1 | c2
DIR_R | AXIS_V | AXIS_H
```

Train example 2: 1 row
```
c0 | c1 | c2
DIR_R | AXIS_V | AXIS_H
```

Train example 3: 1 row
```
c0 | c1 | c2
DIR_R | AXIS_V | AXIS_H
```

Train example 4: 1 row
```
c0 | c1 | c2
DIR_R | AXIS_V | AXIS_H
```

Train example 5: 1 row
```
c0 | c1 | c2
DIR_R | AXIS_V | AXIS_H
```

Train example 6: 1 row
```
c0 | c1 | c2
DIR_R | AXIS_V | AXIS_H
```

```
INIT Ray [:0] SKIP [:1] &r7 &r2 :1 * [L0] END [:0] END [:1] L0 END [:2] input :0 * [L1] END [:0] END [:1] L1 END [:3] &r8 :3 * [L2] axis4_of :0 * [L3] :1 L2 END [:0] END [:1] L3 END [&r9] [&r10] [&r11] [&r12] [&r13]
```

### &r9 (export table 11)

- columns: c0: Box, c1: Dir8, c2: Number, c3: Box
- depth 5, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 4

#### &r9, assignment 1 of 4

- DET values that differ between the assignments: &r1 = {(DIR_T)}
- rows per train example: [12, 12, 30, 12, 90, 12, 56]; test: 143

Train example 0: 12 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 3 2 3 2
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 1 | (0,1)
(0,0) | DIR_L | 3 | (0,3)
(0,1) | DIR_L | 0 | (0,1)
(0,1) | DIR_L | 2 | (0,3)
(0,1) | DIR_R | 0 | (0,1)
(0,2) | DIR_L | 1 | (0,3)
(0,2) | DIR_R | 1 | (0,1)
(0,3) | DIR_L | 0 | (0,3)
(0,3) | DIR_R | 0 | (0,3)
(0,3) | DIR_R | 2 | (0,1)
(0,4) | DIR_R | 1 | (0,3)
(0,4) | DIR_R | 3 | (0,1)
```

Train example 1: 12 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 3 2 3 2
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 1 | (0,1)
(0,0) | DIR_L | 3 | (0,3)
(0,1) | DIR_L | 0 | (0,1)
(0,1) | DIR_L | 2 | (0,3)
(0,1) | DIR_R | 0 | (0,1)
(0,2) | DIR_L | 1 | (0,3)
(0,2) | DIR_R | 1 | (0,1)
(0,3) | DIR_L | 0 | (0,3)
(0,3) | DIR_R | 0 | (0,3)
(0,3) | DIR_R | 2 | (0,1)
(0,4) | DIR_R | 1 | (0,3)
(0,4) | DIR_R | 3 | (0,1)
```

Train example 2: 30 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
6 6 6 6 6
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,0) | DIR_L | 1 | (0,1)
(0,0) | DIR_L | 2 | (0,2)
(0,0) | DIR_L | 3 | (0,3)
(0,0) | DIR_L | 4 | (0,4)
(0,0) | DIR_R | 0 | (0,0)
(0,1) | DIR_L | 0 | (0,1)
(0,1) | DIR_L | 1 | (0,2)
(0,1) | DIR_L | 2 | (0,3)
(0,1) | DIR_L | 3 | (0,4)
(0,1) | DIR_R | 0 | (0,1)
(0,1) | DIR_R | 1 | (0,0)
(0,2) | DIR_L | 0 | (0,2)
(0,2) | DIR_L | 1 | (0,3)
(0,2) | DIR_L | 2 | (0,4)
(0,2) | DIR_R | 0 | (0,2)
(0,2) | DIR_R | 1 | (0,1)
(0,2) | DIR_R | 2 | (0,0)
(0,3) | DIR_L | 0 | (0,3)
(0,3) | DIR_L | 1 | (0,4)
(0,3) | DIR_R | 0 | (0,3)
(0,3) | DIR_R | 1 | (0,2)
(0,3) | DIR_R | 2 | (0,1)
(0,3) | DIR_R | 3 | (0,0)
(0,4) | DIR_L | 0 | (0,4)
(0,4) | DIR_R | 0 | (0,4)
(0,4) | DIR_R | 1 | (0,3)
(0,4) | DIR_R | 2 | (0,2)
(0,4) | DIR_R | 3 | (0,1)
(0,4) | DIR_R | 4 | (0,0)
```

Train example 3: 12 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 3 2 3 2
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 1 | (0,1)
(0,0) | DIR_L | 3 | (0,3)
(0,1) | DIR_L | 0 | (0,1)
(0,1) | DIR_L | 2 | (0,3)
(0,1) | DIR_R | 0 | (0,1)
(0,2) | DIR_L | 1 | (0,3)
(0,2) | DIR_R | 1 | (0,1)
(0,3) | DIR_L | 0 | (0,3)
(0,3) | DIR_R | 0 | (0,3)
(0,3) | DIR_R | 2 | (0,1)
(0,4) | DIR_R | 1 | (0,3)
(0,4) | DIR_R | 3 | (0,1)
```

Train example 4: 90 rows, the first 30 shown
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
+ + + + + + + + +
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,0) | DIR_L | 1 | (0,1)
(0,0) | DIR_L | 2 | (0,2)
(0,0) | DIR_L | 3 | (0,3)
(0,0) | DIR_L | 4 | (0,4)
(0,0) | DIR_L | 5 | (0,5)
(0,0) | DIR_L | 6 | (0,6)
(0,0) | DIR_L | 7 | (0,7)
(0,0) | DIR_L | 8 | (0,8)
(0,0) | DIR_R | 0 | (0,0)
(0,1) | DIR_L | 0 | (0,1)
(0,1) | DIR_L | 1 | (0,2)
(0,1) | DIR_L | 2 | (0,3)
(0,1) | DIR_L | 3 | (0,4)
(0,1) | DIR_L | 4 | (0,5)
(0,1) | DIR_L | 5 | (0,6)
(0,1) | DIR_L | 6 | (0,7)
(0,1) | DIR_L | 7 | (0,8)
(0,1) | DIR_R | 0 | (0,1)
(0,1) | DIR_R | 1 | (0,0)
(0,2) | DIR_L | 0 | (0,2)
(0,2) | DIR_L | 1 | (0,3)
(0,2) | DIR_L | 2 | (0,4)
(0,2) | DIR_L | 3 | (0,5)
(0,2) | DIR_L | 4 | (0,6)
(0,2) | DIR_L | 5 | (0,7)
(0,2) | DIR_L | 6 | (0,8)
(0,2) | DIR_R | 0 | (0,2)
(0,2) | DIR_R | 1 | (0,1)
(0,2) | DIR_R | 2 | (0,0)
```

Train example 5: 12 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 3 2 3 2
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 1 | (0,1)
(0,0) | DIR_L | 3 | (0,3)
(0,1) | DIR_L | 0 | (0,1)
(0,1) | DIR_L | 2 | (0,3)
(0,1) | DIR_R | 0 | (0,1)
(0,2) | DIR_L | 1 | (0,3)
(0,2) | DIR_R | 1 | (0,1)
(0,3) | DIR_L | 0 | (0,3)
(0,3) | DIR_R | 0 | (0,3)
(0,3) | DIR_R | 2 | (0,1)
(0,4) | DIR_R | 1 | (0,3)
(0,4) | DIR_R | 3 | (0,1)
```

Train example 6: 56 rows, the first 30 shown
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
8 8 8 8 8 8 8
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,0) | DIR_L | 1 | (0,1)
(0,0) | DIR_L | 2 | (0,2)
(0,0) | DIR_L | 3 | (0,3)
(0,0) | DIR_L | 4 | (0,4)
(0,0) | DIR_L | 5 | (0,5)
(0,0) | DIR_L | 6 | (0,6)
(0,0) | DIR_R | 0 | (0,0)
(0,1) | DIR_L | 0 | (0,1)
(0,1) | DIR_L | 1 | (0,2)
(0,1) | DIR_L | 2 | (0,3)
(0,1) | DIR_L | 3 | (0,4)
(0,1) | DIR_L | 4 | (0,5)
(0,1) | DIR_L | 5 | (0,6)
(0,1) | DIR_R | 0 | (0,1)
(0,1) | DIR_R | 1 | (0,0)
(0,2) | DIR_L | 0 | (0,2)
(0,2) | DIR_L | 1 | (0,3)
(0,2) | DIR_L | 2 | (0,4)
(0,2) | DIR_L | 3 | (0,5)
(0,2) | DIR_L | 4 | (0,6)
(0,2) | DIR_R | 0 | (0,2)
(0,2) | DIR_R | 1 | (0,1)
(0,2) | DIR_R | 2 | (0,0)
(0,3) | DIR_L | 0 | (0,3)
(0,3) | DIR_L | 1 | (0,4)
(0,3) | DIR_L | 2 | (0,5)
(0,3) | DIR_L | 3 | (0,6)
(0,3) | DIR_R | 0 | (0,3)
(0,3) | DIR_R | 1 | (0,2)
```


#### &r9, assignment 2 of 4

- DET values that differ between the assignments: &r1 = {(DIR_B)}
- rows equal to those of assignment 1 at every example

#### &r9, assignment 3 of 4

- DET values that differ between the assignments: &r1 = {(DIR_L)}
- rows per train example: [8, 8, 20, 8, 54, 8, 35]; test: 77

Train example 0: 8 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 2 . 2 .
. 1 . 1 .
. 1 . 1 .
```
```
c0 | c1 | c2 | c3
(0,1) | DIR_T | 0 | (0,1)
(0,1) | DIR_B | 0 | (0,1)
(0,3) | DIR_T | 0 | (0,3)
(0,3) | DIR_B | 0 | (0,3)
(1,1) | DIR_B | 1 | (0,1)
(1,3) | DIR_B | 1 | (0,3)
(2,1) | DIR_B | 2 | (0,1)
(2,3) | DIR_B | 2 | (0,3)
```

Train example 1: 8 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 2 . 2 .
. 1 . 1 .
. 1 . 1 .
```
```
c0 | c1 | c2 | c3
(0,1) | DIR_T | 0 | (0,1)
(0,1) | DIR_B | 0 | (0,1)
(0,3) | DIR_T | 0 | (0,3)
(0,3) | DIR_B | 0 | (0,3)
(1,1) | DIR_B | 1 | (0,1)
(1,3) | DIR_B | 1 | (0,3)
(2,1) | DIR_B | 2 | (0,1)
(2,3) | DIR_B | 2 | (0,3)
```

Train example 2: 20 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2 2 2
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,0) | DIR_B | 0 | (0,0)
(0,1) | DIR_T | 0 | (0,1)
(0,1) | DIR_B | 0 | (0,1)
(0,2) | DIR_T | 0 | (0,2)
(0,2) | DIR_B | 0 | (0,2)
(0,3) | DIR_T | 0 | (0,3)
(0,3) | DIR_B | 0 | (0,3)
(0,4) | DIR_T | 0 | (0,4)
(0,4) | DIR_B | 0 | (0,4)
(1,0) | DIR_B | 1 | (0,0)
(1,1) | DIR_B | 1 | (0,1)
(1,2) | DIR_B | 1 | (0,2)
(1,3) | DIR_B | 1 | (0,3)
(1,4) | DIR_B | 1 | (0,4)
(2,0) | DIR_B | 2 | (0,0)
(2,1) | DIR_B | 2 | (0,1)
(2,2) | DIR_B | 2 | (0,2)
(2,3) | DIR_B | 2 | (0,3)
(2,4) | DIR_B | 2 | (0,4)
```

Train example 3: 8 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 2 . 2 .
. 1 . 1 .
. 1 . 1 .
```
```
c0 | c1 | c2 | c3
(0,1) | DIR_T | 0 | (0,1)
(0,1) | DIR_B | 0 | (0,1)
(0,3) | DIR_T | 0 | (0,3)
(0,3) | DIR_B | 0 | (0,3)
(1,1) | DIR_B | 1 | (0,1)
(1,3) | DIR_B | 1 | (0,3)
(2,1) | DIR_B | 2 | (0,1)
(2,3) | DIR_B | 2 | (0,3)
```

Train example 4: 54 rows, the first 30 shown
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2 2 2 2 2 2 2
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,0) | DIR_B | 0 | (0,0)
(0,1) | DIR_T | 0 | (0,1)
(0,1) | DIR_B | 0 | (0,1)
(0,2) | DIR_T | 0 | (0,2)
(0,2) | DIR_B | 0 | (0,2)
(0,3) | DIR_T | 0 | (0,3)
(0,3) | DIR_B | 0 | (0,3)
(0,4) | DIR_T | 0 | (0,4)
(0,4) | DIR_B | 0 | (0,4)
(0,5) | DIR_T | 0 | (0,5)
(0,5) | DIR_B | 0 | (0,5)
(0,6) | DIR_T | 0 | (0,6)
(0,6) | DIR_B | 0 | (0,6)
(0,7) | DIR_T | 0 | (0,7)
(0,7) | DIR_B | 0 | (0,7)
(0,8) | DIR_T | 0 | (0,8)
(0,8) | DIR_B | 0 | (0,8)
(1,0) | DIR_B | 1 | (0,0)
(1,1) | DIR_B | 1 | (0,1)
(1,2) | DIR_B | 1 | (0,2)
(1,3) | DIR_B | 1 | (0,3)
(1,4) | DIR_B | 1 | (0,4)
(1,5) | DIR_B | 1 | (0,5)
(1,6) | DIR_B | 1 | (0,6)
(1,7) | DIR_B | 1 | (0,7)
(1,8) | DIR_B | 1 | (0,8)
(2,0) | DIR_B | 2 | (0,0)
(2,1) | DIR_B | 2 | (0,1)
(2,2) | DIR_B | 2 | (0,2)
```

Train example 5: 8 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 2 . 2 .
. 1 . 1 .
. 1 . 1 .
```
```
c0 | c1 | c2 | c3
(0,1) | DIR_T | 0 | (0,1)
(0,1) | DIR_B | 0 | (0,1)
(0,3) | DIR_T | 0 | (0,3)
(0,3) | DIR_B | 0 | (0,3)
(1,1) | DIR_B | 1 | (0,1)
(1,3) | DIR_B | 1 | (0,3)
(2,1) | DIR_B | 2 | (0,1)
(2,3) | DIR_B | 2 | (0,3)
```

Train example 6: 35 rows, the first 30 shown
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2 2 2 2 2
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,0) | DIR_B | 0 | (0,0)
(0,1) | DIR_T | 0 | (0,1)
(0,1) | DIR_B | 0 | (0,1)
(0,2) | DIR_T | 0 | (0,2)
(0,2) | DIR_B | 0 | (0,2)
(0,3) | DIR_T | 0 | (0,3)
(0,3) | DIR_B | 0 | (0,3)
(0,4) | DIR_T | 0 | (0,4)
(0,4) | DIR_B | 0 | (0,4)
(0,5) | DIR_T | 0 | (0,5)
(0,5) | DIR_B | 0 | (0,5)
(0,6) | DIR_T | 0 | (0,6)
(0,6) | DIR_B | 0 | (0,6)
(1,0) | DIR_B | 1 | (0,0)
(1,1) | DIR_B | 1 | (0,1)
(1,2) | DIR_B | 1 | (0,2)
(1,3) | DIR_B | 1 | (0,3)
(1,4) | DIR_B | 1 | (0,4)
(1,5) | DIR_B | 1 | (0,5)
(1,6) | DIR_B | 1 | (0,6)
(2,0) | DIR_B | 2 | (0,0)
(2,1) | DIR_B | 2 | (0,1)
(2,2) | DIR_B | 2 | (0,2)
(2,3) | DIR_B | 2 | (0,3)
(2,4) | DIR_B | 2 | (0,4)
(2,5) | DIR_B | 2 | (0,5)
(2,6) | DIR_B | 2 | (0,6)
(3,0) | DIR_B | 3 | (0,0)
(3,1) | DIR_B | 3 | (0,1)
```


#### &r9, assignment 4 of 4

- DET values that differ between the assignments: &r1 = {(DIR_R)}
- rows equal to those of assignment 3 at every example
### &r10 (export table 12)

- columns: c0: Box, c1: Dir8, c2: Number, c3: Box
- depth 5, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 4

#### &r10, assignment 1 of 4

- DET values that differ between the assignments: &r1 = {(DIR_T)}
- rows per train example: [4, 4, 10, 4, 18, 4, 14]; test: 22

Train example 0: 4 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 . . . 2
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 1 | (0,1)
(0,0) | DIR_L | 3 | (0,3)
(0,4) | DIR_R | 1 | (0,3)
(0,4) | DIR_R | 3 | (0,1)
```

Train example 1: 4 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 . . . 2
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 1 | (0,1)
(0,0) | DIR_L | 3 | (0,3)
(0,4) | DIR_R | 1 | (0,3)
(0,4) | DIR_R | 3 | (0,1)
```

Train example 2: 10 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
5 . . . 5
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,0) | DIR_L | 1 | (0,1)
(0,0) | DIR_L | 2 | (0,2)
(0,0) | DIR_L | 3 | (0,3)
(0,0) | DIR_L | 4 | (0,4)
(0,4) | DIR_R | 0 | (0,4)
(0,4) | DIR_R | 1 | (0,3)
(0,4) | DIR_R | 2 | (0,2)
(0,4) | DIR_R | 3 | (0,1)
(0,4) | DIR_R | 4 | (0,0)
```

Train example 3: 4 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 . . . 2
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 1 | (0,1)
(0,0) | DIR_L | 3 | (0,3)
(0,4) | DIR_R | 1 | (0,3)
(0,4) | DIR_R | 3 | (0,1)
```

Train example 4: 18 rows
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
9 . . . . . . . 9
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,0) | DIR_L | 1 | (0,1)
(0,0) | DIR_L | 2 | (0,2)
(0,0) | DIR_L | 3 | (0,3)
(0,0) | DIR_L | 4 | (0,4)
(0,0) | DIR_L | 5 | (0,5)
(0,0) | DIR_L | 6 | (0,6)
(0,0) | DIR_L | 7 | (0,7)
(0,0) | DIR_L | 8 | (0,8)
(0,8) | DIR_R | 0 | (0,8)
(0,8) | DIR_R | 1 | (0,7)
(0,8) | DIR_R | 2 | (0,6)
(0,8) | DIR_R | 3 | (0,5)
(0,8) | DIR_R | 4 | (0,4)
(0,8) | DIR_R | 5 | (0,3)
(0,8) | DIR_R | 6 | (0,2)
(0,8) | DIR_R | 7 | (0,1)
(0,8) | DIR_R | 8 | (0,0)
```

Train example 5: 4 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 . . . 2
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 1 | (0,1)
(0,0) | DIR_L | 3 | (0,3)
(0,4) | DIR_R | 1 | (0,3)
(0,4) | DIR_R | 3 | (0,1)
```

Train example 6: 14 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
7 . . . . . 7
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_L | 0 | (0,0)
(0,0) | DIR_L | 1 | (0,1)
(0,0) | DIR_L | 2 | (0,2)
(0,0) | DIR_L | 3 | (0,3)
(0,0) | DIR_L | 4 | (0,4)
(0,0) | DIR_L | 5 | (0,5)
(0,0) | DIR_L | 6 | (0,6)
(0,6) | DIR_R | 0 | (0,6)
(0,6) | DIR_R | 1 | (0,5)
(0,6) | DIR_R | 2 | (0,4)
(0,6) | DIR_R | 3 | (0,3)
(0,6) | DIR_R | 4 | (0,2)
(0,6) | DIR_R | 5 | (0,1)
(0,6) | DIR_R | 6 | (0,0)
```


#### &r10, assignment 2 of 4

- DET values that differ between the assignments: &r1 = {(DIR_B)}
- rows equal to those of assignment 1 at every example

#### &r10, assignment 3 of 4

- DET values that differ between the assignments: &r1 = {(DIR_L)}
- rows per train example: [4, 4, 10, 4, 18, 4, 14]; test: 22

Train example 0: 4 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. 0 . 0 .
. . . . .
. 2 . 2 .
```
```
c0 | c1 | c2 | c3
(0,1) | DIR_T | 0 | (0,1)
(0,3) | DIR_T | 0 | (0,3)
(2,1) | DIR_B | 2 | (0,1)
(2,3) | DIR_B | 2 | (0,3)
```

Train example 1: 4 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. 0 . 0 .
. . . . .
. 2 . 2 .
```
```
c0 | c1 | c2 | c3
(0,1) | DIR_T | 0 | (0,1)
(0,3) | DIR_T | 0 | (0,3)
(2,1) | DIR_B | 2 | (0,1)
(2,3) | DIR_B | 2 | (0,3)
```

Train example 2: 10 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 0 0 0 0
. . . . .
2 2 2 2 2
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,1) | DIR_T | 0 | (0,1)
(0,2) | DIR_T | 0 | (0,2)
(0,3) | DIR_T | 0 | (0,3)
(0,4) | DIR_T | 0 | (0,4)
(2,0) | DIR_B | 2 | (0,0)
(2,1) | DIR_B | 2 | (0,1)
(2,2) | DIR_B | 2 | (0,2)
(2,3) | DIR_B | 2 | (0,3)
(2,4) | DIR_B | 2 | (0,4)
```

Train example 3: 4 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. 0 . 0 .
. . . . .
. 2 . 2 .
```
```
c0 | c1 | c2 | c3
(0,1) | DIR_T | 0 | (0,1)
(0,3) | DIR_T | 0 | (0,3)
(2,1) | DIR_B | 2 | (0,1)
(2,3) | DIR_B | 2 | (0,3)
```

Train example 4: 18 rows
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 0 0 0 0 0 0 0 0
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
4 4 4 4 4 4 4 4 4
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,1) | DIR_T | 0 | (0,1)
(0,2) | DIR_T | 0 | (0,2)
(0,3) | DIR_T | 0 | (0,3)
(0,4) | DIR_T | 0 | (0,4)
(0,5) | DIR_T | 0 | (0,5)
(0,6) | DIR_T | 0 | (0,6)
(0,7) | DIR_T | 0 | (0,7)
(0,8) | DIR_T | 0 | (0,8)
(4,0) | DIR_B | 4 | (0,0)
(4,1) | DIR_B | 4 | (0,1)
(4,2) | DIR_B | 4 | (0,2)
(4,3) | DIR_B | 4 | (0,3)
(4,4) | DIR_B | 4 | (0,4)
(4,5) | DIR_B | 4 | (0,5)
(4,6) | DIR_B | 4 | (0,6)
(4,7) | DIR_B | 4 | (0,7)
(4,8) | DIR_B | 4 | (0,8)
```

Train example 5: 4 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. 0 . 0 .
. . . . .
. 2 . 2 .
```
```
c0 | c1 | c2 | c3
(0,1) | DIR_T | 0 | (0,1)
(0,3) | DIR_T | 0 | (0,3)
(2,1) | DIR_B | 2 | (0,1)
(2,3) | DIR_B | 2 | (0,3)
```

Train example 6: 14 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 0 0 0 0 0 0
. . . . . . .
. . . . . . .
3 3 3 3 3 3 3
```
```
c0 | c1 | c2 | c3
(0,0) | DIR_T | 0 | (0,0)
(0,1) | DIR_T | 0 | (0,1)
(0,2) | DIR_T | 0 | (0,2)
(0,3) | DIR_T | 0 | (0,3)
(0,4) | DIR_T | 0 | (0,4)
(0,5) | DIR_T | 0 | (0,5)
(0,6) | DIR_T | 0 | (0,6)
(3,0) | DIR_B | 3 | (0,0)
(3,1) | DIR_B | 3 | (0,1)
(3,2) | DIR_B | 3 | (0,2)
(3,3) | DIR_B | 3 | (0,3)
(3,4) | DIR_B | 3 | (0,4)
(3,5) | DIR_B | 3 | (0,5)
(3,6) | DIR_B | 3 | (0,6)
```


#### &r10, assignment 4 of 4

- DET values that differ between the assignments: &r1 = {(DIR_R)}
- rows equal to those of assignment 3 at every example
### &r11 (export table 13)

- columns: c0: Box
- depth 3, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 4

#### &r11, assignment 1 of 4

- DET values that differ between the assignments: &r1 = {(DIR_T)}
- rows per train example: [2, 2, 5, 2, 9, 2, 7]; test: 11

Train example 0: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 . 1 .
. . . . .
. . . . .
```
```
c0
(0,1)
(0,3)
```

Train example 1: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 . 1 .
. . . . .
. . . . .
```
```
c0
(0,1)
(0,3)
```

Train example 2: 5 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
. . . . .
. . . . .
```
```
c0
(0,0)
(0,1)
(0,2)
(0,3)
(0,4)
```

Train example 3: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 . 1 .
. . . . .
. . . . .
```
```
c0
(0,1)
(0,3)
```

Train example 4: 9 rows
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
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
```

Train example 5: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 . 1 .
. . . . .
. . . . .
```
```
c0
(0,1)
(0,3)
```

Train example 6: 7 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1
. . . . . . .
. . . . . . .
. . . . . . .
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
```


#### &r11, assignment 2 of 4

- DET values that differ between the assignments: &r1 = {(DIR_B)}
- rows equal to those of assignment 1 at every example

#### &r11, assignment 3 of 4

- DET values that differ between the assignments: &r1 = {(DIR_L)}
- rows equal to those of assignment 1 at every example

#### &r11, assignment 4 of 4

- DET values that differ between the assignments: &r1 = {(DIR_R)}
- rows equal to those of assignment 1 at every example
### &r13 (export table 14)

- columns: c0: Dir8
- depth 4, candidate keys none
- DETs its entries are assigned: &r1; assignments: 4

#### &r13, assignment 1 of 4

- DET values that differ between the assignments: &r1 = {(DIR_T)}
- rows per train example: [2, 2, 2, 2, 2, 2, 2]; test: 2

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

Train example 5: 2 rows
```
c0
DIR_L
DIR_R
```

Train example 6: 2 rows
```
c0
DIR_L
DIR_R
```


#### &r13, assignment 2 of 4

- DET values that differ between the assignments: &r1 = {(DIR_B)}
- rows equal to those of assignment 1 at every example

#### &r13, assignment 3 of 4

- DET values that differ between the assignments: &r1 = {(DIR_L)}
- rows per train example: [2, 2, 2, 2, 2, 2, 2]; test: 2

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

Train example 5: 2 rows
```
c0
DIR_T
DIR_B
```

Train example 6: 2 rows
```
c0
DIR_T
DIR_B
```


#### &r13, assignment 4 of 4

- DET values that differ between the assignments: &r1 = {(DIR_R)}
- rows equal to those of assignment 3 at every example
```
DET SenseDomain END [&r14]
```

### &r14 (export table 15)

- columns: S: Sense
- depth 1, candidate keys none
- DETs its entries are assigned: &r14; assignments: 2

#### &r14, assignment 1 of 2

- DET values that differ between the assignments: &r14 = {(SENSE_CW)}
- rows per train example: [0, 0, 0, 0, 0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
S
SENSE_CW
```


#### &r14, assignment 2 of 2

- DET values that differ between the assignments: &r14 = {(SENSE_CC)}
- rows per train example: [0, 0, 0, 0, 0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
S
SENSE_CC
```

```
RULE &r7 :0 * [L0] opposite :0 L0 :1 * [L1] &r14 :0 * [L2] turn :0 L2 :1 L0 :2 * [L3] END [&r15]
```

### &r15 (export table 16)

- columns: c0: Sense, c1: Dir, c2: Dir, c3: Dir
- depth 3, candidate keys none
- DETs its entries are assigned: &r1, &r14; assignments: 8

#### &r15, assignment 1 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CW)}
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_T | DIR_B | DIR_R
```

Train example 1: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_T | DIR_B | DIR_R
```

Train example 2: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_T | DIR_B | DIR_R
```

Train example 3: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_T | DIR_B | DIR_R
```

Train example 4: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_T | DIR_B | DIR_R
```

Train example 5: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_T | DIR_B | DIR_R
```

Train example 6: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_T | DIR_B | DIR_R
```


#### &r15, assignment 2 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CC)}
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_T | DIR_B | DIR_L
```

Train example 1: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_T | DIR_B | DIR_L
```

Train example 2: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_T | DIR_B | DIR_L
```

Train example 3: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_T | DIR_B | DIR_L
```

Train example 4: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_T | DIR_B | DIR_L
```

Train example 5: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_T | DIR_B | DIR_L
```

Train example 6: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_T | DIR_B | DIR_L
```


#### &r15, assignment 3 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CW)}
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_B | DIR_T | DIR_L
```

Train example 1: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_B | DIR_T | DIR_L
```

Train example 2: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_B | DIR_T | DIR_L
```

Train example 3: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_B | DIR_T | DIR_L
```

Train example 4: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_B | DIR_T | DIR_L
```

Train example 5: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_B | DIR_T | DIR_L
```

Train example 6: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_B | DIR_T | DIR_L
```


#### &r15, assignment 4 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CC)}
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_B | DIR_T | DIR_R
```

Train example 1: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_B | DIR_T | DIR_R
```

Train example 2: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_B | DIR_T | DIR_R
```

Train example 3: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_B | DIR_T | DIR_R
```

Train example 4: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_B | DIR_T | DIR_R
```

Train example 5: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_B | DIR_T | DIR_R
```

Train example 6: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_B | DIR_T | DIR_R
```


#### &r15, assignment 5 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CW)}
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_L | DIR_R | DIR_T
```

Train example 1: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_L | DIR_R | DIR_T
```

Train example 2: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_L | DIR_R | DIR_T
```

Train example 3: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_L | DIR_R | DIR_T
```

Train example 4: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_L | DIR_R | DIR_T
```

Train example 5: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_L | DIR_R | DIR_T
```

Train example 6: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_L | DIR_R | DIR_T
```


#### &r15, assignment 6 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CC)}
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_L | DIR_R | DIR_B
```

Train example 1: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_L | DIR_R | DIR_B
```

Train example 2: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_L | DIR_R | DIR_B
```

Train example 3: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_L | DIR_R | DIR_B
```

Train example 4: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_L | DIR_R | DIR_B
```

Train example 5: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_L | DIR_R | DIR_B
```

Train example 6: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_L | DIR_R | DIR_B
```


#### &r15, assignment 7 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CW)}
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_R | DIR_L | DIR_B
```

Train example 1: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_R | DIR_L | DIR_B
```

Train example 2: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_R | DIR_L | DIR_B
```

Train example 3: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_R | DIR_L | DIR_B
```

Train example 4: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_R | DIR_L | DIR_B
```

Train example 5: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_R | DIR_L | DIR_B
```

Train example 6: 1 row
```
c0 | c1 | c2 | c3
SENSE_CW | DIR_R | DIR_L | DIR_B
```


#### &r15, assignment 8 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CC)}
- rows per train example: [1, 1, 1, 1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_R | DIR_L | DIR_T
```

Train example 1: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_R | DIR_L | DIR_T
```

Train example 2: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_R | DIR_L | DIR_T
```

Train example 3: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_R | DIR_L | DIR_T
```

Train example 4: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_R | DIR_L | DIR_T
```

Train example 5: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_R | DIR_L | DIR_T
```

Train example 6: 1 row
```
c0 | c1 | c2 | c3
SENSE_CC | DIR_R | DIR_L | DIR_T
```

```
RULE &r15 :1 * [L0] :3 * [L1] opposite :0 L1 :1 * [L2] input :0 * [L3] neighbor :0 L3 :1 L0 :2 * [L4] neighbor :0 L4 :1 L1 :2 * [L5] neighbor :0 L4 :1 L2 :2 * [L6] END [&r16]
```

### &r16 (export table 17)

- columns: c0: Box, c1: Dir, c2: Box, c3: Box, c4: Box, c5: Dir, c6: Dir
- depth 4, candidate keys none
- DETs its entries are assigned: &r1, &r14; assignments: 8

#### &r16, assignment 1 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CW)}
- rows per train example: [15, 15, 15, 15, 45, 15, 28]; test: 72

Train example 0: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_L | (1,0) | [1 1 -1 5] | (1,1) | DIR_B | DIR_R
(0,1) | DIR_L | (1,1) | (1,0) | (1,2) | DIR_B | DIR_R
(0,2) | DIR_L | (1,2) | (1,1) | (1,3) | DIR_B | DIR_R
(0,3) | DIR_L | (1,3) | (1,2) | (1,4) | DIR_B | DIR_R
(0,4) | DIR_L | (1,4) | (1,3) | [1 1 5 -1] | DIR_B | DIR_R
(1,0) | DIR_L | (2,0) | [2 0 -1 5] | (2,1) | DIR_B | DIR_R
(1,1) | DIR_L | (2,1) | (2,0) | (2,2) | DIR_B | DIR_R
(1,2) | DIR_L | (2,2) | (2,1) | (2,3) | DIR_B | DIR_R
(1,3) | DIR_L | (2,3) | (2,2) | (2,4) | DIR_B | DIR_R
(1,4) | DIR_L | (2,4) | (2,3) | [2 0 5 -1] | DIR_B | DIR_R
(2,0) | DIR_L | [3 -1 0 4] | [3 -1 -1 5] | [3 -1 1 3] | DIR_B | DIR_R
(2,1) | DIR_L | [3 -1 1 3] | [3 -1 0 4] | [3 -1 2 2] | DIR_B | DIR_R
(2,2) | DIR_L | [3 -1 2 2] | [3 -1 1 3] | [3 -1 3 1] | DIR_B | DIR_R
(2,3) | DIR_L | [3 -1 3 1] | [3 -1 2 2] | [3 -1 4 0] | DIR_B | DIR_R
(2,4) | DIR_L | [3 -1 4 0] | [3 -1 3 1] | [3 -1 5 -1] | DIR_B | DIR_R
```

Train example 1: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_L | (1,0) | [1 1 -1 5] | (1,1) | DIR_B | DIR_R
(0,1) | DIR_L | (1,1) | (1,0) | (1,2) | DIR_B | DIR_R
(0,2) | DIR_L | (1,2) | (1,1) | (1,3) | DIR_B | DIR_R
(0,3) | DIR_L | (1,3) | (1,2) | (1,4) | DIR_B | DIR_R
(0,4) | DIR_L | (1,4) | (1,3) | [1 1 5 -1] | DIR_B | DIR_R
(1,0) | DIR_L | (2,0) | [2 0 -1 5] | (2,1) | DIR_B | DIR_R
(1,1) | DIR_L | (2,1) | (2,0) | (2,2) | DIR_B | DIR_R
(1,2) | DIR_L | (2,2) | (2,1) | (2,3) | DIR_B | DIR_R
(1,3) | DIR_L | (2,3) | (2,2) | (2,4) | DIR_B | DIR_R
(1,4) | DIR_L | (2,4) | (2,3) | [2 0 5 -1] | DIR_B | DIR_R
(2,0) | DIR_L | [3 -1 0 4] | [3 -1 -1 5] | [3 -1 1 3] | DIR_B | DIR_R
(2,1) | DIR_L | [3 -1 1 3] | [3 -1 0 4] | [3 -1 2 2] | DIR_B | DIR_R
(2,2) | DIR_L | [3 -1 2 2] | [3 -1 1 3] | [3 -1 3 1] | DIR_B | DIR_R
(2,3) | DIR_L | [3 -1 3 1] | [3 -1 2 2] | [3 -1 4 0] | DIR_B | DIR_R
(2,4) | DIR_L | [3 -1 4 0] | [3 -1 3 1] | [3 -1 5 -1] | DIR_B | DIR_R
```

Train example 2: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_L | (1,0) | [1 1 -1 5] | (1,1) | DIR_B | DIR_R
(0,1) | DIR_L | (1,1) | (1,0) | (1,2) | DIR_B | DIR_R
(0,2) | DIR_L | (1,2) | (1,1) | (1,3) | DIR_B | DIR_R
(0,3) | DIR_L | (1,3) | (1,2) | (1,4) | DIR_B | DIR_R
(0,4) | DIR_L | (1,4) | (1,3) | [1 1 5 -1] | DIR_B | DIR_R
(1,0) | DIR_L | (2,0) | [2 0 -1 5] | (2,1) | DIR_B | DIR_R
(1,1) | DIR_L | (2,1) | (2,0) | (2,2) | DIR_B | DIR_R
(1,2) | DIR_L | (2,2) | (2,1) | (2,3) | DIR_B | DIR_R
(1,3) | DIR_L | (2,3) | (2,2) | (2,4) | DIR_B | DIR_R
(1,4) | DIR_L | (2,4) | (2,3) | [2 0 5 -1] | DIR_B | DIR_R
(2,0) | DIR_L | [3 -1 0 4] | [3 -1 -1 5] | [3 -1 1 3] | DIR_B | DIR_R
(2,1) | DIR_L | [3 -1 1 3] | [3 -1 0 4] | [3 -1 2 2] | DIR_B | DIR_R
(2,2) | DIR_L | [3 -1 2 2] | [3 -1 1 3] | [3 -1 3 1] | DIR_B | DIR_R
(2,3) | DIR_L | [3 -1 3 1] | [3 -1 2 2] | [3 -1 4 0] | DIR_B | DIR_R
(2,4) | DIR_L | [3 -1 4 0] | [3 -1 3 1] | [3 -1 5 -1] | DIR_B | DIR_R
```

Train example 3: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_L | (1,0) | [1 1 -1 5] | (1,1) | DIR_B | DIR_R
(0,1) | DIR_L | (1,1) | (1,0) | (1,2) | DIR_B | DIR_R
(0,2) | DIR_L | (1,2) | (1,1) | (1,3) | DIR_B | DIR_R
(0,3) | DIR_L | (1,3) | (1,2) | (1,4) | DIR_B | DIR_R
(0,4) | DIR_L | (1,4) | (1,3) | [1 1 5 -1] | DIR_B | DIR_R
(1,0) | DIR_L | (2,0) | [2 0 -1 5] | (2,1) | DIR_B | DIR_R
(1,1) | DIR_L | (2,1) | (2,0) | (2,2) | DIR_B | DIR_R
(1,2) | DIR_L | (2,2) | (2,1) | (2,3) | DIR_B | DIR_R
(1,3) | DIR_L | (2,3) | (2,2) | (2,4) | DIR_B | DIR_R
(1,4) | DIR_L | (2,4) | (2,3) | [2 0 5 -1] | DIR_B | DIR_R
(2,0) | DIR_L | [3 -1 0 4] | [3 -1 -1 5] | [3 -1 1 3] | DIR_B | DIR_R
(2,1) | DIR_L | [3 -1 1 3] | [3 -1 0 4] | [3 -1 2 2] | DIR_B | DIR_R
(2,2) | DIR_L | [3 -1 2 2] | [3 -1 1 3] | [3 -1 3 1] | DIR_B | DIR_R
(2,3) | DIR_L | [3 -1 3 1] | [3 -1 2 2] | [3 -1 4 0] | DIR_B | DIR_R
(2,4) | DIR_L | [3 -1 4 0] | [3 -1 3 1] | [3 -1 5 -1] | DIR_B | DIR_R
```

Train example 4: 45 rows, the first 30 shown
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_L | (1,0) | [1 3 -1 9] | (1,1) | DIR_B | DIR_R
(0,1) | DIR_L | (1,1) | (1,0) | (1,2) | DIR_B | DIR_R
(0,2) | DIR_L | (1,2) | (1,1) | (1,3) | DIR_B | DIR_R
(0,3) | DIR_L | (1,3) | (1,2) | (1,4) | DIR_B | DIR_R
(0,4) | DIR_L | (1,4) | (1,3) | (1,5) | DIR_B | DIR_R
(0,5) | DIR_L | (1,5) | (1,4) | (1,6) | DIR_B | DIR_R
(0,6) | DIR_L | (1,6) | (1,5) | (1,7) | DIR_B | DIR_R
(0,7) | DIR_L | (1,7) | (1,6) | (1,8) | DIR_B | DIR_R
(0,8) | DIR_L | (1,8) | (1,7) | [1 3 9 -1] | DIR_B | DIR_R
(1,0) | DIR_L | (2,0) | [2 2 -1 9] | (2,1) | DIR_B | DIR_R
(1,1) | DIR_L | (2,1) | (2,0) | (2,2) | DIR_B | DIR_R
(1,2) | DIR_L | (2,2) | (2,1) | (2,3) | DIR_B | DIR_R
(1,3) | DIR_L | (2,3) | (2,2) | (2,4) | DIR_B | DIR_R
(1,4) | DIR_L | (2,4) | (2,3) | (2,5) | DIR_B | DIR_R
(1,5) | DIR_L | (2,5) | (2,4) | (2,6) | DIR_B | DIR_R
(1,6) | DIR_L | (2,6) | (2,5) | (2,7) | DIR_B | DIR_R
(1,7) | DIR_L | (2,7) | (2,6) | (2,8) | DIR_B | DIR_R
(1,8) | DIR_L | (2,8) | (2,7) | [2 2 9 -1] | DIR_B | DIR_R
(2,0) | DIR_L | (3,0) | [3 1 -1 9] | (3,1) | DIR_B | DIR_R
(2,1) | DIR_L | (3,1) | (3,0) | (3,2) | DIR_B | DIR_R
(2,2) | DIR_L | (3,2) | (3,1) | (3,3) | DIR_B | DIR_R
(2,3) | DIR_L | (3,3) | (3,2) | (3,4) | DIR_B | DIR_R
(2,4) | DIR_L | (3,4) | (3,3) | (3,5) | DIR_B | DIR_R
(2,5) | DIR_L | (3,5) | (3,4) | (3,6) | DIR_B | DIR_R
(2,6) | DIR_L | (3,6) | (3,5) | (3,7) | DIR_B | DIR_R
(2,7) | DIR_L | (3,7) | (3,6) | (3,8) | DIR_B | DIR_R
(2,8) | DIR_L | (3,8) | (3,7) | [3 1 9 -1] | DIR_B | DIR_R
(3,0) | DIR_L | (4,0) | [4 0 -1 9] | (4,1) | DIR_B | DIR_R
(3,1) | DIR_L | (4,1) | (4,0) | (4,2) | DIR_B | DIR_R
(3,2) | DIR_L | (4,2) | (4,1) | (4,3) | DIR_B | DIR_R
```

Train example 5: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_L | (1,0) | [1 1 -1 5] | (1,1) | DIR_B | DIR_R
(0,1) | DIR_L | (1,1) | (1,0) | (1,2) | DIR_B | DIR_R
(0,2) | DIR_L | (1,2) | (1,1) | (1,3) | DIR_B | DIR_R
(0,3) | DIR_L | (1,3) | (1,2) | (1,4) | DIR_B | DIR_R
(0,4) | DIR_L | (1,4) | (1,3) | [1 1 5 -1] | DIR_B | DIR_R
(1,0) | DIR_L | (2,0) | [2 0 -1 5] | (2,1) | DIR_B | DIR_R
(1,1) | DIR_L | (2,1) | (2,0) | (2,2) | DIR_B | DIR_R
(1,2) | DIR_L | (2,2) | (2,1) | (2,3) | DIR_B | DIR_R
(1,3) | DIR_L | (2,3) | (2,2) | (2,4) | DIR_B | DIR_R
(1,4) | DIR_L | (2,4) | (2,3) | [2 0 5 -1] | DIR_B | DIR_R
(2,0) | DIR_L | [3 -1 0 4] | [3 -1 -1 5] | [3 -1 1 3] | DIR_B | DIR_R
(2,1) | DIR_L | [3 -1 1 3] | [3 -1 0 4] | [3 -1 2 2] | DIR_B | DIR_R
(2,2) | DIR_L | [3 -1 2 2] | [3 -1 1 3] | [3 -1 3 1] | DIR_B | DIR_R
(2,3) | DIR_L | [3 -1 3 1] | [3 -1 2 2] | [3 -1 4 0] | DIR_B | DIR_R
(2,4) | DIR_L | [3 -1 4 0] | [3 -1 3 1] | [3 -1 5 -1] | DIR_B | DIR_R
```

Train example 6: 28 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_L | (1,0) | [1 2 -1 7] | (1,1) | DIR_B | DIR_R
(0,1) | DIR_L | (1,1) | (1,0) | (1,2) | DIR_B | DIR_R
(0,2) | DIR_L | (1,2) | (1,1) | (1,3) | DIR_B | DIR_R
(0,3) | DIR_L | (1,3) | (1,2) | (1,4) | DIR_B | DIR_R
(0,4) | DIR_L | (1,4) | (1,3) | (1,5) | DIR_B | DIR_R
(0,5) | DIR_L | (1,5) | (1,4) | (1,6) | DIR_B | DIR_R
(0,6) | DIR_L | (1,6) | (1,5) | [1 2 7 -1] | DIR_B | DIR_R
(1,0) | DIR_L | (2,0) | [2 1 -1 7] | (2,1) | DIR_B | DIR_R
(1,1) | DIR_L | (2,1) | (2,0) | (2,2) | DIR_B | DIR_R
(1,2) | DIR_L | (2,2) | (2,1) | (2,3) | DIR_B | DIR_R
(1,3) | DIR_L | (2,3) | (2,2) | (2,4) | DIR_B | DIR_R
(1,4) | DIR_L | (2,4) | (2,3) | (2,5) | DIR_B | DIR_R
(1,5) | DIR_L | (2,5) | (2,4) | (2,6) | DIR_B | DIR_R
(1,6) | DIR_L | (2,6) | (2,5) | [2 1 7 -1] | DIR_B | DIR_R
(2,0) | DIR_L | (3,0) | [3 0 -1 7] | (3,1) | DIR_B | DIR_R
(2,1) | DIR_L | (3,1) | (3,0) | (3,2) | DIR_B | DIR_R
(2,2) | DIR_L | (3,2) | (3,1) | (3,3) | DIR_B | DIR_R
(2,3) | DIR_L | (3,3) | (3,2) | (3,4) | DIR_B | DIR_R
(2,4) | DIR_L | (3,4) | (3,3) | (3,5) | DIR_B | DIR_R
(2,5) | DIR_L | (3,5) | (3,4) | (3,6) | DIR_B | DIR_R
(2,6) | DIR_L | (3,6) | (3,5) | [3 0 7 -1] | DIR_B | DIR_R
(3,0) | DIR_L | [4 -1 0 6] | [4 -1 -1 7] | [4 -1 1 5] | DIR_B | DIR_R
(3,1) | DIR_L | [4 -1 1 5] | [4 -1 0 6] | [4 -1 2 4] | DIR_B | DIR_R
(3,2) | DIR_L | [4 -1 2 4] | [4 -1 1 5] | [4 -1 3 3] | DIR_B | DIR_R
(3,3) | DIR_L | [4 -1 3 3] | [4 -1 2 4] | [4 -1 4 2] | DIR_B | DIR_R
(3,4) | DIR_L | [4 -1 4 2] | [4 -1 3 3] | [4 -1 5 1] | DIR_B | DIR_R
(3,5) | DIR_L | [4 -1 5 1] | [4 -1 4 2] | [4 -1 6 0] | DIR_B | DIR_R
(3,6) | DIR_L | [4 -1 6 0] | [4 -1 5 1] | [4 -1 7 -1] | DIR_B | DIR_R
```


#### &r16, assignment 2 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CC)}
- rows per train example: [15, 15, 15, 15, 45, 15, 28]; test: 72

Train example 0: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_R | (1,0) | (1,1) | [1 1 -1 5] | DIR_B | DIR_L
(0,1) | DIR_R | (1,1) | (1,2) | (1,0) | DIR_B | DIR_L
(0,2) | DIR_R | (1,2) | (1,3) | (1,1) | DIR_B | DIR_L
(0,3) | DIR_R | (1,3) | (1,4) | (1,2) | DIR_B | DIR_L
(0,4) | DIR_R | (1,4) | [1 1 5 -1] | (1,3) | DIR_B | DIR_L
(1,0) | DIR_R | (2,0) | (2,1) | [2 0 -1 5] | DIR_B | DIR_L
(1,1) | DIR_R | (2,1) | (2,2) | (2,0) | DIR_B | DIR_L
(1,2) | DIR_R | (2,2) | (2,3) | (2,1) | DIR_B | DIR_L
(1,3) | DIR_R | (2,3) | (2,4) | (2,2) | DIR_B | DIR_L
(1,4) | DIR_R | (2,4) | [2 0 5 -1] | (2,3) | DIR_B | DIR_L
(2,0) | DIR_R | [3 -1 0 4] | [3 -1 1 3] | [3 -1 -1 5] | DIR_B | DIR_L
(2,1) | DIR_R | [3 -1 1 3] | [3 -1 2 2] | [3 -1 0 4] | DIR_B | DIR_L
(2,2) | DIR_R | [3 -1 2 2] | [3 -1 3 1] | [3 -1 1 3] | DIR_B | DIR_L
(2,3) | DIR_R | [3 -1 3 1] | [3 -1 4 0] | [3 -1 2 2] | DIR_B | DIR_L
(2,4) | DIR_R | [3 -1 4 0] | [3 -1 5 -1] | [3 -1 3 1] | DIR_B | DIR_L
```

Train example 1: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_R | (1,0) | (1,1) | [1 1 -1 5] | DIR_B | DIR_L
(0,1) | DIR_R | (1,1) | (1,2) | (1,0) | DIR_B | DIR_L
(0,2) | DIR_R | (1,2) | (1,3) | (1,1) | DIR_B | DIR_L
(0,3) | DIR_R | (1,3) | (1,4) | (1,2) | DIR_B | DIR_L
(0,4) | DIR_R | (1,4) | [1 1 5 -1] | (1,3) | DIR_B | DIR_L
(1,0) | DIR_R | (2,0) | (2,1) | [2 0 -1 5] | DIR_B | DIR_L
(1,1) | DIR_R | (2,1) | (2,2) | (2,0) | DIR_B | DIR_L
(1,2) | DIR_R | (2,2) | (2,3) | (2,1) | DIR_B | DIR_L
(1,3) | DIR_R | (2,3) | (2,4) | (2,2) | DIR_B | DIR_L
(1,4) | DIR_R | (2,4) | [2 0 5 -1] | (2,3) | DIR_B | DIR_L
(2,0) | DIR_R | [3 -1 0 4] | [3 -1 1 3] | [3 -1 -1 5] | DIR_B | DIR_L
(2,1) | DIR_R | [3 -1 1 3] | [3 -1 2 2] | [3 -1 0 4] | DIR_B | DIR_L
(2,2) | DIR_R | [3 -1 2 2] | [3 -1 3 1] | [3 -1 1 3] | DIR_B | DIR_L
(2,3) | DIR_R | [3 -1 3 1] | [3 -1 4 0] | [3 -1 2 2] | DIR_B | DIR_L
(2,4) | DIR_R | [3 -1 4 0] | [3 -1 5 -1] | [3 -1 3 1] | DIR_B | DIR_L
```

Train example 2: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_R | (1,0) | (1,1) | [1 1 -1 5] | DIR_B | DIR_L
(0,1) | DIR_R | (1,1) | (1,2) | (1,0) | DIR_B | DIR_L
(0,2) | DIR_R | (1,2) | (1,3) | (1,1) | DIR_B | DIR_L
(0,3) | DIR_R | (1,3) | (1,4) | (1,2) | DIR_B | DIR_L
(0,4) | DIR_R | (1,4) | [1 1 5 -1] | (1,3) | DIR_B | DIR_L
(1,0) | DIR_R | (2,0) | (2,1) | [2 0 -1 5] | DIR_B | DIR_L
(1,1) | DIR_R | (2,1) | (2,2) | (2,0) | DIR_B | DIR_L
(1,2) | DIR_R | (2,2) | (2,3) | (2,1) | DIR_B | DIR_L
(1,3) | DIR_R | (2,3) | (2,4) | (2,2) | DIR_B | DIR_L
(1,4) | DIR_R | (2,4) | [2 0 5 -1] | (2,3) | DIR_B | DIR_L
(2,0) | DIR_R | [3 -1 0 4] | [3 -1 1 3] | [3 -1 -1 5] | DIR_B | DIR_L
(2,1) | DIR_R | [3 -1 1 3] | [3 -1 2 2] | [3 -1 0 4] | DIR_B | DIR_L
(2,2) | DIR_R | [3 -1 2 2] | [3 -1 3 1] | [3 -1 1 3] | DIR_B | DIR_L
(2,3) | DIR_R | [3 -1 3 1] | [3 -1 4 0] | [3 -1 2 2] | DIR_B | DIR_L
(2,4) | DIR_R | [3 -1 4 0] | [3 -1 5 -1] | [3 -1 3 1] | DIR_B | DIR_L
```

Train example 3: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_R | (1,0) | (1,1) | [1 1 -1 5] | DIR_B | DIR_L
(0,1) | DIR_R | (1,1) | (1,2) | (1,0) | DIR_B | DIR_L
(0,2) | DIR_R | (1,2) | (1,3) | (1,1) | DIR_B | DIR_L
(0,3) | DIR_R | (1,3) | (1,4) | (1,2) | DIR_B | DIR_L
(0,4) | DIR_R | (1,4) | [1 1 5 -1] | (1,3) | DIR_B | DIR_L
(1,0) | DIR_R | (2,0) | (2,1) | [2 0 -1 5] | DIR_B | DIR_L
(1,1) | DIR_R | (2,1) | (2,2) | (2,0) | DIR_B | DIR_L
(1,2) | DIR_R | (2,2) | (2,3) | (2,1) | DIR_B | DIR_L
(1,3) | DIR_R | (2,3) | (2,4) | (2,2) | DIR_B | DIR_L
(1,4) | DIR_R | (2,4) | [2 0 5 -1] | (2,3) | DIR_B | DIR_L
(2,0) | DIR_R | [3 -1 0 4] | [3 -1 1 3] | [3 -1 -1 5] | DIR_B | DIR_L
(2,1) | DIR_R | [3 -1 1 3] | [3 -1 2 2] | [3 -1 0 4] | DIR_B | DIR_L
(2,2) | DIR_R | [3 -1 2 2] | [3 -1 3 1] | [3 -1 1 3] | DIR_B | DIR_L
(2,3) | DIR_R | [3 -1 3 1] | [3 -1 4 0] | [3 -1 2 2] | DIR_B | DIR_L
(2,4) | DIR_R | [3 -1 4 0] | [3 -1 5 -1] | [3 -1 3 1] | DIR_B | DIR_L
```

Train example 4: 45 rows, the first 30 shown
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_R | (1,0) | (1,1) | [1 3 -1 9] | DIR_B | DIR_L
(0,1) | DIR_R | (1,1) | (1,2) | (1,0) | DIR_B | DIR_L
(0,2) | DIR_R | (1,2) | (1,3) | (1,1) | DIR_B | DIR_L
(0,3) | DIR_R | (1,3) | (1,4) | (1,2) | DIR_B | DIR_L
(0,4) | DIR_R | (1,4) | (1,5) | (1,3) | DIR_B | DIR_L
(0,5) | DIR_R | (1,5) | (1,6) | (1,4) | DIR_B | DIR_L
(0,6) | DIR_R | (1,6) | (1,7) | (1,5) | DIR_B | DIR_L
(0,7) | DIR_R | (1,7) | (1,8) | (1,6) | DIR_B | DIR_L
(0,8) | DIR_R | (1,8) | [1 3 9 -1] | (1,7) | DIR_B | DIR_L
(1,0) | DIR_R | (2,0) | (2,1) | [2 2 -1 9] | DIR_B | DIR_L
(1,1) | DIR_R | (2,1) | (2,2) | (2,0) | DIR_B | DIR_L
(1,2) | DIR_R | (2,2) | (2,3) | (2,1) | DIR_B | DIR_L
(1,3) | DIR_R | (2,3) | (2,4) | (2,2) | DIR_B | DIR_L
(1,4) | DIR_R | (2,4) | (2,5) | (2,3) | DIR_B | DIR_L
(1,5) | DIR_R | (2,5) | (2,6) | (2,4) | DIR_B | DIR_L
(1,6) | DIR_R | (2,6) | (2,7) | (2,5) | DIR_B | DIR_L
(1,7) | DIR_R | (2,7) | (2,8) | (2,6) | DIR_B | DIR_L
(1,8) | DIR_R | (2,8) | [2 2 9 -1] | (2,7) | DIR_B | DIR_L
(2,0) | DIR_R | (3,0) | (3,1) | [3 1 -1 9] | DIR_B | DIR_L
(2,1) | DIR_R | (3,1) | (3,2) | (3,0) | DIR_B | DIR_L
(2,2) | DIR_R | (3,2) | (3,3) | (3,1) | DIR_B | DIR_L
(2,3) | DIR_R | (3,3) | (3,4) | (3,2) | DIR_B | DIR_L
(2,4) | DIR_R | (3,4) | (3,5) | (3,3) | DIR_B | DIR_L
(2,5) | DIR_R | (3,5) | (3,6) | (3,4) | DIR_B | DIR_L
(2,6) | DIR_R | (3,6) | (3,7) | (3,5) | DIR_B | DIR_L
(2,7) | DIR_R | (3,7) | (3,8) | (3,6) | DIR_B | DIR_L
(2,8) | DIR_R | (3,8) | [3 1 9 -1] | (3,7) | DIR_B | DIR_L
(3,0) | DIR_R | (4,0) | (4,1) | [4 0 -1 9] | DIR_B | DIR_L
(3,1) | DIR_R | (4,1) | (4,2) | (4,0) | DIR_B | DIR_L
(3,2) | DIR_R | (4,2) | (4,3) | (4,1) | DIR_B | DIR_L
```

Train example 5: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_R | (1,0) | (1,1) | [1 1 -1 5] | DIR_B | DIR_L
(0,1) | DIR_R | (1,1) | (1,2) | (1,0) | DIR_B | DIR_L
(0,2) | DIR_R | (1,2) | (1,3) | (1,1) | DIR_B | DIR_L
(0,3) | DIR_R | (1,3) | (1,4) | (1,2) | DIR_B | DIR_L
(0,4) | DIR_R | (1,4) | [1 1 5 -1] | (1,3) | DIR_B | DIR_L
(1,0) | DIR_R | (2,0) | (2,1) | [2 0 -1 5] | DIR_B | DIR_L
(1,1) | DIR_R | (2,1) | (2,2) | (2,0) | DIR_B | DIR_L
(1,2) | DIR_R | (2,2) | (2,3) | (2,1) | DIR_B | DIR_L
(1,3) | DIR_R | (2,3) | (2,4) | (2,2) | DIR_B | DIR_L
(1,4) | DIR_R | (2,4) | [2 0 5 -1] | (2,3) | DIR_B | DIR_L
(2,0) | DIR_R | [3 -1 0 4] | [3 -1 1 3] | [3 -1 -1 5] | DIR_B | DIR_L
(2,1) | DIR_R | [3 -1 1 3] | [3 -1 2 2] | [3 -1 0 4] | DIR_B | DIR_L
(2,2) | DIR_R | [3 -1 2 2] | [3 -1 3 1] | [3 -1 1 3] | DIR_B | DIR_L
(2,3) | DIR_R | [3 -1 3 1] | [3 -1 4 0] | [3 -1 2 2] | DIR_B | DIR_L
(2,4) | DIR_R | [3 -1 4 0] | [3 -1 5 -1] | [3 -1 3 1] | DIR_B | DIR_L
```

Train example 6: 28 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_R | (1,0) | (1,1) | [1 2 -1 7] | DIR_B | DIR_L
(0,1) | DIR_R | (1,1) | (1,2) | (1,0) | DIR_B | DIR_L
(0,2) | DIR_R | (1,2) | (1,3) | (1,1) | DIR_B | DIR_L
(0,3) | DIR_R | (1,3) | (1,4) | (1,2) | DIR_B | DIR_L
(0,4) | DIR_R | (1,4) | (1,5) | (1,3) | DIR_B | DIR_L
(0,5) | DIR_R | (1,5) | (1,6) | (1,4) | DIR_B | DIR_L
(0,6) | DIR_R | (1,6) | [1 2 7 -1] | (1,5) | DIR_B | DIR_L
(1,0) | DIR_R | (2,0) | (2,1) | [2 1 -1 7] | DIR_B | DIR_L
(1,1) | DIR_R | (2,1) | (2,2) | (2,0) | DIR_B | DIR_L
(1,2) | DIR_R | (2,2) | (2,3) | (2,1) | DIR_B | DIR_L
(1,3) | DIR_R | (2,3) | (2,4) | (2,2) | DIR_B | DIR_L
(1,4) | DIR_R | (2,4) | (2,5) | (2,3) | DIR_B | DIR_L
(1,5) | DIR_R | (2,5) | (2,6) | (2,4) | DIR_B | DIR_L
(1,6) | DIR_R | (2,6) | [2 1 7 -1] | (2,5) | DIR_B | DIR_L
(2,0) | DIR_R | (3,0) | (3,1) | [3 0 -1 7] | DIR_B | DIR_L
(2,1) | DIR_R | (3,1) | (3,2) | (3,0) | DIR_B | DIR_L
(2,2) | DIR_R | (3,2) | (3,3) | (3,1) | DIR_B | DIR_L
(2,3) | DIR_R | (3,3) | (3,4) | (3,2) | DIR_B | DIR_L
(2,4) | DIR_R | (3,4) | (3,5) | (3,3) | DIR_B | DIR_L
(2,5) | DIR_R | (3,5) | (3,6) | (3,4) | DIR_B | DIR_L
(2,6) | DIR_R | (3,6) | [3 0 7 -1] | (3,5) | DIR_B | DIR_L
(3,0) | DIR_R | [4 -1 0 6] | [4 -1 1 5] | [4 -1 -1 7] | DIR_B | DIR_L
(3,1) | DIR_R | [4 -1 1 5] | [4 -1 2 4] | [4 -1 0 6] | DIR_B | DIR_L
(3,2) | DIR_R | [4 -1 2 4] | [4 -1 3 3] | [4 -1 1 5] | DIR_B | DIR_L
(3,3) | DIR_R | [4 -1 3 3] | [4 -1 4 2] | [4 -1 2 4] | DIR_B | DIR_L
(3,4) | DIR_R | [4 -1 4 2] | [4 -1 5 1] | [4 -1 3 3] | DIR_B | DIR_L
(3,5) | DIR_R | [4 -1 5 1] | [4 -1 6 0] | [4 -1 4 2] | DIR_B | DIR_L
(3,6) | DIR_R | [4 -1 6 0] | [4 -1 7 -1] | [4 -1 5 1] | DIR_B | DIR_L
```


#### &r16, assignment 3 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CW)}
- rows per train example: [15, 15, 15, 15, 45, 15, 28]; test: 72

Train example 0: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_R | [-1 3 0 4] | [-1 3 1 3] | [-1 3 -1 5] | DIR_T | DIR_L
(0,1) | DIR_R | [-1 3 1 3] | [-1 3 2 2] | [-1 3 0 4] | DIR_T | DIR_L
(0,2) | DIR_R | [-1 3 2 2] | [-1 3 3 1] | [-1 3 1 3] | DIR_T | DIR_L
(0,3) | DIR_R | [-1 3 3 1] | [-1 3 4 0] | [-1 3 2 2] | DIR_T | DIR_L
(0,4) | DIR_R | [-1 3 4 0] | [-1 3 5 -1] | [-1 3 3 1] | DIR_T | DIR_L
(1,0) | DIR_R | (0,0) | (0,1) | [0 2 -1 5] | DIR_T | DIR_L
(1,1) | DIR_R | (0,1) | (0,2) | (0,0) | DIR_T | DIR_L
(1,2) | DIR_R | (0,2) | (0,3) | (0,1) | DIR_T | DIR_L
(1,3) | DIR_R | (0,3) | (0,4) | (0,2) | DIR_T | DIR_L
(1,4) | DIR_R | (0,4) | [0 2 5 -1] | (0,3) | DIR_T | DIR_L
(2,0) | DIR_R | (1,0) | (1,1) | [1 1 -1 5] | DIR_T | DIR_L
(2,1) | DIR_R | (1,1) | (1,2) | (1,0) | DIR_T | DIR_L
(2,2) | DIR_R | (1,2) | (1,3) | (1,1) | DIR_T | DIR_L
(2,3) | DIR_R | (1,3) | (1,4) | (1,2) | DIR_T | DIR_L
(2,4) | DIR_R | (1,4) | [1 1 5 -1] | (1,3) | DIR_T | DIR_L
```

Train example 1: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_R | [-1 3 0 4] | [-1 3 1 3] | [-1 3 -1 5] | DIR_T | DIR_L
(0,1) | DIR_R | [-1 3 1 3] | [-1 3 2 2] | [-1 3 0 4] | DIR_T | DIR_L
(0,2) | DIR_R | [-1 3 2 2] | [-1 3 3 1] | [-1 3 1 3] | DIR_T | DIR_L
(0,3) | DIR_R | [-1 3 3 1] | [-1 3 4 0] | [-1 3 2 2] | DIR_T | DIR_L
(0,4) | DIR_R | [-1 3 4 0] | [-1 3 5 -1] | [-1 3 3 1] | DIR_T | DIR_L
(1,0) | DIR_R | (0,0) | (0,1) | [0 2 -1 5] | DIR_T | DIR_L
(1,1) | DIR_R | (0,1) | (0,2) | (0,0) | DIR_T | DIR_L
(1,2) | DIR_R | (0,2) | (0,3) | (0,1) | DIR_T | DIR_L
(1,3) | DIR_R | (0,3) | (0,4) | (0,2) | DIR_T | DIR_L
(1,4) | DIR_R | (0,4) | [0 2 5 -1] | (0,3) | DIR_T | DIR_L
(2,0) | DIR_R | (1,0) | (1,1) | [1 1 -1 5] | DIR_T | DIR_L
(2,1) | DIR_R | (1,1) | (1,2) | (1,0) | DIR_T | DIR_L
(2,2) | DIR_R | (1,2) | (1,3) | (1,1) | DIR_T | DIR_L
(2,3) | DIR_R | (1,3) | (1,4) | (1,2) | DIR_T | DIR_L
(2,4) | DIR_R | (1,4) | [1 1 5 -1] | (1,3) | DIR_T | DIR_L
```

Train example 2: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_R | [-1 3 0 4] | [-1 3 1 3] | [-1 3 -1 5] | DIR_T | DIR_L
(0,1) | DIR_R | [-1 3 1 3] | [-1 3 2 2] | [-1 3 0 4] | DIR_T | DIR_L
(0,2) | DIR_R | [-1 3 2 2] | [-1 3 3 1] | [-1 3 1 3] | DIR_T | DIR_L
(0,3) | DIR_R | [-1 3 3 1] | [-1 3 4 0] | [-1 3 2 2] | DIR_T | DIR_L
(0,4) | DIR_R | [-1 3 4 0] | [-1 3 5 -1] | [-1 3 3 1] | DIR_T | DIR_L
(1,0) | DIR_R | (0,0) | (0,1) | [0 2 -1 5] | DIR_T | DIR_L
(1,1) | DIR_R | (0,1) | (0,2) | (0,0) | DIR_T | DIR_L
(1,2) | DIR_R | (0,2) | (0,3) | (0,1) | DIR_T | DIR_L
(1,3) | DIR_R | (0,3) | (0,4) | (0,2) | DIR_T | DIR_L
(1,4) | DIR_R | (0,4) | [0 2 5 -1] | (0,3) | DIR_T | DIR_L
(2,0) | DIR_R | (1,0) | (1,1) | [1 1 -1 5] | DIR_T | DIR_L
(2,1) | DIR_R | (1,1) | (1,2) | (1,0) | DIR_T | DIR_L
(2,2) | DIR_R | (1,2) | (1,3) | (1,1) | DIR_T | DIR_L
(2,3) | DIR_R | (1,3) | (1,4) | (1,2) | DIR_T | DIR_L
(2,4) | DIR_R | (1,4) | [1 1 5 -1] | (1,3) | DIR_T | DIR_L
```

Train example 3: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_R | [-1 3 0 4] | [-1 3 1 3] | [-1 3 -1 5] | DIR_T | DIR_L
(0,1) | DIR_R | [-1 3 1 3] | [-1 3 2 2] | [-1 3 0 4] | DIR_T | DIR_L
(0,2) | DIR_R | [-1 3 2 2] | [-1 3 3 1] | [-1 3 1 3] | DIR_T | DIR_L
(0,3) | DIR_R | [-1 3 3 1] | [-1 3 4 0] | [-1 3 2 2] | DIR_T | DIR_L
(0,4) | DIR_R | [-1 3 4 0] | [-1 3 5 -1] | [-1 3 3 1] | DIR_T | DIR_L
(1,0) | DIR_R | (0,0) | (0,1) | [0 2 -1 5] | DIR_T | DIR_L
(1,1) | DIR_R | (0,1) | (0,2) | (0,0) | DIR_T | DIR_L
(1,2) | DIR_R | (0,2) | (0,3) | (0,1) | DIR_T | DIR_L
(1,3) | DIR_R | (0,3) | (0,4) | (0,2) | DIR_T | DIR_L
(1,4) | DIR_R | (0,4) | [0 2 5 -1] | (0,3) | DIR_T | DIR_L
(2,0) | DIR_R | (1,0) | (1,1) | [1 1 -1 5] | DIR_T | DIR_L
(2,1) | DIR_R | (1,1) | (1,2) | (1,0) | DIR_T | DIR_L
(2,2) | DIR_R | (1,2) | (1,3) | (1,1) | DIR_T | DIR_L
(2,3) | DIR_R | (1,3) | (1,4) | (1,2) | DIR_T | DIR_L
(2,4) | DIR_R | (1,4) | [1 1 5 -1] | (1,3) | DIR_T | DIR_L
```

Train example 4: 45 rows, the first 30 shown
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_R | [-1 5 0 8] | [-1 5 1 7] | [-1 5 -1 9] | DIR_T | DIR_L
(0,1) | DIR_R | [-1 5 1 7] | [-1 5 2 6] | [-1 5 0 8] | DIR_T | DIR_L
(0,2) | DIR_R | [-1 5 2 6] | [-1 5 3 5] | [-1 5 1 7] | DIR_T | DIR_L
(0,3) | DIR_R | [-1 5 3 5] | [-1 5 4 4] | [-1 5 2 6] | DIR_T | DIR_L
(0,4) | DIR_R | [-1 5 4 4] | [-1 5 5 3] | [-1 5 3 5] | DIR_T | DIR_L
(0,5) | DIR_R | [-1 5 5 3] | [-1 5 6 2] | [-1 5 4 4] | DIR_T | DIR_L
(0,6) | DIR_R | [-1 5 6 2] | [-1 5 7 1] | [-1 5 5 3] | DIR_T | DIR_L
(0,7) | DIR_R | [-1 5 7 1] | [-1 5 8 0] | [-1 5 6 2] | DIR_T | DIR_L
(0,8) | DIR_R | [-1 5 8 0] | [-1 5 9 -1] | [-1 5 7 1] | DIR_T | DIR_L
(1,0) | DIR_R | (0,0) | (0,1) | [0 4 -1 9] | DIR_T | DIR_L
(1,1) | DIR_R | (0,1) | (0,2) | (0,0) | DIR_T | DIR_L
(1,2) | DIR_R | (0,2) | (0,3) | (0,1) | DIR_T | DIR_L
(1,3) | DIR_R | (0,3) | (0,4) | (0,2) | DIR_T | DIR_L
(1,4) | DIR_R | (0,4) | (0,5) | (0,3) | DIR_T | DIR_L
(1,5) | DIR_R | (0,5) | (0,6) | (0,4) | DIR_T | DIR_L
(1,6) | DIR_R | (0,6) | (0,7) | (0,5) | DIR_T | DIR_L
(1,7) | DIR_R | (0,7) | (0,8) | (0,6) | DIR_T | DIR_L
(1,8) | DIR_R | (0,8) | [0 4 9 -1] | (0,7) | DIR_T | DIR_L
(2,0) | DIR_R | (1,0) | (1,1) | [1 3 -1 9] | DIR_T | DIR_L
(2,1) | DIR_R | (1,1) | (1,2) | (1,0) | DIR_T | DIR_L
(2,2) | DIR_R | (1,2) | (1,3) | (1,1) | DIR_T | DIR_L
(2,3) | DIR_R | (1,3) | (1,4) | (1,2) | DIR_T | DIR_L
(2,4) | DIR_R | (1,4) | (1,5) | (1,3) | DIR_T | DIR_L
(2,5) | DIR_R | (1,5) | (1,6) | (1,4) | DIR_T | DIR_L
(2,6) | DIR_R | (1,6) | (1,7) | (1,5) | DIR_T | DIR_L
(2,7) | DIR_R | (1,7) | (1,8) | (1,6) | DIR_T | DIR_L
(2,8) | DIR_R | (1,8) | [1 3 9 -1] | (1,7) | DIR_T | DIR_L
(3,0) | DIR_R | (2,0) | (2,1) | [2 2 -1 9] | DIR_T | DIR_L
(3,1) | DIR_R | (2,1) | (2,2) | (2,0) | DIR_T | DIR_L
(3,2) | DIR_R | (2,2) | (2,3) | (2,1) | DIR_T | DIR_L
```

Train example 5: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_R | [-1 3 0 4] | [-1 3 1 3] | [-1 3 -1 5] | DIR_T | DIR_L
(0,1) | DIR_R | [-1 3 1 3] | [-1 3 2 2] | [-1 3 0 4] | DIR_T | DIR_L
(0,2) | DIR_R | [-1 3 2 2] | [-1 3 3 1] | [-1 3 1 3] | DIR_T | DIR_L
(0,3) | DIR_R | [-1 3 3 1] | [-1 3 4 0] | [-1 3 2 2] | DIR_T | DIR_L
(0,4) | DIR_R | [-1 3 4 0] | [-1 3 5 -1] | [-1 3 3 1] | DIR_T | DIR_L
(1,0) | DIR_R | (0,0) | (0,1) | [0 2 -1 5] | DIR_T | DIR_L
(1,1) | DIR_R | (0,1) | (0,2) | (0,0) | DIR_T | DIR_L
(1,2) | DIR_R | (0,2) | (0,3) | (0,1) | DIR_T | DIR_L
(1,3) | DIR_R | (0,3) | (0,4) | (0,2) | DIR_T | DIR_L
(1,4) | DIR_R | (0,4) | [0 2 5 -1] | (0,3) | DIR_T | DIR_L
(2,0) | DIR_R | (1,0) | (1,1) | [1 1 -1 5] | DIR_T | DIR_L
(2,1) | DIR_R | (1,1) | (1,2) | (1,0) | DIR_T | DIR_L
(2,2) | DIR_R | (1,2) | (1,3) | (1,1) | DIR_T | DIR_L
(2,3) | DIR_R | (1,3) | (1,4) | (1,2) | DIR_T | DIR_L
(2,4) | DIR_R | (1,4) | [1 1 5 -1] | (1,3) | DIR_T | DIR_L
```

Train example 6: 28 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_R | [-1 4 0 6] | [-1 4 1 5] | [-1 4 -1 7] | DIR_T | DIR_L
(0,1) | DIR_R | [-1 4 1 5] | [-1 4 2 4] | [-1 4 0 6] | DIR_T | DIR_L
(0,2) | DIR_R | [-1 4 2 4] | [-1 4 3 3] | [-1 4 1 5] | DIR_T | DIR_L
(0,3) | DIR_R | [-1 4 3 3] | [-1 4 4 2] | [-1 4 2 4] | DIR_T | DIR_L
(0,4) | DIR_R | [-1 4 4 2] | [-1 4 5 1] | [-1 4 3 3] | DIR_T | DIR_L
(0,5) | DIR_R | [-1 4 5 1] | [-1 4 6 0] | [-1 4 4 2] | DIR_T | DIR_L
(0,6) | DIR_R | [-1 4 6 0] | [-1 4 7 -1] | [-1 4 5 1] | DIR_T | DIR_L
(1,0) | DIR_R | (0,0) | (0,1) | [0 3 -1 7] | DIR_T | DIR_L
(1,1) | DIR_R | (0,1) | (0,2) | (0,0) | DIR_T | DIR_L
(1,2) | DIR_R | (0,2) | (0,3) | (0,1) | DIR_T | DIR_L
(1,3) | DIR_R | (0,3) | (0,4) | (0,2) | DIR_T | DIR_L
(1,4) | DIR_R | (0,4) | (0,5) | (0,3) | DIR_T | DIR_L
(1,5) | DIR_R | (0,5) | (0,6) | (0,4) | DIR_T | DIR_L
(1,6) | DIR_R | (0,6) | [0 3 7 -1] | (0,5) | DIR_T | DIR_L
(2,0) | DIR_R | (1,0) | (1,1) | [1 2 -1 7] | DIR_T | DIR_L
(2,1) | DIR_R | (1,1) | (1,2) | (1,0) | DIR_T | DIR_L
(2,2) | DIR_R | (1,2) | (1,3) | (1,1) | DIR_T | DIR_L
(2,3) | DIR_R | (1,3) | (1,4) | (1,2) | DIR_T | DIR_L
(2,4) | DIR_R | (1,4) | (1,5) | (1,3) | DIR_T | DIR_L
(2,5) | DIR_R | (1,5) | (1,6) | (1,4) | DIR_T | DIR_L
(2,6) | DIR_R | (1,6) | [1 2 7 -1] | (1,5) | DIR_T | DIR_L
(3,0) | DIR_R | (2,0) | (2,1) | [2 1 -1 7] | DIR_T | DIR_L
(3,1) | DIR_R | (2,1) | (2,2) | (2,0) | DIR_T | DIR_L
(3,2) | DIR_R | (2,2) | (2,3) | (2,1) | DIR_T | DIR_L
(3,3) | DIR_R | (2,3) | (2,4) | (2,2) | DIR_T | DIR_L
(3,4) | DIR_R | (2,4) | (2,5) | (2,3) | DIR_T | DIR_L
(3,5) | DIR_R | (2,5) | (2,6) | (2,4) | DIR_T | DIR_L
(3,6) | DIR_R | (2,6) | [2 1 7 -1] | (2,5) | DIR_T | DIR_L
```


#### &r16, assignment 4 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CC)}
- rows per train example: [15, 15, 15, 15, 45, 15, 28]; test: 72

Train example 0: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_L | [-1 3 0 4] | [-1 3 -1 5] | [-1 3 1 3] | DIR_T | DIR_R
(0,1) | DIR_L | [-1 3 1 3] | [-1 3 0 4] | [-1 3 2 2] | DIR_T | DIR_R
(0,2) | DIR_L | [-1 3 2 2] | [-1 3 1 3] | [-1 3 3 1] | DIR_T | DIR_R
(0,3) | DIR_L | [-1 3 3 1] | [-1 3 2 2] | [-1 3 4 0] | DIR_T | DIR_R
(0,4) | DIR_L | [-1 3 4 0] | [-1 3 3 1] | [-1 3 5 -1] | DIR_T | DIR_R
(1,0) | DIR_L | (0,0) | [0 2 -1 5] | (0,1) | DIR_T | DIR_R
(1,1) | DIR_L | (0,1) | (0,0) | (0,2) | DIR_T | DIR_R
(1,2) | DIR_L | (0,2) | (0,1) | (0,3) | DIR_T | DIR_R
(1,3) | DIR_L | (0,3) | (0,2) | (0,4) | DIR_T | DIR_R
(1,4) | DIR_L | (0,4) | (0,3) | [0 2 5 -1] | DIR_T | DIR_R
(2,0) | DIR_L | (1,0) | [1 1 -1 5] | (1,1) | DIR_T | DIR_R
(2,1) | DIR_L | (1,1) | (1,0) | (1,2) | DIR_T | DIR_R
(2,2) | DIR_L | (1,2) | (1,1) | (1,3) | DIR_T | DIR_R
(2,3) | DIR_L | (1,3) | (1,2) | (1,4) | DIR_T | DIR_R
(2,4) | DIR_L | (1,4) | (1,3) | [1 1 5 -1] | DIR_T | DIR_R
```

Train example 1: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_L | [-1 3 0 4] | [-1 3 -1 5] | [-1 3 1 3] | DIR_T | DIR_R
(0,1) | DIR_L | [-1 3 1 3] | [-1 3 0 4] | [-1 3 2 2] | DIR_T | DIR_R
(0,2) | DIR_L | [-1 3 2 2] | [-1 3 1 3] | [-1 3 3 1] | DIR_T | DIR_R
(0,3) | DIR_L | [-1 3 3 1] | [-1 3 2 2] | [-1 3 4 0] | DIR_T | DIR_R
(0,4) | DIR_L | [-1 3 4 0] | [-1 3 3 1] | [-1 3 5 -1] | DIR_T | DIR_R
(1,0) | DIR_L | (0,0) | [0 2 -1 5] | (0,1) | DIR_T | DIR_R
(1,1) | DIR_L | (0,1) | (0,0) | (0,2) | DIR_T | DIR_R
(1,2) | DIR_L | (0,2) | (0,1) | (0,3) | DIR_T | DIR_R
(1,3) | DIR_L | (0,3) | (0,2) | (0,4) | DIR_T | DIR_R
(1,4) | DIR_L | (0,4) | (0,3) | [0 2 5 -1] | DIR_T | DIR_R
(2,0) | DIR_L | (1,0) | [1 1 -1 5] | (1,1) | DIR_T | DIR_R
(2,1) | DIR_L | (1,1) | (1,0) | (1,2) | DIR_T | DIR_R
(2,2) | DIR_L | (1,2) | (1,1) | (1,3) | DIR_T | DIR_R
(2,3) | DIR_L | (1,3) | (1,2) | (1,4) | DIR_T | DIR_R
(2,4) | DIR_L | (1,4) | (1,3) | [1 1 5 -1] | DIR_T | DIR_R
```

Train example 2: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_L | [-1 3 0 4] | [-1 3 -1 5] | [-1 3 1 3] | DIR_T | DIR_R
(0,1) | DIR_L | [-1 3 1 3] | [-1 3 0 4] | [-1 3 2 2] | DIR_T | DIR_R
(0,2) | DIR_L | [-1 3 2 2] | [-1 3 1 3] | [-1 3 3 1] | DIR_T | DIR_R
(0,3) | DIR_L | [-1 3 3 1] | [-1 3 2 2] | [-1 3 4 0] | DIR_T | DIR_R
(0,4) | DIR_L | [-1 3 4 0] | [-1 3 3 1] | [-1 3 5 -1] | DIR_T | DIR_R
(1,0) | DIR_L | (0,0) | [0 2 -1 5] | (0,1) | DIR_T | DIR_R
(1,1) | DIR_L | (0,1) | (0,0) | (0,2) | DIR_T | DIR_R
(1,2) | DIR_L | (0,2) | (0,1) | (0,3) | DIR_T | DIR_R
(1,3) | DIR_L | (0,3) | (0,2) | (0,4) | DIR_T | DIR_R
(1,4) | DIR_L | (0,4) | (0,3) | [0 2 5 -1] | DIR_T | DIR_R
(2,0) | DIR_L | (1,0) | [1 1 -1 5] | (1,1) | DIR_T | DIR_R
(2,1) | DIR_L | (1,1) | (1,0) | (1,2) | DIR_T | DIR_R
(2,2) | DIR_L | (1,2) | (1,1) | (1,3) | DIR_T | DIR_R
(2,3) | DIR_L | (1,3) | (1,2) | (1,4) | DIR_T | DIR_R
(2,4) | DIR_L | (1,4) | (1,3) | [1 1 5 -1] | DIR_T | DIR_R
```

Train example 3: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_L | [-1 3 0 4] | [-1 3 -1 5] | [-1 3 1 3] | DIR_T | DIR_R
(0,1) | DIR_L | [-1 3 1 3] | [-1 3 0 4] | [-1 3 2 2] | DIR_T | DIR_R
(0,2) | DIR_L | [-1 3 2 2] | [-1 3 1 3] | [-1 3 3 1] | DIR_T | DIR_R
(0,3) | DIR_L | [-1 3 3 1] | [-1 3 2 2] | [-1 3 4 0] | DIR_T | DIR_R
(0,4) | DIR_L | [-1 3 4 0] | [-1 3 3 1] | [-1 3 5 -1] | DIR_T | DIR_R
(1,0) | DIR_L | (0,0) | [0 2 -1 5] | (0,1) | DIR_T | DIR_R
(1,1) | DIR_L | (0,1) | (0,0) | (0,2) | DIR_T | DIR_R
(1,2) | DIR_L | (0,2) | (0,1) | (0,3) | DIR_T | DIR_R
(1,3) | DIR_L | (0,3) | (0,2) | (0,4) | DIR_T | DIR_R
(1,4) | DIR_L | (0,4) | (0,3) | [0 2 5 -1] | DIR_T | DIR_R
(2,0) | DIR_L | (1,0) | [1 1 -1 5] | (1,1) | DIR_T | DIR_R
(2,1) | DIR_L | (1,1) | (1,0) | (1,2) | DIR_T | DIR_R
(2,2) | DIR_L | (1,2) | (1,1) | (1,3) | DIR_T | DIR_R
(2,3) | DIR_L | (1,3) | (1,2) | (1,4) | DIR_T | DIR_R
(2,4) | DIR_L | (1,4) | (1,3) | [1 1 5 -1] | DIR_T | DIR_R
```

Train example 4: 45 rows, the first 30 shown
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_L | [-1 5 0 8] | [-1 5 -1 9] | [-1 5 1 7] | DIR_T | DIR_R
(0,1) | DIR_L | [-1 5 1 7] | [-1 5 0 8] | [-1 5 2 6] | DIR_T | DIR_R
(0,2) | DIR_L | [-1 5 2 6] | [-1 5 1 7] | [-1 5 3 5] | DIR_T | DIR_R
(0,3) | DIR_L | [-1 5 3 5] | [-1 5 2 6] | [-1 5 4 4] | DIR_T | DIR_R
(0,4) | DIR_L | [-1 5 4 4] | [-1 5 3 5] | [-1 5 5 3] | DIR_T | DIR_R
(0,5) | DIR_L | [-1 5 5 3] | [-1 5 4 4] | [-1 5 6 2] | DIR_T | DIR_R
(0,6) | DIR_L | [-1 5 6 2] | [-1 5 5 3] | [-1 5 7 1] | DIR_T | DIR_R
(0,7) | DIR_L | [-1 5 7 1] | [-1 5 6 2] | [-1 5 8 0] | DIR_T | DIR_R
(0,8) | DIR_L | [-1 5 8 0] | [-1 5 7 1] | [-1 5 9 -1] | DIR_T | DIR_R
(1,0) | DIR_L | (0,0) | [0 4 -1 9] | (0,1) | DIR_T | DIR_R
(1,1) | DIR_L | (0,1) | (0,0) | (0,2) | DIR_T | DIR_R
(1,2) | DIR_L | (0,2) | (0,1) | (0,3) | DIR_T | DIR_R
(1,3) | DIR_L | (0,3) | (0,2) | (0,4) | DIR_T | DIR_R
(1,4) | DIR_L | (0,4) | (0,3) | (0,5) | DIR_T | DIR_R
(1,5) | DIR_L | (0,5) | (0,4) | (0,6) | DIR_T | DIR_R
(1,6) | DIR_L | (0,6) | (0,5) | (0,7) | DIR_T | DIR_R
(1,7) | DIR_L | (0,7) | (0,6) | (0,8) | DIR_T | DIR_R
(1,8) | DIR_L | (0,8) | (0,7) | [0 4 9 -1] | DIR_T | DIR_R
(2,0) | DIR_L | (1,0) | [1 3 -1 9] | (1,1) | DIR_T | DIR_R
(2,1) | DIR_L | (1,1) | (1,0) | (1,2) | DIR_T | DIR_R
(2,2) | DIR_L | (1,2) | (1,1) | (1,3) | DIR_T | DIR_R
(2,3) | DIR_L | (1,3) | (1,2) | (1,4) | DIR_T | DIR_R
(2,4) | DIR_L | (1,4) | (1,3) | (1,5) | DIR_T | DIR_R
(2,5) | DIR_L | (1,5) | (1,4) | (1,6) | DIR_T | DIR_R
(2,6) | DIR_L | (1,6) | (1,5) | (1,7) | DIR_T | DIR_R
(2,7) | DIR_L | (1,7) | (1,6) | (1,8) | DIR_T | DIR_R
(2,8) | DIR_L | (1,8) | (1,7) | [1 3 9 -1] | DIR_T | DIR_R
(3,0) | DIR_L | (2,0) | [2 2 -1 9] | (2,1) | DIR_T | DIR_R
(3,1) | DIR_L | (2,1) | (2,0) | (2,2) | DIR_T | DIR_R
(3,2) | DIR_L | (2,2) | (2,1) | (2,3) | DIR_T | DIR_R
```

Train example 5: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_L | [-1 3 0 4] | [-1 3 -1 5] | [-1 3 1 3] | DIR_T | DIR_R
(0,1) | DIR_L | [-1 3 1 3] | [-1 3 0 4] | [-1 3 2 2] | DIR_T | DIR_R
(0,2) | DIR_L | [-1 3 2 2] | [-1 3 1 3] | [-1 3 3 1] | DIR_T | DIR_R
(0,3) | DIR_L | [-1 3 3 1] | [-1 3 2 2] | [-1 3 4 0] | DIR_T | DIR_R
(0,4) | DIR_L | [-1 3 4 0] | [-1 3 3 1] | [-1 3 5 -1] | DIR_T | DIR_R
(1,0) | DIR_L | (0,0) | [0 2 -1 5] | (0,1) | DIR_T | DIR_R
(1,1) | DIR_L | (0,1) | (0,0) | (0,2) | DIR_T | DIR_R
(1,2) | DIR_L | (0,2) | (0,1) | (0,3) | DIR_T | DIR_R
(1,3) | DIR_L | (0,3) | (0,2) | (0,4) | DIR_T | DIR_R
(1,4) | DIR_L | (0,4) | (0,3) | [0 2 5 -1] | DIR_T | DIR_R
(2,0) | DIR_L | (1,0) | [1 1 -1 5] | (1,1) | DIR_T | DIR_R
(2,1) | DIR_L | (1,1) | (1,0) | (1,2) | DIR_T | DIR_R
(2,2) | DIR_L | (1,2) | (1,1) | (1,3) | DIR_T | DIR_R
(2,3) | DIR_L | (1,3) | (1,2) | (1,4) | DIR_T | DIR_R
(2,4) | DIR_L | (1,4) | (1,3) | [1 1 5 -1] | DIR_T | DIR_R
```

Train example 6: 28 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_L | [-1 4 0 6] | [-1 4 -1 7] | [-1 4 1 5] | DIR_T | DIR_R
(0,1) | DIR_L | [-1 4 1 5] | [-1 4 0 6] | [-1 4 2 4] | DIR_T | DIR_R
(0,2) | DIR_L | [-1 4 2 4] | [-1 4 1 5] | [-1 4 3 3] | DIR_T | DIR_R
(0,3) | DIR_L | [-1 4 3 3] | [-1 4 2 4] | [-1 4 4 2] | DIR_T | DIR_R
(0,4) | DIR_L | [-1 4 4 2] | [-1 4 3 3] | [-1 4 5 1] | DIR_T | DIR_R
(0,5) | DIR_L | [-1 4 5 1] | [-1 4 4 2] | [-1 4 6 0] | DIR_T | DIR_R
(0,6) | DIR_L | [-1 4 6 0] | [-1 4 5 1] | [-1 4 7 -1] | DIR_T | DIR_R
(1,0) | DIR_L | (0,0) | [0 3 -1 7] | (0,1) | DIR_T | DIR_R
(1,1) | DIR_L | (0,1) | (0,0) | (0,2) | DIR_T | DIR_R
(1,2) | DIR_L | (0,2) | (0,1) | (0,3) | DIR_T | DIR_R
(1,3) | DIR_L | (0,3) | (0,2) | (0,4) | DIR_T | DIR_R
(1,4) | DIR_L | (0,4) | (0,3) | (0,5) | DIR_T | DIR_R
(1,5) | DIR_L | (0,5) | (0,4) | (0,6) | DIR_T | DIR_R
(1,6) | DIR_L | (0,6) | (0,5) | [0 3 7 -1] | DIR_T | DIR_R
(2,0) | DIR_L | (1,0) | [1 2 -1 7] | (1,1) | DIR_T | DIR_R
(2,1) | DIR_L | (1,1) | (1,0) | (1,2) | DIR_T | DIR_R
(2,2) | DIR_L | (1,2) | (1,1) | (1,3) | DIR_T | DIR_R
(2,3) | DIR_L | (1,3) | (1,2) | (1,4) | DIR_T | DIR_R
(2,4) | DIR_L | (1,4) | (1,3) | (1,5) | DIR_T | DIR_R
(2,5) | DIR_L | (1,5) | (1,4) | (1,6) | DIR_T | DIR_R
(2,6) | DIR_L | (1,6) | (1,5) | [1 2 7 -1] | DIR_T | DIR_R
(3,0) | DIR_L | (2,0) | [2 1 -1 7] | (2,1) | DIR_T | DIR_R
(3,1) | DIR_L | (2,1) | (2,0) | (2,2) | DIR_T | DIR_R
(3,2) | DIR_L | (2,2) | (2,1) | (2,3) | DIR_T | DIR_R
(3,3) | DIR_L | (2,3) | (2,2) | (2,4) | DIR_T | DIR_R
(3,4) | DIR_L | (2,4) | (2,3) | (2,5) | DIR_T | DIR_R
(3,5) | DIR_L | (2,5) | (2,4) | (2,6) | DIR_T | DIR_R
(3,6) | DIR_L | (2,6) | (2,5) | [2 1 7 -1] | DIR_T | DIR_R
```


#### &r16, assignment 5 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CW)}
- rows per train example: [15, 15, 15, 15, 45, 15, 28]; test: 72

Train example 0: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_B | (0,1) | (1,1) | [-1 3 1 3] | DIR_R | DIR_T
(0,1) | DIR_B | (0,2) | (1,2) | [-1 3 2 2] | DIR_R | DIR_T
(0,2) | DIR_B | (0,3) | (1,3) | [-1 3 3 1] | DIR_R | DIR_T
(0,3) | DIR_B | (0,4) | (1,4) | [-1 3 4 0] | DIR_R | DIR_T
(0,4) | DIR_B | [0 2 5 -1] | [1 1 5 -1] | [-1 3 5 -1] | DIR_R | DIR_T
(1,0) | DIR_B | (1,1) | (2,1) | (0,1) | DIR_R | DIR_T
(1,1) | DIR_B | (1,2) | (2,2) | (0,2) | DIR_R | DIR_T
(1,2) | DIR_B | (1,3) | (2,3) | (0,3) | DIR_R | DIR_T
(1,3) | DIR_B | (1,4) | (2,4) | (0,4) | DIR_R | DIR_T
(1,4) | DIR_B | [1 1 5 -1] | [2 0 5 -1] | [0 2 5 -1] | DIR_R | DIR_T
(2,0) | DIR_B | (2,1) | [3 -1 1 3] | (1,1) | DIR_R | DIR_T
(2,1) | DIR_B | (2,2) | [3 -1 2 2] | (1,2) | DIR_R | DIR_T
(2,2) | DIR_B | (2,3) | [3 -1 3 1] | (1,3) | DIR_R | DIR_T
(2,3) | DIR_B | (2,4) | [3 -1 4 0] | (1,4) | DIR_R | DIR_T
(2,4) | DIR_B | [2 0 5 -1] | [3 -1 5 -1] | [1 1 5 -1] | DIR_R | DIR_T
```

Train example 1: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_B | (0,1) | (1,1) | [-1 3 1 3] | DIR_R | DIR_T
(0,1) | DIR_B | (0,2) | (1,2) | [-1 3 2 2] | DIR_R | DIR_T
(0,2) | DIR_B | (0,3) | (1,3) | [-1 3 3 1] | DIR_R | DIR_T
(0,3) | DIR_B | (0,4) | (1,4) | [-1 3 4 0] | DIR_R | DIR_T
(0,4) | DIR_B | [0 2 5 -1] | [1 1 5 -1] | [-1 3 5 -1] | DIR_R | DIR_T
(1,0) | DIR_B | (1,1) | (2,1) | (0,1) | DIR_R | DIR_T
(1,1) | DIR_B | (1,2) | (2,2) | (0,2) | DIR_R | DIR_T
(1,2) | DIR_B | (1,3) | (2,3) | (0,3) | DIR_R | DIR_T
(1,3) | DIR_B | (1,4) | (2,4) | (0,4) | DIR_R | DIR_T
(1,4) | DIR_B | [1 1 5 -1] | [2 0 5 -1] | [0 2 5 -1] | DIR_R | DIR_T
(2,0) | DIR_B | (2,1) | [3 -1 1 3] | (1,1) | DIR_R | DIR_T
(2,1) | DIR_B | (2,2) | [3 -1 2 2] | (1,2) | DIR_R | DIR_T
(2,2) | DIR_B | (2,3) | [3 -1 3 1] | (1,3) | DIR_R | DIR_T
(2,3) | DIR_B | (2,4) | [3 -1 4 0] | (1,4) | DIR_R | DIR_T
(2,4) | DIR_B | [2 0 5 -1] | [3 -1 5 -1] | [1 1 5 -1] | DIR_R | DIR_T
```

Train example 2: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_B | (0,1) | (1,1) | [-1 3 1 3] | DIR_R | DIR_T
(0,1) | DIR_B | (0,2) | (1,2) | [-1 3 2 2] | DIR_R | DIR_T
(0,2) | DIR_B | (0,3) | (1,3) | [-1 3 3 1] | DIR_R | DIR_T
(0,3) | DIR_B | (0,4) | (1,4) | [-1 3 4 0] | DIR_R | DIR_T
(0,4) | DIR_B | [0 2 5 -1] | [1 1 5 -1] | [-1 3 5 -1] | DIR_R | DIR_T
(1,0) | DIR_B | (1,1) | (2,1) | (0,1) | DIR_R | DIR_T
(1,1) | DIR_B | (1,2) | (2,2) | (0,2) | DIR_R | DIR_T
(1,2) | DIR_B | (1,3) | (2,3) | (0,3) | DIR_R | DIR_T
(1,3) | DIR_B | (1,4) | (2,4) | (0,4) | DIR_R | DIR_T
(1,4) | DIR_B | [1 1 5 -1] | [2 0 5 -1] | [0 2 5 -1] | DIR_R | DIR_T
(2,0) | DIR_B | (2,1) | [3 -1 1 3] | (1,1) | DIR_R | DIR_T
(2,1) | DIR_B | (2,2) | [3 -1 2 2] | (1,2) | DIR_R | DIR_T
(2,2) | DIR_B | (2,3) | [3 -1 3 1] | (1,3) | DIR_R | DIR_T
(2,3) | DIR_B | (2,4) | [3 -1 4 0] | (1,4) | DIR_R | DIR_T
(2,4) | DIR_B | [2 0 5 -1] | [3 -1 5 -1] | [1 1 5 -1] | DIR_R | DIR_T
```

Train example 3: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_B | (0,1) | (1,1) | [-1 3 1 3] | DIR_R | DIR_T
(0,1) | DIR_B | (0,2) | (1,2) | [-1 3 2 2] | DIR_R | DIR_T
(0,2) | DIR_B | (0,3) | (1,3) | [-1 3 3 1] | DIR_R | DIR_T
(0,3) | DIR_B | (0,4) | (1,4) | [-1 3 4 0] | DIR_R | DIR_T
(0,4) | DIR_B | [0 2 5 -1] | [1 1 5 -1] | [-1 3 5 -1] | DIR_R | DIR_T
(1,0) | DIR_B | (1,1) | (2,1) | (0,1) | DIR_R | DIR_T
(1,1) | DIR_B | (1,2) | (2,2) | (0,2) | DIR_R | DIR_T
(1,2) | DIR_B | (1,3) | (2,3) | (0,3) | DIR_R | DIR_T
(1,3) | DIR_B | (1,4) | (2,4) | (0,4) | DIR_R | DIR_T
(1,4) | DIR_B | [1 1 5 -1] | [2 0 5 -1] | [0 2 5 -1] | DIR_R | DIR_T
(2,0) | DIR_B | (2,1) | [3 -1 1 3] | (1,1) | DIR_R | DIR_T
(2,1) | DIR_B | (2,2) | [3 -1 2 2] | (1,2) | DIR_R | DIR_T
(2,2) | DIR_B | (2,3) | [3 -1 3 1] | (1,3) | DIR_R | DIR_T
(2,3) | DIR_B | (2,4) | [3 -1 4 0] | (1,4) | DIR_R | DIR_T
(2,4) | DIR_B | [2 0 5 -1] | [3 -1 5 -1] | [1 1 5 -1] | DIR_R | DIR_T
```

Train example 4: 45 rows, the first 30 shown
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_B | (0,1) | (1,1) | [-1 5 1 7] | DIR_R | DIR_T
(0,1) | DIR_B | (0,2) | (1,2) | [-1 5 2 6] | DIR_R | DIR_T
(0,2) | DIR_B | (0,3) | (1,3) | [-1 5 3 5] | DIR_R | DIR_T
(0,3) | DIR_B | (0,4) | (1,4) | [-1 5 4 4] | DIR_R | DIR_T
(0,4) | DIR_B | (0,5) | (1,5) | [-1 5 5 3] | DIR_R | DIR_T
(0,5) | DIR_B | (0,6) | (1,6) | [-1 5 6 2] | DIR_R | DIR_T
(0,6) | DIR_B | (0,7) | (1,7) | [-1 5 7 1] | DIR_R | DIR_T
(0,7) | DIR_B | (0,8) | (1,8) | [-1 5 8 0] | DIR_R | DIR_T
(0,8) | DIR_B | [0 4 9 -1] | [1 3 9 -1] | [-1 5 9 -1] | DIR_R | DIR_T
(1,0) | DIR_B | (1,1) | (2,1) | (0,1) | DIR_R | DIR_T
(1,1) | DIR_B | (1,2) | (2,2) | (0,2) | DIR_R | DIR_T
(1,2) | DIR_B | (1,3) | (2,3) | (0,3) | DIR_R | DIR_T
(1,3) | DIR_B | (1,4) | (2,4) | (0,4) | DIR_R | DIR_T
(1,4) | DIR_B | (1,5) | (2,5) | (0,5) | DIR_R | DIR_T
(1,5) | DIR_B | (1,6) | (2,6) | (0,6) | DIR_R | DIR_T
(1,6) | DIR_B | (1,7) | (2,7) | (0,7) | DIR_R | DIR_T
(1,7) | DIR_B | (1,8) | (2,8) | (0,8) | DIR_R | DIR_T
(1,8) | DIR_B | [1 3 9 -1] | [2 2 9 -1] | [0 4 9 -1] | DIR_R | DIR_T
(2,0) | DIR_B | (2,1) | (3,1) | (1,1) | DIR_R | DIR_T
(2,1) | DIR_B | (2,2) | (3,2) | (1,2) | DIR_R | DIR_T
(2,2) | DIR_B | (2,3) | (3,3) | (1,3) | DIR_R | DIR_T
(2,3) | DIR_B | (2,4) | (3,4) | (1,4) | DIR_R | DIR_T
(2,4) | DIR_B | (2,5) | (3,5) | (1,5) | DIR_R | DIR_T
(2,5) | DIR_B | (2,6) | (3,6) | (1,6) | DIR_R | DIR_T
(2,6) | DIR_B | (2,7) | (3,7) | (1,7) | DIR_R | DIR_T
(2,7) | DIR_B | (2,8) | (3,8) | (1,8) | DIR_R | DIR_T
(2,8) | DIR_B | [2 2 9 -1] | [3 1 9 -1] | [1 3 9 -1] | DIR_R | DIR_T
(3,0) | DIR_B | (3,1) | (4,1) | (2,1) | DIR_R | DIR_T
(3,1) | DIR_B | (3,2) | (4,2) | (2,2) | DIR_R | DIR_T
(3,2) | DIR_B | (3,3) | (4,3) | (2,3) | DIR_R | DIR_T
```

Train example 5: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_B | (0,1) | (1,1) | [-1 3 1 3] | DIR_R | DIR_T
(0,1) | DIR_B | (0,2) | (1,2) | [-1 3 2 2] | DIR_R | DIR_T
(0,2) | DIR_B | (0,3) | (1,3) | [-1 3 3 1] | DIR_R | DIR_T
(0,3) | DIR_B | (0,4) | (1,4) | [-1 3 4 0] | DIR_R | DIR_T
(0,4) | DIR_B | [0 2 5 -1] | [1 1 5 -1] | [-1 3 5 -1] | DIR_R | DIR_T
(1,0) | DIR_B | (1,1) | (2,1) | (0,1) | DIR_R | DIR_T
(1,1) | DIR_B | (1,2) | (2,2) | (0,2) | DIR_R | DIR_T
(1,2) | DIR_B | (1,3) | (2,3) | (0,3) | DIR_R | DIR_T
(1,3) | DIR_B | (1,4) | (2,4) | (0,4) | DIR_R | DIR_T
(1,4) | DIR_B | [1 1 5 -1] | [2 0 5 -1] | [0 2 5 -1] | DIR_R | DIR_T
(2,0) | DIR_B | (2,1) | [3 -1 1 3] | (1,1) | DIR_R | DIR_T
(2,1) | DIR_B | (2,2) | [3 -1 2 2] | (1,2) | DIR_R | DIR_T
(2,2) | DIR_B | (2,3) | [3 -1 3 1] | (1,3) | DIR_R | DIR_T
(2,3) | DIR_B | (2,4) | [3 -1 4 0] | (1,4) | DIR_R | DIR_T
(2,4) | DIR_B | [2 0 5 -1] | [3 -1 5 -1] | [1 1 5 -1] | DIR_R | DIR_T
```

Train example 6: 28 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_B | (0,1) | (1,1) | [-1 4 1 5] | DIR_R | DIR_T
(0,1) | DIR_B | (0,2) | (1,2) | [-1 4 2 4] | DIR_R | DIR_T
(0,2) | DIR_B | (0,3) | (1,3) | [-1 4 3 3] | DIR_R | DIR_T
(0,3) | DIR_B | (0,4) | (1,4) | [-1 4 4 2] | DIR_R | DIR_T
(0,4) | DIR_B | (0,5) | (1,5) | [-1 4 5 1] | DIR_R | DIR_T
(0,5) | DIR_B | (0,6) | (1,6) | [-1 4 6 0] | DIR_R | DIR_T
(0,6) | DIR_B | [0 3 7 -1] | [1 2 7 -1] | [-1 4 7 -1] | DIR_R | DIR_T
(1,0) | DIR_B | (1,1) | (2,1) | (0,1) | DIR_R | DIR_T
(1,1) | DIR_B | (1,2) | (2,2) | (0,2) | DIR_R | DIR_T
(1,2) | DIR_B | (1,3) | (2,3) | (0,3) | DIR_R | DIR_T
(1,3) | DIR_B | (1,4) | (2,4) | (0,4) | DIR_R | DIR_T
(1,4) | DIR_B | (1,5) | (2,5) | (0,5) | DIR_R | DIR_T
(1,5) | DIR_B | (1,6) | (2,6) | (0,6) | DIR_R | DIR_T
(1,6) | DIR_B | [1 2 7 -1] | [2 1 7 -1] | [0 3 7 -1] | DIR_R | DIR_T
(2,0) | DIR_B | (2,1) | (3,1) | (1,1) | DIR_R | DIR_T
(2,1) | DIR_B | (2,2) | (3,2) | (1,2) | DIR_R | DIR_T
(2,2) | DIR_B | (2,3) | (3,3) | (1,3) | DIR_R | DIR_T
(2,3) | DIR_B | (2,4) | (3,4) | (1,4) | DIR_R | DIR_T
(2,4) | DIR_B | (2,5) | (3,5) | (1,5) | DIR_R | DIR_T
(2,5) | DIR_B | (2,6) | (3,6) | (1,6) | DIR_R | DIR_T
(2,6) | DIR_B | [2 1 7 -1] | [3 0 7 -1] | [1 2 7 -1] | DIR_R | DIR_T
(3,0) | DIR_B | (3,1) | [4 -1 1 5] | (2,1) | DIR_R | DIR_T
(3,1) | DIR_B | (3,2) | [4 -1 2 4] | (2,2) | DIR_R | DIR_T
(3,2) | DIR_B | (3,3) | [4 -1 3 3] | (2,3) | DIR_R | DIR_T
(3,3) | DIR_B | (3,4) | [4 -1 4 2] | (2,4) | DIR_R | DIR_T
(3,4) | DIR_B | (3,5) | [4 -1 5 1] | (2,5) | DIR_R | DIR_T
(3,5) | DIR_B | (3,6) | [4 -1 6 0] | (2,6) | DIR_R | DIR_T
(3,6) | DIR_B | [3 0 7 -1] | [4 -1 7 -1] | [2 1 7 -1] | DIR_R | DIR_T
```


#### &r16, assignment 6 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CC)}
- rows per train example: [15, 15, 15, 15, 45, 15, 28]; test: 72

Train example 0: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_T | (0,1) | [-1 3 1 3] | (1,1) | DIR_R | DIR_B
(0,1) | DIR_T | (0,2) | [-1 3 2 2] | (1,2) | DIR_R | DIR_B
(0,2) | DIR_T | (0,3) | [-1 3 3 1] | (1,3) | DIR_R | DIR_B
(0,3) | DIR_T | (0,4) | [-1 3 4 0] | (1,4) | DIR_R | DIR_B
(0,4) | DIR_T | [0 2 5 -1] | [-1 3 5 -1] | [1 1 5 -1] | DIR_R | DIR_B
(1,0) | DIR_T | (1,1) | (0,1) | (2,1) | DIR_R | DIR_B
(1,1) | DIR_T | (1,2) | (0,2) | (2,2) | DIR_R | DIR_B
(1,2) | DIR_T | (1,3) | (0,3) | (2,3) | DIR_R | DIR_B
(1,3) | DIR_T | (1,4) | (0,4) | (2,4) | DIR_R | DIR_B
(1,4) | DIR_T | [1 1 5 -1] | [0 2 5 -1] | [2 0 5 -1] | DIR_R | DIR_B
(2,0) | DIR_T | (2,1) | (1,1) | [3 -1 1 3] | DIR_R | DIR_B
(2,1) | DIR_T | (2,2) | (1,2) | [3 -1 2 2] | DIR_R | DIR_B
(2,2) | DIR_T | (2,3) | (1,3) | [3 -1 3 1] | DIR_R | DIR_B
(2,3) | DIR_T | (2,4) | (1,4) | [3 -1 4 0] | DIR_R | DIR_B
(2,4) | DIR_T | [2 0 5 -1] | [1 1 5 -1] | [3 -1 5 -1] | DIR_R | DIR_B
```

Train example 1: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_T | (0,1) | [-1 3 1 3] | (1,1) | DIR_R | DIR_B
(0,1) | DIR_T | (0,2) | [-1 3 2 2] | (1,2) | DIR_R | DIR_B
(0,2) | DIR_T | (0,3) | [-1 3 3 1] | (1,3) | DIR_R | DIR_B
(0,3) | DIR_T | (0,4) | [-1 3 4 0] | (1,4) | DIR_R | DIR_B
(0,4) | DIR_T | [0 2 5 -1] | [-1 3 5 -1] | [1 1 5 -1] | DIR_R | DIR_B
(1,0) | DIR_T | (1,1) | (0,1) | (2,1) | DIR_R | DIR_B
(1,1) | DIR_T | (1,2) | (0,2) | (2,2) | DIR_R | DIR_B
(1,2) | DIR_T | (1,3) | (0,3) | (2,3) | DIR_R | DIR_B
(1,3) | DIR_T | (1,4) | (0,4) | (2,4) | DIR_R | DIR_B
(1,4) | DIR_T | [1 1 5 -1] | [0 2 5 -1] | [2 0 5 -1] | DIR_R | DIR_B
(2,0) | DIR_T | (2,1) | (1,1) | [3 -1 1 3] | DIR_R | DIR_B
(2,1) | DIR_T | (2,2) | (1,2) | [3 -1 2 2] | DIR_R | DIR_B
(2,2) | DIR_T | (2,3) | (1,3) | [3 -1 3 1] | DIR_R | DIR_B
(2,3) | DIR_T | (2,4) | (1,4) | [3 -1 4 0] | DIR_R | DIR_B
(2,4) | DIR_T | [2 0 5 -1] | [1 1 5 -1] | [3 -1 5 -1] | DIR_R | DIR_B
```

Train example 2: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_T | (0,1) | [-1 3 1 3] | (1,1) | DIR_R | DIR_B
(0,1) | DIR_T | (0,2) | [-1 3 2 2] | (1,2) | DIR_R | DIR_B
(0,2) | DIR_T | (0,3) | [-1 3 3 1] | (1,3) | DIR_R | DIR_B
(0,3) | DIR_T | (0,4) | [-1 3 4 0] | (1,4) | DIR_R | DIR_B
(0,4) | DIR_T | [0 2 5 -1] | [-1 3 5 -1] | [1 1 5 -1] | DIR_R | DIR_B
(1,0) | DIR_T | (1,1) | (0,1) | (2,1) | DIR_R | DIR_B
(1,1) | DIR_T | (1,2) | (0,2) | (2,2) | DIR_R | DIR_B
(1,2) | DIR_T | (1,3) | (0,3) | (2,3) | DIR_R | DIR_B
(1,3) | DIR_T | (1,4) | (0,4) | (2,4) | DIR_R | DIR_B
(1,4) | DIR_T | [1 1 5 -1] | [0 2 5 -1] | [2 0 5 -1] | DIR_R | DIR_B
(2,0) | DIR_T | (2,1) | (1,1) | [3 -1 1 3] | DIR_R | DIR_B
(2,1) | DIR_T | (2,2) | (1,2) | [3 -1 2 2] | DIR_R | DIR_B
(2,2) | DIR_T | (2,3) | (1,3) | [3 -1 3 1] | DIR_R | DIR_B
(2,3) | DIR_T | (2,4) | (1,4) | [3 -1 4 0] | DIR_R | DIR_B
(2,4) | DIR_T | [2 0 5 -1] | [1 1 5 -1] | [3 -1 5 -1] | DIR_R | DIR_B
```

Train example 3: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_T | (0,1) | [-1 3 1 3] | (1,1) | DIR_R | DIR_B
(0,1) | DIR_T | (0,2) | [-1 3 2 2] | (1,2) | DIR_R | DIR_B
(0,2) | DIR_T | (0,3) | [-1 3 3 1] | (1,3) | DIR_R | DIR_B
(0,3) | DIR_T | (0,4) | [-1 3 4 0] | (1,4) | DIR_R | DIR_B
(0,4) | DIR_T | [0 2 5 -1] | [-1 3 5 -1] | [1 1 5 -1] | DIR_R | DIR_B
(1,0) | DIR_T | (1,1) | (0,1) | (2,1) | DIR_R | DIR_B
(1,1) | DIR_T | (1,2) | (0,2) | (2,2) | DIR_R | DIR_B
(1,2) | DIR_T | (1,3) | (0,3) | (2,3) | DIR_R | DIR_B
(1,3) | DIR_T | (1,4) | (0,4) | (2,4) | DIR_R | DIR_B
(1,4) | DIR_T | [1 1 5 -1] | [0 2 5 -1] | [2 0 5 -1] | DIR_R | DIR_B
(2,0) | DIR_T | (2,1) | (1,1) | [3 -1 1 3] | DIR_R | DIR_B
(2,1) | DIR_T | (2,2) | (1,2) | [3 -1 2 2] | DIR_R | DIR_B
(2,2) | DIR_T | (2,3) | (1,3) | [3 -1 3 1] | DIR_R | DIR_B
(2,3) | DIR_T | (2,4) | (1,4) | [3 -1 4 0] | DIR_R | DIR_B
(2,4) | DIR_T | [2 0 5 -1] | [1 1 5 -1] | [3 -1 5 -1] | DIR_R | DIR_B
```

Train example 4: 45 rows, the first 30 shown
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_T | (0,1) | [-1 5 1 7] | (1,1) | DIR_R | DIR_B
(0,1) | DIR_T | (0,2) | [-1 5 2 6] | (1,2) | DIR_R | DIR_B
(0,2) | DIR_T | (0,3) | [-1 5 3 5] | (1,3) | DIR_R | DIR_B
(0,3) | DIR_T | (0,4) | [-1 5 4 4] | (1,4) | DIR_R | DIR_B
(0,4) | DIR_T | (0,5) | [-1 5 5 3] | (1,5) | DIR_R | DIR_B
(0,5) | DIR_T | (0,6) | [-1 5 6 2] | (1,6) | DIR_R | DIR_B
(0,6) | DIR_T | (0,7) | [-1 5 7 1] | (1,7) | DIR_R | DIR_B
(0,7) | DIR_T | (0,8) | [-1 5 8 0] | (1,8) | DIR_R | DIR_B
(0,8) | DIR_T | [0 4 9 -1] | [-1 5 9 -1] | [1 3 9 -1] | DIR_R | DIR_B
(1,0) | DIR_T | (1,1) | (0,1) | (2,1) | DIR_R | DIR_B
(1,1) | DIR_T | (1,2) | (0,2) | (2,2) | DIR_R | DIR_B
(1,2) | DIR_T | (1,3) | (0,3) | (2,3) | DIR_R | DIR_B
(1,3) | DIR_T | (1,4) | (0,4) | (2,4) | DIR_R | DIR_B
(1,4) | DIR_T | (1,5) | (0,5) | (2,5) | DIR_R | DIR_B
(1,5) | DIR_T | (1,6) | (0,6) | (2,6) | DIR_R | DIR_B
(1,6) | DIR_T | (1,7) | (0,7) | (2,7) | DIR_R | DIR_B
(1,7) | DIR_T | (1,8) | (0,8) | (2,8) | DIR_R | DIR_B
(1,8) | DIR_T | [1 3 9 -1] | [0 4 9 -1] | [2 2 9 -1] | DIR_R | DIR_B
(2,0) | DIR_T | (2,1) | (1,1) | (3,1) | DIR_R | DIR_B
(2,1) | DIR_T | (2,2) | (1,2) | (3,2) | DIR_R | DIR_B
(2,2) | DIR_T | (2,3) | (1,3) | (3,3) | DIR_R | DIR_B
(2,3) | DIR_T | (2,4) | (1,4) | (3,4) | DIR_R | DIR_B
(2,4) | DIR_T | (2,5) | (1,5) | (3,5) | DIR_R | DIR_B
(2,5) | DIR_T | (2,6) | (1,6) | (3,6) | DIR_R | DIR_B
(2,6) | DIR_T | (2,7) | (1,7) | (3,7) | DIR_R | DIR_B
(2,7) | DIR_T | (2,8) | (1,8) | (3,8) | DIR_R | DIR_B
(2,8) | DIR_T | [2 2 9 -1] | [1 3 9 -1] | [3 1 9 -1] | DIR_R | DIR_B
(3,0) | DIR_T | (3,1) | (2,1) | (4,1) | DIR_R | DIR_B
(3,1) | DIR_T | (3,2) | (2,2) | (4,2) | DIR_R | DIR_B
(3,2) | DIR_T | (3,3) | (2,3) | (4,3) | DIR_R | DIR_B
```

Train example 5: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_T | (0,1) | [-1 3 1 3] | (1,1) | DIR_R | DIR_B
(0,1) | DIR_T | (0,2) | [-1 3 2 2] | (1,2) | DIR_R | DIR_B
(0,2) | DIR_T | (0,3) | [-1 3 3 1] | (1,3) | DIR_R | DIR_B
(0,3) | DIR_T | (0,4) | [-1 3 4 0] | (1,4) | DIR_R | DIR_B
(0,4) | DIR_T | [0 2 5 -1] | [-1 3 5 -1] | [1 1 5 -1] | DIR_R | DIR_B
(1,0) | DIR_T | (1,1) | (0,1) | (2,1) | DIR_R | DIR_B
(1,1) | DIR_T | (1,2) | (0,2) | (2,2) | DIR_R | DIR_B
(1,2) | DIR_T | (1,3) | (0,3) | (2,3) | DIR_R | DIR_B
(1,3) | DIR_T | (1,4) | (0,4) | (2,4) | DIR_R | DIR_B
(1,4) | DIR_T | [1 1 5 -1] | [0 2 5 -1] | [2 0 5 -1] | DIR_R | DIR_B
(2,0) | DIR_T | (2,1) | (1,1) | [3 -1 1 3] | DIR_R | DIR_B
(2,1) | DIR_T | (2,2) | (1,2) | [3 -1 2 2] | DIR_R | DIR_B
(2,2) | DIR_T | (2,3) | (1,3) | [3 -1 3 1] | DIR_R | DIR_B
(2,3) | DIR_T | (2,4) | (1,4) | [3 -1 4 0] | DIR_R | DIR_B
(2,4) | DIR_T | [2 0 5 -1] | [1 1 5 -1] | [3 -1 5 -1] | DIR_R | DIR_B
```

Train example 6: 28 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_T | (0,1) | [-1 4 1 5] | (1,1) | DIR_R | DIR_B
(0,1) | DIR_T | (0,2) | [-1 4 2 4] | (1,2) | DIR_R | DIR_B
(0,2) | DIR_T | (0,3) | [-1 4 3 3] | (1,3) | DIR_R | DIR_B
(0,3) | DIR_T | (0,4) | [-1 4 4 2] | (1,4) | DIR_R | DIR_B
(0,4) | DIR_T | (0,5) | [-1 4 5 1] | (1,5) | DIR_R | DIR_B
(0,5) | DIR_T | (0,6) | [-1 4 6 0] | (1,6) | DIR_R | DIR_B
(0,6) | DIR_T | [0 3 7 -1] | [-1 4 7 -1] | [1 2 7 -1] | DIR_R | DIR_B
(1,0) | DIR_T | (1,1) | (0,1) | (2,1) | DIR_R | DIR_B
(1,1) | DIR_T | (1,2) | (0,2) | (2,2) | DIR_R | DIR_B
(1,2) | DIR_T | (1,3) | (0,3) | (2,3) | DIR_R | DIR_B
(1,3) | DIR_T | (1,4) | (0,4) | (2,4) | DIR_R | DIR_B
(1,4) | DIR_T | (1,5) | (0,5) | (2,5) | DIR_R | DIR_B
(1,5) | DIR_T | (1,6) | (0,6) | (2,6) | DIR_R | DIR_B
(1,6) | DIR_T | [1 2 7 -1] | [0 3 7 -1] | [2 1 7 -1] | DIR_R | DIR_B
(2,0) | DIR_T | (2,1) | (1,1) | (3,1) | DIR_R | DIR_B
(2,1) | DIR_T | (2,2) | (1,2) | (3,2) | DIR_R | DIR_B
(2,2) | DIR_T | (2,3) | (1,3) | (3,3) | DIR_R | DIR_B
(2,3) | DIR_T | (2,4) | (1,4) | (3,4) | DIR_R | DIR_B
(2,4) | DIR_T | (2,5) | (1,5) | (3,5) | DIR_R | DIR_B
(2,5) | DIR_T | (2,6) | (1,6) | (3,6) | DIR_R | DIR_B
(2,6) | DIR_T | [2 1 7 -1] | [1 2 7 -1] | [3 0 7 -1] | DIR_R | DIR_B
(3,0) | DIR_T | (3,1) | (2,1) | [4 -1 1 5] | DIR_R | DIR_B
(3,1) | DIR_T | (3,2) | (2,2) | [4 -1 2 4] | DIR_R | DIR_B
(3,2) | DIR_T | (3,3) | (2,3) | [4 -1 3 3] | DIR_R | DIR_B
(3,3) | DIR_T | (3,4) | (2,4) | [4 -1 4 2] | DIR_R | DIR_B
(3,4) | DIR_T | (3,5) | (2,5) | [4 -1 5 1] | DIR_R | DIR_B
(3,5) | DIR_T | (3,6) | (2,6) | [4 -1 6 0] | DIR_R | DIR_B
(3,6) | DIR_T | [3 0 7 -1] | [2 1 7 -1] | [4 -1 7 -1] | DIR_R | DIR_B
```


#### &r16, assignment 7 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CW)}
- rows per train example: [15, 15, 15, 15, 45, 15, 28]; test: 72

Train example 0: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_T | [0 2 -1 5] | [-1 3 -1 5] | [1 1 -1 5] | DIR_L | DIR_B
(0,1) | DIR_T | (0,0) | [-1 3 0 4] | (1,0) | DIR_L | DIR_B
(0,2) | DIR_T | (0,1) | [-1 3 1 3] | (1,1) | DIR_L | DIR_B
(0,3) | DIR_T | (0,2) | [-1 3 2 2] | (1,2) | DIR_L | DIR_B
(0,4) | DIR_T | (0,3) | [-1 3 3 1] | (1,3) | DIR_L | DIR_B
(1,0) | DIR_T | [1 1 -1 5] | [0 2 -1 5] | [2 0 -1 5] | DIR_L | DIR_B
(1,1) | DIR_T | (1,0) | (0,0) | (2,0) | DIR_L | DIR_B
(1,2) | DIR_T | (1,1) | (0,1) | (2,1) | DIR_L | DIR_B
(1,3) | DIR_T | (1,2) | (0,2) | (2,2) | DIR_L | DIR_B
(1,4) | DIR_T | (1,3) | (0,3) | (2,3) | DIR_L | DIR_B
(2,0) | DIR_T | [2 0 -1 5] | [1 1 -1 5] | [3 -1 -1 5] | DIR_L | DIR_B
(2,1) | DIR_T | (2,0) | (1,0) | [3 -1 0 4] | DIR_L | DIR_B
(2,2) | DIR_T | (2,1) | (1,1) | [3 -1 1 3] | DIR_L | DIR_B
(2,3) | DIR_T | (2,2) | (1,2) | [3 -1 2 2] | DIR_L | DIR_B
(2,4) | DIR_T | (2,3) | (1,3) | [3 -1 3 1] | DIR_L | DIR_B
```

Train example 1: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_T | [0 2 -1 5] | [-1 3 -1 5] | [1 1 -1 5] | DIR_L | DIR_B
(0,1) | DIR_T | (0,0) | [-1 3 0 4] | (1,0) | DIR_L | DIR_B
(0,2) | DIR_T | (0,1) | [-1 3 1 3] | (1,1) | DIR_L | DIR_B
(0,3) | DIR_T | (0,2) | [-1 3 2 2] | (1,2) | DIR_L | DIR_B
(0,4) | DIR_T | (0,3) | [-1 3 3 1] | (1,3) | DIR_L | DIR_B
(1,0) | DIR_T | [1 1 -1 5] | [0 2 -1 5] | [2 0 -1 5] | DIR_L | DIR_B
(1,1) | DIR_T | (1,0) | (0,0) | (2,0) | DIR_L | DIR_B
(1,2) | DIR_T | (1,1) | (0,1) | (2,1) | DIR_L | DIR_B
(1,3) | DIR_T | (1,2) | (0,2) | (2,2) | DIR_L | DIR_B
(1,4) | DIR_T | (1,3) | (0,3) | (2,3) | DIR_L | DIR_B
(2,0) | DIR_T | [2 0 -1 5] | [1 1 -1 5] | [3 -1 -1 5] | DIR_L | DIR_B
(2,1) | DIR_T | (2,0) | (1,0) | [3 -1 0 4] | DIR_L | DIR_B
(2,2) | DIR_T | (2,1) | (1,1) | [3 -1 1 3] | DIR_L | DIR_B
(2,3) | DIR_T | (2,2) | (1,2) | [3 -1 2 2] | DIR_L | DIR_B
(2,4) | DIR_T | (2,3) | (1,3) | [3 -1 3 1] | DIR_L | DIR_B
```

Train example 2: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_T | [0 2 -1 5] | [-1 3 -1 5] | [1 1 -1 5] | DIR_L | DIR_B
(0,1) | DIR_T | (0,0) | [-1 3 0 4] | (1,0) | DIR_L | DIR_B
(0,2) | DIR_T | (0,1) | [-1 3 1 3] | (1,1) | DIR_L | DIR_B
(0,3) | DIR_T | (0,2) | [-1 3 2 2] | (1,2) | DIR_L | DIR_B
(0,4) | DIR_T | (0,3) | [-1 3 3 1] | (1,3) | DIR_L | DIR_B
(1,0) | DIR_T | [1 1 -1 5] | [0 2 -1 5] | [2 0 -1 5] | DIR_L | DIR_B
(1,1) | DIR_T | (1,0) | (0,0) | (2,0) | DIR_L | DIR_B
(1,2) | DIR_T | (1,1) | (0,1) | (2,1) | DIR_L | DIR_B
(1,3) | DIR_T | (1,2) | (0,2) | (2,2) | DIR_L | DIR_B
(1,4) | DIR_T | (1,3) | (0,3) | (2,3) | DIR_L | DIR_B
(2,0) | DIR_T | [2 0 -1 5] | [1 1 -1 5] | [3 -1 -1 5] | DIR_L | DIR_B
(2,1) | DIR_T | (2,0) | (1,0) | [3 -1 0 4] | DIR_L | DIR_B
(2,2) | DIR_T | (2,1) | (1,1) | [3 -1 1 3] | DIR_L | DIR_B
(2,3) | DIR_T | (2,2) | (1,2) | [3 -1 2 2] | DIR_L | DIR_B
(2,4) | DIR_T | (2,3) | (1,3) | [3 -1 3 1] | DIR_L | DIR_B
```

Train example 3: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_T | [0 2 -1 5] | [-1 3 -1 5] | [1 1 -1 5] | DIR_L | DIR_B
(0,1) | DIR_T | (0,0) | [-1 3 0 4] | (1,0) | DIR_L | DIR_B
(0,2) | DIR_T | (0,1) | [-1 3 1 3] | (1,1) | DIR_L | DIR_B
(0,3) | DIR_T | (0,2) | [-1 3 2 2] | (1,2) | DIR_L | DIR_B
(0,4) | DIR_T | (0,3) | [-1 3 3 1] | (1,3) | DIR_L | DIR_B
(1,0) | DIR_T | [1 1 -1 5] | [0 2 -1 5] | [2 0 -1 5] | DIR_L | DIR_B
(1,1) | DIR_T | (1,0) | (0,0) | (2,0) | DIR_L | DIR_B
(1,2) | DIR_T | (1,1) | (0,1) | (2,1) | DIR_L | DIR_B
(1,3) | DIR_T | (1,2) | (0,2) | (2,2) | DIR_L | DIR_B
(1,4) | DIR_T | (1,3) | (0,3) | (2,3) | DIR_L | DIR_B
(2,0) | DIR_T | [2 0 -1 5] | [1 1 -1 5] | [3 -1 -1 5] | DIR_L | DIR_B
(2,1) | DIR_T | (2,0) | (1,0) | [3 -1 0 4] | DIR_L | DIR_B
(2,2) | DIR_T | (2,1) | (1,1) | [3 -1 1 3] | DIR_L | DIR_B
(2,3) | DIR_T | (2,2) | (1,2) | [3 -1 2 2] | DIR_L | DIR_B
(2,4) | DIR_T | (2,3) | (1,3) | [3 -1 3 1] | DIR_L | DIR_B
```

Train example 4: 45 rows, the first 30 shown
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_T | [0 4 -1 9] | [-1 5 -1 9] | [1 3 -1 9] | DIR_L | DIR_B
(0,1) | DIR_T | (0,0) | [-1 5 0 8] | (1,0) | DIR_L | DIR_B
(0,2) | DIR_T | (0,1) | [-1 5 1 7] | (1,1) | DIR_L | DIR_B
(0,3) | DIR_T | (0,2) | [-1 5 2 6] | (1,2) | DIR_L | DIR_B
(0,4) | DIR_T | (0,3) | [-1 5 3 5] | (1,3) | DIR_L | DIR_B
(0,5) | DIR_T | (0,4) | [-1 5 4 4] | (1,4) | DIR_L | DIR_B
(0,6) | DIR_T | (0,5) | [-1 5 5 3] | (1,5) | DIR_L | DIR_B
(0,7) | DIR_T | (0,6) | [-1 5 6 2] | (1,6) | DIR_L | DIR_B
(0,8) | DIR_T | (0,7) | [-1 5 7 1] | (1,7) | DIR_L | DIR_B
(1,0) | DIR_T | [1 3 -1 9] | [0 4 -1 9] | [2 2 -1 9] | DIR_L | DIR_B
(1,1) | DIR_T | (1,0) | (0,0) | (2,0) | DIR_L | DIR_B
(1,2) | DIR_T | (1,1) | (0,1) | (2,1) | DIR_L | DIR_B
(1,3) | DIR_T | (1,2) | (0,2) | (2,2) | DIR_L | DIR_B
(1,4) | DIR_T | (1,3) | (0,3) | (2,3) | DIR_L | DIR_B
(1,5) | DIR_T | (1,4) | (0,4) | (2,4) | DIR_L | DIR_B
(1,6) | DIR_T | (1,5) | (0,5) | (2,5) | DIR_L | DIR_B
(1,7) | DIR_T | (1,6) | (0,6) | (2,6) | DIR_L | DIR_B
(1,8) | DIR_T | (1,7) | (0,7) | (2,7) | DIR_L | DIR_B
(2,0) | DIR_T | [2 2 -1 9] | [1 3 -1 9] | [3 1 -1 9] | DIR_L | DIR_B
(2,1) | DIR_T | (2,0) | (1,0) | (3,0) | DIR_L | DIR_B
(2,2) | DIR_T | (2,1) | (1,1) | (3,1) | DIR_L | DIR_B
(2,3) | DIR_T | (2,2) | (1,2) | (3,2) | DIR_L | DIR_B
(2,4) | DIR_T | (2,3) | (1,3) | (3,3) | DIR_L | DIR_B
(2,5) | DIR_T | (2,4) | (1,4) | (3,4) | DIR_L | DIR_B
(2,6) | DIR_T | (2,5) | (1,5) | (3,5) | DIR_L | DIR_B
(2,7) | DIR_T | (2,6) | (1,6) | (3,6) | DIR_L | DIR_B
(2,8) | DIR_T | (2,7) | (1,7) | (3,7) | DIR_L | DIR_B
(3,0) | DIR_T | [3 1 -1 9] | [2 2 -1 9] | [4 0 -1 9] | DIR_L | DIR_B
(3,1) | DIR_T | (3,0) | (2,0) | (4,0) | DIR_L | DIR_B
(3,2) | DIR_T | (3,1) | (2,1) | (4,1) | DIR_L | DIR_B
```

Train example 5: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_T | [0 2 -1 5] | [-1 3 -1 5] | [1 1 -1 5] | DIR_L | DIR_B
(0,1) | DIR_T | (0,0) | [-1 3 0 4] | (1,0) | DIR_L | DIR_B
(0,2) | DIR_T | (0,1) | [-1 3 1 3] | (1,1) | DIR_L | DIR_B
(0,3) | DIR_T | (0,2) | [-1 3 2 2] | (1,2) | DIR_L | DIR_B
(0,4) | DIR_T | (0,3) | [-1 3 3 1] | (1,3) | DIR_L | DIR_B
(1,0) | DIR_T | [1 1 -1 5] | [0 2 -1 5] | [2 0 -1 5] | DIR_L | DIR_B
(1,1) | DIR_T | (1,0) | (0,0) | (2,0) | DIR_L | DIR_B
(1,2) | DIR_T | (1,1) | (0,1) | (2,1) | DIR_L | DIR_B
(1,3) | DIR_T | (1,2) | (0,2) | (2,2) | DIR_L | DIR_B
(1,4) | DIR_T | (1,3) | (0,3) | (2,3) | DIR_L | DIR_B
(2,0) | DIR_T | [2 0 -1 5] | [1 1 -1 5] | [3 -1 -1 5] | DIR_L | DIR_B
(2,1) | DIR_T | (2,0) | (1,0) | [3 -1 0 4] | DIR_L | DIR_B
(2,2) | DIR_T | (2,1) | (1,1) | [3 -1 1 3] | DIR_L | DIR_B
(2,3) | DIR_T | (2,2) | (1,2) | [3 -1 2 2] | DIR_L | DIR_B
(2,4) | DIR_T | (2,3) | (1,3) | [3 -1 3 1] | DIR_L | DIR_B
```

Train example 6: 28 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_T | [0 3 -1 7] | [-1 4 -1 7] | [1 2 -1 7] | DIR_L | DIR_B
(0,1) | DIR_T | (0,0) | [-1 4 0 6] | (1,0) | DIR_L | DIR_B
(0,2) | DIR_T | (0,1) | [-1 4 1 5] | (1,1) | DIR_L | DIR_B
(0,3) | DIR_T | (0,2) | [-1 4 2 4] | (1,2) | DIR_L | DIR_B
(0,4) | DIR_T | (0,3) | [-1 4 3 3] | (1,3) | DIR_L | DIR_B
(0,5) | DIR_T | (0,4) | [-1 4 4 2] | (1,4) | DIR_L | DIR_B
(0,6) | DIR_T | (0,5) | [-1 4 5 1] | (1,5) | DIR_L | DIR_B
(1,0) | DIR_T | [1 2 -1 7] | [0 3 -1 7] | [2 1 -1 7] | DIR_L | DIR_B
(1,1) | DIR_T | (1,0) | (0,0) | (2,0) | DIR_L | DIR_B
(1,2) | DIR_T | (1,1) | (0,1) | (2,1) | DIR_L | DIR_B
(1,3) | DIR_T | (1,2) | (0,2) | (2,2) | DIR_L | DIR_B
(1,4) | DIR_T | (1,3) | (0,3) | (2,3) | DIR_L | DIR_B
(1,5) | DIR_T | (1,4) | (0,4) | (2,4) | DIR_L | DIR_B
(1,6) | DIR_T | (1,5) | (0,5) | (2,5) | DIR_L | DIR_B
(2,0) | DIR_T | [2 1 -1 7] | [1 2 -1 7] | [3 0 -1 7] | DIR_L | DIR_B
(2,1) | DIR_T | (2,0) | (1,0) | (3,0) | DIR_L | DIR_B
(2,2) | DIR_T | (2,1) | (1,1) | (3,1) | DIR_L | DIR_B
(2,3) | DIR_T | (2,2) | (1,2) | (3,2) | DIR_L | DIR_B
(2,4) | DIR_T | (2,3) | (1,3) | (3,3) | DIR_L | DIR_B
(2,5) | DIR_T | (2,4) | (1,4) | (3,4) | DIR_L | DIR_B
(2,6) | DIR_T | (2,5) | (1,5) | (3,5) | DIR_L | DIR_B
(3,0) | DIR_T | [3 0 -1 7] | [2 1 -1 7] | [4 -1 -1 7] | DIR_L | DIR_B
(3,1) | DIR_T | (3,0) | (2,0) | [4 -1 0 6] | DIR_L | DIR_B
(3,2) | DIR_T | (3,1) | (2,1) | [4 -1 1 5] | DIR_L | DIR_B
(3,3) | DIR_T | (3,2) | (2,2) | [4 -1 2 4] | DIR_L | DIR_B
(3,4) | DIR_T | (3,3) | (2,3) | [4 -1 3 3] | DIR_L | DIR_B
(3,5) | DIR_T | (3,4) | (2,4) | [4 -1 4 2] | DIR_L | DIR_B
(3,6) | DIR_T | (3,5) | (2,5) | [4 -1 5 1] | DIR_L | DIR_B
```


#### &r16, assignment 8 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CC)}
- rows per train example: [15, 15, 15, 15, 45, 15, 28]; test: 72

Train example 0: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_B | [0 2 -1 5] | [1 1 -1 5] | [-1 3 -1 5] | DIR_L | DIR_T
(0,1) | DIR_B | (0,0) | (1,0) | [-1 3 0 4] | DIR_L | DIR_T
(0,2) | DIR_B | (0,1) | (1,1) | [-1 3 1 3] | DIR_L | DIR_T
(0,3) | DIR_B | (0,2) | (1,2) | [-1 3 2 2] | DIR_L | DIR_T
(0,4) | DIR_B | (0,3) | (1,3) | [-1 3 3 1] | DIR_L | DIR_T
(1,0) | DIR_B | [1 1 -1 5] | [2 0 -1 5] | [0 2 -1 5] | DIR_L | DIR_T
(1,1) | DIR_B | (1,0) | (2,0) | (0,0) | DIR_L | DIR_T
(1,2) | DIR_B | (1,1) | (2,1) | (0,1) | DIR_L | DIR_T
(1,3) | DIR_B | (1,2) | (2,2) | (0,2) | DIR_L | DIR_T
(1,4) | DIR_B | (1,3) | (2,3) | (0,3) | DIR_L | DIR_T
(2,0) | DIR_B | [2 0 -1 5] | [3 -1 -1 5] | [1 1 -1 5] | DIR_L | DIR_T
(2,1) | DIR_B | (2,0) | [3 -1 0 4] | (1,0) | DIR_L | DIR_T
(2,2) | DIR_B | (2,1) | [3 -1 1 3] | (1,1) | DIR_L | DIR_T
(2,3) | DIR_B | (2,2) | [3 -1 2 2] | (1,2) | DIR_L | DIR_T
(2,4) | DIR_B | (2,3) | [3 -1 3 1] | (1,3) | DIR_L | DIR_T
```

Train example 1: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_B | [0 2 -1 5] | [1 1 -1 5] | [-1 3 -1 5] | DIR_L | DIR_T
(0,1) | DIR_B | (0,0) | (1,0) | [-1 3 0 4] | DIR_L | DIR_T
(0,2) | DIR_B | (0,1) | (1,1) | [-1 3 1 3] | DIR_L | DIR_T
(0,3) | DIR_B | (0,2) | (1,2) | [-1 3 2 2] | DIR_L | DIR_T
(0,4) | DIR_B | (0,3) | (1,3) | [-1 3 3 1] | DIR_L | DIR_T
(1,0) | DIR_B | [1 1 -1 5] | [2 0 -1 5] | [0 2 -1 5] | DIR_L | DIR_T
(1,1) | DIR_B | (1,0) | (2,0) | (0,0) | DIR_L | DIR_T
(1,2) | DIR_B | (1,1) | (2,1) | (0,1) | DIR_L | DIR_T
(1,3) | DIR_B | (1,2) | (2,2) | (0,2) | DIR_L | DIR_T
(1,4) | DIR_B | (1,3) | (2,3) | (0,3) | DIR_L | DIR_T
(2,0) | DIR_B | [2 0 -1 5] | [3 -1 -1 5] | [1 1 -1 5] | DIR_L | DIR_T
(2,1) | DIR_B | (2,0) | [3 -1 0 4] | (1,0) | DIR_L | DIR_T
(2,2) | DIR_B | (2,1) | [3 -1 1 3] | (1,1) | DIR_L | DIR_T
(2,3) | DIR_B | (2,2) | [3 -1 2 2] | (1,2) | DIR_L | DIR_T
(2,4) | DIR_B | (2,3) | [3 -1 3 1] | (1,3) | DIR_L | DIR_T
```

Train example 2: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_B | [0 2 -1 5] | [1 1 -1 5] | [-1 3 -1 5] | DIR_L | DIR_T
(0,1) | DIR_B | (0,0) | (1,0) | [-1 3 0 4] | DIR_L | DIR_T
(0,2) | DIR_B | (0,1) | (1,1) | [-1 3 1 3] | DIR_L | DIR_T
(0,3) | DIR_B | (0,2) | (1,2) | [-1 3 2 2] | DIR_L | DIR_T
(0,4) | DIR_B | (0,3) | (1,3) | [-1 3 3 1] | DIR_L | DIR_T
(1,0) | DIR_B | [1 1 -1 5] | [2 0 -1 5] | [0 2 -1 5] | DIR_L | DIR_T
(1,1) | DIR_B | (1,0) | (2,0) | (0,0) | DIR_L | DIR_T
(1,2) | DIR_B | (1,1) | (2,1) | (0,1) | DIR_L | DIR_T
(1,3) | DIR_B | (1,2) | (2,2) | (0,2) | DIR_L | DIR_T
(1,4) | DIR_B | (1,3) | (2,3) | (0,3) | DIR_L | DIR_T
(2,0) | DIR_B | [2 0 -1 5] | [3 -1 -1 5] | [1 1 -1 5] | DIR_L | DIR_T
(2,1) | DIR_B | (2,0) | [3 -1 0 4] | (1,0) | DIR_L | DIR_T
(2,2) | DIR_B | (2,1) | [3 -1 1 3] | (1,1) | DIR_L | DIR_T
(2,3) | DIR_B | (2,2) | [3 -1 2 2] | (1,2) | DIR_L | DIR_T
(2,4) | DIR_B | (2,3) | [3 -1 3 1] | (1,3) | DIR_L | DIR_T
```

Train example 3: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_B | [0 2 -1 5] | [1 1 -1 5] | [-1 3 -1 5] | DIR_L | DIR_T
(0,1) | DIR_B | (0,0) | (1,0) | [-1 3 0 4] | DIR_L | DIR_T
(0,2) | DIR_B | (0,1) | (1,1) | [-1 3 1 3] | DIR_L | DIR_T
(0,3) | DIR_B | (0,2) | (1,2) | [-1 3 2 2] | DIR_L | DIR_T
(0,4) | DIR_B | (0,3) | (1,3) | [-1 3 3 1] | DIR_L | DIR_T
(1,0) | DIR_B | [1 1 -1 5] | [2 0 -1 5] | [0 2 -1 5] | DIR_L | DIR_T
(1,1) | DIR_B | (1,0) | (2,0) | (0,0) | DIR_L | DIR_T
(1,2) | DIR_B | (1,1) | (2,1) | (0,1) | DIR_L | DIR_T
(1,3) | DIR_B | (1,2) | (2,2) | (0,2) | DIR_L | DIR_T
(1,4) | DIR_B | (1,3) | (2,3) | (0,3) | DIR_L | DIR_T
(2,0) | DIR_B | [2 0 -1 5] | [3 -1 -1 5] | [1 1 -1 5] | DIR_L | DIR_T
(2,1) | DIR_B | (2,0) | [3 -1 0 4] | (1,0) | DIR_L | DIR_T
(2,2) | DIR_B | (2,1) | [3 -1 1 3] | (1,1) | DIR_L | DIR_T
(2,3) | DIR_B | (2,2) | [3 -1 2 2] | (1,2) | DIR_L | DIR_T
(2,4) | DIR_B | (2,3) | [3 -1 3 1] | (1,3) | DIR_L | DIR_T
```

Train example 4: 45 rows, the first 30 shown
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_B | [0 4 -1 9] | [1 3 -1 9] | [-1 5 -1 9] | DIR_L | DIR_T
(0,1) | DIR_B | (0,0) | (1,0) | [-1 5 0 8] | DIR_L | DIR_T
(0,2) | DIR_B | (0,1) | (1,1) | [-1 5 1 7] | DIR_L | DIR_T
(0,3) | DIR_B | (0,2) | (1,2) | [-1 5 2 6] | DIR_L | DIR_T
(0,4) | DIR_B | (0,3) | (1,3) | [-1 5 3 5] | DIR_L | DIR_T
(0,5) | DIR_B | (0,4) | (1,4) | [-1 5 4 4] | DIR_L | DIR_T
(0,6) | DIR_B | (0,5) | (1,5) | [-1 5 5 3] | DIR_L | DIR_T
(0,7) | DIR_B | (0,6) | (1,6) | [-1 5 6 2] | DIR_L | DIR_T
(0,8) | DIR_B | (0,7) | (1,7) | [-1 5 7 1] | DIR_L | DIR_T
(1,0) | DIR_B | [1 3 -1 9] | [2 2 -1 9] | [0 4 -1 9] | DIR_L | DIR_T
(1,1) | DIR_B | (1,0) | (2,0) | (0,0) | DIR_L | DIR_T
(1,2) | DIR_B | (1,1) | (2,1) | (0,1) | DIR_L | DIR_T
(1,3) | DIR_B | (1,2) | (2,2) | (0,2) | DIR_L | DIR_T
(1,4) | DIR_B | (1,3) | (2,3) | (0,3) | DIR_L | DIR_T
(1,5) | DIR_B | (1,4) | (2,4) | (0,4) | DIR_L | DIR_T
(1,6) | DIR_B | (1,5) | (2,5) | (0,5) | DIR_L | DIR_T
(1,7) | DIR_B | (1,6) | (2,6) | (0,6) | DIR_L | DIR_T
(1,8) | DIR_B | (1,7) | (2,7) | (0,7) | DIR_L | DIR_T
(2,0) | DIR_B | [2 2 -1 9] | [3 1 -1 9] | [1 3 -1 9] | DIR_L | DIR_T
(2,1) | DIR_B | (2,0) | (3,0) | (1,0) | DIR_L | DIR_T
(2,2) | DIR_B | (2,1) | (3,1) | (1,1) | DIR_L | DIR_T
(2,3) | DIR_B | (2,2) | (3,2) | (1,2) | DIR_L | DIR_T
(2,4) | DIR_B | (2,3) | (3,3) | (1,3) | DIR_L | DIR_T
(2,5) | DIR_B | (2,4) | (3,4) | (1,4) | DIR_L | DIR_T
(2,6) | DIR_B | (2,5) | (3,5) | (1,5) | DIR_L | DIR_T
(2,7) | DIR_B | (2,6) | (3,6) | (1,6) | DIR_L | DIR_T
(2,8) | DIR_B | (2,7) | (3,7) | (1,7) | DIR_L | DIR_T
(3,0) | DIR_B | [3 1 -1 9] | [4 0 -1 9] | [2 2 -1 9] | DIR_L | DIR_T
(3,1) | DIR_B | (3,0) | (4,0) | (2,0) | DIR_L | DIR_T
(3,2) | DIR_B | (3,1) | (4,1) | (2,1) | DIR_L | DIR_T
```

Train example 5: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_B | [0 2 -1 5] | [1 1 -1 5] | [-1 3 -1 5] | DIR_L | DIR_T
(0,1) | DIR_B | (0,0) | (1,0) | [-1 3 0 4] | DIR_L | DIR_T
(0,2) | DIR_B | (0,1) | (1,1) | [-1 3 1 3] | DIR_L | DIR_T
(0,3) | DIR_B | (0,2) | (1,2) | [-1 3 2 2] | DIR_L | DIR_T
(0,4) | DIR_B | (0,3) | (1,3) | [-1 3 3 1] | DIR_L | DIR_T
(1,0) | DIR_B | [1 1 -1 5] | [2 0 -1 5] | [0 2 -1 5] | DIR_L | DIR_T
(1,1) | DIR_B | (1,0) | (2,0) | (0,0) | DIR_L | DIR_T
(1,2) | DIR_B | (1,1) | (2,1) | (0,1) | DIR_L | DIR_T
(1,3) | DIR_B | (1,2) | (2,2) | (0,2) | DIR_L | DIR_T
(1,4) | DIR_B | (1,3) | (2,3) | (0,3) | DIR_L | DIR_T
(2,0) | DIR_B | [2 0 -1 5] | [3 -1 -1 5] | [1 1 -1 5] | DIR_L | DIR_T
(2,1) | DIR_B | (2,0) | [3 -1 0 4] | (1,0) | DIR_L | DIR_T
(2,2) | DIR_B | (2,1) | [3 -1 1 3] | (1,1) | DIR_L | DIR_T
(2,3) | DIR_B | (2,2) | [3 -1 2 2] | (1,2) | DIR_L | DIR_T
(2,4) | DIR_B | (2,3) | [3 -1 3 1] | (1,3) | DIR_L | DIR_T
```

Train example 6: 28 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
(0,0) | DIR_B | [0 3 -1 7] | [1 2 -1 7] | [-1 4 -1 7] | DIR_L | DIR_T
(0,1) | DIR_B | (0,0) | (1,0) | [-1 4 0 6] | DIR_L | DIR_T
(0,2) | DIR_B | (0,1) | (1,1) | [-1 4 1 5] | DIR_L | DIR_T
(0,3) | DIR_B | (0,2) | (1,2) | [-1 4 2 4] | DIR_L | DIR_T
(0,4) | DIR_B | (0,3) | (1,3) | [-1 4 3 3] | DIR_L | DIR_T
(0,5) | DIR_B | (0,4) | (1,4) | [-1 4 4 2] | DIR_L | DIR_T
(0,6) | DIR_B | (0,5) | (1,5) | [-1 4 5 1] | DIR_L | DIR_T
(1,0) | DIR_B | [1 2 -1 7] | [2 1 -1 7] | [0 3 -1 7] | DIR_L | DIR_T
(1,1) | DIR_B | (1,0) | (2,0) | (0,0) | DIR_L | DIR_T
(1,2) | DIR_B | (1,1) | (2,1) | (0,1) | DIR_L | DIR_T
(1,3) | DIR_B | (1,2) | (2,2) | (0,2) | DIR_L | DIR_T
(1,4) | DIR_B | (1,3) | (2,3) | (0,3) | DIR_L | DIR_T
(1,5) | DIR_B | (1,4) | (2,4) | (0,4) | DIR_L | DIR_T
(1,6) | DIR_B | (1,5) | (2,5) | (0,5) | DIR_L | DIR_T
(2,0) | DIR_B | [2 1 -1 7] | [3 0 -1 7] | [1 2 -1 7] | DIR_L | DIR_T
(2,1) | DIR_B | (2,0) | (3,0) | (1,0) | DIR_L | DIR_T
(2,2) | DIR_B | (2,1) | (3,1) | (1,1) | DIR_L | DIR_T
(2,3) | DIR_B | (2,2) | (3,2) | (1,2) | DIR_L | DIR_T
(2,4) | DIR_B | (2,3) | (3,3) | (1,3) | DIR_L | DIR_T
(2,5) | DIR_B | (2,4) | (3,4) | (1,4) | DIR_L | DIR_T
(2,6) | DIR_B | (2,5) | (3,5) | (1,5) | DIR_L | DIR_T
(3,0) | DIR_B | [3 0 -1 7] | [4 -1 -1 7] | [2 1 -1 7] | DIR_L | DIR_T
(3,1) | DIR_B | (3,0) | [4 -1 0 6] | (2,0) | DIR_L | DIR_T
(3,2) | DIR_B | (3,1) | [4 -1 1 5] | (2,1) | DIR_L | DIR_T
(3,3) | DIR_B | (3,2) | [4 -1 2 4] | (2,2) | DIR_L | DIR_T
(3,4) | DIR_B | (3,3) | [4 -1 3 3] | (2,3) | DIR_L | DIR_T
(3,5) | DIR_B | (3,4) | [4 -1 4 2] | (2,4) | DIR_L | DIR_T
(3,6) | DIR_B | (3,5) | [4 -1 5 1] | (2,5) | DIR_L | DIR_T
```

```
RULE &r7 &r2 :0 * [L0] END [&r17]
```

### &r17 (export table 18)

- columns: c0: Box
- depth 3, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 4

#### &r17, assignment 1 of 4

- DET values that differ between the assignments: &r1 = {(DIR_T)}
- rows per train example: [2, 2, 5, 2, 9, 2, 7]; test: 11

Train example 0: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 . 1 .
. . . . .
. . . . .
```
```
c0
(0,1)
(0,3)
```

Train example 1: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 . 1 .
. . . . .
. . . . .
```
```
c0
(0,1)
(0,3)
```

Train example 2: 5 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
. . . . .
. . . . .
```
```
c0
(0,0)
(0,1)
(0,2)
(0,3)
(0,4)
```

Train example 3: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 . 1 .
. . . . .
. . . . .
```
```
c0
(0,1)
(0,3)
```

Train example 4: 9 rows
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
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
```

Train example 5: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 . 1 .
. . . . .
. . . . .
```
```
c0
(0,1)
(0,3)
```

Train example 6: 7 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1
. . . . . . .
. . . . . . .
. . . . . . .
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
```


#### &r17, assignment 2 of 4

- DET values that differ between the assignments: &r1 = {(DIR_B)}
- rows equal to those of assignment 1 at every example

#### &r17, assignment 3 of 4

- DET values that differ between the assignments: &r1 = {(DIR_L)}
- rows equal to those of assignment 1 at every example

#### &r17, assignment 4 of 4

- DET values that differ between the assignments: &r1 = {(DIR_R)}
- rows equal to those of assignment 1 at every example
```
INIT Propagation [:0] SKIP [:1] &r17 :1 * [L0] END [:0] END [:1] L0 END [:2] SKIP [:3] &r16 :4 * [L1] :6 * [L2] :7 * [L3] input :0 L1 :1 * [L4] &r0 :0 L4 END [:0] END [:1] L2 END [:2] L3 END [:3] L1 END [&r18] [&r19] [&r20] [&r21]
```

### &r18 (export table 19)

- columns: c0: Box
- depth 6, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r14; assignments: 8

#### &r18, assignment 1 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CW)}
- rows per train example: [2, 2, 5, 2, 9, 2, 7]; test: 11

Train example 0: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 . 1 .
. . . . .
. . . . .
```
```
c0
(0,1)
(0,3)
```

Train example 1: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 . 1 .
. . . . .
. . . . .
```
```
c0
(0,1)
(0,3)
```

Train example 2: 5 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
. . . . .
. . . . .
```
```
c0
(0,0)
(0,1)
(0,2)
(0,3)
(0,4)
```

Train example 3: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 . 1 .
. . . . .
. . . . .
```
```
c0
(0,1)
(0,3)
```

Train example 4: 9 rows
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
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
```

Train example 5: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 . 1 .
. . . . .
. . . . .
```
```
c0
(0,1)
(0,3)
```

Train example 6: 7 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1
. . . . . . .
. . . . . . .
. . . . . . .
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
```


#### &r18, assignment 2 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 1 at every example

#### &r18, assignment 3 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CW)}
- rows per train example: [3, 3, 9, 3, 25, 3, 16]; test: 36

Train example 0: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 . 1 .
. . 1 . .
. . . . .
```
```
c0
(0,1)
(0,3)
(1,2)
```

Train example 1: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 . 1 .
. . 1 . .
. . . . .
```
```
c0
(0,1)
(0,3)
(1,2)
```

Train example 2: 9 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
. 1 1 1 .
. . 1 . .
```
```
c0
(0,0)
(0,1)
(0,2)
(0,3)
(0,4)
(1,1)
(1,2)
(1,3)
(2,2)
```

Train example 3: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 . 1 .
. . 1 . .
. . . . .
```
```
c0
(0,1)
(0,3)
(1,2)
```

Train example 4: 25 rows
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
. 1 1 1 1 1 1 1 .
. . 1 1 1 1 1 . .
. . . 1 1 1 . . .
. . . . 1 . . . .
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
(1,1)
(1,2)
(1,3)
(1,4)
(1,5)
(1,6)
(1,7)
(2,2)
(2,3)
(2,4)
(2,5)
(2,6)
(3,3)
(3,4)
(3,5)
(4,4)
```

Train example 5: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 . 1 .
. . 1 . .
. . . . .
```
```
c0
(0,1)
(0,3)
(1,2)
```

Train example 6: 16 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1
. 1 1 1 1 1 .
. . 1 1 1 . .
. . . 1 . . .
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
(1,1)
(1,2)
(1,3)
(1,4)
(1,5)
(2,2)
(2,3)
(2,4)
(3,3)
```


#### &r18, assignment 4 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 3 at every example

#### &r18, assignment 5 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CW)}
- rows equal to those of assignment 1 at every example

#### &r18, assignment 6 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 1 at every example

#### &r18, assignment 7 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CW)}
- rows equal to those of assignment 1 at every example

#### &r18, assignment 8 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 1 at every example
### &r21 (export table 20)

- columns: c0: Box, c1: Box, c2: Box
- depth 5, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r14; assignments: 8

#### &r21, assignment 1 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CW)}
- rows per train example: [13, 13, 10, 13, 36, 13, 21]; test: 61

Train example 0: 13 rows
```
c0 | c1 | c2
(1,1) | [1 1 -1 5] | (0,0)
(1,3) | (1,1) | (0,2)
[1 1 5 -1] | (1,3) | (0,4)
(2,1) | [2 0 -1 5] | (1,0)
(2,2) | (2,0) | (1,1)
(2,3) | (2,1) | (1,2)
(2,4) | (2,2) | (1,3)
[2 0 5 -1] | (2,3) | (1,4)
[3 -1 1 3] | [3 -1 -1 5] | (2,0)
[3 -1 2 2] | [3 -1 0 4] | (2,1)
[3 -1 3 1] | [3 -1 1 3] | (2,2)
[3 -1 4 0] | [3 -1 2 2] | (2,3)
[3 -1 5 -1] | [3 -1 3 1] | (2,4)
```

Train example 1: 13 rows
```
c0 | c1 | c2
(1,1) | [1 1 -1 5] | (0,0)
(1,3) | (1,1) | (0,2)
[1 1 5 -1] | (1,3) | (0,4)
(2,1) | [2 0 -1 5] | (1,0)
(2,2) | (2,0) | (1,1)
(2,3) | (2,1) | (1,2)
(2,4) | (2,2) | (1,3)
[2 0 5 -1] | (2,3) | (1,4)
[3 -1 1 3] | [3 -1 -1 5] | (2,0)
[3 -1 2 2] | [3 -1 0 4] | (2,1)
[3 -1 3 1] | [3 -1 1 3] | (2,2)
[3 -1 4 0] | [3 -1 2 2] | (2,3)
[3 -1 5 -1] | [3 -1 3 1] | (2,4)
```

Train example 2: 10 rows
```
c0 | c1 | c2
(2,1) | [2 0 -1 5] | (1,0)
(2,2) | (2,0) | (1,1)
(2,3) | (2,1) | (1,2)
(2,4) | (2,2) | (1,3)
[2 0 5 -1] | (2,3) | (1,4)
[3 -1 1 3] | [3 -1 -1 5] | (2,0)
[3 -1 2 2] | [3 -1 0 4] | (2,1)
[3 -1 3 1] | [3 -1 1 3] | (2,2)
[3 -1 4 0] | [3 -1 2 2] | (2,3)
[3 -1 5 -1] | [3 -1 3 1] | (2,4)
```

Train example 3: 13 rows
```
c0 | c1 | c2
(1,1) | [1 1 -1 5] | (0,0)
(1,3) | (1,1) | (0,2)
[1 1 5 -1] | (1,3) | (0,4)
(2,1) | [2 0 -1 5] | (1,0)
(2,2) | (2,0) | (1,1)
(2,3) | (2,1) | (1,2)
(2,4) | (2,2) | (1,3)
[2 0 5 -1] | (2,3) | (1,4)
[3 -1 1 3] | [3 -1 -1 5] | (2,0)
[3 -1 2 2] | [3 -1 0 4] | (2,1)
[3 -1 3 1] | [3 -1 1 3] | (2,2)
[3 -1 4 0] | [3 -1 2 2] | (2,3)
[3 -1 5 -1] | [3 -1 3 1] | (2,4)
```

Train example 4: 36 rows, the first 30 shown
```
c0 | c1 | c2
(2,1) | [2 2 -1 9] | (1,0)
(2,2) | (2,0) | (1,1)
(2,3) | (2,1) | (1,2)
(2,4) | (2,2) | (1,3)
(2,5) | (2,3) | (1,4)
(2,6) | (2,4) | (1,5)
(2,7) | (2,5) | (1,6)
(2,8) | (2,6) | (1,7)
[2 2 9 -1] | (2,7) | (1,8)
(3,1) | [3 1 -1 9] | (2,0)
(3,2) | (3,0) | (2,1)
(3,3) | (3,1) | (2,2)
(3,4) | (3,2) | (2,3)
(3,5) | (3,3) | (2,4)
(3,6) | (3,4) | (2,5)
(3,7) | (3,5) | (2,6)
(3,8) | (3,6) | (2,7)
[3 1 9 -1] | (3,7) | (2,8)
(4,1) | [4 0 -1 9] | (3,0)
(4,2) | (4,0) | (3,1)
(4,3) | (4,1) | (3,2)
(4,4) | (4,2) | (3,3)
(4,5) | (4,3) | (3,4)
(4,6) | (4,4) | (3,5)
(4,7) | (4,5) | (3,6)
(4,8) | (4,6) | (3,7)
[4 0 9 -1] | (4,7) | (3,8)
[5 -1 1 7] | [5 -1 -1 9] | (4,0)
[5 -1 2 6] | [5 -1 0 8] | (4,1)
[5 -1 3 5] | [5 -1 1 7] | (4,2)
```

Train example 5: 13 rows
```
c0 | c1 | c2
(1,1) | [1 1 -1 5] | (0,0)
(1,3) | (1,1) | (0,2)
[1 1 5 -1] | (1,3) | (0,4)
(2,1) | [2 0 -1 5] | (1,0)
(2,2) | (2,0) | (1,1)
(2,3) | (2,1) | (1,2)
(2,4) | (2,2) | (1,3)
[2 0 5 -1] | (2,3) | (1,4)
[3 -1 1 3] | [3 -1 -1 5] | (2,0)
[3 -1 2 2] | [3 -1 0 4] | (2,1)
[3 -1 3 1] | [3 -1 1 3] | (2,2)
[3 -1 4 0] | [3 -1 2 2] | (2,3)
[3 -1 5 -1] | [3 -1 3 1] | (2,4)
```

Train example 6: 21 rows
```
c0 | c1 | c2
(2,1) | [2 1 -1 7] | (1,0)
(2,2) | (2,0) | (1,1)
(2,3) | (2,1) | (1,2)
(2,4) | (2,2) | (1,3)
(2,5) | (2,3) | (1,4)
(2,6) | (2,4) | (1,5)
[2 1 7 -1] | (2,5) | (1,6)
(3,1) | [3 0 -1 7] | (2,0)
(3,2) | (3,0) | (2,1)
(3,3) | (3,1) | (2,2)
(3,4) | (3,2) | (2,3)
(3,5) | (3,3) | (2,4)
(3,6) | (3,4) | (2,5)
[3 0 7 -1] | (3,5) | (2,6)
[4 -1 1 5] | [4 -1 -1 7] | (3,0)
[4 -1 2 4] | [4 -1 0 6] | (3,1)
[4 -1 3 3] | [4 -1 1 5] | (3,2)
[4 -1 4 2] | [4 -1 2 4] | (3,3)
[4 -1 5 1] | [4 -1 3 3] | (3,4)
[4 -1 6 0] | [4 -1 4 2] | (3,5)
[4 -1 7 -1] | [4 -1 5 1] | (3,6)
```


#### &r21, assignment 2 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CC)}
- rows per train example: [13, 13, 10, 13, 36, 13, 21]; test: 61

Train example 0: 13 rows
```
c0 | c1 | c2
[1 1 -1 5] | (1,1) | (0,0)
(1,1) | (1,3) | (0,2)
(1,3) | [1 1 5 -1] | (0,4)
[2 0 -1 5] | (2,1) | (1,0)
(2,0) | (2,2) | (1,1)
(2,1) | (2,3) | (1,2)
(2,2) | (2,4) | (1,3)
(2,3) | [2 0 5 -1] | (1,4)
[3 -1 -1 5] | [3 -1 1 3] | (2,0)
[3 -1 0 4] | [3 -1 2 2] | (2,1)
[3 -1 1 3] | [3 -1 3 1] | (2,2)
[3 -1 2 2] | [3 -1 4 0] | (2,3)
[3 -1 3 1] | [3 -1 5 -1] | (2,4)
```

Train example 1: 13 rows
```
c0 | c1 | c2
[1 1 -1 5] | (1,1) | (0,0)
(1,1) | (1,3) | (0,2)
(1,3) | [1 1 5 -1] | (0,4)
[2 0 -1 5] | (2,1) | (1,0)
(2,0) | (2,2) | (1,1)
(2,1) | (2,3) | (1,2)
(2,2) | (2,4) | (1,3)
(2,3) | [2 0 5 -1] | (1,4)
[3 -1 -1 5] | [3 -1 1 3] | (2,0)
[3 -1 0 4] | [3 -1 2 2] | (2,1)
[3 -1 1 3] | [3 -1 3 1] | (2,2)
[3 -1 2 2] | [3 -1 4 0] | (2,3)
[3 -1 3 1] | [3 -1 5 -1] | (2,4)
```

Train example 2: 10 rows
```
c0 | c1 | c2
[2 0 -1 5] | (2,1) | (1,0)
(2,0) | (2,2) | (1,1)
(2,1) | (2,3) | (1,2)
(2,2) | (2,4) | (1,3)
(2,3) | [2 0 5 -1] | (1,4)
[3 -1 -1 5] | [3 -1 1 3] | (2,0)
[3 -1 0 4] | [3 -1 2 2] | (2,1)
[3 -1 1 3] | [3 -1 3 1] | (2,2)
[3 -1 2 2] | [3 -1 4 0] | (2,3)
[3 -1 3 1] | [3 -1 5 -1] | (2,4)
```

Train example 3: 13 rows
```
c0 | c1 | c2
[1 1 -1 5] | (1,1) | (0,0)
(1,1) | (1,3) | (0,2)
(1,3) | [1 1 5 -1] | (0,4)
[2 0 -1 5] | (2,1) | (1,0)
(2,0) | (2,2) | (1,1)
(2,1) | (2,3) | (1,2)
(2,2) | (2,4) | (1,3)
(2,3) | [2 0 5 -1] | (1,4)
[3 -1 -1 5] | [3 -1 1 3] | (2,0)
[3 -1 0 4] | [3 -1 2 2] | (2,1)
[3 -1 1 3] | [3 -1 3 1] | (2,2)
[3 -1 2 2] | [3 -1 4 0] | (2,3)
[3 -1 3 1] | [3 -1 5 -1] | (2,4)
```

Train example 4: 36 rows, the first 30 shown
```
c0 | c1 | c2
[2 2 -1 9] | (2,1) | (1,0)
(2,0) | (2,2) | (1,1)
(2,1) | (2,3) | (1,2)
(2,2) | (2,4) | (1,3)
(2,3) | (2,5) | (1,4)
(2,4) | (2,6) | (1,5)
(2,5) | (2,7) | (1,6)
(2,6) | (2,8) | (1,7)
(2,7) | [2 2 9 -1] | (1,8)
[3 1 -1 9] | (3,1) | (2,0)
(3,0) | (3,2) | (2,1)
(3,1) | (3,3) | (2,2)
(3,2) | (3,4) | (2,3)
(3,3) | (3,5) | (2,4)
(3,4) | (3,6) | (2,5)
(3,5) | (3,7) | (2,6)
(3,6) | (3,8) | (2,7)
(3,7) | [3 1 9 -1] | (2,8)
[4 0 -1 9] | (4,1) | (3,0)
(4,0) | (4,2) | (3,1)
(4,1) | (4,3) | (3,2)
(4,2) | (4,4) | (3,3)
(4,3) | (4,5) | (3,4)
(4,4) | (4,6) | (3,5)
(4,5) | (4,7) | (3,6)
(4,6) | (4,8) | (3,7)
(4,7) | [4 0 9 -1] | (3,8)
[5 -1 -1 9] | [5 -1 1 7] | (4,0)
[5 -1 0 8] | [5 -1 2 6] | (4,1)
[5 -1 1 7] | [5 -1 3 5] | (4,2)
```

Train example 5: 13 rows
```
c0 | c1 | c2
[1 1 -1 5] | (1,1) | (0,0)
(1,1) | (1,3) | (0,2)
(1,3) | [1 1 5 -1] | (0,4)
[2 0 -1 5] | (2,1) | (1,0)
(2,0) | (2,2) | (1,1)
(2,1) | (2,3) | (1,2)
(2,2) | (2,4) | (1,3)
(2,3) | [2 0 5 -1] | (1,4)
[3 -1 -1 5] | [3 -1 1 3] | (2,0)
[3 -1 0 4] | [3 -1 2 2] | (2,1)
[3 -1 1 3] | [3 -1 3 1] | (2,2)
[3 -1 2 2] | [3 -1 4 0] | (2,3)
[3 -1 3 1] | [3 -1 5 -1] | (2,4)
```

Train example 6: 21 rows
```
c0 | c1 | c2
[2 1 -1 7] | (2,1) | (1,0)
(2,0) | (2,2) | (1,1)
(2,1) | (2,3) | (1,2)
(2,2) | (2,4) | (1,3)
(2,3) | (2,5) | (1,4)
(2,4) | (2,6) | (1,5)
(2,5) | [2 1 7 -1] | (1,6)
[3 0 -1 7] | (3,1) | (2,0)
(3,0) | (3,2) | (2,1)
(3,1) | (3,3) | (2,2)
(3,2) | (3,4) | (2,3)
(3,3) | (3,5) | (2,4)
(3,4) | (3,6) | (2,5)
(3,5) | [3 0 7 -1] | (2,6)
[4 -1 -1 7] | [4 -1 1 5] | (3,0)
[4 -1 0 6] | [4 -1 2 4] | (3,1)
[4 -1 1 5] | [4 -1 3 3] | (3,2)
[4 -1 2 4] | [4 -1 4 2] | (3,3)
[4 -1 3 3] | [4 -1 5 1] | (3,4)
[4 -1 4 2] | [4 -1 6 0] | (3,5)
[4 -1 5 1] | [4 -1 7 -1] | (3,6)
```


#### &r21, assignment 3 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CW)}
- rows per train example: [13, 13, 10, 13, 36, 13, 21]; test: 61

Train example 0: 13 rows
```
c0 | c1 | c2
[-1 3 -1 5] | [-1 3 1 3] | (0,0)
[-1 3 1 3] | [-1 3 3 1] | (0,2)
[-1 3 3 1] | [-1 3 5 -1] | (0,4)
[0 2 -1 5] | (0,1) | (1,0)
(0,0) | (0,2) | (1,1)
(0,1) | (0,3) | (1,2)
(0,2) | (0,4) | (1,3)
(0,3) | [0 2 5 -1] | (1,4)
[1 1 -1 5] | (1,1) | (2,0)
(1,0) | (1,2) | (2,1)
(1,1) | (1,3) | (2,2)
(1,2) | (1,4) | (2,3)
(1,3) | [1 1 5 -1] | (2,4)
```

Train example 1: 13 rows
```
c0 | c1 | c2
[-1 3 -1 5] | [-1 3 1 3] | (0,0)
[-1 3 1 3] | [-1 3 3 1] | (0,2)
[-1 3 3 1] | [-1 3 5 -1] | (0,4)
[0 2 -1 5] | (0,1) | (1,0)
(0,0) | (0,2) | (1,1)
(0,1) | (0,3) | (1,2)
(0,2) | (0,4) | (1,3)
(0,3) | [0 2 5 -1] | (1,4)
[1 1 -1 5] | (1,1) | (2,0)
(1,0) | (1,2) | (2,1)
(1,1) | (1,3) | (2,2)
(1,2) | (1,4) | (2,3)
(1,3) | [1 1 5 -1] | (2,4)
```

Train example 2: 10 rows
```
c0 | c1 | c2
[0 2 -1 5] | (0,1) | (1,0)
(0,0) | (0,2) | (1,1)
(0,1) | (0,3) | (1,2)
(0,2) | (0,4) | (1,3)
(0,3) | [0 2 5 -1] | (1,4)
[1 1 -1 5] | (1,1) | (2,0)
(1,0) | (1,2) | (2,1)
(1,1) | (1,3) | (2,2)
(1,2) | (1,4) | (2,3)
(1,3) | [1 1 5 -1] | (2,4)
```

Train example 3: 13 rows
```
c0 | c1 | c2
[-1 3 -1 5] | [-1 3 1 3] | (0,0)
[-1 3 1 3] | [-1 3 3 1] | (0,2)
[-1 3 3 1] | [-1 3 5 -1] | (0,4)
[0 2 -1 5] | (0,1) | (1,0)
(0,0) | (0,2) | (1,1)
(0,1) | (0,3) | (1,2)
(0,2) | (0,4) | (1,3)
(0,3) | [0 2 5 -1] | (1,4)
[1 1 -1 5] | (1,1) | (2,0)
(1,0) | (1,2) | (2,1)
(1,1) | (1,3) | (2,2)
(1,2) | (1,4) | (2,3)
(1,3) | [1 1 5 -1] | (2,4)
```

Train example 4: 36 rows, the first 30 shown
```
c0 | c1 | c2
[0 4 -1 9] | (0,1) | (1,0)
(0,0) | (0,2) | (1,1)
(0,1) | (0,3) | (1,2)
(0,2) | (0,4) | (1,3)
(0,3) | (0,5) | (1,4)
(0,4) | (0,6) | (1,5)
(0,5) | (0,7) | (1,6)
(0,6) | (0,8) | (1,7)
(0,7) | [0 4 9 -1] | (1,8)
[1 3 -1 9] | (1,1) | (2,0)
(1,0) | (1,2) | (2,1)
(1,1) | (1,3) | (2,2)
(1,2) | (1,4) | (2,3)
(1,3) | (1,5) | (2,4)
(1,4) | (1,6) | (2,5)
(1,5) | (1,7) | (2,6)
(1,6) | (1,8) | (2,7)
(1,7) | [1 3 9 -1] | (2,8)
[2 2 -1 9] | (2,1) | (3,0)
(2,0) | (2,2) | (3,1)
(2,1) | (2,3) | (3,2)
(2,2) | (2,4) | (3,3)
(2,3) | (2,5) | (3,4)
(2,4) | (2,6) | (3,5)
(2,5) | (2,7) | (3,6)
(2,6) | (2,8) | (3,7)
(2,7) | [2 2 9 -1] | (3,8)
[3 1 -1 9] | (3,1) | (4,0)
(3,0) | (3,2) | (4,1)
(3,1) | (3,3) | (4,2)
```

Train example 5: 13 rows
```
c0 | c1 | c2
[-1 3 -1 5] | [-1 3 1 3] | (0,0)
[-1 3 1 3] | [-1 3 3 1] | (0,2)
[-1 3 3 1] | [-1 3 5 -1] | (0,4)
[0 2 -1 5] | (0,1) | (1,0)
(0,0) | (0,2) | (1,1)
(0,1) | (0,3) | (1,2)
(0,2) | (0,4) | (1,3)
(0,3) | [0 2 5 -1] | (1,4)
[1 1 -1 5] | (1,1) | (2,0)
(1,0) | (1,2) | (2,1)
(1,1) | (1,3) | (2,2)
(1,2) | (1,4) | (2,3)
(1,3) | [1 1 5 -1] | (2,4)
```

Train example 6: 21 rows
```
c0 | c1 | c2
[0 3 -1 7] | (0,1) | (1,0)
(0,0) | (0,2) | (1,1)
(0,1) | (0,3) | (1,2)
(0,2) | (0,4) | (1,3)
(0,3) | (0,5) | (1,4)
(0,4) | (0,6) | (1,5)
(0,5) | [0 3 7 -1] | (1,6)
[1 2 -1 7] | (1,1) | (2,0)
(1,0) | (1,2) | (2,1)
(1,1) | (1,3) | (2,2)
(1,2) | (1,4) | (2,3)
(1,3) | (1,5) | (2,4)
(1,4) | (1,6) | (2,5)
(1,5) | [1 2 7 -1] | (2,6)
[2 1 -1 7] | (2,1) | (3,0)
(2,0) | (2,2) | (3,1)
(2,1) | (2,3) | (3,2)
(2,2) | (2,4) | (3,3)
(2,3) | (2,5) | (3,4)
(2,4) | (2,6) | (3,5)
(2,5) | [2 1 7 -1] | (3,6)
```


#### &r21, assignment 4 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CC)}
- rows per train example: [13, 13, 10, 13, 36, 13, 21]; test: 61

Train example 0: 13 rows
```
c0 | c1 | c2
[-1 3 1 3] | [-1 3 -1 5] | (0,0)
[-1 3 3 1] | [-1 3 1 3] | (0,2)
[-1 3 5 -1] | [-1 3 3 1] | (0,4)
(0,1) | [0 2 -1 5] | (1,0)
(0,2) | (0,0) | (1,1)
(0,3) | (0,1) | (1,2)
(0,4) | (0,2) | (1,3)
[0 2 5 -1] | (0,3) | (1,4)
(1,1) | [1 1 -1 5] | (2,0)
(1,2) | (1,0) | (2,1)
(1,3) | (1,1) | (2,2)
(1,4) | (1,2) | (2,3)
[1 1 5 -1] | (1,3) | (2,4)
```

Train example 1: 13 rows
```
c0 | c1 | c2
[-1 3 1 3] | [-1 3 -1 5] | (0,0)
[-1 3 3 1] | [-1 3 1 3] | (0,2)
[-1 3 5 -1] | [-1 3 3 1] | (0,4)
(0,1) | [0 2 -1 5] | (1,0)
(0,2) | (0,0) | (1,1)
(0,3) | (0,1) | (1,2)
(0,4) | (0,2) | (1,3)
[0 2 5 -1] | (0,3) | (1,4)
(1,1) | [1 1 -1 5] | (2,0)
(1,2) | (1,0) | (2,1)
(1,3) | (1,1) | (2,2)
(1,4) | (1,2) | (2,3)
[1 1 5 -1] | (1,3) | (2,4)
```

Train example 2: 10 rows
```
c0 | c1 | c2
(0,1) | [0 2 -1 5] | (1,0)
(0,2) | (0,0) | (1,1)
(0,3) | (0,1) | (1,2)
(0,4) | (0,2) | (1,3)
[0 2 5 -1] | (0,3) | (1,4)
(1,1) | [1 1 -1 5] | (2,0)
(1,2) | (1,0) | (2,1)
(1,3) | (1,1) | (2,2)
(1,4) | (1,2) | (2,3)
[1 1 5 -1] | (1,3) | (2,4)
```

Train example 3: 13 rows
```
c0 | c1 | c2
[-1 3 1 3] | [-1 3 -1 5] | (0,0)
[-1 3 3 1] | [-1 3 1 3] | (0,2)
[-1 3 5 -1] | [-1 3 3 1] | (0,4)
(0,1) | [0 2 -1 5] | (1,0)
(0,2) | (0,0) | (1,1)
(0,3) | (0,1) | (1,2)
(0,4) | (0,2) | (1,3)
[0 2 5 -1] | (0,3) | (1,4)
(1,1) | [1 1 -1 5] | (2,0)
(1,2) | (1,0) | (2,1)
(1,3) | (1,1) | (2,2)
(1,4) | (1,2) | (2,3)
[1 1 5 -1] | (1,3) | (2,4)
```

Train example 4: 36 rows, the first 30 shown
```
c0 | c1 | c2
(0,1) | [0 4 -1 9] | (1,0)
(0,2) | (0,0) | (1,1)
(0,3) | (0,1) | (1,2)
(0,4) | (0,2) | (1,3)
(0,5) | (0,3) | (1,4)
(0,6) | (0,4) | (1,5)
(0,7) | (0,5) | (1,6)
(0,8) | (0,6) | (1,7)
[0 4 9 -1] | (0,7) | (1,8)
(1,1) | [1 3 -1 9] | (2,0)
(1,2) | (1,0) | (2,1)
(1,3) | (1,1) | (2,2)
(1,4) | (1,2) | (2,3)
(1,5) | (1,3) | (2,4)
(1,6) | (1,4) | (2,5)
(1,7) | (1,5) | (2,6)
(1,8) | (1,6) | (2,7)
[1 3 9 -1] | (1,7) | (2,8)
(2,1) | [2 2 -1 9] | (3,0)
(2,2) | (2,0) | (3,1)
(2,3) | (2,1) | (3,2)
(2,4) | (2,2) | (3,3)
(2,5) | (2,3) | (3,4)
(2,6) | (2,4) | (3,5)
(2,7) | (2,5) | (3,6)
(2,8) | (2,6) | (3,7)
[2 2 9 -1] | (2,7) | (3,8)
(3,1) | [3 1 -1 9] | (4,0)
(3,2) | (3,0) | (4,1)
(3,3) | (3,1) | (4,2)
```

Train example 5: 13 rows
```
c0 | c1 | c2
[-1 3 1 3] | [-1 3 -1 5] | (0,0)
[-1 3 3 1] | [-1 3 1 3] | (0,2)
[-1 3 5 -1] | [-1 3 3 1] | (0,4)
(0,1) | [0 2 -1 5] | (1,0)
(0,2) | (0,0) | (1,1)
(0,3) | (0,1) | (1,2)
(0,4) | (0,2) | (1,3)
[0 2 5 -1] | (0,3) | (1,4)
(1,1) | [1 1 -1 5] | (2,0)
(1,2) | (1,0) | (2,1)
(1,3) | (1,1) | (2,2)
(1,4) | (1,2) | (2,3)
[1 1 5 -1] | (1,3) | (2,4)
```

Train example 6: 21 rows
```
c0 | c1 | c2
(0,1) | [0 3 -1 7] | (1,0)
(0,2) | (0,0) | (1,1)
(0,3) | (0,1) | (1,2)
(0,4) | (0,2) | (1,3)
(0,5) | (0,3) | (1,4)
(0,6) | (0,4) | (1,5)
[0 3 7 -1] | (0,5) | (1,6)
(1,1) | [1 2 -1 7] | (2,0)
(1,2) | (1,0) | (2,1)
(1,3) | (1,1) | (2,2)
(1,4) | (1,2) | (2,3)
(1,5) | (1,3) | (2,4)
(1,6) | (1,4) | (2,5)
[1 2 7 -1] | (1,5) | (2,6)
(2,1) | [2 1 -1 7] | (3,0)
(2,2) | (2,0) | (3,1)
(2,3) | (2,1) | (3,2)
(2,4) | (2,2) | (3,3)
(2,5) | (2,3) | (3,4)
(2,6) | (2,4) | (3,5)
[2 1 7 -1] | (2,5) | (3,6)
```


#### &r21, assignment 5 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CW)}
- rows per train example: [13, 13, 10, 13, 36, 13, 21]; test: 61

Train example 0: 13 rows
```
c0 | c1 | c2
[-1 3 1 3] | (1,1) | (0,0)
[-1 3 3 1] | (1,3) | (0,2)
[-1 3 5 -1] | [1 1 5 -1] | (0,4)
(0,1) | (2,1) | (1,0)
(0,2) | (2,2) | (1,1)
(0,3) | (2,3) | (1,2)
(0,4) | (2,4) | (1,3)
[0 2 5 -1] | [2 0 5 -1] | (1,4)
(1,1) | [3 -1 1 3] | (2,0)
(1,2) | [3 -1 2 2] | (2,1)
(1,3) | [3 -1 3 1] | (2,2)
(1,4) | [3 -1 4 0] | (2,3)
[1 1 5 -1] | [3 -1 5 -1] | (2,4)
```

Train example 1: 13 rows
```
c0 | c1 | c2
[-1 3 1 3] | (1,1) | (0,0)
[-1 3 3 1] | (1,3) | (0,2)
[-1 3 5 -1] | [1 1 5 -1] | (0,4)
(0,1) | (2,1) | (1,0)
(0,2) | (2,2) | (1,1)
(0,3) | (2,3) | (1,2)
(0,4) | (2,4) | (1,3)
[0 2 5 -1] | [2 0 5 -1] | (1,4)
(1,1) | [3 -1 1 3] | (2,0)
(1,2) | [3 -1 2 2] | (2,1)
(1,3) | [3 -1 3 1] | (2,2)
(1,4) | [3 -1 4 0] | (2,3)
[1 1 5 -1] | [3 -1 5 -1] | (2,4)
```

Train example 2: 10 rows
```
c0 | c1 | c2
(0,1) | (2,1) | (1,0)
(0,2) | (2,2) | (1,1)
(0,3) | (2,3) | (1,2)
(0,4) | (2,4) | (1,3)
[0 2 5 -1] | [2 0 5 -1] | (1,4)
(1,1) | [3 -1 1 3] | (2,0)
(1,2) | [3 -1 2 2] | (2,1)
(1,3) | [3 -1 3 1] | (2,2)
(1,4) | [3 -1 4 0] | (2,3)
[1 1 5 -1] | [3 -1 5 -1] | (2,4)
```

Train example 3: 13 rows
```
c0 | c1 | c2
[-1 3 1 3] | (1,1) | (0,0)
[-1 3 3 1] | (1,3) | (0,2)
[-1 3 5 -1] | [1 1 5 -1] | (0,4)
(0,1) | (2,1) | (1,0)
(0,2) | (2,2) | (1,1)
(0,3) | (2,3) | (1,2)
(0,4) | (2,4) | (1,3)
[0 2 5 -1] | [2 0 5 -1] | (1,4)
(1,1) | [3 -1 1 3] | (2,0)
(1,2) | [3 -1 2 2] | (2,1)
(1,3) | [3 -1 3 1] | (2,2)
(1,4) | [3 -1 4 0] | (2,3)
[1 1 5 -1] | [3 -1 5 -1] | (2,4)
```

Train example 4: 36 rows, the first 30 shown
```
c0 | c1 | c2
(0,1) | (2,1) | (1,0)
(0,2) | (2,2) | (1,1)
(0,3) | (2,3) | (1,2)
(0,4) | (2,4) | (1,3)
(0,5) | (2,5) | (1,4)
(0,6) | (2,6) | (1,5)
(0,7) | (2,7) | (1,6)
(0,8) | (2,8) | (1,7)
[0 4 9 -1] | [2 2 9 -1] | (1,8)
(1,1) | (3,1) | (2,0)
(1,2) | (3,2) | (2,1)
(1,3) | (3,3) | (2,2)
(1,4) | (3,4) | (2,3)
(1,5) | (3,5) | (2,4)
(1,6) | (3,6) | (2,5)
(1,7) | (3,7) | (2,6)
(1,8) | (3,8) | (2,7)
[1 3 9 -1] | [3 1 9 -1] | (2,8)
(2,1) | (4,1) | (3,0)
(2,2) | (4,2) | (3,1)
(2,3) | (4,3) | (3,2)
(2,4) | (4,4) | (3,3)
(2,5) | (4,5) | (3,4)
(2,6) | (4,6) | (3,5)
(2,7) | (4,7) | (3,6)
(2,8) | (4,8) | (3,7)
[2 2 9 -1] | [4 0 9 -1] | (3,8)
(3,1) | [5 -1 1 7] | (4,0)
(3,2) | [5 -1 2 6] | (4,1)
(3,3) | [5 -1 3 5] | (4,2)
```

Train example 5: 13 rows
```
c0 | c1 | c2
[-1 3 1 3] | (1,1) | (0,0)
[-1 3 3 1] | (1,3) | (0,2)
[-1 3 5 -1] | [1 1 5 -1] | (0,4)
(0,1) | (2,1) | (1,0)
(0,2) | (2,2) | (1,1)
(0,3) | (2,3) | (1,2)
(0,4) | (2,4) | (1,3)
[0 2 5 -1] | [2 0 5 -1] | (1,4)
(1,1) | [3 -1 1 3] | (2,0)
(1,2) | [3 -1 2 2] | (2,1)
(1,3) | [3 -1 3 1] | (2,2)
(1,4) | [3 -1 4 0] | (2,3)
[1 1 5 -1] | [3 -1 5 -1] | (2,4)
```

Train example 6: 21 rows
```
c0 | c1 | c2
(0,1) | (2,1) | (1,0)
(0,2) | (2,2) | (1,1)
(0,3) | (2,3) | (1,2)
(0,4) | (2,4) | (1,3)
(0,5) | (2,5) | (1,4)
(0,6) | (2,6) | (1,5)
[0 3 7 -1] | [2 1 7 -1] | (1,6)
(1,1) | (3,1) | (2,0)
(1,2) | (3,2) | (2,1)
(1,3) | (3,3) | (2,2)
(1,4) | (3,4) | (2,3)
(1,5) | (3,5) | (2,4)
(1,6) | (3,6) | (2,5)
[1 2 7 -1] | [3 0 7 -1] | (2,6)
(2,1) | [4 -1 1 5] | (3,0)
(2,2) | [4 -1 2 4] | (3,1)
(2,3) | [4 -1 3 3] | (3,2)
(2,4) | [4 -1 4 2] | (3,3)
(2,5) | [4 -1 5 1] | (3,4)
(2,6) | [4 -1 6 0] | (3,5)
[2 1 7 -1] | [4 -1 7 -1] | (3,6)
```


#### &r21, assignment 6 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CC)}
- rows per train example: [13, 13, 10, 13, 36, 13, 21]; test: 61

Train example 0: 13 rows
```
c0 | c1 | c2
(1,1) | [-1 3 1 3] | (0,0)
(1,3) | [-1 3 3 1] | (0,2)
[1 1 5 -1] | [-1 3 5 -1] | (0,4)
(2,1) | (0,1) | (1,0)
(2,2) | (0,2) | (1,1)
(2,3) | (0,3) | (1,2)
(2,4) | (0,4) | (1,3)
[2 0 5 -1] | [0 2 5 -1] | (1,4)
[3 -1 1 3] | (1,1) | (2,0)
[3 -1 2 2] | (1,2) | (2,1)
[3 -1 3 1] | (1,3) | (2,2)
[3 -1 4 0] | (1,4) | (2,3)
[3 -1 5 -1] | [1 1 5 -1] | (2,4)
```

Train example 1: 13 rows
```
c0 | c1 | c2
(1,1) | [-1 3 1 3] | (0,0)
(1,3) | [-1 3 3 1] | (0,2)
[1 1 5 -1] | [-1 3 5 -1] | (0,4)
(2,1) | (0,1) | (1,0)
(2,2) | (0,2) | (1,1)
(2,3) | (0,3) | (1,2)
(2,4) | (0,4) | (1,3)
[2 0 5 -1] | [0 2 5 -1] | (1,4)
[3 -1 1 3] | (1,1) | (2,0)
[3 -1 2 2] | (1,2) | (2,1)
[3 -1 3 1] | (1,3) | (2,2)
[3 -1 4 0] | (1,4) | (2,3)
[3 -1 5 -1] | [1 1 5 -1] | (2,4)
```

Train example 2: 10 rows
```
c0 | c1 | c2
(2,1) | (0,1) | (1,0)
(2,2) | (0,2) | (1,1)
(2,3) | (0,3) | (1,2)
(2,4) | (0,4) | (1,3)
[2 0 5 -1] | [0 2 5 -1] | (1,4)
[3 -1 1 3] | (1,1) | (2,0)
[3 -1 2 2] | (1,2) | (2,1)
[3 -1 3 1] | (1,3) | (2,2)
[3 -1 4 0] | (1,4) | (2,3)
[3 -1 5 -1] | [1 1 5 -1] | (2,4)
```

Train example 3: 13 rows
```
c0 | c1 | c2
(1,1) | [-1 3 1 3] | (0,0)
(1,3) | [-1 3 3 1] | (0,2)
[1 1 5 -1] | [-1 3 5 -1] | (0,4)
(2,1) | (0,1) | (1,0)
(2,2) | (0,2) | (1,1)
(2,3) | (0,3) | (1,2)
(2,4) | (0,4) | (1,3)
[2 0 5 -1] | [0 2 5 -1] | (1,4)
[3 -1 1 3] | (1,1) | (2,0)
[3 -1 2 2] | (1,2) | (2,1)
[3 -1 3 1] | (1,3) | (2,2)
[3 -1 4 0] | (1,4) | (2,3)
[3 -1 5 -1] | [1 1 5 -1] | (2,4)
```

Train example 4: 36 rows, the first 30 shown
```
c0 | c1 | c2
(2,1) | (0,1) | (1,0)
(2,2) | (0,2) | (1,1)
(2,3) | (0,3) | (1,2)
(2,4) | (0,4) | (1,3)
(2,5) | (0,5) | (1,4)
(2,6) | (0,6) | (1,5)
(2,7) | (0,7) | (1,6)
(2,8) | (0,8) | (1,7)
[2 2 9 -1] | [0 4 9 -1] | (1,8)
(3,1) | (1,1) | (2,0)
(3,2) | (1,2) | (2,1)
(3,3) | (1,3) | (2,2)
(3,4) | (1,4) | (2,3)
(3,5) | (1,5) | (2,4)
(3,6) | (1,6) | (2,5)
(3,7) | (1,7) | (2,6)
(3,8) | (1,8) | (2,7)
[3 1 9 -1] | [1 3 9 -1] | (2,8)
(4,1) | (2,1) | (3,0)
(4,2) | (2,2) | (3,1)
(4,3) | (2,3) | (3,2)
(4,4) | (2,4) | (3,3)
(4,5) | (2,5) | (3,4)
(4,6) | (2,6) | (3,5)
(4,7) | (2,7) | (3,6)
(4,8) | (2,8) | (3,7)
[4 0 9 -1] | [2 2 9 -1] | (3,8)
[5 -1 1 7] | (3,1) | (4,0)
[5 -1 2 6] | (3,2) | (4,1)
[5 -1 3 5] | (3,3) | (4,2)
```

Train example 5: 13 rows
```
c0 | c1 | c2
(1,1) | [-1 3 1 3] | (0,0)
(1,3) | [-1 3 3 1] | (0,2)
[1 1 5 -1] | [-1 3 5 -1] | (0,4)
(2,1) | (0,1) | (1,0)
(2,2) | (0,2) | (1,1)
(2,3) | (0,3) | (1,2)
(2,4) | (0,4) | (1,3)
[2 0 5 -1] | [0 2 5 -1] | (1,4)
[3 -1 1 3] | (1,1) | (2,0)
[3 -1 2 2] | (1,2) | (2,1)
[3 -1 3 1] | (1,3) | (2,2)
[3 -1 4 0] | (1,4) | (2,3)
[3 -1 5 -1] | [1 1 5 -1] | (2,4)
```

Train example 6: 21 rows
```
c0 | c1 | c2
(2,1) | (0,1) | (1,0)
(2,2) | (0,2) | (1,1)
(2,3) | (0,3) | (1,2)
(2,4) | (0,4) | (1,3)
(2,5) | (0,5) | (1,4)
(2,6) | (0,6) | (1,5)
[2 1 7 -1] | [0 3 7 -1] | (1,6)
(3,1) | (1,1) | (2,0)
(3,2) | (1,2) | (2,1)
(3,3) | (1,3) | (2,2)
(3,4) | (1,4) | (2,3)
(3,5) | (1,5) | (2,4)
(3,6) | (1,6) | (2,5)
[3 0 7 -1] | [1 2 7 -1] | (2,6)
[4 -1 1 5] | (2,1) | (3,0)
[4 -1 2 4] | (2,2) | (3,1)
[4 -1 3 3] | (2,3) | (3,2)
[4 -1 4 2] | (2,4) | (3,3)
[4 -1 5 1] | (2,5) | (3,4)
[4 -1 6 0] | (2,6) | (3,5)
[4 -1 7 -1] | [2 1 7 -1] | (3,6)
```


#### &r21, assignment 7 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CW)}
- rows per train example: [13, 13, 10, 13, 36, 13, 21]; test: 61

Train example 0: 13 rows
```
c0 | c1 | c2
[1 1 -1 5] | [-1 3 -1 5] | (0,0)
(1,1) | [-1 3 1 3] | (0,2)
(1,3) | [-1 3 3 1] | (0,4)
[2 0 -1 5] | [0 2 -1 5] | (1,0)
(2,0) | (0,0) | (1,1)
(2,1) | (0,1) | (1,2)
(2,2) | (0,2) | (1,3)
(2,3) | (0,3) | (1,4)
[3 -1 -1 5] | [1 1 -1 5] | (2,0)
[3 -1 0 4] | (1,0) | (2,1)
[3 -1 1 3] | (1,1) | (2,2)
[3 -1 2 2] | (1,2) | (2,3)
[3 -1 3 1] | (1,3) | (2,4)
```

Train example 1: 13 rows
```
c0 | c1 | c2
[1 1 -1 5] | [-1 3 -1 5] | (0,0)
(1,1) | [-1 3 1 3] | (0,2)
(1,3) | [-1 3 3 1] | (0,4)
[2 0 -1 5] | [0 2 -1 5] | (1,0)
(2,0) | (0,0) | (1,1)
(2,1) | (0,1) | (1,2)
(2,2) | (0,2) | (1,3)
(2,3) | (0,3) | (1,4)
[3 -1 -1 5] | [1 1 -1 5] | (2,0)
[3 -1 0 4] | (1,0) | (2,1)
[3 -1 1 3] | (1,1) | (2,2)
[3 -1 2 2] | (1,2) | (2,3)
[3 -1 3 1] | (1,3) | (2,4)
```

Train example 2: 10 rows
```
c0 | c1 | c2
[2 0 -1 5] | [0 2 -1 5] | (1,0)
(2,0) | (0,0) | (1,1)
(2,1) | (0,1) | (1,2)
(2,2) | (0,2) | (1,3)
(2,3) | (0,3) | (1,4)
[3 -1 -1 5] | [1 1 -1 5] | (2,0)
[3 -1 0 4] | (1,0) | (2,1)
[3 -1 1 3] | (1,1) | (2,2)
[3 -1 2 2] | (1,2) | (2,3)
[3 -1 3 1] | (1,3) | (2,4)
```

Train example 3: 13 rows
```
c0 | c1 | c2
[1 1 -1 5] | [-1 3 -1 5] | (0,0)
(1,1) | [-1 3 1 3] | (0,2)
(1,3) | [-1 3 3 1] | (0,4)
[2 0 -1 5] | [0 2 -1 5] | (1,0)
(2,0) | (0,0) | (1,1)
(2,1) | (0,1) | (1,2)
(2,2) | (0,2) | (1,3)
(2,3) | (0,3) | (1,4)
[3 -1 -1 5] | [1 1 -1 5] | (2,0)
[3 -1 0 4] | (1,0) | (2,1)
[3 -1 1 3] | (1,1) | (2,2)
[3 -1 2 2] | (1,2) | (2,3)
[3 -1 3 1] | (1,3) | (2,4)
```

Train example 4: 36 rows, the first 30 shown
```
c0 | c1 | c2
[2 2 -1 9] | [0 4 -1 9] | (1,0)
(2,0) | (0,0) | (1,1)
(2,1) | (0,1) | (1,2)
(2,2) | (0,2) | (1,3)
(2,3) | (0,3) | (1,4)
(2,4) | (0,4) | (1,5)
(2,5) | (0,5) | (1,6)
(2,6) | (0,6) | (1,7)
(2,7) | (0,7) | (1,8)
[3 1 -1 9] | [1 3 -1 9] | (2,0)
(3,0) | (1,0) | (2,1)
(3,1) | (1,1) | (2,2)
(3,2) | (1,2) | (2,3)
(3,3) | (1,3) | (2,4)
(3,4) | (1,4) | (2,5)
(3,5) | (1,5) | (2,6)
(3,6) | (1,6) | (2,7)
(3,7) | (1,7) | (2,8)
[4 0 -1 9] | [2 2 -1 9] | (3,0)
(4,0) | (2,0) | (3,1)
(4,1) | (2,1) | (3,2)
(4,2) | (2,2) | (3,3)
(4,3) | (2,3) | (3,4)
(4,4) | (2,4) | (3,5)
(4,5) | (2,5) | (3,6)
(4,6) | (2,6) | (3,7)
(4,7) | (2,7) | (3,8)
[5 -1 -1 9] | [3 1 -1 9] | (4,0)
[5 -1 0 8] | (3,0) | (4,1)
[5 -1 1 7] | (3,1) | (4,2)
```

Train example 5: 13 rows
```
c0 | c1 | c2
[1 1 -1 5] | [-1 3 -1 5] | (0,0)
(1,1) | [-1 3 1 3] | (0,2)
(1,3) | [-1 3 3 1] | (0,4)
[2 0 -1 5] | [0 2 -1 5] | (1,0)
(2,0) | (0,0) | (1,1)
(2,1) | (0,1) | (1,2)
(2,2) | (0,2) | (1,3)
(2,3) | (0,3) | (1,4)
[3 -1 -1 5] | [1 1 -1 5] | (2,0)
[3 -1 0 4] | (1,0) | (2,1)
[3 -1 1 3] | (1,1) | (2,2)
[3 -1 2 2] | (1,2) | (2,3)
[3 -1 3 1] | (1,3) | (2,4)
```

Train example 6: 21 rows
```
c0 | c1 | c2
[2 1 -1 7] | [0 3 -1 7] | (1,0)
(2,0) | (0,0) | (1,1)
(2,1) | (0,1) | (1,2)
(2,2) | (0,2) | (1,3)
(2,3) | (0,3) | (1,4)
(2,4) | (0,4) | (1,5)
(2,5) | (0,5) | (1,6)
[3 0 -1 7] | [1 2 -1 7] | (2,0)
(3,0) | (1,0) | (2,1)
(3,1) | (1,1) | (2,2)
(3,2) | (1,2) | (2,3)
(3,3) | (1,3) | (2,4)
(3,4) | (1,4) | (2,5)
(3,5) | (1,5) | (2,6)
[4 -1 -1 7] | [2 1 -1 7] | (3,0)
[4 -1 0 6] | (2,0) | (3,1)
[4 -1 1 5] | (2,1) | (3,2)
[4 -1 2 4] | (2,2) | (3,3)
[4 -1 3 3] | (2,3) | (3,4)
[4 -1 4 2] | (2,4) | (3,5)
[4 -1 5 1] | (2,5) | (3,6)
```


#### &r21, assignment 8 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CC)}
- rows per train example: [13, 13, 10, 13, 36, 13, 21]; test: 61

Train example 0: 13 rows
```
c0 | c1 | c2
[-1 3 -1 5] | [1 1 -1 5] | (0,0)
[-1 3 1 3] | (1,1) | (0,2)
[-1 3 3 1] | (1,3) | (0,4)
[0 2 -1 5] | [2 0 -1 5] | (1,0)
(0,0) | (2,0) | (1,1)
(0,1) | (2,1) | (1,2)
(0,2) | (2,2) | (1,3)
(0,3) | (2,3) | (1,4)
[1 1 -1 5] | [3 -1 -1 5] | (2,0)
(1,0) | [3 -1 0 4] | (2,1)
(1,1) | [3 -1 1 3] | (2,2)
(1,2) | [3 -1 2 2] | (2,3)
(1,3) | [3 -1 3 1] | (2,4)
```

Train example 1: 13 rows
```
c0 | c1 | c2
[-1 3 -1 5] | [1 1 -1 5] | (0,0)
[-1 3 1 3] | (1,1) | (0,2)
[-1 3 3 1] | (1,3) | (0,4)
[0 2 -1 5] | [2 0 -1 5] | (1,0)
(0,0) | (2,0) | (1,1)
(0,1) | (2,1) | (1,2)
(0,2) | (2,2) | (1,3)
(0,3) | (2,3) | (1,4)
[1 1 -1 5] | [3 -1 -1 5] | (2,0)
(1,0) | [3 -1 0 4] | (2,1)
(1,1) | [3 -1 1 3] | (2,2)
(1,2) | [3 -1 2 2] | (2,3)
(1,3) | [3 -1 3 1] | (2,4)
```

Train example 2: 10 rows
```
c0 | c1 | c2
[0 2 -1 5] | [2 0 -1 5] | (1,0)
(0,0) | (2,0) | (1,1)
(0,1) | (2,1) | (1,2)
(0,2) | (2,2) | (1,3)
(0,3) | (2,3) | (1,4)
[1 1 -1 5] | [3 -1 -1 5] | (2,0)
(1,0) | [3 -1 0 4] | (2,1)
(1,1) | [3 -1 1 3] | (2,2)
(1,2) | [3 -1 2 2] | (2,3)
(1,3) | [3 -1 3 1] | (2,4)
```

Train example 3: 13 rows
```
c0 | c1 | c2
[-1 3 -1 5] | [1 1 -1 5] | (0,0)
[-1 3 1 3] | (1,1) | (0,2)
[-1 3 3 1] | (1,3) | (0,4)
[0 2 -1 5] | [2 0 -1 5] | (1,0)
(0,0) | (2,0) | (1,1)
(0,1) | (2,1) | (1,2)
(0,2) | (2,2) | (1,3)
(0,3) | (2,3) | (1,4)
[1 1 -1 5] | [3 -1 -1 5] | (2,0)
(1,0) | [3 -1 0 4] | (2,1)
(1,1) | [3 -1 1 3] | (2,2)
(1,2) | [3 -1 2 2] | (2,3)
(1,3) | [3 -1 3 1] | (2,4)
```

Train example 4: 36 rows, the first 30 shown
```
c0 | c1 | c2
[0 4 -1 9] | [2 2 -1 9] | (1,0)
(0,0) | (2,0) | (1,1)
(0,1) | (2,1) | (1,2)
(0,2) | (2,2) | (1,3)
(0,3) | (2,3) | (1,4)
(0,4) | (2,4) | (1,5)
(0,5) | (2,5) | (1,6)
(0,6) | (2,6) | (1,7)
(0,7) | (2,7) | (1,8)
[1 3 -1 9] | [3 1 -1 9] | (2,0)
(1,0) | (3,0) | (2,1)
(1,1) | (3,1) | (2,2)
(1,2) | (3,2) | (2,3)
(1,3) | (3,3) | (2,4)
(1,4) | (3,4) | (2,5)
(1,5) | (3,5) | (2,6)
(1,6) | (3,6) | (2,7)
(1,7) | (3,7) | (2,8)
[2 2 -1 9] | [4 0 -1 9] | (3,0)
(2,0) | (4,0) | (3,1)
(2,1) | (4,1) | (3,2)
(2,2) | (4,2) | (3,3)
(2,3) | (4,3) | (3,4)
(2,4) | (4,4) | (3,5)
(2,5) | (4,5) | (3,6)
(2,6) | (4,6) | (3,7)
(2,7) | (4,7) | (3,8)
[3 1 -1 9] | [5 -1 -1 9] | (4,0)
(3,0) | [5 -1 0 8] | (4,1)
(3,1) | [5 -1 1 7] | (4,2)
```

Train example 5: 13 rows
```
c0 | c1 | c2
[-1 3 -1 5] | [1 1 -1 5] | (0,0)
[-1 3 1 3] | (1,1) | (0,2)
[-1 3 3 1] | (1,3) | (0,4)
[0 2 -1 5] | [2 0 -1 5] | (1,0)
(0,0) | (2,0) | (1,1)
(0,1) | (2,1) | (1,2)
(0,2) | (2,2) | (1,3)
(0,3) | (2,3) | (1,4)
[1 1 -1 5] | [3 -1 -1 5] | (2,0)
(1,0) | [3 -1 0 4] | (2,1)
(1,1) | [3 -1 1 3] | (2,2)
(1,2) | [3 -1 2 2] | (2,3)
(1,3) | [3 -1 3 1] | (2,4)
```

Train example 6: 21 rows
```
c0 | c1 | c2
[0 3 -1 7] | [2 1 -1 7] | (1,0)
(0,0) | (2,0) | (1,1)
(0,1) | (2,1) | (1,2)
(0,2) | (2,2) | (1,3)
(0,3) | (2,3) | (1,4)
(0,4) | (2,4) | (1,5)
(0,5) | (2,5) | (1,6)
[1 2 -1 7] | [3 0 -1 7] | (2,0)
(1,0) | (3,0) | (2,1)
(1,1) | (3,1) | (2,2)
(1,2) | (3,2) | (2,3)
(1,3) | (3,3) | (2,4)
(1,4) | (3,4) | (2,5)
(1,5) | (3,5) | (2,6)
[2 1 -1 7] | [4 -1 -1 7] | (3,0)
(2,0) | [4 -1 0 6] | (3,1)
(2,1) | [4 -1 1 5] | (3,2)
(2,2) | [4 -1 2 4] | (3,3)
(2,3) | [4 -1 3 3] | (3,4)
(2,4) | [4 -1 4 2] | (3,5)
(2,5) | [4 -1 5 1] | (3,6)
```

```
RULE &r18 :1 * [L0] NOT &r17 :0 L0 END [&r22]
```

### &r22 (export table 21)

- columns: c0: Box
- depth 7, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r14; assignments: 8

#### &r22, assignment 1 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CW)}
- rows per train example: [0, 0, 0, 0, 0, 0, 0]; test: 0


#### &r22, assignment 2 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CC)}
- empty at every example

#### &r22, assignment 3 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CW)}
- rows per train example: [1, 1, 4, 1, 16, 1, 9]; test: 25

Train example 0: 1 row
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . .
. . 1 . .
. . . . .
```
```
c0
(1,2)
```

Train example 1: 1 row
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . .
. . 1 . .
. . . . .
```
```
c0
(1,2)
```

Train example 2: 4 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . .
. 1 1 1 .
. . 1 . .
```
```
c0
(1,1)
(1,2)
(1,3)
(2,2)
```

Train example 3: 1 row
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . .
. . 1 . .
. . . . .
```
```
c0
(1,2)
```

Train example 4: 16 rows
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . .
. 1 1 1 1 1 1 1 .
. . 1 1 1 1 1 . .
. . . 1 1 1 . . .
. . . . 1 . . . .
```
```
c0
(1,1)
(1,2)
(1,3)
(1,4)
(1,5)
(1,6)
(1,7)
(2,2)
(2,3)
(2,4)
(2,5)
(2,6)
(3,3)
(3,4)
(3,5)
(4,4)
```

Train example 5: 1 row
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . .
. . 1 . .
. . . . .
```
```
c0
(1,2)
```

Train example 6: 9 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . .
. 1 1 1 1 1 .
. . 1 1 1 . .
. . . 1 . . .
```
```
c0
(1,1)
(1,2)
(1,3)
(1,4)
(1,5)
(2,2)
(2,3)
(2,4)
(3,3)
```


#### &r22, assignment 4 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 3 at every example

#### &r22, assignment 5 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CW)}
- empty at every example

#### &r22, assignment 6 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CC)}
- empty at every example

#### &r22, assignment 7 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CW)}
- empty at every example

#### &r22, assignment 8 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CC)}
- empty at every example
```
RULE &r22 :0 * [L0] &r15 :1 * [L1] :3 * [L2] diag_dirs :0 * [L3] :2 L1 :3 L2 margin :0 L0 :1 L1 :2 * [L4] jump :0 L0 :1 L3 :2 L4 :3 * [L5] END [&r23]
```

### &r23 (export table 22)

- columns: c0: DiagDir, c1: Box, c2: Number, c3: Dir, c4: Box, c5: Dir
- depth 8, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r14; assignments: 8

#### &r23, assignment 1 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CW)}
- rows per train example: [0, 0, 0, 0, 0, 0, 0]; test: 0


#### &r23, assignment 2 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CC)}
- empty at every example

#### &r23, assignment 3 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CW)}
- rows per train example: [1, 1, 4, 1, 16, 1, 9]; test: 25

Train example 0: 1 row
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . .
. . 1 . .
. . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
DIAG_TL | (1,2) | 1 | DIR_T | (0,1) | DIR_L
```

Train example 1: 1 row
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . .
. . 1 . .
. . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
DIAG_TL | (1,2) | 1 | DIR_T | (0,1) | DIR_L
```

Train example 2: 4 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . .
. 1 1 1 .
. . 2 . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
DIAG_TL | (1,1) | 1 | DIR_T | (0,0) | DIR_L
DIAG_TL | (1,2) | 1 | DIR_T | (0,1) | DIR_L
DIAG_TL | (1,3) | 1 | DIR_T | (0,2) | DIR_L
DIAG_TL | (2,2) | 2 | DIR_T | (0,0) | DIR_L
```

Train example 3: 1 row
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . .
. . 1 . .
. . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
DIAG_TL | (1,2) | 1 | DIR_T | (0,1) | DIR_L
```

Train example 4: 16 rows
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . . . . .
. 1 1 1 1 1 1 1 .
. . 2 2 2 2 2 . .
. . . 3 3 3 . . .
. . . . 4 . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
DIAG_TL | (1,1) | 1 | DIR_T | (0,0) | DIR_L
DIAG_TL | (1,2) | 1 | DIR_T | (0,1) | DIR_L
DIAG_TL | (1,3) | 1 | DIR_T | (0,2) | DIR_L
DIAG_TL | (1,4) | 1 | DIR_T | (0,3) | DIR_L
DIAG_TL | (1,5) | 1 | DIR_T | (0,4) | DIR_L
DIAG_TL | (1,6) | 1 | DIR_T | (0,5) | DIR_L
DIAG_TL | (1,7) | 1 | DIR_T | (0,6) | DIR_L
DIAG_TL | (2,2) | 2 | DIR_T | (0,0) | DIR_L
DIAG_TL | (2,3) | 2 | DIR_T | (0,1) | DIR_L
DIAG_TL | (2,4) | 2 | DIR_T | (0,2) | DIR_L
DIAG_TL | (2,5) | 2 | DIR_T | (0,3) | DIR_L
DIAG_TL | (2,6) | 2 | DIR_T | (0,4) | DIR_L
DIAG_TL | (3,3) | 3 | DIR_T | (0,0) | DIR_L
DIAG_TL | (3,4) | 3 | DIR_T | (0,1) | DIR_L
DIAG_TL | (3,5) | 3 | DIR_T | (0,2) | DIR_L
DIAG_TL | (4,4) | 4 | DIR_T | (0,0) | DIR_L
```

Train example 5: 1 row
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . .
. . 1 . .
. . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
DIAG_TL | (1,2) | 1 | DIR_T | (0,1) | DIR_L
```

Train example 6: 9 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . . .
. 1 1 1 1 1 .
. . 2 2 2 . .
. . . 3 . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
DIAG_TL | (1,1) | 1 | DIR_T | (0,0) | DIR_L
DIAG_TL | (1,2) | 1 | DIR_T | (0,1) | DIR_L
DIAG_TL | (1,3) | 1 | DIR_T | (0,2) | DIR_L
DIAG_TL | (1,4) | 1 | DIR_T | (0,3) | DIR_L
DIAG_TL | (1,5) | 1 | DIR_T | (0,4) | DIR_L
DIAG_TL | (2,2) | 2 | DIR_T | (0,0) | DIR_L
DIAG_TL | (2,3) | 2 | DIR_T | (0,1) | DIR_L
DIAG_TL | (2,4) | 2 | DIR_T | (0,2) | DIR_L
DIAG_TL | (3,3) | 3 | DIR_T | (0,0) | DIR_L
```


#### &r23, assignment 4 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CC)}
- rows per train example: [1, 1, 4, 1, 16, 1, 9]; test: 25

Train example 0: 1 row
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . .
. . 1 . .
. . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
DIAG_TR | (1,2) | 1 | DIR_T | (0,3) | DIR_R
```

Train example 1: 1 row
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . .
. . 1 . .
. . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
DIAG_TR | (1,2) | 1 | DIR_T | (0,3) | DIR_R
```

Train example 2: 4 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . .
. 1 1 1 .
. . 2 . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
DIAG_TR | (1,1) | 1 | DIR_T | (0,2) | DIR_R
DIAG_TR | (1,2) | 1 | DIR_T | (0,3) | DIR_R
DIAG_TR | (1,3) | 1 | DIR_T | (0,4) | DIR_R
DIAG_TR | (2,2) | 2 | DIR_T | (0,4) | DIR_R
```

Train example 3: 1 row
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . .
. . 1 . .
. . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
DIAG_TR | (1,2) | 1 | DIR_T | (0,3) | DIR_R
```

Train example 4: 16 rows
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . . . . .
. 1 1 1 1 1 1 1 .
. . 2 2 2 2 2 . .
. . . 3 3 3 . . .
. . . . 4 . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
DIAG_TR | (1,1) | 1 | DIR_T | (0,2) | DIR_R
DIAG_TR | (1,2) | 1 | DIR_T | (0,3) | DIR_R
DIAG_TR | (1,3) | 1 | DIR_T | (0,4) | DIR_R
DIAG_TR | (1,4) | 1 | DIR_T | (0,5) | DIR_R
DIAG_TR | (1,5) | 1 | DIR_T | (0,6) | DIR_R
DIAG_TR | (1,6) | 1 | DIR_T | (0,7) | DIR_R
DIAG_TR | (1,7) | 1 | DIR_T | (0,8) | DIR_R
DIAG_TR | (2,2) | 2 | DIR_T | (0,4) | DIR_R
DIAG_TR | (2,3) | 2 | DIR_T | (0,5) | DIR_R
DIAG_TR | (2,4) | 2 | DIR_T | (0,6) | DIR_R
DIAG_TR | (2,5) | 2 | DIR_T | (0,7) | DIR_R
DIAG_TR | (2,6) | 2 | DIR_T | (0,8) | DIR_R
DIAG_TR | (3,3) | 3 | DIR_T | (0,6) | DIR_R
DIAG_TR | (3,4) | 3 | DIR_T | (0,7) | DIR_R
DIAG_TR | (3,5) | 3 | DIR_T | (0,8) | DIR_R
DIAG_TR | (4,4) | 4 | DIR_T | (0,8) | DIR_R
```

Train example 5: 1 row
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . .
. . 1 . .
. . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
DIAG_TR | (1,2) | 1 | DIR_T | (0,3) | DIR_R
```

Train example 6: 9 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . . .
. 1 1 1 1 1 .
. . 2 2 2 . .
. . . 3 . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
DIAG_TR | (1,1) | 1 | DIR_T | (0,2) | DIR_R
DIAG_TR | (1,2) | 1 | DIR_T | (0,3) | DIR_R
DIAG_TR | (1,3) | 1 | DIR_T | (0,4) | DIR_R
DIAG_TR | (1,4) | 1 | DIR_T | (0,5) | DIR_R
DIAG_TR | (1,5) | 1 | DIR_T | (0,6) | DIR_R
DIAG_TR | (2,2) | 2 | DIR_T | (0,4) | DIR_R
DIAG_TR | (2,3) | 2 | DIR_T | (0,5) | DIR_R
DIAG_TR | (2,4) | 2 | DIR_T | (0,6) | DIR_R
DIAG_TR | (3,3) | 3 | DIR_T | (0,6) | DIR_R
```


#### &r23, assignment 5 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CW)}
- empty at every example

#### &r23, assignment 6 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CC)}
- empty at every example

#### &r23, assignment 7 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CW)}
- empty at every example

#### &r23, assignment 8 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CC)}
- empty at every example
```
INIT Walk [:0] SKIP [:1] &r3 :0 * [L0] :1 * [L1] END [:0] END [:1] L0 END [:2] L1 END [:2] &r23 :5 * [L2] END [:0] END [:1] L2 END [&r24] [&r25] [&r26]
```

### &r24 (export table 23)

- columns: c0: Color, c1: Number, c2: Color
- depth 10, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r3, &r14; assignments: 8

#### &r24, assignment 1 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CW)}
- rows per train example: [2, 2, 2, 2, 2, 2, 2]; test: 2

Train example 0: 2 rows
```
c0 | c1 | c2
2 | 0 | 2
5 | 0 | 5
```

Train example 1: 2 rows
```
c0 | c1 | c2
2 | 0 | 2
5 | 0 | 5
```

Train example 2: 2 rows
```
c0 | c1 | c2
2 | 0 | 2
5 | 0 | 5
```

Train example 3: 2 rows
```
c0 | c1 | c2
2 | 0 | 2
5 | 0 | 5
```

Train example 4: 2 rows
```
c0 | c1 | c2
2 | 0 | 2
5 | 0 | 5
```

Train example 5: 2 rows
```
c0 | c1 | c2
2 | 0 | 2
5 | 0 | 5
```

Train example 6: 2 rows
```
c0 | c1 | c2
2 | 0 | 2
5 | 0 | 5
```


#### &r24, assignment 2 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 1 at every example

#### &r24, assignment 3 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CW)}
- rows per train example: [4, 4, 6, 4, 10, 4, 8]; test: 12

Train example 0: 4 rows
```
c0 | c1 | c2
2 | 0 | 2
2 | 1 | 5
5 | 0 | 5
5 | 1 | 2
```

Train example 1: 4 rows
```
c0 | c1 | c2
2 | 0 | 2
2 | 1 | 5
5 | 0 | 5
5 | 1 | 2
```

Train example 2: 6 rows
```
c0 | c1 | c2
2 | 0 | 2
2 | 1 | 5
2 | 2 | 2
5 | 0 | 5
5 | 1 | 2
5 | 2 | 5
```

Train example 3: 4 rows
```
c0 | c1 | c2
2 | 0 | 2
2 | 1 | 5
5 | 0 | 5
5 | 1 | 2
```

Train example 4: 10 rows
```
c0 | c1 | c2
2 | 0 | 2
2 | 1 | 5
2 | 2 | 2
2 | 3 | 5
2 | 4 | 2
5 | 0 | 5
5 | 1 | 2
5 | 2 | 5
5 | 3 | 2
5 | 4 | 5
```

Train example 5: 4 rows
```
c0 | c1 | c2
2 | 0 | 2
2 | 1 | 5
5 | 0 | 5
5 | 1 | 2
```

Train example 6: 8 rows
```
c0 | c1 | c2
2 | 0 | 2
2 | 1 | 5
2 | 2 | 2
2 | 3 | 5
5 | 0 | 5
5 | 1 | 2
5 | 2 | 5
5 | 3 | 2
```


#### &r24, assignment 4 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 3 at every example

#### &r24, assignment 5 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CW)}
- rows equal to those of assignment 1 at every example

#### &r24, assignment 6 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 1 at every example

#### &r24, assignment 7 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CW)}
- rows equal to those of assignment 1 at every example

#### &r24, assignment 8 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 1 at every example
```
INIT Propagation [:0] SKIP [:1] &r17 :1 * [L0] input :0 L0 :1 * [L1] END [:0] END [:1] :0 L0 :1 L1 END END [:2] &r22 :1 * [L2] &r16 :4 L2 :6 * [L3] &r3 :0 * [L4] :1 * [L5] END [:0] END [:1] :0 L3 :1 L4 END END [:2] :0 L2 :1 L5 END END [:3] SKIP [&r27] [&r28] [&r29] [&r30]
```

### &r27 (export table 24)

- columns: c0: Box, c1: Color
- depth 9, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r3, &r14; assignments: 8

#### &r27, assignment 1 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CW)}
- rows per train example: [2, 2, 5, 2, 9, 2, 7]; test: 11

Train example 0: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 5 . 2 .
. . . . .
. . . . .
```
```
c0 | c1
(0,1) | 5
(0,3) | 2
```

Train example 1: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . 2 .
. . . . .
. . . . .
```
```
c0 | c1
(0,1) | 2
(0,3) | 2
```

Train example 2: 5 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 5 2 5 2
. . . . .
. . . . .
```
```
c0 | c1
(0,0) | 2
(0,1) | 5
(0,2) | 2
(0,3) | 5
(0,4) | 2
```

Train example 3: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . 5 .
. . . . .
. . . . .
```
```
c0 | c1
(0,1) | 2
(0,3) | 5
```

Train example 4: 9 rows
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 5 2 2 5 5 5 2 2
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1
(0,0) | 5
(0,1) | 5
(0,2) | 2
(0,3) | 2
(0,4) | 5
(0,5) | 5
(0,6) | 5
(0,7) | 2
(0,8) | 2
```

Train example 5: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 5 . 5 .
. . . . .
. . . . .
```
```
c0 | c1
(0,1) | 5
(0,3) | 5
```

Train example 6: 7 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 2 5 5 5 5 2
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1
(0,0) | 5
(0,1) | 2
(0,2) | 5
(0,3) | 5
(0,4) | 5
(0,5) | 5
(0,6) | 2
```


#### &r27, assignment 2 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 1 at every example

#### &r27, assignment 3 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CW)}
- rows per train example: [3, 3, 9, 3, 25, 3, 16]; test: 36

Train example 0: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 5 . 2 .
. . 2 . .
. . . . .
```
```
c0 | c1
(0,1) | 5
(0,3) | 2
(1,2) | 2
```

Train example 1: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . 2 .
. . 5 . .
. . . . .
```
```
c0 | c1
(0,1) | 2
(0,3) | 2
(1,2) | 5
```

Train example 2: 9 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 5 2 5 2
. 5 2 5 .
. . 2 . .
```
```
c0 | c1
(0,0) | 2
(0,1) | 5
(0,2) | 2
(0,3) | 5
(0,4) | 2
(1,1) | 5
(1,2) | 2
(1,3) | 5
(2,2) | 2
```

Train example 3: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . 5 .
. . 5 . .
. . . . .
```
```
c0 | c1
(0,1) | 2
(0,3) | 5
(1,2) | 5
```

Train example 4: 25 rows
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 5 2 2 5 5 5 2 2
. 2 2 5 5 2 2 2 .
. . 5 5 2 2 5 . .
. . . 2 2 5 . . .
. . . . 5 . . . .
```
```
c0 | c1
(0,0) | 5
(0,1) | 5
(0,2) | 2
(0,3) | 2
(0,4) | 5
(0,5) | 5
(0,6) | 5
(0,7) | 2
(0,8) | 2
(1,1) | 2
(1,2) | 2
(1,3) | 5
(1,4) | 5
(1,5) | 2
(1,6) | 2
(1,7) | 2
(2,2) | 5
(2,3) | 5
(2,4) | 2
(2,5) | 2
(2,6) | 5
(3,3) | 2
(3,4) | 2
(3,5) | 5
(4,4) | 5
```

Train example 5: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 5 . 5 .
. . 2 . .
. . . . .
```
```
c0 | c1
(0,1) | 5
(0,3) | 5
(1,2) | 2
```

Train example 6: 16 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 2 5 5 5 5 2
. 2 5 2 2 2 .
. . 5 2 5 . .
. . . 2 . . .
```
```
c0 | c1
(0,0) | 5
(0,1) | 2
(0,2) | 5
(0,3) | 5
(0,4) | 5
(0,5) | 5
(0,6) | 2
(1,1) | 2
(1,2) | 5
(1,3) | 2
(1,4) | 2
(1,5) | 2
(2,2) | 5
(2,3) | 2
(2,4) | 5
(3,3) | 2
```


#### &r27, assignment 4 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CC)}
- rows per train example: [3, 3, 9, 3, 25, 3, 16]; test: 36

Train example 0: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 5 . 2 .
. . 5 . .
. . . . .
```
```
c0 | c1
(0,1) | 5
(0,3) | 2
(1,2) | 5
```

Train example 1: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . 2 .
. . 5 . .
. . . . .
```
```
c0 | c1
(0,1) | 2
(0,3) | 2
(1,2) | 5
```

Train example 2: 9 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 5 2 5 2
. 5 2 5 .
. . 2 . .
```
```
c0 | c1
(0,0) | 2
(0,1) | 5
(0,2) | 2
(0,3) | 5
(0,4) | 2
(1,1) | 5
(1,2) | 2
(1,3) | 5
(2,2) | 2
```

Train example 3: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . 5 .
. . 2 . .
. . . . .
```
```
c0 | c1
(0,1) | 2
(0,3) | 5
(1,2) | 2
```

Train example 4: 25 rows
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 5 2 2 5 5 5 2 2
. 5 5 2 2 2 5 5 .
. . 5 5 5 2 2 . .
. . . 2 5 5 . . .
. . . . 2 . . . .
```
```
c0 | c1
(0,0) | 5
(0,1) | 5
(0,2) | 2
(0,3) | 2
(0,4) | 5
(0,5) | 5
(0,6) | 5
(0,7) | 2
(0,8) | 2
(1,1) | 5
(1,2) | 5
(1,3) | 2
(1,4) | 2
(1,5) | 2
(1,6) | 5
(1,7) | 5
(2,2) | 5
(2,3) | 5
(2,4) | 5
(2,5) | 2
(2,6) | 2
(3,3) | 2
(3,4) | 5
(3,5) | 5
(4,4) | 2
```

Train example 5: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 5 . 5 .
. . 2 . .
. . . . .
```
```
c0 | c1
(0,1) | 5
(0,3) | 5
(1,2) | 2
```

Train example 6: 16 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 2 5 5 5 5 2
. 2 2 2 2 5 .
. . 5 5 2 . .
. . . 5 . . .
```
```
c0 | c1
(0,0) | 5
(0,1) | 2
(0,2) | 5
(0,3) | 5
(0,4) | 5
(0,5) | 5
(0,6) | 2
(1,1) | 2
(1,2) | 2
(1,3) | 2
(1,4) | 2
(1,5) | 5
(2,2) | 5
(2,3) | 5
(2,4) | 2
(3,3) | 5
```


#### &r27, assignment 5 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CW)}
- rows equal to those of assignment 1 at every example

#### &r27, assignment 6 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 1 at every example

#### &r27, assignment 7 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CW)}
- rows equal to those of assignment 1 at every example

#### &r27, assignment 8 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 1 at every example
### &r28 (export table 25)

- columns: c0: Box, c1: Color
- depth 4, candidate keys none
- DETs its entries are assigned: &r0, &r1; assignments: 4

#### &r28, assignment 1 of 4

- DET values that differ between the assignments: &r1 = {(DIR_T)}
- rows per train example: [2, 2, 5, 2, 9, 2, 7]; test: 11

Train example 0: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 5 . 2 .
. . . . .
. . . . .
```
```
c0 | c1
(0,1) | 5
(0,3) | 2
```

Train example 1: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . 2 .
. . . . .
. . . . .
```
```
c0 | c1
(0,1) | 2
(0,3) | 2
```

Train example 2: 5 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 5 2 5 2
. . . . .
. . . . .
```
```
c0 | c1
(0,0) | 2
(0,1) | 5
(0,2) | 2
(0,3) | 5
(0,4) | 2
```

Train example 3: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . 5 .
. . . . .
. . . . .
```
```
c0 | c1
(0,1) | 2
(0,3) | 5
```

Train example 4: 9 rows
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 5 2 2 5 5 5 2 2
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1
(0,0) | 5
(0,1) | 5
(0,2) | 2
(0,3) | 2
(0,4) | 5
(0,5) | 5
(0,6) | 5
(0,7) | 2
(0,8) | 2
```

Train example 5: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 5 . 5 .
. . . . .
. . . . .
```
```
c0 | c1
(0,1) | 5
(0,3) | 5
```

Train example 6: 7 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 2 5 5 5 5 2
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1
(0,0) | 5
(0,1) | 2
(0,2) | 5
(0,3) | 5
(0,4) | 5
(0,5) | 5
(0,6) | 2
```


#### &r28, assignment 2 of 4

- DET values that differ between the assignments: &r1 = {(DIR_B)}
- rows equal to those of assignment 1 at every example

#### &r28, assignment 3 of 4

- DET values that differ between the assignments: &r1 = {(DIR_L)}
- rows equal to those of assignment 1 at every example

#### &r28, assignment 4 of 4

- DET values that differ between the assignments: &r1 = {(DIR_R)}
- rows equal to those of assignment 1 at every example
### &r29 (export table 26)

- columns: c0: Box, c1: Color, c2: Box, c3: Color
- depth 8, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r3, &r14; assignments: 8

#### &r29, assignment 1 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CW)}
- rows per train example: [0, 0, 0, 0, 0, 0, 0]; test: 0


#### &r29, assignment 2 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CC)}
- empty at every example

#### &r29, assignment 3 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CW)}
- rows per train example: [2, 2, 8, 2, 32, 2, 18]; test: 50

Train example 0: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 2 . . .
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,1) | 2 | (1,2) | 5
(0,1) | 5 | (1,2) | 2
```

Train example 1: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 2 . . .
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,1) | 2 | (1,2) | 5
(0,1) | 5 | (1,2) | 2
```

Train example 2: 8 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2 . .
. 2 . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,0) | 2 | (1,1) | 5
(0,0) | 5 | (1,1) | 2
(0,1) | 2 | (1,2) | 5
(0,1) | 5 | (1,2) | 2
(0,2) | 2 | (1,3) | 5
(0,2) | 5 | (1,3) | 2
(1,1) | 2 | (2,2) | 5
(1,1) | 5 | (2,2) | 2
```

Train example 3: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 2 . . .
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,1) | 2 | (1,2) | 5
(0,1) | 5 | (1,2) | 2
```

Train example 4: 32 rows, the first 30 shown
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2 2 2 2 2 . .
. 2 2 2 2 2 . . .
. . 2 2 2 . . . .
. . . 2 . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2 | c3
(0,0) | 2 | (1,1) | 5
(0,0) | 5 | (1,1) | 2
(0,1) | 2 | (1,2) | 5
(0,1) | 5 | (1,2) | 2
(0,2) | 2 | (1,3) | 5
(0,2) | 5 | (1,3) | 2
(0,3) | 2 | (1,4) | 5
(0,3) | 5 | (1,4) | 2
(0,4) | 2 | (1,5) | 5
(0,4) | 5 | (1,5) | 2
(0,5) | 2 | (1,6) | 5
(0,5) | 5 | (1,6) | 2
(0,6) | 2 | (1,7) | 5
(0,6) | 5 | (1,7) | 2
(1,1) | 2 | (2,2) | 5
(1,1) | 5 | (2,2) | 2
(1,2) | 2 | (2,3) | 5
(1,2) | 5 | (2,3) | 2
(1,3) | 2 | (2,4) | 5
(1,3) | 5 | (2,4) | 2
(1,4) | 2 | (2,5) | 5
(1,4) | 5 | (2,5) | 2
(1,5) | 2 | (2,6) | 5
(1,5) | 5 | (2,6) | 2
(2,2) | 2 | (3,3) | 5
(2,2) | 5 | (3,3) | 2
(2,3) | 2 | (3,4) | 5
(2,3) | 5 | (3,4) | 2
(2,4) | 2 | (3,5) | 5
(2,4) | 5 | (3,5) | 2
```

Train example 5: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 2 . . .
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,1) | 2 | (1,2) | 5
(0,1) | 5 | (1,2) | 2
```

Train example 6: 18 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2 2 2 . .
. 2 2 2 . . .
. . 2 . . . .
. . . . . . .
```
```
c0 | c1 | c2 | c3
(0,0) | 2 | (1,1) | 5
(0,0) | 5 | (1,1) | 2
(0,1) | 2 | (1,2) | 5
(0,1) | 5 | (1,2) | 2
(0,2) | 2 | (1,3) | 5
(0,2) | 5 | (1,3) | 2
(0,3) | 2 | (1,4) | 5
(0,3) | 5 | (1,4) | 2
(0,4) | 2 | (1,5) | 5
(0,4) | 5 | (1,5) | 2
(1,1) | 2 | (2,2) | 5
(1,1) | 5 | (2,2) | 2
(1,2) | 2 | (2,3) | 5
(1,2) | 5 | (2,3) | 2
(1,3) | 2 | (2,4) | 5
(1,3) | 5 | (2,4) | 2
(2,2) | 2 | (3,3) | 5
(2,2) | 5 | (3,3) | 2
```


#### &r29, assignment 4 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CC)}
- rows per train example: [2, 2, 8, 2, 32, 2, 18]; test: 50

Train example 0: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . 2 .
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,3) | 2 | (1,2) | 5
(0,3) | 5 | (1,2) | 2
```

Train example 1: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . 2 .
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,3) | 2 | (1,2) | 5
(0,3) | 5 | (1,2) | 2
```

Train example 2: 8 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . 2 2 2
. . . 2 .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,2) | 2 | (1,1) | 5
(0,2) | 5 | (1,1) | 2
(0,3) | 2 | (1,2) | 5
(0,3) | 5 | (1,2) | 2
(0,4) | 2 | (1,3) | 5
(0,4) | 5 | (1,3) | 2
(1,3) | 2 | (2,2) | 5
(1,3) | 5 | (2,2) | 2
```

Train example 3: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . 2 .
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,3) | 2 | (1,2) | 5
(0,3) | 5 | (1,2) | 2
```

Train example 4: 32 rows, the first 30 shown
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . 2 2 2 2 2 2 2
. . . 2 2 2 2 2 .
. . . . 2 2 2 . .
. . . . . 2 . . .
. . . . . . . . .
```
```
c0 | c1 | c2 | c3
(0,2) | 2 | (1,1) | 5
(0,2) | 5 | (1,1) | 2
(0,3) | 2 | (1,2) | 5
(0,3) | 5 | (1,2) | 2
(0,4) | 2 | (1,3) | 5
(0,4) | 5 | (1,3) | 2
(0,5) | 2 | (1,4) | 5
(0,5) | 5 | (1,4) | 2
(0,6) | 2 | (1,5) | 5
(0,6) | 5 | (1,5) | 2
(0,7) | 2 | (1,6) | 5
(0,7) | 5 | (1,6) | 2
(0,8) | 2 | (1,7) | 5
(0,8) | 5 | (1,7) | 2
(1,3) | 2 | (2,2) | 5
(1,3) | 5 | (2,2) | 2
(1,4) | 2 | (2,3) | 5
(1,4) | 5 | (2,3) | 2
(1,5) | 2 | (2,4) | 5
(1,5) | 5 | (2,4) | 2
(1,6) | 2 | (2,5) | 5
(1,6) | 5 | (2,5) | 2
(1,7) | 2 | (2,6) | 5
(1,7) | 5 | (2,6) | 2
(2,4) | 2 | (3,3) | 5
(2,4) | 5 | (3,3) | 2
(2,5) | 2 | (3,4) | 5
(2,5) | 5 | (3,4) | 2
(2,6) | 2 | (3,5) | 5
(2,6) | 5 | (3,5) | 2
```

Train example 5: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . 2 .
. . . . .
. . . . .
```
```
c0 | c1 | c2 | c3
(0,3) | 2 | (1,2) | 5
(0,3) | 5 | (1,2) | 2
```

Train example 6: 18 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . 2 2 2 2 2
. . . 2 2 2 .
. . . . 2 . .
. . . . . . .
```
```
c0 | c1 | c2 | c3
(0,2) | 2 | (1,1) | 5
(0,2) | 5 | (1,1) | 2
(0,3) | 2 | (1,2) | 5
(0,3) | 5 | (1,2) | 2
(0,4) | 2 | (1,3) | 5
(0,4) | 5 | (1,3) | 2
(0,5) | 2 | (1,4) | 5
(0,5) | 5 | (1,4) | 2
(0,6) | 2 | (1,5) | 5
(0,6) | 5 | (1,5) | 2
(1,3) | 2 | (2,2) | 5
(1,3) | 5 | (2,2) | 2
(1,4) | 2 | (2,3) | 5
(1,4) | 5 | (2,3) | 2
(1,5) | 2 | (2,4) | 5
(1,5) | 5 | (2,4) | 2
(2,4) | 2 | (3,3) | 5
(2,4) | 5 | (3,3) | 2
```


#### &r29, assignment 5 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CW)}
- empty at every example

#### &r29, assignment 6 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CC)}
- empty at every example

#### &r29, assignment 7 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CW)}
- empty at every example

#### &r29, assignment 8 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CC)}
- empty at every example
```
RULE &r27 :1 :0 * [L0] :1 * [L1] END END [&r31]
```

### &r31 (export table 27)

- columns: c0: Box, c1: Color
- depth 10, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r3, &r14; assignments: 8

#### &r31, assignment 1 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CW)}
- rows per train example: [2, 2, 5, 2, 9, 2, 7]; test: 11

Train example 0: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 5 . 2 .
. . . . .
. . . . .
```
```
c0 | c1
(0,1) | 5
(0,3) | 2
```

Train example 1: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . 2 .
. . . . .
. . . . .
```
```
c0 | c1
(0,1) | 2
(0,3) | 2
```

Train example 2: 5 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 5 2 5 2
. . . . .
. . . . .
```
```
c0 | c1
(0,0) | 2
(0,1) | 5
(0,2) | 2
(0,3) | 5
(0,4) | 2
```

Train example 3: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . 5 .
. . . . .
. . . . .
```
```
c0 | c1
(0,1) | 2
(0,3) | 5
```

Train example 4: 9 rows
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 5 2 2 5 5 5 2 2
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1
(0,0) | 5
(0,1) | 5
(0,2) | 2
(0,3) | 2
(0,4) | 5
(0,5) | 5
(0,6) | 5
(0,7) | 2
(0,8) | 2
```

Train example 5: 2 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 5 . 5 .
. . . . .
. . . . .
```
```
c0 | c1
(0,1) | 5
(0,3) | 5
```

Train example 6: 7 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 2 5 5 5 5 2
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1
(0,0) | 5
(0,1) | 2
(0,2) | 5
(0,3) | 5
(0,4) | 5
(0,5) | 5
(0,6) | 2
```


#### &r31, assignment 2 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 1 at every example

#### &r31, assignment 3 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CW)}
- rows per train example: [3, 3, 9, 3, 25, 3, 16]; test: 36

Train example 0: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 5 . 2 .
. . 2 . .
. . . . .
```
```
c0 | c1
(0,1) | 5
(0,3) | 2
(1,2) | 2
```

Train example 1: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . 2 .
. . 5 . .
. . . . .
```
```
c0 | c1
(0,1) | 2
(0,3) | 2
(1,2) | 5
```

Train example 2: 9 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 5 2 5 2
. 5 2 5 .
. . 2 . .
```
```
c0 | c1
(0,0) | 2
(0,1) | 5
(0,2) | 2
(0,3) | 5
(0,4) | 2
(1,1) | 5
(1,2) | 2
(1,3) | 5
(2,2) | 2
```

Train example 3: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . 5 .
. . 5 . .
. . . . .
```
```
c0 | c1
(0,1) | 2
(0,3) | 5
(1,2) | 5
```

Train example 4: 25 rows
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 5 2 2 5 5 5 2 2
. 2 2 5 5 2 2 2 .
. . 5 5 2 2 5 . .
. . . 2 2 5 . . .
. . . . 5 . . . .
```
```
c0 | c1
(0,0) | 5
(0,1) | 5
(0,2) | 2
(0,3) | 2
(0,4) | 5
(0,5) | 5
(0,6) | 5
(0,7) | 2
(0,8) | 2
(1,1) | 2
(1,2) | 2
(1,3) | 5
(1,4) | 5
(1,5) | 2
(1,6) | 2
(1,7) | 2
(2,2) | 5
(2,3) | 5
(2,4) | 2
(2,5) | 2
(2,6) | 5
(3,3) | 2
(3,4) | 2
(3,5) | 5
(4,4) | 5
```

Train example 5: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 5 . 5 .
. . 2 . .
. . . . .
```
```
c0 | c1
(0,1) | 5
(0,3) | 5
(1,2) | 2
```

Train example 6: 16 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 2 5 5 5 5 2
. 2 5 2 2 2 .
. . 5 2 5 . .
. . . 2 . . .
```
```
c0 | c1
(0,0) | 5
(0,1) | 2
(0,2) | 5
(0,3) | 5
(0,4) | 5
(0,5) | 5
(0,6) | 2
(1,1) | 2
(1,2) | 5
(1,3) | 2
(1,4) | 2
(1,5) | 2
(2,2) | 5
(2,3) | 2
(2,4) | 5
(3,3) | 2
```


#### &r31, assignment 4 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CC)}
- rows per train example: [3, 3, 9, 3, 25, 3, 16]; test: 36

Train example 0: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 5 . 2 .
. . 5 . .
. . . . .
```
```
c0 | c1
(0,1) | 5
(0,3) | 2
(1,2) | 5
```

Train example 1: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . 2 .
. . 5 . .
. . . . .
```
```
c0 | c1
(0,1) | 2
(0,3) | 2
(1,2) | 5
```

Train example 2: 9 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 5 2 5 2
. 5 2 5 .
. . 2 . .
```
```
c0 | c1
(0,0) | 2
(0,1) | 5
(0,2) | 2
(0,3) | 5
(0,4) | 2
(1,1) | 5
(1,2) | 2
(1,3) | 5
(2,2) | 2
```

Train example 3: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 2 . 5 .
. . 2 . .
. . . . .
```
```
c0 | c1
(0,1) | 2
(0,3) | 5
(1,2) | 2
```

Train example 4: 25 rows
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 5 2 2 5 5 5 2 2
. 5 5 2 2 2 5 5 .
. . 5 5 5 2 2 . .
. . . 2 5 5 . . .
. . . . 2 . . . .
```
```
c0 | c1
(0,0) | 5
(0,1) | 5
(0,2) | 2
(0,3) | 2
(0,4) | 5
(0,5) | 5
(0,6) | 5
(0,7) | 2
(0,8) | 2
(1,1) | 5
(1,2) | 5
(1,3) | 2
(1,4) | 2
(1,5) | 2
(1,6) | 5
(1,7) | 5
(2,2) | 5
(2,3) | 5
(2,4) | 5
(2,5) | 2
(2,6) | 2
(3,3) | 2
(3,4) | 5
(3,5) | 5
(4,4) | 2
```

Train example 5: 3 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 5 . 5 .
. . 2 . .
. . . . .
```
```
c0 | c1
(0,1) | 5
(0,3) | 5
(1,2) | 2
```

Train example 6: 16 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
5 2 5 5 5 5 2
. 2 2 2 2 5 .
. . 5 5 2 . .
. . . 5 . . .
```
```
c0 | c1
(0,0) | 5
(0,1) | 2
(0,2) | 5
(0,3) | 5
(0,4) | 5
(0,5) | 5
(0,6) | 2
(1,1) | 2
(1,2) | 2
(1,3) | 2
(1,4) | 2
(1,5) | 5
(2,2) | 5
(2,3) | 5
(2,4) | 2
(3,3) | 5
```


#### &r31, assignment 5 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CW)}
- rows equal to those of assignment 1 at every example

#### &r31, assignment 6 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 1 at every example

#### &r31, assignment 7 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CW)}
- rows equal to those of assignment 1 at every example

#### &r31, assignment 8 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 1 at every example
```
RULE &r7 input :0 * [L0] :1 * [L1] IF &r22 :0 L0 END &r31 :0 L0 :1 * [L2] END = L2 L1 END END [&r32]
```

### &r32 (export table 28)

- columns: c0: Box, c1: Color, c2: Color
- depth 11, candidate keys none
- DETs its entries are assigned: &r0, &r1, &r3, &r14; assignments: 8

#### &r32, assignment 1 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CW)}
- rows per train example: [15, 15, 15, 15, 45, 15, 28]; test: 72

Train example 0: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 7 | 7
(0,1) | 5 | 5
(0,2) | 7 | 7
(0,3) | 2 | 2
(0,4) | 7 | 7
(1,0) | 7 | 7
(1,1) | 7 | 7
(1,2) | 7 | 7
(1,3) | 7 | 7
(1,4) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 7
(2,3) | 7 | 7
(2,4) | 7 | 7
```

Train example 1: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 7 | 7
(0,1) | 2 | 2
(0,2) | 7 | 7
(0,3) | 2 | 2
(0,4) | 7 | 7
(1,0) | 7 | 7
(1,1) | 7 | 7
(1,2) | 7 | 7
(1,3) | 7 | 7
(1,4) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 7
(2,3) | 7 | 7
(2,4) | 7 | 7
```

Train example 2: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 2 | 2
(0,1) | 5 | 5
(0,2) | 2 | 2
(0,3) | 5 | 5
(0,4) | 2 | 2
(1,0) | 7 | 7
(1,1) | 7 | 7
(1,2) | 7 | 7
(1,3) | 7 | 7
(1,4) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 7
(2,3) | 7 | 7
(2,4) | 7 | 7
```

Train example 3: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 7 | 7
(0,1) | 2 | 2
(0,2) | 7 | 7
(0,3) | 5 | 5
(0,4) | 7 | 7
(1,0) | 7 | 7
(1,1) | 7 | 7
(1,2) | 7 | 7
(1,3) | 7 | 7
(1,4) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 7
(2,3) | 7 | 7
(2,4) | 7 | 7
```

Train example 4: 45 rows, the first 30 shown
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 5 | 5
(0,1) | 5 | 5
(0,2) | 2 | 2
(0,3) | 2 | 2
(0,4) | 5 | 5
(0,5) | 5 | 5
(0,6) | 5 | 5
(0,7) | 2 | 2
(0,8) | 2 | 2
(1,0) | 7 | 7
(1,1) | 7 | 7
(1,2) | 7 | 7
(1,3) | 7 | 7
(1,4) | 7 | 7
(1,5) | 7 | 7
(1,6) | 7 | 7
(1,7) | 7 | 7
(1,8) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 7
(2,3) | 7 | 7
(2,4) | 7 | 7
(2,5) | 7 | 7
(2,6) | 7 | 7
(2,7) | 7 | 7
(2,8) | 7 | 7
(3,0) | 7 | 7
(3,1) | 7 | 7
(3,2) | 7 | 7
```

Train example 5: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 7 | 7
(0,1) | 5 | 5
(0,2) | 7 | 7
(0,3) | 5 | 5
(0,4) | 7 | 7
(1,0) | 7 | 7
(1,1) | 7 | 7
(1,2) | 7 | 7
(1,3) | 7 | 7
(1,4) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 7
(2,3) | 7 | 7
(2,4) | 7 | 7
```

Train example 6: 28 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 5 | 5
(0,1) | 2 | 2
(0,2) | 5 | 5
(0,3) | 5 | 5
(0,4) | 5 | 5
(0,5) | 5 | 5
(0,6) | 2 | 2
(1,0) | 7 | 7
(1,1) | 7 | 7
(1,2) | 7 | 7
(1,3) | 7 | 7
(1,4) | 7 | 7
(1,5) | 7 | 7
(1,6) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 7
(2,3) | 7 | 7
(2,4) | 7 | 7
(2,5) | 7 | 7
(2,6) | 7 | 7
(3,0) | 7 | 7
(3,1) | 7 | 7
(3,2) | 7 | 7
(3,3) | 7 | 7
(3,4) | 7 | 7
(3,5) | 7 | 7
(3,6) | 7 | 7
```


#### &r32, assignment 2 of 8

- DET values that differ between the assignments: &r1 = {(DIR_T)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 1 at every example

#### &r32, assignment 3 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CW)}
- rows per train example: [15, 15, 15, 15, 45, 15, 28]; test: 72

Train example 0: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 7 | 7
(0,1) | 5 | 5
(0,2) | 7 | 7
(0,3) | 2 | 2
(0,4) | 7 | 7
(1,0) | 7 | 7
(1,1) | 7 | 7
(1,2) | 7 | 2
(1,3) | 7 | 7
(1,4) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 7
(2,3) | 7 | 7
(2,4) | 7 | 7
```

Train example 1: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 7 | 7
(0,1) | 2 | 2
(0,2) | 7 | 7
(0,3) | 2 | 2
(0,4) | 7 | 7
(1,0) | 7 | 7
(1,1) | 7 | 7
(1,2) | 7 | 5
(1,3) | 7 | 7
(1,4) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 7
(2,3) | 7 | 7
(2,4) | 7 | 7
```

Train example 2: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 2 | 2
(0,1) | 5 | 5
(0,2) | 2 | 2
(0,3) | 5 | 5
(0,4) | 2 | 2
(1,0) | 7 | 7
(1,1) | 7 | 5
(1,2) | 7 | 2
(1,3) | 7 | 5
(1,4) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 2
(2,3) | 7 | 7
(2,4) | 7 | 7
```

Train example 3: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 7 | 7
(0,1) | 2 | 2
(0,2) | 7 | 7
(0,3) | 5 | 5
(0,4) | 7 | 7
(1,0) | 7 | 7
(1,1) | 7 | 7
(1,2) | 7 | 5
(1,3) | 7 | 7
(1,4) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 7
(2,3) | 7 | 7
(2,4) | 7 | 7
```

Train example 4: 45 rows, the first 30 shown
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 5 | 5
(0,1) | 5 | 5
(0,2) | 2 | 2
(0,3) | 2 | 2
(0,4) | 5 | 5
(0,5) | 5 | 5
(0,6) | 5 | 5
(0,7) | 2 | 2
(0,8) | 2 | 2
(1,0) | 7 | 7
(1,1) | 7 | 2
(1,2) | 7 | 2
(1,3) | 7 | 5
(1,4) | 7 | 5
(1,5) | 7 | 2
(1,6) | 7 | 2
(1,7) | 7 | 2
(1,8) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 5
(2,3) | 7 | 5
(2,4) | 7 | 2
(2,5) | 7 | 2
(2,6) | 7 | 5
(2,7) | 7 | 7
(2,8) | 7 | 7
(3,0) | 7 | 7
(3,1) | 7 | 7
(3,2) | 7 | 7
```

Train example 5: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 7 | 7
(0,1) | 5 | 5
(0,2) | 7 | 7
(0,3) | 5 | 5
(0,4) | 7 | 7
(1,0) | 7 | 7
(1,1) | 7 | 7
(1,2) | 7 | 2
(1,3) | 7 | 7
(1,4) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 7
(2,3) | 7 | 7
(2,4) | 7 | 7
```

Train example 6: 28 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 5 | 5
(0,1) | 2 | 2
(0,2) | 5 | 5
(0,3) | 5 | 5
(0,4) | 5 | 5
(0,5) | 5 | 5
(0,6) | 2 | 2
(1,0) | 7 | 7
(1,1) | 7 | 2
(1,2) | 7 | 5
(1,3) | 7 | 2
(1,4) | 7 | 2
(1,5) | 7 | 2
(1,6) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 5
(2,3) | 7 | 2
(2,4) | 7 | 5
(2,5) | 7 | 7
(2,6) | 7 | 7
(3,0) | 7 | 7
(3,1) | 7 | 7
(3,2) | 7 | 7
(3,3) | 7 | 2
(3,4) | 7 | 7
(3,5) | 7 | 7
(3,6) | 7 | 7
```


#### &r32, assignment 4 of 8

- DET values that differ between the assignments: &r1 = {(DIR_B)}; &r14 = {(SENSE_CC)}
- rows per train example: [15, 15, 15, 15, 45, 15, 28]; test: 72

Train example 0: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 7 | 7
(0,1) | 5 | 5
(0,2) | 7 | 7
(0,3) | 2 | 2
(0,4) | 7 | 7
(1,0) | 7 | 7
(1,1) | 7 | 7
(1,2) | 7 | 5
(1,3) | 7 | 7
(1,4) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 7
(2,3) | 7 | 7
(2,4) | 7 | 7
```

Train example 1: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 7 | 7
(0,1) | 2 | 2
(0,2) | 7 | 7
(0,3) | 2 | 2
(0,4) | 7 | 7
(1,0) | 7 | 7
(1,1) | 7 | 7
(1,2) | 7 | 5
(1,3) | 7 | 7
(1,4) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 7
(2,3) | 7 | 7
(2,4) | 7 | 7
```

Train example 2: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 2 | 2
(0,1) | 5 | 5
(0,2) | 2 | 2
(0,3) | 5 | 5
(0,4) | 2 | 2
(1,0) | 7 | 7
(1,1) | 7 | 5
(1,2) | 7 | 2
(1,3) | 7 | 5
(1,4) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 2
(2,3) | 7 | 7
(2,4) | 7 | 7
```

Train example 3: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 7 | 7
(0,1) | 2 | 2
(0,2) | 7 | 7
(0,3) | 5 | 5
(0,4) | 7 | 7
(1,0) | 7 | 7
(1,1) | 7 | 7
(1,2) | 7 | 2
(1,3) | 7 | 7
(1,4) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 7
(2,3) | 7 | 7
(2,4) | 7 | 7
```

Train example 4: 45 rows, the first 30 shown
Drawn on a 5x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 5 | 5
(0,1) | 5 | 5
(0,2) | 2 | 2
(0,3) | 2 | 2
(0,4) | 5 | 5
(0,5) | 5 | 5
(0,6) | 5 | 5
(0,7) | 2 | 2
(0,8) | 2 | 2
(1,0) | 7 | 7
(1,1) | 7 | 5
(1,2) | 7 | 5
(1,3) | 7 | 2
(1,4) | 7 | 2
(1,5) | 7 | 2
(1,6) | 7 | 5
(1,7) | 7 | 5
(1,8) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 5
(2,3) | 7 | 5
(2,4) | 7 | 5
(2,5) | 7 | 2
(2,6) | 7 | 2
(2,7) | 7 | 7
(2,8) | 7 | 7
(3,0) | 7 | 7
(3,1) | 7 | 7
(3,2) | 7 | 7
```

Train example 5: 15 rows
Drawn on a 3x5 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1
1 1 1 1 1
1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 7 | 7
(0,1) | 5 | 5
(0,2) | 7 | 7
(0,3) | 5 | 5
(0,4) | 7 | 7
(1,0) | 7 | 7
(1,1) | 7 | 7
(1,2) | 7 | 2
(1,3) | 7 | 7
(1,4) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 7
(2,3) | 7 | 7
(2,4) | 7 | 7
```

Train example 6: 28 rows
Drawn on a 4x7 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
1 1 1 1 1 1 1
```
```
c0 | c1 | c2
(0,0) | 5 | 5
(0,1) | 2 | 2
(0,2) | 5 | 5
(0,3) | 5 | 5
(0,4) | 5 | 5
(0,5) | 5 | 5
(0,6) | 2 | 2
(1,0) | 7 | 7
(1,1) | 7 | 2
(1,2) | 7 | 2
(1,3) | 7 | 2
(1,4) | 7 | 2
(1,5) | 7 | 5
(1,6) | 7 | 7
(2,0) | 7 | 7
(2,1) | 7 | 7
(2,2) | 7 | 5
(2,3) | 7 | 5
(2,4) | 7 | 2
(2,5) | 7 | 7
(2,6) | 7 | 7
(3,0) | 7 | 7
(3,1) | 7 | 7
(3,2) | 7 | 7
(3,3) | 7 | 5
(3,4) | 7 | 7
(3,5) | 7 | 7
(3,6) | 7 | 7
```


#### &r32, assignment 5 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CW)}
- rows equal to those of assignment 1 at every example

#### &r32, assignment 6 of 8

- DET values that differ between the assignments: &r1 = {(DIR_L)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 1 at every example

#### &r32, assignment 7 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CW)}
- rows equal to those of assignment 1 at every example

#### &r32, assignment 8 of 8

- DET values that differ between the assignments: &r1 = {(DIR_R)}; &r14 = {(SENSE_CC)}
- rows equal to those of assignment 1 at every example
## What I see

The task: the top row holds seeds of colors 2 and 5 on background 7. Row by row downward, a background cell whose two upper diagonal neighbors are both filled becomes filled, so a pyramid grows under the seeds. A filled cell takes the swap partner (2 to 5, 5 to 2) of its upper-left neighbor's color. Two lib DETs, DirDomain (&r1, 4 values) and SenseDomain (&r14, 2 values), give most tables 8 assignments. The case's is DIR_B with SENSE_CW, assignment 3.

- **&r0** (DominantColor): 7. **&r2** (cells not of color 7): the seeds, 2 to 9 cells, all on row 0. A selection: 2 of 15 cells in e0.
- **&r3** (DET: pairs of two different non-background colors): `2 | 5` and `5 | 2`, the swap.
- **&r4, &r6** (Singleton: the one edge that every seed lies on): DIR_T in every example. This is the scene's fact, the seed row at the top, but this case takes the grow direction from DirDomain, and no clause reads &r4.
- **&r1, &r7, &r8** (the grow direction, per example, with its axis and the perpendicular axis): one row each, a restatement of the DET's value.
- **&r9 to &r11, &r13** (Ray along the seed row from each seed): no clause of this case reads them. &r9 at DIR_B equals &r9 at DIR_T, and DIR_R equals DIR_L: the rays read only the axis of the direction. &r11 is &r2's cells at every assignment.
- **&r14, &r15** (the read side: the grow direction, its opposite, and a quarter turn by the sense): one row per assignment, `SENSE_CW | DIR_B | DIR_T | DIR_L` at assignment 3.
- **&r16** (each cell with the cell before it and that cell's two side neighbors): one row per cell, 1 at every cell of the drawing. The rows at an edge name cells off the grid, printed as margins with a negative entry: at DIR_B, `[-1 3 0 4]` is row -1 above (0,0). A lib relation per cell, with no signal.
- **&r17**: &r2's cells again, the seeds of the fill.
- **&r18** (Propagation: the cells the fill reaches from the seeds): at the two DIR_B assignments, the pyramid. In e2, rows 0, 1 and 2 hold 5, 3 and 1 cells, as the output does. At the other 6 assignments, &r18 equals &r17. The signal about the rule jumps here. The table also tells the case's grow direction, since DIR_B is the only value at which it differs from its source.
- **&r21** (the join: a background cell with its two upper diagonal neighbors): 13 rows in e0, again with cells off the grid, such as `[-1 3 -1 5] | [-1 3 1 3] | (0,0)` at DIR_B.
- **&r22** (filled: reached and not a seed): at DIR_B, (1,2) in e0, 4 cells in e2 and 16 in e4; empty at every example at the other 6 assignments.
- **&r23** (the seed at the head of each filled cell's read-side diagonal) and **&r24** (Walk: a color after k swaps): only &r24 reads &r23, and no clause reads &r24. At DIR_B, &r24 shows the period of the swap: an even k keeps the color and an odd k swaps it (`2 | 1 | 5`, `2 | 2 | 2`).
- **&r27** (Propagation of the colors from the seeds through the swap): the first table at which the sense makes a difference. In e0, (1,2) is 2 at SENSE_CW and 5 at SENSE_CC, and the output has 2. In e1, with two 2s, both give 5. So only a comparison with the outputs picks the sense, and e0 and e3 decide it. At CW, the drawing of e4 is the output's pyramid.
- **&r29** (the color steps): each pair of cells twice, once per row of &r3: `(0,1) | 2 | (1,2) | 5` and `(0,1) | 5 | (1,2) | 2`, though (0,1) holds only 5. A product of the cell pairs with &r3.
- **&r31**: &r27's rows again, as cell and color.
- **&r32** (out: cell, input color, output color): one row per cell. The drawing shows 1 at every cell, since the table has two Color columns, and the change is visible only in rows such as `(1,2) | 7 | 2`.

Rows that look like noise: the repeated assignments; the rows off the grid in &r16 and &r21; the rows of &r29 for a color the cell does not hold; &r4 to &r6, &r9 to &r13, &r23 and &r24, which no clause of this case reads. The signal jumps at &r18, for the shape and the direction, and at &r27, for the color and the sense.
