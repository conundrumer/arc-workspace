# `Between.strict` — marks strictly on both sides

A `strict` output beside `Between.between`: key-k marks lie on both sides of p in its line, along one of the key's axes, with p itself not a casting mark on either side. `between` reads a mark as on its own ray (`cast` at step 0), so over a domain that contains marks, every mark folds in; `strict` requires a nonzero step on both rays, which is what a caller whose domain covers the marks needs. Over a domain that excludes marks, the two coincide.

Code form, inside `Between`:

```
.decl strict(key: Key, p: Position)
strict(Ky, P) :-
    axis(Ky, A), axis4_of(D, A), dir8_opposite(D, O),
    ray(Ky, P, D, K, _), K != 0,
    ray(Ky, P, O, K2, _), K2 != 0.
```

Not: `between` (inclusive fold); a one-sided strict read (`ray(..., K, _), K != 0` past a single mark); a span test written against stored endpoints rather than a cast.

Match: two `ray` (or `clear`) reads on one position at a direction and its opposite, each with a nonzero step test; or an equivalent marks-on-both-sides fold written with `nearer` or `dist` comparisons against mark positions on both sides of a line.

Survey: 2026-09-08 01:36

Callers:
- 253bf280 (local relation `between` over `Ray<Choice>`; its `$Paint` case's domain covers the marks, so the inclusive fold would fill every mark)
- 7666fa5d (local relation `strict` over `Between<Unit>`, `:42-45`; its marks are diagonal lines thickened by the cells they step past, and its domain covers them, so the inclusive fold would fill the step cells on a line's outer side)

Near-misses:
- 505fff84:48 — the closest structural twin: two `ray` reads at a direction and its opposite. Its domain excludes the marker colors, where strict and inclusive coincide, and its two sides read different keys (one end color each), which no single `Between` key holds.
- Inclusive fold plus a mark-removal guard: 06df4c85:44,47; 1478ab18:119; 4290ef0e:61; 4a21e3da:68. Each removes a different set by identity, not by step count; `strict` keeps a mark that two further marks flank, so none of them computes it.
- Both-sides shapes that are not a mark cast: 0d87d2a6:35 (edge-pinned markers), 35ab12c3:52 (half-planes, not collinear), 1c02dbbe:54 (one-sided past a mark), 3e6067c3:65 (box margins, keeps the endpoint pair), 20981f0e:79 (frame-edge distances), 2b01abd0:32 (reflection pairing over two cells), 9c56f360:57 (one-sided complement), 3490cc26 and 28a6681f (folds of absence).
- Adjacency flanks at reach one through `neighbor` (a699fb00:27 and kin): no cast, so no step to test. a699fb00 already carries the adjacency flank and the `Between` fold as separate cases.

Spec:
- `strict` is an added output beside `between`, not a change to it: thirteen `Between` instances whose domain covers the marks want the inclusive reading (a count including its ink endpoints; fills that cover the endpoints; same-color paint handing a mark its own color).
- The mark-removal sites argue for no second interface: each removes a different set, and none computes `strict`.
- 505fff84's per-side mark sets sit outside `Between` at any key — an observation, not a change.
- Migration of 253bf280 feeds `axis(Ch, A) :- impl_choice(Ch), axis_elem(A)` beside its existing `dir` — `Between`'s existing contract.

Survey: 2026-09-10 03:42

Scope: the 358 solvers `since "2026-09-08 01:36"` lists. A modification-time cutoff does not narrow it: every solver's mtime postdates the cutoff, and 308 of the 358 are untracked. The prior survey's own callers and near-misses sit in the list, so the results below are the delta against the entry.

Callers: none new. The lexical signature (a `ray`/`clear` read with a nonzero step test) hits 21 files; every hit but 253bf280 is one-sided. The parser shape (two positive reads of one cast-like relation — ray, clear, cast, clear_cast, stop, run, halt, rest — in one rule, sharing the position and differing in direction) hits only 253bf280:32 and 7666fa5d:42. The split form (two cast-derived relations read on one position in a rule) hits only paint-or-keep disjunctions (a relation and its own negation).

Near-misses, new:
- Inclusive fold plus a mark-removal guard, kin of 1478ab18:121: 6a980be1:43 (`!line_cell(P)`), 55783887:33 (`blank(P)`, by color), 4c7dc4dd:137-140 (the read is restricted to hole-valued cells; marks render by a separate rule at 136), 538b439f:78-82 (`!rect`, `!image`, by identity). Each removes by identity or value, not by step count.
- Domain excludes the marks, where strict and inclusive coincide: 55059096:25, 60a26a3e:59, 6e453dd6:75, 342ae2ed:38 (bg domain).
- One-sided cast with a far-end bound: 342ae2ed:55-57 — `shot.ray(P, D, K, P1), K < K_end`, keyed by a pair of facing corners; the second side is a distance bound, not a second read.
- Edge-pinned markers, kin of 0d87d2a6:35: 22eb0ac0:28-31 (`edge_match`: `dist(P1, D, 0)`, `dist(P2, D2, 0)`, `same_line`).
- Two cells paired across a wall, kin of 2b01abd0:32: 1efba499:57-61 (`crossing`: a loose cell `beyond` on side D and a counterpart `beyond` on the opposite side, in one line). Both-sidedness is about a wall between two cells, not marks about a cell.
- Adjacency flanks at reach one through `neighbor`, kin of a699fb00:27: 182e5d0f:24-28, 18419cfa:84-87, 2b83f449:38-40, 3ad05f52:38-42; 6c434453:53-56 is the four-sided form by defect negation. No cast, so no step to test.

Spec: unchanged. Seven more `Between` instances whose domain covers the marks want the inclusive reading — 16de56c4:108-114 (reaches the outermost ink), 22eb0ac0:43-46, 2c608aff:32-36, 40853293:27-38, and 6cdd2623:65-70 (same-color paint: a mark receives its own color), 25c199f5:69-72 (the stack includes the ink slabs), 29700607:48-54 (the wire includes its header, elbow, and marker). With the four new guard sites, the count of instances that read inclusively and remove by identity grows, and none of them computes `strict`, which is the entry's existing argument for an added output rather than a changed one.

Reimplementations: none at the sites opened.
