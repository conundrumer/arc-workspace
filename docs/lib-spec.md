# Lib specification

The lib, `programs/lib.dl` and the modules under `programs/lib/`, is the vocabulary a solver program is written in. This document states what the lib holds, the test each kind of content passes, the name of each element, and where everything the lib does not hold goes. It is the authority for the rewrite of the lib and for every later addition to it.

## Principle

- A task's intended concept is a composition of simpler things, and the simpler things are finite.
- A kind of object, a bar chart, a checkerboard, a worm, is a conjunction of relations held at particular values.
    - There is no end to such conjunctions: one more conjunct makes one more kind.
- The relations being conjoined are the standard constructions over a few structures, the rows of the matrix under Constructions.
- The lib holds those constructions, the two algebras they stand on, and the searches that find a structure in one input. A solver program is a composition of them.
- Naming a conjunction in the lib is the error this document exists to prevent.

## Kinds of content

Every element of the lib is one of these kinds, and each kind has its own test.

### Algebra

- A fixed vocabulary of relations over a type, closed under that type, with no cell set as input.
    - The box algebra is over Box, Position, and Offset.
    - The orientation algebra is over Dir, Axis, DiagDir, DiagAxis, D4, Sym, and Sense, with Dir8 and Axis4 as the unions.
- Each algebra has a signature or tables, and derived relations.
    - The box algebra's signature is its fundamental operations: every relation of the algebra is a term over it with integer arithmetic and comparison, and no operation of the signature is a term over the others. An operation over an infinite domain is a functor, and each mode a site uses is a relation of its own.
    - The orientation algebra's tables are fact sets, each invariant under the D4 action on every column. The invariance is the check that a table states geometry and not an orientation.
- A derived relation is in the algebra when a site cannot state it without one of these:
    - a variable the claim does not mention
    - a form the program bans: arithmetic, or a number or record literal
- A derived relation whose definition is tests over its own arguments only is written at the site.
- The check is mechanical: a body variable absent from the head, or a banned form in the body.
- The lib holds the derived relations kept through an intermediate. The ground is the handbook's Fidelity rule: the program states the intended concept's relations directly, and a site forced to invent an intermediate states a derivation instead.
    - Each is an inline macro, so a site that needs the intermediate writes the signature atoms.
    - Uses today, in solvers: `neighbor` 293, `nearer` 107, `same_line` 100, `diag_dirs` 72, `jump` 70, `centered` 51, `dist_pair` 48, `perp_dir` 44, `same_dist` 27, `diag_dist` 17.
- A relation over a union type is held as one relation when a site over the union would otherwise case-split on the kind: the union of its components' relations, as `dir8_opposite`, or a cross-type relation made symmetric, as `dir8_adjacent`.
- A table is admitted when a claim states it. The types are finite, so the vocabulary is bounded and an addition is never an explosion.

### Construction

- A structural operation over a domain the caller supplies, stated at the lowest level that can state it.
    - The levels are the matrix's columns: counts, members, members with an order, members with a step, members with edges, cells, valued families, with the two algebras beneath the cells.
- A construction passes three tests:
    - It is one operation on a structure, with a name a mathematician already has. Its description mentions no cells, colors, directions, or arrangement unless the structure is geometric and nothing more abstract can state it.
    - No simpler construction plus clauses that populate its inputs gives it. When X is Y with its inputs populated, Y is the construction and X is a composition.
    - A positive sign is an existing `Requires:` that the construction would discharge.
- Whether the encoding of a construction needs a form the program bans does not bear on the test. Connectivity's labeling needs `ord`, and that decides nothing.
- A construction terminates on finite inputs, and no input of an instance reads an output of that instance. Unfold is the one exception: its `step`, `skip` and `take` read its outputs through atoms whose every variable another atom of the clause grounds, so the recursion filters a finite set. A program recurses through no relation of its own, and a closure in a program is an instance of a construction.
- An instance of a construction asserts nothing about the task by itself.
    - The claim is asserted by the clauses that populate its extensional relations.
    - The `@claim` line that the solver-file document attaches to an instance attaches to those clauses.

### Detector

- A search run on one input:
    - a candidate set generated from the grid
    - a consistency test over each candidate
    - a selection of the survivors
- A detector is a determination run inside the program on one input rather than on the train pairs.
- Where the candidates come from distinguishes a detector from a relation the intended concept has:
    - a test over a closed enumeration, the eight D4 elements, states a relation the intended concept has
    - a test against stored patterns is a lookup
    - a candidate set generated from the grid, every placement, every shift the frame admits, every pair of corners, is a detector
- A detector is judged whole: its candidate set is generated from the input, its test is one test, and it is never decomposed at a site.
- A detector that finds one value, a period, a tile side, a scale, serves both uses of that value:
    - When the value is one for the task, it is a stored parameter, and its `@derive` line names the proposer, which is the detector instantiated over every example under `Uniform` in `programs/proposers.dl`.
    - When the value varies per input, the program instantiates the detector itself.
- A detector runs under an input claim that says what counts.
    - The instance carries the `@claim` line of that input claim.
    - An input that breaks the claim is a divergence witness, judged by the annotator, and the detector is exact for the claim as written.
    - Where a task needs tolerance, the detector carries a defect count and a bound, which is still a relation.

### Task structure

- A comp a kind of task needs, enumerable: `Choose`, `DemonstrationConsistency`. `Choice` and `impl_choice` are the solver's own, under the solver-file document.
- Each has its own rules in the solver-file document.

## What the lib does not hold

### Compositions

- A composition is any derivation built from lib relations by joins and negation. Every program is one.
- A composition never gets a comp, unless its only inputs are the domain its constructions take, as under Cell instances.
- A composition that recurs across solvers is a composition idiom, recorded with:
    - a trigger, the situation it applies to
    - a shape with holes
    - a `Match:` line that finds its instances
- Composition idioms live in the idioms document, each entry in the form a proposal entry has, with its survey.
    - Reading order, a span between two marks, a run through blocking cells, a drawn rectangle's four sides are composition idioms.
- A composition idiom is justified by recurrence, so the count of its instances is the evidence for it. A construction is justified by its level, and a count is no bar for it.
- The style document's idioms, complement tests and off-edge tests, are syntax idioms, and the qualifier separates the two.

### Engine devices

- A clause shape that exists because Souffle cannot do something, such as a universal read inside its own recursive stratum, goes in one of two places:
    - inside a construction's body behind its interface
    - under `@workaround` in a solver
- It is never named, surveyed, or recorded as an idiom.
- A `@workaround` in a solver is a sign to check whether a construction is missing from the lib or not called.

### Approximations

- An output claim with no relational form is approximated per solver under `@approximated`, with its witness, and never enters the lib.

## Names

- A construction is named by its operation: an abstract singular noun, the mathematician's term where one exists.
- A detector is named by what it finds, in the plural.
- An exported relation is named by what one row states:
    - a predicate over its arguments: `connected`, `exposed`, `reachable`, `superset`
    - the noun of the thing a row gives: `rank`, `distance`, `box`
- An extensional relation is named by its rows' role in the construction, and one word has one meaning across the lib:
    - `member`, an opaque element
    - `cell`, a Position in a set
    - `node` and `edge`, a graph; over cells, the nodes are the Positions the construction steps between
    - `source`, where something starts
    - `before`, a strict order
    - `score`, a number that orders
    - `secondary_score`, a number that orders within each tie of `score`
- Names use whole words. An abbreviation is used only in one of these cases:
    - a reader of the lib already knows it: `id`, `max`, `min`, `dist`, `diag`, `perp`, the D4 constant scheme
    - a long word recurs across many names and its short form is unmistakable
- Once an abbreviation is used it is used everywhere the word appears, and nothing else is shortened to the same form.
- The algebras' naming scheme:
    - The Dir and Axis form is bare, the DiagDir and DiagAxis form takes `diag_`, and the union form takes `dir8_` or `axis4_`: `opposite`, `diag_opposite`, `dir8_opposite`.
    - A relation that gives an Offset ends in `_offset`, and the cell relation beside it has no suffix: `jump_offset` and `jump`.
    - A relation stating that two positions agree on something starts with `same_`: `same_dist`, `same_line`.
    - The insets and outsets take `edge_`, `axis_`, `uniform_` by how many sides they set.
    - "Step" means an offset throughout, in `step_offset` and Connectivity's `step`; `neighbor` is the cell one step away.
- Markers:
    - `// @extensional`, a caller-supplied relation
    - `// @detector`
    - `// @task-structure`

## Types

- The ARC types, Color and the orientation types, are nominal: a value has identity and no arithmetic. Its encoding as a number is an engine fact the lib hides.
- A `number` is a count.
- Box is the box algebra's carrier. Position and Offset are its two interpretations, types under Box, and `compose` takes Box at each column, so it adds a cell to a translation.
- `Ident` is an opaque label, `Example` the index of an example, train or test, and `Unit` the key of a single-set site.

## Conventions

- The first column of a relation in a keyed comp is its key, and each key is one independent instance.
- A `Requires:` sentence states a precondition the comp does not check, and what happens when it fails.
- A relation over an infinite domain, such as `margin`, is inline or a functor. That is an engine choice, and the one restriction it puts on callers is stated once in the lib header.
- A site that writes out the definition of a relation or cell instance the lib holds is a reimplementation, which a lint flags.
- Default rows under an extensional relation, which facts or a rule of the component give, exist only in a construction or detector over cells, where they are the cardinal steps or directions, or the D4 identity. A construction over members has none.

## The box algebra

Box is the carrier, Z⁴ as the four margins (t, b, l, r), an abelian group under addition, with the frame implicit in a cell, whose margins on an axis sum to the extent less one. The functors in `programs/lib_functors.cpp` do its arithmetic.

- **Signature**, each operation with the modes sites use.
    - `ZERO`, the identity.
    - Addition: `compose`, and `relative` as its second mode, with the result on the other side.
    - The injection of a count into one margin: `edge_inset(d, k, b)` over Dir.
    - The projection of one margin: `margin(b, d, k)`; for a cell, its distance to edge d.
    - The D4 action on the margins: `apply`.
    - Integer comparison, which the site has natively.
- **Terms with a banned form.**
    - Arithmetic over projections: `corner_dist`, `corner_ring`, `frame_extent`, `edge_depth`, `gap`.
        - `corner_dist`, the sum of a position's two distances to a corner's edges; `corner_ring`, the greater of them, its ring about that corner.
        - `frame_extent(p, a, n)`, the extent of p's frame along a.
        - `edge_depth`, the least of a position's four edge distances.
        - `gap(d, p, q, k)`, with the mode p and q given, the count of cells strictly between p and q along d, q ahead, which is `jump` at k + 1; Gravity's travel to the body ahead, its one site.
    - A literal: `step_offset` hides the `1`, being `jump_offset` at 1; `sub_extent` hides a range.
- **Terms kept through an intermediate**, held.
    - Injections composed: `axis_inset`, `uniform_inset`, `corner_inset`; the outsets `edge_outset`, `axis_outset`, `uniform_outset` and `corner_outset`, each `relative(inset, ZERO, v)`; `jump_offset`, an inset with an outset; `jump` and `neighbor`, an offset composed.
        - `corner_inset(diag, k, b)` is `edge_inset`'s analogue at a corner, k on both of its edges. Its uses are the three `edge_inset` sites at a corner, in 6cbe9eb8, 8618d23e and a61ba2ce.
        - `corner_outset(diag, k, b)` is `edge_outset`'s analogue at a corner, k past both of its edges. Its one use is b1986d4b's `edge_outset` at a corner.
        - `axis_outset` has two sites, both in 4e34c42c.
    - `box_extent`, the `frame_extent` of a cell read in the box's frame through `relative`.
    - Projections split by axis: `split(p, a, along, across)`, p's component along a with the other axis zeroed, and its component across a with a zeroed.
    - A universal over the four margins: `inside`, `interior`.
    - Projections compared, through the projection: `same_dist`, `same_line`, `same_corner`, `same_slab`, `nearer`, `centered`, `dist_pair`, `diag_dist`, `axis_extents`.
        - `same_corner` and `same_slab` are `corner_anchor` and `slab_anchor` renamed into the `same_` family.
    - Added:
        - `toward`, the Dir8 from one position toward another
        - `ahead(d, p, q)`, q on p's line of d's axis and nearer d
        - `frame_offset(p, a, k, v)`, an offset of magnitude k along a that the frame of p admits
- **Written at the site**, each two tests on its own arguments, a composition idiom at +1 atom per use.
    - `crop`: `inside` and `relative`, 231 callers.
    - `box_edge`: `inside` and `same_dist`, 64.
    - `box_corner`: `inside` and `same_corner`, 49.
- **Leaving the module.**
    - To Division and Tiling, which take the axis as data where these fixed it: `divide`'s position forms, `divide_by_size`, `divide_slab`, `divide_by_size_slab`, `divide_2d`, `divide_by_size_2d`, `concat`, `concat_slab`, `concat_2d`.
    - To ExtentDivisions: `divide_gap`.
    - To Division, as its count form: `stride`.
    - To Frame and its idioms: DirFrame, AxisFrame, Frame2D, DirPack.
- **Not added**, each one atom at the site.
    - `nearer_eq`: `nearer` negated with its arguments swapped.
    - `shift_opposite`: `relative(V, ZERO, V_inv)`, which its six callers write.

## The orientation algebra

- **Values.**
    - The constants of each type, `DIR_T` through `SYM_D4`.
    - The enumerations: `dir_elem`, `axis_elem`, `diag_dir_elem`, `diag_axis_elem`, `d4_elem`, `c4_elem`, `sense_elem`, `sym_elem`.
    - The unions: `dir8_elem`, `axis4_elem`.
    - `d4_elem` and `c4_elem` are `sym_member` at a constant, held for the constant.
- **Tables**, each invariant under the D4 action on every column.
    - Incidence: `axis_of`, `diag_axis_of`, `corner_dir(c, a, d)`, the cardinal direction of corner c on axis a.
    - Involutions, the other element of a pair: `opposite`, `diag_opposite`, `perp`, `diag_perp`.
    - Rotations, a turn being the smallest rotation of its type:
        - `turn(s, d, d2)`, the quarter turn in sense s over Dir
        - `dir8_turn(s, d, d2)`, the eighth turn in sense s, admitted on judgment with no site yet
        - `c4_turn(s, t)`, the quarter turn in sense s as its C4 element
    - Reflections, each over Axis4 in one sense, replacing `flip_of` and `diag_flip_of`, which disagreed in sense:
        - `reflection(a, t)`, the reflection across a, as the D4 constants are named
        - `axis_inversion(a, t)`, the reflection that inverts a; `flip_of`'s meaning for its 52 callers
    - Group: `d4_compose`, the composition of two D4 elements, which 21897d95 and 46442a0e write as two `apply` atoms on one position; `d4_inverse`; `sym_member`; `pose_difference`, the D4 element between two poses of one assembly, as [The pose](arclog/rigid.md#the-pose) gives.
    - Identity: `d4_identity(d)`, the one row of the D4 identity.
- **Derived**, each through an intermediate.
    - `perp_dir`, the axes.
    - `diag_dirs`, the other axis.
    - The D4 action on each direction type, `apply_dir`, `apply_diag_dir`, `apply_dir8`: the step offsets. They move here from the box module.
    - Added:
        - `dir8_adjacent`, two Dir8 one compass step apart, a corner and a cardinal it holds, `corner_dir` read both ways; the axis they share
        - `dir8_inversion`, the D4 element that inverts each axis a Dir8 has a component on, the axis inversion for a cardinal and the half turn for a diagonal; the axis and the inversions
- **Unions**, one relation over the union type: `axis4_of`, `dir8_opposite`, `apply_dir8`.
- **Written at the site:** the other sense, `sense_elem(S2), S2 != S`, a test on its own arguments.

## Constructions

- Each construction has two properties the tables sort on:
    - the operation it performs
    - the domain its extensional relations give
- The matrix has one entry per cell, and a row has one entry by the levels.
- The cell column's entries in a row that also has a members entry are cell instances.

| Operation | counts | members | members with an order | members with a step | members with edges | cells | valued families |
| --- | --- | --- | --- | --- | --- | --- | --- |
| count | | Cardinality, Excess | | | | | |
| unanimity | | Singleton | | | | | |
| comparison | | Inclusion | | | | | |
| quotient | | | | | Quotient | Connectivity | |
| rank, extremum | | | Order | | | BoundingBox | |
| iteration | | | | Walk, Unfold | | Ray | |
| closure | | | | | Propagation, Distance | Flood, CellDistance, Enclosure | |
| propagation | | | | | UnitPropagation, PathInverseConsistency | | |
| boundary | | | | | | Boundary | |
| agreement | | | | | | | Agreement |
| division | `divide` | | | | | Division | |
| frame | | | | | | Tiling, Frame | |

### Cell instances

- A composition whose only inputs are the domain its constructions take, the cell set with the cardinal steps by default, gets a name in the lib. A members construction gets a cell instance this way, since every site would supply only the cells and the step.
- The cell instance takes the geometric name where one exists, and otherwise the construction's name qualified by its domain.
- The pairs: Quotient and Connectivity, Propagation and Flood, Distance and CellDistance, Distance and Ray, `divide` and Division.
- Enclosure is two cell instances composed, Flood then Connectivity, over the cell set alone, so it is a construction of its own.

### The constructions

Order takes the order in either of two forms:

- `before(key, a, b)`, a strict order the caller states, read over `member`
- `score(key, t, s)`, a number per member; the order is the preorder it induces, and the lib compares scores and materializes no pairs
    - `secondary_score(key, t, s)`, optional, a number per member that orders the members within each tie of `score`: members compare by `score`, and within a tie by `secondary_score`. A member with a `score` and no `secondary_score` row precedes the members of its tie that have one.
- `probe(key, t)`, in either form, a member ranked by its `before` rows or in the score form and not counted among the members

A nested order of any depth is a composition over Order: the outer Order's rank goes to `score`, and the rank of an inner Order keyed by the outer class goes to `secondary_score`. A third level chains one more Order in the inner one.

| Name | Extensional | Exported | Operation |
| --- | --- | --- | --- |
| Cardinality | `member`, `domain` | `size` | members per key; a key in the domain with no member has size 0 |
| Excess | `plus`, `minus` | `excess` | the amount by which the plus set outnumbers the minus set |
| Singleton | `member` | `value`, `plural` | the one value of the set, absent when the members disagree |
| Inclusion | `pattern`, `observed` | `superset`, `equal` | each observed set against the stored patterns, by count equality; the pattern side is keyed, and the enumeration ranges over pairs that share a member |
| Quotient | `equivalent`, or `edge` | `class` | one class id per equivalence class; `edge` gives a generating relation, which the construction closes inside its body |
| Order | `member`, `before` or `score`, `secondary_score`, `probe` | `rank`, `dual_rank`, `minimal`, `maximal`, `successor`, `cyclic_successor` | rank, the count of predecessors; dual rank, the count of successors; minimal and maximal, the elements nothing precedes or follows, all of them under ties; successor, the immediate successor; cyclic successor, the order closed from the last to the first |
| Walk | `successor`, `steps` | `walk` | the element n successors from a start, bounded by the counts in use |
| Unfold | `start`, `initial_taken`, `initial_untaken`, `conflict`, `score`, `step`, `skip`, `take` | `taken`, `untaken`, `excluded`, and `take` where `score` is given | the state along a walk the state may choose: a partition, one item crossing per `step` and none per `skip`; `step`, `skip` and `take` may read the outputs, and the inputs that bind the types stand before them; with `conflict`, a relation over items, the items in conflict with a take leave `untaken` as `excluded`, without joining `taken`; with `score`, a number per state and item, the item taken at a state is the untaken item of least score, ties fork the walk, each walk is one tiebreak resolution, and walks that reach states of equal content merge |
| Propagation | `source`, `edge`, `join` | `reached` | forward chaining: a source is reached, an `edge` reaches its head once its tail is reached, and a `join` reaches its head once both its tails are; keyed by the start node, with that node as its source, `reached` is the closure of `edge` |
| Distance | `edge`, `weight`, `source`, `source_distance` | `distance`, `predecessor` | least cost from a source, and every predecessor on a least-cost path; a hop costs one, a weighted edge its weight, a source is at zero or at its `source_distance`; weights are non-negative and count cells at every site |
| Connectivity | `node`, `step` | `component`, `adjacent` | connected components under the steps, the cardinals by default; adjacent, one step inside the set |
| Flood | `node`, `source`, `step` | `reached` | the nodes a walk from a source reaches by steps inside the set, the cardinals by default |
| CellDistance | `node`, `source`, `step` | `distance`, `predecessor` | Distance over the steps inside the set, the cardinals by default |
| UnitPropagation | `candidate`, `conflict` | `forced`, `excluded` | a cell with one candidate piece forces it; a piece overlapping or conflicting with a forced piece is excluded; the forced pieces are those every exact cover holds |
| PathInverseConsistency | `candidate`, `conflict` | `supported`, `unsupported` | a candidate is unsupported when it extends to no compatible candidate of some other piece, or to no compatible pair of some two other pieces |
| Enclosure | `cell` | `enclosed` | the parts of the set the frame edge does not reach, each under its id |
| Boundary | `cell`, `dir` | `boundary`, `exposed` | `exposed(p, d)`, nothing of the set one step from p toward d, off-frame counting as nothing; boundary, exposed toward some direction; the directions are the cardinals by default |
| BoundingBox | `cell` | `box` | the least box containing the set |
| Ray | `source`, `node`, `dir` | `ray`, `end` | a straight path from a source, its origin, toward a direction, each step onto a node, with the step count and the origin; a source need not be a node, and is on its own ray at step 0; before its first node, a cast also steps onto a position off its grid where each margin the step lowers stays at or above 0; end, its last cell, the one exposed toward the direction in Boundary's sense |
| Agreement | `source`, `target`, `transform` | `mismatch`, `conflict` | two valued families, keyed by Position or Offset, under the D4 elements in `transform`, the eight by default; mismatch where an image lacks the value; conflict where both exist and differ |
| Division | `cell`, `parts`, `side`, `gap` | `tile` | equal parts per axis, by count or by side, with a gap; an axis given neither passes through; an axis with no `gap` row has gap 0; the cell instance, per axis, of `divide` |
| `divide(t, side, gap, part, remainder)` | | | division of a count with remainder, the remainders past the side dropped by the gap; an inline relation, in `stride`'s place |
| Tiling | `outer`, `inner`, `gap` | `cell` | the frame tiled by the inner frame at the outer positions, one cell per pair, with a gap per axis |
| Frame | `extent` | `cell` | the cells of a frame from its per-axis extents; an axis with no `extent` row has extent 1; `AxisFrame` is its internal part |

## Detectors

| Name | Extensional | Exported | Finds |
| --- | --- | --- | --- |
| Outlines | `node` | `box` | the rectangles drawn in the set |
| Occurrences | `cell`, `shape`, `transform` | `candidate`, `occurrence` | the placements of a shape, candidate where one shape cell lands on its value and occurrence where every one does, under the D4 elements in `transform`, the identity by default |
| Periods | `cell` | `period`, `fundamental_period`, `approximate_period` | the translations that fix a valued set; the fundamental period per axis, the least period; the period read through sparse damage |
| ExtentDivisions | `frame` | `division` | the divisions a frame's extent admits, per axis, read from the extent alone; `division(key, a, n, k, g)`, n parts of side k with gap g |
| Scales | `cell` | `scale` | the scale a picture is drawn at |
| Wallpaper | `transform`, `cell`, `grid`, `period` | `symmetry`, `transform_used`, `action` | the isometries fixing a periodic valued set, each a D4 element with the coset of its shifts under the period translations; `symmetry` holds every shift of the coset under which some cell of the frame lands in the frame, so no member of a coset is chosen; with no period, the D4 symmetries of the set; transform_used, a transform with an admitted representative, which a determination naming a `Sym` reads; action, one step under a generator at each of those shifts, where the image lands in the frame |

- A detector whose test is agreement instantiates Agreement rather than restating it: Occurrences, Periods, Wallpaper.
- A detector whose value is a parameter has a proposer in `programs/proposers.dl` that instantiates it over every example under `Uniform`.

## Task structure

- `Choose`, as [Constraints](arclog/constraints.md#implementation) specifies it: the compile target of the arclog `CHOOSE` form, propagation then enumeration of the residual under a cap.
- `DemonstrationConsistency`, as the solver-file document and the `DemonstrationConsistency` entry specify it.

## Performance

- No solver runs slower after the rewrite than before it.
- The baseline is the corpus run with the run cache bypassed:
    - 862 solvers in 4 min 46 s
    - the slowest solver at 5.8 s, every solver under the 20 s per-grid limit
    - 859 passing
- The one measured hazard is an order materialized as pairs. Order over 3,000 elements:
    - by `before`: 2.1 s
    - by `score`: 0.16 s for `minimal`, 0.6 s for `rank`, 0.2 s for `successor`
    - the present `Extremes`: 0.1 s
    - Placement families reach thousands of elements, so a site that orders by a number, or by two lexicographically, uses the score form.
- The implementation mechanisms, each behind its interface:
    - The algebras run on functors.
    - The closure and propagation rows, Distance, Connectivity, UnitPropagation, PathInverseConsistency, run as lattice relations: one value per key, joined under `Lub`, so a minimum or a shrinking candidate set is a clause.
    - Order's rank by score, `edge_depth`, and BoundingBox's margins are user-defined aggregates, one fold over the scores.
    - [Souffle: undocumented features](souffle-undocumented.md) states both features. Souffle checks neither that the operators form a lattice nor `Leq`, so each `Lub` is a one-line functor over a known lattice.
    - A list-valued functor over the record table serves what neither covers.

## Cost at the sites

The cost of a migration is the change in atoms at the site, measured on the smallest real caller of each comp, each probe passing its pairs and lint.

| Migration | Atoms per site |
| --- | --- |
| Ordinal, Extremes, ArgExtremes to Order | +3 |
| Mode to Cardinality and Order | +2 |
| LexOrder to Order | +5 |
| the present Ray to Ray | −2 |
| Slide to Ray | +2 |
| Between to Ray | +6 |
| Gravity to Distance | +7 |
| GraphDistance to Distance | 0 |
| Components8 to Connectivity | +3 |
| Reach to Connectivity | +1 |
| Rim8 to Boundary | +2 |
| DiagPlacement to the box algebra | +3 |
| D4Map, two sets, to Agreement | +4 |
| divide_slab and divide_by_size_2d to Division | +5 |

- A figure of +4 to +7 is the cost of writing at the site the claim the comp hid: the two-direction join, the contact relation.
- Not measured:
    - OrderFrame, through `axis_inset` over the two ranks
    - IndexCycle, through `cyclic_successor`
    - Rim.depth, through `adjacent`

## Disposition of the present lib

| Present | Becomes |
| --- | --- |
| Tally, Excess, Unanimous, KeyedSetCompare, Canon | Cardinality, Excess, Singleton, Inclusion, Quotient |
| IdentOf | Quotient over the identity |
| Ordinal, Extremes, ArgExtremes, Mode | Order, score form |
| LexOrder, OrderFrame, IndexCycle | composition idioms over Order |
| Order | Order |
| CycleWalk, Take | Walk, Unfold |
| GraphDistance, Gravity | Distance |
| Rim.depth | CellDistance |
| Components, Rim, Bbox | Connectivity, Boundary, BoundingBox |
| Closed | Enclosure |
| Components8, Rim8 | composition idioms over Connectivity and Boundary |
| Reach | Flood |
| Slide, Ray | Ray |
| Between | a composition idiom over Ray |
| Diagonal, DiagPlacement | composition idioms over the box algebra |
| crop, box_edge, box_corner | composition idioms over the box algebra |
| dist, axis_dim, corner_anchor, slab_anchor | margin, frame_extent, same_corner, same_slab |
| dir_of, rotation, flip_of, diag_flip_of | corner_dir, c4_turn, axis_inversion, reflection |
| — | d4_compose, dir8_turn |
| D4Map, one set | Agreement, with the set as source and target |
| D4Map, two sets | Agreement |
| Occurrences, OffsetInvariance, Outlines | Occurrences, Periods, Outlines |
| DividerTiles | a composition idiom over Order with `probe` |
| Divide2D, Tile2D, the division and concat relations | Division, Tiling |
| stride | `divide` |
| CoverForcing, PlacementPruning, TiebreakResolutions | Choose |
| DemonstrationConsistency | unchanged |
| Frame2D, AxisFrame | Frame |
| DirFrame, DirPack | composition idioms over Frame, Cardinality, and the box algebra |
| ParamsHelpers, `Dim` | retired; Params instantiates Frame and Division over stored extents |
| Wallpaper, Induce, Transitive, ScoreOrder, as proposals | Wallpaper, DemonstrationConsistency, Propagation, Order's score form |

## Disposition of the proposals

- Absorbed by the lib, their entries closing with a pointer: Transitive, ScoreOrder, Ordinal.rev, Mode.rare, OrderFrame.succ, ShiftInvariance.shortest, ShiftInvariance.unbroken, Occurrences.admits, Induce, Wallpaper, PixelScale, Magnify, Gravity-diagonal, Divide2D keyed cell, Per-axis gap, SupportPruning, PlacementRoom, Reach8, KeyedSetCompare-extensions, Rim.interior, ahead, TiebreakResolutions-tied-slot, edge_depth, corner_shell as `corner_ring`, toward, frame_shift as `frame_offset`, dir8_flank as `dir8_adjacent`, flip_toward as `dir8_inversion`, D4Placement, D4Map.broken, Frame2D.from, Concat2D.
- Composition idioms, their entries moving to the idioms document with their `Match:` lines: Abut, apply_about, apply_between, bend, Between.on_axis, Between.strict, border_step, box_corner_out, Checkerboard, Closed.wall, Collinear, Concentric, Congruent, corner_only, Crossing, D4Map.onto, DividerTiles.box, flanked, GapComponents, merge, GroupOrder, inward, PeriodOrbit, LineBands, LineColor, LineCover, lone, Maximal, meet, multi_cell, near_edge, near_half, Obstruct, Occurrences.carry, Occurrences.covers, other, Outset, quad, Relocate, run_line, Runs, same_phase, SeatCenter, Shared, SizeMatch, Surround, touch, GreedyWalk, Bbox.advance, Bbox.corner_cell, Bbox.edge_gap, Bbox.flush, Bbox.gap, Bbox.open_corner, Bbox.place.
- Closed or not lib: adjacent8, extent_upto, nearer_eq, shift_opposite, ConcatPipeline, Matching, Reframe.extents, diag_edge_delta, Preempt, Profile, BarChart, Bounce, override-input-defaults, RIGID-group, which belongs with the parameter encodings.
