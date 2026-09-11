# `ScoreOrder<Key, T>` — members ranked by a scalar score

The place each member of a keyed set takes in the order of its score, per key: the count of members with a strictly smaller score, and the same count over the strictly greater ones. Members sharing a score share a rank, and the rank set stays dense under ties. A solver that ranks objects by size, lines by ink count, or colors by cell count reads the ranked member from one instance, in place of stating the score comparison as an `Order.before` or composing `Ordinal` over the score set with a join back to the member.

Code form:

```
.comp ScoreOrder<Key, T> {
    .decl score(key: Key, t: T, s: number)  // input

    // The count of the key's members with a strictly smaller score.
    .decl rank(key: Key, t: T, r: number)
    rank(Ky, T, R) :- score(Ky, T, S), R = count : { score(Ky, _, S2), S2 < S }.

    // The same count over the strictly greater ones.
    .decl rank_desc(key: Key, t: T, r: number)
    rank_desc(Ky, T, R) :- score(Ky, T, S), R = count : { score(Ky, _, S2), S2 > S }.
}
```

Not: `Ordinal`, which ranks the scores themselves and leaves the member behind; `ArgExtremes`, which keeps the members at one extremum alone; `Order` under a `before` that is not a scalar comparison; `LexOrder`; `GroupOrder`.

Match: an `Order` instance whose `before` rule compares one scalar of each element (`N > N2`, `N < N2`) drawn from a per-member score relation, usually a `Tally` or `Bbox.extent`; an `Ordinal` instance whose `idx_set` is fed from a per-member score and whose `rank` or `rank_desc` is read back through that score relation to reach the member; a count aggregate over a score comparison. The score is a measured property of the member (a count, a size) and the rank is consumed as a rank; a coordinate ranked into a place in a compacted frame is `Ordinal` or `OrderFrame`, not this. Grep: `before(.*N1? [<>] N2` and `idx_set(.*tally`.

Survey: 2026-09-10 00:11

The corpus states the operation in two idioms that differ under ties: `Order` with a score-comparing `before`, whose rank counts the members with a smaller score (scores {1, 1, 1, 5} rank {0, 3}); and `Ordinal` over the score set joined back through the score relation, whose rank counts the distinct smaller scores ({0, 1}). No reimplementations: every rank site goes through `Order` or `Ordinal`.

## Callers

`Order` with a score-comparing `before`:

- 694f12f3 — `order`: rectangles ranked by cell count, ascending; `rank` and `rank_desc` index a color table, `first` and `last` pick the extreme.
- 89565ca0 — `fewer`: frames ranked by compartment count; `rank <= K` seats a frame on any row at or past the number of frames with fewer.
- 31f7f899 — `by_reach` ($Spans): bars' reaches ranked by size; `rank` and `rank_desc` compared against a bar's place in the spine order.
- 9caf5b84 — `by_count`: colors ranked by cell count; `rank_desc < keep_n` and `rank >= drop_n` pick survivors.
- 5587a8d0 — `nest`, keyed by `Choice`: patches ranked by cell count, descending; reads `rank`, `last`, and `next` to nest rings.
- dce56571 — `centrality`: cells of the centered line ranked by their distance to the nearer axis edge; `rank < N` takes the N most central cells.
- 81c0276b — `order`, keyed by `Choice`: colors ranked by slot or object count; `rank` gives the chart row.
- 8abad3cf — `row`: colors ranked by the side of their square, ascending; `first`, `last`, and `next` walk the squares' offsets along the row from each edge.

`Ordinal` over the score set, joined back through the score relation:

- 20a9e565 — `growth_order` into `stage_rank`: growth stages ranked by cell count.
- 2753e76c — `order`: colors ranked by rectangle count; `rank_desc` gives the chart row.
- 3ee1011a — `size_rank` ($Rank): bars ranked by cell count; `rank_desc` picks the frame depth.
- 42a15761 — `count_order` into `place`: panels ranked by mark count; `rank` gives the destination tile.
- f8ff0b80 — `o` into `color_rank`: colors ranked by cell count.
- f8b3ba0a — `o` into `minority_rank` (in `Parse`): minority colors ranked by cell count.
- 4290ef0e — `order` ($Rank): rings ranked by size; `rank_desc` gives the nesting depth.
- 08ed6ac7 — `seq`, keyed by `Seg`, and its `Determine` twin: bars ranked by size; the rank indexes a stored color table, keyed by the size itself, so equal-sized bars share a color by design.
- 6e82a1ae — `size_rank` (in `Parse`, keyed by `Key`) ($Rank): objects ranked by cell count; `rank` and `rank_desc` index a color table, so equal counts share a color by design, as in 08ed6ac7.
- 7447852a — `seq` ($Rank): pockets ranked by their margin from the anchor edge; `rank` through `stride` picks the pockets in a marked block, and `pocket_margin` carries the rank back to the pocket.
- 817e6c09 — `seq`: blocks ranked by their distance from the anchor edge; `rank` through `stride` picks every other block, and `block_dist` carries the rank back to the block.
- 85b81ff1 — `tile_rank` (keyed by `DecChoice`), `line_rank`, `obj_rank`, one per case: tiles, lines, and objects ranked by ink count; `rank` is matched against a place's distance from `params.least_dir` to find the input unit that lands there.

## Near-misses

The score is a frame coordinate and the rank a place in a compacted frame — `Ordinal` over the coordinate set, or `OrderFrame`: 19bb5feb `rank`, 58f5dbd5 `lane` ($Arrange), 668eec9a `stack`, 22a4bbc2 `seq`, d406998b `o` ($Sequence), 85c4e7cd `rings`, 4be741c5 `place`, 5289ad53 `Determine.place`, 4acc7107 `shape_ord`/`color_ord` (read as `first`/`next` alone), 3e6067c3 `seq` and 72207abc `order` (`before` is `nearer`).

A pairwise comparison with no rank read: 230f2e48 `fold_dir` ($Roomy), 3dc255db `holds`, 247ef758 `occludes`, 48634b99 `longer` (`ArgExtremes`), 31adaf00 `displaced`.

A two-level or non-scalar `before`: 4df5b0ae `row`, 5d588b4d `seq`, 3d6c6e23 `fill` ($Sink) (`GroupOrder`); 212895b5 `step_order` (product order); 1da012fc `reading`; 3a25b0d8 `hole_rank` (`same_class` makes the order partial beyond the score); e1baa8a4 `bands` (the queried distances are not members of the ranked set).

Spec question: which tie semantics the comp takes. The `Order` callers depend on the member count (a seat past "their number", a cut at the top K); the `Ordinal` callers depend on distinct-score ranks (equal sizes share a color). Under the member-count reading, the form is a subclass `ScoreOrder<Key, T> : Order<Key, T>` with `elem` and `before` derived from `score`, which keeps `first`, `last`, and `next` for the callers that read them; under the dense reading it is `Ordinal` plus one join rule. Under either, the operation as coded is two rules over an existing comp.

Survey: 2026-09-10 07:46, over the solvers at or after the previous survey's time

Over the 380 solvers in scope: 21 `Order` instances, 17 `Ordinal` instances, 25 rules holding the score-comparison shape (matched with the parser), and no count aggregate over a comparison. Every rank site goes through `Order` or `Ordinal`; no reimplementation of the operation. No listed caller changed form. New callers, all under the `Ordinal` idiom: 6e82a1ae `size_rank`, 7447852a `seq`, 817e6c09 `seq`, listed above. In the last two the score is an edge distance, as in dce56571, and the rank is consumed as a rank: what separates them from 19bb5feb and 58f5dbd5, which also rank `Bbox.edge_min`, is that those pack the rank back into a Position.

Near-misses outside the named classes: 5289ad53 `preceding` (`Tally<CaseColor, Ident>`), the marks of every color ranked before a color under the stored `color_rank`, consumed as the offset where the color's block starts, with `through` adding the color's own marks for the block's end — a prefix count over a stored order, where the counted items (marks) are not the scored ones (colors), and the consumer also needs the non-strict count. Inside the named classes: a coordinate ranked into a place in a compacted frame (4c3d4a41 `content_rank`, 58490d8a `slot_rank`, 5d588b4d `slot`, 7e576d6e `seq`); a non-scalar `before` (occlusion orders 1e5d6875 `prec`, 22425bda `stack`, 281123b4 `order`, 652646ff `stack`, 68bc2e87 `order`; walk orders 5792cb4d `chain`, 78332cb0 `chain`, 7b5033c1 `path`; 6cbe9eb8 `nest`, a product order over two box extents); a pairwise comparison with no rank read (3d588dc9 `short`, 3eda0437 `refuted`, 7c008303 `role`, 759f3fd3 `ring_cycle`).

Spec: the boundary against the coordinate class is decided by how the rank is consumed, not by what the score measures. 7447852a, 817e6c09, and dce56571 rank an edge distance and read the rank as a rank; 19bb5feb, 58f5dbd5, and 668eec9a rank an edge distance and pack the rank into a frame position or row. The Match line's "measured property of the member (a count, a size)" understates the callers: a coordinate score is this operation when its rank is consumed as a rank, and `Ordinal` or `OrderFrame` when the rank becomes a place. On ties, 6e82a1ae adds one site to the dense-reading side; 5289ad53 is the one site that wants the member-count reading together with a non-strict count, which neither form as coded gives.

Reimplementations: none. Adjacent lib gap: 52df9849 `nearer_eq` hand-writes a non-strict `nearer` because `nearer` cannot sit under negation (see `nearer_eq.md`).

Survey: 2026-09-10 19:22 — the solvers since 2026-09-10 07:46.

Callers: 89565ca0 and 85b81ff1, over the scope of the 39 solvers named in the brief (045e512c through d9fac9be). The scope holds 2 `Order` instances, 5 `Ordinal` instances, 1 `LexOrder`, 2 `OrderFrame`, and 5 rules holding the pairwise scalar-comparison shape (matched with the parser: one relation positive twice in a rule, a `<`, `>`, `<=`, or `>=` between one argument of each); it holds no count aggregate at all, so no rank is hand-written.

- 89565ca0 — `fewer` (`Order<Unit, Color>`, `before` = `size.tally` compared `N1 < N2`): frames ranked by compartment count; `rank <= K` seats a frame on any chart row at or past the number of frames with fewer. Listed by the first survey; unchanged in form.
- 85b81ff1 — `tile_rank` (`Ordinal<DecChoice>`), `line_rank` (`Ordinal<Unit>`), `obj_rank` (`Ordinal<Unit>`), each fed from a `Tally` (`tile_ink`, `line_tally`, `obj_size`) and read back through that tally to reach the member: tiles, lines, and objects ranked by ink count; the rank is matched against a place's distance from `params.least_dir` (a tile index, an `OrderFrame.pos`) to find the input unit that lands at each place. The file writes the `Ordinal`-plus-join idiom three times, once per case, in the pattern of 42a15761.

Near-misses:

- 212895b5 `step_order` (`Order<ArmKey, Position>`): `before` is a product order over two `diag_dist` readouts (`O1 <= O2, S1 <= S2`), not one scalar comparison — the non-scalar `before` exclusion; listed by the first survey.
- 19bb5feb `rank` (`Ordinal<Dir>` over `Bbox.edge_min`): the score is a coordinate and the rank is packed into a Position through `DirPack` — the compacted-frame class; listed by the first survey.
- 85c4e7cd `rings` (`Ordinal<Unit>` over `Rim.depth`): ranks the depth set itself and reads `rank_desc` back to a depth, with no member behind the score — `Ordinal` over a coordinate, the compacted-frame class; listed by the first survey.
- 291dc1e1 `reading` (`LexOrder<Choice>`): excluded by name.
- 08573cc6 `arm_cell`: two `run.ray` step counts compared `K < N` to keep cells short of the arm's start — a pairwise comparison with no rank read.
- 84ba50d3 `through`: two `dist` readouts compared `K <= K_div` — a pairwise comparison with no rank read.
- One extremum alone, `ArgExtremes`: 045e512c `reach`, 1478ab18 `far`, 3490cc26 `nearest`, 44f52bb0 `best_id`, 84ba50d3 `widest`; and its score-only peer `Extremes`: 1190bc91 `nearest`, 13e47133 `sight`, 291dc1e1 `widest`, 89565ca0 `widest`, 212895b5 `cycle`, 97999447 `unbroken`. Each keeps the member or score at one extremum and reads no rank.
- A `Tally` consumed as a count, not ranked: 84f2aca1 `region_size` and `hole_size` (the count keys a stored color table), 412b6263 `block_n` and `tile_n` (the count is an extent), 13e47133 `pal_len`, b1fc8b8e `ink_tally`. No order is stated over them.

Spec: the scope changes nothing in the interface or the definition. 85b81ff1 is the strongest sign so far that the `Ordinal` idiom is a repeated two-rule form: one file states the operation three times, each time as `idx_set` fed from a `Tally` plus a join back through that tally, with the same consumer shape (rank matched to a place index). On the tie question it adds no evidence: its consumers pair each rank with exactly one place, so tied members over-derive `out` under either reading and leave the far places empty, and the task carries no ties. On the boundary against the compacted-frame class, 85b81ff1 sits where 42a15761 sits: the score is a measured property (an ink count), so it is this operation under the Match line as written, even though the rank is then matched to a place; the previous survey's refinement (consumption decides only when the score is a coordinate) holds here. The `Extremes` sites show that the `Not:` line's `ArgExtremes` exclusion also covers `Extremes`, its score-only peer; the line could name both, a wording point and not a change to the operation.

Reimplementations: none. Adjacent lib gap: 84ba50d3 `through` (line 105) writes two `dist` atoms with `K <= K_div` for the non-strict comparison that `nearer` cannot state under its strict form — a caller for `nearer_eq.md`, not listed there.
