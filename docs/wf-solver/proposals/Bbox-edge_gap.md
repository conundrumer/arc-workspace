# `Bbox.edge_gap` — the border cells the set does not draw

A per-key readout on `Bbox`: a grid cell on the d-side edge line of the set's bounding box that the set does not occupy — the break a drawn outline leaves in its own border, reported with the side it breaks. Existence per key, or per side, is the "the outline is whole" test; the cells themselves are what a solver that fills through, casts through, or individuates the breaks reads.

```
// inside Bbox<Key>
.decl edge_gap(key: Key, p: Position, d: Dir)
edge_gap(K, P, D) :- inside(K, P), edge_cell(K, Q, D), same_dist(D, P, Q), !cell(K, P).
```

Not: `Bbox.gap` (the whole box against the set, edge line included, with no side); this operation is that one narrowed to the edge line; `BoxCells.hole` (the strict interior of a margin box, with no member set); `BoxCells.on_edge` alone (the edge line, with no member test); `Rim` (the set's own boundary, which follows the set's shape); `Outset` (the band outside the box); a difference of the edge line against a set other than the one that fed the box.

Match: a rule joining a box edge-line atom (`BoxCells.on_edge` over a `Bbox.margin`, or an equivalent local edge-line relation) with the complement of the member set that box bounds. The complement takes several forms: a negated member atom, a color test over the same set, a negated mark relation. `grep -n 'on_edge' programs/solvers/*.dl` is a starting point only; the shape is matched with the parser.

Survey: 2026-09-08 21:31

## Spec

The question is which comp hosts the readout: `Bbox`, which already holds the member set, or `BoxCells`, which already holds the edge line and would take a `drawn(key, p)` input beside `cell`.

Five sites test the complement of exactly the set that fed the box — `551d5bf1` (`!box.cell`), `14b8e18c` (`!cell_of` is `box.cell`), `465b7d93` (`!mark` is `shape_box.cell`), `1c786137` (`!in(P, Col)` is `cbox.cell` at that key), `256b0a75` (`in(P, Col), !params.frame(Col)` is `!box.cell` through the color). At those five a `drawn` input would restate `Bbox.cell`, which the Indirection test rejects.

Two sites write the complement as a global set while the box is per component: `292dd178` (`!wall_cell`), `444801d8` (the wall color test). On every train and test input of those two tasks, no component's cell lies on another component's box edge line, so the global set and the key's own set give the same gaps. No surveyed site needs an occupancy set separate from the box's member set.

The cost falls on the `Bbox` host. `edge_gap` reads `inside`, which needs `grid` fed, and five of the seven sites feed `Bbox.cell` alone: `551d5bf1`, `14b8e18c`, `1c786137`, `292dd178`, `465b7d93`. Six of the seven keep their `BoxCells` instance for another readout either way — `hole` at `551d5bf1`, `14b8e18c`, `1c786137`, `292dd178`, and the full edge line at `256b0a75`, `444801d8` — so at `256b0a75` and `444801d8` the gap comes from one comp and the line it breaks from another.

Both output columns earn their place, and callers project. `14b8e18c`, `1c786137`, and `256b0a75` read the gap with no side; `465b7d93` reads the side and drops the position; `551d5bf1`, `292dd178`, and `444801d8` read both. The key is projected the same way: `551d5bf1` and `292dd178` discard it, the other four keep it.

## Callers

- `551d5bf1` — `leak.mark`: the undrawn cell of a rectangle outline's border, whose side is the direction the fill leaks out toward.
- `292dd178` — `cast.mark`: each undrawn border cell of a wall rectangle casts a ray outward on the side it breaks.
- `444801d8` — `open_side`: the side of a wall box holding a non-wall border cell is the side the fill escapes from.
- `465b7d93` — `edge_hole`: a side of the shape's box that the shape does not draw whole blocks the `$Stretch` paint on that side.
- `14b8e18c` — `border_gap`: an unbroken border qualifies the object for the `$Box` and `$Ring` cases.
- `1c786137` — `misdrawn`: a color whose cells do not draw its own box's border whole is not the outline color.
- `256b0a75` — `fill`: the gap cells of the frame box's border are the fourth bracket, and the rule reads their color.

`on_edge` appears in 15 rules across 10 files; the eight non-callers use the edge line positively.

## Near-misses

- The whole box interior against the set, with no edge line and no side — the `Bbox.gap` reading: `22806e14`, `264363fd`, `2ba387bc`, `320afe60`, `3345333e`, `42f14c03`, `44d8ac46`, `470c91de`, `538b439f`, `21897d95`, `3490cc26`, `3dc255db`.
- `271d71e2` — `abut_break`: the broken line is one step outside the box, which is the `Outset` band.
- `247ef758` — `header`: the box's edge line against the border's modal color, a subset of the set that fed the box rather than its complement.
- `41ace6b5` — `foot`: the cell a colored run skips, on a grid line fixed by that color's cells. There is no box.
- `3f23242b` — `edge_paint`: the edge line of a constructed `Frame2D`, negated against a geometric corner test. The frame bounds no member set.
- `465b7d93` — `rim`: interior cells one step off the edge line, not the edge line itself.

Survey: 2026-09-10 07:26

Scope: the 393 solvers edited since the first survey. Every hit not listed here or in the first result reads the edge line positively.

Spec: nothing changes the host question. Both new sites feed `Bbox.cell` alone and feed `BoxCells.cell` with `in(P, _)`. `68bc2e87` keeps its `BoxCells` for no readout but `on_edge`, so with `edge_gap` on `Bbox` that instance goes away, the second such site with `256b0a75`. `810b9b61` keeps `BoxCells` for `hole`. `68bc2e87` states the complement as a member atom at another key with a key disequality (`rect.cell(Col2, P), Col != Col2`), a form the Match line does not name.

Callers, new:

- `810b9b61` — `edge_gap`: a component whose box edge line holds a cell it does not draw is not a whole outline, so the `$Object` case does not recolor it. Reads existence per key.
- `68bc2e87` — `under`: a cell on a color's box edge line that shows another color was drawn later; the pairs order the colors. Reads key and position, joined to the cell's color.

Near-misses, new:

- The whole box against the set, no edge line and no side — the `Bbox.gap` reading: `7b0280bc`, `2bee17df`, `78e78cff`, `6cbe9eb8` (`gap`), `3d588dc9`, `58743b76`, `414297c0`, `58490d8a`, `7d18a6fb`, `465b7d93` (`field.cell`), and the crop renders that paint the box complement bg: `1f85a75f`, `39a8645d`, `48d8fb45`, `3a25b0d8`, `5ad4f10b`, `2037f2c7`, `278e5215`, `50aad11f`, `6ecd11f4`.
- `6cbe9eb8` `inward`, `4c3d4a41` `refuted_dir` — a member cell off the box's edge line: the reverse difference.
- `5daaa586` `side.item` — the edge line of a `MarginFrame` box with the corners negated out; the box bounds no member set.
- `78332cb0` `port` — a shape cell on the edge of a `Tile2D` tile; a fixed division, not a bounding box, tested for occupancy.
- `7d7772cc` `open_dir`, `20981f0e` `clear_step` — a box's margin against the grid edge; no member complement.

Reimplementations: none. The local edge-line relations met (`3f23242b`, `5af49b42`, `2601afb7`) test `dist(P, D, 0)` against the grid edge with no box in the file.
