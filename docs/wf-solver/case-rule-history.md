# Case inclusion: the decision history

What decided which models become cases in a `.dl` solver, from the first "Coverage" principle on.

## 2026-05-07 — Coverage enters (eefe6e0)

`docs/wf-solver/3-principles.md` gains a third principle beside Fidelity and Invariance. The commit message says: "Add Coverage principle to 3-principles (multiple modeling forms via ADT Choice; data/op framing)."

The rule on how many cases:

> Useful coverage gives one model per plausible family. The prior becomes visible from each plausible angle.

The axis along which models differ:

> At any choice node, a choice can lean toward data (flatten) or toward ops (expose). Different op compositions of the same task are also distinct models — coverage extends within op-leaning territory.

## 2026-05-18 — alt model against alt impl (849f681)

A same-model test enters, so that a re-implementation gets no case.

> Two candidates are the same model iff (a) same Consts shape — same parameters, field types, relations — and (b) same outputs for every (input × Consts-value) in that shape. Different on either → different models.

> Op compositions split the same way: re-decomposing the same property over the same Consts is an alt impl. Coverage extends within op-leaning territory only when an op composition commits to a different Consts shape.

Worked examples cover 44f52bb0 `$Direct` against `$GroupMatch`, 34b99a2b `$SetMatch` against `$Xor`, and three same-model bodies for 44f52bb0 `$Direct`.

## 2026-07-03 — the failure Coverage guards, and the evidence gate (e7bb3ba)

The doc moves to `docs/wf-solver/principles.md`. Coverage is named as a guard:

> - **Coverage** — the solver commits to one family where the train pairs support several.

A new rule bounds cases by evidence:

> **Claims are evidence-gated.** Claims the data cannot distinguish all stay — that is what coverage is for (a passthrough interior vs a repainted one, 6f8cd79b). A claim the data barely instantiates doesn't earn a case: a mapping table wants multiple entries exercised (44f52bb0's groups both fire; a one-entry ring table over a plain border sits unexercised), and an identification rule dies when some pair defeats it (87ab05b8 train 0 defeats count-based marker identification — every noise color is a singleton).

The alt-impl rule becomes an instruction: "so don't propose alt impls."

## 2026-07-10 — three more gates (9a222a5)

Three rules are added to Coverage. Each removes a case.

1. The relabeled twin:

    > The criterion compares maps, not swept task sets. A body that relabels its own coordinates — measuring from `opposite(D)` where another measures from `D` — sweeps the same tasks at different Consts values, so the checklist counts it as a different model. The relabeled twin adds no coverage; do not write one.

2. Subsumption by invalid divergence:

    > When every divergence of a claim from a sibling is ill-formed — multivalued or empty — the claim never fits a task the sibling misses; the sibling subsumes it, and it gets no case (99fa7670's line fill). Partiality alone is not subsumption.

3. Concept against setup:

    > Cases are claims about the prior the task teaches. Setup is structure that every candidate claim stands on. […] A same-model separation gets a case only when it separates priors. The boundary runs along consumption: variants whose output every rival claim reads identically are setup; a node that parameterizes the transformation itself splits data vs ops and gets cases.

The evidence gate also gains the unseen-key rule: "A test key absent from the train-exhibited entries rules out the table claim" (1fad071e against 3b4c2228).

## 2026-08-12 to 2026-09-03 — Coverage is amended five times

1. **2026-08-22 (466cb65).** Closure removes no case. "Closure settles encoding, not coverage: it removes no case. A membership set some sibling refills is task data even when this task's fill coincides with a structural class." The commit message gives the ground: 14754a24, whose plus footprint a T-completing sibling would refill.
2. **2026-08-22 (f1abd20).** Among setup variants, the one case goes to "the pin whose facts the body already reads (1190bc91)", and "The settled shape ranks below fidelity and reuse".
3. **2026-08-29 (ae53bad).** Tabulation. "An ops claim whose inputs a co-chosen decision pins to stored data computes a function of Consts; its tabulation is a fill of the data rival, so it gets no case (21897d95)."
4. **2026-09-03 (69d071f).** The evidence gate is restated as a separation. The commit message says the gate "was a list of admitted and refused claims with no statement of what separates them." The new lead: "A rival that reads the task differently gets a case. A rival whose added machinery no pair exercises gets no case." The same commit scopes subsumption to any fill of the parameterization, and adds "A variant that stands on different input structure is a different reading and gets a case; a variant that finds the same structure another way is a pin."
5. **2026-09-03 (69d071f).** No relational form. "A claim with no relational form gets no case: when its encoding rests on arithmetic and the lib addition protocol closes the primitive, the claim goes with it."

## 2026-09-05 to 2026-09-08 — restructure and rename

The prose paragraphs become rule lists with run-in titles, so a review can cite a rule by name (f5b168a, 06f2780, 27a1f81, dbf87b3, 647508d, b4b6088). `f42c17b` renames the vocabulary: claim becomes hypothesis, Consts becomes the parameters, body becomes the program. Coverage now reads:

> A few train pairs underdetermine the family. Coverage is one case per model that the rules of this section admit.

Its subsections are Same model, Table or rule, Subsumption, Prior or setup, Evidence, and Shared parameters.

## 2026-09-09 — cases go to every open divergence (d683be5)

The commit message states the ruling: "Cases go to every model divergence the pairs leave open, so the reparameterization exception is gone."

- The **Reparameterizations** rule is deleted. It had said: "A setup has reparameterizations, and together they get one case."
- Subsumption gains a refutation: "The subsumption is refuted when there is a divergence where the hypothesis is total and the peer is ill-formed."
- Exercised is widened: "A peer model has rules, parameters, or comps that the model at hand does not. If no pair exercises them, that peer gets no case."

## 2026-09-10 — the rules get an order (966ea9c)

> The rules of this section apply in order: Prior or setup, then Evidence, then Subsumption. A peer that Evidence removes gets no case, even when it subsumes the model at hand.

Exercised is widened again: "A pair exercises a part of the peer when that pair's output derives through it, even where a narrower rule would give the same output on every pair."

## 2026-09-11 (dfafe6c) and 2026-09-13 (f306e00)

- **Refused input.** "A divergence at an input the hypothesis's premise excludes does not establish subsumption. A strict hypothesis and a tolerant peer that fold the same evidence differently are two families under Invariance scope, and each gets a case."
- **Multiple derivations.** "Several derivations of one stored value are peer models of each other, and the Coverage rules decide each on its own."
- **Exercised**, second widening: "even where the part's result matches the model at hand's on every pair. Exercised tests only the parts the peer adds; a peer that adds none passes it."
- **Different parse** gets a cell-level test: "Two encodings parse the task differently when a rule of one reads an input cell that the other's structure omits."

## 2026-09-13 — the Coverage rules are declared open (b3bedbd)

`docs/wf-solver/open/` collects the open questions. Four of them are about case inclusion.

- `coverage-rules.md` — three gaps in one section: whether an Exercised pass admits a case or only defers it; whether the first rule that removes a peer settles it; and what size a "part" has. It records that three approved solvers hold a case the narrow reading removes (8e5c0c38, 1a6449f1, 4c416de3), and lists drafts whose case count changes under each reading: 9720b24f gives 2 cases or 4, 8a6d367c gives six combinations or twelve.
- `peer-priors.md` — "The rule gives a case to two candidates that parse the task alike only when they 'separate priors', and no rule says when two candidates do." It counts the approved corpus on both sides and lists about twenty drafts whose cases turn on the answer.
- `different-parse.md` — whether the parse test ranges over structures or over input cells.
- `unchanged-output.md` — whether an output equal to the input is a valid divergence.

## 2026-09-15 — the theory overhaul removes Coverage (fbd9023)

The commit message states it: "Principles: the generator theory replaces coverage by subsumption. A case stands unless it fails Fit, Fidelity, or Equivalence."

The whole Coverage section, `docs/wf-solver/open/coverage-rules.md`, and `peer-priors.md` are deleted. A `## Cases` section replaces them:

> **No other removal.** A case is included exactly when it passes all of these tests: Fit, Fidelity, Equivalence.

1. 2026-09-15T12:10Z, user: "i'm concerned we're overcomplicating when to keep a case. what's the overarching principle that's describing when a case makes sense? like from the human perspective. … it's a constraint that cases should account only for what the task generator would generate (if such a generator existed)."
2. 2026-09-15T13:14Z, user: "i guess another less important reason for coverage is to cover whatever is possible and conceivable. so i'm considering keeping it all in code but labeling/ranking the [good-ness] of cases."
3. 2026-09-16T00:43Z, user: "i went with ranking bc i couldn't decide on the boundary to draw on whether to keep or drop cases".
4. 2026-09-16T02:17Z, user: "the other goal of ranks is to allow keeping around 'dead' cases for the sake of further coverage (and i guess so we don't spend so much effort deliberating over whether to keep or drop cases)".
5. 2026-09-16T02:58Z, user, the fullest statement:

    > "1. yes i couldn't decide which was primary/intended
    > 2. i wanted coverage of possible generators of task
    > 3. i no longer want deliberation over keep/drop by judgment, but i still want a way to classify or rank how far off the case is (deviation) so we can weigh the cases appropriately in whatever future work will consume them
    > 4. i might as well keep around implausible cases for the sake of more code diversity as that can help with ML things"

6. 2026-09-17T00:08Z, user: "the purpose of all that annotation was to have data that could help with ranking the deviation of cases instead of binary inclusion/exclusion."

So the judgment gates are replaced by a per-branch grading. The same commit adds a `Deviation` section with three counts — `relaxed`, `added`, `contradicted` — that a branch carries.

## 2026-09-15 — the review's duty per dropped peer (bc8d4dd)

> - The test a dropped peer fails decides what that peer owes.
>     - A peer dropped under Fidelity owes a witness.
>     - A peer dropped under Equivalence owes the statement that no witness exists.
>     - A peer that fails Fit stays out of the review.

## 2026-09-17 — the counts become plausibility and verdict (89097b7)

The three counts are cut. Two annotator judgments replace them: `plausibility`, an ordinal over `ordinary`, `variant`, `borderline`, `foreign`; and `verdict`, the output the annotator thinks the generator would pair with the witness. The user asked for the term audit that produced both names and ruled on each by agreeing (2026-09-16T13:52Z, 13:57Z, 13:59Z).

## 2026-09-17 — the conditions are named, and a peer that meets them is not dropped (5eb0934)

The commit message: "principles.md names Fit, Fidelity, and Equivalence the case conditions. procedure.md's review says not to drop a peer that meets them, for any reason."

The sequence:

1. A create pass on 9aec4887 reported: "Two peers meet that letter and I left them out … because I judge that no person forms them from these pairs. If plausibility of the model is a gate, the section needs the sentence; if it is not, both are cases and the solver is short by two."
2. The user ruled on the merits (02:04Z): "i saw StoredTies and FullRuns. they're out there but i would think of that when thinking of variations of the task. […] i wouldn't from these pairs, but i would if i thought more generally".
3. A first fix added a **Variations** rule to principles.md Cases:

    > - **Variations.** A branch that a person forms from a variant task alone is a case.
    >     - A branch that changes a scene claim is formed from the pairs.
    >     - A branch that changes rules alone is formed from a variant task: an input the pairs do not contain, on which the branch differs from the concept branch.
    >     - That the pairs alone do not suggest a branch is no ground to leave it out.
    >     - 2d0172a1

4. The user asked whether the procedure line alone would do (02:28Z), then ruled (02:29Z): "do not drop a peer for any raeson if it passes". The Variations rule was reverted out of principles.md, and procedure.md kept one line.
5. The user asked for a label (02:30Z, 02:31Z). The result: principles.md bolds "**case condition**", and procedure.md says "Do not drop a peer that meets the case conditions, for any reason."

## 2026-09-18 — a witness needs the concept case defined (2ba3d0b)

A finalize pass on 9aec4887 asked whether an input where the concept case is undefined and a peer gives a grid is a divergence. The user saw the consequence (03:29Z):

> "there exists a witness input that diverges for two models, and the main case is undefined? allowing that to be the case, i think makes it possible to make any case you want bc you can make any task you want as long as you can find two cases under that task that diverges"

And again (03:35Z):

> "we can invent contrived models by tacking on rules? which is actually whats happening here?"

The session agreed and named the mechanism: any rule that is inert under the scene claims can be tacked on, and it yields a fitting, non-equivalent model. The user ruled "1. amend" (03:36Z). Two definitions in principles.md were narrowed:

> - **divergence witness**: an input on which the concept case is defined and …
> - Two models … are equivalent when they give the same output for every assignment and every input on which the concept case is defined.

A source comment states the consequence: "A model that agrees with the concept case on every input on which the concept case is defined has no witness against it, whatever it gives elsewhere."

This is the bound on the unbounded-peer construction as of 2026-09-18. It closes the construction when the base model is the concept case. A handbook agent checked it on 2026-09-18 (session 214e711f) and reported two residual holes: a peer built off a non-concept case, and a peer whose added rule brings its own parameter, since `EquivalentAcross` needs a bijection between the two parameterizations and none exists when they differ in size. In that second hole, style.md's rule that "Every other branch has at least one `@witness` line" is what stops the branch being written. The user did not rule on that finding.

## 2026-09-18 — "drop" becomes "omit from the solver"

A finalize agent read the Drops rule as a rule about the review, not about solver membership (session 91c7364a, 13:30Z). Its own words:

> "I read 'Drops' as a rule about what the review must list, not about solver membership."

Its grounds were that the bullet sat under the Review question "Are there potential peer models?", beside a bullet about listing, and that procedure.md's review item "A case to keep or add" implies the user adds the case.

The user (13:34Z): "what if we just chose a more precise/conventional word than 'drop'". Then the user wrote the line himself (13:37Z):

> "- If a peer meets the case conditions, do not omit from the solver."

The working tree carries it with "for any reason" restored:

> If a peer meets the case conditions, do not omit it from the solver for any reason.

The case check also moved from Review into Create, as step 5: "Check that the cases are exactly the models that meet the case conditions."

## 2026-09-18 — the open-ended lattice of weaker readings

A create pass on 9bbf930d left out every weaker reading of its `pipes` scene claim. Its report (session 14d1acbd, 15:50Z):

> "I did not add cases because the set of subsets is open-ended, and the weaker readings only differ from the concept on a pipe that is not drawn as one … I judged its plausibility borderline. […] That is the stretch I named: the letter of 'do not omit a peer that meets the case conditions' would include at least the 'open side inside a pipe' reading. I resolved it by reading the case conditions as applying to hypotheses a person could form."

The session that reviewed it rejected each ground: plausibility is not a case condition; the Witness sentence about `ordinary` plausibility says when a witness indicts the concept case, not when a branch belongs; "hypotheses a person could form" is not in the docs. It named the real gap:

> "Weaker statements of one scene claim form an unbounded set of peers, and the handbook gives no rule that bounds them."

The user's response (15:57Z reply) set four follow-ups, one of which still needed a ruling as of 2026-09-22: "a rule for the unbounded set of weaker claims, which needs your ruling." That rule was not yet written.

## What the removed Coverage rules said that Cases does not

The session audit at 2026-09-18T02:18Z (8aba312e) mapped each old gate to its status at that time.

1. **Peer priors** — "Two candidates that parse the task alike get a case only when they separate priors." Gone with no replacement. It was the gate sessions used most: 16 drops in the draft inventory. The word "prior" is gone from the docs.
2. **Different parse** — "A peer model that parses the task differently gets a case." It was an admission, not a removal. Equivalence covers it, and the parse definitions survive under Definitions and Parse priority.
3. **Subsumption, ill-formed divergence** — a hypothesis whose every divergence from a peer was undefined got no case. The docs reject this on purpose: "Fit considers only the pairs. Being undefined on another input does not prevent a model from fitting."
4. **Tabulation** — a rule branch whose inputs another branch pinned to stored data got no case (21897d95). Nothing replaces it. The nearest survivor is Redundant value.
5. **Exercised** — "If no pair exercises a peer's added rules, parameters, or comps, that peer gets no case." Gone. Its final letter had been widened twice, so it counted almost every peer as exercised; sessions kept applying a narrower reading than the letter.
6. **Table entries** — "A mapping table needs multiple entries exercised." Gone.
7. **No relational form** — a hypothesis Fidelity excluded got no case. Instead, a case stays under an `@approximated:` line with witnesses. The Fidelity condition still removes a model whose every encoding Fidelity excludes.
8. **Contradicted rule** — a pair contradicting a rule excluded it. Absorbed into Fit.
9. **Determinable and Unseen key** — kept, as Fit's Unseen key and the determination's held-out test outputs.
10. **Reparameterizations** — removed earlier, at d683be5 on 2026-09-09.
11. **Relabeled twin** and **same model** — the same-model test became the Equivalence condition, with the formal definitions of equivalence and isomorphism under Definitions.
12. **Ordered application** — "The rules of this section apply in order … A peer that Evidence removes gets no case, even when it subsumes the current model." Moot, since one rule set replaced three.
13. **Concept against setup** — the case-removing half is gone. The setup vocabulary survives as Parse priority under Corpus consistency, which ranks Fidelity, reuse, and precedent, and decides an encoding rather than a case.

The net: the old section held about ten grounds on which a fitting peer got no case. The Cases section holds three conditions, and none of them is about whether the evidence makes the peer worth stating. The rules that carried that judgment are gone by intent, so that a session does not deliberate. The cost is the gap the two sessions on 2026-09-18 both hit: nothing bounds the set of peers built by weakening a scene claim or by tacking on a rule that fires only where the concept case is defined but no pair reaches.

## 2026-09-18 — peer models move out of the review and into Create (82e626b)

The Review question "Are there potential peer models?" is deleted. Its two bullets move into Create as step 5:

> 5. Look for peer models, and make the cases exactly the models that meet the case conditions.
>     - If you find a model that meets the case conditions, add it.
>     - For each parameter, try the model that derives its value from the input.
>     - For each input-derived value constant across pairs, try the model that stores it in a parameter.
>     - Do not propose, and do not list in the review, a model equivalent to the model of a case the solver already has.

The same commit creates a `Witness` operation and deletes the review's duty for a peer dropped under Equivalence ("requires the statement that no witness exists"). So the last trace of the 2026-09-15 per-condition duty (bc8d4dd) is the Fidelity one.

## 2026-09-19 to 2026-09-21 — the handbook overhaul

The solver docs move to `docs/handbook/` (e395e8a) and are rewritten in the controlled format, one claim per line (9cb6d5b, 7d91713, b3a61a4, 986202b, 99023df). The Cases rules are not changed in substance. Two edits touch case membership:

- **986202b.** The review loses "A model equivalent to the model of a case the solver already has stays out of the review", and the rule about what stays out of the review becomes "A model that fails Fit or Equivalence stays out of the review, including any note that it was considered."
- **da30cfe, 2026-09-21.** The Principles goal is restated as two ordered aims:

    > - The goal is for the corpus to take as much as it can from each task, in this order:
    >     - **Concept.** The solver expresses the task as a person sees it, as closely as possible.
    >     - **Coverage.** The solver also expresses alternative ways to see the task, for the diversity of ways of writing a solver.

    This is the first time since fbd9023 that the word "Coverage" names a goal rather than a deleted section. The earlier wording, in place since before the overhaul, was "The goal is for a solver to express a task in a way that matches a person's understanding as closely as possible, and for the corpus to extract as much as possible from the tasks."

## 2026-09-22 — the working tree

### Θ is redefined as what the generator gives

`9f236235` create reported, as its callout 2, that the isomorphism clause is vacuous when the two parameterizations have different cardinalities, so every such pair counts as non-equivalent. `9f27f097` create reported, as its callouts 2 and 3, that a narrowed parameter domain makes a distinct model under the letter:

> "The Equivalence condition, read to the letter, makes any narrowing of a parameter's domain a distinct model: 'mirror = flip_of(stored axis)' is not equivalent to `Fixed` only because `Fixed` ranges over all eight D4 values."

The user asked for a resolution that stays consistent (2026-09-22T05:31Z, "ultrathink on resolution and if it will be consistent"), then "apply and then review as before" (05:38Z). The definition became:

> - **parameterization**: the parameters together with the values each one takes across the generator's tasks.
>     - Θᵢ: the values parameter i takes across the generator's tasks
>         - A parameter's type is its encoding, and a value of the type that no task gives is outside Θᵢ.

A first proposal that would have made the allowed values a judgment rather than a choice point was retracted: it contradicted the approved solver 14754a24, which keeps both `Plus` and `Shape`.

### Equivalence becomes two-way agreement

The isomorphism between parameterizations is deleted. The user's question on the shape of the replacement (04:34Z): "so it's like a 'partial' 'bijection'? like the intersectino of two partial fns?" and "is it narrowing or widening? or ruling over a gap?". The ruling (04:36Z): "go, then review doc for consistency". The result:

> - Two models are equivalent when each assignment of either has an assignment of the other that it agrees with.
>     - Equivalent(A, B) ⇔ (∀θ ∈ Θ. ∃φ ∈ Θ′. Agree(θ, φ)) ∧ (∀φ ∈ Θ′. ∃θ ∈ Θ. Agree(θ, φ))
>     - Two assignments agree when, on every input on which the concept case is defined, the two models give the same output or one of them gives none.
>         - Agree(θ, φ) ⇔ ∀x ∈ G_C(θ). A(θ, x) = B(φ, x) ∨ A(θ, x) = ∅ ∨ B(φ, x) = ∅
>         - G_C(θ): the inputs on which the concept case is defined at θ
> - An assignment that agrees with no assignment of the other model refutes equivalence, and a divergence witness against each of those assignments shows it.

Two consequences follow, and both remove cases:

1. A strengthening that is undefined where the concept case is defined agrees with the concept case, so it is equivalent and gets no case. This answers `9f236235` create's callout 3: "a model that adds a precondition to the concept case, and is otherwise identical, diverges only by being undefined where the concept case is defined. Read literally, that is a divergence … The docs need a boundary for strengthenings that compute nothing new."
2. The divergence witness definition is narrowed the same way: "two models each produce an output at some assignment, and the outputs differ."

`G_C(θ)` survives the rewrite. The 2026-09-18 bound (2ba3d0b) is therefore intact: the comparison still ranges over the inputs on which the concept case is defined, and no further.

### The two explicit lines added under Equivalence and under Terms

Four console passes argued that a peer whose divergence lies off the scene claims is not a separate claim.

1. **9f41bd9c create**, callout 6: "I read the Cases Equivalence condition more loosely than its text. Bounding the scrape by the tips that touch the ground and bounding it by the comb's lowest line are not equivalent — a comb floating one line above the ground separates them … I treated them as one claim stated two ways, since scene claim `comb` reconciles them; the tighter reading makes the peer a second branch."
2. **9f41bd9c refine**: "My earlier handoff had dropped three peers on one reason — they part from the concept case only off the scene. That reason is void, so `Below`, `Cast`, and `Lowest` all went in as branches."
3. **9f5f939b create**, callout 2: "The handbook gives no rule for a peer model whose divergence from the concept shows only on inputs that break a scene claim, and I spent most of the pass on it. The `Sight` choice point exists only because the Equivalence condition ranges over every input on which the concept case is defined, so a redundant-under-the-scene-claim test is formally a case; by that letter, the center-is-blank and arm-is-exactly-two tests are cases too, and I left them out."
4. **9f5f939b refine**, callout 3: "By the letter of the Equivalence condition, `Clear` is a case and so are the centre-is-blank and arm-is-exactly-two tests; I included the first and excluded the others on the ground that a case must be a way of seeing the task, and the principles do not state that test."

The user's rulings:

- 13:49Z: "i mean, i dont want agents arguing with the docs. yes the handbook answers it but can we make it more explicit?"

The first line, under Equivalence:

> - Agreement on every input the generator produces does not establish equivalence either: the comparison ranges over every input on which the concept case is defined, whether or not the input breaks a scene claim.
>     - 00dbd492
>         - The two readings of an object's empty region part only where the outline is broken, an input the generator never produces, and each reading is a case.
>     * comment
>         - The 9f41bd9c create and refine sessions read a scene claim as narrowing the comparison, and dropped a peer that parts from the concept case only off the scene.

The second, under Relational form's Terms rule:

> - **Terms.** When two sets of clauses each have the relational form of a rule, the program takes the one stated in the rule's own terms.
>     * comment
>         - The program with the other set is a peer model, and the case conditions decide whether it is a case.
>             * comment
>                 - The 9f41bd9c refine session read Terms as excluding the other set from the cases.

### Judgment is not grounds for omitting a case

procedure.md Develop step 3 gains:

> - If you find a model that meets the case conditions, add it.
>     - Your own judgment or taste is not grounds for omitting it.

This is the third statement of the 2026-09-17 ruling ("do not drop a peer for any raeson if it passes"), after principles.md's **case condition** label and procedure.md's "do not omit it from the solver for any reason".

### Fidelity as a case condition becomes Relational form

The third case condition was "**Fidelity.** The model has an encoding allowed by Fidelity." It becomes:

> - **Relational form.** Each claim the case's branches replace or add has a relational form.

procedure.md follows: "A peer dropped under Relational form requires in the review why no set of clauses states its claim." The Necessity rule in lib-protocol.md loses "Remove the case whose hypothesis has no relational form without that comp."

This edit came from 9ddd00f0 refine, which used `@approximated` on a branch. The user (02:41Z): "i remember a past discussion where we decided to allow it bc it was theoretically possible that the approximation only applied to a branch and the solver could not do with out it. but wdyt", then (02:49Z) "not sure we're on same page. how about this: under your proposal, would this be possible?", then (02:50Z) "ok i agree with you. propose edits".

### The runner holds cases the solver does not write

`@derive` and `@store` directives enter solver-file.md. The runner holds the derived or stored reading of a parameter as a case, and the solver writes no branch for it. `@ignore: derive` and `@ignore: store` dismiss one. The derive report holds a case only when the concept case reads the parameter.

This is the first machinery that adds a case without a session judging it.

### The boundary discussion

The user opened it at 14:44Z, after the four passes:

> "is there another way in between? think about the intention of 00dbd492 having that foreign witness. ultrathink on possible resolutions that balances coverage (which is emerging to be ways of 'enumerating' the Things of arc grounded in task data) with a reasonable boundary. it can even be an effort/thought boundary, like after N rounds (maybe N=1) stop including new cases you think of, ie only include cases you thought of initially, if you thought of more then dont include?"

He refused the first proposal as imprecise (14:56Z):

> "im warm to the direction of your proposal but it feels imprecise and relies on enumerating examples. ideally we would force the thing to be written out like a claim or rule or scene thing so the deliberation goes to actually discussing the things in a solver instead of 'the docs rule that thingness is X but Y under tight reading', ultrathink some more on it how to make it mroe grounded"

Then he restated the goal (15:10Z):

> "wait ok we need to start from the top to make sure we're aligned with the goal and that the goal is clear in the first place. the principles wrote down goals but i think i stated something different and more important. the enumeration of all arc things.
>
> and the point of cases is to give SIGNAL towards that. and even if the case is 'out there', if it's still a new arc thing and the agent thought of it, we won't say no to that.
>
> whereas i believe you're pointing out there's a NOISE kind of thing happening here. repetition of varying guard subclauses?
>
> and then there's this mechanical aspect you're talking about? that's always reliable, whatever tooling can check and rule out if its aligned wt he goal
>
> but first lets ensure the goal is clear and the docs are aligned with it (and it may involve updating procedure)"

And asked for the term to be found rather than illustrated (15:14Z):

> "wait we don't have to call it 'things of ARC'. ultrathink on what im gesturing at. what is the 'thing'. and look for a way to avoid enumerating examples of thing (structure number ...). or at least ensure it is exhaustive, and to choose the highest level way to enumerating. lets establish idea first. dont propose wording until we get to that point"

## Assessment of the 2026-09-22 proposal

The proposal has four parts.

- **Goal.** The corpus enumerates the things of ARC, grounded in task data. A case is signal toward that enumeration.
- **Thing.** A reading of a task with two aspects: the claims the solver makes, and the encoding those claims are stated through.
- **Signal.** A case differs from the concept case by a claim the concept case's claims do not already imply, or by an encoding the concept case does not use.
- **Noise.** A guard — a branch whose clauses are the concept branch's with body atoms added or removed, each added atom over a relation the concept branch reads, and whose every witness carries `@relaxed` — gets no case.

Equivalence is unchanged, and an audit computes the clause difference per branch and reads the `@relaxed` lines.

### Rule by rule

| Rule | Adopted / removed, with the recorded reason | Proposal |
| --- | --- | --- |
| Coverage, one model per plausible family (2026-05-07, eefe6e0) | Adopted: "Useful coverage gives one model per plausible family. The prior becomes visible from each plausible angle." Removed 2026-09-15 (fbd9023): "the generator theory replaces coverage by subsumption." | Restates. The goal clause is the same aim without the word "plausible", which the 2026-09-17 ruling had already stripped. |
| Alt model against alt impl (2026-05-18, 849f681) | Adopted: "Op compositions split the same way: re-decomposing the same property over the same Consts is an alt impl. Coverage extends within op-leaning territory only when an op composition commits to a different Consts shape." Became the Equivalence condition (fbd9023). | **Reverses.** The encoding clause makes a re-decomposition over the same parameterization a case, which this rule named as exactly the thing that gets no case. |
| Evidence gate (2026-07-03, e7bb3ba) | Adopted: "A claim the data barely instantiates doesn't earn a case." Removed 2026-09-15 with all of Coverage. | **Reverses in part.** "Grounded in task data" reads like the evidence gate, but the signal clause has no instantiation test, and the proposal keeps "do not say no to a new thing". The two pull opposite ways. |
| Relabeled twin (2026-07-10, 9a222a5) | Adopted: "The relabeled twin adds no coverage; do not write one." Became Equivalence. | Restates, through Equivalence, which the proposal keeps. |
| Subsumption by invalid divergence (2026-07-10, 9a222a5) | Adopted: "When every divergence of a claim from a sibling is ill-formed … the sibling subsumes it." Removed 2026-09-15; the text as of 2026-09-22 rejects it: "Fit considers only the pairs. Being undefined on another input does not prevent a model from fitting." The Agree clause of 2026-09-22 re-admits the undefined side, but only as agreement, not as subsumption. | Orthogonal. |
| Concept against setup (2026-07-10, 9a222a5) | Adopted: "A same-model separation gets a case only when it separates priors. The boundary runs along consumption." Case-removing half removed 2026-09-15; the vocabulary survives as Parse priority, which decides an encoding, not a case. | **Reverses.** The proposal's encoding clause makes the encoding decide a case, which is the half that was cut on purpose. |
| Closure removes no case (2026-08-22, 466cb65) | Adopted: "Closure settles encoding, not coverage: it removes no case." | **Reverses in direction.** That rule said encoding does not decide coverage. The proposal says encoding creates signal. It does not remove a case, so the conflict is one of principle rather than of outcome. |
| Tabulation (2026-08-29, ae53bad) | Adopted: "its tabulation is a fill of the data rival, so it gets no case (21897d95)." Removed 2026-09-15; the nearest survivor is Redundant value. | Orthogonal. |
| Peer priors (through 2026-09-03, 69d071f) | Adopted: "A rival that reads the task differently gets a case. A rival whose added machinery no pair exercises gets no case." Removed 2026-09-15. The 2026-09-13 open question (`peer-priors.md`) recorded that "no rule says when two candidates do" separate priors. | **Restates the first half, reverses the second.** The signal clause is "reads the task differently" with a stated test. The guard rule revives "added machinery no pair exercises" under a new test. |
| No relational form (2026-09-03, 69d071f) | Adopted: "A claim with no relational form gets no case." Became the Fidelity case condition, and on 2026-09-22 became the **Relational form** condition, restated per claim. | Orthogonal. The proposal does not touch it. |
| Reparameterizations (removed 2026-09-09, d683be5) | Removed: "Cases go to every model divergence the pairs leave open, so the reparameterization exception is gone." The deleted text had been "A setup has reparameterizations, and together they get one case." | **Reverses.** The guard rule is a new exception of the same shape: a family of branches that differ only in one dimension collapses to one case. |
| Exercised (2026-07-10, widened 2026-09-10 and 2026-09-13, removed 2026-09-15) | Adopted: "A peer model has rules, parameters, or comps that the model at hand does not. If no pair exercises them, that peer gets no case." Removed with the note that "its final letter had been widened twice, so it counted almost every peer as exercised; sessions kept applying a narrower reading than the letter." | **Reverses.** This is the closest prior form of the guard rule. See below. |
| Table entries (2026-07-03) | Adopted: "a mapping table wants multiple entries exercised." Removed 2026-09-15. | Orthogonal. |
| Determinable and Unseen key (2026-07-10) | Kept, as Fit's Unseen key and the determination's held-out test outputs. | Orthogonal. |
| Contradicted rule | Absorbed into Fit. | Orthogonal. |
| Different parse (2026-09-13, f306e00) | Adopted as an admission: "Two encodings parse the task differently when a rule of one reads an input cell that the other's structure omits." The 2026-09-13 open question `different-parse.md` asked whether the test ranges over structures or over input cells and was never answered; it went with Coverage on 2026-09-15. | **Restates, and picks the unanswered side.** The proposal's encoding clause is the structure reading of that open question. That question was still open on 2026-09-22. |
| Ordered application (2026-09-10, 966ea9c) | Adopted: "A peer that Evidence removes gets no case, even when it subsumes the model at hand." Moot since one rule set replaced three. | **Restates the need.** Signal and noise can both hold of one branch, and the proposal does not say which wins. |
| Refused input (2026-09-11, dfafe6c) | Adopted: "A divergence at an input the hypothesis's premise excludes does not establish subsumption. A strict hypothesis and a tolerant peer that fold the same evidence differently are two families under Invariance scope, and each gets a case." | **Reverses.** A guard is exactly a strict hypothesis beside a tolerant peer. This rule ruled that both get a case. |
| No other removal (2026-09-15, fbd9023) | Adopted: "A case is included exactly when it passes all of these tests: Fit, Fidelity, Equivalence." User's ground (2026-09-16T02:58Z): "i no longer want deliberation over keep/drop by judgment". | **Reverses.** The guard rule is a fourth removal test. Whether it needs judgment turns on whether the audit can compute it. |
| Do not omit a peer that meets the conditions (2026-09-17, 5eb0934; restated 2026-09-18 and again 2026-09-22) | Adopted on the user's own words (2026-09-18T02:29Z): "do not drop a peer for any raeson if it passes". | **Restates the goal half, reverses the letter.** "We won't say no to a new thing" is this rule. A fourth removal test means some peers that meet the three conditions are omitted. |
| Variations (added and reverted 2026-09-18, 5eb0934) | Proposed: "A branch that a person forms from a variant task alone is a case. … That the pairs alone do not suggest a branch is no ground to leave it out." Reverted after the user ruled that the procedure line alone would do. | Restates. The proposal's "out there is still signal" is the same claim. |
| Witness and equivalence narrowed to `G_C` (2026-09-18, 2ba3d0b) | Adopted on the user's ground: "allowing that to be the case, i think makes it possible to make any case you want bc you can make any task you want as long as you can find two cases under that task that diverges". | Restates. The proposal keeps Equivalence over every input on which the concept case is defined. |
| The unwritten weaker-claims rule (open since 2026-09-18) | Never written. The gap: "Weaker statements of one scene claim form an unbounded set of peers, and the handbook gives no rule that bounds them." | **Answers it.** The guard rule is the first written bound on that set. Note that the 9bbf930d case that raised it was a set of *weaker* readings, and the proposal's guard rule covers atoms added *or removed*, so it covers that case. |
| The scene-claim comparison line (2026-09-22, uncommitted) | Adopted on 2026-09-22 against four passes that read a scene claim as narrowing the comparison: "the comparison ranges over every input on which the concept case is defined, whether or not the input breaks a scene claim." | **Reverses.** The noise rule uses `@relaxed`, which marks a witness that breaks a scene claim, to remove a case. That is the reading this line was written to refuse, earlier on 2026-09-22. |

### The reversals, in one list

1. **Alt impl (2026-05-18).** The encoding clause makes a re-decomposition over the same parameterization a case. The rule said that is an alt impl and gets no case. The Terms comment of 2026-09-22 moves partway, but routes the other clause set through the case conditions, and Equivalence still excludes it.
2. **Closure removes no case (2026-08-22) and Concept against setup (2026-07-10).** Both said encoding does not decide a case. The encoding clause says it does.
3. **Exercised (2026-07-10 to 2026-09-15) and Refused input (2026-09-11).** The guard rule is their subject matter with the verdicts inverted between them: Exercised removed such a peer, Refused input kept it, and the proposal removes it.
4. **Reparameterizations (removed 2026-09-09).** The guard rule is a new collapse-a-family-into-one-case exception, whose removal was the stated reason for that commit.
5. **No other removal (2026-09-15) and the do-not-omit ruling (2026-09-17, restated on 2026-09-22).** A fourth removal test.
6. **The scene-claim line added on 2026-09-22.** `@relaxed` as a removal signal contradicts it directly.

### The prior attempt at a guard-like rule

**Exercised** is the one. Its history:

1. 2026-07-10 (9a222a5), as part of the evidence gate: a claim the data barely instantiates gets no case.
2. 2026-09-03 (69d071f), as a named rule: "A rival whose added machinery no pair exercises gets no case."
3. 2026-09-09 (d683be5), first widening: "A pair exercises a part of the peer when that pair's output derives through it."
4. 2026-09-10 (966ea9c), second widening: "even where a narrower rule would give the same output on every pair."
5. 2026-09-13 (f306e00), third: "Exercised tests only the parts the peer adds; a peer that adds none passes it."
6. 2026-09-13 (b3bedbd), declared open. `coverage-rules.md` recorded that three approved solvers hold a case the narrow reading removes (8e5c0c38, 1a6449f1, 4c416de3), and that 9720b24f gives 2 cases or 4 and 8a6d367c gives six combinations or twelve, depending on the reading.
7. 2026-09-15 (fbd9023), removed. The audit's verdict: "Its final letter had been widened twice, so it counted almost every peer as exercised; sessions kept applying a narrower reading than the letter."

So the rule was tried, widened three times to stop it removing cases the corpus already held, and removed because the letter and the practice had come apart. The proposal's guard rule differs in one way that matters: the old test asked whether a *pair* exercised the added part, and the new one asks whether a *witness* breaks a scene claim. The new test is mechanical, which is the failure mode the old one had. It is still a test about the same population of peers.

### The goal, and whether it is recorded earlier

"Enumerate the things of ARC" is not in the record before 2026-09-22 in those words. The nearest earlier statements, all the user's:

- 2026-09-15T13:14Z: "i guess another less important reason for coverage is to cover whatever is possible and conceivable."
- 2026-09-16T02:58Z: "i wanted coverage of possible generators of task" and "i might as well keep around implausible cases for the sake of more code diversity as that can help with ML things".
- 2026-09-21 (da30cfe), in the doc: "**Coverage.** The solver also expresses alternative ways to see the task, for the diversity of ways of writing a solver."

"Do not say no to a new thing" is recorded, three times: 2026-09-18T02:29Z ("do not drop a peer for any raeson if it passes"), the 2026-09-18 "do not omit it from the solver for any reason", and the 2026-09-22 "Your own judgment or taste is not grounds for omitting it."

The new part is that the enumeration is the *primary* goal and the concept-fidelity aim is subordinate to it. In the doc, the order is the other way: Concept first, then Coverage.

### What the proposal has not accounted for

1. **The tension between Equivalence and the encoding clause.** Two models that differ only in encoding agree on every input, so Equivalence excludes one of them. The proposal keeps Equivalence and adds encoding as signal. Both cannot hold.
2. **00dbd492 does not need the encoding clause.** `$Box` and `$Enclose` part on a broken outline. The bullet written on 2026-09-22 records that as a claim difference off the scene, not as an encoding difference. So the cited example does not support the clause it is cited for.
3. **The signal clause's "claims the solver's claims do not already imply" has no stated test.** This is the same shape as the peer-priors gap, which `peer-priors.md` recorded on 2026-09-13 as "no rule says when two candidates do" separate priors, and which the 2026-09-15 overhaul removed rather than answered.
4. **Signal and noise can both hold.** A guard whose added atom is over a relation the concept branch reads can still be a claim the concept case does not imply. The 2026-09-10 ordered-application rule existed for exactly this, and the proposal states no order.
5. **`@relaxed` is a witness annotation, not a branch property.** Style.md ties `@scene` inclusion to `@claim` and `@relaxed`, and solver-file.md puts `@relaxed` under a `@witness` line. A branch's `@relaxed` set therefore depends on which witnesses a session chose to record. A session that records one extra witness changes the verdict.
6. **The runner holds cases the solver does not write** (`@derive`, `@store`, added on 2026-09-22). The audit's clause-difference computation has no branch to read for those, so the guard rule cannot reach them.
7. **The three open questions from 2026-09-13 that the overhaul deleted rather than answered** — `different-parse.md` (structures or input cells), `unchanged-output.md`, and the "what size is a part" gap in `coverage-rules.md` — all bear on the encoding clause and none has a ruling.

## 2026-09-22 — the guard rule is set aside for a bound on where cases come from

The user said "go" to a check of the guard rule over the approved corpus, and added (15:35Z): "let's think if "Guard" is the most precise/conventional name".

The check applied the guard test to every non-concept branch of the approved solvers. It flagged four branches, and the user had kept each of them:

- 2d0172a1's `Nest`, the branch behind the 2026-09-18 ruling "they're out there but i would think of that when thinking of variations of the task".
- 9bbf930d's `Channel`, `Exit`, and `Mouth`, the weaker readings of `pipes` that raised the open-ended lattice on 2026-09-18.

A test on the form of a branch thus failed the same test as Exercised: it removed cases that the corpus held. In the record, what separated the kept branches from the unwanted ones was their origin. `Nest`, 9f5f939b's `Clear`, and the three pipe readings came from the task, from a variation a person imagines, or from the reference solver. The blank-center and two-cell-arm tests of 9f5f939b came from a session that enumerated the tests of its own program: "an2.py runs all eight combinations of those tests". On the name, "guard" is the conventional word for the added literal, and the branch is a refinement of the concept branch.

The session proposed a bound on where a case comes from, in place of the guard rule, with the user's N=1 cutoff as that bound. The user ruled (15:44Z):

> "1. the N cutoff idea, yes, that is what i meant.
> 2. this is too low level for me to decide"

Item 2 was whether the audit should flag refinements. The session decided that the flag does not exist, because a session would read it as one more ground to drop a case. The guard rule was not written into any doc.

### The goal is restated

A draft goal that defined "a reading" was retracted, because a goal stated as a property of a case gives a session a property to argue. The user on the next draft (16:04Z): "warm to this but "session" is not defined, and im concerned about "the model a person first sees" bc thats caused trouble. and this might be too vague now too. or at least ungrounded. the goal is to have things that the rest of the docs say to make." Then (16:09Z):

> "so my own mental model is: principles gives the rules and general constraints. procedure gives the procedure on what to actually include based on , well, procedure. it's a "subset" of what principles defines, and operational bc it's supposed to be practical (and secondarily, "i thought of this by myself and not from reading the code and tweaking it" correspondings to "a possible reading" that is likely to be a new "thing"). aligned?"

The goal was written into principles.md at about 17:28Z, replacing the Concept and Coverage aims of da30cfe. The text at the end of 2026-09-22:

> ## The goal
> - The goal is for the solvers to enumerate the models that fit the tasks.
>     - A solver holds the concept case.
>     - It holds a case for every other model the pass forms that meets the case conditions.
>         * comment
>             - A model the pass forms is a case whether or not a person sees the task that way.

The Terms line under Relational form, with its session-citing comments, was removed at 21:00Z, under the user's "13 ok" (20:42Z) on the item "remove the Terms line, consolidate the session comments".

### Where cases come from, in the record

The user asked for evidence (16:32Z): "send agent to research how solver agents (all 3) actually come up with cases, we need grounding", and (16:34Z) "wait, how about historical too, like sample across time".

- Over sixteen recent tasks (waves 76 to 92), 300 formed models: 152 were formed after the program existed and 45 before it. The sources included the pass's own program (65 models, 11 kept), imagined variations (61, 8 kept), probe output (59, 17 kept), and the pairs (51, 24 kept).
- In the history sample, cases moved to the first write of the solver in July 2026, with no doc asking for it, and the user stopped being a source of models after 2026-07-09.

The user then asked (16:52Z): "Well this is now making me wonder what if we made analyze its own phase, and create focuses on impl", and (16:57Z) "I only care about the goals and the principles . Cost in impl not a reason." Under a separate phase, the N=1 cutoff holds by construction: the create session reads the list and forms no model of its own. The user set the terms (17:03Z, 17:06Z):

> "How about we trial as an experiment. Trial the analyze phase. On new tasks. Ack"

> "No I mean as an experiment. No create phase (also verify facts in compaction summary before using them). I don’t want to commit to it"

The rule that no model formed after Analyze is a case stayed out of the docs. Develop step 3 kept "Look for peer models".

## 2026-09-22 — the Analyze trial

### By brief, 17:28Z to 18:38Z

A procedure section, `### Analyze`, was written for the trial. Seven `claude -p` sessions ran on 9f669b64, 9f8de559, a04b2602, and a096bf4d, on Opus 5 with effort high. The first three tasks each ran under two briefs: one that asked for the models as `@scene`, `@rule`, and `@claim` lines, and one that asked for no form. a096bf4d ran under the free brief with the reference TS solver left out.

What bears on case membership:

1. The free brief found the wider list of models on all three tasks.
2. The 9f669b64 free session ruled eject-versus-slide the same model "on every input the concept is defined on", which is the reading the scene-claim line under Equivalence had been written against.
3. The a04b2602 free session stated its concept in the reference solver's terms, then judged witnesses against that concept twice.
4. The a096bf4d session, with no reference, reached the reference solver's readings from the pairs alone.

The user ruled on the results (20:42Z):

> "1 2 ok
> 3 read after concept
> 4 veto (we'll derive distributions from determined params)
> 5 queue three more after we're done setting up"

Items 1 and 2 adopted the free form, and two rules: a witness's outputs come from a probe, and the concept is stated before the reference solver is read.

### The standalone analyze agent

From 20:52Z the trial moved to an agent file.

At 21:26Z, in a review of the agent file, a third standing was added to the Analyze step: "A model that fits every pair and has no such input: the model it is equivalent to, and why every assignment of one agrees with one of the other." The briefed trials had had two standings only: the pair a model fails, or a witness.

### a09f6c25 and a1570a43: the concept is declared undefined

Both first runs, at 22:12Z to 22:21Z, made the concept case undefined on a class of inputs, and so made every model that differs only there equivalent to it.

1. **a09f6c25.** The concept said: "A figure with no axis, or with axes that map to different colors, is outside the concept. There the concept is undefined." The reference solver's check order and three other classifications then "agree with the concept vacuously and are equivalent to it."
2. **a1570a43.** The concept gave an output only when the shape's box fits the frame's interior exactly. The agent's friction reply:

    > "Agree counts two models as agreeing when either one gives no output. My concept gives no output unless the shape fits the inside area exactly, so every placement model became equivalent to it. If I had stated the concept as a rule defined on every input, such as "center the shape", the same models would split into separate cases. The documents do not say how far the concept should be defined, so the choice of concept wording decides which models become cases."

### The Agree clause is traced

The diagnosis at 23:07Z:

1. The clause is symmetric.
2. So it also lets a concept that is undefined on an input absorb every model that extends it there, because the comparison ranges only over inputs on which the concept case is defined.
3. Nothing in the principles said how far the concept reaches.

### The reach line and the gate

Three edits were proposed at 23:07Z. The first put a line under the concept case:

> - **concept case**: the case whose model the concept statement describes.
>     - At every assignment, its model is defined on every input the generator produces.
>     - An output the concept statement leaves undetermined on such an input is a choice point or an open parameter.

The second replaced the 44f52bb0 example under "Agreement on every input in the current task does not establish equivalence" with the 3b4c2228 one. Under the Agree clause, the 44f52bb0 pair is equivalent: its table gives no output on a third group, and no output counts as agreement. The third made the witness standing refer to the defined term.

The user approved (23:37Z):

> "if you really judge these to be the best resolutions hten approve
>
> besides 4
>
> here's my proposal: for the parts that should be "gated" away, defer it into a file the agent reads. then step 3 will be : Only after you have completed step 2, read X.md for the next steps"

Procedure.md's Analyze became two sections, `### Analyze` and `### Analyze after the concept`. The second renders to `.claude/analyze-next.md`, which the agent reads only after it has written the concept. The reference solver read is behind the gate.

### a1aa0c1e: the reach line is rewritten

a1aa0c1e ran at 23:43Z on the revised context. Its concept was total, and it named its choice points. Eight models got a probed witness, six failed Fit, and one was equivalent. The agent read the reach line per assignment. It took a floor of another color as an input on which a stored floor color leaves the concept undefined, so it derived the floor, and reported "pole is always `9`" as a peer with a witness. Of the line's second sub-bullet it said: "Neither fits well here."

The line was rewritten, and its second sub-bullet was removed because the Choice points section already states it:

> - **concept case**: the case whose model the concept statement describes.
>     - At the assignment stored for this task or a sibling task, its model is defined on every input the generator produces in that task.

### The reruns, and the scene-claim clause moves

The a09f6c25 rerun (00:09Z) found six models with probed witnesses and five choice points. The concept was undefined on a shape with no axis or with two axis classes, and three models were equivalent on that ground. Its friction reply:

> "The documents do not say whether the concept case gives an output for inputs that break a scene claim, such as a shape with no axis or a plus with two axis classes."

At 00:17Z the phrase "whether or not the input breaks a scene claim" moved from the Equivalence line to the reach line, under the 23:37Z approval. The reach line became:

> - At the assignment stored for this task or a sibling task, its model is defined on every input the generator produces in that task, whether or not the input breaks a scene claim.

The Equivalence line kept "Agreement on every input the generator produces does not establish equivalence either: the comparison ranges over every input on which the concept case is defined."

The a1570a43 rerun (00:18Z) made the concept center the shape, with the rounding as an open parameter. Exact fit became a peer, equivalent to the concept as a strengthening. Four models got probed witnesses.

### a04b2602, and the concept slot

a04b2602 ran at 00:28Z, and again cleanly at 00:59Z after a run that read an earlier run's files. Both reached the same three fitting models as the briefed free run of 18:07Z, with the concept written before the reference solver was read.

For the create agent, the Analyze steps gained slugs on claims, a witness file at `.scratch/<task_id>/witnesses.json` in the witness-file shape, and per witness the scene claim it breaks and the assignment it stands at.

The clean run found an input where the concept and every peer agree and a person reads another output, and the steps had no place for it. The user (01:44Z): "slot: wdyt, wrt create agent and overall analysis", then (01:50Z) "ok add the concept slot". The first bullet of the gated step 3 became:

> - The concept case's model: each divergence witness against it, with the items below, where the second output is the judged output.

### a251c730: two more lines in the Analyze step

a251c730 ran at 01:55Z. It found three peers with probed witnesses. After it read the gated steps, the agent rewrote its concept to add "Where two stamps write different colors to one cell, the output is undefined", and called the reference solver's precedence rule equivalent. Its friction reply marked the choice "Interfered".

A clause was added to the equivalence standing, the equivalence coverage clause:

> - A model that fits every pair with no divergence witness: the model it is equivalent to, and why, including that the generator produces no input on which only one of them gives an output.

The user (02:05Z): "i can't judge this, you settle and iterate".

The second run (02:06Z) put the reference solver's fill-only rule in a note: "Those inputs break `room`, and the concept gives no output there when the colors conflict. For that reason I formed no case for it." So the equivalence standing did not apply.

A clause was added to the concept slot, which asks the agent to grade the inputs on which the concept gives no output:

> - The concept case's model: each divergence witness against it, with the items below, where the second output is the judged output; and the plausibility of each input on which it gives no output.

The third run (02:11Z) graded overlapping stamps `borderline`, left the concept undefined there, and called a singleton-anchor model equivalent: "So no input exists on which both models give outputs that differ."

## 2026-09-22 — the diagnosis

The user, at 2026-09-23T02:12Z:

> "are you in bug patch mode? is this a symptom of a deper problem? consider reframing or quetsioning the premise"

The session's answer: the reach line, the scene-claim clause, the equivalence coverage clause, and the grading of undefined inputs were four edits aimed at one behavior. Each asked the agent to state a judgment, and none changed which models became cases. The third a251c730 run showed it: it graded the overlap and nothing followed from the grade.

The behavior:

1. A divergence witness must be an input on which the concept case is defined, and Agree ranges over the same inputs and counts "one gives none" as agreement.
2. So an agent that declares the concept undefined on a class of inputs shrinks the inputs the comparison ranges over.
3. The agents did this where a person's reading is silent: figures with no axis or two axis classes (a09f6c25), a shape smaller than its frame (a1570a43), and overlapping stamps (a251c730).
4. The real alternatives there then count as equivalent to the concept, and get no case.

Forcing the concept to be total, which the reach line does, asks the agent to invent a rule where a person has none, and the agents said so ("neither fits well", "the documents do not say how far the concept should be defined"). The "gives none" clause exists to keep a strengthening from being a case. Agreement is symmetric, and the mirror of a strengthening is an extension, so the clause also admits the extension as equivalent.

## 2026-09-22 — the Domination proposal

At 2026-09-23T02:14Z the session proposed a reframe. The user did not rule on it.

1. Comparisons range over every input, and no output is one of the values a model gives.
2. Equivalence is the same function up to reparameterization:

    > - Two models are equivalent when each assignment of either has an assignment of the other that gives the same output on every input.
    >     - Equivalent(A, B) ⇔ (∀θ ∈ Θ. ∃φ ∈ Θ′. ∀x ∈ G. A(θ, x) = B(φ, x)) ∧ (∀φ ∈ Θ′. ∃θ ∈ Θ. ∀x ∈ G. A(θ, x) = B(φ, x))

3. A strengthening is excluded by domination, not by agreement:

    > - A model dominates another when each assignment of the other has an assignment of the first that gives the same output on every input on which the other gives one.
    >     - Dominates(A, B) ⇔ ∀φ ∈ Θ′. ∃θ ∈ Θ. ∀x ∈ G. B(φ, x) ≠ ∅ ⇒ A(θ, x) = B(φ, x)

4. Cases gains a fourth condition: "**Domination.** A case other than the concept case is not dominated by another case's model."
5. The divergence witness loses the restriction to inputs on which the concept case is defined:

    > - **divergence witness**: an input on which either of these holds:
    >     - at some assignment, two models give different outputs, or one gives an output and the other none.
    >     - a model's output at some assignment differs from the output the generator pairs with the input.

    The source comment "A model that agrees with the concept case on every input on which the concept case is defined has no witness against it" goes, because it becomes false.
6. The reach line with its scene-claim clause goes, and so do the two clauses added to the Analyze step for a251c730. The concept slot, the broken-scene-claim item, the witness file, the concept template, and the gate stay.

Under the proposal, a strengthening is dominated by the concept and gets no case. An extension dominates the concept and is a case, with a witness on the input where the concept gives none. The reference solver's precedence rule in a251c730 would be a case, with the overlap witness at `borderline`.

## 2026-09-22 — the retrace

The session reported three retraces:

1. "Equivalent up to reparameterization" is the `Iso` and `EquivalentAcross` definition that was deleted earlier on 2026-09-22. Restoring it brings back the two callouts that removed it: 9f236235's vacuous isomorphism across cardinalities, and 9f27f097's narrowed domain. The Reparameterizations rule had been cut on 2026-09-09 (d683be5).
2. Domination is the 2026-07-10 rule **Subsumption by invalid divergence**. Refused input narrowed it on 2026-09-11, and fbd9023 removed it on 2026-09-15. The Agree "gives none" clause of 2026-09-22 had already reversed Refused input: a strengthening is equivalent to the concept, so the strict hypothesis gets no case.
3. Dropping `G_C` reopens the 2026-09-18 construction. A model that tacks an inert rule onto the concept and gives an output where the concept is undefined dominates the concept case, is not dominated, and so is a case.

The inputs the comparison ranges over had been set four ways, each to fix the direction in which the one before had failed:

1. Every input, with an isomorphism between parameterizations (fbd9023, 2026-09-15).
2. The inputs on which the concept case is defined, `G_C` (2ba3d0b, 2026-09-18).
3. `G_C`, with no output counting as agreement (2026-09-22, uncommitted).
4. Every input, with no output as a value, plus Domination (proposed 2026-09-22).

What separates a real alternative from a contrived one is whether an input off the concept is a variant or a contrivance. That is a judgment about the input, and the 2026-09-16 ruling ("i no longer want deliberation over keep/drop by judgment") had taken such judgments off the table. The session proposed no rule.

### The case-membership edits at the end of 2026-09-22

| Edit | Where | Cause | Status |
| --- | --- | --- | --- |
| Agree counts "or one of them gives none" as agreement | principles.md, Equivalence | `9f236235` create callout 3 (04:36Z) | Kept. The Domination proposal would replace it; no ruling. |
| The goal: "for the solvers to enumerate the models that fit the tasks" | principles.md, The goal | the goal discussion, 15:10Z to 16:09Z | Kept. |
| Terms line and its comments | principles.md, Relational form | ruled "13 ok" (20:42Z) | Removed at 21:00Z. |
| The equivalence standing | procedure.md, Analyze step | agent-file review (21:26Z) | Kept, with the coverage clause below. |
| 3b4c2228 in place of 44f52bb0 under Equivalence | principles.md, Equivalence | 44f52bb0 is equivalent under the Agree clause | Kept. |
| The reach line, first form, with "An output the concept statement leaves undetermined … is a choice point or an open parameter" | principles.md, concept case | a09f6c25 and a1570a43 first runs | Rewritten at 00:01Z; the second sub-bullet removed. |
| The reach line: "At the assignment stored for this task or a sibling task, its model is defined on every input the generator produces in that task" | principles.md, concept case | a1aa0c1e | Kept. The Domination proposal would remove it. |
| "whether or not the input breaks a scene claim" | moved from the Equivalence line to the reach line | a09f6c25 rerun | Kept on the reach line. The Domination proposal would remove it with the reach line. |
| The gate, `.claude/analyze-next.md` | procedure.md, Analyze | user's proposal (23:37Z) | Kept. |
| The concept slot | procedure.md, Analyze after the concept | a04b2602 clean run | Kept. |
| "including that the generator produces no input on which only one of them gives an output" | procedure.md, equivalence standing | a251c730 first run | Kept. The Domination proposal would remove it. |
| "and the plausibility of each input on which it gives no output" | procedure.md, concept slot | a251c730 second run | Kept. The Domination proposal would remove it. |

## 2026-09-23 — every input, and branches in place of models

The session had asked whether a witness input's plausibility may decide case membership, or whether any model that differs from another anywhere is a distinct reading, with the 2026-09-18 bound dropped. The user chose the second (02:33Z): "2". Then (02:38Z) "well double check your proposal. ultrathink", and (02:47Z) "go".

The edits:

- Agree ranges over every input: "Two assignments agree when, on every input, the two models give the same output or neither is defined." `G_C` goes.
- The divergence witness loses "on which the concept case is defined". Its first bullet becomes "at some assignment, two models give different outputs, or one is defined and the other is not." The 2026-09-18 source comment goes.
- The reach line goes, and so do the two Analyze clauses added for a251c730.

No Domination condition was added. So a strengthening became a case again, as under Refused input (2026-09-11). The bound on contrived models moved from a case condition to where a model comes from: Analyze forms them before any program exists.

### The concept file is fixed, and Analyze reports branches

The user (03:06Z):

> "i feel agents are intrinsically conservative and dont want to overstate anything, even if it means being inconsistent. as long as the output is constrained ... lets ultrathink of resolutions"

Two lines followed. The concept file is not changed after Analyze step 2. Of the reference TS solver: "Each claim it makes that the concept statement does not make, or makes differently, is a branch." Analyze's report became one entry per choice point, each with its branches and their standing.

### Nothing the pass thinks of is dropped by the pass

On the goal's `* comment` line, "A model the pass forms is a case whether or not a person sees the task that way" (03:37Z): "yes it was ablation. uncomment."

An a2fd1cf0 run left out a scan-order pick as "not equivariant". The user (03:37Z): "i guess it's fine bc the create session can rejudge it? as long as all dropped things are reported". Then (03:42Z): "we should add it, and also instruct the create (and subsequent?) agents to rejudge them", and "well not even rejudge. if it passes it passes". The Analyze report gained a slot for each claim considered and not formed, with why.

On what Create does with that slot (18:23Z):

> "3 b. add them all. if it was thought of, then it's a potential case, and if it passes as a case, add it"

### Combinations of branches

a57f2f04's Analyze gave eight choice points. The user (19:00Z): "ok yea i accept having that many choice points but our tooling was not designed for 256 cases". Create had held nine cases, one per branch. The user (19:02Z): "i'm confused about the cases situation. usually the cartesian product is just taken. whats happening here, why picking specific ones?" On a witness file that names all 256 cases per group (19:04Z): "yea but it's impractical, should still change".

The user said "go" (19:10Z) to this design: the cases are the combinations of the report's branches that fit, and a witness pins a branch's model, not a case.

### Who reconciles cases that do not combine

On an a5f85a15 report whose flat choice points did not combine: "whose burdne should it be to reconcile the cases" (20:11Z), and (20:44Z):

> "i just want the solver to be in its best form, and for the agents to do waht they're best at, and for the tooling to support them best"

On a proposal that Create leave a runner hint under Open (20:50Z): "why keep it open? ok focus on the goals again and ultrathink on the best resolution". The user approved the result (20:53Z): "ok. apply. then review".

- Analyze places each choice point at the concept or under a branch, and says what a case that takes a non-concept branch at two points reads.
- `witness` reports two held cases that no witness separates.
- Create resolves such a pair by nesting, then by a separating witness, then by dropping a case, and reports it as a departure.

### An approximation is for the concept case only

On a concept witness with verdict `other` (21:33Z):

> "restate. but unclear on the apprx thing. to be clear, it should only be used for the concept case"

Analyze's report restates the rule as the generator applies it. Create writes the restated rule as the `@rule` line and the concept file's rule under it as the `@approximated:` line.

## 2026-09-23 — Subsumption enters as the fourth condition

The user rules on the Domination proposal of 2026-09-22, under the name Subsumption:

> "domination (subsumption? i prefer that . it's more precise /conventional right): the circumstance here is different. before, agents were refusing to add cases in the first place and they use this as an excuse. now, we have a big starting point and if it's up to a mechanical check to remove then should be fine?"

The difference from the 2026-07-10 rule and from Refused input is where the rule acts. Analyze forms every branch and Create holds every combination that fits; the runner then reports a held case that no input run shows defined and differing from another, and the pass builds the witness that shows it or drops the case. No agent judges a model out before it is formed.

The condition, in principles.md under Cases, with the definition under Equivalence: a model is subsumed by another when the two are not equivalent and each assignment of it has an assignment of the other at which, on every input where it is defined, its output is the other's; the concept case meets the condition whether or not it is subsumed. Fit is unchanged, so "Being undefined on another input does not prevent a model from fitting" stands: a subsumed model fits, and fails the fourth condition.

What this reverses: Refused input (2026-09-11), in that a strict hypothesis that never differs from the tolerant peer where it is defined is now subsumed by it, and the letter of "No other removal" (2026-09-15), which gains a fourth mechanical test and keeps its reason.

In the corpus at the time: ComponentLines on a5f85a15 and TouchedCorner on a57f2f04 are subsumed by their concept branches; ColorBox on a57f2f04 is subsumed at the stored scan set and not at a narrower one.

## 2026-09-23 — no pass judges subsumption before forming

The user (23:23Z):

> "why was subsumption removed? if it's the case of agents using it to disregard cases, would ANalyze be at risk of that/"

The session named the a57f2f04 Analyze pass, which had left out a touched-corner reading because it "states no rule beyond those two cases". It proposed a line against that. The user (23:25Z): "don't add it yet."

A Create pass then reported that the runner's first subsumption check had kept it from holding models that are restrictions of other models. The user approved three items (23:49Z): "approve 1-3".

1. A witness is judged at the assignment it stands at, which is the stored assignment unless its divergence needs a reassignment. A scene claim that names a parameter is read at that assignment too.
2. Under Subsumption: the runner reports it on a held case, and no pass judges it before the case is formed.
3. Refine on 9f669b64 forms again the combinations and the branch that its Create pass had omitted, and the subsumption finding decides each.

On the second batch of twenty Analyze runs (2026-09-24T00:23Z):

> "i only care about interference and issues w principles
> 1. plausaibiltiy: approve
> 2-3 how to improve docs so it's clearer and analyze agents wouldnt complain (prefer updates over additions)"

The results:

- `ordinary` plausibility became "readily, breaking no scene claim of the concept case".
- The Analyze step that forms branches says: "A branch is formed whether or not another branch's model subsumes it."

## 2026-09-25 — the goal is reworded (9b78018)

The goal block from 2026-09-22 set off a model safeguard in agent sessions. The user (01:53Z):

> "basically all of this holds. so what do you infer it should actually say? it changed recently bc it was influencing solver agents to drop cases, but that's already solved"

The goal became:

> - The corpus supports the synthesis of solver programs, and takes as much as it can from each task, in this order:
>     - **Concept.** A solver has a case for the concept.
>     - **Coverage.** A solver has a case for each other model that meets the case conditions.

"The pass forms" and "whether or not a person sees the task that way" went. Inclusion is left to the case conditions.

## 2026-09-25 — subsumption against every held case (b876d19)

A Refine pass on a1570a43 removed 17 cases that another held case subsumes. The runner had compared each case only with the case that takes the concept branch at one of its points, so it had not reported them. On whether the pass was right to remove the 17 cases (02:34Z): "was it?".

The history shows the partner in the comparison was always any case. The user (02:42Z): "widen". `witness` now compares each case with every other held case, the concept case exempt, and the procedure's line says "differing from another case". The 17 cases stay out.

## 2026-09-25 — rulings from the dispatcher loop

### A concept error is fixed by the pass that finds it

A Create pass on a1aa0c1e found a witness with verdict `other` that points at the concept, and put it under Open, saying a later Analyze pass that forms the model would settle it. The user (14:44Z):

> "confused about "a later Analyze pass". that doesn't make sense. there's only one analyze pass at the beginning. if that agent made decisions based on the assumption there would be a later analyze pass, there is something wrong there"

The session's recommendation left a rerun of Analyze to the user per task. The user vetoed it (14:53Z):

> "really? i want things to be increasingly autonomous. so "you decide per task whether to run Analyze again" veto. but we need to find a way to amke ti work as i want"

Then (14:54Z): "other options? why give it to analyze? don't stay boxed in to what we have". Of the options, the user chose "Whichever pass finds it fixes the concept case, with the witness as evidence" (14:57Z):

> "sounds right, so that means we can Refine it to fix it. i just dont want cases to be arbitrarily dropped"

procedure.md's Witness step now reads:

> - On a branch's witness on which no open values disagree, an `other` verdict identifies a problem with the concept case, and so does a non-concept verdict at `ordinary` plausibility; the concept case is fixed to give the judged output, the verdict becomes `concept`, and the fix goes in the review as a departure.

### Open items, misnamed tags, and split orders

- 15:07Z: "also i accept open items that point towards something being wrong. dont leave out."
- 15:07Z, on a solver that works but has a constructor named for a reading another branch shares (a25697e4): "opt1". solver-file.md now reads: "A constructor denotes only its branch's reading, not a reading another branch shares, and is named for its branch".
- On a scan order stored as two parameters, a corner and an axis, whose product cannot express a sibling task's set of open orders (15:02Z): "conceptually, lexorder takes one Thing. we just split it into 2 bc that's the only primitive we have. so something feels like indirection?" Then (15:04Z): "ok there's no reason to split it into 2 and that seems to be causing problems too so lets think of ways to prevent that from happening". principles.md now reads "The solver stores every open value of an open parameter in one relation, keyed by value".

## 2026-09-25 — Subsumption compares at the same assignment

The Subsumption definition said that each assignment of a model has some assignment of the other at which the outputs match. The runner compares both models at the witness's own assignment. On a47bf94d a pass dropped `x-complement` under the definition although its witness passed the check.

The session read the history as favoring the runner's form: the 2026-09-16 and 2026-09-23 rulings put removal on a mechanical check. principles.md now reads:

> - A model is subsumed by another when the two are not equivalent and, at every assignment of their parameters, on every input where it is defined, its output is the other's.
>     - Subsumed(A, B) ⇔ ¬Equivalent(A, B) ∧ ∀θ ∈ Θ. ∀x ∈ G. Def_A(θ, x) ⇒ A(θ, x) = B(θ, x)

The session had said the old definition's refutation is not mechanical, since a witness would have to show the case differing at every assignment of the other model, which the runner cannot enumerate for stored tables and grids. The user asked (15:42Z):

> "it's not mechanical, but it still sounds checkable ie given proof no judgment needed?"

The session's answer: for a parameter of an enumerated type, the check is mechanical; for a table or a grid, the refutation is an argument about the other model's clauses, which an agent must read and verify. As of 15:44Z the user had not ruled, and the same-assignment form stood.

## 2026-09-25 — `@derive` and `@store` lines are branches

Item 1 asked who adds the case in which a parameter's value is derived instead of stored, or stored instead of derived. The example was 9caba7c3, which has a choice point with three branches and two `@derive` lines, on `field` and `mark`. Its text lists three cases. The runner held nine: those three, each with `field` derived, and each with `mark` derived. It never combined the two lines.

What the history settles, as item 1 records it:

- The 2026-09-09 ruling, "Cases go to every model divergence the pairs leave open, so the reparameterization exception is gone", rules out a runner that adds a derived case for the concept case only.
- The 2026-09-23 ruling on a57f2f04, "usually the cartesian product is just taken", makes a derived value a choice point that combines with every other one. 9caba7c3 then has twelve cases.
- No ruling says who adds the case. The 2026-09-22 entry "The runner holds cases the solver does not write" records a session design.

The first option had the solver write each derived value as a branch, as 2bcee788 writes its `Minority` branch, and removed the `@derive` lines. The user (21:19Z):

> "> The @derive lines go
>
> this is undesirable. makes it all verbose. what's the defense for opt 1?
>
> > A session that reads the file sees three constructors, and learns of the other six cases from this output.
>
> is this a fact or a reason?"

The session answered that the defense is one set of rules for every branch, and that this does not need the verbose form: the `@derive` line stays, the docs define it as a branch of a choice point on the parameter, and the runner expands it as a branch. The user (21:25Z): "i dont understand the diff btwn preprocessing and just keeping it in the runner". The session's answer: in both, the runner holds cases the solver does not list. Kept as a separate kind of case, each rule on cases needs its own clause for it: its name form, its ignore form, which cases get one, whether two combine, and its place in Subsumption. Expanded as a branch, it falls under the rules every branch falls under. The user (21:27Z): "so this is an impl detail that i shouldn't care about in the end?" The session: yes, and what the user sees is that a solver with two lines gets their combinations as cases, and that every solver with such a line gets a Refine pass.

The user (21:34Z):

> "what was the problem in the first place? the fact that these @store @derive branches didn't actually combinatorially combine and the lack of docs explaining their behavior?"

The session answered yes, and added a third cause: the runner's behavior had been changed twice on the session's judgment, and the docs had been edited to follow the runner.

### The ignore line stays

The session had said that the ignore lines go, since a case leaves by a `@witness` verdict or by Subsumption like any branch. The user (21:32Z):

> "explain. i rmemeber adding the ignore (dont call it drop) line in case no witness could be made for it"

The session withdrew that. A branch that no witness separates leaves under Equivalence by the ordinary rule, and the review records why. A derived branch is not written by the session: `derive` proposes it again on every pass. So the ignore line is the record in the file that the branch was tried and left.

The user (21:35Z):

> "ok so im warm towards the solution but i have a feeling there's a lot of gaps given you thought we could get rid of @ignore. like. for combined @store/@derived branches, there may not be a witness, and then how to ignore that?"

Then (21:36Z): "how is it done for normal branches?" A written combination that leaves is left out of `impl_choice`. For a derived branch, the per-case form `// @ignore: derive <name> — <reason>` names the combination, and `<name>` may be a `<name> & <name>` form.

The user (21:38Z): "think of more edge cases like this". The session listed eleven. The user (21:40Z): "filter this down to what you can't resolve on your own". The session resolved all but one on existing rules:

- A derived branch whose only separating witness breaks a scene claim stays, under "do not drop a peer for any raeson if it passes". Ignore lines written on plausibility are reverted to branches with `@relaxed` witnesses.
- `derive` checks equivalence against the written branches before it proposes, so 2bcee788's `Minority` gets no proposal.
- The one left was item 2.

### The docs now

solver-file.md's `@derive` directive reads:

> - **`@derive` directive.** The line is a branch of a choice point on the parameter, which stands under the branches that read it, with the parameter's value derived by the built-in derivation the line's `<Proposer>` selects; lines on one parameter are branches of one point, and the runner holds the cases that take one of them.
>     - The verdict `derived` denotes that branch, beside the verdicts a `@witness` line takes, and its witness's id is the branch's name.
>     - `// @ignore: derive — <reason>` in its place records that the branch failed Equivalence or Subsumption, and the runner then holds no case that takes it; `// @ignore: derive <name> — <reason>` under the `@derive` line records that for only the case `<name>` with the branch.

The `@store` directive reads the same way: "the line is a branch of a choice point on it, which stands under the branches that read it, with the relation's value stored per case; the runner holds the cases that take that branch." The Witness file's name form reads "`<param>=<Proposer>` and `<rel>=stored`: a `@derive` or `@store` line's branch, read as a constructor's name".

procedure.md's Develop step 4 reads "Hold as a branch each built-in derivation that fits a parameter, and each stored reading of a value the program derives", and "A branch whose model is equivalent to that of a `@derive` or `@store` branch loses its constructor and gets no clauses of its own."

## 2026-09-25 — the cases as one clause over the enumerators

A written combination that leaves is left out of `impl_choice`, and 305b1341 lists six of its eight combinations one per line. The user (21:40Z):

> "> The solver lists the combinations it holds
>
> this seems verbose too. i wonder if there's a way to encourage factoring or if there's a better way to say "include these, exclude these""

The session named the forms the corpus already has: 9f669b64 writes the product less a relation, `!as_half_width([R, L, St, Sh, C])`; a09f6c25 writes the product with constraints; a nested constructor needs no listing; and 447fd412 lists a free product of four in four lines. The user (21:46Z): "enumerating cases: i think thats right but i'll have to see examples". The user asked (22:03Z): "no i mean show exmaples of case enum", and "the desired result i mean". The session showed three solvers under the rule:

- 447fd412: `impl_choice([C, V]) :- carry_choice(C), cover_choice(V).`
- 305b1341: the stack choice nested under `Lattice`, as `Lattice {stack: Stack}`, so that the excluded combinations do not exist.
- 9f669b64: unchanged, as the exemplar.

The user (22:05Z): "lgtm do all". solver-file.md now reads:

> - `impl_choice` contains whole `Choice` values, for a record, as a clause over the enumerators that excludes each combination that is not a case, and it appears when a clause reads one or when the cases are not every combination of the fields.

patterns.md follows: "When only some combinations are cases, the record remains, and `impl_choice` excludes the others".

## 2026-09-25 — Subsumption at the parameters either model reads

Item 2 asked at what assignment Subsumption compares two models that read different parameters. The example was a09f6c25. Its `SizeBound` branch reads the open parameter `noise_size`, and `MinSizeNoise` computes the smallest size. `store` proposed `MinSizeNoise` with the size stored as 1. The solver's `@ignore low: store` line dismissed that model as `SizeBound` at the bound 1, and a Refine pass could not judge the line.

The document then recorded as settled: the comparison is at one assignment, the witness's (the 2026-09-23 rulings); and the form in which each assignment of one model may be matched by some assignment of the other is the reparameterization exception the 2026-09-09 ruling removed. What stayed open was what that assignment gives a parameter only one model reads. Under option 1, the assignment covers every parameter either model reads. A witness that reassigns `noise_size` to 3 then shows the stored-size model differing from `SizeBound`, and the model stays as a case.

The user (21:55Z): "so item 2, it sounds like there's no good defense for opt2?" The session's answer: option 2's one argument is that it removes contrived cases, the 2026-09-18 worry "we can invent contrived models by tacking on rules?", and the 2026-09-23 ruling had answered it with "a big starting point" and "a mechanical check". Item 2 was marked settled on option 1.

principles.md now reads:

> - A model is subsumed by another when the two are not equivalent and, at every assignment of the parameters either reads, on every input where it is defined, its output is the other's.

procedure.md's line on a case `witness` reports reads: "Some input, at some assignment of the parameters either case reads, shows the case defined and differing: build the witness that shows it, with `--assign` when it needs one, and the case meets Subsumption and stays."

## 2026-09-26 to 2026-09-27 — the user's rulings

Each ruling is given in the user's words, with what it settled.

### A named `@ignore` line is a pattern

The session asked whether `// @ignore: derive <name>` excludes every case that takes the branches `<name>` contains, or exactly one case. Under the first reading, the lines of four solvers would exclude more cases than they were written for. The user (2026-09-26T14:48Z):

> "Why not 1?"

And (2026-09-26T14:56Z):

> "Ideas about other options? Seems parallel to enum cases vs using dl rules"

The session gave three options. The first kept the pattern and gave the stored value at a `@derive` point the name `<param>=stored`. The user (2026-09-26T15:04Z):

> "1 ok"

This settled that a named `@ignore` line excludes every held case that takes its branches, and that the stored value at a `@derive` point is named `<param>=stored`.

### The case enumeration is exempt from program style

A pass had written the exclusion in `impl_choice` as a relation of its own, because lint's Disjunction rule rejected it written inside the clause. The user (2026-09-26T15:04Z):

> "2 ok so clauses over choice things are not under the same strict standards as program code so generally avoid unnecessary strictness , like avoid verbosity"

This settled that the clauses that enumerate the cases are not held to the program's style rules.

### A witness group holds one grid per tiebreak resolution

A conformance audit of the runner raised the question of what a witness file group holds for a case that gives two grids, one per tiebreak resolution. The session's default was that the group's grid takes a list of grids for such a case. The user (2026-09-26T19:25Z):

> "2.1 i tihnk there's a backlog.md item about the tiebreak thing, but unresolved. approve"

This settled that a group's grid is a list of grids, one per tiebreak resolution, when the cases give more than one.

### `assign` may name a stored relation

The same audit read Subsumption's "every assignment of the parameters either reads" as covering the value a `@store` branch stores. The session first answered that `assign` names Params relations only. The user (2026-09-26T19:27Z):

> "what about under the goals"

The session then found that the definitions make a stored relation a parameter of the branch that stores it, and recommended that `assign` may name it. The user (2026-09-26T19:33Z):

> "right that sounds most consistent. any reason not to? if not, approve"

This settled that a witness's `assign` may name a `@store` line's relation, and that a case taking that branch reads the assigned value.

### The typed-order lint is not narrowed to colors

The principles line on unordered types names only colors. The session had ruled that the typed-order lint therefore narrows to colors. The user (2026-09-27T12:13Z):

> "Wait, it is inferrable the intention of things. Eg. The lint on ordering, there’s no defense to narrow to only colors. Common sense should be prioritized over the letter"

This settled that the typed-order lint stays on every type with identity and no order, and that a handbook line is read for its intent over its letter.

### `@ignore` records a judgment

The session had ruled that the runner stops honoring `@ignore` on a lint hint. It then reversed that on its own: the runner keeps honoring it, and the `@ignore` directive would gain "or a hint". The user (2026-09-27T12:16Z):

> "What’s the difference between hints and findings? Send agent to determine how it’s actually used. Bc point of ignore is to silence what was already judged to be false flag, not to just bypass lint"

This settled the purpose of an `@ignore` line: it silences a flag that was already judged, and it does not bypass lint.

### Approved solvers outside the loop

The audits of approved solvers that have no Analyze files now reported missing `@derive` and `@store` lines, and the session planned to ask how such solvers are brought to the current standard. The user (2026-09-27T14:20Z):

> "4 out of scope"

This settled that approved solvers with no Analyze files are not brought to the current standard.

### One finding per unseparated pair of bases

A base is a `Choice` case without the `@derive` and `@store` branches it takes. The session had ruled that `witness` does not report a pair of cases that take the same `@derive` or `@store` branches while it reports the pair of their bases as unseparated. An audit of the session's rulings against this history reversed that, so that every unseparated pair would be reported. The user (2026-09-27T23:50Z):

> "i suppose that's following the letter. benefit of consistency > cost of noise? or is that the right cost/benefit analysis"

The session answered that the history's lines settle what is compared and what leaves, and do not settle how a finding is shown. It proposed one finding per unseparated pair of bases, naming the branch choices under which the pair is unseparated. The user (2026-09-27T23:53Z):

> "approve"

This settled that `witness` reports one finding per unseparated pair of bases, naming the branch choices under which it holds, whatever kind of branch those choices are.

On 2026-09-29 the first Create pass through the rewritten tool, on ac0c5833 with 80 bases, met hundreds of such findings and regrouped them by hand by the branches that differ. The session put the pair form to the user as a decision with the defense that no pair is folded away. The user:

> "seems like a weak defense not in support of the goals?"

The finding now groups the unseparated pairs by the branches on which they differ, naming their contexts by the fewest names that cover them; each pair stays reachable through its context.

## 2026-09-28 — the user's rulings

Each ruling is given in the user's words, with what it settled.

### A parameter stored by a RIGID call is compared up to pose

The tool printed an undecided line for a determined parameter that a RIGID call stores, because no handbook line said whether the pose counts. The user (2026-09-28T17:51Z):

> "so the decision was to say it's undecided?"

The session then gave three options, that the pose does not count, that it counts, or that the line stays undecided, each with its consequence for the nine solvers affected. The user (2026-09-28T17:55Z):

> "re. RIGID: infer what i want and why i would want it. and next time, do this instead of just giving options and consequwnces (and also the consequences you gave are not helpful for  deciding anyway)"

This settled that the tool compares a parameter stored by a RIGID call up to pose, since a RIGID block makes the stored pose unobservable.

### The cases the tool runs are the solver's cases

The user had objected to ordinary words that had become private terms. The session answered that "held", as in the cases the runner holds, was the handbook's own word and so counted as defined. The user (2026-09-28T18:05Z):

> "we don't have to keep it that way. choose the best term"

This settled that the cases the tool runs are called the solver's cases, in the handbook and in the tool, and that "held" is no longer used for them.

### A group lists the fewest names that give exactly its cases

The session described a one-time rewrite of the witness files in which each group would list every case of the solver that gives its output. The user (2026-09-28T19:26Z):

> "2. prefer to avoid verbosity, if applicable"

The session measured one group on 9ddd00f0 at thirty names, where the old file's largest had nine, and proposed that a group list each base that gives its output and a case that takes a branch only where its output differs from its base's. The user (2026-09-28T19:29Z):

> "is the solution you designed the best solution? there's a math thing going on"

This settled that a group lists the fewest names whose cases together are exactly the cases that give its output.

### Solvers are kept in their current form

The tool, under a new reading of verdict names, reported forty-nine verdict lines in eighteen solvers as failing. The session planned a migration that would rewrite each such verdict to the case it had meant under the old reading, so that the files kept the meaning they were written with. The user (2026-09-28T21:19Z):

> "wait no. solvers should be consistent and be in their best form. we shouldn't deal with backwards compatiblitily or whatever. im ok w churn"

This settled that a solver and its witness file are kept in the current form and in their best form, that the tool keeps no reading for an older form, and that the corpus is rewritten into the current form once, whatever churn that costs.

### A name means the same thing in every place

The session had read the name in a `@witness` verdict as denoting every case that takes the branch, where the principles define a branch's model as one case, and it withdrew the findings built on that reading. The user (2026-09-28T21:50Z):

> "could the docs have been written better such that you wouldnt have misread it"

The session answered that the documents used one name syntax with two readings and did not say so. The user (2026-09-28T21:52Z):

> "ok. is there a Better Writing way to resolve it?"

The session proposed that a name mean the same thing in every place, that a branch's model and a branch's cases each be defined once, and that each place say which of the two it takes. It left the principles line for the user to write. The user (2026-09-28T21:54Z):

> "i don't write text. make this update happen and ensure the semantics are correct and anything it touches"

This settled that a name has one meaning in every place, that a `@witness` verdict names the name's model while a case marker, an `@ignore: derive` or `@ignore: store` line and a group name its cases.

### A name fixes the branch at some choice points

An audit of the handbook text on names found lines that no reading fits, such as `concept` beside another name naming no case. The user (2026-09-28T22:16Z):

> "curious if there's any reframing or renaming that could make resolve some of these things and make things simpler. like did we contort ourselves bc we modeled it wrong?"

The session proposed that a name fix the branch at some choice points and leave the others open, that the `@derive` and `@store` points be taken by each case whose base reads the parameter, and that `concept` be the concept base. The user (2026-09-28T22:22Z):

> "ok"

This settled that a name fixes the branch at some choice points; that its model takes the fixed branches and the concept branch at every other point it takes; that its cases are the cases of the solver that take the fixed branches; that a case's base is its `Choice` value; and that `concept` is the concept base.

### Create compares a branch's model against the Analyze file

The same audit found that the Create step's comparison against the Analyze file read two ways, as covering every case that takes a branch or the branch's model alone, and the session could not infer which the user meant. In the same message as the previous ruling, the user (2026-09-28T22:22Z):

> "6. i don't think i made a decision here. you know the point of the analyze pass right? think of a bunch of cases bc what is thought of is what is plausibly "someone woudl tihnk of it". and then create encodes whatever passes."

This settled that the Analyze file's groups give branches' models, and that Create treats a branch whose model's output differs from the output the Analyze file gives that branch as an error in the solver to fix.

### A nested branch is named by its constructor

The corpus wrote a nested branch in several forms, such as `Derive(g=Iso)` and names joined by `&` without spaces. The session proposed one form: constructor names joined by ` & `, a nested branch named by its constructor alone, and a parent written only to pick one of two points at which the constructor stands. The user (2026-09-28T22:41Z):

> "i dont fully agree but i accept it bc the & chains can get lengthy"

This settled that a nested branch is named by its constructor, that a parent is written only to pick a point where the constructor stands at two points, and that the other forms are faults.

### Every constructor name carries `$`

The user (2026-09-28T22:47Z):

> "thoughts on actually enforcing the $ prefix everywhere? to make it clear it's specifically branch?"

The session recommended the prefix, and then found that a slug from the Analyze pass would give a second spelling of the same branch. The user (2026-09-28T22:52Z):

> "should we just make the analyzer use the $ form? or just keep slug"

The session recommended that the Analyze pass write the constructor form. The user (2026-09-28T22:54Z):

> "go"

This settled that every constructor name carries `$` in markers, verdicts, groups, ignore lines and the tool's output; that `concept`, `any`, `other` and the `=` forms stay bare; and that the slug form is gone, with the Analyze pass naming each branch by its constructor name.

## 2026-09-30 — a proposal comp is written only where the concept case reads it

The first Create pass through the rewritten tool, on ac0c5833, wrote a proposal comp `CentroidDist` that served the branch `$NearestCentroid` alone; the concept case encodes the task without it. The Necessity rule ("A comp that serves one case while another case encodes the task without it is not needed") stood under the lib pass, which the loop does not send, and its clause on the case had been removed on 2026-09-23. The user:

> "the fact that a case forced the creation of a proposal comp when it wasn't the concpet case"

> "i very distinctly remember "proposal comps" fka task-local comps should be removed if they [only are for coverage] or osmething like that. at least there was a rule gating their creation or asking for their removal under some condition"

The session proposed the condition in the pass's own step and a clause under the Relational form condition. The user vetoed the principles edit ("veto principles edit. it's not a principle.") and approved one sentence in the lib protocol's proposal-comp step: a proposal comp is written only where the relations need a banned form and the concept case reads them. A branch whose claim needs the form then has no set of clauses and fails Relational form as the condition already reads.


## 2026-09-30 — the cases the tool runs are the live ones

The first Create pass on ac0c5833 met 616 cases, most of them combinations that no input showed defined and differing from a case with fewer branches, and the audit's deletion survey ran every one. The user asked for a bound, then for a distance from the concept with weights from the witness labels and a threshold. A study over the six solvers with the most cases showed that no label predicts such a repeat and that every weighted threshold drops a case some witness separates. The user:

> "ok we don't have to stick with any of my suggestions. you know what i want: efficiency diversity. ultrathink on the best solution"

> "approve"

This settled that the tool computes the live cases from the inputs at hand, the pairs' and the witness entries', with no judgment and no number to set: the concept case, each branch's model, and each case that some input shows defined and giving a grid no case with fewer of its branches gives, less each case that takes two rejected branches, a rejected branch being one whose every verdict is `concept`. The checks, surveys and counts read the live cases; the others get no finding and no run. The rule is a tool parameter, not a principle.
