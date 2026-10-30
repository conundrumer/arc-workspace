# Held DET choices and conditional OUT

These APIs require a wheel containing the OUT/DET commits. They evaluate no
replacement FITS assignments. Retain the actual rehydrated gold handle for
stored decode records (`decode_source()` / `render_pair_json` correspondence).

```python
choices = json.loads(gold.choice_evidence_json(json.dumps(record['evaluation']['kept_assignments'])))
out_binding = json.loads(mutant.as_program().out_bindings_json())
```

`arclog-study-choices-v1` exports native DET definitions/types/column paths in
dependency order, full held assignments decoded with `Term::decode`, and every
compiled body's exact read subset. `assignment` indexes the supplied full
`kept_assignments`, starting at zero. Subsets retain that full choice index even
when several choices have identical body reads. Each DET carries `source_name`,
static `types`, original `packed_rows` and typed `rows`. `bodies.source_names`
is the same compiled IR traversal the native body-table exporter uses, including
key reads and nested branches. Picks enumerated as models are not held DETs.
Missing/duplicate DETs, unknown relations, wrong row widths or invalid constants
raise ValueError. No interning, evaluation, name parsing or foreign-session
assignment injection occurs. Ident remains opaque in the original task session;
Box/Position margins still require the stored native frame/extents.

`arclog-study-out-bindings-v1` identifies the checked OUT graph node, exact form
and body paths, and the native key projection onto Position/Color columns.
Each projected column has its original label ID, compiled body column and all
original AST label occurrences. Join these exact paths to the structured
reader/site exports for the relation/column feeding OUT; names are display only.
OUT projection deduplicates rows. It is separate from INIT input projections
and from component output collection. New zero-width record schemas must still
agree with native flattened column counts; no Unit column may be guessed by a
consumer.

For live continuation, first call `evaluate_pair` on the same evaluator and
handles. Then:

```python
report, gold_tables, mutant_tables = arclog.study_continuation(
    evaluator, gold, mutant,
    json.dumps(record['evaluation']['kept_assignments']))
report = json.loads(report)
```

The existing `arclog-study-continuation-v1` adds `out_bindings` and detailed
`choices[].out.train[].models[]`: native `packed_rows`, typed `rows`,
`value_kind`, `grid_defined`, actual color `grid` when native `read_grid`
succeeds, equality and differing-cell counts. Each train example also carries
its expected grid. Undefined OUT is explicit and is distinct from an empty row
set; faults/stops remain explicit. Array order is the native model order within
the full held assignment. Models are not paired with gold models by index.

OUT is conditional on held gold values, even when the mutant's DET domain no
longer admits them. The existing `admissibility` report describes that
separately. A changed proposal body does not mean execution selected the held
value from that body. The supplied historical kept assignment must match the
cached observation exactly, including Ident encodings; a mismatch fails rather
than silently using a different FITS choice. Existing saved OUT comparison
reports remain producer evidence and have no invented raw rows or grids.

All additional OUT row materialization is charged to the continuation's native
shared deadline/work budget. Component tables keep their independent API and
explicit table-entry assignment maps; this export does not alter them.
