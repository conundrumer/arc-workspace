# `KeyedSetCompare` extensions — the set-relationship lattice

`within`, `disjoint`, `intersects`, and the size projections, beside `covers` and `equals`. Not: a containment test between two unkeyed sets; counting with no pattern.

Match: `KeyedSetCompare`, `overlap`, `count :`, `_member(`, `best_`.

Homes: none. `within` has no site; `intersects` / `disjoint` are one-line joins at 16b78196, 0a1d4ef5, 184a9768, b7cb93ac; the size projections are `Tally` at 27a28665 and 1b60fb0c; `best_covered` is 44f52bb0 alone. Reimplementations of `covers`: 15113be4, 44f52bb0 (fixed).

Interface: no change.

Verdict: close. 2026-08-29.
