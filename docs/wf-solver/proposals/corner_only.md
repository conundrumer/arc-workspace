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

Match: `!side\(` beside an 8-contact atom, plus renamed variants: the negation of a Dir-narrowed restriction of a contact relation, conjoined with that contact relation at Dir8.

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
