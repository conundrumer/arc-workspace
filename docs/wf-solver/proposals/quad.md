# `quad` — the 2x2 square a cell anchors toward a corner

The three cells that complete a position's 2x2 square on one corner's side: the two cells across that corner's cardinal dirs, and the cell across the corner itself. A solver testing whether content is drawn thick, or reading a cell together with the block it sits in the corner of, names those three cells at once. The known sites write the corner's two dirs and three `neighbor` atoms from the one position.

Code form (plain relation):

```
.decl quad(p: Position, diag: DiagDir, q1: Position, q2: Position, q3: Position) inline
quad(P, G, Q1, Q2, Q3) :-
    diag_dirs(G, _, D1, D2),
    neighbor(P, D1, Q1), neighbor(P, D2, Q2), neighbor(P, G, Q3).
```

Not: `adjacent8` (the whole 8-neighborhood, one cell per direction); `bend` (set neighbors on both cardinal sides of a corner, with no cell across the corner); `corner_only` (diagonal contact with no cardinal contact); `Occurrences` against a stored 2x2 footprint; a block of a decomposition (`divide` family), whose square is fixed to a lattice rather than anchored at the cell.

Match: a rule binding one position's neighbors across a corner's two cardinal dirs and across the corner itself — three `neighbor` or `jump` atoms sharing their first argument, beside a `diag_dirs` atom. Coarse grep: `diag_dirs` in a rule with three `neighbor(` atoms. The parser scans at `.scratch/5ad4f10b/scan.py` through `scan4.py` widen that to `jump`, `compose`, and `displacement`, to the chain form, and to every corner-binding relation.

Survey: 2026-09-09 01:42

Scope: all 575 solvers, parsed and matched. Four scans found the shape: three
or more step atoms sharing a source; the same widened to `compose` and
`displacement`; three or more step atoms with any source, to catch the chain
form; and every rule binding a corner beside two or more step atoms. The
callers below are every rule any of them matched.

Near-misses:

- `465b7d93` `corner` and `54dc2872` `bend` take a corner's two cardinal
  neighbors and no cell across the corner — `bend`.
- `7f4411dc` `square_kept` is the set-level "fills a KxK square" test, built
  as `Occurrences` against a `Frame2D` footprint whose side is a parameter.
  `1fad071e` and `3b4c2228` detect squares against a stored footprint the
  same way.
- `7f4411dc` `support_kept` asks for ink neighbors in two distinct
  directions, which a straight run of three satisfies.
- `31adaf00` `bg_square` enumerates squares as the boxes that diagonal cell
  pairs span, anchored at no cell.
- `bbc9ae5d` `grown` and `49d1d64f` `out` put the corner's dir and the corner
  itself in the two branches of a disjunction, so they are alternative single
  steps rather than a conjunction over one anchor.
- `22208ba4` `moved_cell`, `4522001f` `sq_jump`, `5207a7b5` `slant`,
  `8618d23e` `grow_delta`, `4938f0c2` `img`, and `3979b1a8` `out` decompose a
  corner into its two cardinal dirs and build a delta of task-given extent
  along them, testing no cell at unit distance.

Spec questions:

- Whether the three cells arrive as one row or one row per member. No caller
  reads the two side cells apart, so the ordered five-column form is
  unwitnessed. A per-member form, `quad(p, diag, d, q)` with `d` over the
  corner's two cardinals and the corner itself, would serve `2546ccf6`
  `mirror`, which needs each member tagged with the direction that reaches it
  and writes `block_dir` (`:45-47`) to get it. Against that, the three
  callers that test the whole square hold their three membership atoms in one
  conjunction, which the per-member form turns into a universal over the
  corner's three directions.
- Whether the operation is the geometric readout or the set-level test over
  it — "this keyed cell set fills a 2x2 square". The readout covers all three
  callers; the set-level test covers only 5ad4f10b, because the other two
  test a different set at the anchor than at the other three cells, and both
  keep the anchor in the head.
- Which frame the operation reads. `2546ccf6` reads the quad over
  `DividerFrame` tile positions rather than grid cells, which the code form's
  `neighbor` already admits.

Survey: 2026-09-10 02:48 — scope: the 341 solvers `since 2026-09-09 01:42` lists. It added two callers, 71e489b6 and 142ca369: the entry's four scans, plus a lexical pass over every `diag_dirs` and `dir_of` atom in scope, matched no other rule. Near-misses: 604001fa `missing_corner` (`:36-38`) and 1e5d6875 `open_diag` (`:78-79`), an L-triomino's empty corner as the `DiagDir` absent from `Bbox.corner`, anchored at no cell; 15663ba9 `bend` (`:42-45`), arms on both edges of a corner via Rim negation and no cell across the corner; `DiagPlacement` quadrants of a box (22233c11, 4e7e0eb9, 1990f7a8, 639f5a19, 252143c9, 1f0c79e5); `Occurrences` against stored `GRID*_2x2` footprints (626c0bcc, 142ca369 and 3aa6fb7a under `$Glyph`, 409aa875, b1fc8b8e, 47c1f68c); single steps over `dir8_elem` (6c434453 `replaced`, 39e1d7f9 `footprint`, 414297c0 `glyph`); 36fdfd69 and 6ffbe589 `cluster.step`, two arbitrary Dir8 steps composed with no corner; 72322fa7 `template` under `$Line`, an opposite pair through a center; 6165ea8f `slot` (`:80-83`), a corner decomposed for an `edge_delta` of task-given extent. On the spec: 71e489b6 `solid` is a second site, with 5ad4f10b, that tests the anchor and the three members against one set, so the set-level test covers two of five callers and the readout covers all five; 142ca369 `elbow` reads the corner member apart from the two cardinal members, which the five-column form already separates, and no site reads `q1` apart from `q2`. No new frame. No reimplementations.

## Callers

- 5ad4f10b — `figure` (`:40-44`): the color drawn thick, against the color
  scattered as specks. The head keeps the color alone.
- 3aa6fb7a — `mark` under `$Corner` (`:46-50`): the empty cell that completes
  an L-triomino, with ink on the other three cells.
- 2546ccf6 — `gap` (`:52-57`): the tile a 2x2 block of tiles is missing, read
  over tile positions. The same file reads the quad again at `mirror`
  (`:68-72`), through `block_dir`.
- 71e489b6 — `solid` (`:45`): ground drawn thick, through a local `quad` in the entry's code form; a ground cell in no 2x2 block of ground is thin, and thin clusters are the hole candidates.
- 142ca369 — `elbow` (`:56-59`, with `no_arm` `:52`): the elbow of an L-triomino with the corner its arms straddle, in a split form — the two cardinal members as a universal through the `no_arm` defect over `Rim.rim_dir`, the corner member through `neighbor` tested for bg. `mark` under `$Gap` (`:61-65`) reads the anchor and its cardinal members again.

Survey: 2026-09-12 19:42 — the solvers since 2026-09-10 02:48.

Callers:
5ad4f10b `figure` (`:39-43`) — the color drawn thick, read as a cell with its three quad members in the same color's ink; the head keeps the color alone.
3aa6fb7a `mark` under `$Corner` (`:48-52`) — the empty cell that completes an L-triomino, with ink on the other three cells of the square.
2546ccf6 `gap` (`:57-63`) — the tile a 2x2 block of tiles is missing, read over tile positions; `mirror` (`:73-77`) reads the same quad through `block_dir`.
71e489b6 `quad` (`:38-41`), read by `solid` (`:45`) — a local relation in the entry's code form; ground in no 2x2 block of ground is thin, and thin clusters are the hole candidates.
142ca369 `elbow` (`:55-59`, with `no_arm` `:52`) — the elbow of an L-triomino with the corner its arms straddle, in the split form: the two cardinal members as a universal through the `no_arm` defect over `Rim.rim_dir`, the corner member through `neighbor`.
91714a58 `quad` (`:63-66`), read by `keep` under `$Thick()` (`:68-70`) — a local relation in the entry's code form, declared word for word as 71e489b6 declares it; a cell of a one-color 2x2 square is what the `$Thick` case keeps.

91714a58 is the site this scope adds. The four scans of the entry matched six rules in the scope with three or more step atoms sharing a source, nineteen with three or more step atoms under any source, and twenty-two binding a corner beside two or more step atoms; a listing of every corner-binding atom in the scope gave 260 rules, and a scan for the split form — a corner-bound step beside a solver relation carrying both the anchor and the corner variable — gave twelve. Outside the six callers, every one of those rules fell into the near-miss classes below.

Near-misses:
7e0986d6 `within` (`:60-63`) and 14b8e18c `mark` (`:77-80`) take a corner's two cardinal neighbors and no cell across the corner — `bend`.
7d7772cc `thick` (`:24-25`) is the drawn-thick test through `Rim` negation: a cell whose four cardinal neighbors all hold its color. It names no corner and its cells are not a square.
8dab14c2 `dent` (`:29-35`) steps from one cell toward an open direction, its opposite, and both perpendiculars — a cross of four cardinals, no corner.
891232d6 `onward_cell` (`:102-107`) steps from two sources along parameter-held cardinal directions, with no corner and no diagonal member.
3eda0437 `region` (`:91-94`) takes a cell and the cell across a corner and neither cardinal member — `corner_only`.
762cd429 `source` (`:67-72`) and 22208ba4 `moved_cell` decompose a corner into its two cardinal dirs and jump a task-given extent along them, testing no cell at unit distance.
4c177718 `placement` (`:142-149`) decomposes a corner to align two boxes at facing corner cells, with one step and no square.
150deff5 `occ` detects a 2x2 piece as `Occurrences` against a stored `GRID_MASK_2x2` footprint, as 7f4411dc `square_kept` detects one against a `Frame2D` footprint.
0c786b71, 3af2c5a8, 46442a0e, 47c1f68c, 62c24649, 67e8384a, 833dafe3, and b1fc8b8e each store `tile_d4` as a `GRID_2x2` table — a 2x2 tile arrangement of a decomposition, anchored at no cell.
1478ab18 `right_angle`, 1e5d6875 `copy_land`, 17b866bd `mark_block`, b60334d2 `halo`, 8cb8642d `arm_end`, 6cbe9eb8 `anchor`, 79cce52d `line_rotation`, and a3df8b1e `trace` each take a single diagonal step over an enumerated or parameter-held corner.
11e1fe23 `mini` under `$Converge` (`:81-86`) reads a `DiagPlacement` quadrant of a box and then steps one cell across that corner.

Spec:
The interface and the definition should stand as the entry states them. 91714a58 declares the five-column readout in the code form's exact words, as 71e489b6 does, and its `keep` tests all three members against one set, so no site yet reads `q1` apart from `q2`; the per-member question the 2026-09-09 survey raised gains no new site, and the two-site agreement on the five-column declaration is the strongest evidence the scope offers for the stated form. On the set-level reading, 91714a58 `keep` is a third site that tests the anchor and its three members against one set, so that reading now covers three of six callers. It still does not cover the other three, and both sites added since the readout form was written keep the anchor in the head, which a set membership test would not give; the sets also differ in their key — color at 5ad4f10b and 91714a58, and one set at 71e489b6. The readout is the form that serves every caller. 7d7772cc shows the drawn-thick concept encoded with no square at all, so the operation should stay the geometric readout and not the thickness test over it.

Reimplementations:
none.
