# `D4Map.broken` — the cell where a transform breaks

A per-cell readout on `D4Map`: the src cell whose image under `d` holds a different dst value, with the cell kept — `conflict` is this projected to the key. A solver that partitions one frame's symmetry by region (tiles, objects) keys `src` and `dst` by the frame and re-keys the witness itself, in place of pushing the region into the key and copying the frame's `dst` under every region. Not: `conflict` or `mismatch` themselves (the per-key verdict); a per-region `D4Map` whose `dst` is naturally per region; a cell's image position with no value test (`apply`).

```
    // The src cell whose image under d holds a different dst value — the
    // witness `conflict` projects away.
    .decl broken(key: Key, p: Position, d: D4)
    broken(K, P, D) :- src(K, P, V), d4_elem(D), apply(D, P, P2), dst(K, P2, V2), V2 != V.

    conflict(K, D) :- broken(K, _, D).
```

Match: `apply(`, `!=`, `D4Map`, `conflict(`, `d4_elem`.

Proposed: 2026-08-30 10:13.

Callers: 0934a4d8 alone (`Fit.broken`, re-keyed onto tiles by `mismatchk`). Of 126 `apply` rules, only that one tests a value across the image and keeps the cell; of 16 `D4Map` instances, only that one reads `src`/`dst` back out. Near: verdict projections read as they are (be03b35f's `broken` is `mismatch` re-keyed by diag; 44f52bb0, 981571dc, 18419cfa, e729b7be, 11852cab, 2c181942, b7cb93ac, 4522001f, and the repair families b8825c91, 67b4a34d, 9ecd008a); a `dst` naturally per region (662c240a, 8e5a5113, f25ffba3); an image with both values and no inequality (a8610ef7, feeding `Unanimous`); glide and offset-mirror candidates through `compose` (0dfd9992, af22c60d, 981571dc, 0934a4d8 `ext_map`, 3979b1a8). No site wants the dst cell as witness: the two that copy a frame per region (8e5a5113 on the src side, be03b35f on both) address cells in coordinates that repeat across regions, so a frame-keyed witness would conflate them; 0934a4d8's regions are disjoint sub-blocks of one frame, which is what makes the region a function of the cell.

Interface: a separate readout, src cell only. Making it the base relation `conflict` projects would force a per-cell materialization at fifteen instances that consume only the verdict, where the existential exits at the first witness. Carrying the image cell serves no site.

Reimplementations: f25ffba3 `stamp_mismatch` and `tile_mismatch` (`D4Map.mismatch`/`map`, per example and per tile), 8ee62060 `Fit.mismatch` (`D4Map.mismatch`/`map` on block coordinates), 4522001f `pair_mismatch` (`D4Map<Unit, Color>.mismatch` over `c4_elem`). A shape lib does not hold, hand-written four times: a flip composed with an offset as a mirror candidate (0934a4d8 `ext_map`, af22c60d `band_map`, 981571dc `mirrored`, 3979b1a8 `cand` with `mismatch`) — neither `ShiftInvariance` (axis-aligned translations) nor `D4Map` (origin-fixing elements).

Recommendation: park. One caller, and the interface stands as written; the readout is worth keeping for the next region-partitioned symmetry task. 2026-08-30 10:41.
