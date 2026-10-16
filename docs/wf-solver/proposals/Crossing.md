# `Crossing<Key>` — the cells a mark's lines cover

The cells that share a line with a designated cell, per key, reported with the line family and that cell: the axis-aligned cross a mark stamps across the frame. The family set is an input, so one family gives a single line and `axis4_elem` gives an eight-armed star. The marks are a set of their own, so a mark outside the tested domain still draws its lines, and a caller that feeds `cell` and `mark` one set gets the line-sharing pairs of that set. `mark` may be recursive with `crossing`, as `Take`'s `step` is with its `taken`, so a caller can chain one crossing step per round into a canvas or an equivalence.

Code form (comp, since the family set and the two cell sets are all inputs):

```
.comp Crossing<Key> {
    // The cells tested, per key.
    .decl cell(key: Key, p: Position)  // input

    // The cells whose lines are read, per key. May be recursive with
    // `crossing`.
    .decl mark(key: Key, p: Position)  // input

    // The line families read, per key.
    .decl axis(key: Key, a: Axis4)  // input

    .decl crossing(key: Key, p: Position, a: Axis4, src: Position)
    crossing(Ky, P, A, Src) :-
        cell(Ky, P), mark(Ky, Src), axis(Ky, A), same_line(A, P, Src).
}
```

Not: `Ray` and `Between` (a cast that steps, carries a step count, and halts at a blocker); `Collinear` (which family a whole set lies along); `LineCover` and `LineColor` (a line a set covers whole); `run_line` (the line two adjacent members trace); `flanked` (members one step away on both sides); a `same_line` atom whose family column is bound by a parameter or by another atom, with no fold; any rule whose head reports the family rather than a cell.

Match: a rule that reports a cell because it shares a line with another cell, where the rule itself enumerates the family — a `same_line` atom whose family argument an `axis_elem`, `diag_axis_elem`, or `axis4_elem` atom of the same rule binds, or a disjunction stating one family per branch — and whose head carries a Position that the `same_line` atom binds. A rule whose head carries the family variable and no such Position is excluded, whether or not its two cell arguments come from one source; a rule that reports a cell is in scope even when both cell arguments range over one set. The signature has no lexical anchor beyond `same_line`; match it with the parser.

Survey: 2026-09-12 19:36 — every solver.

Callers:
137f0df0 block_line — tags each grid cell with the family on whose line some block cell sits; the companion gap_cell reports the cells whose block-free line meets the field's box.
140c817e crossed — the grid cells that share a row or a column with a mark.
21f83797 on_line — each grid cell paired with the mark whose row or column it lies on.
23581191 cross — each grid cell paired with the mark whose lines cover it, and that mark's color; 45bbe264 is its family sibling and writes the same rule.
2faf500b cut_cell — per shape, each shape cell paired with the shape's own mark on its line, keyed by the shape id.
319f2597 cross — the grid cells that share a row or a column with the mark.
412b6263 copy_line — the output-frame cells that share a row or a column with a copy, keyed by the case.
41e4d17e painted — the background cells on a line through the cell centered in a caster's box, keyed by the case.
4c7dc4dd spread — one step of the canvas chain: the panel cells on a marked cell's diagonal, over the two diagonal families.
4f537728 painted — per case, the base cells on the mark's line, and the block tiles on the mark's block's line in the tile frame.
8731374e flaw_line — each crop cell paired with the color of the flaw whose row or column it lies on.
8fbca751 group.equiv — one step of the line-sharing closure: the ink cells on a group member's row or column.
917bccba parse.crossing — the cells on the two lines through the rectangle's corner cell, keyed by the case and the corner.
a406ac07 line_ink — each cell paired with the family and the color of an ink cell on that line.
cbded52d fill — the tiles on the line that two same-color marks of one intile position define.
d4469b4b cross_cell — the output cells on the stored center's row or column; mismatch in Determine reads the same shape over the example outputs.
e729b7be center — the marker that shares a row or a column with a line cell.

The signature matched 104 `same_line` atoms across 82 solvers. Of those, 67 atoms in 58 solvers take the family from a parameter or from another atom, so the rule draws one line and not the cross. The remaining 31 solvers enumerate the family in the rule itself; 13 of those report the family rather than a cell, which leaves the 17 callers above, the 45bbe264 family counted once.

Near-misses:
070dd51e line_axis, 0becf7df axis, 178fcbfb bare, 291dc1e1 primary_axis, 2b01abd0 line_axis, 40853293 mark_axis, 50aad11f shared_line, 7e576d6e span.axis, and bdad9b1f line and role — each enumerates the family, but both `same_line` arguments are designated cells and the head reports the family that holds between them.
5168d44c move_dir — the same exclusion, with the family reported as the Dir that the corner parameter reads off it.
22425bda collinear and 80a900e0 aligned — `Collinear`: both arguments range over one cell set, and the relation exists so that a universal can negate it and report which family the whole set lies along.
4cd1b7b2 fill.conflict — both arguments range over cell_cand, the candidate placements of one color, so the two cell arguments come from one source.
The single-family class, 58 solvers: the family comes from a parameter (3345333e damaged, 770cc55f mark, f5b8619d marked at params.axis; 4aab4007 out at params.stripe_axis; 8403a5d5 bar_line at params.bar_axis), from `axis_of` on a direction the rule already carries (62b74c02 fill, 7c66cb00 fall, 88bcf3b4 toward, and 22 further sites), from `perp` on another family (0f63c0b9 mark_line, 5ad8a7c0 crossed, 78e78cff mark, and 6 further sites), or from a derived axis relation (195c6913 on_strip at strip_axis, 84ba50d3 pierced at fall_axis, 1efba499 crossing at cross_axis). None folds over the families, so each states one line.

Spec:
No column of `crossing` is unread across the callers, so the four-column interface stands. The axis column is read at 137f0df0 block_line, 2faf500b cut_cell, a406ac07 line_ink, and cbded52d fill; the src column at 21f83797 on_line, 23581191 cross, and 8fbca751 group.equiv; the other callers read the cell alone.

The Axis4 input type is exercised beyond the cardinals: 4c7dc4dd spread and 80a900e0 aligned enumerate `diag_axis_elem`, and 22425bda collinear enumerates `axis4_elem`, against 33 sites at `axis_elem`. The one input type carries all three.

Two callers feed the mark input from the relation that `crossing` derives: 4c7dc4dd spread chains diagonal steps into a canvas, and 8fbca751 group.equiv chains row and column steps into an equivalence. Each round adds one crossing step. The comp holds no negation, so the recursion is legal, but the entry states nothing about it, and a caller reading the entry cannot tell that the chained use is in scope. The entry should say that `mark` may be recursive with `crossing`, as `Take` says for its `step` and `take`.

The entry's two statements of the same exclusion disagree on the same-set pair. The Match line excludes a rule whose two cell arguments come from one source; the Not line gives the reason as reporting the family rather than the cells. At 4cd1b7b2 fill.conflict the two arguments come from one source and the head reports a cell pair, not the family, so the two tests rule oppositely on it. Restate the exclusion so that one test decides that site, and say whether an instance with `cell` and `mark` fed the same set is in scope.

Reimplementations:
ca8f78db out — two `split` atoms on one axis share their `along` variable to state that the corrupted cell and the clean source cell lie on one line, which `same_line` holds.
The match ran with the parser over `each_solver()`: a `same_line` atom whose family argument an `axis_elem`, `diag_axis_elem`, or `axis4_elem` atom of the same rule binds, with `body_literals` expanding the disjunction branches, and a second pass naming the binder of every family argument the first pass left. No site binds the family to a macro constant or splits it across disjunction branches. A third pass matched the hand-written line test as two `split` atoms on one axis sharing a component variable, and hit ca8f78db alone.
