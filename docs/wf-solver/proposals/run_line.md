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
