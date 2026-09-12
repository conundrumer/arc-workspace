# `Ordinal.rev` — opposite-end readout of an index set

The pairing of each element with its counterpart from the other end. Not: descending layout; a rank flowing into a table; reversal by geometry or by a stored table.

Match: `rank_desc`, `rank(`, `count :`.

Callers: 85c4e7cd alone. Near: 08ed6ac7, 2753e76c (`rank_desc` into a table or an extent); 3906de3d, 9c56f360, 1da012fc, 2ccd9fef (same rank across two index sets).

Survey: 2026-09-11 21:05 — every solver.

Callers:
85c4e7cd `out` — a ring takes the color of the ring at the same rank counted from the other end of the depth set, so the concentric colors reverse.
8dae5dfc `out` — a nesting layer takes the color of the layer at the same rank from the inside, so each object's layer colors reverse.
5792cb4d `out` — a chain cell takes the color of the cell as far from one end as it is from the other, so the chain's colors reverse.

Negative evidence for the count: 77 solvers instantiate `Ordinal`, `Order`, or `LexOrder`, and 18 of them write `rank_desc`; a parser match over every solver for two rank-family atoms joined on one shared rank variable gives 14 hits in 9 solvers. Three of those hits pair two distinct elements of one ordered set, and they are the three above. The opposite-end pairing is the whole of each caller's painting rule, and each caller states it in a comment of the same form ("as deep from the center", "as deep from the inside", "as far ahead as P is behind").

Near-misses:
Descending readout with no pairing — 08ed6ac7 `size_color`, 694f12f3 `fill`, 6e82a1ae `out`, 2753e76c `out`, 4290ef0e `depth_ring`, 3ee1011a `out`, 9caf5b84 `survives`, 668eec9a `line_row`, 20a9e565 `seed`, 4c3d4a41 `out`. Each takes `rank_desc` alone and feeds it to a color table, an extent, a line index, or a count threshold. The far-end index is the answer itself, and no second element is fetched at that index, which the exclusion on a descending layout and on a rank flowing into a table rules out.

Both ranks of one element — 4be741c5 `out`, 652646ff `tile`, 78332cb0 `seat`. Each joins `rank` and `rank_desc` of the same element on two separate rank variables and packs the pair into an `axis_inset`. That is a Box readout of one element's place, not a pairing of two elements, so the operation is absent.

Two-sided threshold — 31f7f899 `paint`. It takes `rank` and `rank_desc` of one element and compares each against a bound. The two ranks bound a selection; no element is fetched at a mirrored index.

Same rank across two index sets — 3906de3d `out`, 9c56f360 `out`, 1da012fc `pick`, 2ccd9fef `carry`, 3a25b0d8 `partner`, 3d6c6e23 `out`, 8698868d `seat`. Each joins two ranks of distinct index sets, or two subsets of one order, at the same rank. That is a correspondence between two sets, not the reversal of one. 8698868d is the nearest of these: it offers the ascending join and the descending join as two cases, but both read the two sets at matching ends, so neither reverses a set.

Order reversed at its source — 8abad3cf `row.before`. Its `$ByPlace()` case writes the comparison inverted, so the order itself runs the other way. No element meets its counterpart; the operation is absent.

Geometric mirror — 50c07299 `out`, 47996f11 `counterpart`, 981571dc `counterpart`, 67b4a34d `restored`, 5751f35e `out`. Each reflects a cell through a box or under a D4 element. The exclusion on reversal by geometry rules these out, and the index set plays no part.

Spec:
The name places the operation on the wrong component. Of the three callers, 85c4e7cd ranks over `Ordinal<Unit>`, while 8dae5dfc ranks over `Order<Ident, Ident>` and 5792cb4d over `Order<Position, Position>`. The operation therefore belongs to the rank interface that `Ordinal` and `Order` share, not to `Ordinal` alone. The entry should name it for that interface and state both host components, or state which one carries it and how the other's callers reach it.

The definition should state the totality the pairing needs. In each caller the join is a pairing only because the key's order is total: the ranks then run 0 to n-1 with no gap, and `rank` and `rank_desc` complement. `Order` does not require a total `before`, and `Ordinal` collapses ties, so a partial order or a tie leaves an element with no counterpart or with several. The three callers all supply a total order — 5792cb4d closes its `before` transitively over a chain, 8dae5dfc over a nesting, 85c4e7cd over a dense depth set — so the requirement is met everywhere and stating it costs nothing. The interface itself needs no other change: all three callers read the pairing as element to element with nothing else, so a single `rev(key, t, t2)` readout serves each one in place of its two-atom join.

The `Match:` line does not meet spec. `rank_desc, rank(, count :` is a bare token list; it names no shape, and by itself it admits the 17 near-miss sites above as readily as the 3 callers. The operation's statement is a shape: two rank-family atoms of one instance and one key, positive in one rule, sharing the rank argument, with the element arguments bound to different variables. A restated line: `Match: in one rule, two positive atoms named rank or rank_desc on the same instance path and key, sharing the last argument's variable, with different variables in the element argument; match with the parser. Also grep rank_desc for statements that split the join across rules.`

Reimplementations:
none. The matcher's 14 hits came from a parser script over every solver, and the grep over `rank_desc`, `rank(`, `Ordinal`, `Order<`, and `LexOrder` covered 77 solver files; no site met on the way hand-writes a primitive that lib already holds.
