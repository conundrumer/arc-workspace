# `lone` — a set member that touches no other member

The cells of a keyed cell set with no cardinal neighbor in the set, and their complement, the members that touch another member. It is how a solver tells a stray dot from the body it lies beside without individuating components: the block is the ink that touches ink, and the marker is the ink that stands alone. Under 4-adjacency it coincides with `multi_cell` over the set's components, stated with no component ids.

```
.comp Lone<Key> {
    // The set, per key.
    .decl cell(key: Key, p: Position)

    // A member with a member one cardinal step away.
    .decl touching(key: Key, p: Position)
    touching(Ky, P) :- cell(Ky, P), dir_elem(D), neighbor(P, D, Q), cell(Ky, Q).

    .decl lone(key: Key, p: Position)
    lone(Ky, P) :- cell(Ky, P), !touching(Ky, P).
}
```

Not: `multi_cell` (a keyed set of more than one member, keyed by an object id); `Rim.rim_dir` and `!Rim.rim` over the set (which sides are open, and the members with no open side); `Abut` (contact between two sets, with the heading); `Surround` (walled in by another set); a contact test between a member and a second set (`beside` rules over two relations).

Match: a rule whose body joins one cell relation to itself through a single `neighbor` atom whose direction ranges over `dir_elem` and whose head keeps the first cell alone, with or without a consumer that negates it over the same set; and the same predicate stated through `Rim.rim_dir` negated over `dir_elem`, or through a `Tally` or `multi_cell` over `Components` of the set.

Survey: 2026-09-10 06:09

Result: the whole corpus, 684 solvers. Matcher at `.scratch/7ddcd7ec/lone_match.py`.

Every site derives touching positively and states lone as its negation; none derives lone directly. Of the callers, eight consume both heads, two touching only, one lone only. The `neighbor` self-join under a class enumerator is the corpus form (eight sites); `Rim.rim_dir` reaches the predicate at one site, and elsewhere only where the direction is kept; `Tally` never states it; `Unanimous`/`multi_cell` over `Components` states it at eleven sites, nine of which individuate components for other reasons, so the id-free form is what two sites (39e1d7f9, 2c737e39) would gain. Three sites key by color, which `Key` covers. No `// family:` sibling points at any site.

Survey: 2026-09-10 06:35 — scope: the solvers whose file time is at or after the line above, 7e0986d6 excluded: 264363fd, 759f3fd3, 7d419a02, 7d7772cc, 7ddcd7ec, 7df24a62, 7f4411dc, d9fac9be. Matcher at `.scratch/7e0986d6/lone_scope.py`. No new caller. The `neighbor` self-join matched at 7ddcd7ec `block` (the listed caller, unchanged), at 759f3fd3 `Determine.ring_cycle` (head keeps neither cell: it reads the output colors of a neighbor pair one ring apart), and at 7d7772cc `rest` (a gate lookup across two relations, not a self-join). Negated `rim_dir` under `dir_elem` matched at 264363fd and 7f4411dc, both keeping the direction. No `Tally`, no `multi_cell`; the one `Components` instance (264363fd `pieces`) feeds `BoxFrame` and `Mode`, so its ids serve elsewhere. Near-misses in scope: 7f4411dc `support` (now `!rim.rim_dir` over `dir_elem` with the direction kept; the earlier `neighbor` self-join form is gone); 7d7772cc `thick` and 759f3fd3 `Parse.rings.seed` (`!rim` over the set, `Rim.interior`'s reading); d9fac9be `gap` and `defect` (a grid cell whose eight neighbors all lie in a second set, the `Surround` reading). No site in scope bears on adjacency or the interface. Two sites state the `Not:` line's `Rim.interior` as `!Rim.rim` over the set, so the `Not:` line can name that lib readout instead of the proposal.

## Spec question

- **Adjacency.** Six sites state the predicate under 8-adjacency: 3e980e27, 7491f3cf, and 42a50994 through `dir8_elem`; 39e1d7f9, 2c737e39, and 1b59e163 through `Components8`. The `Rim`/`Rim8` and `Components`/`Components8` precedent (an internal `dir` relation, a `Lone8` subclass) covers both. 7b80bb43 `chain`, touching under `diag_dir_elem` alone, is a peer class under Closure and stays out.
- `Rim.interior` in the `Not:` line is a proposal, not a lib readout.

## Near-misses

- Single-cell test over `Components` whose ids the program needs elsewhere, the `multi_cell` entry's callers: 0e206a2e `part_cell`, 1b59e163 `obj_pos` (`Components8`), 2f0c5170 `alone`, 581f7754 `lone`, 54dc2872 `multi_cell`, 5af49b42 `multi_cell`, 4b6b68e5 `outline` (by color), 14b8e18c `multi_cell` (by color), 64efde09 `bar`.
- Direction kept in the head, `Rim.rim_dir`'s reading: 15663ba9 `arm`, 71e489b6 `figure_nbr`, 7f4411dc `support`, 264363fd `attached.item` (`Unanimous.value` over the direction), 642d658d `arm` and 0962bcdd `Parse.arm` (direction and neighbor color kept), 508bd3b6 `aim` (diagonal, direction alone in the head), 1d61978c `streak` (diagonal axis kept).
- Contact with a second set: 2b9ef948 `beside_trail`, 2dd70a9a `at_target`, 508bd3b6 `side_wall`, 54d82841 `walled`, f0df5ff0 `painted`, 7b3084d4 `by_color.equiv`.
- Contact between two objects (`Abut`): 3dc255db `holds`, 7b0280bc `touch`, 4364c1c4 `Parse.side`, 72322fa7 `touch`.
- 7b80bb43 `chain` — touching under `diag_dir_elem` over the loose cells, a peer class.
- 3eda0437 `region` — some two box cells a diagonal step apart, the head keeping the box key.
- No `Tally` instance reads a component's cell count against 1 or 2 for this predicate; 16de56c4 `crowded` counts line marks.

## Callers

Self-join through `neighbor`, touching derived positively and lone as its negation:

- 7ddcd7ec `block`, `!block` in `tail` — ink with an inked cardinal neighbor is the block; a tail is the ink that is not.
- 2c608aff `block`, `marker` — the block is the ink that touches ink; the marker stands alone.
- 67385a82 `grouped`, `!grouped` in `out` — grouped ink repaints; the rest keeps its color.
- aedd82e4 `grouped`, `isolated` — isolated ink takes the mark color; grouped ink the ink color under `$Repaint`.
- 195c6913 `swatch_cell`, `seed` — a legend cell touching another is a swatch; a lone one seeds a walk.
- 3e980e27 `Parse.joined`, `Parse.lone` — under `dir8_elem`.
- 7491f3cf `Parse.line`, `Parse.marker` — under `dir8_elem`.
- 42a50994 `grouped`, `!grouped` in `out` — under `dir8_elem`; `$Self` keys the set by color, `$Ink` by `Unit`.
- 88a10436 `touching`, `!touching` in `marker` — under `$Lone`, the ink that stands alone is the marker the shape's copy seats on; the touching ink is the shape.

Through `Rim.rim_dir`:

- 7e0986d6 `touching`, `!touching` in `sprinkle_color` — `!rim.rim_dir` over `dir_elem`, ink keyed by color under `$Isolated`; the color of a lone ink cell is the sprinkle color, and the other ink color is the rectangle color.
- 696d4842 `link`, `dot` — `link` is `!rim.rim_dir` over `dir_elem` keyed by color and keeps its direction for `behind` and `crawl`; `dot` is the lone head, the only part `Lone` would replace.

Through a single-cell test over `Components` whose ids serve nothing else:

- 39e1d7f9 `obj_cell` — `Unanimous<Ident, Position>` over `Components8`; `motif` reads `clash`, `seed` reads `value`.
- 2c737e39 `drawing` — hand-written `multi_cell` over `Components8`; touching head only.

Survey: 2026-09-10 20:18 — the solvers since 2026-09-10 06:35.

Callers: none new in the scope. The two callers the entry already lists are in scope and stand unchanged:
- 42a50994 `grouped`, `!grouped` in `out` — a dot with an ink cell among its eight surrounding cells stays; a lone dot becomes bg. Under `dir8_elem`; `$Self` keys the set by color, `$Ink` by `Unit`.
- 88a10436 `touching`, `!touching` in `marker` — under `$Lone`, the ink that touches no other ink is the marker the copy seats on; the touching ink is the shape. Under `dir_elem`, keyed by `Unit`.

Negative evidence. Matcher at `.scratch/surveys/lone/2026-09-10-201848/lone_scope.py`, hits at `hits.txt` beside it. The `neighbor` self-join over one cell relation matched at 42a50994 `grouped` (twice) and 88a10436 `touching` (the callers), and at 1190bc91 `seq`, 142ca369 `elbow`, 759f3fd3 `Determine.ring_cycle`, 880c1354 `border_step`, 89565ca0 `line`, and 212895b5 `Determine.entered`/`bend`, none of which keeps the first cell alone with a direction enumerator (details below). Negated `rim_dir` under `dir_elem` matched at 264363fd `attached.item` and 7f4411dc `support`, both keeping the direction. No `Tally` in scope reads a component's cell count against 1; every `Tally` over `Components` feeds a rank, an extent, or a comparison between components (412b6263 `block_n`, 84f2aca1 `region_size`, 85b81ff1 `obj_size`, 8698868d `region_count`, 89565ca0 `size`). No `Unanimous<Ident, Position>` over `Components` and no hand-written `multi_cell` in scope. A grep for `step_delta`, `jump(`, `neighbor(`, `rim_dir`, `.rim(`, and the words lone/isolated/alone/single/touch found no further statement of the predicate.

Near-misses:
- 1190bc91 `seq` — a run along D inside one component (`neighbor` self-join over `obj.label`, direction kept) plus `exposed.rim_dir` at the anchor; `marker` is the object that is not the sequence, by component id, with no single-cell test. Direction kept, and the ids serve `walk` and `area`.
- 142ca369 `no_arm`, `elbow` — `exposed.rim_dir` keyed by color, negated per corner: an ink cell with an arm on both dirs of corner G. The direction pair is kept in the head (`Rim.rim_dir`'s reading).
- 409aa875 `no_arm`, `apex` — the same shape under `Rim8` and `dir8_flank`: an ink cell with an arm on each flank of a Dir8. Direction kept.
- 13e47133 `sray.mark` — `rim.rim_dir` under `Rim8`, direction kept as the cast key.
- 264363fd `attached.item` — `!rim.rim_dir` over `dir_elem`; `Unanimous.value` over the direction gives the tip's heading. Direction kept.
- 7f4411dc `support` — `!rim.rim_dir` over `dir_elem`; `support_kept` needs two distinct directions. Direction kept.
- 759f3fd3 `Parse.rings.seed` — `!cross.rim` over the set, the `Rim.interior` reading; `Determine.ring_cycle` joins `ring` to itself through `neighbor` under `dir8_elem` but keeps neither cell.
- 142ca369 `Determine.beside_ink`, negated in `launch_cell` — a painted cell with a same-colored `ex_in` ink cell one cardinal step away. Contact with a second set.
- 8886d717 `around` — a mark cell's cardinal neighbor of a non-mark color. Contact with a second set.
- 05f2a901 `blocked($Touch)` — the cells beside the anchor, one step on along the travel. Contact with a second set, and the head keeps the neighbor.
- d9fac9be `gap`, `defect` — a grid cell whose eight neighbors all lie in a second set. The `Surround` reading.
- 880c1354 `border_step` — `in` joined to itself through `neighbor`, but the head keeps both cells: the successor along the border cycle.
- 89565ca0 `line` — two steps behind a hidden cell along D, both in the line set; the head keeps the frame color and the hidden cell. `speck` picks the color with the most pieces, with no single-cell test.
- 9565186b `$Blob` — the largest component by `Mode` over ids; the "stray cells" are the rest of that color, not lone cells.

Spec. Nothing in scope bears on the interface or the definition. Both in-scope callers fit the comp as written: `Key` covers 42a50994's color key and 88a10436's `Unit`, and both derive touching positively and state lone as its negation. On adjacency, 42a50994 is the only in-scope site under `dir8_elem`, already counted in the entry's spec question; 409aa875 and 13e47133 use `Rim8` but keep the direction, so they add nothing to the 8-adjacency count. No in-scope site states lone through `Tally` or `multi_cell`, so the id-free form gains no new caller here.

Reimplementations: none.

Survey: 2026-09-14 03:34 — the solvers since 2026-09-10 20:18.

Callers:
928ad970 `touching` — a foreground cell with another foreground cell one of its eight steps away; `mark($Lone())` is the foreground that stands alone, and `ink($Lone())` takes the color of the foreground that touches. Under `dir8_elem`, the set keyed by `Unit`, both heads consumed.
981add89 `block_cell` — an ink cell beside an ink cell of its own color belongs to a block; `mark($Isolated())` is the ink no cell of its own color joins. Under `dir_elem`, the set keyed by color through the shared color variable, the lone head consumed alone.

The six callers the entry already lists that fall in this scope stand unchanged: 3e980e27 `Parse.joined`/`Parse.lone`, 7491f3cf `Parse.line`/`Parse.marker`, 88a10436 `touching`/`marker`, 7e0986d6 `touching`/`sprinkle_color`, 39e1d7f9 `obj_cell`, 2c737e39 `drawing`.

Negative evidence. The `neighbor` self-join over one cell relation matched at 68 rules across the scope. Of those, the ones under a direction enumerator that keep the first cell alone are the two new callers above and the three listed callers 3e980e27, 7491f3cf, 88a10436; every other hit keeps the direction, keeps the second cell, or joins two relations, and each is named below. Negated `rim_dir` matched at three sites: the listed caller 7e0986d6 `touching`, and 264363fd `item` and 71e489b6 `figure_nbr`, both keeping the direction. A second pass over adjacency stated through an intermediate relation matched at 8b7bacbf `contact`, 91714a58 `keep`, 71e489b6 `solid`, 21897d95 `Parse.arrow`, 351d6448 `change`, 2ccd9fef `item`, 2546ccf6 `mirror`, and 6f473927 `Parse.place`, none of which states the predicate. No `Tally` in scope reads a member count against 1. `Unanimous<Ident, Position>` over a component labeling appears at 1b59e163, 2f0c5170, 39e1d7f9, 581f7754, and 84ba50d3; a hand-written `multi_cell` appears at 14b8e18c, 54dc2872, 5af49b42, 8b7bacbf, and 2c737e39 `drawing`.

Near-misses:
Direction kept in the head, `Rim.rim_dir`'s reading: 264363fd `attached.item`, 71e489b6 `figure_nbr`, 0962bcdd `Parse.arm`, 642d658d `arm`, 142ca369 `elbow`, 54d82841 `walled`, e1baa8a4 `boundary` (the distance kept as well), 88e364bc `arrow` (two legend cells a step apart, the heading kept).
`!Rim.rim` over the set, the interior reading the `Not:` line excludes: 135a2760 `inner_cell`, 1818057f `flanked`, 2c0b0aff `cross`, 3bdb4ada `dash_cover`, 3befdf3e `Parse.core`, 4347f46a `inner_cell`, 50cb2852 `inner_cell`, 522fdd07 `shrunk`, 58f5dbd5 `cell`, 5b37cb25 `diamond`, 689c358e `center`, 694f12f3 `inner_cell`, 759f3fd3 `Parse.rings.seed`, 7d7772cc `thick`, 7e02026e `flanked`, 800d221b `hub_center`, 917bccba `Parse.center`, bb43febb `inner_cell`.
Contact with a second set: 4ff4c9da `touched`, 7c8af763 `touch`, 800d221b `touch`, 1efba499 `touch`, 8886d717 `around`, 21897d95 `Parse.marked`, 2b9ef948 `beside_trail`, 7b3084d4 `by_color.equiv`.
Contact between two objects, the `Abut` reading: 3dc255db `holds`, 7b0280bc `touch`, 4364c1c4 `Parse.side`, 8b7bacbf `contact`.
A cell with the ring around it, the neighbor kept as the head's cell: 14754a24 `footprint`, 5adee1b2 `grown_box`, 913fb3ed `painted`, 39e1d7f9 `footprint`.
A 2x2 thickness test over a corner's three neighbors, not a single adjacency: 5ad4f10b `figure` and `speck`, 91714a58 `keep`, 71e489b6 `solid`.
Single-member test over `Components` whose ids the program needs elsewhere, the `multi_cell` entry's callers: 1b59e163 `obj_pos`, 2f0c5170 `alone`, 581f7754 `lone` and `sole`, 54dc2872 `multi_cell`, 5af49b42 `multi_cell`, 14b8e18c `multi_cell`, 64efde09 `bar`.
Single occurrence of a color over the whole grid, with no adjacency: 8b7bacbf `multi_cell` (the one cell of its color is the marker), 78e78cff `lone` (`Unanimous<Color, Position>` over every cell).
`Unanimous` over a domain that is not cells: 54d82841 `lone_free`, the bg cell whose free sides agree, over `Dir`.
72322fa7 `untouched` — a figure cell that some other cell of its figure does not touch: adjacency to every other member, not the existence of one.
16de56c4 `crowded` — marks counted per line against 1, not per cell.
3eda0437 `region` — some two box cells a diagonal step apart, the head keeping the box key.

Spec:
Nothing in scope calls for a change to the interface or the definition. Both new callers fit the comp as written: 981add89 keys the set by color and 928ad970 by `Unit`, which `Key` covers; both derive touching positively and state lone as its negation, so no site derives lone directly. 928ad970 adds a seventh site under 8-adjacency, which is caller evidence for the `Lone8` subclass the adjacency question already raises, not a new signal. Two more sites, 7d7772cc `thick` and 759f3fd3 `Parse.rings.seed`, state the `Not:` line's `Rim.interior` as `!Rim.rim` over the set, and this scope adds sixteen more of that form, so the `Not:` line should name that lib readout rather than the proposal.

Reimplementations: none.
The search ran over the parsed corpus with two matchers, one for the `neighbor` self-join and the `rim_dir` statements, one for adjacency reached through an intermediate relation and for the other `Rim` readouts, backed by name searches for `multi_cell`, `Unanimous<Ident, Position>`, and every `tally` compared against a small number. The first matcher reported 1134 lines over the 493 solvers, the second 88.
