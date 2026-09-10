# `Checkerboard<Key>` — the two shades of a cell set's 2-coloring

The parity class of each cell of a keyed cell set, read against a seed cell: `light` is the seed's shade, the cells an even count of unit steps from it, and `dark` is the rest. The seed fixes the phase, so a solver keys data by shade without a number: the seed is the corner the phase is anchored at, or the mark whose class the output follows.

```
.comp Checkerboard<Key> {
    // The cell set the 2-coloring covers, per key.
    .decl cell(key: Key, p: Position)  // input

    // The cell whose shade is `light`, per key.
    .decl seed(key: Key, p: Position)  // input

    .decl light(key: Key, p: Position)
    .decl dark(key: Key, p: Position)

    light(K, P) :- seed(K, P), cell(K, P).
    dark(K, Q) :- light(K, P), dir_elem(D), neighbor(P, D, Q), cell(K, Q).
    light(K, Q) :- dark(K, P), dir_elem(D), neighbor(P, D, Q), cell(K, Q).
}
```

Solver-local form (7ec998c9), the shade carried as a payload that swaps each step:

```
.decl shade(p: Position, s: Sense)
shade(P, S) :-
    in(P, _), params.corner(Diag), corner_dist(P, Diag, 0),   // the anchor corner cell
    params.corner_sense(S).
shade(Q, S2) :-
    shade(P, S), sense_elem(S2), S2 != S,   // the other sense
    dir_elem(D), neighbor(P, D, Q), in(Q, _).
```

The closure reaches the seed's connected part of the set. A parity test over corner distances (`same_phase` at period 2) reaches every cell of the set, connected or not, and needs no seed cell, only a corner; which reading the callers need is the spec question.

Not: a lattice of stored period reached by period-sized jumps (`LatticeOrbit`), whose period-2 class on both axes is a quarter of the cells, not a half; alternation along one line (d492a647, 834ec97d, 3ac3eb23 `$Parity`); the residue of one distance read into a table (`stride`); a tiling of 2×2 blocks (`divide_by_size_2d`).

Match: a recursive relation over positions whose step is one cardinal `neighbor` and whose head value or membership swaps each step — a payload swapped through an `alt` relation or a `!=` over a two-element class, or two heads that feed each other. Also a rule testing two cells' corner distances for equal residue at period 2, through `stride` or `same_phase`. Grep `neighbor(` in rules whose head the rule reads, and `stride(.*2,`; match the shape with the parser (`tests/test_ast_match.py`).

Survey: 2026-09-10 06:44

The survey read the whole corpus (690 solvers): a grep for `stride(.*2,`, `same_phase`, and checker/parity/shade names; a parser match for a self-recursive rule that steps by `neighbor`/`jump`/`compose` and changes a non-position argument (43 hits, each read), and for two relations feeding each other through a step (no hits); and every rule where `corner_dist` and `stride` co-occur.

Callers:

- `programs/solvers/7ec998c9.dl` — `shade`: closure over the whole grid from the anchor corner, a `Sense` payload swapped each step; read once, at the mark, to choose the turn sense.
- `programs/solvers/2072aba6.dl` — `checker` under `$Checker`: closure over the output frame from the corners of a stored DiagAxis, a `Color` payload swapped each step through a stored 2-cycle `alt`; read per output cell, masked to the ink silhouette.
- `programs/solvers/5e6bbc0b.dl` — `block_cell` under `$Parity`: the corner-distance parity test at a stored `period(2)`, from every corner, seeded at the mark; membership only, with `!block_cell` as the fill.

Near-misses:

- The same corner-distance residue form at period 4: c1990cce `echo` under `$Stripe` and `Determine.striped` — diagonal stripes, one class of four.
- A seeded 2-coloring by even-length walks over region `Ident`s with `across` edges: 3bd292e8 `same_side`. The nodes are not cells and the step is not `neighbor`; it reads both shades as membership and negation.
- A period-2 lattice or one line, by two unit steps in one direction per closure step: d492a647 `lattice` and 834ec97d `beam` under `$Parity`.
- Alternation along one line or along erosion depth: 3ac3eb23 `walk`, 0a938d79 `line`, 1e97544e `flow`, 97999447 `$Toggle`, 759f3fd3's ring cycle.
- A D4 pose composed per tile step, whose classes are per-axis parity, a quarter of the tiles: the reflect-unfolds (`unfold_val` in 0c786b71, 3af2c5a8, 4c4377d9, 59341089, 62c24649, 67e8384a, 6d0aefbc, 6fa7a44f, 833dafe3, 8be77c9e, 8d5021e8, bc4146bd, c48954c1, c9e6f938, eb281b96; 47c1f68c `unfold`; 8e5a5113 `content`).
- A payload that advances rather than swaps: the walks, beams, spirals, and dilation depths of 08573cc6, 195c6913, 212895b5, 28e73c20, 351d6448, 4acc7107, 4e34c42c, 508bd3b6, 60d73be6, 69889d6e, 6df30ad6, 72207abc, 7d419a02, 7e2bad24, e179c5f4, 20a9e565.

Spec:

- Closure or parity test. At every caller the cell set is a connected rectangle and the seed lies in it, so the two readings coincide. The parity test needs a corner, which 5e6bbc0b takes from `diag_dir_elem`, so neither form adds an orientation choice. Only the closure reading states the near-miss 3bd292e8, which has no coordinates: with the step as a caller-supplied edge over a generic `T`, and `Checkerboard<Key>` as the cardinal-neighbor Position subclass (as `Components8 : Components` is built), 3bd292e8 becomes a caller and the three cell callers supply one cardinal edge each.
- Payload or membership. 5e6bbc0b needs membership only. 7ec998c9 and 2072aba6 carry a payload whose per-step swap is the `other` operation over a two-member class (`proposals/other.md`); with `light`/`dark` membership, each reads its payload once at the consumer through a two-branch disjunction. Membership serves all three callers.
- 5e6bbc0b's `period` parameter admits values that leave the checkerboard family (c1990cce's stripes at 4). Under the comp the 2 is structural and the parameter goes.

Reimplementations: none of `programs/lib.dl`.

Survey: 2026-09-10 15:01 — the solvers since 2026-09-10 06:44, 045e512c, 0520fde7, 05f2a901, 08573cc6, 0934a4d8, 0c9aba6e, 0d87d2a6, 0dfd9992, 1190bc91, 11dc524f, 136b0064, 137f0df0, 13e47133, 142ca369, 1478ab18, 15113be4, 15663ba9, 16de56c4, 17829a00, 178fcbfb, 17cae0c1, 18286ef8, 182e5d0f, 18419cfa, 18447a8d, 195ba7dc, 195c6913, 1990f7a8, 19bb5feb, 1a07d186, 1a6449f1, 1acc24af, 1ae2feb7, 1b2d62fb, 1b59e163, 1b60fb0c, 1bfc4729, 1c02dbbe, 1c56ad9f, 1c786137, 1caeab9d, 1d0a4b61, 1d398264, 1d61978c, 1e32b0e9, 1e5d6875, 1e97544e, 1efba499, 1f0c79e5, 1f642eb9, 1f85a75f, 1f876c06, 2037f2c7, 20818e16, 20981f0e, 20fb2937, 212895b5, 21f83797, 2204b7a8, 221dfab4, 22208ba4, 22233c11, 22425bda, 22806e14, 22eb0ac0, 234bbc79, 239be575, 23b5c85d, 247ef758, 25094a63, 252143c9, 253bf280, 2546ccf6, 256b0a75, 25c199f5, 25d487eb, 25e02866, 2601afb7, 264363fd, 2685904e, 2697da3f, 269e22fb, 272f95fa, 2753e76c, 278e5215, 27a77e38, 27f8ce4f, 281123b4, 28e73c20, 291dc1e1, 292dd178, 29623171, 29700607, 2a5f8217, 2b01abd0, 2b83f449, 2ba387bc, 2bcee788, 2bee17df, 2c0b0aff, 2c181942, 2c608aff, 2c737e39, 2dc579da, 2e65ae53, 2f0c5170, 2f767503, 2faf500b, 305b1341, 3194b014, 31aa019c, 31d5ba1a, 320afe60, 321b1fc6, 332202d5, 3345333e, 337b420f, 3391f8c0, 33b52de3, 3428a4f5, 342ae2ed, 3490cc26, 34b99a2b, 34cfa167, 351d6448, 358ba94e, 3631a71a, 363442ee, 36a08778, 36d67576, 36fdfd69, 37d3e8b2, 38007db0, 396d80d7, 39a8645d, 39e1d7f9, 3a25b0d8, 3a301edc, 3aa6fb7a, 3ad05f52, 3bd292e8, 3bdb4ada, 3befdf3e, 3d31c5b3, 3d588dc9, 3d6c6e23, 3dc255db, 3e6067c3, 3e980e27, 3ed85e70, 3eda0437, 3ee1011a, 3f23242b, 40853293, 4093f84a, 409aa875, 40f6cd08, 412b6263, 414297c0, 41ace6b5, 4258a5f9, 4290ef0e, 42918530, 42a15761, 42a50994, 42f14c03, 42f83767, 4364c1c4, 444801d8, 445eab21, 446ef5d2, 447fd412, 44d8ac46, 44f52bb0, 456873bc, 45737921, 458e3a53, 45a5af55, 45bbe264, 4612dd53, 465b7d93, 469497ad, 46c35fc7, 46f33fce, 477d2879, 47996f11, 47c1f68c, 4852f2fa, 48634b99, 48d8fb45, 48f8583b, 4938f0c2, 494ef9d7, 4a1cacc2, 4a21e3da, 4aab4007, 4acc7107, 4b6b68e5, 4be741c5, 4c177718, 4c3d4a41, 4c416de3, 4c5c2cf0, 4c7dc4dd, 4df5b0ae, 4e34c42c, 4e45f183, 4e469f39, 4e7e0eb9, 4f537728, 4ff4c9da, 5034a0b5, 506d28a5, 50846271, 508bd3b6, 50a16a69, 50aad11f, 50c07299, 50f325b5, 5117e062, 5168d44c, 516b51b7, 5207a7b5, 522fdd07, 52364a65, 5289ad53, 52df9849, 52fd389e, 538b439f, 539a4f51, 53fb4810, 543a7ed5, 54d82841, 54d9e175, 54db823b, 54dc2872, 55059096, 551d5bf1, 5521c0d9, 5545f144, 55783887, 5587a8d0, 5614dbcf, 5623160b, 56dc2b01, 56ff96f3, 5751f35e, 5792cb4d, 57aa92db, 57edb29d, 581f7754, 5833af48, 58490d8a, 58743b76, 58c02a16, 58e15b12, 58f5dbd5, 5961cc34, 5a5a2103, 5a719d11, 5ad4f10b, 5ad8a7c0, 5adee1b2, 5af49b42, 5b37cb25, 5b526a93, 5b692c0f, 5c0a986e, 5c2c9af4, 5d2a5c43, 5d588b4d, 5daaa586, 5dbc8537, 5e6bbc0b, 5ecac7f7, 5ffb2104, 604001fa, 60a26a3e, 60b61512, 60d73be6, 6165ea8f, 623ea044, 62593bfd, 626c0bcc, 62ab2642, 6350f1f4, 63613498, 639f5a19, 642248e4, 6430c8c4, 6455b5f5, 64a7c07e, 64efde09, 652646ff, 65b59efc, 662c240a, 668eec9a, 66ac4c3b, 66f2d22f, 673ef223, 67636eac, 6773b310, 67a423a3, 67c52801, 67e490f4, 6855a6e4, 689c358e, 68b67ca3, 68bc2e87, 692cd3b6, 694f12f3, 696d4842, 69889d6e, 6a11f6da, 6a1e5592, 6a980be1, 6aa20dc0, 6ad5bdfd, 6b9890af, 6bcdb01e, 6c434453, 6ca952ad, 6cbe9eb8, 6cdd2623, 6d0160f0, 6d58a25d, 6df30ad6, 6e19193c, 6e453dd6, 6e4f6532, 6e82a1ae, 6ecd11f4, 6f473927, 6ffbe589, 6ffe8f07, 7039b2d7, 71e489b6, 72322fa7, 72a961c9, 72ca375d, 73c3b0d8, 73ccf9c2, 7447852a, 7491f3cf, 74dd1130, 753ea09b, 758abdf0, 759f3fd3, 75b8110e, 760b3cac, 762cd429, 7666fa5d, 770cc55f, 776ffc46, 780d0b14, 782b5218, 78332cb0, 7837ac64, 78e78cff, 79369cc6, 794b24be, 79fb03f4, 7acdf6d3, 7b0280bc, 7b3084d4, 7b5033c1, 7b6016b9, 7b80bb43, 7bb29440, 7c008303, 7c66cb00, 7c8af763, 7c9b52a0, 7d18a6fb, 7d1f7ee8, 7d419a02, 7d7772cc, 7ddcd7ec, 7df24a62, 7e0986d6, 7e2bad24, 7e576d6e, 7ec998c9, 7ed72f31, 7ee1c6ea, 7f4411dc, 800d221b, 80214e03, 80a900e0, 80af3007, 810b9b61, 817e6c09, 81c0276b, 825aa9e9, 82819916, 83302e8f, 833966f4, 83b6b474, 83eb0a57, 8403a5d5, 84551f4c, 845d6e51, 846bdb03, 85c4e7cd, 89565ca0, 8e5a5113, 94f9d214, 9565186b, 97999447, 995c5fa3, 99b1bc43, a68b268e, b1948b0a, b1fc8b8e, b7cb93ac, ba26e723, bbb1b8b6, bdad9b1f, cbded52d, ce22a75a, ce4f8723, cf98881b, d19f7514, d47aa2ff, d511f180, d9fac9be, dae9d2b5, e133d23d, e345f17b, e3497940, e98196ab, e9afcf9a, ea9794b1, ed74f2f2, f25ffba3, f2829549, fafffa47.

## 1. Callers

The scope holds 437 solvers, all present. The search: a lexical grep for `stride(` with a literal or parameter period, `same_phase` (no hits), and checker/parity/shade names; a parser match for a rule whose head relation recurs positively in its body with a `neighbor`/`jump`/`compose` step and a non-Position argument rebound (15 hits), for two relations feeding each other through such a step (12 hits), and for `corner_dist` co-occurring with `stride` in one rule (1 hit). Every hit was read in its rule.

1. `programs/solvers/7ec998c9.dl` — `shade` (lines 35–41): closure over the whole grid from the stored anchor corner, a `Sense` payload swapped each cardinal step via `sense_elem(S2), S2 != S`; read once at the mark (line 56) to pick the turn sense of the Z.
2. `programs/solvers/5e6bbc0b.dl` — `block_cell` under `$Parity` (lines 64–68): the corner-distance residue test at `params.period(2)` from every corner (`diag_dir_elem`), seeded at the mark; membership only, `!block_cell` is the fill class.

`2072aba6` (a caller in the recorded survey) is outside this scope. No third caller: every other self-recursive step site rebinds a payload that advances or a Position under a D4 pose, and every other `stride` site reduces one edge distance, not a corner distance.

## 2. Near-misses

1. `3bd292e8` `same_side` (lines 32–34): a seeded 2-coloring by two `across` crossings over region `Ident`s. The nodes are not cells and the step is not `neighbor`, so the Match signature's cardinal-step form rules it out.
2. One-distance residue at a stored period (the Not line's `stride` exclusion): `ba26e723` `on_stride`, `1c56ad9f` `Parse.phase`, `221dfab4` `phase` and `Determine.phase_color`, `8403a5d5` `bar_slot`/`dot_slot`, `516b51b7` ring index, `759f3fd3` `filled` under `$Period`, `7447852a` `mark_margin`, `817e6c09`, `58490d8a`, `13e47133`, `34cfa167`, `97999447` `$Mask`.
3. Alternation along one line (Not line): `97999447` `$Toggle` via `CycleWalk` on a 2-cycle; `1e97544e` `flow` walking a color cycle along a diagonal axis.
4. D4 pose composed per tile step, a quarter-of-tiles class (Not line, reflect-unfolds): `47c1f68c` `unfold` (lines 106–111), `8e5a5113` `content` (lines 103–108).
5. A payload that advances rather than swaps (fails the "swaps each step" clause): `08573cc6` `arm`, `195c6913` `walk`/`step`, `212895b5` `turtle` (phase through `IndexCycle`, a cycle of stored length), `28e73c20` `walk`, `4acc7107` `lane`/`slot`, `4e34c42c` `place`, `508bd3b6` `beam`, `69889d6e` `walk`, `6df30ad6` `depth`, `759f3fd3` `Dilate.depth`, `7e2bad24` `enter`, `142ca369` `enter`/`ray`.
6. Mutual recursion through a step with no membership swap: `16de56c4` `advance`/`lattice` (period jumps, `LatticeOrbit` territory), `1b60fb0c` `turn_step`/`orbit`, `234bbc79` `trail_dest`/`slide`, `5587a8d0` `covers`/`inside` (dilation), `5ffb2104` and `6ad5bdfd` `room`/`rest`, `6cbe9eb8` `anchor`/`obox`, `84551f4c` `toppled`/`landed`, `7447852a` `$Stamp` `mark_cell` (period jumps).

## 3. Spec

The scope's two callers give the same picture as the recorded survey, with no new signal.

1. Closure or parity test: at both callers the cell set is the whole grid and the seed lies in it, so the two readings coincide. 5e6bbc0b takes its corner from `diag_dir_elem`; 7ec998c9 stores it as `params.corner`. Neither form adds an orientation choice. The generic-`T` reading that would admit 3bd292e8 rests on a near-miss, not on a caller, so it is not a change signal from this scope.
2. Payload or membership: 5e6bbc0b needs membership only; 7ec998c9 reads its `Sense` payload once, at the mark, which a `light`/`dark` disjunction at that consumer reproduces. Membership serves both.
3. 5e6bbc0b's `period` parameter admits stripe values outside the family; under the comp the 2 is structural. This rests on the surfacing solver alone: caller-only.

No interface or definition change is argued from this scope.

## 4. Reimplementations

Reimplementations: none.
