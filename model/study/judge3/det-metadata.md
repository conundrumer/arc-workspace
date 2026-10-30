# Receipt-bound DET metadata

The additive `det_metadata.MetadataProducer` subclasses the shared `nonrender_metadata.MetadataProducer`. It consumes mech3's public `det_receipt.receipt(record, exports, raw_bindings)` result; it does not implement a second reader mapper. Existing producer, renderer, headers/body and tool files are unchanged. No documents, rows or evaluations are acquired.

```python
from det_metadata import MetadataProducer
from det_receipt import receipt  # model/study/ast/run/mech3/det_receipt.py

producer = MetadataProducer(engine=engine, read_native=existing_native_reader,
                            corpus=corpus, settings=settings,
                            case_inventory=existing_case_inventory)
transport = receipt(record, exports, raw_bindings)
adapter = producer.produce(record, native_base=native_base,
                           det_projection=transport)
```

Exact signature: `produce(source_record, *, native_base=None, det_projection=None)`. RULE/INIT without a receipt delegate unchanged to the base producer. DET without a receipt retains the explicit UnsupportedProjection refusal. `exports` are the canonical program exports and `raw_bindings` are the original scoped BODY provenance from the shared raw binder. **Keep raw_bindings unchanged for mech3's per-reader calls.** The target's selected union is not the raw BODY interface.

The accepted input is `mech3-det-header-projection-v1` from the public receipt function, including `mapper`, `source_sha256`, `body_path`, complete per-reader evidence and both sides' program/export hashes, raw bindings, selected native header columns and scoped BODY bindings. Mapper hashes cover raw source bytes; record/program/export hashes use mech.run.digest canonical JSON (a program is hashed as a JSON string). Receipt source files must still match their hashes.

The DET table projection is the union of **actually reader-named public header fields**. Repeated reads of one header field are deduplicated; distinct header paths survive even when they use the same BODY column. Public names and row paths come from native column_witnesses. Gold/X use their own scoped LabelIds and physical BODY columns; no cross-side LabelId matching or reader-local aliases. The formatter/callable builder and project_entries are the existing canonical implementations.

A reader-named Unit may use `None` only with the native declared-without-local-label Unit witness and mech3-native-unit-projection-v1 certificate naming the canonical projector. It creates no label. An empty union requires the complete no-reader proof and no native resolved reader of that header. Missing/incomplete receipts raise InvalidDetProjection, never fall back to all BODY columns.

The result retains the base `judge3-source-metadata-v1` adapter shape. `bindings.gold/mutant` and `input.binding`/`comparison_target.binding` now describe the selected DET header union, with public callable templates and source_body_column indices (which may repeat or be certified None). `comparison_target.full_replay_body.projection_indices` reflects that union. Full input transport remains `adapter.det_projection_receipt`; separate per-reader evidence remains `adapter.reader_projection`.

Each side binding has this exact receipt schema:

```text
judge3-det-binding-receipt-v1
  source_sha256, side, program_sha256, export_sha256
  body_path, owner_path, native_ref_sha256, native_selector
  source_body_schema_sha256, projected_schema_sha256, callable_template_sha256
  transport_sha256, projection_indices, mapper, policy
```

`producer.project_entries(binding, entries)` applies the shared projector to supplied entries after checking the binding receipt; it acquires nothing. The inherited callable_definition and graph/selector APIs remain unchanged. No grade, replay-completeness or admission proof is inferred here. DET table/recovery grading belongs to the mechanical owner; these per-reader observations remain separate evidence.

This module wraps the canonical produce body by trusted AST extraction, replacing only its exact explicit DET-refusal guard with receipt validation. It fails if that guard changes. All formatting, graph selection, native schema binding and row projection remain the canonical implementations. Source receipts include this wrapper as well as the base policies and mapper.
