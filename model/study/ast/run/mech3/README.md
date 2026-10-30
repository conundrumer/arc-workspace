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

The default resumes completed attempts, including unavailable results. `--retry-reader-unknown` explicitly revisits only unresolved reader facts. Repeatable `--retry-reader-reason TEXT` selects unresolved reader facts by exact stored reason; completed reader and TEST facts remain reusable. `--retry-test-unknown` explicitly revisits unresolved TEST facts. Repeatable `--retry-test-reason TEXT` narrows that retry to stored problems containing the text, so a bounded-session repair can leave known held-context mismatches untouched. `--rerun-reader` and `--rerun-test` are explicit invalidations for a changed policy. Completed TEST observations survive a reader-only retry.

## Work reuse

Reader metadata and stored row comparisons precede TEST replay. An unavailable reader tuple performs no native TEST evaluation. RULE bindings use the canonical two-sided producer. Direct mutant metadata loads reconstruct the logged mutation from authenticated gold, with exact text and identity checks. Returned bindings must retain the changed BODY path. Native positive and NOT reader atoms both retain their joint field tuple. Each side retains its native inferred types for the shared comparator; a type-changing mutation is compared rather than refused during mapping. INIT compares the complete component key-and-port interface; absent outer-key columns remain unavailable rather than being omitted.

Caches retain immutable native snapshots, original held groups, gold reader resolutions and gold OUT observations within a task. They are bounded or released at task boundaries. Artifact file hashes use the shared stat-keyed hash cache. `--workers` shards whole tasks across spawned processes, preserving per-task evaluator reuse and per-pair durable SQLite writes. Each worker's native thread entitlement is divided from the run's CPU allocation.

## DET transport

`det_receipt.receipt(record, exports, bindings)` supplies `mech3-det-header-projection-v1`: the union of actual reader-named declared header identities, with exact scoped BODY transport, aliases retained, native Unit certificates and complete no-reader proof. The raw bindings establish physical provenance. Shared MetadataProducer owns formatting/projection; this module copies no graph or library policy.

`det_targets.load_det_targets` delegates validity to mech5. Its overlay preserves other producers and disables held-OUT program fit for DET. No DET target acquisition or second recovery search is implemented here.


## Streaming population pairs

`mech3.pair_api.PairLabeler(*, base, population_passes, config, source_reader=None, deadline=30, compare_seconds=1, artifacts=None)` reuses one step4 worker across sequential samples. `base` is the population `labels.sqlite3`; `config` is its evaluator run configuration, including the task directory. `population_passes` is either a mapping containing `fit_split` or a directory in which to write `fits.sqlite3`. Pass outputs must stay under `DATA_ROOT`. Default replay artifacts use the existing evaluator's mech3 artifact directory.

Use `labeler.label_pair(pair_id, *, relabel=False)` for each committed base pair. It reads the base row afresh, resolves the source through the shared `SourceReader.record`, commits this pass's raw facts per pair and returns the normal `load_step4` result with ephemeral `resumed` and `evaluations` fields. A valid completed attempt, including Unknown, resumes by its inputs. `relabel=True` explicitly recomputes reader and missing TEST evidence. Non-fits and DET pairs return `status="not_applicable"` without writing a fact. No grade is produced.

The object is a context manager with `close()`. It closes an internally created SourceReader; a supplied reader remains caller-owned. Keep one instance per process and call it sequentially. Streaming mode holds no base read transaction and performs no population-wide count, so later committed samples are visible. The standalone CLI retains its existing defaults and scope.
