# `Matching<Key>` — unique pairing of two keyed cell sets

An edge kept when using every endpoint cell of both sets exactly once forces it, over `CoverForcing`. Not: region filling by multi-cell pieces; pairing by a functional rule; pairing from data; one-to-many.

Match: `CoverForcing`, `pair(`, `partner`, `count :.*= 1`, `forced`.

Callers: 1a244afd alone. Near: 228f6490, 18447a8d, and the determination `pair(p_in, p_out)` labelings (833966f4, e9afcf9a, 66e6c45b, 68b67ca3, ca8de6ea) pair without exclusivity and share endpoint values across sides; b7cb93ac, 89565ca0 want every bijection (`TiebreakResolutions`).

Closed: 2026-08-30 11:53. 1a244afd calls `CoverForcing` directly: lib holds the operation.
