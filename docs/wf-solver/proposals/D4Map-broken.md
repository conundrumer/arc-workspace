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

Callers: 0934a4d8 alone (`Determine.broken`, re-keyed onto tiles by `mismatchk`). Of 126 `apply` rules, only that one tests a value across the image and keeps the cell; of 16 `D4Map` instances, only that one reads `src`/`dst` back out. Near: verdict projections read as they are (be03b35f's `broken` is `mismatch` re-keyed by diag; 44f52bb0, 981571dc, 18419cfa, e729b7be, 11852cab, 2c181942, b7cb93ac, 4522001f, and the repair families b8825c91, 67b4a34d, 9ecd008a); a `dst` naturally per region (662c240a, 8e5a5113, f25ffba3); an image with both values and no inequality (a8610ef7, feeding `Unanimous`); glide and offset-mirror candidates through `compose` (0dfd9992, af22c60d, 981571dc, 0934a4d8 `ext_map`, 3979b1a8). No site wants the dst cell as witness: the two that copy a frame per region (8e5a5113 on the src side, be03b35f on both) address cells in coordinates that repeat across regions, so a frame-keyed witness would conflate them; 0934a4d8's regions are disjoint sub-blocks of one frame, which is what makes the region a function of the cell.

Interface: a separate readout, src cell only. Making it the base relation `conflict` projects would force a per-cell materialization at fifteen instances that consume only the verdict, where the existential exits at the first witness. Carrying the image cell serves no site.

Reimplementations: f25ffba3 `stamp_mismatch` and `tile_mismatch` (`D4Map.mismatch`/`map`, per example and per tile), 8ee62060 `Determine.mismatch` (`D4Map.mismatch`/`map` on block coordinates), 4522001f `pair_mismatch` (`D4Map<Unit, Color>.mismatch` over `c4_elem`). A shape lib does not hold, hand-written four times: a flip composed with an offset as a mirror candidate (0934a4d8 `ext_map`, af22c60d `band_map`, 981571dc `mirrored`, 3979b1a8 `cand` with `mismatch`) — neither `ShiftInvariance` (axis-aligned translations) nor `D4Map` (origin-fixing elements).

Recommendation: park. One caller, and the interface stands as written; the readout is worth keeping for the next region-partitioned symmetry task. 2026-08-30 10:41.

Survey: 2026-09-10 15:16 — the whole corpus.

## 1. Callers

1. **0934a4d8**, `Determine.broken` (`/Users/davidlu/code/arc-workspace/programs/solvers/0934a4d8.dl` lines 111–114). Over the mosaic's own symmetry (`inv.src` = `inv.dst` = clean mosaic cells per example), it keeps the src cell whose image under D holds a different clean color; `mismatchn` then attributes that cell to its tile at every candidate tile count, so the whole-frame conflict is partitioned by region.

No second caller. Negative evidence: the parser shape (positive `apply`, valued atoms at both ends, a `!=`) matched 13 rules in the corpus; only 0934a4d8's keeps the src cell with a value test at both ends. Of 33 `D4Map` instances (16 at the entry's last survey), the only rule bodies that read `src`/`dst` back are 0934a4d8's `broken` and the three `over` rules of the `D4Map.onto` sites (62593bfd, 67e490f4, 845d6e51), which test absence, not a value. The no-`apply` matcher found no mirror written through `dist`/`same_dist`; its value-disequality hits are all translation (`compose`) or line tests.

## 2. Near-misses

1. **21897d95** `Determine.broken` (L311): verdict per (example, C4), cell dropped; it also tests a neighbor color pair across the inverse turn, not one image value. Exclusion: the per-key verdict (`conflict`/`mismatch` themselves).
2. **3e980e27** `Determine.refuted` (L68–72): verdict per (marker color, D4), cell dropped. Exclusion: the per-key verdict.
3. **eb281b96** `Determine.across_moved` (L81): compares the image's across coordinate, no value. Exclusion: image position with no value test.
4. **0c786b71**, **3af2c5a8**, **47c1f68c**, **62c24649**, **67e8384a**, **833dafe3**, **8d5021e8** `mirror`; **00576224** `out` `$Mid`: the `!=` is on a tile distance that chooses whether to flip; `apply` places, tests nothing. Exclusion: image position with no value test.
5. **a8610ef7** `out` `$Direct` (L41–44): keeps the cell, one stored D, but tests presence of the image in the non-bg set on both branches. Exclusion: no value test between two existing cells (this is the absence reading `mismatch` uses, not `broken`'s conflict reading).
6. **62593bfd**, **67e490f4**, **845d6e51** `over`: `dst` read back, walked to `src` by the inverse, absence tested, verdict per key. Exclusion: the per-key verdict; and the operation is `D4Map.onto`'s, which has its own entry.
7. **5a719d11** `out`, `Determine.cand_out`: `apply` on the tile position finds the paired panel; membership at the pair, no inequality. Exclusion: image with no value test.
8. Verdict projections consumed as they are: **be03b35f** `broken` (mismatch re-keyed by diag; the anchored src coordinates repeat across quadrants, so a frame-keyed witness would conflate them), **47c1f68c** `tile_broken` (the anchor tile's pattern copied under each tile as `src`; `dst` naturally per tile), **8e5a5113** `broken`, `step_broken`, **f25ffba3** `tile_mismatch`, **8ee62060** `block_d4` (keyed by within-block offset, both sides re-decomposed), **44f52bb0** `split_broken`/`sym_broken`/`inv_broken`/`group_broken`, **44d8ac46** `sym_gap`, **662c240a**, **73ccf9c2**, **18419cfa**, **47996f11**, **981571dc**, **11852cab**, **e729b7be**, **4522001f**, **2c181942**, **b7cb93ac**, **4c5c2cf0**, **72ca375d**, **409aa875**, **6165ea8f**, **64efde09**, **3a25b0d8**. Exclusion: `conflict`/`mismatch`/`map` themselves.
9. Repair family **67b4a34d**, **903d1b4a**, **9ecd008a**, **b8825c91**, **f4081712** `out` `$Detect`, and **6aa20dc0** `out`: `compatible` then `apply` reads the image's color, never tests it. Exclusion: image with no value test.
10. Translation break tests through `compose`: **3979b1a8** `Determine.mismatch` (L127), **642d658d** `Determine.differ` (L104), **4e34c42c** `disagree` (L60). A shift is not a D4 element; the entry's earlier note on glide/offset-mirror candidates covers them.

## 3. Spec

No change. The re-survey finds the same one caller as the entry records, and the doubling of `D4Map` instances since then added no site that keeps the witness cell. The interface stands: a src-cell-only readout beside `conflict`. The one per-cell image test elsewhere (a8610ef7, near-miss 5) wants the absence reading with a single stored transform and consumes both branches, so a conflict-reading `broken` would not serve it; that is a caller-only observation, not a change signal.

One entry fix for the console: the `Match:` line is a list of lexical anchors, and the operation lives in rule structure, so it does not meet the lib-protocol spec. The shape that found the sites: a rule with a positive `apply(D, P, P2)`, valued atoms at both P and P2, a `!=` over their values, and P in the head; `match.py` under the scratch path is that matcher.

## 4. Reimplementations

Reimplementations: one site.

- `/Users/davidlu/code/arc-workspace/programs/solvers/3e980e27.dl` lines 68–72, `Determine.refuted`: hand-writes `D4Map.conflict`. With a key of (example, marker cell, marker color), `src` is the footprint's offsets `V`, and `dst` is the train output reframed to the marker (`displacement(P, Q, Q_rel)`); `refuted(M, D)` is then `conflict` projected to the marker color.

The entry's earlier reimplementation list (f25ffba3 `stamp_mismatch`/`tile_mismatch`, 8ee62060 `Determine.mismatch`, 4522001f `pair_mismatch`) is resolved: each of those files now instantiates `D4Map` at that site, so those lines can be struck.
