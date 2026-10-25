# 44f52bb0, case `$Direct`

- concept case: True; tokens: 411; tables: 21 relations, 21 per assignment
- cells: a Position is `(row,col)` of the example's input grid (`(row,col)out` where it fits only the output grid), an Offset `+(drow,dcol)`, another Box `rR0-R1 cC0-C1` over the input grid or `[t b l r]` margins; an Ident is `id<n>`, equal only within one case; see README.md

## Grids

### Train example 0: input 3x3, output 1x1

```
input    output
2 0 2    1
0 2 0
2 0 2
```

### Train example 1: input 3x3, output 1x1

```
input    output
2 0 0    7
2 0 0
0 2 0
```

### Train example 2: input 3x3, output 1x1

```
input    output
2 0 2    1
2 0 2
2 0 2
```

### Train example 3: input 3x3, output 1x1

```
input    output
0 0 0    1
2 0 2
0 0 0
```

### Train example 4: input 3x3, output 1x1

```
input    output
2 2 0    7
0 2 2
0 0 0
```

### Train example 5: input 3x3, output 1x1

```
input    output
2 2 0    7
0 2 0
0 0 0
```

### Test example 0: input 3x3

```
2 0 2
2 2 2
2 0 2
```

### Test example 1: input 3x3

```
0 0 0
2 0 0
2 0 0
```

## Program and tables

Model-written tokens plain, engine-written ones in [brackets]. Each clause is followed by the tables of the relations it declares. A table whose entries hold several DET assignments is given once per assignment, each marked with the values, at that assignment, of the DETs whose value differs between them; a DET's value is the rows of its own table at that assignment.

```
INIT Agreement [:0] SKIP [:1] input :0 * [L0] :1 * [L1] END [:0] END [:1] L0 END [:2] L1 END [:2] input :0 * [L2] :1 * [L3] END [:0] END [:1] L2 END [:2] L3 END [:3] SKIP [&r0] [&r1] [&r2] [&r3] [&r4]
```

### &r0 (export table 2)

- columns: c0: D4
- depth 2, candidate keys none
- rows per train example: [0, 7, 4, 4, 7, 7]; test: 11

Train example 0: 0 rows

Train example 1: 7 rows
```
c0
D4_CW
D4_HT
D4_CC
D4_LR
D4_TB
D4_DG
D4_AD
```

Train example 2: 4 rows
```
c0
D4_CW
D4_CC
D4_DG
D4_AD
```

Train example 3: 4 rows
```
c0
D4_CW
D4_CC
D4_DG
D4_AD
```

Train example 4: 7 rows
```
c0
D4_CW
D4_HT
D4_CC
D4_LR
D4_TB
D4_DG
D4_AD
```

Train example 5: 7 rows
```
c0
D4_CW
D4_HT
D4_CC
D4_LR
D4_TB
D4_DG
D4_AD
```

### &r1 (export table 3)

- columns: c0: D4
- depth 2, candidate keys none
- rows per train example: [0, 7, 4, 4, 7, 7]; test: 11

Train example 0: 0 rows

Train example 1: 7 rows
```
c0
D4_CW
D4_HT
D4_CC
D4_LR
D4_TB
D4_DG
D4_AD
```

Train example 2: 4 rows
```
c0
D4_CW
D4_CC
D4_DG
D4_AD
```

Train example 3: 4 rows
```
c0
D4_CW
D4_CC
D4_DG
D4_AD
```

Train example 4: 7 rows
```
c0
D4_CW
D4_HT
D4_CC
D4_LR
D4_TB
D4_DG
D4_AD
```

Train example 5: 7 rows
```
c0
D4_CW
D4_HT
D4_CC
D4_LR
D4_TB
D4_DG
D4_AD
```

```
INIT Agreement [:0] ex_input :0 ^ [L0] :1 * [L1] :2 * [L2] END [:1] ex_input :0 L0 :1 * [L3] :2 * [L4] END [:0] END [:1] L3 END [:2] L4 END [:2] ex_input :0 L0 :1 * [L5] :2 * [L6] END [:0] END [:1] L5 END [:2] L6 END [:3] SKIP [:3] SKIP [&r5] [&r6] [&r7] [&r8] [&r9]
```

### &r5 (export table 4)

- columns: c0: Example, c1: D4
- depth 2, candidate keys none
- rows per train example: [0, 0, 0, 0, 0, 0]; test: 0; task-wide: 40
- every row is of a task-wide entry

Task-wide, rows whose Example column is e1: 7 rows
```
c0 | c1
e1 | D4_CW
e1 | D4_HT
e1 | D4_CC
e1 | D4_LR
e1 | D4_TB
e1 | D4_DG
e1 | D4_AD
```

Task-wide, rows whose Example column is e2: 4 rows
```
c0 | c1
e2 | D4_CW
e2 | D4_CC
e2 | D4_DG
e2 | D4_AD
```

Task-wide, rows whose Example column is e3: 4 rows
```
c0 | c1
e3 | D4_CW
e3 | D4_CC
e3 | D4_DG
e3 | D4_AD
```

Task-wide, rows whose Example column is e4: 7 rows
```
c0 | c1
e4 | D4_CW
e4 | D4_HT
e4 | D4_CC
e4 | D4_LR
e4 | D4_TB
e4 | D4_DG
e4 | D4_AD
```

Task-wide, rows whose Example column is e5: 7 rows
```
c0 | c1
e5 | D4_CW
e5 | D4_HT
e5 | D4_CC
e5 | D4_LR
e5 | D4_TB
e5 | D4_DG
e5 | D4_AD
```

Task-wide, rows whose Example column is e6: 4 rows
```
c0 | c1
e6 | D4_CW
e6 | D4_CC
e6 | D4_DG
e6 | D4_AD
```

Task-wide, rows whose Example column is e7: 7 rows
```
c0 | c1
e7 | D4_CW
e7 | D4_HT
e7 | D4_CC
e7 | D4_LR
e7 | D4_TB
e7 | D4_DG
e7 | D4_AD
```

### &r6 (export table 5)

- columns: c0: Example, c1: D4
- depth 2, candidate keys none
- rows per train example: [0, 0, 0, 0, 0, 0]; test: 0; task-wide: 40
- every row is of a task-wide entry

Task-wide, rows whose Example column is e1: 7 rows
```
c0 | c1
e1 | D4_CW
e1 | D4_HT
e1 | D4_CC
e1 | D4_LR
e1 | D4_TB
e1 | D4_DG
e1 | D4_AD
```

Task-wide, rows whose Example column is e2: 4 rows
```
c0 | c1
e2 | D4_CW
e2 | D4_CC
e2 | D4_DG
e2 | D4_AD
```

Task-wide, rows whose Example column is e3: 4 rows
```
c0 | c1
e3 | D4_CW
e3 | D4_CC
e3 | D4_DG
e3 | D4_AD
```

Task-wide, rows whose Example column is e4: 7 rows
```
c0 | c1
e4 | D4_CW
e4 | D4_HT
e4 | D4_CC
e4 | D4_LR
e4 | D4_TB
e4 | D4_DG
e4 | D4_AD
```

Task-wide, rows whose Example column is e5: 7 rows
```
c0 | c1
e5 | D4_CW
e5 | D4_HT
e5 | D4_CC
e5 | D4_LR
e5 | D4_TB
e5 | D4_DG
e5 | D4_AD
```

Task-wide, rows whose Example column is e6: 4 rows
```
c0 | c1
e6 | D4_CW
e6 | D4_CC
e6 | D4_DG
e6 | D4_AD
```

Task-wide, rows whose Example column is e7: 7 rows
```
c0 | c1
e7 | D4_CW
e7 | D4_HT
e7 | D4_CC
e7 | D4_LR
e7 | D4_TB
e7 | D4_DG
e7 | D4_AD
```

```
DET ex_output :0 * [L0] END [&r10]
```

### &r10 (export table 6)

- columns: c0: Example
- depth 1, candidate keys none
- DETs its entries are assigned: &r10; assignments: 1
- rows per train example: [0, 0, 0, 0, 0, 0]; test: 0; task-wide: 6
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 1 row
```
c0
e0
```

Task-wide, rows whose Example column is e1: 1 row
```
c0
e1
```

Task-wide, rows whose Example column is e2: 1 row
```
c0
e2
```

Task-wide, rows whose Example column is e3: 1 row
```
c0
e3
```

Task-wide, rows whose Example column is e4: 1 row
```
c0
e4
```

Task-wide, rows whose Example column is e5: 1 row
```
c0
e5
```

```
DET ex_output :0 * [L0] :1 * [L1] :2 * [L2] END [&r11]
```

### &r11 (export table 7)

- columns: c0: Example, c1: Box, c2: Color
- depth 1, candidate keys none
- DETs its entries are assigned: &r11; assignments: 1
- rows per train example: [0, 0, 0, 0, 0, 0]; test: 0; task-wide: 6
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1
```
```
c0 | c1 | c2
e0 | (0,0)out | 1
```

Task-wide, rows whose Example column is e1: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
7
```
```
c0 | c1 | c2
e1 | (0,0)out | 7
```

Task-wide, rows whose Example column is e2: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1
```
```
c0 | c1 | c2
e2 | (0,0)out | 1
```

Task-wide, rows whose Example column is e3: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1
```
```
c0 | c1 | c2
e3 | (0,0)out | 1
```

Task-wide, rows whose Example column is e4: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
7
```
```
c0 | c1 | c2
e4 | (0,0)out | 7
```

Task-wide, rows whose Example column is e5: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
7
```
```
c0 | c1 | c2
e5 | (0,0)out | 7
```

```
INIT Inclusion [:0] SKIP [:1] &r11 :0 * [L0] :1 * [L1] :2 * [L2] END [:0] L0 END [:1] :0 L1 :1 L2 END END [:2] &r11 :0 * [L3] :1 * [L4] :2 * [L5] END [:0] L3 END [:1] :0 L4 :1 L5 END END [&r12] [&r13] [&r14] [&r15]
```

### &r12 (export table 8)

- columns: c0: Example, c1: Example
- depth 3, candidate keys none
- DETs its entries are assigned: &r11; assignments: 1
- rows per train example: [0, 0, 0, 0, 0, 0]; test: 0; task-wide: 18
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 3 rows
```
c0 | c1
e0 | e0
e0 | e2
e0 | e3
```

Task-wide, rows whose Example column is e1: 3 rows
```
c0 | c1
e1 | e1
e1 | e4
e1 | e5
```

Task-wide, rows whose Example column is e2: 3 rows
```
c0 | c1
e2 | e0
e2 | e2
e2 | e3
```

Task-wide, rows whose Example column is e3: 3 rows
```
c0 | c1
e3 | e0
e3 | e2
e3 | e3
```

Task-wide, rows whose Example column is e4: 3 rows
```
c0 | c1
e4 | e1
e4 | e4
e4 | e5
```

Task-wide, rows whose Example column is e5: 3 rows
```
c0 | c1
e5 | e1
e5 | e4
e5 | e5
```

### &r13 (export table 9)

- columns: c0: Example, c1: Example
- depth 3, candidate keys none
- DETs its entries are assigned: &r11; assignments: 1
- rows per train example: [0, 0, 0, 0, 0, 0]; test: 0; task-wide: 18
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 3 rows
```
c0 | c1
e0 | e0
e0 | e2
e0 | e3
```

Task-wide, rows whose Example column is e1: 3 rows
```
c0 | c1
e1 | e1
e1 | e4
e1 | e5
```

Task-wide, rows whose Example column is e2: 3 rows
```
c0 | c1
e2 | e0
e2 | e2
e2 | e3
```

Task-wide, rows whose Example column is e3: 3 rows
```
c0 | c1
e3 | e0
e3 | e2
e3 | e3
```

Task-wide, rows whose Example column is e4: 3 rows
```
c0 | c1
e4 | e1
e4 | e4
e4 | e5
```

Task-wide, rows whose Example column is e5: 3 rows
```
c0 | c1
e5 | e1
e5 | e4
e5 | e5
```

```
DET &r10 :0 * [L0] &r10 :0 * [L1] NOT &r13 :0 L0 :1 L1 END [&r16]
```

### &r16 (export table 10)

- columns: c0: Example, c1: Example
- depth 4, candidate keys none
- DETs its entries are assigned: &r10, &r11, &r16; assignments: 1
- rows per train example: [0, 0, 0, 0, 0, 0]; test: 0; task-wide: 18
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 3 rows
```
c0 | c1
e0 | e1
e0 | e4
e0 | e5
```

Task-wide, rows whose Example column is e1: 3 rows
```
c0 | c1
e1 | e0
e1 | e2
e1 | e3
```

Task-wide, rows whose Example column is e2: 3 rows
```
c0 | c1
e2 | e1
e2 | e4
e2 | e5
```

Task-wide, rows whose Example column is e3: 3 rows
```
c0 | c1
e3 | e1
e3 | e4
e3 | e5
```

Task-wide, rows whose Example column is e4: 3 rows
```
c0 | c1
e4 | e0
e4 | e2
e4 | e3
```

Task-wide, rows whose Example column is e5: 3 rows
```
c0 | c1
e5 | e0
e5 | e2
e5 | e3
```

```
DET OR ex_input :0 * [L0] d4_elem :0 * [L1] NOT &r5 :0 :0 L0 END :1 L1 ex_input :0 * [L2] d4_elem :0 L1 NOT &r5 :0 :0 L2 END :1 L1 &r16 :0 L0 :1 L2 ALSO &r5 :0 :0 * [L3] END :1 L1 &r5 :0 :0 * [L4] END :1 L1 &r16 :0 L3 :1 L4 END END [&r17]
```

### &r17 (export table 11)

- columns: c0: D4
- depth 5, candidate keys none
- DETs its entries are assigned: &r10, &r11, &r16, &r17; assignments: 1
- rows per train example: [0, 0, 0, 0, 0, 0]; test: 0; task-wide: 5
- every row is of a task-wide entry

Task-wide: 5 rows
```
c0
D4_ID
D4_CW
D4_CC
D4_DG
D4_AD
```

```
DET d4_elem :0 * [L0] NOT &r17 :0 L0 &r5 :0 :0 * [L1] END :1 L0 END [&r18]
```

### &r18 (export table 12)

- columns: c0: D4, c1: Example
- depth 6, candidate keys none
- DETs its entries are assigned: &r10, &r11, &r16, &r17, &r18; assignments: 1
- rows per train example: [0, 0, 0, 0, 0, 0]; test: 0; task-wide: 12
- every row is of a task-wide entry

Task-wide, rows whose Example column is e1: 3 rows
```
c0 | c1
D4_HT | e1
D4_LR | e1
D4_TB | e1
```

Task-wide, rows whose Example column is e4: 3 rows
```
c0 | c1
D4_HT | e4
D4_LR | e4
D4_TB | e4
```

Task-wide, rows whose Example column is e5: 3 rows
```
c0 | c1
D4_HT | e5
D4_LR | e5
D4_TB | e5
```

Task-wide, rows whose Example column is e7: 3 rows
```
c0 | c1
D4_HT | e7
D4_LR | e7
D4_TB | e7
```

```
DET &r10 :0 * [L0] NOT &r18 :1 L0 &r5 :0 :0 L0 END :1 * [L1] END [&r19]
```

### &r19 (export table 13)

- columns: c0: Example, c1: D4
- depth 7, candidate keys none
- DETs its entries are assigned: &r10, &r11, &r16, &r17, &r18, &r19; assignments: 1
- rows per train example: [0, 0, 0, 0, 0, 0]; test: 0; task-wide: 8
- every row is of a task-wide entry

Task-wide, rows whose Example column is e2: 4 rows
```
c0 | c1
e2 | D4_CW
e2 | D4_CC
e2 | D4_DG
e2 | D4_AD
```

Task-wide, rows whose Example column is e3: 4 rows
```
c0 | c1
e3 | D4_CW
e3 | D4_CC
e3 | D4_DG
e3 | D4_AD
```

```
INIT Inclusion [:0] SKIP [:1] sym_member :0 * [L0] :1 * [L1] END [:0] L0 END [:1] L1 END [:2] d4_elem :0 * [L2] NOT &r19 :1 L2 END [:0] END [:1] L2 END [&r20] [&r21] [&r22] [&r23]
```

### &r20 (export table 14)

- columns: c1: Sym
- depth 9, candidate keys none
- DETs its entries are assigned: &r10, &r11, &r16, &r17, &r18, &r19; assignments: 1
- rows per train example: [0, 0, 0, 0, 0, 0]; test: 0; task-wide: 5
- every row is of a task-wide entry

Task-wide: 5 rows
```
c1
SYM_1
SYM_LR
SYM_TB
SYM_HT
SYM_BOX
```

### &r21 (export table 15)

- columns: c1: Sym
- depth 9, candidate keys none
- DETs its entries are assigned: &r10, &r11, &r16, &r17, &r18, &r19; assignments: 1
- rows per train example: [0, 0, 0, 0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
c1
SYM_BOX
```

### &r22 (export table 16)

- columns: c0: Sym, c1: D4
- depth 1, candidate keys none
- rows per train example: [0, 0, 0, 0, 0, 0]; test: 0; task-wide: 31
- every row is of a task-wide entry

Task-wide: 31 rows, the first 30 shown
```
c0 | c1
SYM_1 | D4_ID
SYM_LR | D4_ID
SYM_LR | D4_LR
SYM_TB | D4_ID
SYM_TB | D4_TB
SYM_HT | D4_ID
SYM_HT | D4_HT
SYM_DG | D4_ID
SYM_DG | D4_DG
SYM_AD | D4_ID
SYM_AD | D4_AD
SYM_BOX | D4_ID
SYM_BOX | D4_HT
SYM_BOX | D4_LR
SYM_BOX | D4_TB
SYM_X | D4_ID
SYM_X | D4_HT
SYM_X | D4_DG
SYM_X | D4_AD
SYM_C4 | D4_ID
SYM_C4 | D4_CW
SYM_C4 | D4_HT
SYM_C4 | D4_CC
SYM_D4 | D4_ID
SYM_D4 | D4_CW
SYM_D4 | D4_HT
SYM_D4 | D4_CC
SYM_D4 | D4_LR
SYM_D4 | D4_TB
SYM_D4 | D4_DG
```

### &r23 (export table 17)

- columns: c1: D4
- depth 8, candidate keys none
- DETs its entries are assigned: &r10, &r11, &r16, &r17, &r18, &r19; assignments: 1
- rows per train example: [0, 0, 0, 0, 0, 0]; test: 0; task-wide: 4
- every row is of a task-wide entry

Task-wide: 4 rows
```
c1
D4_ID
D4_HT
D4_LR
D4_TB
```

```
DET &r21 :1 * [L0] END [&r24]
```

### &r24 (export table 18)

- columns: c0: Sym
- depth 10, candidate keys none
- DETs its entries are assigned: &r10, &r11, &r16, &r17, &r18, &r19, &r24; assignments: 1
- rows per train example: [0, 0, 0, 0, 0, 0]; test: 0; task-wide: 1
- every row is of a task-wide entry

Task-wide: 1 row
```
c0
SYM_BOX
```

```
RULE &r0 :1 * [L0] &r24 :0 * [L1] sym_member :0 L1 :1 L0 END [&r25]
```

### &r25 (export table 19)

- columns: c0: Sym, c1: D4
- depth 11, candidate keys none
- DETs its entries are assigned: &r10, &r11, &r16, &r17, &r18, &r19, &r24; assignments: 1
- rows per train example: [0, 3, 0, 0, 3, 3]; test: 3

Train example 0: 0 rows

Train example 1: 3 rows
```
c0 | c1
SYM_BOX | D4_HT
SYM_BOX | D4_LR
SYM_BOX | D4_TB
```

Train example 2: 0 rows

Train example 3: 0 rows

Train example 4: 3 rows
```
c0 | c1
SYM_BOX | D4_HT
SYM_BOX | D4_LR
SYM_BOX | D4_TB
```

Train example 5: 3 rows
```
c0 | c1
SYM_BOX | D4_HT
SYM_BOX | D4_LR
SYM_BOX | D4_TB
```

```
DET ex_output :0 * [L0] :1 * [L1] :2 * [L2] NOT &r18 :1 L0 END [&r26]
```

### &r26 (export table 20)

- columns: c0: Example, c1: Box, c2: Color
- depth 7, candidate keys none
- DETs its entries are assigned: &r10, &r11, &r16, &r17, &r18, &r26; assignments: 1
- rows per train example: [0, 0, 0, 0, 0, 0]; test: 0; task-wide: 3
- every row is of a task-wide entry

Task-wide, rows whose Example column is e0: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1
```
```
c0 | c1 | c2
e0 | (0,0)out | 1
```

Task-wide, rows whose Example column is e2: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1
```
```
c0 | c1 | c2
e2 | (0,0)out | 1
```

Task-wide, rows whose Example column is e3: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1
```
```
c0 | c1 | c2
e3 | (0,0)out | 1
```

```
DET ex_output :0 * [L0] :1 * [L1] :2 * [L2] &r18 :1 L0 END [&r27]
```

### &r27 (export table 21)

- columns: c0: Example, c1: Box, c2: Color
- depth 7, candidate keys none
- DETs its entries are assigned: &r10, &r11, &r16, &r17, &r18, &r27; assignments: 1
- rows per train example: [0, 0, 0, 0, 0, 0]; test: 0; task-wide: 3
- every row is of a task-wide entry

Task-wide, rows whose Example column is e1: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
7
```
```
c0 | c1 | c2
e1 | (0,0)out | 7
```

Task-wide, rows whose Example column is e4: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
7
```
```
c0 | c1 | c2
e4 | (0,0)out | 7
```

Task-wide, rows whose Example column is e5: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
7
```
```
c0 | c1 | c2
e5 | (0,0)out | 7
```

```
RULE OR &r26 :1 * [L0] :2 * [L1] NOT &r25 ALSO &r27 :1 L0 :2 L1 &r25 END END [&r28]
```

### &r28 (export table 22)

- columns: c0: Box, c1: Color
- depth 12, candidate keys none
- DETs its entries are assigned: &r10, &r11, &r16, &r17, &r18, &r19, &r24, &r26, &r27; assignments: 1
- rows per train example: [1, 1, 1, 1, 1, 1]; test: 2

Train example 0: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1
```
```
c0 | c1
(0,0)out | 1
```

Train example 1: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
7
```
```
c0 | c1
(0,0)out | 7
```

Train example 2: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1
```
```
c0 | c1
(0,0)out | 1
```

Train example 3: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
1
```
```
c0 | c1
(0,0)out | 1
```

Train example 4: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
7
```
```
c0 | c1
(0,0)out | 7
```

Train example 5: 1 row
Drawn on a 1x1 grid, the size of the output grid, by the first Box column; each cell shows the row's Color, '.' where no row is:
```
7
```
```
c0 | c1
(0,0)out | 7
```

## What I see

The task: a 3x3 input gives the 1x1 output 1 if both mirror flips leave it unchanged (and so the half turn also does), and 7 otherwise. e0, e2 and e3 give 1. e1, e4 and e5 give 7. In the task-wide entries, e6 and e7 are the two test inputs. Each table has one assignment.

- **&r0, &r1** (D4Map's Agreement of the input with itself: the transforms under which the input differs from itself): equal rows. One source fills both inputs, so the two outputs restate each other. The rows already split the examples as the outputs do. e0 has 0 rows, because every D4 transform leaves it unchanged. e2 and e3 have 4 rows, {CW, CC, DG, AD}, and lack HT, LR and TB. e1, e4 and e5 have all 7 rows other than D4_ID. The signal is the elements that are absent, and the entry with the most information, e0's, is empty.
- **&r5, &r6** (the same Agreement per Example, task-wide): &r0's rows with an Example column, plus the test inputs. e6 (the H shape) has the 4 rows of the "1" class, and e7 has the 7 rows of the "7" class. On the train side, this is a restatement of &r0. On the test side, it is the first table that shows a test input's class.
- **&r10** (DET: the train examples): e0 to e5. No signal. It is the domain that &r16 reads.
- **&r11** (DET: the output grids): 1, 7, 1, 1, 7, 7. The first table from the outputs.
- **&r12, &r13** (Inclusion of each output in each other output: covers and equals): equal rows, 18 each. The outputs are all 1x1, so covers and equals give the same pairs, and one restates the other. The signal is the partition {e0, e2, e3}, {e1, e4, e5}, written as pairs with the diagonal: 18 rows for what a class label gives in 6 (the derivability test "order or class as pairs").
- **&r16** (DET: pairs of examples whose outputs differ): the 18 pairs across the two classes. This is the complement of &r13 inside &r10 x &r10, so it adds no signal beyond &r13 and &r10.
- **&r17** (DET: the transforms that do not split the classes): ID, CW, CC, DG, AD. **The signal jumps here.** The three absent transforms, HT, LR and TB, carry the classification. As in 3ac3eb23 &r3, the information is in what the table lacks.
- **&r18** (DET: each class-carrying transform with the examples it breaks): HT, LR, TB x {e1, e4, e5, e7}. This is a product, and the information is in its factors. The Example factor is the "7" class, and it holds the test input e7. So from this table alone, test 1's answer is 7.
- **&r19** (DET: the mismatches of the "1" class): e2 and e3 with {CW, CC, DG, AD}. A selection of &r5. e0 is absent because it has no mismatch, so this table does not show e0 as a member of the class.
- **&r23, &r20, &r21, &r22** (Inclusion of each named subgroup against the transforms that no "1" example breaks): &r23 is the observed set {ID, HT, LR, TB}. &r20 holds the 5 subgroups that the set covers (SYM_1, LR, TB, HT, BOX), and &r21 holds the one that it equals, SYM_BOX. &r22 restates the lib's `sym_member` fact in 31 rows and adds no signal. &r21 reduces the rows to one and gives the group a name, as 3ac3eb23 &r4 does. &r24 (DET) restates &r21.
- **&r25** (RULE: the input's mismatches that are members of SYM_BOX): HT, LR and TB in e1, e4 and e5. The table is empty in e0, e2 and e3. On the applied side, this is the classifier, and the examples where it is empty are the ones whose answer is 1. Here, "empty in some examples" is the rule itself, and it does not question the step's viability.
- **&r26, &r27** (DET: the output of each class): (0,0)out with 1 for e0, e2, e3 and with 7 for e1, e4, e5. Each one is a selection of &r11 by &r18, and together they give the functional dependency of class to color.
- **&r28** (out): 1 where &r25 is empty, 7 where it is not. Equal to the outputs.

Rows that look like noise: &r1, &r6 and &r13 (twin outputs of one lib instance), &r16 (a complement), &r18 (a product), &r22 (a lib fact) and &r24. The signal about the rule jumps at &r17, where the three flips drop out. A reader who has the outputs beside &r0 can see the rule there already.
