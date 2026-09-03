# `Bbox.corner_cell` — the box cell at a corner

A per-corner readout on `Bbox`: the cell of the box at corner `d`, whether or not the set occupies it. `corner` states the member reading — a set cell on both of the corner's box edges — and it is absent exactly where the set leaves that corner open, which is where a solver that reads a corner as a seat or a hole needs the position. Not: `corner` itself (the member reading); `margin` (the box as a Position); `corner_anchor` against ORIGIN, which names which corner of the frame a box hugs, not a cell of the box.

```
    // The box cell at corner d, member or not.
    .decl corner_cell(key: Key, d: DiagDir, p: Position)
    corner_cell(K, D, P) :- inside(K, P), margin(K, M), corner_anchor(D, P, M).
```

Match: a rule joining a `Bbox` instance's `inside` (or its `grid` cells cut by `geq` against `margin`) with `corner_anchor` or `diag_dist` on that instance's `margin` or `edge_min`, deriving a cell. Grep: `corner_anchor`, `edge_min(`, `.margin(`, `Bbox<`.

Survey: 2026-09-02 03:21.

Callers: 470c91de (surfacing), 4938f0c2 (`obj_corner`, 54-55, read at 68; the seat an object's box hugs, taken at the corner facing the marker block — every pair fills that corner, so the member reading passes the pairs too), 14b8e18c (`box_corner`, 65-69, read at 73, beside `box.corner` as the file's other case), 1478ab18 (the `$Inside` vertex rule, 95-100, over marks the box never holds, plus a second hand-built form at 43-48). Of 498 solvers, 184 hold 254 `Bbox`/`BoxFrame` instances and 26 use `corner_anchor`; a parser pass over every box readout joined with a corner primitive returns 16 rules in 12 files, of which those three carry the shape. Both callers sit on a `BoxFrame`, which inherits from `Bbox`, and both already feed `grid`, so `inside` is populated at each. Both reach the corner through `inner` rather than `inside` + `margin` — the same cell set viewed from the box, and the head they read is the proposed one, so the interface stands.

Near: `margin` corner-anchored against ORIGIN, which names the corner of the frame a box hugs (4522001f 108, 218, 234); the hole read as a direction alone, which `!corner` states in one atom (1e5d6875 79, 136; 21897d95 112) — only 470c91de needs the hole's position, because its fold tests membership at the cell; the member reading (19 references in 13 files); the box's centre cell, held by `centered` (11e1fe23 38-42, 247ef758 100-103, 41e4d17e 48-51, 39e1d7f9 109-113); two frames aligned at a shared corner (2013d3e2 49-52 with 73182012); a corner tile of a `divide` (1990f7a8 73); the set member nearest a corner by argmin (3d588dc9 81-83).

Adjacent: five files hand-write the same non-member box readout on one *edge* — `inside` + `margin` + `same_dist`, or `inner` + `dist(_, D, 0)` (21897d95 98-101, 256b0a75 28-30, 444801d8 43-45, 14b8e18c 48, 212895b5 44-47). `Bbox.edge_cell` is member-only, so nothing in lib holds it. The edge form has the wider caller base and the corner is its two-edge intersection; it is a separate operation with a separate entry.

Survey: 2026-09-02 07:24, over the solvers whose file time is at or after the first survey.

No caller in the 14 files of that scope. Six hold a box instance; a parser pass over box readouts joined with a corner primitive returns three rules, of which two are the member reading (469497ad 54, casting a beam from each corner of a solid block; 446ef5d2 63, the piece corner a mark sits diagonally beyond, whose color line 65 reads) and one is the recorded surfacing site. Both member readings need the corner cell to be a set member, which is the boundary the entry draws. Near, in the same scope: `corner_anchor` against ORIGIN over tile indices with no box (47c1f68c 70, 157); `edge_cell` at one edge, member-only (48634b99 56); `inner` joined with `dist` for a within-bar index (48634b99 61, 106).

Closed: 2026-09-02 18:32. Lib holds the operation by composition: on a `BoxFrame`, `inner` with `corner_dist(_, d, 0)` states the box cell at corner d in two atoms, member or not, and `inner` with `dist(_, d, 0)` states the side peer the same way. `corner_dist(_, _, 0)` became the settled corner atom when its hand-written forms were migrated (2026-09-02), which is what makes the composition the plainer encoding. Callers moved to it; the adjacent side operation needs no entry for the same reason.
