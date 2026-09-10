# `Bbox.open_corner` — the box corner a set leaves empty

A per-key readout on `Bbox`: a corner of the set's bounding box that holds no set cell, reported as a direction alone. `corner` states the member reading — a set cell on both of the corner's box edges — and this is its complement over the DiagDir class, which is what a solver that keys data by the corner an L-shaped or notched set opens toward reads.

```
// inside Bbox<Key>
.decl open_corner(key: Key, diag: DiagDir)
open_corner(K, Diag) :- cell(K, _), diag_dir_elem(Diag), !corner(K, _, Diag).
```

Not: `Bbox.corner_cell` (closed: the cell at a corner, member or not — this reports no position); `Bbox.corner` itself (the member reading); `Bbox.gap` (any box cell the set misses, with no corner); `Bbox.edge_gap` (a missed cell of one edge line, with a side); `corner_anchor` against ORIGIN (which corner of the frame a box hugs).

Match: a rule negating a `Bbox` or `BoxFrame` instance's `corner`, at a corner the rule either enumerates over `diag_dir_elem` or binds from elsewhere, with no cell in the head. Grep `\.corner(` under a negation, and `diag_dir_elem` in a rule holding a box atom; hand-built boxes state the same thing through `edge_min` or a local margin relation.

Survey: 2026-09-09 04:13

Scope: all 589 solvers. 236 hold 328 `Bbox`/`BoxFrame` instances, and 50 files carry 77 `.corner(` references, of which 4 sit under negation. A parser pass for the head shape returns 21 rules in 13 files, a wider pass over any negation beside a corner-binding atom returns 41 rules in 27 files, and a `dir_of` pass returns 4 more; read in their rules, one further site reaches a box corner by hand.

## Callers

- `604001fa` — `Parse.missing_corner`: a mark fills three corners of its 2x2 box, and the empty corner keys `params.corner_color`, which names the color the mark's shape takes. `out` reads the direction alone.
- `1e5d6875` — `open_diag`, in the program and again in `Determine`: an L-tromino's open corner is the piece's heading, turned by a stored rotation under `$Rotate` and looked up under `$Lookup`.
- `470c91de` — `gap.item`, feeding `Unanimous<Color, DiagDir>`: each color fills a rectangle with one corner cell bitten out, and that corner is the direction the rectangle slides under `$Gap`. Written by hand over a `BoxFrame` as `corner_cell(Col, D, P), !bx.cell(Col, P)`. Its `corner_cell` stays either way — `slide` under `$Mark` and `ragged` read the corner's position.
- `21897d95` — `bracket`: a bracket is a patch equal to the two arms meeting at a pivot, and the far corner of its box must be empty, or a straight line would count as its own arms. The corner is bound through `diag_opposite`, so the site reads the operation as a test.

## Near-misses

- `3d588dc9` `notch` negates the object's member set over the whole box, which is `Bbox.gap`; its `wedge.item` reports the corner the object is packed into.
- `1478ab18` `right_angle` under `$Free` reports a position, and the set it negates is not the set that bounds the box.
- `af902bf9` `open_pair` and `open_quad` negate a marker set at a quadrant of a single cell, with no box and no member set; `open_pair` reports positions. `252143c9` `quad_color` and `0b148d64` `panel` read the same quadrant with no negation.
- `08573cc6` `Determine.marker_corner` names the frame corner a marker hugs, through `corner_dist(P, Diag, 0)` — the `corner_anchor` against ORIGIN exclusion, and a member reading.
- `15663ba9` `bend` takes the quadrant a bend cell opens onto from the two arms present at the cell.
- `c1990cce` `mirror_corner` is a complement over a two-element corner set derived from `params.grow`, with no box and no cell set.
- Determination universals by defect negation over `diag_dir_elem`: `17b866bd` `stray`/`corner`, `3979b1a8` `anchor`/`growth`, `be03b35f` `template`, `6e02f1e3` `fig_diag`, `3bd67248` `diag_paint`. Each keeps the corners no example contradicts, and none reads box occupancy.

## Spec

The interface and the definition stand as written.

- The composition argument that closed `Bbox.corner_cell` does not transfer. That close rested on `inner` grounding the composition by itself. The negation here binds nothing, so the two-atom form is three atoms at every enumerating site, and `604001fa`, `1e5d6875`, and `470c91de` all carry the grounding atom the readout would absorb.
- `corner` derives from `cell` alone, so `open_corner` needs no `grid`. `604001fa` and `1e5d6875` never feed `box.grid`, so the `inside`/`inner` route to a corner cell is closed to them without a new feed.
- The `cell(K, _)` grounding makes the relation total over the keys that have a cell, which is what `21897d95` reads with the key and the corner both bound. That site gains no atom, and it is one of four.
