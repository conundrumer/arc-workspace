# `LineBands<Key, Val>` — the bands an axis's lines form where neighbors agree

The partition of a frame's lines into maximal runs of adjacent lines that carry the same value at every place across, per key: a region of solid blocks whose rows and columns differ in width reads as one band index per axis, and a caller that ranks the bands recovers the layout with one cell per block. The cells are the caller's, and every cell it feeds enters the comparison, so a line the caller leaves out cuts nothing.

Code form (plain relations, as a solver writes it):

```
// A region cell by its line on axis a and its place across that line.
.decl line_cell(a: Axis, p_line: Position, p_across: Position, col: Color)
line_cell(A, L, X, Col) :- region(P, Col), axis_elem(A), split(P, A, L, X).

// Two lines that hold different colors at one place across.
.decl differ(a: Axis, p_line: Position, p_line2: Position)
differ(A, L, L2) :- line_cell(A, L, X, Col), line_cell(A, L2, X, Col2), Col != Col2.

// Neighboring lines that agree everywhere: no boundary between them.
.decl uncut(x: Line, y: Line)
uncut([A, L], [A, L2]) :-
    line(A, L), line(A, L2), axis_of(D, A), neighbor(L, D, L2), !differ(A, L, L2).

.init bands = Canon<Line>
bands.equiv([A, L], [A, L]) :- line(A, L).
bands.equiv(X, Z) :- bands.equiv(X, Y), uncut(Y, Z).
```

Not: maximal runs of cells inside one line (`Runs`); the one color a whole line holds (`LineColor`); the lines a cell set covers whole (`LineCover`); the closure alone, which `Transitive` states and `Canon` consumes; connected components of a cell set, where adjacency alone joins them (`Components`); the equal tiles a dividing lattice cuts (`divide`, `Tile2D`, `DividerTiles`); per-tile offsets for tiles of unequal size (`ConcatPipeline`, closed); the line pairs one shift of a lattice breaks, which compares only where both cells exist and reports no partition (`OffsetInvariance.line_mismatch`).

Match: a rule with one line-valued-cell relation twice positive, the two occurrences sharing the across position and disagreeing on the value, whose head keeps the two line positions; and a second rule that negates that head under an adjacency of the same two lines (`neighbor`, `jump`, or a `dist` comparison on the axis), feeding `Canon.equiv`, `Components.node`, or an `Order`/`OrderFrame` over lines. Also the positive statement of the same test, where a rule derives line agreement from a per-line defect it negates once and the caller ranks the result. State the shape with the parser (`tests/test_ast_match.py`): the line comparison has no lexical anchor, and the value column may be any type.

Survey: 2026-09-12 19:44 — every solver.

Callers:
90c28cc7 `differ`/`uncut`/`bands` — partitions the region's rows and its columns into maximal runs of neighboring lines that hold the same color at every place across, and ranks those bands into the block layout.
80214e03 `separated($Contrast())`/`block_line` — fuses two touching content lines unless some place across holds differently colored cells on the two lines, then ranks the fused lines into a tile frame; the blocks' bg holes hold no cell, so those places compare nothing and cut nothing.
e1baa8a4 `boundary`/`bands` — marks a line whose neighbor toward an edge carries a different color at some place across, and counts the marks at or inside a line to get that line's band index on the axis.

Negative evidence over the scope: three signatures ran over every parsed solver. The line-comparison shape — one relation twice positive, one argument pair under a disequality, another pair of distinct variables kept in the head — matched 21 rules in 17 solvers. The adjacency half — an adjacency atom over two variables with a negated atom over that same pair — matched 4 rules in 4 solvers, and `90c28cc7 uncut` is the only one over lines. The two-cell statement of the comparison — two `split` atoms on one axis, a disequality, both line variables in the head — matched one rule, `80214e03 separated`. A lexical sweep for band, boundary, separator, collapse, and fuse language added `e1baa8a4 boundary` and the near-misses below.

Near-misses:
1190e5a7 `bands`, with its family sibling 7039b2d7 `bands` — the band is a run of adjacent lines that pass a per-line test (the line is not filled by one color), so the entry's LineColor exclusion rules it out; two adjacent non-divider lines fuse there whatever they hold across.
458e3a53 `line_color`/`tiles` and 8e1813be `stripe` — the same per-line color test, feeding a divider lattice and a stripe order; LineColor again.
22a4bbc2 `boundary` and 80214e03 `separated($Content())` — the band breaks where the neighbor line's color set differs from the line's, the second through `KeyedSetCompare`. The test reads each line's set of colors, not its value at each place across, so LineColor excludes both. The other case of 80214e03 is a caller.
0a1d4ef5 `runs`/`cls` — the band is a run of occupied lines, or a class of rectangles whose spans share a line. Occupancy and span overlap decide it, and no value is compared across two lines.
2dc579da `differs`, 4e34c42c `disagree`, 16b78196 `clash`, 446ef5d2 `clash`, 73251a56 `differ`, and `beats` in 281123b4, 3d31c5b3, 6a11f6da, 75b8110e, a68b268e, cf98881b, ea9794b1 — pairwise disagreement over members that are tiles, motif fragments, placements, cells, or determination candidates. The members are not a frame's lines, and no adjacency groups them into runs.

Spec:
Three points come from the callers beyond the surfacing solver.

1. The axis belongs in the comp's signature, as a column. 90c28cc7 and 80214e03 each declare a `Line` record whose only work is to carry the axis beside the line position into `Canon`, and 80214e03 nests that record again to carry its case; e1baa8a4 carries the axis as a `Dir` through `dist` and keeps no record at all. A comp that takes `(key, axis, line, cell value)` and reports `(key, axis, line, band)` removes both record declarations.

2. The definition should state absence at a place, not only a whole line left out. 80214e03 feeds the blocks' non-bg cells, so a hole leaves a place where one of the two lines holds nothing. That place must cut nothing, which is what its `$Contrast` rule does by demanding two cells. The entry's sentence covers a line the caller leaves out; it does not say what a gap inside a line does.

3. The band label must separate the key and the axis. 90c28cc7 bands both axes in one run, and 80214e03 bands both of its cases in one run, so two lines under different axes or different keys must never take one label. `Canon` gets this from the element type; a comp with the axis as a column has to put the axis and the key into the element it canonizes.

Ranking is not an interface change. All three callers rank the bands right after — 90c28cc7 and 80214e03 through `OrderFrame`, e1baa8a4 by its boundary count — and the band label feeds `OrderFrame.member` directly, so the ranking stays in the unit that holds it.

Reimplementations: none.

``(・_・ヾ``
