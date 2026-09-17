<!-- When editing this doc:
- The corpus supports the synthesis of solver programs.
- Judge a principle by whether it is consistent, useful, and general.
- Write in the indicative mood.
- Avoid justifications, unless there is necessary reason.
- Avoid contrastive structures, unless the alternative needs to be addressed.
- Prefer nested lists:
    - When a sentence states two or more parallel parts, write them as a nested list, one item each.
    - An example or an instance of a rule is a sub-item under it.
- A citation points a reader at a worked application of the rule it is under. A task is cited when its solver's file shows the application without the session that built it, its gloss says what the rule's text does not, and no citation under that rule shows the same application. A task the rule is still open on, or whose solver requires a case under the rule, is not cited; its review line states it.
- A cited task is a bare id. A gloss that states the task's facts in the rule's terms, without the task's internal vocabulary, goes in a comment beside the id.
- A draft solver is listed beside the rule as `draft: <id> — <gloss>` in a comment, and approval replaces that comment with the citation.
- A rule's formal statement goes on a `+` line under the rule. The first `+` line under a definition starts with the term's symbol, and a symbol is declared on a `+` line under the definition or rule that first uses it. -->

# Principles

The goal is for a solver to express a task in a way that matches a person's understanding as closely as possible, and for the corpus to extract as much as possible from the tasks.

The relevant part of a person's understanding is how they think the task could vary.

## Definitions

### The solver's parts

- **parameter**: a relation whose facts come from the task rather than from a clause.
- **derived data**: a relation derived by a clause, including a clause inside `Params`.
    <!-- - Derived data is not a parameter. -->
- **parameter value**: the facts that a task gives a parameter.
- **parameterization**: the parameters together with the values allowed for each one.
    + Θ = ∏ᵢ Θᵢ
        + Θᵢ: the values allowed for parameter i
        + θ ∈ Θ: one combination of allowed values, an assignment
- **assignment**: one choice of value for each parameter.
- **program**: the clauses that derive `out` from `in` and the parameters.
- **lookup table**: a parameter that maps keys from the input to entries that the program uses.

### Models and tasks

- **model**: the function that gives the output grids for an assignment and an input grid.
    + M : Θ × G → 𝒫(G)
        + G: the set of grids
    - A model is defined at an assignment and input when its output is nonempty and contains only total grids.
- **evidence**: a task's train pairs and test inputs.
    + D(T) = (train(T), test_in(T))
- **solver**: one or more models of a task.
    - For each model, the solver stores an assignment determined by the evidence.
        + S_M = (M, stored_M)
- **determination**: the clauses that derive a stored value from the evidence.
    - Test outputs are held out, so two tasks with identical evidence receive the same stored assignment.
        + D(T) = D(T′) ⇒ stored_M(D(T)) = stored_M(D(T′))
- **tiebreak**: content that the task leaves free.
- **candidate**: a set of a pair's accepted outputs that differ only in a tiebreak.
    - Outputs in different candidates differ by more than a tiebreak.
    - A pair has at most two candidates.
- **split task**: a task formed by choosing one candidate at each pair that has two.
    - Each such pair in the resulting task accepts only the chosen candidate.
    + alts(T): the set of split tasks of T
    <!-- - A task with one candidate at every pair is its own only split task.
        + alts(T) = {T} -->
- **fit**: a model fits a split task at an assignment when its output on each pair's input is that pair's candidate, including for the test pairs.
    + M(θ) ⊨ T ⇔ ∀(x, Y) ∈ pairs(T). M(θ, x) = Y
        + pairs(T) = train(T) ⧺ zip(test_in(T), test_out(T))
    - A model fits a task when it fits one of that task's split tasks.
- **model family**: all tasks that a model fits under some assignment.
    + fam(M) = {T | ∃T′ ∈ alts(T). ∃θ ∈ Θ. M(θ) ⊨ T′}
- **sibling task**: another task in the family of this task's model.
- **peer model**: another model whose family contains this task.
- **family invariant**: a value shared by every task in the family.
- **hypothesis**: the assertion that a task belongs to a model's family.
- **case**: one model in the solver, together with its hypothesis.
    - A case's model reads its output grids from `out` at that case, one grid per tiebreak resolution.
- **choice point**: an undetermined property whose possible answers are models represented by cases.
    - **branch**: one possible answer to a choice point.
        - The **concept branch** at a choice point is the branch taken by the concept case.
        - Each case answers every choice point by taking one branch.
            <!-- draft: 447fd412 — a scaled copy of a marked drawing stamps at each block; the stamp's content and which cells of a block's box it reaches combine, so each is its own point. -->
        - A branch's clauses are the clauses shared by its cases and absent from the other cases.
        - A branch's model is the model of a case with that branch, with every other choice point fixed to its concept branch.
- **open parameter**: a parameter whose value the pairs leave unresolved.
    - **open values**: two or more parameter values that the pairs leave unresolved.
    - A sibling task containing an input on which the open values disagree fixes the parameter to one of those values.
    - An undetermined property is an open parameter when its possible answers are values of one parameter.
- **generator**: the process that produced the task's pairs and would produce other tasks.
- **invariant of the inputs**: a regularity satisfied by every input in the evidence.
    - An invariant of the inputs is an estimate of a generator constraint.
- **concept**: the understanding of the task that a person forms.
    - **concept statement**: the concept as expressed by the solver.
    - **concept rule**: one rule in the concept statement.
- **concept case**: the case whose model the concept statement describes.

### Structures and the lib

- **parse**: the structures that a model finds in the input.
- **setup**: the parse shared by every case, together with the clauses that encode it.
- **draft**: a solver that is not yet approved. Its header says `draft`.
- **corpus**: the approved solvers.
- **precedent**: the encoding that the corpus already uses for a structure in the setup.
    - The solver that introduces or improves that encoding establishes the precedent.
    - A precedent covers how the structure is found and encoded. It does not cover the tests performed inside that encoding.
- **orientation type**: a type that meets each condition:
    - The lib enumerates its full value set.
    - Its values remain in the type under the D4 action.
- **component**: a comp declared in a module under `programs/lib/`, or a proposal comp.
- **construction**: a component whose outputs give another form of its inputs.
- **equivariant lib relation**: a lib relation whose output changes under each D4 element exactly as its input does.

### Equivalent models

- Two models over the same parameterization are equivalent when they give the same result for every assignment and every input.
    + Equivalent(A, B) ⇔ ∀θ ∈ Θ. ∀x ∈ G. A(θ, x) = B(θ, x)
- An **isomorphism** between two parameterizations pairs their assignments bijectively.
    + Iso(e, Θ, Θ′) ⇔ (∀θ ∈ Θ. e⁻¹(e(θ)) = θ) ∧ (∀φ ∈ Θ′. e(e⁻¹(φ)) = φ)
        + e : Θ → Θ′; e⁻¹ : Θ′ → Θ
    - Models over those parameterizations are equivalent when every pair of matched assignments gives the same result for every input.
        + EquivalentAcross(A, B) ⇔ ∃e. Iso(e, Θ, Θ′) ∧ ∀θ ∈ Θ. ∀x ∈ G. A(θ, x) = B(e(θ), x)
- Agreement on every input in the current task does not establish equivalence between models.
    - 44f52bb0 <!-- one model stores one symmetry group and two output grids. The other stores two group-to-output entries. Both models agree on every input of this task. -->
- A **divergence witness** is an input on which two models produce different results at some assignment.
    - For models over different parameterizations, equivalence is refuted by a witness under every possible isomorphism.
        + (∀e. Iso(e, Θ, Θ′) ⇒ ∃θ ∈ Θ. ∃x ∈ G. A(θ, x) ≠ B(e(θ), x)) ⇒ ¬EquivalentAcross(A, B)
    - An output identical to the input is still defined, so a divergence at such an output is valid.
        - 41e4d17e <!-- on a solid block, the model based on enclosed regions finds none and returns the input. The model based on objects finds the block and casts from it. -->

## Fidelity

The program states the task's concept without depending on how the task file or grid encodes it.

### Relational form

An ARC concept relates cells, regions, and their properties. The program states those relations directly.

- An **approximation** is a weaker relational rule that the program uses when it cannot express a concept rule as relations.
    - The approximation accepts every input the concept rule accepts, and some inputs the concept rule rejects.
    - At least one pair breaks the concept rule and still has the output that rule specifies.
    - If the weakest form of the concept rule fixed by the pairs accepts the extra inputs that the weaker rule accepts, the weaker rule is the concept rule and there is no approximation.

### ARC types

The program works in the task's own types: colors and orientation types.

### Numbers

- **Grounding.** Every number in a solver counts concrete things that are present in the task.
    - A distance counts the cells between something and an edge.
    - A size counts the members of a set.
    - A rank counts the members that come before one item in an order.
- Clause arithmetic expresses a relational operation. The program states that operation directly.
    - A wraparound shift is a walk around a cycle.
- **Zero is absence.** A `0` counts nothing that is present, so it represents an absence.
    - In a spatial setting, `0` represents the absence of a gap, offset, or distance.
    - A program is allowed to use `0` directly.

### Component instances

- In the program, an instance of a component that is not a construction realizes a concept rule and asserts that the task has that rule.
    - When the task has no such rule, the program expresses the needed step with lib relations or a local clause.
    - That instance may leave any other outputs unused.
- An instance of a construction asserts nothing about the task.

### Indirection

A parameter has the form required by the clause or component that uses it. The parameter is keyed by objects the program already has.

A clause used only to translate one representation into another is evidence that one of those representations is unjustified.

- Naming a position in a 2×2 tile by its corner creates a second name for the same key.
    - a68b268e <!-- a parameter ranks the four positions of a 2×2 division by using those positions as keys. Corner names would duplicate the keys. -->
- Routing a flat correspondence through intermediate coordinates introduces another representation.
    - e633a9e5 <!-- a parameter pairs each input cell directly with its output cell. -->
- Storing an order as successor edges requires closure to expand it before a comparison.
    - a68b268e <!-- one rank per color stores the precedence relation, so comparisons need no expansion. -->
- A stored map from a tile's places to the sections they fill uses each frame cell as its own key.
    <!-- draft: 8fff9e47 — each place in a block directly indexes the output section filled at that place, so no stored correspondence is needed. -->
- Storing an orientation as an `Axis`, `Sense`, or `Sym` requires conversion to the `D4` used by the clause.
    - 8ee62060 <!-- the parameter stores the D4 elements that fit, and the program applies them directly to block positions. -->

Conversion is justified when its two sides differ in content.

- A sparse set differs in content from its `Ordinal` ranking.
- A cell set differs in content from its `Canon` class id when the program treats the class as a single thing.

### Performance

The principled form is the right form regardless of performance. A form chosen for speed reflects constraints of the Datalog implementation and its runner.

## Invariance

ARC's symmetry group is generated by the elements of D4 together with color permutations.

The model is equivariant. When its assignment and input are transformed together, every grid in its output is transformed in the same way.

+ Equivariant(M) ⇔ ∀γ ∈ Γ. ∀θ ∈ Θ. ∀x ∈ G. M(γ · θ, γ · x) = γ · M(θ, x)
    + Γ: ARC's symmetry group
    + γ · M(θ, x) = {γ · y | y ∈ M(θ, x)}

- The program is the part of the solver that stays unchanged under the group.
- What a group element changes becomes a parameter. Orientations and colors are examples.
- A program literal belonging to an ARC type breaks equivariance when the group transforms that value.

### Invariance scope

A way of combining data is not a parameter. Models that apply different combining operations to the same data define different families and use different programs.

- dae9d2b5 <!-- two adjacent 3×3 subgrids combine cell by cell. An output cell fills when at least one source cell is non-background, and the model has no count parameter. -->
- 3428a4f5 <!-- two 6×5 subgrids separated by one row combine cell by cell. A parameter gives the exact number of non-background source cells that fills an output cell. Its value is one, and no possible value makes at least one source cell sufficient. -->

### Orientation

Some tasks distinguish a particular direction, axis, or transformation. When a task does not distinguish an orientation, neither does the program.

- The orientation types represent each possible orientation choice as a value. A mirrored sibling task therefore requires a parameter edit rather than a change to the program.
- **Orientation per axis.** A model whose clauses differ between axes does not choose an orientation when one parameter names the axis on which the clauses are keyed.

### Color

Colors have identity and no other properties.

### Equivariant lib relations

- An equivariant lib relation preserves program equivariance when its inputs derive from parameters, through an atom's arguments or a component instance's `@input` relations.
- A non-equivariant one introduces a hidden orientation into an otherwise symmetric program.
    - Mapping within a tile by distance modulo a period creates a hidden orientation. It is observable unless the extent less one is a multiple of the period.
    - An explicit anchor parameter or an equivariant encoding removes that hidden orientation.
        - 332efdb3 <!-- the motif case places a period-2 motif at every corner of the grid, so no corner is singled out. -->

### Stored or derived

- A value shown directly by the pairs is task data and is stored as a parameter. <!-- , unless it is a family invariant -->
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

A family invariant is not task data, so it is not a parameter. <!-- , even when the pairs show its value directly -->

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
    - a9f96cdd, d364b489 <!-- the two tasks paint one cell per direction and differ only in the type: a9f96cdd runs over the diagonals and d364b489 over the cardinals. Neither program reassigns into the other. -->
- **Payload.** When values vary from member to member, the rows are data and the orientation type is their domain.
    - d364b489 <!-- one parameter relation stores the direction-to-color rows. -->
- **Reassigned set.** A membership set that some sibling task narrows is task data, even when it contains every value of the orientation type in the current task.
    - 14754a24 <!-- each incomplete plus is completed from a footprint containing a center and its four neighbors. A sibling that completed a T-shaped footprint would store a proper subset of that footprint. -->

## Cases

- For a pair with two candidates, the concept case produces one of them. A peer model that produces the other under some assignment is a separate case.
    - The pairs leave undetermined which model the task teaches. That undetermination is a choice point whose branches are those models.
- The outputs within one candidate introduce no case.
    - No parameter stores the resolution values.
    - No clause treats one resolution differently from another.

A case is included exactly when it passes all of these tests:

- **Fit.** The model fits some split task at its stored assignment.
    + Fit(S_M, T) ⇔ ∃T′ ∈ alts(T). M(stored_M(D(T))) ⊨ T′
    - For a case with an open parameter, the model is M_open at the stored open values.
    - **Unseen key.** When a test uses a key that no train pair contains, a lookup table fails Fit.
        - 1fad071e <!-- the test count is 3, and the train counts are 2 and 4. The table is therefore ruled out. -->
        - 3b4c2228 <!-- every test count occurs among the train counts, so the table has no unseen key and passes this test. -->
    - Fit considers only the pairs. Being undefined on another input does not prevent a model from fitting.
- **Fidelity.** The model has an encoding allowed by the Fidelity rules.
- **Equivalence.** The model is not equivalent to the model of another case.

### Branch rules

A branch can keep, replace, or add a rule.

An **annotator** is the user or agent who supplies the plausibility and the verdict.

- **plausibility**: an ordinal estimate of how readily the generator could produce the branch's witness. Its value is the first applicable level:
    - `ordinary`: readily, without breaking any invariant of the inputs.
        - 3b4c2228 <!-- a table containing a grid the derived form cannot draw breaks no regularity of the inputs, and the pairs do not say which of the two the task teaches. -->
    - `sibling`: routinely, in a sibling task.
        - 3b4c2228 <!-- a scene that contains no block of the counted color is a scene a sibling task contains. The stored table has no entry for a count of zero, and a person reads the derived output. -->
    - `borderline`: only under unusual conditions.
    - `foreign`: never.
        - 00dbd492 <!-- the two readings of an object's empty region differ only where the object's outline is broken, which no input in the evidence shows. A person reads the enclosed region there. -->
- **verdict**: the annotator's judgment of the output that the generator would pair with the witness.
    - `concept`: the concept case's output.
    - the branch's constructor name: that branch's output.
    - `open`: any case's output.
    - `neither`: an output that no case produces.

### Parameters across cases

- **One parameter.** In a task, a parameter admits each value that some assignment gives it while its case fits the task. A collection of case-specific parameters forms one parameter when every task that all of their cases fit gives each member the same admitted values. Using one parameter across those cases asserts this condition.
    - d23f8c26 <!-- one column of an odd-width grid is kept. It is the center line on a stored axis in one case and the gap of a two-way divide on that axis in another. Any task that fits both uses one axis value. -->
    - 5d2a5c43 <!-- every decomposition case reads the space between the two parts from one shared parameter, so a change to that width applies to them all. -->
- **Distinct parameters.** Parameters are distinct when some task that their cases fit gives them different sets of admitted values.
    - 87ab05b8 <!-- three cases locate the region by a part count or a size. All values are 2 in this task, while a 6×6 sibling sets the part count to 3 and keeps the sizes at 2. -->
- **Shared form.** A shared parameter has one form.
    - When the consumers require different forms, each case has its own parameter in the form read by its consumer.
    - 2013d3e2 <!-- the output is a corner region of the non-background bounding box. The quadrant case stores it as a tile position, and the fixed-window case stores it as a corner. -->

## Open parameters

The solver stores every open value of an open parameter.

+ open(i) ⊆ Θᵢ: the open values of parameter i
+ M_open(θ, x) = ⋂_{v ∈ open(i)} M(θ[i ↦ v], x)
    + M_open: the case's model, which reads open(i) in place of θᵢ

- The program runs with every open value of the parameter.
    - The output consists of the grids that every open value produces.
        - The case fails Fit at those values on a task containing a pair whose accepted output some open value does not produce.
    - 28a6681f <!-- water settles under gravity one cell at a time. Along a line across gravity, either end can pour first, and the program runs both orders. -->

## Corpus consistency

### Setup priority

The priorities for choosing a setup are, in order:

1. Fidelity.
2. Reuse of facts and component instances already available to the program.
    - 1190bc91 <!-- both cases use one connected-component instance for marker areas. The instance reuses the shared sequence and rays, and each case supplies a different set of area cells. -->
3. The precedent for the structure.
    - 2dee498d <!-- the input contains three identical panels along a stored axis. The setup divides them with `divide_slab` from that axis and a stored panel count, and one panel is the output. -->
    - f25ffba3 <!-- the input contains a data slab along the axis of a stored direction. One case divides the input with `divide_slab` from that axis and a stored panel count, as 2dee498d does, and another case divides it from a stored panel size. -->
