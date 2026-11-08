# Static pruning arguments

A conclusion concerns one checked atom in its lexical scope. Inputs are the labels that exist before that atom and the types of the columns that bind them. A later use, including the candidate membership test itself, supplies no premise. The exporter therefore uses registry-fixed scalar types, or column types of declarations whose defining forms all precede the current form. It does not use a current instance's inferred type parameters or conditional type rules as binding premises. Unknown bindings reduce coverage. A fresh output is not an existing input. Rules under OR, IF or ALL concern that local branch, not the whole enclosing clause; branch joins and test-to-then binding propagation are not inferred by this classifier.

These arguments concern complete relation semantics. A stopped evaluation supplies no counterexample or proof. Bounded packing supplies no premise about a relation's rows.

## Comparisons and negation

Equality compares a term with itself equally; integer ordering compares a number with itself neither less nor greater. Therefore `X != X`, `X < X` and `X > X` are unsatisfiable, while `X = X`, `X <= X` and `X >= X` are valid when X is already bound. A fresh equality operand binds a label and is excluded from the valid-test rule. An established Nat is at least zero, so `N < 0` is unsatisfiable and `N >= 0` is valid. This conclusion requires Operand::Zero, the reserved literal: a second label, even another Nat label, supplies no zero premise. No value is guessed from its name or encoding. Complementing a checked predicate reverses only unsatisfiable and valid; it gives no alias or constant conclusion. Nested negated forms are outside the classifier.

The canonical clause form already reverses `>` into `<` and `>=` into `<=`, exchanges bound equality and inequality operands, renames labels, and orders unordered conjuncts. Pruning must consume those comparison semantics rather than create a second converse-normalization algorithm. Canonical ordering does not prove algebraic relation identities or remove a repeated functional read.

## Box predicates

`interior(A,B)` requires every margin of A to exceed the corresponding margin of B. It cannot hold with A and B the same label. `inside(A,B)` replaces those strict comparisons with non-strict comparisons and therefore always holds on identical boxes.

`nearer(D,P,Q)` compares the same directional margin sum strictly. Equal P and Q give equal sums, so it is unsatisfiable. `gap(D,P,Q,K)` subtracts P from Q and requires at least one forward step. Equal P and Q produce zero steps, so no row survives.

`neighbor(P,D,Q)` composes P with a unit directional translation. At least one margin changes by one; a repeated P/Q label cannot agree with the computed output. Box packing does not wrap or clamp a margin back to its old value: an out-of-range newly packed box stops instead.

`same_dist`, `same_line`, `same_corner` and `same_slab` compare selected margins or directional sums for equality. Repeating their two box labels makes every tested equality true. Every explicitly supplied orientation must already be bound and its whole binding type must be admitted: Dir for same_dist/same_slab, DiagDir for same_corner, Axis4 for same_line. A Dir8 bound at same_dist.D has a nonempty meet with Dir but can also hold diagonal values that the native each(domain) rejects, so that atom is not valid. Omitted orientation columns are projected over a nonempty domain; a fresh orientation site introduces a label and is not a redundant test.

`divide(T,Side,Gap,Part,Remainder)` first requires T >= 0 and Side + Gap > 0, then Remainder = T mod (Side + Gap) < Side. A zero Side cannot satisfy this: either the period is nonpositive or the nonnegative remainder is at least Side. Every emitted T, Side, Part and Remainder is nonnegative; Gap can be negative.

## Orientation predicates

`opposite` maps each cardinal edge to its distinct opposing edge. `diag_opposite` and `dir8_opposite` contain only the explicitly opposing, unequal directions. `perp` and `diag_perp` contain only distinct axes. `perp_dir` explicitly excludes both the same and opposite edge. `turn` applies one clockwise or counterclockwise quarter-turn to a cardinal edge, which never fixes that edge. Repeating either relation's two direction/axis sites is therefore unsatisfiable. The Sense site of `turn` is not part of this repeated-site condition.

The membership relations enumerate their registry-declared domains exactly. The native type lattice establishes inclusion and disjointness, not equality of untagged integer encodings. A bound subtype is valid and a disjoint bound type is unsatisfiable; a wider binding narrowed by the candidate is neither case. `C4` is included in `D4`; `Dir` and `DiagDir` are included in `Dir8`; `Axis` and `DiagAxis` are included in `Axis4`. Geometry explicitly enumerates a Pose as D4; this is the one nominal-type exception used for membership. All ten registry *_elem relations are covered. A type-incompatible complete program can be refused by the ordinary checker before the checked-program exporter is available; this export does not certify unchecked programs.

Term IDs have no runtime type tag. Their numerical encodings are never a substitute for the checker's admitted type domains, and an ill-typed raw algebra call is not a checked counterexample.

## Aliases and constants

`compose(A,0,C)` and `compose(0,A,C)` compute A's margins unchanged. If C is fresh, C aliases the existing A. `relative(0,X,R)` subtracts zero from each margin of X, so a fresh R aliases X. `jump(P,D,0,Q)` composes P with the all-zero translation and a fresh Q aliases P. D must be an existing, admitted direction; otherwise the atom additionally enumerates a direction. When the other input of an identity is literal zero, its output is Constant rather than Alias: zero is not an existing variable.

`relative(X,X,R)` subtracts identical margins and binds a fresh R to the zero box. `edge_inset`, `uniform_inset` and `corner_inset` write either K or zero at each margin, so K = 0 binds the zero box. The corresponding outsets negate those margins and have the same zero result. `axis_inset` and `axis_outset` write K1 and K2 at opposite edges, so both counts zero bind the zero box. `jump_offset(D,0,V)` writes zero or minus zero at each edge and binds the zero offset. Every explicit non-output site must already be bound. In addition, edge/axis insets admit a whole Dir binding, corner insets a whole DiagDir binding at their Diag site, and jump/jump_offset a whole Dir8 binding. A wider joined type can filter rows even when every emitted output is zero; it does not justify redundancy.

Alias and constant describe the output value, not permission to move its scope or discard its native frame/type contract. A key-marked value remains an alias conclusion but supplies no local equality replacement: ConstraintLabel cannot represent that mark.

## Numeric columns

Int retains the existing signed 32-bit numeric encoding and order. Nat restricts it to nonnegative integers; its inclusion in Int changes neither encoding nor arithmetic. `encode_count` converts an unsigned size after checking that it fits an i32, so its outputs are Nat.

| Columns | Argument from the producer |
| --- | --- |
| `divide.T`, `divide.Side`, `divide.Part`, `divide.Remainder` | Accepted rows satisfy the nonnegative-coordinate, positive-period and remainder-before-Side tests. |
| `divide.Gap` | A positive Side permits a negative Gap while the period stays positive. Keep Int. |
| `gap.K` | It emits steps minus one only after requiring steps >= 1. |
| `sub_extent.K`, `frame_offset.K` | They enumerate the half-open range from one to the frame extent. |
| `margin.K`, `dist_pair.K/K2`, `diag_dist.K1/K2`, `corner_dist.K` | They read signed margins or their sums; offsets and boxes reaching beyond a frame can make these negative. Keep Int. |
| inset/outset counts and `jump.K`, `jump_offset.K` | The implementation accepts signed counts and can reverse or expand a displacement. Keep Int. |
| `Cardinality.size.N` | `encode_count(member.len())`. |
| `Excess.excess.N` | `encode_count(plus.len() - minus.len())`, only after plus is larger. |
| `Order.rank.R`, `Order.dual_rank.R` | Encoded cardinalities of predecessor/successor sets or ranking buckets. Input scores remain Int. |
| `Walk.walk.N` | Enumerates from zero through a nonnegative maximum. Input `steps.N` remains Int because negative input counts are accepted and clamped for traversal. |
| `Ray.ray.K`, `Ray.end.K` | An unsigned counter starts at zero and increases by one per step. |
| `CellDistance.distance.K` | Every initial cost is zero and every edge adds one. |
| `Distance.distance.K` | The generic component also accepts signed `weight.W` and `source_distance.K`; a negative initial cost is emitted for an isolated source. Keep Int. |
| `Periods.period.K`, `fundamental_period.K`, `approximate_period.K` | Translation candidates come from `sub_extent`, then the implementation only filters them or selects a least candidate. |
| `ExtentDivisions.division.N/K` | It enumerates N from two upwards, and `side_of` only accepts a positive integral K. |
| `ExtentDivisions.division.G` | The enumeration permits overlaps with negative G. Keep Int. |
| `NumberDomain.N`, `NumberDirDomain.N` | The domain is the inclusive range zero through the largest task-grid extent. |
| `ScaleRatio.K`, `DivisorRatio.K` and axis variants | They encode quotients of positive task-grid extents after checking divisibility. |
| `CountRankAsc.R`, `CountRankDesc.R` | Rank counts colors before a color in a finite ordered set. |
| `DimDiff.D` | `dim_diff` emits `abs_diff` of unequal input/output grid extents, encoded as a count. |
| `TileCount.N`, `TileDim.D`, `SepTileCount.N`, `SepTileCountAxis.N`, `SepTileDim.D`, `SepThickness.G` | `fits` enumerates unsigned counts, unsigned positive tile dimensions and unsigned gaps; `sep_tile_count_axis` can add the count one. |
| Native proposer `Period.K` | `period` tests shifts starting at one below a grid extent, then emits the least common shift. |

`frame_extent.N` and `axis_extents.N1/N2` require the Position producer invariant to be checked across native producers; their arithmetic alone is a signed margin sum plus one. Do not infer Nat just from their names. `box_extent.N` is not unconditionally a count: it computes a frame extent after subtracting B from P, and an over-inset B can give a negative result.

Facts `input`, `ex_input` and `ex_output` have Position, Color and optional Example columns, with no numeric column to split. Copying a numeric column through an earlier derived relation preserves its inferred binding type; it does not create an independent count heuristic.

## Survey boundary

Functional dependencies, cross-atom implications, disjointness, relation symmetry and further identities are survey results until the coordinator selects them. Their measurement may inspect clauses, but production pruning must not implement them merely because they appear in the survey.

## Historical Number BODY descriptors

Historical `Number` is the signed-i32 `Term::Number` domain. `Int` keeps that
same domain: `Term::encode_number` casts i32 to u32, `Term::decode_number` casts
back, and `push_cells` writes the Number's i32 directly. `Term::decode` dispatches
both Int and Nat through that same Number branch. The bridge attests these
operations in the producer, historical-metadata and current acquisition builds;
a descriptor spelling alone supplies no encoding proof.

`Nat` adds the nonnegative domain; its producers are justified above. A
historical Number may bind a new Int or Nat only under the certificate's exact
program, complete stream, native scoped-label and old-header checks, with one
cell and no nominal type. For Nat, the acquisition owner additionally checks
every actual historical cell of that physical column in every validated entry.
Its receipt binds the source/build/payload, side/table/selector, scoped identity,
assignment/example/model coverage, counts and nonnegative min/max. Complete
empty runs are valid; a Count, stopped or absent run supplies no such evidence.
Nat decoding alone does not enforce this domain. Int needs no nonnegative
restriction, since its whole signed domain equals historical Number.

The same certificate accompanies the field through reader/header comparisons
and fresh projection. Current checked type and historical storage type remain
separate evidence; this does not equate Int with Nat in general or normalize
unrelated names. All other type/encoding, row and assignment checks remain
unchanged. The owner's source-attested numeric bridge implements these premises.

## The 41 reported gold memberships

The authenticated gold-match readback finds 41 joined membership tests whose
earlier binding column has exactly the tested type: Dir (12), DiagDir (5),
Dir8 (1), Axis (1), D4 (5), and C4 (17). Their earlier binding atoms lie in the
same body or an enclosing body. `dir_elem`, `diag_dir_elem`, `dir8_elem`,
`axis_elem`, `d4_elem` and `c4_elem` enumerate these complete native domains;
they introduce no label at these joined sites. Thus each test is redundant.
The direct lib bindings are the typed outputs of `axis_inversion`, `d4_inverse`,
`opposite`, `diag_dirs`, or a preceding `d4_elem`. The other bindings read already
defined columns, including typed INIT keys and rigid outputs. No current-test
narrowing or overlapping-domain premise is used. The per-program list is a
study report; none of these conclusions authorizes editing gold.


## Gold case normalization

The case-normalization pass deletes each conjunct that the Decoder's static
prune refuses, with the same function and the same binding premises as the
Decoder (`refused_verdict`), in each list of each form, in source order, each
conjunct against the prefix of the conjuncts it keeps. So the Decoder refuses
no conjunct of a normalized program. It deletes only `Valid`, never `Alias`,
`Constant`, or `Unsatisfiable`. A valid atom is a predicate true of
every incoming row. Joining that predicate therefore preserves each row and
its multiplicity (relations are sets). Under NOT the classifier complements
only the proved valid/unsatisfiable conclusions, so the same argument applies.
A conjunction may lose such a predicate without changing its rows; replacing
an inner body by an equal body also preserves OR, IF, ALL, and INIT key/input
semantics. No branch, projection, or model family is merged.

For `membership.subtype`, the earlier binding's implementation supplies a
value of T, and the tested membership enumerates all of S with T a subtype of
S. Thus its join cannot remove a row. Its label use is Join or Key, not Fresh.
All 41 measured gold matches have this form. Their prior binding atoms stay.
The native normalizer additionally visits every label use of each proposed
deletion and refuses one containing Fresh, including constraint binders. It
uses the mutation editor that preserves declared columns, and runs the native
resolver and whole-program checker on the edited AST. Deleting an only binder
cannot silently shrink a head or leave a later reader unbound.

The original checked program and stored study records are not mutated. Case
normalization writes a derived program with mapped source layout. If no valid
atom exists, the converter keeps the original text byte for byte. The native
streams digest participates in the case-normalization cache key, so a previous
normalization result cannot hide this pass after an engine or type change.

## Sampling and historical read boundary

Static sampling rejects a surviving edited atom when the shared classifier
finds a conclusion at that atom. The atomic editor maps simultaneous original
edit paths to the checked candidate's paths; neither deletion nor an untouched
gold test is a newly proposed atom. Exact identity replay remains available for
stored records, but historical classification does not depend on today's
alternative domain or held-value admission. `stored_static_prune_json` checks
and decodes the actual stored mutant, and `matches_at` applies exactly the
sampler's selected-site predicate to that checked program. Its types and
bindings come exclusively from the stored form.

`metadata_edits` uses the existing identity payload decoder and atomic editor
only to locate recorded changed sites. The temporary edited gold AST must emit
exactly the stored program's native tokens and emitter flags. `trace_paths`
then certifies unique node-kind/token-coverage correspondence; wrapper AST
paths need not be identical. Parsed and decoded gold address interpretations
must agree if both certify. A failed or ambiguous correspondence is explicitly
unavailable. Deleted-only sites supply no new atom. No current choice-domain
or held-interface refusal is evidence that a checked stored atom is unmatched.
These metadata operations neither construct a ValidMutant nor alter execution
admission, sampling, stored pairs, or classifier laws.

CompletionDomain certification returns before output insertion, `specs_drawn`,
and draw-kind counters on static rejection. The existing finite suffix search
therefore keeps searching the same bucket for a replacement until quota,
exhaustion, or its existing deadline. Search-node/attempt counters still count
the work. Unknown classifier evidence is not a proved rejection. The Decoder
and its opt-in legal-mask behavior are unchanged.

## Repeated positive atoms (`atom.repeated`)

`IrBuilder::atom`, `IrBuilder::site` and `IrBuilder::argument` compile a positive
read to a relation and its column-to-variable/zero arguments. Fresh, Join and
Key for the same LabelId compile to the same variable; Fresh is a binding
instruction to the checker, not a different runtime value. Thus after
`R(:C *C)` has bound C, another `R(:C C)` tests the very same tuple membership.
The second read binds nothing. The first read, including its Fresh binder,
is kept. A second Fresh or Key occurrence is not a deletion candidate.

`driver::inputs`, `driver::read` and `join::join_at` evaluate relation reads and
join their restrictions using the shared variable bindings. Relation/RowSet
rows are sets, not bag multiplicities. For each incoming row already satisfying
R with exactly these arguments, testing R again neither removes it nor creates
a new binding. The rule compares the native relation identity and every site's
column/field name and label/zero structurally, ignoring only the first read's
binding marks and unordered named-site order. It does not equate different
columns, aliases, permutations of positional fields, or different source names.

`filters::compile_union` preserves the enclosing variables in each OR branch;
its union is joined with the outer conjuncts. Consequently every row surviving
an enclosing positive R also satisfies R when a branch tests those same labels.
Removing that branch-local read preserves its result on every enclosing row,
then preserves the union and enclosing join. Facts proved only in a branch
never enter a sibling or the enclosing continuation. The same substitution of
a true repeated test is valid inside the existing IF, ALL and negated-form
probes: `compile_if` uses test/then and negated-test/else; `compile_all` tests
counterexamples and domain nonemptiness, and `compile_not` tests existence.
No test/domain fact is assumed in another sibling body. Independent clauses,
INIT keys and INIT inputs start separate repetition environments; key values
alone do not prove all of the key body's earlier tuple memberships.

A lifted read can use train examples only. `reads_train_examples` and
`driver::read` decide this per occurrence; the checked-program matcher requires
that flag to agree before using an enclosing read as evidence. The Decoder's
flat-prefix case uses only earlier reads in the same conjunction, so the same
labels on both reads have the same positive ex_output provenance. No inference
from a relation's spelling or decoded cells substitutes for this condition.
In addition, a positive `ex_output` occurrence is a compiler certificate for
other reads' train-only lifting. An enclosing occurrence does not substitute
for a nested conjunction's own certificate. Such an `ex_output` repeat is
therefore deleted only when the prior occurrence belongs to the SAME body;
it then leaves the certificate in that same conjunction. Cross-body
`ex_output` repeats are deliberately outside this rule, even if their row
predicate is implied. This preserves definedness on test-only dependencies.

Only later positive atoms with no Fresh/Key site are removed. Relations that
are undefined remain undefined through the retained earlier read. Limits may
stop either evaluation sooner; a stop is not claimed equal to a completed row
set. Native whole-program re-resolution/checking, original declared interfaces
and editor provenance are retained. Therefore deletion cannot drop the only
binder, change a key header, or silently rebind a later use. This extends the
existing valid-class normalizer; it is not a second text-cleanup pass.

## Two conjuncts of one conjunction

These rules compare the last conjunct of a flat decoder body with one earlier conjunct of the same body. A row of the body satisfies both. The decoder refuses a conjunct that these rules and the single-conjunct rules find valid, in each list of a form: the top level of a clause's body, a branch of an `OR`, a list of an `IF` or an `ALL`, and a body of an `INIT`, `CHOOSE` or `RIGID_DET` form. A list's verdicts read the types of the labels that the list's own atoms make, and no premise from an enclosing list. A list whose conjunct holds no row makes its enclosing form constant, and a valid conjunct leaves its list's rows. A site matches another where both stand at one column and hold the same label or `0`; `*` and `^` make their label, and a bare label joins it. Only sites of one label take part, and a site on a record's fields matches nothing.

- `atom.implied`: an atom T that makes no label, and an earlier atom A of the same relation that matches each site of T. A row that A matches is a row of the relation with T's values at T's columns, so T holds wherever A holds, and removing T leaves the body's rows. T binds nothing, and A keeps T's relation read, its definedness and, for `ex_output`, the certificate in the same body, as in `atom.repeated`.
- `not.contradicted`: a positive atom P and a `NOT` N of the same relation, in either order, where P matches each site of N. The row that P matches is one that N refuses, so the body has no row. A relation under `NOT` is derived in each case that reads it, so the body is empty, not undefined.
- `not.implied`: two `NOT`s of the same relation, the later N2 matching each site of the earlier N1. A row that N2 would refuse matches N1, which refuses it already, so N2 removes no row that N1 leaves.
- `comparison.implied` and `comparison.contradicted`: two comparisons of the same two operands, in either operand order. Each keeps a set of the outcomes less, equal and greater of one operand against the other, and the two together keep the intersection. An empty intersection holds no row. An intersection equal to the earlier comparison's set leaves the later one nothing to remove.

A `^` that makes the Example label of a read that a case may lift gives the read no train-only certificate, since `binds_train_examples` counts `*` and a join and not `^`. A later read that joins that label can hold the certificate, where a positive `ex_output` atom of the body holds the label, and removing it removes the only certificate. So `atom.repeated` and `atom.implied` give no verdict on a later read of the Example label that an earlier read makes with `^`, unless the relation is a fact or a lib relation, which no case lifts.
