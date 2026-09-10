# `PlacementRoom<Key, Cand, Piece>` — placement pruning by room for every piece

A candidate placement dies when some other piece has no candidate left that can stand beside it, and the survivors are the fixpoint of that kill. It is `PlacementPruning`'s first kill rule on its own: the pair kill, which also refutes a candidate when two other pieces have no conflict-free pair beside it, is dropped. The pair kill joins the candidate set with itself before it walks, so it costs a quadratic base where this one costs a linear one, and a caller whose candidate set runs to hundreds cannot pay it.

The conflicts arrive in two relations. `clash` holds whatever the key — the overlap that no assignment of the key can change; `conflict` is per key. A caller that keys the instance to enumerate an underdetermined choice states the physical conflict once instead of once per member.

```
.comp PlacementRoom<Key, Cand, Piece> {
    // The candidate placements of each piece.
    .decl cand(key: Key, c: Cand, o: Piece)  // input

    // Two candidates no joint placement holds together: `clash` whatever
    // the key, `conflict` under this key.
    .decl clash(c: Cand, c2: Cand)               // input
    .decl conflict(key: Key, c: Cand, c2: Cand)  // input

    // "Every candidate of the piece is blocked" would negate alive inside
    // the recursion, so it walks the piece's candidates in an arbitrary
    // stable ord order.
    .decl _min_after(key: Key, o: Piece, c: Cand, m: number)
    _min_after(K, O, C1, M) :-
        cand(K, C1, O),
        M = min ord(C3) : { cand(K, C3, O), ord(C3) > ord(C1) }.

    .decl _after(key: Key, o: Piece, c: Cand, c2: Cand)
    _after(K, O, C1, C2) :- _min_after(K, O, C1, M), cand(K, C2, O), ord(C2) = M.

    .decl _head(key: Key, o: Piece, c: Cand)
    _head(K, O, C) :- cand(K, C, O), !_after(K, O, _, C).

    .decl _tail(key: Key, o: Piece, c: Cand)
    _tail(K, O, C) :- cand(K, C, O), !_after(K, O, C, _).

    // Piece o2 blocked beside c: every candidate of o2 so far conflicts
    // with c or is dead.
    .decl _blocked(key: Key, c: Cand, o2: Piece, c2: Cand)
    _blocked(K, Cd, O2, C2) :-
        cand(K, Cd, O), _head(K, O2, C2), O2 != O,
        ( clash(Cd, C2) ; conflict(K, Cd, C2) ; dead(K, C2) ).
    _blocked(K, Cd, O2, C2) :-
        _blocked(K, Cd, O2, C1), _after(K, O2, C1, C2),
        ( clash(Cd, C2) ; conflict(K, Cd, C2) ; dead(K, C2) ).

    .decl dead(key: Key, c: Cand)
    dead(K, Cd) :- _blocked(K, Cd, O2, C2), _tail(K, O2, C2).

    .decl alive(key: Key, c: Cand, o: Piece)
    alive(K, Cd, O) :- cand(K, Cd, O), !dead(K, Cd).
}
```

`alive` over-approximates as `PlacementPruning.alive` does, and by more: a caller painting from the survivors fails on cells where leftover rivals disagree, never wrongly.

Not: `PlacementPruning` (the same kill plus the pair kill); `CoverForcing` (elimination from a cell whose rivals are spent, toward an exact cover of a known region); `SupportPruning` (refutation by the pieces a hold strands, over candidates derived by support from roots); `Preempt` (a priority order among candidates, with no piece to strand).

Match: a candidate/piece/conflict site that walks a piece's candidates in `ord` order to state "this piece has no candidate left", with no second walk nested in it. Grep `PlacementPruning` for callers that could drop the pair kill, and `ord(` over `programs/solvers/` for a hand-rolled chain walk over placements.

Survey: 2026-09-09 03:20

Result: no hand-written form of the operation stands anywhere in the corpus. `PlacementPruning` has four call sites, all lib calls.

Two of the three `PlacementPruning` callers need the pair kill, each failing differently without it. 184a9768 goes from 8 to 30 alive on train0 and its `out` becomes multi-valued: at `train0 output rows 7–8, cols 6–11` and `(17,10), (17,11)` the expected color is 8, and the room kill alone leaves 3, 4 and 8 at each of those cells. b7cb93ac holds on three pairs but goes from 25 to 57 alive on train2, where `TiebreakResolutions` then finds no injective assignment and `out` is empty.

Near-misses: 16b78196's `refuted` is the closest hand-written universal — hold a piece, and some other piece has nothing left — but its survivors come from a support-closed reach, with no feedback into the reach and so no fixpoint, which is `SupportPruning`. The `CoverForcing` packers (150deff5, 446ef5d2, 681b3aeb, b1fc8b8e, 4cd1b7b2, 1a244afd) eliminate from a cell whose rivals are spent over a known region. 42f14c03's `unfillable` reads "some hole has no piece that fits" with no conflict relation and no candidate to refute.

Spec: hold this beside `PlacementPruning` rather than weaken `PlacementPruning` to it — weakening breaks 184a9768 and b7cb93ac. The `clash`/`conflict` split rests on the surfacing solver alone: every other `PlacementPruning` caller keys on `Unit` and so has no per-key conflict to separate.

At neither caller does the weaker fixpoint change the output. `PlacementPruning` is strictly stronger and sound, so a valid joint placement survives it; on 5dbc8537 the room kill's output is already the expected grid, so `PlacementPruning` would give that same grid. What rules it out on 5dbc8537 is the runner's 5s CPU limit.

Callers:

- 5dbc8537 — two instances over `Occurrences` candidates for a hole-packing template: one unkeyed on overlap alone, one keyed by the eight reading orders that break the tie among congruent pieces.
- 477d2879 — `pruning` under `$Cover`, where each mark claims the parts of one color it touches. `alive` is identical under both comps on all four pairs, and every pair passes: the pair kill fires on nothing there.

Closed: 2026-09-09 20:13. Lib already holds the operation: `PlacementPruning` reaches the same fixpoint within budget once its pair kill runs over the room kill's survivors, so the weaker comp is not needed.
