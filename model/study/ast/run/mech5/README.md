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

Gold observations and expensive candidate checks commit independently as soon as complete. Cheap comparison observations for one pair commit together before search; the pair result commits when that pair is complete. An interrupted comparison batch can repeat cheap comparison work, while completed case and candidate results stay reusable. Pair validity depends on canonical source input identity. Changing code, prose, producer settings or the base run's incidental metadata does not invalidate a completed pair. Historical base-result hashes remain provenance. Deliberately changing interpretation requires an explicit rerun choice; this pass does not infer that choice from a merge. Independent child records retain their original producer references.

Legacy `mech-target-pair-v1` and full case journals remain readable in place. They are not rewritten, deleted or replayed for cleanup. Legacy stored grades/outcome/support summaries are not consumed as authoritative facts where independent child comparison/candidate facts exist. Native facts and their recorded source identity remain usable across code changes. No completed observations have been erased or recalculated by this cleanup.

## Read interface

`mech5.read_targets.load_targets(database, pair_id, *, source_sha256, base_result_sha256=None, source_groups=None, derive=True)` opens both stores with `mode=ro`; all journal reads share one WAL snapshot. It validates current canonical source identity, stored payload digests and producer provenance. The optional current base-result hash is a caller snapshot check; historical base-result changes do not invalidate unchanged source inputs. `derive=False` validates/resumes facts without constructing evidence views.

The result has `status: done|open`, `valid`, authoritative `facts`, an ephemeral legacy-shaped `record`, durable `reference`, `result_sha256`, current `kind` and `table_only`. `result_sha256` hashes **facts**, not the derived record. Old consumers that check the hash should use `loaded.get('facts', loaded['record'])`. Missing DET rows remain open. A bounded completed operation remains done.

`mech5.evidence.apply_targets(evidence, loaded)` is the canonical pure overlay; it never writes or grades. It preserves other passes' program/reader/attribute evidence, uses the recorded target comparisons and invokes n-mech's clause policy for checked candidates. `certified_empty` validates a read-time `mech-no-x-rows-v1` proof before exposing `comparisons.X_empty`. Callers that already acquired authenticated canonical X groups may supply `source_groups` to derive this proof from existing source data and target observations. X rows are not copied into this store. A complete set of TRAIN containment mismatches across the settled target catalog supplies the read-time all-target lossy proof. An individual mismatch does not decide that proof, and no mismatch claims search-space exhaustion.

n-mech owns `read_grades.read_pair`, `read_grades.read_pairs` and `result_grade.grade_results`, which combine stored passes and compute the grade at read time. This pass publishes neither grades nor grade summaries.


`--retry-unavailable` explicitly retries failed pair acquisition and pairs linked to case-preparation failures. Completed comparisons, searches, candidates and gold case observations retain their source-bound validity. Bounded comparisons/searches are completed attempts and do not enter this retry scope. DET remains open under the default per-pair gate.

Case-preparation failures are stored once as `case_failure` entries (`mech-case-preparation-failure-v1`) with case, phase/error and message; pair facts link them through `case_failure_refs`. Read-time views resolve those references into gaps. During a task each failed case is attempted once; subsequent pairs reuse its failure reference. A later explicit retry starts a new case attempt while preserving successful case observations. Stored X is authenticated before fresh case preparation. Ordinary metadata routing delegates directly to the canonical producer, avoiding redundant program export/copy work.


## Comparison performance

Native gold observations remain once per case/input identity. A task-local index reuses their lossless decoded row families, canonical BODY projections and model row-count sets. Selection uses the shared collector's unchanged bytecode in an owned namespace with cached decoding and one source hash per pair; no shared module globals are changed. Transient indexes are discarded at task boundaries and are never written as label facts.

Before row-level comparison, a name/type matching check rules out impossible fixed column maps. Equality also checks whole-table arity and model row counts where every permitted column map is injective. TRAIN containment uses only necessary row-count bounds for both model-family quantifiers. A projection can collapse rows, so an excess of X rows alone does not rule out containment. Missing context evidence still produces unknown. These obstructions settle the comparison only; they never prove that the library/union search space is exhausted.

Exact proposal queries reuse their bounded nonlib search result in a task-local cache. The key includes typed source/target native row families in context order and every available relation's types/rows. New clauses still use the shared evaluator and its operation cap. The cache is bounded, ephemeral and has no effect on durable input-keyed resume. Progress includes cumulative seconds for metadata, stored X, case acquisition, selection, comparison, proposal and candidate checking, plus proposal query reuse counts.


The native source cache retains canonical finalized snapshots across pairs within a task, keyed by absolute corpus/task path and the entire recorded native reference. It is bounded by view count and estimated buffer size. Misses use the unchanged canonical loader; native index/schema/projection checks still run on hits. Staging snapshots are not retained. This cache is not continuing on-disk integrity attestation.

Canonical metadata inventory copying preserves read-only source-record/reference leaves while cloning the mutable inventory and case envelopes. Kept-assignment and assignment-map leaves are read only. No availability, definition, table or group envelope is shared through this copy memo. Canonical metadata values and source receipts are unchanged. Discarded receipt/view construction is omitted before compact pair persistence. Journal producer integrity checks reuse only identical stored manifest/settings text, with historical hashes retained as provenance.

Progress reports native view loads/reuse, journal commits, commit seconds and total journal-save seconds in addition to phase timings. Label facts, schemas, comparison/search keys and input-keyed resume remain unchanged.

Determined row-level comparisons reuse exact task-local queries across pairs and target aliases. Keys include native row-set families with their context axes, source and target column names/types, cross-case Cartesian policy, relation and bound. Coverage and conservative obstructions still run before lookup. Unknown or bounded attempts are not retained. Query retention is bounded by count and cell references; task changes release it. Pair receipts and target identities are constructed independently of the cached comparison. Progress reports `comparison_queries_run` and `comparison_queries_reused`.


Catalogue-backed case programs are resolved by the shared collector context adapter before assigning a cache identity. An omitted source-program string and an explicit string for the same gold case now share the actual program/kept key. Legacy placeholder-key observations are reused through their original references; existing records are never rewritten or invalidated. The case-collection counter counts collector requests, which may be served by the shared collector cache.


## Read-time all-target negative

`negative.derive_support` derives the settled row-absence rule from existing authenticated comparison and case references. `record.support.all_targets_lossy` is true when G, later own-case tables and every other-case native table form a complete catalog and every canonical TRAIN containment result is mismatch. It is false when any target contains, and null when no such counterexample is known but the catalog or a containment check is missing, bounded or unavailable. No comparison, replay, grade or derived proof is written back.

Catalog completeness uses the gap-free terminal enumeration from the owned producer, the exact G case/body identity, successful case replay receipts, and explicit coverage of every other-case native table. Same-case eligibility remains the producer's canonical source-scope result; no table-index or ordinal cutoff is inferred. Missing case/point/scope evidence blocks completeness. Small case-catalog metadata are cached by their authenticated durable reference; native rows are not copied into this cache.

Catalog and containment coverage are independent of positive equality TEST checks and bounded candidate searches. A complete TRAIN mismatch disproves containment without a TEST negative. Positives still require their existing TRAIN+TEST gates. `apply_targets` forwards `target_catalog.complete` and `comparisons.recovery_support.{complete,all_targets_lossy,receipt_ref}` to the central reader. The central grade/routing predicate is `grades.all_targets_lossy`; empty, equality, Recovery, Partial source and fits retain their grade priority. Legacy facts and input-keyed resume are unchanged.


## Exact input retries

`--pairs-from PATH` reads a JSONL selection containing `pair_id` and `source_sha256`. Duplicate or malformed IDs, absent base rows and changed source bindings are refused. Only those IDs are visited, using indexed lookups in the read-only base store and task/source-line ordering. Existing valid completed results still resume; combine with `--retry-unavailable` to retry unavailable attempts within that explicit selection. Code and historical result hashes do not select or invalidate pairs.

The output database has one writer for its lifetime. `--wait-for-writer` waits for its exclusive lock before constructing an evaluator or evaluating pairs; it does not stop the existing job. Separate writers are not coordinated for shared case/comparison records or deterministic artifact paths. A waiting retry starts when the writer releases the lock and reuses the existing output and child facts. It logs a waiting phase separately from labeling progress.


## Bounded pair execution

The driver supervises one persistent worker, retaining task caches between pairs. `--pair-seconds` sets the wall budget for each new pair attempt (default 600 seconds); comparison and native-operation limits remain unchanged. The parent receives pair/target/phase events and enforces the wall budget independently of Python or native cooperative checks. On expiry it kills and reaps its worker, records a source-bound stopped fact, and continues at the next input. The parent writes only after the worker exits. A completion committed before expiry is preserved, even if its completion event raced the deadline. Committed child facts remain reusable; SQLite rolls back uncommitted work. There is one evaluator worker and no parallel pair evaluation.

Stopped facts carry the phase, target, wall budget, elapsed time and reason once under `stopped`. Read-time views expose the missing work as unknown. `--retry-unavailable` does not retry wall-budget stops; `--retry-stopped` is an explicit choice to retry them. Completed results retain their input-keyed validity across this change. Progress and stopped events identify the pair and target. The supervisor retains the output writer lock, so a queued run waits for the existing retry writer without interrupting it.

The shared comparator enumerates fallback typed injective assignments directly in the original lexical order and checks the same absolute deadline on every visited extension. Explicit and valid by-name projections retain repeated-column aliases. Model, row-projection and Ident loops check the same deadline; exhaustion returns unknown with a phase and reason. A stopped search never establishes mismatch or a negative proof. Uninterruptible builtins/native operations remain covered by the outer pair wall budget.
