# `DividerTiles.box` — the box each cut tile occupies

The rectangle each tile of a cut lattice covers, as a box of the grid's frame, per key and tile. The tiles a cut lattice makes are unequal, and `tile_of` reports which tile a cell sits in and nothing about that tile's extent, so a caller that reads a tile's size, its edges, or a cell's place inside it recovers the extent from the tile's own cells. `crop` against the box states the intile position, `box_edge` and `box_corner` the tile's sides and corners.

```
.comp DividerTiles<Key> {
    ...
    .type _KT = [key: Key, p_tile: Position]

    .init hull = Bbox<_KT>
    hull.cell([K, P_tile], P) :- tile_of(K, P, P_tile).

    // The rectangle tile p_tile covers.
    .decl box(key: Key, p_tile: Position, b: Box)
    box(K, P_tile, B) :- hull.box([K, P_tile], B).
}
```

Not: the bounding box of a set the caller assembles for its own reasons (`Bbox` itself); the box of the content inside a tile, which bounds ink rather than the tile; the tile position `tile_of` reports, which indexes the tile among its siblings and states no extent; `Divide2D` and `Tile2D`, whose tiles are equal and whose `p_inner` already places a cell inside its tile.

Match: a `Bbox` instance whose `cell` rule is fed from a `DividerTiles` instance's `tile_of`, keyed by the tile position, with or without an example or instance key beside it — the statement reaches across the two rules and the `.init`. The form that then crops a grid cell into that box, or reads an edge or a corner off it, is the same statement with its consumer. A per-tile minimum over edge distances, written by hand, states it without `Bbox`. Grep signature: `grep -ln 'Bbox<' programs/solvers/*.dl` intersected with `grep -ln 'tile_of' programs/solvers/*.dl`, then read each `Bbox` instance's `cell` rule; match the hand-written form with the parser.

Survey: 2026-09-13 15:45 — every solver.

Callers:
1be83260 `block` — the box of each block the cut lattice makes, cropped so each block's cells carry an intile position.
20981f0e `tile_box` — the box of each tile the dot lines cut, cropped to put the moving piece in its tile's frame.
2546ccf6 `tile_box` — the box of each tile, cropped to give every cell its intile position.
38007db0 `tile_view` — the box of each tile the one-color lines cut, cropped to compare tiles by their content.
42918530 `bbox` — the box of each tile, reached through the alias `box_of`, cropped to read each drawn rectangle in its own frame.
4e7e0eb9 `part_box` — the box of each part, in the Determine comp, read with `box_extent` to find the parts that are square.
5545f144 `frame` — the box of each panel, reached through `panel_cell`, cropped so a panel's cells become the output frame.
5a719d11 `panel` — the box of each panel of a keyed parse, cropped to the panel's intile frame.
5ecac7f7 `panel_box` — the box of each panel under the `$Separator()` parse, cropped to the panel's intile frame.
6350f1f4 `block` — the box of each block, cropped to give a cell its place inside its block.
65b59efc `tile` — the box of each tile, cropped to place a cell inside the tile it sits in.
7491f3cf `panel` — the box of each panel, cropped to the panel's intile frame.
78332cb0 `tile` — the box of each tile, cropped twice, once for the shape cells and once for the seated content.
7c008303 `tile_box` — the box of each tile, read with `box_extent` for the tile's per-axis size and cropped for the intile position.
88a62173 `bbox` — the box of each tile, cropped to give a grid cell its intile position.
92e50de0 `tile_box` — the box of each tile, cropped to the tile's own frame.
18447a8d `bbox` — the box of each band, fed from `part_of`; the cut runs on the band axis alone, so a band is a tile, and the box is cropped to the band's frame.
18286ef8 `bbox` — the box of the tile the gaze sits in, selected through `gaze_tile_cell` and cropped so a tile position of the arrangement names a cell inside that tile.
20fb2937 `hdr_box` and `fld_box` — the boxes of the two parts the single cut makes, each part picked by its tile index from one edge, each box cropped to that part's frame.
4c177718 `view` — the box of the scene panel, the one panel the legend does not hold, cropped to the output frame.
5dbc8537 `view` — the box of the template panel, picked by `template(T, _)`, cropped to the output frame.
247ef758 `fbox` — the box of the frame part, picked by its tile index from an edge, read with `box_edge` for that part's border cells.
1ae2feb7 `canvas_box` — the box of the canvas part, picked by its tile index from an edge, cropped so offset 0 in that frame sits against the separator.

Near-misses:
0bb8deee `hull`, 20981f0e `piece_box`, 4c177718 `pay_box` — each bounds the ink inside a tile, so the box tracks content and not the tile's extent.
8a371977 `lattice`, 7837ac64 `span_box`, 39e1d7f9 `motif_box` — each bounds tile positions in the arrangement frame, not grid cells, so the result is the arrangement's extent and not a tile's.
38007db0 `block` — bounds a tile's cells together with the separator cells around it, a set the solver assembles for the output it wants.
77fdfe62 `fence_box` — bounds the cells a separator screens from every edge, the union of the interior parts rather than one part.
7d419a02 `unit` under `$Band()` — bounds the band that holds the mark, fed from `part_of`; the cut here can run on both axes, so a band is a slab of tiles.
4c177718 `target_box`, 0bb8deee `obox` — each bounds a set the solver assembles from its own tests, `Bbox` itself.
20fb2937 `blob_box`, 4c177718 `arrow_box`, 5dbc8537 `bbox`, 83302e8f `bbox`, 2e65ae53 `bbox` — each bounds a component or a color region, which the cut does not delimit.
135a2760 `frame` — reads a tile's edge cells with `Rim` over `tile_of`, which recovers the tile's boundary from the tile's own cells but computes no box, so no site here states the operation.

Spec:
The signature stands. Every caller joins the box against a tile position it already holds, and the six that want one tile (18286ef8 `bbox`, 20fb2937 `hdr_box`, 4c177718 `view`, 5dbc8537 `view`, 247ef758 `fbox`, 1ae2feb7 `canvas_box`) reach that tile by a test on the tile position, so `box(key, p_tile, b)` serves them as written and their `Unit` keying is an artifact of `Bbox`.

The definition should expose the intile position beside the box. Twenty-one of the twenty-three callers put the box straight into `crop`, and each writes the tile's cell membership a second time to feed that crop, because `Bbox` gives no membership back. Only 7c008303 `tile_box` and 4e7e0eb9 `part_box` read `box_extent` instead, and only 247ef758 `fbox` reads `box_edge`. A `tile_pos(key, p, p_tile, p_inner)` output, the reading that `Divide2D` and `Tile2D` already give for equal tiles, would remove that repeated membership atom at every cropping caller and leave `box` for the three that read an extent or an edge.

The band reading, the box of a `part_of` part rather than a `tile_of` tile, is caller-only. 18447a8d `bbox` cuts on one axis, so its band is already a tile and the specced form serves it; 7d419a02 `unit` is the one site that needs a slab, and one site does not carry an interface change.

Reimplementations: none.
The grep intersection gave 27 solvers holding both `Bbox<` and `tile_of`, out of 38 with `tile_of`, 44 with a `DividerTiles` instance, and 314 with a `Bbox` instance. A parser matcher over the whole corpus, which taints every relation reachable from a `tile_of` read and then reports each `Bbox` `cell` rule fed from a tainted relation, returned 30 rules across 24 solvers; reading those rules found the aliasing callers 42918530 `box_of` and 5545f144 `panel_cell`. The `part_of` sites came from a separate grep, and the single-tile sites from reading the `part_idx` readers. The hand-written form the spec names, a per-tile minimum over edge distances, occurs nowhere: the corpus holds no `min` or `max` aggregate in any solver, only two comments carrying the word.
