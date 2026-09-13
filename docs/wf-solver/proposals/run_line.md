# `run_line` — the line two adjacent members of a set trace

The line of a frame on which two members of a keyed cell set are adjacent, per key: the set runs along it, if only for two cells. It is how a solver finds a dashed line, where the set covers the line in pieces, so `LineCover` and `LineColor` miss it, and where lone members of the set also sit off the line, as a dash color does at the crossings of a lattice. The line is reported as `DividerFrame` reads it: its axis-only position on the axis it is read across.

```
run_line(K, A, L) :-
    cell(K, P), cell(K, Q),                    // two members
    axis_of(D, A_run), neighbor(P, D, Q),      // one step apart
    perp(A_run, A), split(P, A, L, _).         // the line they run along
```

Not: `Runs` (every maximal segment, individuated); `multi_cell` (two members anywhere under one key); `flanked` (a cell between two members); `LineCover` and `LineColor` (a line the set covers whole); a count of a line's members against a threshold or against its gaps (`Tally`, `Excess`); a pair of members on one line with no adjacency (`same_line`).

Match: a rule with two atoms of one cell set joined by one `neighbor` step, whose head or a following atom names the line one of them lies on — the along or across component of `split` on that cell, an axis with it. Either line convention matches: the position on the axis read across (`DividerFrame`'s), or the axis the line runs along with the across component (`same_line`'s). The signature has no lexical anchor; match it with the parser (`tests/test_ast_match.py`).

Survey: 2026-09-09 21:07, over the whole corpus.

Result: over the 609 solvers, two sites state the operation, and neither hand-writes a lib primitive. The Axis column is the read-across axis, `DividerFrame`'s convention; a consumer that keys its lines by the run axis (4612dd53's `line_gap`) converts with one `perp` atom, and the line Position is the same object under both conventions.

## Callers

- 65b59efc — `lattice.divider`: a separator cell beside another along a line names that line as a divider; a lone separator cell at a crossing does not.
- 4612dd53 — `line`, in the `$Segment` case: two marks adjacent along a box row or column make it a line to repair. The line key comes from `line_cell` (`split` in a separate rule), so the statement crosses rules.

## Near-misses

- Counts of a line's members: 4612dd53 `$Threshold` (`Tally` against a stored minimum) and `$Majority` (`Excess` over the line's gaps).
- Two members collinear with no adjacency test: bdad9b1f `line`, 070dd51e `line_axis`, 2b01abd0 `line_axis`, 40853293 `mark_axis`.
- A segment individuated, then its line read: 538b439f `reach.item` and `thin` (`Runs`).
- A cell with a member on both sides: a699fb00 `flanked`, 182e5d0f `plug`, 2b83f449 `bar_center` (`flanked`).
- Divider feeders that read a whole line (`LineCover`, `LineColor`): 0bb8deee, 135a2760, 18286ef8, 18447a8d, 1be83260, 20fb2937, 247ef758, 2546ccf6, 272f95fa, 2e65ae53, 38007db0, 39e1d7f9, 42918530, 458e3a53, 4c177718, 4e7e0eb9, 4f537728, 5545f144, 54d9e175, 5a719d11, 5dbc8537, 5ecac7f7, 6350f1f4, 77fdfe62.
- Divider feeders where any one cell of the divider class marks its line: 20981f0e, 363442ee, 8597cfd7. The weaker form; a lone crossing cell would mark a false line there.
- Two members adjoining along a diagonal step, read as the diagonal axis or direction with no line: 1d61978c `streak`, 508bd3b6 `aim`. The entry's line convention has no diagonal line, so these would need a run-axis readout over `Axis4`.

## Spec

- The Axis column is the read-across axis. A run-axis consumer applies `perp`; no site argues for the other convention.
- Both callers narrow the set inside their rules (a color, a box and mark test), so a keyed `cell` input covers both.

Survey: 2026-09-13 18:32 — the solvers since 2026-09-09 21:07.

Callers:
9344f635 `segment` — two cells of one color one step apart give that cell with the axis its segment runs along; the next rule, `line_col`, names the line with `same_line`, so the statement crosses two rules inside Parse, and the set is one class per color.
65b59efc `lattice.divider` — a separator cell beside another along a line names that line as a divider; a lone separator cell at a crossing does not.
4612dd53 `line`, in the `$Segment` case — two marks adjacent along a box row or column make it a line to repair, with the line key from `line_cell`.

Negative evidence: over the 482 solvers of this scope, the adjacency signature (one `neighbor` or `jump` step whose two endpoints are bound by two atoms of one relation) matched 59 rules. All but the three above name no line: they join adjacent members into components, arms, walks, legend pairs, or panel successors. A looser net — any adjacency step with both endpoints bound, in a rule that also holds a line read and an axis atom — added 7 rules, and none states the operation.

Near-misses:
6a980be1 `line_axis` — the adjacency gives the run axis alone, unkeyed and global; `line_cell` then names each line from a single line-colored cell, so no line comes out of the pair.
33067df9 `join` — two like tiles one step apart are joined as a pair for grouping; the rule names no line.
1190bc91 `seq` — the adjacency establishes that one object runs along a direction; the head carries the direction and an anchor cell, not a line.
89565ca0 `line` — the adjacency extends a hidden line cell by cell; the head is a cell, with no line coordinate.
e1baa8a4 `boundary` — two adjacent cells that differ name the line between them; the two cells are not two members of one set.
90c28cc7 `uncut` — the `neighbor` step joins two line coordinates, not two members of a cell set.
One cell of the class marks its line, the weaker form: 9356391f `panel.divider`, 6e453dd6 `cut.divider`, 7837ac64 `tiles.divider` in its `$Marked` case. A lone cell off the run marks a false line at each.
A line the set covers whole, read through `LineColor`, `LineCover`, or a universal over the line's cells: 7491f3cf, 780d0b14, 78332cb0, 7c008303, 7c8af763, 7d419a02, 7e576d6e, 81c0276b, 83302e8f, 88a62173, 8a371977, 8d510a79, 92e50de0, each in its `divider` feeder, and 7837ac64 `gapped_line` with `on_line`. 1ae2feb7 `cut.divider` takes the commonest along-position of the ink instead.
A segment individuated, then its line read: 2ccd9fef `run_line` (`Slide`) and 88207623 `in_band` (`Components`).
Two members on one line with no adjacency test: 8a371977 `screened` and 291dc1e1 `overlap`.

Spec:
The Axis column should be reconsidered. Two of the three callers key their lines by the run axis with the across component, `same_line`'s convention: 4612dd53 `line_cell` and 9344f635 `line_col`. One caller, 65b59efc, keys by the read-across axis, because it feeds `DividerTiles.divider`, which takes that convention. The rule computes the run axis first and applies `perp` to report the other, so a run-axis column would drop `perp` from the definition and from the two run-axis callers, and add one `perp` atom to 65b59efc. The line Position is the same object under both conventions, so the choice costs one atom at one site either way.
9344f635 keys its set by color: the color must come out with the line, so the key is a record carrying it, and the same instance sits in a Parse comp that the Determine comp shares, so the key carries the Example too. The keyed `cell` input covers that with no change.

Reimplementations: none. The parser matchers ran over the scope's parsed solvers: the adjacency matcher hit 59 rules, the looser adjacency-with-line matcher 7, a line-naming matcher with no adjacency 84, a `step_offset`-and-`compose` matcher 3, a component-label-with-line matcher 6, and a dump of every `divider`, `line`, `mark`, and `member` feeder rule covered the frame units.
