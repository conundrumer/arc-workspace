<!-- When editing this doc:
- Write in the indicative mood.
- Avoid justifications, unless there is necessary reason.
- Avoid contrastive structures, unless the alternative needs to be addressed.
- A cited task is a bare id. A gloss that states the task's facts in the rule's terms, without the task's internal vocabulary, goes in a comment beside the id. -->

# Principles

The theory of tasks and their solvers, and the design norms for the best model of a task.

The goal is a corpus that supports program synthesis of solvers. Across the corpus, reusable primitives and fragments are drawn from the shared parts of solvers.

## Definitions <!-- deferred -->

- **body** — the rules that derive `out` from `in` and Consts. In synthesis terms, the *program* that the parameters complete.
- **Consts** — the data of a solver. In modeling terms, the *parameters*.
- **slot** — a Consts relation that holds facts. A Consts relation derived by a rule is not a slot. One *parameter*.
- **fill** — the facts a task gives a slot. A parameter's *value*.
- **Consts shape** — the slots with their schemas. The *parameterization*.
- **Fit** — the rules that derive a slot's fill from the examples. The solvers of siblings share the body and the Fit.
- **model** — a Consts shape with the map from fill and input to output that a body computes over it.
- **family** — the tasks a model fits.
- **sibling** — another task in the family.
- **rival model** — of a model: another model that fits the task.
- **setup variant** — another encoding of the same setup: it finds the same structure with a different Consts shape. A *reparameterization* of the setup.
- **settled form** — the encoding that the corpus already uses for a setup structure. A *precedent*.
- **prior** — a core knowledge prior that ARC training tasks teach. The Prior terms of `concepts.md` name them. A case claims which priors the task teaches. Several models claim the same priors.

## Fidelity

The body encodes the concept of the task, apart from how the data or the medium encodes it.

### Relational form

ARC concepts are relations between cells, regions, and properties. The body encodes them as relations.

- Arithmetic in a rule usually represents a relational operation: a wraparound shift is a walk along a cycle. Arithmetic that seems necessary usually shows that a lib primitive is missing, and the lib addition protocol decides.

### ARC values

The body works in the task's own values: colors, directions, axes, D4 elements. Projecting them into bools or ints adds structure (ordering, arithmetic) that they do not have.

### Lib units

If the task does not have a lib unit's concept, the solver does not use that unit.

- Needing part of a unit's computation is not a reason to use it. A body that needs only one step of a unit writes that step with primitives or a local rule.

### Indirection

Data enters in the form that its consumer reads, keyed by objects that the body already has. If a rule's only function is to convert one representation of a thing into another, one of the two representations is unjustified.

- Conversions of that kind:
    - a key renamed into a second vocabulary, as a 2×2 tile position named by its corner
    - a flat correspondence routed through intermediate coordinates
    - an order stored as successor edges, which closure expands before a comparison reads it
- When the two sides differ in content, conversion is justified, as with a sparse set and its ranking (`Ordinal`).

### Performance

The principled form is the right form regardless of performance. A form chosen for speed is an artifact of the medium.

## Invariance

Generalization happens at the family level. The current task is one member of a family symmetric under ARC's transformations: rotations, mirrorings, recolorings, re-anchorings.

- The body is the part that stays the same under those transformations.
- What a transformation changes, an orientation, a color, a placement, becomes a Consts value that the body parameterizes over.
- No two slots admit fills that contradict.
- Bodies specific to the current member are failures.

### Invariance scope

Invariance ranges over ARC's symmetry group: orientation, color, placement. It does not extend to how the rules combine their inputs.

- An OR fold is existence and an XOR fold is exact count: two concepts and two families, not one count-thresholded body with the threshold in Consts (dae9d2b5 vs 34b99a2b).

### Color

Colors have identity and nothing else.

- Structure over colors (an ordering, a mapping, a partition) is task data, stored in Consts.
- Comparing by enum ordinal or iterating C0..C9 in the body adds structure that the task does not have.

### Orientation

A task may single out a direction, axis, or transformation. Without that, no choice is singled out.

- Position's four edge distances remove the corner origin.
- Dir, Axis, DiagDir, and D4 make each orientation choice a value, so a mirrored sibling needs a Consts edit, not a body restructure.

### Equivariance

A lib primitive is equivariant when `f(apply(D, P)) = apply(D, f(P))` for every D in D4. A lib primitive reads specific Position fields internally if and only if it is equivariant.

- Equivariant primitives are safe to parameterize from Consts.
- A non-equivariant primitive adds a hidden orientation to a body that is otherwise symmetric. An explicit anchor parameter, or an equivariant encoding, removes that hidden orientation.
    - A `T mod period` intile mapping is one such primitive, observable on non-divisible extents.
        - 332efdb3 <!-- a period-2 pattern; one case models it with `divide_by_size` K=1 G=1 in place of mod. -->

### Derived vs stored

When the pairs exhibit a value directly, that value is task data, stored in Consts. A body derivation instead claims that the value depends on its source.

- A witness is an input on which two candidates, models or fills of one model, produce different outputs. <!-- In synthesis terms, a *distinguishing input*. --> For that claim, it is a pair on which the derivation and the stored slot's fill give different values.
    - Against a stored constant, the witness is a pair whose source differs from the other pairs' and whose value follows it, so a value that is the same in every pair has no witness.
        - 4522001f <!-- the input is 3×3 and the output 9×9 in every pair; the output extent is stored, and the square of the input extent would reproduce it. -->
    - Against a stored table, the witness is a pair whose key lies outside the train entries.
- **Unwitnessed derivation.** An unwitnessed derivation stands only as a case beside the data case.
    - 3b4c2228 <!-- the count renders as marks down a diagonal, or from a stored grid per count; every train and test count is a key of that table, so the two never differ on a pair. -->
- **Setup derivation.** Setup gets no case, so it cannot include an unwitnessed derivation.
- **Correspondence frame.** Because the pairs witness a correspondence cell by cell, a frame built as a correspondence over input cells (007bbfb7) derives no number.

### Zero is absence

In spatial data, the number 0 means no gap, no offset, no distance: the lack of structure. It is never task data. A body may write `0` directly.

### Closure

A Consts slot can carry structure: a membership set whose rows are exactly a structural class (every cardinal, a D4 orbit) with no payload that varies across them. No sibling fills a proper subset. Which members the task uses decides the encoding:

- **Every member.** If the task uses every member, the class is structural. The body enumerates it (`dir_elem`, `diag_dir_elem`). Consts keys the datum by class.
    - 0ca9ddb6 <!-- a marked dot gets an arm in every cardinal direction or in every diagonal one, and each kind of arm has its own slot, keyed by the mark's color. -->
- **One member.** If the task uses one member and must not use another, a slot holds the member.
- **Peer class.** If a task uses a peer class (cardinals against diagonals), it gets another body, not a refill (1f876c06, dbc1a6ce).
- **Payload.** If the values vary per row, the rows are data and the class is the domain.
    - d364b489 <!-- each marker paints the neighbor on each of its four sides, clipped at the grid edge, and each direction has its own color. -->

Closure decides the encoding and removes no case.

- **Refilled set.** A membership set that some sibling refills is task data even when this task's fill coincides with a structural class.
    - 14754a24 <!-- each incomplete plus is completed from a footprint of a center and its four neighbors; a sibling that completed a T would refill the footprint, so the footprint's data case stands beside its structural case. -->

### Underdetermined choice

If every fill permits a body choice, that choice is not task data.

- A slot for it is unwitnessed. A literal hides it.
- The body enumerates its class and derives `out` per member, so the output is defined where the members agree.
    - 28a6681f <!-- water settles under gravity one cell at a time; along a line across gravity, either end may pour first, and the body runs both orders. -->

## Coverage

A few train pairs underdetermine the family. Coverage is one case per model that the rules of this section admit.

- A model fits a task when some fill of its shape produces the task's outputs from its inputs.
- ARC training tasks are intended to teach core knowledge priors in pure form. Coverage shows which prior the task could be teaching.
- A decision point is a property of the task that the pairs do not determine. <!-- In experimental-design terms, a *factor*, and its answers are its *levels*. -->
- A claim is the assertion that the task is in a model's family. It decomposes by decision point into one answer per point, and each answer is itself a claim. <!-- In scientific terms, a *hypothesis*. -->
- A case is the encoding of one model in the solver, as a value of `Choice`.
    - A solver with one case has no `Choice`.
    - A record-typed `Choice` holds one field per decision point, and is the cross product of independent decision points.
        - 87ab05b8 <!-- one marked cell among noise, and the output fills the 2×2 region that holds it; three ways to locate the region cross two sources of the fill color. -->

### Same model

Two candidates are the same model iff both hold:

- same Consts shape — the free data that a sibling would refill. Derived or materialized helper relations do not count.
- same outputs for every input under every fill of that shape

The test decides:

- Candidates that differ on either are different models.
- Candidates that match on both are alt impls of one model.
- Consts-shape divergence distinguishes candidates that coincide on the current task but parameterize different families.
    - 44f52bb0 <!-- the output is one of two stored grids, by whether the input has a stored symmetry, or, from a table of groups, the stored grid of the largest group that leaves the input invariant; the two agree on every input, the first is a two-entry fill of the second, and they claim different priors. -->

### Data vs ops

Data against ops is the main way in which claims differ. Any relationship can be stored as Consts data (a table, claiming a lookup prior) or written as composed primitives (claiming a compositional prior). The two claim different priors, and both get cases.

- Data-leaning siblings vary the table. Ops-leaning siblings vary the parameters.
- 3b4c2228 <!-- the count renders both ways, as marks composed down a diagonal and as a stored grid per count. -->

### Subsumption

Divergence must be valid to count.

- **Ill-formed divergence.** When every divergence of a claim from a rival is ill-formed (the output has multiple values or is not total), the claim never fits a task that the rival misses, at any fill of its Consts shape. The rival subsumes it, and it gets no case.
    - 99fa7670 <!-- each colored dot fills its line to one edge and then along that edge, where the next dot's fill occludes it; an unblocked ray diverges from that stepwise fill only by claiming two colors on one cell. -->
- **Partiality.** Partiality alone is not subsumption: a model that fails on some inputs but validly diverges on others is still a rival.
- **Tabulation.** When another decision in the same case pins an ops claim's inputs to stored data, that claim computes a function of Consts. Its tabulation is a fill of the data rival, so it gets no case (21897d95).

### Concept vs setup

Cases are claims about the prior that the task teaches.

- A reading is which structures a model finds in the input grid. Models that find different structures are different readings. <!-- In vision terms, a *parse* of the grid. -->
- Setup is the reading that every case shares, with the body rules that encode it.
    - 662c240a <!-- square tiles form a stack along an axis, and the output is the one tile that lacks the symmetry the others share; every case reads the same stack. -->
- **Setup variants.** A setup has variants, and together they get one case: the variant whose facts the body already reads (1190bc91), written in the corpus's settled form (2dee498d, f25ffba3).
    - The solver that introduces or improves a structure's encoding settles its form.
    - 662c240a <!-- the stack can be found by tile count, as the solver does, by tile size, or by squareness with no datum; the same-model test separates the three, since count and size give different outputs at one fill on other extents and squareness has no slot, but all three claim one segmentation prior and differ only in which datum finds the stack. -->
- **Rival priors.** The cases go to the rival priors. A same-model separation gets a case only when it separates priors, regardless of its decision point.
    - 662c240a <!-- a stored symmetry, with the output the tile it fails on, against the existence of any symmetry. -->
- **Different reading.** A rival that reads the task differently gets a case.
    - A variant that depends on different input structure is a different reading and gets a case.
    - A variant that finds the same structure another way remains a setup variant.

### Evidence

- **Exercised.** If no pair exercises a rival's added rules, slots, or comps, that rival gets no case.
    - A pair exercises a part of the solver when that pair's output depends on it.
- **No relational form.** A claim with no relational form gets no case. When a claim's encoding depends on arithmetic and the lib addition protocol closes the primitive, that claim has no relational form (`proposals/MinHops.md`).
- **Table entries.** A mapping table needs multiple entries exercised. A one-entry ring table over a plain border is unexercised.
    - 44f52bb0 <!-- both symmetry classes occur in the pairs. -->
- **Contradicted rule.** When some pair contradicts an identification rule, that rule is excluded.
    - 87ab05b8 <!-- train pair 0 contradicts count-based marker identification, since every noise color is a singleton. -->
- **Refillable.** Data-leaning Consts must be refillable from the train pairs and test inputs. The test outputs are held out.
    - **Unseen key.** A test key absent from the train-exhibited entries rules out the table claim.
        - 1fad071e <!-- the test count is 3 and the train counts are {2, 4}, so its table is ruled out. -->
        - 3b4c2228 <!-- the test counts are in the train set, so its table stands. -->
    - The correct output at that unseen key is evidence that the prior is compositional.

### Shared slots

One shared Consts slot across two claims asserts that they are the same parameter.

- **Separate slots.** If some task fits both claims and fills them differently, it refutes that assertion.
    - 87ab05b8 <!-- each of the three ways to locate the region reads its own slot, a part count or a size, all 2 in this task, because a 6×6 sibling sets the part count to 3 and the sizes to 2. -->
- **One slot.** When no such task exists, the parameter is the same and shares one slot.
    - d23f8c26 <!-- one column of an odd-width grid is kept, as the center line on a stored axis or as the gap of a two-way divide on that axis, and any task that fits both pins the axis to the same value. -->

A shared slot also requires a shared form: both claims read the datum in the same vocabulary.

- When the consumers differ, each claim stores the datum in its consumer's form, in a per-case slot.
    - 2013d3e2 <!-- the output is a corner region of the bounding box of the non-background cells, stored as a tile position for the case that divides the box into quadrants and as a corner for the case that places a fixed window there. -->
- A shared slot that a case must convert fails the Indirection test.
