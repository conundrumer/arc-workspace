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
