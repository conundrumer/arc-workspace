# `D4Map.onto` — the D4 elements that carry one cell set exactly onto another

The ops under which src and dst are the same set: `map` holds and no dst cell is left over. `map` alone reads one way — every src cell lands on a dst cell of its value — so it also holds when the image is a proper part of dst, and a solver asking whether two objects are the same shape wants the two-way reading. With dst = src the two readings agree, so this separates only the sites that compare two different sets.

```
    // A dst cell no src cell reaches under d — the leftover `map` allows.
    .decl over(key: Key, d: D4)
    over(K, D) :- dst(K, Q, V), d4_elem(D), d4_inverse(D, D_back), apply(D_back, Q, P), !src(K, P, V).

    // The ops carrying src onto dst: into it, with nothing left over.
    .decl onto(key: Key, d: D4)
    onto(K, D) :- map(K, D), !over(K, D).
```

Not: `map` (src into dst); `compatible` (agreement where both cells exist); self-symmetry, where src = dst makes the two readings one; a shape found among cells at an unknown placement (`Occurrences`).

Match: a `D4Map` whose `src` and `dst` come from two different objects; `map(` read as an equivalence, as `Canon.equiv` or as a same-shape test; a pair of `map` atoms joined by `d4_inverse`; a `KeyedSetCompare.equals` whose pattern set is the D4 images of one cell set, keyed by D4.

Survey: 2026-09-09 05:34.

Callers: 6165ea8f (`same_shape`, a pair of `map` atoms joined by `d4_inverse` over a pair-keyed instance that holds both directions); 409aa875 (`pick.equiv`, one-way `map` fed to `Canon.equiv`, whose input is documented as an equivalence — one-way `map` is reflexive and transitive but not symmetric, so the site asks for a relation `map` does not give, and D4 being a group makes `onto` symmetric); 62593bfd (`onto`, the entry's code written out beside a pair-keyed instance: two blobs are the same shape when a D4 element carries one onto the other, and that decides which edge each blob slides to); 67e490f4 (`onto`, the entry's code beside a pair-keyed instance over a cutout and an object, each read in its own box, with the element then tested against a stored `Sym` through `sym_member`); 845d6e51 (`onto`, the entry's code beside a pair-keyed instance over a query shape and a legend shape, each read in its own box, with the element then tested against a stored `Sym` through `sym_member`).

Of 31 `D4Map` instances across 26 solvers, 21 feed `src` and `dst` from one relation, where the two readings agree. Ten cross-feed two sets, and eight of those want another reading:

- The into-reading, with `dst` wider than the image by design, so `onto` is false there by construction: 8e5a5113 `lookup` (a tile's ink against an output tile total over every color), f25ffba3 `stamp` (an example's ink against the whole output grid).
- Both sides total over one frame of equal extent, where `map` already implies `onto`: 4522001f `pair`, 8ee62060 `block`, be03b35f `d4m`, 47c1f68c `tile_map`, 8e5a5113 `step`, f25ffba3 `tile`.

Near, outside `D4Map`: 0e206a2e `seat` seeks each D4 image of a pattern among marker cells at an unknown placement, which is `Occurrences`; 39a8645d `same_shape`, 5dbc8537 `congruent`, and 42f14c03 `shape` test two `BoxFrame.inner` sets for one shape through `KeyedSetCompare.equals`, under translation alone, with no D4 element.

No site writes the operation by hand. Of the rules joining an `apply` atom with a negated atom (14 rules in 13 files), each transforms a position and tests one set. `d4_inverse` stands in three solvers: 0dfd9992 tests whether an element is its own inverse, and 21897d95 walks an output cell back to its input cell.

Spec: `map` keeps the into-reading, which the first near-miss group wants, so this is an addition beside `map` and not a redefinition of it. The element stays in the second column — both callers drop it, and it costs them nothing to carry.

Survey: 2026-09-09 05:50, over the solvers at or after the first survey's time

That pass read the four solvers whose file time is at or after 05:34. It found no caller and no reimplementation, and the spec point gains no evidence. `626c0bcc` is the one file the first pass had not seen, and it looks like a congruence site without being one: its `occ` instance seeks four stored 2×2 pieces among the ink cells, three of them rotations of one another, but the pieces stand as four separate catalog entries rather than as D4 images of one, and the match is translation-only — the `Occurrences` case the `Not:` line already names. Its `Determine.piece` stores each painted region from its own `BoxFrame.inner`, so identical shapes coincide under translation, which is the exclusion that covers 39a8645d, 5dbc8537, and 42f14c03.

Survey: 2026-09-09 23:00, over the solvers at or after the second survey's time

That pass read the 310 solvers in scope other than 67e490f4.

Callers: 36d67576 (`poses`, a `KeyedSetCompare<Ident, D4, Position>` whose pattern set is each D4 image of the model part's shape and whose observed set is each part's shape; `poses.equals(Id, D)` is the element carrying the model's shape exactly onto part `Id`'s, and the rule after it reads `D` to carry the model's marks by that pose — `onto` stated through another primitive, in a form the `Match:` line now names). 6165ea8f, 409aa875, and 62593bfd stand unchanged at their call sites. Of 17 `D4Map` instances in 13 scope solvers, 13 feed both sides from one relation (18419cfa, 2c181942, 3a25b0d8, 44d8ac46, 44f52bb0, 47996f11, 47c1f68c `grid_map`, 4c5c2cf0, b7cb93ac); the cross-feeds are the prior callers, 47c1f68c `tile_map`, and 64efde09.

Near: 64efde09 `cong`, a pair-keyed cross-feed of two solid bars of one extent, where `map` already implies `onto`; 1acc24af `seat`/`uncovered`, 50f325b5 `seek`, 291dc1e1 `occ`, 412b6263 `seat`, D4 images of a shape sought at an unknown placement (`Occurrences`); 4938f0c2 `orbit` and 4c5c2cf0 `same`, a group's whole orbit tested against the output's ink, keyed by `Sym`, where no single element carries one set onto the other; 3e980e27 `refuted`, a stamp's D4 read against a total `ex_out` (the into-reading); 4c7dc4dd `Induce.defect`, an exact two-way comparison at the identity, inside the `Induce` proposal comp; 2c181942 `mate`, a line subset at a found placement; 39a8645d, 5dbc8537, 42f14c03, translation-only.

Spec: the element column is read by a caller — 36d67576 applies the `D` it reads from `poses.equals`, and 64efde09 applies the `G` it reads from `map` — so it stays for that reason rather than for cost alone. `map` keeps the into-reading, which 3e980e27 wants.

Reimplementations: none.

Survey: 2026-09-10 08:23, over the solvers at or after the third survey's time

That pass read the 385 solvers in scope other than 845d6e51.

Callers: 3d588dc9 (`key_match`, a `KeyedSetCompare<Ident, D4, Position>` whose pattern set is the stored key footprint in every pose of its `RIGID` chart and whose observed set is each object in its box; `key_match.equals(Id, D)` is the element carrying the footprint exactly onto object `Id`, and `key_cell` reads that `D` to pair each key cell with its footprint cell); 4c177718 (`pose`, a `KeyedSetCompare<Unit, D4, Position>` whose pattern set is the `RIGID` chart's glyph in every pose and whose observed set is the arrow in its box; `pose.equals($U(), D)` is the element carrying the glyph exactly onto the arrow, and the rule reads `D` for `params.chart_tip(D, ...)`). 36d67576, 6165ea8f, 409aa875, 62593bfd, and 67e490f4 stand unchanged at their call sites. Of 17 `D4Map` instances in 17 scope solvers, 14 feed both sides from one relation (new among them 6aa20dc0, 72ca375d `inv`, 73ccf9c2 `inv`); the cross-feeds are the prior callers, 64efde09, and 6aa20dc0. `d4_inverse` stands only in 0dfd9992, 6165ea8f, 62593bfd, 67e490f4. Of the rules joining an `apply` atom with a negated atom (9 rules in 8 files), each but the two `over` rules transforms a position and tests one set.

Near: 6aa20dc0 `fit`, a cross-feed of the template picture against a pair's two square tiles, read through `compatible`, where the dst is two cells by design; 72ca375d `inv` and 73ccf9c2 `inv`, self-symmetry of a box-framed crop; D4 images of a shape sought at an unknown placement (`Occurrences`): 142ca369 `occ`, 3aa6fb7a `occ`, 409aa875 `occ`, 6e4f6532 `seat`, 79369cc6 `occ`, 7df24a62 `occ`, 7b3084d4 `occ`, b7cb93ac `occ`; translation-only `KeyedSetCompare.equals` over box-framed sets: 2a5f8217 `same`, 4ff4c9da `footprint`, 63613498 `same`, 776ffc46 `same_shape`, 4c5c2cf0 `known`, 5a5a2103 `glyph`/`twin`, 38007db0 `same`.

Spec: the element column is read by three callers now (36d67576, 3d588dc9, 4c177718), so it stays. A `RIGID` chart cannot feed `src` as written: it exposes only placed poses, and the stored pose is unobservable, so 3d588dc9 and 4c177718 would need `src` fed from one named pose, a literal the program bans. Either `Callers` separates the sites that would call `onto` from a single `src` pose (36d67576, 62593bfd, 67e490f4, 6165ea8f, 409aa875, 845d6e51) from the sites that state it over a `RIGID` chart (3d588dc9, 4c177718), or the operation takes an already-posed image set, a D4-keyed src, beside the single-pose `src`. `map` keeps the into-reading; no new evidence on that point.

Reimplementations: none.

Survey: 2026-09-10 08:31, over the solvers at or after the fourth survey's time

That pass read the three solvers in scope: 84551f4c, 83eb0a57, 8403a5d5.

Callers: none. No solver in scope instantiates `D4Map`, `KeyedSetCompare`, or `Canon`, and none writes `d4_inverse`. The one `apply` atom in scope (84551f4c `landed`) turns a bar's displacement from its base by a `C4` element and composes it back, with no negated atom: a position transform over one set, not a comparison of two.

Near: 83eb0a57 `occ`, an `Occurrences<Ident, Color>` that seeks each rectangle, recolored to canvas colors, within the canvas at an unknown placement, under translation alone (`Occurrences`); 8403a5d5 `seated`, a stored template placed on the marker by `displacement`/`compose`, translation alone, one set painted rather than two compared; 8403a5d5 `Determine.si`, a `ShiftInvariance<Example, Color>` read for a period, a translation-invariance test on one set.

Spec: no new evidence; the element-column point and the `RIGID`-chart point stand as the fourth survey left them.

Reimplementations: none.

Survey: 2026-09-10 15:25 — the solvers since 2026-09-10 08:31.

## Scope

456 solvers, all present. Nearly all were rewritten after the entry's last `Survey:` line (2026-09-10 08:31), so this pass read the whole scope from the signatures rather than a newer-files slice. Signatures run: `D4Map` inits (28 instances in 24 solvers), `KeyedSetCompare` inits (77), `Canon` inits (28), `d4_inverse` (7 lines), `sym_member`, `Occurrences` inits (42), every `.map(` read, and a parser matcher (`match.py`) for the shapes: an `apply` atom beside a negated atom (15 rules), two `map` atoms joined by `d4_inverse` (1), a `Canon.equiv` head fed from `map` (1), a `pattern_member`/`shape` head fed through `apply` (5), and an `apply` rule reading one relation twice (18).

## 1. Callers

1. 6165ea8f `same_shape` (`/Users/davidlu/code/arc-workspace/programs/solvers/6165ea8f.dl:74`) — two `cong.map` atoms joined by `d4_inverse` over a pair-keyed instance of two box-framed legend shapes; a pair is the same shape when one element carries A onto B and its inverse carries B back.
2. 409aa875 `pick.equiv` (`409aa875.dl:166`) — one-way `same.map` fed to `Canon.equiv`, whose input is documented as an equivalence; the site asks for the symmetric relation `onto` gives.
3. 62593bfd `onto` (`62593bfd.dl:58-71`) — the entry's `over`/`onto` code written out beside `shape_map`, a pair-keyed instance of two blobs in their boxes; a blob paired by shape slides to the paired edge.
4. 67e490f4 `onto` (`67e490f4.dl:101-118`) — the entry's code beside `cong` over a cutout and an object, each in its box; the element is then tested against a stored `Sym` through `sym_member`, and the object's color feeds `Mode`.
5. 845d6e51 `onto` (`845d6e51.dl:72-83`) — the entry's code beside `cong` over a query shape and a legend shape; the element is tested against a stored `Sym`, and the query takes the legend's color.
6. 36d67576 `poses` (`36d67576.dl:53-63`) — `KeyedSetCompare<Ident, D4, Position>` whose pattern set is each D4 image (via `apply`) of the model part's shape and whose observed set is each part's shape; `poses.equals(Id, D)` is the element carrying the model exactly onto part `Id`, and `carried` applies that `D` to the model's marks.
7. 3d588dc9 `key_match` (`3d588dc9.dl:62-72`) — `KeyedSetCompare<Ident, D4, Position>` whose pattern set is the stored key footprint in every pose of its `RIGID` chart (`foot_box.inner(D, ...)`) and whose observed set is each object in its box; `key_cell` reads the `D` to pair each key cell with its footprint cell.
8. 4c177718 `pose` (`4c177718.dl:96-100`) — `KeyedSetCompare<Unit, D4, Position>` whose pattern set is the chart glyph in every pose (`params.chart_glyph(D, P)`) and whose observed set is the arrow in its box; `pose.equals($U(), D)` feeds `params.chart_tip(D, D_tip)`.
9. 898e7135 `congruent` (`898e7135.dl:69-78`) — `KeyedSetCompare<Turned, Ident, Position>` whose observed set is each hole scaled by a candidate factor and turned by every D4 element (via `apply`), keyed `[hole, factor, D]`, and whose pattern set is each piece in its box; `congruent.equals([H, K, _], O)` is the piece a hole's scaled image is carried exactly onto. The src side is a scaled set, so the `onto` call would sit on a `[hole, factor, piece]`-keyed instance; the element is dropped, since pieces are one color.

All eight stand at the call sites the earlier surveys recorded; the rewrite changed none of their forms. No ninth site: every other `D4Map` cross-feed, `map` read, `d4_inverse` use, and D4-imaged catalog is accounted for below.

## 2. Near-misses

1. 64efde09 `cong` (`64efde09.dl:56-58`, read at `emit`, line 106) — pair-keyed cross-feed of two bars the header states congruent; with equal cardinality on both sides `map` already implies `onto`.
2. 4522001f `pair`, 47c1f68c `tile_map`, 8e5a5113 `step`, f25ffba3 `tile` — both sides total over one frame of equal extent, where `map` implies `onto`.
3. 8e5a5113 `lookup`, f25ffba3 `stamp` — the into-reading by design: a tile's or example's ink against a total output; `onto` is false there by construction (the `Not:` line's `map`).
4. 6aa20dc0 `fit` — template against a pair's two square tiles read through `compatible`; the dst is two cells by design (the `Not:` line's `compatible`).
5. Self-feeds (`src` = `dst`), where the two readings agree: 4c5c2cf0 `inv`, 0934a4d8 `inv`, 18419cfa `inv`, 47996f11 `inv` (both), 44d8ac46 `sym`, 47c1f68c `grid_map`, 662c240a `inv`, 72ca375d `inv`, 2c181942 `side_sym`, 44f52bb0 `d4` (both), 73ccf9c2 `inv`, b7cb93ac `turned`, 3a25b0d8 `fig_sym`.
6. D4 images of a shape sought at an unknown placement (the `Not:` line's `Occurrences`): 142ca369 `occ`, 1acc24af `seat`, 291dc1e1 `occ`, 3aa6fb7a `occ`, 409aa875 `occ`, 412b6263 `seat`, 50f325b5 `seek`, 6e4f6532 `seat`, 79369cc6 `occ`, 7b3084d4 `occ`, 7df24a62 `occ`, b7cb93ac `occ`.
7. Group naming, a set of D4 elements against `sym_member`, with no cell set compared: 18419cfa `grp`, 0934a4d8 `symid`, 44d8ac46 `named`, 4c5c2cf0 `sym`, 47996f11 `named`, 47c1f68c `sym_id`, 0dfd9992 `named`, 44f52bb0 `named`/`named_class`/`group`.
8. A group's whole orbit against the output's ink, keyed by `Sym`, where no single element carries one set onto the other: 4938f0c2 `orbit`, 4c5c2cf0 `same`.
9. Translation-only `KeyedSetCompare.equals` over box-framed or tile-framed sets, no D4 element: 136b0064 `same`, 00dbd492 `same` (both), 4ff4c9da `footprint`, 39a8645d `same_shape`, 63613498 `same`, 2a5f8217 `same`, 5dbc8537 `congruent`, 42f14c03 `shape`, 38007db0 `same`, 5a5a2103 `glyph`/`twin`, 4c5c2cf0 `known`, 776ffc46 `same_shape`, 18447a8d `exact`, 14754a24 `maximal`, 2c181942 `mate`.
10. `apply` beside a negated atom, each a position transform over one set (not a two-set comparison): 0934a4d8 `out`, 0dfd9992 `cand` (an element tested as its own inverse), 21897d95 `out` and `broken` (walks output cells back by the inverse turn), 291dc1e1 `turned`, 5a719d11 `out`/`cand_out`, 7ed72f31 `image_along`, 80214e03 `out`, b7cb93ac `foot`, e3497940 `ink`, f25ffba3 `augment_ink`, and the mirror maps in 11dc524f, 1b60fb0c, 2b01abd0, 3345333e, 3631a71a, 47996f11, 47c1f68c, 5545f144, 6f473927.
11. 3e980e27 `refuted` — a stamp's D4 image at a marker against a total `ex_out` (the into-reading; see part 4).
12. 4c7dc4dd `Induce.defect` — an exact comparison at the identity inside the `Induce` proposal comp, no D4 element.

## 3. Spec

No change to the interface or definition from this pass; the two open points stand as the fourth survey left them, now with the post-rewrite sites confirming them.

1. The element column is read by five callers: 36d67576 (`carried` applies `D`), 3d588dc9 (`key_cell` reads `D`), 4c177718 (`chart_tip(D, ...)`), and now also 67e490f4 and 845d6e51, whose `onto([..], D)` feeds `sym_member(S, D)` against a stored `Sym`. It stays.
2. The `RIGID`-chart point stands: 3d588dc9 and 4c177718 feed their pattern set from a D4-keyed source (`foot_box.inner(D, ...)`, `params.chart_glyph(D, P)`) with no single stored pose to feed `src`, while 36d67576, 62593bfd, 67e490f4, 845d6e51, 6165ea8f, and 409aa875 have a single `src`. The choice the fourth survey posed — split `Callers` by that, or give the operation a D4-keyed already-posed `src` beside the single-pose one — gets no new evidence here.
3. `map` keeps the into-reading; 8e5a5113 `lookup`, f25ffba3 `stamp`, and 3e980e27 `refuted` want it.

## 4. Reimplementations

Reimplementations: one candidate.

- `/Users/davidlu/code/arc-workspace/programs/solvers/3e980e27.dl` lines 68–72, `Determine.refuted(M, D)`: places each footprint cell under a candidate D4 at its marker (`apply`, `compose`) and tests `ex_out` for a differing color where a cell exists. That is `D4Map.conflict` over a `[M, E, P]`-keyed instance with `src` = the footprint and `dst` = `ex_out` displaced from the marker; the earlier surveys listed this site as a near-miss only.

Survey: 2026-09-10 21:18 — the solvers since 2026-09-10 15:25.

Callers:
898e7135 `congruent` — a `KeyedSetCompare<Turned, Ident, Position>` whose observed set is each hole scaled by a candidate factor and turned by every D4 element (`d4_elem`, `apply`), keyed `[hole, factor, D]`, and whose pattern set is each piece in its box; `congruent.equals([H, K, _], O)` is the piece that a hole's scaled image is carried exactly onto, and `fit` drops the element since pieces are one color. The site stands as the 2026-09-10 15:25 result recorded it. No second caller: across the scope, no solver instantiates `D4Map`, no rule writes `d4_inverse`, the only `Canon` (84f2aca1 `rect_id`) is fed a reflexive identity over drawn rectangles with no `map`, the only other `KeyedSetCompare` (88a62173 `same`) is a translation-only tile comparison, and the two `Occurrences` instances (890034e9 `occ`, 8a004b2b `seat`) seek a shape at an unknown placement.

Near-misses:
846bdb03 `placed`/`defect` — a shape's D4 images under a stored `Sym` (`sym_member`, `apply`) are tested for meeting each bar's color at the bar's edge; one set is placed and tested against bar colors, and no second cell set is carried onto (the `Not:` line's self-symmetry reading, with no comparison of two sets).
88207623 `image` — a source cell reflected across its line by `flip_of`, `displacement`, `apply`, `compose`; a position transform over one set, painted rather than compared.
85fa5666 — a stored `C4` element turns a corner name through `apply_diag_dir`; no cell set enters.
88a62173 `same` — `KeyedSetCompare.equals` over tiles in their boxes under translation alone, no D4 element.
890034e9 `occ`, 8a004b2b `seat` — a hole's content or a block's ink sought within the grid or drawing at an unknown placement, translation alone (the `Not:` line's `Occurrences`).
8698868d `pair` — blocks and pieces paired by enclosed-region count or rank, not by shape.

Spec:
No change from this pass. 898e7135 is the one caller in scope and drops the element column, so the element-column point rests on the callers the earlier results name (36d67576, 3d588dc9, 4c177718, 67e490f4, 845d6e51) and stands. 898e7135 adds a wrinkle the entry's interface does not hold: its src side is a hole scaled by a factor before the turn, so an `onto` call there would key the instance by `[hole, factor, piece]` and feed `src` from the scaled set; that is a caller-side composition, not an interface change, and this pass alone does not argue for one. The `RIGID`-chart point gains no evidence: no scope solver feeds a D4-keyed pattern set from a chart. `map` keeps the into-reading; no scope site reads it either way.

Reimplementations: none.
The matcher under the scratch path ran the five shapes of the 15:25 result over the 27 scope solvers; shapes A, B, C, and E hit nothing, and shape D, extended to `observed_member` heads, hit only 898e7135 line 71. Grep for `D4Map`, `KeyedSetCompare`, `Canon`, `d4_inverse`, `sym_member`, `Occurrences`, `.map(`, `apply(`, `apply_dir`, `.equals(`, `.equiv(`, `pattern_member`, `d4_elem`, `flip_of`, `rotation(`, `BoxFrame`, `Reframe`, and `ShiftInvariance` found the sites read above and no other.
