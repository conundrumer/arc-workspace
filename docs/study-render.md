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
