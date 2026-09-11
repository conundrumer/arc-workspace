# `Abut<Key>` — the heading a cell takes off the set it touches

The direction from an anchor cell to a cell of another set one step away from it, per key: the heading a mark stuck to an object hangs off at. That heading is which side of the anchor the mark sits on, and it is the way content leaves the mark. The anchor set is an input, so the anchored thing can be a body, a region, or a line.

```
.comp Abut<Key> {
    // The set that is hung off, per key.
    .decl anchor(key: Key, p: Position)

    // The cells that hang off it, per key.
    .decl cell(key: Key, p: Position)

    // p is one step toward d from an anchor cell.
    .decl dir(key: Key, p: Position, d: Dir)
    dir(Ky, P, D) :- anchor(Ky, Q), dir_elem(D), neighbor(Q, D, P), cell(Ky, P).
}
```

Not: `Rim.rim_dir` (one set, and the direction toward its own outside); contact with no direction (`Bbox.edge_cell` and a `neighbor` step); the converse reading, where the head reports the cell and the direction points back at the set it touches; the heading of a cell attached in exactly one direction, which folds `Unanimous` over the headings (264363fd `tip`).

Match: a rule whose head carries a Dir column and whose body joins two cell sets through one `neighbor` atom, reading the direction from the anchor to the cell, or from the cell to the anchor through `opposite`.

Survey: 2026-09-09 01:02

The signature matched 89 rules in 64 solvers. Six of them join two distinct cell sets through one `neighbor` and report the anchor-to-cell heading. A second scan, over the solvers written or edited since the first one, found no further caller.

Survey: 2026-09-10 02:12 — the solvers at or after the first survey's time, 332 of them, `6e4f6532` excluded.

The parser signature matched 45 rules in 34 solvers, and a broader net for a heading tested against a bound direction (one `neighbor` whose direction is a variable bound elsewhere, no direction column in the head) 98 more in 79 solvers. One new caller: 2f767503 `aim`. No reimplementation. The heading-tested reading that 6e4f6532 `faces` writes found no further site: the given-direction sites in scope (67c52801 `marker`, 48634b99 `fill_idx`) step from a line or a run whose direction is fixed before the step, so they construct rather than read a heading. Near-misses of the recorded kinds: contact-side (142ca369 `side_wall`, `elbow`, `Determine.launch_cell`; 1efba499 `touch`; 2b83f449 `post_side`; 396d80d7 `beside`; 46c35fc7 `parse.ring`; 508bd3b6 `side_wall`; 54d82841 `walled`; 3ad05f52 `outward_door`); single-set, 12 rules; construction, 30 rules, among them the frame-edge line stepped inward with D from `dist`; walk steps, 14 rules; contact at range (5b37cb25 `closed`, 234bbc79 `link`); a direction-dependent anchor (5c0a986e `Determine.heading`).

Survey: 2026-09-10 06:10 — the solvers whose file time is after the second survey's time, 50 of them.

The parser signature (`.scratch/7ddcd7ec/abut_match.py`) matched 49 rules in 29 solvers, 15 with a direction column in the head; a wildcard-direction pass added 753ea09b `beside`, and a grep for contact reached through `rim_dir`, `Ray.stop`, `Ray.ray` at k = 1, and `edge_cell` found no further heading read off a two-set contact. Three new callers: 7837ac64 `corner_mark`, 7b80bb43 `straight`, 7d419a02 `shade`. No contact-side site appears in the scope. Near-misses of the recorded kinds: single-set (36a08778 `stub_flow`; 7491f3cf `Parse.line`; 7b5033c1 `link`; 7b80bb43 `flanked`, `chain`; 7ddcd7ec `block`; 759f3fd3 `Parse.arm`; 4c3d4a41 `Determine.refuted_dir` and 71e489b6 `figure_nbr` through `Rim.rim_dir`); the 264363fd `tip` form (696d4842 `end`); walk steps (212895b5 `turtle`, `Determine.entered`, `Determine.bend`; 36a08778 `barred`; 696d4842 `crawl.*`; 759f3fd3 `Dilate.depth`; 7b5033c1 `step`); construction (36a08778 `mark`, `shell`; 4c3d4a41 `seat`; 6f473927 `Parse.tiles`; 73c3b0d8 `landed`; 758abdf0 `placed`; 760b3cac `mirror`; 762cd429 `anchor`; 79fb03f4 `aside`, `rejoin`, `enterable`; 7d7772cc `rest`); contact with no direction (1478ab18 `right_angle`; 71e489b6 `anchor`, `halo`; 72322fa7 `touch`; 753ea09b `beside`; 7b0280bc `touch`; 7b3084d4 `by_color.equiv`; 7c8af763 `touch`); two-sided shape tests (7666fa5d `step`; 72322fa7 `template`); contact at range (696d4842 `faces`); contact with the frame edge, a set against the frame (78332cb0 `port`; 762cd429 `grow`).

On the Dir8 domain: the scope adds a second DiagDir caller, 7837ac64 `corner_mark`, beside 7ddcd7ec `tail`, and two cardinal ones, 7b80bb43 `straight` and 7d419a02 `shade`; six of the eight contact-with-no-direction sites are Dir8 or DiagDir. A `dir` over `dir8_elem` serves all four: the DiagDir callers narrow with `diag_dir_elem`, 7b80bb43 narrows with `dir_elem` (chain cells also touch ink diagonally, and its cast is cardinal), and 7d419a02's band domain filters the off-axis steps on its own. A Dir-only `dir` serves neither DiagDir caller. On anchor identity: 7837ac64 `corner_mark` needs the anchor cell beyond the heading and keys the instance by tile to recover it, as 4364c1c4 `parse.side` keys by the other part; whether `dir` should also carry the anchor cell, as `Ray.ray` carries `src`, now has evidence at two sites. The other callers drop the anchor.

Survey: 2026-09-10 07:06 — the solvers whose file time is after the third survey's time (97999447, b1fc8b8e, b7cb93ac, bdad9b1f, d9fac9be).

The parser signature (`.scratch/80a900e0/abut_match.py`) matched 3 rules in 2 solvers, none with a direction column in the head; a wildcard-direction pass matched nothing, and a grep for contact reached through `rim_dir`, `Ray.stop`, `Ray.ray`, `edge_cell`, and the `opposite` family found no further site. b1fc8b8e and b7cb93ac hold no step atom. No new caller, and no reimplementation of the operation. Near-misses of the recorded kinds: contact with no direction (d9fac9be `defect`, `gap` — each a defect witness over the Dir8 surround of a candidate cell, the second set under negation, so the universal that negates it reads a full surround and drops the heading); construction at range (97999447 `Determine.ray_col` — a `jump` of I cells from a dot toward the stored `ray_dir`, reading the pair's color there); contact with the frame edge (bdad9b1f `line` under `$Edge` — an ink cell at `dist(P, D, 0)` casts inward along `axis_of`, the head an Axis).

On the Dir8 domain: no new caller; both contact-with-no-direction sites in the scope are Dir8, so eight of the ten such sites across the third and fourth surveys are Dir8 or DiagDir. On anchor identity: no site in the scope bears on it.

## Spec question

Whether a site that anchors on the small designated cell and finds the object one step from it computes this operation. Those rules bind the designated cell, step toward `D`, and find the object there, so their `D` runs anchor to cell, which is what `dir` derives. What separates them from 5961cc34 `port_dir` is which side holds the designated thing: there the body is the anchor and the mark is the cell. `anchor` and `cell` are both plain set inputs, so exchanging them mirrors the output through `opposite` and the interface cannot carry that separation.

Settled: they are callers, and the converse the `Not:` line names is the contact-side reading, where the head reports the cell and the direction points at the set it touches.

Whether `dir` should range over Dir8 (`dir8_elem`), with cardinal callers narrowing by `dir_elem`, as `Ray`, `Slide`, and `Rim` do. 18286ef8 `look` reads the heading from the gaze tile to the target tile, adjacent in the tile arrangement under Dir8, and 414297c0 `glyph` under `$Near` steps the key cell onto an ink cell under Dir8 and leaves as a Shift through `step_delta`; with a Dir8 `dir` both are callers, and the Dir8 contact-side sites (396d80d7 `beside`, 46c35fc7 `parse.ring`, 142ca369 `elbow`) show the same domain. Every listed caller is cardinal, so the change costs each one narrowing atom.

## Near-misses

- 271d71e2 `abut` — `box.edge_cell` supplies the direction and the stepped-to cell is tested against no second set, so the rule constructs the abutting line.
- 3d588dc9 `stem_blocks` — the anchor set is direction-dependent (the block box's d-side boundary), which a per-key anchor input cannot state.
- 446ef5d2 `anchor` — a DiagDir off `Bbox.corner`, and the head reports the anchor's corner cell.
- 56dc2b01 `move_dir` — contact at range: the mover stands off its anchor line, so the two sets never touch and the heading is read through `Ray.ray`. Its relation name repeats the caller 5623160b `move_dir`, where the piece does touch the cell it reads its heading off.
- 264363fd `tip` — `attached` joins the template set to itself, and `Unanimous` picks the cell attached in exactly one direction.
- The contact-side family, 22 rules in 22 solvers — the head reports the cell with the direction pointing at the set it touches, which differs from the anchor-to-cell heading by `opposite`. None would consume `dir` without re-applying `opposite`.
- Single-set sites, 9 rules — the heading runs between two cells of one set, which is `Rim.rim_dir`'s domain or a shape test.
- Construction sites, 7 rules — a set plus a given direction, stepped one cell, with no second-set test.
- Walk steps, 14 rules — the direction is the walk's carried heading, not read off contact.

## Callers

- 5961cc34 `port_dir` — the heading each port hangs off its object's body at, which is the heading its beam leaves on.
- 5623160b `move_dir` — the heading a piece travels, from the anchor-colored cell it touches; written with `opposite`, keyed by the piece.
- 53fb4810 `grow_dir` — the direction a band continues, from the anchor cell it rests against; written with `opposite`, keyed by the band.
- 230f2e48 `arm_dir` — the direction from the anchor-colored cell into the arm one step away, keyed by the arm.
- 4364c1c4 `parse.side` — which side of the seam a part sits on, through `opposite`. Its anchor set is per-key (the other part), so it needs a key of (Key, Ident).
- 3f23242b `Determine.arm_dir` — the direction the bracket's stalk leaves the stored seat cell. The anchor is a one-cell set.
- 2f767503 `aim` — the direction the eye looks, from the eye cell into the lens cell it touches, which the sight cast then leaves on. The anchor is a one-cell set, keyed by Unit.
- 6e4f6532 `faces` under `$Backed` — a wall-colored cell of a seated object hangs off the object's cells toward its wall; written with `opposite`, keyed by the seating, with the heading tested against the wall's direction rather than reported. The anchor set is the whole seated object, marks included.
- 73c3b0d8 `hit` — a stepped mark hangs off the wall set toward the move direction; written as a step from the mark, keyed by Unit, with the heading tested against the stored move direction rather than reported, as 6e4f6532 `faces` reads it. The anchor set is the wall cells.
- 7ddcd7ec `tail` — the diagonal a lone cell hangs off the block at, which its cast then leaves on. The anchor is the block; the heading is a DiagDir, under the Dir8 spec question.
- 7837ac64 `corner_mark` — the corner of a tile a crossing mark sits at: from a tile cell one diagonal step to the mark; written with `diag_opposite`, keyed by tile, so the head reports the tile. The heading is a DiagDir, under the Dir8 spec question.
- 7b80bb43 `straight` — the direction a chain cell continues, away from the ink it touches side on, which its cast then leaves on; written with `opposite`, keyed by Unit. The anchor is the ink set, and the chain is a subset of it.
- 7d419a02 `shade`, base rule — the side of the block's band that a neighboring band lies on, which the cone then widens along; keyed by Unit in the band frame, the anchor a one-band set. Its `band_axis(A), axis_of(D, A)` atoms restrict D to the band axis, which the band domain enforces on its own.
- 80a900e0 `rays.dir` under `$Away` — the diagonal a segment's end cell hangs off the obstacle it touches at, which its cast then leaves on; written with `diag_opposite`, keyed by the end cell. The anchor is the non-background cells. The heading is a DiagDir, under the Dir8 spec question.

Survey: 2026-09-10 14:36 — the solvers since 2026-09-10 07:06.

Method: the parser signature (`abut_match.py`, the prior survey's script over this scope) matched 43 rules in 27 of the 59 solvers, 15 with a direction column in the head; the wildcard-direction pass matched nothing; a grep for contact reached through `rim_dir`, `Ray.ray`, `Ray.stop`, `Slide.rest`, `edge_cell`, and the `opposite` family added 16 rules, all read. 23 solvers in scope hold no step or contact atom at all (0520fde7, 137f0df0, 17cae0c1, 19bb5feb, 1a6449f1, 291dc1e1, 34b99a2b, 412b6263, 44f52bb0, 668eec9a, 7c008303, 80af3007, 817e6c09, 81c0276b, 82819916, 83b6b474, 83eb0a57, 845d6e51, 846bdb03, 9565186b, 99b1bc43, b1fc8b8e, b7cb93ac); 0d87d2a6 and 22eb0ac0 hold only a `Between`, 85c4e7cd only a `Rim.depth`, none of which reads a two-set heading.

## 1. Callers

1. 7837ac64 `corner_mark` (recorded) — unchanged: the corner of a tile a crossing mark sits at, one diagonal step from a tile cell to the mark, written with `diag_opposite`.
2. 80a900e0 `rays.dir` under `$Away` (recorded) — unchanged: the diagonal a segment's end cell hangs off the touching object at, written with `diag_opposite`.
3. 84551f4c `toppled`, second rule (new) — a landed cell steps toward the stored `fall` direction and finds a standing bar's cell, which topples that bar; the heading is the stored parameter tested, not reported, exactly the form of the recorded caller 73c3b0d8 `hit` (`landed(P), params.move_dir(D), neighbor(P, D, Q), wall(Q)`). Written with anchor = landed cells and cell = bar cells, `dir` reports the bar cell and `fall`, and `bar_cell` maps it to its base. The instance sits in the positive recursion `toppled → landed → cell → dir → toppled`.
4. 142ca369 `Determine.launch_cell` (new as a caller) — the marker's aim: a ray's first painted cell, one diagonal step from same-colored input ink, keyed by (example, color); written with `diag_opposite`, the head reporting the ink cell. Survey 2 listed it among the contact-side near-misses; it has the same structure as 7837ac64 `corner_mark` (a step from the designated cell to the set it hangs off, the head reporting the anchor side), which survey 3 admitted, and the settled spec question says the anchor/cell exchange is what the interface cannot carry. The heading is a DiagDir, so it is a caller under the Dir8 spec question only.

## 2. Near-misses

1. 142ca369 `side_wall` — contact-side: the head reports the cell with `D` pointing at the wall; `hit` reads that `D` as the axis component and `leave_dir` re-applies `opposite`.
2. 142ca369 `elbow` — contact-side and a two-sided shape test: `G` names the empty corner of an L-triomino, with `!no_arm` testing both of `G`'s cardinals on the same ink cell.
3. 264363fd `tip` — recorded: `attached` is single-set, and `Unanimous` picks the cell attached in exactly one direction.
4. 56dc2b01 `move_dir`, 05f2a901 `move_dir`, 11dc524f `move_dir` — contact at range through `Ray.ray`; 3490cc26 `nearest.cand` and 1190bc91 `nearest.cand` through `Ray.stop`; 409aa875 `shot` and `Determine.launch`, 825aa9e9 `foot`, 97999447 `Determine.ray_col` through `jump` at a stored count.
5. Single-set: 1190bc91 `seq`; 42a50994 `grouped` (both rules); 89565ca0 `line`; 7ec998c9 `shade`; and through `Rim.rim_dir`: 13e47133 `sray.mark`, 142ca369 `no_arm`, 264363fd `attached.item`, 409aa875 `no_arm`, 7e0986d6 `touching`, 7f4411dc `support`, 80a900e0 `end`.
6. Construction (a set plus a given direction, stepped, no second-set test): 05f2a901 `blocked` under `$Touch` (the anchor's ring, then one step along the travel), 142ca369 `mark`, 2c181942 `seat` (the 271d71e2 `abut` form, `edge_cell` supplying the direction), 409aa875 `arrow_cell`, 56dc2b01 `back_line`, 7e576d6e `entry`, 8403a5d5 `next`, 0dfd9992 `step`, 11dc524f `mirror`, 08573cc6 `arm` (both rules), and the `jump_delta` builders 045e512c `toward`, 05f2a901 `shift`, 11dc524f `shift`, 0dfd9992 `axis_rep`, `lat_ax`.
7. Walk steps: 142ca369 `enter`; 212895b5 `turtle`, `Determine.entered`, `Determine.bend`.
8. Contact with no direction: 142ca369 `Determine.beside_ink`; 1478ab18 `right_angle`; 810b9b61 `wall`; 83302e8f `leaky_tile`; d9fac9be `defect`, `gap`.
9. Two-sided shape test: 7e0986d6 `inside`.
10. Contact with the frame edge: bdad9b1f `line` under `$Edge`; 17829a00 `move_dir` (a border cell wearing the object's color, no step); 20981f0e `clear_step` (a box margin at distance 0).

## 3. Spec

1. Dir8 domain: this scope adds a fourth DiagDir caller, 142ca369 `Determine.launch_cell`, beside 7ddcd7ec `tail`, 7837ac64 `corner_mark`, and 80a900e0 `rays.dir`, and all four of this scope's callers are DiagDir or a stored cardinal tested against the head. A `dir` over `dir8_elem` serves every caller met so far; a Dir-only `dir` serves none of the four DiagDir ones. The signal rests on four solvers across surveys, so it stands as a change, not caller-only.
2. Anchor identity: no new evidence. Both new callers fit the plain interface through the anchor/cell exchange: 84551f4c reads the bar cell as `cell` and needs no landed cell; 142ca369 `launch_cell` reads the ink cell as `cell` through `diag_opposite` and needs no painted cell. Only 7837ac64 and 4364c1c4 still need both cells.
3. Definition: no change. The two-set contact through one step, with the direction reported or tested, covers every caller in scope.

## 4. Reimplementations

Reimplementations: `/Users/davidlu/code/arc-workspace/programs/solvers/1190bc91.dl` lines 38–39 — `neighbor(P, D, P2), obj.label($U(), P2, Id)` on a 4-connected component is the negation of `exposed.rim_dir($U(), P, D)`, the `Rim` instance the same rule already reads at line 42.
