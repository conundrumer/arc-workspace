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
