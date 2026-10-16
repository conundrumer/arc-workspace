# `Surround<Key>` — a cell walled in by another set

The cells of a keyed domain whose every neighbor lies in a second keyed set, the wall. The domain is its own input and need not exclude the wall: `Rim.interior` is the case where the domain is the wall. Off the frame counts as a gap, so a cell on the grid edge is never surrounded. The known sites read the hole of a ring, a plus center whose four arms share a color, and a cup, the bg cell with one open side.

```
.comp Surround<Key> {
    // The cells tested, per key.
    .decl cell(key: Key, p: Position)  // input

    // The set that walls, per key.
    .decl wall(key: Key, p: Position)  // input

    .decl dir(d: Dir8)
    dir(D) :- dir_elem(D).

    // Some step toward d leaves the wall — off the frame counts as leaving.
    .decl gap_dir(key: Key, p: Position, d: Dir8)
    gap_dir(K, P, D) :- cell(K, P), dir(D), neighbor(P, D, Q), !wall(K, Q).

    .decl surrounded(key: Key, p: Position)
    surrounded(K, P) :- cell(K, P), !gap_dir(K, P, _).
}

// Surround under 8-adjacency.
.comp Surround8<Key> : Surround<Key> {
    dir(D) :- dir8_elem(D).
}
```

Not: `Rim.interior` (a member of the set it is judged by); `flanked` and `bend` (two sides, not every side); `Closed` and `Reach` (enclosure by flood from the grid edge, at any distance); a fold over a caller-supplied subset of directions that keeps the direction.

Match: a rule that negates a defect over every direction of `dir_elem` or `dir8_elem`, where the defect is `neighbor` from a cell of one set landing on a cell that is not in a second set, and the tested cell's set differs from the second set. The defect may be stated positively as a count of neighbors in the set equal to the class size. Coarse grep: `dir_elem(D), neighbor(` and `dir8_elem(D), neighbor(` beside a negated set atom; match with the parser.

Survey: 2026-09-10 01:17

Callers, seven; none is a `// family:` sibling:

- 6c434453 — `open` / `hole`, the hole of a 3×3 ring: a bg cell with ink on all four sides. Domain bg, wall ink.
- 0962bcdd — `Parse.arm` / `mismatch` / `marker`, a plus center whose four cardinal neighbors hold one non-bg color. Domain every cell, wall keyed by the arm color. Shared by both cases.
- 642d658d — `arm` / `mismatch` / `ring`, four neighbors present and sharing a color, keyed by that color, domain every cell; the detects filter the center afterward.
- 60a26a3e — `ring_gap` / `center($Ringed())`, a bg cell with a `params.ring` cell at each cardinal. Its `$Enclosed` case is the `Reach` peer.
- 54d82841 — `walled` / `free`, the `gap_dir` readout alone: `free(P, D)` feeds `Unanimous<Position, Dir>`, so the cup is the bg cell with one free side.
- 46c35fc7 — `Parse.gap` / `ring`, `Surround8`: a non-ink cell with ink at all eight neighbors; `ring` re-walks the eight neighbors with their direction to read the colors.
- d9fac9be — `defect` / `out($Ring())`, `Surround8` keyed by ink color, domain every cell, the cell's own color then required to differ; and `gap` / `out($Full())`, wall every non-bg cell.

Near-misses:

- 3ad05f52 `door` — wall on both sides of one axis: `flanked`, whose caller it already is.
- 15663ba9 `faces_open` — the two dirs of one corner, a direction subset.
- 5b37cb25 `closed` / `bite.item` — the blob tested two steps out, with the open direction kept; the wall is not the neighbor.
- 77fdfe62 `unscreened` / `fenced`, af902bf9 `open_quad` — enclosure at any distance, not adjacency.
- 1b8318e3 `beside` / `side`, f0df5ff0 `painted` — existential over directions, a dilation.
- 409aa875 `apex`, 142ca369 `elbow` — `Rim` on the cell's own set over the two flanks of one direction.

Spec:

- Both adjacencies have callers (five cardinal, two 8-adjacency), so `Surround` with the `Surround8` override stands as written.
- `gap_dir` stays exposed: 54d82841 reads it with the direction kept and never reads `surrounded`. No site needs the wall neighbor's direction from the comp; 46c35fc7 re-walks `neighbor` after the fold.
- The domain is independent of the wall: at d9fac9be `$Full` and 642d658d the domain is every grid cell, and membership is filtered afterward. The index sentence carries that reading.
- Three callers key the wall by a color chosen per site, with the domain replicated per key; the keyed interface serves them unchanged.

Reimplementations: none. The hand-written pieces beside the sites are the operation itself, edge-seeded `Reach` for enclosure at a distance, and footprints `lib.dl` does not hold.
