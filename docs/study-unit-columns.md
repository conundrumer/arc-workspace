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

Unfold's private state machine still stores a scalar cursor and scalar item
handles. A zero-field parameter has a private singleton handle there.
Private input decoding supplies that handle; public state/output relation
rows are constructed at their actual zero-field widths. Program relations,
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

## Runtime verification

Run from ast. The build refuses an existing destination venv, prints the
source revision and progress, and writes `engine-revision` into the new venv.

```sh
engine/scripts/run_heavy.py --cpus 4 --need soon \
  bash engine/scripts/study/build_unit_v6.sh > run/build-unit-v6.log 2>&1

engine/scripts/run_heavy.py --cpus 12 --need soon \
  venv-s3-unit-v6/bin/python -B -u engine/scripts/study/check_unit_streams.py \
  --jobs 12 --tables --output unit-old-streams-v6.jsonl \
  > unit-old-streams-v6.log 2>&1

engine/scripts/run_heavy.py --cpus 12 --need soon \
  venv-s3-unit-v6/bin/python -B -u check_stage3_fast.py --jobs 12 \
  --case-manifest stage3-fault-replay.json --replay-identities --gold-tables \
  --output stage3-fault-unit-v6.jsonl > stage3-fault-unit-v6.log 2>&1
```

The stream checker loads each task inventory once, reuses its native task
session, streams each result, and prints done/total, elapsed time and rate.
It verifies ids and flags both after native replay and after sexp print/read.
With `--tables` it also obtains static provenance independently of evaluation,
evaluates the full native relation tables, and rejects Unit types in table
and DET schemas. Native evaluation faults and stops remain explicit. It
refuses an existing output so a new run cannot silently overwrite evidence.
