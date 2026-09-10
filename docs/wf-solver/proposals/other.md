# `other` — the other member of a two-member set

Each member of a keyed two-member set paired with the set's other member — the involution a two-color palette induces, which is how a task that exchanges two colors states its recoloring without storing a mapping. The known sites write it as a distinct-pair rule over the set, and the two-ness stays the caller's hypothesis.

```
.comp Other<Key, T> {
    .decl item(key: Key, t: T)  // input

    .decl other(key: Key, t: T, t2: T)
    other(K, A, B) :- item(K, A), item(K, B), A != B.
}
```

Not: a stored color mapping (a params table); `Unanimous` (the one value of a set); a complement against a set wider than two; a selection between the two members by a further test; a distinct pair that witnesses a property (an axis, an adjacency) without the pair itself flowing on.

Match: a rule whose body holds two atoms of one relation that differ only in the value column, joined by `!=`, and whose head pairs the two values — including the inlined form, where one side's membership holds by that relation's own rule. Grep `!= ` beside repeated same-relation atoms; `grep -nE '(C|Col)2? != (C|Col)2?' programs/solvers/*.dl` finds the color instances. The complement form carries no `!=` at all — the head's value is bound positively by the set relation and negated against the reference member — so it needs a scan of its own.

Survey: 2026-09-08 02:12
Survey: 2026-09-08 18:35 — the solvers at or after the first survey's time. It adds the callers `396d80d7`, `3a301edc`, `1f0c79e5`, and `3a25b0d8`, and its weight falls on the strict side of the spec question: at each new caller a third member makes the head multi-valued and the failure lands downstream, and `269e22fb` stays the only site strictness would constrain. No reimplementations.

Survey: 2026-09-09 06:08 — the solvers at or after the second survey's time. It adds the callers `57aa92db` and `5ad4f10b`, both in the complement form, which the grep signature misses. Its weight again falls on the strict side: at each, a third member makes the head two-valued, and every cell the caller renders then takes both colors, so the failure lands downstream. `269e22fb` stays the only site strictness would constrain. No reimplementations.

Survey: 2026-09-10 06:52 — the solvers at or after the third survey's time, 386 of them. It adds twelve callers, `782b5218` through `6df30ad6` in the list below. Its weight falls on the strict side: `4e7e0eb9` and `5117e062` pay for strictness today with a `Unanimous` instance behind the complement, which a strict `other` would absorb, as `16de56c4` pays with `!tripled`; at `782b5218`, `3ad05f52`, `444801d8`, `256b0a75`, `7e0986d6`, `6d58a25d`, and `6ecd11f4` a third member makes the head two-valued and the failure lands downstream; at `7acdf6d3` and `7b0280bc` a third member quietly weakens the rule, where strictness turns it into a failure; `6df30ad6` ranges over a closed two-member class, which the question does not reach. `269e22fb` stays the only site strictness would constrain. No reimplementations: `253bf280` `between` and `7666fa5d` `strict` hand-write a strict two-sided fold beside a `Between` instance whose inclusive fold their domains defeat, an extension of a lib comp.

Survey: 2026-09-10 06:56 — the solvers at or after the third survey's time. It adds the callers `195c6913`, `3e6067c3`, `7e0986d6`, `25d487eb`, `63613498`, `52fd389e`, `7b0280bc`, `7acdf6d3`, and `6df30ad6`, six of them in the complement form with the reference member bound before the call. Its weight again falls on the strict side: at each new caller a third member makes the head multi-valued or quietly widens it, and the failure lands downstream; no new site enumerates both roles and filters later, so `269e22fb` stays the only site strictness would constrain. `T` now ranges over Color, `Ident`, and a solver-defined `Choice` field (`6df30ad6`), which with `7ec998c9` raises whether `other` over a structural two-member class is the same operation. No reimplementations.

Spec question: whether `other` should be strict — absent when the key's set has other than two members, making the two-ness the comp's claim — or stay the distinct-pair rule, with sets of three or more yielding every distinct pair. The survey favors strictness: `16de56c4` pays for it today with a `!tripled` guard behind its pair, backed by a `Tally` instance that strictness would absorb; at `2b01abd0`, `3391f8c0`, `45737921`, `0a938d79`, and `48131b3c` a third member makes the output multi-valued, where strictness would state the two-ness as the comp's claim; at `2037f2c7` a third member quietly weakens the rule, where strictness turns it into a failure. `269e22fb` is the one site the strict form would constrain: it enumerates both role assignments and filters later, so a third member gives it candidates, not a contradiction.

## Callers

- `2b01abd0` — `swap`: the figure's two colors, each becoming the other.
- `3391f8c0` — `swap`: the two copy colors exchanged.
- `45737921` — `swap`, keyed by object id: each object's two colors exchanged.
- `0a938d79` — `other_col`: the other mark-line color, so the repeating lines alternate.
- `48131b3c` — `swapped`: each cell takes the grid palette's other color; the inlined form.
- `2037f2c7` — `only_in`: the other copy of a two-member copy set; the inlined form.
- `269e22fb` — `render`: both role assignments of the input's two colors, filtered downstream.
- `16de56c4` — `seed`: the two cells of a color's line ink, paired in both orders; the strict reading, guarded by `!tripled`.
- `396d80d7` — `core`: the figure palette's other color, relative to the shell that the corner cells witness; written as a complement against the two-member palette.
- `3a301edc` — `blk_color`: the figure palette's other color, relative to the rim color the box edge carries; the inlined form.
- `1f0c79e5` — `trail`: the block palette's other color, relative to the stored mark color; the stored member feeds the reference side.
- `3a25b0d8` — `partner`: the other of the two wall figures, over `Ident`; the inlined form.
- `57aa92db` — `body_col`, keyed by object `Ident`: the object's own color, relative to the mark color every object shares; the complement form.
- `5ad4f10b` — `speck`: the grid's other ink color, relative to the figure color the thick-drawing test picks out; the complement form.
- `6350f1f4` — `out`, in its `$Invert` case: the template's other color, relative to the color the solid blocks carry; the complement form, inlined in a disjunction branch.
- `7ec998c9` — `shade`: the other turn sense, relative to the sense a checkerboard step starts from, over the two-member Sense class; the complement form, inlined in the recursive step.
- `782b5218` — `fill_color`: the noise color, the ink palette's other color relative to the stored barrier; the complement form, the ink palette inlined as `in(_, Col), !bg(Col)`.
- `3ad05f52` — `paint`: the ink palette's other color relative to the stored wall; the complement form, palette inlined.
- `444801d8` — `seed`, keyed by box `Ident`: the box's other ink color relative to the stored wall; the complement form, palette inlined.
- `256b0a75` — `fill`: the odd bracket's color, the bracket palette's other color relative to the stored frame; the complement form.
- `4e7e0eb9` — `ink.item` under `$Blank`, keyed by section: the section's block palette's other color relative to the stored blank; the complement form, one-ness asserted by a `Unanimous` instance.
- `5117e062` — `fill.item`, keyed by `Choice`: the region palette's other color relative to the stored mark; the complement form, one-ness asserted by a `Unanimous` instance.
- `7e0986d6` — `rect` under `$Isolated`: the ink palette's other color relative to the sprinkle color the isolation test picks out; the complement form.
- `6d58a25d` — `shape_color`: the ink palette's other color relative to the marker color the multi-component test picks out; the complement form.
- `7acdf6d3` — `fit`: the pieces of the other ink color relative to the container's color; the inlined distinct-pair form, the pieces' tally supplying one side.
- `6ecd11f4` — `shape_id`, keyed by `Choice`: the other of the two objects relative to the square each case picks out, over `Ident`; the complement form.
- `7b0280bc` — `on_route`: the other end piece, over `Ident`, in both orders, each end seeding the route from the other; the distinct-pair form.
- `6df30ad6` — `nearest.cand`: the other growth, over the two-member `Grow` class of the choice point; the distinct-pair form, inlined.
- `7ee1c6ea` — `swap`, keyed by case: the two ink colors the frame holds, each becoming the other.
- `195c6913` — `corridor_cell`: the other of the two field colors, relative to the wall color the swatches sit on; the complement form, with the cell kept in the head.
- `3e6067c3` — `label_cell`/`label_color`, keyed by box `Ident`: the box's other color, relative to the box color the mode picks out; the complement form, read per cell and collapsed to one value per box.
- `25d487eb` — `mark`: the ink palette's other color, relative to the arrowhead color the mode picks out; the complement form, inlined.
- `63613498` — `twin`: the other of the two shapes holding the key's cells, relative to the key, over `Ident`; the complement form, inlined.
- `52fd389e` — `marker`, keyed by rectangle `Ident`: the rectangle's other color, relative to the stored body color; the complement form, read per cell.

## Near-misses

- Selection between the two members by a further test: `08573cc6` `other_color`, `22425bda` `hides`, `3de23699` `mark`, `16de56c4` `intruder`.
- The second value stored, not derived from the set: `3bd292e8` `other_side`.
- Complement against a set the compared value does not belong to, or wider than two: `d9fac9be` `$Ring`, `35ab12c3` `mark_shift`, `5168d44c` `move_dir`.
- A distinct pair whose atoms differ beyond the value column: `342ae2ed` `link` (facing corners), `4364c1c4` `side` (adjacency across a seam), `0becf7df` `$Line` (pairing fixed by `same_line`).
- The wide residue of the shape: a distinct same-colored pair witnessing an axis, with only the axis kept (`070dd51e`, `40853293`, `2b01abd0` `line_axis`, `2dd70a9a`, `cbded52d`, `bdad9b1f`), and existence tests where `!=` states "more than one", not "the other".

From the second survey:

- Selection between the two members by a further test: `3345333e` `occluder`/`figure`, `34cfa167` `template`/`standalone`, `2f0c5170` `glyph_mark`/`lone_mark`, `1e5d6875` `prec.before`.
- Complement against a set wider than two: `4c7dc4dd` `own`/`demo`, `4ff4c9da` `covered`, `22806e14` `rect`, `20818e16` `rect_color`.
- A distinct pair whose atoms differ beyond the value column, or over a wider set: `351d6448` `change`, `446ef5d2` `clash`, `305b1341` `above`.
- The wide residue: `291dc1e1` `overlap`, `50aad11f` `shared_line`, `22208ba4` `mover`, `358ba94e` `shared`, `2c737e39` `drawing`, `4b6b68e5` `outline`, `2dc579da` `matched`, `38007db0` `band_peer`/`grid_peer`, `3631a71a` `witnessed`.
- The other member of an orientation pair lib already holds: `2ba387bc` `stack` (`opposite`), `1d61978c` `out` (`diag_perp`); not callers, per the protocol.

From the third survey:

- Complement against a set wider than two: `89565ca0` `frame`; `4c7dc4dd` `out`, the panel that is neither of a demonstrated pair; `1c786137` and `1a6449f1` `closed.cell`, a per-color mask over the palette.
- Selection between the members by a further test: `57aa92db` `mark_col`, the palette member no object does without; `1c786137` `marker($Rect())` and `54db823b` `mark`, each a member no defect refutes.
- A distinct pair whose atoms differ beyond the value column, or over a wider set: `40f6cd08` `nested`, `6165ea8f` `tile_color`, `5dbc8537` `pruning.conflict`, `5ffb2104` `room`.
- `!=` stating something other than "the other member": `54d9e175` `mapping`, where it states "changed"; `5545f144` `blunt`, a distance comparison; `5792cb4d` `step`, excluding the cell walked from; `626c0bcc` `clash`, excluding one placement against itself.
- The wide residue: `62593bfd` `paired` and `shape_map`, `5a5a2103` `legend_tile($Twin())`, and the Determine comps where `!=` marks a changed or contradicted cell — `0dfd9992`, `54db823b`, `5614dbcf`, `5a719d11`, `5b526a93`, `5ecac7f7`, `62ab2642`, `97999447`, `54dc2872`, `5af49b42`.

From the 2026-09-10 06:52 survey:

- Selection between the members by a further test: `6cdd2623` `line_color($Border())`, `29700607` `wire`, `7d7772cc` `thick`, `6cbe9eb8` `outline`/`block`, `538b439f` `divider`, `6bcdb01e` `leg` (lib's `perp_dir`, then a rim test), `7e2bad24` `enter` (lib's `diag_opposite`, then a seed test); Determine comps where a member is the one no defect refutes — `1c56ad9f` `wave`, `46c35fc7` `corner_sense`/`edge_sense`/`move`, `2601afb7` `color_dir`, `3e980e27` `stamp_d4`, `47996f11` `axis_center`, `4c3d4a41` `shift`/`rise`, `5521c0d9` `move_dir`.
- Complement against a set wider than two: `5833af48` `plan`, `7d419a02` `ink($Derived())`, `7b0280bc` `square_color`, `36d67576` `mark_cell`, `447fd412` `block.cell`; per-id masks `445eab21`/`7d1f7ee8` `closed.cell`/`outer.cell`, `320afe60` `off_shape.cell`, `5adee1b2` `outside.node`; and the per-cell complement tests that keep a cell with its own color (`7837ac64` `mark`, `1efba499` `loose`, `6b9890af` `object_cell`, `25d487eb` `mark`, `7ed72f31` `shape`, `1c02dbbe` `paint`, `52fd389e`/`543a7ed5` `ring`, among many of the idiom).
- A distinct pair whose atoms differ beyond the value column, or over a wider set: `66ac4c3b` `marker_pair`, `78332cb0` `link`, `6aa20dc0` `pair_box.cell`, `4e34c42c` `occ.cell`/`occ.shape`, `7b0280bc` `touch`, `337b420f` `covered`, `652646ff` `front`, `7c66cb00` `band_line`, `68bc2e87` `under`, `6cbe9eb8` `nest.before`, `212895b5` `step_order.before`, `6a1e5592` `forcing.conflict`, `7b3084d4` `pruning.conflict`, `50846271` `rival`.
- The other member of an orientation pair lib already holds: `1478ab18` `right_angle` (`diag_dirs` and `opposite` compose it); not a caller, per the protocol.
- `!=` stating something else: `72322fa7` `template`, `2697da3f` `arm_depth.edge`, `195c6913` `field`, off-edge `K != 0` tests, and the Determine "changed cell" tests in `272f95fa`, `3eda0437`, `3f23242b`, `4258a5f9`, `44d8ac46`, `642248e4`, `694f12f3`, `6c434453`, `7447852a`, `7491f3cf`, `46c35fc7`.
- The wide residue: `195c6913` `on_strip`, `6d58a25d` `scattered`, `72322fa7` `untouched`, `64efde09` `bar`, `67636eac` `shared_line`, `71e489b6` `continued`/`passage`, `7b5033c1` `fork`, `7f4411dc` `support_kept`, `4e34c42c` `disagree`, Determine `281123b4`/`cf98881b` `beats`, `3eda0437` `refuted`, `47996f11` `mirror_mismatch`, `2601afb7` `dir_bad`.

From the 2026-09-10 06:56 survey:

- Selection between the members by a further test: `195c6913` `out`, `6d58a25d` `shape_color`, `7d7772cc` `pen.cell`, `7e0986d6` `sprinkle_color` and its `$Sparse` case, `7837ac64` `block`, `239be575` `joined`.
- Complement against a set wider than two: `7b0280bc` `square_color`, `5833af48` `plan`, `13e47133` `open`, `195c6913` `legend_cell`, `58490d8a` `marker`, `7d18a6fb` `marker`, `7bb29440` `marked($Body())`, `6e4f6532` `has_body`, `337b420f` `covered`, `6ad5bdfd` `room`, `2697da3f` `arm_depth.edge`, `6cbe9eb8` `block`/`outline`; `7d1f7ee8` and `445eab21` `closed.cell`, the per-color mask.
- The complement as a cell test, with the other member not flowing on: `1b60fb0c` `restored`, `4e45f183` `mark`, `7e576d6e` `gap`, `7ed72f31` `shape` (a multicolor shape works as written, so two-ness is not its claim).
- A distinct pair whose atoms differ beyond the value column, or over a wider set: `4e34c42c` `occ.cell`/`occ.shape`, `6aa20dc0` `pair_box.cell`, `66ac4c3b` `marker_pair`, `6cbe9eb8` `nest.before`, `50846271` `rival`, `72322fa7` `template`, `68bc2e87` `under`, `7c66cb00` `band_line`, `78332cb0` `link`, `1478ab18` `right_angle` (the other corner on an edge, which lib reaches through `opposite`).
- `!=` stating something other than "the other member": `7b5033c1` `step`, `212895b5` and `221dfab4` `cand`, `3eda0437` `block`.
- The wide residue: `195c6913` `field`/`on_strip`, `6d58a25d` `scattered`, `64efde09` `bar`, `71e489b6` `continued`/`passage`, `7f4411dc` `support_kept`, `753ea09b` `between`, `67636eac` `shared_line`, `652646ff`, `414297c0`, `7b5033c1` `fork`, `6a1e5592` conflicts, `7b3084d4`, `4e34c42c` `disagree`, and the Determine comps where `!=` marks a changed or contradicted cell — `2601afb7`, `272f95fa`, `281123b4`, `3e980e27`, `3eda0437`, `3f23242b`, `4258a5f9`, `44d8ac46`, `46c35fc7`, `47996f11`, `516b51b7`, `63613498`, `639f5a19`, `642248e4`, `694f12f3`, `6c434453`, `7447852a`, `7491f3cf`, `72a961c9`, `cf98881b`.
