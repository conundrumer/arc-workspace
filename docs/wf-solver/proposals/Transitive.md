# `Transitive<Key, T>` — the transitive closure of a keyed edge relation

The pairs a chain of one or more edges connects, per key: an edge relation the solver derives (which figure covers which, which span overlaps which) closes into the relation its consumer needs given whole — a strict order for `Order.before`, an equivalence for `Canon.equiv`. `Order` counts `before` as given and never closes it, and `Canon` takes its equivalence as given, so every solver whose edges are pairwise observations writes the closure itself beside the instance.

```
.comp Transitive<Key, T> {
    .decl edge(key: Key, a: T, b: T)  // input

    // a reaches b by one or more edges.
    .decl path(key: Key, a: T, b: T)
    path(K, A, B) :- edge(K, A, B).
    path(K, A, C) :- path(K, A, B), edge(K, B, C).
}
```

Not: symmetric closure alone (`mapping(B, A) :- mapping(A, B)`); reachability from seeds over any edge relation, where only the reached node is kept (`Reach`, `Components`, a seeded read of a closure); a fixed composition of edges across keys (2546ccf6, a diagonal reflection as two axis reflections); a walk with a step count (`CycleWalk`, `Ray`, `MinHops`); a rank over an order already transitive (`Order` fed a comparison on a score).


Match: a rule whose head relation occurs twice positive in its body, the second argument of one occurrence bound to the first of the other, with the head taking the outer two (`r(A, C) :- r(A, B), r(B, C)`, with any shared leading key columns); the two-relation form, a base rule `path :- edge` beside a step rule `path :- path, edge` or `path :- edge, path`; and the statement reached through a primitive — a relation closed by such a rule and fed to `Order.before`, `Canon.equiv`, or a `Components.node` standing in for a closure. Match with the parser: the shape has no lexical anchor beyond the comment "closed transitively".

Survey: 2026-09-09 22:59


Result: over 619 solvers, three shapes were matched with the parser — the self-join closure (11 rules), direct recursion `r :- r, e` with a chaining variable absent from the head (113 rules), and every feed of `.before`, `.equiv`, or `.node` — and each hit was read in its rule. Sixteen callers, twelve in program code and four in Determine comps. No reimplementation of a lib primitive was met.

Spec: `path` as one-or-more edges serves the `Order.before` callers directly, since a strict order must not be reflexive. The callers that want zero-or-more edges (the `Canon.equiv` and orbit callers) write the identity row over their own domain beside the instance, which they need anyway because the domain is theirs, so the reflexive closure is `path` plus that row and no second output is needed. The Key parameter is exercised: 5792cb4d keys by chain end, and 20a9e565 writes two closures over two edge sets that one keyed instance would hold.

Callers:

- 68bc2e87 `under` — a color whose outline shows another color was drawn under it; closed, it ranks the colors through `Order.before`.
- 22425bda `stack.before` — the closure of `hides` at line crossings, written on `stack.before` itself.
- 652646ff `front` — the color that shows where two figures overlap is in front; closed, it feeds `stack.before`.
- 5792cb4d `chain.before`, keyed by chain end — closes `step` into the order along the chain.
- 2d0172a1 `mark_same` — overlapping marks on one axis take one line; closed, it feeds `Canon.equiv`.
- 0a1d4ef5 `cls.equiv` — closes `overlap` into bands, written on `cls.equiv`.
- 33067df9 `group.equiv` — closes `join` into groups, with a reflexive base over `ink`.
- 135a2760 `orbit.equiv` — closes `si.pair` at the panel's period into lattice orbits, feeding `Canon.equiv`.
- 50a16a69 `orbit` — closes `period_step` into lattice orbits, read directly by `out`.
- 20a9e565 `anc_drawn`, `anc_ext` — reflexive closures of two parent relations; one keyed instance would hold both.
- 3bd292e8 `same_side` — closure of the two-step edge `across ∘ across`, with a reflexive base over region ids.
- 78332cb0 `chain.before`, keyed by direction — closes `link` (a tile's shape leaves through one edge where the next tile's shape enters) into the order along the chain, written on `chain.before` itself.
- 3d31c5b3, 6a11f6da, a68b268e, ea9794b1 (with 75b8110e as its family sibling) — `beats` in Determine: tile T's ink shows over tile T2's on some cell; closed, it feeds `order.before` to recover the overlay priority.
- 80214e03 `block_line.equiv` — closes the adjacency of lines no boundary separates into block-lines, with a reflexive base over the content lines, feeding `Canon.equiv`.
- 7b5033c1 `before`, keyed by edge — closes `step` (the walk along the snake from the end nearer that edge) into the order along the path, feeding `path.before`.
- 88bcf3b4 `before`, keyed by worm — closes `step` (the worm's walk from its root) into the order along the walk, feeding `walk.before`; the rank against the worm's cell count truncates the walk.
- 3d6c6e23 `cone` — the cells an apex reaches by steps toward the floor, straight or diagonal; a reflexive-transitive closure of that fixed edge with the base over the apex candidates, read as a pair by `cone_size`.
- 2b83f449 `arrive` — the run entries a dot reaches by the composed edge `far_end ∘ drop`; a reflexive-transitive closure with the base over the dots, read as a pair by `rest_at` and tallied per stop by `pile`.

Near-misses: 281123b4 and cf98881b `beats` in Determine, fed to `order.before` with no closure because every panel pair collides directly, so the edge relation is already transitive; 2546ccf6 `reflect`, a diagonal reflection as the product of two axis reflections, whose key changes between body and head and whose chain is exactly two edges; seeded reads of a closure over an abstract edge, where the head keeps only the reached node (5961cc34, 2dd70a9a, 3e6067c3, 20a9e565 `chain`, 0dfd9992, 1d0a4b61, 1e97544e, 025d127b, 16de56c4, 332f06d7, 16b78196, 2b83f449), which never need the pair relation; walks whose step depends on the path or accumulates a payload (28a6681f, 4e34c42c, 72207abc, e633a9e5, 351d6448, 5545f144, 195c6913, 508bd3b6, 08573cc6, 79cce52d, 3ac3eb23, 4acc7107, 12422b43, 2072aba6, 3979b1a8, and the recursions over `neighbor`, `jump`, `compose`, and `dist`); and `Order.before` feeds that are score or product comparisons, transitive by construction (03560426, 212895b5, 3d6c6e23, 5587a8d0, 5d588b4d, dce56571, 1da012fc, 31f7f899, 89565ca0, 9caf5b84, 4df5b0ae, 3e6067c3 `seq.before`, 72207abc `order.before`).

Survey: 2026-09-09 23:09

Result: delta over the four solvers changed after the first survey (67e490f4, 6855a6e4, 689c358e, 692cd3b6). No callers: none of the four has a recursive rule or feeds `Order.before` or `Canon.equiv`; their two `.node` feeds are plain grid adjacency. No near-misses, and nothing bears on the spec.

Survey: 2026-09-10 04:11

Result: delta over the 341 solvers changed after the second survey, matched with the parser in every scope (self-join closure, direct recursion with a chaining variable absent from the head, and every feed of `.before`, `.equiv`, or `.node`). No new callers: every closure site met is one the entry lists. 36fdfd69 no longer closes `meet` itself: its `cluster` is a `Components8` whose `step` is fed composed `step_delta`s (the `GapComponents` form), so `Components` holds the closure over its own domain, and it is dropped from `Callers`. No reimplementation of a lib primitive was met.

Near-misses: seeded reads of a closure whose head keeps the reached node with a payload, never the pair (045e512c `copy`, 4c7dc4dd `spread`, 5207a7b5 `region`, 53fb4810 `pattern`, 6a980be1 `strip_out`, 7447852a `mark_cell`, 58e15b12 `trace`, 60d73be6 `image`, 762cd429 `copy`, 447fd412 `carry`, 47c1f68c `unfold`); walks whose step depends on the state (28e73c20, 69889d6e, 6bcdb01e); walks with a step count (6df30ad6 and 759f3fd3 `Dilate.depth`); symmetric closure alone (5207a7b5 `Params.slant`); a fixed one-step composition (6165ea8f `slot`); argmin subsumption (5ffb2104 and 6ad5bdfd `Settle.rest`); `Order.before` feeds transitive by construction (3a25b0d8, 694f12f3, 6cbe9eb8, and 1e5d6875 `prec.before` in Determine, the `beats` shape with one color pair, as 281123b4); `Canon.equiv` feeds transitive by construction (142ca369, 269e22fb, 3aa6fb7a, 3d588dc9, 4c177718, 1caeab9d, 5623160b, 67636eac, 5289ad53, 44f52bb0, b1fc8b8e, 281123b4, 494ef9d7, 409aa875); and the two `Components.step` overrides (36fdfd69, 6ffbe589), both `GapComponents`.

Spec: nothing in the delta changes the interface or the definition. When the edge is a bounded spatial nearness, `Components` with a `step` set holds the closure and the ids, so the callers that remain all have non-spatial edges (overlay precedence, span overlap, ancestry, lattice orbits, tile continuation). 60d73be6 `image` is an orbit closure read seeded, which confirms the seeded-read exclusion in `Not:` rather than asking for a second output.

Survey: 2026-09-10 07:00

Result: delta over the 373 solvers changed after the third survey, matched with the parser in every scope: the self-join closure (5 rules, all already listed), direct recursion with a chaining variable absent from the head (58 rules), and every feed of `.before`, `.equiv`, or `.node` (278 rules; the 233 `.node` feeds are all plain cell or shift sets for `Components`, `Reach`, or `Slide`). Three new callers, all in program code: 7b5033c1, 3d6c6e23, and 2b83f449 (the first survey listed 2b83f449 as a seeded read; the site keeps the source, and the pile count needs the pair). No reimplementation of a lib primitive was met.

Near-misses: `Order.before` feeds transitive by construction — 212895b5 `step_order.before` in Determine, 3d6c6e23 `fill.before`, 5587a8d0 `nest.before`, 7e576d6e `seq.before`, 89565ca0 `fewer.before`; `Canon.equiv` feeds transitive by construction — 5587a8d0 `patch.equiv` (same color, or `blob.conn`), 7b3084d4 `by_color.equiv` (symmetric closure alone, transitive because the task's marker touches one color); seeded reads of a closure whose head keeps the reached node, never the pair — 89565ca0 `line`, 7b0280bc `on_route`, and the sites the earlier results list; walks whose step depends on the state or carries a payload — 212895b5 `turtle`, 7e2bad24 `enter`, 7ec998c9 `shade`, 7d419a02 `shade`, and the earlier-listed sites; walks with a step count — 7b0280bc `MinHops.dist`, 6df30ad6 and 759f3fd3 `Dilate.depth`; fixed one-step compositions — 2546ccf6 `reflect`, 6165ea8f `slot`; argmin subsumption — 5ffb2104 and 6ad5bdfd `Settle.rest`; and the `Components.step` override in 36fdfd69.

Spec: nothing in the delta changes the interface or the definition. 7b5033c1 exercises the Key parameter again (by `Dir`, as 78332cb0). 3d6c6e23 and 2b83f449 are the zero-or-more reading: each writes the identity row over its own seed set beside the closure, which confirms that `path` as one-or-more edges plus a caller-written base suffices. Both close a fixed spatial edge that no lib component holds (a three-way cone, a two-hop composite), so they stay callers rather than `Ray` or `Components` sites.

Survey: 2026-09-10 20:37 — the solvers since 2026-09-10 07:00.

Callers: the transitive closure of a keyed edge relation (`Transitive<Key, T>`), surveyed over the 54 solvers in scope, matched with the parser in every scope: the self-join closure (1 rule), direct recursion with a chaining variable absent from the head (10 rules), and every feed of `.before`, `.equiv`, or `.node` (52 rules; the 42 `.node` feeds are plain cell, shift, or region sets for `Components`, `Reach`, `DrawnRect`, or `Slide`). One caller, already listed; no new caller.

- 88bcf3b4 `before`, keyed by worm — closes `step` (the worm's walk from its root) into the order along the walk, feeding `walk.before`; the site stands as the entry lists it.

Near-misses:

- 880c1354 `next_cell` — the first region cell after p along the border, recursing through the cells of the fixed band; the head keeps a pair, but the recursion threads only through band cells and reports one successor per start, the first cell of another kind, so it is a walk whose continuation depends on the content, not the reached set of an edge.
- 89565ca0 `line` — the self-join hit: a frame's line read through the cells that hide it, with two line cells behind; the head keeps the reached cell, never the pair (seeded read).
- 88bcf3b4 `leg`, `free` — walks whose step depends on the state (the leg's goal), the head keeping the reached cell with the worm id.
- 045e512c `copy`, 0dfd9992 `out`, 08573cc6 `arm`, 212895b5 `turtle` — walks whose step carries a payload or depends on the state, the head keeping the reached node.
- 759f3fd3 `Dilate.depth` — a walk with a step count.
- `Order.before` feeds transitive by construction: 8698868d `block_rank.before` and `piece_rank.before` (a count comparison, `fewer`), 89565ca0 `fewer.before` (a tally comparison), 212895b5 `step_order.before` in Determine (a product comparison).
- `Canon.equiv` feeds transitive by construction: 84f2aca1 `rect_id.equiv` (the identity over drawn rectangles, an id generator), 142ca369 `pick.equiv` in Determine (the total equivalence over an example's launch cells), 409aa875 `pick.equiv` in Determine (`D4Map.map` between mark footprints, closed under D4 composition), 44f52bb0 and b1fc8b8e `class.equiv` in Determine (`KeyedSetCompare.equals`).
- `Components.step` override: 88207623 `blob.step`, the Dir8 step set on a `Reach` (an 8-adjacency `Reach`, since lib has `Components8` and no 8-adjacency `Reach`); the closure over its own domain stays in `Components`.

Spec: nothing in this scope changes the interface or the definition. The one caller (88bcf3b4) exercises the Key parameter as before, with `path` as one-or-more edges feeding `Order.before` directly. 880c1354 `next_cell` is the closest new site: it could be written as a closure over the band edge plus one exit step, but that takes three rules against its two, and its result is one successor per start, so it confirms the walk exclusion in `Not:` rather than asking for a second output.

Reimplementations: none.
