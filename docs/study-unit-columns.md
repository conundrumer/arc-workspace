# Zero-field INIT parameters and native table compatibility

An INIT type parameter with no binding projection and no declared bound is
an empty record. It contributes zero positions to every input and output
relation. A successful zero-position relation contains one empty tuple; it
is not an empty relation. The resolver, checked types, compiled input heads,
construction argument widths, row identity, joins and extents all use that
same representation. Export never removes columns from a populated row.

The old implementation used Unit positions for these parameters and filled
unlabeled input positions with a constant. That physical coordinate conveyed
no information. The 9613c813 extent reconstruction is no longer needed.

Unfold's private state machine stores the cursor and each item as one
handle. A zero-field parameter has a private singleton handle there, and a
parameter of several fields has a handle into the run's table of cells.
Private input decoding supplies those handles; public state/output relation
rows are constructed at their actual widths. Program relations,
body queries, INIT projections and native exported tables carry no Unit
coordinate for these bindings. Unit's term decoder remains available for
historical evidence and internal singleton handling.

Logical registry port names/ordinals, reserved stream relation slots, AST
paths and mutation identities are unchanged. Empty records have zero row
paths, while their logical port declaration remains available. The writer
writes AST sites, not Unit cells. Exact replay and reprint of the original
export streams, including model/emitter flags, is the compatibility gate;
it must not be inferred from matching token vocabulary alone.

This is a native table layout change. Corpus-v5 records produced at
5b6a14aa retain their original typed schemas, Unit cells, row widths,
offsets and interned identity namespace. Read those records using those
stored schemas, or regenerate the record entirely under the new build.
Never combine new live schemas with old stored rows or carry numeric native
IDs across sessions/builds. Render2 should show old evidence using its saved
schema; newly generated static INIT projections have only actual head
positions, with no inserted singleton cells. Start corpus-v6 only after
old-stream and historical fault replay pass on the isolated new build.

The separate v4 $Map DET corruption came from synthetic projected checked
instances paired with full FITS-assignment rows. Packing zipped mismatched
row/type arrays, discarding tails. Original checked body IR and full native
DET schemas fixed that source mismatch before corpus-v5. Packing now asserts
native relation arity equals schema arity before visiting a row, so a future
mismatch cannot silently truncate. Held historical evidence is not rewritten,
and no historical assignment is re-searched.

## Default input presence

A zero-field parameter has no key label from which a `from-key` default
can be filled. Key filling therefore matches logical non-key columns before
flattening their fields. An empty logical column prevents a default fill;
an input declaring no non-key columns (Cardinality's `domain`) still gets
one empty tuple per key. An explicitly written successful zero-field input
also still contains one empty tuple. Evaluation and provenance use the same
logical-column matcher.

Flattening before matching lost this distinction in the first zero-field
build: task 62593bfd `$Shape`, form 14, has an unbound Node parameter of
Distance and only an explicit `source_distance`. Its unwritten `source`
was accidentally filled with an empty tuple at cost zero, overriding the
written source distances and making all gold assignments fail FITS. A
real-data diagnostic on runtime-4e157d2c restores gold FITS by explicitly
making that default source empty. The matcher fixes its cause without
restoring Unit positions or special-casing Distance.

## Runtime verification

Builds use only `scripts/build_study_runtime.py` at a committed revision,
which archives the committed tree into a fresh runtime. `ast/run/CURRENT.json`
selects the runtime and Python for all corpus, export and replay checks.
Do not use the superseded Unit-specific venv build helper or assume an
existing venv contains this revision.

Use that runtime's Python for `scripts/study/check_unit_streams.py` with
`--tables` and for the exact historical mutation identity replay. Do not
start corpus-v6 until both gates and gold FITS regression checks pass.

The stream checker loads each task inventory once, reuses its native task
session, streams each result, and prints done/total, elapsed time and rate.
It verifies ids and flags both after native replay and after sexp print/read.
With `--tables` it also obtains static provenance independently of evaluation,
evaluates the full native relation tables, and rejects Unit types in table
and DET schemas. Native evaluation faults and stops remain explicit. It
refuses an existing output so a new run cannot silently overwrite evidence.
