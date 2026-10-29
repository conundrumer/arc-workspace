# Source relation names for decoded case streams

Token decoding continues to declare relations by slot. Reader names are a
separate, versioned sidecar, captured from `WrittenStream.relations` in the
original case-file writer. No printed-program or source-text matching is used.
The source pipeline is `stream::corpus::solver_streams` with `WantedCases::Named`,
including `cases/<task>/` overrides and the same zero-column lowering used by
`model/export.py`.

Obtain a map once per task/case from the gold handle made by `from_stream`:

```python
names_json = gold.relation_source_names_json(source_corpus, task, case)
names = json.loads(names_json)
```

The function requires exact equality of all source-written token IDs and emitter
model flags with that gold stream. A changed source, wrong case, incompatible
vocabulary, or different stream fails explicitly. Old v4/v5 records can obtain
the map with the same function after reconstructing their decoded gold handle.
If the original source no longer produces that stream, retain the record without
a source-name map; never attribute a near match.

Corpus producers should store the returned object in every pair record as
`relation_source_names`, cached once per task/case. It has schema
`arclog-study-relation-names-v1`, task/case/corpus provenance, `stream_identity`
(`ids` and `model`), and `relations` in original writer slot order. Each row has
`relation_slot`, typed `native_relation`, typed `source_relation`, and native
writer `display_name`, including its leading `&` and any output port/part.
Names of unwritten reserved INIT inputs are retained too.

The combined structured exports accept the JSON sidecar:

```python
gold_export = json.loads(arclog.study_program_export_json(gold, names_json))
mutant_export = json.loads(arclog.study_mutant_export_json(mutant, names_json))
```

They export `relation_source_names` and annotate
`definitions.native_relations[].display_name` and `source_relation`. A mutant
validates against its **original gold** stream, and matches native declaration
identity rather than its own potentially reordered writer-slot ordinal. The
original source-name join keys, relation slots, node data and `sexp` stay exact
native evidence. Consumers use the typed map for reader captions/references;
there is no replacement of strings inside an s-expression, and token streams,
decode, evaluation and mutation identity are unchanged.
