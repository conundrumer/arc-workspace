# Terms for the paper

The principles are to be published as a paper that presents them as a theory of ARC tasks. This document proposes the changes to the handbook's terms that make them ready for that paper.

## Goal

- A reader from learning theory, logic, program synthesis, or Bayesian cognitive science reads each term with its intended meaning.
- When a standard term has the same meaning, the handbook uses it.
- A current term changes only when a reader would take it for a standard term with a different meaning.
- A term with no standard match keeps its name. The paper defines it formally and names its nearest standard term in the related work.

## Renames

- **model** → **hypothesis**
    - In logic, a model is a structure that satisfies a theory, and a paper that presents a theory invites that reading.
    - In learning theory, a hypothesis maps inputs to outputs. `M(θ)` is a hypothesis, and `M` over Θ is a parametric hypothesis.
- **hypothesis** (the assertion that a task is in a model's family) → **M solves T**
    - The rename of model takes the word.
    - The assertion is already the solves relation, stated in words.
- **fit** → **solves**
    - In ML, a model is fitted to its training data, so a reader takes "fits" to mean the train pairs. The relation includes the test pairs.
    - "Solves a task" is the ordinary ARC phrase for getting the test outputs right.
    - The case condition Fit becomes Solves, and a family is every task a hypothesis solves at some assignment.
- **concept** → **intended concept**
    - In PAC learning, every member of the class is a concept. The qualifier marks the one a person takes the task to be.
    - Compounds such as concept case and concept branch keep their names.
- **peer model** → **another hypothesis that solves the task**
    - A consistent hypothesis agrees with the observed data, and a peer model also gives the test outputs.
- **evidence** → **observed data**
    - It is the train pairs together with the test inputs.
    - In Bayesian statistics, the evidence is the marginal likelihood, and the paper states priors, likelihoods, and a posterior over cases.
- **concept statement** → **concept claims**
    - It names a set of claims, and in logic a statement is one sentence.
    - It joins the compounds concept case and concept branch, whose head nouns name the thing itself.
- **sibling task** → **task in the family of a case's hypothesis**
    - A task with several cases has several hypotheses, and each has its own family.
    - In the solver files, **family sibling** → **a solver whose header has an `@representative` line**. "Family" then names only a hypothesis's family.
- **rule** (the claim kind) → **output claim**
    - In Datalog and logic programming, a rule is a clause with a body, and the paper presents Datalog programs. The handbook already moved that sense to "clause".
    - An output claim states what the output contains, given its input. It is an invariant of the pairs, as an input claim is an invariant of the inputs.
    - The header directive is `@output`.
- **scene claim** → **input claim**
    - It pairs with output claim, and it states what the inputs contain. The handbook already calls it an invariant of the inputs.
    - "Scene" then names only the generator's scene.
    - The header directive is `@input`. The lib's `// @input` marker, on a relation that a component's caller supplies, becomes `// @extensional`: in Datalog, an extensional relation is given to the program, and an intensional relation is derived by its clauses.

## New terms

- **Consistent**: M(θ) is consistent with a task's observed data when its output on each train input is that pair's candidate and it is defined on each test input.
    - Nearest standard term: consistent hypothesis (learning theory), in the transductive setting, where the test inputs are visible.
    - It reads what the determination reads, so it is the relation available at solve time.
- **The consistent hypotheses**: every hypothesis consistent with the task's observed data. The cases are a selection from them: the ones the analysis forms that solve the task and have relational form, one per equivalence class. The case conditions are the rule for that selection.
    - Nearest standard term: version space (Mitchell, 1982), which is defined as this set.
- **The case's generator**: the estimate of the generator that a case's claims describe. Which case's generator is the author's is unknown, and the observed data does not determine it.
- **Target function**: the author's map from θ and an input grid to the set of output grids the author accepts. A task has one, and each case's hypothesis estimates it.
    - Nearest standard term: target function (PAC learning).
    - "Target" alone reads as the outputs y in supervised learning.
- **Disagreement**: the probability that two hypotheses give different outputs on the test inputs of a drawn task.
    - Nearest standard term: disagreement (active learning).
    - As the name of a quantity, "divergence" reads as a distance between two distributions, such as the KL divergence.
- **The generator's parts**: [Generators](generators.md) defines them.

## Kept terms

- **determination**
    - Nearest standard terms: learner, estimator.
    - The hypothesis is fixed, and the determination chooses only θ. It can give several values, and it is exact.
    - A learner chooses the hypothesis and returns one answer. An estimator implies noisy data and an approximate answer.
    - In Datalog, every clause does inference. Induction collides with the `induce` keyword, and fitting suggests optimizing a loss, where the determination is exact.
    - "Determination" pairs with "undetermined", the word the handbook uses for what the pairs leave open.
- **open parameter**
    - Nearest standard term: non-identifiable parameter.
    - Rename it if the paper states results about identifiability. The matching term for the determination is then identification, as in an identification strategy in econometrics.
- **divergence witness**
    - Nearest standard term: distinguishing input (oracle-guided synthesis).
    - "Witness" is standard in logic.
- **annotator**, **verdict**
    - Nearest standard terms: oracle, label (active learning).
    - The meanings match, and the current names are clear.
- **plausibility**
    - Nearest standard terms: in-distribution, distribution shift, tail, outside the support.
    - [Generators](generators.md) replaces the ordinal scale with a probability: the task prior's probability of the witness's generator assignment, relative to the stored assignment.
- **candidate**, **split task**, **tiebreak**
    - Nearest standard terms: candidate label set, disambiguation (partial-label learning); don't-care (logic synthesis).
    - The meanings match, and the current names are clear.
- **equivalence**
    - Nearest standard term: extensional equivalence.
    - The definition states the domain that the comparison ranges over.
- **family**
    - Nearest standard term: the tasks a hypothesis realizes.
    - The definition is formal and short.
- **generator**
    - Nearest standard term: generator (re-arc).
    - Already standard.
- **variant task**
    - It is a task the author's generator produces at an assignment other than the stored one.
    - The handbook's definition, a task the generator produces, narrows to this. Its one use of the broader sense, in Θᵢ, becomes "the tasks the author's generator produces".
    - An observed variant task is a variant task that is among the ARC tasks.

## Sources to check

Each citation and definition needs to be checked against the source before the paper uses it.

- Valiant (1984), PAC learning: concept, concept class, target concept.
- Mitchell (1982), *Generalization as Search*: version space.
- Jha, Gulwani, Seshia, Tiwari (2010), oracle-guided component-based program synthesis: distinguishing input.
- Lake, Salakhutdinov, Tenenbaum (2015), Bayesian Program Learning: a generative model over programs.
- Hodel (2024), re-arc: generator.
- Chollet (2019), *On the Measure of Intelligence*: the base ARC vocabulary.
