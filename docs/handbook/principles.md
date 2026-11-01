+ document-size-budget: 24700
* comment: when editing this doc
    - `arcdata` marks a section or a statement an `arclog` agent needs only when its brief opts in to arcdata files. That agent's render leaves out each one that has it, and each statement that has `formal`.
    - The corpus supports the synthesis of solver programs.
    - This doc and [Encoding](docs/handbook/encoding.md) state a theory of tasks, models and encodings, in that theory's own terms.
        - A statement about how a file, a format, a marker, a command, or a tool's output represents them, or about how the solver's code is written, goes elsewhere.
        - So does a heuristic, a decision criterion, a convention, or a procedure step.
    - Place a statement in another document whose subject covers it, such as [Style](docs/handbook/style.md), [Patterns](docs/handbook/patterns.md), [Procedure](docs/handbook/procedure.md) or [Solver file](docs/handbook/solver-file.md), even where it relates to a principle. Place it in this doc or Encoding only where no other document's subject covers it.
    - Judge a principle placed here by whether it is consistent, useful, and general.
    - Prefer nested lists:
        - When a sentence states two or more parallel parts, write them as a nested list, one item each.
        - An example or an instance of a principle is a sub-item under it.
    - A citation points a reader at a worked application of the principle it is under.
    - A task is cited when its solver's file shows the application without the session that built it, its gloss says what the principle's text does not, and no citation under that principle shows the same application.
    - A task the principle is still open on, or whose solver requires a case under the principle, is not cited, and its review line states it.
    - A cited task is a bare id.
    - A gloss that states the task's facts in the principle's terms, without the task's internal vocabulary, goes under the id as a statement annotated `+ gloss`.
    - A draft solver is cited the same way, with `+ draft` under the id, and approval removes that line.
    - A principle's formal statement goes under the principle as a statement annotated `+ formal`.
    - The first formal statement under a definition starts with the term's symbol.
    - A symbol is declared in a formal statement under the definition or principle that first uses it.

# Principles

## The goal
- The corpus supports the synthesis of solver programs, and takes as much as it can from each task, in this order:
    - **Concept.** A solver has a case for the concept.
        + xref: docs/handbook/principles.md#the-concept, docs/handbook/principles.md#models-and-tasks
    - **Coverage.** A solver has a case for each other model that meets the case conditions.
        + xref: docs/handbook/principles.md#cases

## Definitions

### The solver's parts
- **parameter**: a relation whose facts are stored rather than derived.
- **derived data**: a relation derived by a clause.
    * comment
        - Derived data is not a parameter.
* comment
    - **parameter value**: the facts that a task gives a parameter.
- **parameterization**: the parameters together with the values each one takes across the generator's tasks.
    + xref: docs/handbook/principles.md#the-generator
    - Θ = ∏ᵢ Θᵢ
        + formal
        - Θᵢ: the values parameter i takes across the generator's tasks
            - A parameter's type is its encoding, and a value of the type that no task gives is outside Θᵢ.
        - θ ∈ Θ: an assignment
- **assignment**: one choice of value for each parameter.
- **program**: the clauses that derive `out` from `in` and the parameters.
- **lookup table**: a parameter that maps keys from the input to entries that the program uses.
    + arcdata

### Models and tasks
- **model**: the function that gives the output grids for an assignment and an input grid.
    - M : Θ × G → 𝒫(G)
        + formal
        - G: the set of grids
    - A model is defined at an assignment and input when its output is nonempty and contains only total grids.
        + xref: src/solver/outcome.py:Outcome, src/solver/undefined.py:NoOutput, src/solver/undefined.py:MissingCells
- **evidence**: a task's train pairs and test inputs.
    - D(T) = (train(T), test_in(T))
        + formal
- **solver**: one or more models of a task.
    - For each model, the solver stores an assignment determined by the evidence.
        + xref: src/checker/branches/checks.py:check_stored_assignment
        - S_M = (M, stored_M)
            + formal
            - stored_M : D(T) ↦ θ, the assignment the determination derives from the evidence
- **determination**: what derives a stored value from the evidence: the solver's clauses, or, among the values a proposer gives or the values of the parameter's type, those at which the model fits every train pair.
    + xref: programs/proposers.dl
    * comment: The user's words, session 129de8fc-2a0d-4d4d-b950-3a0194c762e2, 2026-10-15T15:02:55Z: "where do we draw the line? maybe there's a grey area where it's nearly bruteforce but , say, stops short of reaching the output?", 15:51:39Z: "in positive?", and 15:53:02Z: "we still use DET to say where a param comes from, and we can attach a proposer to it in arclog", with "send" at 16:21:48Z, which picks the coordinator's option 1 of 16:08:50Z.
    - A determination's clauses read the value from the whole evidence, or keep each value at which a fact of the inputs alone, or of the outputs alone, holds.
        + xref: src/checker/lint/form/prediction.py:check_determine_prediction
    - A parameter whose value such clauses give has them.
    - Test outputs are held out, so two tasks with identical evidence receive the same stored assignment.
        - D(T) = D(T′) ⇒ stored_M(D(T)) = stored_M(D(T′))
            + formal
- **tiebreak**: content that the task leaves free.
- **candidate**: a set of a pair's accepted outputs that differ only in a tiebreak.
    + xref: src/solver/pair_runs.py:Candidate
    - Outputs in different candidates differ by more than a tiebreak.
    - A pair has at most two candidates.
- **split task**: a task formed by choosing one candidate at each pair that has two.
    - Each such pair in the resulting task accepts only the chosen candidate.
    - alts(T): the set of split tasks of T
        + formal
    * comment
        - A task with one candidate at every pair is its own only split task.
            - alts(T) = {T}
                + formal
- **fit**: a model fits a split task at an assignment when it fits each of the task's pairs.
    + xref: src/solver/pair_runs.py:PairId
    * comment: The user's words, session 129de8fc, 2026-10-14T21:37:20Z to 21:40:49Z: "proposed text?", "is all this text needed?", and "2", which picks the coordinator's "Split the Fit definition into a train line and a test line?" of 21:40:12Z.
    - A train pair fits when the output on its input is the pair's candidate.
        + xref: src/solver/pair_runs.py:matching
    - A test pair fits when the output on its input holds at most two grids, one of them in the pair's candidate.
        + xref: src/solver/pair_runs.py:matching
    - M(θ) ⊨ T ⇔ (∀(x, Y) ∈ train(T). M(θ, x) = Y) ∧ (∀(x, Y) ∈ test(T). |M(θ, x)| ≤ 2 ∧ M(θ, x) ∩ Y ≠ ∅)
        + formal
        - test(T) = zip(test_in(T), test_out(T))
    - A model fits a task when it fits one of that task's split tasks.
- **model family**: all tasks that a model fits under some assignment.
    - fam(M) = {T | ∃T′ ∈ alts(T). ∃θ ∈ Θ. M(θ) ⊨ T′}
        + formal
- **sibling task**: another task in the family of this task's model.
    + arcdata
    + xref: src/checker/lint/form/case_type.py:check_family_case
- **peer model**: another model whose family contains this task.
    + arcdata
- **hypothesis**: the assertion that a task belongs to a model's family.
- **case**: one model in the solver, together with its hypothesis.

### The generator
+ arcdata

- **generator**: the process that produces the task and other tasks.
- **variant task**: a task the generator produces.
- **task data**: a value that differs between this task and a variant task the model fits.
    + xref: docs/handbook/principles.md#models-and-tasks
    - The program fixes no task data.
        + xref: src/checker/lint/bans.py:check_nonzero_literal
- **invariant of the inputs**: a regularity satisfied by every input in the evidence.
    + xref: docs/handbook/principles.md#models-and-tasks
    - An invariant of the inputs is an estimate of a constraint the generator applies in this task.

### The concept
- **claim**: a statement about the task, of one of these kinds:
    + xref: src/checker/lint/form/witnesses.py:check_claim
    - **scene claim**: what every input contains.
        - A scene claim is an invariant of the inputs.
            + xref: docs/handbook/principles.md#the-generator
    - **rule**: what the output takes from the input.
- **concept**: what a person takes the task to be an instance of.
    - **concept statement**: the claims that express the concept.
        + xref: src/checker/lint/form/header.py:check_header
- **concept case**: the case whose model the concept statement describes.
    + xref: docs/handbook/principles.md#models-and-tasks

### Choice points and open parameters
+ arcdata

- **choice point**: an underdetermined property whose possible answers are models represented by cases.
    + xref: src/checker/lint/style.py:check_choice_domain, docs/handbook/principles.md#models-and-tasks
    - A choice point stands at the concept, or under a branch when its property exists only with that branch.
        + xref: src/checker/lint/form/declared_types.py:check_unread_field
        - When the property exists with several branches of a point, those branches form one branch of it, and the choice among them is a point under that branch.
        - When the property exists only with a combination of branches of different points, the point stands under one of those branches.
    - **branch**: one possible answer to a choice point.
        + xref: src/checker/lint/form/case_type.py:check_gloss
        - The **concept branch** at a choice point is the branch taken by the claims the point stands under.
            + xref: src/checker/witness.py:check_concept_enumerated
        - Each case takes one branch at each choice point at the concept, and at each under a branch it takes.
            + xref: src/checker/lint/form/witnesses.py:check_one_case
            - 447fd412
                + draft
                - A scaled copy of a marked drawing stamps at each block; the stamp's content and which cells of a block's box it reaches combine, so each is its own point.
                    + gloss
        - A branch's model takes that branch, and the concept branch at every other choice point it takes.
            + xref: src/checker/witness.py:check_verdict_denotes
        - A branch's cases are the cases that take it.
- **open parameter**: an underdetermined property whose possible answers are values of one parameter, with the program unchanged.
    + xref: docs/handbook/principles.md#the-solvers-parts
    - **open values**: the values of that parameter that a reader of the concept could take, and that the pairs do not separate.
        + xref: src/checker/open_values.py:check_open_values
    - A sibling task that the model fails at the open values, and fits at one of them, fixes the parameter to that value.
        + xref: docs/handbook/principles.md#models-and-tasks

### Witnesses
+ arcdata

- **divergence witness**: an input on which one of these holds:
    + xref: src/checker/witness.py:check_witness_lines, docs/handbook/principles.md#models-and-tasks, docs/handbook/principles.md#the-generator
    - at some assignment, two models give different outputs, or one is defined and the other is not.
    - a model's output at some assignment differs from the output the generator pairs with the input.
- A branch's witnesses are divergence witnesses between its model and the concept branch's model.
    + xref: src/checker/lint/form/witnesses.py:check_witness, src/checker/store/witness.py:find_witness, src/checker/witness.py:check_branches_witnessed, src/checker/witness.py:check_branch_witness, docs/handbook/principles.md#choice-points-and-open-parameters
- A witness stands at this task's stored assignment when the model it is for is defined there and differs there from what it is separated from. Otherwise it stands at the assignment that changes the fewest of that model's parameters and at which that holds, and at the stored assignment when there is none.
    + xref: src/checker/witness.py:check_witness_assignment, docs/handbook/principles.md#the-concept, docs/handbook/principles.md#choice-points-and-open-parameters
    - The model a witness is for is the branch's model for a branch's witness, the concept case's model for a witness of the concept case, and the case's model for a witness without which a case fails Equivalence or Subsumption.
        + xref: src/checker/witness.py:check_witness_assignment, docs/handbook/principles.md#cases
- A witness breaks a scene claim when the concept case's claim at the assignment the witness stands at is false of it.
    + xref: src/checker/witness.py:check_witness_lines, docs/handbook/principles.md#the-concept
- An output identical to the input is still defined, so a divergence at such an output is valid.
    - 41e4d17e
        - On a solid block, the model based on enclosed regions finds none and returns the input. The model based on objects finds the block and casts from it.
            + gloss
- **annotator**: whoever judges a witness.
- **plausibility**: the annotator's ordinal estimate of how readily the generator could produce the witness. Its value is the first applicable level:
    + xref: src/solver/annotations.py:Plausibility, docs/handbook/principles.md#the-concept, docs/handbook/principles.md#the-generator
    - `ordinary`: readily, breaking no scene claim of the concept case.
        + xref: src/checker/lint/form/witnesses.py:check_witness, docs/handbook/principles.md#the-concept
        - 3b4c2228
            - A table containing a grid the derived form cannot draw breaks no regularity of the inputs, and the pairs do not say which of the two the task teaches.
                + gloss
    - `variant`: routinely, in a variant task.
        - 3b4c2228
            - A scene that contains no block of the counted color is a scene a variant task contains. The stored table has no entry for a count of zero, and a person expects the derived output.
                + gloss
    - `borderline`: only under unusual conditions.
    - `foreign`: never.
        - 00dbd492
            - The two interpretations of an object's empty region differ only where the object's outline is broken, which no input in the evidence shows. A person interprets the region there as enclosed.
                + gloss
- **verdict**: the annotator's judgment of the output that the generator would pair with the witness.
    + xref: src/checker/witness.py:check_entry_outputs, src/checker/witness.py:check_witness_lines, docs/handbook/principles.md#the-concept, docs/handbook/principles.md#choice-points-and-open-parameters
    - `concept`: the concept case's output.
        + xref: src/solver/annotations.py:VerdictWord
    - the branch's name: the output of that branch's model.
        + xref: src/solver/annotations.py:NamedVerdict
    - `any`: the output of any case defined on the witness.
        + xref: src/solver/annotations.py:VerdictWord
    - `other`: an output that no case produces.
        + xref: src/checker/witness.py:check_other_verdict, src/solver/annotations.py:VerdictWord

### Equivalence and subsumption
+ arcdata

- Two models are equivalent when each assignment of either has an assignment of the other that it agrees with.
    + xref: docs/handbook/principles.md#the-solvers-parts
    - Equivalent(A, B) ⇔ (∀θ ∈ Θ. ∃φ ∈ Θ′. Agree(θ, φ)) ∧ (∀φ ∈ Θ′. ∃θ ∈ Θ. Agree(θ, φ))
        + formal
    - Two assignments agree when, on every input, the two models give the same output or neither is defined.
        + xref: src/checker/witness.py:check_branch_witness
        - Agree(θ, φ) ⇔ ∀x ∈ G. A(θ, x) = B(φ, x) ∨ (¬Def_A(θ, x) ∧ ¬Def_B(φ, x))
            + formal
            - Def_M(θ, x): M is defined at θ and x
- Agreement on every input in the current task does not establish equivalence between models.
    - 3b4c2228
        - The stored table and the derived form agree on every input of this task, and a table holding a grid the derived form cannot draw gives it where the derived form gives another.
            + gloss
- Agreement on every input the generator produces does not establish equivalence either: the comparison ranges over every input.
    + xref: docs/handbook/principles.md#the-generator
    - 00dbd492
        - The two interpretations of an object's empty region part only where the outline is broken, an input the generator never produces, and each interpretation is a case.
            + gloss
    * comment
        - The 9f41bd9c create and refine sessions read a scene claim as narrowing the comparison, and dropped a peer that parts from the concept case only off the scene.
- An assignment that agrees with no assignment of the other model refutes equivalence, and a divergence witness against each of those assignments shows it.
    + xref: docs/handbook/principles.md#witnesses
    - (∃θ ∈ Θ. ∀φ ∈ Θ′. ¬Agree(θ, φ)) ⇒ ¬Equivalent(A, B)
        + formal
- A model is subsumed by another when the two are not equivalent and, at every assignment of the parameters either reads, on every input where it is defined, its output is the other's.
    - Subsumed(A, B) ⇔ ¬Equivalent(A, B) ∧ ∀θ ∈ Θ. ∀x ∈ G. Def_A(θ, x) ⇒ A(θ, x) = B(θ, x)
        + formal
    - A witness shows that a model is not subsumed only where that model is defined.
        + xref: docs/handbook/principles.md#witnesses

## Relational form
- An ARC concept relates cells, regions, and their properties.
- A claim has a **relational form** when some set of clauses agrees with the claim on every input the generator produces on which the claim applies, and the claim refers to no number that counts nothing the task has, such as a mean or a centroid.
    + xref: docs/handbook/principles.md#the-generator, docs/handbook/principles.md#the-concept
    * comment: The Analyze pass a0350bef143e9424f on d22278a0 read this definition, which then lacked its last clause, and a separate line that stated that clause without "even where some set of clauses agrees with it", as giving opposite answers for a Euclidean distance that clauses over squared distances agree with, and its transcript review af2f557b8ee46b12c took the definition alone as enough, as tickets 10-648 and 10-654 record.
- An **approximation** is a set of clauses that computes no such number, under its name or another, and that the program runs in place of a rule that has no relational form.
    - An input the generator produces on which an approximation disagrees with its rule is a divergence witness.
        + arcdata
        + xref: src/checker/witness.py:check_approximation_witness, docs/handbook/principles.md#witnesses

## Parameterization

### Invariance
- ARC's symmetry group is generated by the elements of D4 together with color permutations.
- A task transformed by an element of the group is a variant task.
    + xref: docs/handbook/principles.md#the-generator
- The model is equivariant.
- When its assignment and input are transformed together, every grid in its output is transformed in the same way.
- Equivariant(M) ⇔ ∀γ ∈ Γ. ∀θ ∈ Θ. ∀x ∈ G. M(γ · θ, γ · x) = γ · M(θ, x)
    + formal
    - Γ: ARC's symmetry group
    - γ · M(θ, x) = {γ · y | y ∈ M(θ, x)}
- The program is the part of the solver that stays unchanged under the group.
- What a group element changes is task data.
    + xref: src/checker/relabeling.py:check_relabelings, docs/handbook/principles.md#the-generator
    - Orientations and colors are examples.
- A way of combining content is not task data.
    + xref: docs/handbook/principles.md#the-generator
- Models that apply different combining operations to the same content define different families and differ in their clauses.
    + xref: docs/handbook/principles.md#models-and-tasks
    - dae9d2b5
        - Two adjacent 3×3 subgrids combine cell by cell. An output cell fills when at least one source cell is non-background, and the model has no count parameter.
            + gloss
    - 3428a4f5
        - Two 6×5 subgrids separated by one row combine cell by cell. A parameter gives the exact number of non-background source cells that fills an output cell. Its value is one, and no possible value makes at least one source cell sufficient.
            + gloss

### Orientation
- Some tasks distinguish a particular direction, axis, or transformation.
- When a task does not distinguish an orientation, neither does the program.
    + xref: src/checker/lint/bans.py:check_orientation_literal
- An **orientation type** is a type that meets each condition:
    - Its full value set is enumerated.
    - Its values remain in the type under the D4 action.
- A mirrored variant task therefore requires a parameter edit rather than a change to the program.
    + xref: docs/handbook/principles.md#the-generator
- **Orientation per axis.** A model whose clauses differ between axes does not choose an orientation when one parameter stores the axis on which the clauses are keyed.
- **Every value.** When a membership set meets each condition below, the program enumerates every value of the orientation type, and the parameters are per orientation type rather than per value.
    + xref: docs/handbook/principles.md#the-generator
    - It contains every value of an orientation type.
    - No associated data varies by value.
    - No variant task narrows the set.
    - 0ca9ddb6
        - One marker color paints cardinal arms, and another paints diagonal arms. The program enumerates every direction of each type, and each type has its own arm color parameter, keyed by marker color.
            + gloss
- **One member.** If one member is used and another must not be used, a parameter stores the chosen member.
- **Another orientation type.** Switching to another orientation type requires another program rather than a reassignment.
    - Switching between cardinal and diagonal directions is one example, and switching between 4- and 8-adjacency is another.
        * comment: A Create pass on a3325580 reported its delay on connectivity for the third time, and the clause on 4- and 8-adjacency was added for it: session 631a6654, 2026-09-25T14:49 to 14:51.
    - a9f96cdd, d364b489
        - The two tasks paint one cell per direction and differ only in the type: a9f96cdd runs over the diagonals and d364b489 over the cardinals. Neither program reassigns into the other.
            + gloss
- **Payload.** When values vary from member to member, they are task data, in a relation keyed by the orientation type.
    + xref: docs/handbook/principles.md#the-generator
    - d364b489
        - One parameter relation stores the direction-to-color rows.
            + gloss
- **Reassigned set.** A membership set that some variant task narrows is task data, even when it contains every value of the orientation type in the current task.
    + xref: docs/handbook/principles.md#the-generator
    - 14754a24
        - Each incomplete plus is completed from a footprint containing a center and its four neighbors. A variant task that completed a T-shaped footprint would store a proper subset of that footprint.
            + gloss

### Color
- Colors have identity and no other properties.
    + xref: src/checker/lint/bans.py:check_typed_order

### Stored or derived
- Where a stored value fits, the concept case stores structure over colors as a parameter.
    + xref: src/checker/branches/checks.py:check_color_structure_stored, docs/handbook/principles.md#the-concept
    - an ordering
    - a mapping
    - a partition
- Deriving a value asserts that the value depends on the source from which it is derived.
    - **Two parameterizations.** Storing a value and deriving that value produce two different parameterizations.
        + xref: src/checker/branches/checks.py:check_two_parameterizations, src/checker/branches/checks.py:check_stored_or_derived, src/checker/finding.py:UndecidedPayload
        - Where an assignment of the stored model gives, on some input, an output that no assignment of the derived model gives on that input, that assignment agrees with no assignment of the derived model, so they are not equivalent.
            + xref: docs/handbook/principles.md#equivalence-and-subsumption
            * comment: The Analyze pass a52ba117c25f3e31a on cf5fd0ad and its transcript review a1fb31a652189058e each read the line's former words, "On an input where the derivation gives a value other than the stored one", as making a stored value and its derivation never equivalent, against the Θᵢ definition, as tickets 10-625 and 10-629 record.
                + xref: docs/handbook/principles.md#the-solvers-parts
        - 3b4c2228
            - One model renders a count as marks down a diagonal. Another looks up a stored grid for the count. Every train and test count is a key of the table, so the models never differ on a pair.
                + gloss
- **Redundant value.** A value that follows from another parameter in every variant task is derived data rather than a second parameter.
    + xref: src/checker/lint/constants.py:check_const_join, src/checker/lint/heads.py:check_head_repeat, docs/handbook/principles.md#the-generator

### Open parameters
+ arcdata

- The solver stores every open value of an open parameter in one relation.
    + xref: docs/handbook/principles.md#choice-points-and-open-parameters
- open(i) ⊆ Θᵢ: the open values of parameter i
    + formal
- M_open(θ, x) = ⋃_{v ∈ open(i)} M(θ[i ↦ v], x) where ∀v ∈ open(i). Def_M(θ[i ↦ v], x), and ∅ otherwise
    + formal
    - M_open: the model with open(i) in place of θᵢ
- The output contains each grid some open value produces, and is undefined where the model is undefined at some open value.
    + xref: src/checker/sweep.py:values_giving, src/solver/out_grids.py:open_union
    - caa06a1f
        - A periodic pattern continues one step toward the corner of its block, along the horizontal or the vertical axis. The pairs fix neither axis, and the output holds the grid of each. The test pair's two candidates are those two grids.
            + gloss

## Cases
+ arcdata

- A case is included exactly when it meets each **case condition**:
    + xref: src/checker/case_conditions.py:check_case_conditions
    - **Fit.** The model fits some split task at its stored assignment.
        + xref: docs/handbook/principles.md#models-and-tasks
        - Fit(S_M, T) ⇔ ∃T′ ∈ alts(T). M(stored_M(D(T))) ⊨ T′
            + formal
        - For a case with an open parameter, only Fit uses M_open at the stored open values in place of the model.
            + xref: docs/handbook/principles.md#open-parameters
        - **Unseen key.** When a test uses a key that no train pair contains, a lookup table fails Fit.
            + xref: src/checker/drop_one.py:survey_drop_one, docs/handbook/principles.md#the-solvers-parts
            - 1fad071e
                - The test count is 3, and the train counts are 2 and 4. The table is therefore ruled out.
                    + gloss
            - 3b4c2228
                - Every test count occurs among the train counts, so the table has no unseen key and meets this condition.
                    + gloss
        - Being undefined on another input does not prevent a model from fitting.
            + xref: docs/handbook/principles.md#models-and-tasks
    - **Relational form.** Each claim the case's branches replace or add has a relational form.
        + xref: docs/handbook/principles.md#relational-form, docs/handbook/principles.md#choice-points-and-open-parameters
    - **Equivalence.** The model is not equivalent to the model of another case.
        + xref: src/checker/case_conditions.py:check_equivalence, docs/handbook/principles.md#equivalence-and-subsumption
        - Of two cases with equivalent models, the one that takes more non-concept branches fails it, and of two with equal counts, one of them.
            + xref: src/checker/case_conditions.py:check_case_conditions
    - **Subsumption.** The model of a case other than the concept case is not subsumed by the model of another case.
        + xref: src/checker/case_conditions.py:check_subsumption, docs/handbook/principles.md#equivalence-and-subsumption
- For a pair with two candidates, the concept case produces one of them.
    + xref: docs/handbook/principles.md#models-and-tasks
- A peer model that produces the other under some assignment is a separate case when it meets the conditions above.
    + xref: docs/handbook/principles.md#models-and-tasks
- The pairs underdetermine which model the task teaches.
- Which model it teaches is then a choice point whose branches are those models.
    + xref: docs/handbook/principles.md#choice-points-and-open-parameters
    * comment
        - A branch can keep, replace, or add a claim.
- The outputs within one candidate introduce no case.
    + xref: docs/handbook/principles.md#models-and-tasks

### Parameters across cases
- **One parameter.** In a task, a parameter admits each value that some assignment gives it while its case fits the task.
    + xref: docs/handbook/principles.md#models-and-tasks
    - A collection of case-specific parameters forms one parameter when every task that all of their cases fit admits a value common to every member.
    - Using one parameter across those cases asserts this condition.
    * comment
        - The condition is on the whole collection.
        - Parameters that meet in pairs need not all admit one value.
    - d23f8c26
        - One column of an odd-width grid is kept. It is the center line on a stored axis in one case and the gap of a two-way divide on that axis in another. Any task that fits both uses one axis value.
            + gloss
    - 5d2a5c43
        - Every decomposition case reads the space between the two parts from one shared parameter, so a change to that width applies to them all.
            + gloss
- **Distinct parameters.** Parameters are distinct when some task that their cases fit admits no value common to them.
    + xref: docs/handbook/principles.md#models-and-tasks
    - 87ab05b8
        - Three cases locate the region by a part count or a size. All values are 2 in this task, while a 6×6 sibling sets the part count to 3 and keeps the sizes at 2.
            + gloss
