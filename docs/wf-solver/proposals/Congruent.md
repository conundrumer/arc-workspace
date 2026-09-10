# `Congruent<Key, Val>` — keyed cell sets equal up to translation

Which keyed valued cell sets hold the same cells up to translation: each set is read in its own bounding box, and two keys are congruent when those box-relative valued cells are the same set. A solver that asks "which object has this object's shape" builds it from two lib comps and three rules — a `BoxFrame` over the sets, a `KeyedSetCompare` fed from that box's `inner` on both sides, and a readout of `equals`.

```
.comp Congruent<Key, Val> {
    .decl cell(key: Key, p: Position, v: Val)  // input

    .init box = BoxFrame<Key>
    box.cell(Ky, P) :- cell(Ky, P, _).

    // A cell in its own set's box.
    .type Member = [p_inner: Position, v: Val]

    .init same = KeyedSetCompare<Key, Key, Member>
    same.pattern_member(Ky, [I, V])  :- box.inner(Ky, P, I), cell(Ky, P, V).
    same.observed_member(Ky, [I, V]) :- box.inner(Ky, P, I), cell(Ky, P, V).

    .decl congruent(key: Key, key2: Key)
    congruent(Ky, Ky2) :- same.equals(Ky, Ky2).
}
```

Not: a set compared against a stored pattern, which carries its own frame and needs no box (`covers` and `equals` on `KeyedSetCompare` already state that); matching closed over D4 (`D4Map.onto`); containment without equality (`covers`); the translations that fix one set (`ShiftInvariance`); content equality inside a frame the parse already gives, where the box would quotient away the placement the model reads; a fit test at an explicit candidate translation, where the box would discard that translation.

Match: two rules feeding one `KeyedSetCompare` instance's `pattern_member` and `observed_member` from the same box-relative cell relation — a `BoxFrame`, `MarginFrame`, or `Reframe` `inner` readout — with `equals` read as sameness of shape. Also any hand-written equal-shape test over two derived cell sets: a count comparison, a paired walk over both sets, or a `displacement` held constant across a set. Grep: `KeyedSetCompare<`, `pattern_member`, `observed_member`, `BoxFrame<`, `inner(`, `equals(`.

Survey: 2026-09-09 08:00.

Callers: 63613498 (`same`, over `Components` labels), 39a8645d (`same_shape`, copies of a piece), 5dbc8537 (`congruent`, interchangeable pieces), 4ff4c9da (`footprint`, one box split by color class), 2a5f8217 (`same`, one box split into blank and colored shapes), 42f14c03 (`shape`, an object against a hole), 228f6490 (`fits`, a hole against a loose shape), 009d5c81 (`Determine.same`, key shapes sharing a lookup entry), 00dbd492 (`Determine.same`, objects sharing a stored patch), 21897d95 (`Determine.bcmp`, patches sharing a glyph id). No family siblings among them.

The corpus holds 85 `KeyedSetCompare` instances in 67 solvers and 184 `BoxFrame` instances. Of those instances, 18 name one source relation on both sides and 2 more self-compare through an alias or a filtered source; 11 read either side from an `*.inner` readout. No site writes the operation outside `KeyedSetCompare`: of 17 rules binding an offset with `displacement`/`compose` under a negated atom, none tests shape sameness; the 20 keyed set inclusions by defect negation are ray, run, and region tests; the 6 comparisons of two `Tally` counts are size hypotheses, one of them 42f14c03's `$Size` case, a declared peer of its `$Shape` case.

Near: a set against a stored pattern — the `combine_match` family (3428a4f5, 5d2a5c43, dae9d2b5, f2829549, fafffa47 with their siblings), 3618c87e, a85d4709, 995c5fa3, 136b0064, 17cae0c1, 009d5c81 `key_match`, 27a28665, ed74f2f2, 4c177718, 5a5a2103 `glyph`, 00dbd492 `same` in the program, 4c5c2cf0, 1fad071e, 3b4c2228, ff28f65a, 2c181942 `mate`; containment without equality (50846271, 14754a24, 045e512c, 15113be4); D4-closed matching (6165ea8f, 62593bfd, 3d588dc9, 36d67576), which belongs to `D4Map-onto`, whose survey already names 39a8645d, 5dbc8537, and 42f14c03 as its translation-only peers; content equality in a frame the parse gives (a87f7484, 5a5a2103 `twin`, 6350f1f4 `solid`, 38007db0, 15660dd6, and the table canonicalizers 27a28665, 136b0064, 17cae0c1, ed74f2f2, a85d4709, 995c5fa3, 281123b4); placement-exact fit (18447a8d, 2c181942, b7cb93ac, whose interchangeable pieces fall out of `PlacementPruning.alive` with no congruence test); members that are not cells (the `Sym`/`D4` group identifications at 18419cfa, 0934a4d8, 44d8ac46, 47996f11, 47c1f68c, 981571dc, 11852cab, 0dfd9992, 44f52bb0, 4938f0c2, 4c5c2cf0, the color sets at 2ccd9fef and 494ef9d7, and 21897d95 `arms`).

Spec, from the callers: two changes, both argued by solvers other than the surfacing one.

- Two sides rather than one `cell` relation. Eight callers compare one keyed family and are served as written — 63613498, 39a8645d, 5dbc8537, 009d5c81, 00dbd492, and 21897d95 self-compare, and 4ff4c9da and 2a5f8217 split one box's keyed family by color, which `congruent` plus a color test gives. The other two compare families whose key types differ: 42f14c03 pairs `Hole = [o, id]` against `Ident`, and 228f6490 pairs `Ident` against `Shape = [col, id]`. One keyed relation cannot hold both sides there, and a sum key would be a solver-defined type the style bans. `KeyedSetCompare` carries the two-sided shape in `Pat` and `Key`, and `D4Map` names its sides `src` and `dst`, so `Congruent<KeyA, KeyB, Val>` has precedent; self-congruence stays available by feeding one relation to both sides, at the cost that the three `Canon` sites (009d5c81, 00dbd492, 21897d95) instantiate both key params with one type.
- The box exposed through the instance path. Seven callers already hold a `BoxFrame` over the same set for another read: 63613498 `box.margin` for the panel test, 39a8645d `box.inner` for the output crop, 5dbc8537 `box.margin` for the reading order, 4ff4c9da `box.margin` for the alignment test, 42f14c03 `box.inner` for the output with `hole_box.extents` for its `$Dims` case, 00dbd492 `parse.inner` for placing patches back, 21897d95 `bbox` for the glyph pictures. With the box hidden, each keeps a second box over one set.

`Val` needs no change: eight callers compare positions alone and take `Val = Unit`, as `Occurrences` does for positional matching, and 5dbc8537 and 21897d95 carry colors.

Reimplementations: none.
