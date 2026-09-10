# `MinHops<Key, Node>` — fewest-hop distance over a supplied edge relation

Breadth-first search as a relation: the fewest-hop distance from a seed set over a caller-supplied edge relation, per key, together with the edges a fewest-hop walk uses. `pred` lets a consumer trace a fewest-hop walk backward with no hop counting of its own. The route a network task highlights between two ends is the trace of `pred` from one end with the other as the seed. Lib target: program comp beside `Reach`.

```
.comp MinHops<Key, Node> {
    .decl edge(key: Key, a: Node, b: Node)  // input
    .decl seed(key: Key, n: Node)  // input

    // Hops from the nearest seed; subsumption keeps the minimum per node.
    .decl dist(key: Key, n: Node, k: number)
    dist(K, N, 0) :- seed(K, N).
    dist(K, B, D + 1) :- dist(K, A, D), edge(K, A, B).
    dist(K, N, D) <= dist(K, N, D2) :- D2 < D.

    // a is a fewest-hop predecessor of b — an edge some fewest-hop walk uses.
    // Tied walks all appear, so a consumer tracing it backward gets their
    // union; a single walk needs a tiebreak on top.
    .decl pred(key: Key, b: Node, a: Node)
    pred(K, B, A) :- edge(K, A, B), dist(K, A, D), dist(K, B, D2), D2 = D + 1.
}
```

Call site (7b0280bc): squares and wires are the nodes, touching is the edge, and each of the two end squares seeds one key; the route is `pred` traced from the other end, and its wires and squares are recolored.

Not: reachability with no distance (`Reach`); erosion depth from a set's own rim (`Rim.depth`, which is this over grid adjacency); outward depth from a supplied seed set over grid adjacency (`Dilate`); a rank under a supplied transitive order (`Order.rank`); a walk of a stored step count along a cycle (`CycleWalk`); a nearest-first walk whose held set grows with the walk (`GreedyWalk`, closed); weighted distance.

Match: a recursive rule that derives a hop count from a hop count at an edge-neighbor with `+ 1`, from a base of 0 over a seed set, over an edge relation the solver builds (not grid adjacency), with subsumption or a min aggregate keeping the least; an `Extremes`/`ArgExtremes` fold over such a count; and the unfolded form, a walk unrolled into a fixed chain of edge atoms (2dd70a9a's `$Jog`, three legs), which is this operation only when a minimum over the chain length is taken. Grep `+ 1`, `<= ` at a clause head, and `.depth(` reads whose walked set is not the rim's own set, then confirm the edge relation and the readout with the parser (`tests/test_ast_match.py`).

Closed 2026-08-30 with 2dd70a9a as the only caller: it dropped its `$Fewest` case, whose fewest-turns hypothesis has no relational form without the operation, and kept a greedy walk. Reopened 2026-09-10 by 7b0280bc, whose only fitting hypothesis is the fewest-hop route: the data rules out every cell-count, wire-length, and fixed-length reading, so the solver cannot encode the task without the operation.

Survey: 2026-09-10 05:10

Result: over the corpus, 670 solvers, matched with the parser. No second caller. Recursive rules whose head carries a `+ 1` from a same-relation body atom: three, all in proposal comps — this one and the two `Dilate.depth` sites (6df30ad6, 759f3fd3). Subsumptive clauses: those three and the two `Settle.rest` sites (5ffb2104, 6ad5bdfd), which settle a Position. No `min`/`max` aggregate in any solver. Every `.depth(` read is `Rim.depth` walked inward from the walked set's own rim, `Dilate.depth`, or a stored number (52364a65). Of the 109 solvers with a directly recursive rule, none keeps a minimum over a count. The eight `Extremes`/`ArgExtremes` folds fed from a walk fold `Ray` step counts, `Rim.depth`, or non-walk scores.

Near-misses, by the exclusion that rules them out. `Dilate`: 6df30ad6 `rings`, 759f3fd3 `Parse.rings`; 5792cb4d `step`/`chain`, a hop count over 4-adjacency read as `Order.rank` after closing the chain by hand. `Order.rank`: 78332cb0 `chain`, tiles linked by port matching, closed by hand and read as rank. No minimum: 2dd70a9a `$Jog`, an exact-three-legs hypothesis that derives nothing where a two-leg route exists. `Reach` and `GreedyWalk`: 2dd70a9a `$Toward`; 3e6067c3 `at`/`cand` (a route dictated by a color sequence); 5961cc34 `live`/`feeds`, 2b83f449 `arrive`, 025d127b `stuck`. `Ray`: 1b8318e3 `shortest`, 5545f144 `steps`, 13e47133 `$Sight`, 1190bc91 `nearest`, 332202d5 `nearest`, folds over straight-line step counts. `Rim.depth`: 13e47133 `$Peel`, 3ee1011a, 4290ef0e, 45a5af55, 516b51b7, 5751f35e, 639f5a19, 85c4e7cd. `CycleWalk`: 195c6913, 212895b5, 3ac3eb23, 97999447, 79cce52d. No edge relation: dce56571, 271d71e2, 0e671a1a. Transitive closures feeding `Order.before` or `Canon.equiv`: the `beats` closures of 3d31c5b3, 6a11f6da, 75b8110e, a68b268e, ea9794b1; 22425bda, 652646ff, 68bc2e87, 2d0172a1.

Spec. The interface has no signal beyond the surfacing site, which reads `pred` alone. Two boundary questions rest on the near-misses: `Dilate` is this operation with the edge fixed to `neighbor` over a cell domain, so under the generality rule the three `Dilate`-shaped sites (6df30ad6, 759f3fd3, 5792cb4d) would call this comp with a neighbor edge and `Dilate` would be a call pattern rather than a peer; and 5792cb4d and 78332cb0 read hop counts along a branch-free chain as `Order.rank` after closing it by hand, which this comp states with no closure, so the entry should say whether a branch-free edge relation is this operation. 2dd70a9a, if it regained a fewest-hop case, would call the comp with a leg as the Node, `leg_edge` as the edge, `leg_start` as the seed, an `ArgExtremes.low` fold over `dist` at the goal legs, and a `pred` trace with a tiebreak on top; that is the only site that would read `dist` directly, and it is hypothetical. No reimplementation of a lib primitive.

Callers: 7b0280bc `hops`.
