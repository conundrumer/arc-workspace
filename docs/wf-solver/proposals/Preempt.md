# `Preempt<Key, Cand>` — greedy selection under an acyclic priority

The candidates a priority-ordered greedy keeps: a candidate is kept when every candidate that preempts it is out, and a kept candidate puts out the candidates it preempts. The caller supplies the preemption relation, so priority and conflict arrive as one acyclic edge set, and the fixpoint runs downward from the candidates nothing preempts.

```
.comp Preempt<Key, Cand> {
    .decl cand(key: Key, c: Cand)                // input
    .decl preempts(key: Key, c: Cand, c2: Cand)  // input

    // "every preemptor of c is out" is a universal inside the recursion —
    // kept and out are mutually recursive, so no negation across them
    // stratifies. The preemptors of c chain in an arbitrary stable ord order,
    // and the universal becomes a positive walk along that chain.
    .decl _next(key: Key, c: Cand, c2: Cand, c3: Cand)
    _next(K, C, C1, C2) :-
        preempts(K, C1, C), preempts(K, C2, C), ord(C1) < ord(C2),
        M = min ord(C3) : { preempts(K, C3, C), ord(C3) > ord(C1) }, ord(C2) = M.

    .decl _head(key: Key, c: Cand, c2: Cand)
    _head(K, C, C1) :- preempts(K, C1, C), !_next(K, C, _, C1).

    .decl _tail(key: Key, c: Cand, c2: Cand)
    _tail(K, C, C1) :- preempts(K, C1, C), !_next(K, C, C1, _).

    // Every preemptor from the first of the chain up to c2, all out.
    .decl _run_out(key: Key, c: Cand, c2: Cand)
    _run_out(K, C, C1) :- _head(K, C, C1), out(K, C1).
    _run_out(K, C, C2) :- _run_out(K, C, C1), _next(K, C, C1, C2), out(K, C2).

    .decl kept(key: Key, c: Cand)
    kept(K, C) :- cand(K, C), !preempts(K, _, C).
    kept(K, C) :- cand(K, C), _tail(K, C, C1), _run_out(K, C, C1).

    .decl out(key: Key, c: Cand)
    out(K, C) :- kept(K, C1), preempts(K, C1, C).
}
```

Not: a one-shot test against every higher-scoring rival, kept or not — plain negation states that, and it is a different claim; `CoverForcing` (elimination toward an exact cover, with no priority among pieces); `PlacementPruning` (refutation by joint-placement impossibility); `ArgExtremes` (one extremum, no conflict relation); `Order` (a rank, with nothing knocked out); a preemption relation with cycles, which has no downward fixpoint.

Match: a solver that derives a winner set from candidates plus a conflict relation ordered by a strict comparison on a size or score column, where a loser is knocked out by a *winner* rather than by any rival — the cascading reading. Also any hand-rolled `ord`-chain walk standing in for such a fixpoint (grep `ord(` over `programs/solvers/`), and any site that approximates the cascade by iterating a fixed number of levels.

Survey: 2026-08-31 14:58

Result: no second caller. `ord(` matches nine solvers — eight are `as(ord(P), Ident)` id minting inside a Fit comp, and one is a lexical hit on a relation named `cord` — so no hand-rolled ord-chain walk stands outside this proposal. Forty-two relations in thirty-six solvers derive a winner from a strict comparison between two rival bindings, and every one is a one-shot test against any rival or a `before` feed into `Order`/`Ordinal`. The only kept/out recursion in the corpus is this comp's; the other recursive groups are walks and floods. No solver approximates the cascade by iterating a fixed number of levels.

The near-misses sit on the far side of the `Not:` line for one reason: their preemption is transitive or per-cell, so a one-shot negation already states the claim. They are 14754a24's `dominated` (strict set containment, transitive); the per-cell overlay precedence of ea9794b1, 75b8110e, 3d31c5b3, a68b268e, 281123b4, 6a11f6da and cf98881b; 0f63c0b9's nearer ray; 305b1341's panel stack; 03560426's chain overwrite; and 28a6681f's stateful settling along `lex.next`, which orders by `LexOrder` rather than by a fixpoint over an acyclic edge set.

Two observations rest on the one call site, so they argue no change yet: `preempts`'s fields are `c` and `c2`, with the operation's direction only in the prose; and only `kept` is read.

Callers:

- 31adaf00 — `displaces(B, B2)` pairs a background square with a strictly smaller square it overlaps, and the `$Drawn` case paints the kept squares.

Closed: 2026-08-31 16:12 — the user ruled against the operation on the survey's evidence of one caller. The cascade claim has no relational form without the comp, so 31adaf00's `$Drawn` case went with it; that solver keeps `$Larger` alone.
