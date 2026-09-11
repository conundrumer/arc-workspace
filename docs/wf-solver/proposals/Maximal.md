# `Maximal<Key, Item, Member>` — the sets no other set of the family contains

The items of a keyed family whose member set no other item's set strictly contains: containment is read over one member relation, so a caller with a family of candidate sets keeps the greediest ones in one atom. It is how a solver picks the placements that take the most of what they explain, when nothing else orders the candidates.

```
.comp Maximal<Key, Item, Member> {
    .decl member(key: Key, item: Item, m: Member)

    // Two sets that share a member — the only pairs containment can order.
    .decl _rival(key: Key, item: Item, item2: Item)
    _rival(Ky, I, I2) :- member(Ky, I, M), member(Ky, I2, M), I != I2.

    // A member of item's set that item2's set lacks.
    .decl _unmatched(key: Key, item: Item, item2: Item)
    _unmatched(Ky, I, I2) :- _rival(Ky, I, I2), member(Ky, I, M), !member(Ky, I2, M).

    .decl _dominated(key: Key, item: Item)
    _dominated(Ky, I) :- _rival(Ky, I, I2), !_unmatched(Ky, I, I2), _unmatched(Ky, I2, I).

    .decl maximal(key: Key, item: Item)
    maximal(Ky, I) :- member(Ky, I, _), !_dominated(Ky, I).
}
```

Not: `KeyedSetCompare.covers` between a family and a separate catalog; `equals`; the largest set by count (`ArgExtremes` over `Tally`); a greedy pick under a caller-supplied priority (`Preempt`); an exact cover (`CoverForcing`).

`KeyedSetCompare` holds containment already, and a caller reaches the maximal sets by feeding one family to both sides and negating `covers` with `!equals`. Two things argue for the operation of its own. The interface: the caller states the family once, not twice. The cost: `covers` counts over every observed × pattern pair, and 50846271's family of a few thousand placements does not finish, while the containment a maximal test needs only ranges over the pairs that share a member.

Ties are kept: two items with identical member sets are both maximal, which is what `!_unmatched(I, I2), _unmatched(I2, I)` gives. Both call sites read it that way. An item whose member set is empty gets no tuple; a placement covers at least one member, so both call sites are clear of it.

Match: `covers(` with `!` and `equals(` in one rule over a self-fed `KeyedSetCompare`; or a hand-written pair of rules over one keyed member relation, where one rule finds a member the other set lacks and a second negates it in both directions.

Survey: 2026-09-09 14:30
Survey: 2026-09-09 14:51 — the eight solvers written or edited since the first survey.

Callers: 50846271 (`cross`, over placements keyed by case and arm), 14754a24 (`dominated` / `placement`, over placements keyed by footprint case). No third caller: of the corpus's 85 `KeyedSetCompare` instances, 23 self-feed one family, and 22 of those read `equals` alone; of the 26 hand-written rules matching the "a member the other set lacks" shape, only 50846271 composes them into a containment test. The follow-up survey found no caller in its scope: of its 7 `KeyedSetCompare` instances, 3 self-feed one family and all 3 read `equals` alone, and neither hand-written shape fires.

Spec question — the group dimension. A family's items carry a grouping that rivalry must not cross: 50846271 compares placements only within one case and one arm, 14754a24 only within one footprint case, and one grid mark belongs to placements under every group. Folding the group into the key record would let an arm-3 placement dominate an arm-1 one, so Key is the group and Item the compared thing, after `Excess<Key, Member>` and `ArgExtremes<Key, Val>`. Neither caller reads anything but `maximal`, so the three steps are comp-internal.

Near-misses: `covers` against a separate catalog (045e512c, 15113be4, 4c5c2cf0); the biggest catalog entry by count (44f52bb0); a self-fed family read for `equals` alone (a87f7484, 15660dd6, 3a25b0d8, b1fc8b8e); containment between two different families, where nothing is dropped (1acc24af, 4e34c42c); `covers` between two disjoint families of footprints (4ff4c9da); a family of placements folded into one union and compared against the member set, so no placement is dropped (b1fc8b8e `parse.covers`); a keyed set difference kept as output data (2037f2c7, 4c7dc4dd); a tie test over distances rather than membership (1da012fc); exact cover and joint-placement refutation (the `CoverForcing` and `PlacementPruning` sites). `Preempt`'s entry already draws the boundary the other way, naming 14754a24's `dominated` as a one-shot test against every rival.

Survey: 2026-09-10 19:57 — the solvers since 2026-09-09 14:51.

Survey of `Maximal` — the sets no other set of the family contains — over the 65 solvers in scope.

1. Callers: none.
   Negative evidence: the scope holds 21 `KeyedSetCompare` instances, and none pairs a positive `covers` with a negated `equals`. The two self-fed ones (44f52bb0 `Determine.out_cmp`, b1fc8b8e `Determine.out_cmp`) read `equals` alone. The hand-written "a member the other set lacks" shape (one relation positive and negated in one rule, sharing one variable and differing on another) and the "both directions" shape (a swapped-argument pair over one relation, one side negated) fire in no rule of the scope; the same matcher finds both shapes in 50846271 outside the scope, so the matcher is sound.

2. Near-misses:
   1. `covers`/`equals` against a separate catalog: the `combine_match` instances of 0520fde7, 0c9aba6e, 195ba7dc, 1b2d62fb, 31d5ba1a, 3428a4f5, 34b99a2b, ce4f8723, d19f7514, dae9d2b5, e133d23d, e345f17b, f2829549, fafffa47 (`params.combine_member` against the decomposed tiles, `equals`); 0dfd9992 `Determine.named` and 44f52bb0 `Determine.named` / `Determine.named_class` (`sym_member` against the invariance set, `equals`); 2c181942 `mate` (the seat cells per Dir against each docking's cells on the seat line, `equals`).
   2. The biggest catalog entry by count: 44f52bb0 `group` with `best_id` (`covers`, then `ArgExtremes` over `pattern_size`).
   3. A self-fed family read for `equals` alone: 44f52bb0 `Determine.out_cmp` (feeds `differs`), b1fc8b8e `Determine.out_cmp` (feeds `Canon`).
   4. A family of placements folded into one union, so no placement is dropped: b1fc8b8e `Parse.uncovered`, 7f4411dc `square_kept`, 142ca369 `mark`, 409aa875 `placed`, d9fac9be `out` under `$Box`.
   5. An extremum over a scalar, not containment: 045e512c `reach` (`ArgExtremes` over jump length); the `Mode`-over-cells "largest" picks in 045e512c `biggest`, 1a6449f1 `biggest_hole` / `biggest_region`, 8731374e `biggest`, 9565186b `biggest`, b7cb93ac `largest`.
   6. Exact cover and joint-placement refutation: b1fc8b8e `forcing` (`CoverForcing`), b7cb93ac `pruning` (`PlacementPruning`).

3. Spec: no change. No site in the scope reads containment within one family, so the group-dimension question and the ties reading stand on the two prior callers alone, as caller-only signals.

4. Reimplementations: none.
