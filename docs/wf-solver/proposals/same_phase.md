# `same_phase` — two distances in one class of a period

Two numbers sit in one class of a period when each leaves the same offset as
the other: the test a solver makes over a pair of cell distances, erosion
depths, or step indices when it asks whether the pair falls at the same point
of a repeat.

```
.decl same_phase(k1: number, k2: number, w: number) inline
same_phase(K1, K2, W) :- stride(K1, W, 0, _, R), stride(K2, W, 0, _, R).
```

Not: the offset itself, which a solver reads into a table (`stride`); the cells
a lattice identifies from a seed (`LatticeOrbit`); equality of two distances,
which holds under no period.

Match: two positive `stride` atoms of one rule sharing their offset variable,
with their inputs differing and the quotient discarded. The atoms need not
share a source line, so match over a whole rule with the parser
(`tests/test_ast_match.py`); the grep `stride\(.*stride\(` finds only the
one-line sites.

Survey: 2026-09-09 03:30

Callers:

- 5e6bbc0b `block_cell` under `$Parity` — the frame cells whose corner distance
  leaves the same residue as the mark's, which is the mark's own checkerboard
  class.
- c1990cce `echo` under `$Stripe`, and its determination mirror
  `Determine.striped` — the cells whose distance from the mirror corner leaves
  the same residue as the seed's, which are the diagonals an echo is drawn on.
  Two sites, one caller.
- 3ac3eb23 `Determine.mismatch` — rejects a candidate period that folds two
  trail steps of differing lit radius onto one slot.

Near-misses, by what each one shares:

- The period rather than the offset. 58c02a16 `phase` chains two `stride`
  atoms per axis, feeding the first atom's quotient to the second and consuming
  both residues.
- The quotient. 87ab05b8 `region` under `$Div` and `$Block`, and 54d9e175
  `same_region`, join two cells on a decomposition's tile index — the
  operation's complement.
- The offset read into a table. ba26e723 `on_stride`, 13e47133 `out`, 1c56ad9f
  `Parse.phase`, 34cfa167, 5d588b4d `place`, 221dfab4 `phase`, 516b51b7 `out`
  under `$Cycle` and `Determine.ring`, 3ac3eb23 `banner`, and 97999447
  `Determine.mask` each fold one distance and read the residue as a lookup key.
  97999447 `ray_slot` and 539a4f51 reach the same residue by walking
  `CycleWalk` from 0. 221dfab4 `Determine.phase_color`, 212895b5
  `Determine.phase_turn`, 97999447 `Determine.mismatch`, and 516b51b7
  `Determine.mismatch` key `Unanimous` by the residue and read the period break
  off `clash`.
- One quantity against the origin. 13f06aa5, 58490d8a, and 1ae2feb7 each write
  `stride(K, W, 0, _, 0)`, which has no second quantity.
- Membership in a gapped block of the repeat, with the offset discarded.
  695367ec, 22a4bbc2, d406998b, and 3bdb4ada `ink_run`.
- A within-tile Position rather than the number. 4e45f183 `out` and 363442ee
  `paint` under `$Tile` do share an offset between two cells, but the second
  atom constructs its cell from that offset instead of testing a given pair,
  and `concat` states that construction.
- A seed's class as a closure, with no residue and no number test. d492a647
  `lattice`, 834ec97d, 05269061 `known`, 017c7c7b `fill`, 3979b1a8 `out`, and
  8eb1be9a `out` run period-sized jumps to closure; 2072aba6 `checker`
  propagates the period-2 class from a corner by unit steps and carries no
  period value.
- An index folded by no period. 4aab4007 `out` under `$Uniform` joins two cells
  on a corner depth bounded by the border width.

Spec: the three arguments, the absence of a gap column, and the absence of a
residue output are what every caller needs. All three pass gap 0 to both
`stride` atoms, all three bind the shared residue to a variable that appears
nowhere else in the rule, and none reads the quotient. That the residue is
discarded at every caller is what separates the operation from `stride`.

The callers split into two kinds. The seed-class kind, 5e6bbc0b and c1990cce,
tests a cell's distance against a distinguished cell's distance; no grouping
key exists there, since the seed's residue is one value the rule must reach, so
the pair test is the form. The period-break kind tests two indices of one
demonstration for the collision a candidate period would cause, and the corpus
settles that determination with a residue-keyed `Unanimous` instead. 3ac3eb23
is the one period-break caller left, because its `differ` compares two slots'
radius sets through negation rather than two scalars, which `Unanimous` does
not express.

Folding the disagreement into the operation, as a period-break test over a
keyed set, would be a second operation rather than a change to this one:
`Unanimous` already holds it, and it needs the residue value that this
operation does not produce.
