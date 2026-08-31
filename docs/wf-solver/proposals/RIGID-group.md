# `RIGID(<group>, ...)` — rigid assemblies under a subgroup

A group argument on `RIGID`: the closure ranges `sym_member(S, D)` for the named `Sym` in place of `d4_elem`, with `SYM_D4` when the argument is omitted. Under `SYM_C4` the hand becomes data — a stored chart of the wrong hand has an orbit that misses the observed instances, and the fit diffs — while rotation stays gauge. Closing a rotate-only task over D4 instead over-generates placements the task forbids and lets the fit accept a mirrored chart.

The rest of the machinery is group-agnostic: the subgroup's elements are D4 elements, so placed column types and the column actions are unchanged, and the fit compare groups rows by whatever pose labels both sides emit — both sides close through the same generated rule. The change is the elem atom in the expansion plus the group argument in the parser. The group is a macro argument, not a Consts slot: the fit cannot derive it from the pairs, and which column types have an action depends on it (`Sense` and `Sym` are invariant under rotations and inverted by a reflection).

A task treating both hands as distinct pieces needs no new group: that is an id-keyed `SYM_C4` chart with one id per hand.

Gate: a site whose stored pieces rotate but do not reflect.

Not: achiral assemblies; assemblies that reflect; input-derived pieces closed by hand.

Match: `RIGID(`, `c4_elem`, `SYM_C4`, `d4_elem(D)`, `GRID_MASK`, `GRID_SPARSE`.

Callers: none. The RIGID sites hold achiral assemblies (142ca369, 150deff5, 21897d95) or reflect (269e22fb). 1a244afd's `turn_map` is a C4 orbit, but closing it collapses `$Table` into `$Turn`. 2697da3f pairs `SYM_C4` against `SYM_X` over input-derived cells.

Interface: a group argument, `SYM_D4` by default, as a macro argument rather than a Consts slot.

Verdict: park. 2026-08-29.
