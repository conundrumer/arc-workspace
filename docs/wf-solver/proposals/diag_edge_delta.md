# `diag_edge_delta` — edge delta at a corner with two amounts

Two `edge_delta`s at the two edges of a corner. Not: `edge_delta` at a DiagDir (one amount at both edges); `jump` chains at a corner; `diag_dist`.

Match: `edge_delta`, `diag_dirs`, `jump_delta.*jump(`.

Callers: 8618d23e alone. 1e81d6f9 was `edge_delta` at a DiagDir (fixed). Near: 4522001f, 22208ba4 (diagonal shifts); the opposite-pair form at five sites, now `axis_delta`.

Survey: 2026-09-11 21:04 — every solver.

Callers:
8618d23e `grow_delta` — composes two `edge_inset`s at the two edges of a corner, one growth extent along the corner's axis and one across, giving the offset each half of the grid moves by.

No second caller. Across every solver, `edge_inset` (and its former name `edge_delta`) appears at 10 lines in 9 solvers; only 8618d23e holds two of them in one rule. A parser matcher over the whole corpus, for a rule with two offset constructors (`edge_inset`, `edge_outset`, `jump_offset`, `step_offset`, `jump`, `neighbor`) bound to two different Dir variables, matched 42 rules; the rest are either unit steps or translations, covered under near-misses. `diag_dirs` appears in 54 solvers, and no solver outside 8618d23e joins it to a two-amount margin construction. `DirPack`, the other route to a Box from per-Dir amounts, stands at 8 instances (e1baa8a4, 33067df9, 58f5dbd5, 19bb5feb, 2697da3f, 3a301edc, 2d0172a1 twice); every one feeds all four edges, not a corner's two.

Near-misses:
4522001f `sq_jump`, 22208ba4 `moved_cell`, 762cd429 `source`, 5207a7b5 `slant` — each builds a two-amount displacement at a corner, `4522001f` and `5207a7b5` by composing offsets and `22208ba4` and `762cd429` by a two-step `jump` chain. The `Not:` line rules all four out: these are translations toward a corner, not margins at its two edges.
1e81d6f9 `target_anchor` — `edge_inset` at a DiagDir, which is one amount at both edges of the corner. The `Not:` line names that form.
8abad3cf `edge_off` — composes two `edge_inset`s, but both at one Dir: a square's side and a gap summed along one edge. Two amounts, one edge, no corner.
2546ccf6 `gap`, 3aa6fb7a `mark`, 5ad4f10b `figure`, 71e489b6 `quad`, 7666fa5d `step`, 7e0986d6 `within`, 54dc2872 `bend`, 465b7d93 `corner` — a class that steps to both of a corner's cardinal neighbors. The amounts are unit and the cells stay separate, so no Box with two margins is built.
3cd86f4f `shear`, 4be741c5 (its strip-cell rule), 652646ff (its tile rule), 78332cb0 (its tile rule) — two amounts at two edges, but the opposite pair, which `axis_inset` already holds.
2697da3f `arm_margin`, 3a301edc `ring_box` — per-edge margins assembled over all four Dirs through `DirPack`, not the corner's two.
8cb8642d `arm`, 212895b5 `place`, 1478ab18 (its corner-side rule) — read two axis-tagged amounts at a corner out of a position via `diag_dist` or `dist_pair`. The `Not:` line names `diag_dist`; these are the inverse read, not the construction.

Spec:
No change to the operation's definition. Two observations about the entry's fields stand on the sites above.

The `Match:` line names `edge_delta`, `jump_delta`, and `axis_delta`. The corpus renamed those to `edge_inset`, `jump_offset`, and `axis_inset`, so the line matches nothing lexically as written. I searched both spellings; the line needs restating in the current names, and the shape half of it needs stating in prose, because a rule that builds a corner margin from two `edge_inset`s has no single lexical anchor.

The `Not:` line draws its boundary between margins and translations, and the near-misses show what sits on the far side of it: four solvers (4522001f, 22208ba4, 762cd429, 5207a7b5) build a two-amount displacement toward a corner, against this operation's one caller. That is a separate operation, and lib already splits the two readings at the cardinal level (`edge_inset` against `jump_offset`), so the corner forms split the same way. Merging them would undo that split. It belongs in its own entry, not in a widening of this one.

Argument shape is caller-only evidence and no change: 8618d23e supplies its two amounts axis-tagged, as `growth(A, K1, K2, Gr)`, so a promoted primitive would take `(diag, a, k1, k2, b)`, parallel to `diag_dist`'s readout. The near-miss sites 4522001f, 22208ba4, and 5207a7b5 also carry axis-tagged pairs, but they are translations, so they are no evidence for this operation's signature.

Reimplementations:
2546ccf6 `reflect` — its DiagDir rule composes the flip across one axis with the flip across the other. That composition is the half turn, which lib gives directly as `apply(D4_HT, P, Q)`.

The matcher script ran over `dl.corpus.each_solver()` for all 749 solvers and printed 42 hits; the grep half of the search covered `edge_inset`, `edge_delta`, `axis_inset`, `uniform_inset`, `edge_outset`, `axis_outset`, `jump_offset`, `jump_delta`, `diag_dirs`, `dir_of`, and `DirPack`.
