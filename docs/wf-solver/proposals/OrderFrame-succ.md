# `OrderFrame.succ` — an axis order closed into a cycle

The cyclic successor over members ordered along an axis: the member that directly follows m toward edge d, with the d-most member wrapping to the member farthest from d. Known sites build it in three steps: `OrderFrame.pos` read through `dist` from one edge into a dense index, `IndexCycle.succ` over the indices, and a join from indices back to members. Not: `Order.next` (caller-supplied order, no wrap); `IndexCycle` alone (dense numbers, no members); `border_step` (a spatial cycle over frame cells); `CycleWalk` (consumes a cycle's edges, does not build them).

Code form, as written at the introducing site (inside its `Parse` comp):

```
    // Place in the row, counted from the end the colors travel from.
    .decl idx(key: Key, l: Position, k: number)
    idx(K, L, N) :-
        row.pos(K, L, P_pos),
        dir(K, D), opposite(D, O),
        dist(P_pos, O, N).

    .init cyc = IndexCycle<Key>
    cyc.idx(K, N) :- idx(K, _, N).

    // The bar one step ahead, wrapping at the end of the row.
    .decl next_bar(key: Key, l: Position, l2: Position)
    next_bar(K, L, L2) :- idx(K, L, N), cyc.succ(K, N, N2), idx(K, L2, N2).
```

Match: `IndexCycle` fed from a `dist` readout of `OrderFrame.pos`, with or without the join back to members; grep `IndexCycle`, then check what feeds its `idx`. Also: a `last`→`first` wrap rule beside `Order.next`.

Survey: 2026-09-03 21:00.

Callers: 2601afb7 (`idx`/`cyc`/`next_bar`, the introducing site; both cases consume only the member pair); 195c6913 (`pattern`/`cycle` — the index half, but its index only ever names the next swatch's color, so a member successor replaces both relations); 72207abc (`seed_next`: `Order.next` plus a `last`→`first` wrap rule over ink cells on one row — the same operation built on `Order`; `OrderFrame` applies to its seeds without change).

Near: `IndexCycle` over grid-line indices where the index flows on as a count (6d1d5c90, 25ff71a9, 79cce52d, 310f3251); `IndexCycle` over stored parameter domains with no spatial order to close (3ac3eb23, 97999447, 212895b5); spatial border cycles, which are `border_step` (30f42897, ca8de6ea); `Order.next` with terminal ends (03560426, 3e6067c3, 4acc7107, 136b0064); a color cycle read off adjacency, not axis rank (1e97544e); tile succession by `neighbor` with no wrap (2ccd9fef, 351d6448); `OrderFrame.pos` through `dist` into an `ArgExtremes` score, not a cycle (234bbc79).

Spec: the successor is member-typed, with no index exposed — no call site consumes the index for anything but naming a member, so a dense index readout would be an unjustified second representation of the order. The direction goes in a column, `succ(key, d, m, m2)`, matching `nearer`'s shape and keeping the comp's no-privileged-end character. Two of the three sites seed a walk at the order's end, so a companion `end(key, d, m)` readout (the member nearest edge d; the far end reads at `opposite(d)`) belongs beside the successor.
