# Source-record metadata API

`nonrender_metadata.MetadataProducer(...).produce(record)` accepts any original corpus pair record with source programs, native point references, point path and evaluation table indices. It generates no document and writes no files. It performs native AST export and reads stored schemas/catalogue references only: no table entries/rows, replay, judge call or admission inference.

```python
from nonrender_metadata import MetadataProducer, UnsupportedProjection

# Reuse the caller's existing engine and stored-native reader namespace.
producer = MetadataProducer(
    engine=ev.arclog,
    read_native=lambda reference, base: store.snapshot(reference, base)['_native_reader'],
    corpus=corpus_path,
    settings=ev.settings,
)
metadata = producer.produce(record, native_base=corpus_path / record['task'])
```

`store` is the existing shared TargetStore. Construct/reuse it in the caller; the producer neither imports that evaluator nor starts one. Records with `gold_sexp`/`mutant_sexp` are accepted alongside `programs.gold`/`programs.mutant`.

The returned `judge3-source-metadata-v1` packet is an adapter:

- `input.binding` is canonical stored X binding; `comparison_target.binding` is canonical gold point binding. `bindings.gold/mutant` expose `source_body_schema`, `projected_schema`/`fields`, `callable_template`, exact owner/body path, native ref/index/selector and INIT key/port metadata. Both callable templates use &X for reuse as an observer interface. Gold is not an available clause read.
- `source.native_base` supports `TargetStore.mutant_input(record, metadata, ...)`. No native X rows are read by this producer; the caller acquires them through the shared store.
- `same_case.body_view`/`gold_export` and `producer.same_case_after(tables, index, metadata)` reuse the existing selector for same-case points/tables. `definition_after` handles declared aliases with the same canonical policy.
- `availability` comes from the existing renderer dependency_scope/definition_node, including independent definitions and exact native resolver graph. Ambiguity is retained in `gaps`, never resolved by names/indices.
- `all_case_targets` lists every exported case and its own full-gold reference, source program/record locator, kept assignments, assignment map and native base. Missing references remain null. There is no cross-case assignment zip. Optional `case_inventory=` accepts the existing catalogue structure (or callable task -> structure); otherwise the producer reads corpus manifest/cases.npz/retained.jsonl and the existing missing-reference inventory. NumPy is needed only to read cases.npz; it is not imported at module import.
- `policies` binds exact source paths/hashes used. Layout, graph, callable and INIT projection functions are loaded directly from canonical trusted source via AST extraction; no pinned native renderer imports or copied layout/graph policy. `projected_entries=[]` is tagged `entries_status=not_acquired`, never an empty-table claim.

DET requires compared columns named by native resolved readers. The current canonical renderer only offers raw BODY columns there. `produce` therefore raises **UnsupportedProjection** (a ValueError) for DET, explicitly naming the missing reader-named projection; it does not invent a mapper or silently treat all BODY columns as the comparison target. Unsupported/ambiguous INIT layouts also fail closed through the shared binder/projector. Record those gaps as unknown in the collector.

The producer returns metadata only, not admission, row equality, complete replay or coverage proof. Step3 should acquire gold once per case using the shared evaluator, reuse stored X and apply the shared comparator. No existing judgetool or shared headers/body source was changed for this API.

## Callable available definitions

`producer.callable_definition(definition, native_schema)` returns a dictionary with `schema`, `callable_atom` and `source_name`. Supply `definition` from an entry of `metadata["availability"]["definitions"]` and the stored/fresh native reader’s `schema(table)` list. The schema has the canonical physical ordering, source display names, types, frames and row-path bindings; the atom preserves native INIT port/nested-key sites. Both functions are the same extracted Document.schema/callable_atom used by the renderer. No engine or row access occurs. Missing authenticated display names or incompatible native witnesses raise ValueError. This helper formats an already-admitted definition; it neither selects a graph node nor grants new reads.

```python
bound = producer.callable_definition(offered["definition"], native_reader.schema(table))
source_atom = bound["callable_atom"]
source_schema = bound["schema"]
```

The tracked module is `model/study/judge3/nonrender_metadata.py`. Source policies resolve in this checkout; stored catalogues and references use `study_paths.DATA_ROOT`. Carrying the code does not regenerate or change frozen document receipts.

## Fresh case table metadata

`producer.case_table_metadata(export, item)` accepts a shared evaluator's fresh
case export and original-table metadata (`selector`, `source_name`,
`native_schema`). It returns the canonical physical schema, authenticated source
name, callable atom where applicable, matching definitions, and BODY identity
when applicable. It reuses the same source binder and callable formatter. It
does not read rows, replay, relax native column witnesses, select later targets,
or grant availability. The caller must use the canonical resolver/ordering
policy for those decisions.

An INIT input's outer group key can be absent from stored BODY outputs. The
provider explicitly raises `UnsupportedProjection` with the missing LabelIds
and body path in that case. It does not omit those fields or represent an
absent key as inserted Unit. Full support requires the evaluator to acquire
the key and input in their original correlated INIT context.

## Two-sided RAW DET input

`producer.raw_side_bindings(record, native_base=...)` returns
`judge3-raw-side-bindings-v1`: the original source digest, exact `exports` and
`bindings` keyed gold/mutant, native base and source-policy identities. Each
binding carries kind/body/owner/scope, native reference/index/selector, complete
`source_body_schema`, and identity `projected_schema` with physical indices,
source body columns, scoped native LabelIds, types and frames. It calls the
canonical `Document.schema(..., body=True)` and its `bind_body_schema`; it
never calls an entry decoder, reads rows, inserts fields or selects a header.
Non-Unit scalars require the exact exported lexical scope. Existing physical
Unit columns retain their physical index; this supplier inserts no virtual Unit.

Pass the returned exports and RAW bindings to
`mech3.det_receipt.receipt(record, exports, bindings)`. That consumer owns the
unchanged-reader/site audit, complete header witnesses and per-reader transport.
Then pass its certified transport to the DET metadata producer and evaluator's
dedicated acquisition wrapper. RAW BODY metadata is not itself the public DET
column selection and must not be exported as a fallback. The existing ordinary
`produce` method and the judge's DET exclusion are unchanged. Missing/ambiguous
selectors, lexical bindings or incomplete native reader metadata fail before
entry acquisition. Implicit input-axis fields and recursive context bindings
are not invented here; acquisition remains unavailable without native proof.
