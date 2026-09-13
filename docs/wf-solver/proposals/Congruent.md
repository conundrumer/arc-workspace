# `Congruent<Key, Val>` — keyed cell sets equal up to translation

Which keyed valued cell sets hold the same cells up to translation: each set is read in its own bounding box, and two keys are congruent when those box-relative valued cells are the same set. A solver that asks "which object has this object's shape" builds it from two lib comps and three rules — a `Bbox` over the sets, a `KeyedSetCompare` fed through `crop` on both sides, and a readout of `equals`.

```
.comp Congruent<Key, Val> {
    .decl cell(key: Key, p: Position, v: Val)  // input

    .init box = Bbox<Key>
    box.cell(Ky, P) :- cell(Ky, P, _).

    // A cell in its own set's box.
    .type Member = [p_inner: Position, v: Val]

    .init same = KeyedSetCompare<Key, Key, Member>
    same.pattern_member(Ky, [P_inner, V])  :- cell(Ky, P, V), box.box(Ky, B), crop(P, B, P_inner).
    same.observed_member(Ky, [P_inner, V]) :- cell(Ky, P, V), box.box(Ky, B), crop(P, B, P_inner).

    .decl congruent(key: Key, key2: Key)
    congruent(Ky, Ky2) :- same.equals(Ky, Ky2).
}
```

Not: a set compared against a stored pattern, which carries its own frame and needs no box (`covers` and `equals` on `KeyedSetCompare` already state that); matching closed over D4 (`D4Map.onto`); containment without equality (`covers`); the translations that fix one set (`OffsetInvariance`); content equality inside a frame the parse already gives, where the box would quotient away the placement the model reads; a fit test at an explicit candidate translation, where the box would discard that translation.

Match: two rules feeding one `KeyedSetCompare` instance's `pattern_member` and `observed_member` from box-relative cells — a `Bbox` `box` readout passed through `crop`, or any other read of a cell in its own set's box — with `equals` read as sameness of shape. Also any hand-written equal-shape test over two derived cell sets: a count comparison, a paired walk over both sets, or a `relative` offset held constant across a set. Grep: `KeyedSetCompare<`, `pattern_member`, `observed_member`, `Bbox<`, `crop(`, `relative(`, `equals(`.

Survey: 2026-09-09 08:00.

Callers: 63613498 (`same`, over `Components` labels), 39a8645d (`same_shape`, copies of a piece), 5dbc8537 (`congruent`, interchangeable pieces), 4ff4c9da (`footprint`, one box split by color class), 2a5f8217 (`same`, one box split into blank and colored shapes), 42f14c03 (`shape`, an object against a hole), 228f6490 (`fits`, a hole against a loose shape), 009d5c81 (`Determine.same`, key shapes sharing a lookup entry), 00dbd492 (`Determine.same`, objects sharing a stored patch), 21897d95 (`Determine.bcmp`, patches sharing a glyph id). No family siblings among them.

The corpus holds 85 `KeyedSetCompare` instances in 67 solvers and 184 `BoxFrame` instances. Of those instances, 18 name one source relation on both sides and 2 more self-compare through an alias or a filtered source; 11 read either side from an `*.inner` readout. No site writes the operation outside `KeyedSetCompare`: of 17 rules binding an offset with `displacement`/`compose` under a negated atom, none tests shape sameness; the 20 keyed set inclusions by defect negation are ray, run, and region tests; the 6 comparisons of two `Tally` counts are size hypotheses, one of them 42f14c03's `$Size` case, a declared peer of its `$Shape` case.

Near: a set against a stored pattern — the `combine_match` family (3428a4f5, 5d2a5c43, dae9d2b5, f2829549, fafffa47 with their siblings), 3618c87e, a85d4709, 995c5fa3, 136b0064, 17cae0c1, 009d5c81 `key_match`, 27a28665, ed74f2f2, 4c177718, 5a5a2103 `glyph`, 00dbd492 `same` in the program, 4c5c2cf0, 1fad071e, 3b4c2228, ff28f65a, 2c181942 `mate`; containment without equality (50846271, 14754a24, 045e512c, 15113be4); D4-closed matching (6165ea8f, 62593bfd, 3d588dc9, 36d67576), which belongs to `D4Map-onto`, whose survey already names 39a8645d, 5dbc8537, and 42f14c03 as its translation-only peers; content equality in a frame the parse gives (a87f7484, 5a5a2103 `twin`, 6350f1f4 `solid`, 38007db0, 15660dd6, and the table canonicalizers 27a28665, 136b0064, 17cae0c1, ed74f2f2, a85d4709, 995c5fa3, 281123b4); placement-exact fit (18447a8d, 2c181942, b7cb93ac, whose interchangeable pieces fall out of `PlacementPruning.alive` with no congruence test); members that are not cells (the `Sym`/`D4` group identifications at 18419cfa, 0934a4d8, 44d8ac46, 47996f11, 47c1f68c, 981571dc, 11852cab, 0dfd9992, 44f52bb0, 4938f0c2, 4c5c2cf0, the color sets at 2ccd9fef and 494ef9d7, and 21897d95 `arms`).

Spec, from the callers: two changes, both argued by solvers other than the surfacing one.

- Two sides rather than one `cell` relation. Eight callers compare one keyed family and are served as written — 63613498, 39a8645d, 5dbc8537, 009d5c81, 00dbd492, and 21897d95 self-compare, and 4ff4c9da and 2a5f8217 split one box's keyed family by color, which `congruent` plus a color test gives. The other two compare families whose key types differ: 42f14c03 pairs `Hole = [o, id]` against `Ident`, and 228f6490 pairs `Ident` against `Shape = [col, id]`. One keyed relation cannot hold both sides there, and a sum key would be a solver-defined type the style bans. `KeyedSetCompare` carries the two-sided shape in `Pat` and `Key`, and `D4Map` names its sides `src` and `dst`, so `Congruent<KeyA, KeyB, Val>` has precedent; self-congruence stays available by feeding one relation to both sides, at the cost that the three `Canon` sites (009d5c81, 00dbd492, 21897d95) instantiate both key params with one type.
- The box exposed through the instance path. Seven callers already hold a `BoxFrame` over the same set for another read: 63613498 `box.margin` for the panel test, 39a8645d `box.inner` for the output crop, 5dbc8537 `box.margin` for the reading order, 4ff4c9da `box.margin` for the alignment test, 42f14c03 `box.inner` for the output with `hole_box.extents` for its `$Dims` case, 00dbd492 `parse.inner` for placing patches back, 21897d95 `bbox` for the glyph pictures. With the box hidden, each keeps a second box over one set.

`Val` needs no change: eight callers compare positions alone and take `Val = Unit`, as `Occurrences` does for positional matching, and 5dbc8537 and 21897d95 carry colors.

Reimplementations: none.

Survey: 2026-09-10 15:21 — the solvers since 2026-09-09 08:00.

## Survey: `Congruent` over the 457-solver scope

Scratch: `/Users/davidlu/code/arc-workspace/.scratch/surveys/Congruent/` (`match.py`, `negfeed.py`, `hits.json`, `summary.txt`, `stems.txt`). The matcher walks every `KeyedSetCompare` instance in every scope, records the source relations of both member feeds and whether either reads a `BoxFrame`/`MarginFrame`/`Reframe` `inner`, and lists its `equals`/`covers` readers; a second pass looks for hand-written forms (a frame `inner` under negation or paired across two instances, `displacement`/`compose` under negation, and two count readouts joined or compared).

Across the scope: 77 `KeyedSetCompare` instances in 59 solvers, 185 `BoxFrame` instances in 145 solvers. Every instance was read in its rule.

### 1. Callers

Each reads `equals` as sameness of shape over box-relative cells, on both sides derived from the input.

1. 63613498 `same` (L38–40, the surfacing solver) — two `Ident` shapes from `Components` hold the same cells in their own boxes; `twin` (L44) is the non-key shape congruent to the key.
2. 39a8645d `same_shape` (L31–33), fed by `shape_cell` (L26–27) from `box.inner` — pieces of one shape; `copy` (L36–38) adds the same-color test, and `Mode` counts copies.
3. 5dbc8537 `congruent` (L88–90), fed by `shape` (L59–60) from `box.inner` with `Val = Color` — interchangeable pieces, read at L109 to add the per-reading tie-break conflict.
4. 4ff4c9da `footprint` (L34–38) — one `Components8` family split by color class on each side (mark blobs against covered blobs); `copy_cell` (L42) is a covered blob shaped like a mark blob.
5. 2a5f8217 `same` (L28–32) — one family keyed `Shape = [col, id]`, split into colored shapes and blank shapes; `paint` (L35) gives a blank shape the color of its congruent colored shape.
6. 42f14c03 `shape` (L77–81) — two families of different key types: holes `Hole = [o, id]` in `hole_box.inner` against objects `Ident` in `box.inner`; `fits(H, O, $Shape())`.
7. 776ffc46 `same_shape` (L41–43) — two families of different key types: each rectangle's reference shape (`Position`, in `ref.inner`) against each loose ink component (`Ident`, in `shape.inner`); `recolor` (L46–48) gives a congruent loose shape the reference's color. New since the 2026-09-09 survey.
8. 38007db0 `same` (L46–56, read at L64, L72, L80) — tiles from a `DividerFrame`, each viewed in a `BoxFrame` over its own full cell set with `Val = Color`; tiles with the same content are peers. The prior survey put this under "frame the parse gives"; the exclusion's qualifying clause ("where the box would quotient away the placement the model reads") does not hold here: the set is the whole tile, the box is the tile, and the model reads no in-tile placement. `Congruent` over `cut.tile_of` cells with colors computes exactly `same.equals`, and `tile_view`/`tile_content` serve nothing else.
9. 009d5c81 `Determine.same` (L72–77) — train examples whose marker keys (`parse.key_shape`, from `frame.inner` in `Parse`) agree; `Canon` gives one lookup entry per shape.
10. 00dbd492 `Determine.same` (L223–228) — rewritten objects (`obj_member`, from `parse.inner`) sharing a stored patch; `Canon` assigns patch ids.
11. 21897d95 `Determine.bcmp` (L363–368) — bracket patches viewed from `bbox.inner` with colors, `observed_member` aliased to `pattern_member`; `Canon` assigns glyph ids.

No family siblings among them (none carries `// family:`). The prior survey's caller 228f6490 lies outside this scope and was not re-examined.

Negative evidence for hand-written forms: no rule in the scope writes the operation outside `KeyedSetCompare`. The 22 rules with `displacement`/`compose` under negation are stamp-offset extractions and determination offset finders (31aa019c L98, 72322fa7 L60, 3e980e27 L41, 414297c0 L80, 4c416de3 L52, 20fb2937 L238, a9f96cdd L63, and the like). The 8 rules that pair two frame `inner` readouts are correspondences, not equality tests (58f5dbd5 L72, L83 seat a key over a block; 33b52de3 L32, 58743b76 L46, 6b9890af L76 render). The 18 rules joining two count or extent readouts are size and dims hypotheses (42f14c03 `$Size` L95 and `$Dims` L85, 3ed85e70 L68, 67c52801 L69, 7acdf6d3 L43, 446ef5d2 L104, 62593bfd L45, 83b6b474 L52, 7b3084d4 L74, and orderings).

### 2. Near-misses

Each with the exclusion that rules it out.

1. Set against a stored pattern (carries its own frame): 00dbd492 `same` in the program (L158–160, `params.patch_member`); 21897d95 `bshape` (L225–227, `params.bracket_glyph`); 4c177718 `pose` (L96–98, `params.chart_glyph`); 4c5c2cf0 `known` (L55–57, `params.pivot_shape`); 5a5a2103 `glyph` (L85–87, `params.marker`); 009d5c81 `key_match` (L53–55); 136b0064 `glyph_match` (L184–186); 17cae0c1 `glyph` (L79–81); 27a28665 `lookup_match` (L90–92); 995c5fa3 `tile_match` (L122–124); ed74f2f2 `key_match` (L96–98); 494ef9d7 `pairs` (L50–52, colors); 281123b4 `combine` (L131); and the `combine_match` family — 0520fde7, 0c9aba6e, 195ba7dc, 1b2d62fb, 31d5ba1a, 3428a4f5, 34b99a2b, 506d28a5, 5d2a5c43, 6430c8c4, 66f2d22f, 94f9d214, 99b1bc43, ce4f8723, d19f7514, dae9d2b5, e133d23d, e345f17b, f2829549, fafffa47.
2. Matching closed over D4 (`D4Map.onto`): 3d588dc9 `key_match` (L62–64; the stored key is also boxed, in stored D4 poses); 36d67576 `poses` (L53–57, model shape under every `d4_elem` in an anchor frame); 62593bfd `onto` (L51–68, hand-written `D4Map.onto`).
3. Containment without equality (`covers`): 14754a24 `maximal` (L95–100, `covers` and `!equals`); 15113be4 `cover` (L88, `covers`).
4. Content equality in a frame the parse gives, where the box would quotient away placement the model reads: 5a5a2103 `twin` (L95–97, ink at intile positions from `divide`); 66ac4c3b `line_set` (L38–40, ink by along-position of a line from `split`); 21897d95 `arms` (L101–104, a patch against its box's own edge lines, grid frame); 44f52bb0 `out_cmp` (L88–90) and b1fc8b8e `out_cmp` (L191–193), whole train outputs in the grid frame; the Determine canonicalizers 136b0064 `same` (L335–337, intile via `divide_by_size_2d`), 17cae0c1 `same` (L101–103, intile via `divide_by_size_slab`), 27a28665 `same` (L118–120, grid silhouette), 281123b4 `same` (L168–170, per-panel contributions), 995c5fa3 `same` (L161–163, tile content), ed74f2f2 `same` (L123–125, key tile content).
5. Fit at an explicit candidate translation: 18447a8d `exact` (L82–86, a landed piece against a hole at margin `K`); 2c181942 `mate` (L90–94, a docked piece's cells on the seat's line); 14754a24 `fragment` (L86–88, footprint marks in the grid frame against an object).
6. Members that are not cells: 80214e03 `content` (L46–48, color sets per line); 3a25b0d8 `sides` (L109–111, `Dir` sets); 494ef9d7 `Determine.same` (L76–78, colors); the `Sym`/`D4` group identifications 0934a4d8 `symid`, 0dfd9992 `named`, 18419cfa `grp`, 44d8ac46 `named`, 44f52bb0 `group`/`named`/`named_class`, 47996f11 `named`, 47c1f68c `sym_id`, 4938f0c2 `orbit`, 4c5c2cf0 `sym`.

### 3. Spec

1. **Two sides rather than one `cell` relation — supported by two callers beyond the surfacing solver.** 42f14c03 pairs `Hole = [o, id]` against `Ident`, and 776ffc46 pairs `Position` (rectangle boxes) against `Ident` (loose components). Neither can feed one keyed `cell` relation. The other nine callers self-compare (63613498, 39a8645d, 5dbc8537, 38007db0, 009d5c81, 00dbd492, 21897d95) or split one family by a color class (4ff4c9da, 2a5f8217); a two-sided `Congruent<KeyA, KeyB, Val>` serves them by feeding one relation to both sides, and the color-split pair either feeds each side its class or applies the color test on `congruent`. The 776ffc46 site strengthens the entry's existing argument: it is in the program, not in Determine, and its two key types are both parse-derived.
2. **The box exposed through the instance path — supported by seven callers.** 63613498 reads `box.margin` (L36) for the panel test; 39a8645d reads `box.inner` (L49) for the output crop; 5dbc8537 reads `box.margin` (L95, L110) for the reading order and feeds `shape` (L60) to `Occurrences`; 42f14c03 reads `box.inside` (L44), `box.inner` (L66, L69), and `hole_box.extents` (L85); 00dbd492 reads `parse.inner` (L166) to place patches back; 21897d95 reads `bbox.inner` (L375) for the glyph pictures; 009d5c81's `frame.inner` (L48) feeds both the stored-pattern `key_match` and Determine's `same`. With the box hidden, each keeps a second box over the same set. Four callers use the box for nothing else (4ff4c9da, 2a5f8217, 776ffc46, 38007db0). The entry's note that 4ff4c9da reads `box.margin` for an alignment test no longer matches the file: its `box` (L29–30) feeds only `footprint`.
3. **The `Not:` line's tile clause — a definition question from 38007db0.** The exclusion "content equality inside a frame the parse already gives" is qualified by "where the box would quotient away the placement the model reads". 38007db0 is a parse-given frame (tiles from `DividerFrame`) where that qualifier does not hold, because the compared set is the whole tile. The entry should state whether a full-rectangle set (a tile with its bg cells, `Val = Color`) is inside the operation or excluded as content equality; as written, it is inside, and I counted it as a caller. 5a5a2103 `twin` and 66ac4c3b `line_set` are the contrast: same parse-given frames, but only ink is compared, so the box would move it.
4. `Val` needs no change: eight callers take `Val = Unit`; 5dbc8537, 38007db0, and 21897d95 carry colors.

### 4. Reimplementations

Reimplementations: none.
