# Mechanical reader and TEST facts

`step4.py` processes base-label fits pairs outside DET. It uses the shared evaluator for missing whole-mutant TEST OUT evidence and the canonical metadata/projector/comparator for reader-visible differences. The base database remains read-only. Normal-form exclusion belongs to the study at read time.

## Store

The database is `DATA_ROOT/ast/run/mech3/step4.sqlite3`. New writes contain only this pass's facts and their provenance:

- `records`: one reader fact per pair. Schema `mech3-reader-fact-v2` contains `read_difference` (bool or null), an unavailable reason or witness reader sites, and an input-task reference. Source/base bindings and producer identities occupy table columns.
- `test_facts`: the independently acquired `fits_test` (bool or null), an unavailable reason, and replay observation references. It stores no TRAIN verdict or copied base result.
- `objects`: deduplicated replay references, execution contexts and task input receipts. Native output rows remain in the evaluator's replay artifacts.
- `producers`: code/config provenance once per producer. It is not compared against whichever code currently happens to be checked out.

Legacy `records`, `program_checks` and `gold_out_cache` remain readable in place. New results do not write grades, class aliases, summary files, copied source/base records or gold row transports. Operational progress prints to stderr. The deprecated `--summary` argument is accepted without writing a file.

## Read API

Package-safe `mech3.store.load_step4(database, pair_id, *, source_sha256, base_result_sha256, task_sha256=None)` returns done/open, valid, `record`, `facts`, `reference`, `result_sha256` and an optional `test_reference`. The ephemeral record exposes top-level `read_difference` and `fits_test` with the pair/source/base binding. Unknown reasons are `reader_problem` and `test_problem`. `facts` is the authoritative stored hash envelope; the joined view is not another stored result.

Legacy grade/program/reader aliases are projected to those same raw fields. Legacy grades are never used. `fit_contract.apply` and `det_targets.apply_det_targets` return raw evidence only. The canonical shared read entry point owns the grade.

## Resume and explicit retries

Validity uses pair/source/base inputs, task input bytes when supplied, and actual fact/reference hashes. Code, configuration and historical document hashes remain integrity/provenance; unrelated code edits, changed checkout paths or task-path spelling do not invalidate completed facts. New runs use pinned snapshot worktrees.

The default resumes completed attempts, including unavailable results. `--retry-reader-unknown` explicitly revisits only unresolved reader facts. `--retry-test-unknown` explicitly revisits unresolved TEST facts. `--rerun-reader` and `--rerun-test` are explicit invalidations for a changed policy. Completed TEST observations survive a reader-only retry.

## Work reuse

Reader metadata and stored row comparisons precede TEST replay. An unavailable reader tuple performs no native TEST evaluation. RULE bindings use the canonical two-sided producer; a mutant is never attributed to gold's source stream. INIT compares the complete component key-and-port interface; absent outer-key columns remain unavailable rather than being omitted.

Caches retain immutable native snapshots, original held groups, gold reader resolutions and gold OUT observations within a task. They are bounded or released at task boundaries. Artifact file hashes use the shared stat-keyed hash cache. `--workers` shards whole tasks across spawned processes, preserving per-task evaluator reuse and per-pair durable SQLite writes. Each worker's native thread entitlement is divided from the run's CPU allocation.

## DET transport

`det_receipt.receipt(record, exports, bindings)` supplies `mech3-det-header-projection-v1`: the union of actual reader-named declared header identities, with exact scoped BODY transport, aliases retained, native Unit certificates and complete no-reader proof. The raw bindings establish physical provenance. Shared MetadataProducer owns formatting/projection; this module copies no graph or library policy.

`det_targets.load_det_targets` delegates validity to mech5. Its overlay preserves other producers and disables held-OUT program fit for DET. No DET target acquisition or second recovery search is implemented here.
