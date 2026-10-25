# 6d1d5c90, case `$Marked`

- concept case: True; tokens: 332; tables: 20 relations, 110 per assignment
- cells: a Position is `(row,col)` of the example's input grid (`(row,col)out` where it fits only the output grid), an Offset `+(drow,dcol)`, another Box `rR0-R1 cC0-C1` over the input grid or `[t b l r]` margins; an Ident is `id<n>`, equal only within one case; see README.md

## Grids

### Train example 0: input 6x7, output 6x6

```
input            output
2 1 1 1 1 9 8    1 1 1 1 9 8
6 4 3 9 9 9 8    4 3 9 9 9 8
6 4 3 9 3 8 8    4 3 9 3 8 8
6 4 3 3 3 8 8    4 3 3 3 8 8
6 4 8 8 5 5 5    4 8 8 5 5 5
6 4 5 5 5 3 3    4 5 5 5 3 3
```

### Train example 1: input 6x7, output 6x6

```
input            output
6 8 8 8 4 4 4    4 4 1 5 5 5
6 9 9 8 3 4 4    4 4 1 5 5 5
2 9 9 8 3 3 3    8 8 8 4 4 4
6 9 1 1 1 5 3    9 9 8 3 4 4
6 4 4 1 5 5 5    9 9 8 3 3 3
6 4 4 1 5 5 5    9 1 1 1 5 3
```

### Train example 2: input 6x7, output 6x6

```
input            output
6 8 8 8 4 4 4    5 5 3 3 3 1
6 8 9 8 4 9 1    5 5 3 4 3 1
6 8 9 9 9 9 1    5 5 3 4 4 4
2 5 5 3 3 3 1    8 8 8 4 4 4
6 5 5 3 4 3 1    8 9 8 4 9 1
6 5 5 3 4 4 4    8 9 9 9 9 1
```

### Test example 0: input 6x7

```
6 5 8 8 8 9 9
2 5 4 4 4 4 9
6 5 3 1 1 4 9
6 5 3 1 1 4 8
6 1 3 3 3 8 8
6 1 1 3 8 8 9
```

## Program and tables

Model-written tokens plain, engine-written ones in [brackets]. Each clause is followed by the tables of the relations it declares. A table whose entries hold several DET assignments is given once per assignment, each marked with the values, at that assignment, of the DETs whose value differs between them; a DET's value is the rows of its own table at that assignment.

```
DET DirDomain END [&r0]
```

### &r0 (export table 2)

- columns: D: Dir
- depth 1, candidate keys none
- DETs its entries are assigned: &r0; assignments: 4

#### &r0, assignment 1 of 4

- DET values that differ between the assignments: &r0 = {(DIR_T)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
DIR_T
```


#### &r0, assignment 2 of 4

- DET values that differ between the assignments: &r0 = {(DIR_B)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
DIR_B
```


#### &r0, assignment 3 of 4

- DET values that differ between the assignments: &r0 = {(DIR_L)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
DIR_L
```


#### &r0, assignment 4 of 4

- DET values that differ between the assignments: &r0 = {(DIR_R)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
DIR_R
```

```
RULE &r0 :0 * [L0] opposite :0 L0 :1 * [L1] END [&r1]
```

### &r1 (export table 3)

- columns: c0: Dir, c1: Dir
- depth 2, candidate keys none
- DETs its entries are assigned: &r0; assignments: 4

#### &r1, assignment 1 of 4

- DET values that differ between the assignments: &r0 = {(DIR_T)}
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1
DIR_T | DIR_B
```

Train example 1: 1 row
```
c0 | c1
DIR_T | DIR_B
```

Train example 2: 1 row
```
c0 | c1
DIR_T | DIR_B
```


#### &r1, assignment 2 of 4

- DET values that differ between the assignments: &r0 = {(DIR_B)}
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1
DIR_B | DIR_T
```

Train example 1: 1 row
```
c0 | c1
DIR_B | DIR_T
```

Train example 2: 1 row
```
c0 | c1
DIR_B | DIR_T
```


#### &r1, assignment 3 of 4

- DET values that differ between the assignments: &r0 = {(DIR_L)}
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1
DIR_L | DIR_R
```

Train example 1: 1 row
```
c0 | c1
DIR_L | DIR_R
```

Train example 2: 1 row
```
c0 | c1
DIR_L | DIR_R
```


#### &r1, assignment 4 of 4

- DET values that differ between the assignments: &r0 = {(DIR_R)}
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1
DIR_R | DIR_L
```

Train example 1: 1 row
```
c0 | c1
DIR_R | DIR_L
```

Train example 2: 1 row
```
c0 | c1
DIR_R | DIR_L
```

```
RULE input :0 * [L0] &r1 :1 * [L1] margin :0 L0 :1 L1 :2 * [L2] END [&r2]
```

### &r2 (export table 4)

- columns: c0: Box, c1: Dir, c2: Number
- depth 3, candidate keys none
- DETs its entries are assigned: &r0; assignments: 4

#### &r2, assignment 1 of 4

- DET values that differ between the assignments: &r0 = {(DIR_T)}
- rows per train example: [42, 42, 42]; test: 42

Train example 0: 42 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 5 5 5 5 5 5
4 4 4 4 4 4 4
3 3 3 3 3 3 3
2 2 2 2 2 2 2
1 1 1 1 1 1 1
0 0 0 0 0 0 0
```
```
c0 | c1 | c2
(0,0) | DIR_B | 5
(0,1) | DIR_B | 5
(0,2) | DIR_B | 5
(0,3) | DIR_B | 5
(0,4) | DIR_B | 5
(0,5) | DIR_B | 5
(0,6) | DIR_B | 5
(1,0) | DIR_B | 4
(1,1) | DIR_B | 4
(1,2) | DIR_B | 4
(1,3) | DIR_B | 4
(1,4) | DIR_B | 4
(1,5) | DIR_B | 4
(1,6) | DIR_B | 4
(2,0) | DIR_B | 3
(2,1) | DIR_B | 3
(2,2) | DIR_B | 3
(2,3) | DIR_B | 3
(2,4) | DIR_B | 3
(2,5) | DIR_B | 3
(2,6) | DIR_B | 3
(3,0) | DIR_B | 2
(3,1) | DIR_B | 2
(3,2) | DIR_B | 2
(3,3) | DIR_B | 2
(3,4) | DIR_B | 2
(3,5) | DIR_B | 2
(3,6) | DIR_B | 2
(4,0) | DIR_B | 1
(4,1) | DIR_B | 1
```

Train example 1: 42 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 5 5 5 5 5 5
4 4 4 4 4 4 4
3 3 3 3 3 3 3
2 2 2 2 2 2 2
1 1 1 1 1 1 1
0 0 0 0 0 0 0
```
```
c0 | c1 | c2
(0,0) | DIR_B | 5
(0,1) | DIR_B | 5
(0,2) | DIR_B | 5
(0,3) | DIR_B | 5
(0,4) | DIR_B | 5
(0,5) | DIR_B | 5
(0,6) | DIR_B | 5
(1,0) | DIR_B | 4
(1,1) | DIR_B | 4
(1,2) | DIR_B | 4
(1,3) | DIR_B | 4
(1,4) | DIR_B | 4
(1,5) | DIR_B | 4
(1,6) | DIR_B | 4
(2,0) | DIR_B | 3
(2,1) | DIR_B | 3
(2,2) | DIR_B | 3
(2,3) | DIR_B | 3
(2,4) | DIR_B | 3
(2,5) | DIR_B | 3
(2,6) | DIR_B | 3
(3,0) | DIR_B | 2
(3,1) | DIR_B | 2
(3,2) | DIR_B | 2
(3,3) | DIR_B | 2
(3,4) | DIR_B | 2
(3,5) | DIR_B | 2
(3,6) | DIR_B | 2
(4,0) | DIR_B | 1
(4,1) | DIR_B | 1
```

Train example 2: 42 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 5 5 5 5 5 5
4 4 4 4 4 4 4
3 3 3 3 3 3 3
2 2 2 2 2 2 2
1 1 1 1 1 1 1
0 0 0 0 0 0 0
```
```
c0 | c1 | c2
(0,0) | DIR_B | 5
(0,1) | DIR_B | 5
(0,2) | DIR_B | 5
(0,3) | DIR_B | 5
(0,4) | DIR_B | 5
(0,5) | DIR_B | 5
(0,6) | DIR_B | 5
(1,0) | DIR_B | 4
(1,1) | DIR_B | 4
(1,2) | DIR_B | 4
(1,3) | DIR_B | 4
(1,4) | DIR_B | 4
(1,5) | DIR_B | 4
(1,6) | DIR_B | 4
(2,0) | DIR_B | 3
(2,1) | DIR_B | 3
(2,2) | DIR_B | 3
(2,3) | DIR_B | 3
(2,4) | DIR_B | 3
(2,5) | DIR_B | 3
(2,6) | DIR_B | 3
(3,0) | DIR_B | 2
(3,1) | DIR_B | 2
(3,2) | DIR_B | 2
(3,3) | DIR_B | 2
(3,4) | DIR_B | 2
(3,5) | DIR_B | 2
(3,6) | DIR_B | 2
(4,0) | DIR_B | 1
(4,1) | DIR_B | 1
```


#### &r2, assignment 2 of 4

- DET values that differ between the assignments: &r0 = {(DIR_B)}
- rows per train example: [42, 42, 42]; test: 42

Train example 0: 42 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 0 0 0 0 0 0
1 1 1 1 1 1 1
2 2 2 2 2 2 2
3 3 3 3 3 3 3
4 4 4 4 4 4 4
5 5 5 5 5 5 5
```
```
c0 | c1 | c2
(0,0) | DIR_T | 0
(0,1) | DIR_T | 0
(0,2) | DIR_T | 0
(0,3) | DIR_T | 0
(0,4) | DIR_T | 0
(0,5) | DIR_T | 0
(0,6) | DIR_T | 0
(1,0) | DIR_T | 1
(1,1) | DIR_T | 1
(1,2) | DIR_T | 1
(1,3) | DIR_T | 1
(1,4) | DIR_T | 1
(1,5) | DIR_T | 1
(1,6) | DIR_T | 1
(2,0) | DIR_T | 2
(2,1) | DIR_T | 2
(2,2) | DIR_T | 2
(2,3) | DIR_T | 2
(2,4) | DIR_T | 2
(2,5) | DIR_T | 2
(2,6) | DIR_T | 2
(3,0) | DIR_T | 3
(3,1) | DIR_T | 3
(3,2) | DIR_T | 3
(3,3) | DIR_T | 3
(3,4) | DIR_T | 3
(3,5) | DIR_T | 3
(3,6) | DIR_T | 3
(4,0) | DIR_T | 4
(4,1) | DIR_T | 4
```

Train example 1: 42 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 0 0 0 0 0 0
1 1 1 1 1 1 1
2 2 2 2 2 2 2
3 3 3 3 3 3 3
4 4 4 4 4 4 4
5 5 5 5 5 5 5
```
```
c0 | c1 | c2
(0,0) | DIR_T | 0
(0,1) | DIR_T | 0
(0,2) | DIR_T | 0
(0,3) | DIR_T | 0
(0,4) | DIR_T | 0
(0,5) | DIR_T | 0
(0,6) | DIR_T | 0
(1,0) | DIR_T | 1
(1,1) | DIR_T | 1
(1,2) | DIR_T | 1
(1,3) | DIR_T | 1
(1,4) | DIR_T | 1
(1,5) | DIR_T | 1
(1,6) | DIR_T | 1
(2,0) | DIR_T | 2
(2,1) | DIR_T | 2
(2,2) | DIR_T | 2
(2,3) | DIR_T | 2
(2,4) | DIR_T | 2
(2,5) | DIR_T | 2
(2,6) | DIR_T | 2
(3,0) | DIR_T | 3
(3,1) | DIR_T | 3
(3,2) | DIR_T | 3
(3,3) | DIR_T | 3
(3,4) | DIR_T | 3
(3,5) | DIR_T | 3
(3,6) | DIR_T | 3
(4,0) | DIR_T | 4
(4,1) | DIR_T | 4
```

Train example 2: 42 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 0 0 0 0 0 0
1 1 1 1 1 1 1
2 2 2 2 2 2 2
3 3 3 3 3 3 3
4 4 4 4 4 4 4
5 5 5 5 5 5 5
```
```
c0 | c1 | c2
(0,0) | DIR_T | 0
(0,1) | DIR_T | 0
(0,2) | DIR_T | 0
(0,3) | DIR_T | 0
(0,4) | DIR_T | 0
(0,5) | DIR_T | 0
(0,6) | DIR_T | 0
(1,0) | DIR_T | 1
(1,1) | DIR_T | 1
(1,2) | DIR_T | 1
(1,3) | DIR_T | 1
(1,4) | DIR_T | 1
(1,5) | DIR_T | 1
(1,6) | DIR_T | 1
(2,0) | DIR_T | 2
(2,1) | DIR_T | 2
(2,2) | DIR_T | 2
(2,3) | DIR_T | 2
(2,4) | DIR_T | 2
(2,5) | DIR_T | 2
(2,6) | DIR_T | 2
(3,0) | DIR_T | 3
(3,1) | DIR_T | 3
(3,2) | DIR_T | 3
(3,3) | DIR_T | 3
(3,4) | DIR_T | 3
(3,5) | DIR_T | 3
(3,6) | DIR_T | 3
(4,0) | DIR_T | 4
(4,1) | DIR_T | 4
```


#### &r2, assignment 3 of 4

- DET values that differ between the assignments: &r0 = {(DIR_L)}
- rows per train example: [42, 42, 42]; test: 42

Train example 0: 42 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
6 5 4 3 2 1 0
6 5 4 3 2 1 0
6 5 4 3 2 1 0
6 5 4 3 2 1 0
6 5 4 3 2 1 0
6 5 4 3 2 1 0
```
```
c0 | c1 | c2
(0,0) | DIR_R | 6
(0,1) | DIR_R | 5
(0,2) | DIR_R | 4
(0,3) | DIR_R | 3
(0,4) | DIR_R | 2
(0,5) | DIR_R | 1
(0,6) | DIR_R | 0
(1,0) | DIR_R | 6
(1,1) | DIR_R | 5
(1,2) | DIR_R | 4
(1,3) | DIR_R | 3
(1,4) | DIR_R | 2
(1,5) | DIR_R | 1
(1,6) | DIR_R | 0
(2,0) | DIR_R | 6
(2,1) | DIR_R | 5
(2,2) | DIR_R | 4
(2,3) | DIR_R | 3
(2,4) | DIR_R | 2
(2,5) | DIR_R | 1
(2,6) | DIR_R | 0
(3,0) | DIR_R | 6
(3,1) | DIR_R | 5
(3,2) | DIR_R | 4
(3,3) | DIR_R | 3
(3,4) | DIR_R | 2
(3,5) | DIR_R | 1
(3,6) | DIR_R | 0
(4,0) | DIR_R | 6
(4,1) | DIR_R | 5
```

Train example 1: 42 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
6 5 4 3 2 1 0
6 5 4 3 2 1 0
6 5 4 3 2 1 0
6 5 4 3 2 1 0
6 5 4 3 2 1 0
6 5 4 3 2 1 0
```
```
c0 | c1 | c2
(0,0) | DIR_R | 6
(0,1) | DIR_R | 5
(0,2) | DIR_R | 4
(0,3) | DIR_R | 3
(0,4) | DIR_R | 2
(0,5) | DIR_R | 1
(0,6) | DIR_R | 0
(1,0) | DIR_R | 6
(1,1) | DIR_R | 5
(1,2) | DIR_R | 4
(1,3) | DIR_R | 3
(1,4) | DIR_R | 2
(1,5) | DIR_R | 1
(1,6) | DIR_R | 0
(2,0) | DIR_R | 6
(2,1) | DIR_R | 5
(2,2) | DIR_R | 4
(2,3) | DIR_R | 3
(2,4) | DIR_R | 2
(2,5) | DIR_R | 1
(2,6) | DIR_R | 0
(3,0) | DIR_R | 6
(3,1) | DIR_R | 5
(3,2) | DIR_R | 4
(3,3) | DIR_R | 3
(3,4) | DIR_R | 2
(3,5) | DIR_R | 1
(3,6) | DIR_R | 0
(4,0) | DIR_R | 6
(4,1) | DIR_R | 5
```

Train example 2: 42 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
6 5 4 3 2 1 0
6 5 4 3 2 1 0
6 5 4 3 2 1 0
6 5 4 3 2 1 0
6 5 4 3 2 1 0
6 5 4 3 2 1 0
```
```
c0 | c1 | c2
(0,0) | DIR_R | 6
(0,1) | DIR_R | 5
(0,2) | DIR_R | 4
(0,3) | DIR_R | 3
(0,4) | DIR_R | 2
(0,5) | DIR_R | 1
(0,6) | DIR_R | 0
(1,0) | DIR_R | 6
(1,1) | DIR_R | 5
(1,2) | DIR_R | 4
(1,3) | DIR_R | 3
(1,4) | DIR_R | 2
(1,5) | DIR_R | 1
(1,6) | DIR_R | 0
(2,0) | DIR_R | 6
(2,1) | DIR_R | 5
(2,2) | DIR_R | 4
(2,3) | DIR_R | 3
(2,4) | DIR_R | 2
(2,5) | DIR_R | 1
(2,6) | DIR_R | 0
(3,0) | DIR_R | 6
(3,1) | DIR_R | 5
(3,2) | DIR_R | 4
(3,3) | DIR_R | 3
(3,4) | DIR_R | 2
(3,5) | DIR_R | 1
(3,6) | DIR_R | 0
(4,0) | DIR_R | 6
(4,1) | DIR_R | 5
```


#### &r2, assignment 4 of 4

- DET values that differ between the assignments: &r0 = {(DIR_R)}
- rows per train example: [42, 42, 42]; test: 42

Train example 0: 42 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 1 2 3 4 5 6
0 1 2 3 4 5 6
0 1 2 3 4 5 6
0 1 2 3 4 5 6
0 1 2 3 4 5 6
0 1 2 3 4 5 6
```
```
c0 | c1 | c2
(0,0) | DIR_L | 0
(0,1) | DIR_L | 1
(0,2) | DIR_L | 2
(0,3) | DIR_L | 3
(0,4) | DIR_L | 4
(0,5) | DIR_L | 5
(0,6) | DIR_L | 6
(1,0) | DIR_L | 0
(1,1) | DIR_L | 1
(1,2) | DIR_L | 2
(1,3) | DIR_L | 3
(1,4) | DIR_L | 4
(1,5) | DIR_L | 5
(1,6) | DIR_L | 6
(2,0) | DIR_L | 0
(2,1) | DIR_L | 1
(2,2) | DIR_L | 2
(2,3) | DIR_L | 3
(2,4) | DIR_L | 4
(2,5) | DIR_L | 5
(2,6) | DIR_L | 6
(3,0) | DIR_L | 0
(3,1) | DIR_L | 1
(3,2) | DIR_L | 2
(3,3) | DIR_L | 3
(3,4) | DIR_L | 4
(3,5) | DIR_L | 5
(3,6) | DIR_L | 6
(4,0) | DIR_L | 0
(4,1) | DIR_L | 1
```

Train example 1: 42 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 1 2 3 4 5 6
0 1 2 3 4 5 6
0 1 2 3 4 5 6
0 1 2 3 4 5 6
0 1 2 3 4 5 6
0 1 2 3 4 5 6
```
```
c0 | c1 | c2
(0,0) | DIR_L | 0
(0,1) | DIR_L | 1
(0,2) | DIR_L | 2
(0,3) | DIR_L | 3
(0,4) | DIR_L | 4
(0,5) | DIR_L | 5
(0,6) | DIR_L | 6
(1,0) | DIR_L | 0
(1,1) | DIR_L | 1
(1,2) | DIR_L | 2
(1,3) | DIR_L | 3
(1,4) | DIR_L | 4
(1,5) | DIR_L | 5
(1,6) | DIR_L | 6
(2,0) | DIR_L | 0
(2,1) | DIR_L | 1
(2,2) | DIR_L | 2
(2,3) | DIR_L | 3
(2,4) | DIR_L | 4
(2,5) | DIR_L | 5
(2,6) | DIR_L | 6
(3,0) | DIR_L | 0
(3,1) | DIR_L | 1
(3,2) | DIR_L | 2
(3,3) | DIR_L | 3
(3,4) | DIR_L | 4
(3,5) | DIR_L | 5
(3,6) | DIR_L | 6
(4,0) | DIR_L | 0
(4,1) | DIR_L | 1
```

Train example 2: 42 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 1 2 3 4 5 6
0 1 2 3 4 5 6
0 1 2 3 4 5 6
0 1 2 3 4 5 6
0 1 2 3 4 5 6
0 1 2 3 4 5 6
```
```
c0 | c1 | c2
(0,0) | DIR_L | 0
(0,1) | DIR_L | 1
(0,2) | DIR_L | 2
(0,3) | DIR_L | 3
(0,4) | DIR_L | 4
(0,5) | DIR_L | 5
(0,6) | DIR_L | 6
(1,0) | DIR_L | 0
(1,1) | DIR_L | 1
(1,2) | DIR_L | 2
(1,3) | DIR_L | 3
(1,4) | DIR_L | 4
(1,5) | DIR_L | 5
(1,6) | DIR_L | 6
(2,0) | DIR_L | 0
(2,1) | DIR_L | 1
(2,2) | DIR_L | 2
(2,3) | DIR_L | 3
(2,4) | DIR_L | 4
(2,5) | DIR_L | 5
(2,6) | DIR_L | 6
(3,0) | DIR_L | 0
(3,1) | DIR_L | 1
(3,2) | DIR_L | 2
(3,3) | DIR_L | 3
(3,4) | DIR_L | 4
(3,5) | DIR_L | 5
(3,6) | DIR_L | 6
(4,0) | DIR_L | 0
(4,1) | DIR_L | 1
```

```
INIT Cardinality [:0] SKIP [:1] &r2 :3 * [L0] END [:0] END [:1] L0 END [:2] SKIP [&r3] [&r4] [&r5]
```

### &r3 (export table 5)

- columns: c0: Number
- depth 5, candidate keys none
- DETs its entries are assigned: &r0; assignments: 4

#### &r3, assignment 1 of 4

- DET values that differ between the assignments: &r0 = {(DIR_T)}
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
6
```

Train example 1: 1 row
```
c0
6
```

Train example 2: 1 row
```
c0
6
```


#### &r3, assignment 2 of 4

- DET values that differ between the assignments: &r0 = {(DIR_B)}
- rows equal to those of assignment 1 at every example

#### &r3, assignment 3 of 4

- DET values that differ between the assignments: &r0 = {(DIR_L)}
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
7
```

Train example 1: 1 row
```
c0
7
```

Train example 2: 1 row
```
c0
7
```


#### &r3, assignment 4 of 4

- DET values that differ between the assignments: &r0 = {(DIR_R)}
- rows equal to those of assignment 3 at every example
```
INIT Frame [:0] SKIP [:1] &r1 :2 * [L0] axis_of :0 L0 :1 * [L1] &r3 :2 * [L2] END [:0] END [:1] L1 END [:2] L2 END [&r6] [&r7]
```

### &r6 (export table 6)

- columns: c0: Box
- depth 7, candidate keys none
- DETs its entries are assigned: &r0; assignments: 4

#### &r6, assignment 1 of 4

- DET values that differ between the assignments: &r0 = {(DIR_T)}
- rows per train example: [6, 6, 6]; test: 6

Train example 0: 6 rows
```
c0
r0-0 c0-6
r1-1 c0-6
r2-2 c0-6
r3-3 c0-6
r4-4 c0-6
r5-5 c0-6
```

Train example 1: 6 rows
```
c0
r0-0 c0-6
r1-1 c0-6
r2-2 c0-6
r3-3 c0-6
r4-4 c0-6
r5-5 c0-6
```

Train example 2: 6 rows
```
c0
r0-0 c0-6
r1-1 c0-6
r2-2 c0-6
r3-3 c0-6
r4-4 c0-6
r5-5 c0-6
```


#### &r6, assignment 2 of 4

- DET values that differ between the assignments: &r0 = {(DIR_B)}
- rows equal to those of assignment 1 at every example

#### &r6, assignment 3 of 4

- DET values that differ between the assignments: &r0 = {(DIR_L)}
- rows per train example: [7, 7, 7]; test: 7

Train example 0: 7 rows
```
c0
r0-5 c0-0
r0-5 c1-1
r0-5 c2-2
r0-5 c3-3
r0-5 c4-4
r0-5 c5-5
r0-5 c6-6
```

Train example 1: 7 rows
```
c0
r0-5 c0-0
r0-5 c1-1
r0-5 c2-2
r0-5 c3-3
r0-5 c4-4
r0-5 c5-5
r0-5 c6-6
```

Train example 2: 7 rows
```
c0
r0-5 c0-0
r0-5 c1-1
r0-5 c2-2
r0-5 c3-3
r0-5 c4-4
r0-5 c5-5
r0-5 c6-6
```


#### &r6, assignment 4 of 4

- DET values that differ between the assignments: &r0 = {(DIR_R)}
- rows equal to those of assignment 3 at every example
### &r7 (export table 7)

- columns: c0: Axis, c1: Number
- depth 6, candidate keys none
- DETs its entries are assigned: &r0; assignments: 4

#### &r7, assignment 1 of 4

- DET values that differ between the assignments: &r0 = {(DIR_T)}
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1
AXIS_V | 6
```

Train example 1: 1 row
```
c0 | c1
AXIS_V | 6
```

Train example 2: 1 row
```
c0 | c1
AXIS_V | 6
```


#### &r7, assignment 2 of 4

- DET values that differ between the assignments: &r0 = {(DIR_B)}
- rows equal to those of assignment 1 at every example

#### &r7, assignment 3 of 4

- DET values that differ between the assignments: &r0 = {(DIR_L)}
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
```
c0 | c1
AXIS_H | 7
```

Train example 1: 1 row
```
c0 | c1
AXIS_H | 7
```

Train example 2: 1 row
```
c0 | c1
AXIS_H | 7
```


#### &r7, assignment 4 of 4

- DET values that differ between the assignments: &r0 = {(DIR_R)}
- rows equal to those of assignment 3 at every example
```
RULE &r6 :1 * [L0] &r1 :1 * [L1] margin :0 L0 :1 L1 :2 * [L2] &r2 :2 L2 END [&r8]
```

### &r8 (export table 8)

- columns: c0: Box, c1: Dir, c2: Number
- depth 8, candidate keys none
- DETs its entries are assigned: &r0; assignments: 4

#### &r8, assignment 1 of 4

- DET values that differ between the assignments: &r0 = {(DIR_T)}
- rows per train example: [6, 6, 6]; test: 6

Train example 0: 6 rows
```
c0 | c1 | c2
r0-0 c0-6 | DIR_B | 5
r1-1 c0-6 | DIR_B | 4
r2-2 c0-6 | DIR_B | 3
r3-3 c0-6 | DIR_B | 2
r4-4 c0-6 | DIR_B | 1
r5-5 c0-6 | DIR_B | 0
```

Train example 1: 6 rows
```
c0 | c1 | c2
r0-0 c0-6 | DIR_B | 5
r1-1 c0-6 | DIR_B | 4
r2-2 c0-6 | DIR_B | 3
r3-3 c0-6 | DIR_B | 2
r4-4 c0-6 | DIR_B | 1
r5-5 c0-6 | DIR_B | 0
```

Train example 2: 6 rows
```
c0 | c1 | c2
r0-0 c0-6 | DIR_B | 5
r1-1 c0-6 | DIR_B | 4
r2-2 c0-6 | DIR_B | 3
r3-3 c0-6 | DIR_B | 2
r4-4 c0-6 | DIR_B | 1
r5-5 c0-6 | DIR_B | 0
```


#### &r8, assignment 2 of 4

- DET values that differ between the assignments: &r0 = {(DIR_B)}
- rows per train example: [6, 6, 6]; test: 6

Train example 0: 6 rows
```
c0 | c1 | c2
r0-0 c0-6 | DIR_T | 0
r1-1 c0-6 | DIR_T | 1
r2-2 c0-6 | DIR_T | 2
r3-3 c0-6 | DIR_T | 3
r4-4 c0-6 | DIR_T | 4
r5-5 c0-6 | DIR_T | 5
```

Train example 1: 6 rows
```
c0 | c1 | c2
r0-0 c0-6 | DIR_T | 0
r1-1 c0-6 | DIR_T | 1
r2-2 c0-6 | DIR_T | 2
r3-3 c0-6 | DIR_T | 3
r4-4 c0-6 | DIR_T | 4
r5-5 c0-6 | DIR_T | 5
```

Train example 2: 6 rows
```
c0 | c1 | c2
r0-0 c0-6 | DIR_T | 0
r1-1 c0-6 | DIR_T | 1
r2-2 c0-6 | DIR_T | 2
r3-3 c0-6 | DIR_T | 3
r4-4 c0-6 | DIR_T | 4
r5-5 c0-6 | DIR_T | 5
```


#### &r8, assignment 3 of 4

- DET values that differ between the assignments: &r0 = {(DIR_L)}
- rows per train example: [7, 7, 7]; test: 7

Train example 0: 7 rows
```
c0 | c1 | c2
r0-5 c0-0 | DIR_R | 6
r0-5 c1-1 | DIR_R | 5
r0-5 c2-2 | DIR_R | 4
r0-5 c3-3 | DIR_R | 3
r0-5 c4-4 | DIR_R | 2
r0-5 c5-5 | DIR_R | 1
r0-5 c6-6 | DIR_R | 0
```

Train example 1: 7 rows
```
c0 | c1 | c2
r0-5 c0-0 | DIR_R | 6
r0-5 c1-1 | DIR_R | 5
r0-5 c2-2 | DIR_R | 4
r0-5 c3-3 | DIR_R | 3
r0-5 c4-4 | DIR_R | 2
r0-5 c5-5 | DIR_R | 1
r0-5 c6-6 | DIR_R | 0
```

Train example 2: 7 rows
```
c0 | c1 | c2
r0-5 c0-0 | DIR_R | 6
r0-5 c1-1 | DIR_R | 5
r0-5 c2-2 | DIR_R | 4
r0-5 c3-3 | DIR_R | 3
r0-5 c4-4 | DIR_R | 2
r0-5 c5-5 | DIR_R | 1
r0-5 c6-6 | DIR_R | 0
```


#### &r8, assignment 4 of 4

- DET values that differ between the assignments: &r0 = {(DIR_R)}
- rows per train example: [7, 7, 7]; test: 7

Train example 0: 7 rows
```
c0 | c1 | c2
r0-5 c0-0 | DIR_L | 0
r0-5 c1-1 | DIR_L | 1
r0-5 c2-2 | DIR_L | 2
r0-5 c3-3 | DIR_L | 3
r0-5 c4-4 | DIR_L | 4
r0-5 c5-5 | DIR_L | 5
r0-5 c6-6 | DIR_L | 6
```

Train example 1: 7 rows
```
c0 | c1 | c2
r0-5 c0-0 | DIR_L | 0
r0-5 c1-1 | DIR_L | 1
r0-5 c2-2 | DIR_L | 2
r0-5 c3-3 | DIR_L | 3
r0-5 c4-4 | DIR_L | 4
r0-5 c5-5 | DIR_L | 5
r0-5 c6-6 | DIR_L | 6
```

Train example 2: 7 rows
```
c0 | c1 | c2
r0-5 c0-0 | DIR_L | 0
r0-5 c1-1 | DIR_L | 1
r0-5 c2-2 | DIR_L | 2
r0-5 c3-3 | DIR_L | 3
r0-5 c4-4 | DIR_L | 4
r0-5 c5-5 | DIR_L | 5
r0-5 c6-6 | DIR_L | 6
```

```
DET DirDomain END [&r9]
```

### &r9 (export table 9)

- columns: D: Dir
- depth 1, candidate keys none
- DETs its entries are assigned: &r9; assignments: 4

#### &r9, assignment 1 of 4

- DET values that differ between the assignments: &r9 = {(DIR_T)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
DIR_T
```


#### &r9, assignment 2 of 4

- DET values that differ between the assignments: &r9 = {(DIR_B)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
DIR_B
```


#### &r9, assignment 3 of 4

- DET values that differ between the assignments: &r9 = {(DIR_L)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
DIR_L
```


#### &r9, assignment 4 of 4

- DET values that differ between the assignments: &r9 = {(DIR_R)}
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
DIR_R
```

```
DET DimDiff END [&r10]
```

### &r10 (export table 10)

- columns: D: Number
- depth 1, candidate keys none
- DETs its entries are assigned: &r10; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
D
1
```

```
DET RarestColor END [&r11]
```

### &r11 (export table 11)

- columns: C: Color
- depth 1, candidate keys none
- DETs its entries are assigned: &r11; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
C
2
```

```
RULE input :0 * [L0] :1 * [L1] &r9 :0 * [L2] margin :0 L0 :1 L2 :2 0 &r11 :0 L1 END [&r12]
```

### &r12 (export table 12)

- columns: c0: Box, c1: Dir, c2: Color
- depth 2, candidate keys none
- DETs its entries are assigned: &r9, &r11; assignments: 4

#### &r12, assignment 1 of 4

- DET values that differ between the assignments: &r9 = {(DIR_T)}
- rows per train example: [1, 0, 0]; test: 0

Train example 0: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(0,0) | DIR_T | 2
```

Train example 1: 0 rows

Train example 2: 0 rows


#### &r12, assignment 2 of 4

- DET values that differ between the assignments: &r9 = {(DIR_B)}
- rows per train example: [0, 0, 0]; test: 0


#### &r12, assignment 3 of 4

- DET values that differ between the assignments: &r9 = {(DIR_L)}
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(0,0) | DIR_L | 2
```

Train example 1: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . .
. . . . . . .
2 . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(2,0) | DIR_L | 2
```

Train example 2: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . .
. . . . . . .
. . . . . . .
2 . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(3,0) | DIR_L | 2
```


#### &r12, assignment 4 of 4

- DET values that differ between the assignments: &r9 = {(DIR_R)}
- empty at every example
```
INIT Order [:0] SKIP [:1] &r2 :3 * [L0] END [:0] END [:1] L0 END [:2] SKIP [:3] &r2 :3 * [L1] END [:0] END [:1] L1 END [:2] L1 END [:4] SKIP [&r13] [&r14] [&r15] [&r16] [&r17] [&r18] [&r19] [&r20] [&r21] [&r22]
```

### &r13 (export table 13)

- columns: c0: Number, c1: Number
- depth 5, candidate keys none
- DETs its entries are assigned: &r0; assignments: 4

#### &r13, assignment 1 of 4

- DET values that differ between the assignments: &r0 = {(DIR_T)}
- rows per train example: [6, 6, 6]; test: 6

Train example 0: 6 rows
```
c0 | c1
0 | 0
1 | 1
2 | 2
3 | 3
4 | 4
5 | 5
```

Train example 1: 6 rows
```
c0 | c1
0 | 0
1 | 1
2 | 2
3 | 3
4 | 4
5 | 5
```

Train example 2: 6 rows
```
c0 | c1
0 | 0
1 | 1
2 | 2
3 | 3
4 | 4
5 | 5
```


#### &r13, assignment 2 of 4

- DET values that differ between the assignments: &r0 = {(DIR_B)}
- rows equal to those of assignment 1 at every example

#### &r13, assignment 3 of 4

- DET values that differ between the assignments: &r0 = {(DIR_L)}
- rows per train example: [7, 7, 7]; test: 7

Train example 0: 7 rows
```
c0 | c1
0 | 0
1 | 1
2 | 2
3 | 3
4 | 4
5 | 5
6 | 6
```

Train example 1: 7 rows
```
c0 | c1
0 | 0
1 | 1
2 | 2
3 | 3
4 | 4
5 | 5
6 | 6
```

Train example 2: 7 rows
```
c0 | c1
0 | 0
1 | 1
2 | 2
3 | 3
4 | 4
5 | 5
6 | 6
```


#### &r13, assignment 4 of 4

- DET values that differ between the assignments: &r0 = {(DIR_R)}
- rows equal to those of assignment 3 at every example
### &r14 (export table 14)

- columns: c0: Number, c1: Number
- depth 5, candidate keys none
- DETs its entries are assigned: &r0; assignments: 4

#### &r14, assignment 1 of 4

- DET values that differ between the assignments: &r0 = {(DIR_T)}
- rows per train example: [6, 6, 6]; test: 6

Train example 0: 6 rows
```
c0 | c1
0 | 5
1 | 4
2 | 3
3 | 2
4 | 1
5 | 0
```

Train example 1: 6 rows
```
c0 | c1
0 | 5
1 | 4
2 | 3
3 | 2
4 | 1
5 | 0
```

Train example 2: 6 rows
```
c0 | c1
0 | 5
1 | 4
2 | 3
3 | 2
4 | 1
5 | 0
```


#### &r14, assignment 2 of 4

- DET values that differ between the assignments: &r0 = {(DIR_B)}
- rows equal to those of assignment 1 at every example

#### &r14, assignment 3 of 4

- DET values that differ between the assignments: &r0 = {(DIR_L)}
- rows per train example: [7, 7, 7]; test: 7

Train example 0: 7 rows
```
c0 | c1
0 | 6
1 | 5
2 | 4
3 | 3
4 | 2
5 | 1
6 | 0
```

Train example 1: 7 rows
```
c0 | c1
0 | 6
1 | 5
2 | 4
3 | 3
4 | 2
5 | 1
6 | 0
```

Train example 2: 7 rows
```
c0 | c1
0 | 6
1 | 5
2 | 4
3 | 3
4 | 2
5 | 1
6 | 0
```


#### &r14, assignment 4 of 4

- DET values that differ between the assignments: &r0 = {(DIR_R)}
- rows equal to those of assignment 3 at every example
### &r15 (export table 15)

- columns: c0: Number
- depth 5, candidate keys none
- DETs its entries are assigned: &r0; assignments: 4

#### &r15, assignment 1 of 4

- DET values that differ between the assignments: &r0 = {(DIR_T)}
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


#### &r15, assignment 2 of 4

- DET values that differ between the assignments: &r0 = {(DIR_B)}
- rows equal to those of assignment 1 at every example

#### &r15, assignment 3 of 4

- DET values that differ between the assignments: &r0 = {(DIR_L)}
- rows equal to those of assignment 1 at every example

#### &r15, assignment 4 of 4

- DET values that differ between the assignments: &r0 = {(DIR_R)}
- rows equal to those of assignment 1 at every example
### &r16 (export table 16)

- columns: c0: Number
- depth 5, candidate keys none
- DETs its entries are assigned: &r0; assignments: 4

#### &r16, assignment 1 of 4

- DET values that differ between the assignments: &r0 = {(DIR_T)}
- rows per train example: [1, 1, 1]; test: 1

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


#### &r16, assignment 2 of 4

- DET values that differ between the assignments: &r0 = {(DIR_B)}
- rows equal to those of assignment 1 at every example

#### &r16, assignment 3 of 4

- DET values that differ between the assignments: &r0 = {(DIR_L)}
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
6
```

Train example 1: 1 row
```
c0
6
```

Train example 2: 1 row
```
c0
6
```


#### &r16, assignment 4 of 4

- DET values that differ between the assignments: &r0 = {(DIR_R)}
- rows equal to those of assignment 3 at every example
### &r17 (export table 17)

- columns: c0: Number, c1: Number
- depth 5, candidate keys none
- DETs its entries are assigned: &r0; assignments: 4

#### &r17, assignment 1 of 4

- DET values that differ between the assignments: &r0 = {(DIR_T)}
- rows per train example: [5, 5, 5]; test: 5

Train example 0: 5 rows
```
c0 | c1
0 | 1
1 | 2
2 | 3
3 | 4
4 | 5
```

Train example 1: 5 rows
```
c0 | c1
0 | 1
1 | 2
2 | 3
3 | 4
4 | 5
```

Train example 2: 5 rows
```
c0 | c1
0 | 1
1 | 2
2 | 3
3 | 4
4 | 5
```


#### &r17, assignment 2 of 4

- DET values that differ between the assignments: &r0 = {(DIR_B)}
- rows equal to those of assignment 1 at every example

#### &r17, assignment 3 of 4

- DET values that differ between the assignments: &r0 = {(DIR_L)}
- rows per train example: [6, 6, 6]; test: 6

Train example 0: 6 rows
```
c0 | c1
0 | 1
1 | 2
2 | 3
3 | 4
4 | 5
5 | 6
```

Train example 1: 6 rows
```
c0 | c1
0 | 1
1 | 2
2 | 3
3 | 4
4 | 5
5 | 6
```

Train example 2: 6 rows
```
c0 | c1
0 | 1
1 | 2
2 | 3
3 | 4
4 | 5
5 | 6
```


#### &r17, assignment 4 of 4

- DET values that differ between the assignments: &r0 = {(DIR_R)}
- rows equal to those of assignment 3 at every example
### &r18 (export table 18)

- columns: c0: Number, c1: Number
- depth 5, candidate keys none
- DETs its entries are assigned: &r0; assignments: 4

#### &r18, assignment 1 of 4

- DET values that differ between the assignments: &r0 = {(DIR_T)}
- rows per train example: [6, 6, 6]; test: 6

Train example 0: 6 rows
```
c0 | c1
0 | 1
1 | 2
2 | 3
3 | 4
4 | 5
5 | 0
```

Train example 1: 6 rows
```
c0 | c1
0 | 1
1 | 2
2 | 3
3 | 4
4 | 5
5 | 0
```

Train example 2: 6 rows
```
c0 | c1
0 | 1
1 | 2
2 | 3
3 | 4
4 | 5
5 | 0
```


#### &r18, assignment 2 of 4

- DET values that differ between the assignments: &r0 = {(DIR_B)}
- rows equal to those of assignment 1 at every example

#### &r18, assignment 3 of 4

- DET values that differ between the assignments: &r0 = {(DIR_L)}
- rows per train example: [7, 7, 7]; test: 7

Train example 0: 7 rows
```
c0 | c1
0 | 1
1 | 2
2 | 3
3 | 4
4 | 5
5 | 6
6 | 0
```

Train example 1: 7 rows
```
c0 | c1
0 | 1
1 | 2
2 | 3
3 | 4
4 | 5
5 | 6
6 | 0
```

Train example 2: 7 rows
```
c0 | c1
0 | 1
1 | 2
2 | 3
3 | 4
4 | 5
5 | 6
6 | 0
```


#### &r18, assignment 4 of 4

- DET values that differ between the assignments: &r0 = {(DIR_R)}
- rows equal to those of assignment 3 at every example
```
RULE &r12 :0 * [L0] &r1 :1 * [L1] margin :0 L0 :1 L1 :2 * [L2] END [&r23]
```

### &r23 (export table 19)

- columns: c0: Box, c1: Dir, c2: Number
- depth 3, candidate keys none
- DETs its entries are assigned: &r0, &r9, &r11; assignments: 16

#### &r23, assignment 1 of 16

- DET values that differ between the assignments: &r0 = {(DIR_T)}; &r9 = {(DIR_T)}
- rows per train example: [1, 0, 0]; test: 0

Train example 0: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(0,0) | DIR_B | 5
```

Train example 1: 0 rows

Train example 2: 0 rows


#### &r23, assignment 2 of 16

- DET values that differ between the assignments: &r0 = {(DIR_T)}; &r9 = {(DIR_B)}
- rows per train example: [0, 0, 0]; test: 0


#### &r23, assignment 3 of 16

- DET values that differ between the assignments: &r0 = {(DIR_T)}; &r9 = {(DIR_L)}
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
5 . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(0,0) | DIR_B | 5
```

Train example 1: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . . .
. . . . . . .
3 . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(2,0) | DIR_B | 3
```

Train example 2: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . . .
. . . . . . .
. . . . . . .
2 . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(3,0) | DIR_B | 2
```


#### &r23, assignment 4 of 16

- DET values that differ between the assignments: &r0 = {(DIR_T)}; &r9 = {(DIR_R)}
- empty at every example

#### &r23, assignment 5 of 16

- DET values that differ between the assignments: &r0 = {(DIR_B)}; &r9 = {(DIR_T)}
- rows per train example: [1, 0, 0]; test: 0

Train example 0: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(0,0) | DIR_T | 0
```

Train example 1: 0 rows

Train example 2: 0 rows


#### &r23, assignment 6 of 16

- DET values that differ between the assignments: &r0 = {(DIR_B)}; &r9 = {(DIR_B)}
- empty at every example

#### &r23, assignment 7 of 16

- DET values that differ between the assignments: &r0 = {(DIR_B)}; &r9 = {(DIR_L)}
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(0,0) | DIR_T | 0
```

Train example 1: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . . .
. . . . . . .
2 . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(2,0) | DIR_T | 2
```

Train example 2: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . . .
. . . . . . .
. . . . . . .
3 . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(3,0) | DIR_T | 3
```


#### &r23, assignment 8 of 16

- DET values that differ between the assignments: &r0 = {(DIR_B)}; &r9 = {(DIR_R)}
- empty at every example

#### &r23, assignment 9 of 16

- DET values that differ between the assignments: &r0 = {(DIR_L)}; &r9 = {(DIR_T)}
- rows per train example: [1, 0, 0]; test: 0

Train example 0: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
6 . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(0,0) | DIR_R | 6
```

Train example 1: 0 rows

Train example 2: 0 rows


#### &r23, assignment 10 of 16

- DET values that differ between the assignments: &r0 = {(DIR_L)}; &r9 = {(DIR_B)}
- empty at every example

#### &r23, assignment 11 of 16

- DET values that differ between the assignments: &r0 = {(DIR_L)}; &r9 = {(DIR_L)}
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
6 . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(0,0) | DIR_R | 6
```

Train example 1: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . . .
. . . . . . .
6 . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(2,0) | DIR_R | 6
```

Train example 2: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . . .
. . . . . . .
. . . . . . .
6 . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(3,0) | DIR_R | 6
```


#### &r23, assignment 12 of 16

- DET values that differ between the assignments: &r0 = {(DIR_L)}; &r9 = {(DIR_R)}
- empty at every example

#### &r23, assignment 13 of 16

- DET values that differ between the assignments: &r0 = {(DIR_R)}; &r9 = {(DIR_T)}
- rows per train example: [1, 0, 0]; test: 0

Train example 0: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(0,0) | DIR_L | 0
```

Train example 1: 0 rows

Train example 2: 0 rows


#### &r23, assignment 14 of 16

- DET values that differ between the assignments: &r0 = {(DIR_R)}; &r9 = {(DIR_B)}
- empty at every example

#### &r23, assignment 15 of 16

- DET values that differ between the assignments: &r0 = {(DIR_R)}; &r9 = {(DIR_L)}
- rows per train example: [1, 1, 1]; test: 1

Train example 0: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
0 . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(0,0) | DIR_L | 0
```

Train example 1: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . . .
. . . . . . .
0 . . . . . .
. . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(2,0) | DIR_L | 0
```

Train example 2: 1 row
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Number, '.' where no row is:
```
. . . . . . .
. . . . . . .
. . . . . . .
0 . . . . . .
. . . . . . .
. . . . . . .
```
```
c0 | c1 | c2
(3,0) | DIR_L | 0
```


#### &r23, assignment 16 of 16

- DET values that differ between the assignments: &r0 = {(DIR_R)}; &r9 = {(DIR_R)}
- empty at every example
```
INIT Walk [:0] SKIP [:1] &r18 :2 * [L0] :3 * [L1] END [:0] END [:1] L0 END [:2] L1 END [:2] &r23 :3 * [L2] END [:0] END [:1] L2 END [&r24] [&r25] [&r26]
```

### &r24 (export table 20)

- columns: c0: Number, c1: Number, c2: Number
- depth 7, candidate keys none
- DETs its entries are assigned: &r0, &r9, &r11; assignments: 16

#### &r24, assignment 1 of 16

- DET values that differ between the assignments: &r0 = {(DIR_T)}; &r9 = {(DIR_T)}
- rows per train example: [36, 6, 6]; test: 6

Train example 0: 36 rows, the first 30 shown
```
c0 | c1 | c2
0 | 0 | 0
0 | 1 | 1
0 | 2 | 2
0 | 3 | 3
0 | 4 | 4
0 | 5 | 5
1 | 0 | 1
1 | 1 | 2
1 | 2 | 3
1 | 3 | 4
1 | 4 | 5
1 | 5 | 0
2 | 0 | 2
2 | 1 | 3
2 | 2 | 4
2 | 3 | 5
2 | 4 | 0
2 | 5 | 1
3 | 0 | 3
3 | 1 | 4
3 | 2 | 5
3 | 3 | 0
3 | 4 | 1
3 | 5 | 2
4 | 0 | 4
4 | 1 | 5
4 | 2 | 0
4 | 3 | 1
4 | 4 | 2
4 | 5 | 3
```

Train example 1: 6 rows
```
c0 | c1 | c2
0 | 0 | 0
1 | 0 | 1
2 | 0 | 2
3 | 0 | 3
4 | 0 | 4
5 | 0 | 5
```

Train example 2: 6 rows
```
c0 | c1 | c2
0 | 0 | 0
1 | 0 | 1
2 | 0 | 2
3 | 0 | 3
4 | 0 | 4
5 | 0 | 5
```


#### &r24, assignment 2 of 16

- DET values that differ between the assignments: &r0 = {(DIR_T)}; &r9 = {(DIR_B)}
- rows per train example: [6, 6, 6]; test: 6

Train example 0: 6 rows
```
c0 | c1 | c2
0 | 0 | 0
1 | 0 | 1
2 | 0 | 2
3 | 0 | 3
4 | 0 | 4
5 | 0 | 5
```

Train example 1: 6 rows
```
c0 | c1 | c2
0 | 0 | 0
1 | 0 | 1
2 | 0 | 2
3 | 0 | 3
4 | 0 | 4
5 | 0 | 5
```

Train example 2: 6 rows
```
c0 | c1 | c2
0 | 0 | 0
1 | 0 | 1
2 | 0 | 2
3 | 0 | 3
4 | 0 | 4
5 | 0 | 5
```


#### &r24, assignment 3 of 16

- DET values that differ between the assignments: &r0 = {(DIR_T)}; &r9 = {(DIR_L)}
- rows per train example: [36, 24, 18]; test: 30

Train example 0: 36 rows, the first 30 shown
```
c0 | c1 | c2
0 | 0 | 0
0 | 1 | 1
0 | 2 | 2
0 | 3 | 3
0 | 4 | 4
0 | 5 | 5
1 | 0 | 1
1 | 1 | 2
1 | 2 | 3
1 | 3 | 4
1 | 4 | 5
1 | 5 | 0
2 | 0 | 2
2 | 1 | 3
2 | 2 | 4
2 | 3 | 5
2 | 4 | 0
2 | 5 | 1
3 | 0 | 3
3 | 1 | 4
3 | 2 | 5
3 | 3 | 0
3 | 4 | 1
3 | 5 | 2
4 | 0 | 4
4 | 1 | 5
4 | 2 | 0
4 | 3 | 1
4 | 4 | 2
4 | 5 | 3
```

Train example 1: 24 rows
```
c0 | c1 | c2
0 | 0 | 0
0 | 1 | 1
0 | 2 | 2
0 | 3 | 3
1 | 0 | 1
1 | 1 | 2
1 | 2 | 3
1 | 3 | 4
2 | 0 | 2
2 | 1 | 3
2 | 2 | 4
2 | 3 | 5
3 | 0 | 3
3 | 1 | 4
3 | 2 | 5
3 | 3 | 0
4 | 0 | 4
4 | 1 | 5
4 | 2 | 0
4 | 3 | 1
5 | 0 | 5
5 | 1 | 0
5 | 2 | 1
5 | 3 | 2
```

Train example 2: 18 rows
```
c0 | c1 | c2
0 | 0 | 0
0 | 1 | 1
0 | 2 | 2
1 | 0 | 1
1 | 1 | 2
1 | 2 | 3
2 | 0 | 2
2 | 1 | 3
2 | 2 | 4
3 | 0 | 3
3 | 1 | 4
3 | 2 | 5
4 | 0 | 4
4 | 1 | 5
4 | 2 | 0
5 | 0 | 5
5 | 1 | 0
5 | 2 | 1
```


#### &r24, assignment 4 of 16

- DET values that differ between the assignments: &r0 = {(DIR_T)}; &r9 = {(DIR_R)}
- rows equal to those of assignment 2 at every example

#### &r24, assignment 5 of 16

- DET values that differ between the assignments: &r0 = {(DIR_B)}; &r9 = {(DIR_T)}
- rows equal to those of assignment 2 at every example

#### &r24, assignment 6 of 16

- DET values that differ between the assignments: &r0 = {(DIR_B)}; &r9 = {(DIR_B)}
- rows equal to those of assignment 2 at every example

#### &r24, assignment 7 of 16

- DET values that differ between the assignments: &r0 = {(DIR_B)}; &r9 = {(DIR_L)}
- rows per train example: [6, 18, 24]; test: 12

Train example 0: 6 rows
```
c0 | c1 | c2
0 | 0 | 0
1 | 0 | 1
2 | 0 | 2
3 | 0 | 3
4 | 0 | 4
5 | 0 | 5
```

Train example 1: 18 rows
```
c0 | c1 | c2
0 | 0 | 0
0 | 1 | 1
0 | 2 | 2
1 | 0 | 1
1 | 1 | 2
1 | 2 | 3
2 | 0 | 2
2 | 1 | 3
2 | 2 | 4
3 | 0 | 3
3 | 1 | 4
3 | 2 | 5
4 | 0 | 4
4 | 1 | 5
4 | 2 | 0
5 | 0 | 5
5 | 1 | 0
5 | 2 | 1
```

Train example 2: 24 rows
```
c0 | c1 | c2
0 | 0 | 0
0 | 1 | 1
0 | 2 | 2
0 | 3 | 3
1 | 0 | 1
1 | 1 | 2
1 | 2 | 3
1 | 3 | 4
2 | 0 | 2
2 | 1 | 3
2 | 2 | 4
2 | 3 | 5
3 | 0 | 3
3 | 1 | 4
3 | 2 | 5
3 | 3 | 0
4 | 0 | 4
4 | 1 | 5
4 | 2 | 0
4 | 3 | 1
5 | 0 | 5
5 | 1 | 0
5 | 2 | 1
5 | 3 | 2
```


#### &r24, assignment 8 of 16

- DET values that differ between the assignments: &r0 = {(DIR_B)}; &r9 = {(DIR_R)}
- rows equal to those of assignment 2 at every example

#### &r24, assignment 9 of 16

- DET values that differ between the assignments: &r0 = {(DIR_L)}; &r9 = {(DIR_T)}
- rows per train example: [49, 7, 7]; test: 7

Train example 0: 49 rows, the first 30 shown
```
c0 | c1 | c2
0 | 0 | 0
0 | 1 | 1
0 | 2 | 2
0 | 3 | 3
0 | 4 | 4
0 | 5 | 5
0 | 6 | 6
1 | 0 | 1
1 | 1 | 2
1 | 2 | 3
1 | 3 | 4
1 | 4 | 5
1 | 5 | 6
1 | 6 | 0
2 | 0 | 2
2 | 1 | 3
2 | 2 | 4
2 | 3 | 5
2 | 4 | 6
2 | 5 | 0
2 | 6 | 1
3 | 0 | 3
3 | 1 | 4
3 | 2 | 5
3 | 3 | 6
3 | 4 | 0
3 | 5 | 1
3 | 6 | 2
4 | 0 | 4
4 | 1 | 5
```

Train example 1: 7 rows
```
c0 | c1 | c2
0 | 0 | 0
1 | 0 | 1
2 | 0 | 2
3 | 0 | 3
4 | 0 | 4
5 | 0 | 5
6 | 0 | 6
```

Train example 2: 7 rows
```
c0 | c1 | c2
0 | 0 | 0
1 | 0 | 1
2 | 0 | 2
3 | 0 | 3
4 | 0 | 4
5 | 0 | 5
6 | 0 | 6
```


#### &r24, assignment 10 of 16

- DET values that differ between the assignments: &r0 = {(DIR_L)}; &r9 = {(DIR_B)}
- rows per train example: [7, 7, 7]; test: 7

Train example 0: 7 rows
```
c0 | c1 | c2
0 | 0 | 0
1 | 0 | 1
2 | 0 | 2
3 | 0 | 3
4 | 0 | 4
5 | 0 | 5
6 | 0 | 6
```

Train example 1: 7 rows
```
c0 | c1 | c2
0 | 0 | 0
1 | 0 | 1
2 | 0 | 2
3 | 0 | 3
4 | 0 | 4
5 | 0 | 5
6 | 0 | 6
```

Train example 2: 7 rows
```
c0 | c1 | c2
0 | 0 | 0
1 | 0 | 1
2 | 0 | 2
3 | 0 | 3
4 | 0 | 4
5 | 0 | 5
6 | 0 | 6
```


#### &r24, assignment 11 of 16

- DET values that differ between the assignments: &r0 = {(DIR_L)}; &r9 = {(DIR_L)}
- rows per train example: [49, 49, 49]; test: 49

Train example 0: 49 rows, the first 30 shown
```
c0 | c1 | c2
0 | 0 | 0
0 | 1 | 1
0 | 2 | 2
0 | 3 | 3
0 | 4 | 4
0 | 5 | 5
0 | 6 | 6
1 | 0 | 1
1 | 1 | 2
1 | 2 | 3
1 | 3 | 4
1 | 4 | 5
1 | 5 | 6
1 | 6 | 0
2 | 0 | 2
2 | 1 | 3
2 | 2 | 4
2 | 3 | 5
2 | 4 | 6
2 | 5 | 0
2 | 6 | 1
3 | 0 | 3
3 | 1 | 4
3 | 2 | 5
3 | 3 | 6
3 | 4 | 0
3 | 5 | 1
3 | 6 | 2
4 | 0 | 4
4 | 1 | 5
```

Train example 1: 49 rows, the first 30 shown
```
c0 | c1 | c2
0 | 0 | 0
0 | 1 | 1
0 | 2 | 2
0 | 3 | 3
0 | 4 | 4
0 | 5 | 5
0 | 6 | 6
1 | 0 | 1
1 | 1 | 2
1 | 2 | 3
1 | 3 | 4
1 | 4 | 5
1 | 5 | 6
1 | 6 | 0
2 | 0 | 2
2 | 1 | 3
2 | 2 | 4
2 | 3 | 5
2 | 4 | 6
2 | 5 | 0
2 | 6 | 1
3 | 0 | 3
3 | 1 | 4
3 | 2 | 5
3 | 3 | 6
3 | 4 | 0
3 | 5 | 1
3 | 6 | 2
4 | 0 | 4
4 | 1 | 5
```

Train example 2: 49 rows, the first 30 shown
```
c0 | c1 | c2
0 | 0 | 0
0 | 1 | 1
0 | 2 | 2
0 | 3 | 3
0 | 4 | 4
0 | 5 | 5
0 | 6 | 6
1 | 0 | 1
1 | 1 | 2
1 | 2 | 3
1 | 3 | 4
1 | 4 | 5
1 | 5 | 6
1 | 6 | 0
2 | 0 | 2
2 | 1 | 3
2 | 2 | 4
2 | 3 | 5
2 | 4 | 6
2 | 5 | 0
2 | 6 | 1
3 | 0 | 3
3 | 1 | 4
3 | 2 | 5
3 | 3 | 6
3 | 4 | 0
3 | 5 | 1
3 | 6 | 2
4 | 0 | 4
4 | 1 | 5
```


#### &r24, assignment 12 of 16

- DET values that differ between the assignments: &r0 = {(DIR_L)}; &r9 = {(DIR_R)}
- rows equal to those of assignment 10 at every example

#### &r24, assignment 13 of 16

- DET values that differ between the assignments: &r0 = {(DIR_R)}; &r9 = {(DIR_T)}
- rows equal to those of assignment 10 at every example

#### &r24, assignment 14 of 16

- DET values that differ between the assignments: &r0 = {(DIR_R)}; &r9 = {(DIR_B)}
- rows equal to those of assignment 10 at every example

#### &r24, assignment 15 of 16

- DET values that differ between the assignments: &r0 = {(DIR_R)}; &r9 = {(DIR_L)}
- rows equal to those of assignment 10 at every example

#### &r24, assignment 16 of 16

- DET values that differ between the assignments: &r0 = {(DIR_R)}; &r9 = {(DIR_R)}
- rows equal to those of assignment 10 at every example
```
RULE input :0 * [L0] :1 * [L1] &r9 :0 * [L2] &r10 :0 * [L3] edge_inset :0 L2 :1 L3 :2 * [L4] inside :0 L0 :1 L4 relative :0 L4 :1 L0 :2 * [L5] &r1 :1 * [L6] margin :0 L0 :1 L6 :2 * [L7] &r23 :2 * [L8] &r24 :1 L7 :2 L8 :3 * [L9] &r8 :2 L9 :0 * [L10] axis_of :0 L2 :1 * [L11] split :0 L5 :1 L11 :2 * [L12] compose :0 L10 :1 L12 :2 * [L13] END [&r27]
```

### &r27 (export table 21)

- columns: c0: Box, c1: Box, c2: Number, c3: Dir, c4: Color, c5: Axis, c6: Dir, c7: Box, c8: Number, c9: Box, c10: Box, c11: Box, c12: Number, c13: Number
- depth 9, candidate keys none
- DETs its entries are assigned: &r0, &r9, &r10, &r11; assignments: 16

#### &r27, assignment 1 of 16

- DET values that differ between the assignments: &r0 = {(DIR_T)}; &r9 = {(DIR_T)}
- rows per train example: [35, 0, 0]; test: 0

Train example 0: 35 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . .
6 4 3 9 9 9 8
6 4 3 9 3 8 8
6 4 3 3 3 8 8
6 4 8 8 5 5 5
6 4 5 5 5 3 3
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13
(1,0) | r2-2 c0-6 | 1 | DIR_T | 6 | AXIS_V | DIR_B | r0-1 c0-6 | 4 | [2 7 0 0] | r0-1 c0-0 | r1-5 c0-6 | 5 | 3
(1,1) | r2-2 c0-6 | 1 | DIR_T | 4 | AXIS_V | DIR_B | r0-1 c0-6 | 4 | [2 7 0 0] | r0-1 c1-1 | r1-5 c0-6 | 5 | 3
(1,2) | r2-2 c0-6 | 1 | DIR_T | 3 | AXIS_V | DIR_B | r0-1 c0-6 | 4 | [2 7 0 0] | r0-1 c2-2 | r1-5 c0-6 | 5 | 3
(1,3) | r2-2 c0-6 | 1 | DIR_T | 9 | AXIS_V | DIR_B | r0-1 c0-6 | 4 | [2 7 0 0] | r0-1 c3-3 | r1-5 c0-6 | 5 | 3
(1,4) | r2-2 c0-6 | 1 | DIR_T | 9 | AXIS_V | DIR_B | r0-1 c0-6 | 4 | [2 7 0 0] | r0-1 c4-4 | r1-5 c0-6 | 5 | 3
(1,5) | r2-2 c0-6 | 1 | DIR_T | 9 | AXIS_V | DIR_B | r0-1 c0-6 | 4 | [2 7 0 0] | r0-1 c5-5 | r1-5 c0-6 | 5 | 3
(1,6) | r2-2 c0-6 | 1 | DIR_T | 8 | AXIS_V | DIR_B | r0-1 c0-6 | 4 | [2 7 0 0] | r0-1 c6-6 | r1-5 c0-6 | 5 | 3
(2,0) | r3-3 c0-6 | 1 | DIR_T | 6 | AXIS_V | DIR_B | r1-2 c0-6 | 3 | [4 5 0 0] | r1-2 c0-0 | r1-5 c0-6 | 5 | 2
(2,1) | r3-3 c0-6 | 1 | DIR_T | 4 | AXIS_V | DIR_B | r1-2 c0-6 | 3 | [4 5 0 0] | r1-2 c1-1 | r1-5 c0-6 | 5 | 2
(2,2) | r3-3 c0-6 | 1 | DIR_T | 3 | AXIS_V | DIR_B | r1-2 c0-6 | 3 | [4 5 0 0] | r1-2 c2-2 | r1-5 c0-6 | 5 | 2
(2,3) | r3-3 c0-6 | 1 | DIR_T | 9 | AXIS_V | DIR_B | r1-2 c0-6 | 3 | [4 5 0 0] | r1-2 c3-3 | r1-5 c0-6 | 5 | 2
(2,4) | r3-3 c0-6 | 1 | DIR_T | 3 | AXIS_V | DIR_B | r1-2 c0-6 | 3 | [4 5 0 0] | r1-2 c4-4 | r1-5 c0-6 | 5 | 2
(2,5) | r3-3 c0-6 | 1 | DIR_T | 8 | AXIS_V | DIR_B | r1-2 c0-6 | 3 | [4 5 0 0] | r1-2 c5-5 | r1-5 c0-6 | 5 | 2
(2,6) | r3-3 c0-6 | 1 | DIR_T | 8 | AXIS_V | DIR_B | r1-2 c0-6 | 3 | [4 5 0 0] | r1-2 c6-6 | r1-5 c0-6 | 5 | 2
(3,0) | r4-4 c0-6 | 1 | DIR_T | 6 | AXIS_V | DIR_B | r2-3 c0-6 | 2 | [6 3 0 0] | r2-3 c0-0 | r1-5 c0-6 | 5 | 1
(3,1) | r4-4 c0-6 | 1 | DIR_T | 4 | AXIS_V | DIR_B | r2-3 c0-6 | 2 | [6 3 0 0] | r2-3 c1-1 | r1-5 c0-6 | 5 | 1
(3,2) | r4-4 c0-6 | 1 | DIR_T | 3 | AXIS_V | DIR_B | r2-3 c0-6 | 2 | [6 3 0 0] | r2-3 c2-2 | r1-5 c0-6 | 5 | 1
(3,3) | r4-4 c0-6 | 1 | DIR_T | 3 | AXIS_V | DIR_B | r2-3 c0-6 | 2 | [6 3 0 0] | r2-3 c3-3 | r1-5 c0-6 | 5 | 1
(3,4) | r4-4 c0-6 | 1 | DIR_T | 3 | AXIS_V | DIR_B | r2-3 c0-6 | 2 | [6 3 0 0] | r2-3 c4-4 | r1-5 c0-6 | 5 | 1
(3,5) | r4-4 c0-6 | 1 | DIR_T | 8 | AXIS_V | DIR_B | r2-3 c0-6 | 2 | [6 3 0 0] | r2-3 c5-5 | r1-5 c0-6 | 5 | 1
(3,6) | r4-4 c0-6 | 1 | DIR_T | 8 | AXIS_V | DIR_B | r2-3 c0-6 | 2 | [6 3 0 0] | r2-3 c6-6 | r1-5 c0-6 | 5 | 1
(4,0) | r5-5 c0-6 | 1 | DIR_T | 6 | AXIS_V | DIR_B | r3-4 c0-6 | 1 | [8 1 0 0] | r3-4 c0-0 | r1-5 c0-6 | 5 | 0
(4,1) | r5-5 c0-6 | 1 | DIR_T | 4 | AXIS_V | DIR_B | r3-4 c0-6 | 1 | [8 1 0 0] | r3-4 c1-1 | r1-5 c0-6 | 5 | 0
(4,2) | r5-5 c0-6 | 1 | DIR_T | 8 | AXIS_V | DIR_B | r3-4 c0-6 | 1 | [8 1 0 0] | r3-4 c2-2 | r1-5 c0-6 | 5 | 0
(4,3) | r5-5 c0-6 | 1 | DIR_T | 8 | AXIS_V | DIR_B | r3-4 c0-6 | 1 | [8 1 0 0] | r3-4 c3-3 | r1-5 c0-6 | 5 | 0
(4,4) | r5-5 c0-6 | 1 | DIR_T | 5 | AXIS_V | DIR_B | r3-4 c0-6 | 1 | [8 1 0 0] | r3-4 c4-4 | r1-5 c0-6 | 5 | 0
(4,5) | r5-5 c0-6 | 1 | DIR_T | 5 | AXIS_V | DIR_B | r3-4 c0-6 | 1 | [8 1 0 0] | r3-4 c5-5 | r1-5 c0-6 | 5 | 0
(4,6) | r5-5 c0-6 | 1 | DIR_T | 5 | AXIS_V | DIR_B | r3-4 c0-6 | 1 | [8 1 0 0] | r3-4 c6-6 | r1-5 c0-6 | 5 | 0
(5,0) | r0-0 c0-6 | 1 | DIR_T | 6 | AXIS_V | DIR_B | r4-5 c0-6 | 0 | [4 5 0 0] | r4-5 c0-0 | r1-5 c0-6 | 5 | 5
(5,1) | r0-0 c0-6 | 1 | DIR_T | 4 | AXIS_V | DIR_B | r4-5 c0-6 | 0 | [4 5 0 0] | r4-5 c1-1 | r1-5 c0-6 | 5 | 5
```

Train example 1: 0 rows

Train example 2: 0 rows


#### &r27, assignment 2 of 16

- DET values that differ between the assignments: &r0 = {(DIR_T)}; &r9 = {(DIR_B)}
- rows per train example: [0, 0, 0]; test: 0


#### &r27, assignment 3 of 16

- DET values that differ between the assignments: &r0 = {(DIR_T)}; &r9 = {(DIR_L)}
- rows per train example: [36, 36, 36]; test: 36

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 1 1 1 1 9 8
. 4 3 9 9 9 8
. 4 3 9 3 8 8
. 4 3 3 3 8 8
. 4 8 8 5 5 5
. 4 5 5 5 3 3
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13
(0,1) | r1-1 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_B | r0-5 c0-1 | 5 | (1,0)out | (0,0)out | r0-5 c1-6 | 5 | 4
(0,2) | r1-1 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_B | r0-5 c1-2 | 5 | (1,1)out | (0,1)out | r0-5 c1-6 | 5 | 4
(0,3) | r1-1 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_B | r0-5 c2-3 | 5 | (1,2)out | (0,2)out | r0-5 c1-6 | 5 | 4
(0,4) | r1-1 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_B | r0-5 c3-4 | 5 | (1,3)out | (0,3)out | r0-5 c1-6 | 5 | 4
(0,5) | r1-1 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_B | r0-5 c4-5 | 5 | (1,4)out | (0,4)out | r0-5 c1-6 | 5 | 4
(0,6) | r1-1 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c5-6 | 5 | (1,5)out | (0,5)out | r0-5 c1-6 | 5 | 4
(1,1) | r2-2 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_B | r0-5 c0-1 | 4 | (2,0)out | (1,0)out | r0-5 c1-6 | 5 | 3
(1,2) | r2-2 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_B | r0-5 c1-2 | 4 | (2,1)out | (1,1)out | r0-5 c1-6 | 5 | 3
(1,3) | r2-2 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_B | r0-5 c2-3 | 4 | (2,2)out | (1,2)out | r0-5 c1-6 | 5 | 3
(1,4) | r2-2 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_B | r0-5 c3-4 | 4 | (2,3)out | (1,3)out | r0-5 c1-6 | 5 | 3
(1,5) | r2-2 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_B | r0-5 c4-5 | 4 | (2,4)out | (1,4)out | r0-5 c1-6 | 5 | 3
(1,6) | r2-2 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c5-6 | 4 | (2,5)out | (1,5)out | r0-5 c1-6 | 5 | 3
(2,1) | r3-3 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_B | r0-5 c0-1 | 3 | (3,0)out | (2,0)out | r0-5 c1-6 | 5 | 2
(2,2) | r3-3 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_B | r0-5 c1-2 | 3 | (3,1)out | (2,1)out | r0-5 c1-6 | 5 | 2
(2,3) | r3-3 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_B | r0-5 c2-3 | 3 | (3,2)out | (2,2)out | r0-5 c1-6 | 5 | 2
(2,4) | r3-3 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_B | r0-5 c3-4 | 3 | (3,3)out | (2,3)out | r0-5 c1-6 | 5 | 2
(2,5) | r3-3 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c4-5 | 3 | (3,4)out | (2,4)out | r0-5 c1-6 | 5 | 2
(2,6) | r3-3 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c5-6 | 3 | (3,5)out | (2,5)out | r0-5 c1-6 | 5 | 2
(3,1) | r4-4 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_B | r0-5 c0-1 | 2 | (4,0)out | (3,0)out | r0-5 c1-6 | 5 | 1
(3,2) | r4-4 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_B | r0-5 c1-2 | 2 | (4,1)out | (3,1)out | r0-5 c1-6 | 5 | 1
(3,3) | r4-4 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_B | r0-5 c2-3 | 2 | (4,2)out | (3,2)out | r0-5 c1-6 | 5 | 1
(3,4) | r4-4 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_B | r0-5 c3-4 | 2 | (4,3)out | (3,3)out | r0-5 c1-6 | 5 | 1
(3,5) | r4-4 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c4-5 | 2 | (4,4)out | (3,4)out | r0-5 c1-6 | 5 | 1
(3,6) | r4-4 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c5-6 | 2 | (4,5)out | (3,5)out | r0-5 c1-6 | 5 | 1
(4,1) | r5-5 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_B | r0-5 c0-1 | 1 | (5,0)out | (4,0)out | r0-5 c1-6 | 5 | 0
(4,2) | r5-5 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c1-2 | 1 | (5,1)out | (4,1)out | r0-5 c1-6 | 5 | 0
(4,3) | r5-5 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c2-3 | 1 | (5,2)out | (4,2)out | r0-5 c1-6 | 5 | 0
(4,4) | r5-5 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_B | r0-5 c3-4 | 1 | (5,3)out | (4,3)out | r0-5 c1-6 | 5 | 0
(4,5) | r5-5 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_B | r0-5 c4-5 | 1 | (5,4)out | (4,4)out | r0-5 c1-6 | 5 | 0
(4,6) | r5-5 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_B | r0-5 c5-6 | 1 | (5,5)out | (4,5)out | r0-5 c1-6 | 5 | 0
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 8 8 8 4 4 4
. 9 9 8 3 4 4
. 9 9 8 3 3 3
. 9 1 1 1 5 3
. 4 4 1 5 5 5
. 4 4 1 5 5 5
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13
(0,1) | r3-3 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c0-1 | 5 | (3,0)out | (0,0)out | r0-5 c1-6 | 3 | 2
(0,2) | r3-3 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c1-2 | 5 | (3,1)out | (0,1)out | r0-5 c1-6 | 3 | 2
(0,3) | r3-3 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c2-3 | 5 | (3,2)out | (0,2)out | r0-5 c1-6 | 3 | 2
(0,4) | r3-3 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_B | r0-5 c3-4 | 5 | (3,3)out | (0,3)out | r0-5 c1-6 | 3 | 2
(0,5) | r3-3 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_B | r0-5 c4-5 | 5 | (3,4)out | (0,4)out | r0-5 c1-6 | 3 | 2
(0,6) | r3-3 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_B | r0-5 c5-6 | 5 | (3,5)out | (0,5)out | r0-5 c1-6 | 3 | 2
(1,1) | r4-4 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_B | r0-5 c0-1 | 4 | (4,0)out | (1,0)out | r0-5 c1-6 | 3 | 1
(1,2) | r4-4 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_B | r0-5 c1-2 | 4 | (4,1)out | (1,1)out | r0-5 c1-6 | 3 | 1
(1,3) | r4-4 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c2-3 | 4 | (4,2)out | (1,2)out | r0-5 c1-6 | 3 | 1
(1,4) | r4-4 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_B | r0-5 c3-4 | 4 | (4,3)out | (1,3)out | r0-5 c1-6 | 3 | 1
(1,5) | r4-4 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_B | r0-5 c4-5 | 4 | (4,4)out | (1,4)out | r0-5 c1-6 | 3 | 1
(1,6) | r4-4 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_B | r0-5 c5-6 | 4 | (4,5)out | (1,5)out | r0-5 c1-6 | 3 | 1
(2,1) | r5-5 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_B | r0-5 c0-1 | 3 | (5,0)out | (2,0)out | r0-5 c1-6 | 3 | 0
(2,2) | r5-5 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_B | r0-5 c1-2 | 3 | (5,1)out | (2,1)out | r0-5 c1-6 | 3 | 0
(2,3) | r5-5 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c2-3 | 3 | (5,2)out | (2,2)out | r0-5 c1-6 | 3 | 0
(2,4) | r5-5 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_B | r0-5 c3-4 | 3 | (5,3)out | (2,3)out | r0-5 c1-6 | 3 | 0
(2,5) | r5-5 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_B | r0-5 c4-5 | 3 | (5,4)out | (2,4)out | r0-5 c1-6 | 3 | 0
(2,6) | r5-5 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_B | r0-5 c5-6 | 3 | (5,5)out | (2,5)out | r0-5 c1-6 | 3 | 0
(3,1) | r0-0 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_B | r0-5 c0-1 | 2 | (0,0)out | (3,0)out | r0-5 c1-6 | 3 | 5
(3,2) | r0-0 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_B | r0-5 c1-2 | 2 | (0,1)out | (3,1)out | r0-5 c1-6 | 3 | 5
(3,3) | r0-0 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_B | r0-5 c2-3 | 2 | (0,2)out | (3,2)out | r0-5 c1-6 | 3 | 5
(3,4) | r0-0 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_B | r0-5 c3-4 | 2 | (0,3)out | (3,3)out | r0-5 c1-6 | 3 | 5
(3,5) | r0-0 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_B | r0-5 c4-5 | 2 | (0,4)out | (3,4)out | r0-5 c1-6 | 3 | 5
(3,6) | r0-0 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_B | r0-5 c5-6 | 2 | (0,5)out | (3,5)out | r0-5 c1-6 | 3 | 5
(4,1) | r1-1 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_B | r0-5 c0-1 | 1 | (1,0)out | (4,0)out | r0-5 c1-6 | 3 | 4
(4,2) | r1-1 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_B | r0-5 c1-2 | 1 | (1,1)out | (4,1)out | r0-5 c1-6 | 3 | 4
(4,3) | r1-1 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_B | r0-5 c2-3 | 1 | (1,2)out | (4,2)out | r0-5 c1-6 | 3 | 4
(4,4) | r1-1 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_B | r0-5 c3-4 | 1 | (1,3)out | (4,3)out | r0-5 c1-6 | 3 | 4
(4,5) | r1-1 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_B | r0-5 c4-5 | 1 | (1,4)out | (4,4)out | r0-5 c1-6 | 3 | 4
(4,6) | r1-1 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_B | r0-5 c5-6 | 1 | (1,5)out | (4,5)out | r0-5 c1-6 | 3 | 4
```

Train example 2: 36 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 8 8 8 4 4 4
. 8 9 8 4 9 1
. 8 9 9 9 9 1
. 5 5 3 3 3 1
. 5 5 3 4 3 1
. 5 5 3 4 4 4
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13
(0,1) | r4-4 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c0-1 | 5 | (4,0)out | (0,0)out | r0-5 c1-6 | 2 | 1
(0,2) | r4-4 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c1-2 | 5 | (4,1)out | (0,1)out | r0-5 c1-6 | 2 | 1
(0,3) | r4-4 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c2-3 | 5 | (4,2)out | (0,2)out | r0-5 c1-6 | 2 | 1
(0,4) | r4-4 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_B | r0-5 c3-4 | 5 | (4,3)out | (0,3)out | r0-5 c1-6 | 2 | 1
(0,5) | r4-4 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_B | r0-5 c4-5 | 5 | (4,4)out | (0,4)out | r0-5 c1-6 | 2 | 1
(0,6) | r4-4 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_B | r0-5 c5-6 | 5 | (4,5)out | (0,5)out | r0-5 c1-6 | 2 | 1
(1,1) | r5-5 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c0-1 | 4 | (5,0)out | (1,0)out | r0-5 c1-6 | 2 | 0
(1,2) | r5-5 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_B | r0-5 c1-2 | 4 | (5,1)out | (1,1)out | r0-5 c1-6 | 2 | 0
(1,3) | r5-5 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c2-3 | 4 | (5,2)out | (1,2)out | r0-5 c1-6 | 2 | 0
(1,4) | r5-5 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_B | r0-5 c3-4 | 4 | (5,3)out | (1,3)out | r0-5 c1-6 | 2 | 0
(1,5) | r5-5 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_B | r0-5 c4-5 | 4 | (5,4)out | (1,4)out | r0-5 c1-6 | 2 | 0
(1,6) | r5-5 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_B | r0-5 c5-6 | 4 | (5,5)out | (1,5)out | r0-5 c1-6 | 2 | 0
(2,1) | r0-0 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_B | r0-5 c0-1 | 3 | (0,0)out | (2,0)out | r0-5 c1-6 | 2 | 5
(2,2) | r0-0 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_B | r0-5 c1-2 | 3 | (0,1)out | (2,1)out | r0-5 c1-6 | 2 | 5
(2,3) | r0-0 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_B | r0-5 c2-3 | 3 | (0,2)out | (2,2)out | r0-5 c1-6 | 2 | 5
(2,4) | r0-0 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_B | r0-5 c3-4 | 3 | (0,3)out | (2,3)out | r0-5 c1-6 | 2 | 5
(2,5) | r0-0 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_B | r0-5 c4-5 | 3 | (0,4)out | (2,4)out | r0-5 c1-6 | 2 | 5
(2,6) | r0-0 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_B | r0-5 c5-6 | 3 | (0,5)out | (2,5)out | r0-5 c1-6 | 2 | 5
(3,1) | r1-1 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_B | r0-5 c0-1 | 2 | (1,0)out | (3,0)out | r0-5 c1-6 | 2 | 4
(3,2) | r1-1 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_B | r0-5 c1-2 | 2 | (1,1)out | (3,1)out | r0-5 c1-6 | 2 | 4
(3,3) | r1-1 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_B | r0-5 c2-3 | 2 | (1,2)out | (3,2)out | r0-5 c1-6 | 2 | 4
(3,4) | r1-1 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_B | r0-5 c3-4 | 2 | (1,3)out | (3,3)out | r0-5 c1-6 | 2 | 4
(3,5) | r1-1 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_B | r0-5 c4-5 | 2 | (1,4)out | (3,4)out | r0-5 c1-6 | 2 | 4
(3,6) | r1-1 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_B | r0-5 c5-6 | 2 | (1,5)out | (3,5)out | r0-5 c1-6 | 2 | 4
(4,1) | r2-2 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_B | r0-5 c0-1 | 1 | (2,0)out | (4,0)out | r0-5 c1-6 | 2 | 3
(4,2) | r2-2 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_B | r0-5 c1-2 | 1 | (2,1)out | (4,1)out | r0-5 c1-6 | 2 | 3
(4,3) | r2-2 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_B | r0-5 c2-3 | 1 | (2,2)out | (4,2)out | r0-5 c1-6 | 2 | 3
(4,4) | r2-2 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_B | r0-5 c3-4 | 1 | (2,3)out | (4,3)out | r0-5 c1-6 | 2 | 3
(4,5) | r2-2 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_B | r0-5 c4-5 | 1 | (2,4)out | (4,4)out | r0-5 c1-6 | 2 | 3
(4,6) | r2-2 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_B | r0-5 c5-6 | 1 | (2,5)out | (4,5)out | r0-5 c1-6 | 2 | 3
```


#### &r27, assignment 4 of 16

- DET values that differ between the assignments: &r0 = {(DIR_T)}; &r9 = {(DIR_R)}
- empty at every example

#### &r27, assignment 5 of 16

- DET values that differ between the assignments: &r0 = {(DIR_B)}; &r9 = {(DIR_T)}
- rows per train example: [35, 0, 0]; test: 0

Train example 0: 35 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . .
6 4 3 9 9 9 8
6 4 3 9 3 8 8
6 4 3 3 3 8 8
6 4 8 8 5 5 5
6 4 5 5 5 3 3
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13
(1,0) | r1-1 c0-6 | 1 | DIR_T | 6 | AXIS_V | DIR_T | r0-1 c0-6 | 1 | [1 8 0 0] | r0-1 c0-0 | r1-5 c0-6 | 0 | 1
(1,1) | r1-1 c0-6 | 1 | DIR_T | 4 | AXIS_V | DIR_T | r0-1 c0-6 | 1 | [1 8 0 0] | r0-1 c1-1 | r1-5 c0-6 | 0 | 1
(1,2) | r1-1 c0-6 | 1 | DIR_T | 3 | AXIS_V | DIR_T | r0-1 c0-6 | 1 | [1 8 0 0] | r0-1 c2-2 | r1-5 c0-6 | 0 | 1
(1,3) | r1-1 c0-6 | 1 | DIR_T | 9 | AXIS_V | DIR_T | r0-1 c0-6 | 1 | [1 8 0 0] | r0-1 c3-3 | r1-5 c0-6 | 0 | 1
(1,4) | r1-1 c0-6 | 1 | DIR_T | 9 | AXIS_V | DIR_T | r0-1 c0-6 | 1 | [1 8 0 0] | r0-1 c4-4 | r1-5 c0-6 | 0 | 1
(1,5) | r1-1 c0-6 | 1 | DIR_T | 9 | AXIS_V | DIR_T | r0-1 c0-6 | 1 | [1 8 0 0] | r0-1 c5-5 | r1-5 c0-6 | 0 | 1
(1,6) | r1-1 c0-6 | 1 | DIR_T | 8 | AXIS_V | DIR_T | r0-1 c0-6 | 1 | [1 8 0 0] | r0-1 c6-6 | r1-5 c0-6 | 0 | 1
(2,0) | r2-2 c0-6 | 1 | DIR_T | 6 | AXIS_V | DIR_T | r1-2 c0-6 | 2 | [3 6 0 0] | r1-2 c0-0 | r1-5 c0-6 | 0 | 2
(2,1) | r2-2 c0-6 | 1 | DIR_T | 4 | AXIS_V | DIR_T | r1-2 c0-6 | 2 | [3 6 0 0] | r1-2 c1-1 | r1-5 c0-6 | 0 | 2
(2,2) | r2-2 c0-6 | 1 | DIR_T | 3 | AXIS_V | DIR_T | r1-2 c0-6 | 2 | [3 6 0 0] | r1-2 c2-2 | r1-5 c0-6 | 0 | 2
(2,3) | r2-2 c0-6 | 1 | DIR_T | 9 | AXIS_V | DIR_T | r1-2 c0-6 | 2 | [3 6 0 0] | r1-2 c3-3 | r1-5 c0-6 | 0 | 2
(2,4) | r2-2 c0-6 | 1 | DIR_T | 3 | AXIS_V | DIR_T | r1-2 c0-6 | 2 | [3 6 0 0] | r1-2 c4-4 | r1-5 c0-6 | 0 | 2
(2,5) | r2-2 c0-6 | 1 | DIR_T | 8 | AXIS_V | DIR_T | r1-2 c0-6 | 2 | [3 6 0 0] | r1-2 c5-5 | r1-5 c0-6 | 0 | 2
(2,6) | r2-2 c0-6 | 1 | DIR_T | 8 | AXIS_V | DIR_T | r1-2 c0-6 | 2 | [3 6 0 0] | r1-2 c6-6 | r1-5 c0-6 | 0 | 2
(3,0) | r3-3 c0-6 | 1 | DIR_T | 6 | AXIS_V | DIR_T | r2-3 c0-6 | 3 | [5 4 0 0] | r2-3 c0-0 | r1-5 c0-6 | 0 | 3
(3,1) | r3-3 c0-6 | 1 | DIR_T | 4 | AXIS_V | DIR_T | r2-3 c0-6 | 3 | [5 4 0 0] | r2-3 c1-1 | r1-5 c0-6 | 0 | 3
(3,2) | r3-3 c0-6 | 1 | DIR_T | 3 | AXIS_V | DIR_T | r2-3 c0-6 | 3 | [5 4 0 0] | r2-3 c2-2 | r1-5 c0-6 | 0 | 3
(3,3) | r3-3 c0-6 | 1 | DIR_T | 3 | AXIS_V | DIR_T | r2-3 c0-6 | 3 | [5 4 0 0] | r2-3 c3-3 | r1-5 c0-6 | 0 | 3
(3,4) | r3-3 c0-6 | 1 | DIR_T | 3 | AXIS_V | DIR_T | r2-3 c0-6 | 3 | [5 4 0 0] | r2-3 c4-4 | r1-5 c0-6 | 0 | 3
(3,5) | r3-3 c0-6 | 1 | DIR_T | 8 | AXIS_V | DIR_T | r2-3 c0-6 | 3 | [5 4 0 0] | r2-3 c5-5 | r1-5 c0-6 | 0 | 3
(3,6) | r3-3 c0-6 | 1 | DIR_T | 8 | AXIS_V | DIR_T | r2-3 c0-6 | 3 | [5 4 0 0] | r2-3 c6-6 | r1-5 c0-6 | 0 | 3
(4,0) | r4-4 c0-6 | 1 | DIR_T | 6 | AXIS_V | DIR_T | r3-4 c0-6 | 4 | [7 2 0 0] | r3-4 c0-0 | r1-5 c0-6 | 0 | 4
(4,1) | r4-4 c0-6 | 1 | DIR_T | 4 | AXIS_V | DIR_T | r3-4 c0-6 | 4 | [7 2 0 0] | r3-4 c1-1 | r1-5 c0-6 | 0 | 4
(4,2) | r4-4 c0-6 | 1 | DIR_T | 8 | AXIS_V | DIR_T | r3-4 c0-6 | 4 | [7 2 0 0] | r3-4 c2-2 | r1-5 c0-6 | 0 | 4
(4,3) | r4-4 c0-6 | 1 | DIR_T | 8 | AXIS_V | DIR_T | r3-4 c0-6 | 4 | [7 2 0 0] | r3-4 c3-3 | r1-5 c0-6 | 0 | 4
(4,4) | r4-4 c0-6 | 1 | DIR_T | 5 | AXIS_V | DIR_T | r3-4 c0-6 | 4 | [7 2 0 0] | r3-4 c4-4 | r1-5 c0-6 | 0 | 4
(4,5) | r4-4 c0-6 | 1 | DIR_T | 5 | AXIS_V | DIR_T | r3-4 c0-6 | 4 | [7 2 0 0] | r3-4 c5-5 | r1-5 c0-6 | 0 | 4
(4,6) | r4-4 c0-6 | 1 | DIR_T | 5 | AXIS_V | DIR_T | r3-4 c0-6 | 4 | [7 2 0 0] | r3-4 c6-6 | r1-5 c0-6 | 0 | 4
(5,0) | r5-5 c0-6 | 1 | DIR_T | 6 | AXIS_V | DIR_T | r4-5 c0-6 | 5 | [9 0 0 0] | r4-5 c0-0 | r1-5 c0-6 | 0 | 5
(5,1) | r5-5 c0-6 | 1 | DIR_T | 4 | AXIS_V | DIR_T | r4-5 c0-6 | 5 | [9 0 0 0] | r4-5 c1-1 | r1-5 c0-6 | 0 | 5
```

Train example 1: 0 rows

Train example 2: 0 rows


#### &r27, assignment 6 of 16

- DET values that differ between the assignments: &r0 = {(DIR_B)}; &r9 = {(DIR_B)}
- empty at every example

#### &r27, assignment 7 of 16

- DET values that differ between the assignments: &r0 = {(DIR_B)}; &r9 = {(DIR_L)}
- rows per train example: [36, 36, 36]; test: 36

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 1 1 1 1 9 8
. 4 3 9 9 9 8
. 4 3 9 3 8 8
. 4 3 3 3 8 8
. 4 8 8 5 5 5
. 4 5 5 5 3 3
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13
(0,1) | r0-0 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_T | r0-5 c0-1 | 0 | (0,0)out | (0,0)out | r0-5 c1-6 | 0 | 0
(0,2) | r0-0 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_T | r0-5 c1-2 | 0 | (0,1)out | (0,1)out | r0-5 c1-6 | 0 | 0
(0,3) | r0-0 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_T | r0-5 c2-3 | 0 | (0,2)out | (0,2)out | r0-5 c1-6 | 0 | 0
(0,4) | r0-0 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_T | r0-5 c3-4 | 0 | (0,3)out | (0,3)out | r0-5 c1-6 | 0 | 0
(0,5) | r0-0 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_T | r0-5 c4-5 | 0 | (0,4)out | (0,4)out | r0-5 c1-6 | 0 | 0
(0,6) | r0-0 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c5-6 | 0 | (0,5)out | (0,5)out | r0-5 c1-6 | 0 | 0
(1,1) | r1-1 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_T | r0-5 c0-1 | 1 | (1,0)out | (1,0)out | r0-5 c1-6 | 0 | 1
(1,2) | r1-1 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_T | r0-5 c1-2 | 1 | (1,1)out | (1,1)out | r0-5 c1-6 | 0 | 1
(1,3) | r1-1 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_T | r0-5 c2-3 | 1 | (1,2)out | (1,2)out | r0-5 c1-6 | 0 | 1
(1,4) | r1-1 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_T | r0-5 c3-4 | 1 | (1,3)out | (1,3)out | r0-5 c1-6 | 0 | 1
(1,5) | r1-1 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_T | r0-5 c4-5 | 1 | (1,4)out | (1,4)out | r0-5 c1-6 | 0 | 1
(1,6) | r1-1 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c5-6 | 1 | (1,5)out | (1,5)out | r0-5 c1-6 | 0 | 1
(2,1) | r2-2 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_T | r0-5 c0-1 | 2 | (2,0)out | (2,0)out | r0-5 c1-6 | 0 | 2
(2,2) | r2-2 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_T | r0-5 c1-2 | 2 | (2,1)out | (2,1)out | r0-5 c1-6 | 0 | 2
(2,3) | r2-2 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_T | r0-5 c2-3 | 2 | (2,2)out | (2,2)out | r0-5 c1-6 | 0 | 2
(2,4) | r2-2 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_T | r0-5 c3-4 | 2 | (2,3)out | (2,3)out | r0-5 c1-6 | 0 | 2
(2,5) | r2-2 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c4-5 | 2 | (2,4)out | (2,4)out | r0-5 c1-6 | 0 | 2
(2,6) | r2-2 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c5-6 | 2 | (2,5)out | (2,5)out | r0-5 c1-6 | 0 | 2
(3,1) | r3-3 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_T | r0-5 c0-1 | 3 | (3,0)out | (3,0)out | r0-5 c1-6 | 0 | 3
(3,2) | r3-3 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_T | r0-5 c1-2 | 3 | (3,1)out | (3,1)out | r0-5 c1-6 | 0 | 3
(3,3) | r3-3 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_T | r0-5 c2-3 | 3 | (3,2)out | (3,2)out | r0-5 c1-6 | 0 | 3
(3,4) | r3-3 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_T | r0-5 c3-4 | 3 | (3,3)out | (3,3)out | r0-5 c1-6 | 0 | 3
(3,5) | r3-3 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c4-5 | 3 | (3,4)out | (3,4)out | r0-5 c1-6 | 0 | 3
(3,6) | r3-3 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c5-6 | 3 | (3,5)out | (3,5)out | r0-5 c1-6 | 0 | 3
(4,1) | r4-4 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_T | r0-5 c0-1 | 4 | (4,0)out | (4,0)out | r0-5 c1-6 | 0 | 4
(4,2) | r4-4 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c1-2 | 4 | (4,1)out | (4,1)out | r0-5 c1-6 | 0 | 4
(4,3) | r4-4 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c2-3 | 4 | (4,2)out | (4,2)out | r0-5 c1-6 | 0 | 4
(4,4) | r4-4 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_T | r0-5 c3-4 | 4 | (4,3)out | (4,3)out | r0-5 c1-6 | 0 | 4
(4,5) | r4-4 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_T | r0-5 c4-5 | 4 | (4,4)out | (4,4)out | r0-5 c1-6 | 0 | 4
(4,6) | r4-4 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_T | r0-5 c5-6 | 4 | (4,5)out | (4,5)out | r0-5 c1-6 | 0 | 4
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 8 8 8 4 4 4
. 9 9 8 3 4 4
. 9 9 8 3 3 3
. 9 1 1 1 5 3
. 4 4 1 5 5 5
. 4 4 1 5 5 5
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13
(0,1) | r2-2 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c0-1 | 0 | (2,0)out | (0,0)out | r0-5 c1-6 | 2 | 2
(0,2) | r2-2 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c1-2 | 0 | (2,1)out | (0,1)out | r0-5 c1-6 | 2 | 2
(0,3) | r2-2 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c2-3 | 0 | (2,2)out | (0,2)out | r0-5 c1-6 | 2 | 2
(0,4) | r2-2 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_T | r0-5 c3-4 | 0 | (2,3)out | (0,3)out | r0-5 c1-6 | 2 | 2
(0,5) | r2-2 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_T | r0-5 c4-5 | 0 | (2,4)out | (0,4)out | r0-5 c1-6 | 2 | 2
(0,6) | r2-2 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_T | r0-5 c5-6 | 0 | (2,5)out | (0,5)out | r0-5 c1-6 | 2 | 2
(1,1) | r3-3 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_T | r0-5 c0-1 | 1 | (3,0)out | (1,0)out | r0-5 c1-6 | 2 | 3
(1,2) | r3-3 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_T | r0-5 c1-2 | 1 | (3,1)out | (1,1)out | r0-5 c1-6 | 2 | 3
(1,3) | r3-3 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c2-3 | 1 | (3,2)out | (1,2)out | r0-5 c1-6 | 2 | 3
(1,4) | r3-3 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_T | r0-5 c3-4 | 1 | (3,3)out | (1,3)out | r0-5 c1-6 | 2 | 3
(1,5) | r3-3 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_T | r0-5 c4-5 | 1 | (3,4)out | (1,4)out | r0-5 c1-6 | 2 | 3
(1,6) | r3-3 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_T | r0-5 c5-6 | 1 | (3,5)out | (1,5)out | r0-5 c1-6 | 2 | 3
(2,1) | r4-4 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_T | r0-5 c0-1 | 2 | (4,0)out | (2,0)out | r0-5 c1-6 | 2 | 4
(2,2) | r4-4 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_T | r0-5 c1-2 | 2 | (4,1)out | (2,1)out | r0-5 c1-6 | 2 | 4
(2,3) | r4-4 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c2-3 | 2 | (4,2)out | (2,2)out | r0-5 c1-6 | 2 | 4
(2,4) | r4-4 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_T | r0-5 c3-4 | 2 | (4,3)out | (2,3)out | r0-5 c1-6 | 2 | 4
(2,5) | r4-4 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_T | r0-5 c4-5 | 2 | (4,4)out | (2,4)out | r0-5 c1-6 | 2 | 4
(2,6) | r4-4 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_T | r0-5 c5-6 | 2 | (4,5)out | (2,5)out | r0-5 c1-6 | 2 | 4
(3,1) | r5-5 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_T | r0-5 c0-1 | 3 | (5,0)out | (3,0)out | r0-5 c1-6 | 2 | 5
(3,2) | r5-5 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_T | r0-5 c1-2 | 3 | (5,1)out | (3,1)out | r0-5 c1-6 | 2 | 5
(3,3) | r5-5 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_T | r0-5 c2-3 | 3 | (5,2)out | (3,2)out | r0-5 c1-6 | 2 | 5
(3,4) | r5-5 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_T | r0-5 c3-4 | 3 | (5,3)out | (3,3)out | r0-5 c1-6 | 2 | 5
(3,5) | r5-5 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_T | r0-5 c4-5 | 3 | (5,4)out | (3,4)out | r0-5 c1-6 | 2 | 5
(3,6) | r5-5 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_T | r0-5 c5-6 | 3 | (5,5)out | (3,5)out | r0-5 c1-6 | 2 | 5
(4,1) | r0-0 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_T | r0-5 c0-1 | 4 | (0,0)out | (4,0)out | r0-5 c1-6 | 2 | 0
(4,2) | r0-0 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_T | r0-5 c1-2 | 4 | (0,1)out | (4,1)out | r0-5 c1-6 | 2 | 0
(4,3) | r0-0 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_T | r0-5 c2-3 | 4 | (0,2)out | (4,2)out | r0-5 c1-6 | 2 | 0
(4,4) | r0-0 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_T | r0-5 c3-4 | 4 | (0,3)out | (4,3)out | r0-5 c1-6 | 2 | 0
(4,5) | r0-0 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_T | r0-5 c4-5 | 4 | (0,4)out | (4,4)out | r0-5 c1-6 | 2 | 0
(4,6) | r0-0 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_T | r0-5 c5-6 | 4 | (0,5)out | (4,5)out | r0-5 c1-6 | 2 | 0
```

Train example 2: 36 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 8 8 8 4 4 4
. 8 9 8 4 9 1
. 8 9 9 9 9 1
. 5 5 3 3 3 1
. 5 5 3 4 3 1
. 5 5 3 4 4 4
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13
(0,1) | r3-3 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c0-1 | 0 | (3,0)out | (0,0)out | r0-5 c1-6 | 3 | 3
(0,2) | r3-3 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c1-2 | 0 | (3,1)out | (0,1)out | r0-5 c1-6 | 3 | 3
(0,3) | r3-3 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c2-3 | 0 | (3,2)out | (0,2)out | r0-5 c1-6 | 3 | 3
(0,4) | r3-3 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_T | r0-5 c3-4 | 0 | (3,3)out | (0,3)out | r0-5 c1-6 | 3 | 3
(0,5) | r3-3 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_T | r0-5 c4-5 | 0 | (3,4)out | (0,4)out | r0-5 c1-6 | 3 | 3
(0,6) | r3-3 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_T | r0-5 c5-6 | 0 | (3,5)out | (0,5)out | r0-5 c1-6 | 3 | 3
(1,1) | r4-4 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c0-1 | 1 | (4,0)out | (1,0)out | r0-5 c1-6 | 3 | 4
(1,2) | r4-4 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_T | r0-5 c1-2 | 1 | (4,1)out | (1,1)out | r0-5 c1-6 | 3 | 4
(1,3) | r4-4 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c2-3 | 1 | (4,2)out | (1,2)out | r0-5 c1-6 | 3 | 4
(1,4) | r4-4 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_T | r0-5 c3-4 | 1 | (4,3)out | (1,3)out | r0-5 c1-6 | 3 | 4
(1,5) | r4-4 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_T | r0-5 c4-5 | 1 | (4,4)out | (1,4)out | r0-5 c1-6 | 3 | 4
(1,6) | r4-4 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_T | r0-5 c5-6 | 1 | (4,5)out | (1,5)out | r0-5 c1-6 | 3 | 4
(2,1) | r5-5 c0-6 | 1 | DIR_L | 8 | AXIS_H | DIR_T | r0-5 c0-1 | 2 | (5,0)out | (2,0)out | r0-5 c1-6 | 3 | 5
(2,2) | r5-5 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_T | r0-5 c1-2 | 2 | (5,1)out | (2,1)out | r0-5 c1-6 | 3 | 5
(2,3) | r5-5 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_T | r0-5 c2-3 | 2 | (5,2)out | (2,2)out | r0-5 c1-6 | 3 | 5
(2,4) | r5-5 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_T | r0-5 c3-4 | 2 | (5,3)out | (2,3)out | r0-5 c1-6 | 3 | 5
(2,5) | r5-5 c0-6 | 1 | DIR_L | 9 | AXIS_H | DIR_T | r0-5 c4-5 | 2 | (5,4)out | (2,4)out | r0-5 c1-6 | 3 | 5
(2,6) | r5-5 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_T | r0-5 c5-6 | 2 | (5,5)out | (2,5)out | r0-5 c1-6 | 3 | 5
(3,1) | r0-0 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_T | r0-5 c0-1 | 3 | (0,0)out | (3,0)out | r0-5 c1-6 | 3 | 0
(3,2) | r0-0 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_T | r0-5 c1-2 | 3 | (0,1)out | (3,1)out | r0-5 c1-6 | 3 | 0
(3,3) | r0-0 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_T | r0-5 c2-3 | 3 | (0,2)out | (3,2)out | r0-5 c1-6 | 3 | 0
(3,4) | r0-0 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_T | r0-5 c3-4 | 3 | (0,3)out | (3,3)out | r0-5 c1-6 | 3 | 0
(3,5) | r0-0 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_T | r0-5 c4-5 | 3 | (0,4)out | (3,4)out | r0-5 c1-6 | 3 | 0
(3,6) | r0-0 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_T | r0-5 c5-6 | 3 | (0,5)out | (3,5)out | r0-5 c1-6 | 3 | 0
(4,1) | r1-1 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_T | r0-5 c0-1 | 4 | (1,0)out | (4,0)out | r0-5 c1-6 | 3 | 1
(4,2) | r1-1 c0-6 | 1 | DIR_L | 5 | AXIS_H | DIR_T | r0-5 c1-2 | 4 | (1,1)out | (4,1)out | r0-5 c1-6 | 3 | 1
(4,3) | r1-1 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_T | r0-5 c2-3 | 4 | (1,2)out | (4,2)out | r0-5 c1-6 | 3 | 1
(4,4) | r1-1 c0-6 | 1 | DIR_L | 4 | AXIS_H | DIR_T | r0-5 c3-4 | 4 | (1,3)out | (4,3)out | r0-5 c1-6 | 3 | 1
(4,5) | r1-1 c0-6 | 1 | DIR_L | 3 | AXIS_H | DIR_T | r0-5 c4-5 | 4 | (1,4)out | (4,4)out | r0-5 c1-6 | 3 | 1
(4,6) | r1-1 c0-6 | 1 | DIR_L | 1 | AXIS_H | DIR_T | r0-5 c5-6 | 4 | (1,5)out | (4,5)out | r0-5 c1-6 | 3 | 1
```


#### &r27, assignment 8 of 16

- DET values that differ between the assignments: &r0 = {(DIR_B)}; &r9 = {(DIR_R)}
- empty at every example

#### &r27, assignment 9 of 16

- DET values that differ between the assignments: &r0 = {(DIR_L)}; &r9 = {(DIR_T)}
- rows per train example: [35, 0, 0]; test: 0

Train example 0: 35 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . .
6 4 3 9 9 9 8
6 4 3 9 3 8 8
6 4 3 3 3 8 8
6 4 8 8 5 5 5
6 4 5 5 5 3 3
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13
(1,0) | r0-5 c1-1 | 1 | DIR_T | 6 | AXIS_V | DIR_R | r0-1 c0-6 | 6 | r0-1 c1-1 | r0-1 c0-0 | r1-5 c0-6 | 6 | 5
(1,1) | r0-5 c2-2 | 1 | DIR_T | 4 | AXIS_V | DIR_R | r0-1 c0-6 | 5 | r0-1 c2-2 | r0-1 c1-1 | r1-5 c0-6 | 6 | 4
(1,2) | r0-5 c3-3 | 1 | DIR_T | 3 | AXIS_V | DIR_R | r0-1 c0-6 | 4 | r0-1 c3-3 | r0-1 c2-2 | r1-5 c0-6 | 6 | 3
(1,3) | r0-5 c4-4 | 1 | DIR_T | 9 | AXIS_V | DIR_R | r0-1 c0-6 | 3 | r0-1 c4-4 | r0-1 c3-3 | r1-5 c0-6 | 6 | 2
(1,4) | r0-5 c5-5 | 1 | DIR_T | 9 | AXIS_V | DIR_R | r0-1 c0-6 | 2 | r0-1 c5-5 | r0-1 c4-4 | r1-5 c0-6 | 6 | 1
(1,5) | r0-5 c6-6 | 1 | DIR_T | 9 | AXIS_V | DIR_R | r0-1 c0-6 | 1 | r0-1 c6-6 | r0-1 c5-5 | r1-5 c0-6 | 6 | 0
(1,6) | r0-5 c0-0 | 1 | DIR_T | 8 | AXIS_V | DIR_R | r0-1 c0-6 | 0 | r0-1 c0-0 | r0-1 c6-6 | r1-5 c0-6 | 6 | 6
(2,0) | r0-5 c1-1 | 1 | DIR_T | 6 | AXIS_V | DIR_R | r1-2 c0-6 | 6 | r1-2 c1-1 | r1-2 c0-0 | r1-5 c0-6 | 6 | 5
(2,1) | r0-5 c2-2 | 1 | DIR_T | 4 | AXIS_V | DIR_R | r1-2 c0-6 | 5 | r1-2 c2-2 | r1-2 c1-1 | r1-5 c0-6 | 6 | 4
(2,2) | r0-5 c3-3 | 1 | DIR_T | 3 | AXIS_V | DIR_R | r1-2 c0-6 | 4 | r1-2 c3-3 | r1-2 c2-2 | r1-5 c0-6 | 6 | 3
(2,3) | r0-5 c4-4 | 1 | DIR_T | 9 | AXIS_V | DIR_R | r1-2 c0-6 | 3 | r1-2 c4-4 | r1-2 c3-3 | r1-5 c0-6 | 6 | 2
(2,4) | r0-5 c5-5 | 1 | DIR_T | 3 | AXIS_V | DIR_R | r1-2 c0-6 | 2 | r1-2 c5-5 | r1-2 c4-4 | r1-5 c0-6 | 6 | 1
(2,5) | r0-5 c6-6 | 1 | DIR_T | 8 | AXIS_V | DIR_R | r1-2 c0-6 | 1 | r1-2 c6-6 | r1-2 c5-5 | r1-5 c0-6 | 6 | 0
(2,6) | r0-5 c0-0 | 1 | DIR_T | 8 | AXIS_V | DIR_R | r1-2 c0-6 | 0 | r1-2 c0-0 | r1-2 c6-6 | r1-5 c0-6 | 6 | 6
(3,0) | r0-5 c1-1 | 1 | DIR_T | 6 | AXIS_V | DIR_R | r2-3 c0-6 | 6 | r2-3 c1-1 | r2-3 c0-0 | r1-5 c0-6 | 6 | 5
(3,1) | r0-5 c2-2 | 1 | DIR_T | 4 | AXIS_V | DIR_R | r2-3 c0-6 | 5 | r2-3 c2-2 | r2-3 c1-1 | r1-5 c0-6 | 6 | 4
(3,2) | r0-5 c3-3 | 1 | DIR_T | 3 | AXIS_V | DIR_R | r2-3 c0-6 | 4 | r2-3 c3-3 | r2-3 c2-2 | r1-5 c0-6 | 6 | 3
(3,3) | r0-5 c4-4 | 1 | DIR_T | 3 | AXIS_V | DIR_R | r2-3 c0-6 | 3 | r2-3 c4-4 | r2-3 c3-3 | r1-5 c0-6 | 6 | 2
(3,4) | r0-5 c5-5 | 1 | DIR_T | 3 | AXIS_V | DIR_R | r2-3 c0-6 | 2 | r2-3 c5-5 | r2-3 c4-4 | r1-5 c0-6 | 6 | 1
(3,5) | r0-5 c6-6 | 1 | DIR_T | 8 | AXIS_V | DIR_R | r2-3 c0-6 | 1 | r2-3 c6-6 | r2-3 c5-5 | r1-5 c0-6 | 6 | 0
(3,6) | r0-5 c0-0 | 1 | DIR_T | 8 | AXIS_V | DIR_R | r2-3 c0-6 | 0 | r2-3 c0-0 | r2-3 c6-6 | r1-5 c0-6 | 6 | 6
(4,0) | r0-5 c1-1 | 1 | DIR_T | 6 | AXIS_V | DIR_R | r3-4 c0-6 | 6 | r3-4 c1-1 | r3-4 c0-0 | r1-5 c0-6 | 6 | 5
(4,1) | r0-5 c2-2 | 1 | DIR_T | 4 | AXIS_V | DIR_R | r3-4 c0-6 | 5 | r3-4 c2-2 | r3-4 c1-1 | r1-5 c0-6 | 6 | 4
(4,2) | r0-5 c3-3 | 1 | DIR_T | 8 | AXIS_V | DIR_R | r3-4 c0-6 | 4 | r3-4 c3-3 | r3-4 c2-2 | r1-5 c0-6 | 6 | 3
(4,3) | r0-5 c4-4 | 1 | DIR_T | 8 | AXIS_V | DIR_R | r3-4 c0-6 | 3 | r3-4 c4-4 | r3-4 c3-3 | r1-5 c0-6 | 6 | 2
(4,4) | r0-5 c5-5 | 1 | DIR_T | 5 | AXIS_V | DIR_R | r3-4 c0-6 | 2 | r3-4 c5-5 | r3-4 c4-4 | r1-5 c0-6 | 6 | 1
(4,5) | r0-5 c6-6 | 1 | DIR_T | 5 | AXIS_V | DIR_R | r3-4 c0-6 | 1 | r3-4 c6-6 | r3-4 c5-5 | r1-5 c0-6 | 6 | 0
(4,6) | r0-5 c0-0 | 1 | DIR_T | 5 | AXIS_V | DIR_R | r3-4 c0-6 | 0 | r3-4 c0-0 | r3-4 c6-6 | r1-5 c0-6 | 6 | 6
(5,0) | r0-5 c1-1 | 1 | DIR_T | 6 | AXIS_V | DIR_R | r4-5 c0-6 | 6 | r4-5 c1-1 | r4-5 c0-0 | r1-5 c0-6 | 6 | 5
(5,1) | r0-5 c2-2 | 1 | DIR_T | 4 | AXIS_V | DIR_R | r4-5 c0-6 | 5 | r4-5 c2-2 | r4-5 c1-1 | r1-5 c0-6 | 6 | 4
```

Train example 1: 0 rows

Train example 2: 0 rows


#### &r27, assignment 10 of 16

- DET values that differ between the assignments: &r0 = {(DIR_L)}; &r9 = {(DIR_B)}
- empty at every example

#### &r27, assignment 11 of 16

- DET values that differ between the assignments: &r0 = {(DIR_L)}; &r9 = {(DIR_L)}
- rows per train example: [36, 36, 36]; test: 36

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 1 1 1 1 9 8
. 4 3 9 9 9 8
. 4 3 9 3 8 8
. 4 3 3 3 8 8
. 4 8 8 5 5 5
. 4 5 5 5 3 3
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13
(0,1) | r0-5 c2-2 | 1 | DIR_L | 1 | AXIS_H | DIR_R | r0-5 c0-1 | 5 | [0 0 2 9] | (0,0)out | r0-5 c1-6 | 6 | 4
(0,2) | r0-5 c3-3 | 1 | DIR_L | 1 | AXIS_H | DIR_R | r0-5 c1-2 | 4 | [0 0 4 7] | (0,1)out | r0-5 c1-6 | 6 | 3
(0,3) | r0-5 c4-4 | 1 | DIR_L | 1 | AXIS_H | DIR_R | r0-5 c2-3 | 3 | [0 0 6 5] | (0,2)out | r0-5 c1-6 | 6 | 2
(0,4) | r0-5 c5-5 | 1 | DIR_L | 1 | AXIS_H | DIR_R | r0-5 c3-4 | 2 | [0 0 8 3] | (0,3)out | r0-5 c1-6 | 6 | 1
(0,5) | r0-5 c6-6 | 1 | DIR_L | 9 | AXIS_H | DIR_R | r0-5 c4-5 | 1 | [0 0 10 1] | (0,4)out | r0-5 c1-6 | 6 | 0
(0,6) | r0-5 c0-0 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c5-6 | 0 | [0 0 5 6] | (0,5)out | r0-5 c1-6 | 6 | 6
(1,1) | r0-5 c2-2 | 1 | DIR_L | 4 | AXIS_H | DIR_R | r0-5 c0-1 | 5 | [0 0 2 9] | (1,0)out | r0-5 c1-6 | 6 | 4
(1,2) | r0-5 c3-3 | 1 | DIR_L | 3 | AXIS_H | DIR_R | r0-5 c1-2 | 4 | [0 0 4 7] | (1,1)out | r0-5 c1-6 | 6 | 3
(1,3) | r0-5 c4-4 | 1 | DIR_L | 9 | AXIS_H | DIR_R | r0-5 c2-3 | 3 | [0 0 6 5] | (1,2)out | r0-5 c1-6 | 6 | 2
(1,4) | r0-5 c5-5 | 1 | DIR_L | 9 | AXIS_H | DIR_R | r0-5 c3-4 | 2 | [0 0 8 3] | (1,3)out | r0-5 c1-6 | 6 | 1
(1,5) | r0-5 c6-6 | 1 | DIR_L | 9 | AXIS_H | DIR_R | r0-5 c4-5 | 1 | [0 0 10 1] | (1,4)out | r0-5 c1-6 | 6 | 0
(1,6) | r0-5 c0-0 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c5-6 | 0 | [0 0 5 6] | (1,5)out | r0-5 c1-6 | 6 | 6
(2,1) | r0-5 c2-2 | 1 | DIR_L | 4 | AXIS_H | DIR_R | r0-5 c0-1 | 5 | [0 0 2 9] | (2,0)out | r0-5 c1-6 | 6 | 4
(2,2) | r0-5 c3-3 | 1 | DIR_L | 3 | AXIS_H | DIR_R | r0-5 c1-2 | 4 | [0 0 4 7] | (2,1)out | r0-5 c1-6 | 6 | 3
(2,3) | r0-5 c4-4 | 1 | DIR_L | 9 | AXIS_H | DIR_R | r0-5 c2-3 | 3 | [0 0 6 5] | (2,2)out | r0-5 c1-6 | 6 | 2
(2,4) | r0-5 c5-5 | 1 | DIR_L | 3 | AXIS_H | DIR_R | r0-5 c3-4 | 2 | [0 0 8 3] | (2,3)out | r0-5 c1-6 | 6 | 1
(2,5) | r0-5 c6-6 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c4-5 | 1 | [0 0 10 1] | (2,4)out | r0-5 c1-6 | 6 | 0
(2,6) | r0-5 c0-0 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c5-6 | 0 | [0 0 5 6] | (2,5)out | r0-5 c1-6 | 6 | 6
(3,1) | r0-5 c2-2 | 1 | DIR_L | 4 | AXIS_H | DIR_R | r0-5 c0-1 | 5 | [0 0 2 9] | (3,0)out | r0-5 c1-6 | 6 | 4
(3,2) | r0-5 c3-3 | 1 | DIR_L | 3 | AXIS_H | DIR_R | r0-5 c1-2 | 4 | [0 0 4 7] | (3,1)out | r0-5 c1-6 | 6 | 3
(3,3) | r0-5 c4-4 | 1 | DIR_L | 3 | AXIS_H | DIR_R | r0-5 c2-3 | 3 | [0 0 6 5] | (3,2)out | r0-5 c1-6 | 6 | 2
(3,4) | r0-5 c5-5 | 1 | DIR_L | 3 | AXIS_H | DIR_R | r0-5 c3-4 | 2 | [0 0 8 3] | (3,3)out | r0-5 c1-6 | 6 | 1
(3,5) | r0-5 c6-6 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c4-5 | 1 | [0 0 10 1] | (3,4)out | r0-5 c1-6 | 6 | 0
(3,6) | r0-5 c0-0 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c5-6 | 0 | [0 0 5 6] | (3,5)out | r0-5 c1-6 | 6 | 6
(4,1) | r0-5 c2-2 | 1 | DIR_L | 4 | AXIS_H | DIR_R | r0-5 c0-1 | 5 | [0 0 2 9] | (4,0)out | r0-5 c1-6 | 6 | 4
(4,2) | r0-5 c3-3 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c1-2 | 4 | [0 0 4 7] | (4,1)out | r0-5 c1-6 | 6 | 3
(4,3) | r0-5 c4-4 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c2-3 | 3 | [0 0 6 5] | (4,2)out | r0-5 c1-6 | 6 | 2
(4,4) | r0-5 c5-5 | 1 | DIR_L | 5 | AXIS_H | DIR_R | r0-5 c3-4 | 2 | [0 0 8 3] | (4,3)out | r0-5 c1-6 | 6 | 1
(4,5) | r0-5 c6-6 | 1 | DIR_L | 5 | AXIS_H | DIR_R | r0-5 c4-5 | 1 | [0 0 10 1] | (4,4)out | r0-5 c1-6 | 6 | 0
(4,6) | r0-5 c0-0 | 1 | DIR_L | 5 | AXIS_H | DIR_R | r0-5 c5-6 | 0 | [0 0 5 6] | (4,5)out | r0-5 c1-6 | 6 | 6
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 8 8 8 4 4 4
. 9 9 8 3 4 4
. 9 9 8 3 3 3
. 9 1 1 1 5 3
. 4 4 1 5 5 5
. 4 4 1 5 5 5
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13
(0,1) | r0-5 c2-2 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c0-1 | 5 | [0 0 2 9] | (0,0)out | r0-5 c1-6 | 6 | 4
(0,2) | r0-5 c3-3 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c1-2 | 4 | [0 0 4 7] | (0,1)out | r0-5 c1-6 | 6 | 3
(0,3) | r0-5 c4-4 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c2-3 | 3 | [0 0 6 5] | (0,2)out | r0-5 c1-6 | 6 | 2
(0,4) | r0-5 c5-5 | 1 | DIR_L | 4 | AXIS_H | DIR_R | r0-5 c3-4 | 2 | [0 0 8 3] | (0,3)out | r0-5 c1-6 | 6 | 1
(0,5) | r0-5 c6-6 | 1 | DIR_L | 4 | AXIS_H | DIR_R | r0-5 c4-5 | 1 | [0 0 10 1] | (0,4)out | r0-5 c1-6 | 6 | 0
(0,6) | r0-5 c0-0 | 1 | DIR_L | 4 | AXIS_H | DIR_R | r0-5 c5-6 | 0 | [0 0 5 6] | (0,5)out | r0-5 c1-6 | 6 | 6
(1,1) | r0-5 c2-2 | 1 | DIR_L | 9 | AXIS_H | DIR_R | r0-5 c0-1 | 5 | [0 0 2 9] | (1,0)out | r0-5 c1-6 | 6 | 4
(1,2) | r0-5 c3-3 | 1 | DIR_L | 9 | AXIS_H | DIR_R | r0-5 c1-2 | 4 | [0 0 4 7] | (1,1)out | r0-5 c1-6 | 6 | 3
(1,3) | r0-5 c4-4 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c2-3 | 3 | [0 0 6 5] | (1,2)out | r0-5 c1-6 | 6 | 2
(1,4) | r0-5 c5-5 | 1 | DIR_L | 3 | AXIS_H | DIR_R | r0-5 c3-4 | 2 | [0 0 8 3] | (1,3)out | r0-5 c1-6 | 6 | 1
(1,5) | r0-5 c6-6 | 1 | DIR_L | 4 | AXIS_H | DIR_R | r0-5 c4-5 | 1 | [0 0 10 1] | (1,4)out | r0-5 c1-6 | 6 | 0
(1,6) | r0-5 c0-0 | 1 | DIR_L | 4 | AXIS_H | DIR_R | r0-5 c5-6 | 0 | [0 0 5 6] | (1,5)out | r0-5 c1-6 | 6 | 6
(2,1) | r0-5 c2-2 | 1 | DIR_L | 9 | AXIS_H | DIR_R | r0-5 c0-1 | 5 | [0 0 2 9] | (2,0)out | r0-5 c1-6 | 6 | 4
(2,2) | r0-5 c3-3 | 1 | DIR_L | 9 | AXIS_H | DIR_R | r0-5 c1-2 | 4 | [0 0 4 7] | (2,1)out | r0-5 c1-6 | 6 | 3
(2,3) | r0-5 c4-4 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c2-3 | 3 | [0 0 6 5] | (2,2)out | r0-5 c1-6 | 6 | 2
(2,4) | r0-5 c5-5 | 1 | DIR_L | 3 | AXIS_H | DIR_R | r0-5 c3-4 | 2 | [0 0 8 3] | (2,3)out | r0-5 c1-6 | 6 | 1
(2,5) | r0-5 c6-6 | 1 | DIR_L | 3 | AXIS_H | DIR_R | r0-5 c4-5 | 1 | [0 0 10 1] | (2,4)out | r0-5 c1-6 | 6 | 0
(2,6) | r0-5 c0-0 | 1 | DIR_L | 3 | AXIS_H | DIR_R | r0-5 c5-6 | 0 | [0 0 5 6] | (2,5)out | r0-5 c1-6 | 6 | 6
(3,1) | r0-5 c2-2 | 1 | DIR_L | 9 | AXIS_H | DIR_R | r0-5 c0-1 | 5 | [0 0 2 9] | (3,0)out | r0-5 c1-6 | 6 | 4
(3,2) | r0-5 c3-3 | 1 | DIR_L | 1 | AXIS_H | DIR_R | r0-5 c1-2 | 4 | [0 0 4 7] | (3,1)out | r0-5 c1-6 | 6 | 3
(3,3) | r0-5 c4-4 | 1 | DIR_L | 1 | AXIS_H | DIR_R | r0-5 c2-3 | 3 | [0 0 6 5] | (3,2)out | r0-5 c1-6 | 6 | 2
(3,4) | r0-5 c5-5 | 1 | DIR_L | 1 | AXIS_H | DIR_R | r0-5 c3-4 | 2 | [0 0 8 3] | (3,3)out | r0-5 c1-6 | 6 | 1
(3,5) | r0-5 c6-6 | 1 | DIR_L | 5 | AXIS_H | DIR_R | r0-5 c4-5 | 1 | [0 0 10 1] | (3,4)out | r0-5 c1-6 | 6 | 0
(3,6) | r0-5 c0-0 | 1 | DIR_L | 3 | AXIS_H | DIR_R | r0-5 c5-6 | 0 | [0 0 5 6] | (3,5)out | r0-5 c1-6 | 6 | 6
(4,1) | r0-5 c2-2 | 1 | DIR_L | 4 | AXIS_H | DIR_R | r0-5 c0-1 | 5 | [0 0 2 9] | (4,0)out | r0-5 c1-6 | 6 | 4
(4,2) | r0-5 c3-3 | 1 | DIR_L | 4 | AXIS_H | DIR_R | r0-5 c1-2 | 4 | [0 0 4 7] | (4,1)out | r0-5 c1-6 | 6 | 3
(4,3) | r0-5 c4-4 | 1 | DIR_L | 1 | AXIS_H | DIR_R | r0-5 c2-3 | 3 | [0 0 6 5] | (4,2)out | r0-5 c1-6 | 6 | 2
(4,4) | r0-5 c5-5 | 1 | DIR_L | 5 | AXIS_H | DIR_R | r0-5 c3-4 | 2 | [0 0 8 3] | (4,3)out | r0-5 c1-6 | 6 | 1
(4,5) | r0-5 c6-6 | 1 | DIR_L | 5 | AXIS_H | DIR_R | r0-5 c4-5 | 1 | [0 0 10 1] | (4,4)out | r0-5 c1-6 | 6 | 0
(4,6) | r0-5 c0-0 | 1 | DIR_L | 5 | AXIS_H | DIR_R | r0-5 c5-6 | 0 | [0 0 5 6] | (4,5)out | r0-5 c1-6 | 6 | 6
```

Train example 2: 36 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 8 8 8 4 4 4
. 8 9 8 4 9 1
. 8 9 9 9 9 1
. 5 5 3 3 3 1
. 5 5 3 4 3 1
. 5 5 3 4 4 4
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13
(0,1) | r0-5 c2-2 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c0-1 | 5 | [0 0 2 9] | (0,0)out | r0-5 c1-6 | 6 | 4
(0,2) | r0-5 c3-3 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c1-2 | 4 | [0 0 4 7] | (0,1)out | r0-5 c1-6 | 6 | 3
(0,3) | r0-5 c4-4 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c2-3 | 3 | [0 0 6 5] | (0,2)out | r0-5 c1-6 | 6 | 2
(0,4) | r0-5 c5-5 | 1 | DIR_L | 4 | AXIS_H | DIR_R | r0-5 c3-4 | 2 | [0 0 8 3] | (0,3)out | r0-5 c1-6 | 6 | 1
(0,5) | r0-5 c6-6 | 1 | DIR_L | 4 | AXIS_H | DIR_R | r0-5 c4-5 | 1 | [0 0 10 1] | (0,4)out | r0-5 c1-6 | 6 | 0
(0,6) | r0-5 c0-0 | 1 | DIR_L | 4 | AXIS_H | DIR_R | r0-5 c5-6 | 0 | [0 0 5 6] | (0,5)out | r0-5 c1-6 | 6 | 6
(1,1) | r0-5 c2-2 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c0-1 | 5 | [0 0 2 9] | (1,0)out | r0-5 c1-6 | 6 | 4
(1,2) | r0-5 c3-3 | 1 | DIR_L | 9 | AXIS_H | DIR_R | r0-5 c1-2 | 4 | [0 0 4 7] | (1,1)out | r0-5 c1-6 | 6 | 3
(1,3) | r0-5 c4-4 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c2-3 | 3 | [0 0 6 5] | (1,2)out | r0-5 c1-6 | 6 | 2
(1,4) | r0-5 c5-5 | 1 | DIR_L | 4 | AXIS_H | DIR_R | r0-5 c3-4 | 2 | [0 0 8 3] | (1,3)out | r0-5 c1-6 | 6 | 1
(1,5) | r0-5 c6-6 | 1 | DIR_L | 9 | AXIS_H | DIR_R | r0-5 c4-5 | 1 | [0 0 10 1] | (1,4)out | r0-5 c1-6 | 6 | 0
(1,6) | r0-5 c0-0 | 1 | DIR_L | 1 | AXIS_H | DIR_R | r0-5 c5-6 | 0 | [0 0 5 6] | (1,5)out | r0-5 c1-6 | 6 | 6
(2,1) | r0-5 c2-2 | 1 | DIR_L | 8 | AXIS_H | DIR_R | r0-5 c0-1 | 5 | [0 0 2 9] | (2,0)out | r0-5 c1-6 | 6 | 4
(2,2) | r0-5 c3-3 | 1 | DIR_L | 9 | AXIS_H | DIR_R | r0-5 c1-2 | 4 | [0 0 4 7] | (2,1)out | r0-5 c1-6 | 6 | 3
(2,3) | r0-5 c4-4 | 1 | DIR_L | 9 | AXIS_H | DIR_R | r0-5 c2-3 | 3 | [0 0 6 5] | (2,2)out | r0-5 c1-6 | 6 | 2
(2,4) | r0-5 c5-5 | 1 | DIR_L | 9 | AXIS_H | DIR_R | r0-5 c3-4 | 2 | [0 0 8 3] | (2,3)out | r0-5 c1-6 | 6 | 1
(2,5) | r0-5 c6-6 | 1 | DIR_L | 9 | AXIS_H | DIR_R | r0-5 c4-5 | 1 | [0 0 10 1] | (2,4)out | r0-5 c1-6 | 6 | 0
(2,6) | r0-5 c0-0 | 1 | DIR_L | 1 | AXIS_H | DIR_R | r0-5 c5-6 | 0 | [0 0 5 6] | (2,5)out | r0-5 c1-6 | 6 | 6
(3,1) | r0-5 c2-2 | 1 | DIR_L | 5 | AXIS_H | DIR_R | r0-5 c0-1 | 5 | [0 0 2 9] | (3,0)out | r0-5 c1-6 | 6 | 4
(3,2) | r0-5 c3-3 | 1 | DIR_L | 5 | AXIS_H | DIR_R | r0-5 c1-2 | 4 | [0 0 4 7] | (3,1)out | r0-5 c1-6 | 6 | 3
(3,3) | r0-5 c4-4 | 1 | DIR_L | 3 | AXIS_H | DIR_R | r0-5 c2-3 | 3 | [0 0 6 5] | (3,2)out | r0-5 c1-6 | 6 | 2
(3,4) | r0-5 c5-5 | 1 | DIR_L | 3 | AXIS_H | DIR_R | r0-5 c3-4 | 2 | [0 0 8 3] | (3,3)out | r0-5 c1-6 | 6 | 1
(3,5) | r0-5 c6-6 | 1 | DIR_L | 3 | AXIS_H | DIR_R | r0-5 c4-5 | 1 | [0 0 10 1] | (3,4)out | r0-5 c1-6 | 6 | 0
(3,6) | r0-5 c0-0 | 1 | DIR_L | 1 | AXIS_H | DIR_R | r0-5 c5-6 | 0 | [0 0 5 6] | (3,5)out | r0-5 c1-6 | 6 | 6
(4,1) | r0-5 c2-2 | 1 | DIR_L | 5 | AXIS_H | DIR_R | r0-5 c0-1 | 5 | [0 0 2 9] | (4,0)out | r0-5 c1-6 | 6 | 4
(4,2) | r0-5 c3-3 | 1 | DIR_L | 5 | AXIS_H | DIR_R | r0-5 c1-2 | 4 | [0 0 4 7] | (4,1)out | r0-5 c1-6 | 6 | 3
(4,3) | r0-5 c4-4 | 1 | DIR_L | 3 | AXIS_H | DIR_R | r0-5 c2-3 | 3 | [0 0 6 5] | (4,2)out | r0-5 c1-6 | 6 | 2
(4,4) | r0-5 c5-5 | 1 | DIR_L | 4 | AXIS_H | DIR_R | r0-5 c3-4 | 2 | [0 0 8 3] | (4,3)out | r0-5 c1-6 | 6 | 1
(4,5) | r0-5 c6-6 | 1 | DIR_L | 3 | AXIS_H | DIR_R | r0-5 c4-5 | 1 | [0 0 10 1] | (4,4)out | r0-5 c1-6 | 6 | 0
(4,6) | r0-5 c0-0 | 1 | DIR_L | 1 | AXIS_H | DIR_R | r0-5 c5-6 | 0 | [0 0 5 6] | (4,5)out | r0-5 c1-6 | 6 | 6
```


#### &r27, assignment 12 of 16

- DET values that differ between the assignments: &r0 = {(DIR_L)}; &r9 = {(DIR_R)}
- empty at every example

#### &r27, assignment 13 of 16

- DET values that differ between the assignments: &r0 = {(DIR_R)}; &r9 = {(DIR_T)}
- rows per train example: [35, 0, 0]; test: 0

Train example 0: 35 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . .
6 4 3 9 9 9 8
6 4 3 9 3 8 8
6 4 3 3 3 8 8
6 4 8 8 5 5 5
6 4 5 5 5 3 3
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13
(1,0) | r0-5 c0-0 | 1 | DIR_T | 6 | AXIS_V | DIR_L | r0-1 c0-6 | 0 | r0-1 c0-0 | r0-1 c0-0 | r1-5 c0-6 | 0 | 0
(1,1) | r0-5 c1-1 | 1 | DIR_T | 4 | AXIS_V | DIR_L | r0-1 c0-6 | 1 | r0-1 c1-1 | r0-1 c1-1 | r1-5 c0-6 | 0 | 1
(1,2) | r0-5 c2-2 | 1 | DIR_T | 3 | AXIS_V | DIR_L | r0-1 c0-6 | 2 | r0-1 c2-2 | r0-1 c2-2 | r1-5 c0-6 | 0 | 2
(1,3) | r0-5 c3-3 | 1 | DIR_T | 9 | AXIS_V | DIR_L | r0-1 c0-6 | 3 | r0-1 c3-3 | r0-1 c3-3 | r1-5 c0-6 | 0 | 3
(1,4) | r0-5 c4-4 | 1 | DIR_T | 9 | AXIS_V | DIR_L | r0-1 c0-6 | 4 | r0-1 c4-4 | r0-1 c4-4 | r1-5 c0-6 | 0 | 4
(1,5) | r0-5 c5-5 | 1 | DIR_T | 9 | AXIS_V | DIR_L | r0-1 c0-6 | 5 | r0-1 c5-5 | r0-1 c5-5 | r1-5 c0-6 | 0 | 5
(1,6) | r0-5 c6-6 | 1 | DIR_T | 8 | AXIS_V | DIR_L | r0-1 c0-6 | 6 | r0-1 c6-6 | r0-1 c6-6 | r1-5 c0-6 | 0 | 6
(2,0) | r0-5 c0-0 | 1 | DIR_T | 6 | AXIS_V | DIR_L | r1-2 c0-6 | 0 | r1-2 c0-0 | r1-2 c0-0 | r1-5 c0-6 | 0 | 0
(2,1) | r0-5 c1-1 | 1 | DIR_T | 4 | AXIS_V | DIR_L | r1-2 c0-6 | 1 | r1-2 c1-1 | r1-2 c1-1 | r1-5 c0-6 | 0 | 1
(2,2) | r0-5 c2-2 | 1 | DIR_T | 3 | AXIS_V | DIR_L | r1-2 c0-6 | 2 | r1-2 c2-2 | r1-2 c2-2 | r1-5 c0-6 | 0 | 2
(2,3) | r0-5 c3-3 | 1 | DIR_T | 9 | AXIS_V | DIR_L | r1-2 c0-6 | 3 | r1-2 c3-3 | r1-2 c3-3 | r1-5 c0-6 | 0 | 3
(2,4) | r0-5 c4-4 | 1 | DIR_T | 3 | AXIS_V | DIR_L | r1-2 c0-6 | 4 | r1-2 c4-4 | r1-2 c4-4 | r1-5 c0-6 | 0 | 4
(2,5) | r0-5 c5-5 | 1 | DIR_T | 8 | AXIS_V | DIR_L | r1-2 c0-6 | 5 | r1-2 c5-5 | r1-2 c5-5 | r1-5 c0-6 | 0 | 5
(2,6) | r0-5 c6-6 | 1 | DIR_T | 8 | AXIS_V | DIR_L | r1-2 c0-6 | 6 | r1-2 c6-6 | r1-2 c6-6 | r1-5 c0-6 | 0 | 6
(3,0) | r0-5 c0-0 | 1 | DIR_T | 6 | AXIS_V | DIR_L | r2-3 c0-6 | 0 | r2-3 c0-0 | r2-3 c0-0 | r1-5 c0-6 | 0 | 0
(3,1) | r0-5 c1-1 | 1 | DIR_T | 4 | AXIS_V | DIR_L | r2-3 c0-6 | 1 | r2-3 c1-1 | r2-3 c1-1 | r1-5 c0-6 | 0 | 1
(3,2) | r0-5 c2-2 | 1 | DIR_T | 3 | AXIS_V | DIR_L | r2-3 c0-6 | 2 | r2-3 c2-2 | r2-3 c2-2 | r1-5 c0-6 | 0 | 2
(3,3) | r0-5 c3-3 | 1 | DIR_T | 3 | AXIS_V | DIR_L | r2-3 c0-6 | 3 | r2-3 c3-3 | r2-3 c3-3 | r1-5 c0-6 | 0 | 3
(3,4) | r0-5 c4-4 | 1 | DIR_T | 3 | AXIS_V | DIR_L | r2-3 c0-6 | 4 | r2-3 c4-4 | r2-3 c4-4 | r1-5 c0-6 | 0 | 4
(3,5) | r0-5 c5-5 | 1 | DIR_T | 8 | AXIS_V | DIR_L | r2-3 c0-6 | 5 | r2-3 c5-5 | r2-3 c5-5 | r1-5 c0-6 | 0 | 5
(3,6) | r0-5 c6-6 | 1 | DIR_T | 8 | AXIS_V | DIR_L | r2-3 c0-6 | 6 | r2-3 c6-6 | r2-3 c6-6 | r1-5 c0-6 | 0 | 6
(4,0) | r0-5 c0-0 | 1 | DIR_T | 6 | AXIS_V | DIR_L | r3-4 c0-6 | 0 | r3-4 c0-0 | r3-4 c0-0 | r1-5 c0-6 | 0 | 0
(4,1) | r0-5 c1-1 | 1 | DIR_T | 4 | AXIS_V | DIR_L | r3-4 c0-6 | 1 | r3-4 c1-1 | r3-4 c1-1 | r1-5 c0-6 | 0 | 1
(4,2) | r0-5 c2-2 | 1 | DIR_T | 8 | AXIS_V | DIR_L | r3-4 c0-6 | 2 | r3-4 c2-2 | r3-4 c2-2 | r1-5 c0-6 | 0 | 2
(4,3) | r0-5 c3-3 | 1 | DIR_T | 8 | AXIS_V | DIR_L | r3-4 c0-6 | 3 | r3-4 c3-3 | r3-4 c3-3 | r1-5 c0-6 | 0 | 3
(4,4) | r0-5 c4-4 | 1 | DIR_T | 5 | AXIS_V | DIR_L | r3-4 c0-6 | 4 | r3-4 c4-4 | r3-4 c4-4 | r1-5 c0-6 | 0 | 4
(4,5) | r0-5 c5-5 | 1 | DIR_T | 5 | AXIS_V | DIR_L | r3-4 c0-6 | 5 | r3-4 c5-5 | r3-4 c5-5 | r1-5 c0-6 | 0 | 5
(4,6) | r0-5 c6-6 | 1 | DIR_T | 5 | AXIS_V | DIR_L | r3-4 c0-6 | 6 | r3-4 c6-6 | r3-4 c6-6 | r1-5 c0-6 | 0 | 6
(5,0) | r0-5 c0-0 | 1 | DIR_T | 6 | AXIS_V | DIR_L | r4-5 c0-6 | 0 | r4-5 c0-0 | r4-5 c0-0 | r1-5 c0-6 | 0 | 0
(5,1) | r0-5 c1-1 | 1 | DIR_T | 4 | AXIS_V | DIR_L | r4-5 c0-6 | 1 | r4-5 c1-1 | r4-5 c1-1 | r1-5 c0-6 | 0 | 1
```

Train example 1: 0 rows

Train example 2: 0 rows


#### &r27, assignment 14 of 16

- DET values that differ between the assignments: &r0 = {(DIR_R)}; &r9 = {(DIR_B)}
- empty at every example

#### &r27, assignment 15 of 16

- DET values that differ between the assignments: &r0 = {(DIR_R)}; &r9 = {(DIR_L)}
- rows per train example: [36, 36, 36]; test: 36

Train example 0: 36 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 1 1 1 1 9 8
. 4 3 9 9 9 8
. 4 3 9 3 8 8
. 4 3 3 3 8 8
. 4 8 8 5 5 5
. 4 5 5 5 3 3
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13
(0,1) | r0-5 c1-1 | 1 | DIR_L | 1 | AXIS_H | DIR_L | r0-5 c0-1 | 1 | [0 0 1 10] | (0,0)out | r0-5 c1-6 | 0 | 1
(0,2) | r0-5 c2-2 | 1 | DIR_L | 1 | AXIS_H | DIR_L | r0-5 c1-2 | 2 | [0 0 3 8] | (0,1)out | r0-5 c1-6 | 0 | 2
(0,3) | r0-5 c3-3 | 1 | DIR_L | 1 | AXIS_H | DIR_L | r0-5 c2-3 | 3 | [0 0 5 6] | (0,2)out | r0-5 c1-6 | 0 | 3
(0,4) | r0-5 c4-4 | 1 | DIR_L | 1 | AXIS_H | DIR_L | r0-5 c3-4 | 4 | [0 0 7 4] | (0,3)out | r0-5 c1-6 | 0 | 4
(0,5) | r0-5 c5-5 | 1 | DIR_L | 9 | AXIS_H | DIR_L | r0-5 c4-5 | 5 | [0 0 9 2] | (0,4)out | r0-5 c1-6 | 0 | 5
(0,6) | r0-5 c6-6 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c5-6 | 6 | [0 0 11 0] | (0,5)out | r0-5 c1-6 | 0 | 6
(1,1) | r0-5 c1-1 | 1 | DIR_L | 4 | AXIS_H | DIR_L | r0-5 c0-1 | 1 | [0 0 1 10] | (1,0)out | r0-5 c1-6 | 0 | 1
(1,2) | r0-5 c2-2 | 1 | DIR_L | 3 | AXIS_H | DIR_L | r0-5 c1-2 | 2 | [0 0 3 8] | (1,1)out | r0-5 c1-6 | 0 | 2
(1,3) | r0-5 c3-3 | 1 | DIR_L | 9 | AXIS_H | DIR_L | r0-5 c2-3 | 3 | [0 0 5 6] | (1,2)out | r0-5 c1-6 | 0 | 3
(1,4) | r0-5 c4-4 | 1 | DIR_L | 9 | AXIS_H | DIR_L | r0-5 c3-4 | 4 | [0 0 7 4] | (1,3)out | r0-5 c1-6 | 0 | 4
(1,5) | r0-5 c5-5 | 1 | DIR_L | 9 | AXIS_H | DIR_L | r0-5 c4-5 | 5 | [0 0 9 2] | (1,4)out | r0-5 c1-6 | 0 | 5
(1,6) | r0-5 c6-6 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c5-6 | 6 | [0 0 11 0] | (1,5)out | r0-5 c1-6 | 0 | 6
(2,1) | r0-5 c1-1 | 1 | DIR_L | 4 | AXIS_H | DIR_L | r0-5 c0-1 | 1 | [0 0 1 10] | (2,0)out | r0-5 c1-6 | 0 | 1
(2,2) | r0-5 c2-2 | 1 | DIR_L | 3 | AXIS_H | DIR_L | r0-5 c1-2 | 2 | [0 0 3 8] | (2,1)out | r0-5 c1-6 | 0 | 2
(2,3) | r0-5 c3-3 | 1 | DIR_L | 9 | AXIS_H | DIR_L | r0-5 c2-3 | 3 | [0 0 5 6] | (2,2)out | r0-5 c1-6 | 0 | 3
(2,4) | r0-5 c4-4 | 1 | DIR_L | 3 | AXIS_H | DIR_L | r0-5 c3-4 | 4 | [0 0 7 4] | (2,3)out | r0-5 c1-6 | 0 | 4
(2,5) | r0-5 c5-5 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c4-5 | 5 | [0 0 9 2] | (2,4)out | r0-5 c1-6 | 0 | 5
(2,6) | r0-5 c6-6 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c5-6 | 6 | [0 0 11 0] | (2,5)out | r0-5 c1-6 | 0 | 6
(3,1) | r0-5 c1-1 | 1 | DIR_L | 4 | AXIS_H | DIR_L | r0-5 c0-1 | 1 | [0 0 1 10] | (3,0)out | r0-5 c1-6 | 0 | 1
(3,2) | r0-5 c2-2 | 1 | DIR_L | 3 | AXIS_H | DIR_L | r0-5 c1-2 | 2 | [0 0 3 8] | (3,1)out | r0-5 c1-6 | 0 | 2
(3,3) | r0-5 c3-3 | 1 | DIR_L | 3 | AXIS_H | DIR_L | r0-5 c2-3 | 3 | [0 0 5 6] | (3,2)out | r0-5 c1-6 | 0 | 3
(3,4) | r0-5 c4-4 | 1 | DIR_L | 3 | AXIS_H | DIR_L | r0-5 c3-4 | 4 | [0 0 7 4] | (3,3)out | r0-5 c1-6 | 0 | 4
(3,5) | r0-5 c5-5 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c4-5 | 5 | [0 0 9 2] | (3,4)out | r0-5 c1-6 | 0 | 5
(3,6) | r0-5 c6-6 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c5-6 | 6 | [0 0 11 0] | (3,5)out | r0-5 c1-6 | 0 | 6
(4,1) | r0-5 c1-1 | 1 | DIR_L | 4 | AXIS_H | DIR_L | r0-5 c0-1 | 1 | [0 0 1 10] | (4,0)out | r0-5 c1-6 | 0 | 1
(4,2) | r0-5 c2-2 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c1-2 | 2 | [0 0 3 8] | (4,1)out | r0-5 c1-6 | 0 | 2
(4,3) | r0-5 c3-3 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c2-3 | 3 | [0 0 5 6] | (4,2)out | r0-5 c1-6 | 0 | 3
(4,4) | r0-5 c4-4 | 1 | DIR_L | 5 | AXIS_H | DIR_L | r0-5 c3-4 | 4 | [0 0 7 4] | (4,3)out | r0-5 c1-6 | 0 | 4
(4,5) | r0-5 c5-5 | 1 | DIR_L | 5 | AXIS_H | DIR_L | r0-5 c4-5 | 5 | [0 0 9 2] | (4,4)out | r0-5 c1-6 | 0 | 5
(4,6) | r0-5 c6-6 | 1 | DIR_L | 5 | AXIS_H | DIR_L | r0-5 c5-6 | 6 | [0 0 11 0] | (4,5)out | r0-5 c1-6 | 0 | 6
```

Train example 1: 36 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 8 8 8 4 4 4
. 9 9 8 3 4 4
. 9 9 8 3 3 3
. 9 1 1 1 5 3
. 4 4 1 5 5 5
. 4 4 1 5 5 5
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13
(0,1) | r0-5 c1-1 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c0-1 | 1 | [0 0 1 10] | (0,0)out | r0-5 c1-6 | 0 | 1
(0,2) | r0-5 c2-2 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c1-2 | 2 | [0 0 3 8] | (0,1)out | r0-5 c1-6 | 0 | 2
(0,3) | r0-5 c3-3 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c2-3 | 3 | [0 0 5 6] | (0,2)out | r0-5 c1-6 | 0 | 3
(0,4) | r0-5 c4-4 | 1 | DIR_L | 4 | AXIS_H | DIR_L | r0-5 c3-4 | 4 | [0 0 7 4] | (0,3)out | r0-5 c1-6 | 0 | 4
(0,5) | r0-5 c5-5 | 1 | DIR_L | 4 | AXIS_H | DIR_L | r0-5 c4-5 | 5 | [0 0 9 2] | (0,4)out | r0-5 c1-6 | 0 | 5
(0,6) | r0-5 c6-6 | 1 | DIR_L | 4 | AXIS_H | DIR_L | r0-5 c5-6 | 6 | [0 0 11 0] | (0,5)out | r0-5 c1-6 | 0 | 6
(1,1) | r0-5 c1-1 | 1 | DIR_L | 9 | AXIS_H | DIR_L | r0-5 c0-1 | 1 | [0 0 1 10] | (1,0)out | r0-5 c1-6 | 0 | 1
(1,2) | r0-5 c2-2 | 1 | DIR_L | 9 | AXIS_H | DIR_L | r0-5 c1-2 | 2 | [0 0 3 8] | (1,1)out | r0-5 c1-6 | 0 | 2
(1,3) | r0-5 c3-3 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c2-3 | 3 | [0 0 5 6] | (1,2)out | r0-5 c1-6 | 0 | 3
(1,4) | r0-5 c4-4 | 1 | DIR_L | 3 | AXIS_H | DIR_L | r0-5 c3-4 | 4 | [0 0 7 4] | (1,3)out | r0-5 c1-6 | 0 | 4
(1,5) | r0-5 c5-5 | 1 | DIR_L | 4 | AXIS_H | DIR_L | r0-5 c4-5 | 5 | [0 0 9 2] | (1,4)out | r0-5 c1-6 | 0 | 5
(1,6) | r0-5 c6-6 | 1 | DIR_L | 4 | AXIS_H | DIR_L | r0-5 c5-6 | 6 | [0 0 11 0] | (1,5)out | r0-5 c1-6 | 0 | 6
(2,1) | r0-5 c1-1 | 1 | DIR_L | 9 | AXIS_H | DIR_L | r0-5 c0-1 | 1 | [0 0 1 10] | (2,0)out | r0-5 c1-6 | 0 | 1
(2,2) | r0-5 c2-2 | 1 | DIR_L | 9 | AXIS_H | DIR_L | r0-5 c1-2 | 2 | [0 0 3 8] | (2,1)out | r0-5 c1-6 | 0 | 2
(2,3) | r0-5 c3-3 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c2-3 | 3 | [0 0 5 6] | (2,2)out | r0-5 c1-6 | 0 | 3
(2,4) | r0-5 c4-4 | 1 | DIR_L | 3 | AXIS_H | DIR_L | r0-5 c3-4 | 4 | [0 0 7 4] | (2,3)out | r0-5 c1-6 | 0 | 4
(2,5) | r0-5 c5-5 | 1 | DIR_L | 3 | AXIS_H | DIR_L | r0-5 c4-5 | 5 | [0 0 9 2] | (2,4)out | r0-5 c1-6 | 0 | 5
(2,6) | r0-5 c6-6 | 1 | DIR_L | 3 | AXIS_H | DIR_L | r0-5 c5-6 | 6 | [0 0 11 0] | (2,5)out | r0-5 c1-6 | 0 | 6
(3,1) | r0-5 c1-1 | 1 | DIR_L | 9 | AXIS_H | DIR_L | r0-5 c0-1 | 1 | [0 0 1 10] | (3,0)out | r0-5 c1-6 | 0 | 1
(3,2) | r0-5 c2-2 | 1 | DIR_L | 1 | AXIS_H | DIR_L | r0-5 c1-2 | 2 | [0 0 3 8] | (3,1)out | r0-5 c1-6 | 0 | 2
(3,3) | r0-5 c3-3 | 1 | DIR_L | 1 | AXIS_H | DIR_L | r0-5 c2-3 | 3 | [0 0 5 6] | (3,2)out | r0-5 c1-6 | 0 | 3
(3,4) | r0-5 c4-4 | 1 | DIR_L | 1 | AXIS_H | DIR_L | r0-5 c3-4 | 4 | [0 0 7 4] | (3,3)out | r0-5 c1-6 | 0 | 4
(3,5) | r0-5 c5-5 | 1 | DIR_L | 5 | AXIS_H | DIR_L | r0-5 c4-5 | 5 | [0 0 9 2] | (3,4)out | r0-5 c1-6 | 0 | 5
(3,6) | r0-5 c6-6 | 1 | DIR_L | 3 | AXIS_H | DIR_L | r0-5 c5-6 | 6 | [0 0 11 0] | (3,5)out | r0-5 c1-6 | 0 | 6
(4,1) | r0-5 c1-1 | 1 | DIR_L | 4 | AXIS_H | DIR_L | r0-5 c0-1 | 1 | [0 0 1 10] | (4,0)out | r0-5 c1-6 | 0 | 1
(4,2) | r0-5 c2-2 | 1 | DIR_L | 4 | AXIS_H | DIR_L | r0-5 c1-2 | 2 | [0 0 3 8] | (4,1)out | r0-5 c1-6 | 0 | 2
(4,3) | r0-5 c3-3 | 1 | DIR_L | 1 | AXIS_H | DIR_L | r0-5 c2-3 | 3 | [0 0 5 6] | (4,2)out | r0-5 c1-6 | 0 | 3
(4,4) | r0-5 c4-4 | 1 | DIR_L | 5 | AXIS_H | DIR_L | r0-5 c3-4 | 4 | [0 0 7 4] | (4,3)out | r0-5 c1-6 | 0 | 4
(4,5) | r0-5 c5-5 | 1 | DIR_L | 5 | AXIS_H | DIR_L | r0-5 c4-5 | 5 | [0 0 9 2] | (4,4)out | r0-5 c1-6 | 0 | 5
(4,6) | r0-5 c6-6 | 1 | DIR_L | 5 | AXIS_H | DIR_L | r0-5 c5-6 | 6 | [0 0 11 0] | (4,5)out | r0-5 c1-6 | 0 | 6
```

Train example 2: 36 rows, the first 30 shown
Drawn on a 6x7 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. 8 8 8 4 4 4
. 8 9 8 4 9 1
. 8 9 9 9 9 1
. 5 5 3 3 3 1
. 5 5 3 4 3 1
. 5 5 3 4 4 4
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13
(0,1) | r0-5 c1-1 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c0-1 | 1 | [0 0 1 10] | (0,0)out | r0-5 c1-6 | 0 | 1
(0,2) | r0-5 c2-2 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c1-2 | 2 | [0 0 3 8] | (0,1)out | r0-5 c1-6 | 0 | 2
(0,3) | r0-5 c3-3 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c2-3 | 3 | [0 0 5 6] | (0,2)out | r0-5 c1-6 | 0 | 3
(0,4) | r0-5 c4-4 | 1 | DIR_L | 4 | AXIS_H | DIR_L | r0-5 c3-4 | 4 | [0 0 7 4] | (0,3)out | r0-5 c1-6 | 0 | 4
(0,5) | r0-5 c5-5 | 1 | DIR_L | 4 | AXIS_H | DIR_L | r0-5 c4-5 | 5 | [0 0 9 2] | (0,4)out | r0-5 c1-6 | 0 | 5
(0,6) | r0-5 c6-6 | 1 | DIR_L | 4 | AXIS_H | DIR_L | r0-5 c5-6 | 6 | [0 0 11 0] | (0,5)out | r0-5 c1-6 | 0 | 6
(1,1) | r0-5 c1-1 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c0-1 | 1 | [0 0 1 10] | (1,0)out | r0-5 c1-6 | 0 | 1
(1,2) | r0-5 c2-2 | 1 | DIR_L | 9 | AXIS_H | DIR_L | r0-5 c1-2 | 2 | [0 0 3 8] | (1,1)out | r0-5 c1-6 | 0 | 2
(1,3) | r0-5 c3-3 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c2-3 | 3 | [0 0 5 6] | (1,2)out | r0-5 c1-6 | 0 | 3
(1,4) | r0-5 c4-4 | 1 | DIR_L | 4 | AXIS_H | DIR_L | r0-5 c3-4 | 4 | [0 0 7 4] | (1,3)out | r0-5 c1-6 | 0 | 4
(1,5) | r0-5 c5-5 | 1 | DIR_L | 9 | AXIS_H | DIR_L | r0-5 c4-5 | 5 | [0 0 9 2] | (1,4)out | r0-5 c1-6 | 0 | 5
(1,6) | r0-5 c6-6 | 1 | DIR_L | 1 | AXIS_H | DIR_L | r0-5 c5-6 | 6 | [0 0 11 0] | (1,5)out | r0-5 c1-6 | 0 | 6
(2,1) | r0-5 c1-1 | 1 | DIR_L | 8 | AXIS_H | DIR_L | r0-5 c0-1 | 1 | [0 0 1 10] | (2,0)out | r0-5 c1-6 | 0 | 1
(2,2) | r0-5 c2-2 | 1 | DIR_L | 9 | AXIS_H | DIR_L | r0-5 c1-2 | 2 | [0 0 3 8] | (2,1)out | r0-5 c1-6 | 0 | 2
(2,3) | r0-5 c3-3 | 1 | DIR_L | 9 | AXIS_H | DIR_L | r0-5 c2-3 | 3 | [0 0 5 6] | (2,2)out | r0-5 c1-6 | 0 | 3
(2,4) | r0-5 c4-4 | 1 | DIR_L | 9 | AXIS_H | DIR_L | r0-5 c3-4 | 4 | [0 0 7 4] | (2,3)out | r0-5 c1-6 | 0 | 4
(2,5) | r0-5 c5-5 | 1 | DIR_L | 9 | AXIS_H | DIR_L | r0-5 c4-5 | 5 | [0 0 9 2] | (2,4)out | r0-5 c1-6 | 0 | 5
(2,6) | r0-5 c6-6 | 1 | DIR_L | 1 | AXIS_H | DIR_L | r0-5 c5-6 | 6 | [0 0 11 0] | (2,5)out | r0-5 c1-6 | 0 | 6
(3,1) | r0-5 c1-1 | 1 | DIR_L | 5 | AXIS_H | DIR_L | r0-5 c0-1 | 1 | [0 0 1 10] | (3,0)out | r0-5 c1-6 | 0 | 1
(3,2) | r0-5 c2-2 | 1 | DIR_L | 5 | AXIS_H | DIR_L | r0-5 c1-2 | 2 | [0 0 3 8] | (3,1)out | r0-5 c1-6 | 0 | 2
(3,3) | r0-5 c3-3 | 1 | DIR_L | 3 | AXIS_H | DIR_L | r0-5 c2-3 | 3 | [0 0 5 6] | (3,2)out | r0-5 c1-6 | 0 | 3
(3,4) | r0-5 c4-4 | 1 | DIR_L | 3 | AXIS_H | DIR_L | r0-5 c3-4 | 4 | [0 0 7 4] | (3,3)out | r0-5 c1-6 | 0 | 4
(3,5) | r0-5 c5-5 | 1 | DIR_L | 3 | AXIS_H | DIR_L | r0-5 c4-5 | 5 | [0 0 9 2] | (3,4)out | r0-5 c1-6 | 0 | 5
(3,6) | r0-5 c6-6 | 1 | DIR_L | 1 | AXIS_H | DIR_L | r0-5 c5-6 | 6 | [0 0 11 0] | (3,5)out | r0-5 c1-6 | 0 | 6
(4,1) | r0-5 c1-1 | 1 | DIR_L | 5 | AXIS_H | DIR_L | r0-5 c0-1 | 1 | [0 0 1 10] | (4,0)out | r0-5 c1-6 | 0 | 1
(4,2) | r0-5 c2-2 | 1 | DIR_L | 5 | AXIS_H | DIR_L | r0-5 c1-2 | 2 | [0 0 3 8] | (4,1)out | r0-5 c1-6 | 0 | 2
(4,3) | r0-5 c3-3 | 1 | DIR_L | 3 | AXIS_H | DIR_L | r0-5 c2-3 | 3 | [0 0 5 6] | (4,2)out | r0-5 c1-6 | 0 | 3
(4,4) | r0-5 c4-4 | 1 | DIR_L | 4 | AXIS_H | DIR_L | r0-5 c3-4 | 4 | [0 0 7 4] | (4,3)out | r0-5 c1-6 | 0 | 4
(4,5) | r0-5 c5-5 | 1 | DIR_L | 3 | AXIS_H | DIR_L | r0-5 c4-5 | 5 | [0 0 9 2] | (4,4)out | r0-5 c1-6 | 0 | 5
(4,6) | r0-5 c6-6 | 1 | DIR_L | 1 | AXIS_H | DIR_L | r0-5 c5-6 | 6 | [0 0 11 0] | (4,5)out | r0-5 c1-6 | 0 | 6
```


#### &r27, assignment 16 of 16

- DET values that differ between the assignments: &r0 = {(DIR_R)}; &r9 = {(DIR_R)}
- empty at every example
## What I see

The task: the left column of a 6x7 input is a band of 6s with one 2. The output drops the band and rotates the rows down by the 2's row index: 0 in e0, 2 in e1 and 3 in e2. Two DETs of four directions each give 16 assignments: &r0 is the shift direction and &r9 is the marker edge. The case's assignment is &r0 = DIR_B with &r9 = DIR_L (assignment 7 of the tables that read both).

- **&r0, &r1** (DET: shift direction; its opposite, the edge that the rows count from): one row, the same in every example. A constant per assignment.
- **&r2** (every cell with its distance from that edge): 42 rows, one per cell. The drawing is a gradient (5 to 0 down the rows at &r0 = DIR_T). This restates the input's cells and the grid size.
- **&r3** (Cardinality of the distances): 6 at DIR_T and DIR_B, 7 at DIR_L and DIR_R: the grid's height or width. **&r6, &r7** (Frame: the rows or the columns as boxes, and the axis with its length) restate it. From &r3 on, the assignments fall into two pairs that the renderer reports as equal ("rows equal to those of assignment 1"). Assignments 1 and 2 are equal, and 3 and 4 are equal. Only the axis of a direction reaches these tables. The sign does not reach them until &r8 and &r23, and so the four values of &r0 give two distinct tables.
- **&r8** (each row box with its distance): the frame's index. At DIR_T it numbers the rows 5 to 0 from the top, and at DIR_B 0 to 5. No signal beyond &r2 and &r6.
- **&r9** (DET: marker edge), **&r10** (DET DimDiff): 1, the band's width, which is the input width minus the output width. **&r11** (DET RarestColor): 2, the marker's color. Each lib DET reduces the grids to one value, and here each value is one of the rule's parameters.
- **&r12** (input cells of color &r11 at distance 0 from edge &r9): **the signal jumps here.** At &r9 = DIR_L, there is one row in every example: `(0,0)`, `(2,0)`, `(3,0)`, the marker in each band. At DIR_T, it holds one row in e0 only, the corner cell (0,0), and it is empty in e1 and e2. At DIR_B and DIR_R, it is empty at every example. At this DET, the table alone picks the right value: the right value is the one assignment that gives exactly one row in every example.
- **&r13 to &r18** (Order over the distances): &r13 is the pairs (k, k), &r15 is the low (0), &r16 is the high (5 or 6), &r17 is k to k+1 without the wrap, and &r18 is k to k+1 mod 6 (`5 | 0`), the cycle. Each is a function of the grid size, and each is the same in every example. They restate &r3 and add no signal.
- **&r23** (the marker with its distance from the counting edge): the shift amount. At assignment 7 (&r0 = DIR_B, &r9 = DIR_L) the values are 0, 2 and 3, the rotation of each example. At assignment 3 (&r0 = DIR_T) they are 5, 3 and 2, the distances from the other edge. Both are one row per example, and the table alone cannot tell which is right. The 16 assignments give 8 that are empty at every example (the wrong marker edges).
- **&r24** (Walk along the cycle: from each row index, each step count up to the amount, the row reached): at assignment 7, the row counts are 6, 18 and 24, which is 6 x (amount + 1). The table is the closure of &r18 up to &r23's amount, so it adds no signal beyond those two, but its row count per example encodes the amount. The walks at the amount itself are the only rows that the next clause uses. The walks at smaller steps are noise.
- **&r27** (out: each kept input cell, placed at its rotated row): 36 rows at four assignments (&r9 = DIR_L with each &r0). The drawing is by the first Box column, the input cell, so at all four it shows the input without the band. The output cell is column c10, and only that column tells the assignments apart. In e0, assignment 7 has `(0,1) ... (0,0)out`, which keeps row 0 at row 0, and assignment 3 has `(0,1) ... (1,0)out`, which moves it to row 1. Only a comparison with the outputs picks assignment 7.

Rows that look like noise: &r2, &r3, &r6 to &r8 and &r13 to &r18 (the grid's size and index, restated per example and per assignment); the twin assignments from &r3 on; the walks of &r24 at steps short of the amount. The signal jumps at &r12, which picks the marker edge, and at &r23, which gives the amounts. The shift direction is never told apart until the outputs are compared.
