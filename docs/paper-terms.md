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
- **hypothesis** (the assertion that a task is in a model's family) → **M fits T**
    - The rename of model takes the word.
    - The assertion is already the fit relation, stated in words.
- **concept** → **intended concept**
    - In PAC learning, every member of the class is a concept. The qualifier marks the one a person takes the task to be.
    - Compounds such as concept case and concept branch keep their names.
- **peer model** → **consistent hypothesis**
    - In learning theory, a consistent hypothesis agrees with every example, and the version space is the set of consistent hypotheses.
    - A hypothesis that fits the task is consistent in that sense.

## New terms

- **Version space**: every hypothesis that fits the task. The cases are a selection from it: the members the analysis forms that have relational form, one per equivalence class. The case conditions are the rule for that selection.
- **Generative model**: a task's generators and hypotheses over all of its cases. The case is a hidden variable, and the evidence doesn't determine it. For each case, the generator is the one its scene claims describe, and the hypothesis is the one its program runs. After the renames, this is the only use of the word "model".

## Kept terms

- **determination**
    - Nearest standard terms: learner, estimator.
    - The hypothesis is fixed, and the determination chooses only θ. It can give several values, and it is exact.
    - A learner chooses the hypothesis and returns one answer. An estimator implies noisy data and an approximate answer.
    - In Datalog, every clause does inference. Induction collides with the `induce` keyword, and fitting collides with the Fit case condition.
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
    - The ordinal scale is the paper's own. The standard phrases explain its levels.
- **candidate**, **split task**, **tiebreak**
    - Nearest standard terms: candidate label set, disambiguation (partial-label learning); don't-care (logic synthesis).
    - The meanings match, and the current names are clear.
- **fit**
    - Nearest standard terms: consistent, realizes.
    - The definition states that fit includes the test pairs.
- **equivalence**
    - Nearest standard term: extensional equivalence.
    - The definition states the domain that the comparison ranges over.
- **family**
    - Nearest standard term: the tasks a hypothesis realizes.
    - The definition is formal and short.
- **generator**
    - Nearest standard term: generator (re-arc).
    - Already standard.

## Sources to check

Each citation and definition needs to be checked against the source before the paper uses it.

- Valiant (1984), PAC learning: concept, concept class, target concept.
- Mitchell (1982), *Generalization as Search*: version space.
- Jha, Gulwani, Seshia, Tiwari (2010), oracle-guided component-based program synthesis: distinguishing input.
- Lake, Salakhutdinov, Tenenbaum (2015), Bayesian Program Learning: a generative model over programs.
- Hodel (2024), re-arc: generator.
- Chollet (2019), *On the Measure of Intelligence*: the base ARC vocabulary.
