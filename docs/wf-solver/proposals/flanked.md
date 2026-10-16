# `flanked` — a cell between set members on one axis

The cell that holds keyed set members one step away on both sides of one axis, reported with that axis. It is the straight-run peer of `bend`, which straddles a corner's two cardinals, and the adjacency peer of `Between.between`, which folds over a whole line's reach. The cell need not be a member: the known sites read a plug in a wire, a doorway in a wall, a break a covering left in a drawn line, and a bg cell pinched between two dots.

Code form (comp, since the tested set and the flanking set differ at most sites):

```
.comp Flanked<Key> {
    // The cells tested, per key.
    .decl cell(key: Key, p: Position)  // input

    // The cells that flank, per key.
    .decl flank(key: Key, p: Position)  // input

    .decl flanked(key: Key, p: Position, a: Axis4)
    flanked(K, P, A) :-
        cell(K, P), axis4_of(D, A), dir8_opposite(D, D2),
        neighbor(P, D, Q), flank(K, Q),
        neighbor(P, D2, Q2), flank(K, Q2).
}
```

Not: `bend` (the two cardinals of a corner); `Between.between` and `Between.strict` (marks anywhere along the line, by ray reach); `Rim.interior` (a member no step of the adjacency leaves, which is every side at once); a chain, whose second step leaves the first step's target; `opposite` reversing a walk's heading; two `neighbor` atoms whose directions are not an opposite pair.

Match: a rule with two `neighbor` atoms out of one cell whose directions are an opposite pair — from `opposite`, from `dir8_opposite`, from `axis_of` or `axis4_of` twice, or from `dist_pair` — each landing on a cell of one set. The step may be mediated by a helper relation that itself reaches `neighbor`. The signature has no lexical anchor; match it with the parser.

Survey: 2026-09-09 14:20, over the whole corpus.

## Callers

Each is its own family representative.

- 4c416de3 — `outline`: any grid cell with a drawn frame cell on both sides of one axis, so a one-cell break in a drawn line still counts as outline. `Components` then joins the box border into one component.
- 182e5d0f — `plug`: a wire cell with a cap cell on both sides, which names the wire's end.
- 18419cfa — `doorway`: a region interior cell with wall on both sides of axis `A`, reported as the perpendicular axis the interior opens along, which then picks the mirror.
- 3ad05f52 — `door`: a non-wall cell with wall on both sides, cut out of the wall so no room floods through it.
- a699fb00 — `flanked`: a bg cell with a dot on both neighbors along the stored axis. The file is the witness for the operation's identity: its `$Span` case is `Between<Unit>` over the same cells and marks, and the two stand as peer cases.
- 2b83f449 — `bar_center`: a bar cell with bar on both sides of the across axis, which is the middle of a 3-cell bar.
- 3bd292e8 — `across`: a wall cell with a region cell on both sides; the two region labels it reports two-color the regions.
- 21897d95 — `Parse.arrow`, through its one-sided helper `marked`: an arrow center is a cell with arrow-colored cells on both sides of the axis across its stem.
- 7b80bb43 — `flanked`: an ink cell with ink on both sides of one axis, the interior of a straight run; the cells it excludes are the loose cells that diagonal chains are made of. The axis is projected away.

## Near-misses

- Reach in place of adjacency, which the entry excludes: 253bf280 `between`, 4c7dc4dd `flank` (a `Between` instance despite the name), 505fff84 `seg`, 06df4c85 `fill` (two `Ray.stop` reaches), 28a6681f `rest` (a recursive run predicate), 35ab12c3 `straddled`, 52df9849 `sweep`.
- 1818057f `flanked` and its sibling 7e02026e: the same name over `Rim.interior` — a set member no step of the adjacency leaves.
- Both-sides tests with no step: 16b78196 `bar` (two `Bbox.edge_min` readings at 0), 4e45f183 `balanced` (two negated box-side tests).
- 7f4411dc `support_kept`: two steps out of one cell with `D1 != D2` alone, so a corner bend passes.
- 89565ca0 `line`: a chain, whose second step leaves the first step's target.
- Corner pairs, which belong to `bend`: 2546ccf6 `gap`, 3aa6fb7a `mark`, 465b7d93 `corner`, 54dc2872 `bend`, 15663ba9 `bend`, 5ad4f10b `figure`, 142ca369 `bounce`, 508bd3b6 `bounce`.
- `opposite` reversing a walk's heading: 712bf12e `line`, d9f24cd1 `walk`, 3ac3eb23 `center` and `walk`, e179c5f4 `walk`, 29c11459 `walk`, 1190bc91 `seq`, 5ffb2104 `room`, e633a9e5 `edge_off`, 21897d95 `arrow_host.item`.
- Single steps in separate disjunction branches: 33067df9 `join`, 49d1d64f `out`, bbc9ae5d `grown`.

## Spec

- **The axis column carries.** Four callers read it. 18419cfa turns it with `perp` into the axis the interior opens along; a699fb00 and 2b83f449 constrain it to a stored axis, so a comp that enumerated the axis internally and hid it would over-derive at both; 21897d95 constrains it relative to another direction. The other four project it away.
- **Two inputs are justified.** Seven of eight callers have a tested set distinct from the flanking set. Only 2b83f449 has the two coincide, and it feeds one set twice.
- **The flanker readout is the open question.** 3bd292e8's `across` never tests the flanking cells for membership — it reads their region labels and requires the two labels to differ. Without a `pair(key, p, a, q, q2)` readout it cannot call the comp at all. The other seven callers bind the flankers to `_` or to a membership test alone, so the signal is one site, and that site is not the surfacing solver.
- **No `Val` column is needed.** Three callers bind a shared color across the two flankers, but in each the color comes from a single-valued parameter, so the tie collapses into one flank set.
- **The key is unexercised.** All eight callers are single-set and would key on `Unit`. Style requires the `Key` type parameter regardless.

Survey: 2026-09-10 05:38, delta over the solvers that postdate the 2026-09-09 survey.

The already-listed sites stand in the form the earlier survey recorded. One caller is new.

## Callers

- 72322fa7 — `template`, `$Line` case: a non-bg center cell with cells of one other color one step away at both ends of a line through it, over `dir8_opposite`, so the line is a row, a column, or a diagonal. The flankers' shared color is read out with the center's color and the step's `Shift` as the template an arm demonstrates. It is its own family representative.

## Near-misses

- Reach in place of adjacency: 7666fa5d `strict` (two `Between.ray` reaches with `K != 0`, the `Between-strict` proposal's site), 3e6067c3 `corridor` (a cell past one box's side and short of another's, by `nearer`), 1c02dbbe `separated` (two `nearer` tests along one `Dir`), 2b83f449 `far_end` (a `Slide.clear` run between two run ends), 6e4f6532 `faces` (a `Ray` reach to a wall on one side, an adjacency to the object's own cell on the other).
- Two neighbors read as a footprint, with no flank set: 79fb03f4 `aside`, the cell beside a marker and its two neighbors along the stored `flow_dir`. The neighbors are ordered as entry and end and tested downstream, so the site needs the two directions apart, which the axis column loses.
- Two adjacencies with no opposite pair, so a corner passes: 7b5033c1 `fork`, 753ea09b `between`, 71e489b6 `passage`.
- One side open, the other closed: 6bcdb01e `leg` (`!rim_dir` toward `D2`, `rim_dir` toward its opposite).
- Corner pairs, which belong to `bend` or `quad`: 7666fa5d `step`, 71e489b6 `quad`, and 15663ba9 `bend` now through an `arm` helper.
- Chains, whose second step leaves the first step's target: 5b37cb25 `closed`, 2b83f449 `drop`, 5792cb4d `step`, 7b5033c1 `step`, 212895b5 `Determine.bend`.
- `opposite` reversing a walk's heading or naming the reverse of one adjacency: 08573cc6 `arm_cell`, 36a08778 `shell` and `stub_flow`, 4364c1c4 `Parse.side`, 5623160b `move_dir`, 53fb4810 `grow_dir`, 56dc2b01 `back_line`, 6ad5bdfd `Settle.room`, 446ef5d2 `clash`, 494ef9d7 `Parse.rest`, 5adee1b2 `legend_entry`, 5b37cb25 `edge_color`, 6cbe9eb8 `anchor`, 6f473927 `Parse.tiles`, 7837ac64 `corner_mark`, 2bcee788 `wall.cell`, 13e47133 `sray.mark`, 5e6bbc0b `far_end`, 4c3d4a41 `Determine.refuted_dir`, 64efde09 `reach`, 6e4f6532 `wall_toward`, 29700607 `wire`.
- `dist_pair` as a nearer-half test beside a single step: 2faf500b `moved`, 642248e4 `tail`.

## Spec

- **The axis column should range over `Axis4`.** 72322fa7 flanks over `dir8_opposite`: its `$Line` figure has arms on a row, a column, or a diagonal, and the four line families are one enumeration in the rule. With an `Axis`-typed column the comp cannot state that site. `Between` already takes `Axis4`, and `neighbor` takes `Dir8`, so the code form changes only in its direction atoms (`axis4_of` and `dir8_opposite` in place of `axis_of` and `opposite`); an `Axis`-only caller narrows with `axis_elem`. The signal rests on one site beyond the surfacing solver.
- **The key is now exercised.** At 72322fa7 the flank set is the cells of one color and the tested set is the non-bg cells of any other color, so the site keys on the arm color: `flank(Ca, Q) :- in(Q, Ca), !bg(Ca)` and `cell(Ca, P) :- in(P, Cc), !bg(Cc), Cc != Ca`. That encoding reads the arm color off the key and needs no flanker readout and no `Val` column.
- **The flanker readout gains no second site.** 72322fa7 reads the flankers' shared color, and the key encoding above carries it. 79fb03f4 reads both flankers as positions, and it needs them told apart by direction, which a `pair(key, p, a, q, q2)` readout does not do. 3bd292e8 `across` stays the one site that needs the pair.
- **A direction readout is not needed.** 72322fa7 reads `step_delta(D, V)` for each of the axis's two directions, and both directions of the axis produce a template row. `axis4_of(D, A)` with the axis column recovers both.

## Reimplementations

None: no site in the scope hand-writes a `programs/lib.dl` primitive.
