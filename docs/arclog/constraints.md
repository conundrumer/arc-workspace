# Constraints

The arclog forms for a choice among candidates: the `ONE` mark, which keeps one row of a relation for each value of a key, and the `CHOOSE` form, which takes exactly one candidate for each row of `for`, with pairs of candidates that are never chosen together. A **pick** is one such form, a relation's `ONE` marks or a `CHOOSE`. The two do what the Souffle lib did with `TiebreakResolutions`, `CoverForcing` and `PlacementPruning`, and they are where the output of a solver becomes a set of grids.

## One

```
(RULE &corner
  (&crop_corner *D)
  (ONE))
```

a6953f00: one of two corners.

```
(RULE &ties
  (&row *K)
  (&fewer.rank (:t *F) *R)
  (<= R K)
  (ONE K)
  (ONE F))
```

89565ca0: each chart row takes one frame with no more frames before it than the row's index, and each frame one row.

```
(RULE &ties
  (&view (:W *Key))
  (&lead_end (:C Key) *L)
  (&line_of (:P_line *S))
  (margin (:B S) (:D L) (:K *N))
  (&order.rank (:key (:C Key)) (:t *X) *R)
  (<= R N)
  (ONE Key S)
  (ONE Key X))
```

a3325580: at the lead corner that `&view` holds, each line takes one kept object no further down the order than the line's distance from the lead edge, and each object one line. Where two objects tie, each assignment of the tied objects to lines is a model.

A clause may end in `ONE` marks. A mark `(ONE <col> ...)` names key columns of the relation, and `(ONE)` names none, so it keeps one row. A relation may carry several marks. A model of the marks keeps, of the clause's rows, exactly one row for each value of each mark's key that has rows, for all marks at once. The relation is a chosen relation, and it holds the rows of one model. The mark stands on the relation, with its clause, and not at a read site, so every reader of the relation reads the same model. In the stream, the marks come with the clause's projection.

Rows are independent where no mark's key links them. A part of the rows that has no model has no rows, and the rest of the rows stand. The engine finds those parts, so the file writes no group.

## Choose

```
(CHOOSE &fill
  (for ((&cell_cand ^P))
    (from (&cell_cand P *Col)))
  (never
    (&cell_cand *P *Col)
    (&cell_cand (:P *P2) Col)
    (!= P P2)
    (axis_elem *A)
    (same_line A P (:Q P2))))

(RULE &output
  (&fill *P *Col))
```

4cd1b7b2: each row and each column holds every palette color once, and a blank takes the color that leaves it so. Each cell takes one of the colors it may take, and one color at two cells of one line is never chosen.

- `for` is a key clause, as an [instance](arclog.md#instance)'s is: the labels marked `^` are its columns, in scope in the clauses inside it, and each of its rows takes one candidate. A `CHOOSE` with no `for` clause takes one candidate.
- `from` gives each row's candidates, as an input body does. It stands inside `for` where it reads the row's labels, and after it where every row has the same candidates.
- `never` stands after `for`, reads the candidate relation twice and names a pair of candidates that no model holds together. The two atoms' row and candidate labels are the pair. A `CHOOSE` has any number of `never` clauses, none included.
- The chosen relation, `&fill`, has the row's columns then the candidate's, and the program reads it like any relation.

A pick whose every constraint is that some columns of the pick determine its row is written with [`ONE`](#one). A `CHOOSE` is written only for a pick with a `never` that is not that: 4cd1b7b2's one color never at two cells of a line, and the covers of b1fc8b8e and 446ef5d2, where a piece chosen at one cell is chosen at all its cells, or two pieces clash.

## Semantics

A model of a `CHOOSE` is a choice of one candidate for each row that has a candidate, with no `never` pair chosen. A model of a relation's `ONE` marks is as [One](#one) gives. A model of the program is a model of each `CHOOSE`, of each relation's marks, and of each `DEMONSTRATED` form's choice of one confirmed rule per key, as [Demonstrated](arclog.md#demonstrated) gives. Each chosen relation holds the rows of one model of the program, and the program's other relations are derived once per model.

A row with no candidate is absent from every model, and a key whose rows admit no joint choice has no model. A key with no model contributes no rows, and the program reads that as it reads any absence, with `NOT`: b1fc8b8e classifies ink as broken when no partition into the unit exists, and 446ef5d2 keeps the one candidate rectangle whose pieces pack it.

A `DET` reads a chosen relation only where every model gives the same value, which in the corpus is where the pick has one model: 1a244afd's pairing.

## The output set

A case's output on an input is a set of grids. The engine finds the grid columns of `&output` by testing every pair of one Position column and one Color column against `ex_output` over the train examples: the **grid columns** are the pair that matches every example. One grid is read per model, from the rows at that model, with every other column of `&output` projected away, and equal grids are one. A grid is undefined where a cell has no color or two.

Whether a case solves a pair compares the set with the pair's accepted outputs: one grid for a plain pair, several for a pair with a `tiebreak` alt. A train pair stops enumeration at the first grid outside its accepted set or past its count. On a test input, the output is the set of distinct grids over the case's models, as on any input. A test pair is solved where that set holds at most 2 grids, one of them in the pair's candidate, as [solves](../handbook/principles.md#models-and-tasks), the handbook's fit, gives: ARC-AGI scores two attempts per test output. That limit is a term of the solves relation and not of the output, and not a claim of the solver, so the arclog file never states it.

No agreement over models is supported: a claim of the form "the placements every cover holds", 50846271's `$Packed` alt, has no encoding.

## What it replaces

- `TiebreakResolutions`, the `TiebreakResolution` ADT and the `res` column on `output`. The engine builds the model, so no term carries it.
- `CoverForcing` and `PlacementPruning`, with the guards their partiality needed, `!ruled_out` and `!unplaced`, and the claim texts that described elimination. A `CHOOSE` is total: where propagation stalls, the engine searches.
- Pre-pruning written by hand beside the component, 446ef5d2's `stranded`, and a pruning followed by a tiebreak over its survivors, b7cb93ac. One `CHOOSE` does both.

Not expressible, and not needed by any solver: a constraint that is not pairwise, an optional choice, and agreement over models.

## Evidence

A run over the nine `CoverForcing` solvers, every train and test input, counting exact covers of each key's candidate set with a backtracking enumerator capped at three: every key has one cover or none, and the forced set is the cover wherever one exists. No solver relied on the component's reading-order peel to pick among covers, so the enumeration changes no output. Three solvers, b1fc8b8e, 446ef5d2 and 50846271, read a key's lack of a cover as information, which is why a key with no model is absent rather than undefined.

Across the 17 solvers that use the two components and the 4 that use `TiebreakResolutions`, a row is a cell or a piece, `never` is overlap, a line constraint, a repeated piece or a broken chain of steps, and every constraint is pairwise. On every corpus input a person solves the pick by propagation alone, and so does the engine: propagation is the first thing a model search runs, and backtracking is the fallback no corpus input reaches.

## Implementation

Souffle cannot search, but it can enumerate. A `Choose` component runs `UnitPropagation` first, which fixes what propagation fixes, and enumerates the residual as `TiebreakResolutions` enumerates assignments, filtered by `never`, under a cap that turns a residual too large into undefined. On every corpus input the residual is empty. The grid read, the dedup, the cull and the search for the grid columns are the runner's in any backend. A backend with search, an answer-set solver, runs the same semantics with no cap.
