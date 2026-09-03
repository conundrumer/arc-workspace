# `MinHops<Key, Node>` — fewest-hop distance over a supplied edge relation

Breadth-first search as a relation: the fewest-hop distance from a seed set over a caller-supplied edge relation, per key, together with the edges a fewest-hop walk uses. `pred` lets a consumer trace a fewest-hop walk backward with no hop counting of its own. Not: reachability with no distance (`Reach`); erosion depth from a set's own rim (`Rim.depth`, which is this over grid adjacency); a rank under a supplied transitive order (`Order.rank`); a walk of a stored step count along a cycle (`CycleWalk`); weighted distance. Lib target: body comp beside `Reach`.

```
.comp MinHops<Key, Node> {
    .decl edge(key: Key, a: Node, b: Node)  // input
    .decl seed(key: Key, n: Node)  // input

    // Hops from the nearest seed; subsumption keeps the minimum per node.
    .decl dist(key: Key, n: Node, k: number)

    // a is a fewest-hop predecessor of b — an edge some fewest-hop walk uses.
    // Tied walks all appear, so a consumer tracing it backward gets their
    // union; a single walk needs a tiebreak on top.
    .decl pred(key: Key, b: Node, a: Node)
}
```

Match: `<=`, `K + 1`, `depth(`, `Reach`, `Order`, `CycleWalk`.

Callers: 2dd70a9a alone — the `MinHops` comp, the `$Fewest` case of `on_path`. `+ 1` and subsumption occur nowhere else in the corpus, and of 72 `Extremes`/`ArgExtremes` instances only this one scores hop counts. Near: 13e47133 (`$Peel` is `Rim.depth`, `$Sight` an extremum over a `Ray` step index); 2b83f449, 195c6913, 212895b5, 3ac3eb23, 97999447, 79cce52d (walks over self-built graphs, taking no minimum, or advancing a stored index along a cycle); 1b8318e3, dce56571, 271d71e2 (extremum over a ray length, a tally, or grid `dist`); 0e671a1a (a fixed leg shape from Consts data); the `beats` closures of 3d31c5b3, 6a11f6da, 75b8110e, a68b268e, ea9794b1 (transitive orders feeding `Order`).

Interface: unchanged. `pred` is the readback — the caller traces it in two rules with no arithmetic, and the fewest-hop set is a DAG, so emitting whole paths is unbounded in the node count. A `goal` input would absorb the caller's `ArgExtremes`, but it would block the `dist`-only reading and a goal set is caller data. `Rim.depth` is this comp over grid adjacency, rule for rule; a rewrite would materialize four to eight edges per cell at ten sites and pay for a `pred` no site reads, so `Rim` stays and `lib.dl` should record the correspondence. No site reads `pred` without `dist`; if a `dist`-only site appears, `pred` moves into a derived subcomponent.

Reimplementations: 13e47133 `sray.mark` hand-writes `Rim.rim_dir` beside `rim = Rim8<Unit>`. 22a4bbc2 `obj_dist`, 1ae2feb7 `won`, and 25d487eb `margins` hand-write `Bbox.edge_min`. 13713586 `near` has that shape but minimizes across every surviving wall direction, so `Bbox` covers it only while one survives.

Verdict: close; 2dd70a9a drops its `$Fewest` case, whose fewest-turns claim has no relational form, and keeps a greedy walk in its place. 2026-08-30.
