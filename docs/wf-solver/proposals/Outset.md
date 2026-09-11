# `Outset<Key>` — the band of cells around a box

The cells within a given width of a box and outside it, per key: the width lets the box out at each edge, and the band is what the let-out box covers that the box itself does not. It is the outward peer of `BoxCells.hole`, and it is what a solver drawing a border around a region paints. The box's own cells have to be materialized before the band can subtract them, because `geq` is inline and Souffle cannot negate it.

Code form:

```
.comp Outset<Key> {
    .decl box(key: Key, b: Position)          // input
    .decl width(key: Key, d: Dir, k: number)  // input
    .decl cell(key: Key, p: Position)         // input

    // An edge with no width lets the box out by zero.
    .decl edge(key: Key, d: Dir, k: number)
    edge(Ky, D, K) :- width(Ky, D, K).
    edge(Ky, D, 0) :- box(Ky, _), dir_elem(D), !width(Ky, D, _).

    .init pack = DirPack<Key>
    pack.edge(Ky, D, K) :- edge(Ky, D, K).

    // The box let out by the width at each edge.
    .decl outset_box(key: Key, b: Position)
    outset_box(Ky, B) :- box(Ky, B0), pack.pos(Ky, W), displacement(W, B0, B).

    .decl inside(key: Key, p: Position)
    inside(Ky, P) :- cell(Ky, P), box(Ky, B), geq(P, B).

    .decl covered(key: Key, p: Position)
    covered(Ky, P) :- cell(Ky, P), outset_box(Ky, B), geq(P, B).

    .decl ring(key: Key, p: Position)
    ring(Ky, P) :- covered(Ky, P), !inside(Ky, P).
}
```

Solver-local form (52fd389e), where the width is uniform and the box comes from a `Bbox`:

```
.decl ring_box(id: Ident, b: Position)
ring_box(Id, B) :-
    rect_box.margin(Id, M),
    marker_count.tally(Id, K), uniform_delta(K, W),
    displacement(W, M, B).

.decl ring(id: Ident, p: Position)
ring(Id, P) :- in(P, _), ring_box(Id, B), geq(P, B), !rect_box.inside(Id, P).
```

Not: `Border` (the frame inside a border, viewed inward, with no cells outside the box); `BoxCells.on_edge` (the box's own edge lines); `Rim` (a set's own boundary cells, which follow the set's shape rather than a box); a box translated by a Shift (16b78196, 4522001f), which moves a box instead of letting it out; a box let out with no band read off it; the enclosed cells of a box (`Bbox.inside`, `geq` alone).

Match: a rule deriving a second box from a box margin and a width, through `displacement` or `compose` with an `Inset`, joined by a rule that tests `geq` against that second box and negates membership in the first. Grep `displacement(` and `uniform_delta(` in `programs/solvers/*.dl`, then read each site for the width-to-box direction; a site may instead relax the cell (`compose(P, W, P_near), geq(P_near, M)`), which is the same operation with the addition on the other side.

Survey: 2026-09-08 19:56

The survey read the whole corpus, 542 solvers. Two rules test `geq` against a derived box while negating membership in the source box, and they are the two callers. Of the 29 rules that combine a box margin with `compose` or `displacement`, every other one translates a box by a Shift, seats content in a box frame, or reads the offset between two boxes. No site writes the relaxed-cell variant, and no site builds the band by feeding a let-out box to `BoxCells` or `MarginFrame`.

Near: 49d1d64f and ed74f2f2 (a box let out, with no band read off it — the ring cells carry content seated from elsewhere); 28e73c20 (a uniform delta taken inward, read as a turn threshold); 412b6263 (the ring Inset offsets copies into the grown frame, and the outer lines fall out as frame cells off the copies); 444801d8 and 2d0172a1 (`BoxCells.on_edge`, the box's own edge lines); 4290ef0e (`Rim` depth over a canvas, no box and no width); 36fdfd69, 4258a5f9, dc1df850, a9f96cdd (the one-step band around a cell set, which follows the set's shape); 522fdd07, 1a6449f1, 4347f46a, 50cb2852, bb43febb (the inward peers, `BoxCells.hole` and `Bbox.inside`).

Survey: 2026-09-08 20:11

The second survey read the seven solvers whose file time is at or after the first survey's dispatch. It found no caller, and no near-miss beyond the two peers the `Not:` line already names. One site stores a let-out amount packed — `48d8fb45.dl:21`, `win_delta([1, -3, -1, -1])` — and takes the whole let-out box as its output, so it reads no band and bears no weight on the width form.

Survey: 2026-09-08 20:34

The third survey read the eight solvers whose file time is at or after the second survey's dispatch. It found no caller beyond 52fd389e, whose edit after the second survey left the operation unchanged, and no near-miss beyond the classes the `Not:` line already names: 247ef758 reads a box's own edge lines and its interior, 539a4f51 draws an L-shaped band as a level set of `diag_dist` with no box and no width, and 53fb4810 reads a `Bbox` for its extent alone.

Survey: 2026-09-09 01:58

The fourth survey read the 48 solvers whose file time is at or after the third survey's dispatch. It found no caller beyond 543a7ed5, whose edit after the third survey left the operation unchanged, and no near-miss beyond the classes the `Not:` line already names: 58f5dbd5 crops a let-out box with no band read off it and offsets seated copies into a grown frame, 5751f35e differences two independently derived boxes with no source box and no width, 40f6cd08 orders two box margins against each other, and 551d5bf1 reads the gaps in a drawn outline off `BoxCells.on_edge`.

Dilation form: one `dir8_elem` step off `Bbox.inside` covers the same cells as the box let out by one, because the source is a full rectangle. Two solvers write a band that way — 5adee1b2 (`grown_box`) and 305b1341 (`panel`) — and both take the band together with the box's own cells, which is `covered` rather than `ring`. Both state the unit as a step and hold no width value, so calling the comp asks them for a width of 1 that their programs otherwise do not name. The forms come apart off a full rectangle and above unit width: 543a7ed5's `$Band()` steps off a shape's own cells, and 5587a8d0's `covers` steps repeatedly over a set of Shifts. Two questions follow for the spec: whether `covered` is a readout beside `ring`, and which form a unit width takes.

Width form: `width` arrives per Dir and packs inside the comp with `DirPack`. `MarginFrame`, the inward peer, takes its widths that way, and the two comps over the same box-and-margins concept would otherwise disagree on how a width arrives. 3a301edc holds its width as one scalar per Dir already, and packs it caller-side only because the earlier form asked for an Inset; 52fd389e spreads its count over `dir_elem` and drops `uniform_delta`. That is the migration step: the file on disk still calls `uniform_delta(K, W)`.

Callers:

- `programs/solvers/3a301edc.dl` — `ring_box` and `ring`. The band around a rectangle is as thick at each edge as the block the rectangle holds is long on that axis, so the width is per-edge.
- `programs/solvers/52fd389e.dl` — `ring_box` and `ring`. The width is uniform: one cell per marker the rectangle holds.
- `programs/solvers/543a7ed5.dl` — `ring_box` and `ring`, under the `$Ring` outline. The width is uniform and one cell: the band sits immediately around each shape's bounding box.
- `programs/solvers/5adee1b2.dl` — `grown_box`. Each shape's bounding box let out by one on every edge, read as the band together with the box's own cells. It writes the dilation form, so it calls the comp on the two questions the fourth survey raises.
- `programs/solvers/890034e9.dl` — `outline`. The band one cell around each twin of the frame's hole, a full rectangle, drawn in the frame's color. It writes the dilation form as `ring`, so it calls the comp on the unit-width question.

Survey: 2026-09-10 20:49 — the solvers since 2026-09-09 01:58.

The survey read the 70 solvers in scope for the band of cells around a box within a width: a rule deriving a let-out box from a box margin and a width, joined by a `geq` test against that box with membership in the source box negated, and the dilation form, one `dir8_elem` step off a full rectangle. It grepped `displacement(`, `uniform_delta(`, `edge_delta(`, `axis_delta(`, `compose(`, `geq(`, `gt(`, the `Bbox`, `BoxCells`, `BoxFrame`, `MarginFrame`, `Rim`, and `DrawnRect` instances, `dir8_elem` beside `neighbor(`, and relation names carrying ring, band, outline, border, grown, or frame, and read each hit in its rule.

Callers:

- `programs/solvers/890034e9.dl` — `outline`. The band one cell around each twin of the frame's hole, a full rectangle, drawn in the frame's color; unchanged since the entry listed it, still the dilation form as `ring` (`dir8_elem`, `neighbor`, `in(Q, _)`, `!twin`).

No second caller: no rule in scope tests `geq` against a box derived from a box margin and a width, and no site writes the relaxed-cell variant. Of the `displacement` and `compose` sites that touch a box margin (045e512c, 20981f0e, 264363fd, 291dc1e1, 2c181942, 7c66cb00, 85b81ff1, 88207623, 88a10436), every one moves a box or content by a Shift, seats content in a box frame, or reads the offset between two boxes. The two `uniform_delta` sites (412b6263, 8719f442) build an Inset that seats content in a grown frame. The `geq` and `gt` sites (8731374e, 846bdb03, 8698868d, 84f2aca1, 20981f0e) read a box's enclosed cells or its strict interior.

Near-misses:

- 8719f442 — `seat_delta` and `cell`. The program names `ring_width(1)`, packs it with `uniform_delta` into the Inset that seats the input's block tile inside the grown tile frame, then takes the block tile with its `dir8_elem` neighbors as the tile frame; `copy` reads the ring tiles by direction. It is the 412b6263 class, content offset into a grown frame with the outer cells falling out around it: there is no cell domain to feed the comp, because the grown frame is what the dilation produces. It reads the seat together with the ring, which is `covered`, not `ring`.
- 412b6263 — `ring`. The known near-miss: the ring Inset offsets copies into the grown frame, and the outer lines fall out as frame cells off the copies.
- 8731374e — `covered`. `geq` alone against a drawn rectangle: the enclosed cells of a box.
- 8698868d — `interior`. A block's ring is `box.inside` minus the BoxFrame over `gt(P, M)`: the box's own edge lines, `BoxCells.on_edge`.
- 2c181942 — `seat`; 85fa5666 — `seat`. One step beyond a `Bbox.edge_cell` toward its edge, or beyond a `Bbox.corner` toward its corner: one side or one corner of the unit band, read as a seat for content carried from elsewhere (the 49d1d64f class).
- d9fac9be — `outline`, `defect`, `gap`. `Rim` over a `Frame2D` is the box's own edge lines, used as a shape to find; `defect` and `gap` test the eight surrounding cells of one cell, no box and no width.
- 759f3fd3 — `rings`. `Dilate` depth from the crossing cell, stepping `dir8_elem`, indexes square rings by depth: no box and no width, the 4290ef0e class.
- 85c4e7cd — `peel`; 13e47133 — `rim`. `Rim` and `Rim8` depth over the whole grid or an open set, which follow the set's shape.
- 20981f0e — `landing`; 85b81ff1 — `moved`. A box margin composed with a Shift and tested with `geq(M, ORIGIN)`, or the displacement between two box margins: a box moved, not let out.
- 137f0df0 — `bx.inside`; 3490cc26 — `span.inside`; 84f2aca1 — `region`; 846bdb03 — `interior`; 1a6449f1 and 868de0fa — `bcells.hole`. The inward peers, `Bbox.inside`, `gt`, and `BoxCells.hole`.

Spec:

1. The `covered` readout. 8719f442 reads the box together with its band, as 5adee1b2 does; it would call the comp on that readout only if the comp also realized the domain when none is given, since its grown frame exists only as the dilation's output. That is a question for the spec, whether `cell` may default to the let-out box's own frame, and it rests on one near-miss beside one caller, so it is reported and not argued as a change.
2. The unit width. 8719f442 is a dilation-form site that names its width as a number, `ring_width(1)`, and packs it with `uniform_delta`: unlike 5adee1b2 and 890034e9, calling the comp asks it for nothing its program does not already hold. It does not settle which form a unit width takes, because its ring is found by the step and not by the width.
3. The `Not:` line. `Dilate` (proposal comp in 759f3fd3 and 6df30ad6: depth outward from a seed set through one direction set) covers the same cells as `covered` when the seed is a full rectangle, the directions are `dir8_elem`, and the width is uniform: depth at most the width. The two come apart on a per-edge width, on a seed that is not a rectangle, and on cardinal-only steps, where the depth band has cut corners. The `Not:` line should name `Dilate` beside `Rim`, as the outward operation that follows a set's shape and holds no per-edge width.
4. Interface and definition otherwise: no site in scope argues a change to `box`, `width` per Dir, or `ring`.

Reimplementations: none.
