# `shift_opposite` — the shift that undoes a shift

The translation back along a Shift, so a solver holding one direction of a correspondence reads the other without negating each edge. A placement taken from `Occurrences` seats the shape on the cells; the solver that needs the cells seated on the shape wants this operation.

```
.decl shift_opposite(v: Shift, v_inv: Shift) inline
shift_opposite(V, V_inv) :- displacement(V, ORIGIN, V_inv).
```

Not: `opposite` and its Dir8 peers, which reverse a direction and carry no amount; `d4_inverse`, the inverse of a D4 element; `displacement` between two cells, which is the shift itself.

Match: a `displacement` atom with `ORIGIN` as one of its two Position arguments. Grep: `displacement(.*ORIGIN`.

Closed: 2026-09-09 14:31. Lib holds the operation. `displacement(V, ORIGIN, V_inv)` states it in one atom: a Shift is a Position, and the displacement from it to the origin is the way back. Three solvers write that atom (3ed85e70, 5207a7b5, 4e34c42c), all reading a placement or a delta from its far end, so the idiom is settled and a named primitive would only rename it.
