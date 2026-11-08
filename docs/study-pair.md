# Stage 3: clause-pair evaluation

```python
report_json, gold_tables, mutant_tables = arclog.evaluate_pair(
    gold, point, gold.construct(spec),
    task="007bbfb7", tasks="engine/data/tasks",
)
```

The two table objects are the existing `arclog.CaseTables`, with the export's
flat columns, packed `int32` values, frames, extents, column provenance,
projections, and assignment records. They share one native task session,
so identity-valued cells have the same namespace. The binding releases the
GIL for evaluation and column construction. Independent calls can run in
parallel.

`table_indices` in the JSON report identifies four tables, using the
returned objects' table numbering (including the two evidence tables):

- `gold_all` and `mutant_all`: the complete clause body over each program's
  own incoming DET assignments.
- `gold_kept` and `mutant_kept`: that complete body at each gold FITS
  assignment, in `kept_assignments` order. Native DET columns retain only
  the parameters that the clause reads.

Earlier relation tables are included because the native frame and
provenance records reference them. Their faults and stops are retained.
Bodies are compiled directly from the original checked program to IR views
containing the exact conjuncts and their enclosing binding context (INIT
keys, CHOOSE context, and RIGID_DET keys). No public clause is reconstructed
or rechecked. Nominal types, zero-valued columns, aliases, recursive reads,
and original source paths stay in their checked context. Evaluation preserves the checked owner's task-wide or
per-input side. It does not use a decoder's partial approximation of a
final negation or constraint.

FITS walks the gold program's non-pick DETs in engine dependency order,
including parameters of an unused clause. This keeps the clause's incoming
parameters explicit even when OUT does not read them. `gold_assignments`
records each reached assignment and its FITS result. An assignment is kept
when every OUT model equals every train output. `kept_assignments` retains
all such assignments. `gold_fits` is null when a stop/fault prevents a
negative answer. The full mutant program through OUT runs at those exact
gold parameter values; the mutant never selects its own FITS assignment.

`outputs` records each train example and model. `equals` requires a fully
defined grid of the right shape. For defined grids, `differing_cells`
counts unequal cells over the union of coordinates, with missing cells
counted as different. Undefined OUT counts all expected cells as missing.
For malformed OUT rows, it counts expected cells that are missing,
ambiguous, differently colored, or in a different frame, plus occupied
extra coordinates. Those cases carry `grid_defined=false` and a reason.

`comparisons` compares native tables over their own assignment domains;
`kept_comparisons` compares at the same gold FITS assignments. At a matched
assignment, model alternatives form a Cartesian comparison family, identified
by `gold_model`, `mutant_model`, and `model_alignment="cartesian"`. Indices
are local to each program; equal indices or counts do not establish a shared
pick choice. Removing a pick dependency can legitimately change the number
of models. Each model pair and its visited rows charge the comparison work
cap, including empty and undefined values. Task-wide values are explicitly broadcast over examples when a mutation
changes scope; comparison records mark `scope_alignment`. Row tuples
are aligned by original AST label identity and type. The relation describes
the **mutant relative to gold**: equal, subset, superset, or overlap (which
can have zero kept rows). Counts are `kept`, `extra`, and `missing`.
Different typed schemas have no equal tuples and report
`schema_equal=false`. An assignment absent from the other domain is
explicitly tagged `assignment_presence=gold_only` or `mutant_only`, and its
rows are missing or extra, respectively. Native `Undefined` is a completed
semantic value, including at non-FITS assignments where a construction's input
domain is violated. Such comparisons report `comparable=false`,
`comparison="undefined"`, each side's `gold_value` / `mutant_value` and known
row counts, with null relation and kept/extra/missing counts. Undefined is
never replaced by empty rows or reported as an evaluator fault.
DET names are aligned through
the engine writer's source/decode correspondence, not numeric slot guesses.

A pair and its components report `complete`, `stopped` with the reached
bound, or `fault` with its reason. No fault is replaced by an empty table or
a guessed assignment. Projections and extent failures remain visible.
A projection stop leaves a table over the projection cap with its entries'
row counts alone and is listed in `projection_stops`. An extent stop at its observation budget or an evaluation
bound is listed in `extent_stops` and leaves row status intact. Extent faults
and machine-dependent stops remain faults and stops of the table.
One query evaluates a clause, finished or in progress, on one example at one
assignment. Its evaluations read the native binding and row caps. Relation,
body and OUT walks count work without a total work cap; a bounded assignment
loses only its own rows and later assignments remain available, and the
status of the table, its form and the result stays as the other assignments
give it. A stop of that kind is listed in `assignment_stops`, with its table,
example and assignment, and its entry stays stopped. The search for
projections reads each value's rows as effort, and extents have an
observation budget of their own. Row comparison charges row
visits to its own bounded budget before materialization. Native run, assignment,
request work, request byte and cancellation bounds still apply. A panic becomes an explicit pair
fault. A complete pair can have no FITS assignment.

## Task reuse and runtime corpus inspection

The kept-FITS body pass reuses complete models already evaluated in the
all-assignment pass on the native plain-body branch. The evaluator and reuse
eligibility share `BodyView::uses_owner_context`; recursive owner-state inputs
remain native held queries. Reuse requires the same example and every required
DET value, and every matching entry must agree on the entire ordered model
vector, including empty and undefined models. Stops and incomplete walks do
not certify reuse. Full held assignments are still validated, and held table
metadata, projections, extents and proofs are built in their own receipt context.
No searched table is relabeled as a held table.

Corpus consumers share the complete native writer artifact with mutation
certification. `StudyProgram::written_stream` retains one `WrittenStream`
(tokens, token paths, declaration slots and form spans) for its immutable
checked program and first registry/settings context. `decode_stream` derives
its ids/model/paths from that same artifact, and pair evaluation uses it
instead of writing each certified mutant again. A different registry or any
different `DecodeSettings` field gets a write in that context, never the
first context's cached artifact. The raw checked-program writer adapters
remain available and derive their results from the same writer.

Dependency-prefix matching constructs only the final retained key. It walks
form paths once, compares the one possible cached boundary by length and
then by exact source/path/token content, and avoids allocating every
cumulative token prefix. The retained key bytes and source-identity contract
are unchanged. Relation interning also recognizes immutable `Relation`
clones by their shared hash-cell **owner**, without computing or comparing
the hash value. `RowSet::shared` identifies only one part and is insufficient
for that proof. Independently constructed relations still use the existing
exact row comparison. Within that comparison, a column-matched part sharing
its `RowSet` storage needs no row membership scan, and every other part is
still checked; cache keys, eviction and bounds are unchanged.

The recorded corpus-v8 phase shares were evaluate 57.7%, inclusive
native_decode 26.4%, filters 7.1% and draw 5.6%. The native_decode phase also
contains lossless storage, not just typed filter views. Eliminating it
entirely would yield only 1.36x overall; a 2x improvement there would require
about 2.19x evaluation speed to reach 1.8x overall. The first 80 saved pairs of 15113be4, 47996f11 and 5207a7b5 spent
119.76/164.04, 54.89/57.78 and 77.34/84.05 seconds respectively in mutant
clause evaluation. If half of those clause times were eliminated, the
corresponding evaluation speedups would be 1.57x, 1.90x and 1.85x. At the
recorded 57.7% evaluation share this is roughly 1.27–1.38x overall. This is
an optimistic conditional estimate: those timings do not separate held model
queries from annotations or establish how many queries qualify for reuse.
It does not establish a 1.8x whole-corpus gain. In fact, all sampled pairs
from 47996f11 and 5207a7b5 had zero kept assignments, so this reuse saves no
second query there. All three samples stopped overall; 15113be4 had one
kept assignment, whose query reuse eligibility is not established by phase
timings. These are Amdahl limits,
not measured speedups. Saved expensive-task samples put 73--95% of evaluate
in mutant_clause. They do not separate its writer/prefix, query and extent
costs, so the allocation reductions above do not support a numerical 1.8x
claim. No baseline or measurement run is needed to establish these changes;
the next real corpus run supplies their runtime evidence. Python storage
optimization and bounded extent materialization are separate coordinated
changes; every native table and its stop/fault evidence remains exported.

For a corpus, construct one `arclog.StudyTaskEvaluator(task, tasks, settings)`
per task. Its `from_stream(ids, model)` begins a new case and releases the
previous case's observations and native result-cache allocations, including
hash-table capacities. Use `evaluate_pair(gold, point, mutant)` for its pairs,
and call `finish_case()` in a `finally` block. Passing a different gold handle
to `evaluate_pair` or `gold_tables` also activates a fresh case. Task evidence
and the interned identifier namespace remain available across cases.

Only one active gold FITS observation, one current gold body, one optional full
gold relation-table result, one cumulative native dependency prefix and one packed
column prefix are retained. The body entry is replaced before another body
is built. Body queries use the original checked IR, without retaining
synthetic view programs or check caches.
The task never retains a history of gold handles, mutations or cumulative
prefix snapshots. A later visit to a released handle creates a fresh observation.

The native prefix's row estimate and packed prefix's owned capacities share
an admission budget of half `session_bytes`. Packed accounting includes nested vectors, strings, table names and
run-interning metadata. Packing's relation-address memo is dropped before a
prefix is retained, so it cannot keep native relation indexes alive. Checked
program metadata and active gold observations are limited to the current case;
this admission budget is not a cap on temporary native evaluation or returned
Python buffers. Native work/row/assignment bounds still apply to that work.
Each report includes current cache entry counts and byte estimates.

An exact matching source prefix reuses its cumulative native relation tables;
only declarations after its boundary are evaluated. Source ordering is written once for the active gold program. The
packed prefix preserves row-run interning and appends each side's two body
tables, preserving the full buffers and offsets. Repeated relation rows within
one packing operation are sorted once at each typed schema.

`evaluator.gold_tables(gold)` returns `(status_json, CaseTables)` containing
the full export relation tables and evidence in the same task session as
pair tables. Native evaluation is retained for the active gold case, including
explicit stops and faults. Call it once when recording each gold case. A table
over the projection cap gives its entries' row counts and its projections in
place of its rows. With `held_rows=True`, each entry gives its rows as its
evaluation holds them: a product of parts over the projection cap gives its row
count and its parts, as the table's projections, and every other entry its rows.
It runs under no clock, so its rows do not depend on machine load. A stop at a cap of a query, at `TABLE_ROW_WORK` bindings counted over one assignment of a table, or at the assignment byte budget of the settings (the bytes that the assignment holds at a time, so it does not depend on what the session held before), rejects that assignment alone ([`ReachedBound::is_assignment`](../engine/arclog/src/eval/values.rs)): its entry stays a stopped entry, the other assignments of the table, example and call go on and give the rows they give alone, and the table, its form and the result stay `complete`. The call lists each such stop in `assignment_stops` (`table_form`, `example`, `assignment`, `model`, `reason`, `form`; a stop of the walk of an example, before any assignment, has `assignment` and `model` null; the packing adds its own with `source` `packing`). The walk of a table stops at the assignment cap, at the request work cap of the settings, which sums the work of the whole call, and at the request byte budget of the settings, which counts the bytes the request holds at a time; a table that the request work cap stops has the reason `RequestWork`, and one that the request byte budget stops has the reason `RequestBytes`, which no earlier assignment stop hides. The session's byte bound (`TABLE_BYTES` for this call) makes the session evict its caches and stops no walk.

`evaluator.gold_tables(program, form=F)` returns the tables of the top-level form at index `F` alone, with no evidence, and the rows that the full result gives them. Call `gold_tables` without `form` on a program first. A later call with `form` on a program that opens with the same forms evaluates only from its first form that differs through `F`. Those forms see the result cache as the evaluation of the earlier forms left it, so their counts of work are what a full evaluation counts. Where one of their tables stops at a cap of work or at a byte budget, or the cache evicts, the forms through `F` are evaluated again from the first form, in a session of their own. The call leaves the active case and the held program as they were.

`gold_tables` without `form` keeps the walk of each table, from one program to the next, in the evaluator's form cache (`study_pair::form_memo`). A walk is the table's rows on each example at each assignment of the `DET`s it reads. Its key is the content of the table's form (`ResolvedProgram::content`: the form's text, with each read standing for the content of its maker), the Name and place of the table, the content of each `DET` in the order of the assignments, and the text of the form and of each form it reads at any depth, since the work of a search follows the order of a clause as written and the content is free of that order. A program that holds a form that has that key takes the walk, and its stop, from the cache, and does not run it. The cache also keeps the lookups, ids and stores that the walk made in the result cache. A program takes the walk only where each kept lookup finds in its own result cache what it found, and the replay then makes the ids and stores. The count of work of a later table, and with it its stop at `TABLE_ROW_WORK`, is then what a walk of the whole program counts. A walk is not kept, and no walk is taken, where any of these holds: the cache is off (`form_cache=False`); a stop of the program's size stops that the walk could read exists; a stop of the deadline, a cancellation or the byte bound, or a fault, is in its rows; the result cache evicted during the walk, or would evict during the replay; the table's form is below the top level; a `DET` of the walk is an output of an instance or a `RIGID_DET`; a form that a stop names has no one form of its content in the program; or the walk's events passed the limit, or it counted little work. Such a walk runs as it would without the cache. The cache keeps only a walk that counted at least 2^14 bindings and 32 bindings for each event it made, since a replay costs about an event; its capture stops at 2^14 events. The cache remembers the key of a walk that it does not keep, and runs that walk with no capture. It counts each relation once, however many walks hold it: two relations of the same rows and columns of parts are one. It holds at most a quarter of `session_bytes` (`form_cache_bytes=` sets another), which the native prefix and the packed prefix then do not use, drops the walk used least recently first, and a case's end does not release it. `clear_form_cache()` releases it. Where a caller sets a request's count of work (`PairCache::set_request_work`), a walk is taken only where that count has room for the work the walk counted, which the walk then charges to it, and a walk that ends with that count past its cap is not kept. Each report of `gold_tables` has the cache's counts as `form_cache`. The counts of work in the report, such as `largest_counts`, give the work that ran. A walk taken from the cache does not run, so with the form cache on they can be lower than in a run without it, while the tables are equal.

The task evaluator defaults to `compact=True`: the first pair for a gold
handle contains the gold assignment records and train observations;
subsequent pairs refer to that record through `gold_observation_ref`.
References are local to the evaluator. Set `compact=False` for standalone
reports containing repeated gold observations.

Run the checker archived at the selected runtime's `ready.checks` with its
exact `ready.python`, using explicit task and export paths. The scratch
compatibility entrypoints `check_stage3.py` and `check_stage3_fast.py` delegate
to that archived checker after canonical provenance authentication. They carry
no independent inspector, serializer or status policy and fail when the
selected runtime lacks its checker; they never fall back to a live checkout.

This walks every case in the real stream export, draws one K=1 mutant per
point by default, and evaluates calls concurrently. JSONL is flushed for
every draw and pair, and a heartbeat prints done/total cases, elapsed time,
and case/pair rates every second. It checks actual native row offsets,
assignment references, comparison counts, and kept gold train outputs at
runtime. It runs no tests. `--native-dir DIR` additionally saves native
buffers as base64 alongside their dtype metadata. `--task`, `--case-limit`,
and `--point-limit` restrict a short inspection; `--work-cap 0` exercises
explicit stops.

Native extent derivation now widens the original typed IR, preserving the
result interface while exposing positive branch witnesses. It never
constructs a synthetic public clause. This subsumes the owner-scope fix
reproduced on gold `009d5c81` in `arclog.stream_tables`, and also removes
branch-flattening alias and dropped-interface failures. Body query model
enumeration uses the same native pick walker as relation evaluation.
Runtime verification requires a wheel rebuilt from these sources.

Recursive instance inputs retain typed relations on their shared graph node.
An `Unfold` model carries its reached state contexts. Queries of inputs that
read the instance's outputs run at each state's key/cursor and state-local
output rows, with the native bound join; their rows are unioned within that
model. Negations therefore see one state, rather than the union of states.
The same input relations are available to native table and extent lookup.

`evaluator.replay(gold, identity_json)` returns `(point, mutant)` for one
exact historical identity. It reconstructs only the recorded leaf edits,
checks the full candidate again, requires an exact identity round trip, and
runs the AST audit. A historical mutant that the current checks refuse
raises its diagnostic; it is never replaced by a new draw.

For an isolated performance wheel from the enclosing `ast` directory, use
`engine-perf/scripts/build_study_perf.sh` through `run_heavy.py`. It builds the `engine-perf`
worktree into `target-perf` and `wheels-perf`, installs only into `venv-perf`,
and prints build progress every five seconds. Existing `venv` and `wheels`
remain available to live runs. After the optimized runtime inspection,
`engine-perf/scripts/compare_study_pair.py stage3-fast.jsonl <candidate.jsonl>` expands compact
gold references and compares mutation identities, reports, and native buffer
inspection summaries. Only timing and cache telemetry are excluded.

The bounded corpus driver is versioned as
`engine-perf/scripts/check_study_pair_corpus.py` (it reads the enclosing `ast`
helpers). It gives every case its own Python frame and releases pair buffers
before the next evaluation. Case-finalization also runs on faults.

Resume the existing race from `ast` after rebuilding and stopping its old
writer:

```bash
engine/scripts/run_heavy.py --cpus 12 --need soon \
  venv-perf/bin/python -u engine-perf/scripts/check_study_pair_corpus.py \
  --jobs 12 --resume --output stage3-fast2.jsonl
```

`--resume` appends without re-evaluating any task/case with a terminal `case`
row, including an explicitly faulted case. An interrupted case without that
row restarts from its beginning, so its earlier partial pair rows remain as
evidence. Gold observation reference numbers start above the file's per-task
high-water mark. A torn final JSONL row is truncated before appending; valid
rows are preserved. `--resume-from PATH` is repeatable and reads additional
checkpoint files without modifying them. Summaries report this invocation's
work and its skipped case count; progress continues to print every second.

After integrating the checked-IR fixes and memory lifecycle, one isolated
wheel supports fault replay and corpus resume. Build only committed source
with `scripts/build_study_runtime.py --revision <commit> --output <fresh-runtime>`;
the build owns its source archive, wheel and interpreter directory,
and removes its Cargo target once it verifies the install.
Select the approved runtime from the corpus workspace's `run/CURRENT.json`
through the native provenance selector, rather than assuming a venv path.
Keep output provenance and checkpoint compatibility when using
the archived `check_study_pair_corpus.py` with `--case-manifest ...
--replay-identities --gold-tables` or `--resume --output ...`.
