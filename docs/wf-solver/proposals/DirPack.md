# `DirPack<Key>` — a Position packed from per-Dir scalars

The inverse read of `dist`, keyed: a relation holding one scalar per Dir packs into one Position, each axis's pair through `axis_delta` and the two axes perp-glued. Not: `axis_delta` itself (one axis, scalars in hand); `Bbox.margin` (this pack applied to a cell set's own edge minima); `edge_delta` (one dir, zero elsewhere); a `compose` glue of Positions already packed.

Code form:

```
.comp DirPack<Key> {
    .decl edge(key: Key, d: Dir, k: number)  // input

    .decl axis_pos(key: Key, a: Axis, p: Position)
    axis_pos(Key, A, P) :-
        axis_of(D, A), opposite(D, O),
        edge(Key, D, K1), edge(Key, O, K2),
        axis_delta(D, K1, K2, P).

    .decl pos(key: Key, p: Position)
    pos(Key, P) :-
        perp(A1, A2), axis_pos(Key, A1, P1), axis_pos(Key, A2, P2),
        compose(P1, P2, P).
}
```

Match: a rule holding `axis_of(D, A), opposite(D, O)`, two readouts of one scalar relation at `D` and `O`, and `axis_delta`, whose per-axis outputs a second rule glues with `perp` and `compose`. A site may write the pack without `axis_delta` — as a Position record or as two `edge_delta` composes. Grep: `axis_delta`, then judge the surrounding pair of rules.

Survey: 2026-08-31 07:36

Result: 4 sites across 3 solvers pack a per-Dir scalar relation into a Position; no others corpus-wide. The opposite-pair readout shape appears in 27 further files only as two-sided existence or ordering tests, and the perp-glue shape in 15 further files only over Positions already packed — neither produces a Position from per-Dir scalars. 19bb5feb also reads the per-axis half on its own, crossing axis halves of different keys, so `axis_pos` stays public. e1baa8a4 holds its scalar inline, so its call adds one `edge` rule. 2d0172a1's `pad` packs an Inset where the other sites pack frame cells; `Inset` aliases `Position`, so one column serves both.

Callers:

- 2d0172a1 (`pad_axis`/`pad`; `fig_axis`/`fig_box`)
- 19bb5feb (`mark_axis_pos`, with `axis_pos` also read alone)
- e1baa8a4 (`axis_band`)

Recommendation: park. 2026-08-31 07:45. Three callers sit under the threshold. The operation looks general: the inverse read of `dist`, taking its scalar relation as the domain and fixing no configuration.
