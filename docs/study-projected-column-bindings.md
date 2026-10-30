# Projected column bindings

A resolved relation can retain fewer columns than its defining clause lists.
The resolver's `label_position` describes that physical interface. The original
listing position describes the declaration before projection. Substituting the
latter when the former is absent resurrects a dropped label at an unrelated
physical column.

`ResolvedProgram::given` now normalizes `GivenLabel.place` for clauses, CHOOSE
forms and OUT forms from `label_position`, including its absence. Logical slots,
record widths and original typed source paths remain intact. Instance ports,
rigid outputs and demonstrated layouts retain the existing native-position-or-
declared-position rule. Both
flow placement and component key-source consumers consequently see the same
normalized metadata.

`ResolvedProgram::column_bindings` owns physical bindings and header selection.
It retains every applicable local binding and the existing first-occupied
selection, including an unlabelled declared column occupying a position before
another label. The table exporter delegates its `column_placements` to this
helper. Empty-listing header selection still requires native `row_paths`;
additional `read_row_paths` can supply evidence without selecting a header.
There is no second selection rule in the renderer or static export.

## Structured witness

Each `definitions.native_relations` entry adds `column_witness_status` and
`column_witnesses`. Existing relation identity, selector and header fields stay
in place. `column_witness_status: complete` means the native schema was
enumerated, not that every column binding resolved. Each column has its own
status. A witness contains:

- `physical_column`, native `type`, typed `row_path`, and optional canonical
  `native_name`;
- `definition_path`, exact native `relation`, and the original `logical_slot`;
- all `bindings`, each with `scope_path`, `label_id`, `body_path`, typed
  `source_column_path`, native scalar `field_type`, and its placement `proof`;
- `selected_header_binding`, identifying the binding the native producer selects,
  independently of other aliases;
- `status`: `resolved`, `declared_without_local_label`, or `unsupported`.

Proof kinds are `resolver_label_position`, `declared_layout` and
`resolved_row_path`. A declared computed column can have no local label. An
unsupported mapping does not acquire a synthetic label. Type names use the
existing native column-type representation; mapping operates on native types,
column names and label identities before serialization. Scope lookup reuses the
IR compiler's native lookup.

The witness does not format an optional stream's label spelling. The final table
producer still owns `name`, `label` and `source_label`. A canonical relation name
and a form-local label can differ without an error; physical binding identity,
scope, typed path and type determine whether they refer to the same column.

## Observed evidence

The saved deaa878f evidence for task 14754a24, pair beginning `0007c7c2`, has one
physical Box column at `&r16`, with native row path slot 4 (XRel). The original
head also lists Key at slot 0. The old fallback assigns Key to physical position
0 after Key has been projected away, and the placement's first occupant hides
XRel. Its misleading frame provenance then reaches the rows that read XRel.

Task 3979b1a8, pair beginning `0086f9f6`, shows the same class in headers:
`&r26` retains K and V (typed source paths slots 2 and 5) while the old metadata
labels its physical Number and Offset columns P and A. At `&r29`, the retained
Example column is E, while old metadata names D. These are native identity/type
contradictions, not alternate display names.

The fix applies to every projected named head, not to these tasks alone. It
changes provenance and header bindings, not evaluated rows, assignment identity,
collection budgets or native frame laws. Remaining unresolved extents and bounded
collection stops remain explicit. Native confirmation requires a committed
runtime build; historical buffers keep their original metadata.
