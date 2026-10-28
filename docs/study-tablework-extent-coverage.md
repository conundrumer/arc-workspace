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

The first coverage/derivation separation (`4223b27d`) removed double charges
and queries with a single outer example. Its replay still had 204 TableWork
records, versus 89 on `6108dd6e`. It did not cover the main task-wide case.
The separate RIGID_DET derivation contract is owned by the AST thread.

## Task-wide row context

The remaining class was losing the Example binding of a frame when the table
itself has no single outer Example. A task-wide Singleton's native key already
contains the Example that its Box's `input` frame belongs to. Treating outer
context `None` as missing proof caused recomputation of widened key/member
bodies for every such column, instead of reading that native key.

The exact saved record `4e7e0eb9`, `$Any $Blank`, body `[2,0]` completes on
`6108dd6e` and stops on `4223b27d`. The bounded comparison in
`run/tablework-one-4e7e0eb9/` shows complete row values on both builds. The
three form `[1]` Singleton tables hold Example, Axis and input-framed Box
columns (two also hold Color); only their extent derivation stops on 4223.
There are no value bounds, other bounds or Deadline stops in that comparison.
This evidence does not establish a held-stop cache defect.

`frame_context` now proves per-column row contexts from compiled source-atom
arguments. Explicit `ex_input`/`ex_output` and native lifted reads identify an
Example argument by their native schema. Its scoped LabelId must match an
actual Example column of the current native interface; all frame-contributing
sources must agree. A later native read can propagate an earlier column's
proof through its actual argument ordinal/column path. Constants remain typed
native terms and are decoded with `Term::decode(..., Example)`. Column names,
the mere presence of an Example column, and expected-output dimensions never
supply a context. Equal LabelIds in different forms cannot match.

Both relation and body masks use these proofs against the already materialized
rows. Every row with a proved context gets that exact example's declared grid
extent without re-evaluating the body. Missing, conflicting or unprojected
bindings keep the bounded native derivation path. In that path explicit
example facts also retain their Example argument; reads of task-wide source
tables can use the exact argument-constrained row proofs when no outer grid
is available. This covers direct facts, component keys, normal relation reads
and downstream copies through one proof mechanism at all annotation entry
points. Full geometric slots/status codes, positive no_grid proof priority,
native row evaluation, work caps and genuine stop reporting are unchanged.

The direct proof and bounded derivation share one implementation of source
read lookup (`read_at`), native explicit/lifted Example argument selection
(`example_argument`), scoped argument binding (`RowExample::from_argument`),
and typed Example decoding (`RowExample::get`) in `frame_context`. The
`Analysis` methods delegate to it; they do not carry a second interpretation.
This resolves duplicate-reference group G04, including nested key/OR reads,
explicit fact Example arguments and native constant arguments.

Validation requires an immutable runtime built from the landed commit, then
the same full identity manifest, work cap and gold/native-table paths as the
two baseline files. A clean compile is not a claim that the replay has passed.
