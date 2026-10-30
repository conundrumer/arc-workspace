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

Decoder suppression is currently conservative to a flat top-level clause. Completion is detected on every grammar step, including an atom closing on the next relation token and a clause closing on END. The mutation editor preserves its declaration columns. Both the original and proposed equality are submitted to the whole native checker, and their scoped label types, relation types and native checker grid evidence must agree. A non-refusal from a prefix checker is not sufficient: it can mean Undecided. Incomplete or nested forms, untyped zero bindings, failed checks and changed interfaces retain the original atom. In particular, EqualityAndZero rejects a top-level all-zero exported column; this implementation does not claim that a constant atom always has an admitted equality representative. This is an explicit remaining coverage limitation against the brief.

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
