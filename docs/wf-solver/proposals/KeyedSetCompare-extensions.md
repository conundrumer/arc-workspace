# `KeyedSetCompare` extensions — the set-relationship order

`within`, `disjoint`, `intersects`, and the size projections, beside `covers` and `equals`. Not: a containment test between two unkeyed sets; counting with no pattern.

Match: `KeyedSetCompare`, `overlap`, `count :`, `_member(`, `best_`.

Callers: none. `within` has no site; `intersects` / `disjoint` are one-line joins at 16b78196, 0a1d4ef5, 184a9768, b7cb93ac; the size projections are `Tally` at 27a28665, 1b60fb0c, and 7acdf6d3; `best_covered` is 44f52bb0 alone. Reimplementations of `covers`: 15113be4, 44f52bb0 (fixed).

Closed: 2026-08-29. Interface: no change. Each extension is a one-line join or a `Tally` join at its sites, and `within` has no site.
