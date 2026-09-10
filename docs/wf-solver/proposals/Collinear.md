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

Survey: 2026-09-10 15:12 — the solvers since 2026-09-10 07:05, 045e512c, 0520fde7, 05f2a901, 08573cc6, 0934a4d8, 0c9aba6e, 0d87d2a6, 0dfd9992, 1190bc91, 11dc524f, 136b0064, 137f0df0, 13e47133, 142ca369, 1478ab18, 15113be4, 15663ba9, 16de56c4, 17829a00, 178fcbfb, 17cae0c1, 18286ef8, 182e5d0f, 18419cfa, 18447a8d, 195ba7dc, 195c6913, 1990f7a8, 19bb5feb, 1a07d186, 1a6449f1, 1acc24af, 1ae2feb7, 1b2d62fb, 1b59e163, 1b60fb0c, 1bfc4729, 1c02dbbe, 1c56ad9f, 1c786137, 1caeab9d, 1d0a4b61, 1d398264, 1d61978c, 1e32b0e9, 1e5d6875, 1e97544e, 1efba499, 1f0c79e5, 1f642eb9, 1f85a75f, 1f876c06, 2037f2c7, 20818e16, 20981f0e, 20fb2937, 212895b5, 21f83797, 2204b7a8, 221dfab4, 22208ba4, 22233c11, 22425bda, 22806e14, 22eb0ac0, 234bbc79, 239be575, 23b5c85d, 247ef758, 25094a63, 252143c9, 253bf280, 2546ccf6, 256b0a75, 25c199f5, 25d487eb, 25e02866, 2601afb7, 264363fd, 2685904e, 2697da3f, 269e22fb, 272f95fa, 2753e76c, 278e5215, 27a77e38, 27f8ce4f, 281123b4, 28e73c20, 291dc1e1, 292dd178, 29623171, 29700607, 2a5f8217, 2b01abd0, 2b83f449, 2ba387bc, 2bcee788, 2bee17df, 2c0b0aff, 2c181942, 2c608aff, 2c737e39, 2dc579da, 2e65ae53, 2f0c5170, 2f767503, 2faf500b, 305b1341, 3194b014, 31aa019c, 31d5ba1a, 320afe60, 321b1fc6, 332202d5, 3345333e, 337b420f, 3391f8c0, 33b52de3, 3428a4f5, 342ae2ed, 3490cc26, 34b99a2b, 34cfa167, 351d6448, 358ba94e, 3631a71a, 363442ee, 36a08778, 36d67576, 36fdfd69, 37d3e8b2, 38007db0, 396d80d7, 39a8645d, 39e1d7f9, 3a25b0d8, 3a301edc, 3aa6fb7a, 3ad05f52, 3bd292e8, 3bdb4ada, 3befdf3e, 3d31c5b3, 3d588dc9, 3d6c6e23, 3dc255db, 3e6067c3, 3e980e27, 3ed85e70, 3eda0437, 3ee1011a, 3f23242b, 40853293, 4093f84a, 409aa875, 40f6cd08, 412b6263, 414297c0, 41ace6b5, 4258a5f9, 4290ef0e, 42918530, 42a15761, 42a50994, 42f14c03, 42f83767, 4364c1c4, 444801d8, 445eab21, 446ef5d2, 447fd412, 44d8ac46, 44f52bb0, 456873bc, 45737921, 458e3a53, 45a5af55, 45bbe264, 4612dd53, 465b7d93, 469497ad, 46c35fc7, 46f33fce, 477d2879, 47996f11, 47c1f68c, 4852f2fa, 48634b99, 48d8fb45, 48f8583b, 4938f0c2, 494ef9d7, 4a1cacc2, 4a21e3da, 4aab4007, 4acc7107, 4b6b68e5, 4be741c5, 4c177718, 4c3d4a41, 4c416de3, 4c5c2cf0, 4c7dc4dd, 4df5b0ae, 4e34c42c, 4e45f183, 4e469f39, 4e7e0eb9, 4f537728, 4ff4c9da, 5034a0b5, 506d28a5, 50846271, 508bd3b6, 50a16a69, 50aad11f, 50c07299, 50f325b5, 5117e062, 5168d44c, 516b51b7, 5207a7b5, 522fdd07, 52364a65, 5289ad53, 52df9849, 52fd389e, 538b439f, 539a4f51, 53fb4810, 543a7ed5, 54d82841, 54d9e175, 54db823b, 54dc2872, 55059096, 551d5bf1, 5521c0d9, 5545f144, 55783887, 5587a8d0, 5614dbcf, 5623160b, 56dc2b01, 56ff96f3, 5751f35e, 5792cb4d, 57aa92db, 57edb29d, 581f7754, 5833af48, 58490d8a, 58743b76, 58c02a16, 58e15b12, 58f5dbd5, 5961cc34, 5a5a2103, 5a719d11, 5ad4f10b, 5ad8a7c0, 5adee1b2, 5af49b42, 5b37cb25, 5b526a93, 5b692c0f, 5c0a986e, 5c2c9af4, 5d2a5c43, 5d588b4d, 5daaa586, 5dbc8537, 5e6bbc0b, 5ecac7f7, 5ffb2104, 604001fa, 60a26a3e, 60b61512, 60d73be6, 6165ea8f, 623ea044, 62593bfd, 626c0bcc, 62ab2642, 6350f1f4, 63613498, 639f5a19, 642248e4, 6430c8c4, 6455b5f5, 64a7c07e, 64efde09, 652646ff, 65b59efc, 662c240a, 668eec9a, 66ac4c3b, 66f2d22f, 673ef223, 67636eac, 6773b310, 67a423a3, 67c52801, 67e490f4, 6855a6e4, 689c358e, 68b67ca3, 68bc2e87, 692cd3b6, 694f12f3, 696d4842, 69889d6e, 6a11f6da, 6a1e5592, 6a980be1, 6aa20dc0, 6ad5bdfd, 6b9890af, 6bcdb01e, 6c434453, 6ca952ad, 6cbe9eb8, 6cdd2623, 6d0160f0, 6d58a25d, 6df30ad6, 6e19193c, 6e453dd6, 6e4f6532, 6e82a1ae, 6ecd11f4, 6f473927, 6ffbe589, 6ffe8f07, 7039b2d7, 71e489b6, 72322fa7, 72a961c9, 72ca375d, 73c3b0d8, 73ccf9c2, 7447852a, 7491f3cf, 74dd1130, 753ea09b, 758abdf0, 759f3fd3, 75b8110e, 760b3cac, 762cd429, 7666fa5d, 770cc55f, 776ffc46, 780d0b14, 782b5218, 78332cb0, 7837ac64, 78e78cff, 79369cc6, 794b24be, 79fb03f4, 7acdf6d3, 7b0280bc, 7b3084d4, 7b5033c1, 7b6016b9, 7b80bb43, 7bb29440, 7c008303, 7c66cb00, 7c8af763, 7c9b52a0, 7d18a6fb, 7d1f7ee8, 7d419a02, 7d7772cc, 7ddcd7ec, 7df24a62, 7e0986d6, 7e2bad24, 7e576d6e, 7ec998c9, 7ed72f31, 7ee1c6ea, 7f4411dc, 800d221b, 80214e03, 80a900e0, 80af3007, 810b9b61, 817e6c09, 81c0276b, 825aa9e9, 82819916, 83302e8f, 833966f4, 83b6b474, 83eb0a57, 8403a5d5, 84551f4c, 845d6e51, 846bdb03, 85c4e7cd, 89565ca0, 8e5a5113, 94f9d214, 9565186b, 97999447, 995c5fa3, 99b1bc43, a68b268e, b1948b0a, b1fc8b8e, b7cb93ac, ba26e723, bbb1b8b6, bdad9b1f, cbded52d, ce22a75a, ce4f8723, cf98881b, d19f7514, d47aa2ff, d511f180, d9fac9be, dae9d2b5, e133d23d, e345f17b, e3497940, e98196ab, e9afcf9a, ea9794b1, ed74f2f2, f25ffba3, f2829549, fafffa47.

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
