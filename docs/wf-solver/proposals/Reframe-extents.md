# `Reframe.extents` — how big the outer is

The `Bbox.extents` readout on a `Reframe` outer. Not: `Bbox.extents`; whole-grid extents; a size stored in Consts.

Match: `Reframe`, `\.inner(`, `axis_dims`, `c\.box`.

Callers: 4522001f alone. f8b3ba0a's Fit was a hand-written `BoxFrame` (fixed). Reimplementations of `Bbox.extents`: 15660dd6, f25ffba3, 20270e3b (fixed). Half the `Reframe` instances have an anchor-cell outer, where the readout would silently give the grid's size; the stored-box case is a margin-size subtraction, which the `Reframe` route already states relationally.

Verdict: close. 2026-08-29.
