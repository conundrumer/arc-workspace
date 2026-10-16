# `box_corner_out` — the cell one diagonal step beyond a box's corner

The cell that sits diagonally outside a box at corner `d`: the box's corner cell, stepped once further along that corner's own diagonal. It is the seat content takes when it hangs off a corner, and the cell content thrown out of a box lands on. The domain is the caller's, as it is for `box_corner`, so the cell need not be occupied.

```
.decl box_corner_out(p: Position, b: Box, d: DiagDir) inline
box_corner_out(P, B, D) :- diag_opposite(D, D_back), neighbor(P, D_back, Q), box_corner(Q, B, D).
```

Not: `box_corner` (the corner cell itself); the inward peer, the cell one diagonal step inside the corner, which the same shape states with the step taken toward `d` instead of away from it; `Outset` (the whole band of a given width around a box); a step of more than one cell off the corner (`jump`); the diagonal ray out of the corner (`Ray` cast from the corner cell); a cardinal step off a box edge (`box_edge` beside `neighbor` at a Dir); `corner_anchor` against `ZERO`, which names the corner of the frame a box hugs.

Match: a rule that derives a cell from a box's corner by one diagonal step outward — a box atom, a domain atom, a corner-binding atom at a DiagDir, and `neighbor` or `jump` at that same DiagDir. The corner may be bound by `box_corner`, by `corner_anchor` against the box, or by `corner_dist(_, _, 0)` against a box read into the cell's own frame, and the step may sit in a rule of its own that takes the corner cell as an input. Match with the parser: a rule holding a corner-binding atom and a `neighbor` or `jump` atom that share both the corner cell variable and the DiagDir variable, with the step's direction equal to the corner, or equal to its `diag_opposite` when the head cell is the one that is grounded.

Survey: 2026-09-14 02:11 — every solver.

Callers:
446ef5d2 anchor — the cell one diagonal step out of a piece's box corner, read as the seat of the mark that labels that piece.
4938f0c2 img — the seat one step out of the block's corner on the quadrant an object lies past, which the object's transformed offset is composed onto.
5c0a986e heading — inside its Determine comp, the cell one step past a color block's corner, tested for new ink to determine that color's diagonal heading.
66e6c45b target — under the `$Explode()` case, the output cell each shape cell takes, one diagonal step out of the shape box's corner.
85fa5666 seat — the cell one diagonal step out of each square's box at corner D, keyed by square and corner.
95990924 seat — the same cell, with the square's box from a `Bbox` instance, kept only where it stays inside the frame.
952a094c outer — the same cell, with the step in its own rule that takes the corner cell from the `corner` relation beside it.

The shape signature matched 9 rules in 9 solvers across the corpus; 6 of those are callers, 3 are near-misses below. A second pass over the cross-rule form — every `neighbor`/`jump` whose direction variable is a DiagDir, 43 atoms in all — added 952a094c and no other. None of the seven carries a `representative:` line, so each is its own family.

Near-misses:
The inward peer, one diagonal step from the corner toward the box's inside: 952a094c inner and 6cbe9eb8 anchor, both written as `diag_opposite` before the step. The entry's Not line rules it out.
A cardinal step off a corner cell: 4c177718 placement steps toward the arrow's heading from a `corner_anchor` corner, and 79cce52d line_rotation steps inward along one axis of the corner from a `corner_dist` corner. The step is at a Dir, not the corner's own diagonal.
The step leaves a cell other than the corner-bound one: 11e1fe23 mini, where the corner of the mark's box gives only the direction and the step starts at the box's center; 49d1d64f out, where the corner test is on the input cell and the step starts at that cell's image under the seat frame change, beside a cardinal branch of the same shape.
A diagonal step from a lone cell, with no box: 140c817e corner_cell and 1478ab18 right_angle enumerate all four diagonals off a mark; 7837ac64 corner_mark steps off a mark to name the tile its corner faces; 1e5d6875 copy_land steps off every piece cell; 11e1fe23 mini under `$Cross()` steps back from the meeting cell toward a mark; 71e489b6 quad, 91714a58 quad, 3aa6fb7a mark and 5ad4f10b figure take the corner cell of a 2x2 block, which `quad` covers.
17b866bd mark_block jumps a line-width off a mark, which is both a step of more than one cell and no box corner.
The rest of the 43 diagonal steps are walk steps — 28e73c20 walk, a3df8b1e trace, bbc9ae5d grown and the like — where the direction is the walk's heading and no corner is bound.

Spec:
The code form's grounding is backward for most sites, so the interface should expose the corner cell. `neighbor` computes its target from a grounded source and `box_corner` tests a grounded cell, so `box_corner_out(P, B, D)` as written binds nothing unless the caller grounds P, the outward cell. Four of the seven callers ground only the corner cell and want the outward cell produced: 4938f0c2 img, 66e6c45b target, 85fa5666 seat and 952a094c outer. Three ground both: 446ef5d2 anchor through `in(Q, Col)`, 5c0a986e heading through `new_ink`, 95990924 seat through `cell(Ky, Q, _)`. None grounds the outward cell alone. A four-column form — the corner cell, the box, the corner, the outward cell, stated as `box_corner(P, B, D), neighbor(P, D, Q)` — serves all seven, keeps the domain with the caller exactly as `box_corner` does, and lets the three that also want the outward cell in a domain keep their own atom. It also drops the `diag_opposite` atom the current form needs.

The same producing-against-testing gap shows outside the callers: 1478ab18 corner_cell builds the corner cell of the box two marks span by composing one cell's along component with the other's across component, because lib states a box corner only as a test. `Bbox.corner_cell` records that gap for the keyed case.

Every caller's box comes from a `Bbox` instance: pbox in 446ef5d2, block in 4938f0c2, bx in 5c0a986e, bb in 66e6c45b and 952a094c, bbox in 85fa5666, sbox in 95990924. The Box-typed form is therefore not exercised over a box from any other source. That is what the corpus shows, and it is not an argument to key the operation.

Reimplementations: none.

The two matchers ran over the parsed corpus under the survey's scratch path: the first pairs a corner-binding atom with a `neighbor`/`jump` atom sharing a cell variable, reporting whether the directions are linked, and the second lists every `neighbor`/`jump` whose direction variable is bound as a DiagDir, for the cross-rule form. A third matcher looked for the offset statement — a corner-binding atom with `step_offset` or `jump_offset` at the corner's direction — and found no rule.
