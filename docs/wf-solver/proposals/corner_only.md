# `corner_only` — contact with a set at a corner alone

The cells that touch a keyed cell set diagonally and have no cardinal contact with it: some neighbor across a corner is in the set, and no neighbor across a side is. The known sites build it from an 8-adjacency contact relation and the negation of that relation's cardinal restriction:

```
.decl beside(p: Position, d: Dir8)
beside(P, D) :- domain(P), dir8_elem(D), neighbor(P, D, Q), set(Q).

.decl side(p: Position)
side(P) :- dir_elem(D), beside(P, D).

.decl corner_only(p: Position)
corner_only(P) :- beside(P, _, _), !side(P).
```

Not: the 8-neighborhood itself (`adjacent8`, closed: two atoms); a diagonal contact test with no cardinal exclusion; `Rim8.rim_dir` (a set cell's own exposed sides); the connectivity difference between `Components8` and `Components`.

Match: a rule that reports a cell's diagonal contact with the set and denies its cardinal contact — the contact relation at a DiagDir, conjoined with the negation of that same relation narrowed to Dir. The two stages may sit in separate rules; the cardinal side may be a relation of its own that carries no direction; and the diagonal contact may reach the set through `diag_opposite` and `neighbor` instead of through a relation with a Dir8 column. Match with the parser: first, every rule holding a negation together with an 8-contact positive — a `neighbor`, `jump`, or `diag_dirs` atom, or an atom over a relation declared with a Dir8 or DiagDir column — marking the hits whose negated relation narrows that contact to cardinals; second, the two-relation split, where the diagonal contact and the cardinal contact each sit in their own relation and the consuming rule carries neither direction.

Survey: 2026-09-08 18:34

Spec question: whether the interface carries the corner direction. `1b8318e3` reads it — the corner the block sits at is also the slide's heading — so a membership-only `corner_only(p)` does not serve that site, and the direction-bearing form `corner_only(key, p, d)` serves both, with `396d80d7` reading membership as `corner_only(Ky, P, _)`. The cell domain is an input beside the set: both sites exclude the set by their own tests (bg at `396d80d7`, non-block at `1b8318e3`). No value column: with the direction exposed, a caller re-joins its own valued relation at the reported direction. Both sites are single-set, so the keyed form has no evidence from them.

## Callers

- `396d80d7` — `corner_only`: the bg cells that touch the two-color figure at a corner alone; they witness the shell color, and the palette's other color is painted onto them.
- `1b8318e3` — `run`, second disjunct: a diagonal slide counts only when the dot rests on a cell that touches the block at the corner ahead and on no side.

## Near-misses

- The 8-neighborhood itself (`adjacent8`, closed): `5117e062` `region`.
- Diagonal contact with no cardinal exclusion: `140c817e` `corner_cell`, `b60334d2` `halo`.
- A set cell's own exposed side (`Rim8.rim_dir`): `13e47133` `sray.mark`.
- A negation that falls on something other than a cardinal contact: `15663ba9` `faces_open` (flood reach at the neighbor), `46c35fc7` `gap` (set membership at the same neighbor).
- `3a25b0d8` `side` — a name collision (which side of a midline a hole sits on), not the operation.

Survey: 2026-09-14 02:13 — the solvers since 2026-09-08 18:34.

Callers:
95990924 `corner_only` — the background cells that meet the figure's ink across a corner and on no side; the cell's corner direction names, through `diag_opposite`, the square that seats it, and the paint color follows that corner.
142ca369 `launch_cell` (in `Determine`) — a painted ray cell with no cardinal ink of its own color, whose diagonal step back lands on ink: the first cell of a ray, whose corner direction gives the ray's heading and reaches the marker behind it. The domain is the painted cells of one color in one example and the set is that example's ink of that color, so the instance is keyed by (example, color).

Near-misses:
The 8-neighborhood itself (`adjacent8`, closed): 71e489b6 `halo`, 890034e9 `outline`, d9fac9be `defect` and `gap` — the ring around a set, with no cardinal exclusion.
Diagonal contact with no cardinal exclusion: 7837ac64 `corner_mark`, 11e1fe23 `mini`.
The opposite polarity — cardinal contact required on both directions of a corner, stated as a universal through a defect: 142ca369 `elbow` (through `no_arm`), 409aa875 `apex` (through `no_arm`), 896d5239 `apex` (through `one_armed`). At 142ca369 the corner cell must be empty, which is the inverse of the corner contact this operation reports.
A negation that falls on something other than a cardinal contact with the set: 142ca369 `ray` (`!hit`, a cardinal wall test with no diagonal contact beside it), 8cb8642d `arm_end` (the next cell along the arm), 3d588dc9 `notch` (a nearer box cell).
A corner of a box, not contact with a set: 6e19193c `tip`, 604001fa `missing_corner`, 1e5d6875 `open_diag`, 470c91de `gap.item`, 93c31fbe `open_corner`.
A set cell's own exposed side (`Rim8.rim`): 8f3a5a89 `painted`, 800d221b `hub_center`.
Connectivity through a corner (`Components8`): every `Components8` instance in the scope, 33 solvers.

Spec:
The scope supports the interface the 2026-09-08 18:34 result proposed, and adds the evidence that result lacked on two points.

The key is now exercised. 142ca369 `launch_cell` runs the operation once per (example, color): the cardinal exclusion `beside_ink` and the diagonal contact both read ink of the cell's own color, and each example carries its own grid. A single-set form does not serve it, so `corner_only(key, p, d)` stands with the key exercised by a site whose sets differ across keys.

The direction column is a DiagDir. 95990924 declares `corner_only(p: Position, d: DiagDir)` and 142ca369 carries the same direction into `launch_cell(e, p_l, d: DiagDir, col)`. The 8-contact stage that the entry's code form shows at Dir8 is internal: both sites report only the corner, and 142ca369 writes no Dir8 stage at all, deriving the diagonal contact straight from `diag_opposite` and `neighbor`.

The cell domain stays an input beside the set. 95990924 excludes ink with its own `!parse.ink` test, and 142ca369's domain is the painted cells, which the input holds as background. No site derives the domain from the set.

No value column is needed. 142ca369 needs the ink cell across the corner and reaches it by re-joining `neighbor` at the reported direction, which is the re-join the direction-bearing form intends.

Reimplementations: none.
The first matcher took every rule holding a negation together with an 8-contact positive — a `neighbor`, `jump`, or `diag_dirs` atom, or an atom over a relation declared with a Dir8 or DiagDir column — and marked the hits whose negated relation narrows a contact to cardinals; it matched 106 rules across 65 of the 509 solvers, 8 of them marked. The second matcher took the two-relation split, where the diagonal contact and the cardinal contact each sit in their own relation and the consuming rule carries neither direction; it matched 1 rule, 8719f442 `out`, a tile ring with no set contact. Each hit was read in its rule.
