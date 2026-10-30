# Keyed extent evidence and table work

Extent annotation must preserve the native projected `KeyRead` relation.
Replacing it with the key body's positive witnesses changes a keyed input
query from a join on distinct keys to a join on every witness of each key.
This adds a witness product even when the input's values are already complete.
The condition applies to every keyed component input and checked body, including
BoundingBox and Agreement, independently of task identity.

For example, the saved `4e7e0eb9` `$Any $Blank` native relation at form 7 holds
1,845 rows with 25 distinct `(Example, C)` keys. Joining those rows to the raw
key witnesses produces 142,965 combinations. The projected-key join has 1,845.
These counts come from stored native values; they are not a claim that a new
runtime or the full fault replay has passed.

`BodyView::widened` remains the only widening implementation. It exposes the
current body's positive witnesses and union alternatives while retaining native
key nodes. `BodyView::key_views` exposes their existing compiled clauses and
original paths, without compiling another key language. `key_evidence` queries
those witnesses separately, merges their frame proofs by the complete projected
key and original scoped label, and supplies hidden-key source and maker evidence
to the input's analysis. It never joins independent model ordinals. As with the
original widened derivation, all models contributing the same row must agree on
its extent. Different examples and incompatible DET assignments cannot share a
proof. Assignment matching calls native `session::same_rows`, checking actual
arity and rows rather than treating a row hash as equality. Study assignment
alignment, closed-DET admissibility and full-held-choice annotation matching
use the same exact predicate; canonical
relation naming, open-DET singleton membership and work precharges remain at
their respective callers. Faults, undefined values and native stops remain explicit evidence.

The second bypass was recursive input-port derivation: public relation and body
tables applied intrinsic/direct/no-grid evidence planning, while ports always
requested widened derivation. One `EvidencePlan` now serves all three entry
points. Relation and body metadata adapters retain the original checked column
order and provenance, and share DET-schema validation and projection policy.
Metadata-only callers perform neither projection evaluation nor annotation.
Ports complete intrinsic Position and proved grid-frame slots from their native
rows, and request derivation only for the remaining wanted Box slots.

All geometric slots remain in their original native order, including unresolved
slots. Missing size rules, opaque frames and missing evidence remain unresolved;
they do not prove `no_grid`. Actual evaluator bounds remain bounds. The work cap
is unchanged. Direct completion is a formatting walk over already charged rows;
independent key witness evaluation and proof indexing are charged normally,
using the parent Reads work count and source cache. A nested proof never
creates a new work cap.

`frame_context::node_at_path` owns recursive source-path lookup for both relation
and algebra nodes; `read_at` is its relation-only adapter. `ReadCoordinates` owns
the checked forward and inverse mapping between native IR argument positions and
source columns (Input, explicit lifted Example and ordinary reads). Provenance,
source constraints and key evidence use that single coordinate rule. Exported
row-path-to-table-column mapping retains its separate contract.

Runtime confirmation must use an immutable build and the saved regression
identities, including `4e7e0eb9` and the keyed Agreement form 6 of `3e980e27`.
Neither CURRENT nor an active corpus is changed by this implementation.
