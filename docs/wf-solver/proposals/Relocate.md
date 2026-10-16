# `Relocate<Key, Val>` — a scene with a landing set painted and a vacated set blanked

The render, per key: a cell holds what lands on it; a vacated cell that nothing landed on holds the blank value; every other cell keeps the scene. The vacated set and the landings are separate inputs, so what leaves and what lands need not be related: a move, an erase with a paint elsewhere, and content that walks off the frame render the same way. Where the move comes from is the caller's.

```
.comp Relocate<Key, Val> {
    // The scene the render reads, per key.
    .decl scene(key: Key, p: Position, v: Val)  // input

    // The cells content leaves, per key.
    .decl vacated(key: Key, p: Position)  // input

    // The cells content lands on, with what lands, per key.
    .decl placed(key: Key, p: Position, v: Val)  // input

    // The value a vacated cell takes when nothing lands on it, per key. A
    // stored color, or one read from the grid.
    .decl blank(key: Key, v: Val)  // input

    .decl cell(key: Key, p: Position, v: Val)
    cell(K, P, V) :- placed(K, P, V).
    cell(K, P, V) :- vacated(K, P), !placed(K, P, _), blank(K, V).
    cell(K, P, V) :- scene(K, P, V), !placed(K, P, _), !vacated(K, P).
}
```

Not: an overlay with no vacated cells (paint over the scene, `out(P, C) :- in(P, C), !paint(P, _)`); a stamp whose footprint carries the blank as stamped content (a landing value, not a vacated set); a render whose untouched cells take a value other than the scene's (every non-landing cell blank); a kept set that stays while every other cell takes the blank, which states no vacated set, even when a move is written that way and the outputs agree; an erase with no landing set (a vacated set blanked over the scene, two branches); a blank that varies per vacated cell; a translation of the whole frame (`compose` with an Offset over every cell); the walk or slide that finds where content lands.

Match: three exclusive branches over the input cells — a landing set with its value, the negation of that landing set with a vacated set and a blank value, and the negation of both with the input cell's own value. The scene is `in` or `ex_in`. The vacated set may be a color test on the input cell (every mover-colored cell vacates) or a relation over the movers' cells; the blank may be `params.bg`, a local `bg`, or a Mode readout. When the landing set lies inside the vacated set, the scene branch may negate the vacated set alone. The branches take one of these forms:

- one-rule: the three branches in one `out` rule, as a disjunction or as separate rules on one head;
- two-stage: a rule that blanks the vacated set over the scene (`in(P, Col), !<vacated>(P)` beside `<vacated>(P), <blank>(Col)` on one head), and `out` paints the landing over it;
- folded: the vacated-to-blank rule written inside the paint relation (`<paint>(P, Bg) :- <vacated>(P), <blank>(Bg).`), and `out` overlays that relation over the scene (`out(P, Col) :- in(P, Col), !<paint>(P, _)`). The landing gets no precedence over the vacated cells, so a caller in this form has the two sets disjoint.

Coarse grep: a blank atom in a rule that also negates a placement relation, beside `Col = C_in` or `Col = Col_in`; the two-stage head; or a rule of an overlaid relation whose value is a blank atom, beside the overlay `out`. Match with the parser, with the scene fixed to `in`/`ex_in`: a landing relation whose own body reads `in` under a negation is still a landing.

Survey: 2026-09-10 03:01

Callers, 23; none is a `// family:` sibling of another. All on `out` unless noted.

Moves — placed, vacated to blank, scene:

- 73c3b0d8 — marks step one cell and splash; mark-colored input cells vacate to bg.
- 182e5d0f — a bead slides along a cord to its plug; `consumed` (cord run and seat) clears to bg.
- 22208ba4 — corner blocks step inward; `vacated` clears to bg.
- 230f2e48 — the stretch past a joint folds a quarter turn; `tail` cells clear to bg.
- 3906de3d — mover cells pack toward a gravity edge; mover-colored input cells vacate.
- 9c56f360 — mover cells pack toward an edge against a barrier; `mover` cells clear.
- 332f06d7 — a piece slides along a corridor; `piece_cell` shows the corridor color, a blank other than bg.
- 271d71e2 — a block slides to a marker line; `assembly` cells clear.
- 228f6490 — a shape moves into its hole; `erase` cells clear.
- 3618c87e `$PerCell` — marker cells fall to a slice edge; `cleared` cells go bg, scene read through `cell_split`.
- 5034a0b5 — marks step toward the frame side of their color; `move(P, _, _, Ch)` cells clear via a local `bg` relation.
- 6e4f6532 — objects move onto same-shape targets under D4; `object_cell` clears via a local `bg`.
- 6855a6e4 — mover shapes reflect into brackets; `mover_cell` clears to bg.
- 05f2a901 — two-stage: `cleared` is the scene with `mover_cell` blanked, and `landed` paints over it.
- 56dc2b01 — two-stage, as 05f2a901, with `back_line` as a second placed set.
- 758abdf0 — a full mark run lands against the far edge in the wall color and a short one grows a cell; `vacated` (the full run's cells) clears to bg.
- 825aa9e9 — shapes fall toward a floor as bodies; `mover_cell` cells clear to bg.

Erase and paint — the same three branches where what leaves and what lands are unrelated sets:

- 1a244afd — a mark is painted at a turned offset from a pivot; pointer-colored cells are erased.
- 3345333e — the symmetric figure is repaired under `paint`; `occluder` cells clear.
- 3d588dc9 — a key's block edge takes the face color; its stem `cleared` to bg.
- 3dc255db — held cells clear to bg and a line of their color runs out of the spout.
- 465b7d93 — a shape's color paints the frame's rim; the shape (`mark`) is erased.
- 22806e14 — rectangle centers take the marker color; the marker (`gone`) clears when it fails a count.
- 247ef758 — legend shapes stamp at crossings; `erased` legend shapes clear.
- 195c6913 — a walk paints a pattern and stop marks; `swatch_cell` clears to the wall color, a blank other than bg.
- 456873bc `$Restore` — `marked` cells take the mark color and inked cells under the cover take ink; cover-colored input cells nothing lands on clear to bg.
- 673ef223 — a flagged bar cell casts the mark color along `cast.clear`; mark-colored input cells take `params.cap`, a blank other than bg.

Near-misses:

- Every non-landing cell blank, no scene branch — 52 solvers, among them 025d127b, 25ff71a9, 5623160b, 54dc2872, 28e73c20 `$Repaint`.
- Kept set stays, landing, everything else blank — untouched cells outside the kept set take the blank whether or not content left: 18447a8d (`base`), 20981f0e (`dot`), 31f7f899 (`spine`), 6ad5bdfd (`wall`), 6a1e5592 (`wall`), 28a6681f (`wall`), 1b8318e3 (`block`), 67c52801 (`floor`), 17829a00 (`border_cell`), 1e5d6875 `$Keep`, 0e206a2e `$Kept`. On every pair of those tasks the output equals Relocate's, since every untouched non-kept cell is already bg.
- Region re-render — landing and blank inside a region, scene outside it; the region's untouched cells take the blank: 2b83f449 (`open_cell`), 494ef9d7 (`pair_line`), 4c3d4a41 (`rewritten`), 1ae2feb7 (`canvas`), 05a7bcf2 (`through`, blank = wall), 2685904e `$Repaint` (`band_cell`).
- Overlay with no vacated cells: 13f06aa5, 140c817e, 22233c11, 4938f0c2, 1e5d6875 `$Cover`, 28e73c20 `$Passthrough`, 3a301edc `$Outset`, 2685904e `$Passthrough`, 5c2c9af4, 17b866bd, 1818057f with its sibling 7e02026e.
- Blank read per vacated cell, not one value per key: 696d4842 (`vacated(P, Col)` takes the dot's color, per shape), 18286ef8 (`gaze_cell` takes the content the landing displaced — a swap).

Spec:

- Move, or erase and paint. The title says content leaves and lands; the interface, with `vacated` and `placed` independent, says erase and paint. Fifteen callers are moves and eight transfer no content. Both groups call the comp unchanged, so the interface holds; the title should name the render alone and leave the move to the caller.
- Blank per key. 696d4842 and 18286ef8 need the vacated cell's value to vary per cell; a `vacated(key, p, v)` interface takes them in, and two sites against twenty-three with a constant do not argue for it.
- The kept-set form is output-equivalent on those tasks and states a kept set where Relocate states a vacated set. The `Not:` line should name it, so a later survey does not count it.
- The two-stage form (05f2a901, 56dc2b01) is under "the rule that feeds it" in the Match line, and the coarse grep misses it: it has no `Col = C_in`. Add `in(P, Col), !<vacated>(P)` beside `<vacated>(P), params.bg(Col)` on one head to the coarse grep.

Reimplementations: none. The one hand-written step delta beside a caller (`jump_delta` over `sub_extent` in 05f2a901 and 56dc2b01) feeds a lib `Slide`, the slide-until-halted pattern.

Survey: 2026-09-10 03:32, over the solvers at or after the previous survey's time

Result: over the 334 solvers in scope, read by a parser matcher for the three-branch shape, a two-stage matcher, and the coarse grep. The sixteen listed callers in scope are unchanged in form. New callers: 456873bc `$Restore` and 673ef223, both erase-and-paint, both calling the comp unchanged; and the surfacing solver 758abdf0, a move. Near-misses in the named classes: every non-landing cell blank (456873bc `$Draw`, 45bbe264, 5751f35e `$Layers`, 48f8583b); kept set stays, everything else blank (4b6b68e5 `outline`, 08573cc6 `seed`, 5e6bbc0b `mark_cell` — a move written in the kept-set form because its two-valued scene makes every untouched cell the blank); region re-render (29623171 `tile`, 5a5a2103 `parse.tile`, 41ace6b5, 256b0a75); overlay with no vacated cells (137f0df0, 15663ba9, 1d61978c, 5168d44c, 543a7ed5, 71e489b6, 6a980be1, bdad9b1f, 5207a7b5, 1190bc91).

Spec: no interface change. 673ef223's `blank` is a state color (what a mark shows once its ray is drawn), which supports naming the render rather than the move, and a `blank` comment reading "the value a vacated cell takes when nothing lands on it". 5e6bbc0b supports naming the kept-set form on the `Not:` line.

Reimplementations: none.

Survey: 2026-09-10 07:45, over the solvers at or after the previous survey's time

Result: over the 380 solvers in scope (the 334 of the previous survey plus 46 new files), read by the previous survey's parser matchers, the coarse grep, a strict one-stage matcher (scene fixed to `in`/`ex_in`), and a matcher for a folded form (below). The eighteen listed callers in scope are unchanged in form; 825aa9e9 stands as listed. Every `out` rule of the 46 new solvers was read directly.

Callers, 5 new; none is a `// family:` sibling. All on `out`.

Moves:

- 7d7772cc — marks on the free side of a fence move along their line to the cell beside the fence or to the far edge; `rest` lands, `mark` cells clear to `free_bg.mode`, the free side's bg read from the grid; every other cell stands.
- 7acdf6d3 — loose pieces move into a container's hollow; folded form: `move` holds both the hollow cells in the pieces' color and the piece-colored input cells in bg, and `out` overlays `move` over the scene.

Erase and paint:

- 7b80bb43 — a bent chain of loose ink cells straightens: the anchor's continuation fills along `cast.clear` in the anchor's color; the rest of the chain (`cleared`) clears to a local `bg`, the pair's dominant color.
- 7e0986d6 — sprinkle cells inside a rectangle are restored to the rectangle color (`inside`), and the rest of the sprinkle clears to bg; the scene branch negates `sprinkle` alone, since `inside ⊆ sprinkle`. The repair reading of 3345333e.
- 264363fd (prior scope, missed by the earlier matchers) — a template stamps onto every marker and its tips cast rays; folded form: `paint` holds the stamps, the rays, and `tmpl(P, _), bg(Col)` (the template erased), and `out` overlays `paint` over the scene.

Near-misses (new; the earlier lists still hold):

- Every non-landing cell blank, no scene branch: 762cd429 (`copy`), 78332cb0 (`placed`, blank = `params.sep`), 7837ac64 (`block`), 794b24be (`inked`), 7c9b52a0 (`ink`), 7d18a6fb (`ink`), 80af3007 (`stamp`), 81c0276b, 1efba499 (`ink`), 2faf500b (`moved` — a move whose scene is all bg), 6ca952ad (`fallen` — likewise), 3befdf3e (`paint`).
- Kept set stays, landing, everything else blank: 782b5218 (`barrier_cell` kept, `fill_cell` lands, the other side bg), 7c66cb00 (`band_cell` kept, `landed` lands, everything else a local `bg` — a move in the kept-set form, as 5e6bbc0b). Output-equal to Relocate on every pair.
- Erase with no landing: 58f5dbd5 (`hole` cells go bg inside a crop view, the rest pass through), 7f4411dc (`square_kept` / `support_kept`: kept cells pass, everything else bg — the kept-set form with no landing). Not a named class; see Spec.
- Region re-render: 7b6016b9 (`bg_cell`: outside fill or enclosed fill, others pass), 7c8af763 (bg cells take a region or tile vote, non-bg pass), 5a719d11 (`parse.frame.tile_of` panels: paired mark or the panel's ground, cutting lines stand), 221dfab4 (`parse.corridor`: copy, beam, or bg between them).
- Overlay with no vacated cells: 7666fa5d, 770cc55f, 776ffc46, 78e78cff, 79369cc6, 79fb03f4, 7b0280bc, 7d1f7ee8, 7d419a02, 7ddcd7ec, 7df24a62, 7e2bad24, 7e576d6e, 7ec998c9, 7ed72f31, 7ee1c6ea, 800d221b, 80a900e0, 810b9b61, 817e6c09, 516b51b7; and two stamps whose footprint carries bg as stamped content — 6c434453 `$Flank` (the hole's corners print bg) and 2c737e39 (the drawing's anchor prints bg, consuming the target). A stamped blank is a landing value, not a vacated set.

Spec:

- Folded form. 7acdf6d3 and 264363fd write the vacated-to-blank rule inside the paint relation and overlay that relation over the scene: `move(P, Bg) :- fit(_, Col), in(P, Col), params.bg(Bg).` then `out(P, Col) :- in(P, Col), !move(P, _).` This is a third form beside the one-rule and two-stage forms, and neither the Match line nor the coarse grep names it; a grep for it is a rule of the overlaid relation whose value is `params.bg` or a local `bg`, beside `out(P, Col) :- in(P, Col), !<paint>(P, _)`. The folded form gives the landing no precedence over the vacated cells; both callers rely on the two sets being disjoint (the hollow is bg cells; the template lies outside the rectangles), so Relocate's `cell`, which does give precedence, renders them the same. No interface change.
- Scene branch negating the vacated set alone. In 7e0986d6 the landing lies inside the vacated set, so the scene branch is `!sprinkle` with no `!inside`; 456873bc `$Restore` restricts `placed` the same way. The Match line could allow the scene branch to negate the vacated set alone when the landing set is a subset of it.
- Derived blank. 7d7772cc reads its blank from a Mode instance (`free_bg.mode`) and 7b80bb43 and 7c66cb00 from a local `bg` derived by Mode; the coarse grep's `params.bg(Col)` anchor misses all three. The `blank` input already takes a derived value; only the grep needs widening.
- Erase with no landing. 58f5dbd5 and 7f4411dc are Relocate with an empty `placed`. The Match line's three-branch requirement leaves them out; the `Not:` line should say whether an erase alone (two branches) is this operation or not, so a later survey does not weigh it.
- Matcher gap, for later surveys: the earlier one-stage matcher inferred erase relations from any head with a scene passthrough under a negation, and then treated those heads as scenes; a landing relation whose own body reads `in` under a negation (7d7772cc `rest`) was dropped as a landing. A strict matcher fixes the scene to `in`/`ex_in`. That gap and the folded form are why 264363fd was missed in the two earlier surveys.

Reimplementations: none.
