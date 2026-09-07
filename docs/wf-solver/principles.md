<!-- When editing this doc:
- Write in the indicative mood.
- Avoid justifications, unless there is necessary reason.
- Avoid constrastive structures, unless the alternative needs to be addressed.
- When citing a task:
    - To give precedence: write a bare id.
    - To state the task's facts: write an id with a gloss not using the task's internal vocabulary. -->

# Principles

The theory of tasks and their solvers, and the design norms for the best model of a task.

## Definitions

- **body** — the rules that derive `out` from `in` and Consts. In synthesis terms, the *program* that the parameters complete.
- **Consts** — the data of a solver. In modeling terms, the *parameters*.
- **slot** — a Consts relation that holds facts. A Consts relation derived by a rule is not a slot. One *parameter*.
- **fill** — the facts a task gives a slot. A parameter's *value*.
- **Consts shape** — the slots with their schemas. The *parameterization*.
- **Fit** — the rules that derive a slot's fill from the examples. Sibling solvers share the body and the Fit.
- **model** — a Consts shape with the map from fill and input to output that a body computes over it. Bodies that compute the same map over one shape are alt impls of one model, and the same-model test (Coverage) checks that. A model fits a task when some fill of its shape produces the task's outputs from its inputs.
- **family** — the tasks a model fits.
- **sibling** — another task in the family.
- **rival model** — of a model: another model that fits the task.
- **decision point** — a property of the task that the pairs do not determine. In experimental-design terms, a *factor*, and its answers are its *levels*.
- **claim** — the assertion that the task is in a model's family. In scientific terms, a *hypothesis*. A claim decomposes by decision point into one answer per point.
- **case** — the encoding of one model in the solver, as a value of `Choice`. A record-typed `Choice` holds one field per decision point. A solver with one case has no `Choice`.
- **witness** — an input on which two candidates, models or fills of one model, produce different outputs. In synthesis terms, a *distinguishing input*.
- **exercised** — a part of the solver is exercised by a pair when that pair's output depends on it.
- **setup** — the reading that every case shares, and the body rules that encode it.
- **setup variant** — another encoding of the same setup: it finds the same structure with a different Consts shape. A *reparameterization* of the setup.
- **settled form** — the encoding that the corpus already uses for a setup structure. The solver that introduces a structure settles its form. A *precedent*.
- **reading** — which structures a model finds in the input grid. Models that find different structures are different readings. In vision terms, a *parse* of the grid.
- **prior** — a core knowledge prior that ARC training tasks teach. The Prior terms of `concepts.md` name them. A case claims which priors the task teaches. Several models claim the same priors.

The goal is a corpus that supports program synthesis of solvers. Lib primitives are the vocabulary of that synthesis, and fragments of solvers are its larger units. Bodies and their Fits accumulate across the corpus as fragments for reuse. Consts data stays specific to each task.

## Fidelity

The body is faithful to the concept of the task: the actual task, not an artifact of how the data or the medium encodes it.

**Relational form.** ARC concepts are relations between cells, regions, and properties. The body encodes them as relations. Arithmetic in a rule usually represents a relational operation: a wraparound shift is a walk along a cycle. Arithmetic that seems necessary is a missing lib primitive.

**Lib units.** If the task does not have a lib unit's concept, the solver does not use that unit. Needing part of its computation is not a reason to use it. If only one step is needed, it is written with primitives or a local rule.

**ARC values.** The body works in the task's own values: colors, directions, axes, D4 elements. Projecting them into bools or ints adds structure (ordering, arithmetic) that they do not have.

**Indirection.** Data enters in the form that its consumer reads, keyed by objects that the body already has. If a rule's only function is to convert one representation of a thing into another, one of the two representations is unjustified. Examples: renaming keys into a second vocabulary (a 2×2 tile position as its corner name); passing a flat correspondence through intermediate coordinates; storing an order as successor edges, which closure must expand before a comparison can read it. When the two sides differ in content, conversion is justified, as with a sparse set and its ranking (`Ordinal`).

**Performance.** The principled form is the right form regardless of performance.

## Invariance

The current task is one member of a family symmetric under ARC's transformations: rotations, mirrorings, recolorings, re-anchorings. The body is the part that stays the same across those variations. Each variation becomes a Consts value that the body parameterizes over. No two slots admit fills that contradict. Bodies specific to the current member are failures.

**Scope.** Invariance ranges over ARC's symmetry group: orientation, color, placement. It does not extend to the rule algebra. An OR fold is existence and an XOR fold is exact count: two concepts and two families, not one count-thresholded body with the threshold in Consts (dae9d2b5 vs 34b99a2b).

**Color.** Colors have identity and nothing else. Structure over colors (an ordering, a mapping, a partition) is task data, stored in Consts. Comparing by enum ordinal or iterating C0..C9 in the body adds structure that the task does not have.

**Orientation.** A task may privilege a direction, axis, or transformation. Without that, no choice is privileged. Position's four edge distances remove the corner origin. Dir, Axis, DiagDir, and D4 make orientation choices values, so a mirrored sibling needs a Consts edit, not a body restructure.

**Derived vs stored.** When the pairs exhibit a value directly, that value is task data, stored in Consts. A body derivation instead claims that the value depends on its source. That claim needs a witness: some pair varies the source and the value follows. A value that is the same in every pair has no witness. A derivation that reproduces it makes a claim that the data does not support (4522001f stores its 9×9 canvas; N·N of the 3×3 input would reproduce it). An unwitnessed derivation is allowed only as a case beside the data case, never as a replacement for it (3b4c2228). Setup gets no case, so it cannot include an unwitnessed derivation. Because the pairs witness a correspondence cell by cell, a frame built as a correspondence over input cells (007bbfb7) derives no number.

**Zero is absence.** In spatial data, the number 0 means no gap, no offset, no distance: the lack of structure. It is never task data. A body may write `0` directly.

**Closure.** A Consts slot can carry structure: a membership set whose rows are exactly a structural class (every cardinal, a D4 orbit) with no payload that varies across them. No sibling fills a proper subset. Which members fire decides the encoding:

- If every member fires, the class is structural. The body enumerates it (`dir_elem`, `diag_dir_elem`). Consts keys the datum by class (0ca9ddb6 stores `arm_paint` and `diag_paint`, one color per kind).
- If one member fires and another must not, a slot holds the member.
- If a task fires a peer class (cardinals against diagonals), it gets another body, not a refill (1f876c06, dbc1a6ce).
- If the values vary per row (d364b489's per-direction arm colors), the rows are data and the class is just the domain.

Closure determines encoding, not coverage: it removes no case. A membership set that some sibling refills is task data even when this task's fill coincides with a structural class (14754a24's plus footprint is the anchor plus every cardinal step; a T-completing sibling refills it, so its `shape` case stands beside the structural one).

**Underdetermined choices.** If every fill permits a body choice, that choice is not task data. A slot for it is unwitnessed. A literal hides it. The body enumerates its class and derives `out` per member, so the output is defined where the members agree (28a6681f settles water cell by cell; either end of the lateral axis may pour first, and the body runs both).

**Equivariance.** If and only if the choice is unobservable, a lib primitive may read specific Position slots internally: `f(apply(D, P)) = apply(D, f(P))` for every D in D4. Equivariant primitives are safe to parameterize from Consts. A non-equivariant primitive adds a hidden orientation to a body that is otherwise symmetric. A `T mod period` intile mapping is one, observable on non-divisible extents. The remedy is an explicit anchor parameter, or an equivariant encoding: 332efdb3 models its period-2 pattern with `divide_by_size` K=1 G=1 in place of mod.

## Coverage

A few train pairs underdetermine the family. Each model is a claim that the task is an instance of family F. Coverage is one model per plausible claim, encoded as cases of `Choice`. ARC training tasks are intended to teach core knowledge priors in pure form. Coverage shows which prior the task could be teaching. A record-typed Choice is the cross product of independent decision points (87ab05b8: three locate families × two fill-color claims).

**Data vs ops.** This is the main axis along which claims differ. Any relationship can be stored as Consts data (a table, claiming a lookup prior) or written as composed primitives (claiming a compositional prior). 3b4c2228 renders its count both ways: `$Tally` composes marks down a diagonal; `$Lookup` selects a stored grid. Data-leaning siblings vary the table. Ops-leaning siblings vary the parameters.

**Same model or different.** Two candidates are the same model iff both hold:

- same Consts shape — the free data that a sibling would refill. Derived or materialized helper relations do not count.
- same outputs for every input under every Consts value of that shape

Candidates that differ on either are different models. Each gets a case. Candidates that match on both are alt impls of one model. Consts-shape divergence distinguishes candidates that coincide on the current task but parameterize different families: 44f52bb0's `$Direct` (one sym set plus two grids) and `$GroupMatch` (a group→grid table) agree on every input, and their sibling families diverge. One shared Consts slot across two claims asserts that they are the same parameter. If some task fits both claims and fills them differently, it refutes that assertion: 87ab05b8 keeps `divisor`, `tile_dim`, `block_dim` separate, all 2, because a 6×6 sibling splits them into 2 and 3. When no such task exists, the parameter is the same and shares one slot: d23f8c26's `axis` is read by its equidistance case and its divide case alike, and any task that fits both pins them to the same value.

A shared slot also requires a shared form: both claims read the datum in the same vocabulary. When the consumers differ, each claim stores the datum in its consumer's form, in a per-case slot. A shared slot that a case must convert fails the Indirection test. 2013d3e2 stores the output's location per case: $Half's `out_tile` is the tile position that its divide produces; $Window's `corner` is the DiagDir that `corner_anchor` reads.

The criterion compares maps, not the sets of tasks that the models fit. A body can relabel its own coordinates, measuring from `opposite(D)` where another measures from `D`. It fits the same tasks at different Consts values, so the checklist counts it as a different model. That relabeled body adds no coverage and gets no case.

Divergence must also be valid to count. When every divergence of a claim from a sibling is ill-formed (the output has multiple values or is not total), the claim never fits a task that the sibling misses, at any fill of its Consts shape. The sibling subsumes it, and it gets no case (99fa7670's line fill: an unblocked ray diverges from the stepwise flow only by claiming two colors on one cell). Partiality alone is not subsumption: a model that fails on some inputs but validly diverges on others is still a rival. When a co-chosen decision pins an ops claim's inputs to stored data, that claim computes a function of Consts. Its tabulation is a fill of the data rival, so it gets no case (21897d95).

**Concept vs setup.** Cases are claims about the prior that the task teaches. Setup is structure that every candidate claim depends on: whichever selection rule 662c240a teaches, it reads the same stack of three tiles. Setup has variants of its own. That stack can be found by tile count, by tile size, or by squareness with no datum. The same-model test separates the three by Consts shape, but all three invoke one segmentation prior and differ only in which datum finds the stack. Together they get one case: the variant whose facts the body already reads (1190bc91), written in the corpus's settled form (2dee498d, f25ffba3). Coverage applies to the rival priors: a privileged reflection ($Shared) against symmetry-existence ($Asym). A same-model separation gets a case only when it separates priors, regardless of its decision point. A variant that depends on different input structure is a different reading and gets a case. A variant that finds the same structure another way remains a setup variant. If a solver introduces or improves a form, that solver settles it.

**A claim needs evidence.** A rival that reads the task differently gets a case. If no pair exercises a rival's added rules, slots, or comps, that rival gets no case. A claim with no relational form gets no case. When a claim's encoding depends on arithmetic and the lib addition protocol closes the primitive, that claim has no relational form (`proposals/MinHops.md`). A mapping table needs multiple entries exercised (44f52bb0's groups both fire; a one-entry ring table over a plain border sits unexercised). When some pair contradicts an identification rule, that rule is out (87ab05b8 train 0 contradicts count-based marker identification: every noise color is a singleton). Data-leaning Consts must be refillable from the train pairs and test inputs. The test outputs are held out. A test key absent from the train-exhibited entries rules out the table claim (1fad071e: test count 3 over train's {2, 4} rules out its lookup render; 3b4c2228's test counts stay inside train's set, so its table stands). The correct output at that unseen key is evidence that the prior is compositional.
