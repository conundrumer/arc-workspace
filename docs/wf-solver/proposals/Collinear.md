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
- **`Unanimous` already states it at four sites.** 538b439f, 67a423a3, 7ed72f31, and 221dfab4 instantiate `Unanimous` over a line coordinate, and the concept there is agreement on a value, which the Lib components rule admits. What the comp adds over that is the `Axis4` family readout in one relation, diagonals (whose coordinate is not a `split` component), and the singleton note. Whether that is enough to name a component is the judgment.
- **Axis vocabulary converts at three callers.** 221dfab4 wants a `Dir` (the pattern advances along the perpendicular), 538b439f and 7ed72f31 key by the `split` axis whose along component is shared, which is the perpendicular of `along`'s axis. Each conversion is one `perp` or `axis_of` atom; `Axis4` on `along` stands.
- **The pair-existential sites are a judgment.** The six near-misses under the first bullet state "the set is a segment along A" as "some two members share a line of A". On a segment the two agree; on an L the existential yields both axes. The `Not:` line rules them out as written; whether they are this operation written loosely, and so callers with `along` plus `multi_cell`, is for the closing judgment.
- **A `Not:` addition.** Separation across members (50aad11f, 67636eac `shared_line`) is not on the `Not:` line and matches the signature's shape.

Survey: 2026-09-10 15:12 — the solvers since 2026-09-10 07:05.

## 1. Callers

Six solvers in the scope write the operation. Each is its own family representative. Line numbers are current.

1. 80a900e0 — `aligned` / `bent` / `along` (`programs/solvers/80a900e0.dl:39-49`): the entry's code form over an 8-connected object's cells, `diag_axis_elem` only; `segment` narrows `along` with a distinct-pair test, `end` reads the axis through `diag_axis_of`. The surfacing solver: the call site projects the line away and keeps the family.
2. 22425bda — `collinear` / `off_family` / `family` (`:32-40`): a color's ink cells all on one line of some family over `axis4_elem`; `line` (`:45`) then realizes the whole grid line from any member with `same_line`.
3. 538b439f — `reach` with `thin` (`:50-54`): `Unanimous` over each component's `split` along component per axis; a component on one line of some axis is a segment, not a rectangle. The axis and the line are projected away.
4. 67a423a3 — `color_line` (`:35-38`, `$Color` case): `Unanimous` over a color's `split` across component per axis; the line coordinate is read from `value` as the `line` key.
5. 7ed72f31 — `mirror_line` (`:37-38`): `Unanimous` over a mirror object's `split` along component per axis; `value` is the flip frame, absent on the axis a line mirror runs along.
6. 221dfab4 — `Parse.marker_dist` / `step_dir` (`:51-56`): `Unanimous` over the marker cells' `dist` to each edge, `!clash` read per `Dir`; `corridor` and `marker_line` (`:59-70`) realize the line from a member with `same_line` and `same_dist`. Keyed, serving the program and `Determine`.

The entry's other two recorded callers, 12997ef3 and 2de01db2, are outside this scope. Negative evidence for the rest of the scope: the parser matcher ran over all 437 solvers with six shapes (defect helper negated over a set pair; `!=` over line-prim outputs; `Unanimous` over a line coordinate; `!=` over transitively line-bound columns; `dist(P, D, K), K != 0` in a negated head; existential `same_line` over a set pair), plus a second pass for a negated helper defined by `dist(_, _, 0)` or `gt(_, ORIGIN)`; the grep signature (`same_line(`, `split(`, `same_dist(`, `corner_dist(`, `Unanimous`) hit 182 files, 370 lines. Every hit was read in its rule. Outside the six above, every hit is a line-key materialization from `split`, a `LineColor` instance, a cast or line read from one mark, a corner test, a mirror-consistency check (0934a4d8, 3631a71a `cell_split`), or one of the near-misses below.

## 2. Near-misses

1. One pair on one line, no universal over the set (`same_line` alone): 2b01abd0 `line_axis` (`:22-24`), 40853293 `mark_axis` (`:21-24`), bdad9b1f `line` `$Shape` (`:38-40`) and `Determine.role` (`:67-71`), cbded52d `fill` `$Line` (`:67-70`), 7e576d6e `span.axis` (`:100`, a segment's two endpoints), 195c6913 `on_strip` (`:69-72`, a swatch with some other swatch on its line). Each derives an axis from two members sharing a line.
2. A merge of collinear cells, pairwise with no universal: 5289ad53 `lines.equiv` (`:71-74`), `Canon` over same-color `same_line`.
3. A set against a frame edge, which the `Not:` line excludes: 6ad5bdfd `off_wall_edge` (`:60-61`), 2601afb7 `Determine.anchor_bad` (`:156-157`), 6cdd2623 `interior_color` (`:45-48`).
4. Separation across members, which the `Not:` line excludes: 50aad11f `shared_line` (`:38-42`), 67636eac `shared_line` (`:74-77`).
5. A side the wall covers whole, which is `LineCover` with the edge line fixed: 508bd3b6 `open_edge` (`:53-56`).
6. `Unanimous` keyed by the line with the color as value (`LineColor`): 7d7772cc and the other `line_color` instances.
7. `Unanimous<_, Position>` that tests a singleton (`multi_cell`, not a line): 1b59e163 `obj_pos`, 2f0c5170 `alone`, 581f7754 `lone`/`sole`, 78e78cff `lone`, 39e1d7f9 `obj_cell`/`motif_hue`.

## 3. Spec

The scope adds no caller and no new form; the sites in part 1 are the six in-scope members of the recorded survey, unchanged in shape. No interface or definition change follows from this scope.

1. The coordinate readout question stands as recorded: two callers read the line coordinate from `Unanimous.value` (67a423a3, 7ed72f31), two realize the line from a member (22425bda, 221dfab4), and two project it away (80a900e0, 538b439f). The surfacing solver alone projects the line away and reads the family; that is caller-only evidence.
2. `Axis4` on `along` stands: the scope's callers use `axis_elem` (four), `diag_axis_elem` (80a900e0), and `axis4_elem` (22425bda); 221dfab4 converts to `Dir` with one `axis_of`.
3. The pair-existential judgment in the entry's spec gains two in-scope sites (7e576d6e `span.axis`, 195c6913 `on_strip`) of the same loose shape.
4. The `Not:` line still lacks the separation-across-members exclusion (50aad11f, 67636eac), as the entry's last spec bullet says.

## 4. Reimplementations

Reimplementations: none.
