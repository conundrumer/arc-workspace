# `Bbox.advance` — a set's own length as a displacement

A per-key readout on `Bbox`: the displacement toward `d` whose size is the set's own extent along `d`'s axis. Composed with any position, it steps that position one set-length on, so a solver that places content immediately beyond a set — the set itself moved off its own footprint, a copy stacked against it, a reflection seated past its far edge — states the placement in one atom. The known sites read the extent off the box, reselect the axis from the direction, and turn the number into a jump.

```
.decl advance(key: Key, d: Dir, delta: Shift)
advance(K, D, Delta) :- extent(K, A, N), axis_of(D, A), jump_delta(D, N, Delta).
```

Not: a jump of a stored or counted length (`jump`, `jump_delta`); a slide until contact (`Dock`); an extent used as a bound, a period, or a border width; `Bbox.margin` composed with another box's margin.

Match: a rule that binds `axis_of(D, A)` and a `Bbox` instance's `extent(_, A, N)` and feeds that `N` to `jump` or `jump_delta` toward the same `D`.

Survey: 2026-09-08 22:07

Callers:

- `5521c0d9` — `parse.moved`: each block cell carried the block's own extent, so the block sits directly beyond where it stood.
- `11dc524f` — `mirror`: the reflection's box sits one shape-length past the docked shape's box, so the two boxes meet at the mirror. The rule is the signature verbatim.
- `4acc7107` — `slot`: each next shape in a stack takes the corner one shape-depth past the shape before it, plus a gap. Direction and extent agree by construction — `stack_dir` comes from `diag_dirs` on the same axis — rather than through an `axis_of` atom.
- `22208ba4` — `moved_cell`: a corner block steps inward one block-length toward each edge of the opposite corner, as two `jump` atoms, one per axis.
- `22233c11` — `echo_cell`: a quadrant moves one quadrant-length outward along its own corner diagonal. One `jump_delta` stands for the two-axis advance only because a repeated variable states the quadrant is square.
- `447fd412` — `carry`: one step along the template corresponds to one block-side in the grid. A rewrite must keep the square guard as its own atom, since `advance` states no such thing.

Near-misses:

- Extent as a period — `53fb4810` `period`, `1ae2feb7` `claim`. The consumer takes a number, not a `Shift`. `53fb4810` is closest: its walk's first step is one band-length on.
- Extent as a margin or border width — `3a301edc` `thick.edge`, `2697da3f` `arm_depth.edge`. The result is an `Inset`.
- Extent as a bound — `3befdf3e` line 106.
- `4522001f` `sq_jump` — the operation, on a `MarginFrame` rather than a `Bbox`, with the extents from `axis_dims`. One site is not enough to move the operation off `Bbox`.
- Flush slides that jump by `Bbox.edge_min` — `05a7bcf2`, `320afe60`, `62b74c02`, `496994bd`, `20a9e565`.
- Counted lengths — `271d71e2` `advance` (an `Extremes` over a marker distance; a name collision at promotion), `8eb1be9a` `period.tally`, `12422b43` `pat_len`.

Spec question: widen `d` to `Dir8`, with the delta composed from the extent on each axis instead of one scalar. `22208ba4` and `22233c11` are corner moves that both diverge from the Dir-only form. Under it, `22208ba4` still spends three atoms for "one block-length toward the corner", and the entry's body cannot state the non-square diagonal case at all, since `jump_delta` carries one scalar to both axes. A per-axis definition gives the square case the same answer and the rectangular case the right one.
