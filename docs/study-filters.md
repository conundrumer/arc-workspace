# Native study filters (stage 4)

`arclog-tables/src/study_filters{,.rs,/}` owns the operations. Thin
`arclog-tables-py/src/study_filters.rs` bindings release the GIL. No token
positions, filesystem reads, publication metadata or program fingerprints
participate. `study_filter_policy()` returns `native-filters-v1`.

```python
final = arclog.study_final_output(gold_program, mutation_point)
recovery = json.loads(arclog.study_recovery(
    json.dumps(gold_table), json.dumps(mutant_table),
    n_train=n_train, final_output=final,
    available=json.dumps(available_tables),
))
equality = json.loads(arclog.study_table_equal(
    json.dumps(mutant_table), json.dumps(candidates),
    earlier=json.dumps(gold_context_at_point),
))
normal = json.loads(arclog.study_normalize(
    json.dumps(table), earlier=json.dumps(gold_context_at_its_point),
))
```

All operations accept `max_work=10_000_000` and no clock: a stop at it
depends on the inputs alone. Each result holds `work`, the units counted, and
`work_cap`, `max_work`. Exhaustion, missing complete rows, incompatible input
universes, or missing required normalization metadata return `status:
"unknown"` with a reason. An exhaustive negative is `determined`; a
different shared prior DET value is `not_applicable`. Never interpret
unknown as empty, unequal or unrecoverable. These are table operations:
Python supplies the task/case inventory, applies quotas and persists results.

## Input contract for the run thread

One table value is at **one explicit DET assignment**, with set-valued rows
at each input. Use the native `evaluate_pair` kept tables at the kept gold
assignment; never take a mutant's independent fitting assignment.

```json
{
  "types": ["Position", "Color"],
  "columns": ["P", "Col"],
  "rows": [[[0,2,0,2,1]], [[1,1,0,2,3]], []],
  "assignment": {"&background": [[0]]},
  "kept_assignment": {"&background": [[0]]},
  "head": "RULE",
  "relation": "&example",
  "flows": [[[0,0]], [[0,0]]]
}
```

`rows` is the complete native physical row array, separately for each train
input then each test input. A Box/Position/Offset occupies four i32 margins;
all other logical columns occupy one i32. Zero-column rows are `[]`, so
`[[]]` is a present zero-column row and `[]` is an empty relation. Duplicate
rows are removed natively. Missing rows are null/absent, **never** `[]`.
Full values are required; samples, counts, projections, stopped/undefined
entries are not a substitute. Task-wide native rows must be broadcast to
the input universe (and split by their Example value where present), as in
the old `scan_test.all_rows`.

Assignment maps contain actual sorted DET row values keyed by the gold AST
relation identity, not local assignment indices or unaligned decoder slots.
Pair values and any semijoin sources must share the native Ident namespace;
use the stage-3 shared session, or a proven translation from that session.
`kept_assignment` is the full kept assignment when this table reads only
part of it. Recovery can exclude the mutated form's own DET result by
listing it in `current_relations` on gold/mutant. Shared prior DET values
must agree. Candidate-specific DETs cannot be silently guessed for a join.

`flows` has one list per column, each source either the native object
`{"kind":0,"source_table":2}` or the old tuple `[kind, source_table, ...]`.
Kinds are copy/computed/constant/lib-name, 0/1/2/3. Include the original AST
`head` and actual flows for normalization; empty flow lists are meaningful.
Earlier context tables have the same shape and assignment metadata.
`relation:"ex_output"` or `table:1` excludes output evidence from
restatement/lookup; the inputs-presence rule still observes it, like gold.

Candidates are `{"id": <AST/table address>, "role":"available" |
"later_gold", "table": <table>, "earlier": [<tables>]}`. `earlier` defaults
to the operation's context. Normalize a later gold table against **its own
gold context**, not the mutant point's context. Supply every dependency-ready
table available at the point and every later gold table; this operation
reports each comparison and every match, with explicit equality witnesses.
Recovery's `available` uses this same shape with **only** `role:"available"`;
a later-gold relation can never witness a semijoin.

INIT output normalization also needs `component`, `port`, `input_relations`
(the relations its original INIT reads, with `input` named `ex_input`),
and the complete `siblings` list, possibly empty, at this assignment.
Column names identify carried key/registry-copy columns. If names are
absent, the old entity-value containment fallback applies. Use the task's
gold AST inventory to set `used:false` for unused output ports, for both
member and context tables. The operations do not infer a task-wide usage
policy from an individual table's rows.

## Recovery and code labels

The original policy is `judge2/row_recovery.py`, called by
`ce5/mutk-engine-fixes/prequota_gate.py`: one fixed typed equality
conjunction then one fixed projection, shared across every train input.
Projection columns may repeat. Position matches Box, `number` matches
Number, and complete four-margin values are compared atomically. Selection
can be empty; gold-empty witnesses may use contradictory typed constants.
`restrictions=False` requests just this original operation.

With the default `restrictions=True`, recovery additionally enumerates:

- One comparison of mutant columns or a column and a typed constant. Equal
  and unequal work on compatible logical types; ordered comparisons work
  on Number only, as in the engine. Thresholds come from observed complete
  column values; every distinct inequality cut has such a representative.
- One semijoin or antijoin to an available table on a fixed typed key
  mapping, with the source's remaining columns existentially projected.
  Repeated mutant key columns and empty keys are supported. The source and
  every key mapping are fixed across all train inputs.

Either restriction may be followed by the original equality selection and
projection. The returned witness contains the restriction, source AST id,
key/column mapping, constants, selection and projection. Native recovery
rechecks the complete witness against every train input before proving it.
This is finite train-row recovery evidence, not held-out correctness or a
claim that a future legal clause can name every constant.

A proof returns `recoverable:true`, `code_label:"DETOUR"`, and
`judge_eligible:false`. If `final_output=True`, the code label is `WRONG`.
The final-output flag is required; `study_final_output` derives it from
relations the checked gold OUT reads directly. No proof means a null code
label; an unknown result has null judge eligibility. Apply these code
labels before quotas/judge publication, and retain their evidence.

## Equality normalization policy

The port reads the existing active `nf4f -> nf3f -> nf2f -> nff` **spec**
rules. Gold and mutant share: Example-key/program-constant/duplicate
removal; determined constants and finite-domain maps with the task-wide
earlier-shown guard; lookup; Cartesian factoring; earlier-table
restatement; domain/product enumeration; pooled restatement; reverse
finite-domain relabeling; lib constants; input-presence masks; and
registry-carried-column component degeneracy (Enclosure.enclosed exempt).
Computed/complement are off, and many-to-many factors stay, as in spec.
Unused-port inventory remains an explicit gold-context input.

Normal forms contain actual typed factor rows and mask structure, with
removal reasons. Equality proves a factor permutation, typed column
permutations, and one Ident bijection shared by **all** kept factors and
inputs. It does not compare truncated normal-form hashes. Legacy searches
that silently stopped at 64 mappings/720 canonical leaves are exact native
searches subject to the explicit work/deadline bound; a stop is unknown.
Frame names/extents are not added to this policy: the old nf4f keys compare
typed cell values. Recovery reads train only; normalization/equality read
the full supplied train-plus-test universe, like the old gold normalizer.
