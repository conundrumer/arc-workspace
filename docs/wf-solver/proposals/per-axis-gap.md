# Per-axis gap on `Divide2D` and `Tile2D`

`gap(a, g)` in place of the scalar `gap(g)` on both comps, with `concat_2d` changed alongside for round-trip symmetry. The scalar states that the separator has one width on both axes, a claim independent of tile shape (f8b3ba0a divides rectangular tiles under one gap); under `gap(a, g)` a site that wants one width spreads it with `gap(A, G) :- axis_elem(A), c.gap(G)`, and the claim becomes the site's to restate. Change both comps together or neither: they differ only in dim-by-count against dim-by-size.

**Caller.** 20fb2937: bands across the header under `c.band_gap`, layers abutting along it. It writes the two `divide_by_size` calls by hand; under the change, one `split` on the band axis recovers its separate band and layer positions from `tile`'s composed outer.

Not: slab divides; a gap keyed per key; `divide_gap`.

Match: pairs of `divide(` / `divide_by_size(` in one rule, `perp(A, A2)`, `tile_pos(`.

Callers: 20fb2937 alone. Seventeen `tile_pos` sites pass an asymmetric gap pair with a single tile on the zero-gap axis; every genuinely 2D gap-bearing site is isotropic (b1fc8b8e, and the nonzero-gap `divide_2d` / `divide_by_size_2d` / `concat_2d` calls).

Interface: both comps together or neither, with `concat_2d` alongside.

Verdict: park. 2026-08-29.
