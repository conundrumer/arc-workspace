# Pair judge tool

The tool and mechanical lib pass share `ReplayEvaluator`. It uses the existing
`StudyProgram.from_sexp` and `StudyTaskEvaluator.gold_tables` bindings. It runs
the whole mutant program, with the candidate inserted after its dependencies
and OUT retained. It matches returned entries against gold's saved DET values
on every dependency slot. No compatible entry means **unknown**. It neither
installs saved values nor assumes OUT prunes assignments.

Use the pinned study Python, from this directory:

```sh
../ast/run/runtime-5ee2f066/venv/bin/python judge_tool.py --pair PAIR_DIRECTORY --limit 30 run --clause-file clause.sexp
../ast/run/runtime-5ee2f066/venv/bin/python judge_tool.py --pair PAIR_DIRECTORY check --clause-file clause.sexp --columns '["P","Col"]'
../ast/run/runtime-5ee2f066/venv/bin/python judge_tool.py --pair PAIR_DIRECTORY alternative --clause-file clause.sexp
../ast/run/runtime-5ee2f066/venv/bin/python judge_tool.py --pair PAIR_DIRECTORY final --answer answer.json
```

`run` explores without grading. Printed tables contain train rows, complete row
counts and omitted counts; test rows are withheld. `--limit` bounds total rows.
`check` and `alternative` return one of the specification's six clause outcomes.
Reasons are evidence for a person, never inputs to the checks. No grade is made
here. The labeler owns admission, grades, mechanical coverage and attributes.

A final answer has this shape. An empty clauses list means no clause found.

```json
{"schema":"judge-tool-answer-v3","pair_id":"...","render_version":"...","clauses":[{"kind":"recovery","clause":"(RULE &fix ...)","columns":["P","Col"],"reasons":["X supplies P and Col; the named relation removes the extra rows."]}]}
```

Each clause has `kind: recovery|alternative` and one or two evidence reasons.
`columns` is optional, and names exported variables in target physical order;
explicit repeated names are supported. Without `columns`, the whole exported
table is compared: no output column is silently discarded. The final check reruns every clause and
retains its submitted kind even on refusal or unknown. It binds source, adapter,
pair, render version and specification identities. `judge_run.completed=false`
when an outcome is unknown or the mechanical admission is unauthenticated;
manual HELD qualifications are not completed judge runs. No-kept or missing comparisons cannot prove a
negative. The judge supplies no label or grade.

`surface.prepare` maps source relation names and `&X` to the real program. It
uses the producer's exact INIT projection and P's `inline_init`/`canonical_or`.
INIT adapter witnesses stay private. Duplicate projected fields that share a
source column alias the same native value. It does not turn a submitted RULE
into a DET. Routine DET-kind pairs are excluded.

Checks use complete train and test entries from fresh gold replays.
`checks.observe_gold` acquires G's exact body/INIT projection. `live_targets`
replays every exported gold case and enumerates its actual returned tables:
same-case tables after the point and every other-case table. Stored snapshot
rows, omitted-alias declarations and population completeness flags do not supply
or gate target values. The existing native export inventory/from_stream APIs
supply cases absent from saved corpus records. Kept DET values remain the only
saved values used to select contexts. Other-case names are ignored and DET
ordinals are never zipped. An alternative matching a target receives the same
recovery check. Continuation references also come from fresh replay.

`tables.compare` matches columns by name, otherwise type, component ids by a
consistent renaming, and Position/Box by four margins. `tables.contains` shares
that comparator for the mechanical pass. A missing compatible replay entry or
an operation reaching its bound remains unknown.

Stdout is a compact judge view: outcome, reason, bounded train table with row
counts/omissions, and differences for each target. Identical differences are
grouped with every target named. Test differences identify inputs without
revealing target test rows or row counts. Hashes, paths, settings and receipts
remain in `sessions/PAIR_ID.jsonl`. `--record FILE` before the command also
writes the full checked result to a specified file inside judgetool. Import
consumers still receive full evidence from `evaluate`; the stdout view is not
a replacement for a durable checked record.

Direct recoveries require target columns at a positive X site. Lib-computed
columns require native prefix replays proving exactly one row per X row.
Multirow libraries and unrelated producers are partial sources. Union branches
are checked for their X source, then a native counterfactual proves X branches
supply needed target rows; an explicit X-not-redundant receipt is also required.
Unresolved scoped provenance remains unknown, never verified.

## Shared import API

- `ReplayEvaluator(*, config=None, deadline=30, artifacts=...)`; reuse for a task,
  then `close()`. Native limits apply to each operation, not an entire lib search.
- `evaluate(record, clause, target, columns=None, explore=False, row_limit=100)`;
  target contains `adapter`, `ntrain`, `ntest`, and optional `source`, `mode`.
- `replay_program(record, whole_program, inserted_form, candidate=...)`: one
  execution core, assignment-labelled evidence, no policy conclusion.
- `registry_interfaces(record)`: unchanged native registry, typed sites/readers,
  source/program/runtime hashes. It evaluates no lib relation in Python.
- `checks.observe_gold`, `tables.TargetStore.mutant_input`, `catalog.acquire`,
  `catalog.equality`, `live_targets.acquire`, `tables.compare`, `tables.contains`: shared acquisition and
  comparison; the labeler supplies its own grade policy.

Internal artifacts retain the entire inserted program, native report, settings,
and all returned entries of the requested table, including other assignments.
They contain test evidence and are not judge-facing documents. No downstream
claim is built on other assignments. The judge sees only bounded train rows.

## Review and historical calibration

[review/index.md](review/index.md) links four actual recorded sessions with
commands and exact outputs. No model judge was called. `record_review.py`
refreshes these requested recordings; `calibrate.py` streams explicitly supplied
source-name candidates without inventing migration.

`reproduce.py` is the separate, explicit historical P profile. It preserves P's
old syntax adaptation and train comparator, so its results are not current-spec
certificates. The requested historical replay produced 47 verified, 7 refused,
1 incomplete, versus P's 46/7/2: one former Deadline now completed. Both runs of
the four historical negatives ran all four and verified none. See
`reproduction-current/summary.json` (current paths/settings), with prior runs in
`reproduction/summary.json` and `reproduction-19efc068/summary.json`. Exact
Deadline totals cannot be made invariant to machine load.

The obsolete `native-api.md`, `judge-tool-brief.md` and older integration review
are historical proposals, not implemented interfaces. No new native endpoint
was built or requested. n-judgedoc owns the whole current brief.

`candidate_train.candidate_training(record,adapter)` is a separate, no-evaluation
feature provider. It selects the explicit native `evaluation.table_indices.mutant_all`
BODY, not the document's KEPT index, then decodes TRAIN/TASK entries only and
uses the same physical projector. It never calls decode_kept/compatible or
returns test rows. TASK broadcast requires native TASK entries and authenticated
task evidence. It labels population as all stored assignments, exhaustive=false;
no exhaustive branch-available population is inferred.

`raw_body.observe_gold_body(ev,record,native_base=...,ntrain=...,ntest=...)`
acquires a fresh gold table in the exact raw stored mechanical BODY layout,
including INIT private witnesses. It authenticates gold_all against the exact
body view and uses the producer's `headers.bind_body_schema` to map physical
columns by native LabelId, then copies the exact exported BODY/key node into a standalone observer through
the same replay core, including mechanical DET bodies and private INIT labels.
It does not assume that body order is written-relation order or substitute an
INIT public input projection. Missing scalar identities fail closed.

## View comparison targets

```sh
../ast/run/runtime-5ee2f066/venv/bin/python judge_tool.py --pair PAIR_DIRECTORY --limit 30 view-target --target-id T7 --offset 30 --assignment 0 --example train1
```

The document's target ID selects a comparison-only table; this does not grant
clause read access. Values come from fresh full gold replay. The page contains
train rows only, with complete counts and omissions for the selected kept
contexts. Assignment indices are zero-based within the target's own case.
`--offset` skips rows across the selected groups; `--limit 0` prints counts only.
See [target-view-usage.md](target-view-usage.md) for the brief's exact usage.

Regenerate recordings into a new directory, preserving frozen review:

```sh
../ast/run/runtime-5ee2f066/venv/bin/python record_review.py --pairs ../judge3/calibration2-v4 --output review-v4
```

The new display rollout and target-view recordings are in
[review-v4/index.md](review-v4/index.md), tied to the separately regenerated
55-pair calibration2-v4 document version. Frozen v3 recordings are preserved in
`review/`. The v4 view recordings include a later same-case target and two
pages of an other-case target, with kept/input selectors and complete counts.

## Case collection for mechanical consumers

`case_collector.acquire_case(ev, record, case_context, ntrain, ntest)` collects
unscoped native tables and BODY observers in one full gold replay, cached by
case/program/kept values/settings. The JSON-serializable bundle retains each
original table's full `native_schema` from `reader.schema(table)`. Source code
comes from `CODE_ROOT`; relative catalogue paths resolve under `DATA_ROOT`;
source-name recovery uses `MAIN_ROOT` through `study_paths`.

`select_pair(bundles, record, adapter, ev=ev)` selects the point projection,
later same-case tables and all other-case tables without another replay.
Available references carry their original physical schema for the canonical
callable provider; this metadata does not grant read access. `compare_target`
uses the shared comparator, including Cartesian contexts across cases, for
whole-table equality or projected containment. `evaluate_cached` delegates to
the existing clause checker with cached targets and one mutant replay by
default. Additional provenance operations that exceed that cap remain unknown.
Persist bundles and call `clear_cache(ev)` at the task boundary to release them.

This additive collector has source/syntax review only; no collector replay or
runtime qualification has been performed. Unsupported BODY observers remain
explicit gaps. The v5 recorded sessions use the existing tool route and remain
data under `DATA_ROOT/judgetool/review-v5`, separate from collector qualification.

Stored snapshot consumers use `tables.decode_kept` to bridge native `slot N`
and fresh `&rN` dependency names while delegating value decoding to the existing
P helper. `kept_groups` and replay coverage share this adapter. Schema-only
comparisons use `tables.comparison_type`, which treats Position and Box as four
margins without changing the lossless native schema.

For historical selector witnesses, `TargetStore.selector_snapshot(record,
base, identity)` selects the exact saved source: an explicitly certified
DET-independent `ex_input` fallback comes from `record.native.gold`; other
selectors come from `record.full_replay.gold`. The original table index and
selector are authenticated within that source. The returned receipt records
which source was used; a table index is never transferred between snapshots.

Mechanical pass 4 may set `ReplayEvaluator(artifacts=DATA_ROOT/'ast/run/mech4'/
SUBDIRECTORY)`. Artifact paths are resolved and restricted to that root or the
existing `DATA_ROOT/judgetool` root. This is an output-path allowance, not a
separate evaluator or a change in verification policy.

`tables.compatible_kept` compares held DET contexts with one consistent Ident
renaming across all slots. It uses P's decoded held prefixes and native entry
values, encoding slot-tagged rows for the existing bounded relational comparator.
It never independently renames each slot or unions entries/models. Both replay
coverage and `kept_groups` use this same matcher.

`raw_body.observe_gold_body` is a mechanical observation route, separate from
judge admission. It copies the exact exported BODY node text (and the exact
INIT key BODY for an input), preserving the original full program and OUT.
It can observe DET bodies without reading a reader-projected DET relation.
This newly repaired route and the held-context adapter await runtime qualification.

### Shared repair handoff

`raw_body.observe_gold_body` now falls back, at most once, to
`ReplayEvaluator.gold_point_body(record)` when a standalone observer cannot
preserve scope or produce complete kept answers. This uses the existing
`TaskEvaluator.replay` and `evaluate_pair` APIs and the exact canonical catalogue
source handle. Native gold OUT/FITS precedes the original-scope BODY query under
full HeldAssignments; native entry maps bind those full contexts to saved kept
values. Only GOLD evidence is retained. The native API also performs historical
mutant-side work, disclosed in receipts; its verdict is not reused and no base
label is written. There is no new endpoint or copied library evaluator. The
wrapper allows at most one standalone replay plus one native pair call.

`out_fit.check(ev, record, ntrain=..., ntest=..., gold_cache=None)` returns plain
JSON with `fits_test` (bool/null), `complete`, `reason`, an `evaluations` count
dictionary, `evidence_files` path/SHA256 pairs and a binding receipt. It copies
the exact native OUT BODY/key projection into an observer before the original
OUT, using `out_bindings_json` LabelIds. Gold all-assignment entries are cached
by task/case/program/runtime/settings/code/task-file/axes, and each pair selects
its kept contexts through `kept_entries`. Cached values remain JSON-compatible
and are not mutated. Complete TEST equality to gold is the approved sufficient
positive. Additional/differing families remain unknown unless a sound negative
is established; this is not a replacement implementation of accepted-grid fit.

`replay_program(..., retain_forms=[...])` retains all rows/assignments/models at
those exact form indices in artifacts. It is mutually exclusive with
`retain_all`; list size and indices are bounded by the submitted program.
Artifact roots also include `DATA_ROOT/ast/run/mech5`, in addition to mech4 and
judgetool. These changes are source-reviewed, not runtime-qualified by a
mechanical launch. Only separately authorized four-session judge-tool recordings
were regenerated; their reader pages remain under `DATA_ROOT/judgetool/review-v5`.
The subsequent dataset redesign and six dataset-only sessions are still pending.

Specification prose is not runtime provenance: the CLI and evaluator do not
read or hash the judge specification, and edits to its wording do not invalidate
results. Historical records may retain specification hash fields; they are not
used as validity gates. Pair and render identities identify the input supplied
for a recorded session, rather than a current prose policy. Code/runtime,
source-data and configuration receipts remain the execution provenance.
