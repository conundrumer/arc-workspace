# `SupportPruning<Key, Cand, Piece>` — placement refutation by held-candidate reach

Candidates derive by support from anchored roots, and a candidate is refuted when holding it strands a piece: the support-closed reach regrown beside the hold never derives any candidate of that piece — the support-aware peer of `PlacementPruning`, whose kill rules test pairwise conflict and cannot see derivability.

Code form (generalized from the surfacing solver's plain relations):

```
.comp SupportPruning<Key, Cand, Piece> {
    // The candidate placements of each piece.
    .decl cand(key: Key, c: Cand, o: Piece)  // input

    // Two candidates no joint placement holds together. Read as given;
    // feed both directions.
    .decl conflict(key: Key, c: Cand, c2: Cand)  // input

    // c standing lets c2 derive — disjunctive over supporters.
    .decl support(key: Key, c: Cand, c2: Cand)  // input

    // The anchored candidates every assembly contains.
    .decl root(key: Key, c: Cand)  // input

    // The reach beside a held candidate: grown from the roots through
    // support, conflicting with neither a root nor the hold, the held
    // piece fixed at the hold.
    .decl beside(key: Key, held: Cand, c: Cand)
    beside(K, Cd, C) :- cand(K, Cd, _), root(K, C), !conflict(K, C, Cd).
    beside(K, Cd, C2) :-
        beside(K, Cd, C), support(K, C, C2),
        !_root_clash(K, C2), !conflict(K, C2, Cd),
        cand(K, Cd, O), cand(K, C2, O2), (O2 != O ; C2 = Cd).

    // Conflicts with some root — the guard is universal over roots.
    .decl _root_clash(key: Key, c: Cand)
    _root_clash(K, C) :- root(K, R), conflict(K, C, R).

    .decl _piece(key: Key, o: Piece)
    _piece(K, O) :- cand(K, _, O).

    .decl _reached(key: Key, held: Cand, o: Piece)
    _reached(K, Cd, O) :- beside(K, Cd, C), cand(K, C, O).

    // Holding c leaves some piece with no derivable candidate.
    .decl refuted(key: Key, c: Cand)
    refuted(K, Cd) :- cand(K, Cd, _), _piece(K, O), !_reached(K, Cd, O).

    .decl alive(key: Key, c: Cand, o: Piece)
    alive(K, Cd, O) :- cand(K, Cd, O), !refuted(K, Cd).
}
```

The reach is per-candidate and positive, so no negation sits inside the recursion. It over-approximates like `PlacementPruning.alive`: reach members are not checked against each other, only against the roots and the hold, so a caller painting from the survivors fails on cells where leftover rivals disagree — never wrongly. The two refutations are complementary: the pair-walk kills candidates whose rivals cannot pairwise coexist; this kills candidates whose hold strands a piece.

Not: `PlacementPruning` (free-standing candidates, pairwise kill walks, no support); `Reach` (cell connectivity — no candidates, conflicts, or holds); `CoverForcing` (a known target region, forced by elimination); a plain anchored growth recursion with no held-candidate refutation over it.

Match: a recursive relation whose leading columns carry one held candidate (piece + placement) unchanged through the recursion while the trailing columns range over derived placements, based at an anchor, each step negating an overlap/clash relation against the held columns; plus a rule that negates that reach over every piece to refute the held candidate. Grep: `clash\|conflict\|overlap` over paired (piece, shift) columns, then judge the surrounding recursion; a growth recursion alone (`placement`-style, seats composed onto an anchored base) is the `Not:` case unless a hold threads it.

Survey: 2026-08-31 12:03

Result: over the 423 solvers, no site outside the surfacing solver holds the operation. Candidate-level negated clash occurs in two other solvers, both cell-level. The held-thread recursion shape appears in 8 further solvers, each threading a key — a Choice tag, a line, an object id, a color — never a piece with its placement. The anchored-growth-over-placements family has four other members: two deterministic chains with one placement per piece and nothing to hold or refute (234bbc79, 03560426), and two `PlacementPruning` fills over free-standing `Occurrences` candidates with no support edge and no root (184a9768, b7cb93ac); the `CoverForcing` sites pack a known target region. The survey also caught a spec defect: the step rule's root guard was existential, admitting a candidate that clears some root while conflicting with another; the code form now guards through `_root_clash`, and no known assignment is multi-root.

Callers:

- 16b78196 — `clash`/`beside`/`refuted` over `placement`/`seat_step`, as plain program relations.

Verdict: park. 2026-08-31 12:09. One caller does not clear the threshold. The operation looks general: it names one prior-level operation — refuting a placement by the pieces its hold strands — and takes its whole domain (the candidates, conflicts, supports, and roots) as parameters, fixing no configuration.
