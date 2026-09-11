# `BarChart<Key, T>` — a keyed score drawn as bars in a frame of its own

The chart of a per-member score, per key: one row per member, counted from a rank edge in ascending score, each row's bar as many cells long as the member's score, growing from a bar edge; the frame is as many rows as members and as long as the highest score. A solver that renders "how many of each" as a bar chart, a histogram, or a sorted stack of bars reads the frame and the member at each cell from one instance, in place of composing a rank, a member count, a score maximum, a `Frame2D`, and a paint rule that compares the cell's distance to the score. A descending chart is the same chart from the opposite rank edge.

Code form:

```
.comp BarChart<Key, T> {
    // Each member's score, per key — the length of its bar.
    .decl score(key: Key, t: T, s: number)  // input

    // The edge the rows are counted from, and the edge the bars grow from.
    .decl rank_dir(d: Dir)  // input
    .decl bar_dir(d: Dir)   // input

    // Rows ascend by score: the lowest score lies against the rank edge.
    // A member's rank is the count of members with a smaller score.
    .init order = Order<Key, T>
    order.elem(Ky, T) :- score(Ky, T, _).
    order.before(Ky, T, T2) :- score(Ky, T, S), score(Ky, T2, S2), S < S2.

    .init members = Tally<Key, T>
    members.item(Ky, T) :- score(Ky, T, _).

    .init widest = Extremes<Key>
    widest.cand(Ky, S) :- score(Ky, _, S).

    // The frame: one row per member, as long as the highest score.
    .init frame = Frame2D<Key>
    frame.extent(Ky, A, N) :- rank_dir(D), axis_of(D, A), members.tally(Ky, N).
    frame.extent(Ky, A, N) :- bar_dir(D), axis_of(D, A), widest.high(Ky, N).

    .decl cell(key: Key, p: Position)
    cell(Ky, P) :- frame.cell(Ky, P).

    // The member whose row p lies in.
    .decl row(key: Key, p: Position, t: T)
    row(Ky, P, T) :- cell(Ky, P), rank_dir(D), dist(P, D, R), order.rank(Ky, T, R).

    // p on t's bar: nearer the bar edge than t's score.
    .decl bar(key: Key, p: Position, t: T)
    bar(Ky, P, T) :- row(Ky, P, T), score(Ky, T, S), bar_dir(D), dist(P, D, K), K < S.
}
```

Members sharing a score share a row and leave the rows past it without a member, so a tie makes `row` and `bar` multi-valued and the chart partial. The seated form (89565ca0) repairs that with a tiebreak over the rows at or past each member's rank, which reads `order.rank` as the member count it is.

Not: the rank alone (`ScoreOrder`, `Ordinal`, `Order`); the frame alone (`Frame2D`); a per-line count drawn in place on the input frame, where the rows are the input's own lines and no member is ranked; a bar whose length is read from the input as a run rather than counted; a stack of members with no bar (`OrderFrame`); a chart whose rows follow an order other than the score.

Match: a `Frame2D` instance whose two extents are a member count (`Tally`) and a score maximum (`Extremes.high`, or the rank-0 score of a descending rank), with a paint rule that reads a rank off `dist` toward one edge, reaches the member through its score, and compares `dist` toward the perpendicular edge against that score (`K < N`). Also the seated form, where a tiebreak assigns members to rows before the paint rule. Grep: `Frame2D<` in a file that also holds `Extremes<` or `rank_desc(.*, 0)` and `Ordinal<` or `Order<`, then the `dist(P, D, K), K < N` shape read with the parser (`tests/test_ast_match.py`).

Survey: 2026-09-10 07:45

Scope: all 700 solvers in `programs/solvers/`. The grep signature hit 8 files; a parser match of the paint-rule shape (a `dist` distance compared `<` against a count, with a second `dist` on the same cell feeding a rank lookup) hit exactly 3 rules, all in the callers below. No `// family:` sibling set is involved.

Callers:

- 81c0276b — `chart`, `order`, `colors`, `widest`, and the `out` rule: the chart of per-color slot or object counts, keyed by `Choice`, rows ascending from `params.rank_dir`, bars growing from `params.bar_dir` (a `turn` of `bar_sense`), bg past a bar's end.
- 2753e76c — `chart`, `order`, `colors`, and the `bar` rule: the chart of per-color rectangle counts, rows descending from the corner's rank-axis edge (`rank_desc`), bars from the corner's across edge; the descending chart, which is the same chart from the opposite rank edge.
- 89565ca0 — `chart`, `frames`, `widest`, `fewer`, `seat`, `ties`, and the `out` rule: the chart of per-frame compartment counts, in the seated form: the frame from `Tally` and `Extremes.high`, `Order<Unit, Color>` ranks by count, `seat(F, K)` keeps the rows at or past a frame's rank, `TiebreakResolutions` assigns one frame per row, and the paint rule reads the member from `ties.assign`, not from a rank lookup.

Near-misses:

- 1fad071e `marked`: one bar of one count in a stored `out_pos` frame; no member is ranked.
- d631b094 `bar` (`AxisFrame`) and dce56571 `line_cell`: a single line whose extent is a count; no member rank, no frame from a member count.
- 2601afb7 `ink` ($Length) and 37ce87bb `result_cell`: a count drawn as a bar from an edge, in place on the input frame; the rows are the input's own lines and nothing is ranked.
- 58490d8a `copy`: a per-marker count drawn as strided copies along the marker's own row; in place, no rank.
- 31f7f899 `paint` ($Spans): reaches handed out in size order, but each bar keeps its own input line as its row, and the bar's cells are the reach set read from the input.
- 668eec9a `line_row` and `out`: a fixed-extent `Frame2D` of solid rows in position order, not score order; no bar length.
- 3ee1011a `out` ($Rank) and 5587a8d0 `nest`: members in descending count order, one per concentric ring inward; no bar.
- f8ff0b80 `out` and f8b3ba0a `out`: a 1-wide `DirFrame` of colors in count-rank order; a stack with no bar.
- 4df5b0ae `row` (`Order`) and 2ba387bc `tiles`: shapes stacked side by side in count or reading order, keeping their form (`OrderFrame` territory).
- 5289ad53 `frame`: a fixed frame with one cell per mark in reading order, colors by a stored rank; no row per member.
- 08ed6ac7, 42a15761, 694f12f3, 6e82a1ae: the size rank alone, consumed as a recolor or a panel permutation in place.
- 4290ef0e `paint`, 639f5a19, 5e6bbc0b, 758abdf0, f25ffba3: bar-only shape hits where the compared count is a ring size, band depth, packed count, run length, or half extent, with no ranked member.

Spec:

- The rank counts members, not distinct scores. An `Ordinal` over the score set gives dense ranks over distinct scores; 89565ca0's `seat` (`fewer.rank(F, R), R <= K`) reads `Order<Unit, Color>.rank`, the count of members with a strictly smaller score. The two differ under a tie, and the seated form is wrong on dense ranks: for scores {1, 1, 2}, dense ranks are {0, 0, 1}, so the 2-member may seat at row 1 with a 1-member at row 2; member ranks are {0, 0, 2}, so the 2-member seats at row 2 only, which is what 89565ca0 needs. On distinct scores the two coincide. The code form's `Order<Key, T>` (`elem` from `score`, `before` by `<` on scores) lets 89565ca0 read the comp's rank for its seat and drop `fewer`; `<` on numbers is transitive, so `Order`'s flagged assumption holds. 81c0276b writes this form; 2753e76c writes the `Ordinal` form.
- Split `bar` from `row` for the seated form. 89565ca0's paint rule takes the member from `ties.assign` and then tests `dist(P, Db, K2), K2 < N`. A member-agnostic readout, p nearer the bar edge than t's score with no row test, would serve that site directly; `bar` as written requires `row`, which 89565ca0 must bypass. One site only, so this is a signal from one caller rather than a settled change.
- The interface otherwise fits every caller. `rank_dir`/`bar_dir` unkeyed suits all three (81c0276b and 89565ca0 derive `bar_dir` from a `Sense` via `turn`; 2753e76c derives both from a `DiagDir` and `rank_axis` via `diag_dirs`). The bg-past-end branch stays in the caller in all three sites (81c0276b: `K >= N, params.bg`; 2753e76c: `!bar(P, _)`; 89565ca0: `speck(Col)`), so the comp rightly does not paint the remainder.

Reimplementations: 2753e76c reads the frame's bar-axis extent as `order.rank_desc($U(), N, 0)`, the top-ranked count, which is `Extremes.high` over the counts. The site reuses an instance it already has (Setup priority 2), so the fix is a judgment: if `BarChart` is promoted, the comp's `widest` supplies it.

Survey: 2026-09-10 14:36 — the solvers since 2026-09-10 07:45.

**Signature coverage.** The grep anchors (`Frame2D<` with `Extremes<` or `rank_desc(.., 0)` and `Ordinal<`/`Order<`) hit 4 scope files: 291dc1e1, 668eec9a, 81c0276b, 89565ca0. The parser match of the paint-rule shape (a `dist` distance compared against a variable, with a second `dist` on the same cell feeding a rank or seat lookup) hit exactly 2 rules in scope. Widened to every `<`, `<=`, `>`, `>=` between a `dist` distance and a variable, the scope holds only those same 2 rules (each also carries the `K >= N` past-the-end branch). No `// family:` sibling set is involved.

## 1. Callers

1. 81c0276b — `chart` (`Frame2D<Choice>`), `order` (`Order<Choice, Color>`), `colors` (`Tally`), `widest` (`Extremes`), and the `out` rule at `programs/solvers/81c0276b.dl:90`: the chart of per-color slot counts ($Tiles) or component counts ($Objects), rows ascending from `params.rank_dir`, bars growing from `params.bar_dir` (a `turn` of `bar_sense`), bg past a bar's end. Already listed in the entry; the site is unchanged in form.
2. 89565ca0 — `chart`, `frames`, `widest`, `fewer` (`Order<Unit, Color>`), `row`, `seat`, `ties` (`TiebreakResolutions`), and the `out` rule at `programs/solvers/89565ca0.dl:103`: the chart of per-frame compartment counts in the seated form. `seat(F, K) :- row(K), fewer.rank($U(), F, R), R <= K` keeps the rows at or past a frame's member rank, `ties.assign` seats one frame per row, and the paint rule reads the member from the assignment and then tests `dist(P, Db, K2), K2 < N`. Already listed in the entry; the site is unchanged in form.

No further caller in scope: the widened comparison scan returns nothing outside these two rules, and the `Ray`-based scan (a ray step count compared against a variable) hits only 1190bc91's `arm.blocked`, which orders arms by sequence index and draws no chart.

## 2. Near-misses

1. 668eec9a `line_row`, `out` — a fixed-extent `Frame2D` of solid rows; a line's row is its position rank from `params.order_dir` (`Extremes.low` then `Ordinal.rank_desc`), not a score, and a row is solid or bg with no bar length. Exclusions: "a chart whose rows follow an order other than the score" and "a stack of members with no bar". (Already in the entry.)
2. 291dc1e1 `slab` (`Frame2D<Ident>`), `widest` (`Extremes`), `slot` (`DirFrame<Choice>`), `out` — blocks stacked in reading order (`LexOrder`), each slab as long as the longest block, the block's own cropped cells centered in it. The `Extremes.high` extent matches the frame half of the signature, but the rows follow reading order and the content is the input block, not a counted bar. Exclusions: "a stack of members with no bar (`OrderFrame`)" and "a chart whose rows follow an order other than the score".
3. 19bb5feb `rank` (`Ordinal<Dir>`), `place` (`DirPack`), `rank_frame` (`Frame2D`) — markers ranked densely per edge, each taking the output cell at its rank pair; the frame's extents are the rank extents. Exclusion: "the rank alone (`Ordinal`)"; no member has a score-length bar.
4. 412b6263 `stack` (`Frame2D`, $Count) — the copy count from `Tally` sets one extent of the tile arrangement, one copy per input object. Exclusion: "the frame alone (`Frame2D`)"; nothing is ranked and no bar is drawn.
5. 83b6b474 `side`, `square` (`Frame2D<number>`) — the square whose border cell count equals the shape cell count (`Tally` against `Tally`). Exclusion: "the frame alone"; a count fixes an extent, no member row, no bar.
6. 83eb0a57 `largest`, `top` (`ArgExtremes`) and 1478ab18 `far` (`ArgExtremes`) — the size rank picks the canvas, the topmost piece, or the widest mark pair. Exclusion: "the rank alone"; consumed as a pick, not drawn.
7. 212895b5 `step_order` and 7e576d6e `seq` (`Order<_, Position>`) — a rank along a path carries state step by step. Exclusion: "the rank alone".
8. 1190bc91 `arm.blocked` (`arm.ray(J, P, ..), J < K`) — a ray of an earlier sequence index blocks a later one. Exclusion: not a bar; the compared value is a sequence index, and the rows are the input's own lines.

## 3. Spec

1. Interface: no change from these sites. Both callers key the chart differently (81c0276b by `Choice`, 89565ca0 by `Unit`) with unkeyed `rank_dir`/`bar_dir`, and both derive `bar_dir` via `turn` from a `Sense`; the code form's unkeyed direction inputs suit both. Both leave the past-the-end branch in the caller (`params.bg` / `speck`), so the comp rightly paints only the bars.
2. Definition, member rank: 89565ca0's `fewer` is exactly the code form's `order` (`elem` from the scored set, `before` by `<` on scores), and its `seat` reads `fewer.rank` as a member count (`R <= K`), which is what the entry's tie argument needs; 81c0276b's `order` is the same construction. Both scope callers confirm `Order`, not `Ordinal`, as the rank. No change beyond what the entry states.
3. Seated form, caller-only: 89565ca0 bypasses `row` (it seats through `ties.assign`) and needs the row index set (`row(K)` from `chart.cell` and `dist` toward `rank_dir`), which the code form does not expose, then tests the bar with its own `dist` against the score. A member-agnostic bar readout and a row-index readout would serve it. This rests on the surfacing solver alone in this scope (no second seated site), so it is reported as caller-only, as the entry already records.

## 4. Reimplementations

Reimplementations: none.

No scope site met on the way hand-writes a `programs/lib.dl` primitive. 2753e76c, the entry's recorded reimplementation (`order.rank_desc($U(), N, 0)` for `Extremes.high`), is outside this scope.
