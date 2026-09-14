# `ConcatPipeline<Key>` — unequal-sized rectilinear tiles

Per-tile dims and cumulative per-edge offsets for tiles laid side by side. Not: uniform tilings (`concat`, `concat_slab`, `concat_2d`, `Tile2D`); one tile at an offset; tabulated correspondences.

Match: a cumulative per-edge placement of unequal tiles — a recursive rule pair whose base places the tile at an edge at `ZERO`, and whose step composes onto the accumulated box or offset an `edge_inset` or `jump_offset` amount read from a per-tile size, walking inward along an order; or the same accumulation as a `sum` aggregate or `+` arithmetic over the sizes of the tiles before a tile. The base and the step may sit in separate rules under one head, and the walk may reach the sizes through another primitive (`Order.next`, a tally, a box extent).

Callers: none beyond e633a9e5. Near: 291dc1e1 (blocks stack as slabs of their own thickness; all one thickness on the data); 0bb8deee (unequal quadrants, equal crops); e1baa8a4, 0a1d4ef5 (unequal bands, index only).

Interface: no change.

Closed: 2026-08-29 (minute not recorded). e633a9e5 rewritten as a per-edge walk.

Route: 4df5b0ae ranks one place per tile line with `Order`, so a tile's offset is the count of lines before it.
