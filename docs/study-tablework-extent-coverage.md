# Extent annotation coverage and table work

The regression class was treating a column's presence in an export as a request
to evaluate another native query. Commit `070178ae` expanded extent coverage
from Box columns with made frames to every geometric scalar column. Both
`table_extents` and `body_extents` then widened and evaluated a derivation for
any Box column, including columns with a directly known input/output grid.
`direct_extents` also charged an existing Position/Offset row again while
formatting its annotation. Those charges shared the actual table evaluation's
work counter and could make unchanged programs hit its cap.

The real replay supplies an exact example: `21897d95`, `$AGlyph $BArms`, body
`[15,0]`, completes on `6108dd6e`; on `968f0e95` both native table collections
stop at form `[3]`. That form is the BoundingBox instance, whose box inherits
the input frame from its cell input. The same manifest also changes
`4e7e0eb9`, `$Whole $Blank`, gold relation tables from complete to TableWork.
These observations are in `ast/stage3-fault-{6108dd6e,968f0e95}.jsonl`.
Stage 3 calls gold tables, stream tables and pair evaluation, not the separate
continuation/admissibility operation; `62e9c85d` is not on this path.

Extent export coverage and extent derivation requests are now separate:

- `Extents.columns` remains every geometric scalar column, in native order.
- A parallel mask requests native derivation only for Box columns that lack
  a direct proof. Relation and body entry points use the same mask. Body
  gathers and component output plans keep the original full slot indices.
- Position extents come from their native margins. Box extents use an already
  declared input/output frame only where the exact example supplies it.
  Task-wide/lifted contexts without a single grid keep native derivation;
  no Example column or expected grid is guessed.
- Formatting already materialized rows charges no additional bindings, just
  as packing their native value buffer does not evaluate the rows again.
  Queries needed for unknown/made frames and their source-table lookups keep
  the original bounded work counter and report real stops.
- Direct grid evidence is cached per native example, independently of a
  different column's query stop. Native downstream extent reads and the
  emitted annotations both retain that evidence. Stops are still reported;
  missing frame evidence remains unresolved, and only positive native proof
  gives no_grid.

This removes the class at all relation/body annotation entry points, rather
than exempting a task, hiding a stop, raising the cap or suppressing a genuine
derivation. The external row/column layout and status codes are unchanged.
The separate RIGID_DET derivation contract is owned by the AST thread.

Validation requires an immutable runtime built from the landed commit, then
the same full identity manifest, work cap and gold/native-table paths as the
two baseline files. A clean compile is not a claim that the replay has passed.
