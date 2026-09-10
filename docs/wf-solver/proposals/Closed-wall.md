# `Closed.wall` — the cells that wall a closed region

A per-key readout on `Closed`: a position outside the cell set one step from a region the set closes, reported with that region's id — the wall of each closed region. A solver that acts on the object that walls a region joins the wall with its own component labeling; a solver that counts the regions an object walls folds over the id.

```
// inside Closed<Key>
.decl wall(key: Key, p: Position, id: Ident)
wall(Ky, P, Id) :- region(Ky, Q, Id), dir_elem(D), neighbor(Q, D, P), !cell(Ky, P).
```

Not: `Reach` seeded from a set (the cells the set reaches, not the cells beside it); `Surround` (a cell walled at every neighbor, with no region); `Rim.rim_dir` (the set's own boundary and the direction it faces); `Abut` (contact that keeps the direction); a one-step band around an arbitrary set with no closed region behind it; `Bbox.edge_cell` contact.

Match: a rule joining `Closed.region` (or a `Reach` negation that states enclosure from the grid edge) with one `neighbor` step over `dir_elem` onto a cell of the closing set, its component label, or its color, with no direction in the head. Grep `region(` beside `neighbor(` in `programs/solvers/*.dl`, and `!.*reach(` beside `neighbor(`; match with the parser (`tests/test_ast_match.py`).

Survey: 2026-09-10 07:26

Scope: the whole corpus, 697 solvers. Every rule reading `Closed.region`, or a negated edge-seeded `Reach.reach`, beside a `neighbor` step, and every consumer of those one rule away, matched with the parser.

Callers, seven; none is a `// family:` sibling:

- `810b9b61` — `wall`: the ink component one step from a region its color closes. Key = color; id folded away.
- `358ba94e` — `cavity_count.item`: the closed bg regions one step from each square, counted per square. Reads the id.
- `67e490f4` — `stencil(Id, $Bordering())`: the object one step from any closed field region. Id folded away.
- `0a2355a6` — `Parse.joint_holes.item`: the closed bg regions one step from each object, counted per object. Reads the id.
- `37d3e8b2` — `joint_holes.item`: the same rule in an identical `Parse` comp. Neither file is marked a sibling of the other.
- `320afe60` — `encloses(Id, $Joint())`: the shape one step from any closed bg region. Id folded away.
- `184a9768` — `frame`: an object one step from a hole, where the hole is the cell-level `Closed` (`Reach` from the edge plus negation). No id exists.

Every caller steps over `dir_elem` and joins the wall cell onto its own component labeling in the same rule.

Near-misses:

- `18419cfa` `doorway` — a region cell with wall-colored cells on both sides of an axis; the head keeps the axis and names the interior cell.
- `15663ba9` `faces_open` — a step onto the open complement, not onto the closing set.
- `543a7ed5` `outside.reach` beside a `dir8_elem` step, `71e489b6` `halo` — a one-step band off a set with no closed region behind it.
- `46c35fc7` `parse.ring` — `Surround`.
- Per-closer keying (`0a2355a6` and `320afe60` `$Own`, `2d0172a1` `encloses`, `4b6b68e5` `trapped`, `3a25b0d8` `hole`, `445eab21` `measure.item`, `1a6449f1` and `1c786137` `region`): `Closed` is keyed by the object whose complement is flooded, so the key names the closer and no neighbor step is taken. The "own" reading beside the callers' "joint" reading.

Spec:

- The readout belongs on `Closed`: every site reads the wall from a `Closed` instance or its cell-level half, and none steps over `dir8_elem`. `184a9768` would swap its `Reach` for a `Closed` to call it.
- The id column stays: three callers fold over it, the other four bind it to `_`. No caller reads the wall cell without joining it onto its own labeling.

Reimplementations: none. `184a9768`'s `Reach` plus negation is the cell-level unit lib names, not a reimplementation of `Closed`.
