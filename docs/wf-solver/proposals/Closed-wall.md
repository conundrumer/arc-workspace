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

Survey: 2026-09-10 15:06 — the solvers since 2026-09-10 07:26, 045e512c, 0520fde7, 05f2a901, 08573cc6, 0934a4d8, 0c9aba6e, 0d87d2a6, 0dfd9992, 1190bc91, 11dc524f, 136b0064, 137f0df0, 13e47133, 142ca369, 1478ab18, 15113be4, 15663ba9, 16de56c4, 17829a00, 178fcbfb, 17cae0c1, 18286ef8, 182e5d0f, 18419cfa, 18447a8d, 195ba7dc, 195c6913, 1990f7a8, 19bb5feb, 1a07d186, 1a6449f1, 1acc24af, 1ae2feb7, 1b2d62fb, 1b59e163, 1b60fb0c, 1bfc4729, 1c02dbbe, 1c56ad9f, 1c786137, 1caeab9d, 1d0a4b61, 1d398264, 1d61978c, 1e32b0e9, 1e5d6875, 1e97544e, 1efba499, 1f0c79e5, 1f642eb9, 1f85a75f, 1f876c06, 2037f2c7, 20818e16, 20981f0e, 20fb2937, 212895b5, 21f83797, 2204b7a8, 221dfab4, 22208ba4, 22233c11, 22425bda, 22806e14, 22eb0ac0, 234bbc79, 239be575, 23b5c85d, 247ef758, 25094a63, 252143c9, 253bf280, 2546ccf6, 256b0a75, 25c199f5, 25d487eb, 25e02866, 2601afb7, 264363fd, 2685904e, 2697da3f, 269e22fb, 272f95fa, 2753e76c, 278e5215, 27a77e38, 27f8ce4f, 281123b4, 28e73c20, 291dc1e1, 292dd178, 29623171, 29700607, 2a5f8217, 2b01abd0, 2b83f449, 2ba387bc, 2bcee788, 2bee17df, 2c0b0aff, 2c181942, 2c608aff, 2c737e39, 2dc579da, 2e65ae53, 2f0c5170, 2f767503, 2faf500b, 305b1341, 3194b014, 31aa019c, 31d5ba1a, 320afe60, 321b1fc6, 332202d5, 3345333e, 337b420f, 3391f8c0, 33b52de3, 3428a4f5, 342ae2ed, 3490cc26, 34b99a2b, 34cfa167, 351d6448, 358ba94e, 3631a71a, 363442ee, 36a08778, 36d67576, 36fdfd69, 37d3e8b2, 38007db0, 396d80d7, 39a8645d, 39e1d7f9, 3a25b0d8, 3a301edc, 3aa6fb7a, 3ad05f52, 3bd292e8, 3bdb4ada, 3befdf3e, 3d31c5b3, 3d588dc9, 3d6c6e23, 3dc255db, 3e6067c3, 3e980e27, 3ed85e70, 3eda0437, 3ee1011a, 3f23242b, 40853293, 4093f84a, 409aa875, 40f6cd08, 412b6263, 414297c0, 41ace6b5, 4258a5f9, 4290ef0e, 42918530, 42a15761, 42a50994, 42f14c03, 42f83767, 4364c1c4, 444801d8, 445eab21, 446ef5d2, 447fd412, 44d8ac46, 44f52bb0, 456873bc, 45737921, 458e3a53, 45a5af55, 45bbe264, 4612dd53, 465b7d93, 469497ad, 46c35fc7, 46f33fce, 477d2879, 47996f11, 47c1f68c, 4852f2fa, 48634b99, 48d8fb45, 48f8583b, 4938f0c2, 494ef9d7, 4a1cacc2, 4a21e3da, 4aab4007, 4acc7107, 4b6b68e5, 4be741c5, 4c177718, 4c3d4a41, 4c416de3, 4c5c2cf0, 4c7dc4dd, 4df5b0ae, 4e34c42c, 4e45f183, 4e469f39, 4e7e0eb9, 4f537728, 4ff4c9da, 5034a0b5, 506d28a5, 50846271, 508bd3b6, 50a16a69, 50aad11f, 50c07299, 50f325b5, 5117e062, 5168d44c, 516b51b7, 5207a7b5, 522fdd07, 52364a65, 5289ad53, 52df9849, 52fd389e, 538b439f, 539a4f51, 53fb4810, 543a7ed5, 54d82841, 54d9e175, 54db823b, 54dc2872, 55059096, 551d5bf1, 5521c0d9, 5545f144, 55783887, 5587a8d0, 5614dbcf, 5623160b, 56dc2b01, 56ff96f3, 5751f35e, 5792cb4d, 57aa92db, 57edb29d, 581f7754, 5833af48, 58490d8a, 58743b76, 58c02a16, 58e15b12, 58f5dbd5, 5961cc34, 5a5a2103, 5a719d11, 5ad4f10b, 5ad8a7c0, 5adee1b2, 5af49b42, 5b37cb25, 5b526a93, 5b692c0f, 5c0a986e, 5c2c9af4, 5d2a5c43, 5d588b4d, 5daaa586, 5dbc8537, 5e6bbc0b, 5ecac7f7, 5ffb2104, 604001fa, 60a26a3e, 60b61512, 60d73be6, 6165ea8f, 623ea044, 62593bfd, 626c0bcc, 62ab2642, 6350f1f4, 63613498, 639f5a19, 642248e4, 6430c8c4, 6455b5f5, 64a7c07e, 64efde09, 652646ff, 65b59efc, 662c240a, 668eec9a, 66ac4c3b, 66f2d22f, 673ef223, 67636eac, 6773b310, 67a423a3, 67c52801, 67e490f4, 6855a6e4, 689c358e, 68b67ca3, 68bc2e87, 692cd3b6, 694f12f3, 696d4842, 69889d6e, 6a11f6da, 6a1e5592, 6a980be1, 6aa20dc0, 6ad5bdfd, 6b9890af, 6bcdb01e, 6c434453, 6ca952ad, 6cbe9eb8, 6cdd2623, 6d0160f0, 6d58a25d, 6df30ad6, 6e19193c, 6e453dd6, 6e4f6532, 6e82a1ae, 6ecd11f4, 6f473927, 6ffbe589, 6ffe8f07, 7039b2d7, 71e489b6, 72322fa7, 72a961c9, 72ca375d, 73c3b0d8, 73ccf9c2, 7447852a, 7491f3cf, 74dd1130, 753ea09b, 758abdf0, 759f3fd3, 75b8110e, 760b3cac, 762cd429, 7666fa5d, 770cc55f, 776ffc46, 780d0b14, 782b5218, 78332cb0, 7837ac64, 78e78cff, 79369cc6, 794b24be, 79fb03f4, 7acdf6d3, 7b0280bc, 7b3084d4, 7b5033c1, 7b6016b9, 7b80bb43, 7bb29440, 7c008303, 7c66cb00, 7c8af763, 7c9b52a0, 7d18a6fb, 7d1f7ee8, 7d419a02, 7d7772cc, 7ddcd7ec, 7df24a62, 7e0986d6, 7e2bad24, 7e576d6e, 7ec998c9, 7ed72f31, 7ee1c6ea, 7f4411dc, 800d221b, 80214e03, 80a900e0, 80af3007, 810b9b61, 817e6c09, 81c0276b, 825aa9e9, 82819916, 83302e8f, 833966f4, 83b6b474, 83eb0a57, 8403a5d5, 84551f4c, 845d6e51, 846bdb03, 85c4e7cd, 89565ca0, 8e5a5113, 94f9d214, 9565186b, 97999447, 995c5fa3, 99b1bc43, a68b268e, b1948b0a, b1fc8b8e, b7cb93ac, ba26e723, bbb1b8b6, bdad9b1f, cbded52d, ce22a75a, ce4f8723, cf98881b, d19f7514, d47aa2ff, d511f180, d9fac9be, dae9d2b5, e133d23d, e345f17b, e3497940, e98196ab, e9afcf9a, ea9794b1, ed74f2f2, f25ffba3, f2829549, fafffa47.

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
