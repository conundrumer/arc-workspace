# `GapComponents<Key>` — connected components across a one-cell gap

The clusters of a keyed cell set when two cells join across at most one cell between them, in any of the eight directions: a `Components8` whose step is two unit steps composed, so a dotted or checkered outline, or a figure whose parts stand one cell apart, reads as one unit. Each cluster is labeled by an opaque id, as in `Components`.

```
.comp GapComponents<Key> : Components8<Key> {
    step(S) :-
        dir8_elem(D1), step_delta(D1, S1), dir8_elem(D2), step_delta(D2, S2),
        compose(S1, S2, S).
}
```

An equivalent statement is the ring form: the one-step ring around each set cell, two cells meeting when their rings share a cell, and `Canon` over the transitive closure of `meet`.

Not: `Components` and `Components8` (no gap); `Dilate` and `Rim.depth` (a distance, no closure); `Transitive` (the closure alone, over a caller's edge); `Reach` seeded across a gap through bg cells (the bg cells are nodes, so the gap is not bounded); a join of like-valued tiles across a tiling (33067df9, whose nearness is the tile arrangement's, not the grid's).

Match: a `Components` or `Components8` instance with a `step` fed by two `step_delta` atoms composed; a two-atom self-join of a one-step ring relation (`ring(A, R), ring(B, R)`) fed to `Canon.equiv` or closed transitively; a `Canon.equiv` or `Components.node` feed whose edge is `jump` or `neighbor` at distance two over the set; any closure over a "within two steps" or "at most one cell between" relation. Match with the parser.

Survey: 2026-09-10 02:35

Result: over 643 solvers, the parser matched a `step` head on a Components-family instance, self-joins of a ring relation built by `neighbor` under a direction enumerator that reach `equiv`, `node`, or `seed`, two-step rules (`neighbor` twice, `jump`, `jump_delta`, `step_delta` twice) feeding `equiv` or `node` or recursive, every recursive rule over `neighbor`/`jump`/`compose`/`uniform_delta`, every `Canon.equiv` from a geometric atom, and every `Reach` whose node set is not a plain bg flood. Two callers, both bridging exactly one cell under 8-adjacency, stating the same relation (Chebyshev distance at most 2, closed), so the composed-step and ring forms are the same operation. No site bridges a wider gap; the only cardinal two-step sites are near-misses, so a gap-width or 4-adjacency parameter rests on no caller. The composed step set holds the zero delta and the eight unit deltas, which `Components` absorbs (a self-loop, and steps the two-step deltas subsume), so the code form needs no filter. Near-misses: a two-cardinal-step probe with no closure (5b37cb25 `closed`); a line extended through one hidden cell, directed and cardinal, where the gap cell joins the set (89565ca0 `line`); cell pairs across one wall cell closed at region level with parity two, which separates sides (3bd292e8 `across`/`same_side`); a paint flood through doorways, where the bridged cells are nodes (3ad05f52 `flood`); adjacency with no gap (3aa6fb7a `piece`, 477d2879 `pruning.conflict`); same color on one line with no gap bound (5289ad53 `lines.equiv`); and 33067df9 `join`, already in `Not:`. Reimplementation: 36fdfd69 `mark_ring`/`meet`/`cluster.equiv` (lines 31–41).

Survey: 2026-09-10 03:05

Result: over the four solvers modified after the first survey (6ffe8f07, 7039b2d7, 72322fa7, 72a961c9), no caller and no reimplementation. Near-misses: a two-sided `neighbor` probe from a center cell in opposite directions, with no closure and the center itself a set cell (72322fa7 `template`); a touching group under plain `Components8` with no gap (72322fa7 `figure`). No site bridges a gap, so the interface gets no new signal.

Callers:

- 6ffbe589 `cluster` — ink cells cluster across at most one cell; the largest cluster is the figure to crop.
- 36fdfd69 `cluster` — marks cluster across at most one cell; each cluster's box takes the fill.
