# Constraints
- The arclog forms for a choice among candidates: the `ONE` mark, which keeps one row of a relation for each value of a key, and the `CHOOSE` form, which takes exactly one candidate for each row of `for`, with pairs of candidates that are never chosen together. A **pick** is one such form, a relation's `ONE` marks or a `CHOOSE`. They are where the output of a solver becomes a set of grids.

## One
```
(RULE &ties
  (&row *K)
  (&fewer.rank (:t *F) *R)
  (<= R K)
  (ONE K)
  (ONE F))
```
- A clause may end in `ONE` marks. A mark `(ONE <col> ...)` names key columns of the relation, and `(ONE)` names none, so it keeps one row. A relation may have several marks. A model of the marks keeps, of the clause's rows, exactly one row for each value of each mark's key that has rows, for all marks at once. The relation is a chosen relation, and it holds the rows of one model. The mark stands on the relation, with its clause, and not at a read site, so every reader of the relation reads the same model.
- Rows are independent where no mark's key links them. A part of the rows that has no model has no rows, and the rest of the rows stand. The engine finds those parts, so the file writes no group.

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
- `for` is a key clause, as [Instance](./arclog.md#instance) gives it: the labels marked `^` are its columns, in scope in the clauses inside it, and each of its rows takes one candidate. A `CHOOSE` with no `for` clause takes one candidate.
- `from` gives each row's candidates, as an input body does. It stands inside `for` where it reads the row's labels, and after it where every row has the same candidates. A `*X` or `^X` in it is refused when it makes a name that a label of the `for` clause holds.
- `never` stands after `for`, and names a pair of candidates that no model holds together. Its body reads the candidate relation, the relation of the `from` atom, at least twice. The first two reads in written order are the pair: each read's row labels and candidate labels give one candidate at one row, and a row column that a read leaves out matches every row. A later read of the candidate relation is a condition on the pair. A `CHOOSE` has any number of `never` clauses, none included.
- The chosen relation, `&fill`, has the row's columns then the candidate's, and the program reads it like any relation.
- A pick whose every constraint is that some columns of the pick determine its row is written with [One](#one). A `CHOOSE` is written only for a pick with a `never` that is not that.

## Semantics
- A model of a `CHOOSE` is a choice of one candidate for each row that has a candidate, with no `never` pair chosen. A model of a relation's `ONE` marks is as [One](#one) gives. A model of the program is a model of each `CHOOSE`, of each relation's marks, and of each `DEMONSTRATED` form's choice of one confirmed rule per key, as [Demonstrated](./arclog.md#demonstrated) gives. Each chosen relation holds the rows of one model of the program, and the program's other relations are derived once per model.
- A row with no candidate is absent from every model, and a key whose rows admit no joint choice has no model. A key with no model contributes no rows, and the program reads that as it reads any absence, with `NOT`.
- A `DET` reads a chosen relation only where the pick has one model.

## The output set
- A case's output on an input is a set of grids. The rows of the program's `OUT` form ([The OUT form](./arclog.md#the-out-form)) are the rows of the Position column and the Color column that it selects, so no column of any relation is searched for. One grid is read per model, from the rows at that model, and equal grids are one. A grid is undefined where a cell has no color or two.
- On a train input, the case's output set equals one of the pair's candidates: one grid for a plain pair, several for a pair with a `tiebreak` alt, and a second candidate for a pair with a `rule` alt. On a test input, the output is the set of distinct grids over the case's models, as on any input. A test pair accepts at most 2 grids, one of them in the pair's candidate, as the handbook's fit, which [Models and tasks](../handbook/principles.md#models-and-tasks) gives, has it: ARC-AGI scores two attempts per test output. The arclog file never states that limit.
- No agreement over models is supported: a claim about what every model holds has no encoding.
