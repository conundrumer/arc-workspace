# Stored judge command results

`judge3.result_records.load_checked_result(path, *, expected_pair_id=None,
expected_source_sha256=None)` is the read-only labeler interface. Add
`study_paths.CODE_ROOT` to the import path. It imports no native runtime,
replays nothing, computes no grade and reads no prose specification.
Paths may be absolute under DATA_ROOT or canonical DATA-relative paths.

Each new command publishes its public `result.json` and optional full TRAIN
`table.json`, then writes a private `judge-checked-envelope-v1` under
`DATA_ROOT/judgetool/dataset-runs/`. The envelope contains `pair_id`,
`source_sha256`, `operation`, `submitted_kind`, `columns`, `expected_axes`,
the public file identities, source-record identity, and `checked` (the raw,
unnormalized native checked result). `submitted_kind` is recovery for `check`,
alternative for `alternative`, and null for exploratory `run`.

The last atomic write is a `judge-result-index-v1` record under
`judgetool/dataset-result-index/`, keyed by the SHA256 of the canonical
DATA-relative public result path. It binds public result/table SHA256, private
envelope SHA256, source-record SHA256 and pair/source/operation/kind identities.
These identities are private: no hashes or execution receipts enter judge data.
The resolver does not require today's implementation bytes to equal a stored
producer hash; code changes do not retroactively invalidate old executions.

An available resolution returns:

- `schema`, `status: available`, pair/source/operation/submitted-kind and columns;
- `expected_axes`: the source-bound candidate train/test axes;
- `native_axes.candidate` and `native_axes.target`, when actually recorded by
  the evaluator, each with `required_axes`, `present_axes`, `missing_axes`;
- `checked`, including the raw outcome, comparison/context/provenance receipts,
  replay and target artifact references, and code/runtime receipts;
- `identities` for public result/table, private envelope, source record and index.

Axes are `[kept_assignment, example_kind, example_index]`, with kinds 1 TRAIN
and 2 TEST. Selected-target axes retain their own case namespace, before any
Cartesian comparator expansion. The resolver forwards native axis receipts;
it never constructs observed axes from counts. Positive checked outcomes
without required native axis receipts are unavailable through this interface.
Refused and unknown native outcomes can be authenticated without inventing
missing native table proofs.

Missing, malformed, incomplete or changed bindings return
`{schema, status: unavailable, reason}`. Public/source/op/candidate identities
are validated against the stored native checked envelope. Earlier public files
without a private index remain unindexed; this API does not promote or repair
their historical outcomes. The labeler keeps its separate legacy final-v3
reader.

This interface authenticates **one command**, not completion of a judge run.
A refused/did-not-verify result, an empty list of result references, or a model's
words cannot establish a completed negative search. The runner/labeler needs a
separate authenticated completed-answer/submission record binding the pair,
source, answer and selected checked-result references. There is no final CLI
command, and this module deliberately produces no submission/completion flag.

## Host submission boundary

The agreed host wire is `judge-submission-v1`. It contains `pair_id`,
`source_sha256`, `session_id`, host completion status
`completed|interrupted|failed`, immutable answer artifact path/SHA256,
`selected_results` (canonical DATA-relative public result path/SHA256 plus
`submitted_kind`), explicit `no_clause_found` (true exactly when the list is
empty), and the actual host termination receipt/reference. The host publishes
it atomically only after receiving the final answer.

The runner owns this producer and the authenticity of its termination evidence;
that integration requires coordinator/runner agreement before production. The
tool does not produce this record or assert host completion. The labeler resolves
every selected result, verifies bindings and preserves raw outcomes. A completed
host run can still yield Unknown when its checked evidence is unknown or missing.
An empty completed answer requires the actual host record; absence of results
is never completion evidence. No final CLI is introduced.
