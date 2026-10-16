# `Closed.wall` — the cells that wall a closed region

A per-key readout on `Closed`: a position outside the cell set one step from a region the set closes, reported with that region's id — the wall of each closed region. A solver that acts on the object that walls a region joins the wall with its own component labeling; a solver that counts the regions an object walls folds over the id.

```
// inside Closed<Key>
.decl wall(key: Key, p: Position, id: Ident)
wall(Ky, P, Id) :- region(Ky, Q, Id), dir_elem(D), neighbor(Q, D, P), !cell(Ky, P).
```

Not: `Reach` seeded from a set (the cells the set reaches, not the cells beside it); `Surround` (a cell walled at every neighbor, with no region); `Rim.rim_dir` (the set's own boundary and the direction it faces); `Abut` (contact that keeps the direction); a one-step band around an arbitrary set with no closed region behind it; `Bbox.edge_cell` contact.

Match: a rule joining `Closed.region` (or a `Reach` negation that states enclosure from the grid edge) with one `neighbor` step over `dir_elem` onto a cell of the closing set, its component label, or its color, with no direction in the head. Grep `region(` beside `neighbor(` in `programs/solvers/*.dl`, and `!.*reach(` beside `neighbor(`; match with the parser.

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

Survey: 2026-09-10 15:06 — the solvers since 2026-09-10 07:26.

## Survey: `Closed.wall` over the given scope (437 solvers)

Method: the matcher at `/Users/davidlu/code/arc-workspace/.scratch/surveys/Closed-wall/match.py` parses each scope solver and reports every rule that reads a positive `<Closed inst>.region` or a negated `<Reach inst>.reach` beside a `neighbor` step, plus one-hop consumers of such a rule that take a `neighbor` step. A lexical sweep (`Closed<`, `Reach<`, `region(`, `reach(`, and `neighbor(` on lines naming hole/enclose/trap/cavity/interior) covered enclosure stated any other way. Lexical hits are in `/Users/davidlu/code/arc-workspace/.scratch/surveys/Closed-wall/hits.txt`.

### 1. Callers

Five, all direct matches, none a `// family:` sibling. Each steps over `dir_elem` and joins the wall cell onto its own component labeling in the same rule.

1. `810b9b61` — `wall` (line 82): the ink component of color `Col` one step from a region that `Col` closes off; `Closed<Color>`, id bound to `_`.
2. `358ba94e` — `cavity_count.item` (line 57): the closed bg regions one step from each square, tallied per square; reads the id.
3. `67e490f4` — `stencil(Id, $Bordering())` (line 57): the object one step from any closed field region; id bound to `_`.
4. `37d3e8b2` — `Parse.joint_holes.item` (line 62): the closed bg regions one step from each object, tallied per object; reads the id.
5. `320afe60` — `encloses(Id, $Joint())` (line 67): the shape one step from any closed bg region; id bound to `_`.

Negative evidence: the parser match found no other rule in the scope that joins `Closed.region` or a negated `Reach.reach` with a `neighbor` step, and the one-hop pass found only `15663ba9` (part 2). The two callers the entry lists outside this scope (`0a2355a6`, `184a9768`) are not in the scope.

### 2. Near-misses

1. `18419cfa` `doorway` (line 84) — steps from a region cell onto wall-colored cells on both sides of one axis; the head keeps the axis and names the interior cell, so it is not the wall (excluded by "with no direction in the head").
2. `15663ba9` `faces_open` (line 50) — the one-hop hit: a step from a bend cell onto a cell that is not enclosed; the step lands on the open complement, not on the closing set.
3. `543a7ed5` `outline_cell($Band())` (line 77) — one `dir8_elem` step off a shape cell onto `outside.reach`: a band around a set with no closed region behind it.
4. `71e489b6` `halo` (line 65) — a `dir8_elem` band around `hole`, which is a thin ground cluster with no passage, not a `Closed` region.
5. `46c35fc7` `parse.ring` (line 55) — `Surround`: eight ink cells around one hole cell.
6. `5adee1b2` `painted` (line 63) — positive per-shape `outside.reach` on box cells; no neighbor step, and it names the cells the shape leaves open, not the wall.
7. Per-closer keying, no neighbor step: `320afe60` `encloses(Id, $Own())`, `37d3e8b2` `own_holes.item`, `4b6b68e5` `trapped`, `3a25b0d8` `hole`, `445eab21` `measure.item`, `1a6449f1` and `1c786137` `region`, `89565ca0` `size.item`, `7d1f7ee8` `enclosed`. In each, `Closed` is keyed by the closer (color, outline id, figure id), so the key names the wall's owner and the "own" reading needs no step.
8. Cell-level enclosure with no step onto the closing set: `44d8ac46`, `5168d44c`, `7ee1c6ea` (`Closed.region` read as a cell set); `60a26a3e`, `6e453dd6`, `782b5218`, `7b6016b9`, `83302e8f`, `45a5af55` (negated `Reach.reach` read as a cell test).

### 3. Spec

No change. The five callers in scope agree with the entry's recorded result:

1. The readout belongs on `Closed`: every caller reads its wall from a `Closed` instance, and every step is over `dir_elem`; no site in scope steps over `dir8_elem` onto a closed region.
2. The id column stays: two callers (`358ba94e`, `37d3e8b2`) fold over it in a `Tally`; the other three bind it to `_`.
3. The `!cell(Ky, P)` filter in the proposed rule is implied at every site by the join onto the caller's own labeling (ink, object, shape), which is disjoint from the closed set; no caller reads the wall cell without that join, so the exclusion costs nothing and matches every site.

`37d3e8b2`'s `Parse` comp is the same rule as `0a2355a6`'s (outside scope, per the entry), and neither file carries a `// family:` line; that is a family-marker gap, not a spec signal.

### 4. Reimplementations

Reimplementations: none. The `Reach` plus `!reach` forms in `15663ba9`, `543a7ed5`, `60a26a3e`, `6e453dd6`, `782b5218`, `7b6016b9`, and `83302e8f` are the cell-level enclosure unit lib names (`Reach` seeded from the edge), not hand-written `Closed`.
