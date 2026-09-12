# `shift_opposite` — the shift that undoes a shift

The translation back along a Shift, so a solver holding one direction of a correspondence reads the other without negating each edge. A placement taken from `Occurrences` seats the shape on the cells; the solver that needs the cells seated on the shape wants this operation.

```
.decl shift_opposite(v: Shift, v_inv: Shift) inline
shift_opposite(V, V_inv) :- displacement(V, ORIGIN, V_inv).
```

Not: `opposite` and its Dir8 peers, which reverse a direction and carry no amount; `d4_inverse`, the inverse of a D4 element; `displacement` between two cells, which is the shift itself.

Match: a `displacement` atom with `ORIGIN` as one of its two Position arguments; or two `displacement` atoms in one rule with their two Position arguments exchanged, so one binds the shift and the other its inverse. Grep finds the first shape (`displacement(.*ORIGIN`); the parser (`tests/test_ast_match.py`) matches both.

Survey: 2026-09-11 02:54 — the whole corpus.

Callers:
045e512c fits — undoes an `Occurrences` seating of an object on the template, `displacement(M, ORIGIN, Delta)`, to get the step that carries the template's copy back onto the object.
3ed85e70 place — undoes the placement of a clue in a shape, `displacement(M, ORIGIN, V)`, to read the shift that seats the shape on the clue.
4e34c42c fitted — undoes a fragment-to-fragment fit, `displacement(V, ORIGIN, V_inv)`, so the fit read from the other fragment's frame is the same relation.
5207a7b5 slant — inside Params, undoes the slant's step, `displacement(V, ORIGIN, V2)`, so one line runs both ways.
652646ff drawn — undoes the placement of a color's cells in the whole figure, `displacement(M, ORIGIN, Box)`, to read the figure back onto the grid.
351d6448 cand — reaches the operation through `displacement` with its ends swapped: `displacement(P_intile, P_intile2, V), displacement(P_intile2, P_intile, V_back)` pairs each candidate velocity with the shift that undoes it.

Near-misses:
20981f0e clear_step — `opposite(D, D2), step_delta(D2, Delta)` builds a step away from a wall from a reversed direction; it holds no forward shift, so it is the `opposite` exclusion, which carries no amount.
3979b1a8 cand — `diag_opposite(Diag, Back), jump_delta(Back, N, Delta)` builds the jump back toward the input from a reversed corner; the same exclusion, `diag_opposite` reverses a direction and no shift is undone.
332efdb3 period — the wallpaper lattice's generators are stored as facts in both directions per axis; no rule holds one direction and derives the other, so the site states the set as a parameter value rather than writing the operation.
4290ef0e, 50c07299 — `displacement(P, M, V), compose(M, V, Q)` reflects a cell through a point: the shift is reapplied, not undone, which is the `displacement` exclusion, the shift itself.
4c177718 placement, 2c181942 dock_cell, 8a004b2b painted — each reads a seating shift as `displacement` between two cells, or composes a placement forward; the shift itself, the `displacement` exclusion.

Spec:
No interface change is argued by the sites. Every caller takes a Shift and wants the Shift back, and the two-argument inline form covers each one. Four of the six sites (045e512c, 3ed85e70, 4e34c42c, 652646ff) apply the operation to an `Occurrences` placement, and 652646ff and 3ed85e70 comment the step as reading the placement back into the other frame. That raises a question the entry should record: whether `Occurrences` should expose the inverse placement as its own readout, so those four callers read it directly, with `shift_opposite` kept for the sites that hold a shift from elsewhere (5207a7b5, 351d6448). The 351d6448 site shows a second statement of the operation, the swapped `displacement` pair, that the current `Match:` line's grep does not cover; the line should add that shape (two `displacement` atoms in one rule with their Position arguments exchanged) so the next survey reads it.

Reimplementations: none.
Matcher: a parser script over the corpus, 749 solvers, 13644 rules. Pattern hits: `displacement` with `ORIGIN` at a Position argument, 5; swapped `displacement` pair in one rule, 1; `jump_delta`/`step_delta` fed from an `opposite` output, 2; negated record components, 8, all Params facts; `compose` with `ORIGIN` as its sum, 0.

Box (2026-09-11): The code form reads `relative(V, ZERO, V_inv)`, both columns type `Offset`, and the entry's name follows `Shift` to `Offset`. Every caller writes that form today, and the `Not:` line's `displacement` between two cells is `relative`. The algebra states the ground: the records form a group under addition, so `ZERO` minus a value is its inverse. One caller falls outside the proposed signature — `652646ff` `drawn` negates an `Occurrences` placement, a `Position`, and reads the result as a `Box`, the figure's frame, which it then seats cells in with `compose`. The inverse of a general box is not a translation, so an inline typed `Offset` on both columns serves the translation sites and not that one. See docs/wf-solver/box.md.
