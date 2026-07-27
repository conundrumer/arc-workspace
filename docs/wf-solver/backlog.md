# Backlog

List of queued ideas. Sessions append on ask; one line per item.

2. Neighbor/adjacency utility for solver sessions — rep-side rival-claim adjacency notes and on-demand review-time similarity against a fresh draft. Machinery: `archive/corpus-analysis`.
3. Further exploratory analysis of corpus structure (motif mining below hub level, walk super-family). Machinery: same as item 2.
4. "Perceptual" detectors: an invariance test over a closed value enum (D4, Dir — at most 8 candidates) differs in kind from a detector whose hypothesis space scales with the grid dims (53b68214's period shifts via `sub_extent`, O(N) candidates). The latter reads as perception/search rather than a relation the concept has, which strains the everything-as-relations stance; lib already carries such sweeps (`Occurrences` placements, swept tile sizes via `sub_extent`). Think through whether dimension-sized detectors deserve their own status. No prescription yet.
5. There's a pattern within rules. There's a query "head" and then there's the branch, eg in `712bf12e`, `line` has two cases. And there's body sub-clauses entirely derived from consts, so conceptually it doesn't made sense to be in the body as it's not saying a per-example thing. Something to think about for an abstraction on top of Datalog/Souffle.