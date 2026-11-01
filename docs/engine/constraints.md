# Constraints implementation

What the [constraints](../arclog/constraints.md) forms replace in the Souffle lib, the evidence for them, and how the engine builds their models.

The `ONE` mark and the `CHOOSE` form do what the Souffle lib did with `TiebreakResolutions`, `CoverForcing` and `PlacementPruning`.

## What it replaces

- `TiebreakResolutions`, the `TiebreakResolution` ADT and the `res` column on `output`. The engine builds the model, so no term carries it.
- `CoverForcing` and `PlacementPruning`, with the guards their partiality needed, `!ruled_out` and `!unplaced`, and the claim texts that described elimination. A `CHOOSE` is total: where propagation stalls, the engine searches.
- Pre-pruning written by hand beside the component, 446ef5d2's `stranded`, and a pruning followed by a tiebreak over its survivors, b7cb93ac. One `CHOOSE` does both.

Not expressible, and not needed by any solver: a constraint that is not pairwise, an optional choice, and agreement over models.

## Evidence

A run over the nine `CoverForcing` solvers, every train and test input, counting exact covers of each key's candidate set with a backtracking enumerator capped at three: every key has one cover or none, and the forced set is the cover wherever one exists. No solver relied on the component's reading-order peel to pick among covers, so the enumeration changes no output. Three solvers, b1fc8b8e, 446ef5d2 and 50846271, read a key's lack of a cover as information, which is why a key with no model is absent rather than undefined.

Across the 17 solvers that use the two components and the 4 that use `TiebreakResolutions`, a row is a cell or a piece, `never` is overlap, a line constraint, a repeated piece or a broken chain of steps, and every constraint is pairwise. On the inputs of the nine `CoverForcing` solvers, propagation alone solves the pick. Propagation is the first thing a model search runs, and backtracking is the fallback.

## Implementation

Souffle cannot search, but it can enumerate. A `Choose` component runs `UnitPropagation` first, which fixes what propagation fixes, and enumerates the residual as `TiebreakResolutions` enumerates assignments, filtered by `never`, under a cap that turns a residual too large into undefined. On every corpus input the residual is empty. The grid read, the dedup and the cull are the runner's in any backend. A backend with search, an answer-set solver, runs the same semantics with no cap.
