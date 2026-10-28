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
