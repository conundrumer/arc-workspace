# Current ordered postprocessing: step 2 ready

Coordinator ran step 1: **116,384 Unknown**, 162 seconds, zero evaluations.
`step1-summary.json` records the counts and named missing steps. Step 2 is ready;
it has not been executed here. Normal-form classification is owned separately
by n-mech2 in `ast/run/mech2/normal.sqlite3`; it is not in this thread's queue.

```bash
python3 /Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 --need now /Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-5ee2f066/venv/bin/python -B model/study/ast/run/mech/step2_check.py > /Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/mech/step2.log 2>&1
```

`step2_check.py` reads `labels.sqlite3` without writing it, and updates only
pairs with a stored, train-verified witness in `settled.sqlite3`. It reuses each
assignment's `test_verified` boolean, including false; when absent on assignment
zero, it reuses `generalizes` (boolean or 0/1), as the coordinator directed.
Only remaining witnesses are applied. `witness_test.Checker` uses the study's
canonical verifier and shared `judgetool.tables.compare` for final equality,
including fresh Ident renaming. It searches for no new witness and replays no
mutant. Selector predicates and X's test rows come from stored native tables;
the new evidence is fresh gold BODY test rows through the one shared evaluator's
`raw_body.observe_gold_body`. Gold data is cached by gold program, case, point,
layout, kept values and settings, with bounded retention. Source gzip files are
scanned once each, decoding only selected lines, and checked against base hashes.

Every witness immediately commits one `witness_tests` row (FULL/WAL), keyed by
pair and assignment. Its validity binds the exact witness, source record, base
result, code and configuration hashes, plus a digest of its payload. Stored and
new outcomes are distinguished; new outcomes retain target/native/evaluator
receipts. Valid completed attempts, including explicit unknown, are resumed
without another evaluation. `step2_pairs` then binds the pair's evidence/grade
digests. An interruption between those commits reuses the witness and only
finishes the pair reduction. Dependency changes stop the pass before another
check. No later-step evidence is overwritten.

Ordinary RULE recoveries with all assignments train/test verified can grade
Recovery; redundant stays an attribute. Raw INIT BODY success does not establish
the public key/port projection, and DNF success does not establish settled union
provenance: these retain an explicit step 3 admission gap. Equivalent comparison
and all-target lossiness remain step 3. Unsupported scalar/DET layouts, missing
test entries and stopped replay remain unknown, never false test results.

`step2-summary.json` reports complete/interrupted status, grade/missing-step
counts, reused true/false results, new true/false/unknown results, actual witness
applications, gold replays, elapsed time and resume counts. The log streams
done/total, elapsed, rate and ETA. No tests or replay were launched while preparing
this command; only static syntax and source/API review were performed.

## Step 1 and the stored base

The base run has finished. Its database has **116,384 rows**: 116,352 writes,
17 reused rows and 15 durable error rows. All stored rows are included in grading.
The base is never labeled again by the following steps; step7 retries only the
specified move-failure record. Earlier prototype full replay scripts below are
preparation, not the authorized way to recompute the base.

`step1_reduce.py` is a function of stored base rows only. It checks original
source/code/config/result receipts and writes one FULL/WAL grade+evidence per
pair to a separate settled.sqlite3, with digest-checked resume. No corpus read,
engine evaluation or test run occurs. Unsupported positives await steps2/3/4;
G-only lossy awaits ALL-target comparison and is never a Reject. Ordinary
recovery on redundant X remains Recovery with the attribute; only union source
proof requires nonredundancy. Every provisional Unknown names missing_steps.
Step1 preserves stored sibling/redundant with the recorded base scope.

```bash
python3 /Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 --need now python3 -B model/study/ast/run/mech/step1_reduce.py
```

The sandbox blocked local startup (nice value0 Operation not permitted, exit125).
Coordinator subsequently ran the command successfully and supplied the results
above. It wrote step1-summary.json and settled.sqlite3 without native work.
Do not rerun step 1 over later-step grades.

`read_grades.load_grade(database,pair_id,source_record=None)` is the canonical
read-only availability API: valid Unknown is status=done with named missing steps;
status=open means no valid row or changed base source/code/config/result,
evidence, reducer source or spec. Source is checked against the CURRENT base
receipt; pass a newly acquired original corpus source record for fresh-content
checking. This does not claim continuing on-disk native integrity attestation.
The source locator is mech-source-v1 with real corpus path, TASK/file and 1-based
line. The raw original base result is referenced by its original digest.

`TargetStore.mutant_input` is label-only: gold-kept +train/test. Features need the
shared raw/all-STORED-assignment train projector, whose owner was asked9640; no
kept-selected X or held-out outputs are supplied to features. Population coverage
is a separate native receipt, not inferred from the stored entries.

---

# Mechanical labels for corpus-v11

This README's implementation details describe the running **mechanical-labels-v2**
evidence pass. The settled grades now in plan.md and judge-decisions.md require a
separate validation/reduction pass. grades.py now implements the settled grade
reducer; the old six-label producer and compatibility export still do not. Do not treat an exported train witness as
a final grade before the required target and test checks. The running algorithm
is unchanged. Native session/library endpoint proposals are historical planning;
no such implementation or runtime is approved or available.

`run.py` labels the union of retained records in `*/pairs.jsonl.gz` and all records
in `*/recoverable.jsonl.gz`. There is no 300 MB cap: 9f669b64, 15113be4,
4e7e0eb9 and 136b0064 are included. `--sources kept` or `--sources recovered`
selects just one stream. Equal-gold recovered records are included, too.
Only published task directories named with exactly eight lowercase hex digits
are admitted. The producer writes `.TASK.tmp` and atomically renames it on
completion; hidden staging directories are excluded even though pathlib glob
matches them. Explicit --tasks must also name published task directories.

## Coordinator commands

From any working directory, set:

```bash
M=/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/mech
H=/Users/davidlu/code/arc-workspace/scripts/run_heavy.py
```

First run this operational pilot (three retained and three recovered records per
task, for 00576224, 007bbfb7 and 009d5c81; at most 18 pairs):

```bash
python3 "$H" --cpus 4 --need now bash "$M/launch.sh" pilot 4
```

Run the same command again to check that it reports skips and no new writes.
Inspect the saved evidence with:

```bash
sqlite3 "$M/labels.sqlite3" 'select json_extract(record_json,"$.task"), json_extract(record_json,"$.source.stream"), json_extract(record_json,"$.label"), json_extract(record_json,"$.search"), json_extract(record_json,"$.sibling"), json_extract(record_json,"$.redundant"), json_extract(record_json,"$.error") from pairs;'
```

Then start the full run, continuing the same output:

```bash
python3 "$H" --cpus 4 --need soon bash "$M/launch.sh" full 4
```

Output: **`$M/labels.sqlite3`**. Keep its `-wal` and `-shm` files with it while
running; SQLite manages them. This is the authoritative per-pair output, not a
task batch or a JSONL file waiting to flush. An optional consistent JSONL snapshot:

```bash
python3 "$H" --cpus 1 python3 "$M/export.py" "$M/labels.sqlite3" "$M/labels.jsonl"
```

The export changes only the view, never the database or resume receipts. It
records producer_result_sha256, exporter/normalizer hashes and export_sha256
(canonical output before adding export_sha256). Existing labels/provenance stay
intact. Search-name compatibility mapping is evidence-based:

| Legacy diagnostic | Exported search outcome | Retained distinction |
| --- | --- | --- |
| DETOUR | recovery_verified, if all train witnesses verify | legacy_search |
| VARIANT | recovery_verified, if all train witnesses verify | projection_only |
| WRONG/no_signal | recovery_verified, if all train witnesses verify | no_signal, sibling, redundant |
| WRONG/memorized | recovery_verified, if all train witnesses verify | memorized, generalizes |
| WRONG/unrecoverable | covered_space_no_recovery only with explicit structural obstruction | original proof and search_scope |
| unknown | verified if all train witnesses verify; otherwise bound_unknown only with an actual SearchBound | original per-assignment evidence |
| error or missing/incomplete evidence | unavailable | error and legacy_search |

`rerun` follows the normalized outcome; `legacy_rerun` preserves its original
value. Structural absence refers only to the producer's recorded target and
source-row grammar. It does not assert absence against the new all-case/union/
computed-column target space. An unknown caused by missing evidence is not
renamed into a bound. These names are a compatibility view of stored evidence,
not the settled final pair grades or an authenticated native judge verdict.

## Missing tasks and performance artifacts

`follow_missing.py` watches only the 16 coordinator-named tasks in
corpus-v12-body-full. It uses the unchanged producer, writes missing-v12.sqlite3
durably per pair, and copies committed rows into labels.sqlite3 with FULL
transactions. It never overwrites a different valid row. It can run alongside
the v11 pass because these task keys are disjoint. Restart resumes by pair;
unpublished `.TASK.tmp` directories are not sources.

```bash
python3 "$H" --cpus 1 --need soon python3 -B "$M/follow_missing.py" --workers 1 > "$M/missing-v12.log" 2>&1
```

`profile_done.py` performs only the requested single-done-pair profile/parity
work, using saved results as the reference, not a new baseline pass. The round-1
snapshot covered all eight present label/operation strata (four labels, both
operations); extension and undetermined were absent. All computed fields except
wallclock seconds matched. Reports are in profiles/round1-profile,
profiles/round1-cache and profiles/round1-cache-published. Profiles attributed
about 79% of sampled label time to native snapshot loading. The first cached
profile took 0.0957 s versus 0.1258 s on those eight already-done pairs; this is
a small profile sample, not a claim about full-run throughput.

`algorithm_cache.py` is an isolated, undeployed acquisition-only candidate. It
reuses the original algorithm via owned function bindings. Cache keys include
absolute task identity and the complete native reference; only published final
tasks can hit. Misses use the canonical digest-checking loader; pair-local
annotations are kept out of cached views. The cache has a charged 128 MiB budget
and 24-entry cap. Corpus-owner source review confirms finalized native packs
have no supported in-place mutation. Cache hits are not a continuing disk
integrity attestation. round1-compatibility.json records the eight-pair parity
evidence and old accepted code hash. No deployment has been performed here.

`prepare_lib_sample.py` prepares task-diverse, stratified requests from a
snapshot of no-witness records; it does not execute library predicates or report
gains. Its selector describes the earlier restricted space and must be revised
for the settled target/union rules before measurement. Native session contracts
discussed during planning are not implemented, approved execution capabilities.

These heavy commands require the coordinator's execution environment. The
coordinator ran the pilot: 17 records (9 kept, 8 recovered), about 5.5 pairs/s;
the second run skipped all 17 with no new writes. No tests were run by n-mech.
The first full start failed because pathlib glob admitted hidden staging tasks.
The runner now filters those at discovery and explicit task admission, and source
read errors include the exact path and line context. This runner-only fix leaves
labeling/configuration hashes unchanged, so the 17 existing records stay valid.
The helper owner's bounded source/API review passed for the current algorithm
hash; see SOURCE_REVIEW.md. This does not establish output parity or pilot success.

## Fresh implementation and reference boundaries

`algorithm.py` is a fresh implementation, replacing the initial port at the
coordinator's request. Its behavioral references are `briefs/progsynth.md`, P's
scripts (hashes in REFERENCE.json), `codelabel/` and the study's family_recovery
modules. No P helper code remains in the implementation. The existing durable
runner and record format are retained. Prior port hashes are not compatible.

The study's modules remain the single implementations of native pack loading,
canonical logical rows, full-kept assignment matching, model-family semantics,
available-table certification, bounded search and independent direct verification.
The new code imports `native_storage.load_native`, `filters.native/rows_at` and
`next_revision.family_recovery`. It calls the shared kernels directly; it does
not call the old corpus `recovery()` label policy, infer labels from old DETOUR
verdicts, or invoke `check_recovery_adapter.configure_helper`. The unpromoted
final-output policy and parked V5 candidate are not selected.

The executable pipeline is:

1. Authenticate native snapshots and establish explicit train-input scope.
2. Build the available-table inventory from full replay and exact full-kept
   maps, checking shared-session namespace, kept-assignment identity and native
   acquisition status, and recording all incompleteness. A DET-independent ex_input fact may also
   be certified from the pair snapshot by the canonical helper. No earlier-form
   table is admitted by guessing from partial DET signatures or model IDs.
3. Form the gold and mutant SETs of model rowSETs under every kept assignment.
4. Search mutant-to-gold, available-to-gold and available-to-mutant for every
   assignment. Independent source-family preparation is shared, search results
   are independent, and every positive uses the shared direct verifier.
5. Verify eligible witnesses on exactly matching, explicitly mapped test-input
   axes, then derive the six labels and attributes.

## Known faults addressed

* **Target-row lookup literals:** the grammar admits only zero on Number/number
  and the zero box on Box/Position/Offset. Every other constant must be reached
  through an available table. Gold guides synthesis, but never becomes an
  executable lookup table of arbitrary row literals. The shared search and
  atom enumerator are bound to an owned Python function namespace using their
  existing code objects and an explicit legal-comparison provider. No live
  module-global function is patched. This reuses shared code without vendoring
  it or changing any other consumer's grammar.
* **Projection-only DETOUR:** projection-only witnesses are recorded explicitly;
  the historical search diagnostic is VARIANT, not DETOUR. Under the unchanged
  six-label precedence, an identity projection with extra columns is extension
  unless equivalent/fits takes precedence; column renaming/reordering remains
  overapproximation. `rename` and `shape` keep these distinctions visible.
* **Premature recovery:** inventory acquisition precedes every recovery call,
  even projection-only search. Incomplete inventories are exposed and suppress
  a DETOUR diagnostic and unsupported negative baseline attributes. An unresolved
  sibling baseline also suppresses a DETOUR diagnostic.
* **Conditional sibling baseline:** available-to-gold search runs on every pair,
  including lossy pairs and failed mutant-to-gold searches. The mutant is absent
  from those sources. Redundant searches likewise run independently of success.
* **Bounds treated as negatives:** SearchBound is unknown. An existential
  attribute is true for a verified hit, false only after every candidate
  definitively misses with a complete inventory, and null for unresolved
  searches or inventory. Every source status/reason is saved.

## Labels, attributes and changes relative to P

The label set and precedence remain equivalent, fits, extension,
overapproximation, lossy, undetermined, including labels6's first-assignment
projection-only extension check and all-assignment identity check. Fits consumes
saved native fits booleans, not GIVEN-output equality. Whole model-family SETs
are preserved; equal models collapse and numeric model IDs never pair sides.
The legacy `search`/`rerun` strings are diagnostics, not the six-label outcome.

`sibling` retains labels6's first-assignment aggregation; `redundant` retains
redundant_pass's any-assignment aggregation. This does not substitute pool_pass's
all-assignment interpretation. All assignments and source proofs are retained
for consumers needing another aggregation. `generalizes` remains the first
assignment's test verification and is null when a witness reads an available
table, no explicit test-input scope/mapping exists, or test verification cannot
complete. A failed test read no longer erases valid train evidence.

Intentional result differences relative to P are the unconditional sibling
search, null bounded/uncertified baseline negatives, removal of heuristic
available-form fallback, and stronger test-axis coverage. The ex_input fact is
exposed at its per-input callable interface: when it has a leading Example
column, the current train input is selected and Example is removed. P could
leave a global Example column in the full-replay fact. This can change available
source witnesses and therefore attributes/selection_found. Incompleteness is
reported explicitly, not resolved with guessed tables. Search deadlines can also
change witnesses/outcomes with load. No empirical parity claim is made before
the coordinator's pilot.

All retained pairs are selected by retained=true, rather than pool_index's
judge_eligible selection. Pool relation, missing/extra counts, fits, onpath and
original recovery status/reason are saved alongside the new code-search status.
Default witness budget is 1 second / 20,000 states; sibling and redundant budgets
are 0.5 seconds per available-source search. Changing budgets invalidates resume.
`selection_found` remains labels6's boolean; assignment statuses distinguish a
bounded unknown from a definitive failed search.

No old P result is trusted as a resume record. Inspected outputs lack labeling
code/dependency and source-record hashes, labels6 omits point/clause, old
no-witness sibling=false was untested, and full witnesses for direct
reverification are missing. A matching join key does not prove historical
source/code identity. Those pairs are recomputed.

## Stable record and resume contract (for the speed thread)

Schema is **`mech-pair-v1`**, semantics is **`mechanical-labels-v2`**.
SQLite has a `metadata(key,value)` table and a `pairs` table:

```sql
pair_id TEXT PRIMARY KEY,
source_sha256 TEXT NOT NULL,
code_sha256 TEXT NOT NULL,
config_sha256 TEXT NOT NULL,
result_sha256 TEXT NOT NULL,
record_json TEXT NOT NULL
```

All hashes are lowercase SHA-256 hex. Canonical JSON is Python
`json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)`
encoded as UTF-8. `pair_id` hashes the canonical object containing task, case,
point, clause, K, operation and edits, matching the complete labels6 join key.
`pool_pair_id` separately preserves P pool_index's hash of the **original-order**
identity object with ensure_ascii=False and compact separators. Consumers must
not confuse these two IDs.

`source_sha256` hashes the **entire decoded source record** with canonical JSON.
This includes content-addressed native references; canonical load_native checks
their compressed block SHA-256 while loading them. `source` gives corpus,
stream, filename and one-based line number. Moving/recompressing an unchanged
source record does not invalidate its hash. Native pack data are assumed
immutable, as in the corpus; a resume does not reread all native blocks of
skipped records. Conflicting records for the same join key within a task are a
checked error, not silently chosen evidence.

`code_manifest` contains semantics and exact source hashes for algorithm.py,
native_storage.py, filters.py, native_tables.py, recovery.py and
next_revision/family_recovery.py; `code_sha256` hashes this manifest.
`config` contains seconds, baseline_seconds and semantics; `config_sha256`
hashes it. `runner_sha256` separately records run.py bytes, so scheduling,
inventory and I/O speedups need not invalidate unchanged labeling code.
`result_sha256` hashes the complete decoded `record_json`. The JSON holds all
six-label fields, key fields, provenance, timestamps, per-assignment witness,
test verification, sibling/redundant searches and their bounds/errors.

For each selected pair, a start skips the saved record **only** if source hash,
accepted code hash, configuration, schema, manifest hash and result hash match,
and there is no top-level error. Bounded unknowns are completed outcomes and
are valid resume records; execution errors are durable diagnostics and retried.
No task-level done marker is used. Replacing a stale record is one SQLite
transaction with synchronous=FULL in WAL mode, committed by the worker
immediately after that pair finishes. No worker accumulates a task's results.
This gives one current row per pair and survives a truncated/interrupted run.
Task workers scan compressed inputs incrementally, retain only a small key/hash
map, and never materialize the big task files. Native preparation happens once
per pair. A bounded number of tasks runs simultaneously.

Every five seconds the parent reports done/total, elapsed, pairs/second and ETA,
including skips and error records. During inventory it reports task done/total,
elapsed, rate and ETA instead. Totals use completed corpus retained counts and
streamed recovered-line counts; observed task counts are checked against these
totals. No size-based exclusion is made. Task failures or labeling errors give
a nonzero exit, leaving committed rows available for resume.

One runner owns an advisory `<output>.lock`; multiple workers use SQLite's
transaction lock. For takeover send SIGTERM to the **run.py parent** and wait
for exit. Workers finish their current pair, commit it, and stop before starting
another. Start the new implementation on the same database. A hard kill is
also resumable; the uncommitted pair is rerun. No output deletion is needed.

Changing algorithm.py or an imported labeling dependency changes code_sha256
and normally recomputes affected output. To reuse earlier code after a reviewed
semantic-preserving speed change, pass `--compatibility receipt.json` with:

```json
{
  "current_code_sha256": "<new code_manifest hash>",
  "semantics": "mechanical-labels-v2",
  "compatible_code_sha256": ["<reviewed old code_manifest hash>"],
  "evidence": "<specific review/evidence establishing identical results>"
}
```

The receipt is an explicit equivalence claim by its author, not automatic proof.
It must be reviewed before coordinator use. Never list code that used the old
conditional sibling search, treated bounds as misses, or changed grammar,
aggregation, family semantics or labeling precedence. Initial-port hashes are
incompatible with this fresh implementation. Retain this schema,
canonicalization and resume predicate in the faster implementation.


## Settled grade reduction (separate from the live producer)

`grades.py` owns grade ordering and `judge_eligible`; `reduce_grades.py` commits
one reduction per pair to a SEPARATE `grades.sqlite3`. It never writes the running
`labels.sqlite3`. No engine, library evaluator, native comparator, INIT parser or
dependency graph implementation is duplicated. Source evidence from the old pass
remains reusable; an old train witness alone cannot establish a final positive.

Input JSONL schema `mech-grade-evidence-v1` is an adapter contract, not an
assertion that evaluator.py already emits it. The evidence adapter must verify
referenced artifact contents, source/result hashes, compatible contexts and full
coverage before supplying these fields. Merely supplying receipt_ref or a hash
is not authentication; the reducer performs policy, not receipt verification.
No untrusted judge text or raw replay-completion result is accepted as a check.

Required identity fields are `pair_id` and `source_sha256`. Optional evidence:

* `program`: complete, receipt_ref, fits_train, fits_test, refused (mutant only).
* `comparisons.targets`: target identity plus equal and check fields below.
* `comparisons.point`: complete, receipt_ref, lossy, X_holds_every_gold_row,
  referring to the settled keyed INIT/reader DET projection, not raw body rows.
* `comparisons.reader_difference`: complete, receipt_ref, read_difference;
  complete reader-visible row tuples must establish this distinction.
* `target_catalog`: complete and receipt_ref for every eligible case/target.
* `clauses` (tool answers/exploration), `mechanical_clauses`: exact six spec
  outcome strings, purpose (`answer` or `exploration`), engine_ran, receipt_ref,
  check and provenance. A negative answer needs judgment_complete=true;
  unknown/no-kept replay is not a completed negative. `judge_run` with complete,
  answered and receipt_ref also supports an authenticated no-clause answer.
  Explorations never affect grades or judge-ran status.
* A positive `check` has train=true, test=true, complete=true,
  kept_contexts_complete=true, test_target=gold_full_replay, receipt_ref.
  Target equality uses these same fields directly on the comparison object.
  Test refs must bind exact gold full-replay body table + test projection,
  compatible kept contexts and complete model groups, including INIT keys.
* Recovery provenance: target_columns=X_or_single_row_lib_from_X,
  lib_single_row_per_X=true (vacuous with no lib), restrictions_only=true.
  A union also needs union=true, X_supplies_needed_rows=true,
  X_nonredundant=true. Partial source needs partial_source=true and the same
  target train/test check. Missing proof remains Unknown, never a negative.
* `search`: status, complete, settled_space, unvisited, receipt_ref.
  Only covered_space_no_recovery with complete=true, settled_space=true,
  unvisited=0 plus complete target catalog establishes final exhaustion.
  Legacy WRONG/unrecoverable against one target cannot supply this.
* `redundant`, `sibling` retain true/false/null. `filter_class` retains the
  corpus filter classification separately from grade; it is never silently
  translated into target equality. Filtered-source ingestion remains pending.

Grades follow the spec: equivalent, Recovery, Partial source, fits/extension,
Reject, Unknown, Refused. A complete lossy comparison gives mechanical Reject;
fits requires train/test outputs plus the reader-difference check. Neither goes
to the judge. DET pairs are excluded. A non-fitting pair with only a passing
answer continuation gives Reject and continuation as an attribute. Candidate
refusal does not mean mutant Refused. Final admission requires authenticated
point support and an unresolved grade, not just an old overapproximation label.

Run once the authenticated evidence adapter publishes its JSONL:

```bash
python3 "$H" --cpus 1 python3 "$M/reduce_grades.py" "$M/settled-evidence.jsonl" --output "$M/grades.sqlite3"
```

This is a reducer command, NOT the pending executable lib-sample measurement.
The producer uses the same approved shared ReplayEvaluator as the tool. Its
physical target adapter/ready receipt must arrive before candidate generation
and lib timing can be qualified. The sample preparer now emits source locators,
not obsolete native-endpoint requests, and excludes fits/lossy/extension/DET;
it is a legacy shortlist only, requiring settled support rechecks.

Resume schema `mech-grade-record-v1`: SQLite grades row keys pair_id; columns
are evidence_sha256, code_sha256, config_sha256, result_sha256, record_json.
Hash complete canonical input evidence (including source and prior-result refs),
all reducer code, and configuration containing the exact current spec hash.
Skip only when all hashes and saved JSON digest match. FULL/WAL commits each
pair immediately; bounds/Unknown are durable outcomes, new evidence changes
the input hash and recomputes only that pair. This format is separate from and
does not invalidate the stable running mech-pair-v1 resume contract. Later
optimized reducer code needs reviewed compatibility before accepting prior code.
Every invocation reports done/total, elapsed, rate and ETA, including skips.


`review_metadata.load_review_metadata(manifest_path, record)` consumes current
judge3 review manifests via the shared evaluator source loader. It validates
canonical source-record content agreement and preserves the whole adapter,
including exact INIT fields/projection indices, gold FULLREPLAY body reference,
its own kept map, stored/unavailable comparison refs and per-case inventory.
It always reports target_catalog.complete=false and admission unavailable:
source agreement does not authenticate native identity, eligibility or coverage.
The renderer raw-JSONL source digest and mechanical canonical-record digest are
different conventions and are not compared. This consumer implements no row
projection, graph closure, cross-case alignment or equality. Those remain shared
with the tool. No native endpoint is used.

Other-case later eligibility has no exported anchor. Graph/form/slot IDs are
local; own mutant-to-gold source paths and native row keys do not provide case
correspondence. No pair.top, name or ordinal cutoff is inferred. A coordinator
rule or explicit target receipt is needed before this catalog can be complete;
that gap does not prevent checking a supported main-case target independently.


`target_acquisition.acquire_main_target` consumes the shared tool's fresh gold
observer when v11 lacks the BODY table (all 55 calibration pairs). It runs no
component output substitute, and calls no second evaluator. The same full GOLD
observer replay supplies train and test; saved projected G must cross-check on
all expected train contexts first. Its receipt distinguishes fresh replay from
old stored refs and binds source/program/kept/layout and artifact. Unknowns stay
unknown. Main-target data acquisition does not make the all-case catalog complete.
The shared observer now supplies saved_train_contexts_complete and exact
required train-context count after excluding test display entries and checking
the complete train axis. The consumer verifies source/gold-program/kept/layout
hashes, context counts and required train/test axis, including cache returns.
Gold's callable template is used; borrowing the mutant template requires shared
exact callable-row-path agreement. Actual evaluator qualification is pending;
source/API agreement is not a successful replay or deployment claim.


## Settled executable consumers

The authoritative target scope is now G, all strictly later tables of this case,
and EVERY native table of EVERY other case. Other-case names are ignored and
kept maps are case-local. The previous other-case cutoff question is resolved.
Target execution bindings/aliases/ports still come from the shared catalog;
unsupported bindings remain Unknown. No other-case ordinal zip is introduced.

`clause_evidence.py:clause_evidence` maps actual `judgetool-clause-v2` results to
mechanical evidence, checks source/route, every kept/train/test context, full
replay test authority and explicit provenance. Library-derived target fields need
one_row_per_X and restrictions_only proof. Unions additionally need needed X
rows and explicit nonredundancy; missing general union proof stays Unknown.
No raw replay success, reasons or judge prose establishes a grade.

`judge_merge.py:merge_final` merges checked final-v3 outcomes, including an empty
no-clause answer, with source-bound mechanical evidence. Unknown/no-kept results
do not supply completed negative answers. Candidate refusal never sets mutant
refused. All continuation outcomes are retained when the tool supplies kind.
`admission.py:admission` exports mech-admission-v1 with digest/source/grade refs,
whitelisted boolean evidence and no test rows. policy_eligible is a policy result;
receipt_authenticated remains false until the caller has authenticated its input
receipts. reduce_grades deliberately does not authenticate arbitrary input JSON.
The document owner must validate the referenced receipt chain before prompting.

`lib_plan.py:candidates` lazily produces type-compatible X projections, supplied
grounded lib computations and combinations of supplied restriction atoms, plus
explicit clauses (including union candidates). Atoms are syntax, never Python
lib evaluation; shared native checking/multiplicity decides admissibility.
Projection types only prune syntax (Position/Box share margin representation).
No observed-row literals or gold row lookup is generated. A finite plan is a
subset and is NEVER certified whole-space coverage.

`lib_pass.py` is the durable candidate executor. Jobs JSONL contains record_path,
source_sha256, manifest_path, ntrain, ntest, base_evidence and plan. It requires
settled source-preserving no-witness admission, excluding fits/lossy/DET. The plan
schema is mech-lib-plan-v1: optional candidates [{clause,columns,role,target}],
generate boolean (default true), restriction_atoms (grounded syntax strings),
computations [{atoms:[...],columns:[...]}], max_restrictions (default2). Grounded
registry atoms/computations must come from the shared registry-site adapter;
automatic registry grounding is not yet integrated. Every candidate is checked
by THE SAME ReplayEvaluator.evaluate, compatibility=false, explore=false. An
arbitrary non-G target fragment is refused until shared catalog binding is ready.

```bash
python3 "$H" --cpus 1 "$M/../runtime-5ee2f066/venv/bin/python" -B "$M/lib_pass.py" "$M/lib-jobs.jsonl" --output "$M/lib.sqlite3" --seconds 30 --candidate-seconds 0.5 --max-candidates 128
```

This is executable once source-bound jobs/shared plans are published, not a claim
that lib-jobs.jsonl exists or a full-space/qualification measurement. One native
operation has candidate-seconds; --seconds is the per-pair scheduling cutoff
between candidates, not a preemptive deadline on all nested evaluator operations.
The evaluator retains complete internal artifacts under judgetool/replays/mech-lib.
Candidate results commit immediately in SQLite FULL/WAL; final per-pair results
also commit immediately. SIGTERM finishes the current candidate and saves an
interrupted pair, which resumes from its durable candidates. Completed records
skip only with source/code/config/plan hashes and result digest matching. Hashes
include shared evaluator/surface/tables/checks, own planner/reducer and spec/runtime
configuration. Source edits during a run abort rather than misstamp receipts.
Source code changes require review before accepting an earlier code hash; no
compatibility is silently assumed. Existing labels.sqlite3 is never overwritten.
Each progress line includes done/total, elapsed, rate, ETA, gains, bounds, reuse,
unknown candidates and pair time. Output stores candidate and pair elapsed time
for the requested sample cost report; no new baseline run is needed.

`corpus_index.py` indexes ALL records, retained and corpus-filtered, from published
corpus task directories. It reuses run.records(include_filtered=True), whose
default kept-only behavior remains unchanged for the running legacy pass. Filter
classes (empty/equal/available/later/no_dependency) are recorded distinctly with
their stored authority; recoverable_gold is search evidence, not a filter class.
Equal recovered records are included. Unknown filter completion stays explicit.
Multiple source variants for one pair are retained by source hash, not silently
merged; final target/test grading must consume a selected authenticated source.
The index resumes by source/code/result hashes and commits each source immediately.

```bash
python3 "$H" --cpus 1 python3 "$M/corpus_index.py" "$M/../corpus-v11" "$M/../corpus-v12-body-full" --output "$M/sources.sqlite3"
```

Remaining dependencies requested from owners: automatic native registry-site
grounding, complete target-specific replay bindings, full X/G containment and
reader-visible tuple-difference receipts, program train/test fit/refusal, and
sibling/redundant searches using the settled independent-table inventory. The
old producer's fields do not certify these under the expanded scope. Shared
lib-multiplicity/general-union qualification is incomplete. No complete target
or whole-space negative is manufactured while any such coverage is missing.
