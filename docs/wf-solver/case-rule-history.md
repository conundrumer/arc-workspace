# Case inclusion: the decision history

What decided which models become cases in a `.dl` solver, from the first "Coverage" principle to the three case conditions of 2026-09-22.

Sources: `git log` over `docs/wf-solver/`, and Claude Code transcripts under `~/.claude/projects/-Users-davidlu-code-arc-workspace/`. Transcript timestamps are UTC and run four hours ahead of the commit dates.

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

The user's reasoning is in the transcripts, in session 47ab7f86 and its successor 5d054d0a.

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

This came from session 8aba312e, on the night of 2026-09-18 UTC. The sequence:

1. A create pass on 9aec4887 reported: "Two peers meet that letter and I left them out … because I judge that no person forms them from these pairs. If plausibility of the model is a gate, the section needs the sentence; if it is not, both are cases and the solver is short by two."
2. The user built a decision card, then ruled on the merits (02:04Z): "i saw StoredTies and FullRuns. they're out there but i would think of that when thinking of variations of the task. […] i wouldn't from these pairs, but i would if i thought more generally".
3. The user then asked the session to revisit the removed gates (02:10Z, 02:15Z): "ok wait let's revisit those old gates." The session's audit of where each old Coverage gate stands is in the closing summary below.
4. A first fix added a **Variations** rule to principles.md Cases:

    > - **Variations.** A branch that a person forms from a variant task alone is a case.
    >     - A branch that changes a scene claim is formed from the pairs.
    >     - A branch that changes rules alone is formed from a variant task: an input the pairs do not contain, on which the branch differs from the concept branch.
    >     - That the pairs alone do not suggest a branch is no ground to leave it out.
    >     - 2d0172a1

5. The user asked whether the procedure line alone would do (02:28Z), then ruled (02:29Z): "do not drop a peer for any raeson if it passes". The Variations rule was reverted out of principles.md, and procedure.md kept one line.
6. The user asked for a label (02:30Z, 02:31Z). The result: principles.md bolds "**case condition**", and procedure.md says "Do not drop a peer that meets the case conditions, for any reason."

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

The user scoped the fix (13:32Z): "scope is doc edits. let's discuss ways to resolve minmally ideally without changing principles.md". Then (13:34Z): "what if we just chose a more precise/conventional word than 'drop'". Then the user wrote the line himself (13:37Z):

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

The session audit at 2026-09-18T02:18Z (8aba312e) mapped each old gate to its status at that time. With the doc history added:

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

Session 631a6654 ran through the create and refine reports of four console workers (9f236235, 9f27f097, 9f41bd9c, 9f5f939b) and fixed what they raised. The edits are in the working tree, uncommitted. They are the state of the case rules as of 2026-09-22.

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

The Lean theory `theory/Theory/Core.lean` was changed to match: `Agree`, the two-sided `Equivalent`, `not_equivalent_of_witness`, and the deletion of `Iso` and `EquivalentAcross`.

### The two explicit lines added under Equivalence and under Terms

Four console passes argued that a peer whose divergence lies off the scene claims is not a separate claim.

1. **9f41bd9c create**, callout 6: "I read the Cases Equivalence condition more loosely than its text. Bounding the scrape by the tips that touch the ground and bounding it by the comb's lowest line are not equivalent — a comb floating one line above the ground separates them … I treated them as one claim stated two ways, since scene claim `comb` reconciles them; the tighter reading makes the peer a second branch."
2. **9f41bd9c refine**: "My earlier handoff had dropped three peers on one reason — they part from the concept case only off the scene. That reason is void, so `Below`, `Cast`, and `Lowest` all went in as branches."
3. **9f5f939b create**, callout 2: "The handbook gives no rule for a peer model whose divergence from the concept shows only on inputs that break a scene claim, and I spent most of the pass on it. The `Sight` choice point exists only because the Equivalence condition ranges over every input on which the concept case is defined, so a redundant-under-the-scene-claim test is formally a case; by that letter, the center-is-blank and arm-is-exactly-two tests are cases too, and I left them out."
4. **9f5f939b refine**, callout 3: "By the letter of the Equivalence condition, `Clear` is a case and so are the centre-is-blank and arm-is-exactly-two tests; I included the first and excluded the others on the ground that a case must be a way of seeing the task, and the principles do not state that test."

The user's rulings:

- 13:49Z: "i mean, i dont want agents arguing with the docs. yes the handbook answers it but can we make it more explicit?"
- 13:51Z: "you need to be ultrathoughtful about doc edits. the principles docs must not have gaps or inconsistencies and you have to be very careful"
- 13:54Z: "we need both of these lines? also add very brief comments about why we need to restate these"
- 13:57Z: "cite the specific sessions"

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

`9f41bd9c` refine reported that it read the commented-out content as instruction: "I read the principles update through `git diff`, saw two `* comment` blocks naming my earlier rulings, and acted on them."

The user added, at 14:32Z: "btw i may comment out restatement lines in principles to 'ablate'".

### Judgment is not grounds for omitting a case

procedure.md Develop step 3 gains:

> - If you find a model that meets the case conditions, add it.
>     - Your own judgment or taste is not grounds for omitting it.

This is the third statement of the 2026-09-17 ruling ("do not drop a peer for any raeson if it passes"), after principles.md's **case condition** label and procedure.md's "do not omit it from the solver for any reason".

### Fidelity as a case condition becomes Relational form

The third case condition was "**Fidelity.** The model has an encoding allowed by Fidelity." It becomes:

> - **Relational form.** Each claim the case's branches replace or add has a relational form.

procedure.md follows: "A peer dropped under Relational form requires in the review why no set of clauses states its claim." The Necessity rule in lib-protocol.md loses "Remove the case whose hypothesis has no relational form without that comp."

This edit came from 9ddd00f0 refine, which used `@approximated` on a branch. The user (02:41Z): "i remember a past discussion where we decided to allow it bc it was theoretically possible that the approximation only applied to a branch and the solver could not do with out it. but wdyt", then (02:49Z) "not sure we're on same page. how about this: under your proposal, would this be possible?", then (02:50Z) "ok i agree with you. propose edits", with the constraint (02:51Z) "minimal doc edits? ie prefer no change or change existing text over adding new cluases".

### The runner holds cases the solver does not write

`@derive` and `@store` directives enter solver-file.md. The runner holds the derived or stored reading of a parameter as a case, and the solver writes no branch for it. `@ignore: derive` and `@ignore: store` dismiss one. `@allow` is renamed `@ignore` (user, 21:13Z on 2026-09-21: "conventional/precise? ignore?"). The derive report holds a case only when the concept case reads the parameter.

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

Then (15:21Z): "this sounds right so far. wondering if we're retracing old paths. send agent to review the whole saga of this Case situation via git history and CC transcripts".

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

The assessment above went to the user at 15:30Z (session 631a6654). The user said "go" to a check of the guard rule over the approved corpus, and added (15:35Z): "let's think if "Guard" is the most precise/conventional name".

The check applied the guard test to every non-concept branch of the approved solvers. It flagged four branches, and the user had kept each of them:

- 2d0172a1's `Nest`, the branch behind the 2026-09-18 ruling "they're out there but i would think of that when thinking of variations of the task".
- 9bbf930d's `Channel`, `Exit`, and `Mouth`, the weaker readings of `pipes` that raised the open-ended lattice on 2026-09-18.

A test on the form of a branch thus failed the same test as Exercised: it removed cases that the corpus held. In the record, what separated the kept branches from the unwanted ones was their origin. `Nest`, 9f5f939b's `Clear`, and the three pipe readings came from the task, from a variation a person imagines, or from the reference solver. The blank-center and two-cell-arm tests of 9f5f939b came from a session that enumerated the tests of its own program: "an2.py runs all eight combinations of those tests". On the name, "guard" is the conventional word for the added literal, and the branch is a refinement of the concept branch.

The session proposed a bound on where a case comes from, in place of the guard rule, with the user's N=1 cutoff as that bound. The user ruled (15:44Z):

> "1. the N cutoff idea, yes, that is what i meant.
> 2. this is too low level for me to decide"

Item 2 was whether the audit should flag refinements. The session decided that the flag does not exist, because a session would read it as one more ground to drop a case. The guard rule was not written into any doc.

### The goal is restated

The user stopped the wording twice:

- 15:48Z: "i see you're jumping to "patching the bug" mode. first we need to establish what the docs should accomplish"
- 15:51Z: "this is "patch the bug" mode. you're thinking too low level. we need the docs to be in their best form. don't just patch. refactor. rethink the additions we've been adding. consider placement carefully. where does each rule or step constraint belong if they are needed"

A draft goal that defined "a reading" was retracted, because a goal stated as a property of a case gives a session a property to argue. The user on the next draft (16:04Z): "warm to this but "session" is not defined, and im concerned about "the model a person first sees" bc thats caused trouble. and this might be too vague now too. or at least ungrounded. the goal is to have things that the rest of the docs say to make." Then (16:09Z):

> "so my own mental model is: principles gives the rules and general constraints. procedure gives the procedure on what to actually include based on , well, procedure. it's a "subset" of what principles defines, and operational bc it's supposed to be practical (and secondarily, "i thought of this by myself and not from reading the code and tweaking it" correspondings to "a possible reading" that is likely to be a new "thing"). aligned?"

The goal was written into principles.md at about 17:28Z, replacing the Concept and Coverage aims of da30cfe. At 21:22Z "corpus" became "solvers". The user had written (21:21Z): ""corpus" can be replaced with a self-explanatory phrase." The text at the end of 2026-09-22:

> ## The goal
> - The goal is for the solvers to enumerate the models that fit the tasks.
>     - A solver holds the concept case.
>     - It holds a case for every other model the pass forms that meets the case conditions.
>         * comment
>             - A model the pass forms is a case whether or not a person sees the task that way.

The Terms line under Relational form, with its session-citing comments, was removed at 21:00Z, under the user's "13 ok" (20:42Z) on the item "remove the Terms line, consolidate the session comments".

### Where cases come from, in the record

The user asked for evidence (16:32Z): "send agent to research how solver agents (all 3) actually come up with cases, we need grounding", and (16:34Z) "wait, how about historical too, like sample across time". Two agents wrote `.scratch/review/case-origins.md` and `.scratch/review/case-origins-history.md`.

- Over sixteen recent tasks (waves 76 to 92), 300 formed models: 152 were formed after the program existed and 45 before it. The sources included the pass's own program (65 models, 11 kept), imagined variations (61, 8 kept), probe output (59, 17 kept), and the pairs (51, 24 kept).
- In the history sample, cases moved to the first write of the solver in July 2026, with no doc asking for it, and the user stopped being a source of models after 2026-07-09.

The user then asked (16:52Z): "Well this is now making me wonder what if we made analyze its own phase, and create focuses on impl", and (16:57Z) "I only care about the goals and the principles . Cost in impl not a reason." Under a separate phase, the N=1 cutoff holds by construction: the create session reads the list and forms no model of its own. The user set the terms (17:03Z, 17:06Z):

> "How about we trial as an experiment. Trial the analyze phase. On new tasks. Ack"

> "No I mean as an experiment. No create phase (also verify facts in compaction summary before using them). I don’t want to commit to it"

The rule that no model formed after Analyze is a case stayed out of the docs. Develop step 3 kept "Look for peer models".

## 2026-09-22 — the Analyze trial

The trial ran into the evening of 2026-09-22 local time. A timestamp from 00:00Z on is on 2026-09-23 UTC.

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

From 20:52Z the trial moved to an agent file. The user asked that the agent see only the description of solvers (20:52Z: "the analyze agent should not see style or solver-file.md ... should it? it just needs to see the desription not the impl of solvers."), and that it be independent of the console (21:43Z: "idk what s going on w the console but lets break away from it. this analyze agent should be standalone."; 21:49Z: "the analyze agnet is standalone as in you should be able to launch it as a subagent"). `scripts/context.py --write` generates `.claude/agents/analyze.md` from `prompts/agents/analyze.md`: the principles, the keywords, and the Analyze operation. The agent file is not tracked by git. The agent ran on Opus 5.5.

At 21:26Z, in a review of the agent file, a third standing was added to the Analyze step: "A model that fits every pair and has no such input: the model it is equivalent to, and why every assignment of one agrees with one of the other." The briefed trials had had two standings only: the pair a model fails, or a witness.

The trial was a fix loop. After each run, the agent answered a question on friction, an inspector agent read its transcript, and the session fixed the issues before the next run. When the session launched a1570a43 before fixing the issues of a09f6c25, the user said (22:41Z): "we were supposed to do one at a time to fix issues".

The report's reader is the create agent. The user (00:35Z): "the consumer is the create agent. what should happen to make the report serve the create agent".

### a09f6c25 and a1570a43: the concept is declared undefined

Both first runs, at 22:12Z to 22:21Z, made the concept case undefined on a class of inputs, and so made every model that differs only there equivalent to it.

1. **a09f6c25.** The concept said: "A figure with no axis, or with axes that map to different colors, is outside the concept. There the concept is undefined." The reference solver's check order and three other classifications then "agree with the concept vacuously and are equivalent to it."
2. **a1570a43.** The concept gave an output only when the shape's box fits the frame's interior exactly. The agent's friction reply:

    > "Agree counts two models as agreeing when either one gives no output. My concept gives no output unless the shape fits the inside area exactly, so every placement model became equivalent to it. If I had stated the concept as a rule defined on every input, such as "center the shape", the same models would split into separate cases. The documents do not say how far the concept should be defined, so the choice of concept wording decides which models become cases."

### The Agree clause is traced

The user asked (22:47Z): "send agent to brief you on details about the prior trials bc they were successful and this wasnt, and that should inform what fix to make". The brief found three differences. The briefed runs had no equivalence standing. They had the solver-file template, whose `@relaxed` line makes a witness that breaks a scene claim normal. They ran at effort high. The user (22:57Z):

> "set effort to high
>
> concerned you are proposing "patch the bug" solutions
>
> ultrathink on the best resolutions, keeping in mind best practices i've been asking for repeatedly"

A search of the transcript found the origin of "or one of them gives none". The clause was written at 04:36:38Z. It answered `9f236235` create's callout 3, which the user had pointed to at 04:24Z ("9f236235 create agent had complaints about the principles doc"): a strengthening of the concept case "diverges only by being undefined where the concept case is defined. Read literally, that is a divergence". The user's go was "go, then review doc for consistency" (04:36Z). No later user message revisited the clause.

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

The user (23:55Z): "6 as you know, edits to the principle doc must be very thoughtfully made according to the standards i've repeatedly asked you for. ultrathink then propose". The line was rewritten, and its second sub-bullet was removed because the Choice points section already states it:

> - **concept case**: the case whose model the concept statement describes.
>     - At the assignment stored for this task or a sibling task, its model is defined on every input the generator produces in that task.

The user (00:01Z): "only apply", then, on lines found under `candidate`: "this is a symptom of general lack of discipline and all existing changes to principles.md must now be carefully reviewed". The review moved the alt lines back to solver-file.md. The user left the other findings (00:07Z): "rest of items: confirm they are minor noise that would not interfere. if so, leave them. and * comment lines are excluded anyway."

### The reruns, and the scene-claim clause moves

The a09f6c25 rerun (00:09Z) found six models with probed witnesses and five choice points. The concept was undefined on a shape with no axis or with two axis classes, and three models were equivalent on that ground. Its friction reply:

> "The documents do not say whether the concept case gives an output for inputs that break a scene claim, such as a shape with no axis or a plus with two axis classes."

At 00:17Z the phrase "whether or not the input breaks a scene claim" moved from the Equivalence line to the reach line, under the 23:37Z approval. The reach line became:

> - At the assignment stored for this task or a sibling task, its model is defined on every input the generator produces in that task, whether or not the input breaks a scene claim.

The Equivalence line kept "Agreement on every input the generator produces does not establish equivalence either: the comparison ranges over every input on which the concept case is defined."

The a1570a43 rerun (00:18Z) made the concept center the shape, with the rounding as an open parameter. Exact fit became a peer, equivalent to the concept as a strengthening. Four models got probed witnesses.

### a04b2602, and the concept slot

a04b2602 ran at 00:28Z, and again cleanly at 00:59Z after a run that read an earlier run's files. Both reached the same three fitting models as the briefed free run of 18:07Z, with the concept written before the reference solver was read.

For the create agent, the Analyze steps gained slugs on claims, a witness file at `.scratch/<task_id>/witnesses.json` in the witness-file shape, and per witness the scene claim it breaks and the assignment it stands at. The user limited the scope (00:51Z): "don't touch 6 7 scope is only analysis".

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

The user, at 2026-09-23T02:18Z: "go review the cases saga, we may be retracing again. eg we used to have a reparameterization clause". At 02:20Z the user added: "there was a brief giving the history. if you dont know where it is ask an agent. it looks like you don't know, the file path got lost to compaction. send the agent to look through our transcript before compaction for the file path. and then lets move it into docs so we dont lose it".

This document was at `.scratch/9bbf930d/case-rule-history.md`, which git ignores. At 2026-09-23T02:24Z it moved to `docs/wf-solver/case-rule-history.md`, and its relative dates were replaced with absolute ones.

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

The user, at 2026-09-23T02:26Z:

> "extend, send agent to extend based on transcript
> ---
> determine what our goal is to confirm alignment before thinking of resolutions"

### The case-membership edits at the end of 2026-09-22

All are in the working tree, uncommitted.

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
