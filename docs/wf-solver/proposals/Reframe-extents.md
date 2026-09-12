# `Reframe.extents` — how big the outer is

The `Bbox.extents` readout on a `Reframe` outer. Not: `Bbox.extents`; whole-grid extents; a size stored as a parameter.

Match: `Reframe`, `\.inner(`, `axis_dims`, `params\.box`.

Callers: 4522001f alone. f8b3ba0a's determination was a hand-written `BoxFrame` (fixed). Reimplementations of `Bbox.extents`: 15660dd6, f25ffba3, 20270e3b (fixed). Half the `Reframe` instances have an anchor-cell outer, where the readout would silently give the grid's size; the stored-box case is a margin-size subtraction, which the `Reframe` route already states relationally.

Closed: 2026-08-30 11:53. The `Reframe` route states the stored-box case relationally, and on an anchor-cell outer the readout would silently give the grid's size.

Box (2026-09-11): `Reframe` retires into `relative`, so the route the close rested on is gone. `box_extent(b, p, a, n)` holds that route: the extent of box `b` along axis `a`, read in the frame of cell `p`. The one caller writes it — `4522001f` takes its box's two extents as `box_extent(B, P, A, K1), box_extent(B, P, A2, K2)`. The close holds on the new ground, and the hazard it named is now structural: `box_extent` binds the frame from a named cell, so no site can read the grid's size by accident. See docs/wf-solver/box.md.
