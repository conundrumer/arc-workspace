<!-- When editing this doc:
- Write in the indicative mood.
- Avoid justifications, unless there is necessary reason.
- Avoid contrastive structures, unless the alternative needs to be addressed.
- Prefer nested lists:
    - When a sentence states two or more parallel parts, write them as a nested list, one item each.
    - An example or an instance of a rule is a sub-item under it.
- A citation points a reader at a worked application of the rule it sits under. A task is cited when its solver's file shows the application without the session that built it, its gloss says what the rule's text does not, and no citation under that rule shows the same application. A task the rule is still open on, or whose solver owes a case under the rule, is not cited; its review line carries the point.
- A cited task is a bare id. A gloss that states the task's facts in the rule's terms, without the task's internal vocabulary, goes in a comment beside the id.
- A citation of a draft solver waits at the citation's place in a comment, and the solver's approval turns it into the citation.
- A rule's formal statement goes on a `+` line under the rule. The first `+` line under a definition starts with the term's symbol, and a symbol is declared on a `+` line under the definition or rule that first uses it. -->

# Principles

The goal is for a solver to express a task in a way that matches a person's understanding as closely as possible.

The corpus aims to extract as much as possible from the tasks. The relevant part of a person's understanding is how they think the task could vary.

The corpus supports the synthesis of solver programs.

## Definitions

### The solver's parts

- **parameter**: a relation whose facts come from the task rather than from a rule.
- **derived data**: a relation derived by a rule, including a rule inside `Params`.
    - Derived data is not a parameter.
- **parameter value**: the facts that a task gives a parameter.
- **parameterization**: the parameters together with the values allowed for each one.
    + Θ = ∏ᵢ Θᵢ
        + Θᵢ: the values allowed for parameter i
    - Every combination of allowed values in the product is an assignment.
- **assignment**: one value chosen for every parameter.
- **program**: the rules that derive `out` from `in` and the parameters.
- **lookup table**: a parameter that maps keys from the input to entries that the program uses.

### Models and tasks

- **model**: the function that maps an assignment and an input grid to an output grid.
    + M : Θ × G ⇀ G
        + G: the set of grids
    - A model is defined at an assignment and input when `out` is exactly one total grid. It is undefined there otherwise.
- **evidence**: a task's train pairs and test inputs.
    + D(T) = (train(T), test_in(T))
- **solver**: one or more models of a task.
    - For each model, the solver stores an assignment for each evidence.
        + S_M = (M, stored_M)
- **determination**: the rules that derive a stored value from the evidence.
    - Test outputs are held out, so two tasks with identical evidence receive the same stored assignment.
        + D(T) = D(T′) ⇒ stored_M(D(T)) = stored_M(D(T′))
- **fit**: a model fits a task at an assignment when it reproduces every pair in the task, including the test pairs.
    + M(θ) ⊨ T ⇔ ∀(x, y) ∈ pairs(T). M(θ, x) = y
        + pairs(T) = train(T) ⧺ zip(test_in(T), test_out(T))
- **model family**: all tasks that a model fits under some assignment.
    + fam(M) = {T | ∃θ ∈ Θ. M(θ) ⊨ T}
- **sibling task**: another task in the family of this task's model.
- **peer model**: another model that fits the same task.
- **family invariant**: a value shared by every task in the family.
- **hypothesis**: the assertion that a task belongs to a model's family.
- **case**: one model in the solver, together with its hypothesis.
- **choice point**: a property of the task that the pairs do not determine.
    - **branch**: one possible answer to a choice point.
        - Each case answers every choice point by taking one branch.
            <!-- draft: 447fd412 — a scaled copy of a marked drawing stamps at each block; what the stamp carries and which cells of a block's box it reaches combine, so each is its own point. -->
        - A branch's rules are the rules that the cases with that branch share and that the other cases lack.
        - A branch's model is the model of a case with that branch, with every other choice point fixed to the branch used by the intended case.
- **open parameter**: a parameter whose value the pairs leave unresolved.
    - **open values**: the values that the pairs leave unresolved.
    - A sibling task containing an input on which the open values disagree fixes the parameter to one of those values.
    - An undetermined property is an open parameter when its possible answers are values of one parameter. It is a choice point when each possible answer is a model represented by a case.
- **generator**: the process that produced the task's pairs and would produce other tasks.
    - **generator's rules**: the rules the generator uses to produce each output from its input.
- **invariant of the inputs**: a regularity satisfied by every input in the evidence.
    - An invariant of the inputs is an estimate of a generator constraint.
- **concept**: the reading of the task that a person forms.
    - **concept statement**: the concept as expressed by the solver.
        - The concept statement estimates the generator's rules.
- **intended case**: the case whose model the concept statement describes.
    - **intended branch**: at a choice point, the branch used by the intended case.

### Structures and the lib

- **parse**: the structures that a model finds in the input.
- **setup**: the parse shared by every case, together with the rules that encode it.
- **draft**: a solver that is not yet approved. Its header says `draft`.
- **corpus**: the approved solvers. A solver is in the corpus or is a draft.
- **precedent**: the encoding that the corpus already uses for a structure in the setup.
    - The solver that introduces or improves that encoding establishes the precedent.
    - A precedent covers how the structure is found and encoded. It does not cover the tests performed inside that encoding.
- **orientation type**: `Dir`, `Axis`, `DiagDir`, `DiagAxis`, `D4`, `C4`, `Sense`, or `Sym`.
    - Its values are exactly the values enumerated by the lib.
- **lib unit**: a comp in the lib, as named by `lib.dl`.
- **lib primitive**: a relation declared by the lib outside a unit.
- **equivariant lib primitive**: a lib primitive whose output transforms in the same way as its input under every element of D4.

### Equivalent models

- Two models over the same parameterization are equivalent when they give the same result for every assignment and every input.
    + Equivalent(A, B) ⇔ ∀θ ∈ Θ. ∀x ∈ G. A(θ, x) = B(θ, x)
- An **isomorphism** between two parameterizations pairs their assignments bijectively.
    + Iso(e, Θ₁, Θ₂) ⇔ (∀θ ∈ Θ₁. e⁻¹(e(θ)) = θ) ∧ (∀φ ∈ Θ₂. e(e⁻¹(φ)) = φ)
    - Models over those parameterizations are equivalent when every pair of matched assignments gives the same result for every input.
        + EquivalentAcross(A, B) ⇔ ∃e. Iso(e, Θ₁, Θ₂) ∧ ∀θ ∈ Θ₁. ∀x ∈ G. A(θ, x) = B(e(θ), x)
- Agreement on every input in the current task does not establish equivalence between models over different parameterizations.
    - 44f52bb0 <!-- one model stores one symmetry group and two output grids. The other stores two group-to-output entries. Both models agree on every input of this task. -->
- Equivalent parameters and redundant values decide which relations count as a single parameter.
- A **divergence witness** is an input on which two models produce different results at some assignment.
    - A divergence witness refutes equivalence.
    - For models over different parameterizations, equivalence is refuted by a witness under every possible isomorphism.
        + (∀e. Iso(e, Θ₁, Θ₂) ⇒ ∃θ ∈ Θ₁. ∃x ∈ G. A(θ, x) ≠ B(e(θ), x)) ⇒ ¬EquivalentAcross(A, B)
    - An output identical to the input is still defined, so a divergence at such an output is valid.
        - 41e4d17e <!-- on a solid block, the model based on enclosed regions finds none and returns the input. The model based on objects finds the block and casts from it. -->

## Fidelity

The program encodes the task's concept independently of how the data or the medium represents that concept.

### Relational form

ARC concepts are relations among cells, regions, and properties. The program encodes them as relations.

### ARC types

The program works in the task's own types: colors and orientation types.

### Numbers

- **Grounding.** Every number in a solver counts concrete things that are present in the task.
    - A distance counts the cells between something and an edge.
    - A size counts the members of a set.
    - A rank counts the members that come before one item in an order.
- Arithmetic in a rule usually represents a relational operation. The program writes that operation directly.
    - A wraparound shift is a walk around a cycle.
- **Zero is absence.** A `0` counts nothing that is present, so it represents an absence.
    - In a spatial setting, `0` represents the absence of a gap, offset, or distance.
    - A program is allowed to use `0` directly.

### Lib units

Whether the task has a lib unit's concept determines whether the program uses that unit.

- The part of the unit's computation that the program needs does not determine whether the program uses the unit.
- If the concept is absent, the program writes the needed step using lib primitives or a local rule.
- If the concept is present, the program instantiates the unit and uses any exposed output it needs.
    - The other outputs can remain unused.

### Indirection

A parameter has the form required by the rule or component that uses it. The parameter is keyed by objects the program already has.

A rule used only to translate one representation into another is evidence that one of those representations is unjustified.

- Naming a position in a 2×2 tile by its corner creates a second name for the same key.
- Routing a flat correspondence through intermediate coordinates introduces another representation.
- Storing an order as successor edges requires closure to expand it before a comparison.
- A stored map from a tile's places to the sections they fill uses each frame cell as its own key.
- Storing an orientation as an `Axis`, `Sense`, or `Sym` requires conversion to the `D4` used by the rule.
    - 8ee62060 <!-- the parameter stores the D4 elements that fit, and the program applies them directly to block positions. -->

Conversion is justified when its two sides differ in content.

- A sparse set differs in content from its `Ordinal` ranking.
- A cell set differs in content from its `Canon` class id when the program treats the class as a single thing.

### Performance

The principled form is the right form regardless of performance. A form chosen for speed is an artifact of the medium.

## Invariance

ARC's symmetry group is generated by the elements of D4 together with color permutations.

The model is equivariant. If its assignment and input are transformed together, its output is transformed in the same way.

+ Equivariant(M) ⇔ ∀γ ∈ Γ. ∀θ ∈ Θ. ∀x ∈ G. M(γ · θ, γ · x) = γ · M(θ, x)
    + Γ: ARC's symmetry group
    + γ · M(θ, x): the transformed result, or undefined when M(θ, x) is undefined

- The program is the part of the solver that stays unchanged under the group.
- What a group element changes becomes a parameter. Orientations and colors are examples.
- A program literal belonging to an ARC type breaks equivariance when the group transforms that value.

### Invariance scope

Invariance does not range over the ways rules combine their inputs.

### Orientation

Some tasks distinguish a particular direction, axis, or transformation. When a task does not distinguish an orientation, neither does the program.

- The orientation types represent each possible orientation choice as a value. A mirrored sibling task therefore requires a parameter edit rather than a change to the program.
- **Orientation per axis.** A model whose rules differ between axes does not choose an orientation when one parameter names the axis on which the rules are keyed.

### Color

Colors have identity and no other properties.

### Equivariant lib primitives

- An equivariant lib primitive preserves program equivariance when its arguments come from parameters.
- A non-equivariant lib primitive introduces a hidden orientation into an otherwise symmetric program.
    - Mapping within a tile by distance modulo a period creates a hidden orientation. It is observable unless the extent less one is a multiple of the period.
    - An explicit anchor parameter or an equivariant encoding removes that hidden orientation.
        - 332efdb3 <!-- the motif case seats a period-2 motif at every corner of the grid, so no corner is singled out. -->

### Stored or derived

- A value shown directly by the pairs is task data and is stored as a parameter.
    - Structure over colors is task data and is stored as a parameter.
        - an ordering
        - a mapping
        - a partition
    - A number that a sibling task reassigns is a parameter.
- Deriving a value asserts that the value depends on the source from which it is derived.
    - **Two parameterizations.** Storing a value and deriving that value produce two different parameterizations.
        - On an input where the derivation gives a value other than the stored one, the two models diverge, so they are not equivalent.
        - 3b4c2228 <!-- one model renders a count as marks down a diagonal. Another looks up a stored grid for the count. Every train and test count is a key of the table, so the models never differ on a pair. -->
- **Redundant value.** A value already fixed by another parameter is derived data rather than a second parameter.

### Family invariants

A value shared by every task in a family is a family invariant rather than task data, so it is not a parameter.

The values of an orientation type that the task uses determine the encoding.

- **Every value.**
    - A membership set is a family invariant when:
        - it contains every value of an orientation type
        - no associated data varies by value
        - no sibling task narrows the set
    - The program enumerates every value of the orientation type, and the parameters are per orientation type rather than per value.
        - 0ca9ddb6 <!-- one marker color paints cardinal arms, and another paints diagonal arms. The program enumerates every direction of each type, and each type has its own arm color parameter, keyed by marker color. -->
- **One member.** If one member is used and another must not be used, a parameter stores the chosen member.
- **Another orientation type.** Switching to another orientation type requires another program rather than a reassignment. Switching between cardinal and diagonal directions is one example.
    - a9f96cdd <!-- one marker paints one cell in each diagonal direction. A separate stored color applies to each direction. -->
    - d364b489 <!-- each marker paints one cell in each cardinal direction. A separate stored color applies to each direction. -->
- **Payload.** When values vary from member to member, the rows are data and the orientation type is their domain.
    - d364b489 <!-- each marker paints the neighbor on each of its four sides, with clipping at the grid edge. Each direction has its own color. -->
- **Reassigned set.** A membership set that some sibling task narrows is task data, even when it contains every value of the orientation type in the current task.
    - 14754a24 <!-- each incomplete plus is completed from a footprint containing a center and its four neighbors. A sibling that completed a T-shaped footprint would store a proper subset of that footprint. -->

### Underdetermined choice

The solver records every open value of an open parameter.

- The program runs with every open value of the parameter.
    - The output is defined for every input on which all open values produce the same output.
    - 28a6681f <!-- water settles under gravity one cell at a time. Along a line across gravity, either end can pour first, and the program runs both orders. -->
- On an input that resolves the choice, the output is multi-valued.
    - On a task that contains such a pair, the model fails Fit at the open values.

### Equivalent parameters

- **One parameter.** A parameter shared between two cases asserts that one value serves both cases in every task that fits both.
    - Two parameters are equivalent when one value serves both in every task that fits both cases.
    - Equivalent parameters are one parameter.
    - d23f8c26 <!-- one column of an odd-width grid is kept. It is the center line on a stored axis in one case and the gap of a two-way divide on that axis in another. Any task that fits both uses one axis value. -->
    - 5d2a5c43 <!-- `gap` supplies the stored tile layout in one case, and `divide_gap` supplies the divide rules in another. Both relations state the separator's width. A sibling that widens the separator reassigns them together. -->
- **Distinct parameters.** Two parameters are distinct when some task fits both cases and the parameters have no common value for that task.
    - Each case then has its own parameter.
    - 87ab05b8 <!-- three cases locate the region by a part count or a size. All values are 2 in this task, while a 6×6 sibling sets the part count to 3 and keeps the sizes at 2. -->
- **Shared form.** A shared parameter has one form, so both cases read it using the same vocabulary.
    - When the consumers require different forms, each case has its own parameter in the form read by its consumer.
    - 2013d3e2 <!-- the output is a corner region of the non-background bounding box. The quadrant case stores it as a tile position, and the fixed-window case stores it as a corner. -->

## Cases

Some pairs have a second accepted output. Such a pair yields two tasks, one for each output. A model fits the task when it fits either of them.

- A peer model that produces the second accepted output under some assignment is a separate case when it passes the case tests below.
- **Tiebreak** is content that the task leaves free.
    - When the second accepted output differs from the first only in a tiebreak, both outputs belong to one model and there is no additional case.
    - The case tests do not apply to those resolutions.

**No other removal.** A case is included exactly when it passes all of these tests:

- **Fit.** The model fits the task at its stored assignment.
    + Fit(S_M, T) ⇔ M(stored_M(D(T))) ⊨ T
    - **Unseen key.** When a test uses a key that no train pair contains, a lookup table fails Fit.
        - 1fad071e <!-- the test count is 3, and the train counts are 2 and 4. The table is therefore ruled out. -->
        - 3b4c2228 <!-- every test count occurs among the train counts, so the table has no unseen key and passes this test. -->
    - Fit considers only the pairs. Being undefined on another input does not prevent a model from fitting.
- **Fidelity.** The model has an encoding allowed by the Fidelity rules.
- **Equivalence.** The model is not equivalent to the model of another case.

### Deviation

Each branch has three counts over its rules. The branch and the generator together determine each count. The evidence, the branch's divergence witness, and the concept statement provide estimates of the counts.

The intended branch has `0` for all three estimates. The branch has no divergence from itself, and the concept statement includes its rules.

- **relaxed**: the minimum number of generator constraints whose relaxation lets the generator produce an input on which this branch and the intended branch disagree.
    - **relaxation witness**: that input.
    - **relaxed estimate**: for any other branch, the minimum number of invariants of the inputs broken by a divergence witness between the branch and the intended branch.
- **added**: the number of rules in the branch that are absent from the generator's rules.
    - **added estimate**: the number of rules in the branch that are absent from the concept statement.
- **contradicted**: the number of rules in the branch whose output on the relaxation witness differs from the generator's output there.
    - **contradicted estimate**: the number of rules in the branch whose outcome the concept statement rejects on a divergence witness that minimizes the number of broken invariants of the inputs.
        - An outcome that the concept statement does not address is not rejected.

## Corpus consistency

### Setup priority

The priorities for choosing a setup are, in order:

1. Fidelity.
2. Reuse of facts and lib instances already available to the program.
    - 1190bc91 <!-- both cases use one connected-component instance for marker areas. The instance reuses the shared sequence and rays, and each case supplies a different set of area cells. -->
3. The precedent for the structure.
    - 2dee498d <!-- the input holds three identical panels along a stored axis. The setup divides them with `divide_slab` from that axis and a stored panel count, and one panel is the output. -->
    - f25ffba3 <!-- the input holds a data slab along the axis of a stored direction. One case divides the input with `divide_slab` from that axis and a stored panel count, as 2dee498d does, and another case divides it from a stored panel size. -->
