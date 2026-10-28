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
`kept_comparisons` compares at the same gold FITS assignments. Task-wide values are explicitly broadcast over examples when a mutation
changes scope; comparison records mark `scope_alignment`. Row tuples
are aligned by original AST label identity and type. The relation describes
the **mutant relative to gold**: equal, subset, superset, or overlap (which
can have zero kept rows). Counts are `kept`, `extra`, and `missing`.
Different typed schemas have no equal tuples and report
`schema_equal=false`. An assignment absent from the other domain is
explicitly tagged `assignment_presence=gold_only` or `mutant_only`, and its
rows are missing or extra, respectively. DET names are aligned through
the engine writer's source/decode correspondence, not numeric slot guesses.

A pair and its components report `complete`, `stopped` with the reached
bound, or `fault` with its reason. No fault is replaced by an empty table or
a guessed assignment. Projections and extent failures remain visible.
Table evaluations use the native table work caps; OUT shares a work budget
with the gold assignment walk; row comparison also charges row visits to
a bounded budget before materialization. Native run, assignment, deadline,
and cancellation bounds still apply. A panic becomes an explicit pair
fault. A complete pair can have no FITS assignment.

## Task reuse and runtime corpus inspection

For a corpus, construct one `arclog.StudyTaskEvaluator(task, tasks, settings)`
per task. Use its `from_stream(ids, model)` and
`evaluate_pair(gold, point, mutant)` methods. This retains the native task
session and evidence tables across cases, the checked-body compilation
cache, and bounded prefix tables (128 entries, at most 64 MiB estimated).
Gold FITS is evaluated once per gold handle; complete gold clause tables
are cached by `(gold handle, body AST path)`. Each report includes phase
timings and cache counters. Independent tasks can run concurrently.

`evaluator.gold_tables(gold)` returns `(status_json, CaseTables)` containing
the full export relation tables and evidence in the same task session as
pair tables. Native evaluation is cached once per handle, with explicit
stops and faults retained. Call it once when recording each gold case.
Gold handles are retained until the task evaluator is released.

The task evaluator defaults to `compact=True`: the first pair for a gold
handle contains the gold assignment records and train observations;
subsequent pairs refer to that record through `gold_observation_ref`.
References are local to the evaluator. Set `compact=False` for standalone
reports containing repeated gold observations.

From the enclosing `ast` directory, after `build_stage1.sh`:

```bash
engine/scripts/run_heavy.py --cpus 12 --need soon \
  venv/bin/python -u check_stage3_fast.py --jobs 12 --output stage3-fast.jsonl
```

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
