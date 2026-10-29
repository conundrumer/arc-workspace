# Mechanical results and read-time grades

Each pass owns its stored facts. The grade is computed when read and is never a
SQLite row. The original 116,384 base records remain readable without relabeling.

## Analysis API

Use the repository's Python environment (Python 3.12 or later), with
`model/study/ast/run/mech` on `sys.path`:

```python
from collections import Counter
from read_grades import read_pairs

counts = Counter()
absent = 0
for pair in read_pairs():
    if not pair['valid'] or pair['normal'] is not True:
        absent += 1
        continue
    facts = pair['facts']
    counts[pair['grade'], facts['operation'], facts['K']] += 1
print(counts)
print('absent: non-normal, unavailable normal form, or unavailable base', absent)
```

`read_pair(pair_id, *, paths=None, source_record=None)` returns the same joined
view for one pair. `StudyReader(paths=None)` is a context manager with both
methods for bulk callers. `load_grade(database, pair_id, source_record=None)` is
an import-compatible wrapper; `database` now means the witness journal.

The view has `pair_id`, `facts` (task, case, point, operation, K, kind), `results`
(base, witness_tests, fit_split, lib_search, target_comparison, judge_outcomes,
normal), computed `grade`, `attributes`, `missing_steps`, `judge_eligible`, and
`normal`. A valid base with missing pass results still has a computed Unknown;
missing/corrupt base data is `valid=false,status=open`. Optional results retain
explicit done/open and validation details. Normality filters analysis counts
and fits only; it does not gate labeling passes.

All stores are opened read-only and can be read while their WAL writers run.
The base cursor is a snapshot; optional passes are read as available. Every
consumed result must match the pair/source/base input identity and payload
integrity. A store changing between reads cannot substitute a result for another
input. Producer code/config hashes remain provenance; unrelated code changes
and prose edits do not invalidate facts. The spec is never read at runtime.

`result_grade.grade_results(base, *, witness_tests=(), fit_split=None,
lib_search=None, target_comparison=None, judge_outcomes=(), base_reference=None)`
is the public pure reduction of these authenticated inputs. It has no SQL,
filesystem, native evaluation, or writes. The read layer calls the same policy;
no pass maintains its own grade table or grade snapshot. The normalized fit
reader returns independent reader and TEST references; both are retained in
`results.fit_split` for auditing.

Default stores, under `DATA_ROOT/ast/run`:

| Facts | Store | Owner/reader |
| --- | --- | --- |
| Pair identity and original mechanical results | mech/labels.sqlite3 | mech base |
| New witness test checks | mech/settled.sqlite3, witness_tests | mech |
| Normal status | mech2/normal.sqlite3 | mech2.read_normal |
| Reader difference and TEST program fit | mech3/step4.sqlite3 | mech3.store.load_step4 |
| Library candidate outcomes | mech4/lib.sqlite3 | mech4.read_results.load_result |
| Target comparisons and candidates | mech5/targets.sqlite3 | mech5.read_targets.load_targets |
| Checked judge final artifact references | mech/judge.sqlite3 | grade_judge.py |

`paths` overrides these names. Readers accept legacy and compact owner schemas.
The original base payload remains visible in `results.base`; it is not copied
into any new pass result. New judge ingestion stores references to the tool's
existing final/source/manifest artifacts, not copied outcomes or joined evidence.
Legacy owner data is adapted at read time, without native replay.

## Base labeling pass

`run.py` resumes a stored pair row when its payload digest matches, it has no
error, and its source hash is the source record's hash. Code and config hashes
in the row are provenance; a code change does not rerun a pair. `--relabel`
recomputes every pair. `--compatibility` is accepted and ignored.
`corpus_index.py --reindex` and `mech2/classify_normal.py --reclassify` are the
matching explicit reruns of those passes.

## Witness pass

`step2_check.py` reuses the base's stored test result (`test_verified`, or
assignment-zero `generalizes`) and runs only missing train-witness checks.
Existing witness rows resume by source, witness and task input identity plus
payload digest; the original base-envelope hash is retained as provenance. Code/config hashes are provenance only.
Unknown is durable too; `--retry-unknown` explicitly retries it. Completed
booleans always resume, including the earlier 29,423 and later retry results.
The resume scan reads only the fact and its input bindings; full native receipt
trees are expanded by the analysis reader when consumed. Base scanning follows
ingestion order for locality. Progress reports total and phase elapsed time;
rate and ETA use the current phase rather than including earlier resume work.
The old `--compatible-boolean-producer` and `--reuse-completed-booleans` options
remain accepted for command compatibility but are no longer needed to preserve
input-identical results.

New payload schema `mech-witness-test-fact-v2` stores only the test fact; pair,
assignment, source and witness identities are already in the row columns. Large repeated receipt structures are interned once in `witness_objects`;
readers expand their hash-bound references. Old inline v1 payloads remain readable. A result commits before moving to the next
witness. There is no durable derived work queue, pair grade, combined evidence,
or summary file. Progress and final work statistics go to stdout/stderr.
Bulk row/AST lists are interned as chunks rather than serializing every nested
cell separately. Expanded facts and the witness verification policy are unchanged.

Cheap stored X/selector checks precede fresh gold acquisition. Exact native
reference/table/source binding results are cached; up to 32 gold target views
share a 128 MiB budget. Pair hashes and within-pair journal reads are memoized. Both caches are cleared at case boundaries. Canonical
native/schema/held-context semantics remain in the shared evaluator. Actual
native operations and proof receipts remain inspectable; cache hits are counted.

The shared full-program parity fix must be merged before restart: a multi-form
program is compared as an ordered list of parsed forms, not passed to a
single-expression parser. Startup refuses the known broken parser route.

From the main tree, after merging and stopping the old writer:

```bash
python3 scripts/run_heavy.py --cpus 1 --need soon \
  work/lm/data-study/ast/run/runtime-5ee2f066/venv/bin/python -B \
  model/study/ast/run/mech/step2_check.py --retry-unknown \
  > work/lm/data-study/ast/run/mech/step2-retry.log 2>&1
```

Do not change a live store's schema under a running job. Deploy the reader/writer
change first, stop the old writer, and only then remove obsolete derived tables.
The coordinator removes the legacy `grades` table after this writer merges.
Legacy `evidence` and completion tables are ignored; witness and base facts are
preserved. `grade_store.PassStore` stores provenance once and creates no grades.

## Policy details

An open judge route can reuse original native TRAIN nonfit checks. A complete
`native_closed_candidate_set` failure at every kept assignment rules out program
fit without a TEST verdict. `program_evidence.stored_train_nonfit` authenticates
the original source and records exact counterexample pointers; `program_nonfit`
is the shared reducer/admission predicate. The legacy aggregate `fits=false`
alone proves nothing. The joined reader acquires this source evidence only for
an otherwise open judge route, and stores no derived grade or copied fact.
`fits_test` and whole-program `complete` remain unchanged. Positive fits still
requires the complete TRAIN+TEST evidence described below.

Every positive uses complete kept TRAIN+TEST comparisons against fresh gold.
Partial source requires explicit `X_contributes_rows=true` and a complete
`row_contribution` receipt binding the original native artifact, required
TRAIN+TEST context count and nonempty successful contexts. Syntactically reading X, or reproducing the target with
X disabled, is insufficient. Missing proof stays Unknown. The evaluator owner
emits this proof; the reducer does not implement a second evaluator.

Certified `comparisons.X_empty` (complete, empty, train, test,
kept_contexts_complete, durable receipt reference) grades/filter-classifies
`empty`, below valid grades. A missing model family is not empty. Raw row counts
or failed containment are not settled-space negatives. Bounds and missing
entries never prove absence. Attributes do not change a grade.

`clause_evidence_from_identity(result, source_sha256, kept_count, receipt_ref,
*, purpose='answer', role='recovery', ntrain, ntest)` normalizes compact native
receipts without copying the original source record. `clause_evidence` remains
the original-record wrapper over the exact same adapter.
