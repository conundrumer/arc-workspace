# `Border<Key>` — the frame inside a uniform border

A frame viewed inside a uniform border of given width, one border per key: the width packs into a margin, and each cell at least that far from every edge pairs with its position in the enclosed frame. Border cells get no pair, so a divide of the enclosed frame never reads a negative distance off one of them.

Code form:

```
.comp Border<Key> {
    .decl cell(key: Key, p: Position)  // input
    .decl width(key: Key, k: number)   // input

    .decl margin_axis(key: Key, a: Axis, p: Inset)
    margin_axis(Ky, A, P) :- width(Ky, K), axis_of(D, A), axis_delta(D, K, K, P).

    .decl margin(key: Key, p: Inset)
    margin(Ky, P) :-
        perp(A1, A2), margin_axis(Ky, A1, P1), margin_axis(Ky, A2, P2),
        compose(P1, P2, P).

    // Internal keys pair the solver key with the viewed cell; the origin is
    // the key's margin, so each pair has one outer.
    .type KP = [key: Key, p: Position]

    .init rf = Reframe<KP>
    rf.outer([Ky, P], M) :- cell(Ky, P), margin(Ky, M).
    rf.cell([Ky, P], P) :- cell(Ky, P).

    .decl field(key: Key, p: Position, p_field: Position)
    field(Ky, P, P_field) :-
        cell(Ky, P), margin(Ky, M), geq(P, M),  // clear of the border
        rf.inner([Ky, P], P_field).
}
```

Not: `Reframe` (an outer of any shape, with no guard and no pairing of its own); `BoxFrame` (a margin read off a cell set, not given as a width); `Bbox.inside` (membership inside a box, with no reframing); the gap of a `divide` (separators between tiles, with no ring around them); `divide_by_size` with the roles swapped, K the line width and G the tile size, which states the same bordered lattice with no margin — a gap cell gets no decomposition, so the swap yields tile membership and no tile index in the enclosed frame, and it serves a site that tests membership (1c0d0a4b, 332efdb3's `$Stripes`) rather than one that keys data by tile position; a crop to a stored sub-box (a placement, not a uniform ring).

Match: a site that subtracts a uniform margin from a frame's cells and keeps the cells clear of it. In the shape above that is a `geq` guard and a `Reframe` whose outer is one scalar spread over all four edges, but a site may pack the margin as a Position record, or as a signed Inset it composes onto each cell, or drop the guard where the caller's other tests already exclude the border. Grep: `Reframe<`, then judge the outer; `geq` beside `axis_delta` or a Position record of one repeated variable; `compose(` beside a parameter typed `Inset`; divide-family calls whose position argument is not a raw grid cell.

Survey: 2026-09-01 21:41

Result: three sites hand-write the operation, beside the surfacing solver's two. Each stores a uniform ring: 332efdb3 and f8b3ba0a as the signed Inset `[-1, -1, -1, -1]`, which fuses the width with the direction of the shift, and 77fdfe62 as the unsigned record `[2, 2, 2, 2]`; under Border each stores the width the pairs exhibit. In all three the operation serves one case, and a sibling case encodes the task with no margin subtraction, so none of the three needs it to state its task. f8b3ba0a determines its Inset from a `Bbox` margin through `displacement`; a width parameter is determined from one edge of that margin, which states the uniformity in place of determining four edges that agree. The guard carries the complement too: 332efdb3 paints the border cells bg, and reads them by negating `field`.

Of the twelve solvers that init `Reframe`, only 77fdfe62 and the surfacing solver give it an outer that is one uniform margin; the rest take a `Bbox` or `BoxFrame` margin, a marker cell, a center, or a stored box. Two ring shapes stay outside: a ring around a sub-box (1c786137, 1a6449f1) and a ring added outward (49d1d64f; ed74f2f2 and 28e73c20 write theirs inside `Params`, which no program comp reaches). Either one takes an outer parameter or an inverse read, and that is `Reframe`.

Callers:

- 332efdb3 (`$Inset`)
- f8b3ba0a (`$Lattice`)
- 77fdfe62 (`$Margin`)
- 33067df9 (`in_border`, `out_border`)

Closed: 2026-09-02 13:56 — generalized, not rejected. A uniform width is one assignment of per-edge margins, so the operation continues as `MarginFrame` (promoted to `programs/lib.dl` 2026-09-02, with its callers migrated): widths arrive one scalar per Dir, a uniform border spreads one stored width over `dir_elem`, and the packed-Inset construction this entry's width input avoided stays avoided.
