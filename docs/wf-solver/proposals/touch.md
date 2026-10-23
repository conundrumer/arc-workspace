# `touch` — a member of one keyed set beside a member of another

The key pairs whose sets meet side by side: a member of the first keyed set is one cardinal step from a member of the second, and the two keys are all the rule reports. It is the undirected contact test between two structures — a wire on a box, a mark on a shape, a region against the ink that walls it — where the head keeps what touched what and neither the cells nor the direction. A key may be an object id, a color, or a cell that stands for itself.

```
touch(K1, K2) :- a(K1, P), dir_elem(D), neighbor(P, D, Q), b(K2, Q).
```

The 8b7bacbf site states the step once, as the ink beside any cell, and joins it onto the marker, the objects, the background region, and the box; `contact` is the key-pair form, object against object:

```
beside(P, Q, Col) :- in(P, _), dir_elem(D), neighbor(P, D, Q), ink(Q, Col).
contact(A, B) :- object.label(_, P, A), beside(P, Q, _), object.label(_, Q, B).
live(W, M) :- marker(P, M), beside(P, _, G), object.label(G, _, W), circuit(M, W).
wall(H, P, Col) :- region.label($U(), Q, H), beside(Q, P, Col).
touch(H, W) :- box.reach(H, P), beside(P, Q, _), !box.reach(H, Q), object.label(_, Q, W).
```

Not: `Abut` (the direction from the anchor to the cell is kept); `lone` (one set against itself); `Surround` (every neighbor lies in the second set); `Closed.wall` (the closing set beside a `Closed` region, a special case of the second set); `Rim.rim_dir` (a set's own outside); a contact at range through `Ray` or `jump`; a step whose direction is bound before the step, which constructs a neighbor rather than testing contact.

Match: a rule whose body joins two different cell relations through one `neighbor` atom whose direction ranges over `dir_elem` or `dir8_elem`, with no Dir column in the head. The head keeps a key of each side, or a key of one side and a cell of the other. Grep `dir_elem(D), neighbor(` and `dir8_elem(D), neighbor(` in `programs/solvers/*.dl` and keep the rules whose two cell atoms are different relations; match with the parser.

Survey: 2026-09-10 21:59 — the whole corpus.

Callers:
8b7bacbf beside — the ink cell one cardinal step from any cell, with its color; `live`, `wall`, and `touch` join it onto the marker, the bg region, and the box, so all three contacts of the surfacing solver read through it.
182e5d0f entry — a bead cell beside a cord cell, both cells kept as their own keys; `landing` is the same operation the other way, the cord-run cell beside a plug.
195c6913 wall — the field color whose cell lies beside a swatch cell; key = color.
234bbc79 joint_of — a joint cell beside a piece, reported with the piece's id.
2b9ef948 beside_trail — a cell beside a path-colored cell; the consumers narrow it to the free color and the frame color, so it is a color class against the path.
271d71e2 Determine.frame — the non-gauge color beside a gauge cell; key = color.
3dc255db holds — object beside object over one keyed relation, the key pair kept and then filtered by size.
4364c1c4 Parse.side excluded; see near-misses.
477d2879 touches — a mark cell beside a part, with the part's key and id; `line_nbr` is a second statement, a cell beside a line cell, consumed both as mark-against-line and as line-against-line.
4ff4c9da touched — the color whose cell lies beside a mark cell, under `dir8_elem`.
543a7ed5 outline_cell — the outside bg cell beside a shape cell, under `dir8_elem`, the bg cell kept as its own key.
642248e4 Determine.grew — an input cell beside a changed cell; `no_growth` negates it per color, so it is a color class against the changed set.
71e489b6 anchor — a cluster beside a solid cell, with the cluster id and the solid cell.
753ea09b beside — a region beside a rail, ids only, the direction a wildcard (so 8-adjacent through `_step`).
7b0280bc touch — piece beside piece over one keyed relation, under `dir8_elem`, ids only; feeds a hop graph.
7b3084d4 by_color.equiv — a marker cell beside a content cell, under `dir8_elem`; the touched color's class then absorbs the marker.
7c8af763 touch — a cell beside an ink cell with its color; `region_vote.item` and `tile_vote.item` join it onto regions and tiles.
800d221b touch — a wire cell beside a region cell with its color; `center_mode.item` is a second statement, a wire cell beside a hub cell.
8886d717 around — the non-mark color beside a mark cell; consumed per cell and per cluster.
83302e8f leaky_tile — a tiling tile beside a gap cell, the tile position kept as key.
142ca369 Determine.beside_ink — a painted cell beside input ink of its own color; its negation marks the launch cell.
f0df5ff0 painted — a bg cell beside an ink cell, under `dir8_elem`, the bg cell kept as its own key.

Near-misses:
The one-step band: a set dilated by one step and clipped to the frame, the second relation the frame domain (`in`, `ex_in`, `cell`, `parse.field`, `concat_2d`) and the head keeping the band cell or painting it. No second structure is named, which the entry's "two structures" rules out — 140c817e corner_cell; 4258a5f9 halo; b60334d2 halo (three rules); dc1df850 halo; ce22a75a grown; 5117e062 region; 31aa019c footprint; 305b1341 panel; 5adee1b2 grown_box; 38007db0 block.cell; 8719f442 cell; 20fb2937 paint; 6c434453 replaced; 71e489b6 halo; 890034e9 outline; 800d221b hub; 67a423a3 ring; 5587a8d0 covers; 14754a24 footprint; 15113be4 Determine.key_block; 3aa6fb7a Determine.piece.seed; 1818057f and 7e02026e flank_covered.
`Closed.wall`: a closed region beside the set that walls it, joined onto that set's labeling — 0a2355a6 Parse.joint_holes.item; 37d3e8b2 Parse.joint_holes.item; 358ba94e cavity_count.item; 320afe60 encloses; 67e490f4 stencil; 810b9b61 wall; 184a9768 frame (the cell-level `Reach` form).
`lone` (one set against itself, no key pair kept) — 2c608aff block; 7ddcd7ec block; 88a10436 touching; 67385a82 grouped; aedd82e4 grouped; 42a50994 grouped; 3e980e27 Parse.joined; 7491f3cf Parse.line; 195c6913 swatch_cell; 72322fa7 touch (one-sided, the neighbor untested); 5792cb4d link and 7b5033c1 link (a cell-pair edge in one set); 7b80bb43 chain.
`Abut` (the direction kept) — 4364c1c4 Parse.side; 414297c0 glyph (the step kept as a Shift); 6a980be1 line_axis, 7e2bad24 wall_axis, 80214e03 separated, 65b59efc's tiling divider, and 4612dd53 line (the step's axis kept, `axis_of` with the axis free).
`Surround` (every neighbor, the second set under negation) — d9fac9be defect; d9fac9be gap; 46c35fc7 Parse.gap; 60a26a3e ring_gap; 6c434453 open.
A step whose direction is bound before the step — 49d1d64f out and 8719f442 copy (D from `dist(P, D, 0)`); 05f2a901 blocked (band then a `move_dir` step); the 17 `unfold_val`/`unfold` tile walks and the `params.*_dir` steps.
Walk steps, the neighbor a recursion frontier — 2072aba6 checker; 7ec998c9 shade; 447fd412 carry; 89565ca0 line; d492a647's period pattern.
Contact at range — 3bd292e8 across (two regions across one wall cell, the key pair kept: the touch head form at range 2).
Diagonal-only contact — 1478ab18 right_angle (a corner candidate beside a mark over `diag_dir_elem`, the corner cell kept); 1d61978c streak and 3eda0437 region (same-set over `diag_dir_elem`).
Two-sided shape tests (`flanked`, `quad`, `bend`) — 182e5d0f plug; 3ad05f52 door; 4c416de3 outline; a699fb00 flanked; 7b80bb43 flanked; 18419cfa doorway; 5ad4f10b figure; 3aa6fb7a mark; 2546ccf6 gap; 7666fa5d step; 7e0986d6 inside; 54dc2872 bend; 465b7d93 corner.

Spec:
The adjacency is data at the callers: of the 22 callers, 4ff4c9da, 543a7ed5, 7b0280bc, 7b3084d4, and f0df5ff0 step over `dir8_elem`, 753ea09b over a wildcard that also ranges the eight, and the rest over `dir_elem`. The entry states "one cardinal step" and its code form fixes `dir_elem`; a `dir` input over `dir8_elem`, narrowed by the caller as `Abut`'s survey settled for the same split, serves both groups, and 1478ab18 right_angle then joins as a `diag_dir_elem` caller.
The key pair is the head at 3dc255db, 753ea09b, 7b0280bc, and 83302e8f; every other caller keeps a cell of one side as its own key, or a color as a key, and eight keep a witness cell beside the key (182e5d0f entry, 234bbc79, 477d2879 touches, 71e489b6 anchor, 800d221b touch, 7c8af763, 8b7bacbf beside, 142ca369). Those eight fold or pass the cell downstream (a vote token, a seed, a candidate), so the head should carry the two cells beside the two keys, or the entry should state the cell-as-key reading as the way a caller keeps a cell.
The same keyed relation on both inputs (3dc255db, 7b0280bc) is a call, as D4Map with dst = src is; the entry should say so, since `lone` excludes the unkeyed self-contact and a reader may take the keyed one for it too.
The band near-misses are the largest class the signature matches (25 rules) and the Not line does not name them; a line naming the one-step band (Dilate at depth 1, Outset, the `adjacent8` proposal) as not this operation would close that reading.
The seven `Closed.wall` sites fit the touch form exactly (region id against object id, in one atom); the two entries claim them both, and one should yield.

Reimplementations: none.
Method: the parser matcher at the scratch path walked every rule of the 738 solvers and reported each positive `neighbor` atom whose direction is not a head column, tagged by what binds the direction and by whether its two endpoint cells sit in different relations, one relation, or one side only: 375 steps in 230 solvers, 96 of them with the direction from `dir_elem`, `dir8_elem`, `diag_dir_elem`, or a wildcard, 54 of those in 44 solvers joining two different relations. Each hit was read in its rule; the 87 steps whose direction comes through `opposite`, `axis_of`, `diag_dirs`, `dir_of`, `turn`, or `perp_dir` were read as well, and a grep for contact reached through `rim_dir`, `step_delta` with `compose`, `jump` at 1, and `.wall(` found no further two-set contact.
