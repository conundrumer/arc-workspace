# `Collinear<Key>` — the line family a cell set lies along

The line families under which every member of a keyed cell set shares one line: the set is a straight run, a dashed line, or scattered marks on one row, column, or diagonal, and `along` names the family and so the set's axis. A singleton lies along every tested family; a caller that tells a segment from a dot narrows with `multi_cell`. It is the converse containment of `LineCover`, which finds a line inside a set; this finds a set inside a line.

```
.comp Collinear<Key> {
    // The set tested, per key.
    .decl cell(key: Key, p: Position)  // input

    // The line families tested, per key: a solver tests the axes it has
    // (`axis_elem`, `diag_axis_elem`, `axis4_elem`).
    .decl axis(key: Key, a: Axis4)  // input

    // same_line over the set, so the universal below can negate it.
    .decl aligned(key: Key, a: Axis4, p: Position, q: Position)
    aligned(Ky, A, P, Q) :- cell(Ky, P), cell(Ky, Q), axis(Ky, A), same_line(A, P, Q).

    // Some pair of the set shares no line of the family.
    .decl bent(key: Key, a: Axis4)
    bent(Ky, A) :- cell(Ky, P), cell(Ky, Q), axis(Ky, A), !aligned(Ky, A, P, Q).

    // The set lies on one line of the family.
    .decl along(key: Key, a: Axis4)
    along(Ky, A) :- cell(Ky, _), axis(Ky, A), !bent(Ky, A).
}
```

Not: `LineCover` and `LineColor` (a line the set covers or colors whole); `run_line` (the line two adjacent members trace, with no test on the rest of the set); `Runs` (maximal segments inside lines); `flanked` and `bend` (one cell's neighbors); a set against a frame edge (`dist(P, D, 0)` over every member, as 3bd67248 `off_edge`), which is collinearity with the edge line fixed; two members on one line with no universal over the set (`same_line` alone); `OrderFrame`, which orders members along an axis it is given, and its precondition that distinct members share no line (50aad11f `shared_line`), a separation across members rather than a set inside a line.

Match: a defect relation over two atoms of one cell set and an axis, negating `same_line` (through a materialized helper) or comparing the across components of `split` (or `corner_dist` for a diagonal) for inequality, negated in a second rule over the same set and axis. Grep signature: `grep -ln 'same_line(\|split(' programs/solvers/*.dl`, then read for a per-set defect relation that a later rule negates. The hand-written shape is matched with the parser (`tests/test_ast_match.py`).

Survey: 2026-09-10 07:05 — over the whole corpus.

Eight solvers write the operation, each its own family representative. The three known hand-written sites take the entry's defect form; four more state it through `Unanimous` over a line coordinate of the set's cells (the `along` or `across` component of `split`, or `dist` to an edge), reading `value` or `!clash`; one states it through a disequality over materialized line ids. Every site tests the cardinal axes only, except the surfacing solver (diagonals only) and 22425bda (`axis4_elem`). Every site's singleton reading agrees with the entry's: a lone cell lies along every family, and 7ed72f31 (a point mirror has a line on both axes) and 538b439f (a lone dust cell is thin) rely on it. No site re-derives a lib primitive to state the operation. The matcher (`.scratch/80a900e0/collinear_match*.py`) ran over all 694 solvers: the defect-negation shape, the disequality over `split`/`corner_dist`/`dist` outputs and over materialized line ids, `Unanimous` over a line coordinate, and the pair-`same_line` shape; each hit was read in its rule.

## Callers

- 80a900e0 — `aligned`/`bent`/`along` (`:38-49`), the entry's code form over an 8-connected object's cells, diagonal families only; `segment` narrows `along` with a distinct-pair test, and `end` and `across` read the axis.
- 22425bda — `collinear`/`off_family`/`family` (`:31-40`): a color's visible cells all on one line of some family over `axis4_elem`; `line` then reads the whole grid line from any member with `same_line`.
- 12997ef3 — `off_axis`/`layout_axis` (`:34-41`): the marker set, unkeyed, over `axis_elem`, the defect written as a disequality over `split` across components; the axis feeds `OrderFrame`.
- 538b439f — `reach` with `thin` (`:49-53`): `Unanimous` over each component's `split` along component per axis; a component on one line of some axis is a segment, not a rectangle. The axis is projected away.
- 67a423a3 — `color_line` (`:33-37`), `$Color` case: `Unanimous` over a color's `split` across component per axis; the cells of one color all in one row or column. It reads the line coordinate from `value`.
- 7ed72f31 — `mirror_line` (`:34-37`): `Unanimous` over a mirror run's `split` along component per axis; it reads the line coordinate from `value` as the flip's frame, absent on the axis a line mirror runs along.
- 221dfab4 — `Parse.marker_dist`/`step_dir` (`:49-53`): `Unanimous` over the marker cells' `dist` to each edge, `!clash` read per `Dir`; the segment lies square to `D`, which is `along` the perpendicular axis. The comp is keyed, and serves the program and `Determine`.
- 2de01db2 — `shared` (`:41-43`): a color on more than one line along `params.axis`, as a disequality over the color's materialized line ids; `!shared` is `along` at the stored axis. The `multi_cell` entry also lists this site, over the lines as members.

## Near-misses

- One pair on one line, with no universal over the set, which the entry excludes: 070dd51e `line_axis`, 2b01abd0 `line_axis`, 40853293 `mark_axis`, bdad9b1f `line` (`$Shape`) and `Determine.role`, cbded52d `fill` (`$Line`), 2dd70a9a `stub_dir`. Each derives the axis a set runs along from some two distinct members sharing a line.
- A set against a frame edge, which the entry excludes: 3bd67248 `off_edge` (program and `Determine`), 3ac3eb23 `Determine.off_edge`, f45f5ca7 `Parse.off_edge`, 6ad5bdfd `off_wall_edge`, 2601afb7 `Determine.anchor_bad`, 6cdd2623 `interior_color` (every cell on the border, any edge).
- Separation across members: 50aad11f `shared_line`, 67636eac `shared_line`. The universal is negative and ranges over pairs from distinct members — no two shapes share a line of the axis — which is `OrderFrame`'s separation precondition, not a set inside a line.
- Order between two sets: 1da012fc `behind`/`ahead`, a defect over `dist` of two components negated into "every cell of a nearer than every cell of b"; the test is `>=`, not equality.
- `Unanimous` keyed by the line with the color as value (`LineColor`), which the entry excludes: 538b439f, 67a423a3, 7d7772cc and the other `line_color` instances.

## Spec

- **The line coordinate is read at two callers.** 67a423a3 and 7ed72f31 take the line's axis-only Position from `Unanimous.value` and consume it (as a line key, as a flip frame). Under `along` alone they would read it back with `split` from any member — one atom, but a restatement. Two more callers realize the line as grid cells from a member: 22425bda `line` (`same_line`) and 221dfab4 `corridor`/`marker_line` (`same_line`, `same_dist`). The other four project the line away. Whether `Collinear` exposes the coordinate is open; for a diagonal family it is a scalar (`corner_dist`), not a Position, so one readout does not fit both.
- **`Unanimous` already states it at four sites.** 538b439f, 67a423a3, 7ed72f31, and 221dfab4 instantiate `Unanimous` over a line coordinate, and the concept there is agreement on a value, which the Lib units rule admits. What the comp adds over that is the `Axis4` family readout in one relation, diagonals (whose coordinate is not a `split` component), and the singleton note. Whether that is enough to name a unit is the judgment.
- **Axis vocabulary converts at three callers.** 221dfab4 wants a `Dir` (the pattern advances along the perpendicular), 538b439f and 7ed72f31 key by the `split` axis whose along component is shared, which is the perpendicular of `along`'s axis. Each conversion is one `perp` or `axis_of` atom; `Axis4` on `along` stands.
- **The pair-existential sites are a judgment.** The six near-misses under the first bullet state "the set is a segment along A" as "some two members share a line of A". On a segment the two agree; on an L the existential yields both axes. The `Not:` line rules them out as written; whether they are this operation written loosely, and so callers with `along` plus `multi_cell`, is for the closing judgment.
- **A `Not:` addition.** Separation across members (50aad11f, 67636eac `shared_line`) is not on the `Not:` line and matches the signature's shape.
