# `GreedyWalk<Key, Node>` — nearest-first self-avoiding walk

The walk a nearest-first rule traces over a costed edge relation: from a seed, each step takes the cheapest edge to a node the walk does not already hold, and the walk ends where every edge out leads to a node it holds. The held set is what the walk itself has grown, so the availability test sits inside the recursion; lib's `Take` carries it positively, keyed by the node the walk stands at. The pick's minimum also sits inside the recursion, which no aggregate or stratified negation states, and a subsumption clause is what settles it; subsumption is not program style, so the operation enters as a proposal comp:

```
.comp GreedyWalk<Key, Node> {
    .decl seed(key: Key, n: Node)                      // input
    .decl edge(key: Key, a: Node, b: Node, k: number)  // input

    .init state = Take<Key, Node, Node>
    state.start(Ky, N) :- seed(Ky, N).
    state.init_taken(Ky, N) :- seed(Ky, N).
    state.init_untaken(Ky, N) :- edge(Ky, _, N, _), seed(Ky, N0), N != N0.
    state.step(Ky, A, B) :- hop(Ky, A, B).
    state.take(Ky, A, B) :- hop(Ky, A, B).

    // The step taken: every edge to an untaken node competes, and the dearer
    // ones are subsumed away. A tie leaves both, and the walk forks.
    .decl pick(key: Key, a: Node, b: Node, k: number)
    pick(Ky, A, B, K) :- state.untaken(Ky, A, B), edge(Ky, A, B, K).
    pick(Ky, A, B, K) <= pick(Ky, A, _, K2) :- K2 < K.

    .decl hop(key: Key, a: Node, b: Node)
    hop(Ky, A, B) :- pick(Ky, A, B, _).
}
```

Every pick candidate of one head arrives in one fixpoint iteration — a head's `untaken` rows derive together from the hop that enters it, and `edge` is static — so the subsumption prunes the dear steps before the next iteration reads them.

The minimum does not reduce to ordinary positive recursion. The tried route: rank each node's static candidates with `Order` by cost, then pick the first untaken candidate by a prefix walk over `Order.next` carrying `taken`. It fails where two candidates of one head tie on cost and one is held: `next` is no chain under a tie, so the walk crosses the held one and reaches a farther candidate without ever checking its tied rival — 3490cc26 train 0 has exactly that tie, and the walk stole a hop. A strict total order would repair it, but none is principled outside a comp: linearizing ties by `ord` is the device lib fences inside `CoverForcing`.

Not: a walk whose edge availability is fixed before the walk starts, which plain positive recursion states (2dd70a9a's `toward_reach`, 03560426's `anchor` chain); reachability with no order (`Reach`); fewest-hop distance from a seed set (`MinHops`, closed); a walk of a stored step count along a supplied cycle (`CycleWalk`); a rank under a supplied order (`Order`); one-shot greedy selection with no walk state (`Preempt`, closed); an extremum over static candidates (`ArgExtremes`).

Match: a recursive rule that tests membership in a set the same recursion grows, keyed by a step index or by the walk's position. Grep `+ 1` and `S+1` over `programs/solvers/` for step-indexed recursion, `<=` at the head of a clause for subsumption, and relation names `visit`, `seen`, `held`, `unheld`, `used`, `unused` for a hand-rolled held set. Also any site that approximates the walk by unrolling a fixed number of steps into separate relations.

Survey: 2026-09-01 21:35

Result: no second caller. `+ 1` matches three files: two are prose in header comments, and the only code hits were inside this comp's original step-indexed form. Subsumption at a clause head occurs once corpus-wide, in this comp. Of the held-set names, `visit` and `unheld` occur only here; `held` in 28a6681f is the forward-derived complement of a lateral drain, and `taken` in 03560426 and 228f6490 names a claimed cell. Eighty-seven solvers hold a recursive relation group, and no rule in any group negates a relation of its own group; only 28a6681f's `free` joins a same-group relation under a disequality beside this comp's `unheld` rules. No recursive rule anywhere pairs a cost comparison with a test against a set the same recursion grows, and no site unrolls a walk into a step chain of three or more copies of one relation — the longest hand-unrolled walk is 2dd70a9a's two `leg_edge` atoms for a fixed three-leg path.

The near-misses sit on the far side of the `Not:` line for one reason: their edge set is complete before the walk runs, so plain positive recursion states them. They are 28a6681f's `free`/`solid` (a set the recursion shrinks, but stepped along a `LexOrder` with no cost), 2dd70a9a's `toward_reach`, 03560426's `anchor` chain, 234bbc79's `trail_dest`/`slide`, 72207abc's `grown`, 16b78196's `placement`/`seat_step`, 4522001f's `fit_box`, and 2b83f449's `arrive`. 0e671a1a stores its chain over marks as a parameters table, so the operation would replace data rather than a hand-written walk. 1190bc91, 332202d5, and 13e47133 pick a nearest source by `Extremes`/`ArgExtremes` over static candidates.

Callers: none.

Closed: 2026-09-02 15:16

The solver does without the operation. 3490cc26's candidates come one per direction from `Ray.stop`, so "no open candidate nearer than K" is a conjunction over the closed Dir class: a direction is clear when its line holds no block, holds one no nearer than K, or holds one the walk has taken. `opposite` joins the two clear looks of an axis and `perp` joins the two clear axes, so the conjunction is a positive fold through the class's own structure — monotone, stratified, and free of the subsumption timing argument. The route generalizes to any caller whose candidates are indexed by a closed structural class with at most one per member. The generic operation — arbitrary out-degree, no structural index on the candidates — still has no relational form short of a fenced device; a task that needs it reopens from here.
