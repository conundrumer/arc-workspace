# Mechanical reader evidence

`step4.py` reads non-DET pairs labeled fits in the base database and their original source records. It writes its own durable records under `DATA_ROOT/ast/run/mech3`. Stored native TRAIN fit and explicit complete TEST verdicts are reused. When TEST evidence is missing, `judgetool/out_fit.py:check` runs the whole mutant program with OUT and compares its TEST output against fresh full gold replay through the shared evaluator. The base labels remain read-only.

Reader comparisons preserve each actual reader's joint field projection. Any verified reader-visible difference supplies the fits-versus-extension attribute. Establishing equality requires complete reader and held/input coverage. INIT uses the component's canonical projected key-and-port input interface. Private BODY fields do not enter that interface.

DET pairs supply table projection receipts and never receive fits or extension here. Their target projection is the union of actual reader-named declared header identities. Distinct header aliases survive even when they share one BODY column. The final table grade consumes the all-target comparison and recovery evidence.

The shared TEST check selects the native OUT projection and retains the original OUT program. Complete equality with gold's full replay establishes the positive test check. Extra or differing output families retain the shared helper's Unknown or sound negative result. Reader attributes can be consumed independently of the test-fit gate.

## Shared DET receipt

Add this directory to the import path and call `det_receipt.receipt(record, exports, bindings)`. `exports` has gold and mutant native export objects. `bindings` has the corresponding canonical raw BODY bindings; these establish physical provenance and do not select the compared DET table. `side_receipt(export, raw_binding, point)` exposes the per-reader mapping independently.

The receipt schema is `mech3-det-header-projection-v1`. Each side contains the raw binding, selected header columns with scoped BODY transport, and program/export hashes. Unit insertion requires a native header certificate. Empty selection requires a complete no-reader inventory. Ambiguous or unsupported mappings raise `reader_projection.Unavailable`.

Record, program and export hashes use shared `mech/run.py:digest`: UTF-8 canonical JSON with sorted keys, compact separators, Unicode preserved and nonfinite numbers refused. The program value is the S-expression string, including its JSON string encoding. `mapper` hashes source files as raw bytes and records their absolute checkout paths.

The shared MetadataProducer remains responsible for callable formatting and row projection. This module supplies no copied graph resolver, library evaluator or renderer policy.

## Durable consumption

`store.load_step4(database, pair_id, source_sha256=..., base_result_sha256=...)` returns a validated record or an open/stale status. A valid completed Unknown is distinct from a pair with no valid record. Validation checks payload, source/base, code/config, dependency files and task-file identity. `fit_contract.apply` merges validated evidence through n-mech's reducer.

SQLite uses WAL and synchronous FULL, with a transaction per pair. Resume requires matching source, base result, labeling dependency and configuration hashes. Replay artifacts are checked against their file hashes. A separate `program_checks` journal durably records TEST checks before reader processing, allowing a reader-only code change to reuse the same test evidence. `gold_out_cache` stores the shared helper's lossless all-assignment entry transport, keyed by its program/runtime/settings/code/task identity; each pair is selected by the canonical kept matcher. The pass streams progress and writes a separate summary with grade counts, reader attributes and named missing steps.

## Run prerequisites

The checkout must contain canonical nonrender metadata, `tables.comparison_type`, the corrected canonical `tables.kept_groups` slot, held-Ident and task-scope handling, and `out_fit.check`. Final DET grades require qualified all-target evidence and the table-only reducer guard; DET records are excluded from the fits-split command.
