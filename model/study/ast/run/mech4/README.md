# G-only lib recovery pass

This pass searches the base run's G-open hints through the shared evaluator. It stores its own native observations, checked candidate outcomes, search-stop facts and their provenance. Grades belong to n-mech's read-time join. Normal-form exclusions belong to study read-time counts and fits.

## Store and reader

The authoritative database is DATA_ROOT/ast/run/mech4/lib.sqlite3. Writes use SQLite WAL with synchronous FULL. Completed native checks and finished pairs commit immediately. No queue, grade, normalized-clause copy, comparison cache, AST export, registry copy or summary file is written.

| Table | Contents |
| --- | --- |
| `records` | `(kind,key)` primary key, input/code/config/result SHA256 and a compressed root-object reference |
| `objects` | Content-addressed canonical values, recursively referenced so repeated receipts and values are stored once |
| `producers` | `(code,config)` primary key, references to recorded executable manifest and run settings |
| `operations` | Native operation reservation/completion, pair/scope, observed charge and native result/artifact reference |

Record kinds written by this pass are `gold_case`, `candidate` and `pair`. `gold_case` contains newly acquired native GOLD observations, retained once per exact case/program/kept/input/settings identity. Native execution artifacts are evidence receipts; their original references remain intact. `candidate` is the shared evaluator's checked TRAIN+TEST/provenance result. A `pair` contains the source and immutable base-result references, candidate references, GOLD/input references and observed search termination. It carries neither a grade nor copies of candidate outcomes. Program AST exports, canonical metadata, registry groundings, screen comparisons and search beams are recomputed in memory.

Pair keys are `digest({"pair": pair_id, "target": "G"})`. The compact pair schema is `mech4-lib-facts-v2`; its fields are `pair_id`, `source_sha256`, `source`, `base_result_ref`, `candidates`, `gold_ref`, `task_receipt`, and `stop`. `stop` records the actual termination path/reason/error. Source/base references bind facts to the original pair; code/config references bind their producer. Prose and document hashes are not dependencies.

With CODE_ROOT/ast/run on sys.path:

```python
from mech4.read_results import load_result
view = load_result(database, pair_id,
                   source_sha256=current_source_sha,
                   base_result_sha256=immutable_base_result_sha,
                   source_record=already_loaded_source_record)
```

`source_record` is optional; passing it avoids a source-gzip scan. The reader verifies source/base/result and retained producer hashes, joins referenced checks and derives `mechanical_clauses`, `found_recovery` and `search_status` in memory. It never computes or stores a grade. A done bounded/unavailable attempt remains Unknown evidence, never a negative proof or judge admission. Missing, corrupt or interrupted results are open.

Legacy inline JSON records remain readable through the same decoder, including their original producer/config/result digests and evidence references. They are normalized at read time from checked candidate receipts. A storage or wording change does not require a native rerun. Recorded code is retained provenance; readers do not reopen mutable producer files or the prose specification to decide validity. Active writers still stop on executable source changes. Completed pair facts are reused across persistence-only changes by the validity reader. Only canonical input identity and stored-result integrity gate reuse of candidate work. Current code/configuration hashes are provenance and never invalidate completed work. GOLD keys bind the program, case, kept values and canonical task inputs; candidate keys additionally bind the clause and explicit output columns. Native budget scopes use these inputs, so a source merge cannot reset charged work. Original base receipts remain intact; a changed base-result envelope is reported as `base_reference_matches` and does not invalidate an unchanged source/task result. No historical receipts are stripped or promoted to new proofs.

## Search and new work

The hint is base `overapproximation` without a train witness, or a per-assignment `search_bound`, excluding base fits/errors and already resolved grades through n-mech's computed compatibility reader. Routing never persists the grade it reads. `prepare.py` previews this population without writing anything; `run_lib.py` builds its queue in memory from authoritative stores.

The finite grammar uses owner-provided registry modes/sites, grounded predicates and NOT, resolver-admitted available-table restrictions, one computed library relation and bounded conjunctions. No Python library evaluator or grounding policy is copied. Fresh GOLD values are acquired once per case/program/kept/input configuration because the base lacks authoritative lib-check target TEST rows.

Candidate TRAIN screening batches uniquely named RULE tables into the original whole mutant, preserving OUT. Output tables are resolved by exact inserted form. A failed batch splits under the same call/time caps; it does not establish an individual refusal. Every expected kept TRAIN context is required. Screening proposes explicit ordered output columns. TRAIN matches receive independent shared-evaluator TRAIN+TEST checks against fresh G and native X-row/one-row-per-X provenance. Every split and provenance replay is charged. The planner never combines model masks or zips model ordinals.

This layer leaves deeper/structured groundings, multiple computations, unions and other targets uncovered. Read-time `bound_unknown` reflects that uncovered space even when the finite plan was visited. It grants no full-space exhaustion, negative grade or admission. Other-target lib work follows the target pass. Unsupported DET/CHOOSE projections remain unavailable.

## Limits and coordination

Source prerequisites are the canonical nonrender metadata producer, n-mech registry helpers and shared evaluator artifact-root/retain_forms/matcher/exact-context support. Original helper patches are under DATA_ROOT/ast/run/mech4/patches. Interface presence is checked before execution. The actual-X successful-row provenance repair remains a correctness prerequisite for lib/partial/union results; existing prefix multiplicity alone is insufficient.

Native operation reservations are committed before execution. Interrupted operations retain their declared deadline charge. Pair call/time limits apply across restarts of the same scope. An operation already started can run to its own native deadline. Gold setup has a separate per-case limit. Disk/source guards run before native calls. Logs stream population/attempt progress, elapsed, rate, ETA and counters; these derived values are never written to an analysis store. SIGINT/SIGTERM stop after durable work.

After prerequisite merges and coordinator readiness, commands run from the main checkout:

```sh
cd /Users/davidlu/code/arc-workspace
python3 scripts/run_heavy.py --cpus 1 --need soon work/lm/data-study/ast/run/runtime-5ee2f066/venv/bin/python -B model/study/ast/run/mech4/prepare.py --limit 20
python3 scripts/run_heavy.py --cpus 1 --need soon work/lm/data-study/ast/run/runtime-5ee2f066/venv/bin/python -B model/study/ast/run/mech4/run_lib.py --limit 20
```

Run the second command without `--limit` for the full hint population. If a deliberate change alters the meaning of results, explicitly use `--fresh-output DATA_ROOT/ast/run/mech4/NEW.sqlite3`; it requires a new database and preserves the original facts/receipts. Changing code or bounds with the same output resumes completed facts and does not rerun them. A previous persisted queue is ignored. Native limits and artifact directories are configuration scoped. No tests or native evaluation were run while building this source.


## Performance scheduling

The lib extension keeps available-only restrictions already present in every base assignment as syntax for combinations with libs. It does not replay those restrictions alone or combine two such base-only restrictions. Missing base inventory or newly admitted available sources keep standalone screening active. This is scheduling of an explicitly uncovered search, never an exhaustion/Reject proof.

Unused containment comparisons are omitted. The shared comparison type adapter rejects impossible output-type proposals before native calls; selectors remain available for later computed outputs. A single-clause screen whose largest model has fewer rows than every target model cannot match through projection and is dropped from the recovery beam. This local obstruction never becomes an all-target/union negative.

Syntax plans use a bounded in-memory cache keyed by canonical callable/type/source identities and registry declarations. Native row results are not shared across different mutants without proof. Selector/computation conjunctions are tried first, with fresh existential labels renamed through the canonical helper when they collide. Default native batches contain 16 candidates. Two canonical, read-only native snapshots retain warm gold and the current mutant; task boundaries clear them. Exact TargetStore ref/base keys and miss validation remain unchanged, and cache hits are not disk-integrity attestation. Native budgets, independent positive verification and input-keyed resume remain unchanged.

Routing reuses n-mech's bulk StudyReader when available, with the compatibility reader retained for older source. Pure grade/presentation changes do not interrupt native execution; full producer provenance remains recorded. Native-policy source changes still stop the writer. Performance evidence and retained-result reads are process artifacts under DATA_ROOT/ast/run/mech4/review.
