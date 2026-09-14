# `Between.on_axis` — the axis a two-sided fold ran on

`Between` accepts several axes under one key, folds each of them, and drops which one fired, so a caller that acts on the fold's axis recovers that axis outside the unit.

Code form, inside `Between`:

```
.decl on_axis(key: Key, p: Position, a: Axis4)
on_axis(Ky, P, A) :-
    axis(Ky, A), axis4_of(D, A), dir8_opposite(D, O),
    ray(Ky, P, D, _, _), ray(Ky, P, O, _, _).

between(Ky, P) :- on_axis(Ky, P, _).
```

Not: `between` (the fold with no axis); `Between.strict` (the same fold with a nonzero step on both sides); the instance's own `axis` input read back on the key (it gives every axis fed, not the one that folded); a one-sided `ray` read tagged by its direction.

Match: a rule that reads `between`, or a local both-sides fold over `ray` or `clear` at a direction and its opposite, and binds the fold's axis, whether that axis comes from the key, from a relation re-derived from the same marks, or from a second read of the instance's `axis` input; also an instance whose key holds an Axis, an Axis4, or a DiagAxis while its `mark` and `cell` inputs do not vary with that key.

Survey: 2026-09-14 10:30 — every solver.

Callers:
070dd51e line_axis/span — `bet.axis` takes both axes under each color key, so `span(P, Col, A)` recovers the fold's axis by joining `line_axis(Col, A)`, a relation re-derived from the same marks, and the over-axis rule then picks the winning span at a crossing.
40853293 over — `spans.axis` is fed from `mark_axis(Col, A)` and `over` reads that same relation back beside `spans.between(Col, P)`; a color with three or more marks feeds two axes, and the read-back then tags a cell with an axis its span did not run on.
55783887 emit — the instance is keyed by `DiagAxis` with `span.axis(DA, DA)` while `span.cell` and `span.mark` do not vary with the key, so the key exists only to carry the fold's diagonal out to `diag_perp(DA, DA2)`.
95755ff2 span/cast.cell — the instance is keyed by `Axis` with `span.axis(A, A)` and key-independent `cell` and `mark`, so `cast.cell([$Span(), D], P) :- axis_of(D, A), span.between(A, P)` can hold the cast to the axis the span ran on.

Near-misses:
0d87d2a6 mark_cast and 6cdd2623 mark_cast — each is keyed by an Axis, but `mark` varies with that key (the marker sits on the edge of that axis), so the key carries mark data rather than only the fold's axis; neither `line(P, $Span())` rule binds the axis.
16de56c4 span and 4290ef0e side — the key holds an Axis, and `cell` and `mark` vary with it, so one axis is fed per key; no read binds the axis.
6a980be1 on_pattern_line — reads `strip_span.axis($U(), A2)` back beside the fold; that is the instance's own `axis` input read back, and one axis is fed.
253bf280 between and 7666fa5d strict — local both-sides folds over `ray` at a direction and its opposite, but each demands a nonzero step on both sides, which is `Between.strict`; neither head carries the axis.
505fff84 seg — a fold over a direction and its opposite, but the two `ray` reads come from separate keys of one `Ray` instance rather than one instance's two-sided fold, and the head drops the axis.
08573cc6 arm_cell and 9c56f360 strip — two `ray` reads in one rule, but 08573cc6 compares two distances along one direction and 9c56f360 puts the opposite direction under negation; neither is a two-sided fold.
0f63c0b9 beaten — two `ray` reads from different keys, contesting which mark is nearer; no fold along an axis.
Single-axis keys with no axis read: 538b439f span, 136b0064 stroke, 8597cfd7 spans, 25c199f5 span, 7acdf6d3 hollow, 4a21e3da span, 6e453dd6 flank, 505fff84 set_spans, 6a980be1 strip_span, 22eb0ac0 spans, a699fb00 spans, aa18de87 axis_spans. Each feeds one axis per key, so nothing is dropped.
Multi-axis keys with no axis read: 06df4c85 bet, 070dd51e bet (the `$Around()` and `$Over()` fills), 1478ab18 span, 1f876c06 span, 22168020 spans, 29700607 path, 2c608aff span, 55059096 span, 60a26a3e link, 4c7dc4dd flank, 8cb8642d join, 8b9c3697 cavity, 992798f6 span, dbc1a6ce spans, ded97339 ink_spans and self_spans, e729b7be crossing, cbded52d btw, 7e576d6e span, 0e671a1a span. Each folds several axes under one key and paints without asking which fired.

Spec:
The interface and the definition should stand as written. The evidence for the operation is in 55783887 and 95755ff2, where the key is an Axis or a DiagAxis and `cell` and `mark` do not vary with it: the multi-axis fold that `Between` offers goes unused, and the key exists only so the axis survives the fold. With `on_axis`, both instances take a `Unit` key, and the axis comes out of the unit. 070dd51e and 40853293 encode one model shape two ways — one re-derives the axis from the marks, one narrows the `axis` input and reads it back — so the operation also settles a split. 40853293's read-back is the one site where the current form is not merely longer: it names every axis fed for that color, which parts from the fold's axis once a color feeds two.
The `a: Axis4` column matches the type of `Between.axis`, and each caller narrows it at the call site: 070dd51e, 40853293 and 95755ff2 to `Axis`, 55783887 to `DiagAxis`. That narrowing is the corpus's usual read of an Axis4 column, as `Ray.dir` is read, and is no ground to split the column by axis type.
No site binds the axis of a strict fold, so there is no evidence for exposing the axis on `Between.strict`.

Reimplementations: none.
Search method: a `Between` name grep over `programs/solvers/` gave 42 files, of which 40 hold the unit and 2 hold the name in prose. A rule-splitting scan over all 793 solvers for two or more `ray` or `clear` atoms in one rule at two directions gave 5 rules. A scan of every rule reading `.between(` that also names an axis gave 6 hits, of which 2 named a case constructor rather than an axis.
