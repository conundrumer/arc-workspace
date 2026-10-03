# Generators

[Principles](handbook/principles.md) defines a task's generator as the process that produces the task and its variant tasks, and uses it without defining it further. This document defines the generator as an object that can be sampled and evaluated, and derives from it the quantities that plausibility and verdicts estimate. Its theory comes first, and its implementation in the solver files and Souffle follows. Terms follow [Terms for the paper](paper-terms.md).

## Theory

### What the generator is

- The generator is the process the task's author ran. The task's pairs, the held-out test pairs included, are its outputs, and a reader's reading of the task is an estimate of it.
- Each case gives its own estimate of the generator, the case's generator: the one its claims describe. Its input claims estimate the generator's input constraints, and its output claims estimate the generator's target function.
    - An input claim holds on every observed input, the test inputs included, so the observed data checks it on every input of the task.
    - An output claim holds on every pair, the held-out test pairs included, so the observed data checks it on the train pairs alone.
- Which case's generator is the author's is unknown, and the observed data does not determine it.

### Parts of a generator

- **Scene**: the content of one input, in the terms of the intended concept: the frame, the background, and the parts the input claims mention, with their properties.
- **Task prior**: a distribution over assignments θ. One draw gives the assignment of one task.
- **Scene prior**: a distribution over scenes given θ. One draw gives one scene, and the renderer makes one pair from it.
- **Support**: the set a prior gives positive probability to.
- **Input constraint**: a predicate on an input grid and θ that holds on every input the generator gives at θ. Each input claim is the estimate of one input constraint.
    - A predicate on one input and the output the target function gives it is also an input constraint. An example is that the output differs from the input.
- **Task constraint**: a predicate on θ together with all of a task's scenes. An example is that the train pairs determine the test outputs.
- **Renderer**: the map from θ and a scene to an input grid and a set of output grids. It is defined on every scene, including scenes outside the support.
- **Target function**: the map from θ and an input grid to the set of output grids that the author's renderer gives for a scene of that input. The set holds every output the author accepts: each candidate, with each of its tiebreak resolutions. The target function is defined on an input when every scene of that input gives the same set. A task has one target function, and it is unknown. Each case's renderer gives that case's estimate of it.
- **Task sampler** and **scene sampler**: the procedures that take a seed to a draw from the task prior and the scene prior.

### Parameters of the generator

- A claim reads its values from parameters. "Exactly N markers" is the claim, and N is a parameter in θ that the determination derives from the inputs.
    - A parameter that only a claim reads is a parameter of the generator and not of the hypothesis.
- The inputs do not fix the form of a claim, such as "exactly N" against "between N1 and N2". That choice is a choice among cases, and the likelihood of the inputs under each case's generator weighs it.
- The output has no constraint of its own. A property of the output that is the same in every pair, such as a fixed color, a template, or a fixed size, is task data in θ, and the target function reads it.

### The support and its probabilities

- The support of the task prior is closed under the symmetry group. A task transformed by an element γ of the group is a task the author's generator produces, and it is a variant task exactly when γ changes θ.
- The probabilities are fitted on the corpus, so they can differ across the group where authors favor some colors or some directions.
- A variant task is a task that the same generator clauses produce at other parameter values. The task prior's support is then every value of each parameter's type at which the input constraints can hold together.
    - The orbit of the stored assignment under the symmetry group is a lower bound on that support.

### Witnesses

- A constraint takes one of three values on a grid at an assignment: it holds, it fails, or it is undefined. It is undefined when it is stated over parts that another claim defines, and that claim fails. "Every run of ink is a domino" defines the dominoes, and a claim about the dominoes is undefined on a grid where some run of ink is not a domino.
- The assignment a witness stands at changes only the hypothesis's parameters, so every claim-only parameter keeps its stored value there. A witness breaks the claims that fail on it at that assignment.
- A witness's **generator assignment** is the assignment it stands at, with the parameter of each claim it breaks reassigned to a value at which the claim holds.
- A grid that breaks a claim that defines its parts, at every value of that claim's parameters, has no scene.

### Quantities derived from the generator

- **Probability of a witness**: the task prior's probability of the witness's generator assignment, divided by its probability of the stored assignment, under the cases' generators, each weighted by the posterior over cases. It replaces the plausibility levels.
    - It is 1 for a witness that breaks no claim and stands at the stored assignment.
    - The division removes the probability of the task itself, which no plausibility level judges.
- **Disagreement of two cases**: the probability that two cases give different outputs on the test inputs of a drawn task, where undefined counts as an output. Each case reads the drawn task at the assignment its own determination gives from that task's observed data.

    ```
    dis(A, B) = P[ A(θ_A(T), x) ≠ B(θ_B(T), x) ]
        T drawn from the mixture of the cases' generators, weighted by the posterior over cases
        x a test input of T
        θ_A(T) the assignment A's determination gives from T's observed data
    ```

    - On one task, two cases can store different values of one parameter, so each case's assignment comes from its own determination.
    - A hypothesis's error is the probability that its test output differs from the target function's on a drawn task, so `dis(A, B)` is A's error when B's renderer gives the target function.
    - `dis(A, B) = 0` on the support does not make A and B equivalent. Equivalence ranges over every input.
- **Posterior over cases**: the prior over cases, times the likelihood of the observed inputs under each case's generator, over the cases consistent with the observed data.
    - At solve time the test outputs are unknown, so the posterior ranges over the consistent cases. A solver's cases also solve the task, which takes the test outputs.
    - When two cases share a scene prior, their likelihoods are equal and the prior over cases decides.
    - The prior over cases is fitted on the corpus.
- **Verdict**: the set of outputs the target function gives a witness. The posterior over cases estimates it by weighting the output sets of the cases' renderers. Away from approximated output claims, each renderer's output is its case's output.
    - A verdict of `any` corresponds to a target set that holds the output of every case defined on the witness.
- The case conditions select cases without these quantities. The quantities annotate the cases.
- The plausibility levels and verdicts already written in the solvers are a test set for these quantities.

### Information beyond the pairs

- A generator derived from a solver agrees with that solver's outputs by construction. That agreement does not show that the solver is right.
- Information on the solver's outputs beyond the pairs comes from these sources:
    - The held-out test outputs. When a branch is consistent with the observed data and does not solve the task, the author's output on a test input differs from the branch's.
    - Readers. A reader given the task with a witness as an added test input, and with no view of the cases, gives an output. The distribution of readers' outputs estimates the verdict.
    - Observed variant tasks: variant tasks that are among the ARC tasks. One whose inputs show scenes that this task's inputs do not bears on the target function on those scenes.

## Implementation

### Scenes and parameters

- **Scene schema**: the relations a task's scenes are stated in. A scene is an instance of the scene schema: a set of facts over those relations.
- A parameter that only a claim reads is read by no clause of the program, and it is stored in `Params` with the parameters the program reads.
- A claim's prose may state a value, as in "three colors". When the claim is written as clauses, a value that is task data moves into `Params`, by the literal ban, and a value that comes from geometry, such as the four sides of a rectangle, becomes a range over an orientation type.

### Input constraints as clauses

- Each input claim has a clause form: a relation over the grid and `Params` that holds when the claim holds.
- The `@relaxed` lines of a witness are the slugs of the claims it breaks.
- The constraints are evaluated on the grid, since a grid with no scene has no instance of the scene schema.

### The renderer

- The renderer is written in Datalog over the same lib and `Params` as the solver.
- Each case's generator has its own renderer. For an output claim with no `@approximated:` line, the renderer takes the claim's part of the output from that case's program.
- For an output claim with an `@approximated:` line, the renderer states the exact claim in a relation marked with the claim's slug. That relation alone is exempt from program style, since an exact claim of this kind needs arithmetic. On a witness where the concept case's renderer and every case disagree, that renderer gives the output that a verdict of `other` estimates.

### Sampling

- A scene sampler is a Souffle program and a driver that is the same for every task.
    1. The program derives, for each choice the sampler makes, a candidate relation from `Params` and from the choices already made.
    2. The driver reads one candidate relation, picks one tuple by the seed and the probabilities, and adds that tuple as a fact.
    3. The driver runs Souffle again and continues with the next choice, until no choice remains.
    4. When a candidate relation is empty, or an input constraint that the candidate relations do not enforce fails on the finished scene, the driver restarts from the seed's next draw.
- Each candidate relation is the support of one choice. The choices are ordered so that each scene has one sequence of choices. Replaying a scene's sequence through the same candidate relations then tests whether the scene is in the support and gives the probability of its sequence.
- A restart conditions the draw on success. The probability of a scene under a generator is the probability of its sequence divided by the generator's success rate, which sampling estimates.
- A grid that several scenes produce has the sum of their probabilities.

### Comparisons

- These comparisons set parts from different sources against each other:
    - Every observed input is in the support of each consistent case's generator.
    - On a sampled task, the θ the sampler drew is among the values the determination returns.
    - The constraint clauses reproduce the `@relaxed` lines of the witness files.
    - On sampled inputs, each case is defined wherever the input constraints hold.

## The corpus

- Fitted on the corpus, the generators and solvers give these distributions:
    - over programs: how often each lib component and each clause shape occurs
    - over scenes: which scene components occur, with their parameters
    - over pairs of a scene component and an output claim, which the keywords index
    - over choice points: which branches arise with which concepts
- For solver synthesis:
    - The posterior over cases orders the search, and the inputs alone, the test inputs included, narrow it before any output is read.
    - The sampler gives the θ of each task it samples, so each sampled task comes with its solver: the same program at that θ. Sampled tasks are training data.
    - One generator can emit a task twice, once with a divergence witness among the train pairs and once without. The two show which observed pairs resolve which choice point.
    - Where several cases are consistent with the observed data, the posterior ranks their test outputs, and `dis` says whether the ranking matters on the test input.
- For generator synthesis:
    - `Params` gives the parameters the task prior draws, the input claims give the input constraints, and the program gives each case's estimate of the target function.
    - What remains to write is the scene sampler. A lib of scene components, each with candidate relations and fitted probabilities, would supply it.

## Open questions

- **Where a concept ends.** The criterion above bounds the support of the task prior by the generator's clauses. How far the probabilities reach from this task's values is a fitted quantity, and no principle yet states it.
- **The verdict beyond the observed data.** Away from the observed inputs, the cases' renderers differ, and the posterior over cases weighs them. Within one task, only readers and observed variant tasks bear on that weighing.
- **Grids with no scene.** A grid that breaks a claim that defines its parts, at every value of that claim's parameters, has no scene, so no renderer gives it an output, and the verdict on it has no definition.
