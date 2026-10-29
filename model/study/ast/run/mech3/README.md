# Mechanical reader evidence

`step4.py` reads the base label database and original stored source records. It writes its own durable records under `DATA_ROOT/ast/run/mech3`; it performs no program replay or base relabeling. The scope is base fits pairs and DET pairs.

Reader comparisons preserve each actual reader's joint field projection. Any verified reader-visible difference supplies the fits-versus-extension attribute. Establishing equality requires complete reader and held/input coverage. INIT uses the component's canonical projected key-and-port input interface. Private BODY fields do not enter that interface.

DET pairs supply table projection receipts and never receive fits or extension here. Their target projection is the union of actual reader-named declared header identities. Distinct header aliases survive even when they share one BODY column. The final table grade consumes n-mech's all-target comparison and recovery evidence.

The program-fit gate accepts explicit complete native TRAIN and TEST accepted-output verdicts from the stored record. TRAIN fit and raw OUT equality cannot establish TEST fit. Missing proof remains Unknown with the owed step named. Reader attributes can be consumed independently of that gate.

## Shared DET receipt

Add this directory to the import path and call `det_receipt.receipt(record, exports, bindings)`. `exports` has gold and mutant native export objects. `bindings` has the corresponding canonical raw BODY bindings; these establish physical provenance and do not select the compared DET table. `side_receipt(export, raw_binding, point)` exposes the per-reader mapping independently.

The receipt schema is `mech3-det-header-projection-v1`. Each side contains the raw binding, selected header columns with scoped BODY transport, and program/export hashes. Unit insertion requires a native header certificate. Empty selection requires a complete no-reader inventory. Ambiguous or unsupported mappings raise `reader_projection.Unavailable`.

Record, program and export hashes use shared `mech/run.py:digest`: UTF-8 canonical JSON with sorted keys, compact separators, Unicode preserved and nonfinite numbers refused. The program value is the S-expression string, including its JSON string encoding. `mapper` hashes source files as raw bytes and records their absolute checkout paths.

The shared MetadataProducer remains responsible for callable formatting and row projection. This module supplies no copied graph resolver, library evaluator or renderer policy.

## Durable consumption

`store.load_step4(database, pair_id, source_sha256=..., base_result_sha256=...)` returns a validated record or an open/stale status. A valid completed Unknown is distinct from a pair with no valid record. Validation checks payload, source/base, code/config, dependency files and task-file identity. `fit_contract.apply` merges validated evidence through n-mech's reducer.

SQLite uses WAL and synchronous FULL, with a transaction per pair. Resume requires matching source, base result, labeling dependency and configuration hashes. The pass streams progress and writes a separate summary with grade counts, reader attributes, DET counts and named missing steps.

## Run prerequisites

The checkout must contain canonical nonrender metadata, `tables.comparison_type`, and the corrected canonical `tables.kept_groups` slot, held-Ident and task-scope handling. Final ordinary grades require qualified complete TEST program-fit evidence. Final DET grades require n-mech's qualified all-target evidence and table-only reducer guard. No evaluator is substituted when those proofs are unavailable.
