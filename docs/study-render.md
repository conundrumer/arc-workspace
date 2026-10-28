# Native structured program evidence

Part 1 bindings (JSON strings):

```python
gold_evidence = json.loads(gold.render_json())       # StudyProgram
mutant_evidence = json.loads(mutant.render_json())   # ValidMutant
```

Schema: `arclog-study-render-v1`. `parts` declares completeness separately:
`nodes=complete`; `definitions_readers`, `types_frames`, `literal_meanings`
are currently `pending`. A consumer must check the part it uses. Unsupported
nodes or a presentation/source mismatch raise `ValueError`; nothing is dropped.

`nodes` contains every node in original AST preorder, including the program
at `[]`, INIT key clauses, input heads, input bodies, nested branches and
individual label arguments. Every node has `path`, `kind`, `data`, `sexp` and
`children` (child paths). Paths are arrays of integer AST child indexes;
they are unrelated to stream-token positions. `sexp` is display text from
the engine writer. Bodies have a display list wrapper. Source names are
preserved; decoded names use the engine's synthesized spelling. Presentation
wrappers for named record fields never create fictitious source paths.

`data` contains the original AST values: atom relation references and sites,
comparison operator/operands, declaration names/columns, INIT component and
input port names, and label uses (`fresh`, `join`, `key`, `reserved_zero`)
with their original label IDs. Written names and anonymous slots remain
distinguished in structured name objects. Label IDs have lexical scope; use
the AST owner path as well. `program_sexp` is the full engine-written program.

For gold, `source_path_correspondence` declares identity. A `ValidMutant`
adds `mutation_identity` and an explicit array `source_path_correspondence`:
each original node has `before_path`, `after_path` and `status` (`preserved`,
`deleted`, `replaced`, `replaced_subtree`). A replacement descendant has no
guessed identity: its `after_path` is null. The edited atom itself maps to
its actual new path. Deleted descendants also map to null. All new nodes
are independently addressable in the mutant's own `nodes` array.

`mutant.as_program().render_json()` exports the mutant AST but does not retain
its edit provenance; use `ValidMutant.render_json()` when correspondence is
needed. Build identity is the existing `arclog.streams_digest()` binding;
there is no fingerprint over rewritten program fields.

Renderer meanings of reserved zero are in
[`study-reserved-zero.md`](study-reserved-zero.md).

## Stored identities and packed assignment rows

```python
# Reconstruct from the ORIGINAL gold handle, with no redraw or evaluation.
mutant = gold.construct_identity(json.dumps(stored_identity))
evidence = json.loads(mutant.render_json())

# Each schema type is the engine's native column_types spelling.
cell = json.loads(arclog.StudyProgram.decode_term_json("Position", 131074))
rows = json.loads(arclog.StudyProgram.decode_rows_json(column_types, packed_rows))
```

Identity reconstruction checks the point belongs to gold, paths are unique
original leaf paths, replacements are legal original-site alternatives,
metadata is canonical and exact, and the edited whole program resolves,
types, checks and writes its stream. It enumerates no complete mutation domain
and uses no RNG. Invalid historical records raise `ValueError`; they are not
repaired. The caller binds source task/case/revision to its stored gold record:
a bare program parsed from sexp does not itself carry those external fields.

Packed-term decoding calls native `Term::decode` with the supplied static type.
It accepts signed int32 or unsigned u32 encodings, validates finite constants,
and rejects unsupported types or wrong row widths. Box/Position/Offset cells
return native unpacked margins; their reference-frame coordinates/extent must
come from the native table's frame records. It cannot infer a frame size from
one packed value. Number, Color, Example, Unit and orientations return typed
values, with orientation names from the engine registry. Ident is explicitly
an opaque identity in its task session; no interned content is invented.
Pose values decode as native D4 orientations, retaining the supplied nominal
type text. Flatten record types to scalar columns first.

## Native body columns and stored decode source AST

`body_views` is complete for every mutation point. Each entry has `body_path`,
`owner_path`, `kind`, native evaluation `scope`, `input_port`, and ordered
`columns`. A column has `body_column`, native name `cN`, **original `label_id`**,
engine-native `label_spelling`, and inferred `type`. This is exactly the ordered
`BodyView.clause.columns` / `BodyView.paths.labels` used by body_tables.rs,
not the export's ordinal `column_slots`. Compare identities within the same
lexical owner; spellings are display metadata.

For an INIT input, `input_port_projection` maps each resolved scalar port
column to its original head-site path, label ID and body column. Project the
native body witness rows with this map to obtain the input-port rows; these
rows are not the component's output. `unprojected_body_label_ids` identifies
body witnesses omitted by that projection. Native `point=1` identifies body
tables; use evaluate_pair's explicit `table_indices` to distinguish all/kept
and gold/mutant, since their structural selectors intentionally coincide.

Prefer `gold.render_pair_json(identity_json)` when loading stored decode sexp.
It returns `{schema: arclog-study-render-pair-v1, gold, mutant}`. A sexp reader
turns anonymous decode slots into written names and can materialize named
record-field wrappers. If direct identity validation fails, the constructor
recovers the source decode AST via the engine's own stream writer and
complete-stream grammar/binder, then validates the exact stored identity on
that AST. It never guesses a slot from a name. `render_pair_json` supplies the
**actual rehydrated gold AST** whose original paths and label IDs the mutant's
correspondence references. Loading the display gold sexp and independently
using that parse's descendant paths is not a correspondence contract.

## Definitions and readers

`parts.definitions_readers=complete`. `definitions.graph_nodes` exports the
resolver's actual nodes, definition kinds, source forms, scope/side and read
edges. `definitions.readers` exports each original atom's path/reference and
resolved graph node or library ID, plus explicit component/proposer uses.
Instance input-port identities remain scoped ports, never library predicates
because their spelling happens to match one.

`definitions.native_relations` maps each engine stream relation slot to its
structured original relation, exact native `source_name`, defining AST path,
and native selector `(form, point=0, relation)`. Use `source_name` to join packed
kept-assignment relation names to schemas; use the actual rehydrated source
from render_pair_json for stored decode records. Some INIT port aliases have
no physical table; a selector identifies a table if it is present, not a
promise that the exporter materialized one. Body tables use the separate
body_views selector and pair-report table_indices.

`definitions.registry.entries` includes the **entire** embedded registry and
arclog proposer bodies, so every library reference's definition closure is
available without Python parsing. Entries have an explicit kind/implementation,
structured declaration S-expressions (`symbol`/`string`/`list`), engine source
text, native AST read references for macros/arclog proposers, and component
input/output port metadata. Native implementations expose their exact registry
contract and implementation kind, not an invented arclog body. Component
input defaults, copies, frame/type rules are present in the structured native
registry declaration. Facts have explicit definitions too.

## Reuse and cache bounds

The immutable embedded registry export is parsed once per engine process into
`OnceLock<Arc<JSON>>`. Each checked StudyProgram shares its immutable render
result across handle clones, so gold BodyViews and definitions are not rebuilt
per identity. Stored-sexpression handles cache their native decoded-source
handle for one exact Registry/settings pair. `gold.decode_source()` exposes
that reusable handle; render2 should retain it once per task/case and call its
construct_identity/render_pair_json methods. render_pair_json validates and
uses that same cached source, including its already computed gold export.
Custom registries/settings fall back to uncached computation rather than
reusing a mismatched cache. Per-program caches live as long as caller-owned
handles, not in an unbounded global program map. JSON results remain complete
values; render2 may store identical immutable definitions once in artifacts.

## Authoritative implementation meanings

Signatures are not marked as meanings. Each registry entry now has `semantics`,
looked up by its exact resolved ID (`lib:Walk`, `lib:apply`, `fact:input`, …).
The frozen authored source is `docs/study-library-meanings.source.md`; the
explicit ID catalogue is `engine/lib/study-meanings.json`. Each entry carries
its authored summary/full contract, source lines and section. All 140 current
registry declarations have authored coverage. A future unmapped ID is
`status=pending`; `definitions.semantic_coverage` and `parts.native_semantics`
report this separately from structural reader completeness. There is no runtime
name/port regex or guessed semantics.

Walk additionally exports structured start-domain, zero-step, bound, branching
and dead-end rules checked against its native implementation. apply exports its
margin transformation rule and all eight margin-index permutations **computed
by the native Geometry/D4 action**, with the authored meaning. Its all-zero
margin input remains all-zero under every D4 element. The registry cache retains
these contracts alongside signatures, avoiding repeated parsing/geometry work.

`definitions.native_relations[].display_name` is the engine writer's spelling
(`&rN`/output port for a decode), while `source_name` remains the exact native
kept-assignment join key (`slot N`, etc.). These fields have different purposes;
the renderer must not parse a definition header to recover either one.

## Resolved arguments, comparisons and typed reserved zero

`parts.argument_types=complete` and `parts.literal_meanings=complete`.

## Exact-kept continuation and DET admissibility

`arclog.study_continuation(evaluator, gold, mutant, expected_kept_json=None)`
returns `(report_json, gold_CaseTables, mutant_CaseTables)`. First call
`evaluator.evaluate_pair(gold, point, mutant)` on these exact handles. This
operation reads that evaluator's cached gold observation; it never walks FITS
or selects replacement assignments. Keep the evaluator alive for the case.
Tables include every materialized written relation, in written order, including
INIT component output ports. Native schemas, frames, example/model/assignment
axes and packed storage are the ordinary `CaseTables` export. Evidence tables
are prepended as usual. Relation table selectors use the same form/slot map as
`definitions.native_relations`. Assignment indices follow report
`kept_assignments`, even when a relation reads only a subset of those DETs.

For each held DET the report removes only that DET's held value, evaluates its
native domain with the other kept values fixed, and compares exact row sets.
For a proposer DET with ONE, the held singleton must occur in a domain value.
Undefined domains, changed schemas, faults and bounds remain explicit. OUT is
reported separately at the held full assignment: native parameter evaluation
overrides the proposal body with the held value, **including when that value is
inadmissible**. Such conditional OUT evidence does not claim that execution
selected a row from the displayed candidate body. No alternate FITS is used.
One shared deadline and table-work counter bound this additional operation.

For historical corpus-v5/v8 records pass the stored full `kept_assignments` as
`expected_kept_json`. A mismatch is an error, including a different interned
Ident namespace; packed identifiers from another task session must never be
silently injected. Reuse original source streams and the task evaluator's
ingestion/evaluation sequence when recreating the observation. The API cannot
retroactively claim an unrecorded historical observation. Existing recorded OUT
reports remain historical producer evidence and should be described as such.
On v8, CHANGE, definition closure, authored meanings, typed Term decoding,
native frame sources, and input-port projection already work; continuation is
an additional binding requiring the new build.
`typed_sites.arguments` gives every scalar site argument's original `path`,
`site_path`, `scope_path`, label ID (null for zero), native `resolved_type`,
source `column_type` where applicable, native checker `frame` evidence, and
`literal` for reserved zero. The type comes from the same Inference/site-type
and same-frame rule machinery as the checker, including INIT type-parameter
bindings; Python does not infer it from names. `typed_sites.comparisons` gives
both operand types/frames and typed zero meanings, keyed by the comparison's
original node path.

A frame's `established` grids identify input/output and current example or
example label. `not_established_by_native_grid_analysis` is an explicit lack
of proof, not “no frame.” `contextual_reserved_zero` describes the constant's
relation reference frame; no independent label frame is invented. Offset and
non-frame types report `not_applicable`. `parts.types_frames` remains pending
until the separate native made-frame/table provenance part is supplied. This
bounded checker analysis deliberately does not replace native table extents.

## Native made-frame and column provenance part

```python
frames = json.loads(arclog.study_frame_sources_json(program))
```

This separate table-code API accepts the same checked StudyProgram and evaluates
no task. Its schema is `arclog-study-frame-sources-v1`, `complete=true` for the
native static provenance walk. `relations` has exact native relation selectors,
ordered types/names/original label IDs, and each column's actual native sources.
Known omitted native port tables are explicitly marked, with the input-port
projection as their contract; they are not empty computed outputs.

`bodies` maps each original body path/owner to all native lexical variables,
their original label IDs/types, result-body column if present, and native sources.
It includes branch locals without changing the query's evaluated output schema.
Sources carry kind/code, exact native source relation name, source row/column,
original atom path, occurrence and frame expressions. A frame is a read of that
source column's frame, a `made` frame with explicit maker registry ID/column/
original path/outer frame, or explicit `native_unknown`. Every source variant
is handled; unsupported metadata raises ValueError. Non-frame types are
identified by `frame_applicable=false`. Empty source frames on a constant
claim no independently named frame, not a grid chosen by the renderer.

Resolve run-specific frame IDs/extents using the already supplied native tables;
this API does not invent input sizes or reevaluate rows. Cache this immutable
frame part once per retained program handle in render2's bounded task worker.
Together with typed_sites' native static grid evidence this completes the
available native frame/provenance export; the core-only `types_frames=pending`
flag deliberately does not claim the separate table part has been supplied.

INIT projection implementation uses the evaluator's `InstanceShape.head_labels`
and `port_types`, including parameter record field order and inserted Unit
columns. It does not look up resolver column_position on input heads, which
need not have those entries. Each projection item has native port-column
ordinal/type, original label/body column or an explicit inserted Unit constant,
and `head_occurrence_paths` (all exact head occurrences, with a single
`site_path` only when unique). `group_key_label_ids` names the grouping key
separately: construction input rows exclude that key and are evaluated per key.
