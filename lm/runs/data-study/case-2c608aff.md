# 2c608aff, case `concept`

- concept case: True; tokens: 329; tables: 19 relations, 19 per assignment
- cells: a Position is `(row,col)` of the example's input grid (`(row,col)out` where it fits only the output grid), an Offset `+(drow,dcol)`, another Box `rR0-R1 cC0-C1` over the input grid or `[t b l r]` margins; an Ident is `id<n>`, equal only within one case; see README.md

## Grids

### Train example 0: input 9x12, output 9x12

```
input                      output
8 8 8 8 8 8 8 8 8 8 8 8    8 8 8 8 8 8 8 8 8 8 8 8
8 8 3 3 3 8 8 8 8 8 8 8    8 8 3 3 3 8 8 8 8 8 8 8
8 8 3 3 3 8 8 8 8 8 8 8    8 8 3 3 3 8 8 8 8 8 8 8
8 8 3 3 3 8 8 8 8 4 8 8    8 8 3 3 3 4 4 4 4 4 8 8
8 8 3 3 3 8 8 8 8 8 8 8    8 8 3 3 3 8 8 8 8 8 8 8
8 8 8 8 8 8 8 8 8 8 8 8    8 8 8 8 8 8 8 8 8 8 8 8
8 8 8 8 8 8 8 8 8 8 8 8    8 8 8 8 8 8 8 8 8 8 8 8
8 8 8 8 8 8 8 4 8 8 8 8    8 8 8 8 8 8 8 4 8 8 8 8
8 8 8 8 8 8 8 8 8 8 8 8    8 8 8 8 8 8 8 8 8 8 8 8
```

### Train example 1: input 10x12, output 10x12

```
input                      output
2 2 2 2 2 2 2 2 2 2 2 2    2 2 2 2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2 2 2 2    2 2 2 2 2 2 2 2 2 2 2 2
2 2 2 1 1 1 2 2 2 2 2 2    2 2 2 1 1 1 2 2 2 2 2 2
2 2 2 1 1 1 2 2 2 2 2 2    2 2 2 1 1 1 2 2 2 2 2 2
2 2 2 1 1 1 2 2 2 2 2 2    2 2 2 1 1 1 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2 2 2 2    2 2 2 8 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2 2 2 2    2 2 2 8 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2 2 2 2    2 2 2 8 2 2 2 2 2 2 2 2
2 2 2 8 2 2 2 2 2 2 2 2    2 2 2 8 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2 2 2 2    2 2 2 2 2 2 2 2 2 2 2 2
```

### Train example 2: input 14x12, output 14x12

```
input                      output
1 1 1 1 2 1 1 1 1 1 1 1    1 1 1 1 2 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1    1 1 1 1 2 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1    1 1 1 1 2 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1    1 1 1 1 2 1 1 1 1 1 1 1
1 1 1 4 4 4 4 1 1 1 1 1    1 1 1 4 4 4 4 1 1 1 1 1
1 1 1 4 4 4 4 1 1 1 1 1    1 1 1 4 4 4 4 1 1 1 1 1
1 1 1 4 4 4 4 1 1 1 2 1    1 1 1 4 4 4 4 2 2 2 2 1
1 1 1 4 4 4 4 1 1 1 1 1    1 1 1 4 4 4 4 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1    1 1 1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1    1 1 1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1    1 1 1 1 1 1 1 1 1 1 1 1
1 2 1 1 1 1 1 1 1 1 1 1    1 2 1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1    1 1 1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1    1 1 1 1 1 1 1 1 1 1 1 1
```

### Train example 3: input 14x18, output 14x18

```
input                                  output
1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1    1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 4 1 1 1 1 1 1 1 1 1    1 1 1 1 1 1 1 1 4 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1    1 1 1 1 1 1 1 1 4 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 4 1 1 1 1 1 1    1 1 1 1 1 1 1 1 4 1 1 4 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 4 1 1    1 1 1 1 1 1 1 1 4 1 1 4 1 1 1 4 1 1
1 1 4 1 1 1 1 5 5 5 5 5 1 1 1 1 1 1    1 1 4 4 4 4 4 5 5 5 5 5 1 1 1 1 1 1
1 1 1 1 1 1 1 5 5 5 5 5 1 1 1 1 1 1    1 1 1 1 1 1 1 5 5 5 5 5 1 1 1 1 1 1
1 1 1 1 1 1 1 5 5 5 5 5 1 1 1 1 1 1    1 1 1 1 1 1 1 5 5 5 5 5 1 1 1 1 1 1
1 1 1 1 1 1 1 5 5 5 5 5 1 1 1 1 1 1    1 1 1 1 1 1 1 5 5 5 5 5 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1    1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1    1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1 1 4 1 1 1 1    1 1 1 1 1 1 1 1 1 1 1 1 1 4 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1    1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1    1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
```

### Test example 0: input 19x21

```
2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2 1 2 2 2 2 2 2 2 2 2 2 2
2 2 1 2 2 2 2 2 2 2 2 2 2 2 2 2 2 1 2 2 2
2 2 2 2 2 2 2 2 2 2 2 2 2 1 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 8 8 8 8 8 8 8 8 2 2 2 2 2 2
2 2 2 2 2 2 2 8 8 8 8 8 8 8 8 2 2 2 2 2 2
2 2 2 2 2 2 2 8 8 8 8 8 8 8 8 2 2 2 2 1 2
2 2 2 2 2 2 2 8 8 8 8 8 8 8 8 2 2 2 2 2 2
2 2 1 2 2 2 2 8 8 8 8 8 8 8 8 2 2 2 2 2 2
2 2 2 2 2 2 2 8 8 8 8 8 8 8 8 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 1 2 2 2 2 2
2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2
2 2 2 1 2 2 2 2 2 2 2 1 2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2 2
```

## Program and tables

Model-written tokens plain, engine-written ones in [brackets]. Each clause is followed by the tables of the relations it declares. A table whose entries hold several DET assignments is given once per assignment, each marked with the values, at that assignment, of the DETs whose value differs between them; a DET's value is the rows of its own table at that assignment.

```
INIT Cardinality [:0] input :0 * [L0] :1 ^ [L1] END [:1] input :0 * [L2] :1 L1 END [:0] END [:1] L2 END [:2] SKIP [:2] SKIP [&r0] [&r1] [&r2]
```

### &r0 (export table 2)

- columns: c0: Color, c1: Number
- depth 2, candidate keys none
- rows per train example: [3, 3, 3, 3]; test: 3

Train example 0: 3 rows
```
c0 | c1
3 | 12
4 | 2
8 | 94
```

Train example 1: 3 rows
```
c0 | c1
1 | 9
2 | 110
8 | 1
```

Train example 2: 3 rows
```
c0 | c1
1 | 149
2 | 3
4 | 16
```

Train example 3: 3 rows
```
c0 | c1
1 | 227
4 | 5
5 | 20
```

```
INIT Order [:0] SKIP [:1] &r0 :1 :0 * [L0] END END [:0] END [:1] L0 END [:2] SKIP [:3] &r0 :1 :0 * [L1] END :2 * [L2] END [:0] END [:1] L1 END [:2] L2 END [:4] SKIP [&r3] [&r4] [&r5] [&r6] [&r7] [&r8] [&r9] [&r10] [&r11] [&r12]
```

### &r3 (export table 3)

- columns: c0: Color, c1: Number
- depth 4, candidate keys none
- rows per train example: [3, 3, 3, 3]; test: 3

Train example 0: 3 rows
```
c0 | c1
3 | 1
4 | 0
8 | 2
```

Train example 1: 3 rows
```
c0 | c1
1 | 1
2 | 2
8 | 0
```

Train example 2: 3 rows
```
c0 | c1
1 | 2
2 | 0
4 | 1
```

Train example 3: 3 rows
```
c0 | c1
1 | 2
4 | 0
5 | 1
```

### &r4 (export table 4)

- columns: c0: Color, c1: Number
- depth 4, candidate keys none
- rows per train example: [3, 3, 3, 3]; test: 3

Train example 0: 3 rows
```
c0 | c1
3 | 1
4 | 2
8 | 0
```

Train example 1: 3 rows
```
c0 | c1
1 | 1
2 | 0
8 | 2
```

Train example 2: 3 rows
```
c0 | c1
1 | 0
2 | 2
4 | 1
```

Train example 3: 3 rows
```
c0 | c1
1 | 0
4 | 2
5 | 1
```

### &r5 (export table 5)

- columns: c0: Color
- depth 4, candidate keys none
- rows per train example: [1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
4
```

Train example 1: 1 row
```
c0
8
```

Train example 2: 1 row
```
c0
2
```

Train example 3: 1 row
```
c0
4
```

### &r6 (export table 6)

- columns: c0: Color
- depth 4, candidate keys none
- rows per train example: [1, 1, 1, 1]; test: 1

Train example 0: 1 row
```
c0
8
```

Train example 1: 1 row
```
c0
2
```

Train example 2: 1 row
```
c0
1
```

Train example 3: 1 row
```
c0
1
```

### &r7 (export table 7)

- columns: c0: Color, c1: Color
- depth 4, candidate keys none
- rows per train example: [2, 2, 2, 2]; test: 2

Train example 0: 2 rows
```
c0 | c1
3 | 8
4 | 3
```

Train example 1: 2 rows
```
c0 | c1
1 | 2
8 | 1
```

Train example 2: 2 rows
```
c0 | c1
2 | 4
4 | 1
```

Train example 3: 2 rows
```
c0 | c1
4 | 5
5 | 1
```

### &r8 (export table 8)

- columns: c0: Color, c1: Color
- depth 4, candidate keys none
- rows per train example: [3, 3, 3, 3]; test: 3

Train example 0: 3 rows
```
c0 | c1
3 | 8
4 | 3
8 | 4
```

Train example 1: 3 rows
```
c0 | c1
1 | 2
2 | 8
8 | 1
```

Train example 2: 3 rows
```
c0 | c1
1 | 2
2 | 4
4 | 1
```

Train example 3: 3 rows
```
c0 | c1
1 | 4
4 | 5
5 | 1
```

```
RULE input :0 * [L0] :1 * [L1] NOT &r6 :1 L1 END [&r13]
```

### &r13 (export table 9)

- columns: c0: Box, c1: Color
- depth 5, candidate keys none
- rows per train example: [14, 10, 19, 25]; test: 57

Train example 0: 14 rows
Drawn on a 9x12 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . . . . .
. . 3 3 3 . . . . . . .
. . 3 3 3 . . . . . . .
. . 3 3 3 . . . . 4 . .
. . 3 3 3 . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . 4 . . . .
. . . . . . . . . . . .
```
```
c0 | c1
(1,2) | 3
(1,3) | 3
(1,4) | 3
(2,2) | 3
(2,3) | 3
(2,4) | 3
(3,2) | 3
(3,3) | 3
(3,4) | 3
(3,9) | 4
(4,2) | 3
(4,3) | 3
(4,4) | 3
(7,7) | 4
```

Train example 1: 10 rows
Drawn on a 10x12 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . 1 1 1 . . . . . .
. . . 1 1 1 . . . . . .
. . . 1 1 1 . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . 8 . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1
(2,3) | 1
(2,4) | 1
(2,5) | 1
(3,3) | 1
(3,4) | 1
(3,5) | 1
(4,3) | 1
(4,4) | 1
(4,5) | 1
(8,3) | 8
```

Train example 2: 19 rows
Drawn on a 14x12 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . 2 . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . 4 4 4 4 . . . . .
. . . 4 4 4 4 . . . . .
. . . 4 4 4 4 . . . 2 .
. . . 4 4 4 4 . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. 2 . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1
(0,4) | 2
(4,3) | 4
(4,4) | 4
(4,5) | 4
(4,6) | 4
(5,3) | 4
(5,4) | 4
(5,5) | 4
(5,6) | 4
(6,3) | 4
(6,4) | 4
(6,5) | 4
(6,6) | 4
(6,10) | 2
(7,3) | 4
(7,4) | 4
(7,5) | 4
(7,6) | 4
(11,1) | 2
```

Train example 3: 25 rows
Drawn on a 14x18 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . . . . . . . . . . .
. . . . . . . . 4 . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . 4 . . . . . .
. . . . . . . . . . . . . . . 4 . .
. . 4 . . . . 5 5 5 5 5 . . . . . .
. . . . . . . 5 5 5 5 5 . . . . . .
. . . . . . . 5 5 5 5 5 . . . . . .
. . . . . . . 5 5 5 5 5 . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . 4 . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
```
```
c0 | c1
(1,8) | 4
(3,11) | 4
(4,15) | 4
(5,2) | 4
(5,7) | 5
(5,8) | 5
(5,9) | 5
(5,10) | 5
(5,11) | 5
(6,7) | 5
(6,8) | 5
(6,9) | 5
(6,10) | 5
(6,11) | 5
(7,7) | 5
(7,8) | 5
(7,9) | 5
(7,10) | 5
(7,11) | 5
(8,7) | 5
(8,8) | 5
(8,9) | 5
(8,10) | 5
(8,11) | 5
(11,13) | 4
```

```
RULE &r13 :0 * [L0] dir_elem :0 * [L1] neighbor :0 L0 :1 L1 :2 * [L2] &r13 :0 L2 END [&r14]
```

### &r14 (export table 10)

- columns: c0: Dir, c1: Box, c2: Box
- depth 6, candidate keys none
- rows per train example: [34, 24, 48, 62]; test: 164

Train example 0: 34 rows, the first 30 shown
Drawn on a 9x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . .
. . 2 3 2 . . . . . . .
. . 3 4 3 . . . . . . .
. . 3 4 3 . . . . . . .
. . 2 3 2 . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1 | c2
DIR_T | (2,2) | (1,2)
DIR_T | (2,3) | (1,3)
DIR_T | (2,4) | (1,4)
DIR_T | (3,2) | (2,2)
DIR_T | (3,3) | (2,3)
DIR_T | (3,4) | (2,4)
DIR_T | (4,2) | (3,2)
DIR_T | (4,3) | (3,3)
DIR_T | (4,4) | (3,4)
DIR_B | (1,2) | (2,2)
DIR_B | (1,3) | (2,3)
DIR_B | (1,4) | (2,4)
DIR_B | (2,2) | (3,2)
DIR_B | (2,3) | (3,3)
DIR_B | (2,4) | (3,4)
DIR_B | (3,2) | (4,2)
DIR_B | (3,3) | (4,3)
DIR_B | (3,4) | (4,4)
DIR_L | (1,3) | (1,2)
DIR_L | (1,4) | (1,3)
DIR_L | (2,3) | (2,2)
DIR_L | (2,4) | (2,3)
DIR_L | (3,3) | (3,2)
DIR_L | (3,4) | (3,3)
DIR_L | (4,3) | (4,2)
DIR_L | (4,4) | (4,3)
DIR_R | (1,2) | (1,3)
DIR_R | (1,3) | (1,4)
DIR_R | (2,2) | (2,3)
DIR_R | (2,3) | (2,4)
```

Train example 1: 24 rows
Drawn on a 10x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . 2 3 2 . . . . . .
. . . 3 4 3 . . . . . .
. . . 2 3 2 . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1 | c2
DIR_T | (3,3) | (2,3)
DIR_T | (3,4) | (2,4)
DIR_T | (3,5) | (2,5)
DIR_T | (4,3) | (3,3)
DIR_T | (4,4) | (3,4)
DIR_T | (4,5) | (3,5)
DIR_B | (2,3) | (3,3)
DIR_B | (2,4) | (3,4)
DIR_B | (2,5) | (3,5)
DIR_B | (3,3) | (4,3)
DIR_B | (3,4) | (4,4)
DIR_B | (3,5) | (4,5)
DIR_L | (2,4) | (2,3)
DIR_L | (2,5) | (2,4)
DIR_L | (3,4) | (3,3)
DIR_L | (3,5) | (3,4)
DIR_L | (4,4) | (4,3)
DIR_L | (4,5) | (4,4)
DIR_R | (2,3) | (2,4)
DIR_R | (2,4) | (2,5)
DIR_R | (3,3) | (3,4)
DIR_R | (3,4) | (3,5)
DIR_R | (4,3) | (4,4)
DIR_R | (4,4) | (4,5)
```

Train example 2: 48 rows, the first 30 shown
Drawn on a 14x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . 2 3 3 2 . . . . .
. . . 3 4 4 3 . . . . .
. . . 3 4 4 3 . . . . .
. . . 2 3 3 2 . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1 | c2
DIR_T | (5,3) | (4,3)
DIR_T | (5,4) | (4,4)
DIR_T | (5,5) | (4,5)
DIR_T | (5,6) | (4,6)
DIR_T | (6,3) | (5,3)
DIR_T | (6,4) | (5,4)
DIR_T | (6,5) | (5,5)
DIR_T | (6,6) | (5,6)
DIR_T | (7,3) | (6,3)
DIR_T | (7,4) | (6,4)
DIR_T | (7,5) | (6,5)
DIR_T | (7,6) | (6,6)
DIR_B | (4,3) | (5,3)
DIR_B | (4,4) | (5,4)
DIR_B | (4,5) | (5,5)
DIR_B | (4,6) | (5,6)
DIR_B | (5,3) | (6,3)
DIR_B | (5,4) | (6,4)
DIR_B | (5,5) | (6,5)
DIR_B | (5,6) | (6,6)
DIR_B | (6,3) | (7,3)
DIR_B | (6,4) | (7,4)
DIR_B | (6,5) | (7,5)
DIR_B | (6,6) | (7,6)
DIR_L | (4,4) | (4,3)
DIR_L | (4,5) | (4,4)
DIR_L | (4,6) | (4,5)
DIR_L | (5,4) | (5,3)
DIR_L | (5,5) | (5,4)
DIR_L | (5,6) | (5,5)
```

Train example 3: 62 rows, the first 30 shown
Drawn on a 14x18 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . 2 3 3 3 2 . . . . . .
. . . . . . . 3 4 4 4 3 . . . . . .
. . . . . . . 3 4 4 4 3 . . . . . .
. . . . . . . 2 3 3 3 2 . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
```
```
c0 | c1 | c2
DIR_T | (6,7) | (5,7)
DIR_T | (6,8) | (5,8)
DIR_T | (6,9) | (5,9)
DIR_T | (6,10) | (5,10)
DIR_T | (6,11) | (5,11)
DIR_T | (7,7) | (6,7)
DIR_T | (7,8) | (6,8)
DIR_T | (7,9) | (6,9)
DIR_T | (7,10) | (6,10)
DIR_T | (7,11) | (6,11)
DIR_T | (8,7) | (7,7)
DIR_T | (8,8) | (7,8)
DIR_T | (8,9) | (7,9)
DIR_T | (8,10) | (7,10)
DIR_T | (8,11) | (7,11)
DIR_B | (5,7) | (6,7)
DIR_B | (5,8) | (6,8)
DIR_B | (5,9) | (6,9)
DIR_B | (5,10) | (6,10)
DIR_B | (5,11) | (6,11)
DIR_B | (6,7) | (7,7)
DIR_B | (6,8) | (7,8)
DIR_B | (6,9) | (7,9)
DIR_B | (6,10) | (7,10)
DIR_B | (6,11) | (7,11)
DIR_B | (7,7) | (8,7)
DIR_B | (7,8) | (8,8)
DIR_B | (7,9) | (8,9)
DIR_B | (7,10) | (8,10)
DIR_B | (7,11) | (8,11)
```

```
RULE &r13 :0 * [L0] :1 * [L1] NOT &r14 :0 L0 END [&r15]
```

### &r15 (export table 11)

- columns: c0: Box, c1: Color
- depth 7, candidate keys none
- rows per train example: [2, 1, 3, 5]; test: 9

Train example 0: 2 rows
Drawn on a 9x12 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . 4 . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . 4 . . . .
. . . . . . . . . . . .
```
```
c0 | c1
(3,9) | 4
(7,7) | 4
```

Train example 1: 1 row
Drawn on a 10x12 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . 8 . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1
(8,3) | 8
```

Train example 2: 3 rows
Drawn on a 14x12 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . 2 . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . 2 .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. 2 . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1
(0,4) | 2
(6,10) | 2
(11,1) | 2
```

Train example 3: 5 rows
Drawn on a 14x18 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . . . . . . . . . . .
. . . . . . . . 4 . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . 4 . . . . . .
. . . . . . . . . . . . . . . 4 . .
. . 4 . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . 4 . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
```
```
c0 | c1
(1,8) | 4
(3,11) | 4
(4,15) | 4
(5,2) | 4
(11,13) | 4
```

```
RULE &r15 :0 * [L0] axis_elem :0 * [L1] END [&r16]
```

### &r16 (export table 12)

- columns: c0: Axis, c1: Box
- depth 8, candidate keys none
- rows per train example: [4, 2, 6, 10]; test: 18

Train example 0: 4 rows
Drawn on a 9x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . 2 . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . 2 . . . .
. . . . . . . . . . . .
```
```
c0 | c1
AXIS_V | (3,9)
AXIS_V | (7,7)
AXIS_H | (3,9)
AXIS_H | (7,7)
```

Train example 1: 2 rows
Drawn on a 10x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . 2 . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1
AXIS_V | (8,3)
AXIS_H | (8,3)
```

Train example 2: 6 rows
Drawn on a 14x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . 2 . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . 2 .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. 2 . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1
AXIS_V | (0,4)
AXIS_V | (6,10)
AXIS_V | (11,1)
AXIS_H | (0,4)
AXIS_H | (6,10)
AXIS_H | (11,1)
```

Train example 3: 10 rows
Drawn on a 14x18 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . . . . . . . .
. . . . . . . . 2 . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . 2 . . . . . .
. . . . . . . . . . . . . . . 2 . .
. . 2 . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . 2 . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
```
```
c0 | c1
AXIS_V | (1,8)
AXIS_V | (3,11)
AXIS_V | (4,15)
AXIS_V | (5,2)
AXIS_V | (11,13)
AXIS_H | (1,8)
AXIS_H | (3,11)
AXIS_H | (4,15)
AXIS_H | (5,2)
AXIS_H | (11,13)
```

```
INIT Ray [:0] OR &r15 :1 ^ [L0] OR &r14 :1 * [L1] ALSO = L1 L0 END ALSO &r16 :1 L0 :2 * [L2] axis4_of :0 * [L3] :1 L2 ALSO &r16 :1 L0 input :0 L1 END END [:1] &r15 :1 L0 OR &r14 :1 * [L4] ALSO = L4 L0 END END [:0] END [:1] L4 END [:2] &r16 :1 L0 input :0 * [L5] END [:0] END [:1] L5 END [:3] &r16 :1 L0 :2 * [L6] axis4_of :0 * [L7] :1 L6 END [:0] END [:1] L7 END [&r17] [&r18] [&r19] [&r20] [&r21]
```

### &r17 (export table 13)

- columns: c0: Box, c1: Box, c2: Dir8, c3: Number, c4: Box
- depth 10, candidate keys none
- rows per train example: [963, 495, 1787, 3689]; test: 14263

Train example 0: 963 rows, the first 30 shown
```
c0 | c1 | c2 | c3 | c4
(3,9) | (0,2) | DIR_T | - | -
(3,9) | (0,3) | DIR_T | - | -
(3,9) | (0,4) | DIR_T | - | -
(3,9) | (0,9) | DIR_T | - | -
(3,9) | (1,0) | DIR_L | - | -
(3,9) | (1,1) | DIR_L | - | -
(3,9) | (1,2) | DIR_T | - | -
(3,9) | (1,2) | DIR_B | - | -
(3,9) | (1,2) | DIR_L | - | -
(3,9) | (1,2) | DIR_R | - | -
(3,9) | (1,3) | DIR_T | - | -
(3,9) | (1,3) | DIR_B | - | -
(3,9) | (1,3) | DIR_L | - | -
(3,9) | (1,3) | DIR_R | - | -
(3,9) | (1,4) | DIR_T | - | -
(3,9) | (1,4) | DIR_B | - | -
(3,9) | (1,4) | DIR_L | - | -
(3,9) | (1,4) | DIR_R | - | -
(3,9) | (1,5) | DIR_R | - | -
(3,9) | (1,6) | DIR_R | - | -
(3,9) | (1,7) | DIR_R | - | -
(3,9) | (1,8) | DIR_R | - | -
(3,9) | (1,9) | DIR_T | - | -
(3,9) | (1,9) | DIR_R | - | -
(3,9) | (1,10) | DIR_R | - | -
(3,9) | (1,11) | DIR_R | - | -
(3,9) | (2,0) | DIR_L | - | -
(3,9) | (2,1) | DIR_L | - | -
(3,9) | (2,2) | DIR_T | - | -
(3,9) | (2,2) | DIR_B | - | -
```

Train example 1: 495 rows, the first 30 shown
```
c0 | c1 | c2 | c3 | c4
(8,3) | (0,3) | DIR_T | - | -
(8,3) | (0,4) | DIR_T | - | -
(8,3) | (0,5) | DIR_T | - | -
(8,3) | (1,3) | DIR_T | - | -
(8,3) | (1,4) | DIR_T | - | -
(8,3) | (1,5) | DIR_T | - | -
(8,3) | (2,0) | DIR_L | - | -
(8,3) | (2,1) | DIR_L | - | -
(8,3) | (2,2) | DIR_L | - | -
(8,3) | (2,3) | DIR_T | - | -
(8,3) | (2,3) | DIR_B | - | -
(8,3) | (2,3) | DIR_L | - | -
(8,3) | (2,3) | DIR_R | - | -
(8,3) | (2,4) | DIR_T | - | -
(8,3) | (2,4) | DIR_B | - | -
(8,3) | (2,4) | DIR_L | - | -
(8,3) | (2,4) | DIR_R | - | -
(8,3) | (2,5) | DIR_T | - | -
(8,3) | (2,5) | DIR_B | - | -
(8,3) | (2,5) | DIR_L | - | -
(8,3) | (2,5) | DIR_R | - | -
(8,3) | (2,6) | DIR_R | - | -
(8,3) | (2,7) | DIR_R | - | -
(8,3) | (2,8) | DIR_R | - | -
(8,3) | (2,9) | DIR_R | - | -
(8,3) | (2,10) | DIR_R | - | -
(8,3) | (2,11) | DIR_R | - | -
(8,3) | (3,0) | DIR_L | - | -
(8,3) | (3,1) | DIR_L | - | -
(8,3) | (3,2) | DIR_L | - | -
```

Train example 2: 1787 rows, the first 30 shown
```
c0 | c1 | c2 | c3 | c4
(0,4) | (0,0) | DIR_L | - | -
(0,4) | (0,1) | DIR_L | - | -
(0,4) | (0,2) | DIR_L | - | -
(0,4) | (0,3) | DIR_T | - | -
(0,4) | (0,3) | DIR_L | - | -
(0,4) | (0,4) | DIR_T | - | -
(0,4) | (0,4) | DIR_B | - | -
(0,4) | (0,4) | DIR_L | - | -
(0,4) | (0,4) | DIR_R | - | -
(0,4) | (0,5) | DIR_T | - | -
(0,4) | (0,5) | DIR_R | - | -
(0,4) | (0,6) | DIR_T | - | -
(0,4) | (0,6) | DIR_R | - | -
(0,4) | (0,7) | DIR_R | - | -
(0,4) | (0,8) | DIR_R | - | -
(0,4) | (0,9) | DIR_R | - | -
(0,4) | (0,10) | DIR_R | - | -
(0,4) | (0,11) | DIR_R | - | -
(0,4) | (1,3) | DIR_T | - | -
(0,4) | (1,4) | DIR_T | - | -
(0,4) | (1,4) | DIR_B | - | -
(0,4) | (1,5) | DIR_T | - | -
(0,4) | (1,6) | DIR_T | - | -
(0,4) | (2,3) | DIR_T | - | -
(0,4) | (2,4) | DIR_T | - | -
(0,4) | (2,4) | DIR_B | - | -
(0,4) | (2,5) | DIR_T | - | -
(0,4) | (2,6) | DIR_T | - | -
(0,4) | (3,3) | DIR_T | - | -
(0,4) | (3,4) | DIR_T | - | -
```

Train example 3: 3689 rows, the first 30 shown
```
c0 | c1 | c2 | c3 | c4
(1,8) | (0,7) | DIR_T | - | -
(1,8) | (0,8) | DIR_T | - | -
(1,8) | (0,9) | DIR_T | - | -
(1,8) | (0,10) | DIR_T | - | -
(1,8) | (0,11) | DIR_T | - | -
(1,8) | (1,0) | DIR_L | - | -
(1,8) | (1,1) | DIR_L | - | -
(1,8) | (1,2) | DIR_L | - | -
(1,8) | (1,3) | DIR_L | - | -
(1,8) | (1,4) | DIR_L | - | -
(1,8) | (1,5) | DIR_L | - | -
(1,8) | (1,6) | DIR_L | - | -
(1,8) | (1,7) | DIR_T | - | -
(1,8) | (1,7) | DIR_L | - | -
(1,8) | (1,8) | DIR_T | - | -
(1,8) | (1,8) | DIR_B | - | -
(1,8) | (1,8) | DIR_L | - | -
(1,8) | (1,8) | DIR_R | - | -
(1,8) | (1,9) | DIR_T | - | -
(1,8) | (1,9) | DIR_R | - | -
(1,8) | (1,10) | DIR_T | - | -
(1,8) | (1,10) | DIR_R | - | -
(1,8) | (1,11) | DIR_T | - | -
(1,8) | (1,11) | DIR_R | - | -
(1,8) | (1,12) | DIR_R | - | -
(1,8) | (1,13) | DIR_R | - | -
(1,8) | (1,14) | DIR_R | - | -
(1,8) | (1,15) | DIR_R | - | -
(1,8) | (1,16) | DIR_R | - | -
(1,8) | (1,17) | DIR_R | - | -
```

### &r18 (export table 14)

- columns: c0: Box, c1: Box, c2: Dir8, c3: Number, c4: Box
- depth 10, candidate keys none
- rows per train example: [104, 40, 204, 420]; test: 1764

Train example 0: 104 rows, the first 30 shown
Drawn on a 9x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . + . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . + . . . .
. . . . . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4
(3,9) | (0,2) | DIR_T | 1 | (1,2)
(3,9) | (0,2) | DIR_T | 2 | (2,2)
(3,9) | (0,2) | DIR_T | 3 | (3,2)
(3,9) | (0,2) | DIR_T | 4 | (4,2)
(3,9) | (0,3) | DIR_T | 1 | (1,3)
(3,9) | (0,3) | DIR_T | 2 | (2,3)
(3,9) | (0,3) | DIR_T | 3 | (3,3)
(3,9) | (0,3) | DIR_T | 4 | (4,3)
(3,9) | (0,4) | DIR_T | 1 | (1,4)
(3,9) | (0,4) | DIR_T | 2 | (2,4)
(3,9) | (0,4) | DIR_T | 3 | (3,4)
(3,9) | (0,4) | DIR_T | 4 | (4,4)
(3,9) | (0,9) | DIR_T | 3 | (3,9)
(3,9) | (1,0) | DIR_L | 2 | (1,2)
(3,9) | (1,0) | DIR_L | 3 | (1,3)
(3,9) | (1,0) | DIR_L | 4 | (1,4)
(3,9) | (1,11) | DIR_R | 7 | (1,4)
(3,9) | (1,11) | DIR_R | 8 | (1,3)
(3,9) | (1,11) | DIR_R | 9 | (1,2)
(3,9) | (2,0) | DIR_L | 2 | (2,2)
(3,9) | (2,0) | DIR_L | 3 | (2,3)
(3,9) | (2,0) | DIR_L | 4 | (2,4)
(3,9) | (2,11) | DIR_R | 7 | (2,4)
(3,9) | (2,11) | DIR_R | 8 | (2,3)
(3,9) | (2,11) | DIR_R | 9 | (2,2)
(3,9) | (3,0) | DIR_L | 2 | (3,2)
(3,9) | (3,0) | DIR_L | 3 | (3,3)
(3,9) | (3,0) | DIR_L | 4 | (3,4)
(3,9) | (3,0) | DIR_L | 9 | (3,9)
(3,9) | (3,11) | DIR_R | 2 | (3,9)
```

Train example 1: 40 rows, the first 30 shown
Drawn on a 10x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . + . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4
(8,3) | (0,3) | DIR_T | 2 | (2,3)
(8,3) | (0,3) | DIR_T | 3 | (3,3)
(8,3) | (0,3) | DIR_T | 4 | (4,3)
(8,3) | (0,3) | DIR_T | 8 | (8,3)
(8,3) | (0,4) | DIR_T | 2 | (2,4)
(8,3) | (0,4) | DIR_T | 3 | (3,4)
(8,3) | (0,4) | DIR_T | 4 | (4,4)
(8,3) | (0,5) | DIR_T | 2 | (2,5)
(8,3) | (0,5) | DIR_T | 3 | (3,5)
(8,3) | (0,5) | DIR_T | 4 | (4,5)
(8,3) | (2,0) | DIR_L | 3 | (2,3)
(8,3) | (2,0) | DIR_L | 4 | (2,4)
(8,3) | (2,0) | DIR_L | 5 | (2,5)
(8,3) | (2,11) | DIR_R | 6 | (2,5)
(8,3) | (2,11) | DIR_R | 7 | (2,4)
(8,3) | (2,11) | DIR_R | 8 | (2,3)
(8,3) | (3,0) | DIR_L | 3 | (3,3)
(8,3) | (3,0) | DIR_L | 4 | (3,4)
(8,3) | (3,0) | DIR_L | 5 | (3,5)
(8,3) | (3,11) | DIR_R | 6 | (3,5)
(8,3) | (3,11) | DIR_R | 7 | (3,4)
(8,3) | (3,11) | DIR_R | 8 | (3,3)
(8,3) | (4,0) | DIR_L | 3 | (4,3)
(8,3) | (4,0) | DIR_L | 4 | (4,4)
(8,3) | (4,0) | DIR_L | 5 | (4,5)
(8,3) | (4,11) | DIR_R | 6 | (4,5)
(8,3) | (4,11) | DIR_R | 7 | (4,4)
(8,3) | (4,11) | DIR_R | 8 | (4,3)
(8,3) | (8,0) | DIR_L | 3 | (8,3)
(8,3) | (8,11) | DIR_R | 8 | (8,3)
```

Train example 2: 204 rows, the first 30 shown
Drawn on a 14x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . + . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . + .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. + . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4
(0,4) | (0,0) | DIR_L | 4 | (0,4)
(0,4) | (0,3) | DIR_T | 4 | (4,3)
(0,4) | (0,3) | DIR_T | 5 | (5,3)
(0,4) | (0,3) | DIR_T | 6 | (6,3)
(0,4) | (0,3) | DIR_T | 7 | (7,3)
(0,4) | (0,4) | DIR_T | 0 | (0,4)
(0,4) | (0,4) | DIR_T | 4 | (4,4)
(0,4) | (0,4) | DIR_T | 5 | (5,4)
(0,4) | (0,4) | DIR_T | 6 | (6,4)
(0,4) | (0,4) | DIR_T | 7 | (7,4)
(0,4) | (0,5) | DIR_T | 4 | (4,5)
(0,4) | (0,5) | DIR_T | 5 | (5,5)
(0,4) | (0,5) | DIR_T | 6 | (6,5)
(0,4) | (0,5) | DIR_T | 7 | (7,5)
(0,4) | (0,6) | DIR_T | 4 | (4,6)
(0,4) | (0,6) | DIR_T | 5 | (5,6)
(0,4) | (0,6) | DIR_T | 6 | (6,6)
(0,4) | (0,6) | DIR_T | 7 | (7,6)
(0,4) | (0,11) | DIR_R | 7 | (0,4)
(0,4) | (4,0) | DIR_L | 3 | (4,3)
(0,4) | (4,0) | DIR_L | 4 | (4,4)
(0,4) | (4,0) | DIR_L | 5 | (4,5)
(0,4) | (4,0) | DIR_L | 6 | (4,6)
(0,4) | (4,11) | DIR_R | 5 | (4,6)
(0,4) | (4,11) | DIR_R | 6 | (4,5)
(0,4) | (4,11) | DIR_R | 7 | (4,4)
(0,4) | (4,11) | DIR_R | 8 | (4,3)
(0,4) | (5,0) | DIR_L | 3 | (5,3)
(0,4) | (5,0) | DIR_L | 4 | (5,4)
(0,4) | (5,0) | DIR_L | 5 | (5,5)
```

Train example 3: 420 rows, the first 30 shown
Drawn on a 14x18 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . . . . . . . .
. . . . . . . . + . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . + . . . . . .
. . . . . . . . . . . . . . . + . .
. . + . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . + . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4
(1,8) | (0,7) | DIR_T | 5 | (5,7)
(1,8) | (0,7) | DIR_T | 6 | (6,7)
(1,8) | (0,7) | DIR_T | 7 | (7,7)
(1,8) | (0,7) | DIR_T | 8 | (8,7)
(1,8) | (0,8) | DIR_T | 1 | (1,8)
(1,8) | (0,8) | DIR_T | 5 | (5,8)
(1,8) | (0,8) | DIR_T | 6 | (6,8)
(1,8) | (0,8) | DIR_T | 7 | (7,8)
(1,8) | (0,8) | DIR_T | 8 | (8,8)
(1,8) | (0,9) | DIR_T | 5 | (5,9)
(1,8) | (0,9) | DIR_T | 6 | (6,9)
(1,8) | (0,9) | DIR_T | 7 | (7,9)
(1,8) | (0,9) | DIR_T | 8 | (8,9)
(1,8) | (0,10) | DIR_T | 5 | (5,10)
(1,8) | (0,10) | DIR_T | 6 | (6,10)
(1,8) | (0,10) | DIR_T | 7 | (7,10)
(1,8) | (0,10) | DIR_T | 8 | (8,10)
(1,8) | (0,11) | DIR_T | 5 | (5,11)
(1,8) | (0,11) | DIR_T | 6 | (6,11)
(1,8) | (0,11) | DIR_T | 7 | (7,11)
(1,8) | (0,11) | DIR_T | 8 | (8,11)
(1,8) | (1,0) | DIR_L | 8 | (1,8)
(1,8) | (1,17) | DIR_R | 9 | (1,8)
(1,8) | (5,0) | DIR_L | 7 | (5,7)
(1,8) | (5,0) | DIR_L | 8 | (5,8)
(1,8) | (5,0) | DIR_L | 9 | (5,9)
(1,8) | (5,0) | DIR_L | 10 | (5,10)
(1,8) | (5,0) | DIR_L | 11 | (5,11)
(1,8) | (5,17) | DIR_R | 6 | (5,11)
(1,8) | (5,17) | DIR_R | 7 | (5,10)
```

### &r19 (export table 15)

- columns: c0: Box, c1: Box
- depth 9, candidate keys none
- rows per train example: [26, 10, 51, 105]; test: 441

Train example 0: 26 rows
Drawn on a 9x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . + . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . + . . . .
. . . . . . . . . . . .
```
```
c0 | c1
(3,9) | (1,2)
(3,9) | (1,3)
(3,9) | (1,4)
(3,9) | (2,2)
(3,9) | (2,3)
(3,9) | (2,4)
(3,9) | (3,2)
(3,9) | (3,3)
(3,9) | (3,4)
(3,9) | (3,9)
(3,9) | (4,2)
(3,9) | (4,3)
(3,9) | (4,4)
(7,7) | (1,2)
(7,7) | (1,3)
(7,7) | (1,4)
(7,7) | (2,2)
(7,7) | (2,3)
(7,7) | (2,4)
(7,7) | (3,2)
(7,7) | (3,3)
(7,7) | (3,4)
(7,7) | (4,2)
(7,7) | (4,3)
(7,7) | (4,4)
(7,7) | (7,7)
```

Train example 1: 10 rows
Drawn on a 10x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . + . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1
(8,3) | (2,3)
(8,3) | (2,4)
(8,3) | (2,5)
(8,3) | (3,3)
(8,3) | (3,4)
(8,3) | (3,5)
(8,3) | (4,3)
(8,3) | (4,4)
(8,3) | (4,5)
(8,3) | (8,3)
```

Train example 2: 51 rows, the first 30 shown
Drawn on a 14x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . + . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . + .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. + . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1
(0,4) | (0,4)
(0,4) | (4,3)
(0,4) | (4,4)
(0,4) | (4,5)
(0,4) | (4,6)
(0,4) | (5,3)
(0,4) | (5,4)
(0,4) | (5,5)
(0,4) | (5,6)
(0,4) | (6,3)
(0,4) | (6,4)
(0,4) | (6,5)
(0,4) | (6,6)
(0,4) | (7,3)
(0,4) | (7,4)
(0,4) | (7,5)
(0,4) | (7,6)
(6,10) | (4,3)
(6,10) | (4,4)
(6,10) | (4,5)
(6,10) | (4,6)
(6,10) | (5,3)
(6,10) | (5,4)
(6,10) | (5,5)
(6,10) | (5,6)
(6,10) | (6,3)
(6,10) | (6,4)
(6,10) | (6,5)
(6,10) | (6,6)
(6,10) | (6,10)
```

Train example 3: 105 rows, the first 30 shown
Drawn on a 14x18 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . . . . . . . .
. . . . . . . . + . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . + . . . . . .
. . . . . . . . . . . . . . . + . .
. . + . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . + . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
```
```
c0 | c1
(1,8) | (1,8)
(1,8) | (5,7)
(1,8) | (5,8)
(1,8) | (5,9)
(1,8) | (5,10)
(1,8) | (5,11)
(1,8) | (6,7)
(1,8) | (6,8)
(1,8) | (6,9)
(1,8) | (6,10)
(1,8) | (6,11)
(1,8) | (7,7)
(1,8) | (7,8)
(1,8) | (7,9)
(1,8) | (7,10)
(1,8) | (7,11)
(1,8) | (8,7)
(1,8) | (8,8)
(1,8) | (8,9)
(1,8) | (8,10)
(1,8) | (8,11)
(3,11) | (3,11)
(3,11) | (5,7)
(3,11) | (5,8)
(3,11) | (5,9)
(3,11) | (5,10)
(3,11) | (5,11)
(3,11) | (6,7)
(3,11) | (6,8)
(3,11) | (6,9)
```

### &r20 (export table 16)

- columns: c0: Box, c1: Box
- depth 9, candidate keys none
- rows per train example: [216, 120, 504, 1260]; test: 3591

Train example 0: 216 rows, the first 30 shown
Drawn on a 9x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . + . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . + . . . .
. . . . . . . . . . . .
```
```
c0 | c1
(3,9) | (0,0)
(3,9) | (0,1)
(3,9) | (0,2)
(3,9) | (0,3)
(3,9) | (0,4)
(3,9) | (0,5)
(3,9) | (0,6)
(3,9) | (0,7)
(3,9) | (0,8)
(3,9) | (0,9)
(3,9) | (0,10)
(3,9) | (0,11)
(3,9) | (1,0)
(3,9) | (1,1)
(3,9) | (1,2)
(3,9) | (1,3)
(3,9) | (1,4)
(3,9) | (1,5)
(3,9) | (1,6)
(3,9) | (1,7)
(3,9) | (1,8)
(3,9) | (1,9)
(3,9) | (1,10)
(3,9) | (1,11)
(3,9) | (2,0)
(3,9) | (2,1)
(3,9) | (2,2)
(3,9) | (2,3)
(3,9) | (2,4)
(3,9) | (2,5)
```

Train example 1: 120 rows, the first 30 shown
Drawn on a 10x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . + . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1
(8,3) | (0,0)
(8,3) | (0,1)
(8,3) | (0,2)
(8,3) | (0,3)
(8,3) | (0,4)
(8,3) | (0,5)
(8,3) | (0,6)
(8,3) | (0,7)
(8,3) | (0,8)
(8,3) | (0,9)
(8,3) | (0,10)
(8,3) | (0,11)
(8,3) | (1,0)
(8,3) | (1,1)
(8,3) | (1,2)
(8,3) | (1,3)
(8,3) | (1,4)
(8,3) | (1,5)
(8,3) | (1,6)
(8,3) | (1,7)
(8,3) | (1,8)
(8,3) | (1,9)
(8,3) | (1,10)
(8,3) | (1,11)
(8,3) | (2,0)
(8,3) | (2,1)
(8,3) | (2,2)
(8,3) | (2,3)
(8,3) | (2,4)
(8,3) | (2,5)
```

Train example 2: 504 rows, the first 30 shown
Drawn on a 14x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . + . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . + .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. + . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1
(0,4) | (0,0)
(0,4) | (0,1)
(0,4) | (0,2)
(0,4) | (0,3)
(0,4) | (0,4)
(0,4) | (0,5)
(0,4) | (0,6)
(0,4) | (0,7)
(0,4) | (0,8)
(0,4) | (0,9)
(0,4) | (0,10)
(0,4) | (0,11)
(0,4) | (1,0)
(0,4) | (1,1)
(0,4) | (1,2)
(0,4) | (1,3)
(0,4) | (1,4)
(0,4) | (1,5)
(0,4) | (1,6)
(0,4) | (1,7)
(0,4) | (1,8)
(0,4) | (1,9)
(0,4) | (1,10)
(0,4) | (1,11)
(0,4) | (2,0)
(0,4) | (2,1)
(0,4) | (2,2)
(0,4) | (2,3)
(0,4) | (2,4)
(0,4) | (2,5)
```

Train example 3: 1260 rows, the first 30 shown
Drawn on a 14x18 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . . . . . . . .
. . . . . . . . + . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . + . . . . . .
. . . . . . . . . . . . . . . + . .
. . + . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . + . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
```
```
c0 | c1
(1,8) | (0,0)
(1,8) | (0,1)
(1,8) | (0,2)
(1,8) | (0,3)
(1,8) | (0,4)
(1,8) | (0,5)
(1,8) | (0,6)
(1,8) | (0,7)
(1,8) | (0,8)
(1,8) | (0,9)
(1,8) | (0,10)
(1,8) | (0,11)
(1,8) | (0,12)
(1,8) | (0,13)
(1,8) | (0,14)
(1,8) | (0,15)
(1,8) | (0,16)
(1,8) | (0,17)
(1,8) | (1,0)
(1,8) | (1,1)
(1,8) | (1,2)
(1,8) | (1,3)
(1,8) | (1,4)
(1,8) | (1,5)
(1,8) | (1,6)
(1,8) | (1,7)
(1,8) | (1,8)
(1,8) | (1,9)
(1,8) | (1,10)
(1,8) | (1,11)
```

### &r21 (export table 17)

- columns: c0: Box, c1: Dir8
- depth 9, candidate keys none
- rows per train example: [8, 4, 12, 20]; test: 36

Train example 0: 8 rows
Drawn on a 9x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . 4 . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . 4 . . . .
. . . . . . . . . . . .
```
```
c0 | c1
(3,9) | DIR_T
(3,9) | DIR_B
(3,9) | DIR_L
(3,9) | DIR_R
(7,7) | DIR_T
(7,7) | DIR_B
(7,7) | DIR_L
(7,7) | DIR_R
```

Train example 1: 4 rows
Drawn on a 10x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . 4 . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1
(8,3) | DIR_T
(8,3) | DIR_B
(8,3) | DIR_L
(8,3) | DIR_R
```

Train example 2: 12 rows
Drawn on a 14x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . 4 . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . 4 .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. 4 . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1
(0,4) | DIR_T
(0,4) | DIR_B
(0,4) | DIR_L
(0,4) | DIR_R
(6,10) | DIR_T
(6,10) | DIR_B
(6,10) | DIR_L
(6,10) | DIR_R
(11,1) | DIR_T
(11,1) | DIR_B
(11,1) | DIR_L
(11,1) | DIR_R
```

Train example 3: 20 rows
Drawn on a 14x18 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . . . . . . . .
. . . . . . . . 4 . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . 4 . . . . . .
. . . . . . . . . . . . . . . 4 . .
. . 4 . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . 4 . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
```
```
c0 | c1
(1,8) | DIR_T
(1,8) | DIR_B
(1,8) | DIR_L
(1,8) | DIR_R
(3,11) | DIR_T
(3,11) | DIR_B
(3,11) | DIR_L
(3,11) | DIR_R
(4,15) | DIR_T
(4,15) | DIR_B
(4,15) | DIR_L
(4,15) | DIR_R
(5,2) | DIR_T
(5,2) | DIR_B
(5,2) | DIR_L
(5,2) | DIR_R
(11,13) | DIR_T
(11,13) | DIR_B
(11,13) | DIR_L
(11,13) | DIR_R
```

```
RULE &r15 :0 * [L0] input :0 * [L1] NOT &r14 :0 L1 &r16 :0 L0 :1 * [L2] axis4_of :0 * [L3] :1 L2 dir8_opposite :0 L3 :1 * [L4] &r17 :0 :0 L0 END :1 L1 :2 L3 &r17 :0 :0 L0 END :1 L1 :2 L4 END [&r22]
```

### &r22 (export table 18)

- columns: c0: Box, c1: Dir8, c2: Box, c3: Axis, c4: Dir8
- depth 11, candidate keys none
- rows per train example: [16, 10, 24, 36]; test: 72

Train example 0: 16 rows
Drawn on a 9x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . 2 2 2 2 4 . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . 4 . . . .
. . . . . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4
(3,5) | DIR_L | (3,9) | AXIS_H | DIR_R
(3,5) | DIR_R | (3,9) | AXIS_H | DIR_L
(3,6) | DIR_L | (3,9) | AXIS_H | DIR_R
(3,6) | DIR_R | (3,9) | AXIS_H | DIR_L
(3,7) | DIR_L | (3,9) | AXIS_H | DIR_R
(3,7) | DIR_R | (3,9) | AXIS_H | DIR_L
(3,8) | DIR_L | (3,9) | AXIS_H | DIR_R
(3,8) | DIR_R | (3,9) | AXIS_H | DIR_L
(3,9) | DIR_T | (3,9) | AXIS_V | DIR_B
(3,9) | DIR_B | (3,9) | AXIS_V | DIR_T
(3,9) | DIR_L | (3,9) | AXIS_H | DIR_R
(3,9) | DIR_R | (3,9) | AXIS_H | DIR_L
(7,7) | DIR_T | (7,7) | AXIS_V | DIR_B
(7,7) | DIR_B | (7,7) | AXIS_V | DIR_T
(7,7) | DIR_L | (7,7) | AXIS_H | DIR_R
(7,7) | DIR_R | (7,7) | AXIS_H | DIR_L
```

Train example 1: 10 rows
Drawn on a 10x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . 2 . . . . . . . .
. . . 2 . . . . . . . .
. . . 2 . . . . . . . .
. . . 4 . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4
(5,3) | DIR_T | (8,3) | AXIS_V | DIR_B
(5,3) | DIR_B | (8,3) | AXIS_V | DIR_T
(6,3) | DIR_T | (8,3) | AXIS_V | DIR_B
(6,3) | DIR_B | (8,3) | AXIS_V | DIR_T
(7,3) | DIR_T | (8,3) | AXIS_V | DIR_B
(7,3) | DIR_B | (8,3) | AXIS_V | DIR_T
(8,3) | DIR_T | (8,3) | AXIS_V | DIR_B
(8,3) | DIR_B | (8,3) | AXIS_V | DIR_T
(8,3) | DIR_L | (8,3) | AXIS_H | DIR_R
(8,3) | DIR_R | (8,3) | AXIS_H | DIR_L
```

Train example 2: 24 rows
Drawn on a 14x12 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . 4 . . . . . . .
. . . . 2 . . . . . . .
. . . . 2 . . . . . . .
. . . . 2 . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . 2 2 2 4 .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. 4 . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4
(0,4) | DIR_T | (0,4) | AXIS_V | DIR_B
(0,4) | DIR_B | (0,4) | AXIS_V | DIR_T
(0,4) | DIR_L | (0,4) | AXIS_H | DIR_R
(0,4) | DIR_R | (0,4) | AXIS_H | DIR_L
(1,4) | DIR_T | (0,4) | AXIS_V | DIR_B
(1,4) | DIR_B | (0,4) | AXIS_V | DIR_T
(2,4) | DIR_T | (0,4) | AXIS_V | DIR_B
(2,4) | DIR_B | (0,4) | AXIS_V | DIR_T
(3,4) | DIR_T | (0,4) | AXIS_V | DIR_B
(3,4) | DIR_B | (0,4) | AXIS_V | DIR_T
(6,7) | DIR_L | (6,10) | AXIS_H | DIR_R
(6,7) | DIR_R | (6,10) | AXIS_H | DIR_L
(6,8) | DIR_L | (6,10) | AXIS_H | DIR_R
(6,8) | DIR_R | (6,10) | AXIS_H | DIR_L
(6,9) | DIR_L | (6,10) | AXIS_H | DIR_R
(6,9) | DIR_R | (6,10) | AXIS_H | DIR_L
(6,10) | DIR_T | (6,10) | AXIS_V | DIR_B
(6,10) | DIR_B | (6,10) | AXIS_V | DIR_T
(6,10) | DIR_L | (6,10) | AXIS_H | DIR_R
(6,10) | DIR_R | (6,10) | AXIS_H | DIR_L
(11,1) | DIR_T | (11,1) | AXIS_V | DIR_B
(11,1) | DIR_B | (11,1) | AXIS_V | DIR_T
(11,1) | DIR_L | (11,1) | AXIS_H | DIR_R
(11,1) | DIR_R | (11,1) | AXIS_H | DIR_L
```

Train example 3: 36 rows, the first 30 shown
Drawn on a 14x18 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . . . . . . . . . . .
. . . . . . . . 4 . . . . . . . . .
. . . . . . . . 2 . . . . . . . . .
. . . . . . . . 2 . . 4 . . . . . .
. . . . . . . . 2 . . 2 . . . 4 . .
. . 4 2 2 2 2 . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . 4 . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4
(1,8) | DIR_T | (1,8) | AXIS_V | DIR_B
(1,8) | DIR_B | (1,8) | AXIS_V | DIR_T
(1,8) | DIR_L | (1,8) | AXIS_H | DIR_R
(1,8) | DIR_R | (1,8) | AXIS_H | DIR_L
(2,8) | DIR_T | (1,8) | AXIS_V | DIR_B
(2,8) | DIR_B | (1,8) | AXIS_V | DIR_T
(3,8) | DIR_T | (1,8) | AXIS_V | DIR_B
(3,8) | DIR_B | (1,8) | AXIS_V | DIR_T
(3,11) | DIR_T | (3,11) | AXIS_V | DIR_B
(3,11) | DIR_B | (3,11) | AXIS_V | DIR_T
(3,11) | DIR_L | (3,11) | AXIS_H | DIR_R
(3,11) | DIR_R | (3,11) | AXIS_H | DIR_L
(4,8) | DIR_T | (1,8) | AXIS_V | DIR_B
(4,8) | DIR_B | (1,8) | AXIS_V | DIR_T
(4,11) | DIR_T | (3,11) | AXIS_V | DIR_B
(4,11) | DIR_B | (3,11) | AXIS_V | DIR_T
(4,15) | DIR_T | (4,15) | AXIS_V | DIR_B
(4,15) | DIR_B | (4,15) | AXIS_V | DIR_T
(4,15) | DIR_L | (4,15) | AXIS_H | DIR_R
(4,15) | DIR_R | (4,15) | AXIS_H | DIR_L
(5,2) | DIR_T | (5,2) | AXIS_V | DIR_B
(5,2) | DIR_B | (5,2) | AXIS_V | DIR_T
(5,2) | DIR_L | (5,2) | AXIS_H | DIR_R
(5,2) | DIR_R | (5,2) | AXIS_H | DIR_L
(5,3) | DIR_L | (5,2) | AXIS_H | DIR_R
(5,3) | DIR_R | (5,2) | AXIS_H | DIR_L
(5,4) | DIR_L | (5,2) | AXIS_H | DIR_R
(5,4) | DIR_R | (5,2) | AXIS_H | DIR_L
(5,5) | DIR_L | (5,2) | AXIS_H | DIR_R
(5,5) | DIR_R | (5,2) | AXIS_H | DIR_L
```

```
RULE &r22 :0 * [L0] :1 * [L1] &r15 :0 L0 :1 * [L2] END [&r23]
```

### &r23 (export table 19)

- columns: c0: Box, c1: Color, c2: Box
- depth 12, candidate keys none
- rows per train example: [6, 4, 9, 13]; test: 27

Train example 0: 6 rows
Drawn on a 9x12 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . 4 4 4 4 4 . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . 4 . . . .
. . . . . . . . . . . .
```
```
c0 | c1 | c2
(3,5) | 4 | (3,9)
(3,6) | 4 | (3,9)
(3,7) | 4 | (3,9)
(3,8) | 4 | (3,9)
(3,9) | 4 | (3,9)
(7,7) | 4 | (7,7)
```

Train example 1: 4 rows
Drawn on a 10x12 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . 8 . . . . . . . .
. . . 8 . . . . . . . .
. . . 8 . . . . . . . .
. . . 8 . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1 | c2
(5,3) | 8 | (8,3)
(6,3) | 8 | (8,3)
(7,3) | 8 | (8,3)
(8,3) | 8 | (8,3)
```

Train example 2: 9 rows
Drawn on a 14x12 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . 2 . . . . . . .
. . . . 2 . . . . . . .
. . . . 2 . . . . . . .
. . . . 2 . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . 2 2 2 2 .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
. 2 . . . . . . . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
```
```
c0 | c1 | c2
(0,4) | 2 | (0,4)
(1,4) | 2 | (0,4)
(2,4) | 2 | (0,4)
(3,4) | 2 | (0,4)
(6,7) | 2 | (6,10)
(6,8) | 2 | (6,10)
(6,9) | 2 | (6,10)
(6,10) | 2 | (6,10)
(11,1) | 2 | (11,1)
```

Train example 3: 13 rows
Drawn on a 14x18 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . . . . . . . . . . .
. . . . . . . . 4 . . . . . . . . .
. . . . . . . . 4 . . . . . . . . .
. . . . . . . . 4 . . 4 . . . . . .
. . . . . . . . 4 . . 4 . . . 4 . .
. . 4 4 4 4 4 . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . 4 . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
```
```
c0 | c1 | c2
(1,8) | 4 | (1,8)
(2,8) | 4 | (1,8)
(3,8) | 4 | (1,8)
(3,11) | 4 | (3,11)
(4,8) | 4 | (1,8)
(4,11) | 4 | (3,11)
(4,15) | 4 | (4,15)
(5,2) | 4 | (5,2)
(5,3) | 4 | (5,2)
(5,4) | 4 | (5,2)
(5,5) | 4 | (5,2)
(5,6) | 4 | (5,2)
(11,13) | 4 | (11,13)
```

```
RULE OR &r23 :1 * [L0] :2 * [L1] ALSO input :0 L0 :1 L1 NOT &r23 :1 L0 END END [&r24]
```

### &r24 (export table 20)

- columns: c0: Box, c1: Color
- depth 13, candidate keys none
- rows per train example: [108, 120, 168, 252]; test: 399

Train example 0: 108 rows, the first 30 shown
Drawn on a 9x12 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
8 8 8 8 8 8 8 8 8 8 8 8
8 8 3 3 3 8 8 8 8 8 8 8
8 8 3 3 3 8 8 8 8 8 8 8
8 8 3 3 3 4 4 4 4 4 8 8
8 8 3 3 3 8 8 8 8 8 8 8
8 8 8 8 8 8 8 8 8 8 8 8
8 8 8 8 8 8 8 8 8 8 8 8
8 8 8 8 8 8 8 4 8 8 8 8
8 8 8 8 8 8 8 8 8 8 8 8
```
```
c0 | c1
(0,0) | 8
(0,1) | 8
(0,2) | 8
(0,3) | 8
(0,4) | 8
(0,5) | 8
(0,6) | 8
(0,7) | 8
(0,8) | 8
(0,9) | 8
(0,10) | 8
(0,11) | 8
(1,0) | 8
(1,1) | 8
(1,2) | 3
(1,3) | 3
(1,4) | 3
(1,5) | 8
(1,6) | 8
(1,7) | 8
(1,8) | 8
(1,9) | 8
(1,10) | 8
(1,11) | 8
(2,0) | 8
(2,1) | 8
(2,2) | 3
(2,3) | 3
(2,4) | 3
(2,5) | 8
```

Train example 1: 120 rows, the first 30 shown
Drawn on a 10x12 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 2 2 2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2 2 2 2
2 2 2 1 1 1 2 2 2 2 2 2
2 2 2 1 1 1 2 2 2 2 2 2
2 2 2 1 1 1 2 2 2 2 2 2
2 2 2 8 2 2 2 2 2 2 2 2
2 2 2 8 2 2 2 2 2 2 2 2
2 2 2 8 2 2 2 2 2 2 2 2
2 2 2 8 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2 2 2 2
```
```
c0 | c1
(0,0) | 2
(0,1) | 2
(0,2) | 2
(0,3) | 2
(0,4) | 2
(0,5) | 2
(0,6) | 2
(0,7) | 2
(0,8) | 2
(0,9) | 2
(0,10) | 2
(0,11) | 2
(1,0) | 2
(1,1) | 2
(1,2) | 2
(1,3) | 2
(1,4) | 2
(1,5) | 2
(1,6) | 2
(1,7) | 2
(1,8) | 2
(1,9) | 2
(1,10) | 2
(1,11) | 2
(2,0) | 2
(2,1) | 2
(2,2) | 2
(2,3) | 1
(2,4) | 1
(2,5) | 1
```

Train example 2: 168 rows, the first 30 shown
Drawn on a 14x12 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1 1 1 1 2 1 1 1 1 1 1 1
1 1 1 1 2 1 1 1 1 1 1 1
1 1 1 1 2 1 1 1 1 1 1 1
1 1 1 1 2 1 1 1 1 1 1 1
1 1 1 4 4 4 4 1 1 1 1 1
1 1 1 4 4 4 4 1 1 1 1 1
1 1 1 4 4 4 4 2 2 2 2 1
1 1 1 4 4 4 4 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1
1 2 1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1
```
```
c0 | c1
(0,0) | 1
(0,1) | 1
(0,2) | 1
(0,3) | 1
(0,4) | 2
(0,5) | 1
(0,6) | 1
(0,7) | 1
(0,8) | 1
(0,9) | 1
(0,10) | 1
(0,11) | 1
(1,0) | 1
(1,1) | 1
(1,2) | 1
(1,3) | 1
(1,4) | 2
(1,5) | 1
(1,6) | 1
(1,7) | 1
(1,8) | 1
(1,9) | 1
(1,10) | 1
(1,11) | 1
(2,0) | 1
(2,1) | 1
(2,2) | 1
(2,3) | 1
(2,4) | 2
(2,5) | 1
```

Train example 3: 252 rows, the first 30 shown
Drawn on a 14x18 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 4 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 4 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 4 1 1 4 1 1 1 1 1 1
1 1 1 1 1 1 1 1 4 1 1 4 1 1 1 4 1 1
1 1 4 4 4 4 4 5 5 5 5 5 1 1 1 1 1 1
1 1 1 1 1 1 1 5 5 5 5 5 1 1 1 1 1 1
1 1 1 1 1 1 1 5 5 5 5 5 1 1 1 1 1 1
1 1 1 1 1 1 1 5 5 5 5 5 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1 1 4 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
```
```
c0 | c1
(0,0) | 1
(0,1) | 1
(0,2) | 1
(0,3) | 1
(0,4) | 1
(0,5) | 1
(0,6) | 1
(0,7) | 1
(0,8) | 1
(0,9) | 1
(0,10) | 1
(0,11) | 1
(0,12) | 1
(0,13) | 1
(0,14) | 1
(0,15) | 1
(0,16) | 1
(0,17) | 1
(1,0) | 1
(1,1) | 1
(1,2) | 1
(1,3) | 1
(1,4) | 1
(1,5) | 1
(1,6) | 1
(1,7) | 1
(1,8) | 4
(1,9) | 1
(1,10) | 1
(1,11) | 1
```

## What I see

The task: a solid block sits on the background, and lone marker cells lie around it. A marker whose row or column crosses the block fills the cells between it and the block with its color; a marker on neither line stays alone. The case has no DET and reads no table from the outputs: every table is a RULE or an instance output over the inputs. Every table has one assignment.

- **&r0** (Cardinality of each input color): 3 rows per example, `3 | 12`, `4 | 2`, `8 | 94` in e0.
- **&r3 to &r8** (Order over &r0's counts): ranks up and down (&r3, &r4), the least-counted color (&r5: 4, 8, 2, 4) and the most-counted (&r6: 8, 2, 1, 1, the background), successor pairs (&r7) and the same with the wrap pair (&r8). Each is a function of &r0. &r6 is the one the next clause reads. &r5 is the marker color in all four train examples. That is signal about the task, but no clause reads it; the program finds the markers by shape (&r15). &r1, &r2 and &r9 to &r12 have no table in the export.
- **&r13** (input cells not of &r6's color): the block and the markers, 14/10/19/25 rows. A selection, and the drawing is the whole object layout.
- **&r14** (pairs of ink cells that are neighbors): 34/24/48/62 rows, `neighbor` restricted to &r13's cells. The drawing by c1 shows the count of ink neighbors: 4 inside the block, 3 on its edges, 2 at its corners, and no row at a marker. A lib relation per pair, but the counts make the block's shape plain, and the markers are where the drawing is empty.
- **&r15** (ink cells with no ink neighbor): the markers, 2/1/3/5 rows. &r14 is read under NOT. The table's signal is what &r13 holds and &r14 lacks.
- **&r16**: &r15 x the two axes, 2 at each marker. A product.
- **&r17 to &r21** (Ray from each marker along the four directions, stopped at the block): **&r17** has 963 to 3689 rows (14263 at the test), and its Number and Box columns are `-` in the rows shown, which the README does not explain. **&r18** (104 to 420 rows) holds the steps, but its drawing is by c0, the marker, so it shows `+` at each marker and nothing of the rays. The same holds for **&r19** (the stops: each marker with all of the block's cells and itself, 13 per marker in e0, a product) and **&r20** (each marker with every cell of the grid, 108 per marker in e0, the Ray.node idiom). **&r21** is &r15 x the four directions. These tables hold most of the case's rows, and none of the signal shows in their drawings.
- **&r22** (cells between a marker and the block, reached from both sides): 16/10/24/36 rows. The drawing shows 2 on each span cell and 4 at each marker. A marker on no line of the block, such as (7,7) in e0 and (11,1) in e2, has only its own 4 rows. Here the signal about the rule jumps: the spans in the drawing are the cells the outputs add.
- **&r23** (the span cells with the marker's color): 6/4/9/13 rows. The drawings are the outputs' new cells plus the markers: in e0, 4 at (3,5) to (3,9), and the lone (7,7).
- **&r24** (out): &r23 over the input, equal to the outputs.

Rows that look like noise: &r17 to &r20, which are nearly all of the case's rows and whose drawings show only the markers; &r3, &r4, &r7, &r8 (Order outputs nothing reads); the products &r16 and &r21; and in &r22, the 4 rows of each marker that crosses no line of the block.
