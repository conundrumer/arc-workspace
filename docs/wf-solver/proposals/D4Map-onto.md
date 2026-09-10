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

Survey: 2026-09-10 15:25 — the solvers since 2026-09-10 08:31, 009d5c81, 00dbd492, 045e512c, 0520fde7, 05f2a901, 08573cc6, 0934a4d8, 0962bcdd, 0c9aba6e, 0ca9ddb6, 0d87d2a6, 0dfd9992, 10fcaaa3, 1190bc91, 11dc524f, 136b0064, 137f0df0, 13e47133, 142ca369, 14754a24, 1478ab18, 15113be4, 15663ba9, 16de56c4, 17829a00, 178fcbfb, 17b866bd, 17cae0c1, 1818057f, 18286ef8, 182e5d0f, 18419cfa, 18447a8d, 195ba7dc, 195c6913, 1990f7a8, 19bb5feb, 1a07d186, 1a6449f1, 1acc24af, 1ae2feb7, 1b2d62fb, 1b59e163, 1b60fb0c, 1bfc4729, 1c02dbbe, 1c56ad9f, 1c786137, 1caeab9d, 1d0a4b61, 1d398264, 1d61978c, 1e32b0e9, 1e5d6875, 1e97544e, 1efba499, 1f0c79e5, 1f642eb9, 1f85a75f, 1f876c06, 2037f2c7, 20818e16, 20981f0e, 20fb2937, 212895b5, 21897d95, 21f83797, 2204b7a8, 221dfab4, 22208ba4, 22233c11, 22425bda, 22806e14, 22eb0ac0, 234bbc79, 239be575, 23b5c85d, 247ef758, 25094a63, 252143c9, 253bf280, 2546ccf6, 256b0a75, 25c199f5, 25d487eb, 25e02866, 2601afb7, 264363fd, 2685904e, 2697da3f, 269e22fb, 272f95fa, 2753e76c, 278e5215, 27a28665, 27a77e38, 27f8ce4f, 281123b4, 28e73c20, 291dc1e1, 292dd178, 29623171, 29700607, 2a5f8217, 2b01abd0, 2b83f449, 2ba387bc, 2bcee788, 2bee17df, 2c0b0aff, 2c181942, 2c608aff, 2c737e39, 2dc579da, 2e65ae53, 2f0c5170, 2f767503, 2faf500b, 305b1341, 3194b014, 31aa019c, 31d5ba1a, 320afe60, 321b1fc6, 332202d5, 3345333e, 337b420f, 3391f8c0, 33b52de3, 3428a4f5, 342ae2ed, 3490cc26, 34b99a2b, 34cfa167, 351d6448, 358ba94e, 3631a71a, 363442ee, 36a08778, 36d67576, 36fdfd69, 37d3e8b2, 38007db0, 396d80d7, 39a8645d, 39e1d7f9, 3a25b0d8, 3a301edc, 3aa6fb7a, 3ac3eb23, 3ad05f52, 3bd292e8, 3bdb4ada, 3befdf3e, 3d31c5b3, 3d588dc9, 3d6c6e23, 3dc255db, 3e6067c3, 3e980e27, 3ed85e70, 3eda0437, 3ee1011a, 3f23242b, 40853293, 4093f84a, 409aa875, 40f6cd08, 412b6263, 414297c0, 41ace6b5, 4258a5f9, 4290ef0e, 42918530, 42a15761, 42a50994, 42f14c03, 42f83767, 4364c1c4, 444801d8, 445eab21, 446ef5d2, 447fd412, 44d8ac46, 44f52bb0, 4522001f, 456873bc, 45737921, 458e3a53, 45a5af55, 45bbe264, 4612dd53, 465b7d93, 469497ad, 46c35fc7, 46f33fce, 477d2879, 47996f11, 47c1f68c, 4852f2fa, 48634b99, 48d8fb45, 48f8583b, 4938f0c2, 494ef9d7, 4a1cacc2, 4a21e3da, 4aab4007, 4acc7107, 4b6b68e5, 4be741c5, 4c177718, 4c3d4a41, 4c416de3, 4c5c2cf0, 4c7dc4dd, 4df5b0ae, 4e34c42c, 4e45f183, 4e469f39, 4e7e0eb9, 4f537728, 4ff4c9da, 5034a0b5, 506d28a5, 50846271, 508bd3b6, 50a16a69, 50aad11f, 50c07299, 50f325b5, 5117e062, 5168d44c, 516b51b7, 5207a7b5, 522fdd07, 52364a65, 5289ad53, 52df9849, 52fd389e, 538b439f, 539a4f51, 53fb4810, 543a7ed5, 54d82841, 54d9e175, 54db823b, 54dc2872, 55059096, 551d5bf1, 5521c0d9, 5545f144, 55783887, 5587a8d0, 5614dbcf, 5623160b, 56dc2b01, 56ff96f3, 5751f35e, 5792cb4d, 57aa92db, 57edb29d, 581f7754, 5833af48, 58490d8a, 58743b76, 58c02a16, 58e15b12, 58f5dbd5, 5961cc34, 5a5a2103, 5a719d11, 5ad4f10b, 5ad8a7c0, 5adee1b2, 5af49b42, 5b37cb25, 5b526a93, 5b692c0f, 5c0a986e, 5c2c9af4, 5d2a5c43, 5d588b4d, 5daaa586, 5dbc8537, 5e6bbc0b, 5ecac7f7, 5ffb2104, 604001fa, 60a26a3e, 60b61512, 60d73be6, 6165ea8f, 623ea044, 62593bfd, 626c0bcc, 62ab2642, 6350f1f4, 63613498, 639f5a19, 642248e4, 642d658d, 6430c8c4, 6455b5f5, 64a7c07e, 64efde09, 652646ff, 65b59efc, 662c240a, 668eec9a, 66ac4c3b, 66e6c45b, 66f2d22f, 673ef223, 67636eac, 6773b310, 67a423a3, 67c52801, 67e490f4, 6855a6e4, 689c358e, 68b67ca3, 68bc2e87, 692cd3b6, 694f12f3, 696d4842, 69889d6e, 6a11f6da, 6a1e5592, 6a980be1, 6aa20dc0, 6ad5bdfd, 6b9890af, 6bcdb01e, 6c434453, 6ca952ad, 6cbe9eb8, 6cdd2623, 6d0160f0, 6d58a25d, 6df30ad6, 6e19193c, 6e453dd6, 6e4f6532, 6e82a1ae, 6ecd11f4, 6f473927, 6ffbe589, 6ffe8f07, 7039b2d7, 71e489b6, 72322fa7, 72a961c9, 72ca375d, 73c3b0d8, 73ccf9c2, 7447852a, 7491f3cf, 74dd1130, 753ea09b, 758abdf0, 759f3fd3, 75b8110e, 760b3cac, 762cd429, 7666fa5d, 770cc55f, 776ffc46, 780d0b14, 782b5218, 78332cb0, 7837ac64, 78e78cff, 79369cc6, 794b24be, 79fb03f4, 7acdf6d3, 7b0280bc, 7b3084d4, 7b5033c1, 7b6016b9, 7b80bb43, 7bb29440, 7c008303, 7c66cb00, 7c8af763, 7c9b52a0, 7d18a6fb, 7d1f7ee8, 7d419a02, 7d7772cc, 7ddcd7ec, 7df24a62, 7e02026e, 7e0986d6, 7e2bad24, 7e576d6e, 7ec998c9, 7ed72f31, 7ee1c6ea, 7f4411dc, 800d221b, 80214e03, 80a900e0, 80af3007, 810b9b61, 817e6c09, 81c0276b, 825aa9e9, 82819916, 83302e8f, 833966f4, 83b6b474, 83eb0a57, 8403a5d5, 84551f4c, 845d6e51, 846bdb03, 85c4e7cd, 89565ca0, 8e5a5113, 94f9d214, 9565186b, 97999447, 995c5fa3, 99b1bc43, a68b268e, a9f96cdd, b1948b0a, b1fc8b8e, b60334d2, b7cb93ac, ba26e723, bbb1b8b6, bdad9b1f, ca8de6ea, cbded52d, ce22a75a, ce4f8723, cf98881b, d19f7514, d364b489, d47aa2ff, d511f180, d9fac9be, dae9d2b5, e133d23d, e345f17b, e3497940, e98196ab, e9afcf9a, ea9794b1, ed74f2f2, f25ffba3, f2829549, fafffa47.

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
