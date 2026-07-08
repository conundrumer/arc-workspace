# Backlog

User-owned list of queued ideas. Sessions append on ask; one line per item.

## TODO

- `axis_dims(p, a, n1, n2)` — wide extent readout of Position: a line as (N, 1), a square as a repeated variable, long-axis by comparison (feca6190 `long_axis`). (2026-07-08)
- `dist_pair(p, d, k, k2)` — distances to an edge and its opposite: centered as a repeated variable (c48954c1), nearer-half in `DiagPlacement.nearer`. (2026-07-08)
- `diag_dist(p, diag, a, k1, k2)` — distances to a corner's two edges: on-diagonal as a repeated variable; collapses `Diagonal.diagonal`, `DiagPlacement.diag_cell`, `DiagRay.ray`, `corner_anchor`. (2026-07-08)
- Pointwise ≥ on Position — `Bbox.inside` becomes margin plus one comparison. (2026-07-08)
- Retire Dim: `_2d` composites take scalars; isotropic Dim Consts slots go scalar (square claim) or axis-tagged rows (rectangular claim); anisotropic slots (1fad071e `out_dim`) go rows + per-axis divide + perp glue; Dim stays only as ConstsHelpers grouping notation. (2026-07-08)
- `diag_edge_delta` proposal signature: the axis-tagged pair in place of Dim. (2026-07-08)

## Pending

- Program similarity analysis over `programs/solvers/` to find representative programs for reference. Candidate signals: Consts-shape signatures, body relation graphs. (2026-07-01)
