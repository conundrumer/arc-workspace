# `meet` — a position from one position's along component and another's across

The position that takes p's component along axis a and q's component across it. When p and q share a frame, that is where p's line perpendicular to a meets q's line along it: an L-path's elbow, a corner of the axis-aligned rectangle a cell pair spans, a frame built as a cross product of line sets. Two callers read p and q from different frames and land the result in a third, so the component selection is the definition and the line crossing is its shared-frame reading.

```
.decl meet(a: Axis, p: Position, q: Position, r: Position) inline
meet(A, P, Q, R) :-
    split(P, A, Along, _), split(Q, A, _, Across), compose(Along, Across, R).
```

Not: `compose` of two full positions (element-wise sum, not selection); a `compose` whose other operand arrives already axis-only, from a frame's `pos` or a stored line (one split, nothing selected from a second position); a perp-glue of one position's own two components; two `split`s that share a component to compare lines (`same_line` and its variations); a `split` whose along or across component keys a line.

Match: two `split` atoms sharing an axis variable, one binding the along component and wildcarding the across, the other the reverse, with the two bound components fed to `compose`.

Survey: 2026-09-08 16:27
Survey: 2026-09-08 22:59 — scope: the solvers whose file time is at or after the line above. It added no caller: of the 56 solvers in scope, the strict signature matched one rule, the caller 29700607, and the loose tier added none. Its near-misses fall in groups the `Not:` line already excludes: a crossing of two line keys (247ef758 `cross`), a perp-glue of axis-only operands (0dfd9992 `lat0`), and two splits sharing a component to compare lines (4ff4c9da `aligned`, 291dc1e1 `overlap`).
Survey: 2026-09-08 23:09 — same scope rule. It added no caller: of the five solvers in scope, no rule matches the signature at either tier, and none writes a cell through `keep_axis`, `axis_near`, `axis_far`, two `dist` atoms, or a `DirPack`. Its near-misses fall in groups the `Not:` line already excludes: a perp glue of two operands that arrive axis-only (20981f0e `place`), a `split` whose component keys a line (5545f144 `line_color.item`, 20981f0e's tiling `divider`), and a crossing of two line keys that constructs no position (57edb29d `design`). No reimplementations.
Survey: 2026-09-09 02:35 — same scope rule. Of the 27 solvers in scope, the strict signature matched two rules: 581f7754 `shift`, already a caller, and 5b526a93 `site`, added below. The loose tier added none, and no rule in scope writes a cell through `keep_axis`/`keep_dir`/`axis_near`/`axis_far`, two `dist` atoms, or `axis_pos`. Its near-misses fall in groups the `Not:` line already excludes: a `split` whose component keys a line (5a719d11 `Parse.line_color.item`, 5a5a2103 `tile_line`, 5b692c0f `axis_pick.item` and `axis_cell`, 5833af48 `band_color.item`, 5ad4f10b `run_color.item`), a Position packed from one object's four edge ranks (58f5dbd5 `tile.pos`, 19bb5feb `place.pos`), and `compose` of two full positions (57aa92db, 4c5c2cf0, 4938f0c2, 409aa875, 56dc2b01, 5af49b42, 5b526a93 `covered`). No reimplementations. 19bb5feb's listed `rank_cell` site is absent from the working tree, which replaces it with a `Frame2D` over `place.pos`.

The strict signature matches exactly seven rules corpus-wide; a loose tier (the same flow without the wildcard and distinct-position conditions) adds nothing, and no site writes the cell through `keep_axis`/`axis_near`/`axis_far` or two `dist` atoms. Two callers leave `a` free under `axis_elem` to take both mixed corners of a pair, and one consumes the result under negation, which the positive `inline` form supports — the interface needs no change. Near-misses, each excluded by a `Not:` clause: crossings of two line keys (0a1d4ef5 `hole`, 1be83260 `palette`); one position split and reglued through a per-component map (1190e5a7 `out`, 458e3a53 `out`); two splits sharing a component to compare or key lines (137f0df0, 22eb0ac0, bdad9b1f, ca8f78db, 4ff4c9da, 12997ef3, eb281b96); a `compose` whose other operand is already axis-only (1a07d186, 234bbc79, 25c199f5, 25ff71a9, 2601afb7, 6d1d5c90, 7e4d4f7c); perp-glues of one position's own components (ten rules, e.g. 0dfd9992 `dom`, e633a9e5 `tile`).

Callers:

- 29700607 — `elbow`: the wire's turn, the marker's place along the head axis with the header's across it.
- 0e671a1a — `Parse.elbow`: the turn of a leg between an ordered mark pair.
- 1478ab18 — `box_corner`: the two other corners of the box a diagonal mark pair spans, axis free.
- af902bf9 — `open_pair`: a mixed corner of two markers in opposite quadrants, tested under negation, axis free.
- 3cd86f4f — `frame`: the sheared frame as the cross product of the image's slide-lines and across-lines.
- 15660dd6 — `out_pos`: along component from the tiling frame, across from the panel frame — cross-frame.
- 38007db0 — `out`: along component from the grid, across from a block's own box frame — cross-frame.
- 581f7754 — `shift` (`:48`): the marker's landing on the anchor's line — the marker's along component on the anchor's edge axis, the anchor's across component.
- 5b526a93 — `site`: the crossing of two hollow squares' placements, one box margin's along component met with another's across it, axis free.
- 19bb5feb — `rank_cell`: the same set via `place.axis_pos` twice into `compose`; `place.pos` twice with `meet` states it.
