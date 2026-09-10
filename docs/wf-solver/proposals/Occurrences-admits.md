# `Occurrences.admits` — the placements a partial view of a shape admits

A per-placement readout on `Occurrences`, containment read the other way: the placements whose shape, seated there, accounts for every cell of the key's set. `occurrence` asks that every shape member land on a matching cell, so a shape that shows only in part — occluded, damaged, clipped — has no occurrence; `admits` asks instead that no cell of the set land off the shape, which is what a caller reconstructing a known figure from what remains of it reads.

```
    // A cell of the key's set that the placement leaves out.
    .decl unexplained(key: Key, p: Position)
    unexplained(Ky, M) :- placement(Ky, M), cell(Ky, P, _), !image(Ky, M, P).

    // The placements that account for the key's whole set.
    .decl admits(key: Key, p: Position)
    admits(Ky, M) :- placement(Ky, M), !unexplained(Ky, M).
```

Not: `occurrence` (the shape ⊆ the cells, absence refuting); `mismatch` (its defect); a placement kept by a count of matched members against a threshold; `KeyedSetCompare.covers`, which compares two given sets and seats nothing.

Match: a rule pair that seats a shape at candidate placements and then keeps the placements no cell of the matched set contradicts — a defect rule whose body is the placement, a cell of the set, and the negated seated shape, and an acceptance rule negating that defect. Grep: `compose(`, `!` on a compose-defined relation, `displacement(`.

Survey: 2026-09-09 15:38, whole corpus.

Callers: 652646ff (surfacing, `stray` / `drawn`), 1acc24af (`uncovered` / `plugs`, where the acceptance rule also carries an access-region test that is outside the operation).

Near: the union of all occurrences covering the ink, with the placement column a wildcard (b1fc8b8e `uncovered`); a per-offset filter, each offset surviving on its own with no whole shape seated (3f23242b `missed`, 20fb2937 `missed` in `Determine`); the same coverage readout wanted over `D4Map`, where the enumerated thing is the transform rather than a placement, so no role swap is available (62593bfd `over` / `onto`); the compatible reading of a set's own mirror image (3345333e `contradicted`); `KeyedSetCompare.equals` over a hole and a landed piece (18447a8d `fits`); containment between two rival placements' covered sets (50846271 `unmatched`); `occurrence` negated over train examples (49d1d64f, 342dd610, 291dc1e1).

Closed: 2026-09-09 16:12. Lib holds the operation: `admits` is `occurrence` on the same instance with `shape` and `cell` exchanged. Under the exchange the partial view is the shape and the whole figure is the cells, `align` pairs the same candidates, and `mismatch` becomes `unexplained` at the inverse placement, which `displacement(M, ORIGIN, V)` reads back — 3ed85e70 sets that precedent and 269e22fb follows it. 652646ff is encoded that way.

The exchange carries a call site only where the inverted placement and the exchanged key serve the site's other consumers. At 1acc24af they do not: the acceptance is per notch, so the exchanged key gains the notch id, and `placed` and `unreached` ride on the placement in its own sense. That site keeps the hand-written acceptance over a non-exchanged instance.
