# Backlog

List of queued ideas. Sessions append on ask; one line per item.

1. Mutation lint over `.dl` solvers: delete each negated body atom (and each rule), then re-run all pairs. If a mutant survives, the data does not instantiate the deleted structure. Informational report; candidate home `run_dl.py --lint`.
2. Neighbor/adjacency utility for solver sessions — rep-side rival-claim adjacency notes and on-demand review-time similarity against a fresh draft. Machinery: `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/20957eed-3b0d-4702-b912-7e36f41b2b64/scratchpad`.
3. Further exploratory analysis of corpus structure (motif mining below hub level, walk super-family). Machinery: same scratchpad as item 2.
4. Standardization sweeps over divergences the similarity analysis found: case-enum relation naming (`impl_choice` vs `choice`/`choice_elem`), role naming across the fold family (`P_grid_out` vs `P_intile`), Consts decl+fact layout. Pick a standard per divergence, apply corpus-wide. Machinery: same scratchpad as item 2.
5. "Perceptual" detectors: an invariance test over a closed value enum (D4, Dir — at most 8 candidates) differs in kind from a detector whose hypothesis space scales with the grid dims (53b68214's period shifts via `sub_extent`, O(N) candidates). The latter reads as perception/search rather than a relation the concept has, which strains the everything-as-relations stance; lib already carries such sweeps (`Occurrences` placements, swept tile sizes via `sub_extent`). Think through whether dimension-sized detectors deserve their own status. No prescription yet.
6. Dedicated Index/Id type, to distinguish from numbers. Maybe Rank too? Purpose is to label these specific types of numbers as having fewer properties than numbers.
7. There's a pattern within rules. There's a query "head" and then there's the branch, eg in `712bf12e`, `line` has two cases. Something to think about for an abstraction on top of Datalog/Souffle.