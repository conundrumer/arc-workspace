# `Frame2D.from` — the frame a cell already carries

Every cell of the frame that a position belongs to, per key: the caller hands over the positions it has built, and the instance hands back the whole frame those positions sit in. A solver that assembles an output frame out of placed cells, and then has to name the cells nothing placed — the blank of a canvas, the gap cells of an assembly, the cells a negation fills — reads the extent off one placed cell and feeds it straight back as an extent. The number is an intermediate no rule consumes, and it forces the caller to reselect the axis beside it.

```
.comp Frame2D<Key> {
    .decl extent(key: Key, a: Axis, n: number)  // @input

    // A cell of the frame. Its own extents fix the frame.
    .decl from(key: Key, p: Position)  // @input
    extent(K, A, N) :- from(K, P), axis_elem(A), axis_dim(P, A, N).

    .decl cell(key: Key, p: Position)
}
```

The same addition applies to `AxisFrame`, whose `extent` carries the axis column.

Not: an extent a rule derives from a count, a ratio, or a stored number, which names a size rather than reading one off a frame a cell carries; `Bbox`, which bounds a set inside the frame it sits in rather than giving that frame; `crop` and `relative`, which re-read a cell against a box; `Reframe.extents`, which reports a size as numbers for a rule to consume; `axis_dim` read for a value that some other rule compares or places.

Match: a `Frame2D` or `AxisFrame` instance whose `extent` rule reads `axis_dim` off a position bound by a positive atom of the solver's own, with `axis_elem` or a stored axis beside it, and whose `cell` output is the only consumer of that extent — the statement spans the `.init` and the one rule. Grep signature: `grep -ln 'Frame2D<\|AxisFrame<' programs/solvers/*.dl` intersected with `grep -ln 'axis_dim' programs/solvers/*.dl`, then read each instance's `extent` rule. A hand-written enumeration of a frame's cells from one member position states the operation without the instance; match that shape with the parser.
