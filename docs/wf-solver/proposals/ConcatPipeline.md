# `ConcatPipeline<Key>` — unequal-sized rectilinear tiles

Per-tile dims and cumulative per-edge offsets for tiles laid side by side. Not: uniform tilings (`concat`, `concat_slab`, `concat_2d`, `Tile2D`); one tile at an offset; tabulated correspondences.

Grep: `sum `, `+ [A-Z]`, `edge_off`, `jump_delta` chains.

Homes: none beyond e633a9e5. Near: 291dc1e1 (blocks stack as slabs of their own thickness; all one thickness on the data); 0bb8deee (unequal quadrants, equal crops); e1baa8a4, 0a1d4ef5 (unequal bands, index only).

Interface: no change.

Verdict: close; e633a9e5 rewritten as a per-edge walk. 2026-08-29.
