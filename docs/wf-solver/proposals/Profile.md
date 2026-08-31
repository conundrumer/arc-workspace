# `Profile<Key>` — per-line extremal cells of a set against a blocker set

On each line of a direction's axis, the cells of a keyed set with no blocker strictly further toward that direction — the set's silhouette when the blockers are the set itself, its exposed rim when they are a wider solid.

```
.comp Profile<Key> {
    // The cells profiled, per key.
    .decl cell(key: Key, p: Position)  // input

    // The cells that can hide a cell, per key; feed `cell` for the set's own
    // silhouette.
    .decl blocker(key: Key, p: Position)  // input

    // The profiled directions, per key.
    .decl dir(key: Key, d: Dir)  // input

    // A cell with a blocker strictly further toward d in its line.
    .decl hidden(key: Key, d: Dir, p: Position)
    hidden(Ky, D, P) :-
        cell(Ky, P), blocker(Ky, Q), dir(Ky, D),
        axis_of(D, A), same_line(A, P, Q),
        dist(P, D, K), dist(Q, D, K2), K2 < K.

    // The profile toward d: on each line, the cell lying furthest that way.
    .decl profile(key: Key, d: Dir, p: Position)
    profile(Ky, D, P) :- cell(Ky, P), dir(Ky, D), !hidden(Ky, D, P).
}
```

Not: `Bbox.edge_cell` (one readout per box side, not per line); `Ray` (marks casting, with distances and stops); `Rim` (the adjacency boundary, no per-line extremum); `ArgExtremes` (the generic extremum — this is its geometric per-line case, with the line and direction folded into the geometry rather than a record key).

Match: a defect rule joining two cells of one set through `same_line` on a direction's axis and comparing their `dist` toward that direction with a strict inequality, with a second rule negating the defect over the same set — grep `same_line`, then confirm the paired `dist`/`<` defect shape.

Survey: 2026-08-31 09:57

Result: over the 423 solvers, no site outside the surfacing solver holds the operation. The 45 `same_line` references and 24 parser-matched dist-comparison rules elsewhere state orders, spans, sidedness, walks, and per-object extremum ranks, with no per-line fold. One near-miss could be served at the same length: 505fff84's `Fit.side`, a per-row two-marker extremum that today reads the pair directly under a `Row` key. The other near-misses resolve to `Bbox.edge_cell`, `Extremes`, `Rim`, or `Ray` under the `Not:` line. The survey also found reimplementations of existing primitives, routed to `migrate` without a verdict: `Bbox.edge_min` at 13713586, 22a4bbc2, 1ae2feb7; `Rim.rim_dir` at 2b83f449.

Callers:
- 16b78196 — `face`/`beyond` (silhouette: blockers are the set itself), as plain body relations.

Recommendation: park. 2026-08-31 10:07. One caller and one equal-length near-miss do not clear the threshold. The operation looks general: it names one prior-level operation — the per-line extremum toward a direction — and takes its whole domain (the profiled set, the blocker set, the directions) as parameters, fixing no configuration beyond the frame.
