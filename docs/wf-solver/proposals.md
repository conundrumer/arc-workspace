# Proposals

The record of every lib candidate, from its sweep to its verdict. An entry is written when a sweep is dispatched. When the sweep returns, the entry carries a `Recommendation` line; the user's verdict replaces it with a `Verdict` line. Under `close` the entry stays: a later sweep covers only the solvers whose file time is at or after the entry's date. Under `park` it stays with its spec and its home. On `promote` it leaves once its homes are migrated. Not a changelog or a notes file.

An entry's first sentence is its index line, read under the entry's title: it stands alone and names the operation. A family of solvers (`// family:` siblings with their representative) counts as one home.

## `Wallpaper<Key, Val>` — lattice-quotiented isometry detection

The isometry peer of `ShiftInvariance`: which isometries of the frame — a
D4 element composed with a shift — fix a keyed valued cell set, given the
set's per-axis periods. Candidates are quotiented by the translation
lattice: one representative per coset, its shift drawn from the lattice's
fundamental domain, and square-checked against the lattice where the kind
squares to the identity (a symmetry's square is a translation, and the
group's translations are the lattice). `ShiftInvariance.period` feeds the
`period` input directly. Lib target: body comp beside `ShiftInvariance`;
`Gen` moves beside it.

```
.type Gen = [d: D4, delta: Shift]

.comp Wallpaper<Key, Val> {
    .decl kind(d: D4)                           // input
    .decl cell(key: Key, p: Position, v: Val)   // input
    .decl grid(key: Key, p: Position)           // input
    .decl period(key: Key, a: Axis, k: number)  // input

    // Witnessed, uncontradicted coset representatives.
    .decl sym(key: Key, g: Gen)

    // Kinds with an admitted representative; the identity kind whenever a
    // lattice exists. A Sym-naming Fit reads this.
    .decl kind_used(key: Key, d: D4)

    // One step along an admitted isometry or a lattice shift, over the
    // full grid — the map an orbit closure walks.
    .decl step(key: Key, p: Position, q: Position)
}
```

- A representative needs a witness — some cell pair it maps one onto the
  other; vacuous overlap is no evidence. The rest of its coset arrives by
  composition with the lattice in the caller's closure.
- The internal canonical corner for fundamental-domain shifts is
  unobservable: every corner yields the same cosets and maps.
- An axis without a period contributes only the zero shift, so an
  aperiodic grid degrades to center-anchored D4 detection.

**Home.** 0dfd9992: wallpaper repair —
`Parse` feeds detected per-axis periods and the stored point group's
kinds; `out` closes survivor colors over `step`; its Fit names the
kinds every example uses as a `point_group` Sym value.

Not: translation periodicity alone (`ShiftInvariance`); a fixed-frame symmetry (`D4Map`); a reflection about a line the data names.

Grep: `ShiftInvariance`, `sym_member`, `apply(D`, `mismatch`, `witnessed`, `period`.

Homes: 0dfd9992 alone. Near: af22c60d, 981571dc, 0934a4d8 (Fit), 1b60fb0c search a mirror line or rotation center over an aperiodic pattern, where the comp tries no shift; the three Fit sites factor the search per axis over line indices.

Interface: `step` would carry its generator, `step(key, g, p, q)`; `period` stays an input; an aperiodic axis contributing its full extent would serve the four sites, but their per-axis factoring reads as a separate reflection-axis primitive.

Verdict: park. 2026-08-29.

## `RIGID(<group>, ...)` — rigid assemblies under a subgroup

A group argument on `RIGID`: the closure ranges `sym_member(S, D)` for the named `Sym` in place of `d4_elem`, with `SYM_D4` when the argument is omitted. Under `SYM_C4` the hand becomes data — a stored chart of the wrong hand has an orbit that misses the observed instances, and the fit diffs — while rotation stays gauge. Closing a rotate-only task over D4 instead over-generates placements the task forbids and lets the fit accept a mirrored chart.

The rest of the machinery is group-agnostic: the subgroup's elements are D4 elements, so placed column types and the column actions are unchanged, and the fit compare groups rows by whatever pose labels both sides emit — both sides close through the same generated rule. The change is the elem atom in the expansion plus the group argument in the parser. The group is a macro argument, not a Consts slot: the fit cannot derive it from the pairs, and which column types have an action depends on it (`Sense` and `Sym` are invariant under rotations and inverted by a reflection).

A task treating both hands as distinct pieces needs no new group: that is an id-keyed `SYM_C4` chart with one id per hand.

Gate: a site whose stored pieces rotate but do not reflect.

Not: achiral assemblies; assemblies that reflect; input-derived pieces closed by hand.

Grep: `RIGID(`, `c4_elem`, `SYM_C4`, `d4_elem(D)`, `GRID_MASK`, `GRID_SPARSE`.

Homes: none. The RIGID sites hold achiral assemblies (142ca369, 150deff5, 21897d95) or reflect (269e22fb). 1a244afd's `turn_map` is a C4 orbit, but closing it collapses `$Table` into `$Turn`. 2697da3f pairs `SYM_C4` against `SYM_X` over input-derived cells.

Interface: a group argument, `SYM_D4` by default, as a macro argument rather than a Consts slot.

Verdict: park. 2026-08-29.

## Per-axis gap on `Divide2D` and `Tile2D`

`gap(a, g)` in place of the scalar `gap(g)` on both comps, with `concat_2d` changed alongside for round-trip symmetry. The scalar states that the separator has one width on both axes, a claim independent of tile shape (f8b3ba0a divides rectangular tiles under one gap); under `gap(a, g)` a site that wants one width spreads it with `gap(A, G) :- axis_elem(A), c.gap(G)`, and the claim becomes the site's to restate. Change both comps together or neither: they differ only in dim-by-count against dim-by-size.

**Home.** 20fb2937: bands across the header under `c.band_gap`, layers abutting along it. It writes the two `divide_by_size` calls by hand; under the change, one `split` on the band axis recovers its separate band and layer positions from `tile`'s composed outer.

Not: slab divides; a gap keyed per key; `divide_gap`.

Grep: pairs of `divide(` / `divide_by_size(` in one rule, `perp(A, A2)`, `tile_pos(`.

Homes: 20fb2937 alone. Seventeen `tile_pos` sites pass an asymmetric gap pair with a single tile on the zero-gap axis; every genuinely 2D gap-bearing site is isotropic (b1fc8b8e, and the nonzero-gap `divide_2d` / `divide_by_size_2d` / `concat_2d` calls).

Interface: both comps together or neither, with `concat_2d` alongside.

Verdict: park. 2026-08-29.

## `ConcatPipeline<Key>` — unequal-sized rectilinear tiles

Per-tile dims and cumulative per-edge offsets for tiles laid side by side. Not: uniform tilings (`concat`, `concat_slab`, `concat_2d`, `Tile2D`); one tile at an offset; tabulated correspondences.

Grep: `sum `, `+ [A-Z]`, `edge_off`, `jump_delta` chains.

Homes: none beyond e633a9e5. Near: 291dc1e1 (blocks stack as slabs of their own thickness; all one thickness on the data); 0bb8deee (unequal quadrants, equal crops); e1baa8a4, 0a1d4ef5 (unequal bands, index only).

Interface: no change.

Verdict: close; e633a9e5 rewritten as a per-edge walk. 2026-08-29.

## `KeyedSetCompare` extensions — the set-relationship lattice

`within`, `disjoint`, `intersects`, and the size projections, beside `covers` and `equals`. Not: a containment test between two unkeyed sets; counting with no pattern.

Grep: `KeyedSetCompare`, `overlap`, `count :`, `_member(`, `best_`.

Homes: none. `within` has no site; `intersects` / `disjoint` are one-line joins at 16b78196, 0a1d4ef5, 184a9768, b7cb93ac; the size projections are `Tally` at 27a28665 and 1b60fb0c; `best_covered` is 44f52bb0 alone. Reimplementations of `covers`: 15113be4, 44f52bb0 (fixed).

Interface: no change.

Verdict: close. 2026-08-29.

## `Reframe.extents` — how big the outer is

The `BoxFrame.extents` readout on a `Reframe` outer. Not: `BoxFrame.extents`; whole-grid extents; a size stored in Consts.

Grep: `Reframe`, `\.inner(`, `axis_dims`, `c\.box`.

Homes: 4522001f alone. f8b3ba0a's Fit was a hand-written `BoxFrame` (fixed). Reimplementations of `BoxFrame.extents`: 15660dd6, f25ffba3, 20270e3b (fixed). Half the `Reframe` instances have an anchor-cell outer, where the readout would silently give the grid's size; the stored-box case is a margin-size subtraction, which the `Reframe` route already states relationally.

Verdict: close. 2026-08-29.

## `Ordinal.rev` — opposite-end readout of an index set

The pairing of each element with its counterpart from the other end. Not: descending layout; a rank flowing into a table; reversal by geometry or by a stored table.

Grep: `rank_desc`, `rank(`, `count :`.

Homes: 85c4e7cd alone. Near: 08ed6ac7, 2753e76c (`rank_desc` into a table or an extent); 3906de3d, 9c56f360, 1da012fc, 2ccd9fef (same rank across two index sets).

Verdict: close. 2026-08-29.

## `diag_edge_delta` — edge delta at a corner with two amounts

Two `edge_delta`s at the two edges of a corner. Not: `edge_delta` at a DiagDir (one amount at both edges); `jump` chains at a corner; `diag_dist`.

Grep: `edge_delta`, `diag_dirs`, `jump_delta.*jump(`.

Homes: 8618d23e alone. 1e81d6f9 was `edge_delta` at a DiagDir (fixed). Near: 4522001f, 22208ba4 (diagonal shifts); the opposite-pair form at five sites, now `axis_delta`.

Verdict: close; 8618d23e keeps it as a plain relation. 2026-08-29.

## `Matching<Key>` — unique pairing of two keyed cell sets

An edge kept when using every endpoint cell of both sets exactly once forces it, over `CoverForcing`. Not: region filling by multi-cell pieces; pairing by a functional rule; pairing from data; one-to-many.

Grep: `CoverForcing`, `pair(`, `partner`, `count :.*= 1`, `forced`.

Homes: 1a244afd alone. Near: 228f6490, 18447a8d, and the Fit `pair(p_in, p_out)` labelings (833966f4, e9afcf9a, 66e6c45b, 68b67ca3, ca8de6ea) pair without exclusivity and share endpoint values across sides; b7cb93ac, 89565ca0 want every bijection (`TiebreakResolutions`).

Verdict: close; 1a244afd calls `CoverForcing` directly. 2026-08-29.
