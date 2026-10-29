# Target observations

This pass reads the base index and stored X tables, acquires fresh full gold tables once per case, compares every eligible target, and checks new nonlib selector proposals through the shared evaluator. It stores only its own observations and input/provenance references. Grades, empty certificates, support aggregates, counts and normalized overlays are read-time functions. No summary file is written.

Run from the committed snapshot worktree after merging. Use the runtime interpreter for the task:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-5ee2f066/venv/bin/python scripts/run_heavy.py --need soon --cpus 1 /Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-5ee2f066/venv/bin/python -m model.study.ast.run.mech5.targets --retry-unavailable
```

Default output is `DATA_ROOT/ast/run/mech5/targets.sqlite3`; native audit artifacts stay beneath `DATA_ROOT/ast/run/mech5/replays`. Progress logs done/total, elapsed, rate and ETA. Logs are unfiltered work counters, not grades or scientific fits. Normal-form exclusions belong to study read-time analysis.

The default run leaves DET pairs absent/open. `--include-det` remains blocked until mechanical DET collection/checking over actual mutant BODY and certified public reader-header projection is integrated. Adding that capability fills the same store and skips completed non-DET pairs. Unsupported CHOOSE projections, INIT outer-key layouts or BODY observers remain explicit gaps. A missing adapter does not prove that an input gives no answer. Native bounds and the one-mutant-operation candidate cap remain unknown, never negatives. Shared evaluator/UI dependencies must remain frozen while the dependency guard is active.

## Authoritative store

SQLite uses WAL and synchronous FULL. `entries` has columns `kind`, `key`, `inputs`, `code`, `config`, `result_sha256`, `payload`, keyed by `(kind,key)`. `payload` is zlib-compressed canonical JSON; `inputs` is its request identity hash. `producers` retains each historical code manifest and settings under code/config identity. No document hash is generated or checked. Code hashes record provenance and are not compared with current files for resume validity.

- `pair`: `mech-target-facts-v2`, canonical source hash, historical base-result hash as provenance, case/axis/comparison/search references, own failures and an explicit work stop. The SQL key supplies pair_id. It stores no grade, reduced outcome, base label/kind/source-record copy, target-row copy or derived support/certificate.
- `case`: `mech-case-observations-v2`, fresh native table/body observations and schemas, replay receipts and gaps. Program export metadata, stored kept values and derived completeness/missing lists are omitted. Required contexts live once in an `axis` entry. Runtime expansion reuses canonical native metadata export without replaying gold.
- `axis`: `mech-case-axis-v1`, the expected observation context domain for the case.
- `comparison`: `mech-target-comparison-v2`, the target query identity and canonical equality/TRAIN-containment results. No row-count obstruction, duplicated native schema or copied candidate result.
- `search`: witness-search facts, limitations and candidate-result reference. The normalized clause and source/target aggregate judgments are not copied here.
- `candidate`: the shared evaluator's native clause-check result, stored once. Normalized mechanical clause evidence is computed through n-mech's canonical identity adapter when read.

Every completed operation commits immediately. Pair validity depends on canonical source input identity. Changing code, prose, producer settings or the base run's incidental metadata does not invalidate a completed pair. Historical base-result hashes remain provenance. Deliberately changing interpretation requires an explicit rerun choice; this pass does not infer that choice from a merge. Independent child records retain their original producer references.

Legacy `mech-target-pair-v1` and full case journals remain readable in place. They are not rewritten, deleted or replayed for cleanup. Legacy stored grades/outcome/support summaries are not consumed as authoritative facts where independent child comparison/candidate facts exist. Native facts and their recorded source identity remain usable across code changes. No completed observations have been erased or recalculated by this cleanup.

## Read interface

`mech5.read_targets.load_targets(database, pair_id, *, source_sha256, base_result_sha256=None, source_groups=None, derive=True)` opens both stores with `mode=ro`; all journal reads share one WAL snapshot. It validates current canonical source identity, stored payload digests and producer provenance. The optional current base-result hash is a caller snapshot check; historical base-result changes do not invalidate unchanged source inputs. `derive=False` validates/resumes facts without constructing evidence views.

The result has `status: done|open`, `valid`, authoritative `facts`, an ephemeral legacy-shaped `record`, durable `reference`, `result_sha256`, current `kind` and `table_only`. `result_sha256` hashes **facts**, not the derived record. Old consumers that check the hash should use `loaded.get('facts', loaded['record'])`. Missing DET rows remain open. A bounded completed operation remains done.

`mech5.evidence.apply_targets(evidence, loaded)` is the canonical pure overlay; it never writes or grades. It preserves other passes' program/reader/attribute evidence, uses the recorded target comparisons and invokes n-mech's clause policy for checked candidates. `certified_empty` validates a read-time `mech-no-x-rows-v1` proof before exposing `comparisons.X_empty`. Callers that already acquired authenticated canonical X groups may supply `source_groups` to derive this proof from existing source data and target observations. X rows are not copied into this store. Raw containment misses never imply all_targets_lossy or search exhaustion.

n-mech owns `read_grades.read_pair`, `read_grades.read_pairs` and `result_grade.grade_results`, which combine stored passes and compute the grade at read time. This pass publishes neither grades nor grade summaries.


`--retry-unavailable` explicitly retries failed pair acquisition and pairs linked to case-preparation failures. Completed comparisons, searches, candidates and gold case observations retain their source-bound validity. Bounded comparisons/searches are completed attempts and do not enter this retry scope. DET remains open under the default per-pair gate.

Case-preparation failures are stored once as `case_failure` entries (`mech-case-preparation-failure-v1`) with case, phase/error and message; pair facts link them through `case_failure_refs`. Read-time views resolve those references into gaps. During a task each failed case is attempted once; subsequent pairs reuse its failure reference. A later explicit retry starts a new case attempt while preserving successful case observations. Stored X is authenticated before fresh case preparation. Ordinary metadata routing delegates directly to the canonical producer, avoiding redundant program export/copy work.
