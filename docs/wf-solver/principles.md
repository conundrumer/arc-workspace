<!-- When editing this doc:
- Write in the indicative mood.
- Avoid justifications, unless there is necessary reason.
- Avoid contrastive structures, unless the alternative needs to be addressed.
- Prefer nested lists:
    - When a sentence states two or more parallel parts, write them as a nested list, one item each.
    - An example or an instance of a rule is a sub-item under it.
- A citation points a reader at a worked application of the rule it sits under. A task is cited when its solver's file shows the application without the session that built it, its gloss says what the rule's text does not, and no citation under that rule shows the same application. A task the rule is still open on, or whose solver owes a case under the rule, is not cited; its review line carries the point.
- A cited task is a bare id. A gloss that states the task's facts in the rule's terms, without the task's internal vocabulary, goes in a comment beside the id.
- A citation of a draft solver waits at the citation's place as `<!-- draft: <id> — <gloss> -->`, and the solver's approval turns it into the citation.
- A rule's formal statement goes on a `+` line under the rule. The first `+` line under a definition starts with the term's symbol, and a symbol is declared on a `+` line under the definition or rule that first uses it. -->

# Principles

The theory of tasks and their solvers, and the design norms for the best model of a task.

The goal is a corpus that supports program synthesis of solvers. Across the corpus, reusable primitives and fragments are drawn from the shared parts of solvers.

The formal statement is the rule.

## Definitions

- **parameter** — a relation whose facts come from the task, not from a rule.
    + i
- **value** (of a parameter) — the facts a task gives it.
    + θᵢ
- **parameterization** — the parameters with their schemas.
    + Θ = ∏ᵢ Θᵢ
        + Θᵢ — the values that parameter i admits
- **assignment** (of a parameterization) — the value of each of its parameters.
    + θ
- **program** — the rules that derive `out` from `in` and the parameters.
- **table** — a parameter that maps keys to entries. The program reads the key from the input and takes its entry.
- **model** — the function that takes an assignment and an input and computes the output, implemented by a program.
    + M : Θ × G ⇀ G
        + G — the set of grids
- **solver** — the file that models a task: a program, its parameters, and their determination.
- **determination** — the rules that derive a parameter's value from the train pairs and the test inputs.
    + detᵢ(train(T), test_in(T)) = θ(T)ᵢ
        + T — a task: a finite set of pairs (x, y) of an input and its output, test pairs included
            + an unbound T, i, or M is the current one
        + train(T) — the train pairs of T
        + test_in(T) — the test inputs of T
        + θ(T) — the assignment that T's solver stores, or that a solver with this program and determination would store
        + θ(T)ᵢ — its value of parameter i
- **family** (of a model) — the tasks it fits: a model fits a task when some assignment of its parameterization produces the task's outputs from its inputs.
    - Their solvers share the program and the determination.
    - Where the representative holds several cases, the sibling's solver holds the cases whose models fit the sibling's task.
    + fam(M) = { T : ∃θ. M(θ) ⊨ T }
        + M(θ) ⊨ T — ∀(x, y) ∈ T. M(θ, x) = y
    + ∀T ∈ fam(M). M(θ(T)) ⊨ T
- **sibling** (of a task) — another task in the family of that task's model.
    + T, T′ ∈ fam(M), T′ ≠ T
        + a prime marks another of the same kind
- **case** — the encoding of one model in the solver, under one element of `Choice`.
- **parse** — which structures a model finds in the input grid.
- **setup** — the parse that every case shares, with the program rules that encode it.

## Fidelity

The program encodes the concept of the task, apart from how the data or the medium encodes it.

### Relational form

ARC concepts are relations between cells, regions, and properties. The program encodes them as relations.

- Arithmetic in a rule usually represents a relational operation.
    - A wraparound shift is a walk along a cycle.
- Arithmetic that seems necessary usually shows that a lib primitive is missing, and the lib addition protocol decides.

### ARC types

The program works in the task's own types: colors, directions, axes, D4 elements. Projecting them into bools or ints adds structure (ordering, arithmetic) that they do not have.

### Lib units

If the task does not have a lib unit's concept, the solver does not use that unit.

- Needing part of a unit's computation is not a reason to use it.
    - A program that needs only one step of a unit writes that step with primitives or a local rule.
    - A program may read one exposed output of a comp and leave the rest unread, as long as the task has the unit's concept.

### Indirection

Parameters enter in the form that their consumer reads, keyed by objects that the program already has. If a rule's only function is to convert one representation of a thing into another, one of the two representations is unjustified.

- Conversions of that kind:
    - a key renamed into a second vocabulary
        - a 2×2 tile position named by its corner
    - a flat correspondence routed through intermediate coordinates
    - an order stored in the parameters as successor edges, which closure expands before a comparison reads it
    - a frame's cells keyed by themselves
        - a stored map from a tile's places to the sections they fill
- When the two sides differ in content, conversion is justified:
    - a sparse set and its ranking (`Ordinal`)
    - a cell set and the id of its equivalence class (`Canon`), when the program acts on the class as one thing through that id

### Performance

The principled form is the right form regardless of performance. A form chosen for speed is an artifact of the medium.

## Invariance

Generalization happens at the family level. The current task is one member of a family symmetric under ARC's transformations: rotations, mirrorings, recolorings, re-anchorings.

- The program is the part that stays the same under those transformations.
- What a transformation changes, an orientation, a color, a placement, becomes a parameter.
- No two parameters admit values that contradict.
- Programs specific to the current member are failures.

### Invariance scope

Invariance ranges over ARC's symmetry group: orientation, color, placement. It does not extend to how the rules combine their inputs.

### Color

Colors have identity and nothing else.

- Structure over colors (an ordering, a mapping, a partition) is task data, stored as a parameter.
- Comparing by enum ordinal or iterating C0..C9 in the program adds structure that the task does not have.

### Orientation

A task may single out a direction, axis, or transformation. Without that, no choice is singled out.

- Position's four edge distances remove the corner origin.
- Dir, Axis, DiagDir, and D4 make each orientation choice a value, so a mirrored sibling needs a parameter edit, not a program restructure.

### Equivariance

A lib primitive is equivariant when transforming its input by any D4 element transforms its output the same way. A lib primitive reads specific Position fields internally if and only if it is equivariant.

- Equivariant primitives are safe to feed from the parameters.
- A non-equivariant primitive adds a hidden orientation to a program that is otherwise symmetric. An explicit anchor parameter, or an equivariant encoding, removes that hidden orientation.
    - An intile mapping by distance mod period is one such primitive, observable on non-divisible extents.
        - 332efdb3 <!-- a period-2 pattern; one case models it with `divide_by_size` K=1 G=1 in place of mod. -->

### Stored or derived

When the pairs exhibit a value directly, that value is task data, stored as a parameter. A program derivation instead claims that the value depends on its source.

- A witness of a divergence is an input on which two candidates, models or assignments of one model, produce different outputs. A witness of that dependence is a pair on which the derivation differs from the stored value.
    - Against a stored constant, the witness is a pair whose source differs from the other pairs' and whose value follows it, or a test input on which the derivation differs from the constant. A value that is the same on every pair and test input has no witness.
        - 4522001f <!-- the input is 3×3 and the output 9×9 in every pair, and the test input is 3×3; the output extent is stored, and the square of the input extent would reproduce it. -->
    - Against a stored table, the witness is a test input whose key has no train entry.
- **Unwitnessed derivation.** An unwitnessed derivation stands only as a case beside the stored case.
    - 3b4c2228 <!-- the count renders as marks down a diagonal, or from a stored grid per count; every train and test count is a key of that table, so the two never differ on a pair. -->
    - **Multiple derivations.** Several derivations of one stored value are peer models of each other, and the Coverage rules decide each on its own. No derivation is preferred for being the corpus's usual form.
- **Setup derivation.** Setup gets no case, so it cannot include an unwitnessed derivation.
- **Correspondence frame.** Because the pairs witness a correspondence cell by cell, a frame built as a correspondence over input cells (007bbfb7) derives no number.

### Zero is absence

In spatial data, the number 0 means no gap, no offset, no distance: the lack of structure. It is never task data. A program may write `0` directly.

### Closure

A parameter can carry structure: a membership set whose rows are exactly a structural class (every cardinal, a D4 orbit) with no payload that varies across them. No sibling assigns it a proper subset.

+ ∀T′ ∈ fam(M) ∖ {T}. θ(T′)ᵢ = C
    + C — a structural class
    + a membership parameter i over C has ∀θ. θᵢ ⊆ C

Which members the task uses decides the encoding:

- **Every member.** If the task uses every member, the class is structural.
    - The program enumerates it (`dir_elem`, `diag_dir_elem`).
    - The parameters are keyed by class.
    - 0ca9ddb6 <!-- a marked dot gets an arm in every cardinal direction or in every diagonal one, and each kind of arm has its own parameter, keyed by the mark's color. -->
- **One member.** If the task uses one member and must not use another, a parameter holds the member.
- **Peer class.** If a task uses a peer class (cardinals against diagonals), it gets another program, not a reassignment (a9f96cdd, d364b489).
- **Payload.** If the values vary per row, the rows are data and the class is the domain.
    - d364b489 <!-- each marker paints the neighbor on each of its four sides, clipped at the grid edge, and each direction has its own color. -->

Closure decides the encoding and removes no case.

- **Reassigned set.** A membership set that some sibling reassigns is task data even when this task's value coincides with a structural class.
    + ∃T′ ∈ fam(M) ∖ {T}. θ(T′)ᵢ ⊊ C
    - 14754a24 <!-- each incomplete plus is completed from a footprint of a center and its four neighbors; a sibling that completed a T would reassign the footprint, so the footprint's stored case stands beside its structural case. -->

### Underdetermined choice

If every assignment permits a program choice, that choice is not task data.

- A parameter for it is unwitnessed.
- A literal hides it.
- The program enumerates its class and derives `out` per member, so the output is defined where the members agree.
    - 28a6681f <!-- water settles under gravity one cell at a time; along a line across gravity, either end may pour first, and the program runs both orders. -->

## Coverage

A few train pairs underdetermine the family. Coverage is one case per model that the rules of this section admit.

- **hypothesis** — the assertion that the task is in a model's family.
    + T ∈ fam(M)
- **choice point** — a property of the task that the pairs do not determine.
- **branch** (of a choice point) — one of its possible answers.
- **peer model** (of a model) — another model that fits the same task.
    + T ∈ fam(M) ∩ fam(M′), M′ ≠ M
- **prior** — a core knowledge prior that ARC training tasks are intended to teach in pure form. A case claims which priors the task teaches. Several models can claim the same priors.
- The rules of this section apply in order:
    1. Prior or setup.
    2. Evidence.
    3. Subsumption.
- A peer that Evidence removes gets no case, even when it subsumes the current model.
- Coverage shows which prior the task could be teaching.
- A hypothesis decomposes by choice point into one branch per point, and each branch is itself a hypothesis.
    + H = ∏ⱼ Bⱼ
        + Bⱼ — the branches of choice point j
        + H — the hypotheses these rules judge
    - Branches of one choice point exclude one another.
        + b, b′ ∈ Bⱼ, b ≠ b′ ⇒ ¬∃M. b(M) ∧ b′(M)
            + b(M) — model M answers its point with b
    - Branches of separate choice points combine, and each combination of one branch per point is a hypothesis that these rules judge.
        + b ∈ Bⱼ, b′ ∈ Bₖ, j ≠ k ⇒ ∃M. b(M) ∧ b′(M)
        <!-- draft: 447fd412 — a scaled copy of a marked drawing stamps at each block; what the stamp carries and which cells of a block's box it reaches combine, so each is its own point. -->
- A solver with one case has no `Choice`.
- A record-typed `Choice` holds one field per choice point; `impl_choice` lists the combinations these rules admit.
    - 87ab05b8 <!-- one marked cell among noise, and the output fills the 2×2 region that holds it; three ways to locate the region cross two sources of the fill color. -->

### Same model

Two candidates are the same model iff both hold:

- same parameterization — the free data that a sibling would reassign. Derived or materialized helper relations are not parameters.
- same outputs for every input under every assignment of that parameterization
    + A = B ⇔ Θ_A = Θ_B ∧ ∀θ ∀x. A(θ, x) = B(θ, x)
        + A and B — two models
        + Θ_A and Θ_B — their parameterizations
        + = between values of a partial function: both undefined, or both defined and equal

The test decides:

- Candidates that differ on either are different models.
- Candidates that match on both are two implementations of one model.
- Divergence in parameterization distinguishes candidates that coincide on the current task but parameterize different families.
    - 44f52bb0 <!-- the output is one of two stored grids, by whether the input has a stored symmetry, or, from a table of groups, the stored grid of the largest group that leaves the input invariant; the two agree on every input, the first is a two-entry assignment of the second, and they claim different priors. -->
- An OR fold is existence and an XOR fold is exact count: two concepts and two families, not one count-thresholded program with the threshold as a parameter (dae9d2b5 vs 34b99a2b).

### Table or rule

Table against rule is the main way in which hypotheses differ. Any relationship can be stored as a table (claiming a lookup prior) or written as a rule over composed primitives (claiming a compositional prior). The two claim different priors, and both get cases.

- Table siblings vary the table.
- Rule siblings vary the rule's parameters.
- 3b4c2228 <!-- the count renders both ways, as marks composed down a diagonal and as a stored grid per count. -->

### Subsumption

Divergence must be valid to count.

- **Ill-formed divergence.** When every divergence of a hypothesis from a peer is ill-formed (the output has multiple values or is not total), the hypothesis never fits a task that the peer misses, at any assignment of its parameterization. The peer subsumes it, and it gets no case. The subsumption is refuted when there is a divergence where the hypothesis is total and the peer is ill-formed.
    + (∀θ ∃θ′ ∀x. M(θ, x)↓ ⇒ M(θ, x) = M′(θ′, x)) ⇒ fam(M) ⊆ fam(M′)
        + M(θ, x)↓ — M defined at θ and x: `out` is a grid, total and single-valued
    - **Refused input.** A divergence at an input the hypothesis's premise excludes does not establish subsumption. A strict hypothesis and a tolerant peer that fold the same evidence differently are two families under Invariance scope, and each gets a case.
    - **Tabulation.** When another branch in the same case makes a rule hypothesis read every input from the parameters, that hypothesis computes a function of the parameters alone. Its tabulation is an assignment of the table peer, so it gets no case (21897d95).
        + ∀θ ∃θ′ ∀x. M_rule(θ, x)↓ ⇒ M_rule(θ, x) = M_tab(θ′, x)
            + M_rule and M_tab — the models of the rule hypothesis and its table peer
    - 99fa7670 <!-- each colored dot fills its line to one edge and then along that edge, where the next dot's fill occludes it; an unblocked ray diverges from that stepwise fill only by claiming two colors on one cell. -->
- **Partiality.** Partiality alone is not subsumption: a model that fails on some inputs but validly diverges on others is still a peer.

### Prior or setup

Cases are hypotheses about the prior that the task teaches.

- **precedent** (of a setup structure) — the encoding that the corpus already uses for it.
    - The solver that introduces or improves a structure's encoding sets its precedent.
    - A precedent covers how a structure is found and encoded, not the tests inside that encoding: which cells or lines qualify follows the task's concept, so a solver whose test differs still follows the precedent.
    - When two encodings of one structure stand in different solvers, the one that is not the precedent is a deviation, and a session notes it in the review.
    - Two encodings that stand as cases of one solver are peer parses, and neither is a deviation.
        - 1a6449f1 <!-- rings sit in noise, and the output crops one of them; `Outlines` finds a ring as a drawn rectangle and `Closed` as a wall that cuts a region off from the grid edge, each under its own case. -->
- Models that find different structures are different parses.
- **Setup priority.** A setup follows, in order:
    1. Fidelity.
    2. Reuse of the facts and lib instances the program already has (1190bc91).
    3. The structure's precedent (2dee498d, f25ffba3).
- **Peer priors.** The cases go to the peer priors. Two candidates that parse the task alike get a case only when they separate priors, regardless of their choice point.
    - 662c240a <!-- a stored symmetry, with the output the tile it fails on, against the existence of any symmetry. -->
- **Different parse.** A peer model that parses the task differently gets a case.
    - Two encodings parse the task differently when a rule of one reads an input cell that the other's structure omits.
        - A read of a structure's extents or place reads no cell.
        - A read that binds a position to a cell of the structure reads a cell.
            - Bound to the structure's own cells it is the same parse.
            - Over an unrestricted position it is a different parse.
        - A write through the structure as a frame reads no cell.
        - A rule that reads a cell of the box the set omits makes the box a different parse.
    - An encoding that finds the same structure over the same cells another way is the same parse. Same model decides whether it is a peer.

### Evidence

- **Exercised.** A peer model has rules, parameters, or comps that the current model does not. If no pair exercises them, that peer gets no case.
    - A pair exercises a part of the peer when that pair's output derives through it:
        - even where a narrower rule would give the same output on every pair
        - even where the part's result matches the current model's on every pair
            <!-- draft: 8ba14f53 — a third parse groups the cells into the same objects as the other two on every pair, and every pair's output derives through the components it adds. -->
    - Exercised tests only the parts the peer adds; a peer that adds none passes it.
- **No relational form.** A hypothesis gets no case when Fidelity excludes every encoding of it.
    - When a hypothesis's encoding depends on arithmetic and the lib addition protocol closes the primitive, that hypothesis has no relational form (`proposals/MinHops.md`).
- **Table entries.** A mapping table needs multiple entries exercised. A one-entry ring table over a plain border is unexercised.
    - 44f52bb0 <!-- both symmetry classes occur in the pairs. -->
- **Contradicted rule.** When some pair contradicts a rule that chooses one part of the input, that rule is excluded.
    - 87ab05b8 <!-- train pair 0 contradicts picking the marker by count, since every noise color is a singleton. -->
- **Determinable.** The parameters of a table hypothesis must be determinable from the train pairs and test inputs. The test outputs are held out.
    - **Unseen key.** A test key with no train entry rules out the table hypothesis.
        - 1fad071e <!-- the test count is 3 and the train counts are {2, 4}, so its table is ruled out. -->
        - 3b4c2228 <!-- the test counts are in the train set, so its table stands. -->
    - The correct output at that unseen key is evidence that the prior is compositional.

### Shared parameters

A parameter shared across two hypotheses asserts that one value serves both in every task that fits both.

- **Separate parameters.** If some task fits both hypotheses with no common value of the parameter, it refutes that assertion.
    + ∃T ∈ fam(A) ∩ fam(B). ¬∃θ ∃θ′. A(θ) ⊨ T ∧ B(θ′) ⊨ T ∧ θᵢ = θ′ᵢ
    - 87ab05b8 <!-- each of the three ways to locate the region reads its own parameter, a part count or a size, all 2 in this task, because a 6×6 sibling sets the part count to 3 and the sizes to 2. -->
- **One parameter.** When no such task exists, one value serves both, and they share one parameter.
    - d23f8c26 <!-- one column of an odd-width grid is kept, as the center line on a stored axis or as the gap of a two-way divide on that axis, and any task that fits both fits them at one axis value. -->

A shared parameter also requires a shared form: both hypotheses read its value in the same vocabulary.

- When the consumers differ, each hypothesis has a per-case parameter in its consumer's form.
    - 2013d3e2 <!-- the output is a corner region of the bounding box of the non-background cells, stored as a tile position for the case that divides the box into quadrants and as a corner for the case that places a fixed window there. -->
- A shared parameter that a case must convert fails the Indirection test.
