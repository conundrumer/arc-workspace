# `Bounce<Key>` — a diagonal heading reflected off the sides that block it

The heading a diagonal beam leaves a cell with: each component of the heading whose side is blocked inverts, and the two components recombine into the outgoing heading. A beam that grazes a wall on one axis turns a quarter; one wedged into a corner turns back on itself; one in the open keeps its heading. The caller says which sides block, so the blocker can be a color, an object, or the rim of a region.

```
.comp Bounce<Key> {
    // The cells a beam may stand at, per key.
    .decl cell(key: Key, p: Position)  // input

    // A beam at p is blocked toward d, per key.
    .decl side(key: Key, p: Position, d: Dir)  // input

    // One outgoing component of a heading, inverted where its side blocks.
    .decl leave_dir(key: Key, p: Position, d: DiagDir, d_out: Dir)
    leave_dir(K, P, D, D_out) :-
        cell(K, P), diag_dirs(D, _, D_cmp, _),
        ( side(K, P, D_cmp), opposite(D_cmp, D_out)
        ; !side(K, P, D_cmp), D_out = D_cmp
        ).

    // The heading the beam leaves p with, its two components recombined.
    .decl bounce(key: Key, p: Position, d: DiagDir, d_out: DiagDir)
    bounce(K, P, D, D_out) :-
        leave_dir(K, P, D, D1), leave_dir(K, P, D, D2),
        diag_dirs(D_out, _, D1, D2).
}
```

Not: the beam's walk (the caller steps it and decides what ends it); a straight cast (`Ray`); a run that halts at a blocker (`Slide`); a D4 reflection of content (`apply`, `flip_of`); a cardinal heading, which reverses under `opposite` alone.

Match: a rule whose head takes a `DiagDir` built by `diag_dirs(D_out, _, D1, D2)` from two cardinal readouts of another `DiagDir`, or a rule that applies `opposite` to a component `diag_dirs` reads off a heading. Candidate files: `grep -l diag_dirs programs/solvers/*.dl`.

Spec question: does a caller want to hand the comp a blocker cell set and have it probe the neighbors itself, in place of supplying the blocked sides?

Survey: 2026-09-02 19:49

Callers:

- `142ca369` — `leave_dir` and `bounce`, the same construction, over a `side_wall` that also carries the wall's color into the ray's ink.
- `508bd3b6` — the surfacing solver.
- `7e2bad24` — `leave_dir` and `bounce`, the same construction, as its $Contact case, over sides blocked by a reflective color; a transparent color the beam paints through is not a side.

Near-misses: `a3df8b1e` and `e179c5f4` each reverse a single cardinal component with `opposite` alone, with no second component to recombine. `2546ccf6` reflects content across the grid's cut lines with `flip_of` and `apply`, and composes two of those at a corner.

The spec question is settled: both callers derive the blocked sides themselves, and neither derivation is available from a blocker cell set. 508bd3b6's `$Side` counts only a wall that covers a whole grid edge, and 142ca369 reads the blocking cell's color as the payload its ray carries on.

Survey: 2026-09-10 06:33

Delta over the solvers since the survey above. Callers: none new. Near-misses: `69889d6e`'s `walk` climbs a corner by toggling between the corner's two stored directions when the cell ahead is blocked, with no component inverted and no recombination; `73c3b0d8`'s `splash_dir` reverses one fixed cardinal with `opposite` alone. No new evidence on the spec question.
