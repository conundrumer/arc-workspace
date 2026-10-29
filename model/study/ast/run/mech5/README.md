# Target comparisons

This pass contributes target evidence to the central reducer. It reads the base database and stored X tables, and writes only under `DATA_ROOT/ast/run/mech5`. It does not label the base again or write settled grades.

`targets.py` acquires fresh full gold values once per task/case/program/own-kept context, journals the resulting JSON bundle immediately, and selects G, later tables of the pair's case, and all tables of other cases through the shared collector. The case key excludes the mutation and changed point. Task input content, catalogue content, labeling dependencies and replay settings bind validity. Other-case comparison ignores names and uses the shared Cartesian assignment comparison; model families remain sets of row sets.

Every equality checks the whole projected X table on TRAIN and TEST through the canonical name/type/Ident/margin comparator. INIT and DET projections come from shared metadata providers. The pass searches only other targets with proved TRAIN containment, using the existing nonlib selector search. Available callables come from the canonical resolver and native physical schemas. Every new candidate goes through the shared cached-target evaluator and n-mech's `clause_evidence` adapter. Gold is not replayed per candidate. Candidate verification has a one-mutant-replay cap; operations beyond that cap remain unknown.

The nonlib search is a proposal mechanism. Omitted nondeterministic selector sources, fresh Ident namespaces, unrenderable clauses, bounded enumeration, computed columns and unions can leave recoveries undiscovered. None proves that the settled recovery space is exhausted. Raw containment misses and branch-local row counts are diagnostics. `all_targets_lossy` remains null. `mech-no-x-rows-v1` certifies only absence of X-sourced recovery under complete globally empty X and a nonempty witness for every target; it does not imply search exhaustion or Reject. A validated certificate becomes `comparisons.X_empty` with complete TRAIN, TEST and kept-context evidence. The central reducer owns the empty filter class. Partial source requires actual X-row contribution under the settled policy.

## Deployment status

Source is built; no target run, evaluation or tests have been launched. The all-population entrypoint deliberately fails preflight while the mechanical DET route is unavailable. Ordinary judge checking excludes DET, and the collector does not yet support its public reader-header projection. Raw private BODY columns and kind changes cannot substitute for that route. n-eval owns the missing collector/checker capability and evaluator relocation; n-judgetool supplies its pending repair handoff. The shared DET metadata wrapper and mech3 transport must also be merged. Shared held-slot decoding, global Ident agreement and exact cached context coverage repairs must land before deployment. The evaluator's artifact-root change must permit `DATA_ROOT/ast/run/mech5/replays`.

After those dependencies are integrated and this preflight is updated, run from the main checkout:

```sh
python3 scripts/run_heavy.py --need soon --cpus 1 python3 -m model.study.ast.run.mech5.targets
```

This is a future deployment command, currently blocked. Task selection with repeated `--task` and a new-work bound with `--limit` are available for coordinator qualification. Such a selected run reports `complete: false`. Full results go to `work/lm/data-study/ast/run/mech5/targets.sqlite3` and `summary.json`. Progress includes done/total, elapsed, rate, ETA and case replay phases. The summary reports contribution outcomes grouped by base label and kind; central settled grade counts still require the reducer overlay.

## Durable format and resume

`target_store.Journal` uses SQLite WAL and synchronous FULL. Each completed case, comparison, search, candidate and pair commits independently to `entries`. Keys are `(kind,key)`; `inputs`, `code`, `config` and `result_sha256` bind canonical JSON identities. `payload` is zlib-compressed canonical JSON. `producers` retains the code manifest and settings for each code/config hash. Code paths are study-relative, so unchanged files retain validity after merge into the main tree.

A pair result uses `mech-target-pair-v1`. It carries pair/source/base-result identities, the original source locator, base-result reference, kind, `table_only` for DET, target comparisons, support diagnostics, checked mechanical clauses, gaps, missing steps, and durable child references. `outcome` is this pass's strongest contribution: equivalent, Recovery, Partial source or Unknown. Other owners' program/reader/judge evidence can strengthen Unknown in the central reducer.

A restart skips valid pairs before opening corpus source streams. Pair/source/base/code/config hashes and child journal payloads must agree. Stale pairs are computed again. Finished bounded or unavailable attempts remain durable Unknown; they are distinct from open results. A code/config change requires new validity or an explicitly reviewed compatibility mechanism; arbitrary predecessor hashes are not accepted.

The source index is the base row's `source` object (`corpus`, `stream`, `file`, `line`, plus task) and canonical source hash. Source lines are read sequentially and checked against both source SHA and canonical pair identity. Case acquisition identity is independent of the representative mutant record used to discover its case.

## Consumer API

Import the `mech5` package with `model/study/ast/run` on the module path, or use the repository-qualified namespace shown by the command.

```python
from mech5.read_targets import load_targets
from mech5.evidence import apply_targets

loaded = load_targets(database, pair_id,
                      source_sha256=current_source_sha,
                      base_result_sha256=current_base_result_sha)
if loaded['valid']:
    evidence = apply_targets(evidence, loaded)
```

`load_targets` opens databases read-only. It checks the current base row, code/config manifests, task-input receipt and all referenced journal payloads. Policy prose is not read or used as a validity dependency. Legacy specification hashes and manifest entries remain readable as recorded metadata; their files are not checked. It returns `status: done`, `valid: true`, `record`, `reference`, `result_sha256`, `outcome`, `kind` and `table_only`. The reference binds database/table/kind/key and code/config/result hashes. Missing, corrupt or stale evidence returns `status: open`, `valid: false` and a reason. A valid Unknown is done.

`apply_targets` checks source/base/result binding, adds the durable target reference, replaces target comparisons/support, and adds this producer's clauses. It preserves program fit, reader evidence, other mechanical clauses and attributes. It never writes a database. n-mech's central reducer owns grade precedence and DET's exclusion from fits/extension. Child journal payloads are the durable mechanical evidence; replay artifacts retain the evaluator's full audit material.
