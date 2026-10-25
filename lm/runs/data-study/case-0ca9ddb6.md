# 0ca9ddb6, case `$Ray`

- concept case: True; tokens: 894; tables: 42 relations, 42 per assignment
- cells: a Position is `(row,col)` of the example's input grid (`(row,col)out` where it fits only the output grid), an Offset `+(drow,dcol)`, another Box `rR0-R1 cC0-C1` over the input grid or `[t b l r]` margins; an Ident is `id<n>`, equal only within one case; see README.md

## Grids

### Train example 0: input 9x9, output 9x9

```
input                output
0 0 0 0 0 0 0 0 0    0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0    0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0    0 4 0 4 0 0 0 0 0
0 0 2 0 0 0 0 0 0    0 0 2 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0    0 4 0 4 0 0 0 0 0
0 0 0 0 0 0 0 0 0    0 0 0 0 0 0 7 0 0
0 0 0 0 0 0 1 0 0    0 0 0 0 0 7 1 7 0
0 0 0 0 0 0 0 0 0    0 0 0 0 0 0 7 0 0
0 0 0 0 0 0 0 0 0    0 0 0 0 0 0 0 0 0
```

### Train example 1: input 9x9, output 9x9

```
input                output
0 0 0 8 0 0 0 0 0    0 0 0 8 0 0 0 0 0
0 0 0 0 0 0 0 0 0    0 0 0 0 0 4 0 4 0
0 0 0 0 0 0 2 0 0    0 0 7 0 0 0 2 0 0
0 0 1 0 0 0 0 0 0    0 7 1 7 0 4 0 4 0
0 0 0 0 0 0 0 0 0    0 0 7 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0    0 0 0 0 0 0 7 0 0
0 0 0 0 0 0 1 0 0    4 0 4 0 0 7 1 7 0
0 2 0 0 0 0 0 0 0    0 2 0 0 0 0 7 0 0
0 0 0 0 0 0 0 0 0    4 0 4 0 0 0 0 0 0
```

### Train example 2: input 9x9, output 9x9

```
input                output
0 0 0 0 0 0 0 0 0    0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0    0 4 0 4 0 0 0 0 0
0 0 2 0 0 0 0 0 0    0 0 2 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0    0 4 0 4 0 0 0 0 0
0 0 0 0 0 0 0 0 0    0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 6 0 0    0 0 0 0 0 0 6 0 0
0 0 0 0 0 0 0 0 0    0 0 0 7 0 0 0 0 0
0 0 0 1 0 0 0 0 0    0 0 7 1 7 0 0 0 0
0 0 0 0 0 0 0 0 0    0 0 0 7 0 0 0 0 0
```

### Test example 0: input 9x9

```
0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 1 0 0
0 0 2 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0
0 0 0 0 0 8 0 0 0
0 0 0 0 0 0 0 0 0
0 6 0 0 0 0 0 2 0
0 0 0 0 0 0 0 0 0
```

## Program and tables

Model-written tokens plain, engine-written ones in [brackets]. Each clause is followed by the tables of the relations it declares. A table whose entries hold several DET assignments is given once per assignment, each marked with the values, at that assignment, of the DETs whose value differs between them; a DET's value is the rows of its own table at that assignment.

```
INIT Cardinality [:0] ex_input :0 * [L0] :1 * [L1] :2 ^ [L2] END [:1] ex_input :0 * [L3] :1 * [L4] :2 L2 END [:0] END [:1] :0 L3 :1 L4 END END [:2] SKIP [:2] SKIP [&r0] [&r1] [&r2]
```

### &r0 (export table 2)

- columns: c0: Color, c1: Number
- depth 2, candidate keys none
- rows per train example: [0, 0, 0]; test: 0; task-wide: 5
- every row is of a task-wide entry

Task-wide: 5 rows
```
c0 | c1
0 | 309
1 | 5
2 | 6
6 | 2
8 | 2
```

```
DET DivisorRatio END [&r3]
```

### &r3 (export table 3)

- columns: K: Number
- depth 1, candidate keys none
- DETs its entries are assigned: &r3; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
K
1
```

```
INIT Order [:0] SKIP [:1] &r0 :0 :0 * [L0] END END [:0] END [:1] L0 END [:2] SKIP [:3] &r0 :0 :0 * [L1] END :1 * [L2] END [:0] END [:1] L1 END [:2] L2 END [:4] SKIP [&r4] [&r5] [&r6] [&r7] [&r8] [&r9] [&r10] [&r11] [&r12] [&r13]
```

### &r4 (export table 4)

- columns: c0: Color, c1: Number
- depth 4, candidate keys none
- rows per train example: [0, 0, 0]; test: 0; task-wide: 5
- every row is of a task-wide entry

Task-wide: 5 rows
```
c0 | c1
0 | 4
1 | 2
2 | 3
6 | 0
8 | 0
```

### &r5 (export table 5)

- columns: c0: Color, c1: Number
- depth 4, candidate keys none
- rows per train example: [0, 0, 0]; test: 0; task-wide: 5
- every row is of a task-wide entry

Task-wide: 5 rows
```
c0 | c1
0 | 0
1 | 2
2 | 1
6 | 3
8 | 3
```

### &r6 (export table 6)

- columns: c0: Color
- depth 4, candidate keys none
- rows per train example: [0, 0, 0]; test: 0; task-wide: 2
- every row is of a task-wide entry

Task-wide: 2 rows
```
c0
6
8
```

### &r7 (export table 7)

- columns: c0: Color
- depth 4, candidate keys none
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
c0
0
```

### &r8 (export table 8)

- columns: c0: Color, c1: Color
- depth 4, candidate keys none
- rows per train example: [0, 0, 0]; test: 0; task-wide: 4
- every row is of a task-wide entry

Task-wide: 4 rows
```
c0 | c1
1 | 2
2 | 0
6 | 1
8 | 1
```

### &r9 (export table 9)

- columns: c0: Color, c1: Color
- depth 4, candidate keys none
- rows per train example: [0, 0, 0]; test: 0; task-wide: 6
- every row is of a task-wide entry

Task-wide: 6 rows
```
c0 | c1
0 | 6
0 | 8
1 | 2
2 | 0
6 | 1
8 | 1
```

```
DET ex_input :0 * [L0] :1 * [L1] :2 * [L2] NOT &r7 :1 L2 END [&r14]
```

### &r14 (export table 10)

- columns: c0: Example, c1: Box, c2: Color
- depth 5, candidate keys none
- DETs its entries are assigned: &r14; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 15
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 2 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . 2 . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . 1 . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2
e0 | (3,2) | 2
e0 | (6,6) | 1
```

Task-wide, rows whose Example column is e1: 5 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . 8 . . . . .
. . . . . . . . .
. . . . . . 2 . .
. . 1 . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . 1 . .
. 2 . . . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2
e1 | (0,3) | 8
e1 | (2,6) | 2
e1 | (3,2) | 1
e1 | (6,6) | 1
e1 | (7,1) | 2
```

Task-wide, rows whose Example column is e2: 3 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . 2 . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . 6 . .
. . . . . . . . .
. . . 1 . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2
e2 | (2,2) | 2
e2 | (5,6) | 6
e2 | (7,3) | 1
```

Task-wide, rows whose Example column is e3: 5 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . 1 . .
. . 2 . . . . . .
. . . . . . . . .
. . . . . 8 . . .
. . . . . . . . .
. 6 . . . . . 2 .
. . . . . . . . .
```
```
c0 | c1 | c2
e3 | (2,6) | 1
e3 | (3,2) | 2
e3 | (5,5) | 8
e3 | (7,1) | 6
e3 | (7,7) | 2
```

```
DET ex_output :0 * [L0] :1 * [L1] :2 * [L2] ex_input :0 L0 :1 L1 :2 * [L3] != L3 L2 END [&r15]
```

### &r15 (export table 11)

- columns: c0: Example, c1: Box, c2: Color, c3: Color
- depth 1, candidate keys none
- DETs its entries are assigned: &r15; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 32
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 8 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. 1 . 1 . . . . .
. . . . . . . . .
. 1 . 1 . . . . .
. . . . . . 1 . .
. . . . . 1 . 1 .
. . . . . . 1 . .
. . . . . . . . .
```
```
c0 | c1 | c2 | c3
e0 | (2,1) | 0 | 4
e0 | (2,3) | 0 | 4
e0 | (4,1) | 0 | 4
e0 | (4,3) | 0 | 4
e0 | (5,6) | 0 | 7
e0 | (6,5) | 0 | 7
e0 | (6,7) | 0 | 7
e0 | (7,6) | 0 | 7
```

Task-wide, rows whose Example column is e1: 16 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . .
. . . . . 1 . 1 .
. . 1 . . . . . .
. 1 . 1 . 1 . 1 .
. . 1 . . . . . .
. . . . . . 1 . .
1 . 1 . . 1 . 1 .
. . . . . . 1 . .
1 . 1 . . . . . .
```
```
c0 | c1 | c2 | c3
e1 | (1,5) | 0 | 4
e1 | (1,7) | 0 | 4
e1 | (2,2) | 0 | 7
e1 | (3,1) | 0 | 7
e1 | (3,3) | 0 | 7
e1 | (3,5) | 0 | 4
e1 | (3,7) | 0 | 4
e1 | (4,2) | 0 | 7
e1 | (5,6) | 0 | 7
e1 | (6,0) | 0 | 4
e1 | (6,2) | 0 | 4
e1 | (6,5) | 0 | 7
e1 | (6,7) | 0 | 7
e1 | (7,6) | 0 | 7
e1 | (8,0) | 0 | 4
e1 | (8,2) | 0 | 4
```

Task-wide, rows whose Example column is e2: 8 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . .
. 1 . 1 . . . . .
. . . . . . . . .
. 1 . 1 . . . . .
. . . . . . . . .
. . . . . . . . .
. . . 1 . . . . .
. . 1 . 1 . . . .
. . . 1 . . . . .
```
```
c0 | c1 | c2 | c3
e2 | (1,1) | 0 | 4
e2 | (1,3) | 0 | 4
e2 | (3,1) | 0 | 4
e2 | (3,3) | 0 | 4
e2 | (6,3) | 0 | 7
e2 | (7,2) | 0 | 7
e2 | (7,4) | 0 | 7
e2 | (8,3) | 0 | 7
```

```
INIT Connectivity [:0] OR &r15 :0 ^ [L0] :1 * [L1] ALSO &r14 :0 L0 :1 L1 END END [:1] OR &r15 :0 L0 :1 * [L2] ALSO &r14 :0 L0 :1 L2 END END [:0] END [:1] L2 END [:2] SKIP [:2] OR diag_dir_elem :0 * [L3] step_offset :0 L3 :1 * [L4] ALSO dir_elem :0 * [L5] step_offset :0 L5 :1 L4 END END [:0] L4 END [&r16] [&r17] [&r18] [&r19]
```

### &r16 (export table 12)

- columns: c0: Example, c1: Box, c2: Ident
- depth 7, candidate keys none
- DETs its entries are assigned: &r14, &r15; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 47
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 10 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. a . a . . . . .
. . a . . . . . .
. a . a . . . . .
. . . . . . b . .
. . . . . b b b .
. . . . . . b . .
. . . . . . . . .
```
```
c0 | c1 | c2
e0 | (2,1) | id1
e0 | (2,3) | id1
e0 | (3,2) | id1
e0 | (4,1) | id1
e0 | (4,3) | id1
e0 | (5,6) | id0
e0 | (6,5) | id0
e0 | (6,6) | id0
e0 | (6,7) | id0
e0 | (7,6) | id0
```

Task-wide, rows whose Example column is e1: 21 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . a . . . . .
. . . . . b . b .
. . c . . . b . .
. c c c . b . b .
. . c . . . . . .
. . . . . . d . .
e . e . . d d d .
. e . . . . d . .
e . e . . . . . .
```
```
c0 | c1 | c2
e1 | (0,3) | id3
e1 | (1,5) | id5
e1 | (1,7) | id5
e1 | (2,2) | id4
e1 | (2,6) | id5
e1 | (3,1) | id4
e1 | (3,2) | id4
e1 | (3,3) | id4
e1 | (3,5) | id5
e1 | (3,7) | id5
e1 | (4,2) | id4
e1 | (5,6) | id0
e1 | (6,0) | id2
e1 | (6,2) | id2
e1 | (6,5) | id0
e1 | (6,6) | id0
e1 | (6,7) | id0
e1 | (7,1) | id2
e1 | (7,6) | id0
e1 | (8,0) | id2
e1 | (8,2) | id2
```

Task-wide, rows whose Example column is e2: 11 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. a . a . . . . .
. . a . . . . . .
. a . a . . . . .
. . . . . . . . .
. . . . . . b . .
. . . c . . . . .
. . c c c . . . .
. . . c . . . . .
```
```
c0 | c1 | c2
e2 | (1,1) | id7
e2 | (1,3) | id7
e2 | (2,2) | id7
e2 | (3,1) | id7
e2 | (3,3) | id7
e2 | (5,6) | id6
e2 | (6,3) | id8
e2 | (7,2) | id8
e2 | (7,3) | id8
e2 | (7,4) | id8
e2 | (8,3) | id8
```

Task-wide, rows whose Example column is e3: 5 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . a . .
. . b . . . . . .
. . . . . . . . .
. . . . . c . . .
. . . . . . . . .
. d . . . . . e .
. . . . . . . . .
```
```
c0 | c1 | c2
e3 | (2,6) | id10
e3 | (3,2) | id11
e3 | (5,5) | id9
e3 | (7,1) | id13
e3 | (7,7) | id12
```

### &r18 (export table 13)

- columns: c0: Example, c1: Box
- depth 6, candidate keys none
- DETs its entries are assigned: &r14, &r15; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 47
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 10 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. 1 . 1 . . . . .
. . 1 . . . . . .
. 1 . 1 . . . . .
. . . . . . 1 . .
. . . . . 1 1 1 .
. . . . . . 1 . .
. . . . . . . . .
```
```
c0 | c1
e0 | (2,1)
e0 | (2,3)
e0 | (3,2)
e0 | (4,1)
e0 | (4,3)
e0 | (5,6)
e0 | (6,5)
e0 | (6,6)
e0 | (6,7)
e0 | (7,6)
```

Task-wide, rows whose Example column is e1: 21 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . 1 . . . . .
. . . . . 1 . 1 .
. . 1 . . . 1 . .
. 1 1 1 . 1 . 1 .
. . 1 . . . . . .
. . . . . . 1 . .
1 . 1 . . 1 1 1 .
. 1 . . . . 1 . .
1 . 1 . . . . . .
```
```
c0 | c1
e1 | (0,3)
e1 | (1,5)
e1 | (1,7)
e1 | (2,2)
e1 | (2,6)
e1 | (3,1)
e1 | (3,2)
e1 | (3,3)
e1 | (3,5)
e1 | (3,7)
e1 | (4,2)
e1 | (5,6)
e1 | (6,0)
e1 | (6,2)
e1 | (6,5)
e1 | (6,6)
e1 | (6,7)
e1 | (7,1)
e1 | (7,6)
e1 | (8,0)
e1 | (8,2)
```

Task-wide, rows whose Example column is e2: 11 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . .
. 1 . 1 . . . . .
. . 1 . . . . . .
. 1 . 1 . . . . .
. . . . . . . . .
. . . . . . 1 . .
. . . 1 . . . . .
. . 1 1 1 . . . .
. . . 1 . . . . .
```
```
c0 | c1
e2 | (1,1)
e2 | (1,3)
e2 | (2,2)
e2 | (3,1)
e2 | (3,3)
e2 | (5,6)
e2 | (6,3)
e2 | (7,2)
e2 | (7,3)
e2 | (7,4)
e2 | (8,3)
```

Task-wide, rows whose Example column is e3: 5 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . 1 . .
. . 1 . . . . . .
. . . . . . . . .
. . . . . 1 . . .
. . . . . . . . .
. 1 . . . . . 1 .
. . . . . . . . .
```
```
c0 | c1
e3 | (2,6)
e3 | (3,2)
e3 | (5,5)
e3 | (7,1)
e3 | (7,7)
```

### &r19 (export table 14)

- columns: c0: Box
- depth 6, candidate keys none
- DETs its entries are assigned: &r14, &r15; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 8
- every row is of a task-wide entry

Task-wide: 8 rows
```
c0
+(-1,-1)
+(-1,0)
+(-1,1)
+(0,-1)
+(0,1)
+(1,-1)
+(1,0)
+(1,1)
```

```
DET &r14 :0 * [L0] :1 * [L1] &r16 :0 :0 L0 END :1 L1 :2 * [L2] END [&r20]
```

### &r20 (export table 15)

- columns: c0: Example, c1: Box, c2: Ident
- depth 8, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r20; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 15
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 2 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . a . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . b . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2
e0 | (3,2) | id1
e0 | (6,6) | id0
```

Task-wide, rows whose Example column is e1: 5 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . a . . . . .
. . . . . . . . .
. . . . . . b . .
. . c . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . d . .
. e . . . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2
e1 | (0,3) | id3
e1 | (2,6) | id5
e1 | (3,2) | id4
e1 | (6,6) | id0
e1 | (7,1) | id2
```

Task-wide, rows whose Example column is e2: 3 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . a . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . b . .
. . . . . . . . .
. . . c . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2
e2 | (2,2) | id7
e2 | (5,6) | id6
e2 | (7,3) | id8
```

Task-wide, rows whose Example column is e3: 5 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . a . .
. . b . . . . . .
. . . . . . . . .
. . . . . c . . .
. . . . . . . . .
. d . . . . . e .
. . . . . . . . .
```
```
c0 | c1 | c2
e3 | (2,6) | id10
e3 | (3,2) | id11
e3 | (5,5) | id9
e3 | (7,1) | id13
e3 | (7,7) | id12
```

```
DET &r20 :0 * [L0] :2 * [L1] dir_elem :0 * [L2] END [&r21]
```

### &r21 (export table 16)

- columns: c0: Dir, c1: Example, c2: Ident
- depth 9, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r20, &r21; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 60
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 8 rows
```
c0 | c1 | c2
DIR_T | e0 | id0
DIR_T | e0 | id1
DIR_B | e0 | id0
DIR_B | e0 | id1
DIR_L | e0 | id0
DIR_L | e0 | id1
DIR_R | e0 | id0
DIR_R | e0 | id1
```

Task-wide, rows whose Example column is e1: 20 rows
```
c0 | c1 | c2
DIR_T | e1 | id0
DIR_T | e1 | id2
DIR_T | e1 | id3
DIR_T | e1 | id4
DIR_T | e1 | id5
DIR_B | e1 | id0
DIR_B | e1 | id2
DIR_B | e1 | id3
DIR_B | e1 | id4
DIR_B | e1 | id5
DIR_L | e1 | id0
DIR_L | e1 | id2
DIR_L | e1 | id3
DIR_L | e1 | id4
DIR_L | e1 | id5
DIR_R | e1 | id0
DIR_R | e1 | id2
DIR_R | e1 | id3
DIR_R | e1 | id4
DIR_R | e1 | id5
```

Task-wide, rows whose Example column is e2: 12 rows
```
c0 | c1 | c2
DIR_T | e2 | id6
DIR_T | e2 | id7
DIR_T | e2 | id8
DIR_B | e2 | id6
DIR_B | e2 | id7
DIR_B | e2 | id8
DIR_L | e2 | id6
DIR_L | e2 | id7
DIR_L | e2 | id8
DIR_R | e2 | id6
DIR_R | e2 | id7
DIR_R | e2 | id8
```

Task-wide, rows whose Example column is e3: 20 rows
```
c0 | c1 | c2
DIR_T | e3 | id9
DIR_T | e3 | id10
DIR_T | e3 | id11
DIR_T | e3 | id12
DIR_T | e3 | id13
DIR_B | e3 | id9
DIR_B | e3 | id10
DIR_B | e3 | id11
DIR_B | e3 | id12
DIR_B | e3 | id13
DIR_L | e3 | id9
DIR_L | e3 | id10
DIR_L | e3 | id11
DIR_L | e3 | id12
DIR_L | e3 | id13
DIR_R | e3 | id9
DIR_R | e3 | id10
DIR_R | e3 | id11
DIR_R | e3 | id12
DIR_R | e3 | id13
```

```
INIT Ray [:0] OR &r14 :0 ^ [L0] :1 * [L1] &r16 :0 :0 L0 END :1 L1 :2 ^ [L2] ALSO &r21 :0 L0 :1 L2 :2 * [L3] ALSO &r21 :0 L0 :1 L2 ex_input :0 L0 :1 L1 END END [:1] &r14 :0 L0 :1 * [L4] &r16 :0 :0 L0 END :1 L4 :2 L2 END [:0] END [:1] L4 END [:2] &r21 :0 L0 :1 L2 ex_input :0 L0 :1 * [L5] END [:0] END [:1] L5 END [:3] &r21 :0 L0 :1 L2 :2 * [L6] END [:0] END [:1] L6 END [&r22] [&r23] [&r24] [&r25] [&r26]
```

### &r22 (export table 17)

- columns: c0: Example, c1: Ident, c2: Box, c3: Dir8, c4: Number, c5: Box
- depth 11, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r20, &r21; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 300
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 40 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . 1 . . . 1 . .
. . 1 . . . 1 . .
. . 1 . . . 1 . .
1 1 4 1 1 1 2 1 1
. . 1 . . . 1 . .
. . 1 . . . 1 . .
1 1 2 1 1 1 4 1 1
. . 1 . . . 1 . .
. . 1 . . . 1 . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
e0 | id0 | (0,6) | DIR_T | 6 | (6,6)
e0 | id0 | (1,6) | DIR_T | 5 | (6,6)
e0 | id0 | (2,6) | DIR_T | 4 | (6,6)
e0 | id0 | (3,6) | DIR_T | 3 | (6,6)
e0 | id0 | (4,6) | DIR_T | 2 | (6,6)
e0 | id0 | (5,6) | DIR_T | 1 | (6,6)
e0 | id0 | (6,0) | DIR_L | 6 | (6,6)
e0 | id0 | (6,1) | DIR_L | 5 | (6,6)
e0 | id0 | (6,2) | DIR_L | 4 | (6,6)
e0 | id0 | (6,3) | DIR_L | 3 | (6,6)
e0 | id0 | (6,4) | DIR_L | 2 | (6,6)
e0 | id0 | (6,5) | DIR_L | 1 | (6,6)
e0 | id0 | (6,6) | DIR_T | 0 | (6,6)
e0 | id0 | (6,6) | DIR_B | 0 | (6,6)
e0 | id0 | (6,6) | DIR_L | 0 | (6,6)
e0 | id0 | (6,6) | DIR_R | 0 | (6,6)
e0 | id0 | (6,7) | DIR_R | 1 | (6,6)
e0 | id0 | (6,8) | DIR_R | 2 | (6,6)
e0 | id0 | (7,6) | DIR_B | 1 | (6,6)
e0 | id0 | (8,6) | DIR_B | 2 | (6,6)
e0 | id1 | (0,2) | DIR_T | 3 | (3,2)
e0 | id1 | (1,2) | DIR_T | 2 | (3,2)
e0 | id1 | (2,2) | DIR_T | 1 | (3,2)
e0 | id1 | (3,0) | DIR_L | 2 | (3,2)
e0 | id1 | (3,1) | DIR_L | 1 | (3,2)
e0 | id1 | (3,2) | DIR_T | 0 | (3,2)
e0 | id1 | (3,2) | DIR_B | 0 | (3,2)
e0 | id1 | (3,2) | DIR_L | 0 | (3,2)
e0 | id1 | (3,2) | DIR_R | 0 | (3,2)
e0 | id1 | (3,3) | DIR_R | 1 | (3,2)
```

Task-wide, rows whose Example column is e1: 100 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 2 2 4 1 1 3 1 1
. 1 1 1 . . 2 . .
1 2 2 2 1 1 5 1 1
1 2 4 2 1 1 3 1 1
. 1 1 1 . . 2 . .
. 1 1 1 . . 2 . .
1 2 2 2 1 1 5 1 1
1 4 2 2 1 1 3 1 1
. 1 1 1 . . 2 . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
e1 | id0 | (0,6) | DIR_T | 6 | (6,6)
e1 | id0 | (1,6) | DIR_T | 5 | (6,6)
e1 | id0 | (2,6) | DIR_T | 4 | (6,6)
e1 | id0 | (3,6) | DIR_T | 3 | (6,6)
e1 | id0 | (4,6) | DIR_T | 2 | (6,6)
e1 | id0 | (5,6) | DIR_T | 1 | (6,6)
e1 | id0 | (6,0) | DIR_L | 6 | (6,6)
e1 | id0 | (6,1) | DIR_L | 5 | (6,6)
e1 | id0 | (6,2) | DIR_L | 4 | (6,6)
e1 | id0 | (6,3) | DIR_L | 3 | (6,6)
e1 | id0 | (6,4) | DIR_L | 2 | (6,6)
e1 | id0 | (6,5) | DIR_L | 1 | (6,6)
e1 | id0 | (6,6) | DIR_T | 0 | (6,6)
e1 | id0 | (6,6) | DIR_B | 0 | (6,6)
e1 | id0 | (6,6) | DIR_L | 0 | (6,6)
e1 | id0 | (6,6) | DIR_R | 0 | (6,6)
e1 | id0 | (6,7) | DIR_R | 1 | (6,6)
e1 | id0 | (6,8) | DIR_R | 2 | (6,6)
e1 | id0 | (7,6) | DIR_B | 1 | (6,6)
e1 | id0 | (8,6) | DIR_B | 2 | (6,6)
e1 | id2 | (0,1) | DIR_T | 7 | (7,1)
e1 | id2 | (1,1) | DIR_T | 6 | (7,1)
e1 | id2 | (2,1) | DIR_T | 5 | (7,1)
e1 | id2 | (3,1) | DIR_T | 4 | (7,1)
e1 | id2 | (4,1) | DIR_T | 3 | (7,1)
e1 | id2 | (5,1) | DIR_T | 2 | (7,1)
e1 | id2 | (6,1) | DIR_T | 1 | (7,1)
e1 | id2 | (7,0) | DIR_L | 1 | (7,1)
e1 | id2 | (7,1) | DIR_T | 0 | (7,1)
e1 | id2 | (7,1) | DIR_B | 0 | (7,1)
```

Task-wide, rows whose Example column is e2: 60 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . 1 1 . . 1 . .
. . 1 1 . . 1 . .
1 1 4 2 1 1 2 1 1
. . 1 1 . . 1 . .
. . 1 1 . . 1 . .
1 1 2 2 1 1 4 1 1
. . 1 1 . . 1 . .
1 1 2 4 1 1 2 1 1
. . 1 1 . . 1 . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
e2 | id6 | (0,6) | DIR_T | 5 | (5,6)
e2 | id6 | (1,6) | DIR_T | 4 | (5,6)
e2 | id6 | (2,6) | DIR_T | 3 | (5,6)
e2 | id6 | (3,6) | DIR_T | 2 | (5,6)
e2 | id6 | (4,6) | DIR_T | 1 | (5,6)
e2 | id6 | (5,0) | DIR_L | 6 | (5,6)
e2 | id6 | (5,1) | DIR_L | 5 | (5,6)
e2 | id6 | (5,2) | DIR_L | 4 | (5,6)
e2 | id6 | (5,3) | DIR_L | 3 | (5,6)
e2 | id6 | (5,4) | DIR_L | 2 | (5,6)
e2 | id6 | (5,5) | DIR_L | 1 | (5,6)
e2 | id6 | (5,6) | DIR_T | 0 | (5,6)
e2 | id6 | (5,6) | DIR_B | 0 | (5,6)
e2 | id6 | (5,6) | DIR_L | 0 | (5,6)
e2 | id6 | (5,6) | DIR_R | 0 | (5,6)
e2 | id6 | (5,7) | DIR_R | 1 | (5,6)
e2 | id6 | (5,8) | DIR_R | 2 | (5,6)
e2 | id6 | (6,6) | DIR_B | 1 | (5,6)
e2 | id6 | (7,6) | DIR_B | 2 | (5,6)
e2 | id6 | (8,6) | DIR_B | 3 | (5,6)
e2 | id7 | (0,2) | DIR_T | 2 | (2,2)
e2 | id7 | (1,2) | DIR_T | 1 | (2,2)
e2 | id7 | (2,0) | DIR_L | 2 | (2,2)
e2 | id7 | (2,1) | DIR_L | 1 | (2,2)
e2 | id7 | (2,2) | DIR_T | 0 | (2,2)
e2 | id7 | (2,2) | DIR_B | 0 | (2,2)
e2 | id7 | (2,2) | DIR_L | 0 | (2,2)
e2 | id7 | (2,2) | DIR_R | 0 | (2,2)
e2 | id7 | (2,3) | DIR_R | 1 | (2,2)
e2 | id7 | (2,4) | DIR_R | 2 | (2,2)
```

Task-wide, rows whose Example column is e3: 100 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 1 . . 1 1 1 .
. 1 1 . . 1 1 1 .
1 2 2 1 1 2 4 2 1
1 2 4 1 1 2 2 2 1
. 1 1 . . 1 1 1 .
1 2 2 1 1 4 2 2 1
. 1 1 . . 1 1 1 .
2 5 3 2 2 3 3 5 2
. 1 1 . . 1 1 1 .
```
```
c0 | c1 | c2 | c3 | c4 | c5
e3 | id9 | (0,5) | DIR_T | 5 | (5,5)
e3 | id9 | (1,5) | DIR_T | 4 | (5,5)
e3 | id9 | (2,5) | DIR_T | 3 | (5,5)
e3 | id9 | (3,5) | DIR_T | 2 | (5,5)
e3 | id9 | (4,5) | DIR_T | 1 | (5,5)
e3 | id9 | (5,0) | DIR_L | 5 | (5,5)
e3 | id9 | (5,1) | DIR_L | 4 | (5,5)
e3 | id9 | (5,2) | DIR_L | 3 | (5,5)
e3 | id9 | (5,3) | DIR_L | 2 | (5,5)
e3 | id9 | (5,4) | DIR_L | 1 | (5,5)
e3 | id9 | (5,5) | DIR_T | 0 | (5,5)
e3 | id9 | (5,5) | DIR_B | 0 | (5,5)
e3 | id9 | (5,5) | DIR_L | 0 | (5,5)
e3 | id9 | (5,5) | DIR_R | 0 | (5,5)
e3 | id9 | (5,6) | DIR_R | 1 | (5,5)
e3 | id9 | (5,7) | DIR_R | 2 | (5,5)
e3 | id9 | (5,8) | DIR_R | 3 | (5,5)
e3 | id9 | (6,5) | DIR_B | 1 | (5,5)
e3 | id9 | (7,5) | DIR_B | 2 | (5,5)
e3 | id9 | (8,5) | DIR_B | 3 | (5,5)
e3 | id10 | (0,6) | DIR_T | 2 | (2,6)
e3 | id10 | (1,6) | DIR_T | 1 | (2,6)
e3 | id10 | (2,0) | DIR_L | 6 | (2,6)
e3 | id10 | (2,1) | DIR_L | 5 | (2,6)
e3 | id10 | (2,2) | DIR_L | 4 | (2,6)
e3 | id10 | (2,3) | DIR_L | 3 | (2,6)
e3 | id10 | (2,4) | DIR_L | 2 | (2,6)
e3 | id10 | (2,5) | DIR_L | 1 | (2,6)
e3 | id10 | (2,6) | DIR_T | 0 | (2,6)
e3 | id10 | (2,6) | DIR_B | 0 | (2,6)
```

### &r23 (export table 18)

- columns: c0: Example, c1: Ident, c2: Box, c3: Dir8, c4: Number, c5: Box
- depth 11, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r20, &r21; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 60
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 8 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . a . . . b . .
. . . . . . . . .
. . . . . . . . .
a . . . . . . . a
. . . . . . . . .
. . . . . . . . .
b . . . . . . . b
. . . . . . . . .
. . a . . . b . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
e0 | id0 | (0,6) | DIR_T | 6 | (6,6)
e0 | id0 | (6,0) | DIR_L | 6 | (6,6)
e0 | id0 | (6,8) | DIR_R | 2 | (6,6)
e0 | id0 | (8,6) | DIR_B | 2 | (6,6)
e0 | id1 | (0,2) | DIR_T | 3 | (3,2)
e0 | id1 | (3,0) | DIR_L | 2 | (3,2)
e0 | id1 | (3,8) | DIR_R | 6 | (3,2)
e0 | id1 | (8,2) | DIR_B | 5 | (3,2)
```

Task-wide, rows whose Example column is e1: 20 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 1 1 . . 2 . 1
. . . . . . . . .
1 . . . . . . . 1
1 . . . . . . . 1
. . . . . . . . .
. . . . . . . . .
1 . . . . . . . 1
1 . . . . . . . 1
. 1 1 1 . . 2 . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
e1 | id0 | (0,6) | DIR_T | 6 | (6,6)
e1 | id0 | (6,0) | DIR_L | 6 | (6,6)
e1 | id0 | (6,8) | DIR_R | 2 | (6,6)
e1 | id0 | (8,6) | DIR_B | 2 | (6,6)
e1 | id2 | (0,1) | DIR_T | 7 | (7,1)
e1 | id2 | (7,0) | DIR_L | 1 | (7,1)
e1 | id2 | (7,8) | DIR_R | 7 | (7,1)
e1 | id2 | (8,1) | DIR_B | 1 | (7,1)
e1 | id3 | (0,0) | DIR_L | 3 | (0,3)
e1 | id3 | (0,3) | DIR_T | 0 | (0,3)
e1 | id3 | (0,8) | DIR_R | 5 | (0,3)
e1 | id3 | (8,3) | DIR_B | 8 | (0,3)
e1 | id4 | (0,2) | DIR_T | 3 | (3,2)
e1 | id4 | (3,0) | DIR_L | 2 | (3,2)
e1 | id4 | (3,8) | DIR_R | 6 | (3,2)
e1 | id4 | (8,2) | DIR_B | 5 | (3,2)
e1 | id5 | (0,6) | DIR_T | 2 | (2,6)
e1 | id5 | (2,0) | DIR_L | 6 | (2,6)
e1 | id5 | (2,8) | DIR_R | 2 | (2,6)
e1 | id5 | (8,6) | DIR_B | 6 | (2,6)
```

Task-wide, rows whose Example column is e2: 12 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . a b . . c . .
. . . . . . . . .
a . . . . . . . a
. . . . . . . . .
. . . . . . . . .
c . . . . . . . c
. . . . . . . . .
b . . . . . . . b
. . a b . . c . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
e2 | id6 | (0,6) | DIR_T | 5 | (5,6)
e2 | id6 | (5,0) | DIR_L | 6 | (5,6)
e2 | id6 | (5,8) | DIR_R | 2 | (5,6)
e2 | id6 | (8,6) | DIR_B | 3 | (5,6)
e2 | id7 | (0,2) | DIR_T | 2 | (2,2)
e2 | id7 | (2,0) | DIR_L | 2 | (2,2)
e2 | id7 | (2,8) | DIR_R | 6 | (2,2)
e2 | id7 | (8,2) | DIR_B | 6 | (2,2)
e2 | id8 | (0,3) | DIR_T | 7 | (7,3)
e2 | id8 | (7,0) | DIR_L | 3 | (7,3)
e2 | id8 | (7,8) | DIR_R | 5 | (7,3)
e2 | id8 | (8,3) | DIR_B | 1 | (7,3)
```

Task-wide, rows whose Example column is e3: 20 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. 1 1 . . 1 1 1 .
. . . . . . . . .
1 . . . . . . . 1
1 . . . . . . . 1
. . . . . . . . .
1 . . . . . . . 1
. . . . . . . . .
2 . . . . . . . 2
. 1 1 . . 1 1 1 .
```
```
c0 | c1 | c2 | c3 | c4 | c5
e3 | id9 | (0,5) | DIR_T | 5 | (5,5)
e3 | id9 | (5,0) | DIR_L | 5 | (5,5)
e3 | id9 | (5,8) | DIR_R | 3 | (5,5)
e3 | id9 | (8,5) | DIR_B | 3 | (5,5)
e3 | id10 | (0,6) | DIR_T | 2 | (2,6)
e3 | id10 | (2,0) | DIR_L | 6 | (2,6)
e3 | id10 | (2,8) | DIR_R | 2 | (2,6)
e3 | id10 | (8,6) | DIR_B | 6 | (2,6)
e3 | id11 | (0,2) | DIR_T | 3 | (3,2)
e3 | id11 | (3,0) | DIR_L | 2 | (3,2)
e3 | id11 | (3,8) | DIR_R | 6 | (3,2)
e3 | id11 | (8,2) | DIR_B | 5 | (3,2)
e3 | id12 | (0,7) | DIR_T | 7 | (7,7)
e3 | id12 | (7,0) | DIR_L | 7 | (7,7)
e3 | id12 | (7,8) | DIR_R | 1 | (7,7)
e3 | id12 | (8,7) | DIR_B | 1 | (7,7)
e3 | id13 | (0,1) | DIR_T | 7 | (7,1)
e3 | id13 | (7,0) | DIR_L | 1 | (7,1)
e3 | id13 | (7,8) | DIR_R | 7 | (7,1)
e3 | id13 | (8,1) | DIR_B | 1 | (7,1)
```

### &r24 (export table 19)

- columns: c0: Example, c1: Ident, c2: Box
- depth 10, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r20, &r21; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 15
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 2 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . a . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . b . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2
e0 | id0 | (6,6)
e0 | id1 | (3,2)
```

Task-wide, rows whose Example column is e1: 5 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . a . . . . .
. . . . . . . . .
. . . . . . b . .
. . c . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . d . .
. e . . . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2
e1 | id0 | (6,6)
e1 | id2 | (7,1)
e1 | id3 | (0,3)
e1 | id4 | (3,2)
e1 | id5 | (2,6)
```

Task-wide, rows whose Example column is e2: 3 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . a . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . b . .
. . . . . . . . .
. . . c . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2
e2 | id6 | (5,6)
e2 | id7 | (2,2)
e2 | id8 | (7,3)
```

Task-wide, rows whose Example column is e3: 5 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . a . .
. . b . . . . . .
. . . . . . . . .
. . . . . c . . .
. . . . . . . . .
. d . . . . . e .
. . . . . . . . .
```
```
c0 | c1 | c2
e3 | id9 | (5,5)
e3 | id10 | (2,6)
e3 | id11 | (3,2)
e3 | id12 | (7,7)
e3 | id13 | (7,1)
```

### &r25 (export table 20)

- columns: c0: Example, c1: Ident, c2: Box
- depth 10, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r20, &r21; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1215
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 162 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
```
```
c0 | c1 | c2
e0 | id0 | (0,0)
e0 | id0 | (0,1)
e0 | id0 | (0,2)
e0 | id0 | (0,3)
e0 | id0 | (0,4)
e0 | id0 | (0,5)
e0 | id0 | (0,6)
e0 | id0 | (0,7)
e0 | id0 | (0,8)
e0 | id0 | (1,0)
e0 | id0 | (1,1)
e0 | id0 | (1,2)
e0 | id0 | (1,3)
e0 | id0 | (1,4)
e0 | id0 | (1,5)
e0 | id0 | (1,6)
e0 | id0 | (1,7)
e0 | id0 | (1,8)
e0 | id0 | (2,0)
e0 | id0 | (2,1)
e0 | id0 | (2,2)
e0 | id0 | (2,3)
e0 | id0 | (2,4)
e0 | id0 | (2,5)
e0 | id0 | (2,6)
e0 | id0 | (2,7)
e0 | id0 | (2,8)
e0 | id0 | (3,0)
e0 | id0 | (3,1)
e0 | id0 | (3,2)
```

Task-wide, rows whose Example column is e1: 405 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
```
```
c0 | c1 | c2
e1 | id0 | (0,0)
e1 | id0 | (0,1)
e1 | id0 | (0,2)
e1 | id0 | (0,3)
e1 | id0 | (0,4)
e1 | id0 | (0,5)
e1 | id0 | (0,6)
e1 | id0 | (0,7)
e1 | id0 | (0,8)
e1 | id0 | (1,0)
e1 | id0 | (1,1)
e1 | id0 | (1,2)
e1 | id0 | (1,3)
e1 | id0 | (1,4)
e1 | id0 | (1,5)
e1 | id0 | (1,6)
e1 | id0 | (1,7)
e1 | id0 | (1,8)
e1 | id0 | (2,0)
e1 | id0 | (2,1)
e1 | id0 | (2,2)
e1 | id0 | (2,3)
e1 | id0 | (2,4)
e1 | id0 | (2,5)
e1 | id0 | (2,6)
e1 | id0 | (2,7)
e1 | id0 | (2,8)
e1 | id0 | (3,0)
e1 | id0 | (3,1)
e1 | id0 | (3,2)
```

Task-wide, rows whose Example column is e2: 243 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
```
```
c0 | c1 | c2
e2 | id6 | (0,0)
e2 | id6 | (0,1)
e2 | id6 | (0,2)
e2 | id6 | (0,3)
e2 | id6 | (0,4)
e2 | id6 | (0,5)
e2 | id6 | (0,6)
e2 | id6 | (0,7)
e2 | id6 | (0,8)
e2 | id6 | (1,0)
e2 | id6 | (1,1)
e2 | id6 | (1,2)
e2 | id6 | (1,3)
e2 | id6 | (1,4)
e2 | id6 | (1,5)
e2 | id6 | (1,6)
e2 | id6 | (1,7)
e2 | id6 | (1,8)
e2 | id6 | (2,0)
e2 | id6 | (2,1)
e2 | id6 | (2,2)
e2 | id6 | (2,3)
e2 | id6 | (2,4)
e2 | id6 | (2,5)
e2 | id6 | (2,6)
e2 | id6 | (2,7)
e2 | id6 | (2,8)
e2 | id6 | (3,0)
e2 | id6 | (3,1)
e2 | id6 | (3,2)
```

Task-wide, rows whose Example column is e3: 405 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
```
```
c0 | c1 | c2
e3 | id9 | (0,0)
e3 | id9 | (0,1)
e3 | id9 | (0,2)
e3 | id9 | (0,3)
e3 | id9 | (0,4)
e3 | id9 | (0,5)
e3 | id9 | (0,6)
e3 | id9 | (0,7)
e3 | id9 | (0,8)
e3 | id9 | (1,0)
e3 | id9 | (1,1)
e3 | id9 | (1,2)
e3 | id9 | (1,3)
e3 | id9 | (1,4)
e3 | id9 | (1,5)
e3 | id9 | (1,6)
e3 | id9 | (1,7)
e3 | id9 | (1,8)
e3 | id9 | (2,0)
e3 | id9 | (2,1)
e3 | id9 | (2,2)
e3 | id9 | (2,3)
e3 | id9 | (2,4)
e3 | id9 | (2,5)
e3 | id9 | (2,6)
e3 | id9 | (2,7)
e3 | id9 | (2,8)
e3 | id9 | (3,0)
e3 | id9 | (3,1)
e3 | id9 | (3,2)
```

```
DET &r20 :0 * [L0] :2 * [L1] ex_input :0 L0 :1 * [L2] END [&r27]
```

### &r27 (export table 21)

- columns: c0: Example, c1: Box, c2: Ident
- depth 9, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r20, &r27; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1215
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 162 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
```
```
c0 | c1 | c2
e0 | (0,0) | id0
e0 | (0,0) | id1
e0 | (0,1) | id0
e0 | (0,1) | id1
e0 | (0,2) | id0
e0 | (0,2) | id1
e0 | (0,3) | id0
e0 | (0,3) | id1
e0 | (0,4) | id0
e0 | (0,4) | id1
e0 | (0,5) | id0
e0 | (0,5) | id1
e0 | (0,6) | id0
e0 | (0,6) | id1
e0 | (0,7) | id0
e0 | (0,7) | id1
e0 | (0,8) | id0
e0 | (0,8) | id1
e0 | (1,0) | id0
e0 | (1,0) | id1
e0 | (1,1) | id0
e0 | (1,1) | id1
e0 | (1,2) | id0
e0 | (1,2) | id1
e0 | (1,3) | id0
e0 | (1,3) | id1
e0 | (1,4) | id0
e0 | (1,4) | id1
e0 | (1,5) | id0
e0 | (1,5) | id1
```

Task-wide, rows whose Example column is e1: 405 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
```
```
c0 | c1 | c2
e1 | (0,0) | id0
e1 | (0,0) | id2
e1 | (0,0) | id3
e1 | (0,0) | id4
e1 | (0,0) | id5
e1 | (0,1) | id0
e1 | (0,1) | id2
e1 | (0,1) | id3
e1 | (0,1) | id4
e1 | (0,1) | id5
e1 | (0,2) | id0
e1 | (0,2) | id2
e1 | (0,2) | id3
e1 | (0,2) | id4
e1 | (0,2) | id5
e1 | (0,3) | id0
e1 | (0,3) | id2
e1 | (0,3) | id3
e1 | (0,3) | id4
e1 | (0,3) | id5
e1 | (0,4) | id0
e1 | (0,4) | id2
e1 | (0,4) | id3
e1 | (0,4) | id4
e1 | (0,4) | id5
e1 | (0,5) | id0
e1 | (0,5) | id2
e1 | (0,5) | id3
e1 | (0,5) | id4
e1 | (0,5) | id5
```

Task-wide, rows whose Example column is e2: 243 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
```
```
c0 | c1 | c2
e2 | (0,0) | id6
e2 | (0,0) | id7
e2 | (0,0) | id8
e2 | (0,1) | id6
e2 | (0,1) | id7
e2 | (0,1) | id8
e2 | (0,2) | id6
e2 | (0,2) | id7
e2 | (0,2) | id8
e2 | (0,3) | id6
e2 | (0,3) | id7
e2 | (0,3) | id8
e2 | (0,4) | id6
e2 | (0,4) | id7
e2 | (0,4) | id8
e2 | (0,5) | id6
e2 | (0,5) | id7
e2 | (0,5) | id8
e2 | (0,6) | id6
e2 | (0,6) | id7
e2 | (0,6) | id8
e2 | (0,7) | id6
e2 | (0,7) | id7
e2 | (0,7) | id8
e2 | (0,8) | id6
e2 | (0,8) | id7
e2 | (0,8) | id8
e2 | (1,0) | id6
e2 | (1,0) | id7
e2 | (1,0) | id8
```

Task-wide, rows whose Example column is e3: 405 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
```
```
c0 | c1 | c2
e3 | (0,0) | id9
e3 | (0,0) | id10
e3 | (0,0) | id11
e3 | (0,0) | id12
e3 | (0,0) | id13
e3 | (0,1) | id9
e3 | (0,1) | id10
e3 | (0,1) | id11
e3 | (0,1) | id12
e3 | (0,1) | id13
e3 | (0,2) | id9
e3 | (0,2) | id10
e3 | (0,2) | id11
e3 | (0,2) | id12
e3 | (0,2) | id13
e3 | (0,3) | id9
e3 | (0,3) | id10
e3 | (0,3) | id11
e3 | (0,3) | id12
e3 | (0,3) | id13
e3 | (0,4) | id9
e3 | (0,4) | id10
e3 | (0,4) | id11
e3 | (0,4) | id12
e3 | (0,4) | id13
e3 | (0,5) | id9
e3 | (0,5) | id10
e3 | (0,5) | id11
e3 | (0,5) | id12
e3 | (0,5) | id13
```

```
DET &r14 :0 * [L0] :1 * [L1] :2 * [L2] &r16 :0 :0 L0 END :1 L1 :2 * [L3] &r16 :0 :0 L0 END :1 * [L4] :2 L3 &r15 :0 L0 :1 L4 :2 * [L5] relative :0 L1 :1 L4 :2 * [L6] END [&r28]
```

### &r28 (export table 22)

- columns: c0: Example, c1: Box, c2: Box, c3: Box, c4: Color, c5: Color, c6: Ident
- depth 8, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r28; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 32
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 8 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . 4 . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . 4 . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
e0 | (3,2) | (2,1) | +(-1,-1) | 2 | 4 | id1
e0 | (3,2) | (2,3) | +(-1,1) | 2 | 4 | id1
e0 | (3,2) | (4,1) | +(1,-1) | 2 | 4 | id1
e0 | (3,2) | (4,3) | +(1,1) | 2 | 4 | id1
e0 | (6,6) | (5,6) | +(-1,0) | 1 | 7 | id0
e0 | (6,6) | (6,5) | +(0,-1) | 1 | 7 | id0
e0 | (6,6) | (6,7) | +(0,1) | 1 | 7 | id0
e0 | (6,6) | (7,6) | +(1,0) | 1 | 7 | id0
```

Task-wide, rows whose Example column is e1: 16 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . 4 . .
. . 4 . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . 4 . .
. 4 . . . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
e1 | (2,6) | (1,5) | +(-1,-1) | 2 | 4 | id5
e1 | (2,6) | (1,7) | +(-1,1) | 2 | 4 | id5
e1 | (2,6) | (3,5) | +(1,-1) | 2 | 4 | id5
e1 | (2,6) | (3,7) | +(1,1) | 2 | 4 | id5
e1 | (3,2) | (2,2) | +(-1,0) | 1 | 7 | id4
e1 | (3,2) | (3,1) | +(0,-1) | 1 | 7 | id4
e1 | (3,2) | (3,3) | +(0,1) | 1 | 7 | id4
e1 | (3,2) | (4,2) | +(1,0) | 1 | 7 | id4
e1 | (6,6) | (5,6) | +(-1,0) | 1 | 7 | id0
e1 | (6,6) | (6,5) | +(0,-1) | 1 | 7 | id0
e1 | (6,6) | (6,7) | +(0,1) | 1 | 7 | id0
e1 | (6,6) | (7,6) | +(1,0) | 1 | 7 | id0
e1 | (7,1) | (6,0) | +(-1,-1) | 2 | 4 | id2
e1 | (7,1) | (6,2) | +(-1,1) | 2 | 4 | id2
e1 | (7,1) | (8,0) | +(1,-1) | 2 | 4 | id2
e1 | (7,1) | (8,2) | +(1,1) | 2 | 4 | id2
```

Task-wide, rows whose Example column is e2: 8 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . 4 . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . 4 . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5 | c6
e2 | (2,2) | (1,1) | +(-1,-1) | 2 | 4 | id7
e2 | (2,2) | (1,3) | +(-1,1) | 2 | 4 | id7
e2 | (2,2) | (3,1) | +(1,-1) | 2 | 4 | id7
e2 | (2,2) | (3,3) | +(1,1) | 2 | 4 | id7
e2 | (7,3) | (6,3) | +(-1,0) | 1 | 7 | id8
e2 | (7,3) | (7,2) | +(0,-1) | 1 | 7 | id8
e2 | (7,3) | (7,4) | +(0,1) | 1 | 7 | id8
e2 | (7,3) | (8,3) | +(1,0) | 1 | 7 | id8
```

```
DET &r28 :0 * [L0] :3 * [L1] :2 * [L2] :4 * [L3] :5 * [L4] &r22 :0 :0 L0 :1 L1 END :1 L3 :3 * [L5] &r27 :0 L0 :1 L1 :2 L3 != L5 0 END [&r29]
```

### &r29 (export table 23)

- columns: c0: Example, c1: Color, c2: Ident, c3: Box, c4: Number, c5: Color
- depth 12, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r20, &r21, &r27, &r28, &r29; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 16
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 4 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . a . .
. . . . . a . a .
. . . . . . a . .
. . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
e0 | 1 | id0 | (5,6) | 1 | 7
e0 | 1 | id0 | (6,5) | 1 | 7
e0 | 1 | id0 | (6,7) | 1 | 7
e0 | 1 | id0 | (7,6) | 1 | 7
```

Task-wide, rows whose Example column is e1: 8 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . a . . . . . .
. a . a . . . . .
. . a . . . . . .
. . . . . . b . .
. . . . . b . b .
. . . . . . b . .
. . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
e1 | 1 | id0 | (5,6) | 1 | 7
e1 | 1 | id0 | (6,5) | 1 | 7
e1 | 1 | id0 | (6,7) | 1 | 7
e1 | 1 | id0 | (7,6) | 1 | 7
e1 | 1 | id4 | (2,2) | 1 | 7
e1 | 1 | id4 | (3,1) | 1 | 7
e1 | 1 | id4 | (3,3) | 1 | 7
e1 | 1 | id4 | (4,2) | 1 | 7
```

Task-wide, rows whose Example column is e2: 4 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . a . . . . .
. . a . a . . . .
. . . a . . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
e2 | 1 | id8 | (6,3) | 1 | 7
e2 | 1 | id8 | (7,2) | 1 | 7
e2 | 1 | id8 | (7,4) | 1 | 7
e2 | 1 | id8 | (8,3) | 1 | 7
```

```
RULE &r29 :2 * [L0] dir_elem :0 * [L1] END [&r30]
```

### &r30 (export table 24)

- columns: c0: Dir, c1: Color
- depth 13, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r20, &r21, &r27, &r28, &r29; assignments: 1
- rows per train example: [4, 4, 4]; test: 4

Train example 0: 4 rows
```
c0 | c1
DIR_T | 1
DIR_B | 1
DIR_L | 1
DIR_R | 1
```

Train example 1: 4 rows
```
c0 | c1
DIR_T | 1
DIR_B | 1
DIR_L | 1
DIR_R | 1
```

Train example 2: 4 rows
```
c0 | c1
DIR_T | 1
DIR_B | 1
DIR_L | 1
DIR_R | 1
```

```
INIT Ray [:0] OR input :0 * [L0] :1 ^ [L1] &r29 :2 L1 ALSO &r30 :1 L1 :2 * [L2] ALSO &r30 :1 L1 input :0 L0 END END [:1] input :0 * [L3] :1 L1 &r29 :2 L1 END [:0] END [:1] L3 END [:2] &r30 :1 L1 input :0 * [L4] END [:0] END [:1] L4 END [:3] &r30 :1 L1 :2 * [L5] END [:0] END [:1] L5 END [&r31] [&r32] [&r33] [&r34] [&r35]
```

### &r31 (export table 25)

- columns: c0: Color, c1: Box, c2: Dir8, c3: Number, c4: Box
- depth 15, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r20, &r21, &r27, &r28, &r29; assignments: 1
- rows per train example: [20, 40, 20]; test: 20

Train example 0: 20 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . 1 . .
. . . . . . 1 . .
. . . . . . 1 . .
. . . . . . 1 . .
. . . . . . 1 . .
. . . . . . 1 . .
1 1 1 1 1 1 4 1 1
. . . . . . 1 . .
. . . . . . 1 . .
```
```
c0 | c1 | c2 | c3 | c4
1 | (0,6) | DIR_T | 6 | (6,6)
1 | (1,6) | DIR_T | 5 | (6,6)
1 | (2,6) | DIR_T | 4 | (6,6)
1 | (3,6) | DIR_T | 3 | (6,6)
1 | (4,6) | DIR_T | 2 | (6,6)
1 | (5,6) | DIR_T | 1 | (6,6)
1 | (6,0) | DIR_L | 6 | (6,6)
1 | (6,1) | DIR_L | 5 | (6,6)
1 | (6,2) | DIR_L | 4 | (6,6)
1 | (6,3) | DIR_L | 3 | (6,6)
1 | (6,4) | DIR_L | 2 | (6,6)
1 | (6,5) | DIR_L | 1 | (6,6)
1 | (6,6) | DIR_T | 0 | (6,6)
1 | (6,6) | DIR_B | 0 | (6,6)
1 | (6,6) | DIR_L | 0 | (6,6)
1 | (6,6) | DIR_R | 0 | (6,6)
1 | (6,7) | DIR_R | 1 | (6,6)
1 | (6,8) | DIR_R | 2 | (6,6)
1 | (7,6) | DIR_B | 1 | (6,6)
1 | (8,6) | DIR_B | 2 | (6,6)
```

Train example 1: 40 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . 1 . . . 1 . .
. . 1 . . . 1 . .
. . 1 . . . 1 . .
1 1 4 1 1 1 2 1 1
. . 1 . . . 1 . .
. . 1 . . . 1 . .
1 1 2 1 1 1 4 1 1
. . 1 . . . 1 . .
. . 1 . . . 1 . .
```
```
c0 | c1 | c2 | c3 | c4
1 | (0,2) | DIR_T | 3 | (3,2)
1 | (0,6) | DIR_T | 6 | (6,6)
1 | (1,2) | DIR_T | 2 | (3,2)
1 | (1,6) | DIR_T | 5 | (6,6)
1 | (2,2) | DIR_T | 1 | (3,2)
1 | (2,6) | DIR_T | 4 | (6,6)
1 | (3,0) | DIR_L | 2 | (3,2)
1 | (3,1) | DIR_L | 1 | (3,2)
1 | (3,2) | DIR_T | 0 | (3,2)
1 | (3,2) | DIR_B | 0 | (3,2)
1 | (3,2) | DIR_L | 0 | (3,2)
1 | (3,2) | DIR_R | 0 | (3,2)
1 | (3,3) | DIR_R | 1 | (3,2)
1 | (3,4) | DIR_R | 2 | (3,2)
1 | (3,5) | DIR_R | 3 | (3,2)
1 | (3,6) | DIR_T | 3 | (6,6)
1 | (3,6) | DIR_R | 4 | (3,2)
1 | (3,7) | DIR_R | 5 | (3,2)
1 | (3,8) | DIR_R | 6 | (3,2)
1 | (4,2) | DIR_B | 1 | (3,2)
1 | (4,6) | DIR_T | 2 | (6,6)
1 | (5,2) | DIR_B | 2 | (3,2)
1 | (5,6) | DIR_T | 1 | (6,6)
1 | (6,0) | DIR_L | 6 | (6,6)
1 | (6,1) | DIR_L | 5 | (6,6)
1 | (6,2) | DIR_B | 3 | (3,2)
1 | (6,2) | DIR_L | 4 | (6,6)
1 | (6,3) | DIR_L | 3 | (6,6)
1 | (6,4) | DIR_L | 2 | (6,6)
1 | (6,5) | DIR_L | 1 | (6,6)
```

Train example 2: 20 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . 1 . . . . .
. . . 1 . . . . .
. . . 1 . . . . .
. . . 1 . . . . .
. . . 1 . . . . .
. . . 1 . . . . .
. . . 1 . . . . .
1 1 1 4 1 1 1 1 1
. . . 1 . . . . .
```
```
c0 | c1 | c2 | c3 | c4
1 | (0,3) | DIR_T | 7 | (7,3)
1 | (1,3) | DIR_T | 6 | (7,3)
1 | (2,3) | DIR_T | 5 | (7,3)
1 | (3,3) | DIR_T | 4 | (7,3)
1 | (4,3) | DIR_T | 3 | (7,3)
1 | (5,3) | DIR_T | 2 | (7,3)
1 | (6,3) | DIR_T | 1 | (7,3)
1 | (7,0) | DIR_L | 3 | (7,3)
1 | (7,1) | DIR_L | 2 | (7,3)
1 | (7,2) | DIR_L | 1 | (7,3)
1 | (7,3) | DIR_T | 0 | (7,3)
1 | (7,3) | DIR_B | 0 | (7,3)
1 | (7,3) | DIR_L | 0 | (7,3)
1 | (7,3) | DIR_R | 0 | (7,3)
1 | (7,4) | DIR_R | 1 | (7,3)
1 | (7,5) | DIR_R | 2 | (7,3)
1 | (7,6) | DIR_R | 3 | (7,3)
1 | (7,7) | DIR_R | 4 | (7,3)
1 | (7,8) | DIR_R | 5 | (7,3)
1 | (8,3) | DIR_B | 1 | (7,3)
```

### &r32 (export table 26)

- columns: c0: Color, c1: Box, c2: Dir8, c3: Number, c4: Box
- depth 15, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r20, &r21, &r27, &r28, &r29; assignments: 1
- rows per train example: [4, 8, 4]; test: 4

Train example 0: 4 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . 1 . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
1 . . . . . . . 1
. . . . . . . . .
. . . . . . 1 . .
```
```
c0 | c1 | c2 | c3 | c4
1 | (0,6) | DIR_T | 6 | (6,6)
1 | (6,0) | DIR_L | 6 | (6,6)
1 | (6,8) | DIR_R | 2 | (6,6)
1 | (8,6) | DIR_B | 2 | (6,6)
```

Train example 1: 8 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . 1 . . . 1 . .
. . . . . . . . .
. . . . . . . . .
1 . . . . . . . 1
. . . . . . . . .
. . . . . . . . .
1 . . . . . . . 1
. . . . . . . . .
. . 1 . . . 1 . .
```
```
c0 | c1 | c2 | c3 | c4
1 | (0,2) | DIR_T | 3 | (3,2)
1 | (0,6) | DIR_T | 6 | (6,6)
1 | (3,0) | DIR_L | 2 | (3,2)
1 | (3,8) | DIR_R | 6 | (3,2)
1 | (6,0) | DIR_L | 6 | (6,6)
1 | (6,8) | DIR_R | 2 | (6,6)
1 | (8,2) | DIR_B | 5 | (3,2)
1 | (8,6) | DIR_B | 2 | (6,6)
```

Train example 2: 4 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . 1 . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
1 . . . . . . . 1
. . . 1 . . . . .
```
```
c0 | c1 | c2 | c3 | c4
1 | (0,3) | DIR_T | 7 | (7,3)
1 | (7,0) | DIR_L | 3 | (7,3)
1 | (7,8) | DIR_R | 5 | (7,3)
1 | (8,3) | DIR_B | 1 | (7,3)
```

### &r33 (export table 27)

- columns: c0: Color, c1: Box
- depth 14, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r20, &r21, &r27, &r28, &r29; assignments: 1
- rows per train example: [1, 2, 1]; test: 1

Train example 0: 1 row
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . 1 . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1
1 | (6,6)
```

Train example 1: 2 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . 1 . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . 1 . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1
1 | (3,2)
1 | (6,6)
```

Train example 2: 1 row
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . 1 . . . . .
. . . . . . . . .
```
```
c0 | c1
1 | (7,3)
```

### &r34 (export table 28)

- columns: c0: Color, c1: Box
- depth 14, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r20, &r21, &r27, &r28, &r29; assignments: 1
- rows per train example: [81, 81, 81]; test: 81

Train example 0: 81 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
```
```
c0 | c1
1 | (0,0)
1 | (0,1)
1 | (0,2)
1 | (0,3)
1 | (0,4)
1 | (0,5)
1 | (0,6)
1 | (0,7)
1 | (0,8)
1 | (1,0)
1 | (1,1)
1 | (1,2)
1 | (1,3)
1 | (1,4)
1 | (1,5)
1 | (1,6)
1 | (1,7)
1 | (1,8)
1 | (2,0)
1 | (2,1)
1 | (2,2)
1 | (2,3)
1 | (2,4)
1 | (2,5)
1 | (2,6)
1 | (2,7)
1 | (2,8)
1 | (3,0)
1 | (3,1)
1 | (3,2)
```

Train example 1: 81 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
```
```
c0 | c1
1 | (0,0)
1 | (0,1)
1 | (0,2)
1 | (0,3)
1 | (0,4)
1 | (0,5)
1 | (0,6)
1 | (0,7)
1 | (0,8)
1 | (1,0)
1 | (1,1)
1 | (1,2)
1 | (1,3)
1 | (1,4)
1 | (1,5)
1 | (1,6)
1 | (1,7)
1 | (1,8)
1 | (2,0)
1 | (2,1)
1 | (2,2)
1 | (2,3)
1 | (2,4)
1 | (2,5)
1 | (2,6)
1 | (2,7)
1 | (2,8)
1 | (3,0)
1 | (3,1)
1 | (3,2)
```

Train example 2: 81 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1
```
```
c0 | c1
1 | (0,0)
1 | (0,1)
1 | (0,2)
1 | (0,3)
1 | (0,4)
1 | (0,5)
1 | (0,6)
1 | (0,7)
1 | (0,8)
1 | (1,0)
1 | (1,1)
1 | (1,2)
1 | (1,3)
1 | (1,4)
1 | (1,5)
1 | (1,6)
1 | (1,7)
1 | (1,8)
1 | (2,0)
1 | (2,1)
1 | (2,2)
1 | (2,3)
1 | (2,4)
1 | (2,5)
1 | (2,6)
1 | (2,7)
1 | (2,8)
1 | (3,0)
1 | (3,1)
1 | (3,2)
```

```
DET &r14 :0 * [L0] :1 * [L1] &r16 :0 :0 L0 END :1 L1 :2 * [L2] END [&r36]
```

### &r36 (export table 29)

- columns: c0: Example, c1: Box, c2: Ident
- depth 8, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r36; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 15
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 2 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . a . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . b . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2
e0 | (3,2) | id1
e0 | (6,6) | id0
```

Task-wide, rows whose Example column is e1: 5 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . a . . . . .
. . . . . . . . .
. . . . . . b . .
. . c . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . d . .
. e . . . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2
e1 | (0,3) | id3
e1 | (2,6) | id5
e1 | (3,2) | id4
e1 | (6,6) | id0
e1 | (7,1) | id2
```

Task-wide, rows whose Example column is e2: 3 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . a . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . b . .
. . . . . . . . .
. . . c . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2
e2 | (2,2) | id7
e2 | (5,6) | id6
e2 | (7,3) | id8
```

Task-wide, rows whose Example column is e3: 5 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . a . .
. . b . . . . . .
. . . . . . . . .
. . . . . c . . .
. . . . . . . . .
. d . . . . . e .
. . . . . . . . .
```
```
c0 | c1 | c2
e3 | (2,6) | id10
e3 | (3,2) | id11
e3 | (5,5) | id9
e3 | (7,1) | id13
e3 | (7,7) | id12
```

```
DET &r36 :0 * [L0] :2 * [L1] diag_dir_elem :0 * [L2] END [&r37]
```

### &r37 (export table 30)

- columns: c0: DiagDir, c1: Example, c2: Ident
- depth 9, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r36, &r37; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 60
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 8 rows
```
c0 | c1 | c2
DIAG_TL | e0 | id0
DIAG_TL | e0 | id1
DIAG_TR | e0 | id0
DIAG_TR | e0 | id1
DIAG_BL | e0 | id0
DIAG_BL | e0 | id1
DIAG_BR | e0 | id0
DIAG_BR | e0 | id1
```

Task-wide, rows whose Example column is e1: 20 rows
```
c0 | c1 | c2
DIAG_TL | e1 | id0
DIAG_TL | e1 | id2
DIAG_TL | e1 | id3
DIAG_TL | e1 | id4
DIAG_TL | e1 | id5
DIAG_TR | e1 | id0
DIAG_TR | e1 | id2
DIAG_TR | e1 | id3
DIAG_TR | e1 | id4
DIAG_TR | e1 | id5
DIAG_BL | e1 | id0
DIAG_BL | e1 | id2
DIAG_BL | e1 | id3
DIAG_BL | e1 | id4
DIAG_BL | e1 | id5
DIAG_BR | e1 | id0
DIAG_BR | e1 | id2
DIAG_BR | e1 | id3
DIAG_BR | e1 | id4
DIAG_BR | e1 | id5
```

Task-wide, rows whose Example column is e2: 12 rows
```
c0 | c1 | c2
DIAG_TL | e2 | id6
DIAG_TL | e2 | id7
DIAG_TL | e2 | id8
DIAG_TR | e2 | id6
DIAG_TR | e2 | id7
DIAG_TR | e2 | id8
DIAG_BL | e2 | id6
DIAG_BL | e2 | id7
DIAG_BL | e2 | id8
DIAG_BR | e2 | id6
DIAG_BR | e2 | id7
DIAG_BR | e2 | id8
```

Task-wide, rows whose Example column is e3: 20 rows
```
c0 | c1 | c2
DIAG_TL | e3 | id9
DIAG_TL | e3 | id10
DIAG_TL | e3 | id11
DIAG_TL | e3 | id12
DIAG_TL | e3 | id13
DIAG_TR | e3 | id9
DIAG_TR | e3 | id10
DIAG_TR | e3 | id11
DIAG_TR | e3 | id12
DIAG_TR | e3 | id13
DIAG_BL | e3 | id9
DIAG_BL | e3 | id10
DIAG_BL | e3 | id11
DIAG_BL | e3 | id12
DIAG_BL | e3 | id13
DIAG_BR | e3 | id9
DIAG_BR | e3 | id10
DIAG_BR | e3 | id11
DIAG_BR | e3 | id12
DIAG_BR | e3 | id13
```

```
INIT Ray [:0] OR &r14 :0 ^ [L0] :1 * [L1] &r16 :0 :0 L0 END :1 L1 :2 ^ [L2] ALSO &r37 :0 L0 :1 L2 :2 * [L3] ALSO &r37 :0 L0 :1 L2 ex_input :0 L0 :1 L1 END END [:1] &r14 :0 L0 :1 * [L4] &r16 :0 :0 L0 END :1 L4 :2 L2 END [:0] END [:1] L4 END [:2] &r37 :0 L0 :1 L2 ex_input :0 L0 :1 * [L5] END [:0] END [:1] L5 END [:3] &r37 :0 L0 :1 L2 :2 * [L6] END [:0] END [:1] L6 END [&r38] [&r39] [&r40] [&r41] [&r42]
```

### &r38 (export table 31)

- columns: c0: Example, c1: Ident, c2: Box, c3: Dir8, c4: Number, c5: Box
- depth 11, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r36, &r37; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 230
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 32 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 . . . . 1 . . .
1 1 . . 1 . . . .
. 1 1 1 . . . . .
. . 4 1 . . . . .
. 1 . 1 1 . . . 1
1 . . . 1 1 . 1 .
. . . . . 1 4 . .
. . . . . 1 1 1 .
. . . . 1 . . 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5
e0 | id0 | (0,0) | DIAG_TL | 6 | (6,6)
e0 | id0 | (1,1) | DIAG_TL | 5 | (6,6)
e0 | id0 | (2,2) | DIAG_TL | 4 | (6,6)
e0 | id0 | (3,3) | DIAG_TL | 3 | (6,6)
e0 | id0 | (4,4) | DIAG_TL | 2 | (6,6)
e0 | id0 | (4,8) | DIAG_TR | 2 | (6,6)
e0 | id0 | (5,5) | DIAG_TL | 1 | (6,6)
e0 | id0 | (5,7) | DIAG_TR | 1 | (6,6)
e0 | id0 | (6,6) | DIAG_TL | 0 | (6,6)
e0 | id0 | (6,6) | DIAG_TR | 0 | (6,6)
e0 | id0 | (6,6) | DIAG_BL | 0 | (6,6)
e0 | id0 | (6,6) | DIAG_BR | 0 | (6,6)
e0 | id0 | (7,5) | DIAG_BL | 1 | (6,6)
e0 | id0 | (7,7) | DIAG_BR | 1 | (6,6)
e0 | id0 | (8,4) | DIAG_BL | 2 | (6,6)
e0 | id0 | (8,8) | DIAG_BR | 2 | (6,6)
e0 | id1 | (0,5) | DIAG_TR | 3 | (3,2)
e0 | id1 | (1,0) | DIAG_TL | 2 | (3,2)
e0 | id1 | (1,4) | DIAG_TR | 2 | (3,2)
e0 | id1 | (2,1) | DIAG_TL | 1 | (3,2)
e0 | id1 | (2,3) | DIAG_TR | 1 | (3,2)
e0 | id1 | (3,2) | DIAG_TL | 0 | (3,2)
e0 | id1 | (3,2) | DIAG_TR | 0 | (3,2)
e0 | id1 | (3,2) | DIAG_BL | 0 | (3,2)
e0 | id1 | (3,2) | DIAG_BR | 0 | (3,2)
e0 | id1 | (4,1) | DIAG_BL | 1 | (3,2)
e0 | id1 | (4,3) | DIAG_BR | 1 | (3,2)
e0 | id1 | (5,0) | DIAG_BL | 2 | (3,2)
e0 | id1 | (5,4) | DIAG_BR | 2 | (3,2)
e0 | id1 | (6,5) | DIAG_BR | 3 | (3,2)
```

Task-wide, rows whose Example column is e1: 74 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 . . 4 1 1 . . 2
1 1 1 . 2 1 . 2 .
. 2 1 1 . 1 5 . .
1 . 4 1 . 2 1 1 .
. 1 . 1 3 . . 1 2
1 . . 2 1 1 . 1 1
1 . 2 . . 1 4 . .
. 5 . . . 1 1 1 .
2 . 1 . 1 . . 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5
e1 | id0 | (0,0) | DIAG_TL | 6 | (6,6)
e1 | id0 | (1,1) | DIAG_TL | 5 | (6,6)
e1 | id0 | (2,2) | DIAG_TL | 4 | (6,6)
e1 | id0 | (3,3) | DIAG_TL | 3 | (6,6)
e1 | id0 | (4,4) | DIAG_TL | 2 | (6,6)
e1 | id0 | (4,8) | DIAG_TR | 2 | (6,6)
e1 | id0 | (5,5) | DIAG_TL | 1 | (6,6)
e1 | id0 | (5,7) | DIAG_TR | 1 | (6,6)
e1 | id0 | (6,6) | DIAG_TL | 0 | (6,6)
e1 | id0 | (6,6) | DIAG_TR | 0 | (6,6)
e1 | id0 | (6,6) | DIAG_BL | 0 | (6,6)
e1 | id0 | (6,6) | DIAG_BR | 0 | (6,6)
e1 | id0 | (7,5) | DIAG_BL | 1 | (6,6)
e1 | id0 | (7,7) | DIAG_BR | 1 | (6,6)
e1 | id0 | (8,4) | DIAG_BL | 2 | (6,6)
e1 | id0 | (8,8) | DIAG_BR | 2 | (6,6)
e1 | id2 | (0,8) | DIAG_TR | 7 | (7,1)
e1 | id2 | (1,7) | DIAG_TR | 6 | (7,1)
e1 | id2 | (2,6) | DIAG_TR | 5 | (7,1)
e1 | id2 | (3,5) | DIAG_TR | 4 | (7,1)
e1 | id2 | (4,4) | DIAG_TR | 3 | (7,1)
e1 | id2 | (5,3) | DIAG_TR | 2 | (7,1)
e1 | id2 | (6,0) | DIAG_TL | 1 | (7,1)
e1 | id2 | (6,2) | DIAG_TR | 1 | (7,1)
e1 | id2 | (7,1) | DIAG_TL | 0 | (7,1)
e1 | id2 | (7,1) | DIAG_TR | 0 | (7,1)
e1 | id2 | (7,1) | DIAG_BL | 0 | (7,1)
e1 | id2 | (7,1) | DIAG_BR | 0 | (7,1)
e1 | id2 | (8,0) | DIAG_BL | 1 | (7,1)
e1 | id2 | (8,2) | DIAG_BR | 1 | (7,1)
```

Task-wide, rows whose Example column is e2: 46 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 . . 1 . . . .
. 1 1 1 . . . . .
. . 4 1 . . . . 1
. 1 . 1 1 . . 1 1
2 . . . 1 1 1 1 .
. 1 . . . 2 4 . .
. . 1 . 1 1 1 1 .
. . . 4 1 . . 1 1
. . 1 1 1 . . . 1
```
```
c0 | c1 | c2 | c3 | c4 | c5
e2 | id6 | (0,1) | DIAG_TL | 5 | (5,6)
e2 | id6 | (1,2) | DIAG_TL | 4 | (5,6)
e2 | id6 | (2,3) | DIAG_TL | 3 | (5,6)
e2 | id6 | (3,4) | DIAG_TL | 2 | (5,6)
e2 | id6 | (3,8) | DIAG_TR | 2 | (5,6)
e2 | id6 | (4,5) | DIAG_TL | 1 | (5,6)
e2 | id6 | (4,7) | DIAG_TR | 1 | (5,6)
e2 | id6 | (5,6) | DIAG_TL | 0 | (5,6)
e2 | id6 | (5,6) | DIAG_TR | 0 | (5,6)
e2 | id6 | (5,6) | DIAG_BL | 0 | (5,6)
e2 | id6 | (5,6) | DIAG_BR | 0 | (5,6)
e2 | id6 | (6,5) | DIAG_BL | 1 | (5,6)
e2 | id6 | (6,7) | DIAG_BR | 1 | (5,6)
e2 | id6 | (7,4) | DIAG_BL | 2 | (5,6)
e2 | id6 | (7,8) | DIAG_BR | 2 | (5,6)
e2 | id6 | (8,3) | DIAG_BL | 3 | (5,6)
e2 | id7 | (0,0) | DIAG_TL | 2 | (2,2)
e2 | id7 | (0,4) | DIAG_TR | 2 | (2,2)
e2 | id7 | (1,1) | DIAG_TL | 1 | (2,2)
e2 | id7 | (1,3) | DIAG_TR | 1 | (2,2)
e2 | id7 | (2,2) | DIAG_TL | 0 | (2,2)
e2 | id7 | (2,2) | DIAG_TR | 0 | (2,2)
e2 | id7 | (2,2) | DIAG_BL | 0 | (2,2)
e2 | id7 | (2,2) | DIAG_BR | 0 | (2,2)
e2 | id7 | (3,1) | DIAG_BL | 1 | (2,2)
e2 | id7 | (3,3) | DIAG_BR | 1 | (2,2)
e2 | id7 | (4,0) | DIAG_BL | 2 | (2,2)
e2 | id7 | (4,4) | DIAG_BR | 2 | (2,2)
e2 | id7 | (5,5) | DIAG_BR | 3 | (2,2)
e2 | id7 | (6,6) | DIAG_BR | 4 | (2,2)
```

Task-wide, rows whose Example column is e3: 78 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 . . . 1 1 . . 2
1 2 . . 1 1 . 2 .
. 1 2 1 . . 5 . 1
. . 4 2 . 2 . 2 .
. 1 . 1 4 . 1 . 1
1 . . 2 1 5 . . .
1 . 2 . 1 1 2 . 1
. 5 . 1 . . 1 5 .
2 . 2 . . . 1 1 2
```
```
c0 | c1 | c2 | c3 | c4 | c5
e3 | id9 | (0,0) | DIAG_TL | 5 | (5,5)
e3 | id9 | (1,1) | DIAG_TL | 4 | (5,5)
e3 | id9 | (2,2) | DIAG_TL | 3 | (5,5)
e3 | id9 | (2,8) | DIAG_TR | 3 | (5,5)
e3 | id9 | (3,3) | DIAG_TL | 2 | (5,5)
e3 | id9 | (3,7) | DIAG_TR | 2 | (5,5)
e3 | id9 | (4,4) | DIAG_TL | 1 | (5,5)
e3 | id9 | (4,6) | DIAG_TR | 1 | (5,5)
e3 | id9 | (5,5) | DIAG_TL | 0 | (5,5)
e3 | id9 | (5,5) | DIAG_TR | 0 | (5,5)
e3 | id9 | (5,5) | DIAG_BL | 0 | (5,5)
e3 | id9 | (5,5) | DIAG_BR | 0 | (5,5)
e3 | id9 | (6,4) | DIAG_BL | 1 | (5,5)
e3 | id9 | (6,6) | DIAG_BR | 1 | (5,5)
e3 | id9 | (7,3) | DIAG_BL | 2 | (5,5)
e3 | id9 | (7,7) | DIAG_BR | 2 | (5,5)
e3 | id9 | (8,2) | DIAG_BL | 3 | (5,5)
e3 | id9 | (8,8) | DIAG_BR | 3 | (5,5)
e3 | id10 | (0,4) | DIAG_TL | 2 | (2,6)
e3 | id10 | (0,8) | DIAG_TR | 2 | (2,6)
e3 | id10 | (1,5) | DIAG_TL | 1 | (2,6)
e3 | id10 | (1,7) | DIAG_TR | 1 | (2,6)
e3 | id10 | (2,6) | DIAG_TL | 0 | (2,6)
e3 | id10 | (2,6) | DIAG_TR | 0 | (2,6)
e3 | id10 | (2,6) | DIAG_BL | 0 | (2,6)
e3 | id10 | (2,6) | DIAG_BR | 0 | (2,6)
e3 | id10 | (3,5) | DIAG_BL | 1 | (2,6)
e3 | id10 | (3,7) | DIAG_BR | 1 | (2,6)
e3 | id10 | (4,4) | DIAG_BL | 2 | (2,6)
e3 | id10 | (4,8) | DIAG_BR | 2 | (2,6)
```

### &r39 (export table 32)

- columns: c0: Example, c1: Ident, c2: Box, c3: Dir8, c4: Number, c5: Box
- depth 11, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r36, &r37; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 60
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 8 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
a . . . . b . . .
b . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . a
b . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . a . . b a
```
```
c0 | c1 | c2 | c3 | c4 | c5
e0 | id0 | (0,0) | DIAG_TL | 6 | (6,6)
e0 | id0 | (4,8) | DIAG_TR | 2 | (6,6)
e0 | id0 | (8,4) | DIAG_BL | 2 | (6,6)
e0 | id0 | (8,8) | DIAG_BR | 2 | (6,6)
e0 | id1 | (0,5) | DIAG_TR | 3 | (3,2)
e0 | id1 | (1,0) | DIAG_TL | 2 | (3,2)
e0 | id1 | (5,0) | DIAG_BL | 2 | (3,2)
e0 | id1 | (8,7) | DIAG_BR | 5 | (3,2)
```

Task-wide, rows whose Example column is e1: 20 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 . . 2 1 1 . . 2
1 . . . . . . . .
. . . . . . . . .
1 . . . . . . . .
. . . . . . . . 2
1 . . . . . . . 1
1 . . . . . . . .
. . . . . . . . .
2 . 1 . 1 . . 1 1
```
```
c0 | c1 | c2 | c3 | c4 | c5
e1 | id0 | (0,0) | DIAG_TL | 6 | (6,6)
e1 | id0 | (4,8) | DIAG_TR | 2 | (6,6)
e1 | id0 | (8,4) | DIAG_BL | 2 | (6,6)
e1 | id0 | (8,8) | DIAG_BR | 2 | (6,6)
e1 | id2 | (0,8) | DIAG_TR | 7 | (7,1)
e1 | id2 | (6,0) | DIAG_TL | 1 | (7,1)
e1 | id2 | (8,0) | DIAG_BL | 1 | (7,1)
e1 | id2 | (8,2) | DIAG_BR | 1 | (7,1)
e1 | id3 | (0,3) | DIAG_TL | 0 | (0,3)
e1 | id3 | (0,3) | DIAG_TR | 0 | (0,3)
e1 | id3 | (3,0) | DIAG_BL | 3 | (0,3)
e1 | id3 | (5,8) | DIAG_BR | 5 | (0,3)
e1 | id4 | (0,5) | DIAG_TR | 3 | (3,2)
e1 | id4 | (1,0) | DIAG_TL | 2 | (3,2)
e1 | id4 | (5,0) | DIAG_BL | 2 | (3,2)
e1 | id4 | (8,7) | DIAG_BR | 5 | (3,2)
e1 | id5 | (0,4) | DIAG_TL | 2 | (2,6)
e1 | id5 | (0,8) | DIAG_TR | 2 | (2,6)
e1 | id5 | (4,8) | DIAG_BR | 2 | (2,6)
e1 | id5 | (8,0) | DIAG_BL | 6 | (2,6)
```

Task-wide, rows whose Example column is e2: 12 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 1 . . 1 . . . .
. . . . . . . . .
. . . . . . . . 1
. . . . . . . . 1
2 . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . 1
. . 1 1 1 . . . 1
```
```
c0 | c1 | c2 | c3 | c4 | c5
e2 | id6 | (0,1) | DIAG_TL | 5 | (5,6)
e2 | id6 | (3,8) | DIAG_TR | 2 | (5,6)
e2 | id6 | (7,8) | DIAG_BR | 2 | (5,6)
e2 | id6 | (8,3) | DIAG_BL | 3 | (5,6)
e2 | id7 | (0,0) | DIAG_TL | 2 | (2,2)
e2 | id7 | (0,4) | DIAG_TR | 2 | (2,2)
e2 | id7 | (4,0) | DIAG_BL | 2 | (2,2)
e2 | id7 | (8,8) | DIAG_BR | 6 | (2,2)
e2 | id8 | (2,8) | DIAG_TR | 5 | (7,3)
e2 | id8 | (4,0) | DIAG_TL | 3 | (7,3)
e2 | id8 | (8,2) | DIAG_BL | 1 | (7,3)
e2 | id8 | (8,4) | DIAG_BR | 1 | (7,3)
```

Task-wide, rows whose Example column is e3: 20 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 . . . 1 1 . . 2
1 . . . . . . . .
. . . . . . . . 1
. . . . . . . . .
. . . . . . . . 1
1 . . . . . . . .
1 . . . . . . . 1
. . . . . . . . .
2 . 2 . . . 1 1 2
```
```
c0 | c1 | c2 | c3 | c4 | c5
e3 | id9 | (0,0) | DIAG_TL | 5 | (5,5)
e3 | id9 | (2,8) | DIAG_TR | 3 | (5,5)
e3 | id9 | (8,2) | DIAG_BL | 3 | (5,5)
e3 | id9 | (8,8) | DIAG_BR | 3 | (5,5)
e3 | id10 | (0,4) | DIAG_TL | 2 | (2,6)
e3 | id10 | (0,8) | DIAG_TR | 2 | (2,6)
e3 | id10 | (4,8) | DIAG_BR | 2 | (2,6)
e3 | id10 | (8,0) | DIAG_BL | 6 | (2,6)
e3 | id11 | (0,5) | DIAG_TR | 3 | (3,2)
e3 | id11 | (1,0) | DIAG_TL | 2 | (3,2)
e3 | id11 | (5,0) | DIAG_BL | 2 | (3,2)
e3 | id11 | (8,7) | DIAG_BR | 5 | (3,2)
e3 | id12 | (0,0) | DIAG_TL | 7 | (7,7)
e3 | id12 | (6,8) | DIAG_TR | 1 | (7,7)
e3 | id12 | (8,6) | DIAG_BL | 1 | (7,7)
e3 | id12 | (8,8) | DIAG_BR | 1 | (7,7)
e3 | id13 | (0,8) | DIAG_TR | 7 | (7,1)
e3 | id13 | (6,0) | DIAG_TL | 1 | (7,1)
e3 | id13 | (8,0) | DIAG_BL | 1 | (7,1)
e3 | id13 | (8,2) | DIAG_BR | 1 | (7,1)
```

### &r40 (export table 33)

- columns: c0: Example, c1: Ident, c2: Box
- depth 10, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r36, &r37; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 15
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 2 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . a . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . b . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2
e0 | id0 | (6,6)
e0 | id1 | (3,2)
```

Task-wide, rows whose Example column is e1: 5 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . a . . . . .
. . . . . . . . .
. . . . . . b . .
. . c . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . d . .
. e . . . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2
e1 | id0 | (6,6)
e1 | id2 | (7,1)
e1 | id3 | (0,3)
e1 | id4 | (3,2)
e1 | id5 | (2,6)
```

Task-wide, rows whose Example column is e2: 3 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . a . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . b . .
. . . . . . . . .
. . . c . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2
e2 | id6 | (5,6)
e2 | id7 | (2,2)
e2 | id8 | (7,3)
```

Task-wide, rows whose Example column is e3: 5 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . a . .
. . b . . . . . .
. . . . . . . . .
. . . . . c . . .
. . . . . . . . .
. d . . . . . e .
. . . . . . . . .
```
```
c0 | c1 | c2
e3 | id9 | (5,5)
e3 | id10 | (2,6)
e3 | id11 | (3,2)
e3 | id12 | (7,7)
e3 | id13 | (7,1)
```

### &r41 (export table 34)

- columns: c0: Example, c1: Ident, c2: Box
- depth 10, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r36, &r37; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1215
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 162 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
```
```
c0 | c1 | c2
e0 | id0 | (0,0)
e0 | id0 | (0,1)
e0 | id0 | (0,2)
e0 | id0 | (0,3)
e0 | id0 | (0,4)
e0 | id0 | (0,5)
e0 | id0 | (0,6)
e0 | id0 | (0,7)
e0 | id0 | (0,8)
e0 | id0 | (1,0)
e0 | id0 | (1,1)
e0 | id0 | (1,2)
e0 | id0 | (1,3)
e0 | id0 | (1,4)
e0 | id0 | (1,5)
e0 | id0 | (1,6)
e0 | id0 | (1,7)
e0 | id0 | (1,8)
e0 | id0 | (2,0)
e0 | id0 | (2,1)
e0 | id0 | (2,2)
e0 | id0 | (2,3)
e0 | id0 | (2,4)
e0 | id0 | (2,5)
e0 | id0 | (2,6)
e0 | id0 | (2,7)
e0 | id0 | (2,8)
e0 | id0 | (3,0)
e0 | id0 | (3,1)
e0 | id0 | (3,2)
```

Task-wide, rows whose Example column is e1: 405 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
```
```
c0 | c1 | c2
e1 | id0 | (0,0)
e1 | id0 | (0,1)
e1 | id0 | (0,2)
e1 | id0 | (0,3)
e1 | id0 | (0,4)
e1 | id0 | (0,5)
e1 | id0 | (0,6)
e1 | id0 | (0,7)
e1 | id0 | (0,8)
e1 | id0 | (1,0)
e1 | id0 | (1,1)
e1 | id0 | (1,2)
e1 | id0 | (1,3)
e1 | id0 | (1,4)
e1 | id0 | (1,5)
e1 | id0 | (1,6)
e1 | id0 | (1,7)
e1 | id0 | (1,8)
e1 | id0 | (2,0)
e1 | id0 | (2,1)
e1 | id0 | (2,2)
e1 | id0 | (2,3)
e1 | id0 | (2,4)
e1 | id0 | (2,5)
e1 | id0 | (2,6)
e1 | id0 | (2,7)
e1 | id0 | (2,8)
e1 | id0 | (3,0)
e1 | id0 | (3,1)
e1 | id0 | (3,2)
```

Task-wide, rows whose Example column is e2: 243 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
```
```
c0 | c1 | c2
e2 | id6 | (0,0)
e2 | id6 | (0,1)
e2 | id6 | (0,2)
e2 | id6 | (0,3)
e2 | id6 | (0,4)
e2 | id6 | (0,5)
e2 | id6 | (0,6)
e2 | id6 | (0,7)
e2 | id6 | (0,8)
e2 | id6 | (1,0)
e2 | id6 | (1,1)
e2 | id6 | (1,2)
e2 | id6 | (1,3)
e2 | id6 | (1,4)
e2 | id6 | (1,5)
e2 | id6 | (1,6)
e2 | id6 | (1,7)
e2 | id6 | (1,8)
e2 | id6 | (2,0)
e2 | id6 | (2,1)
e2 | id6 | (2,2)
e2 | id6 | (2,3)
e2 | id6 | (2,4)
e2 | id6 | (2,5)
e2 | id6 | (2,6)
e2 | id6 | (2,7)
e2 | id6 | (2,8)
e2 | id6 | (3,0)
e2 | id6 | (3,1)
e2 | id6 | (3,2)
```

Task-wide, rows whose Example column is e3: 405 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
```
```
c0 | c1 | c2
e3 | id9 | (0,0)
e3 | id9 | (0,1)
e3 | id9 | (0,2)
e3 | id9 | (0,3)
e3 | id9 | (0,4)
e3 | id9 | (0,5)
e3 | id9 | (0,6)
e3 | id9 | (0,7)
e3 | id9 | (0,8)
e3 | id9 | (1,0)
e3 | id9 | (1,1)
e3 | id9 | (1,2)
e3 | id9 | (1,3)
e3 | id9 | (1,4)
e3 | id9 | (1,5)
e3 | id9 | (1,6)
e3 | id9 | (1,7)
e3 | id9 | (1,8)
e3 | id9 | (2,0)
e3 | id9 | (2,1)
e3 | id9 | (2,2)
e3 | id9 | (2,3)
e3 | id9 | (2,4)
e3 | id9 | (2,5)
e3 | id9 | (2,6)
e3 | id9 | (2,7)
e3 | id9 | (2,8)
e3 | id9 | (3,0)
e3 | id9 | (3,1)
e3 | id9 | (3,2)
```

```
DET &r36 :0 * [L0] :2 * [L1] ex_input :0 L0 :1 * [L2] END [&r43]
```

### &r43 (export table 35)

- columns: c0: Example, c1: Box, c2: Ident
- depth 9, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r36, &r43; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 1215
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 162 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
```
```
c0 | c1 | c2
e0 | (0,0) | id0
e0 | (0,0) | id1
e0 | (0,1) | id0
e0 | (0,1) | id1
e0 | (0,2) | id0
e0 | (0,2) | id1
e0 | (0,3) | id0
e0 | (0,3) | id1
e0 | (0,4) | id0
e0 | (0,4) | id1
e0 | (0,5) | id0
e0 | (0,5) | id1
e0 | (0,6) | id0
e0 | (0,6) | id1
e0 | (0,7) | id0
e0 | (0,7) | id1
e0 | (0,8) | id0
e0 | (0,8) | id1
e0 | (1,0) | id0
e0 | (1,0) | id1
e0 | (1,1) | id0
e0 | (1,1) | id1
e0 | (1,2) | id0
e0 | (1,2) | id1
e0 | (1,3) | id0
e0 | (1,3) | id1
e0 | (1,4) | id0
e0 | (1,4) | id1
e0 | (1,5) | id0
e0 | (1,5) | id1
```

Task-wide, rows whose Example column is e1: 405 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
```
```
c0 | c1 | c2
e1 | (0,0) | id0
e1 | (0,0) | id2
e1 | (0,0) | id3
e1 | (0,0) | id4
e1 | (0,0) | id5
e1 | (0,1) | id0
e1 | (0,1) | id2
e1 | (0,1) | id3
e1 | (0,1) | id4
e1 | (0,1) | id5
e1 | (0,2) | id0
e1 | (0,2) | id2
e1 | (0,2) | id3
e1 | (0,2) | id4
e1 | (0,2) | id5
e1 | (0,3) | id0
e1 | (0,3) | id2
e1 | (0,3) | id3
e1 | (0,3) | id4
e1 | (0,3) | id5
e1 | (0,4) | id0
e1 | (0,4) | id2
e1 | (0,4) | id3
e1 | (0,4) | id4
e1 | (0,4) | id5
e1 | (0,5) | id0
e1 | (0,5) | id2
e1 | (0,5) | id3
e1 | (0,5) | id4
e1 | (0,5) | id5
```

Task-wide, rows whose Example column is e2: 243 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
3 3 3 3 3 3 3 3 3
```
```
c0 | c1 | c2
e2 | (0,0) | id6
e2 | (0,0) | id7
e2 | (0,0) | id8
e2 | (0,1) | id6
e2 | (0,1) | id7
e2 | (0,1) | id8
e2 | (0,2) | id6
e2 | (0,2) | id7
e2 | (0,2) | id8
e2 | (0,3) | id6
e2 | (0,3) | id7
e2 | (0,3) | id8
e2 | (0,4) | id6
e2 | (0,4) | id7
e2 | (0,4) | id8
e2 | (0,5) | id6
e2 | (0,5) | id7
e2 | (0,5) | id8
e2 | (0,6) | id6
e2 | (0,6) | id7
e2 | (0,6) | id8
e2 | (0,7) | id6
e2 | (0,7) | id7
e2 | (0,7) | id8
e2 | (0,8) | id6
e2 | (0,8) | id7
e2 | (0,8) | id8
e2 | (1,0) | id6
e2 | (1,0) | id7
e2 | (1,0) | id8
```

Task-wide, rows whose Example column is e3: 405 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
5 5 5 5 5 5 5 5 5
```
```
c0 | c1 | c2
e3 | (0,0) | id9
e3 | (0,0) | id10
e3 | (0,0) | id11
e3 | (0,0) | id12
e3 | (0,0) | id13
e3 | (0,1) | id9
e3 | (0,1) | id10
e3 | (0,1) | id11
e3 | (0,1) | id12
e3 | (0,1) | id13
e3 | (0,2) | id9
e3 | (0,2) | id10
e3 | (0,2) | id11
e3 | (0,2) | id12
e3 | (0,2) | id13
e3 | (0,3) | id9
e3 | (0,3) | id10
e3 | (0,3) | id11
e3 | (0,3) | id12
e3 | (0,3) | id13
e3 | (0,4) | id9
e3 | (0,4) | id10
e3 | (0,4) | id11
e3 | (0,4) | id12
e3 | (0,4) | id13
e3 | (0,5) | id9
e3 | (0,5) | id10
e3 | (0,5) | id11
e3 | (0,5) | id12
e3 | (0,5) | id13
```

```
DET &r28 :0 * [L0] :3 * [L1] :2 * [L2] :4 * [L3] :5 * [L4] &r38 :0 :0 L0 :1 L1 END :1 L3 :3 * [L5] &r43 :0 L0 :1 L1 :2 L3 != L5 0 END [&r44]
```

### &r44 (export table 36)

- columns: c0: Example, c1: Color, c2: Ident, c3: Box, c4: Color, c5: Number
- depth 12, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r28, &r36, &r37, &r43, &r44; assignments: 1
- rows per train example: [0, 0, 0]; test: 0; task-wide: 16
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 4 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. a . a . . . . .
. . . . . . . . .
. a . a . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
e0 | 2 | id1 | (2,1) | 4 | 1
e0 | 2 | id1 | (2,3) | 4 | 1
e0 | 2 | id1 | (4,1) | 4 | 1
e0 | 2 | id1 | (4,3) | 4 | 1
```

Task-wide, rows whose Example column is e1: 8 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. . . . . a . a .
. . . . . . . . .
. . . . . a . a .
. . . . . . . . .
. . . . . . . . .
b . b . . . . . .
. . . . . . . . .
b . b . . . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
e1 | 2 | id2 | (6,0) | 4 | 1
e1 | 2 | id2 | (6,2) | 4 | 1
e1 | 2 | id2 | (8,0) | 4 | 1
e1 | 2 | id2 | (8,2) | 4 | 1
e1 | 2 | id5 | (1,5) | 4 | 1
e1 | 2 | id5 | (1,7) | 4 | 1
e1 | 2 | id5 | (3,5) | 4 | 1
e1 | 2 | id5 | (3,7) | 4 | 1
```

Task-wide, rows whose Example column is e2: 4 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Ident, as a letter by first appearance, '.' where no row is:
```
. . . . . . . . .
. a . a . . . . .
. . . . . . . . .
. a . a . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4 | c5
e2 | 2 | id7 | (1,1) | 4 | 1
e2 | 2 | id7 | (1,3) | 4 | 1
e2 | 2 | id7 | (3,1) | 4 | 1
e2 | 2 | id7 | (3,3) | 4 | 1
```

```
RULE &r44 :2 * [L0] diag_dir_elem :0 * [L1] END [&r45]
```

### &r45 (export table 37)

- columns: c0: DiagDir, c1: Color
- depth 13, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r28, &r36, &r37, &r43, &r44; assignments: 1
- rows per train example: [4, 4, 4]; test: 4

Train example 0: 4 rows
```
c0 | c1
DIAG_TL | 2
DIAG_TR | 2
DIAG_BL | 2
DIAG_BR | 2
```

Train example 1: 4 rows
```
c0 | c1
DIAG_TL | 2
DIAG_TR | 2
DIAG_BL | 2
DIAG_BR | 2
```

Train example 2: 4 rows
```
c0 | c1
DIAG_TL | 2
DIAG_TR | 2
DIAG_BL | 2
DIAG_BR | 2
```

```
INIT Ray [:0] OR input :0 * [L0] :1 ^ [L1] &r44 :2 L1 ALSO &r45 :1 L1 :2 * [L2] ALSO &r45 :1 L1 input :0 L0 END END [:1] input :0 * [L3] :1 L1 &r44 :2 L1 END [:0] END [:1] L3 END [:2] &r45 :1 L1 input :0 * [L4] END [:0] END [:1] L4 END [:3] &r45 :1 L1 :2 * [L5] END [:0] END [:1] L5 END [&r46] [&r47] [&r48] [&r49] [&r50]
```

### &r46 (export table 38)

- columns: c0: Color, c1: Box, c2: Dir8, c3: Number, c4: Box
- depth 15, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r28, &r36, &r37, &r43, &r44; assignments: 1
- rows per train example: [16, 30, 16]; test: 30

Train example 0: 16 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . 1 . . .
1 . . . 1 . . . .
. 1 . 1 . . . . .
. . 4 . . . . . .
. 1 . 1 . . . . .
1 . . . 1 . . . .
. . . . . 1 . . .
. . . . . . 1 . .
. . . . . . . 1 .
```
```
c0 | c1 | c2 | c3 | c4
2 | (0,5) | DIAG_TR | 3 | (3,2)
2 | (1,0) | DIAG_TL | 2 | (3,2)
2 | (1,4) | DIAG_TR | 2 | (3,2)
2 | (2,1) | DIAG_TL | 1 | (3,2)
2 | (2,3) | DIAG_TR | 1 | (3,2)
2 | (3,2) | DIAG_TL | 0 | (3,2)
2 | (3,2) | DIAG_TR | 0 | (3,2)
2 | (3,2) | DIAG_BL | 0 | (3,2)
2 | (3,2) | DIAG_BR | 0 | (3,2)
2 | (4,1) | DIAG_BL | 1 | (3,2)
2 | (4,3) | DIAG_BR | 1 | (3,2)
2 | (5,0) | DIAG_BL | 2 | (3,2)
2 | (5,4) | DIAG_BR | 2 | (3,2)
2 | (6,5) | DIAG_BR | 3 | (3,2)
2 | (7,6) | DIAG_BR | 4 | (3,2)
2 | (8,7) | DIAG_BR | 5 | (3,2)
```

Train example 1: 30 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . 1 . . . 2
. . . . . 1 . 2 .
. . . . . . 5 . .
. . . . . 2 . 1 .
. . . . 2 . . . 1
. . . 2 . . . . .
1 . 2 . . . . . .
. 5 . . . . . . .
2 . 1 . . . . . .
```
```
c0 | c1 | c2 | c3 | c4
2 | (0,4) | DIAG_TL | 2 | (2,6)
2 | (0,8) | DIAG_TR | 2 | (2,6)
2 | (0,8) | DIAG_TR | 7 | (7,1)
2 | (1,5) | DIAG_TL | 1 | (2,6)
2 | (1,7) | DIAG_TR | 1 | (2,6)
2 | (1,7) | DIAG_TR | 6 | (7,1)
2 | (2,6) | DIAG_TL | 0 | (2,6)
2 | (2,6) | DIAG_TR | 0 | (2,6)
2 | (2,6) | DIAG_TR | 5 | (7,1)
2 | (2,6) | DIAG_BL | 0 | (2,6)
2 | (2,6) | DIAG_BR | 0 | (2,6)
2 | (3,5) | DIAG_TR | 4 | (7,1)
2 | (3,5) | DIAG_BL | 1 | (2,6)
2 | (3,7) | DIAG_BR | 1 | (2,6)
2 | (4,4) | DIAG_TR | 3 | (7,1)
2 | (4,4) | DIAG_BL | 2 | (2,6)
2 | (4,8) | DIAG_BR | 2 | (2,6)
2 | (5,3) | DIAG_TR | 2 | (7,1)
2 | (5,3) | DIAG_BL | 3 | (2,6)
2 | (6,0) | DIAG_TL | 1 | (7,1)
2 | (6,2) | DIAG_TR | 1 | (7,1)
2 | (6,2) | DIAG_BL | 4 | (2,6)
2 | (7,1) | DIAG_TL | 0 | (7,1)
2 | (7,1) | DIAG_TR | 0 | (7,1)
2 | (7,1) | DIAG_BL | 0 | (7,1)
2 | (7,1) | DIAG_BL | 5 | (2,6)
2 | (7,1) | DIAG_BR | 0 | (7,1)
2 | (8,0) | DIAG_BL | 1 | (7,1)
2 | (8,0) | DIAG_BL | 6 | (2,6)
2 | (8,2) | DIAG_BR | 1 | (7,1)
```

Train example 2: 16 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
1 . . . 1 . . . .
. 1 . 1 . . . . .
. . 4 . . . . . .
. 1 . 1 . . . . .
1 . . . 1 . . . .
. . . . . 1 . . .
. . . . . . 1 . .
. . . . . . . 1 .
. . . . . . . . 1
```
```
c0 | c1 | c2 | c3 | c4
2 | (0,0) | DIAG_TL | 2 | (2,2)
2 | (0,4) | DIAG_TR | 2 | (2,2)
2 | (1,1) | DIAG_TL | 1 | (2,2)
2 | (1,3) | DIAG_TR | 1 | (2,2)
2 | (2,2) | DIAG_TL | 0 | (2,2)
2 | (2,2) | DIAG_TR | 0 | (2,2)
2 | (2,2) | DIAG_BL | 0 | (2,2)
2 | (2,2) | DIAG_BR | 0 | (2,2)
2 | (3,1) | DIAG_BL | 1 | (2,2)
2 | (3,3) | DIAG_BR | 1 | (2,2)
2 | (4,0) | DIAG_BL | 2 | (2,2)
2 | (4,4) | DIAG_BR | 2 | (2,2)
2 | (5,5) | DIAG_BR | 3 | (2,2)
2 | (6,6) | DIAG_BR | 4 | (2,2)
2 | (7,7) | DIAG_BR | 5 | (2,2)
2 | (8,8) | DIAG_BR | 6 | (2,2)
```

### &r47 (export table 39)

- columns: c0: Color, c1: Box, c2: Dir8, c3: Number, c4: Box
- depth 15, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r28, &r36, &r37, &r43, &r44; assignments: 1
- rows per train example: [4, 8, 4]; test: 8

Train example 0: 4 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . 2 . . .
2 . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
2 . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . 2 .
```
```
c0 | c1 | c2 | c3 | c4
2 | (0,5) | DIAG_TR | 3 | (3,2)
2 | (1,0) | DIAG_TL | 2 | (3,2)
2 | (5,0) | DIAG_BL | 2 | (3,2)
2 | (8,7) | DIAG_BR | 5 | (3,2)
```

Train example 1: 8 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . 1 . . . 2
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . 1
. . . . . . . . .
1 . . . . . . . .
. . . . . . . . .
2 . 1 . . . . . .
```
```
c0 | c1 | c2 | c3 | c4
2 | (0,4) | DIAG_TL | 2 | (2,6)
2 | (0,8) | DIAG_TR | 2 | (2,6)
2 | (0,8) | DIAG_TR | 7 | (7,1)
2 | (4,8) | DIAG_BR | 2 | (2,6)
2 | (6,0) | DIAG_TL | 1 | (7,1)
2 | (8,0) | DIAG_BL | 1 | (7,1)
2 | (8,0) | DIAG_BL | 6 | (2,6)
2 | (8,2) | DIAG_BR | 1 | (7,1)
```

Train example 2: 4 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 . . . 2 . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
2 . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . 2
```
```
c0 | c1 | c2 | c3 | c4
2 | (0,0) | DIAG_TL | 2 | (2,2)
2 | (0,4) | DIAG_TR | 2 | (2,2)
2 | (4,0) | DIAG_BL | 2 | (2,2)
2 | (8,8) | DIAG_BR | 6 | (2,2)
```

### &r48 (export table 40)

- columns: c0: Color, c1: Box
- depth 14, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r28, &r36, &r37, &r43, &r44; assignments: 1
- rows per train example: [1, 2, 1]; test: 2

Train example 0: 1 row
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . 2 . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1
2 | (3,2)
```

Train example 1: 2 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . . . . . 2 . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. 2 . . . . . . .
. . . . . . . . .
```
```
c0 | c1
2 | (2,6)
2 | (7,1)
```

Train example 2: 1 row
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. . 2 . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
. . . . . . . . .
```
```
c0 | c1
2 | (2,2)
```

### &r49 (export table 41)

- columns: c0: Color, c1: Box
- depth 14, candidate keys none
- DETs its entries are assigned: &r14, &r15, &r28, &r36, &r37, &r43, &r44; assignments: 1
- rows per train example: [81, 81, 81]; test: 81

Train example 0: 81 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
```
```
c0 | c1
2 | (0,0)
2 | (0,1)
2 | (0,2)
2 | (0,3)
2 | (0,4)
2 | (0,5)
2 | (0,6)
2 | (0,7)
2 | (0,8)
2 | (1,0)
2 | (1,1)
2 | (1,2)
2 | (1,3)
2 | (1,4)
2 | (1,5)
2 | (1,6)
2 | (1,7)
2 | (1,8)
2 | (2,0)
2 | (2,1)
2 | (2,2)
2 | (2,3)
2 | (2,4)
2 | (2,5)
2 | (2,6)
2 | (2,7)
2 | (2,8)
2 | (3,0)
2 | (3,1)
2 | (3,2)
```

Train example 1: 81 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
```
```
c0 | c1
2 | (0,0)
2 | (0,1)
2 | (0,2)
2 | (0,3)
2 | (0,4)
2 | (0,5)
2 | (0,6)
2 | (0,7)
2 | (0,8)
2 | (1,0)
2 | (1,1)
2 | (1,2)
2 | (1,3)
2 | (1,4)
2 | (1,5)
2 | (1,6)
2 | (1,7)
2 | (1,8)
2 | (2,0)
2 | (2,1)
2 | (2,2)
2 | (2,3)
2 | (2,4)
2 | (2,5)
2 | (2,6)
2 | (2,7)
2 | (2,8)
2 | (3,0)
2 | (3,1)
2 | (3,2)
```

Train example 2: 81 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
2 2 2 2 2 2 2 2 2
```
```
c0 | c1
2 | (0,0)
2 | (0,1)
2 | (0,2)
2 | (0,3)
2 | (0,4)
2 | (0,5)
2 | (0,6)
2 | (0,7)
2 | (0,8)
2 | (1,0)
2 | (1,1)
2 | (1,2)
2 | (1,3)
2 | (1,4)
2 | (1,5)
2 | (1,6)
2 | (1,7)
2 | (1,8)
2 | (2,0)
2 | (2,1)
2 | (2,2)
2 | (2,3)
2 | (2,4)
2 | (2,5)
2 | (2,6)
2 | (2,7)
2 | (2,8)
2 | (3,0)
2 | (3,1)
2 | (3,2)
```

```
RULE &r3 :0 * [L0] OR &r31 :0 :0 * [L1] END :1 * [L2] :3 * [L3] &r29 :2 L1 :4 * [L4] ALSO &r46 :0 :0 L1 END :1 L2 :3 L3 &r44 :2 L1 :4 L4 END != L3 0 <= L3 L0 END [&r51]
```

### &r51 (export table 42)

- columns: c0: Color, c1: Number, c2: Color, c3: Box, c4: Number
- depth 16, candidate keys none
- DETs its entries are assigned: &r3, &r14, &r15, &r20, &r21, &r27, &r28, &r29, &r36, &r37, &r43, &r44; assignments: 1
- rows per train example: [8, 16, 8]; test: 12

Train example 0: 8 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . .
. . . . . . . . .
. 1 . 1 . . . . .
. . . . . . . . .
. 1 . 1 . . . . .
. . . . . . 1 . .
. . . . . 1 . 1 .
. . . . . . 1 . .
. . . . . . . . .
```
```
c0 | c1 | c2 | c3 | c4
1 | 1 | 7 | (5,6) | 1
1 | 1 | 7 | (6,5) | 1
1 | 1 | 7 | (6,7) | 1
1 | 1 | 7 | (7,6) | 1
2 | 1 | 4 | (2,1) | 1
2 | 1 | 4 | (2,3) | 1
2 | 1 | 4 | (4,1) | 1
2 | 1 | 4 | (4,3) | 1
```

Train example 1: 16 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . .
. . . . . 1 . 1 .
. . 1 . . . . . .
. 1 . 1 . 1 . 1 .
. . 1 . . . . . .
. . . . . . 1 . .
1 . 1 . . 1 . 1 .
. . . . . . 1 . .
1 . 1 . . . . . .
```
```
c0 | c1 | c2 | c3 | c4
1 | 1 | 7 | (2,2) | 1
1 | 1 | 7 | (3,1) | 1
1 | 1 | 7 | (3,3) | 1
1 | 1 | 7 | (4,2) | 1
1 | 1 | 7 | (5,6) | 1
1 | 1 | 7 | (6,5) | 1
1 | 1 | 7 | (6,7) | 1
1 | 1 | 7 | (7,6) | 1
2 | 1 | 4 | (1,5) | 1
2 | 1 | 4 | (1,7) | 1
2 | 1 | 4 | (3,5) | 1
2 | 1 | 4 | (3,7) | 1
2 | 1 | 4 | (6,0) | 1
2 | 1 | 4 | (6,2) | 1
2 | 1 | 4 | (8,0) | 1
2 | 1 | 4 | (8,2) | 1
```

Train example 2: 8 rows
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the count of rows at the cell, '.' where no row is:
```
. . . . . . . . .
. 1 . 1 . . . . .
. . . . . . . . .
. 1 . 1 . . . . .
. . . . . . . . .
. . . . . . . . .
. . . 1 . . . . .
. . 1 . 1 . . . .
. . . 1 . . . . .
```
```
c0 | c1 | c2 | c3 | c4
1 | 1 | 7 | (6,3) | 1
1 | 1 | 7 | (7,2) | 1
1 | 1 | 7 | (7,4) | 1
1 | 1 | 7 | (8,3) | 1
2 | 1 | 4 | (1,1) | 1
2 | 1 | 4 | (1,3) | 1
2 | 1 | 4 | (3,1) | 1
2 | 1 | 4 | (3,3) | 1
```

```
RULE OR &r51 :2 * [L0] :4 * [L1] ALSO input :0 L0 :1 L1 NOT &r51 :2 L0 END END [&r52]
```

### &r52 (export table 43)

- columns: c0: Color, c1: Box
- depth 17, candidate keys none
- DETs its entries are assigned: &r3, &r14, &r15, &r20, &r21, &r27, &r28, &r29, &r36, &r37, &r43, &r44; assignments: 1
- rows per train example: [81, 81, 81]; test: 81

Train example 0: 81 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0
0 4 0 4 0 0 0 0 0
0 0 2 0 0 0 0 0 0
0 4 0 4 0 0 0 0 0
0 0 0 0 0 0 7 0 0
0 0 0 0 0 7 1 7 0
0 0 0 0 0 0 7 0 0
0 0 0 0 0 0 0 0 0
```
```
c0 | c1
0 | (0,0)
0 | (0,1)
0 | (0,2)
0 | (0,3)
0 | (0,4)
0 | (0,5)
0 | (0,6)
0 | (0,7)
0 | (0,8)
0 | (1,0)
0 | (1,1)
0 | (1,2)
0 | (1,3)
0 | (1,4)
0 | (1,5)
0 | (1,6)
0 | (1,7)
0 | (1,8)
0 | (2,0)
0 | (2,2)
0 | (2,4)
0 | (2,5)
0 | (2,6)
0 | (2,7)
0 | (2,8)
0 | (3,0)
0 | (3,1)
0 | (3,3)
0 | (3,4)
0 | (3,5)
```

Train example 1: 81 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
0 0 0 8 0 0 0 0 0
0 0 0 0 0 4 0 4 0
0 0 7 0 0 0 2 0 0
0 7 1 7 0 4 0 4 0
0 0 7 0 0 0 0 0 0
0 0 0 0 0 0 7 0 0
4 0 4 0 0 7 1 7 0
0 2 0 0 0 0 7 0 0
4 0 4 0 0 0 0 0 0
```
```
c0 | c1
0 | (0,0)
0 | (0,1)
0 | (0,2)
0 | (0,4)
0 | (0,5)
0 | (0,6)
0 | (0,7)
0 | (0,8)
0 | (1,0)
0 | (1,1)
0 | (1,2)
0 | (1,3)
0 | (1,4)
0 | (1,6)
0 | (1,8)
0 | (2,0)
0 | (2,1)
0 | (2,3)
0 | (2,4)
0 | (2,5)
0 | (2,7)
0 | (2,8)
0 | (3,0)
0 | (3,4)
0 | (3,6)
0 | (3,8)
0 | (4,0)
0 | (4,1)
0 | (4,3)
0 | (4,4)
```

Train example 2: 81 rows, the first 30 shown
Drawn on a 9x9 grid, the size of the input grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
0 0 0 0 0 0 0 0 0
0 4 0 4 0 0 0 0 0
0 0 2 0 0 0 0 0 0
0 4 0 4 0 0 0 0 0
0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 6 0 0
0 0 0 7 0 0 0 0 0
0 0 7 1 7 0 0 0 0
0 0 0 7 0 0 0 0 0
```
```
c0 | c1
0 | (0,0)
0 | (0,1)
0 | (0,2)
0 | (0,3)
0 | (0,4)
0 | (0,5)
0 | (0,6)
0 | (0,7)
0 | (0,8)
0 | (1,0)
0 | (1,2)
0 | (1,4)
0 | (1,5)
0 | (1,6)
0 | (1,7)
0 | (1,8)
0 | (2,0)
0 | (2,1)
0 | (2,3)
0 | (2,4)
0 | (2,5)
0 | (2,6)
0 | (2,7)
0 | (2,8)
0 | (3,0)
0 | (3,2)
0 | (3,4)
0 | (3,5)
0 | (3,6)
0 | (3,7)
```

## What I see

The task: a 1 dot grows a plus of 7s, a 2 dot grows an x of 4s, one step out; dots of other colors (6, 8) do nothing. The program first reads the train pairs through DETs (&r14 to &r29, then &r36 to &r44), then applies what they find (&r30 to &r35, &r45 to &r52). Each table has one assignment. The DET tables are task-wide, with an Example column that also holds the test input (e3).

- **&r0** (Cardinality of ex_input by color): task-wide counts over all four inputs, `0 | 309`, `1 | 5`, `2 | 6`, `6 | 2`, `8 | 2`. An aggregate with Color as its key.
- **&r3** (DivisorRatio): one row, 1. From the table I can't say what the 1 is. The final RULE (&r51) reads it as the arms' reach (`<= L3 L0`).
- **&r4 to &r9** (Order over &r0's counts): ascending and descending ranks (&r4, &r5), the least-counted colors 6, 8 (&r6), the most-counted color 0 (&r7, the ground), and the successor pairs (&r8; &r9 adds `0 | 6` and `0 | 8` for the tie). Each is a function of &r0's count column. They add only the name of the ground color, which is what the next clause reads.
- **&r14** (DET: input cells not of &r7's color): the dots, 2/5/3/5 per example, test included. A selection: 15 rows in place of 324 cells.
- **&r15** (DET: output cells whose color differs from the input's): 8/16/8 cells, drawn as pluses and xs. This is the first table that holds information from the outputs. Every row has input color 0 and output color 4 or 7.
- **&r16** (Components8 over &r14's and &r15's cells): each star joined with its dot. In e1, `c` is the plus around the 1 at (3,2), `e` the x around the 2 at (7,1), and `a`, the 8 at (0,3), stands alone. In e2, `b`, the 6, stands alone. **&r18** restates &r16 without the Ident, and **&r19** is the eight step offsets, a constant.
- **&r20** (DET: each dot's component), **&r36** (the same clause again): &r14's cells with the Ident, a restatement with a key. **&r21, &r37**: &r20 x 4 directions (cardinal, diagonal), 8/20/12/20 rows, a product.
- **&r22 to &r27** (Ray from each dot in the four cardinal directions): &r22 has 300 rows, every cell on each dot's row and column with its step count, drawn as crosses to the grid's edges. Its rows follow from &r20 and the grid size: a closure of the grid's step inside the grid. &r23 is the ray ends at the grid's edges, and &r24 the marks, which restate &r20. **&r25, &r27** have 1215 rows: dots x 81 cells. The drawing shows the count of dots (2, 5, 3, 5) at every cell, which marks a product of &r20 with the grid, the Ray.node idiom. **&r38 to &r43** do the same for the diagonals (230 and 1215 rows). The four 1215-row tables &r25, &r27, &r41, &r43 hold equal rows, and so do &r20, &r24, &r36, &r40.
- **&r28** (DET: each star cell with its dot, offset, mark color and paint color): 32 rows, one per &r15 cell, for example `e0 | (3,2) | (2,1) | +(-1,-1) | 2 | 4` and `e0 | (6,6) | (5,6) | +(-1,0) | 1 | 7`. Mark color to paint color is a functional dependency, 2 to 4 and 1 to 7, in every row. The 6 and 8 dots have no rows, so the table shows they are inert.
- **&r29** (DET: &r28's rows on a cardinal ray at K != 0): 16 rows, all with mark 1 and paint 7. Its value as a DET is the one row (1, 7). **&r44** does the same on the diagonals: (2, 4). These two rows are the rule's parameters. The information about the rule jumps from &r15 to &r28, and &r29 and &r44 reduce it to two rows.
- **&r30, &r45** (RULE: the directions of a mark color): 4 rows, equal in every example. A product of &r29's (or &r44's) mark color with the 4 directions.
- **&r31 to &r35** (Ray from the input's 1 cells): **&r31** is the crosses to the edges (20/40/20 rows) and **&r32** their ends. **&r33** is the 1 cells, a selection of the input. **&r34** is 81 rows of color 1, one at every cell: a product of the color with the grid. &r31 and &r34 hold nothing beyond &r33 and the grid. **&r46 to &r50** do the same for the 2 cells on the diagonals.
- **&r51** (painted: ray cells with 0 < K <= &r3): 8/16/8 cells with the paint color, the same cells as &r15's at every train example. This is where the applied side gets the rule: the 300- and 230-row rays are selected down to 32 rows by K <= 1.
- **&r52** (out): 81 rows per example, equal to the output grids.

Rows that look like noise: &r25, &r27, &r41, &r43 (1215 rows each) and &r34, &r49 (81 rows each), products with the grid; &r22, &r38, &r31, &r46, rays to the grid's edge of which later clauses keep only the rows at K = 1 (&r29 and &r44 by the join with &r28, &r51 by K <= &r3); the restatements &r18, &r24, &r36, &r40; the per-example constants &r30, &r45. By row count, most of the case's rows are in these tables.
