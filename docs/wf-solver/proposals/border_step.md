# `border_step` — the frame's border as a directed cycle

The next border cell after p, walking the frame's edge in sense s: p sits on edge d, and the step runs toward `turn(s, d)`. At a corner the cell sits on two edges, and only one of them steps back into the frame, so every border cell has one successor and the border closes into a cycle. Feeding it to `CycleWalk` walks the perimeter.

Solver-local form (30f42897):

```
.decl ring_succ(s: Sense, p: Position, q: Position)
ring_succ(S, P, Q) :-
    in(P, _), turn(S, D, D_step), dist(P, D, 0),   // a cell on edge D
    neighbor(P, D_step, Q), in(Q, _).              // the step along that edge
```

The frame carries the border, so the operation needs no cell set: `dist(P, D_step, K), K != 0` states that the step stays in the frame, in place of `in(Q, _)`. That makes an inline primitive, `border_step(p, s, q)`, the lib target. The alternative — a `BorderCycle<Key>` comp over a supplied cell set — would carry the border of a set that is not a frame.

Not: `Rim` (a set's boundary cells, with no order along it); `LexOrder` over border cells (an order with two ends, not a cycle); a walk that turns on a margin it carries (08573cc6's arms, 28e73c20's spiral, whose first lap traces the border before it insets); a ray cast along one edge (`Ray`); a step that crosses the border rather than running along it (49d1d64f, 305b1341).

Match: a rule joining `turn(S, D, D_step)` with `dist(P, D, 0)` and a `neighbor`/`jump` step toward `D_step`. Grep `turn(` in `programs/solvers/*.dl`, then read each site for the border-membership join. `Fit` and `Parse` comps are body code and hold sites too.

Survey: 2026-08-30 20:07

The survey read the whole corpus. Of 26 `turn(` sites in 21 files, two join `turn` with border membership and a step; a parser scan over on-edge membership plus a step, with and without the direction relation, added no further site. The other `CycleWalk` sites build cycles over row and column indices with `IndexCycle`, not over border cells.

Both parts of the interface hold at the second caller. ca8de6ea joins its own `ring_cell` on both ends of the step for what the frame already states, and its positions come from a 3×3 `ex_out` frame rather than the input grid — so the frame-intrinsic `dist(P, D_step, K), K != 0` form serves a frame the input never carries, which a `BorderCycle<Key>` over a supplied cell set would not do better. Both callers need `s` free in the relation: 30f42897 runs both senses because the sense is unobservable, and ca8de6ea ranges over both to derive its ring's sense before pinning it.

Callers:

- `programs/solvers/30f42897.dl` — `ring.succ`, feeding `CycleWalk<Sense, Position>` so the block repeats around the perimeter.
- `programs/solvers/ca8de6ea.dl` — `border_step` and `ring_succ` in its `Fit` comp, feeding `CycleWalk<Unit, Position>` to recover the ring's sense and each ring's shift.

Verdict: close; both callers keep the operation as plain rules. 2026-08-31.
